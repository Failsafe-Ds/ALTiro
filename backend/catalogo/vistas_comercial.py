"""Rutas de comercial sobre el catálogo (RF-36, RF-37, HU-20, CA-20.1, CA-20.2; ADR-018).

Todas exigen el rol ``comercial`` (``@requiere_rol``: 403 registrado si falta;
401 sin sesión). Las que reciben una referencia la resuelven con
``obtener_autorizado`` (una referencia inexistente responde el 404 neutro, sin
registro). Campos permitidos explícitos por ruta (ADR-013, E-2). Respuestas
con lista explícita de campos, sin ids internos ni datos personales, y con
``Cache-Control: no-store``.
"""

from autorizacion.acceso import obtener_autorizado
from autorizacion.decoradores import requiere_rol
from catalogo import servicios
from catalogo.errores import ErrorVersion
from catalogo.models import Oficio, Servicio
from catalogo.politicas import PoliticaOficioComercial, PoliticaServicioComercial
from comun.api import leer_json, manejar_errores, metodos, respuesta_error, respuesta_json

CAMPOS_CREAR_OFICIO = {"nombre", "regulado", "orden", "motivo"}
# ``regulado`` se admite en la lectura solo para responder con un mensaje propio
# en ese campo: el servicio lo rechaza siempre (ADR-018, punto 2).
CAMPOS_MODIFICAR_OFICIO = {"version", "motivo", "nombre", "orden", "activo", "regulado"}
CAMPOS_CREAR_SERVICIO = {"oficio", "nombre", "orden", "modalidades", "motivo"}
# ``oficio`` se admite en la lectura solo para responder con un mensaje propio: no se cambia.
CAMPOS_MODIFICAR_SERVICIO = {"version", "motivo", "nombre", "orden", "activo", "modalidades", "oficio"}


def datos_oficio_comercial(oficio):
    return {
        "ref": str(oficio.ref),
        "codigo": oficio.codigo,
        "nombre": oficio.nombre,
        "regulado": oficio.regulado,
        "orden": oficio.orden,
        "activo": oficio.activo,
        "version": oficio.version,
    }


def datos_servicio_comercial(servicio):
    return {
        "ref": str(servicio.ref),
        "oficio": servicio.oficio.codigo,
        "nombre": servicio.nombre,
        "orden": servicio.orden,
        "activo": servicio.activo,
        "version": servicio.version,
        "modalidades": servicios.modalidades_de(servicio),
    }


@metodos("GET")
@requiere_rol("comercial")
def catalogo_comercial(request):
    """Catálogo completo, con oficios y servicios inactivos y su ``version``."""
    todos = Servicio.objects.select_related("oficio").order_by("orden", "nombre", "pk")
    por_oficio = {}
    for servicio in todos:
        por_oficio.setdefault(servicio.oficio_id, []).append(datos_servicio_comercial(servicio))
    return respuesta_json(
        {
            "oficios": [
                {**datos_oficio_comercial(oficio), "servicios": por_oficio.get(oficio.pk, [])}
                for oficio in Oficio.objects.order_by("orden", "codigo")
            ]
        }
    )


def _con_conflicto(funcion):
    try:
        return funcion()
    except ErrorVersion as error:
        return respuesta_error(409, error.mensaje)


@metodos("POST")
@requiere_rol("comercial")
@manejar_errores
def crear_oficio(request):
    datos = leer_json(request, CAMPOS_CREAR_OFICIO)
    return _con_conflicto(
        lambda: respuesta_json({"oficio": datos_oficio_comercial(servicios.crear_oficio(request.usuario, datos))}, 201)
    )


@metodos("PATCH")
@requiere_rol("comercial")
@manejar_errores
def modificar_oficio(request, ref):
    """Primero la referencia y la política; después el cuerpo."""
    oficio = obtener_autorizado(Oficio.objects.all(), ref, request.usuario, PoliticaOficioComercial())
    datos = leer_json(request, CAMPOS_MODIFICAR_OFICIO)
    return _con_conflicto(
        lambda: respuesta_json({"oficio": datos_oficio_comercial(servicios.modificar_oficio(request.usuario, oficio, datos))})
    )


@metodos("POST")
@requiere_rol("comercial")
@manejar_errores
def crear_servicio(request):
    datos = leer_json(request, CAMPOS_CREAR_SERVICIO)
    return _con_conflicto(
        lambda: respuesta_json({"servicio": datos_servicio_comercial(servicios.crear_servicio(request.usuario, datos))}, 201)
    )


@metodos("PATCH")
@requiere_rol("comercial")
@manejar_errores
def modificar_servicio(request, ref):
    servicio = obtener_autorizado(
        Servicio.objects.select_related("oficio"), ref, request.usuario, PoliticaServicioComercial()
    )
    datos = leer_json(request, CAMPOS_MODIFICAR_SERVICIO)
    return _con_conflicto(
        lambda: respuesta_json(
            {"servicio": datos_servicio_comercial(servicios.modificar_servicio(request.usuario, servicio, datos))}
        )
    )
