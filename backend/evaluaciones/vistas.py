"""Rutas de evaluación, denuncia y moderación (HU-09, HU-18, HU-21, HU-25; RF-29 a RF-31, RF-37; ADR-026, E-3 y E-4).

De las partes (``PoliticaTicket``: un tercero, incluidos los roles
administrativos, recibe el 404 idéntico con registro; la parte se deduce del
usuario, así que ``ParteEquivocada`` no aplica, E-5):

- ``POST /api/tickets/<ref>/evaluacion`` ``{puntualidad, trabajo, cordialidad, comentario?}``
- ``GET  /api/tickets/<ref>/evaluaciones`` → ``{mia, recibida, …}``
- ``POST /api/tickets/<ref>/evaluacion-recibida/denuncia`` ``{motivo}``

De moderación (``@requiere_rol("moderacion")`` y ``PoliticaDenuncia``):

- ``GET  /api/moderacion/denuncias?estado=abierta|resuelta``
- ``GET  /api/moderacion/denuncias/<ref>``
- ``GET  /api/moderacion/denuncias/<ref>/conversacion`` (solo abierta; si no, 404 registrado)
- ``POST /api/moderacion/denuncias/<ref>/resolucion`` ``{decision, motivo}``
"""
import re

from django.http import JsonResponse

from autorizacion.acceso import obtener_autorizado
from autorizacion.decoradores import requiere_rol
from comun.api import (
    MENSAJE_CLAVE_DESCONOCIDA,
    ErroresDeCampo,
    ErrorSolicitud,
    leer_json,
    manejar_errores,
    metodos,
    respuesta_error,
)
from evaluaciones import moderacion, servicios
from evaluaciones.models import (
    DIMENSIONES,
    LARGO_COMENTARIO,
    LARGO_MOTIVO,
    NOTA_MAXIMA,
    NOTA_MINIMA,
    DecisionDenuncia,
    EstadoDenuncia,
)
from evaluaciones.politicas import PoliticaConversacionDenuncia, PoliticaDenuncia
from expediente.errores import ErrorEstado
from tickets.models import Ticket
from tickets.politicas import PoliticaTicket

CAMPOS_EVALUACION = {*DIMENSIONES, "comentario"}
MENSAJE_NOTA = {
    "puntualidad": "Elige de 1 a 5 qué tan puntual fue.",
    "trabajo": "Elige de 1 a 5 cómo quedó el trabajo.",
    "cordialidad": "Elige de 1 a 5 qué tan amable fue el trato.",
}
MENSAJE_COMENTARIO = f"Tu comentario puede tener hasta {LARGO_COMENTARIO} caracteres. Acórtalo un poco."
MENSAJE_MOTIVO_VACIO = "Cuéntanos por qué denuncias esta evaluación."
MENSAJE_MOTIVO_RESOLUCION = "Escribe el motivo de tu decisión: queda registrado."
MENSAJE_MOTIVO_LARGO = f"El motivo puede tener hasta {LARGO_MOTIVO} caracteres. Acórtalo un poco."
MENSAJE_DECISION = "Elige si la evaluación se mantiene o se retira."
MENSAJE_FILTRO = "No pudimos aplicar el filtro. Elige «En revisión» o «Resueltas» y vuelve a intentarlo."

_NO_VACIO = re.compile(r"\S")


def _json(datos, estado=200):
    respuesta = JsonResponse(datos, status=estado)
    respuesta["Cache-Control"] = "no-store"
    return respuesta


def _conflicto(error):
    return respuesta_error(409, error.mensaje)


def _nota(valor):
    # ``bool`` es subclase de ``int``: se rechaza explícitamente.
    return isinstance(valor, int) and not isinstance(valor, bool) and NOTA_MINIMA <= valor <= NOTA_MAXIMA


def _motivo(datos, campo, mensaje_vacio, errores):
    texto = datos.get(campo)
    if not isinstance(texto, str) or not _NO_VACIO.search(texto):
        errores[campo] = mensaje_vacio
        return None
    texto = texto.strip()
    if len(texto) > LARGO_MOTIVO:
        errores[campo] = MENSAJE_MOTIVO_LARGO
        return None
    return texto


def _leer_evaluacion(request):
    datos = leer_json(request, CAMPOS_EVALUACION)
    errores = {d: MENSAJE_NOTA[d] for d in DIMENSIONES if not _nota(datos.get(d))}
    comentario = datos.get("comentario", "")
    if comentario is None:
        comentario = ""
    if not isinstance(comentario, str) or len(comentario.strip()) > LARGO_COMENTARIO:
        errores["comentario"] = MENSAJE_COMENTARIO
    if errores:
        raise ErroresDeCampo(errores)
    return {d: datos[d] for d in DIMENSIONES}, comentario.strip()


def _ticket(request, ref):
    return obtener_autorizado(Ticket.objects.all(), ref, request.usuario, PoliticaTicket())


# --- De las partes ---


@metodos("POST")
@manejar_errores
def evaluacion(request, ref):
    notas, comentario = _leer_evaluacion(request)  # El cuerpo se valida primero.
    ticket = _ticket(request, ref)
    try:
        creada = servicios.evaluar(ticket, request.usuario, notas, comentario)
    except ErrorEstado as error:
        return _conflicto(error)
    return _json({"evaluacion": servicios.datos_evaluacion(creada)}, 201)


@metodos("GET")
@manejar_errores
def evaluaciones(request, ref):
    if request.GET:
        raise ErrorSolicitud(MENSAJE_CLAVE_DESCONOCIDA)
    ticket = _ticket(request, ref)
    return _json(servicios.evaluaciones_de(ticket, request.usuario))


@metodos("POST")
@manejar_errores
def denuncia(request, ref):
    datos = leer_json(request, {"motivo"})
    errores = {}
    motivo = _motivo(datos, "motivo", MENSAJE_MOTIVO_VACIO, errores)
    if errores:
        raise ErroresDeCampo(errores)
    ticket = _ticket(request, ref)
    try:
        creada = servicios.denunciar(ticket, request.usuario, motivo)
    except ErrorEstado as error:
        return _conflicto(error)
    return _json({"denuncia": servicios.datos_denuncia_propia(creada)}, 201)


# --- De moderación ---


def _denuncia(request, ref, politica=None):
    return obtener_autorizado(moderacion.consulta(), ref, request.usuario, politica or PoliticaDenuncia())


@metodos("GET")
@requiere_rol("moderacion")
@manejar_errores
def denuncias(request):
    parametros = request.GET
    if set(parametros) - {"estado"} or len(parametros.getlist("estado")) > 1:
        raise ErrorSolicitud(MENSAJE_CLAVE_DESCONOCIDA)
    estado = parametros.get("estado")
    consulta = moderacion.consulta()
    if estado is not None:
        if estado not in EstadoDenuncia.values:
            raise ErroresDeCampo({"estado": MENSAJE_FILTRO})
        consulta = consulta.filter(estado=estado)
    # El moderador no ve en la lista las denuncias de sus propios trabajos (conflicto de interés).
    consulta = consulta.exclude(evaluacion__ticket__cliente_id=request.usuario.pk).exclude(
        evaluacion__ticket__perfil_maestro_id=request.usuario.pk
    )
    return _json({"denuncias": [moderacion.datos_en_lista(d) for d in consulta.order_by("creada_en", "id")]})


@metodos("GET")
@requiere_rol("moderacion")
def denuncia_detalle(request, ref):
    return _json({"denuncia": moderacion.datos_detalle(_denuncia(request, ref))})


@metodos("GET")
@requiere_rol("moderacion")
def denuncia_conversacion(request, ref):
    # Denuncia no abierta: 404 idéntico con registro. Moderador que es parte: ConflictoDeInteres (E-4.3).
    denuncia_actual = _denuncia(request, ref, PoliticaConversacionDenuncia())
    return _json(moderacion.leer_conversacion(denuncia_actual, request.usuario))


@metodos("POST")
@requiere_rol("moderacion")
@manejar_errores
def denuncia_resolucion(request, ref):
    datos = leer_json(request, {"decision", "motivo"})
    errores = {}
    decision = datos.get("decision")
    if decision not in DecisionDenuncia.values:
        errores["decision"] = MENSAJE_DECISION
    motivo = _motivo(datos, "motivo", MENSAJE_MOTIVO_RESOLUCION, errores)
    if errores:
        raise ErroresDeCampo(errores)
    denuncia_actual = _denuncia(request, ref)
    try:
        resuelta = moderacion.resolver(denuncia_actual, request.usuario, DecisionDenuncia(decision), motivo)
    except ErrorEstado as error:
        return _conflicto(error)
    resuelta = moderacion.consulta().get(pk=resuelta.pk)
    return _json({"denuncia": moderacion.datos_detalle(resuelta)})
