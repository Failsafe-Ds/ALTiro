"""Deja en ``request.usuario`` el usuario de la sesión, o ``None`` (visitante)."""
from identidad.sesion import usuario_de_la_sesion


class UsuarioDeLaSesionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.usuario = usuario_de_la_sesion(request)
        return self.get_response(request)
