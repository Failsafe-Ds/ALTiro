"""``GET /api/busqueda``, pública (RF-09 a RF-13, CA-04.1; ADR-022).

Parámetros: ``oficio`` (código), ``comuna`` (código CUT), opcionalmente
``fecha`` (AAAA-MM-DD), ``inicio`` y ``fin`` ("HH:MM", los tres juntos) y
``pagina``. Desconocidos: 400 general; inválidos: 400 en el campo.

Respuesta con lista explícita de campos. Cada tarjeta (RF-13): ref pública,
nombre, foto de 160 px, oficio y calificación (``{promedio, cantidad}``, o
``null`` y "Todavía no tiene evaluaciones"; calculada en lote por ``ordenar``),
y las comunas que atiende (``atiende_en``, hasta ``MAXIMO_COMUNAS`` nombres, y
``atiende_en_mas``; ADR-022, E-1): primero la comuna buscada, después las de
la misma región y al final las demás, cada grupo en orden alfabético, así que
el orden no delata la base. Y el ``precio`` del servicio visible del oficio
buscado (DA-29; ADR-022, E-2): ``{modalidad, modalidad_texto, monto, desde}``,
con los mismos nombres que la ficha pública; si hay más de uno, el de menor
monto y ``desde`` verdadero. Se toma de la misma carga de servicios de la
búsqueda (sin consultas extra) y no entra al puntaje ni al orden. **Nunca** el puntaje ni sus componentes, cuál es la
comuna base, el RUT ni el contacto (ADR-022, puntos 2 y 5). Las sugerencias van en
una lista aparte y cada una indica qué criterio incumple (RF-12, CA-04.2,
CA-04.3). ``Cache-Control: no-store`` (una licencia que vence o una
suspensión deben reflejarse en la siguiente búsqueda; RNF-25).
"""
import unicodedata

from django.http import JsonResponse
from django.utils import timezone

from busqueda import servicios, sugerencias
from catalogo.models import Modalidad
from evaluaciones import calificacion
from comun.api import manejar_errores, metodos, publica
from expediente import vigencia
from perfil.vistas_publicas import url_foto
from territorio.models import Comuna

TAMANO_FOTO = 160
MAXIMO_COMUNAS = 3
SIN_EVALUACIONES = calificacion.SIN_EVALUACIONES
MENSAJE_SIN_RESULTADOS = (
    "No encontramos maestros con esos criterios. Prueba con otro horario, otro día o una comuna cercana."
)


def _alfabetico(nombre):
    return unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()


def comunas_en_lote(candidatos):
    """``{codigo: (nombre, region)}`` de todas las comunas atendidas por ``candidatos``, en una consulta."""
    codigos = {codigo for c in candidatos for codigo in c.comunas}
    return {
        codigo: (nombre, region)
        for codigo, nombre, region in Comuna.objects.filter(codigo__in=codigos).values_list(
            "codigo", "nombre", "provincia__region_id"
        )
    }


def atiende_en(candidato, buscada, nombres):
    """Nombres de las comunas atendidas, sin marcar la base (ADR-022, E-1)."""
    region_buscada = buscada.provincia.region_id

    def clave(codigo):
        nombre, region = nombres[codigo]
        return (codigo != buscada.codigo, region != region_buscada, _alfabetico(nombre))

    orden = sorted((codigo for codigo in candidato.comunas if codigo in nombres), key=clave)
    return [nombres[codigo][0] for codigo in orden[:MAXIMO_COMUNAS]], max(0, len(orden) - MAXIMO_COMUNAS)


def precio(candidato):
    """Precio publicado del oficio buscado, sin consultas extra (DA-29; ADR-022, E-2)."""
    servicio = candidato.precio
    return {
        "modalidad": servicio.modalidad,
        "modalidad_texto": Modalidad(servicio.modalidad).label,
        "monto": servicio.monto,
        "desde": candidato.servicios_del_oficio > 1,
    }


def tarjeta(candidato, oficio, buscada, nombres):
    perfil = candidato.perfil
    comunas, mas = atiende_en(candidato, buscada, nombres)
    return {
        "ref": str(perfil.ref),
        "nombre": perfil.perfil_maestro.usuario.nombre,
        "foto": url_foto(perfil, TAMANO_FOTO),
        "oficio": {"codigo": oficio.codigo, "nombre": oficio.nombre},
        "calificacion": calificacion.datos_tarjeta(candidato.calificacion),
        "calificacion_texto": calificacion.texto(candidato.calificacion),
        "atiende_en": comunas,
        "atiende_en_mas": mas,
        "precio": precio(candidato),
    }


def _con_cabeceras(respuesta):
    respuesta["Cache-Control"] = "no-store"
    return respuesta


@publica
@metodos("GET")
def busqueda(request):
    ahora = timezone.now()
    return _con_cabeceras(_buscar(request, ahora))


@manejar_errores
def _buscar(request, ahora):
    filtros = servicios.leer_filtros(request.GET, vigencia.hoy_negocio(ahora))
    resultado = servicios.buscar(filtros, ahora)
    nombres = comunas_en_lote(resultado.principales + [c for c, _ in resultado.sugerencias])

    def una(candidato):
        return tarjeta(candidato, filtros.oficio, filtros.comuna, nombres)

    return JsonResponse(
        {
            "resultados": [una(c) for c in resultado.principales],
            "total": resultado.total,
            "pagina": resultado.pagina,
            "paginas": resultado.paginas,
            "mensaje": None if resultado.total else MENSAJE_SIN_RESULTADOS,
            "sugerencias": [
                {**una(c), "incumple": incumple, "incumple_texto": sugerencias.TEXTOS[incumple]}
                for c, incumple in resultado.sugerencias
            ],
        }
    )
