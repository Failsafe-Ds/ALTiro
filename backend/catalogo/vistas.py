"""Endpoints públicos de solo lectura del catálogo (ADR-017, punto 1; ADR-018, puntos 5 y 6; CA-20.2).

- ``GET /api/oficios``: oficios activos (lo usa la postulación del maestro).
- ``GET /api/catalogo``: oficios y servicios activos con sus modalidades y
  precios de referencia. Sin datos personales ni identificadores internos.

Caché (ADR-018, punto 5; D-16): ``Cache-Control: no-cache`` más ``ETag``. El
navegador revalida en cada consulta y recibe 304 si nada cambió; si comercial
cambió un precio, recibe el valor actualizado (CA-20.2). El ``max-age=3600``
anterior lo habría impedido.
"""
import hashlib
import json

from django.http import HttpResponse

from catalogo.models import Oficio, Servicio, ServicioModalidad
from comun.api import metodos, publica


def datos_oficio(oficio):
    """Lista explícita de campos de un oficio. Sin datos personales."""
    return {"codigo": oficio.codigo, "nombre": oficio.nombre, "regulado": oficio.regulado}


def datos_modalidad(modalidad):
    return {"modalidad": modalidad.modalidad, "precio_referencia": modalidad.precio_referencia}


def _respuesta_revalidable(request, datos):
    """JSON con ``Cache-Control: no-cache`` y ``ETag`` fuerte; 304 si el cliente ya tiene esta versión."""
    cuerpo = json.dumps(datos, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    etag = f'"{hashlib.sha256(cuerpo).hexdigest()[:32]}"'
    candidatos = [valor.strip() for valor in request.headers.get("If-None-Match", "").split(",")]
    if etag in candidatos:
        respuesta = HttpResponse(status=304)
    else:
        respuesta = HttpResponse(cuerpo, content_type="application/json")
    respuesta["ETag"] = etag
    respuesta["Cache-Control"] = "no-cache"
    return respuesta


@publica
@metodos("GET")
def oficios(request):
    activos = Oficio.objects.filter(activo=True).order_by("orden", "codigo")
    return _respuesta_revalidable(request, {"oficios": [datos_oficio(o) for o in activos]})


def catalogo_publico():
    """Oficios activos con sus servicios activos y las modalidades de cada uno (RF-36, CA-20.2)."""
    oficios_activos = list(Oficio.objects.filter(activo=True).order_by("orden", "codigo"))
    servicios = list(
        Servicio.objects.filter(activo=True, oficio__in=oficios_activos).order_by("orden", "nombre", "pk")
    )
    modalidades = {}
    for modalidad in ServicioModalidad.objects.filter(servicio__in=servicios).order_by("modalidad"):
        modalidades.setdefault(modalidad.servicio_id, []).append(datos_modalidad(modalidad))
    por_oficio = {}
    for servicio in servicios:
        if servicio.pk in modalidades:
            por_oficio.setdefault(servicio.oficio_id, []).append(
                {"ref": str(servicio.ref), "nombre": servicio.nombre, "modalidades": modalidades[servicio.pk]}
            )
    return {
        "oficios": [
            {**datos_oficio(oficio), "servicios": por_oficio.get(oficio.pk, [])} for oficio in oficios_activos
        ]
    }


@publica
@metodos("GET")
def catalogo(request):
    return _respuesta_revalidable(request, catalogo_publico())
