"""Avisos de tickets dentro de la aplicación (RF-18, RF-24, CA-15.3, CA-23.7; ADR-024).

- Sin consultas periódicas (ADR-024, punto 3): la pantalla los pide al abrirse
  y con el botón "Actualizar".
- La tabla no guarda datos personales: ``texto`` arma el mensaje al leerlo,
  desde el punto de vista de quien lo recibe y solo con lo que su
  serialización del ticket le permite ver (ADR-023, punto 5). El aviso de un
  pedido nuevo nunca nombra al cliente ni su dirección (RF-17, D-13).
- ``marcar_vistos``: solo los avisos del propio usuario. Las refs ajenas o
  inexistentes se ignoran sin decir cuáles (no se revela si existen).
Vocabulario de pantalla: "pedido" y "horario" (ADR-024, punto 4; RNF-17).
"""
from django.utils import timezone

from perfil import agenda, ocurrencias
from tickets.models import AvisoTicket, MotivoCierre, TipoAvisoTicket

DIAS = agenda.DIAS
MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

# Motivo de cierre, según quién lee (CA-23.7).
MOTIVOS_PARA_CLIENTE = {
    MotivoCierre.VENCIDO_PLAZO: "el maestro no respondió en 24 horas",
    MotivoCierre.VENCIDO_PROXIMIDAD: "faltaban 4 horas o menos para el horario y el maestro no respondió",
    MotivoCierre.CANCELADO_CLIENTE: "lo cancelaste",
    MotivoCierre.RECHAZADO_MAESTRO: "el maestro no puede tomarlo",
    MotivoCierre.BLOQUE_TOMADO: "el maestro tomó otro trabajo en ese horario",
}
MOTIVOS_PARA_MAESTRO = {
    MotivoCierre.VENCIDO_PLAZO: "pasaron 24 horas sin tu respuesta",
    MotivoCierre.VENCIDO_PROXIMIDAD: "faltaban 4 horas o menos para el horario y no respondiste",
    MotivoCierre.CANCELADO_CLIENTE: "el cliente lo canceló",
    MotivoCierre.RECHAZADO_MAESTRO: "lo rechazaste",
    MotivoCierre.BLOQUE_TOMADO: "aceptaste otro trabajo en ese horario",
}


def cuando(ticket):
    """"el jueves 8 de octubre, de 08:00 a 12:00" (formato de 24 horas, CA-14.1)."""
    fecha = ticket.fecha
    return (
        f"el {DIAS[fecha.isoweekday()]} {fecha.day} de {MESES[fecha.month - 1]}, "
        f"de {agenda.formato_hora(ticket.inicio_min)} a {agenda.formato_hora(ticket.fin_min)}"
    )


def texto(aviso, ticket):
    """Mensaje del aviso para su destinatario. ``ticket`` trae cargado lo de ``serializacion.consulta``."""
    servicio = ticket.servicio_maestro.servicio.nombre
    para_maestro = aviso.destinatario_id == ticket.perfil_maestro_id
    if aviso.tipo == TipoAvisoTicket.TICKET_NUEVO:
        return f"Tienes un pedido nuevo: {servicio} en {ticket.comuna.nombre}, {cuando(ticket)}. Revísalo y responde."
    if aviso.tipo == TipoAvisoTicket.TICKET_ACEPTADO:
        nombre = ticket.perfil_maestro.usuario.nombre
        return f"{nombre} aceptó tu pedido de {servicio} para {cuando(ticket)}."
    motivos = MOTIVOS_PARA_MAESTRO if para_maestro else MOTIVOS_PARA_CLIENTE
    motivo = motivos.get(ticket.motivo_cierre, "")
    dueno = "El pedido" if para_maestro else "Tu pedido"
    return f"{dueno} de {servicio} para {cuando(ticket)} se cerró: {motivo}."


def datos_aviso(aviso):
    return {
        "ref": str(aviso.ref),
        "tipo": aviso.tipo,
        "texto": texto(aviso, aviso.ticket),
        "ticket": str(aviso.ticket.ref),
        "creado_en": timezone.localtime(aviso.creado_en, ocurrencias.ZONA).isoformat(),
        "visto": aviso.visto_en is not None,
    }


def del_usuario(usuario_id):
    """Avisos de ``usuario_id``, del más nuevo al más antiguo, con lo que usa ``texto``."""
    return (
        AvisoTicket.objects.filter(destinatario_id=usuario_id)
        .select_related(
            "ticket__servicio_maestro__servicio", "ticket__comuna", "ticket__perfil_maestro__usuario"
        )
        .order_by("-creado_en", "-id")
    )


def sin_ver(usuario_id):
    return AvisoTicket.objects.filter(destinatario_id=usuario_id, visto_en__isnull=True).count()


def marcar_vistos(usuario_id, refs, ahora=None):
    """Marca como vistos los avisos de ``usuario_id`` con esas refs. Devuelve cuántos cambió."""
    ahora = ahora or timezone.now()
    return AvisoTicket.objects.filter(destinatario_id=usuario_id, ref__in=refs, visto_en__isnull=True).update(
        visto_en=ahora
    )
