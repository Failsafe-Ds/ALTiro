"""Deja en ``request.usuario`` el usuario de la sesión, o ``None`` (visitante), y la sesión sin renovar en consultas automáticas."""
from django.contrib.sessions.middleware import SessionMiddleware

from identidad.sesion import usuario_de_la_sesion


class UsuarioDeLaSesionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.usuario = usuario_de_la_sesion(request)
        return self.get_response(request)


class SesionMiddleware(SessionMiddleware):
    """``SessionMiddleware`` que no renueva el plazo en las consultas automáticas (ADR-005, «Actividad»).

    Solo cuentan como actividad las peticiones iniciadas por la persona. Una
    vista de consulta periódica (hoy, la lectura de la conversación; ADR-026,
    E-2.5) marca ``request.sin_renovar_sesion``: si la sesión no cambió, no se
    guarda ni se reenvía la cookie, y el vencimiento sigue donde estaba.
    """

    def process_response(self, request, response):
        sesion = getattr(request, "session", None)
        if getattr(request, "sin_renovar_sesion", False) and sesion is not None and not sesion.modified:
            return response
        return super().process_response(request, response)
