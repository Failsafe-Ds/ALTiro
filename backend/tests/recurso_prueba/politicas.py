"""Política del recurso ficticio: solo su dueño, sin excepción por rol (ADR-013, punto 2)."""
from autorizacion.politicas import Politica


class PoliticaRecursoPrueba(Politica):
    entidad = "recurso_prueba"

    def permite(self, usuario, objeto):
        return usuario is not None and objeto.dueno_id == usuario.pk
