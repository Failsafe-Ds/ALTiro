"""Planificador del actor Sistema (ADR-016, punto 1; cierra DA-06; DA-16).

Corre las tareas idempotentes de ``expediente.tareas``, ``autorizacion.tareas`` y el cierre
de tickets vencidos (``tickets.transiciones.cerrar_vencidos``, ADR-016 E-1) cada
``ALTIRO_PLANIFICADOR_INTERVALO_SEGUNDOS`` (por defecto 300, ADR-016 E-1):

    python manage.py planificador            # bucle (servicio "planificador")
    python manage.py planificador --una-vez  # una corrida (pruebas y operación manual)

- Cada tarea está protegida: si una falla, se registra el error con la traza
  segura (``comun.registros.FiltroTrazasSeguras``, en el handler de consola) y
  las demás siguen.
- Cada corrida deja un evento con los conteos, sin datos personales (RNF-22,
  en parte).
- Apagado limpio con SIGTERM o SIGINT: termina la tarea en curso y sale.
- Mientras espera, renueva un archivo de latido que usa el healthcheck del
  servicio en ``docker-compose.yml``.
- No aplica migraciones: las aplica ``app`` antes de declararse sana.
"""
import logging
import signal
import tempfile
import threading
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connection, connections
from django.utils import timezone

from autorizacion import tareas as tareas_autorizacion
from expediente import tareas
from tickets import transiciones as tareas_tickets

logger = logging.getLogger("expediente.planificador")

# (nombre del conteo, tarea). El orden es el de ADR-016, punto 1.
TAREAS = (
    ("avisos_creados", tareas.emitir_avisos_por_vencer),
    # ADR-016 E-1: cierre de tickets pendientes vencidos (RF-21, RF-22, RF-24).
    ("tickets_cerrados", tareas_tickets.cerrar_vencidos),
    ("accesos_denegados_purgados", tareas_autorizacion.purgar_accesos_denegados),
    ("archivos_huerfanos_borrados", tareas.limpiar_archivos_huerfanos),
)

# Latido para el healthcheck: se renueva al menos cada LATIDO_SEGUNDOS.
ARCHIVO_LATIDO = Path(tempfile.gettempdir()) / "altiro-planificador.latido"
LATIDO_SEGUNDOS = 60


def _descartar_conexion_inservible():
    """Descarta una conexión inservible (p. ej., la base se reinició) u obsoleta.

    Fuera de un bloque atómico: el planificador corre en autocommit; dentro de
    uno (pruebas) cerrar la conexión rompería la transacción en curso.
    """
    if not connection.in_atomic_block:
        close_old_connections()


def correr_tareas(ahora=None):
    """Corre todas las tareas una vez. Devuelve (conteos, nombres de las tareas que fallaron)."""
    ahora = ahora or timezone.now()
    conteos = {}
    fallidas = []
    for nombre, tarea in TAREAS:
        _descartar_conexion_inservible()
        try:
            conteos[nombre] = tarea(ahora)
        except Exception:  # noqa: BLE001 — la falla de una tarea no detiene las demás.
            logger.exception("Planificador: falló la tarea %s.", nombre)
            fallidas.append(nombre)
    _descartar_conexion_inservible()
    detalle = " ".join(f"{nombre}={valor}" for nombre, valor in conteos.items())
    logger.info("Planificador: corrida terminada. %s tareas_fallidas=%s", detalle, len(fallidas))
    return conteos, fallidas


def _latido():
    try:
        ARCHIVO_LATIDO.touch()
    except OSError:
        logger.warning("Planificador: no se pudo renovar el archivo de latido.")


class Command(BaseCommand):
    help = "Corre las tareas del actor Sistema (avisos de vencimiento, purga y limpieza) cada cierto intervalo."

    def add_arguments(self, parser):
        parser.add_argument("--una-vez", action="store_true", help="Corre las tareas una sola vez y termina.")

    def handle(self, *args, una_vez=False, **opciones):
        if una_vez:
            _, fallidas = correr_tareas()
            if fallidas:
                raise CommandError(f"Fallaron {len(fallidas)} tareas; revisa el registro del planificador.")
            return
        self._bucle(settings.ALTIRO_PLANIFICADOR_INTERVALO_SEGUNDOS)

    def _bucle(self, intervalo):
        parar = threading.Event()

        def detener(numero, _marco):
            logger.info("Planificador: señal %s recibida; se detiene al terminar la corrida en curso.", numero)
            parar.set()

        signal.signal(signal.SIGTERM, detener)
        signal.signal(signal.SIGINT, detener)
        logger.info("Planificador iniciado. intervalo_segundos=%s", intervalo)
        while not parar.is_set():
            _latido()
            correr_tareas()
            siguiente = time.monotonic() + intervalo
            while not parar.is_set():
                restante = siguiente - time.monotonic()
                if restante <= 0:
                    break
                _latido()
                parar.wait(min(restante, LATIDO_SEGUNDOS))
        connections.close_all()
        logger.info("Planificador detenido.")
