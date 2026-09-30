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

La parte que actúa ya la verificaron la política y la vista (ADR-023, punto 6).
"""
from django.db import transaction
from django.db.models import Q
import datetime

from django.utils import timezone

from expediente import vigencia
from expediente.errores import ErrorEstado
from expediente.models import Expediente
from perfil import publicacion
from tickets.avisos import MOTIVOS_PARA_CLIENTE, MOTIVOS_PARA_MAESTRO
from tickets.models import (
    ANTICIPACION_MINIMA,
    ESTADOS_QUE_OCUPAN,
    PLAZO_RESPUESTA,
    AutorTipo,
    AvisoTicket,
    EstadoTicket,
    MotivoCierre,
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
