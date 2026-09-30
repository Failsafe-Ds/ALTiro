"""Reglas de la conversación de un ticket (RF-25, CA-07.1 a CA-07.3, CA-15.2; ADR-026, E-2).

- Solo las dos partes (``PoliticaTicket``, en la vista).
- Se escribe solo en ``aceptado``; se lee en ``aceptado`` y ``finalizado``. En
  ``cerrado`` no hubo conversación (solo se llega desde ``pendiente``). En
  ``pendiente``, todavía no existe (P-31).
- ``clave_envio``: un reenvío con la misma clave devuelve el mismo mensaje.
- Cada mensaje deja (o reactiva) el aviso ``mensaje_nuevo`` a la otra parte.
"""
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from expediente.errores import ErrorEstado
from mensajeria.models import Mensaje
from perfil import ocurrencias
from tickets import avisos
from tickets.models import EstadoTicket, Ticket, TipoAvisoTicket

MENSAJE_PENDIENTE = (
    "La conversación se abre cuando el maestro acepta el pedido. Mientras tanto, revisa el estado en tus pedidos."
)
MENSAJE_FINALIZADO = "Este trabajo ya terminó: puedes leer la conversación, pero ya no enviar mensajes."
MENSAJE_CERRADO = "Este pedido se cerró sin ser aceptado, así que no hubo conversación."

AVISO_FINALIZADO = "Este trabajo terminó. Puedes leer la conversación, pero ya no enviar mensajes."
AVISO_CERRADO = "No hubo conversación: este pedido se cerró antes de que el maestro lo aceptara."


class ReferenciaDesconocida(Exception):
    """``despues`` no es un mensaje de esta conversación."""


def _autor(mensaje, usuario, ticket):
    """"tu", "cliente" o "maestro", desde el punto de vista de quien lee. Sin ids ni nombres."""
    if mensaje.autor_id == usuario.pk:
        return "tu"
    return "cliente" if mensaje.autor_id == ticket.cliente_id else "maestro"


def datos_mensaje(mensaje, usuario, ticket):
    return {
        "ref": str(mensaje.ref),
        "texto": mensaje.texto,
        "enviado_en": timezone.localtime(mensaje.enviado_en, ocurrencias.ZONA).isoformat(),
        "autor": _autor(mensaje, usuario, ticket),
    }


def leer(ticket, usuario, despues=None):
    """Mensajes en orden de envío; con ``despues`` (ref), solo los posteriores a ese."""
    if ticket.estado == EstadoTicket.PENDIENTE:
        raise ErrorEstado(MENSAJE_PENDIENTE)
    datos = {
        "estado": ticket.estado,
        "puede_escribir": ticket.estado == EstadoTicket.ACEPTADO,
        "aviso": {EstadoTicket.FINALIZADO: AVISO_FINALIZADO, EstadoTicket.CERRADO: AVISO_CERRADO}.get(ticket.estado),
        "mensajes": [],
    }
    if ticket.estado == EstadoTicket.CERRADO:
        return datos
    consulta = Mensaje.objects.filter(ticket_id=ticket.pk)
    if despues is not None:
        ultimo = consulta.filter(ref=despues).values("enviado_en", "id").first()
        if ultimo is None:
            raise ReferenciaDesconocida
        consulta = consulta.filter(
            Q(enviado_en__gt=ultimo["enviado_en"]) | Q(enviado_en=ultimo["enviado_en"], id__gt=ultimo["id"])
        )
    datos["mensajes"] = [datos_mensaje(m, usuario, ticket) for m in consulta.order_by("enviado_en", "id")]
    return datos


def _existente(ticket, usuario, clave_envio):
    return Mensaje.objects.filter(ticket_id=ticket.pk, autor_id=usuario.pk, clave_envio=clave_envio).first()


def enviar(ticket, usuario, texto, clave_envio):
    """Guarda el mensaje. Devuelve ``(mensaje, creado)``; un reenvío con la misma clave no duplica."""
    with transaction.atomic():
        # El bloqueo del ticket ordena el envío frente a una finalización simultánea.
        actual = Ticket.objects.select_for_update().get(pk=ticket.pk)
        repetido = _existente(actual, usuario, clave_envio)
        if repetido is not None:
            return repetido, False
        if actual.estado == EstadoTicket.PENDIENTE:
            raise ErrorEstado(MENSAJE_PENDIENTE)
        if actual.estado == EstadoTicket.FINALIZADO:
            raise ErrorEstado(MENSAJE_FINALIZADO)
        if actual.estado != EstadoTicket.ACEPTADO:
            raise ErrorEstado(MENSAJE_CERRADO)
        ahora = timezone.now()
        try:
            with transaction.atomic():
                mensaje = Mensaje.objects.create(
                    ticket_id=actual.pk, autor_id=usuario.pk, texto=texto, enviado_en=ahora, clave_envio=clave_envio
                )
        except IntegrityError:
            # Defensa: el bloqueo ya ordena los reenvíos; si otra petición con la misma clave ganó, ese mensaje.
            repetido = _existente(actual, usuario, clave_envio)
            if repetido is None:
                raise
            return repetido, False
        otra_parte = actual.perfil_maestro_id if usuario.pk == actual.cliente_id else actual.cliente_id
        avisos.emitir(actual, otra_parte, TipoAvisoTicket.MENSAJE_NUEVO, ahora)
    return mensaje, True
