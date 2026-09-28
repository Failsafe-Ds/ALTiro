"""Vistas de prueba de la autorización centralizada (RNF-07; ADR-011). Privadas por defecto."""
from django.http import JsonResponse

from autorizacion.acceso import obtener_autorizado
from autorizacion.decoradores import requiere_rol
from comun.api import metodos
from tests.recurso_prueba.models import RecursoPrueba
from tests.recurso_prueba.politicas import PoliticaRecursoPrueba


@metodos("GET")
def recurso(request, ref):
    objeto = obtener_autorizado(RecursoPrueba.objects.all(), ref, request.usuario, PoliticaRecursoPrueba())
    return JsonResponse({"recurso": {"ref": str(objeto.ref)}})


@metodos("GET")
@requiere_rol("curatoria")
def solo_curatoria(request):
    return JsonResponse({"mensaje": "Acceso permitido."})
