"""Carga servicios de DEMOSTRACIÓN en el catálogo (datos FICTICIOS; RF-36 solo para la demo).

- Nombres y precios de referencia **inventados**, rotulados "(demo)" en el
  nombre, para mostrar la prueba de concepto. No son precios de mercado ni
  datos del informe.
- Idempotente: crea solo los servicios (oficio, nombre) que faltan; nunca
  modifica ni borra lo que ya existe, incluidos los cambios de comercial.
- Se ejecuta a mano; ninguna migración lo llama.
- No escribe la bitácora: igual que la carga inicial del CSV de oficios, es una
  carga de datos de demostración desde la consola, no una acción de una persona
  de comercial en la aplicación; la aplicación no puede identificar a quien
  ejecuta el comando y no se inventa un autor ni se usa el actor Sistema
  (ADR-010). Emite un evento de aplicación con el conteo.

Uso dentro del contenedor:
    python manage.py cargar_datos_demo
"""
import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Max

from catalogo.models import Modalidad, Oficio, Servicio, ServicioModalidad

logger = logging.getLogger(__name__)

ROTULO = " (demo)"
T, H = Modalidad.POR_TRABAJO, Modalidad.POR_HORA

# (código del oficio, nombre sin rótulo, {modalidad: precio de referencia ficticio})
SERVICIOS_DEMO = (
    ("gas", "Instalación de cocina a gas", {T: 35000}),
    ("gas", "Revisión de calefont", {T: 25000, H: 15000}),
    ("electricidad", "Instalación de enchufe", {T: 20000}),
    ("electricidad", "Revisión de tablero eléctrico", {H: 18000}),
    ("gasfiteria", "Cambio de llave de agua", {T: 18000}),
    ("gasfiteria", "Destape de cañería", {T: 30000, H: 15000}),
    ("carpinteria", "Arreglo de puerta", {T: 25000}),
    ("carpinteria", "Armado de mueble", {H: 12000}),
    ("pintura", "Pintura de habitación", {T: 80000}),
    ("pintura", "Retoque de muros", {H: 10000}),
    ("albanileria", "Reparación de muro", {T: 60000}),
    ("cerrajeria", "Apertura de puerta", {T: 20000}),
    ("cerrajeria", "Cambio de chapa", {T: 25000}),
    ("jardineria", "Corte de pasto", {H: 10000}),
    ("jardineria", "Poda de arbustos", {T: 30000}),
)


def cargar_datos_demo():
    """Crea los servicios de demostración que faltan. Devuelve cuántos creó."""
    creados = 0
    with transaction.atomic():
        oficios = {oficio.codigo: oficio for oficio in Oficio.objects.select_for_update()}
        for codigo, nombre, modalidades in SERVICIOS_DEMO:
            oficio = oficios.get(codigo)
            nombre = nombre + ROTULO
            if oficio is None or Servicio.objects.filter(oficio=oficio, nombre=nombre).exists():
                continue
            orden = (Servicio.objects.filter(oficio=oficio).aggregate(m=Max("orden"))["m"] or 0) + 1
            servicio = Servicio.objects.create(oficio=oficio, nombre=nombre, orden=orden)
            ServicioModalidad.objects.bulk_create(
                [ServicioModalidad(servicio=servicio, modalidad=m, precio_referencia=p) for m, p in modalidades.items()]
            )
            creados += 1
    return creados


class Command(BaseCommand):
    help = "Carga servicios FICTICIOS de demostración en el catálogo (idempotente)."

    def handle(self, *args, **opciones):
        creados = cargar_datos_demo()
        logger.info("Datos de demostración del catálogo cargados por comando de consola: %s servicios nuevos.", creados)
        self.stdout.write(f"Servicios de demostración creados: {creados} (datos ficticios, rotulados «(demo)»).")
