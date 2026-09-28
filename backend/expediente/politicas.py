"""Política de acceso a los documentos del expediente (HU-25, CA-25.2, RNF-06, RNF-07; ADR-011, ADR-015).

Regla de HU-25: "curatoría puede revisar documentos por su función… cualquier
otro acceso se deniega y queda registrado".

- Permite al maestro dueño del expediente del documento.
- Permite a quien tiene el rol ``curatoria``, leído desde ``usuario_rol`` en la
  base de datos, nunca desde la petición.
- Todos los demás (cliente, otro maestro, comercial, moderación, control de
  gestión) quedan denegados: ``obtener_autorizado`` lanza ``AccesoDenegado`` y
  el middleware responde el 404 idéntico y lo registra (ADR-011, puntos 2 y 3).

Conflicto de interés (ADR-011, E-2): no aplica a estas rutas. Si el dueño
tiene además el rol ``curatoria``, se le permite como dueño, igual que a
cualquier maestro con su propio documento. El conflicto se evalúa en las
rutas de curatoría (incremento 4), donde el dueño no puede revisar ni
resolver su propio expediente.
"""
from autorizacion.politicas import Politica
from identidad.models import Rol, UsuarioRol


class PoliticaDocumento(Politica):
    entidad = "documento"

    def permite(self, usuario, documento):
        if documento.expediente.perfil_maestro_id == usuario.pk:
            return True
        return UsuarioRol.objects.filter(usuario=usuario, rol=Rol.CURATORIA).exists()
