"""Reglas calculadas únicas del expediente (ADR-016, punto 3; ADR-017, puntos 3 y 4).

S3 y S4 las reutilizan: no se duplican en otras capas.

- ``hoy_negocio``: "hoy" en ``America/Santiago`` (``TIME_ZONE`` sigue en UTC).
- ``vigente``: vigente si no tiene vencimiento o si ``hoy < fecha_vencimiento``.
- ``requisitos_para_aprobar``: documentos exigidos (ADR-017, punto 3).
- ``licencia_habilitante_de`` (pura, sin consultas), ``licencia_habilitante``
  y ``oficio_habilitado``: un oficio regulado está
  habilitado si tiene una licencia SEC ``validado`` y vigente (ADR-017,
  punto 4), con la regla de renovación de ADR-017, E-1. Regla única.
- ``faltantes_para_aprobar``: requisitos sin documento ``validado`` y, en las
  licencias, sin oficio habilitado. Es la regla de aprobación (RF-33, CA-19.2).
- ``requisitos_sin_documento``: requisitos para los que el maestro todavía no
  entregó ningún documento actual. Es lo que ve el maestro como "faltantes"
  (ADR-017, E-2).

- ``dias_restantes``: días que faltan para el vencimiento (RF-08, CA-17.1).
- ``en_seguimiento`` y ``requiere_aviso``: qué documentos se vigilan y cuándo
  corresponde el aviso de RF-35 (ADR-016, punto 2).
"""
import datetime
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


def dias_restantes(fecha_vencimiento, hoy):
    """Días que faltan para ``fecha_vencimiento`` contados desde ``hoy`` (RF-08, CA-17.1).

    - ``None`` si el documento no vence (RF-04, CA-11.2): no hay días que mostrar.
    - Coherente con ``vigente`` (``hoy < fecha_vencimiento``): el documento está
      vigente si y solo si el resultado es mayor que 0. **El día del vencimiento
      el resultado es 0 y el documento ya no está vigente**; después es negativo.
      Vence mañana: 1; vence hoy: 0 (vencido); venció ayer: -1.
    """
    if fecha_vencimiento is None:
        return None
    return (fecha_vencimiento - hoy).days


# RF-35, CA-24.2: "30 días antes del vencimiento".
DIAS_AVISO = 30


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
    # Un documento eliminado por retención ya no tiene archivo: no cuenta (RNF-26; ADR-026, E-9).
    if documento.eliminado_en is not None:
        return False
    if documento.estado == EstadoDocumento.VALIDADO:
        return True
    return documento.estado == EstadoDocumento.REEMPLAZADO and not documento.motivo_observacion.strip()


def licencia_habilitante_de(licencias, hoy):
    """Regla pura de ADR-017, punto 4 y E-1, sobre licencias ya cargadas (sin consultas).

    ``licencias``: todas las licencias SEC (actuales y reemplazadas) de **un**
    expediente y **un** oficio, en cualquier orden. Permite cargarlas en lote
    (búsqueda de S4) sin duplicar la regla.

    Cuenta la licencia validada **más reciente** (por ``cargado_en`` y ``pk``), y
    solo si está vigente:

    - si la actual está ``validado``, cuenta solo ella (E-1: "cuando curatoría
      valida la nueva, cuenta solo la nueva");
    - si la actual está ``en_revision`` u ``observado``, sigue contando la
      anterior validada (ahora ``reemplazado``) mientras siga vigente;
    - nunca cuenta una licencia sin revisar ni una observada.
    """
    for licencia in sorted(licencias, key=lambda d: (d.cargado_en, d.pk), reverse=True):
        if fue_validado(licencia):
            return licencia if vigente(licencia.fecha_vencimiento, hoy) else None
    return None


def licencia_habilitante(expediente, oficio, hoy=None):
    """Licencia SEC que habilita ``oficio`` en el expediente, o ``None`` (ADR-017, punto 4 y E-1).

    Carga las licencias de ese oficio y aplica ``licencia_habilitante_de``.
    """
    hoy = hoy or hoy_negocio()
    licencias = Documento.objects.filter(expediente=expediente, tipo=LICENCIA_SEC, oficio=oficio)
    return licencia_habilitante_de(list(licencias), hoy)


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
        for documento in documentos_actuales(expediente).filter(
            estado=EstadoDocumento.VALIDADO, eliminado_en__isnull=True
        )
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


def en_seguimiento(documento, hoy):
    """Verdadero si se vigila el vencimiento de ``documento`` (avisos de RF-35 y su muestra).

    - Tiene vencimiento y sigue vigente. Un documento sin vencimiento nunca se
      vigila ni genera aviso (RF-04, CA-24.3).
    - Es un documento actual, o es la licencia reemplazada que **sigue
      contando** para habilitar su oficio (ADR-017, E-1): mientras la licencia
      nueva no esté validada, el vencimiento de la anterior es el que
      deshabilita el oficio, y es el que el maestro y curatoría deben conocer.
    - Un documento reemplazado que ya no cuenta no se vigila.
    """
    if documento.fecha_vencimiento is None or not vigente(documento.fecha_vencimiento, hoy):
        return False
    if documento.estado != EstadoDocumento.REEMPLAZADO:
        return True
    if documento.tipo != LICENCIA_SEC:
        return False
    return licencia_habilitante(documento.expediente, documento.oficio, hoy) == documento


def requiere_aviso(documento, hoy):
    """RF-35, CA-24.2: faltan ``DIAS_AVISO`` días o menos, y el documento sigue vigente y en seguimiento."""
    restantes = dias_restantes(documento.fecha_vencimiento, hoy)
    return restantes is not None and restantes <= DIAS_AVISO and en_seguimiento(documento, hoy)


def candidatos_a_aviso(hoy):
    """Documentos que vencen en ``DIAS_AVISO`` días o menos y siguen vigentes (filtro previo en SQL).

    La regla completa es ``requiere_aviso``; este filtro solo acota la consulta.
    """
    return (
        Documento.objects.filter(
            fecha_vencimiento__gt=hoy,
            fecha_vencimiento__lte=hoy + datetime.timedelta(days=DIAS_AVISO),
            eliminado_en__isnull=True,
        )
        .select_related("expediente", "oficio")
        .order_by("fecha_vencimiento", "pk")
    )


def expedientes_por_vencer(hoy):
    """Ids de los expedientes con algún documento que requiere aviso hoy (filtro ``?por_vencer`` de curatoría).

    Mismo criterio que el aviso de RF-35 (``requiere_aviso``): vence en
    ``DIAS_AVISO`` días o menos, sigue vigente y está en seguimiento.
    """
    return {documento.expediente_id for documento in candidatos_a_aviso(hoy) if requiere_aviso(documento, hoy)}
