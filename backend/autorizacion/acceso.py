"""Punto único de acceso a un recurso por referencia (RNF-07, CA-25.1, CA-25.3; ADR-011, «Decisión», punto 5).

``obtener_autorizado`` busca por ``ref`` **sin filtrar por dueño** y después
aplica la política: así distingue un recurso inexistente (404 sin registro)
de uno ajeno (el mismo 404, pero registrado en ``acceso_denegado``).

Conflicto de interés (ADR-011, E-2): ``Politica.conflicto`` se evalúa **antes**
que ``permite``. Un rol administrativo no exime del conflicto (ADR-013, punto 2.5).
"""
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from autorizacion.excepciones import AccesoDenegado, ConflictoDeInteres, RecursoNoEncontrado


def obtener_autorizado(consulta_base, ref, usuario, politica):
    """Devuelve el objeto de ``consulta_base`` con ese ``ref`` si la política lo permite.

    - No existe (o la referencia no es válida): ``RecursoNoEncontrado``.
    - Existe y la política declara conflicto de interés: ``ConflictoDeInteres``.
    - Existe y la política lo deniega: ``AccesoDenegado``.
    """
    try:
        objeto = consulta_base.get(ref=ref)
    except (ObjectDoesNotExist, ValidationError, ValueError):
        raise RecursoNoEncontrado() from None
    if politica.conflicto(usuario, objeto):
        raise ConflictoDeInteres(politica.entidad, ref)
    if not politica.permite(usuario, objeto):
        raise AccesoDenegado(politica.entidad, ref)
    return objeto
