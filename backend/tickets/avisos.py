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
from urllib.parse import urlencode

from django.db import IntegrityError, transaction
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


def pesos(monto):
    """"$45.000" (separador de miles chileno)."""
    return f"${monto:,}".replace(",", ".")


def motivo_cierre_texto(ticket, para_maestro):
    """El motivo de cierre en palabras de quien lee (CA-08.2, CA-23.7). ``None`` si no está cerrado."""
    if not ticket.motivo_cierre:
        return None
    motivos = MOTIVOS_PARA_MAESTRO if para_maestro else MOTIVOS_PARA_CLIENTE
    texto_motivo = motivos[ticket.motivo_cierre]
    return texto_motivo[0].upper() + texto_motivo[1:]


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
    if aviso.tipo == TipoAvisoTicket.PRECIO_REGISTRADO:
        if ticket.monto_final is None or ticket.estado != "aceptado":
            return f"El maestro registró el precio final de {servicio} para {cuando(ticket)}. Revisa tu pedido."
        return (
            f"El maestro registró el precio final de {servicio} para {cuando(ticket)}: {pesos(ticket.monto_final)}. "
            "Revísalo y acéptalo, o avísale si no estás de acuerdo."
        )
    if aviso.tipo == TipoAvisoTicket.PRECIO_OBJETADO:
        return (
            f"El cliente no está de acuerdo con el precio final de {servicio} para {cuando(ticket)}. "
            "Coordínalo con él y vuelve a registrar el precio."
        )
    if aviso.tipo == TipoAvisoTicket.MENSAJE_NUEVO:
        return f"Tienes un mensaje nuevo sobre el pedido de {servicio} para {cuando(ticket)}. Abre la conversación para leerlo."
    if aviso.tipo == TipoAvisoTicket.CONVERSACION_REVISADA:
        # M-04, P-33: se avisa a ambas partes cada vez que moderación abre la conversación.
        return (
            f"Moderación revisó la conversación del pedido de {servicio} de {cuando(ticket)} "
            "porque hay una denuncia sobre una evaluación de ese trabajo."
        )
    if aviso.tipo == TipoAvisoTicket.ORDEN_FINALIZADA:
        return f"El trabajo de {servicio} de {cuando(ticket)} terminó con un precio final de {pesos(ticket.monto_final)}."
    motivos = MOTIVOS_PARA_MAESTRO if para_maestro else MOTIVOS_PARA_CLIENTE
    motivo = motivos.get(ticket.motivo_cierre, "")
    dueno = "El pedido" if para_maestro else "Tu pedido"
    return f"{dueno} de {servicio} para {cuando(ticket)} se cerró: {motivo}."


def enlace(aviso, ticket):
    """CA-23.5: al cliente cuyo pedido se cerró por ``bloque_tomado``, la búsqueda con alternativas.

    Mismo oficio, comuna y horario del pedido, en la página de búsqueda
    (parámetros de ``buscar.html``). ``mensaje_nuevo``: la conversación del
    ticket (ADR-026, E-2). En los demás avisos: ``None``.
    """
    if aviso.tipo == TipoAvisoTicket.MENSAJE_NUEVO:
        return f"/conversacion.html?{urlencode({'ticket': str(ticket.ref)})}"
    if (
        aviso.tipo != TipoAvisoTicket.TICKET_CERRADO
        or ticket.motivo_cierre != MotivoCierre.BLOQUE_TOMADO
        or aviso.destinatario_id != ticket.cliente_id
    ):
        return None
    parametros = {
        "oficio": ticket.servicio_maestro.servicio.oficio.codigo,
        "region": ticket.comuna.provincia.region_id,
        "comuna": ticket.comuna_id,
        "fecha": ticket.fecha.isoformat(),
        "inicio": agenda.formato_hora(ticket.inicio_min),
        "fin": agenda.formato_hora(ticket.fin_min),
    }
    return f"/buscar.html?{urlencode(parametros)}"


def datos_aviso(aviso):
    return {
        "ref": str(aviso.ref),
        "tipo": aviso.tipo,
        "texto": texto(aviso, aviso.ticket),
        "ticket": str(aviso.ticket.ref),
        "creado_en": timezone.localtime(aviso.creado_en, ocurrencias.ZONA).isoformat(),
        "visto": aviso.visto_en is not None,
        "enlace": enlace(aviso, aviso.ticket),
    }


def del_usuario(usuario_id):
    """Avisos de ``usuario_id``, del más nuevo al más antiguo, con lo que usa ``texto``."""
    return (
        AvisoTicket.objects.filter(destinatario_id=usuario_id)
        .select_related(
            "ticket__servicio_maestro__servicio__oficio", "ticket__comuna__provincia", "ticket__perfil_maestro__usuario"
        )
        .order_by("-creado_en", "-id")
    )


def emitir(ticket, destinatario_id, tipo, ahora):
    """Crea el aviso o, si ya existía (único por ticket, destinatario y tipo), lo reactiva.

    Reactivar = ``visto_en=NULL`` con otro ``creado_en`` (ADR-026, E-2.6). Si
    otra petición lo crea al mismo tiempo, el único de la base lo resuelve y se
    reactiva la fila que quedó.
    """
    filas = AvisoTicket.objects.filter(ticket=ticket, destinatario_id=destinatario_id, tipo=tipo)
    if filas.update(creado_en=ahora, visto_en=None):
        return
    try:
        with transaction.atomic():
            AvisoTicket.objects.create(ticket=ticket, destinatario_id=destinatario_id, tipo=tipo, creado_en=ahora)
    except IntegrityError:
        filas.update(creado_en=ahora, visto_en=None)


def sin_ver(usuario_id):
    return AvisoTicket.objects.filter(destinatario_id=usuario_id, visto_en__isnull=True).count()


def marcar_vistos(usuario_id, refs, ahora=None):
    """Marca como vistos los avisos de ``usuario_id`` con esas refs. Devuelve cuántos cambió."""
    ahora = ahora or timezone.now()
    return AvisoTicket.objects.filter(destinatario_id=usuario_id, ref__in=refs, visto_en__isnull=True).update(
        visto_en=ahora
    )
