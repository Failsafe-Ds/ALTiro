"""Inicio, cierre y lectura de la sesión (RF-02, RNF-09, ADR-005).

``django.contrib.auth`` no está instalada (ADR-001), así que no se usan
``login()`` ni ``logout()``. La sesión guarda el id del usuario y
``get_session_auth_hash()``: si el hash de la contraseña cambia, la sesión
deja de ser válida.
"""
from django.middleware.csrf import rotate_token
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from identidad.models import Usuario

_CLAVE_USUARIO = "_usuario_id"
_CLAVE_HASH = "_usuario_hash"


def iniciar_sesion(request, usuario):
    """Crea la sesión autenticada con un ID nuevo (rotación) y rota el token CSRF (ADR-006)."""
    if request.session.get(_CLAVE_USUARIO) not in (None, usuario.pk):
        request.session.flush()
    else:
        request.session.cycle_key()
    request.session[_CLAVE_USUARIO] = usuario.pk
    request.session[_CLAVE_HASH] = usuario.get_session_auth_hash()
    rotate_token(request)
    Usuario.objects.filter(pk=usuario.pk).update(last_login=timezone.now())
    request.usuario = usuario


def cerrar_sesion(request):
    """Borra la sesión en el servidor (RF-02)."""
    request.session.flush()
    request.usuario = None


def usuario_de_la_sesion(request):
    """Devuelve el usuario de la sesión vigente o ``None``. Una sesión inválida se borra."""
    pk = request.session.get(_CLAVE_USUARIO)
    if pk is None:
        return None
    usuario = Usuario.objects.filter(pk=pk).first()
    if usuario is None or not constant_time_compare(
        request.session.get(_CLAVE_HASH, ""), usuario.get_session_auth_hash()
    ):
        request.session.flush()
        return None
    return usuario
