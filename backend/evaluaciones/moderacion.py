"""Moderación de denuncias (HU-21, RF-31, RF-37, CA-21.1, CA-21.2; ADR-026, E-4; M-04).

- Detalle: la denuncia, la evaluación y un resumen del ticket (servicio,
  comuna, fechas y precio), **sin dirección, teléfono ni nombres** (E-4.5).
- Conversación: reutiliza ``mensajeria.conversacion.leer``. Cada consulta
  escribe en la bitácora ``conversacion_consultada`` (entidad ``ticket``,
  motivo "Denuncia <ref>") y deja el aviso ``conversacion_revisada`` a ambas
  partes (E-4.4, P-33), en la misma transacción.
- Resolución: ``mantener`` o ``retirar`` con motivo obligatorio. Escribe en la
  bitácora ``denuncia_resuelta`` con el estado anterior y el nuevo de la
  evaluación (CA-21.2, RF-37). ``retirar`` no borra: la excluye del promedio.
"""
from django.db import transaction
from django.utils import timezone

from bitacora import servicios as bitacora
from catalogo.models import Modalidad
from evaluaciones.models import DecisionDenuncia, Denuncia, EstadoDenuncia, EstadoEvaluacion, Evaluacion
from evaluaciones.servicios import datos_evaluacion
from expediente.errores import ErrorEstado
from mensajeria import conversacion
from perfil import agenda, ocurrencias
from tickets import avisos
from tickets.models import EstadoTicket, TipoAvisoTicket

ACCION_CONVERSACION = "conversacion_consultada"
ACCION_RESOLUCION = "denuncia_resuelta"
MENSAJE_YA_RESUELTA = "Esta denuncia ya fue resuelta. Revisa la decisión registrada en el detalle."

NUEVO_ESTADO = {DecisionDenuncia.MANTENER: EstadoEvaluacion.PUBLICADA, DecisionDenuncia.RETIRAR: EstadoEvaluacion.RETIRADA}


def consulta():
    return Denuncia.objects.select_related(
        "evaluacion__ticket__servicio_maestro__servicio__oficio", "evaluacion__ticket__comuna"
    )


def _instante(valor):
    return None if valor is None else timezone.localtime(valor, ocurrencias.ZONA).isoformat()


def _denunciante(denuncia):
    ticket = denuncia.evaluacion.ticket
    return "cliente" if denuncia.denunciante_id == ticket.cliente_id else "maestro"


def datos_en_lista(denuncia):
    ticket = denuncia.evaluacion.ticket
    return {
        "ref": str(denuncia.ref),
        "estado": denuncia.estado,
        "estado_texto": EstadoDenuncia(denuncia.estado).label,
        "creada_en": _instante(denuncia.creada_en),
        "denunciante": _denunciante(denuncia),
        "servicio": ticket.servicio_maestro.servicio.nombre,
        "comuna": ticket.comuna.nombre,
    }


def _resumen_ticket(ticket):
    """Sin dirección, teléfono, descripción ni nombres (E-4.5, minimización)."""
    return {
        "oficio": ticket.servicio_maestro.servicio.oficio.nombre,
        "servicio": ticket.servicio_maestro.servicio.nombre,
        "comuna": ticket.comuna.nombre,
        "fecha": ticket.fecha.isoformat(),
        "inicio": agenda.formato_hora(ticket.inicio_min),
        "fin": agenda.formato_hora(ticket.fin_min),
        "estado": ticket.estado,
        "modalidad": ticket.modalidad,
        "modalidad_texto": Modalidad(ticket.modalidad).label,
        "monto_publicado": ticket.monto_publicado,
        "monto_final": ticket.monto_final,
        "enviado_en": _instante(ticket.enviado_en),
        "finalizado_en": _instante(ticket.finalizado_en),
    }


def datos_detalle(denuncia):
    return {
        **datos_en_lista(denuncia),
        "motivo": denuncia.motivo,
        "decision": denuncia.decision,
        "decision_texto": denuncia.get_decision_display() if denuncia.decision else None,
        "motivo_resolucion": denuncia.motivo_resolucion,
        "resuelta_en": _instante(denuncia.resuelta_en),
        "puede_ver_conversacion": denuncia.estado == EstadoDenuncia.ABIERTA,
        "evaluacion": datos_evaluacion(denuncia.evaluacion),
        "ticket": _resumen_ticket(denuncia.evaluacion.ticket),
    }


def leer_conversacion(denuncia, moderador):
    """Los mensajes del ticket, con registro en la bitácora y aviso a ambas partes."""
    ticket = denuncia.evaluacion.ticket
    ahora = timezone.now()
    with transaction.atomic():
        bitacora.registrar(
            autor=moderador,
            accion=ACCION_CONVERSACION,
            entidad="ticket",
            entidad_ref=ticket.ref,
            motivo=f"Denuncia {denuncia.ref}",
        )
        for parte_id in (ticket.cliente_id, ticket.perfil_maestro_id):
            avisos.emitir(ticket, parte_id, TipoAvisoTicket.CONVERSACION_REVISADA, ahora)
        datos = conversacion.leer(ticket, moderador)
    # Moderación solo lee (M-04): nunca escribe en la conversación.
    datos.update(puede_escribir=False, aviso=None if ticket.estado != EstadoTicket.CERRADO else datos["aviso"])
    return datos


def resolver(denuncia, moderador, decision, motivo):
    with transaction.atomic():
        actual = Denuncia.objects.select_for_update().get(pk=denuncia.pk)
        if actual.estado != EstadoDenuncia.ABIERTA:
            raise ErrorEstado(MENSAJE_YA_RESUELTA)
        evaluacion = Evaluacion.objects.select_for_update().get(pk=actual.evaluacion_id)
        anterior = evaluacion.estado
        nuevo = NUEVO_ESTADO[decision]
        if nuevo != anterior:
            evaluacion.estado = nuevo
            evaluacion.save(update_fields=["estado"])
        actual.estado = EstadoDenuncia.RESUELTA
        actual.decision = decision
        actual.motivo_resolucion = motivo
        actual.resuelta_por_id = moderador.pk
        actual.resuelta_en = timezone.now()
        actual.save(update_fields=["estado", "decision", "motivo_resolucion", "resuelta_por_id", "resuelta_en"])
        bitacora.registrar(
            autor=moderador,
            accion=ACCION_RESOLUCION,
            entidad="evaluacion",
            entidad_ref=evaluacion.ref,
            motivo=motivo,
            valor_anterior={"estado": anterior, "denuncia": str(actual.ref), "denuncia_estado": EstadoDenuncia.ABIERTA},
            valor_nuevo={"estado": nuevo, "denuncia": str(actual.ref), "denuncia_estado": EstadoDenuncia.RESUELTA,
                         "decision": decision},
        )
    return actual
