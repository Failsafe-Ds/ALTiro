"""Serialización del ticket según la relación con **ese** ticket (RF-17, RNF-08, CA-06.3, CA-15.1; ADR-023, punto 5).

Dos listas explícitas de campos, nunca el modelo completo:

- ``para_cliente``: lo que pidió (con su dirección, CA-06.3) y el maestro
  (ref pública y nombre). El teléfono del maestro solo si el ticket fue
  aceptado (D-21, contacto mutuo).
- ``para_maestro``: servicio, descripción, **comuna**, bloque y materiales
  (CA-15.1). Mientras está pendiente, **sin** dirección, teléfono ni nombre
  del cliente (RF-17, RNF-08, D-13): esos datos no salen del servidor. El
  bloque ``contacto`` (nombre, teléfono y dirección) solo existe si el ticket
  fue aceptado; un ticket cerrado desde pendiente nunca la revela.

Nunca: ids internos (salvo ``numero``, el número visible de ADR-023, punto 1),
RUT, correo, la comuna del perfil del cliente ni datos del expediente.
``consulta()`` carga en una sola consulta todo lo que usan las dos listas.
"""
from django.utils import timezone

from catalogo.models import Modalidad
from perfil import agenda, ocurrencias
from tickets.models import ESTADOS_QUE_OCUPAN, Ticket


def consulta():
    return Ticket.objects.select_related(
        "servicio_maestro__servicio__oficio",
        "comuna",
        "cliente__usuario",
        "perfil_maestro__usuario",
        "perfil_maestro__perfil_publico",
    )


def _instante(valor):
    return None if valor is None else timezone.localtime(valor, ocurrencias.ZONA).isoformat()


def _comunes(ticket):
    servicio = ticket.servicio_maestro.servicio
    return {
        "ref": str(ticket.ref),
        "numero": ticket.id,
        "estado": ticket.estado,
        "motivo_cierre": ticket.motivo_cierre,
        "servicio": {
            "ref": str(servicio.ref),
            "nombre": servicio.nombre,
            "oficio": {"codigo": servicio.oficio.codigo, "nombre": servicio.oficio.nombre},
        },
        "comuna": {"codigo": str(ticket.comuna_id), "nombre": ticket.comuna.nombre},
        "bloque": {
            "fecha": ticket.fecha.isoformat(),
            "inicio": agenda.formato_hora(ticket.inicio_min),
            "fin": agenda.formato_hora(ticket.fin_min),
        },
        "descripcion": ticket.descripcion,
        "materiales": ticket.materiales,
        "modalidad": ticket.modalidad,
        "modalidad_texto": Modalidad(ticket.modalidad).label,
        "monto_publicado": ticket.monto_publicado,
        "enviado_en": _instante(ticket.enviado_en),
        "vence_en": _instante(ticket.vence_en),
        "aceptado_en": _instante(ticket.aceptado_en),
        "finalizado_en": _instante(ticket.finalizado_en),
        "cerrado_en": _instante(ticket.cerrado_en),
    }


def fue_aceptado(ticket):
    """El contacto solo existe si el ticket fue aceptado (aceptado o finalizado; ADR-023, punto 5)."""
    return ticket.estado in ESTADOS_QUE_OCUPAN


def para_cliente(ticket):
    datos = _comunes(ticket)
    maestro = ticket.perfil_maestro
    datos["direccion"] = ticket.direccion
    datos["maestro"] = {"ref": str(maestro.perfil_publico.ref), "nombre": maestro.usuario.nombre}
    if fue_aceptado(ticket):
        datos["contacto"] = {"telefono": maestro.usuario.telefono}
    return datos


def para_maestro(ticket):
    datos = _comunes(ticket)
    if fue_aceptado(ticket):
        cliente = ticket.cliente.usuario
        datos["contacto"] = {"nombre": cliente.nombre, "telefono": cliente.telefono, "direccion": ticket.direccion}
    return datos


def para(ticket, usuario):
    """Serialización según la relación de ``usuario`` con el ticket. La política ya exigió que sea una parte."""
    if usuario.pk == ticket.cliente_id:
        return para_cliente(ticket)
    if usuario.pk == ticket.perfil_maestro_id:
        return para_maestro(ticket)
    raise ValueError("Solo las partes del ticket tienen una serialización.")
