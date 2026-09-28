"""Toda ruta ``/api/`` es privada por defecto (RF-02, CA-25.3; propuesta del S1, §5, punto 1).

Las vistas públicas se marcan con ``comun.api.publica``. Sin sesión, una ruta
privada responde 401 antes de ejecutar la vista.
"""
from comun.api import respuesta_error

MENSAJE_SIN_SESION = "Tu sesión terminó o no has iniciado sesión. Inicia sesión para continuar."


class PrivadoPorDefectoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, vista, args, kwargs):
        if not request.path.startswith("/api/"):
            return None
        if getattr(vista, "publica", False):
            return None
        if getattr(request, "usuario", None) is None:
            return respuesta_error(401, MENSAJE_SIN_SESION)
        return None
