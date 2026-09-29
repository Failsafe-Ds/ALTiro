"""Genera el volumen de prueba de RNF-01 y RNF-03 con datos **FICTICIOS** (propuesta del S4, §2; ADR-022, punto 8).

**Úsese solo en una pila aparte**, nunca en la de la demostración::

    ALTIRO_HTTP_PORT=8080 ALTIRO_HTTPS_PORT=8443 \
    DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost:8443,https://127.0.0.1:8443 \
    docker compose -p altiro-volumen up -d --build
    docker compose -p altiro-volumen exec app \
        python manage.py generar_volumen_prueba --semilla 42 --confirmo-datos-ficticios

Qué crea (informe §3 del CLAUDE.md, "volumen de prueba"):

- 100 maestros con expediente ``aprobado``, comuna base y cobertura en el
  Gran Concepción (provincia de Concepción y, a veces, Arauco), foto (JPEG
  sintético de un color, procesado con ``perfil.fotos``) y agenda semanal;
- 300 servicios publicados (3 por maestro), solo de oficios **no regulados**:
  los regulados exigirían licencias SEC con archivo cifrado, que este comando
  no fabrica (supuesto de este incremento);
- los servicios del catálogo de demostración que falten
  (``catalogo.management.commands.cargar_datos_demo``, también ficticios).

Pendiente: los **1.000 tickets** se agregan cuando exista la app ``tickets``
(S4, incremento 4) en ``generar_tickets``; los 5.000 mensajes, en el S5.

Rotulado y resguardos:

- Nombres "Maestro Ficticio NNN (datos de prueba)", RUT sintéticos a partir
  de 50.000.000, teléfonos "+56 9 0000 0NNN", sin correo.
- Contraseñas **inutilizables** (``set_unusable_password``): nadie puede
  entrar con estas cuentas.
- Se niega a correr sin ``--confirmo-datos-ficticios``.
- Idempotente por semilla: cada maestro se identifica por su RUT, derivado de
  la semilla y de su número; si ya existe, no se toca. Cada maestro se crea en
  su propia transacción.
- No escribe la bitácora (igual que ``cargar_datos_demo``): no es una acción
  de una persona de la aplicación.
"""
import io
import logging
import random
import secrets

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image

from catalogo.management.commands.cargar_datos_demo import cargar_datos_demo
from catalogo.models import Servicio, ServicioModalidad
from expediente.models import EstadoExpediente, Expediente, OficioMaestro
from identidad import servicios as identidad
from identidad.models import PerfilMaestro
from perfil import fotos
from perfil.models import Cobertura, Disponibilidad, PerfilPublico, ServicioMaestro

logger = logging.getLogger(__name__)

MAESTROS = 100
SERVICIOS_POR_MAESTRO = 3
RUT_BASE = 50_000_000
# Provincia de Concepción (81xx) y algunas de Arauco (82xx), CUT 2018 (ADR-012).
COMUNAS_BASE = [8101, 8102, 8103, 8104, 8105, 8106, 8107, 8108, 8109, 8110, 8111, 8112]
COMUNAS_EXTRA = COMUNAS_BASE + [8201, 8202, 8203, 8205]
MOTIVO = "Datos ficticios del volumen de prueba (RNF-01, RNF-03)."


def rut_ficticio(semilla, numero):
    """RUT sintético válido, distinto por semilla y número, sin puntos: 5x.xxx.xxx-DV."""
    cuerpo = RUT_BASE + (semilla % 10_000) * 1_000 + numero
    suma, factor = 0, 2
    for digito in reversed(str(cuerpo)):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    dv = 11 - suma % 11
    return f"{cuerpo}-{'0' if dv == 11 else 'K' if dv == 10 else dv}"


def _foto(azar):
    salida = io.BytesIO()
    color = tuple(azar.randint(40, 220) for _ in range(3))
    Image.new("RGB", (320, 320), color).save(salida, format="JPEG", quality=80)
    return fotos.variantes(salida.getvalue())


def _servicios_por_oficio():
    """``{oficio: [Servicio]}`` de los oficios **no regulados** activos con servicios activos."""
    por_oficio = {}
    for servicio in Servicio.objects.filter(activo=True, oficio__activo=True, oficio__regulado=False).select_related(
        "oficio"
    ).order_by("oficio__orden", "orden", "pk"):
        if ServicioModalidad.objects.filter(servicio=servicio).exists():
            por_oficio.setdefault(servicio.oficio, []).append(servicio)
    return por_oficio


def _elegir_servicios(azar, por_oficio):
    oficios = list(por_oficio)
    elegidos = azar.sample(oficios, 2)
    while sum(len(por_oficio[o]) for o in elegidos) < SERVICIOS_POR_MAESTRO:
        elegidos.append(azar.choice([o for o in oficios if o not in elegidos]))
    candidatos = [s for o in elegidos for s in por_oficio[o]]
    servicios = azar.sample(candidatos, SERVICIOS_POR_MAESTRO)
    return {s.oficio for s in servicios}, servicios


def _agenda(azar):
    bloques = []
    for dia in sorted(azar.sample(range(1, 8), azar.randint(2, 5))):
        inicio = azar.randint(14, 36) * 30  # 07:00 a 18:00
        fin = min(inicio + azar.randint(4, 12) * 30, 1440)
        bloques.append((dia, inicio, fin))
    return bloques


def crear_maestro(semilla, numero, por_oficio):
    """Crea el maestro ficticio ``numero``; devuelve ``False`` si ya existía."""
    rut = rut_ficticio(semilla, numero)
    if PerfilMaestro.objects.filter(rut=rut.replace("-", "")).exists():
        return False
    azar = random.Random(f"{semilla}-{numero}")
    variantes = _foto(azar)
    nombre_foto = fotos.guardar(variantes)
    try:
        with transaction.atomic():
            usuario = identidad.crear_cuenta_maestro(
                nombre=f"Maestro Ficticio {numero + 1:03d} (datos de prueba)",
                telefono=f"+56 9 0000 {numero:04d}",
                rut=rut,
                contrasena=secrets.token_urlsafe(24),
            )
            usuario.set_unusable_password()
            usuario.save(update_fields=["password"])
            oficios, servicios = _elegir_servicios(azar, por_oficio)
            OficioMaestro.objects.bulk_create([OficioMaestro(maestro_id=usuario.pk, oficio=o) for o in oficios])
            ServicioMaestro.objects.bulk_create(
                [
                    ServicioMaestro(
                        maestro_id=usuario.pk,
                        servicio=s,
                        modalidad=ServicioModalidad.objects.filter(servicio=s).order_by("modalidad").first().modalidad,
                        monto=azar.randint(10, 120) * 1000,
                    )
                    for s in servicios
                ]
            )
            base = azar.choice(COMUNAS_BASE)
            extra = azar.sample([c for c in COMUNAS_EXTRA if c != base], azar.randint(1, 4))
            Cobertura.objects.bulk_create(
                [Cobertura(maestro_id=usuario.pk, comuna_id=base, es_base=True)]
                + [Cobertura(maestro_id=usuario.pk, comuna_id=c, es_base=False) for c in extra]
            )
            Disponibilidad.objects.bulk_create(
                [
                    Disponibilidad(maestro_id=usuario.pk, dia_semana=d, inicio_min=i, fin_min=f)
                    for d, i, f in _agenda(azar)
                ]
            )
            PerfilPublico.objects.filter(perfil_maestro_id=usuario.pk).update(
                foto=nombre_foto, foto_actualizada_en=timezone.now()
            )
            Expediente.objects.filter(perfil_maestro_id=usuario.pk).update(
                estado=EstadoExpediente.APROBADO, estado_motivo=MOTIVO, estado_cambiado_en=timezone.now()
            )
    except BaseException:
        fotos.borrar(nombre_foto)
        raise
    return True


def generar_tickets(semilla):
    """Pendiente (S4, incremento 4): 1.000 tickets ficticios cuando exista la app ``tickets``."""
    return 0


class Command(BaseCommand):
    help = "Genera el volumen de prueba FICTICIO (100 maestros, 300 servicios). Solo para una pila aparte."

    def add_arguments(self, parser):
        parser.add_argument("--semilla", type=int, required=True)
        parser.add_argument("--confirmo-datos-ficticios", action="store_true", dest="confirmo")
        # Solo para las pruebas automáticas; el volumen del informe es 100.
        parser.add_argument("--maestros", type=int, default=MAESTROS, help="Cantidad de maestros (por defecto 100).")

    def handle(self, *args, semilla, confirmo, maestros, **opciones):
        if not confirmo:
            raise CommandError(
                "Este comando crea datos ficticios de volumen. Úsalo solo en una pila aparte "
                "(docker compose -p altiro-volumen) y confírmalo con --confirmo-datos-ficticios."
            )
        if not 1 <= maestros <= 999:
            raise CommandError("La cantidad de maestros debe estar entre 1 y 999.")
        cargar_datos_demo()
        por_oficio = _servicios_por_oficio()
        if len(por_oficio) < 2:
            raise CommandError("El catálogo no tiene servicios suficientes de oficios no regulados.")
        creados = sum(crear_maestro(semilla, numero, por_oficio) for numero in range(maestros))
        tickets = generar_tickets(semilla)
        logger.info("Volumen de prueba ficticio generado: %s maestros nuevos, %s tickets.", creados, tickets)
        self.stdout.write(
            f"Maestros ficticios nuevos: {creados} de {maestros} (semilla {semilla}). "
            f"Tickets: {tickets} (pendiente hasta la app tickets, S4 incremento 4)."
        )
