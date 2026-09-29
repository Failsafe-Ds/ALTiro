"""Política de acceso a un ticket (RNF-07, CA-25.1, HU-25; ADR-023, punto 6; cierra DA-05).

Solo el cliente o el maestro de **ese** ticket. Cualquier otro usuario
autenticado, incluidos los roles administrativos (curatoría, comercial,
moderación y control de gestión), recibe el 404 idéntico y queda registrado
en ``acceso_denegado`` (``obtener_autorizado`` + middleware). Moderación
llega a la conversación con una disputa abierta en el S5; hoy no hay excepción.
"""
from autorizacion.politicas import Politica


class PoliticaTicket(Politica):
    entidad = "ticket"

    def permite(self, usuario, ticket):
        # ``perfil_cliente`` y ``perfil_maestro`` usan como clave primaria el id del usuario.
        return usuario.pk in (ticket.cliente_id, ticket.perfil_maestro_id)
