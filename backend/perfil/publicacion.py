"""Regla única de publicación (RF-05, RF-34, RNF-25, CA-12.2, CA-24.1, CA-24.3; ADR-019, puntos 2 y 3).

Se calcula **en cada lectura**; no hay marca guardada ni tarea programada
(ADR-019, punto 2): una licencia deja de habilitar el mismo día de su
vencimiento, en hora de Santiago (``hoy_negocio``), sin esperar a ningún
proceso. La reactivación ocurre sola cuando curatoría valida una licencia nueva.
La usan el maestro (sus servicios y su perfil), el perfil público y la
búsqueda de S4: nadie más decide la visibilidad.

- ``motivos_no_visible(servicio_maestro, hoy)``: códigos, en este orden:
  ``retirado``, ``catalogo_inactivo``, ``oficio_no_declarado``,
  ``modalidad_no_admitida``, ``licencia_no_vigente`` y ``maestro_no_elegible``.
  Lista vacía = visible.
- ``visible``: sin motivos.
- ``pendientes_del_maestro`` y ``maestro_elegible``: expediente ``aprobado`` +
  comuna base + foto (ADR-019, punto 3; ADR-021).
- ``maestro_publicado``: elegible + al menos un servicio visible.
- ``servicios_visibles``: los que ven los clientes (perfil público; S4).

Comuna base: tabla ``cobertura`` (incremento 3). Foto: ``perfil_publico.foto``
(incremento 5). ``pendientes_para_publicarse`` agrega a los pendientes del
maestro "al menos un servicio visible": es la lista que ve el maestro en
``GET /api/maestros/perfil``.
"""
from expediente import vigencia
from expediente.models import EstadoExpediente, Expediente, OficioMaestro
from catalogo.models import ServicioModalidad
from perfil.models import Cobertura, PerfilPublico, ServicioMaestro

RETIRADO = "retirado"
CATALOGO_INACTIVO = "catalogo_inactivo"
OFICIO_NO_DECLARADO = "oficio_no_declarado"
MODALIDAD_NO_ADMITIDA = "modalidad_no_admitida"
LICENCIA_NO_VIGENTE = "licencia_no_vigente"
MAESTRO_NO_ELEGIBLE = "maestro_no_elegible"

MOTIVOS = (
    RETIRADO, CATALOGO_INACTIVO, OFICIO_NO_DECLARADO, MODALIDAD_NO_ADMITIDA, LICENCIA_NO_VIGENTE, MAESTRO_NO_ELEGIBLE,
)

# Pendientes del maestro para ser elegible.
POSTULACION_NO_APROBADA = "postulacion_no_aprobada"
SIN_COMUNA_BASE = "sin_comuna_base"
SIN_FOTO = "sin_foto"
# Además, para estar publicado.
SIN_SERVICIO_VISIBLE = "sin_servicio_visible"


def tiene_comuna_base(maestro_id):
    """Condición de RF-06 ("un maestro sin comuna base no aparece"; CA-13.1)."""
    return Cobertura.objects.filter(maestro_id=maestro_id, es_base=True).exists()


def tiene_foto(maestro_id):
    """Foto cargada (ADR-021, punto 1)."""
    return PerfilPublico.objects.filter(perfil_maestro_id=maestro_id, foto__isnull=False).exists()


def pendientes_del_maestro(maestro_id):
    """Lo que le falta al maestro para ser elegible, en orden fijo (lista vacía = elegible)."""
    pendientes = []
    estado = Expediente.objects.filter(perfil_maestro_id=maestro_id).values_list("estado", flat=True).first()
    if estado != EstadoExpediente.APROBADO:
        pendientes.append(POSTULACION_NO_APROBADA)
    if not tiene_comuna_base(maestro_id):
        pendientes.append(SIN_COMUNA_BASE)
    if not tiene_foto(maestro_id):
        pendientes.append(SIN_FOTO)
    return pendientes


def maestro_elegible(maestro_id):
    return not pendientes_del_maestro(maestro_id)


def _licencia_vigente(servicio_maestro, oficio, hoy):
    """Reutiliza la regla única de ``expediente.vigencia`` (ADR-017, punto 4 y E-1)."""
    expediente = Expediente.objects.get(perfil_maestro_id=servicio_maestro.maestro_id)
    return vigencia.oficio_habilitado(expediente, oficio, hoy)


def motivos_no_visible(servicio_maestro, hoy=None, elegible=None):
    """Por qué los clientes no ven ``servicio_maestro``; lista vacía si lo ven.

    ``elegible`` permite reutilizar el cálculo del maestro al revisar varios
    servicios suyos; si es ``None`` se calcula.
    """
    hoy = hoy or vigencia.hoy_negocio()
    servicio = servicio_maestro.servicio
    oficio = servicio.oficio
    motivos = []
    if servicio_maestro.retirado_en is not None:
        motivos.append(RETIRADO)
    if not servicio.activo or not oficio.activo:
        motivos.append(CATALOGO_INACTIVO)
    if not OficioMaestro.objects.filter(maestro_id=servicio_maestro.maestro_id, oficio=oficio).exists():
        motivos.append(OFICIO_NO_DECLARADO)
    if not ServicioModalidad.objects.filter(servicio=servicio, modalidad=servicio_maestro.modalidad).exists():
        motivos.append(MODALIDAD_NO_ADMITIDA)
    if oficio.regulado and not _licencia_vigente(servicio_maestro, oficio, hoy):
        motivos.append(LICENCIA_NO_VIGENTE)
    if elegible is None:
        elegible = maestro_elegible(servicio_maestro.maestro_id)
    if not elegible:
        motivos.append(MAESTRO_NO_ELEGIBLE)
    return motivos


def visible(servicio_maestro, hoy=None):
    return not motivos_no_visible(servicio_maestro, hoy)


def servicios_activos(maestro_id):
    """Servicios no retirados del maestro, en orden estable."""
    return (
        ServicioMaestro.objects.filter(maestro_id=maestro_id, retirado_en__isnull=True)
        .select_related("servicio__oficio")
        .order_by("servicio__oficio__orden", "servicio__orden", "servicio__nombre", "pk")
    )


def maestro_publicado(maestro_id, hoy=None):
    """Elegible y con al menos un servicio visible (ADR-019, punto 3)."""
    if not maestro_elegible(maestro_id):
        return False
    hoy = hoy or vigencia.hoy_negocio()
    return any(not motivos_no_visible(s, hoy, elegible=True) for s in servicios_activos(maestro_id))


def servicios_visibles(maestro_id, hoy=None):
    """Servicios que los clientes ven, si el maestro es elegible; si no, ninguno."""
    if not maestro_elegible(maestro_id):
        return []
    hoy = hoy or vigencia.hoy_negocio()
    return [s for s in servicios_activos(maestro_id) if not motivos_no_visible(s, hoy, elegible=True)]


def pendientes_para_publicarse(maestro_id, hoy=None):
    """Lo que le falta al maestro para estar publicado, en orden fijo (lista vacía = publicado).

    Los pendientes de elegibilidad más ``SIN_SERVICIO_VISIBLE`` si ninguno de
    sus servicios sería visible aunque fuera elegible.
    """
    pendientes = pendientes_del_maestro(maestro_id)
    hoy = hoy or vigencia.hoy_negocio()
    if not any(not motivos_no_visible(s, hoy, elegible=True) for s in servicios_activos(maestro_id)):
        pendientes.append(SIN_SERVICIO_VISIBLE)
    return pendientes
