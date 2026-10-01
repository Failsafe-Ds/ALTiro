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

Ambas agregan ``precio`` (el precio final vigente, el mismo monto para las dos
partes; ``None`` si no hay) y ``motivo_cierre_texto`` en palabras de quien lee
(historial, CA-08.2). ``para_maestro`` agrega ``precio_registrable`` (RF-26:
aceptado y con el horario ya empezado).

Nunca: ids internos (salvo ``numero``, el número visible de ADR-023, punto 1),
RUT, correo, la comuna del perfil del cliente ni datos del expediente.
``consulta()`` carga en una sola consulta todo lo que usan las dos listas.
"""
from django.utils import timezone

from catalogo.models import Modalidad
from perfil import agenda, ocurrencias
from tickets import avisos
from tickets.models import ESTADOS_QUE_OCUPAN, EstadoTicket, Ticket


def consulta():
    return Ticket.objects.select_related(
        "servicio_maestro__servicio__oficio",
        "comuna",
        "cliente__usuario",
        "perfil_maestro__usuario",
        "perfil_maestro__perfil_publico",
    )


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
        "enviado_en": ocurrencias.iso_local(ticket.enviado_en),
        "vence_en": ocurrencias.iso_local(ticket.vence_en),
        "aceptado_en": ocurrencias.iso_local(ticket.aceptado_en),
        "finalizado_en": ocurrencias.iso_local(ticket.finalizado_en),
        "cerrado_en": ocurrencias.iso_local(ticket.cerrado_en),
    }


def _precio(ticket):
    """Precio final vigente (RF-26, RF-28): "por_aceptar" mientras está aceptado, "acordado" al finalizar."""
    if ticket.monto_final is None:
        return None
    return {
        "monto": ticket.monto_final,
        "estado": "acordado" if ticket.estado == EstadoTicket.FINALIZADO else "por_aceptar",
        "registrado_en": ocurrencias.iso_local(ticket.monto_final_en),
        "aceptado_en": ocurrencias.iso_local(ticket.precio_aceptado_en),
    }


def _con_historial(datos, ticket, para_maestro):
    datos["precio"] = _precio(ticket)
    datos["motivo_cierre_texto"] = avisos.motivo_cierre_texto(ticket, para_maestro)
    return datos


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
    return _con_historial(datos, ticket, para_maestro=False)


def para_maestro(ticket):
    datos = _comunes(ticket)
    if fue_aceptado(ticket):
        cliente = ticket.cliente.usuario
        datos["contacto"] = {"nombre": cliente.nombre, "telefono": cliente.telefono, "direccion": ticket.direccion}
    datos["precio_registrable"] = ticket.estado == EstadoTicket.ACEPTADO and timezone.now() >= ticket.inicio_en
    return _con_historial(datos, ticket, para_maestro=True)


def para(ticket, usuario):
    """Serialización según la relación de ``usuario`` con el ticket. La política ya exigió que sea una parte."""
    if usuario.pk == ticket.cliente_id:
        return para_cliente(ticket)
    if usuario.pk == ticket.perfil_maestro_id:
        return para_maestro(ticket)
    raise ValueError("Solo las partes del ticket tienen una serialización.")
