"""API de control de gestión (HU-22, RF-38, CA-22.1, CA-22.2; ADR-026, E-6; propuesta del S5, §3.3).

- ``GET /api/gestion/indicadores?desde=&hasta=``: los tres indicadores base.
- ``GET /api/gestion/exportacion?desde=&hasta=``: CSV agregado (adjunto).

Solo el rol ``control_gestion`` (``requiere_rol``: sin el rol, 403 registrado).
Período de 31 a 366 días, con ambas fechas incluidas; fecha ausente o
inválida, o período fuera de rango: 400 en el campo (ADR-013). Otra clave o
una clave repetida: 400 general.
"""
import datetime
import re

from django.db import transaction
from django.http import HttpResponse, JsonResponse

from autorizacion.decoradores import requiere_rol
from bitacora import servicios as bitacora
from comun.api import MENSAJE_CLAVE_DESCONOCIDA, ErroresDeCampo, ErrorSolicitud, manejar_errores, metodos
from gestion import exportacion, indicadores

DIAS_MINIMO = 31
DIAS_MAXIMO = 366
CAMPOS_PERIODO = ("desde", "hasta")
MENSAJE_FECHA = {
    "desde": "Elige la fecha de inicio del período (día, mes y año).",
    "hasta": "Elige la fecha de término del período (día, mes y año).",
}
MENSAJE_RANGO = (
    f"El período debe tener entre {DIAS_MINIMO} y {DIAS_MAXIMO} días, contando ambas fechas. "
    "Cambia la fecha de término."
)
ACCION_EXPORTACION = "exportacion_agregada"
_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}")


def _fecha(valor):
    if not isinstance(valor, str) or not _FECHA.fullmatch(valor):
        return None
    try:
        return datetime.date.fromisoformat(valor)
    except ValueError:
        return None


def leer_periodo(parametros):
    if set(parametros) - set(CAMPOS_PERIODO) or any(len(parametros.getlist(c)) > 1 for c in CAMPOS_PERIODO):
        raise ErrorSolicitud(MENSAJE_CLAVE_DESCONOCIDA)
    fechas = {campo: _fecha(parametros.get(campo)) for campo in CAMPOS_PERIODO}
    errores = {campo: MENSAJE_FECHA[campo] for campo, fecha in fechas.items() if fecha is None}
    if not errores and not DIAS_MINIMO <= (fechas["hasta"] - fechas["desde"]).days + 1 <= DIAS_MAXIMO:
        errores["hasta"] = MENSAJE_RANGO
    if errores:
        raise ErroresDeCampo(errores)
    return fechas["desde"], fechas["hasta"]


@metodos("GET")
@requiere_rol("control_gestion")
@manejar_errores
def indicadores_base(request):
    desde, hasta = leer_periodo(request.GET)
    datos = {"periodo": {"desde": desde.isoformat(), "hasta": hasta.isoformat()}}
    datos.update(indicadores.calcular(desde, hasta))
    respuesta = JsonResponse(datos)
    respuesta["Cache-Control"] = "no-store"
    return respuesta


@metodos("GET")
@requiere_rol("control_gestion")
@manejar_errores
def exportar(request):
    desde, hasta = leer_periodo(request.GET)
    inicio, fin = indicadores.periodo(desde, hasta)
    with transaction.atomic():
        texto, filas, suprimidas = exportacion.generar(inicio, fin)
        # Bitácora sin datos personales: autor, período y cantidades (RF-37; ADR-026, E-6).
        bitacora.registrar(
            autor=request.usuario,
            accion=ACCION_EXPORTACION,
            entidad="exportacion",
            entidad_ref=f"{desde.isoformat()}..{hasta.isoformat()}",
            motivo="Exportación agregada de control de gestión (RF-38)",
            valor_nuevo={
                "desde": desde.isoformat(),
                "hasta": hasta.isoformat(),
                "filas": filas,
                "filas_suprimidas": suprimidas,
            },
        )
    respuesta = HttpResponse(texto.encode("utf-8-sig"), content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = (
        f'attachment; filename="altiro-agregado-{desde.isoformat()}-{hasta.isoformat()}.csv"'
    )
    respuesta["Cache-Control"] = "no-store"
    return respuesta
