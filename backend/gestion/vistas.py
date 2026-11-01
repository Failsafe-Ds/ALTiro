"""API de control de gestión (HU-22, RF-38, CA-22.1, CA-22.2; ADR-026, E-6; propuesta del S5, §3.3).

- ``GET /api/gestion/indicadores?desde=&hasta=``: los tres indicadores base.
- ``GET /api/gestion/exportacion?desde=&hasta=``: CSV agregado (adjunto).

Solo el rol ``control_gestion`` (``requiere_rol``: sin el rol, 403 registrado).
El período son **meses calendario completos y cerrados** (``AAAA-MM``), de 1 a
12 meses, con ambos meses incluidos y ``hasta`` anterior al mes en curso
(zona de negocio): así dos consultas no se solapan a medias ni cambian dentro
de un mes abierto, y restarlas no aísla días (R-08; enmienda E-6.6 de ADR-026,
provisional). Mes ausente o inválido, o período fuera de rango: 400 en el
campo (ADR-013). Otra clave o una clave repetida: 400 general.
"""
import datetime
import re

from django.db import transaction
from django.http import HttpResponse, JsonResponse

from autorizacion.decoradores import requiere_rol
from bitacora import servicios as bitacora
from comun.api import MENSAJE_CLAVE_DESCONOCIDA, ErroresDeCampo, ErrorSolicitud, manejar_errores, metodos
from comun.texto import recortar
from expediente.vigencia import hoy_negocio
from gestion import exportacion, indicadores

MESES_MINIMO = 1
MESES_MAXIMO = 12
CAMPOS_PERIODO = ("desde", "hasta")
MENSAJE_MES = {
    "desde": "Elige el mes de inicio del período (mes y año).",
    "hasta": "Elige el mes de término del período (mes y año).",
}
MENSAJE_RANGO = (
    f"El período debe tener entre {MESES_MINIMO} y {MESES_MAXIMO} meses, contando ambos. "
    "Cambia el mes de término."
)
MENSAJE_RANGO_INVERTIDO = "«Hasta» debe ser igual o posterior a «Desde». Cambia el mes de término."
MENSAJE_MES_ABIERTO = "Elige un mes que ya terminó: el mes en curso todavía no se puede consultar."
ACCION_EXPORTACION = "exportacion_agregada"
_MES = re.compile(r"\d{4}-\d{2}")


def _mes(valor):
    """Primer día del mes ``AAAA-MM`` (recortado), o ``None`` si no es válido."""
    valor = recortar(valor)
    if not isinstance(valor, str) or not _MES.fullmatch(valor):
        return None
    try:
        return datetime.date(int(valor[:4]), int(valor[5:]), 1)
    except ValueError:
        return None


def _ultimo_dia(mes):
    siguiente = (mes.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return siguiente - datetime.timedelta(days=1)


def leer_periodo(parametros):
    """Devuelve el primer día del mes ``desde`` y el primer día del mes ``hasta``."""
    if set(parametros) - set(CAMPOS_PERIODO) or any(len(parametros.getlist(c)) > 1 for c in CAMPOS_PERIODO):
        raise ErrorSolicitud(MENSAJE_CLAVE_DESCONOCIDA)
    meses = {campo: _mes(parametros.get(campo)) for campo in CAMPOS_PERIODO}
    errores = {campo: MENSAJE_MES[campo] for campo, mes in meses.items() if mes is None}
    if not errores:
        desde, hasta = meses["desde"], meses["hasta"]
        cuenta = (hasta.year - desde.year) * 12 + hasta.month - desde.month + 1
        if cuenta < MESES_MINIMO:
            errores["hasta"] = MENSAJE_RANGO_INVERTIDO
        elif cuenta > MESES_MAXIMO:
            errores["hasta"] = MENSAJE_RANGO
        elif hasta >= hoy_negocio().replace(day=1):
            errores["hasta"] = MENSAJE_MES_ABIERTO
    if errores:
        raise ErroresDeCampo(errores)
    return meses["desde"], meses["hasta"]


@metodos("GET")
@requiere_rol("control_gestion")
@manejar_errores
def indicadores_base(request):
    desde, hasta = leer_periodo(request.GET)
    datos = {"periodo": {"desde": f"{desde:%Y-%m}", "hasta": f"{hasta:%Y-%m}"}, "umbral": indicadores.K}
    datos.update(indicadores.calcular(desde, _ultimo_dia(hasta)))
    respuesta = JsonResponse(datos)
    respuesta["Cache-Control"] = "no-store"
    return respuesta


@metodos("GET")
@requiere_rol("control_gestion")
@manejar_errores
def exportar(request):
    desde, hasta = leer_periodo(request.GET)
    inicio, fin = indicadores.periodo(desde, _ultimo_dia(hasta))
    desde, hasta = f"{desde:%Y-%m}", f"{hasta:%Y-%m}"
    with transaction.atomic():
        texto, filas, suprimidas, celdas = exportacion.generar(inicio, fin)
        # Bitácora sin datos personales: autor, período y cantidades (RF-37; ADR-026, E-6).
        bitacora.registrar(
            autor=request.usuario,
            accion=ACCION_EXPORTACION,
            entidad="exportacion",
            entidad_ref=f"{desde}..{hasta}",
            motivo="Exportación agregada de control de gestión (RF-38)",
            valor_nuevo={
                "desde": desde,
                "hasta": hasta,
                "filas": filas,
                "filas_suprimidas": suprimidas,
                "celdas_suprimidas": celdas,
            },
        )
    respuesta = HttpResponse(texto.encode("utf-8-sig"), content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = (
        f'attachment; filename="altiro-agregado-{desde}-{hasta}.csv"'
    )
    respuesta["Cache-Control"] = "no-store"
    return respuesta
