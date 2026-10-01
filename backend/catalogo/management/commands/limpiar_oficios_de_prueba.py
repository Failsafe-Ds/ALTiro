"""Quita de la base de demostración los oficios que dejaron las pruebas de navegador (ADR-028, punto 6).

Las verificaciones de QA del S3 (RNF-18 con Playwright, y el script ``qa3``)
dieron de alta oficios desde la pantalla de comercial contra la pila de
demostración y los dejaron desactivados: ``oficio_prueba_s3_<motor>_<n>`` y
``oficio_qa3_<n>``. No salen en la búsqueda ni en la postulación (solo se
listan oficios activos), pero sí en la pantalla de catálogo de comercial.

Resguardos:

- **Por defecto no borra nada**: lista lo que quitaría. Borra solo con
  ``--confirmo``.
- Solo oficios cuyo código calza **exactamente** con ``PATRONES`` y que están
  **desactivados**; nunca toca otro oficio.
- Borra el oficio con sus servicios y modalidades en una transacción por
  oficio. Si algo los referencia (un maestro, un documento o un servicio de un
  maestro: ``PROTECT``), lo deja intacto y lo informa.
- Idempotente: una segunda ejecución no encuentra nada.
- No escribe la bitácora (ADR-010; mismo criterio que ``cargar_datos_demo``).
  Las entradas que ya existen sobre esos oficios **se conservan**: la
  bitácora no se edita ni se borra.

Uso dentro del contenedor:
    python manage.py limpiar_oficios_de_prueba            # solo lista
    python manage.py limpiar_oficios_de_prueba --confirmo # borra
"""
import logging
import re

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import ProtectedError

from catalogo.models import Oficio, Servicio, ServicioModalidad

logger = logging.getLogger(__name__)

PATRONES = (
    re.compile(r"oficio_prueba_s3_(chromium|firefox)_\d+"),
    re.compile(r"oficio_qa3_\d+"),
)


def es_de_prueba(codigo):
    return any(patron.fullmatch(codigo) for patron in PATRONES)


def candidatos():
    """Oficios desactivados cuyo código calza exactamente con un patrón de prueba."""
    return [o for o in Oficio.objects.filter(activo=False).order_by("codigo") if es_de_prueba(o.codigo)]


def limpiar(oficios):
    """Borra cada oficio con sus servicios; devuelve ``(borrados, conservados)`` con sus códigos."""
    borrados, conservados = [], []
    for oficio in oficios:
        try:
            with transaction.atomic():
                servicios = Servicio.objects.filter(oficio=oficio)
                ServicioModalidad.objects.filter(servicio__in=servicios).delete()
                servicios.delete()
                oficio.delete()
            borrados.append(oficio.codigo)
        except ProtectedError:
            conservados.append(oficio.codigo)
    return borrados, conservados


class Command(BaseCommand):
    help = "Lista (o borra con --confirmo) los oficios desactivados que dejaron las pruebas de navegador."

    def add_arguments(self, parser):
        parser.add_argument("--confirmo", action="store_true", help="Borra de verdad; sin esta opción solo lista.")

    def handle(self, *args, confirmo=False, **opciones):
        oficios = candidatos()
        if not oficios:
            self.stdout.write("No hay oficios de prueba que quitar.")
            return
        if not confirmo:
            self.stdout.write(f"Se quitarían {len(oficios)} oficios de prueba (desactivados):")
            for oficio in oficios:
                self.stdout.write(f"  - {oficio.codigo}")
            self.stdout.write("No se borró nada. Para borrarlos: limpiar_oficios_de_prueba --confirmo")
            return
        borrados, conservados = limpiar(oficios)
        logger.info("Limpieza de oficios de prueba por comando de consola: %s borrados, %s conservados.",
                    len(borrados), len(conservados))
        self.stdout.write(f"Oficios de prueba borrados: {len(borrados)}.")
        if conservados:
            self.stdout.write("Se conservaron porque algo los usa: " + ", ".join(conservados))
