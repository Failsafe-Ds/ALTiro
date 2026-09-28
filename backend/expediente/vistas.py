"""Endpoints del maestro sobre su propio expediente (ADR-017; propuesta del S2, §4).

Patrón "me" (ADR-011): sin identificador en la ruta; el expediente es siempre
el de la cuenta de la sesión. Exigen el rol ``maestro`` (403 registrado si
falta, ADR-011, punto 3). Respuestas con lista explícita de campos: nunca el
RUT, ids internos ni quién cambió el estado (ADR-010, E-1).
"""
from django.http import JsonResponse

from autorizacion.decoradores import requiere_rol
from catalogo.vistas import datos_oficio
from comun.api import ErroresDeCampo, leer_json, manejar_errores, metodos, respuesta_error
from expediente import servicios, vigencia
from expediente.errores import ErrorEstado
from expediente.models import Expediente, OficioMaestro
from identidad.errores import ErrorValidacion

CAMPOS_DECLARAR_OFICIOS = {"oficios"}


def _mi_expediente(request):
    return Expediente.objects.get(perfil_maestro_id=request.usuario.pk)


def datos_expediente(expediente):
    oficios = (
        OficioMaestro.objects.filter(maestro_id=expediente.perfil_maestro_id)
        .select_related("oficio")
        .order_by("oficio__orden", "oficio__codigo")
    )
    return {
        "estado": expediente.estado,
        "motivo": expediente.estado_motivo,
        "oficios": [datos_oficio(om.oficio) for om in oficios],
        # Los documentos llegan en el incremento 2 y los avisos en el 5 (propuesta del S2, §7).
        "documentos": [],
        "faltantes": [
            {"tipo": tipo, "oficio": {"codigo": oficio.codigo, "nombre": oficio.nombre} if oficio else None}
            for tipo, oficio in vigencia.faltantes_para_aprobar(expediente)
        ],
        "avisos": [],
    }


def _respuesta(expediente):
    respuesta = JsonResponse({"expediente": datos_expediente(expediente)})
    respuesta["Cache-Control"] = "no-store"
    return respuesta


@metodos("GET")
@requiere_rol("maestro")
def mi_expediente(request):
    return _respuesta(_mi_expediente(request))


@metodos("POST")
@requiere_rol("maestro")
@manejar_errores
def mis_oficios(request):
    datos = leer_json(request, CAMPOS_DECLARAR_OFICIOS)
    try:
        expediente = servicios.declarar_oficios(_mi_expediente(request), datos.get("oficios"))
    except ErrorValidacion as error:
        raise ErroresDeCampo({error.campo: error.mensaje}) from None
    except ErrorEstado as error:
        return respuesta_error(409, error.mensaje)
    return _respuesta(expediente)
