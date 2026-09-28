"""Reglas calculadas únicas del expediente (ADR-016, punto 3; ADR-017, puntos 3 y 4).

S3 y S4 las reutilizan: no se duplican en otras capas.

- ``hoy_negocio``: "hoy" en ``America/Santiago`` (``TIME_ZONE`` sigue en UTC).
- ``vigente``: vigente si no tiene vencimiento o si ``hoy < fecha_vencimiento``.
- ``requisitos_para_aprobar``: documentos exigidos (ADR-017, punto 3).
- ``faltantes_para_aprobar``: requisitos sin documento ``validado`` (y, en las
  licencias, vigente). Es la regla de aprobación (incremento 4).
- ``requisitos_sin_documento``: requisitos para los que el maestro todavía no
  entregó ningún documento actual. Es lo que ve el maestro como "faltantes"
  (ver la decisión en su docstring).

Pendiente (incremento 5 del S2): ``dias_restantes`` y ``oficio_habilitado``.
"""
from zoneinfo import ZoneInfo

from django.utils import timezone

from expediente.models import Documento, EstadoDocumento, OficioMaestro, TipoDocumento

ZONA_NEGOCIO = ZoneInfo("America/Santiago")

# Tipos de requisito para aprobar (ADR-017, punto 3; supuesto a validar, P-03).
# Misma nomenclatura que ``documento.tipo``.
CEDULA = TipoDocumento.CEDULA_IDENTIDAD.value  # por ambos lados
ANTECEDENTES = TipoDocumento.CERTIFICADO_ANTECEDENTES.value
LICENCIA_SEC = TipoDocumento.LICENCIA_SEC.value  # una por cada oficio regulado declarado (RF-33)


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


def documentos_actuales(expediente):
    """Documentos actuales (no reemplazados) del expediente, en orden estable."""
    return (
        Documento.objects.filter(expediente=expediente)
        .exclude(estado=EstadoDocumento.REEMPLAZADO)
        .select_related("oficio")
        .order_by("tipo", "oficio__orden", "cargado_en")
    )


def _requisitos_del(expediente):
    regulados = [
        om.oficio
        for om in OficioMaestro.objects.filter(maestro_id=expediente.perfil_maestro_id, oficio__regulado=True)
        .select_related("oficio")
    ]
    return requisitos_para_aprobar(regulados)


def _requisitos_cumplidos(expediente, hoy):
    """Requisitos cubiertos por documentos ``validado`` (y licencias vigentes) (ADR-017, punto 3)."""
    return {
        (documento.tipo, documento.oficio)
        for documento in documentos_actuales(expediente).filter(estado=EstadoDocumento.VALIDADO)
        if documento.tipo != LICENCIA_SEC or vigente(documento.fecha_vencimiento, hoy)
    }


def faltantes_para_aprobar(expediente, hoy=None):
    """Requisitos de ADR-017, punto 3, que el expediente todavía no cumple, en orden."""
    hoy = hoy or hoy_negocio()
    cumplidos = _requisitos_cumplidos(expediente, hoy)
    return [requisito for requisito in _requisitos_del(expediente) if requisito not in cumplidos]


def requisitos_sin_documento(expediente):
    """Requisitos para los que no hay ningún documento actual, en orden.

    Decisión del incremento 2 (a validar por el equipo): para el maestro, un
    documento entregado cuenta aunque siga ``en_revision`` u ``observado``;
    su estado se muestra aparte, por documento (RF-08). No cambia la regla de
    aprobación, que sigue exigiendo documentos ``validado`` y licencias
    vigentes (``faltantes_para_aprobar``).
    """
    entregados = {(documento.tipo, documento.oficio) for documento in documentos_actuales(expediente)}
    return [requisito for requisito in _requisitos_del(expediente) if requisito not in entregados]
