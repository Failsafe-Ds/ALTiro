"""Endpoint público de solo lectura del catálogo mínimo de oficios (ADR-017, punto 1; propuesta del S2, §4)."""
from django.http import JsonResponse

from catalogo.models import Oficio
from comun.api import metodos, publica


def datos_oficio(oficio):
    """Lista explícita de campos de un oficio. Sin datos personales."""
    return {"codigo": oficio.codigo, "nombre": oficio.nombre, "regulado": oficio.regulado}


@publica
@metodos("GET")
def oficios(request):
    respuesta = JsonResponse({"oficios": [datos_oficio(o) for o in Oficio.objects.order_by("orden", "codigo")]})
    # Lista cerrada que cambia solo con una migración (mismo criterio que el catálogo territorial).
    respuesta["Cache-Control"] = "public, max-age=3600"
    return respuesta
