"""Política de acceso a un servicio del maestro (RNF-07, CA-25.1; ADR-011; ADR-019).

Solo el maestro dueño. Cualquier otro usuario con el rol ``maestro`` recibe el
404 idéntico y queda registrado (``obtener_autorizado`` + middleware). Los
demás roles no llegan aquí: la vista exige ``@requiere_rol("maestro")`` (403
registrado). No hay función administrativa definida sobre esta ruta.
"""
from autorizacion.politicas import Politica


class PoliticaServicioMaestro(Politica):
    entidad = "servicio_maestro"

    def permite(self, usuario, servicio_maestro):
        # ``perfil_maestro`` usa como clave primaria el id del usuario.
        return servicio_maestro.maestro_id == usuario.pk


class PoliticaDisponibilidad(Politica):
    """Solo el maestro dueño del bloque (ADR-020; mismo criterio que ``PoliticaServicioMaestro``)."""

    entidad = "disponibilidad"

    def permite(self, usuario, bloque):
        return bloque.maestro_id == usuario.pk
