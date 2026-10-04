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

Con ``--con-cuentas`` (ADR-028) también crea maestros publicados, clientes y
tickets ficticios para probar el flujo completo (``busqueda.cuentas_demo``).
Las cuentas con ingreso reciben una contraseña aleatoria que se imprime **una
sola vez** en la consola (nunca en el registro). Las existentes conservan la
suya salvo ``--restablecer-contrasenas``. También crea una cuenta
administrativa por rol administrativo (ADR-028, Enmienda E-1).

Con ``--maestros-por-comuna [N]`` (ADR-028, Enmienda E-1; por defecto 3)
garantiza al menos N maestros ficticios publicados con comuna base en cada
comuna, o solo en las de ``--region R``, o solo en las ``--comuna C`` (se puede
repetir; ADR-028, E-2) (``busqueda.maestros_por_comuna``), para probar los
filtros de la búsqueda. N va de 1 a 99. Esos maestros no tienen ingreso.

Uso dentro del contenedor:
    python manage.py cargar_datos_demo
    python manage.py cargar_datos_demo --con-cuentas [--restablecer-contrasenas]
    python manage.py cargar_datos_demo --maestros-por-comuna [N] [--region R] [--comuna C ...]
"""
import logging
import time

from django.core.management.base import BaseCommand, CommandError
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
    help = "Carga servicios FICTICIOS de demostración en el catálogo (idempotente); con --con-cuentas, también cuentas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--con-cuentas", action="store_true", dest="con_cuentas",
            help="Crea también maestros publicados, clientes y tickets ficticios (ADR-028).",
        )
        parser.add_argument(
            "--restablecer-contrasenas", action="store_true", dest="restablecer",
            help="Con --con-cuentas: da una contraseña nueva a las cuentas demo que ya existen.",
        )
        parser.add_argument(
            "--maestros-por-comuna", type=int, nargs="?", const=3, default=None, dest="por_comuna", metavar="N",
            help="Garantiza al menos N maestros ficticios publicados con comuna base en cada comuna (por defecto 3).",
        )
        parser.add_argument(
            "--region", type=int, default=None, metavar="CODIGO",
            help="Con --maestros-por-comuna: solo las comunas de esa región (código CUT, por ejemplo 8).",
        )
        parser.add_argument(
            "--comuna", type=int, action="append", default=None, dest="comunas", metavar="CODIGO",
            help="Con --maestros-por-comuna: solo esa comuna (código CUT, por ejemplo 8101). Se puede repetir.",
        )

    def handle(self, *args, con_cuentas=False, restablecer=False, por_comuna=None, region=None, comunas=None,
               **opciones):
        if restablecer and not con_cuentas:
            raise CommandError("--restablecer-contrasenas solo se usa junto con --con-cuentas.")
        if (region is not None or comunas) and por_comuna is None:
            raise CommandError("--region y --comuna solo se usan junto con --maestros-por-comuna.")
        creados = cargar_datos_demo()
        logger.info("Datos de demostración del catálogo cargados por comando de consola: %s servicios nuevos.", creados)
        self.stdout.write(f"Servicios de demostración creados: {creados} (datos ficticios, rotulados «(demo)»).")
        if con_cuentas:
            self._cuentas(restablecer)
        elif por_comuna is None:
            self.stdout.write("Para crear también maestros, clientes y tickets con los que ingresar: agrega --con-cuentas.")
        if por_comuna is not None:
            self._por_comuna(por_comuna, region, comunas)

    def _por_comuna(self, n, region, comunas=None):
        from busqueda.maestros_por_comuna import cargar_maestros_por_comuna

        inicio = time.monotonic()
        try:
            resumen = cargar_maestros_por_comuna(n, region=region, comunas=comunas, avance=self.stdout.write)
        except ValueError as error:
            raise CommandError(str(error)) from None
        segundos = time.monotonic() - inicio
        logger.info(
            "Maestros de demostración por comuna cargados por comando de consola: %s maestros nuevos en %s comunas.",
            resumen.maestros, resumen.comunas,
        )
        self.stdout.write(
            f"Maestros por comuna (datos ficticios, sin ingreso): {resumen.maestros} nuevos en {resumen.comunas} comunas, "
            f"{resumen.licencias} licencias SEC, {resumen.tickets} tickets y {resumen.evaluaciones} evaluaciones; "
            f"mínimo por comuna: {resumen.minimo}; {segundos:.0f} s."
        )
        if resumen.faltantes:
            raise CommandError(f"Comunas con menos de {n} maestros: {resumen.faltantes[:20]}.")

    def _cuentas(self, restablecer):
        from busqueda.cuentas_demo import cargar_cuentas_demo

        try:
            maestros, tickets, cuentas = cargar_cuentas_demo(restablecer=restablecer)
        except ValueError as error:
            raise CommandError(str(error)) from None
        # El registro solo lleva conteos: nunca identificadores ni contraseñas.
        logger.info(
            "Cuentas de demostración cargadas por comando de consola: %s maestros nuevos, %s tickets nuevos.",
            maestros, tickets,
        )
        self.stdout.write(f"Maestros de demostración nuevos: {maestros}. Tickets de demostración nuevos: {tickets}.")
        if not cuentas:
            return
        self.stdout.write("Cuentas de demostración (datos ficticios). Ingresa en «Ingresar» con:")
        for cuenta in cuentas:
            self.stdout.write(f"  - {cuenta.rol}: {cuenta.identificador}")
        claves = {c.contrasena for c in cuentas if c.contrasena}
        if claves:
            self.stdout.write(f"Contraseña de las cuentas nuevas o restablecidas: {claves.pop()}")
            self.stdout.write("  Anótala ahora: no se guarda en ningún archivo ni registro y no se vuelve a mostrar.")
        conservadas = [c.identificador for c in cuentas if not c.contrasena]
        if conservadas:
            self.stdout.write(
                "Conservan la contraseña que tenían: " + ", ".join(conservadas)
                + ". Para darles una nueva: cargar_datos_demo --con-cuentas --restablecer-contrasenas."
            )
