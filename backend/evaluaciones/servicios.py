"""Reglas de evaluación y denuncia de las partes (RF-29, RF-31, CA-09.1, CA-09.2, CA-18.1; ADR-026, E-3 y E-4.2).

- La parte se deduce del usuario (``PoliticaTicket`` ya garantizó que es una
  de las dos): quien evalúa es ``parte``; el evaluado, la otra.
- Solo sobre una orden ``finalizado`` (CA-09.1, CA-18.1). La segunda
  evaluación de la misma parte → 409; el único de la base lo garantiza también
  ante peticiones simultáneas (CA-09.2).
- Denuncia: solo la parte evaluada, sobre la evaluación recibida ``publicada``
  y una sola vez (P-26).
"""
from django.db import IntegrityError, transaction

from evaluaciones.models import (
    DIMENSIONES,
    Denuncia,
    EstadoDenuncia,
    EstadoEvaluacion,
    Evaluacion,
    ParteEvaluacion,
)
from expediente.errores import ErrorEstado
from perfil import ocurrencias
from tickets.models import EstadoTicket

MENSAJE_NO_TERMINADO = (
    "Podrás evaluar cuando el trabajo termine y tenga su precio final. Revisa el estado en tu historial."
)
MENSAJE_CERRADO = "Este pedido se cerró sin realizarse, así que no se puede evaluar."
MENSAJE_YA_EVALUASTE = "Ya evaluaste este trabajo"
MENSAJE_SIN_EVALUACION = "Todavía no recibiste una evaluación de este trabajo, así que no hay nada que denunciar."
MENSAJE_RETIRADA = "Esta evaluación ya fue retirada por moderación."
MENSAJE_YA_DENUNCIASTE = "Ya denunciaste esta evaluación. Moderación la revisa y te avisará por este medio."

TEXTO_PARTE = {ParteEvaluacion.CLIENTE: "cliente", ParteEvaluacion.MAESTRO: "maestro"}


def parte_de(usuario, ticket):
    return ParteEvaluacion.CLIENTE if usuario.pk == ticket.cliente_id else ParteEvaluacion.MAESTRO


def _otra_parte_id(usuario, ticket):
    return ticket.perfil_maestro_id if usuario.pk == ticket.cliente_id else ticket.cliente_id


def datos_evaluacion(evaluacion):
    """Lista explícita de campos: sin ids, sin autor ni evaluado."""
    return {
        "parte": evaluacion.parte,
        "puntualidad": evaluacion.puntualidad,
        "trabajo": evaluacion.trabajo,
        "cordialidad": evaluacion.cordialidad,
        "comentario": evaluacion.comentario,
        "creada_en": ocurrencias.iso_local(evaluacion.creada_en),
        "estado": evaluacion.estado,
        "estado_texto": EstadoEvaluacion(evaluacion.estado).label,
    }


def datos_denuncia_propia(denuncia):
    return {
        "estado": denuncia.estado,
        "estado_texto": EstadoDenuncia(denuncia.estado).label,
        "creada_en": ocurrencias.iso_local(denuncia.creada_en),
        "decision_texto": denuncia.get_decision_display() if denuncia.decision else None,
    }


def _motivo_no_evaluable(ticket):
    if ticket.estado == EstadoTicket.FINALIZADO:
        return None
    return MENSAJE_CERRADO if ticket.estado == EstadoTicket.CERRADO else MENSAJE_NO_TERMINADO


def evaluaciones_de(ticket, usuario):
    """``{mia, recibida, puede_evaluar, aviso}`` desde el punto de vista de ``usuario``."""
    filas = {e.parte: e for e in Evaluacion.objects.filter(ticket=ticket)}
    propia = parte_de(usuario, ticket)
    otra = ParteEvaluacion.MAESTRO if propia == ParteEvaluacion.CLIENTE else ParteEvaluacion.CLIENTE
    mia, recibida = filas.get(propia), filas.get(otra)
    datos_recibida = None
    if recibida is not None:
        denuncia = Denuncia.objects.filter(evaluacion=recibida, denunciante_id=usuario.pk).first()
        datos_recibida = {
            **datos_evaluacion(recibida),
            "denuncia": datos_denuncia_propia(denuncia) if denuncia else None,
            "puede_denunciar": denuncia is None and recibida.estado == EstadoEvaluacion.PUBLICADA,
        }
    motivo = _motivo_no_evaluable(ticket)
    return {
        "parte": propia,
        "evalua_a": TEXTO_PARTE[otra],
        "mia": datos_evaluacion(mia) if mia else None,
        "recibida": datos_recibida,
        "puede_evaluar": motivo is None and mia is None,
        "aviso": motivo if mia is None else None,
    }


def evaluar(ticket, usuario, notas, comentario):
    """Guarda la evaluación de la parte de ``usuario``. ``notas``: dict de las tres dimensiones."""
    motivo = _motivo_no_evaluable(ticket)
    if motivo is not None:
        raise ErrorEstado(motivo)
    parte = parte_de(usuario, ticket)
    if Evaluacion.objects.filter(ticket=ticket, parte=parte).exists():
        raise ErrorEstado(MENSAJE_YA_EVALUASTE)
    try:
        with transaction.atomic():
            return Evaluacion.objects.create(
                ticket=ticket,
                parte=parte,
                autor_id=usuario.pk,
                evaluado_id=_otra_parte_id(usuario, ticket),
                comentario=comentario,
                **{d: notas[d] for d in DIMENSIONES},
            )
    except IntegrityError:
        # Otra petición simultánea de la misma parte ganó: el único de la base decide (CA-09.2).
        raise ErrorEstado(MENSAJE_YA_EVALUASTE) from None


def denunciar(ticket, usuario, motivo):
    """La parte evaluada denuncia la evaluación recibida, una sola vez."""
    with transaction.atomic():
        recibida = (
            Evaluacion.objects.select_for_update()
            .filter(ticket=ticket, evaluado_id=usuario.pk)
            .first()
        )
        if recibida is None:
            raise ErrorEstado(MENSAJE_SIN_EVALUACION)
        if Denuncia.objects.filter(evaluacion=recibida, denunciante_id=usuario.pk).exists():
            raise ErrorEstado(MENSAJE_YA_DENUNCIASTE)
        if recibida.estado != EstadoEvaluacion.PUBLICADA:
            raise ErrorEstado(MENSAJE_RETIRADA)
        try:
            with transaction.atomic():
                return Denuncia.objects.create(evaluacion=recibida, denunciante_id=usuario.pk, motivo=motivo)
        except IntegrityError:
            raise ErrorEstado(MENSAJE_YA_DENUNCIASTE) from None
