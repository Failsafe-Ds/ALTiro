"""Endpoints del maestro sobre su propio expediente (ADR-017; propuesta del S2, §4).

Patrón "me" (ADR-011): sin identificador en la ruta; el expediente es siempre
el de la cuenta de la sesión. Exigen el rol ``maestro`` (403 registrado si
falta, ADR-011, punto 3). Respuestas con lista explícita de campos: nunca el
RUT, ids internos, quién cambió el estado o revisó (ADR-010, E-1), ni nombres
o rutas de archivos (ADR-015).
"""
from django.conf import settings
from django.http import JsonResponse

from autorizacion.decoradores import requiere_rol
from catalogo.vistas import datos_oficio
from comun.api import (
    ErroresDeCampo,
    leer_json,
    leer_multipart,
    manejar_errores,
    metodos,
    respuesta_error,
)
from expediente import servicios, vigencia
from expediente.errores import ErrorEstado, ErroresValidacion
from expediente.models import EstadoDocumento, Expediente, OficioMaestro
from identidad.errores import ErrorValidacion

CAMPOS_DECLARAR_OFICIOS = {"oficios"}
CAMPOS_DOCUMENTO = {"tipo", "oficio", "fecha_emision", "fecha_vencimiento"}
ARCHIVOS_DOCUMENTO = {"archivo", "archivo_reverso"}

MENSAJE_SUBIDA_GRANDE = "Las fotos son muy pesadas. Tómalas de nuevo o elige otras."


def _mi_expediente(request):
    return Expediente.objects.get(perfil_maestro_id=request.usuario.pk)


def _oficio_resumido(oficio):
    return {"codigo": oficio.codigo, "nombre": oficio.nombre} if oficio else None


def datos_documento(documento):
    """Lista explícita (RF-08): sin archivos, rutas, revisor ni ids internos.

    ``motivo_observacion``: lo que curatoría escribió al observar (CA-17.2);
    ``null`` si no está observado. Nunca quién revisó ni cuándo (ADR-010, E-1).
    """
    observado = documento.estado == EstadoDocumento.OBSERVADO
    return {
        "ref": str(documento.ref),
        "tipo": documento.tipo,
        "oficio": _oficio_resumido(documento.oficio),
        "estado": documento.estado,
        "fecha_emision": documento.fecha_emision.isoformat(),
        "fecha_vencimiento": documento.fecha_vencimiento.isoformat() if documento.fecha_vencimiento else None,
        "motivo_observacion": documento.motivo_observacion if observado else None,
    }


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
        # Documentos actuales: los reemplazados no se muestran.
        "documentos": [datos_documento(d) for d in vigencia.documentos_actuales(expediente)],
        # Requisitos sin ningún documento entregado (ver vigencia.requisitos_sin_documento).
        "faltantes": [
            {"tipo": tipo, "oficio": _oficio_resumido(oficio)}
            for tipo, oficio in vigencia.requisitos_sin_documento(expediente)
        ],
        # Los avisos llegan en el incremento 5 (propuesta del S2, §7).
        "avisos": [],
    }


def _respuesta(expediente, estado=200):
    respuesta = JsonResponse({"expediente": datos_expediente(expediente)}, status=estado)
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


def _largo_declarado(request):
    try:
        return int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return 0


@metodos("POST")
@requiere_rol("maestro")
@manejar_errores
def mis_documentos(request):
    """Carga un documento (multipart; RF-04, ADR-015, ADR-017). 201 con el expediente."""
    # Sobre este tamaño el manejador en memoria descarta los archivos sin
    # escribirlos a disco (settings.FILE_UPLOAD_HANDLERS): se informa aquí.
    if _largo_declarado(request) > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
        return respuesta_error(413, MENSAJE_SUBIDA_GRANDE)
    datos, archivos = leer_multipart(request, CAMPOS_DOCUMENTO, ARCHIVOS_DOCUMENTO)
    try:
        expediente = servicios.cargar_documento(request.usuario, datos, archivos)
    except ErroresValidacion as error:
        raise ErroresDeCampo(error.errores) from None
    except ErrorEstado as error:
        return respuesta_error(409, error.mensaje)
    return _respuesta(expediente, estado=201)
