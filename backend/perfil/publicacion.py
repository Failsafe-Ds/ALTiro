"""Regla única de publicación (RF-05, RF-34, RNF-25, CA-12.2, CA-24.1, CA-24.3; ADR-019, puntos 2 y 3, y E-1).

Se calcula **en cada lectura**; no hay marca guardada ni tarea programada
(ADR-019, punto 2): una licencia deja de habilitar el mismo día de su
vencimiento, en hora de Santiago (``hoy_negocio``), sin esperar a ningún
proceso. La reactivación ocurre sola cuando curatoría valida una licencia nueva.
La usan el maestro (sus servicios y su perfil), el perfil público y la
búsqueda de S4: nadie más decide la visibilidad.

- ``motivos_no_visible_de(servicio_maestro, ctx, hoy)``: la regla **pura**
  (ADR-019, E-1), sin consultas. Códigos, en este orden: ``retirado``,
  ``catalogo_inactivo``, ``oficio_no_declarado``, ``modalidad_no_admitida``,
  ``licencia_no_vigente`` y ``maestro_no_elegible``. Lista vacía = visible.
- ``motivos_no_visible(servicio_maestro, hoy)``: envoltorio que arma el
  contexto de un servicio con ``contextos_en_lote`` (un solo camino) y llama
  a la regla pura.
- ``contextos_en_lote(maestro_ids)``: contextos de muchos maestros con un
  número constante de consultas (búsqueda, RNF-01).
- ``visible``: sin motivos.
- ``pendientes_de`` (pura), ``pendientes_del_maestro`` y ``maestro_elegible``:
  expediente ``aprobado`` + comuna base + foto (ADR-019, punto 3; ADR-021).
- ``maestro_publicado``: elegible + al menos un servicio visible.
- ``servicios_visibles``: los que ven los clientes (perfil público; S4).

``pendientes_para_publicarse`` agrega a los pendientes del maestro "al menos
un servicio visible": es la lista que ve el maestro en ``GET /api/maestros/perfil``.
"""
from collections import defaultdict
from dataclasses import dataclass, field, replace

from django.db.models import F

from catalogo.models import ServicioModalidad
from expediente import vigencia
from expediente.models import Documento, EstadoExpediente, Expediente, OficioMaestro
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


def pendientes_de(estado, con_base, con_foto):
    """Regla pura de elegibilidad (ADR-019, punto 3): lo que falta, en orden fijo (vacía = elegible)."""
    pendientes = []
    if estado != EstadoExpediente.APROBADO:
        pendientes.append(POSTULACION_NO_APROBADA)
    if not con_base:
        pendientes.append(SIN_COMUNA_BASE)
    if not con_foto:
        pendientes.append(SIN_FOTO)
    return pendientes


def pendientes_del_maestro(maestro_id):
    """Lo que le falta al maestro para ser elegible, en orden fijo (lista vacía = elegible)."""
    estado = Expediente.objects.filter(perfil_maestro_id=maestro_id).values_list("estado", flat=True).first()
    return pendientes_de(estado, tiene_comuna_base(maestro_id), tiene_foto(maestro_id))


def maestro_elegible(maestro_id):
    return not pendientes_del_maestro(maestro_id)


# --- Regla pura de visibilidad y su contexto (ADR-019, Enmienda E-1) ---


@dataclass(frozen=True)
class Contexto:
    """Datos de **un** maestro ya cargados para ``motivos_no_visible_de`` (ADR-019, E-1).

    - ``elegible``: resultado de ``pendientes_de`` (aprobado, comuna base y foto).
    - ``oficios_declarados``: ids de los oficios que declaró.
    - ``modalidades_admitidas``: pares ``(servicio_id, modalidad)`` del catálogo.
    - ``licencias``: ``{oficio_id: [Documento]}`` con todas las licencias SEC del
      expediente (actuales y reemplazadas), que se evalúan con
      ``vigencia.licencia_habilitante_de``.
    """

    elegible: bool
    oficios_declarados: frozenset = frozenset()
    modalidades_admitidas: frozenset = frozenset()
    licencias: dict = field(default_factory=dict)


def motivos_no_visible_de(servicio_maestro, ctx, hoy):
    """Regla única, **pura**: por qué los clientes no ven ``servicio_maestro``; vacía si lo ven.

    ``servicio_maestro`` debe traer ``servicio`` y ``servicio.oficio`` cargados
    (``select_related``); ``ctx`` es el ``Contexto`` de su maestro. Sin consultas.
    """
    servicio = servicio_maestro.servicio
    oficio = servicio.oficio
    motivos = []
    if servicio_maestro.retirado_en is not None:
        motivos.append(RETIRADO)
    if not servicio.activo or not oficio.activo:
        motivos.append(CATALOGO_INACTIVO)
    if oficio.pk not in ctx.oficios_declarados:
        motivos.append(OFICIO_NO_DECLARADO)
    if (servicio.pk, servicio_maestro.modalidad) not in ctx.modalidades_admitidas:
        motivos.append(MODALIDAD_NO_ADMITIDA)
    if oficio.regulado and vigencia.licencia_habilitante_de(ctx.licencias.get(oficio.pk, ()), hoy) is None:
        motivos.append(LICENCIA_NO_VIGENTE)
    if not ctx.elegible:
        motivos.append(MAESTRO_NO_ELEGIBLE)
    return motivos


def _contexto_de(servicio_maestro, elegible):
    """Contexto de un solo servicio: el mismo camino que la búsqueda (``contextos_en_lote``).

    Si ``elegible`` viene ya calculado, reemplaza al del lote.
    """
    maestro_id = servicio_maestro.maestro_id
    ctx = contextos_en_lote([maestro_id], servicio_ids={servicio_maestro.servicio_id})[maestro_id]
    return ctx if elegible is None else replace(ctx, elegible=elegible)


def motivos_no_visible(servicio_maestro, hoy=None, elegible=None):
    """Envoltorio de ``motivos_no_visible_de``: arma el contexto con consultas.

    ``elegible`` permite reutilizar el cálculo del maestro al revisar varios
    servicios suyos; si es ``None`` se calcula.
    """
    hoy = hoy or vigencia.hoy_negocio()
    return motivos_no_visible_de(servicio_maestro, _contexto_de(servicio_maestro, elegible), hoy)


def contextos_en_lote(maestro_ids, servicio_ids=None):
    """``{maestro_id: Contexto}`` de muchos maestros con un número **constante** de consultas (RNF-01; E-1).

    ``servicio_ids`` acota las modalidades admitidas que se cargan (servicios
    del catálogo que se van a evaluar); si es ``None`` se cargan todas.
    Un maestro sin expediente queda no elegible. Seis consultas.
    """
    ids = sorted(set(maestro_ids))
    if not ids:
        return {}
    estados = dict(
        Expediente.objects.filter(perfil_maestro_id__in=ids).values_list("perfil_maestro_id", "estado")
    )
    con_base = set(
        Cobertura.objects.filter(maestro_id__in=ids, es_base=True).values_list("maestro_id", flat=True)
    )
    con_foto = set(
        PerfilPublico.objects.filter(perfil_maestro_id__in=ids, foto__isnull=False).values_list(
            "perfil_maestro_id", flat=True
        )
    )
    declarados = defaultdict(set)
    for maestro_id, oficio_id in OficioMaestro.objects.filter(maestro_id__in=ids).values_list(
        "maestro_id", "oficio_id"
    ):
        declarados[maestro_id].add(oficio_id)
    modalidades = ServicioModalidad.objects.all()
    if servicio_ids is not None:
        modalidades = modalidades.filter(servicio_id__in=set(servicio_ids))
    admitidas = frozenset(modalidades.values_list("servicio_id", "modalidad"))
    licencias = defaultdict(lambda: defaultdict(list))
    for documento in Documento.objects.filter(
        expediente__perfil_maestro_id__in=ids, tipo=vigencia.LICENCIA_SEC
    ).annotate(maestro_id=F("expediente__perfil_maestro_id")):
        licencias[documento.maestro_id][documento.oficio_id].append(documento)
    return {
        maestro_id: Contexto(
            elegible=not pendientes_de(estados.get(maestro_id), maestro_id in con_base, maestro_id in con_foto),
            oficios_declarados=frozenset(declarados[maestro_id]),
            modalidades_admitidas=admitidas,
            licencias=dict(licencias[maestro_id]),
        )
        for maestro_id in ids
    }


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
