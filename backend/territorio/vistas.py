"""Endpoints públicos de solo lectura del catálogo territorial (RF-01, CA-01.2, ADR-012)."""
from django.http import JsonResponse

from comun.api import metodos, publica, respuesta_error
from territorio.models import Comuna, Region

# Lista cerrada y estable: se puede guardar en caché del navegador (RNF-02).
_CACHE = "public, max-age=3600"


@publica
@metodos("GET")
def regiones(request):
    respuesta = JsonResponse(
        {"regiones": [{"codigo": r.codigo, "nombre": r.nombre} for r in Region.objects.order_by("orden")]}
    )
    respuesta["Cache-Control"] = _CACHE
    return respuesta


@publica
@metodos("GET")
def comunas_de_region(request, codigo):
    """Solo las comunas de la región pedida (CA-01.2), con su provincia."""
    if not Region.objects.filter(codigo=codigo).exists():
        return respuesta_error(404, "No encontramos esa región. Elige una región de la lista.")
    comunas = (
        Comuna.objects.filter(provincia__region_id=codigo).select_related("provincia").order_by("nombre")
    )
    respuesta = JsonResponse(
        {
            "comunas": [
                {
                    "codigo": c.codigo,
                    "nombre": c.nombre,
                    "provincia": {"codigo": c.provincia.codigo, "nombre": c.provincia.nombre},
                }
                for c in comunas
            ]
        }
    )
    respuesta["Cache-Control"] = _CACHE
    return respuesta
