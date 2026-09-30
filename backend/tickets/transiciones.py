"""Transiciones del ticket después de crearlo (RF-19 a RF-24, HU-15, HU-10, HU-23, CA-10.2, CA-14.3, CA-15.x, CA-23.x; ADR-023, puntos 3 y 4; ADR-016 E-1; ADR-024, punto 2).

Tabla de ADR-023, punto 3:

- ``aceptar`` (el maestro): pendiente → aceptado, con ``ahora < vence_en``, el
  servicio todavía visible (D-11; si no, 409) y sin cruce con otro aceptado o
  finalizado. Los demás pendientes **del mismo maestro** cuyos rangos se cruzan
  se cierran con ``bloque_tomado`` y autor el maestro (D-12, CA-23.5).
- ``rechazar`` (el maestro): pendiente → cerrado ``rechazado_maestro``. El
  horario queda libre porque un pendiente nunca ocupa (CA-15.3, CA-23.4).
- ``cancelar`` (el cliente): pendiente → cerrado ``cancelado_cliente``. Un
  aceptado no se cancela (CA-10.2).
- ``cerrar_vencidos`` (el Sistema, tarea del planificador) y la **protección al
  actuar**: pendiente con ``ahora ≥ vence_en`` → cerrado ``vencido_proximidad``
  si ``inicio_en − 4 h ≤ enviado_en + 24 h`` (28 h exactas cuentan como
  proximidad, CA-23.6) y ``vencido_plazo`` en otro caso.

Repetir una acción ya aplicada devuelve el estado actual (D-10). Cualquier otra
transición: ``ErrorEstado`` (409) con un mensaje accionable.

Concurrencia (D-9): primero ``select_for_update`` del expediente del maestro
y después los tickets por id ascendente. Cada cambio escribe su
``ticket_evento`` y sus avisos (``ticket_aceptado`` al cliente;
``ticket_cerrado`` a ambas partes, CA-23.7) en la misma transacción.

Precio final (S5, incremento 1; RF-26 a RF-28, CA-16.1 a CA-16.3; ADR-026, E-1;
propuesta del S5, §3.2):

- ``registrar_precio`` (el maestro): en ``aceptado`` y con ``ahora ≥ inicio_en``.
  Si se exige aceptación (por hora, o por trabajo con un monto distinto del
  publicado) queda "por aceptar" y se avisa al cliente (``precio_registrado``);
  si no, la orden pasa a ``finalizado`` (``orden_finalizada`` al cliente).
- ``aceptar_precio`` (el cliente): envía el monto que acepta; si no es el
  vigente → 409. La orden pasa a ``finalizado`` (``orden_finalizada`` al maestro).
- ``objetar_precio`` (el cliente): vacía el precio vigente y avisa al maestro
  (``precio_objetado``).
- Una orden ``finalizado`` no cambia de precio (CA-16.3). Repetir lo mismo → 200 (D-10).

Cada acción escribe su ``precio_final_evento``; el paso a ``finalizado``, su
``ticket_evento`` con el autor. Los avisos de precio se **reactivan** si ya
existían (el único ``aviso_ticket_una_vez``), como ``mensaje_nuevo`` (ADR-026, E-2).

La parte que actúa ya la verificaron la política y la vista (ADR-023, punto 6).
"""
from django.db import transaction
from django.db.models import Q
import datetime

from django.utils import timezone

from expediente import vigencia
from expediente.errores import ErrorEstado
from catalogo.models import Modalidad
from expediente.models import Expediente
from perfil import publicacion
from tickets.avisos import MOTIVOS_PARA_CLIENTE, MOTIVOS_PARA_MAESTRO
from tickets.models import (
    ANTICIPACION_MINIMA,
    ESTADOS_QUE_OCUPAN,
    PLAZO_RESPUESTA,
    AutorTipo,
    AccionPrecio,
    AvisoTicket,
    EstadoTicket,
    MotivoCierre,
    PrecioFinalEvento,
    Ticket,
    TicketEvento,
    TipoAvisoTicket,
)

LOTE_CIERRE = 200

MENSAJE_SERVICIO_NO_VISIBLE = (
    "Ese servicio ya no está publicado en tu perfil y no puedes aceptar el pedido. "
    "Revisa tus servicios y tus documentos, o rechaza el pedido."
)
MENSAJE_CRUCE = (
    "Ya aceptaste otro trabajo que se cruza con este horario. Rechaza este pedido para avisarle al cliente."
)
MENSAJE_FINALIZADO = "Este trabajo ya terminó y no se puede cambiar."
MENSAJE_YA_ACEPTADO_RECHAZO = (
    "Ya aceptaste este pedido y no se puede rechazar. Si no puedes hacerlo, coordínalo con el cliente."
)
MENSAJE_YA_ACEPTADO_CANCELACION = (
    "El maestro ya aceptó este pedido y no se puede cancelar. "
    "Coordínalo con él por la conversación del trabajo aceptado."
)
MENSAJE_CERRADO_MAESTRO = "Este pedido se cerró: {motivo}. Ya no se puede responder."
MENSAJE_CERRADO_CLIENTE = (
    "Tu pedido se cerró: {motivo}. Si todavía necesitas el trabajo, busca otro horario o maestro."
)

# Precio final (CA-16.x). Vocabulario del oficio: "pedido", "trabajo", "horario".
MENSAJE_PRECIO_ANTES_DEL_HORARIO = (
    "Todavía no empieza el horario de este trabajo. Podrás registrar el precio final cuando empiece."
)
MENSAJE_PRECIO_SIN_ACEPTAR = "Primero acepta el pedido. El precio final se registra en un trabajo aceptado."
MENSAJE_PRECIO_FINALIZADO = "Este trabajo ya terminó y su precio no se puede cambiar."
MENSAJE_SIN_PRECIO_POR_ACEPTAR = (
    "Este trabajo no tiene un precio por aceptar. Cuando el maestro registre el precio final, te avisaremos."
)
MENSAJE_MONTO_CAMBIO = "El maestro cambió el monto, revísalo antes de aceptarlo."
MENSAJE_PEDIDO_SIN_PRECIO = "El maestro todavía no acepta este pedido, así que no tiene precio final."


class PedidoVencido(ErrorEstado):
    """Protección al actuar: el pendiente venció y se acaba de cerrar (409). El cierre ya quedó guardado."""


def motivo_vencimiento(ticket):
    """CA-23.6: a las 28 horas exactas (o menos) gana la proximidad del horario."""
    # En UTC, como calcular_vence_en (DEF-QA-005).
    if ticket.inicio_en.astimezone(datetime.timezone.utc) - ANTICIPACION_MINIMA <= ticket.enviado_en + PLAZO_RESPUESTA:
        return MotivoCierre.VENCIDO_PROXIMIDAD
    return MotivoCierre.VENCIDO_PLAZO


def mensaje_cerrado(ticket, para_maestro):
    motivos = MOTIVOS_PARA_MAESTRO if para_maestro else MOTIVOS_PARA_CLIENTE
    plantilla = MENSAJE_CERRADO_MAESTRO if para_maestro else MENSAJE_CERRADO_CLIENTE
    return plantilla.format(motivo=motivos[ticket.motivo_cierre])


# --- Escrituras (siempre dentro de una transacción con el ticket bloqueado) ---


def _evento(ticket, anterior, ahora, autor_id):
    TicketEvento.objects.create(
        ticket_id=ticket.pk,
        fecha=ahora,
        estado_anterior=anterior,
        estado_nuevo=ticket.estado,
        motivo=ticket.motivo_cierre,
        autor_tipo=AutorTipo.SISTEMA if autor_id is None else AutorTipo.USUARIO,
        autor_id=autor_id,
    )


def _cerrar(ticket, motivo, ahora, autor_id):
    """pendiente → cerrado. ``autor_id`` ``None``: el Sistema. Avisa a ambas partes (RF-24, CA-23.7)."""
    ticket.estado = EstadoTicket.CERRADO
    ticket.motivo_cierre = motivo
    ticket.cerrado_en = ahora
    ticket.save(update_fields=["estado", "motivo_cierre", "cerrado_en"])
    _evento(ticket, EstadoTicket.PENDIENTE, ahora, autor_id)
    AvisoTicket.objects.bulk_create([
        AvisoTicket(ticket=ticket, destinatario_id=destinatario, tipo=TipoAvisoTicket.TICKET_CERRADO, creado_en=ahora)
        for destinatario in (ticket.cliente_id, ticket.perfil_maestro_id)
    ])


def _bloquear_maestro(maestro_id):
    """D-9: el expediente del maestro primero (serializa creación, aceptación y cierre)."""
    Expediente.objects.select_for_update().filter(perfil_maestro_id=maestro_id).first()


def _vencido(ticket, ahora):
    return ticket.estado == EstadoTicket.PENDIENTE and ahora >= ticket.vence_en


def _actuar(ticket, ahora, para_maestro, aplicar, filtro_extra=None):
    """Bloquea, aplica la protección al actuar y, si no venció, ``aplicar(ticket_bloqueado, bloqueados)``."""
    with transaction.atomic():
        _bloquear_maestro(ticket.perfil_maestro_id)
        filtro = Q(pk=ticket.pk) | filtro_extra if filtro_extra is not None else Q(pk=ticket.pk)
        bloqueados = list(Ticket.objects.select_for_update().filter(filtro).order_by("id"))
        actual = next(t for t in bloqueados if t.pk == ticket.pk)
        if not _vencido(actual, ahora):
            return aplicar(actual, [t for t in bloqueados if t.pk != ticket.pk])
        _cerrar(actual, motivo_vencimiento(actual), ahora, None)
    raise PedidoVencido(mensaje_cerrado(actual, para_maestro))


# --- Casos de uso ---


def aceptar(ticket, usuario, ahora=None):
    """RF-19. Devuelve el ticket actualizado (o el mismo, si ya estaba aceptado)."""
    ahora = ahora or timezone.now()
    cruces = Q(
        perfil_maestro_id=ticket.perfil_maestro_id, estado=EstadoTicket.PENDIENTE,
        inicio_en__lt=ticket.fin_en, fin_en__gt=ticket.inicio_en,
    )

    def aplicar(actual, otros):
        if actual.estado == EstadoTicket.ACEPTADO:
            return actual
        if actual.estado == EstadoTicket.FINALIZADO:
            raise ErrorEstado(MENSAJE_FINALIZADO)
        if actual.estado == EstadoTicket.CERRADO:
            raise ErrorEstado(mensaje_cerrado(actual, para_maestro=True))
        hoy = vigencia.hoy_negocio(ahora)
        if publicacion.motivos_no_visible(actual.servicio_maestro, hoy):
            raise ErrorEstado(MENSAJE_SERVICIO_NO_VISIBLE)
        ocupado = Ticket.objects.filter(
            perfil_maestro_id=actual.perfil_maestro_id, estado__in=ESTADOS_QUE_OCUPAN,
            inicio_en__lt=actual.fin_en, fin_en__gt=actual.inicio_en,
        ).exists()
        if ocupado:
            raise ErrorEstado(MENSAJE_CRUCE)
        actual.estado = EstadoTicket.ACEPTADO
        actual.aceptado_en = ahora
        actual.save(update_fields=["estado", "aceptado_en"])
        _evento(actual, EstadoTicket.PENDIENTE, ahora, usuario.pk)
        AvisoTicket.objects.create(
            ticket=actual, destinatario_id=actual.cliente_id, tipo=TipoAvisoTicket.TICKET_ACEPTADO, creado_en=ahora
        )
        # D-12: los pendientes que se cruzan. Uno ya vencido se cierra por su vencimiento (ocurrió primero, CA-23.6).
        for otro in otros:
            if _vencido(otro, ahora):
                _cerrar(otro, motivo_vencimiento(otro), ahora, None)
            elif otro.estado == EstadoTicket.PENDIENTE:
                _cerrar(otro, MotivoCierre.BLOQUE_TOMADO, ahora, usuario.pk)
        return actual

    return _actuar(ticket, ahora, True, aplicar, cruces)


def rechazar(ticket, usuario, ahora=None):
    """RF-20, CA-15.3, CA-23.4."""
    ahora = ahora or timezone.now()

    def aplicar(actual, _otros):
        if actual.estado == EstadoTicket.CERRADO and actual.motivo_cierre == MotivoCierre.RECHAZADO_MAESTRO:
            return actual
        if actual.estado == EstadoTicket.ACEPTADO:
            raise ErrorEstado(MENSAJE_YA_ACEPTADO_RECHAZO)
        if actual.estado == EstadoTicket.FINALIZADO:
            raise ErrorEstado(MENSAJE_FINALIZADO)
        if actual.estado == EstadoTicket.CERRADO:
            raise ErrorEstado(mensaje_cerrado(actual, para_maestro=True))
        _cerrar(actual, MotivoCierre.RECHAZADO_MAESTRO, ahora, usuario.pk)
        return actual

    return _actuar(ticket, ahora, True, aplicar)


def cancelar(ticket, usuario, ahora=None):
    """RF-23, CA-23.3; CA-10.2: un aceptado no se cancela."""
    ahora = ahora or timezone.now()

    def aplicar(actual, _otros):
        if actual.estado == EstadoTicket.CERRADO and actual.motivo_cierre == MotivoCierre.CANCELADO_CLIENTE:
            return actual
        if actual.estado == EstadoTicket.ACEPTADO:
            raise ErrorEstado(MENSAJE_YA_ACEPTADO_CANCELACION)
        if actual.estado == EstadoTicket.FINALIZADO:
            raise ErrorEstado(MENSAJE_FINALIZADO)
        if actual.estado == EstadoTicket.CERRADO:
            raise ErrorEstado(mensaje_cerrado(actual, para_maestro=False))
        _cerrar(actual, MotivoCierre.CANCELADO_CLIENTE, ahora, usuario.pk)
        return actual

    return _actuar(ticket, ahora, False, aplicar)


def cerrar_si_vencido(ticket, ahora):
    """Protección al actuar para quien no pasa por ``_actuar`` (el pedido repetido de D-10).

    Debe llamarse dentro de una transacción que ya bloqueó el expediente del maestro.
    Devuelve ``True`` si lo cerró.
    """
    actual = Ticket.objects.select_for_update().get(pk=ticket.pk)
    if not _vencido(actual, ahora):
        return False
    _cerrar(actual, motivo_vencimiento(actual), ahora, None)
    ticket.estado, ticket.motivo_cierre, ticket.cerrado_en = actual.estado, actual.motivo_cierre, actual.cerrado_en
    return True


# --- Precio final (S5, incremento 1; ADR-026, E-1) ---


def exige_aceptacion(ticket, monto):
    """ADR-026, E-1.2: por hora siempre; por trabajo si el monto final difiere del publicado (RF-27)."""
    return ticket.modalidad == Modalidad.POR_HORA or monto != ticket.monto_publicado


def _evento_precio(ticket, accion, monto, autor_id, ahora):
    PrecioFinalEvento.objects.create(ticket_id=ticket.pk, accion=accion, monto=monto, autor_id=autor_id, fecha=ahora)


def _avisar(ticket, destinatario_id, tipo, ahora):
    """Crea el aviso o, si ya existía (único por ticket, destinatario y tipo), lo reactiva."""
    reactivados = AvisoTicket.objects.filter(ticket=ticket, destinatario_id=destinatario_id, tipo=tipo).update(
        creado_en=ahora, visto_en=None
    )
    if not reactivados:
        AvisoTicket.objects.create(ticket=ticket, destinatario_id=destinatario_id, tipo=tipo, creado_en=ahora)


def _finalizar(ticket, ahora, autor_id, destinatario_id):
    ticket.estado = EstadoTicket.FINALIZADO
    ticket.finalizado_en = ahora
    ticket.save(update_fields=["estado", "finalizado_en", "monto_final", "monto_final_en", "monto_final_autor",
                               "precio_aceptado_en"])
    _evento(ticket, EstadoTicket.ACEPTADO, ahora, autor_id)
    _avisar(ticket, destinatario_id, TipoAvisoTicket.ORDEN_FINALIZADA, ahora)


def _sin_precio_posible(actual, para_maestro):
    """409 de los estados en que no hay precio: pendiente o cerrado."""
    if actual.estado == EstadoTicket.CERRADO:
        return ErrorEstado(mensaje_cerrado(actual, para_maestro))
    return ErrorEstado(MENSAJE_PRECIO_SIN_ACEPTAR if para_maestro else MENSAJE_PEDIDO_SIN_PRECIO)


def registrar_precio(ticket, usuario, monto, ahora=None):
    """RF-26, CA-16.1. ``monto`` ya validado (entero de 1 a ``MONTO_MAXIMO``)."""
    ahora = ahora or timezone.now()

    def aplicar(actual, _otros):
        if actual.estado == EstadoTicket.FINALIZADO:
            if actual.monto_final == monto:
                return actual
            raise ErrorEstado(MENSAJE_PRECIO_FINALIZADO)
        if actual.estado != EstadoTicket.ACEPTADO:
            raise _sin_precio_posible(actual, para_maestro=True)
        if actual.monto_final == monto:
            return actual
        if ahora < actual.inicio_en:
            raise ErrorEstado(MENSAJE_PRECIO_ANTES_DEL_HORARIO)
        actual.monto_final, actual.monto_final_en, actual.monto_final_autor_id = monto, ahora, usuario.pk
        _evento_precio(actual, AccionPrecio.REGISTRADO, monto, usuario.pk, ahora)
        if exige_aceptacion(actual, monto):
            actual.save(update_fields=["monto_final", "monto_final_en", "monto_final_autor"])
            _avisar(actual, actual.cliente_id, TipoAvisoTicket.PRECIO_REGISTRADO, ahora)
        else:
            _finalizar(actual, ahora, usuario.pk, actual.cliente_id)
        return actual

    return _actuar(ticket, ahora, True, aplicar)


def aceptar_precio(ticket, usuario, monto, ahora=None):
    """RF-27, CA-16.2. El cliente envía el monto que acepta (ADR-026, E-1.4)."""
    ahora = ahora or timezone.now()

    def aplicar(actual, _otros):
        if actual.estado == EstadoTicket.FINALIZADO:
            if actual.monto_final == monto:
                return actual
            raise ErrorEstado(MENSAJE_PRECIO_FINALIZADO)
        if actual.estado != EstadoTicket.ACEPTADO:
            raise _sin_precio_posible(actual, para_maestro=False)
        if actual.monto_final is None:
            raise ErrorEstado(MENSAJE_SIN_PRECIO_POR_ACEPTAR)
        if actual.monto_final != monto:
            raise ErrorEstado(MENSAJE_MONTO_CAMBIO)
        actual.precio_aceptado_en = ahora
        _evento_precio(actual, AccionPrecio.ACEPTADO, monto, usuario.pk, ahora)
        _finalizar(actual, ahora, usuario.pk, actual.perfil_maestro_id)
        return actual

    return _actuar(ticket, ahora, False, aplicar)


def objetar_precio(ticket, usuario, ahora=None):
    """ADR-026, E-1.5. Repetir la objeción (el último evento ya es una objeción) → 200."""
    ahora = ahora or timezone.now()

    def aplicar(actual, _otros):
        if actual.estado == EstadoTicket.FINALIZADO:
            raise ErrorEstado(MENSAJE_PRECIO_FINALIZADO)
        if actual.estado != EstadoTicket.ACEPTADO:
            raise _sin_precio_posible(actual, para_maestro=False)
        if actual.monto_final is None:
            ultimo = PrecioFinalEvento.objects.filter(ticket_id=actual.pk).order_by("-fecha", "-id").first()
            if ultimo is not None and ultimo.accion == AccionPrecio.OBJETADO:
                return actual
            raise ErrorEstado(MENSAJE_SIN_PRECIO_POR_ACEPTAR)
        _evento_precio(actual, AccionPrecio.OBJETADO, actual.monto_final, usuario.pk, ahora)
        actual.monto_final = actual.monto_final_en = actual.monto_final_autor_id = None
        actual.save(update_fields=["monto_final", "monto_final_en", "monto_final_autor"])
        _avisar(actual, actual.perfil_maestro_id, TipoAvisoTicket.PRECIO_OBJETADO, ahora)
        return actual

    return _actuar(ticket, ahora, False, aplicar)


# --- Tarea del Sistema (RF-21, RF-22; ADR-016 E-1) ---


def cerrar_vencidos(ahora=None):
    """Cierra los pendientes con ``ahora ≥ vence_en``. Idempotente; devuelve cuántos cerró.

    Por lotes de ``LOTE_CIERRE``, cada lote en su transacción, con ``skip_locked``
    (ADR-023, punto 4): uno que otra transacción tiene bloqueado (una acción en
    curso) se deja para la corrida siguiente. No bloquea el expediente: con
    ``ahora ≥ vence_en`` ninguna aceptación puede tener éxito, y como nunca
    espera un bloqueo de ticket, no invierte el orden de D-9.
    """
    ahora = ahora or timezone.now()
    cerrados = 0
    while True:
        with transaction.atomic():
            lote = list(
                Ticket.objects.select_for_update(skip_locked=True)
                .filter(estado=EstadoTicket.PENDIENTE, vence_en__lte=ahora)
                .order_by("id")[:LOTE_CIERRE]
            )
            for ticket in lote:
                _cerrar(ticket, motivo_vencimiento(ticket), ahora, None)
        cerrados += len(lote)
        if len(lote) < LOTE_CIERRE:
            return cerrados
