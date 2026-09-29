"""Fixtures comunes de las pruebas."""
import pytest
from django.conf import settings as ajustes_django

from catalogo import carga as carga_oficios
from catalogo.models import Oficio
from territorio.carga import cargar, leer_filas
from territorio.models import Comuna, Provincia, Region


def directorios_de_datos():
    """Nombres de los ajustes ``ALTIRO_*_DIR``: directorios con datos reales (volúmenes).

    Hoy solo ``ALTIRO_DOCUMENTOS_DIR`` (ADR-015). Uno nuevo con ese patrón (por
    ejemplo, el de las fotos de perfil) queda aislado sin cambiar este archivo.
    """
    return sorted(n for n in dir(ajustes_django) if n.startswith("ALTIRO_") and n.endswith("_DIR"))


@pytest.fixture(scope="session", autouse=True)
def directorios_de_datos_de_la_sesion(tmp_path_factory):
    """DEF-QA-008: ninguna prueba toca los volúmenes reales, aunque corra dentro de ``app``.

    Desde el inicio de la sesión, cada ``ALTIRO_*_DIR`` apunta a un directorio
    temporal propio. Es la base a la que vuelve el fixture ``settings`` de
    pytest-django al terminar cada prueba. El entorno no se cambia: la tarea de
    limpieza lo usa para reconocer el directorio real (``expediente.tareas``).
    """
    anteriores = {}
    for nombre in directorios_de_datos():
        anteriores[nombre] = getattr(ajustes_django, nombre)
        directorio = tmp_path_factory.mktemp(nombre.lower())
        directorio.chmod(0o700)
        setattr(ajustes_django, nombre, directorio)
    yield
    for nombre, valor in anteriores.items():
        setattr(ajustes_django, nombre, valor)


@pytest.fixture(autouse=True)
def directorios_de_datos_aislados(settings, tmp_path):
    """Además, cada prueba parte con sus propios directorios vacíos (DEF-QA-008).

    Las fixtures ``directorio_documentos`` de cada módulo lo vuelven a cambiar
    por otro temporal; nunca por el real.
    """
    for nombre in directorios_de_datos():
        directorio = tmp_path / f"aislado-{nombre.lower()}"
        directorio.mkdir(mode=0o700)
        setattr(settings, nombre, directorio)


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
