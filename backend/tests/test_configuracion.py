"""Pruebas de configuración y secretos (RNF-24, ADR-009) y ajustes base (ADR-001, ADR-006, ADR-008)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from altiro.configuracion import leer_booleano, leer_lista, leer_secreto, leer_variable

BACKEND_DIR = Path(__file__).resolve().parent.parent


# --- leer_secreto ---

def test_leer_secreto_desde_archivo(tmp_path, monkeypatch):
    archivo = tmp_path / "secreto"
    archivo.write_text("valor-de-prueba\n", encoding="utf-8")
    monkeypatch.setenv("PRUEBA_SECRETO_FILE", str(archivo))

    assert leer_secreto("PRUEBA_SECRETO") == "valor-de-prueba"


def test_leer_secreto_falla_si_falta_la_variable_file(monkeypatch):
    monkeypatch.delenv("PRUEBA_SECRETO_FILE", raising=False)

    with pytest.raises(ImproperlyConfigured, match="PRUEBA_SECRETO_FILE"):
        leer_secreto("PRUEBA_SECRETO")


def test_leer_secreto_no_acepta_el_valor_directo_en_el_entorno(monkeypatch):
    monkeypatch.delenv("PRUEBA_SECRETO_FILE", raising=False)
    monkeypatch.setenv("PRUEBA_SECRETO", "valor-en-claro")

    with pytest.raises(ImproperlyConfigured):
        leer_secreto("PRUEBA_SECRETO")


def test_leer_secreto_falla_si_el_archivo_no_existe(tmp_path, monkeypatch):
    monkeypatch.setenv("PRUEBA_SECRETO_FILE", str(tmp_path / "no-existe"))

    with pytest.raises(ImproperlyConfigured, match="No se pudo leer"):
        leer_secreto("PRUEBA_SECRETO")


def test_leer_secreto_falla_si_el_archivo_esta_vacio(tmp_path, monkeypatch):
    archivo = tmp_path / "vacio"
    archivo.write_text("  \n", encoding="utf-8")
    monkeypatch.setenv("PRUEBA_SECRETO_FILE", str(archivo))

    with pytest.raises(ImproperlyConfigured, match="vacío"):
        leer_secreto("PRUEBA_SECRETO")


# --- otras variables ---

def test_leer_variable_falla_si_falta(monkeypatch):
    monkeypatch.delenv("PRUEBA_VARIABLE", raising=False)

    with pytest.raises(ImproperlyConfigured, match="PRUEBA_VARIABLE"):
        leer_variable("PRUEBA_VARIABLE")


def test_leer_lista_separa_por_comas_e_ignora_vacios(monkeypatch):
    monkeypatch.setenv("PRUEBA_LISTA", " localhost, ,127.0.0.1 ")

    assert leer_lista("PRUEBA_LISTA") == ["localhost", "127.0.0.1"]


def test_leer_lista_falla_si_no_hay_valores(monkeypatch):
    monkeypatch.setenv("PRUEBA_LISTA", " , ")

    with pytest.raises(ImproperlyConfigured):
        leer_lista("PRUEBA_LISTA")


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("true", True), ("TRUE", True), ("1", True), ("false", False), ("0", False), ("", False)],
)
def test_leer_booleano(monkeypatch, valor, esperado):
    monkeypatch.setenv("PRUEBA_BOOLEANO", valor)

    assert leer_booleano("PRUEBA_BOOLEANO", por_defecto=False) is esperado


def test_leer_booleano_rechaza_valores_ambiguos(monkeypatch):
    monkeypatch.setenv("PRUEBA_BOOLEANO", "quizas")

    with pytest.raises(ImproperlyConfigured):
        leer_booleano("PRUEBA_BOOLEANO", por_defecto=False)


# --- la aplicación no arranca si falta un secreto (ADR-009) ---

def _secretos_actuales():
    valores = []
    for variable in ("DJANGO_SECRET_KEY_FILE", "ALTIRO_DB_PASSWORD_FILE"):
        ruta = os.environ.get(variable)
        if ruta and os.path.exists(ruta):
            valores.append(Path(ruta).read_text(encoding="utf-8").strip())
    return valores


@pytest.mark.parametrize("variable", ["DJANGO_SECRET_KEY_FILE", "ALTIRO_DB_PASSWORD_FILE"])
@pytest.mark.parametrize("modo", ["ausente", "archivo_inexistente"])
def test_la_aplicacion_no_arranca_si_falta_un_secreto(variable, modo, tmp_path):
    entorno = os.environ.copy()
    entorno["DJANGO_SETTINGS_MODULE"] = "altiro.settings"
    if modo == "ausente":
        entorno.pop(variable, None)
    else:
        entorno[variable] = str(tmp_path / "no-existe")

    resultado = subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=BACKEND_DIR,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert resultado.returncode != 0
    salida = resultado.stdout + resultado.stderr
    assert "ImproperlyConfigured" in salida
    assert variable in salida
    for secreto in _secretos_actuales():
        assert secreto not in salida


# --- ajustes base ---

def test_panel_de_administracion_no_instalado():
    # ADR-001
    assert "django.contrib.admin" not in settings.INSTALLED_APPS


def test_csrf_activo_y_cookies_seguras():
    # ADR-006, ADR-008
    assert "django.middleware.csrf.CsrfViewMiddleware" in settings.MIDDLEWARE
    assert settings.CSRF_COOKIE_SECURE is True
    assert settings.SESSION_COOKIE_SECURE is True


def test_sin_hsts_en_django():
    # ADR-008
    assert settings.SECURE_HSTS_SECONDS == 0
