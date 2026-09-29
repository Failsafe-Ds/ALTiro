"""Rangos ocupados de la agenda de los maestros (CA-14.3; ADR-022, punto 1; ADR-023, punto 4).

Un bloque está **ocupado** si se cruza con un ticket ``aceptado`` o
``finalizado`` del mismo maestro (ADR-023, punto 4; D-12: "mismo bloque"
significa que los rangos se cruzan). Un ticket ``pendiente`` o ``cerrado`` no
ocupa: el bloque sigue libre para otros pedidos (RF-20).

Una sola consulta en lote sobre ``ticket`` (índice único parcial
``ticket_bloque_ocupado_unico``), para que la búsqueda, la ficha y la creación
del ticket mantengan un número de consultas constante (RNF-01).
"""
from collections import defaultdict


def rangos_ocupados(maestro_ids, desde, hasta):
    """``{maestro_id: [(inicio_en, fin_en), ...]}`` de los tickets que ocupan agenda entre ``desde`` y ``hasta``.

    Incluye los que se cruzan con ``[desde, hasta)`` aunque empiecen antes o terminen después.
    """
    # Import local: ``tickets.models`` importa ``perfil.models``.
    from tickets.models import ESTADOS_QUE_OCUPAN, Ticket

    ids = set(maestro_ids)
    if not ids:
        return {}
    rangos = defaultdict(list)
    for maestro_id, inicio, fin in (
        Ticket.objects.filter(
            perfil_maestro_id__in=ids, estado__in=ESTADOS_QUE_OCUPAN, inicio_en__lt=hasta, fin_en__gt=desde
        )
        .order_by("perfil_maestro_id", "inicio_en")
        .values_list("perfil_maestro_id", "inicio_en", "fin_en")
    ):
        rangos[maestro_id].append((inicio, fin))
    return dict(rangos)
