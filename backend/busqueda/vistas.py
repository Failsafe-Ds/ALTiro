"""``GET /api/busqueda``, pública (RF-09 a RF-13, CA-04.1; ADR-022).

Parámetros: ``oficio`` (código), ``comuna`` (código CUT), opcionalmente
``fecha`` (AAAA-MM-DD), ``inicio`` y ``fin`` ("HH:MM", los tres juntos) y
``pagina``. Desconocidos: 400 general; inválidos: 400 en el campo.

Respuesta con lista explícita de campos. Cada tarjeta (RF-13): ref pública,
nombre, foto de 160 px, oficio y calificación (``null`` y "Todavía no tiene
evaluaciones" hasta el S5). **Nunca** el puntaje ni sus componentes, la comuna
base, el RUT ni el contacto (ADR-022, puntos 2 y 5). Las sugerencias van en
una lista aparte y cada una indica qué criterio incumple (RF-12, CA-04.2,
CA-04.3). ``Cache-Control: no-store`` (una licencia que vence o una
suspensión deben reflejarse en la siguiente búsqueda; RNF-25).
"""
from django.http import JsonResponse
from django.utils import timezone

from busqueda import servicios, sugerencias
from comun.api import manejar_errores, metodos, publica
from expediente import vigencia
from perfil.vistas_publicas import url_foto

TAMANO_FOTO = 160
SIN_EVALUACIONES = "Todavía no tiene evaluaciones"
MENSAJE_SIN_RESULTADOS = (
    "No encontramos maestros con esos criterios. Prueba con otro horario, otro día o una comuna cercana."
)


def tarjeta(candidato, oficio):
    perfil = candidato.perfil
    return {
        "ref": str(perfil.ref),
        "nombre": perfil.perfil_maestro.usuario.nombre,
        "foto": url_foto(perfil, TAMANO_FOTO),
        "oficio": {"codigo": oficio.codigo, "nombre": oficio.nombre},
        "calificacion": None,
        "calificacion_texto": SIN_EVALUACIONES,
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
    return JsonResponse(
        {
            "resultados": [tarjeta(c, filtros.oficio) for c in resultado.principales],
            "total": resultado.total,
            "pagina": resultado.pagina,
            "paginas": resultado.paginas,
            "mensaje": None if resultado.total else MENSAJE_SIN_RESULTADOS,
            "sugerencias": [
                {**tarjeta(c, filtros.oficio), "incumple": incumple, "incumple_texto": sugerencias.TEXTOS[incumple]}
                for c, incumple in resultado.sugerencias
            ],
        }
    )
