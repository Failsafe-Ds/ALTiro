"""Excepciones de autorización (RNF-07; ADR-011, «Decisión»).

Las traduce ``autorizacion.middleware.AutorizacionMiddleware``:

- ``RecursoNoEncontrado``: 404 neutro, sin registro.
- ``AccesoDenegado``: el recurso existe pero la política lo deniega; se
  registra en ``acceso_denegado`` y responde exactamente el mismo 404.
- ``RolRequerido``: falta el rol en una ruta cuya existencia no es secreta;
  se registra (``entidad_ref`` NULL) y responde 403.
- ``ConflictoDeInteres``: el usuario tiene el rol, pero actúa sobre un recurso
  propio donde la política declara conflicto (ADR-011, E-2; ADR-013, punto 2.5);
  se registra y responde 403 con un mensaje accionable, sin ``AlTiro-Rechazo``.
"""


class RecursoNoEncontrado(Exception):
    """La referencia no corresponde a ningún recurso."""


class AccesoDenegado(Exception):
    """El recurso existe, pero la política lo deniega a este usuario."""

    def __init__(self, entidad, ref):
        super().__init__(entidad)
        self.entidad = entidad
        self.ref = ref


class RolRequerido(Exception):
    """El usuario no tiene ninguno de los roles que exige la ruta."""

    def __init__(self, roles):
        super().__init__(", ".join(roles))
        self.roles = tuple(roles)


class ConflictoDeInteres(Exception):
    """El usuario tiene el rol, pero el recurso es suyo y la política declara conflicto de interés."""

    def __init__(self, entidad, ref):
        super().__init__(entidad)
        self.entidad = entidad
        self.ref = ref
