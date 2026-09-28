"""Fixtures comunes de las pruebas."""
import pytest

from territorio.carga import cargar, leer_filas
from territorio.models import Comuna, Provincia, Region


@pytest.fixture(autouse=True)
def catalogo_territorial(request):
    """Garantiza el catálogo CUT en las pruebas con base de datos (ADR-012).

    Lo carga la migración, pero las pruebas con ``transaction=True`` vacían
    todas las tablas al terminar; aquí se vuelve a cargar si falta.
    """
    if request.node.get_closest_marker("django_db") is None:
        return
    request.getfixturevalue("_django_db_helper")
    if not Comuna.objects.exists():
        cargar(Region, Provincia, Comuna, leer_filas())
