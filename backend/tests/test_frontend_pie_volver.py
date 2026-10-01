"""Pie de página con versión y enlace «← Volver» en las páginas estáticas.

Verificación estática (sin navegador): el HTML trae el pie aunque falle JavaScript,
la versión sale de un solo archivo (js/version.js), no hay scripts ni estilos en
línea (CSP estricta) y las páginas, salvo el inicio, traen un «Volver» con enlace
de respaldo real.

La carpeta frontend/ no está en la imagen de la aplicación. Para ejecutar:
  docker compose run --rm -v "$(pwd -W)/backend:/app" -v "$(pwd -W)/frontend:/frontend:ro" \
    --entrypoint pytest app -q tests/test_frontend_pie_volver.py
"""

import os
import re
from pathlib import Path

import pytest

CANDIDATOS = [Path(os.environ.get("FRONTEND_DIR", "/frontend")), Path(__file__).resolve().parents[2] / "frontend"]
FRONTEND = next((c for c in CANDIDATOS if (c / "index.html").exists()), None)

pytestmark = pytest.mark.skipif(FRONTEND is None, reason="frontend/ no está montado (ver docstring)")

# Páginas que ya traen su propio enlace a la página padre en el encabezado.
CON_ENLACE_PROPIO = {"conversacion.html", "evaluar.html", "curatoria-expediente.html"}


def paginas():
    if FRONTEND is None:
        return []
    return sorted((FRONTEND / "").glob("*.html")) + sorted((FRONTEND / "errores").glob("*.html"))


def ids(rutas):
    return [r.relative_to(FRONTEND).as_posix() for r in rutas]


@pytest.fixture(scope="module")
def version():
    texto = (FRONTEND / "js" / "version.js").read_text(encoding="utf-8")
    coincide = re.search(r'ALTIRO_VERSION\s*=\s*"(\d+\.\d+\.\d+)"', texto)
    assert coincide, "version.js debe definir ALTIRO_VERSION = \"X.Y.Z\""
    return coincide.group(1)


def test_version_tiene_formato(version):
    # La versión cambia en cada iteración; aquí solo se exige el formato X.Y.Z.
    assert version.count(".") == 2


@pytest.mark.parametrize("ruta", paginas(), ids=ids(paginas()) if FRONTEND else None)
def test_pie_y_scripts(ruta):
    html = ruta.read_text(encoding="utf-8")
    assert '<footer class="pie" role="contentinfo">' in html
    assert 'id="pie-version"' in html
    assert "© 2026 Equipo AlTiro" in html
    assert "no es un servicio comercial" in html
    assert re.search(r'src="/?js/version\.js" defer', html)
    assert re.search(r'src="/?js/pie\.js" defer', html)
    # Un solo lugar para la versión: no se repite escrita en el HTML.
    assert not re.search(r"v\d+\.\d+\.\d+", html)
    # CSP estricta: nada en línea.
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)
    assert "<style" not in html
    assert not re.search(r'\son\w+="', html)
    assert 'style="' not in html


@pytest.mark.parametrize("ruta", paginas(), ids=ids(paginas()) if FRONTEND else None)
def test_volver(ruta):
    html = ruta.read_text(encoding="utf-8")
    nombre = ruta.name
    if nombre == "index.html" or ruta.parent.name == "errores" or nombre in CON_ENLACE_PROPIO:
        assert "data-volver" not in html
        return
    enlace = re.search(r'<a [^>]*data-volver[^>]*href="([^"]+)"[^>]*>← Volver</a>', html)
    assert enlace, "falta el enlace «← Volver» con href de respaldo"
    assert (FRONTEND / enlace.group(1)).exists()
    assert re.search(r'src="js/volver\.js" defer', html)
