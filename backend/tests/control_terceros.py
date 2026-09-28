"""Prueba de control de RNF-07 (propuesta del S1, §5, punto 7; ADR-011, «Decisión», punto 1).

Toda ruta con identificador (``<…>``) debe:
1. tener al menos una prueba de acceso de terceros marcada con
   ``@pytest.mark.terceros("nombre_de_ruta")`` en ``tests/test_*.py``;
2. usar el convertidor ``uuid``.

Excepción explícita: los códigos CUT públicos del catálogo territorial.
Las marcas se leen de forma estática (``ast``), sin importar los módulos.
"""
import ast
import re
import uuid
from pathlib import Path

from django.urls import URLPattern, URLResolver, get_resolver

DIRECTORIO_PRUEBAS = Path(__file__).resolve().parent

# Rutas con identificador exentas, con su motivo. Agregar una exige cambiar este archivo.
RUTAS_EXENTAS = {
    # Pública; el identificador es un código CUT, no un recurso de una persona (ADR-011, punto 1).
    "api/territorio/regiones/<int:codigo>/comunas",
}

_PARAMETRO = re.compile(r"<(?:(?P<convertidor>[^>:]+):)?(?P<nombre>\w+)>")
_EJEMPLOS = {"uuid": str(uuid.UUID(int=1)), "int": "1", "slug": "x", "str": "x", "path": "x"}


class Ruta:
    def __init__(self, patron, nombre, vista):
        self.patron = patron
        self.nombre = nombre
        self.vista = vista

    @property
    def publica(self):
        return getattr(self.vista, "publica", False)

    @property
    def convertidores(self):
        return [m.group("convertidor") or "str" for m in _PARAMETRO.finditer(self.patron)]

    def __repr__(self):
        return f"Ruta({self.patron!r}, {self.nombre!r})"


def rutas(patrones=None, prefijo=""):
    """Todas las rutas finales, entrando recursivamente en los ``include``."""
    if patrones is None:
        patrones = get_resolver().url_patterns
    resultado = []
    for patron in patrones:
        texto = prefijo + str(patron.pattern)
        if isinstance(patron, URLResolver):
            resultado.extend(rutas(patron.url_patterns, texto))
        elif isinstance(patron, URLPattern):
            resultado.append(Ruta(texto, patron.name, patron.callback))
    return resultado


def url_de_ejemplo(patron):
    """URL concreta para un patrón, con un valor válido para cada convertidor."""
    return "/" + _PARAMETRO.sub(lambda m: _EJEMPLOS[m.group("convertidor") or "str"], patron)


def marcas_terceros(directorio=DIRECTORIO_PRUEBAS):
    """Nombres de ruta citados en ``@pytest.mark.terceros("…")`` de ``test_*.py``."""
    nombres = set()
    for archivo in sorted(Path(directorio).glob("test_*.py")):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for decorador in nodo.decorator_list:
                if (
                    isinstance(decorador, ast.Call)
                    and isinstance(decorador.func, ast.Attribute)
                    and decorador.func.attr == "terceros"
                    and ast.unparse(decorador.func.value) == "pytest.mark"
                ):
                    nombres.update(
                        arg.value for arg in decorador.args
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                    )
    return nombres


def problemas(lista_de_rutas, marcas, exentas=RUTAS_EXENTAS):
    """Lista de incumplimientos; vacía si todas las rutas con identificador cumplen."""
    encontrados = []
    for ruta in lista_de_rutas:
        if not ruta.convertidores or ruta.patron in exentas:
            continue
        if ruta.nombre is None or ruta.nombre not in marcas:
            encontrados.append(f"{ruta.patron}: sin prueba marcada con pytest.mark.terceros")
        if any(c != "uuid" for c in ruta.convertidores):
            encontrados.append(f"{ruta.patron}: el identificador debe usar el convertidor uuid")
    return encontrados
