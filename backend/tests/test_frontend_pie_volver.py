"""Pie de página con versión y encabezado sin botones «Volver» en las páginas estáticas.

Verificación estática (sin navegador): el HTML trae el pie aunque falle JavaScript,
la versión sale de un solo archivo (js/version.js), no hay scripts ni estilos en
línea (CSP estricta) y ninguna página trae un botón o enlace «Volver»: la marca
AlTiro del encabezado cumple esa función (ADR-002 E-3, punto 6). El botón Atrás
del navegador sigue funcionando (pasos con history.pushState).

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

# «← Paso anterior» es un control del formulario por pasos, no un «Volver» de
# navegación: sin él, un formulario restaurado en el paso 2 tras recargar no
# tendría cómo llegar al paso 1 (no hay historial previo, RNF-20). Se permite
# exactamente ese texto y solo en estas páginas (ADR-002 E-3.1, PROVISIONAL).
PASO_ANTERIOR = "← Paso anterior"
FORMULARIOS_POR_PASOS = {
    "registro-cliente.html",
    "postulacion-maestro.html",
    "mi-postulacion.html",
    "pedir-trabajo.html",
    "mis-servicios.html",
}


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
def test_sin_volver(ruta):
    html = ruta.read_text(encoding="utf-8")
    assert "data-volver" not in html
    assert "volver.js" not in html
    # Ningún botón ni enlace cuyo texto sea «Volver» (con o sin flecha, o «Volver a…»).
    # "Volver a cargar" (recargar datos) y "No, volver" (cancelar una confirmación) no navegan.
    textos = re.findall(r"<(?:a|button)\b[^>]*>\s*([^<]*)<", html)
    navegar = [t.strip() for t in textos if re.match(r"(←\s*)?Volver\b(?! a cargar)", t.strip())]
    assert not navegar, f"botones «Volver» que deben eliminarse: {navegar}"
    # «Paso anterior» solo en los formularios por pasos y siempre con el mismo texto.
    pasos = [t.strip() for t in textos if re.search(r"[Pp]aso anterior", t)]
    if ruta.name in FORMULARIOS_POR_PASOS:
        assert pasos and all(t == PASO_ANTERIOR for t in pasos), f"texto distinto de «{PASO_ANTERIOR}»: {pasos}"
    else:
        assert not pasos, f"«Paso anterior» fuera de un formulario por pasos: {pasos}"
    # Encabezado: solo la marca AlTiro (el menú lo agrega menu.js con sesión).
    encabezado = re.search(r"<header class=\"encabezado\">(.*?)</header>", html, re.S)
    assert encabezado, "falta el encabezado"
    enlaces = re.findall(r"<a\b[^>]*>", encabezado.group(1))
    assert len(enlaces) == 1 and 'class="marca"' in enlaces[0]


def test_sin_script_volver():
    assert not (FRONTEND / "js" / "volver.js").exists()
