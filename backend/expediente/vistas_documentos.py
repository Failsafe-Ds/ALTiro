"""Enlace temporal y descarga de los documentos del expediente (RNF-06, CA-25.2, RNF-07; ADR-011, ADR-015).

- ``GET /api/documentos/<uuid:ref>/enlace?cara=anverso|reverso``: con la
  política aplicada (``PoliticaDocumento``), responde un enlace firmado de
  600 s ligado al documento, a la cara y al usuario (``autorizacion.enlaces``).
  Sin ``cara``, se entiende ``anverso`` (todo documento tiene esa foto).
- ``GET /api/documentos/<uuid:ref>/archivo?cara=…&t=…``: **vuelve a aplicar la
  política** (el enlace no la reemplaza, ADR-015, D-3), verifica el token para
  ese usuario, ese documento y esa cara, descifra el archivo y lo entrega con
  cabeceras que impiden guardarlo en caché, interpretarlo como otra cosa o
  ejecutar contenido.

Orden: primero la política y después los parámetros. Así cualquier acceso de
un tercero responde el 404 idéntico y queda registrado (HU-25, CA-25.2), sean
cuales sean sus parámetros; y un 400 solo llega a quien sí tiene acceso.

Documentos reemplazados (ADR-017, E-3):

- Por ``/api/documentos/<ref>/enlace`` solo se pide el enlace del documento
  actual: uno ``reemplazado`` responde el 404 neutro, sin registro (quien
  pregunta sí tiene relación con él). El dueño ve y abre solo los actuales.
- ``GET /api/curatoria/documentos/<uuid:ref>/enlace``: curatoría pide el
  enlace de cualquier documento de un expediente ajeno, también uno
  reemplazado, desde el historial. Exige el rol y aplica el conflicto de
  interés (ADR-011, E-2): el dueño con rol ``curatoria`` recibe el 403
  registrado.
- El archivo de un documento reemplazado solo se entrega a curatoría que no es
  dueña (con un token de 600 s emitido para ella); el dueño recibe el 404
  neutro, sin registro.

Ninguna respuesta incluye rutas del volumen ni nombres de archivo internos.
"""
import datetime
import logging
from urllib.parse import urlencode

from django.http import HttpResponse, JsonResponse
from django.utils import timezone

from autorizacion import enlaces
from autorizacion.acceso import obtener_autorizado
from autorizacion.decoradores import requiere_rol
from autorizacion.excepciones import RecursoNoEncontrado
from comun.api import ErrorSolicitud, error_interno, manejar_errores, metodos, respuesta_error
from expediente import almacenamiento
from expediente.models import Documento, EstadoDocumento
from expediente.politicas import PoliticaDocumento, PoliticaDocumentoCuratoria, es_dueno_del_expediente

logger = logging.getLogger(__name__)

MENSAJE_FOTO_INVALIDA = (
    "No pudimos abrir la foto pedida. Vuelve a la lista de documentos e inténtalo de nuevo."
)
# RNF-26 (ADR-026, E-9): el archivo se borró al cumplirse el plazo de retención.
MENSAJE_ELIMINADO = (
    "Este documento ya no está disponible: se eliminó al cumplirse su plazo de retención. "
    "Si todavía se necesita, hay que cargarlo de nuevo."
)
MENSAJE_SIN_REVERSO = (
    "Este documento tiene una sola foto, la de adelante. Ábrela desde la lista de documentos."
)

PARAMETROS_ENLACE = frozenset({"cara"})
PARAMETROS_ARCHIVO = frozenset({"cara", "t"})
_CARAS = (almacenamiento.ANVERSO, almacenamiento.REVERSO)

# Cabeceras del archivo (ADR-015; RNF-06): sin caché, sin interpretar el tipo,
# sin ejecutar nada aunque el contenido fuera hostil y sin uso desde otro origen.
CABECERAS_ARCHIVO = {
    "Content-Disposition": 'inline; filename="documento.jpg"',
    "Cache-Control": "no-store, private",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "sandbox; default-src 'none'",
    "Cross-Origin-Resource-Policy": "same-origin",
}


def _documento_autorizado(request, ref, admite_reemplazado_para_curatoria=False):
    """Documento con la política aplicada (404 idéntico, registrado si es ajeno).

    Un documento reemplazado responde el 404 neutro sin registro, salvo que se
    admita para curatoría no dueña (descarga, ADR-017, E-3).
    """
    documento = obtener_autorizado(
        Documento.objects.select_related("expediente"), ref, request.usuario, PoliticaDocumento()
    )
    if documento.estado == EstadoDocumento.REEMPLAZADO and (
        not admite_reemplazado_para_curatoria or es_dueno_del_expediente(request.usuario, documento.expediente)
    ):
        raise RecursoNoEncontrado()
    return documento


def _nombre_archivo(documento, cara):
    return documento.archivo if cara == almacenamiento.ANVERSO else documento.archivo_reverso


def _cara_del_enlace(request, documento):
    """Cara pedida (``anverso`` si no viene). Errores: 400 accionable."""
    parametros = request.GET
    if set(parametros) - PARAMETROS_ENLACE or len(parametros.getlist("cara")) > 1:
        raise ErrorSolicitud(MENSAJE_FOTO_INVALIDA)
    cara = parametros.get("cara", almacenamiento.ANVERSO)
    if cara not in _CARAS:
        raise ErrorSolicitud(MENSAJE_FOTO_INVALIDA)
    if _nombre_archivo(documento, cara) is None:
        raise ErrorSolicitud(MENSAJE_SIN_REVERSO)
    return cara


@metodos("GET")
@manejar_errores
def documento_enlace(request, ref):
    return _respuesta_enlace(request, _documento_autorizado(request, ref))


@metodos("GET")
@requiere_rol("curatoria")
@manejar_errores
def curatoria_documento_enlace(request, ref):
    """Enlace para curatoría: documentos actuales o reemplazados de un expediente ajeno (ADR-017, E-3)."""
    documento = obtener_autorizado(
        Documento.objects.select_related("expediente"), ref, request.usuario, PoliticaDocumentoCuratoria()
    )
    return _respuesta_enlace(request, documento)


def _respuesta_enlace(request, documento):
    if documento.eliminado_en is not None:
        return respuesta_error(409, MENSAJE_ELIMINADO)
    cara = _cara_del_enlace(request, documento)
    # El timestamp del token es el segundo entero en curso: caduca 600 s después.
    caduca_en = timezone.now().replace(microsecond=0) + datetime.timedelta(seconds=enlaces.VIGENCIA_SEGUNDOS)
    token = enlaces.firmar(documento.ref, request.usuario.pk, cara)
    respuesta = JsonResponse(
        {
            "url": f"/api/documentos/{documento.ref}/archivo?{urlencode({'cara': cara, 't': token})}",
            "caduca_en": caduca_en.isoformat(),
        }
    )
    respuesta["Cache-Control"] = "no-store"
    return respuesta


def _cara_y_token(request):
    """Parámetros del archivo; cualquier problema responde el 404 neutro."""
    parametros = request.GET
    if set(parametros) != PARAMETROS_ARCHIVO or any(len(parametros.getlist(p)) != 1 for p in PARAMETROS_ARCHIVO):
        raise RecursoNoEncontrado()
    cara = parametros["cara"]
    if cara not in _CARAS:
        raise RecursoNoEncontrado()
    return cara, parametros["t"]


@metodos("GET")
def documento_archivo(request, ref):
    documento = _documento_autorizado(request, ref, admite_reemplazado_para_curatoria=True)
    cara, token = _cara_y_token(request)
    try:
        referencia = enlaces.verificar(token, request.usuario.pk, cara)
    except enlaces.EnlaceInvalido:
        raise RecursoNoEncontrado() from None
    nombre = _nombre_archivo(documento, cara)
    # Un enlace emitido antes de la eliminación por retención: 404 neutro, no 500.
    if referencia != str(documento.ref) or nombre is None or documento.eliminado_en is not None:
        raise RecursoNoEncontrado()
    try:
        contenido = almacenamiento.leer(documento.ref, cara, nombre)
    except almacenamiento.ArchivoIlegible:
        # Falla de integridad del servidor, no un recurso inexistente: 500
        # genérico. Sin nombre de archivo, ruta, clave ni contenido.
        logger.error("No se pudo leer el archivo de un documento (documento=%s, cara=%s).", documento.ref, cara)
        return error_interno(request)
    respuesta = HttpResponse(contenido, content_type="image/jpeg")
    for cabecera, valor in CABECERAS_ARCHIVO.items():
        respuesta[cabecera] = valor
    return respuesta
