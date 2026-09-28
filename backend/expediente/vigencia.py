"""Reglas calculadas únicas del expediente (ADR-016, punto 3; ADR-017, puntos 3 y 4).

S3 y S4 las reutilizan: no se duplican en otras capas.

- ``hoy_negocio``: "hoy" en ``America/Santiago`` (``TIME_ZONE`` sigue en UTC).
- ``vigente``: vigente si no tiene vencimiento o si ``hoy < fecha_vencimiento``.
- ``faltantes_para_aprobar``: requisitos de ADR-017, punto 3.

Pendiente (incremento 5 del S2, con el modelo ``documento``): ``dias_restantes``
y ``oficio_habilitado``.
"""
from zoneinfo import ZoneInfo

from django.utils import timezone

from expediente.models import OficioMaestro

ZONA_NEGOCIO = ZoneInfo("America/Santiago")

# Tipos de requisito para aprobar (ADR-017, punto 3; supuesto a validar, P-03).
CEDULA = "cedula"  # por ambos lados
ANTECEDENTES = "antecedentes"
LICENCIA_SEC = "licencia_sec"  # una por cada oficio regulado declarado (RF-33)


def hoy_negocio(ahora=None):
    """Fecha de hoy en ``America/Santiago``. ``ahora`` (aware) permite probarla."""
    return (ahora or timezone.now()).astimezone(ZONA_NEGOCIO).date()


def vigente(fecha_vencimiento, hoy):
    """Un documento sin vencimiento siempre está vigente (RF-04, CA-11.2)."""
    return fecha_vencimiento is None or hoy < fecha_vencimiento


def requisitos_para_aprobar(oficios_regulados):
    """Requisitos del expediente: ``(tipo, oficio)``, con ``oficio`` solo en las licencias."""
    return [(CEDULA, None), (ANTECEDENTES, None)] + [
        (LICENCIA_SEC, oficio) for oficio in sorted(oficios_regulados, key=lambda o: (o.orden, o.codigo))
    ]


def _requisitos_cumplidos(expediente, hoy):
    """Requisitos cubiertos por documentos ``validado`` (y licencias vigentes).

    Los documentos llegan en el incremento 2 del S2: hasta entonces ninguno se cumple.
    """
    return set()


def faltantes_para_aprobar(expediente, hoy=None):
    """Requisitos de ADR-017, punto 3, que el expediente todavía no cumple, en orden."""
    hoy = hoy or hoy_negocio()
    regulados = [
        om.oficio
        for om in OficioMaestro.objects.filter(maestro_id=expediente.perfil_maestro_id, oficio__regulado=True)
        .select_related("oficio")
    ]
    cumplidos = _requisitos_cumplidos(expediente, hoy)
    return [requisito for requisito in requisitos_para_aprobar(regulados) if requisito not in cumplidos]
