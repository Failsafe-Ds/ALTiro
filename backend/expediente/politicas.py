"""Políticas de acceso al expediente y a sus documentos (HU-19, HU-25, CA-19.4, CA-25.2, RNF-06, RNF-07; ADR-011, ADR-015, ADR-017).

Regla de HU-25: "curatoría puede revisar documentos por su función… cualquier
otro acceso se deniega y queda registrado". Regla de HU-19: "Ningún maestro
se auto aprueba".

``PoliticaDocumento`` (rutas generales ``/api/documentos/…``, incremento 3):

- Permite al maestro dueño del expediente del documento.
- Permite a quien tiene el rol ``curatoria``, leído desde ``usuario_rol`` en la
  base de datos, nunca desde la petición.
- Todos los demás (cliente, otro maestro, comercial, moderación, control de
  gestión) quedan denegados: ``obtener_autorizado`` lanza ``AccesoDenegado`` y
  el middleware responde el 404 idéntico y lo registra (ADR-011, puntos 2 y 3).
- Sin conflicto de interés: si el dueño tiene además el rol ``curatoria``, se
  le permite como dueño, igual que a cualquier maestro con su propio documento.

Políticas de las rutas de curatoría (``/api/curatoria/…``, incremento 4). La
vista exige además el rol con ``@requiere_rol("curatoria")``:

- ``PoliticaExpedienteCuratoria`` y ``PoliticaDocumentoCuratoria``: conflicto
  de interés si el usuario es el dueño del expediente (ADR-011, E-2; ADR-013,
  punto 2.5): 403 accionable y registrado, también en lectura. Si no hay
  conflicto, permiten a quien tiene el rol ``curatoria``.
"""
from autorizacion.politicas import Politica
from identidad.models import Rol, UsuarioRol


def tiene_rol_curatoria(usuario):
    """El rol se lee desde ``usuario_rol`` en la base de datos."""
    return UsuarioRol.objects.filter(usuario=usuario, rol=Rol.CURATORIA).exists()


def es_dueno_del_expediente(usuario, expediente):
    # ``perfil_maestro`` usa como clave primaria el id del usuario.
    return expediente.perfil_maestro_id == usuario.pk


class PoliticaDocumento(Politica):
    entidad = "documento"

    def permite(self, usuario, documento):
        if es_dueno_del_expediente(usuario, documento.expediente):
            return True
        return tiene_rol_curatoria(usuario)


class PoliticaExpedienteCuratoria(Politica):
    entidad = "expediente"

    def conflicto(self, usuario, expediente):
        return es_dueno_del_expediente(usuario, expediente)

    def permite(self, usuario, expediente):
        return tiene_rol_curatoria(usuario)


class PoliticaDocumentoCuratoria(Politica):
    entidad = "documento"

    def conflicto(self, usuario, documento):
        return es_dueno_del_expediente(usuario, documento.expediente)

    def permite(self, usuario, documento):
        return tiene_rol_curatoria(usuario)
