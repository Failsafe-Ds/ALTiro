"""Fixtures comunes de las pruebas."""
import pytest

from catalogo import carga as carga_oficios
from catalogo.models import Oficio
from territorio.carga import cargar, leer_filas
from territorio.models import Comuna, Provincia, Region


@pytest.fixture(autouse=True)
def catalogo_territorial(request):
    """Garantiza los catálogos de solo lectura en las pruebas con base de datos.

    El catálogo CUT (ADR-012) y el de oficios (ADR-017) los cargan migraciones,
    pero las pruebas con ``transaction=True`` vacían todas las tablas al
    terminar; aquí se vuelven a cargar si faltan.
    """
    if request.node.get_closest_marker("django_db") is None:
        return
    request.getfixturevalue("_django_db_helper")
    if not Comuna.objects.exists():
        cargar(Region, Provincia, Comuna, leer_filas())
    if not Oficio.objects.exists():
        carga_oficios.cargar(Oficio, carga_oficios.leer_filas())
