"""Exigencia de rol en una vista (RNF-07, HU-25; propuesta del S1, §5, punto 2; ADR-011, punto 2).

``requiere_rol(*roles)`` lee los roles de ``usuario_rol`` en la base de datos,
nunca de la petición. Si el usuario no tiene ninguno, lanza ``RolRequerido``
(403, registrado). Tener el rol es condición necesaria, no suficiente: la
vista debe aplicar además la política del recurso (``obtener_autorizado``).

Una vista con rol exigido nunca es pública: combinarla con
``comun.api.publica`` en cualquier orden es un error de configuración.
"""
import functools

from django.core.exceptions import ImproperlyConfigured

from autorizacion.excepciones import RolRequerido
from comun.api import respuesta_error
from comun.middleware import MENSAJE_SIN_SESION
from identidad.models import Rol, UsuarioRol

_ROLES_VALIDOS = frozenset(valor for valor, _ in Rol.choices)


def requiere_rol(*roles):
    if not roles or set(roles) - _ROLES_VALIDOS:
        raise ImproperlyConfigured("requiere_rol exige uno o más roles definidos.")

    def decorador(vista):
        if getattr(vista, "publica", False):
            raise ImproperlyConfigured("Una vista pública no puede exigir un rol.")

        @functools.wraps(vista)
        def envoltura(request, *args, **kwargs):
            usuario = getattr(request, "usuario", None)
            if usuario is None:
                return respuesta_error(401, MENSAJE_SIN_SESION)
            if not UsuarioRol.objects.filter(usuario=usuario, rol__in=roles).exists():
                raise RolRequerido(roles)
            return vista(request, *args, **kwargs)

        envoltura.roles_requeridos = tuple(roles)
        return envoltura

    return decorador
