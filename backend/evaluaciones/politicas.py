"""Política de las rutas de moderación (HU-21, HU-25, CA-21.1, CA-25.3; ADR-026, E-4.3).

La vista exige además ``@requiere_rol("moderacion")``.

- ``PoliticaDenuncia``: conflicto de interés si el moderador es parte del
  ticket de la evaluación denunciada (403 accionable y registrado, también en
  lectura; ADR-013, punto 2.5). Sin conflicto, permite a quien tiene el rol
  ``moderacion`` (leído de ``usuario_rol``).
- ``PoliticaConversacionDenuncia``: además exige la denuncia ``abierta``
  (E-4.1: la disputa abierta es la denuncia abierta). En otro caso,
  ``AccesoDenegado``: el 404 idéntico con registro.
"""
from autorizacion.politicas import Politica
from evaluaciones.models import EstadoDenuncia
from identidad.models import Rol, UsuarioRol

MENSAJE_CONFLICTO = (
    "No puedes revisar una denuncia de un trabajo en el que participaste. Otra persona de moderación debe hacerlo."
)


def tiene_rol_moderacion(usuario):
    return UsuarioRol.objects.filter(usuario=usuario, rol=Rol.MODERACION).exists()


def es_parte(usuario, ticket):
    # ``perfil_cliente`` y ``perfil_maestro`` usan como clave primaria el id del usuario.
    return usuario.pk in (ticket.cliente_id, ticket.perfil_maestro_id)


class PoliticaDenuncia(Politica):
    entidad = "denuncia"
    mensaje_conflicto = MENSAJE_CONFLICTO

    def conflicto(self, usuario, denuncia):
        return es_parte(usuario, denuncia.evaluacion.ticket)

    def permite(self, usuario, denuncia):
        return tiene_rol_moderacion(usuario)


class PoliticaConversacionDenuncia(PoliticaDenuncia):
    def permite(self, usuario, denuncia):
        return denuncia.estado == EstadoDenuncia.ABIERTA and super().permite(usuario, denuncia)
