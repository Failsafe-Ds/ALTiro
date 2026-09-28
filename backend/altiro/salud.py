"""Verificación de salud del servicio (infraestructura; RNF-23)."""
import logging

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def salud(request):
    """Responde 200 si la aplicación funciona y la base de datos responde; 503 si no.

    La respuesta nunca incluye detalles internos del error.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError as error:
        logger.warning("Salud: base de datos no disponible (%s).", type(error).__name__)
        respuesta = JsonResponse({"estado": "con_problemas", "base_datos": "no_disponible"}, status=503)
    else:
        respuesta = JsonResponse({"estado": "ok", "base_datos": "ok"})
    respuesta["Cache-Control"] = "no-store"
    return respuesta
