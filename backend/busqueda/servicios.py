"""Búsqueda de maestros: filtros excluyentes, puntaje y páginas (RF-09 a RF-13; ADR-022; ADR-019, E-1; ADR-020, E-1).

Flujo de ``buscar(filtros, ahora)``:

1. ``leer_filtros``: valida los parámetros (``oficio`` y ``comuna``
   obligatorios; ``fecha``, ``inicio`` y ``fin`` los tres o ninguno, con la
   fecha dentro del horizonte de 14 días; ``pagina`` opcional).
2. ``cargar_candidatos``: prefiltro en SQL (servicio activo del oficio,
   expediente ``aprobado`` y cobertura en alguna comuna de la **provincia**
   pedida, para poder armar también las sugerencias de RF-12) y carga en lote
   del contexto de la regla única, la cobertura, la agenda, los rangos ocupados
   y los perfiles públicos. Número de consultas constante (RNF-01). El
   prefiltro solo descarta a quien la regla única también descartaría.
3. ``cumple``: decisión final, **pura**, para cada candidato: servicio visible
   del oficio según ``publicacion.motivos_no_visible_de`` (RNF-25, CA-24.4),
   comuna pedida en la cobertura (CA-02.1, CA-13.2) y, con filtro de bloque,
   una ocurrencia ofrecible ese día que **contiene** el rango pedido (CA-02.3,
   RF-16, CA-14.3). Los filtros son excluyentes (CA-02.4).
4. Orden por ``busqueda.puntaje`` y páginas de 20 (ADR-022, D-8).

Nada de lo calculado para ordenar (puntaje, disponibilidad, cercanía, comuna
base) sale de este módulo hacia la respuesta: la vista arma la tarjeta con una
lista explícita de campos (RF-13).
"""
import datetime
import re
from collections import defaultdict
from dataclasses import dataclass, field

from busqueda import puntaje
from catalogo.models import Oficio
from comun.api import MENSAJE_CLAVE_DESCONOCIDA, MENSAJE_VALOR_REPETIDO, ErroresDeCampo, ErrorSolicitud
from expediente import vigencia
from expediente.models import EstadoExpediente
from perfil import agenda, ocupacion, ocurrencias, publicacion
from perfil.models import Cobertura, Disponibilidad, PerfilPublico, ServicioMaestro
from territorio.models import Comuna

TAMANO_PAGINA = 20
PAGINA_MAXIMA = 9999
PARAMETROS = frozenset({"oficio", "comuna", "fecha", "inicio", "fin", "pagina"})
PARAMETROS_BLOQUE = ("fecha", "inicio", "fin")

MENSAJE_OFICIO_FALTA = "Elige el oficio que necesitas."
MENSAJE_OFICIO_INVALIDO = "Elige un oficio de la lista."
MENSAJE_COMUNA_FALTA = "Elige la comuna donde necesitas el trabajo."
MENSAJE_COMUNA_INVALIDA = "Elige una comuna de la lista."
MENSAJE_BLOQUE_INCOMPLETO = (
    "Para buscar por horario elige el día, la hora de inicio y la hora de término. "
    "Si no te importa el horario, deja los tres en blanco."
)
MENSAJE_FECHA_INVALIDA = "Elige un día del calendario."
MENSAJE_FECHA_FUERA = "Elige un día entre hoy y los próximos {dias} días."
MENSAJE_FIN_NO_POSTERIOR = (
    "La hora de término debe ser después de la hora de inicio. Por ejemplo, de 08:00 a 12:00."
)
MENSAJE_PAGINA_INVALIDA = "Vuelve a la primera página de resultados."
MENSAJE_TEXTO_INVALIDO = "Este dato tiene caracteres que no se pueden usar. Elígelo de nuevo."

_FECHA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_DIGITOS = re.compile(r"[0-9]{1,6}")


@dataclass(frozen=True)
class Bloque:
    fecha: datetime.date
    inicio_min: int
    fin_min: int


@dataclass(frozen=True)
class Filtros:
    oficio: Oficio
    comuna: Comuna
    bloque: Bloque | None = None
    pagina: int = 1


# --- 1. Parámetros ---


def _unico(parametros, nombre, errores):
    valores = parametros.getlist(nombre)
    if not valores:
        return None
    if len(valores) > 1:
        errores[nombre] = MENSAJE_VALOR_REPETIDO
        return None
    valor = valores[0].strip()
    if "\x00" in valor or len(valor) > 40:
        errores[nombre] = MENSAJE_TEXTO_INVALIDO
        return None
    return valor


def _oficio(valor, errores):
    if valor in (None, ""):
        errores["oficio"] = MENSAJE_OFICIO_FALTA
        return None
    oficio = Oficio.objects.filter(codigo=valor, activo=True).first()
    if oficio is None:
        errores["oficio"] = MENSAJE_OFICIO_INVALIDO
    return oficio


def _comuna(valor, errores):
    if valor in (None, ""):
        errores["comuna"] = MENSAJE_COMUNA_FALTA
        return None
    comuna = None
    if _DIGITOS.fullmatch(valor):
        comuna = Comuna.objects.select_related("provincia").filter(codigo=int(valor)).first()
    if comuna is None:
        errores["comuna"] = MENSAJE_COMUNA_INVALIDA
    return comuna


def _fecha(valor, hoy, errores):
    try:
        fecha = datetime.date.fromisoformat(valor) if _FECHA.fullmatch(valor) else None
    except ValueError:
        fecha = None
    if fecha is None:
        errores["fecha"] = MENSAJE_FECHA_INVALIDA
        return None
    if not hoy <= fecha < hoy + datetime.timedelta(days=ocurrencias.HORIZONTE_DIAS):
        errores["fecha"] = MENSAJE_FECHA_FUERA.format(dias=ocurrencias.HORIZONTE_DIAS - 1)
        return None
    return fecha


def _hora(valor, campo, errores):
    try:
        return agenda.minutos_de_hora(valor)
    except agenda.HoraInvalida as error:
        errores[campo] = error.mensaje
        return None


def _bloque(valores, hoy, errores):
    presentes = [nombre for nombre in PARAMETROS_BLOQUE if valores[nombre] not in (None, "")]
    if not presentes:
        return None
    if len(presentes) < len(PARAMETROS_BLOQUE):
        for nombre in PARAMETROS_BLOQUE:
            if nombre not in presentes and nombre not in errores:
                errores[nombre] = MENSAJE_BLOQUE_INCOMPLETO
        return None
    fecha = _fecha(valores["fecha"], hoy, errores)
    inicio = _hora(valores["inicio"], "inicio", errores)
    fin = _hora(valores["fin"], "fin", errores)
    if inicio is not None and inicio >= ocurrencias.MINUTOS_DIA:
        errores["inicio"] = agenda.MENSAJE_INICIO_FIN_DE_DIA
        return None
    if inicio is not None and fin is not None and fin <= inicio:
        errores["fin"] = MENSAJE_FIN_NO_POSTERIOR
        return None
    if fecha is None or inicio is None or fin is None:
        return None
    return Bloque(fecha, inicio, fin)


def _pagina(valor, errores):
    if valor in (None, ""):
        return 1
    if not _DIGITOS.fullmatch(valor) or not 1 <= int(valor) <= PAGINA_MAXIMA:
        errores["pagina"] = MENSAJE_PAGINA_INVALIDA
        return None
    return int(valor)


def leer_filtros(parametros, hoy):
    """Filtros validados desde ``request.GET``.

    - Parámetro desconocido: ``ErrorSolicitud`` (400 general, sin repetirlo).
    - Parámetro inválido o que falta: ``ErroresDeCampo`` (400 en el campo).
    """
    if set(parametros) - PARAMETROS:
        raise ErrorSolicitud(MENSAJE_CLAVE_DESCONOCIDA)
    errores = {}
    valores = {nombre: _unico(parametros, nombre, errores) for nombre in PARAMETROS}
    oficio = _oficio(valores["oficio"], errores) if "oficio" not in errores else None
    comuna = _comuna(valores["comuna"], errores) if "comuna" not in errores else None
    bloque = _bloque(valores, hoy, errores)
    pagina = _pagina(valores["pagina"], errores) if "pagina" not in errores else None
    if errores:
        raise ErroresDeCampo(errores)
    return Filtros(oficio=oficio, comuna=comuna, bloque=bloque, pagina=pagina)


# --- 2. Carga en lote ---


@dataclass
class Candidato:
    """Lo que la búsqueda sabe de un maestro. Nunca se serializa entero."""

    maestro_id: int
    perfil: PerfilPublico | None = None
    servicio_visible: bool = False
    comunas: dict = field(default_factory=dict)  # codigo -> es_base
    ofrecibles: list = field(default_factory=list)  # Ocurrencia


def cargar_candidatos(oficio, comunas, ahora, hoy):
    """``[Candidato]`` de los maestros que podrían cumplir con ``oficio`` en alguna de ``comunas``.

    Consultas constantes: servicios (1), contexto en lote (6), cobertura (1),
    agenda (1), perfiles (1) y rangos ocupados (1, sobre ``ticket``).
    """
    servicios = list(
        ServicioMaestro.objects.filter(
            retirado_en__isnull=True,
            servicio__oficio=oficio,
            maestro__expediente__estado=EstadoExpediente.APROBADO,
            maestro_id__in=Cobertura.objects.filter(comuna_id__in=comunas).values("maestro_id"),
        ).select_related("servicio__oficio")
    )
    if not servicios:
        return []
    contextos = publicacion.contextos_en_lote(
        {s.maestro_id for s in servicios}, servicio_ids={s.servicio_id for s in servicios}
    )
    candidatos = {}
    for servicio in servicios:
        candidato = candidatos.setdefault(servicio.maestro_id, Candidato(servicio.maestro_id))
        if not publicacion.motivos_no_visible_de(servicio, contextos[servicio.maestro_id], hoy):
            candidato.servicio_visible = True
    ids = [m for m, c in candidatos.items() if c.servicio_visible]
    if not ids:
        return []
    for maestro_id, codigo, es_base in Cobertura.objects.filter(maestro_id__in=ids).values_list(
        "maestro_id", "comuna_id", "es_base"
    ):
        candidatos[maestro_id].comunas[codigo] = es_base
    patrones = defaultdict(list)
    for patron in Disponibilidad.objects.filter(maestro_id__in=ids, retirado_en__isnull=True).order_by(
        "dia_semana", "inicio_min", "pk"
    ):
        patrones[patron.maestro_id].append(patron)
    desde = ocurrencias.instante(hoy, 0) or ahora
    hasta = desde + datetime.timedelta(days=ocurrencias.HORIZONTE_DIAS + 1)
    ocupados = ocupacion.rangos_ocupados(ids, desde, hasta)
    for perfil in PerfilPublico.objects.filter(perfil_maestro_id__in=ids).select_related("perfil_maestro__usuario"):
        candidatos[perfil.perfil_maestro_id].perfil = perfil
    for maestro_id in ids:
        candidatos[maestro_id].ofrecibles = [
            una
            for una in ocurrencias.ocurrencias(patrones[maestro_id], hoy, ocurrencias.HORIZONTE_DIAS)
            if ocurrencias.ofrecible(una, ahora, ocupados.get(maestro_id, ()))
        ]
    return [candidatos[m] for m in ids if candidatos[m].perfil is not None]


# --- 3. Decisión pura ---


def contiene(una, bloque):
    """La ocurrencia es de ese día y contiene el rango pedido (ADR-022, D-3)."""
    return una.fecha == bloque.fecha and una.inicio_min <= bloque.inicio_min and una.fin_min >= bloque.fin_min


def cumple_bloque(candidato, bloque):
    return bloque is None or any(contiene(una, bloque) for una in candidato.ofrecibles)


def cumple_comuna(candidato, comuna_codigo):
    return comuna_codigo in candidato.comunas


def cumple(candidato, comuna_codigo, bloque):
    """Filtros excluyentes de RF-09 (CA-02.4). El oficio y la publicación ya los decidió la regla única."""
    return candidato.servicio_visible and cumple_comuna(candidato, comuna_codigo) and cumple_bloque(candidato, bloque)


# --- 4. Orden ---


def calificaciones_en_lote(maestro_ids):
    """``{maestro_id: (promedio, cantidad)}``. Las evaluaciones llegan en el S5: hoy, vacío."""
    return {}


def ordenar(candidatos, comuna_codigo, bloque, hoy, en_cobertura=True):
    """Candidatos de mayor a menor puntaje, con el desempate de RF-11 (ADR-022, puntos 2 y 3)."""
    calificaciones = calificaciones_en_lote([c.maestro_id for c in candidatos])

    def clave(candidato):
        d = puntaje.disponibilidad({u.fecha for u in candidato.ofrecibles}, hoy, bloque is not None)
        c = puntaje.cercania(candidato.comunas.get(comuna_codigo, False), en_cobertura)
        promedio, cantidad = calificaciones.get(candidato.maestro_id, (None, 0))
        return puntaje.clave_orden(puntaje.puntaje(d, c), promedio, cantidad, candidato.perfil.ref, hoy)

    return sorted(candidatos, key=clave)


@dataclass
class Resultado:
    principales: list
    total: int
    pagina: int
    paginas: int
    sugerencias: list  # [(Candidato, incumple)]


def buscar(filtros, ahora):
    """Aplica los filtros, ordena y pagina. Las sugerencias solo si no hay resultados (RF-12)."""
    from busqueda import sugerencias

    hoy = vigencia.hoy_negocio(ahora)
    provincia = list(Comuna.objects.filter(provincia_id=filtros.comuna.provincia_id).values_list("codigo", flat=True))
    candidatos = cargar_candidatos(filtros.oficio, provincia, ahora, hoy)
    codigo = filtros.comuna.codigo
    principales = ordenar([c for c in candidatos if cumple(c, codigo, filtros.bloque)], codigo, filtros.bloque, hoy)
    total = len(principales)
    paginas = max(1, -(-total // TAMANO_PAGINA))
    inicio = (filtros.pagina - 1) * TAMANO_PAGINA
    propuestas = [] if total else sugerencias.sugerir(candidatos, codigo, filtros.bloque, hoy)
    return Resultado(principales[inicio:inicio + TAMANO_PAGINA], total, filtros.pagina, paginas, propuestas)
