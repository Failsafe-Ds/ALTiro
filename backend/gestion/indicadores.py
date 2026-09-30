"""Los tres indicadores base (HU-22, RF-38, CA-22.1; informe §2.9.2; ADR-026, E-6.1).

- ``periodo``: ``desde`` y ``hasta`` (fechas de ``America/Santiago``, ambas
  incluidas) como instantes ``[inicio, fin)``.
- ``concrecion``: tickets ``finalizado`` con ``monto_final`` / tickets enviados
  en el período (por ``enviado_en``). Un solo ``aggregate`` en la base.
- ``primera_respuesta``: mediana y cantidad del tiempo entre ``enviado_en`` y el
  primer ``ticket_evento`` cuyo autor es el maestro del ticket con ``aceptado``
  o cierre ``rechazado_maestro``. No cuentan ``bloque_tomado`` ni los cierres
  del Sistema (P-32). Mediana con ``PERCENTILE_CONT`` en la base.
- ``vigencia_documental``: porcentaje de maestros con expediente aprobado cuyos
  documentos obligatorios están vigentes hoy. Carga en lote (tres consultas) y
  aplica las reglas puras de ``expediente/vigencia.py``; no las duplica.
"""
import datetime
from collections import defaultdict

from django.db.models import Aggregate, Count, F, FloatField, Func, OuterRef, Q, Subquery

from expediente import vigencia
from expediente.models import Documento, EstadoDocumento, EstadoExpediente, Expediente, OficioMaestro
from tickets.models import AutorTipo, EstadoTicket, MotivoCierre, Ticket, TicketEvento

DEFINICION_CONCRECION = (
    "Pedidos enviados en el período que terminaron como trabajo finalizado con precio final, "
    "divididos por todos los pedidos enviados en el período."
)
DEFINICION_PRIMERA_RESPUESTA = (
    "Mediana del tiempo entre el envío del pedido y la primera respuesta del maestro (aceptar o rechazar), "
    "para los pedidos enviados en el período. No cuentan los pedidos cerrados por el sistema ni los que "
    "se cerraron porque el maestro tomó otro trabajo en ese horario."
)
DEFINICION_VIGENCIA = (
    "Porcentaje de maestros aprobados que hoy tienen vigentes todos sus documentos obligatorios "
    "(cédula, certificado de antecedentes y licencia de cada oficio regulado)."
)


class Mediana(Aggregate):
    """Mediana continua de PostgreSQL (``PERCENTILE_CONT(0.5)``)."""

    function = "PERCENTILE_CONT"
    template = "%(function)s(0.5) WITHIN GROUP (ORDER BY %(expressions)s)"
    output_field = FloatField()


class Segundos(Func):
    """Segundos de un intervalo (``EXTRACT(EPOCH FROM …)``)."""

    template = "EXTRACT(EPOCH FROM %(expressions)s)"
    output_field = FloatField()


def periodo(desde, hasta):
    """Instantes ``[inicio, fin)`` del período, con ``hasta`` incluido (zona de negocio)."""
    inicio = datetime.datetime.combine(desde, datetime.time.min, tzinfo=vigencia.ZONA_NEGOCIO)
    fin = datetime.datetime.combine(hasta + datetime.timedelta(days=1), datetime.time.min, tzinfo=vigencia.ZONA_NEGOCIO)
    return inicio, fin


def tickets_del_periodo(inicio, fin):
    return Ticket.objects.filter(enviado_en__gte=inicio, enviado_en__lt=fin)


def _porcentaje(parte, total):
    return round(100 * parte / total, 1) if total else None


FILTRO_CONCRETADO = Q(estado=EstadoTicket.FINALIZADO, monto_final__isnull=False)


def concrecion(inicio, fin):
    datos = tickets_del_periodo(inicio, fin).aggregate(
        enviados=Count("id"), concretados=Count("id", filter=FILTRO_CONCRETADO)
    )
    return {
        "porcentaje": _porcentaje(datos["concretados"], datos["enviados"]),
        "concretados": datos["concretados"],
        "enviados": datos["enviados"],
        "definicion": DEFINICION_CONCRECION,
    }


def _primera_respuesta_del_maestro():
    return (
        TicketEvento.objects.filter(
            ticket_id=OuterRef("pk"),
            autor_tipo=AutorTipo.USUARIO,
            autor_id=OuterRef("perfil_maestro_id"),
            estado_anterior=EstadoTicket.PENDIENTE,
        )
        .filter(
            Q(estado_nuevo=EstadoTicket.ACEPTADO)
            | Q(estado_nuevo=EstadoTicket.CERRADO, motivo=MotivoCierre.RECHAZADO_MAESTRO)
        )
        .order_by("fecha", "id")
        .values("fecha")[:1]
    )


def primera_respuesta(inicio, fin):
    datos = (
        tickets_del_periodo(inicio, fin)
        .annotate(respondido_en=Subquery(_primera_respuesta_del_maestro()))
        .filter(respondido_en__isnull=False)
        .annotate(demora=Segundos(F("respondido_en") - F("enviado_en")))
        .aggregate(mediana=Mediana("demora"), cantidad=Count("id"))
    )
    mediana = datos["mediana"]
    return {
        "mediana_minutos": None if mediana is None else int(mediana / 60 + 0.5),
        "cantidad": datos["cantidad"],
        "definicion": DEFINICION_PRIMERA_RESPUESTA,
    }


def _cumple(documentos, regulados, hoy):
    """Todos los documentos obligatorios vigentes hoy (reglas de ``expediente/vigencia.py``)."""
    por_requisito = defaultdict(list)
    for documento in documentos:
        por_requisito[(documento.tipo, documento.oficio_id)].append(documento)
    for tipo, oficio in vigencia.requisitos_para_aprobar(regulados):
        if tipo == vigencia.LICENCIA_SEC:
            if vigencia.licencia_habilitante_de(por_requisito[(tipo, oficio.pk)], hoy) is None:
                return False
            continue
        actuales = [d for d in por_requisito[(tipo, None)] if d.estado != EstadoDocumento.REEMPLAZADO]
        if not any(vigencia.fue_validado(d) and vigencia.vigente(d.fecha_vencimiento, hoy) for d in actuales):
            return False
    return True


def vigencia_documental(hoy=None):
    hoy = hoy or vigencia.hoy_negocio()
    expedientes = dict(
        Expediente.objects.filter(estado=EstadoExpediente.APROBADO).values_list("pk", "perfil_maestro_id")
    )
    regulados = defaultdict(list)
    for om in OficioMaestro.objects.filter(
        maestro_id__in=expedientes.values(), oficio__regulado=True
    ).select_related("oficio"):
        regulados[om.maestro_id].append(om.oficio)
    documentos = defaultdict(list)
    for documento in Documento.objects.filter(expediente_id__in=expedientes.keys()):
        documentos[documento.expediente_id].append(documento)
    vigentes = sum(
        _cumple(documentos[pk], regulados[maestro_id], hoy) for pk, maestro_id in expedientes.items()
    )
    return {
        "porcentaje": _porcentaje(vigentes, len(expedientes)),
        "vigentes": vigentes,
        "aprobados": len(expedientes),
        "definicion": DEFINICION_VIGENCIA,
    }


def calcular(desde, hasta):
    inicio, fin = periodo(desde, hasta)
    return {
        "concrecion": concrecion(inicio, fin),
        "primera_respuesta": primera_respuesta(inicio, fin),
        "vigencia_documental": vigencia_documental(),
    }
