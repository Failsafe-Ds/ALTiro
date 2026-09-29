"""Política de acceso de comercial al catálogo (RNF-07, HU-20; ADR-018, punto 6).

La vista exige además ``@requiere_rol("comercial")``. El catálogo no es un
recurso de una persona: la política permite a quien tiene el rol
``comercial`` (leído desde ``usuario_rol`` en la base de datos). No hay
conflicto de interés definido en el informe para el catálogo, así que no se
inventa uno (ADR-013, punto 2.5).
"""
from autorizacion.politicas import Politica
from identidad.models import Rol, UsuarioRol


def tiene_rol_comercial(usuario):
    return UsuarioRol.objects.filter(usuario=usuario, rol=Rol.COMERCIAL).exists()


class PoliticaOficioComercial(Politica):
    entidad = "oficio"

    def permite(self, usuario, oficio):
        return tiene_rol_comercial(usuario)


class PoliticaServicioComercial(Politica):
    entidad = "servicio"

    def permite(self, usuario, servicio):
        return tiene_rol_comercial(usuario)
