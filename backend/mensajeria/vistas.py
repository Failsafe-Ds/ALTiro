"""Rutas de la conversación de un ticket (HU-07, RF-25, CA-07.1 a CA-07.3, CA-15.2; ADR-026, E-2).

``/api/tickets/<uuid:ref>/mensajes``:

- ``GET`` (``?despues=<ref>`` opcional): los mensajes en orden de envío, o
  solo los posteriores a ``despues``. En ``cerrado``, lista vacía con el aviso
  "no hubo conversación"; en ``pendiente``, 409 accionable. **No renueva la
  sesión** (ADR-005): la pantalla la consulta cada 20 s; la actividad de la
  persona es abrir el pedido y enviar mensajes.
- ``POST`` ``{texto, clave_envio}``: solo en ``aceptado`` (otro estado: 409
  accionable). 201 con el mensaje; 200 con el mismo mensaje si la
  ``clave_envio`` ya se usó (reenvío con conexión irregular).

Solo las dos partes (``PoliticaTicket``): un tercero, incluidos los roles
administrativos, recibe el 404 idéntico con registro (CA-25.1). La respuesta
dice "tu", "cliente" o "maestro"; sin ids internos ni datos de contacto.
"""
import re
import uuid


from autorizacion.acceso import obtener_autorizado
from comun.api import (
    ErrorSolicitud,
    ErroresDeCampo,
    MENSAJE_CLAVE_DESCONOCIDA,
    MENSAJE_VALOR_REPETIDO,
    leer_json,
    manejar_errores,
    metodos,
    respuesta_error,
    respuesta_json,
)
from expediente.errores import ErrorEstado
from mensajeria import conversacion
from mensajeria.models import LARGO_MAXIMO
from tickets.models import Ticket
from tickets.politicas import PoliticaTicket

CAMPOS_ENVIO = {"texto", "clave_envio"}

MENSAJE_TEXTO_VACIO = "Escribe tu mensaje antes de enviarlo."
MENSAJE_TEXTO_LARGO = f"Tu mensaje puede tener hasta {LARGO_MAXIMO} caracteres. Acórtalo o envíalo en dos partes."
MENSAJE_CLAVE_INVALIDA = "No pudimos enviar tu mensaje. Vuelve a cargar la página e inténtalo de nuevo."
MENSAJE_DESPUES_INVALIDO = "No pudimos actualizar la conversación. Vuelve a cargar la página."

_NO_VACIO = re.compile(r"\S")


def _uuid(valor):
    if not isinstance(valor, str):
        return None
    try:
        return uuid.UUID(valor)
    except ValueError:
        return None


def _despues(parametros):
    """``despues`` (opcional): ref de un mensaje. Otro parámetro: 400 general (ADR-013, E-2)."""
    if set(parametros) - {"despues"}:
        raise ErrorSolicitud(MENSAJE_CLAVE_DESCONOCIDA)
    valores = parametros.getlist("despues")
    if not valores:
        return None
    if len(valores) > 1:
        raise ErroresDeCampo({"despues": MENSAJE_VALOR_REPETIDO})
    ref = _uuid(valores[0])
    if ref is None:
        raise ErroresDeCampo({"despues": MENSAJE_DESPUES_INVALIDO})
    return ref


def _envio(request):
    datos = leer_json(request, CAMPOS_ENVIO)
    errores = {}
    texto = datos.get("texto")
    if not isinstance(texto, str) or not _NO_VACIO.search(texto):
        errores["texto"] = MENSAJE_TEXTO_VACIO
    elif len(texto) > LARGO_MAXIMO:
        errores["texto"] = MENSAJE_TEXTO_LARGO
    clave = _uuid(datos.get("clave_envio"))
    if clave is None:
        errores["clave_envio"] = MENSAJE_CLAVE_INVALIDA
    if errores:
        raise ErroresDeCampo(errores)
    return texto, clave


def _leer(request, ticket):
    try:
        datos = conversacion.leer(ticket, request.usuario, _despues(request.GET))
    except conversacion.ReferenciaDesconocida:
        # Un ref de otra conversación se trata igual que uno inexistente (no revela nada).
        raise ErroresDeCampo({"despues": MENSAJE_DESPUES_INVALIDO})
    return respuesta_json(datos)


def _enviar(request, ticket, texto, clave):
    mensaje, creado = conversacion.enviar(ticket, request.usuario, texto, clave)
    return respuesta_json({"mensaje": conversacion.datos_mensaje(mensaje, request.usuario, ticket)}, 201 if creado else 200)


@metodos("GET", "POST")
@manejar_errores
def mensajes(request, ref):
    if request.method == "GET":
        # Consulta automática: no cuenta como actividad (ADR-005; identidad.middleware.SesionMiddleware).
        request.sin_renovar_sesion = True
        envio = None
    else:
        envio = _envio(request)  # El cuerpo se valida primero, como en las acciones del ticket.
    # Un tercero (incluidos los roles administrativos) recibe el 404 idéntico con registro (CA-25.1).
    ticket = obtener_autorizado(Ticket.objects.all(), ref, request.usuario, PoliticaTicket())
    try:
        return _leer(request, ticket) if envio is None else _enviar(request, ticket, *envio)
    except ErrorEstado as error:
        return respuesta_error(409, error.mensaje)
