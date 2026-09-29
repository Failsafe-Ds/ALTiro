"""Utilidades de la API JSON (propuesta del S1, §4; ADR-013, Enmienda E-2; RNF-15).

Formato de error común, sin trazas ni nombres internos::

    {"mensaje": "Revisa los campos marcados.", "errores": {"campo": "acción correctiva"}}

- Clave desconocida: 400 general, sin repetir la clave ni el valor recibidos.
- Campo conocido pero no permitido en el contexto: 400 en ese campo.
"""
import functools
import json

from django.core.exceptions import ImproperlyConfigured
from django.http import JsonResponse

MENSAJE_REVISA_CAMPOS = "Revisa los campos marcados."
MENSAJE_CLAVE_DESCONOCIDA = (
    "Lo que enviaste tiene datos que este formulario no usa. Vuelve a cargar la página e inténtalo de nuevo."
)
MENSAJE_CUERPO_INVALIDO = "No pudimos leer los datos enviados. Recarga la página e inténtalo de nuevo."
MENSAJE_CAMPO_NO_PERMITIDO = "Este dato no corresponde aquí: quítalo e inténtalo de nuevo."
MENSAJE_TEXTO_INVALIDO = "Este dato tiene caracteres que no se pueden usar. Escríbelo de nuevo."
MENSAJE_VALOR_REPETIDO = "Este dato llegó repetido. Recarga la página e inténtalo de nuevo."
MENSAJE_ARCHIVO_ESPERADO = "Aquí va una foto. Elige la foto de nuevo e inténtalo otra vez."

# Todos los campos que aparecen en alguna lista de campos permitidos (E-2),
# incluidos los del formulario de documentos (multipart), los de curatoría, los
# del catálogo de comercial (ADR-018) y los de servicios del maestro (ADR-019).
CAMPOS_CONOCIDOS = frozenset(
    {"nombre", "telefono", "correo", "contrasena", "comuna", "rut", "identificador", "oficios",
     "tipo", "oficio", "fecha_emision", "fecha_vencimiento", "archivo", "archivo_reverso",
     "estado_nuevo", "estado_actual", "motivo", "resultado",
     "regulado", "orden", "activo", "version", "modalidades",
     "servicio", "modalidad", "monto"}
)


class ErrorSolicitud(Exception):
    """400 general: la solicitud no se puede atribuir a un campo del formulario."""

    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


class ErroresDeCampo(Exception):
    """400 con errores por campo."""

    def __init__(self, errores):
        super().__init__(", ".join(sorted(errores)))
        self.errores = errores


def respuesta_error(estado, mensaje, errores=None):
    return JsonResponse({"mensaje": mensaje, "errores": errores or {}}, status=estado)


def respuesta_errores_de_campo(errores):
    return respuesta_error(400, MENSAJE_REVISA_CAMPOS, errores)


def publica(vista):
    """Marca una vista como accesible sin sesión (propuesta del S1, §5, punto 1).

    Una vista que exige un rol (``autorizacion.decoradores.requiere_rol``) no
    puede ser pública: la combinación es un error de configuración.
    """
    if getattr(vista, "roles_requeridos", None):
        raise ImproperlyConfigured("Una vista que exige un rol no puede marcarse como pública.")
    vista.publica = True
    return vista


def metodos(*permitidos):
    """Limita los métodos HTTP; responde 405 en el formato común."""

    def decorador(vista):
        @functools.wraps(vista)
        def envoltura(request, *args, **kwargs):
            if request.method not in permitidos:
                respuesta = respuesta_error(405, "Esta operación no está disponible.")
                respuesta["Allow"] = ", ".join(permitidos)
                return respuesta
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


def _texto_procesable(valor):
    """Falso si un texto trae una secuencia Unicode no procesable (sustituto aislado)."""
    if not isinstance(valor, str):
        return True
    try:
        valor.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def leer_json(request, permitidos):
    """Lee un objeto JSON y aplica la lista de campos permitidos del contexto (E-2).

    - Cuerpo que no es un objeto JSON o clave desconocida: ``ErrorSolicitud``.
    - Campo conocido no permitido, o texto no procesable: ``ErroresDeCampo``.
    """
    if request.content_type != "application/json":
        raise ErrorSolicitud(MENSAJE_CUERPO_INVALIDO)
    try:
        datos = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ErrorSolicitud(MENSAJE_CUERPO_INVALIDO) from None
    if not isinstance(datos, dict):
        raise ErrorSolicitud(MENSAJE_CUERPO_INVALIDO)
    # Las claves desconocidas se revisan antes que cualquier campo (E-2).
    if set(datos) - CAMPOS_CONOCIDOS:
        raise ErrorSolicitud(MENSAJE_CLAVE_DESCONOCIDA)
    errores = {campo: MENSAJE_CAMPO_NO_PERMITIDO for campo in datos if campo not in permitidos}
    errores.update(
        {campo: MENSAJE_TEXTO_INVALIDO for campo, valor in datos.items()
         if campo not in errores and campo != "contrasena" and not _texto_procesable(valor)}
    )
    if errores:
        raise ErroresDeCampo(errores)
    return datos


def leer_multipart(request, campos, archivos):
    """Lee un formulario ``multipart/form-data`` con la disciplina de ``leer_json`` (E-2).

    - ``campos``: campos de texto permitidos; ``archivos``: campos de archivo permitidos.
    - Otro tipo de cuerpo o clave desconocida (texto o archivo): ``ErrorSolicitud``.
    - Campo conocido no permitido, archivo enviado como texto (o al revés),
      valor repetido o texto no procesable: ``ErroresDeCampo``.
    Devuelve ``(datos, archivos)``: diccionarios con un solo valor por campo.
    Los errores de lectura del cuerpo los responde ``solicitud_invalida`` (400).
    """
    if request.content_type != "multipart/form-data":
        raise ErrorSolicitud(MENSAJE_CUERPO_INVALIDO)
    textos, adjuntos = request.POST, request.FILES
    if (set(textos) | set(adjuntos)) - CAMPOS_CONOCIDOS:
        raise ErrorSolicitud(MENSAJE_CLAVE_DESCONOCIDA)
    errores = {}
    for campo in textos:
        if campo in archivos:
            errores[campo] = MENSAJE_ARCHIVO_ESPERADO
        elif campo not in campos:
            errores[campo] = MENSAJE_CAMPO_NO_PERMITIDO
        elif len(textos.getlist(campo)) > 1:
            errores[campo] = MENSAJE_VALOR_REPETIDO
        elif not _texto_procesable(textos[campo]) or "\x00" in textos[campo]:
            errores[campo] = MENSAJE_TEXTO_INVALIDO
    for campo in adjuntos:
        if campo not in archivos:
            errores[campo] = MENSAJE_CAMPO_NO_PERMITIDO
        elif len(adjuntos.getlist(campo)) > 1:
            errores[campo] = MENSAJE_VALOR_REPETIDO
    if errores:
        raise ErroresDeCampo(errores)
    return {campo: textos[campo] for campo in textos}, {campo: adjuntos[campo] for campo in adjuntos}


def manejar_errores(vista):
    """Traduce ``ErrorSolicitud`` y ``ErroresDeCampo`` al formato común."""

    @functools.wraps(vista)
    def envoltura(request, *args, **kwargs):
        try:
            return vista(request, *args, **kwargs)
        except ErrorSolicitud as error:
            return respuesta_error(400, error.mensaje)
        except ErroresDeCampo as error:
            return respuesta_errores_de_campo(error.errores)

    return envoltura


# --- Respuestas de Django en formato JSON ---


# Señal de rechazo CSRF (ADR-006, Enmienda E-1; ADR-011, Enmienda E-1).
# Solo la lleva la respuesta de ``fallo_csrf``: el cliente reintenta una única
# vez (tras GET /api/sesion/csrf) un 403 de un método distinto de GET que traiga
# esta cabecera con este valor. Ningún otro 403 —en particular, la falta de
# rol— la lleva, y por eso no se reintenta.
CABECERA_RECHAZO = "AlTiro-Rechazo"
RECHAZO_CSRF = "csrf"


def fallo_csrf(request, reason=""):
    """CSRF_FAILURE_VIEW (ADR-006). No muestra el motivo interno.

    CsrfViewMiddleware rechaza en ``process_view``, antes de la vista: esta
    respuesta no tuvo efectos ni dejó registro (ADR-006, E-1).
    """
    respuesta = respuesta_error(
        403, "Tu formulario venció o se abrió desde otro sitio. Recarga la página e inténtalo de nuevo."
    )
    respuesta[CABECERA_RECHAZO] = RECHAZO_CSRF
    return respuesta


MENSAJE_NO_ENCONTRADO = "No encontramos lo que buscas. Revisa el enlace o vuelve al inicio."


def respuesta_no_encontrado():
    """Único 404 neutro de la API (ADR-011, punto 2).

    Lo usan la ruta inexistente, el recurso inexistente y el recurso ajeno: el
    cuerpo es idéntico byte a byte, para no revelar si un recurso existe.
    """
    return respuesta_error(404, MENSAJE_NO_ENCONTRADO)


def no_encontrado(request, exception=None):
    return respuesta_no_encontrado()


MENSAJE_SOLICITUD_INVALIDA = "No pudimos leer lo que enviaste. Vuelve a cargar la página e inténtalo de nuevo."
MENSAJE_ERROR_INTERNO = "Tuvimos un problema y no pudimos completar lo que pediste. Inténtalo de nuevo en unos minutos."


def solicitud_invalida(request, exception=None):
    """handler400 (DEF-QA-006, RNF-15): Host no permitido, cuerpo multipart ilegible,
    demasiados campos o archivos. JSON en español; nunca el motivo interno."""
    return respuesta_error(400, MENSAJE_SOLICITUD_INVALIDA)


def error_interno(request):
    return respuesta_error(500, MENSAJE_ERROR_INTERNO)
