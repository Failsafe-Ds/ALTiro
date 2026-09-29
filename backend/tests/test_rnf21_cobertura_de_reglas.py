"""RNF-21: porcentaje de reglas críticas cubiertas por pruebas, por grupo (ADR-022, punto 8; D-18).

Lee de forma estática (``ast``) las marcas ``@pytest.mark.regla("ID", ...)``
de ``tests/test_*.py`` y calcula, por grupo de ``tests/reglas_rnf21.py``, la
proporción de reglas citadas. Solo exige el umbral en ``GRUPOS_ACTIVOS``.
Las pruebas marcadas corren en la misma suite: si una falla, la suite falla.
"""
import ast
from pathlib import Path

from tests import reglas_rnf21

DIRECTORIO = Path(__file__).resolve().parent


def reglas_marcadas(directorio=DIRECTORIO):
    citadas = set()
    for archivo in sorted(Path(directorio).glob("test_*.py")):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
        for nodo in ast.walk(arbol):
            if (
                isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "regla"
                and ast.unparse(nodo.func.value) == "pytest.mark"
            ):
                citadas.update(a.value for a in nodo.args if isinstance(a, ast.Constant) and isinstance(a.value, str))
    return citadas


def cobertura_por_grupo(citadas):
    return {
        grupo: len(set(reglas) & citadas) / len(reglas) for grupo, reglas in reglas_rnf21.REGLAS.items()
    }


def test_las_marcas_citan_reglas_del_catalogo():
    desconocidas = reglas_marcadas() - reglas_rnf21.todas()
    assert not desconocidas, f"Marcas de regla que no están en el catálogo: {sorted(desconocidas)}"


def test_rnf21_cobertura_de_reglas():
    cobertura = cobertura_por_grupo(reglas_marcadas())
    for grupo in reglas_rnf21.GRUPOS_ACTIVOS:
        assert cobertura[grupo] >= reglas_rnf21.UMBRAL, (grupo, cobertura[grupo])
    # Evidencia en la salida con -s: porcentaje por grupo, también de los no activos.
    print({grupo: f"{valor:.0%}" for grupo, valor in sorted(cobertura.items())})
