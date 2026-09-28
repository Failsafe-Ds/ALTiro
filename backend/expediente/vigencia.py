"""Reglas calculadas únicas del expediente (ADR-016, punto 3; ADR-017, puntos 3 y 4).

S3 y S4 las reutilizan: no se duplican en otras capas.

- ``hoy_negocio``: "hoy" en ``America/Santiago`` (``TIME_ZONE`` sigue en UTC).
- ``vigente``: vigente si no tiene vencimiento o si ``hoy < fecha_vencimiento``.
- ``requisitos_para_aprobar``: documentos exigidos (ADR-017, punto 3).
- ``licencia_habilitante`` y ``oficio_habilitado``: un oficio regulado está
  habilitado si tiene una licencia SEC ``validado`` y vigente (ADR-017,
  punto 4), con la regla de renovación de ADR-017, E-1. Regla única.
- ``faltantes_para_aprobar``: requisitos sin documento ``validado`` y, en las
  licencias, sin oficio habilitado. Es la regla de aprobación (RF-33, CA-19.2).
- ``requisitos_sin_documento``: requisitos para los que el maestro todavía no
  entregó ningún documento actual. Es lo que ve el maestro como "faltantes"
  (ADR-017, E-2).

Pendiente (incremento 5 del S2): ``dias_restantes``.
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


def fue_validado(documento):
    """Verdadero si curatoría validó el documento, aunque después haya sido reemplazado.

    Un documento se revisa una sola vez, desde ``en_revision``
    (``expediente.servicios.revisar_documento``): al observarlo se guarda un
    motivo (CHECK ``documento_motivo_observacion``) y al validarlo el motivo
    queda vacío (CHECK ``documento_validado_sin_observacion``). Un documento
    sin revisar nunca queda ``reemplazado``: se borra (ADR-017, punto 5). Por
    eso un ``reemplazado`` sin motivo de observación estaba ``validado``.
    """
    if documento.estado == EstadoDocumento.VALIDADO:
        return True
    return documento.estado == EstadoDocumento.REEMPLAZADO and not documento.motivo_observacion.strip()


def licencia_habilitante(expediente, oficio, hoy=None):
    """Licencia SEC que habilita ``oficio`` en el expediente, o ``None`` (ADR-017, punto 4 y E-1).

    Cuenta la licencia validada **más reciente** de ese oficio, y solo si está vigente:

    - si la actual está ``validado``, cuenta solo ella (E-1: "cuando curatoría
      valida la nueva, cuenta solo la nueva");
    - si la actual está ``en_revision`` u ``observado``, sigue contando la
      anterior validada (ahora ``reemplazado``) mientras siga vigente;
    - nunca cuenta una licencia sin revisar ni una observada.
    """
    hoy = hoy or hoy_negocio()
    licencias = Documento.objects.filter(
        expediente=expediente, tipo=LICENCIA_SEC, oficio=oficio
    ).order_by("-cargado_en", "-pk")
    for licencia in licencias:
        if fue_validado(licencia):
            return licencia if vigente(licencia.fecha_vencimiento, hoy) else None
    return None


def oficio_habilitado(expediente, oficio, hoy=None):
    """Un oficio regulado está habilitado si tiene licencia habilitante (RF-33; ADR-017, punto 4).

    Un oficio no regulado no exige licencia: devuelve verdadero. No evalúa el
    estado del expediente.
    """
    if not oficio.regulado:
        return True
    return licencia_habilitante(expediente, oficio, hoy) is not None


def faltantes_para_aprobar(expediente, hoy=None):
    """Requisitos de ADR-017, punto 3, que el expediente todavía no cumple, en orden.

    - Cédula y antecedentes: el documento actual debe estar ``validado``.
    - Licencia SEC de cada oficio regulado declarado: el oficio debe estar
      habilitado (``oficio_habilitado``, con la regla de E-1).
    """
    hoy = hoy or hoy_negocio()
    validados = {
        documento.tipo
        for documento in documentos_actuales(expediente).filter(estado=EstadoDocumento.VALIDADO)
        if documento.tipo != LICENCIA_SEC
    }
    faltantes = []
    for tipo, oficio in _requisitos_del(expediente):
        cumplido = oficio_habilitado(expediente, oficio, hoy) if tipo == LICENCIA_SEC else tipo in validados
        if not cumplido:
            faltantes.append((tipo, oficio))
    return faltantes


def requisitos_sin_documento(expediente):
    """Requisitos para los que no hay ningún documento actual, en orden.

    ADR-017, E-2: para el maestro, un
    documento entregado cuenta aunque siga ``en_revision`` u ``observado``;
    su estado se muestra aparte, por documento (RF-08). No cambia la regla de
    aprobación, que sigue exigiendo documentos ``validado`` y licencias
    vigentes (``faltantes_para_aprobar``).
    """
    entregados = {(documento.tipo, documento.oficio) for documento in documentos_actuales(expediente)}
    return [requisito for requisito in _requisitos_del(expediente) if requisito not in entregados]
