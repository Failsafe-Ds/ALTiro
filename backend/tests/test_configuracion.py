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
    for variable in ("DJANGO_SECRET_KEY_FILE", "ALTIRO_DB_PASSWORD_FILE", "ALTIRO_DOCUMENTOS_CLAVE_FILE"):
        ruta = os.environ.get(variable)
        if ruta and os.path.exists(ruta):
            valores.append(Path(ruta).read_text(encoding="utf-8").strip())
    return valores


@pytest.mark.parametrize("variable", ["DJANGO_SECRET_KEY_FILE", "ALTIRO_DB_PASSWORD_FILE", "ALTIRO_DOCUMENTOS_CLAVE_FILE"])
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


def test_csrf_se_verifica_antes_que_la_autorizacion():
    # ADR-006 E-1: un 403 con AlTiro-Rechazo: csrf no ejecutó la vista ni dejó
    # registro en acceso_denegado; exige CSRF antes que AutorizacionMiddleware.
    csrf = settings.MIDDLEWARE.index("django.middleware.csrf.CsrfViewMiddleware")
    autorizacion = settings.MIDDLEWARE.index("autorizacion.middleware.AutorizacionMiddleware")
    assert csrf < autorizacion


def test_sin_hsts_en_django():
    # ADR-008
    assert settings.SECURE_HSTS_SECONDS == 0


# --- Clave y directorio de documentos (ADR-015, RNF-24) ---


def _manage_check(entorno):
    return subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=BACKEND_DIR,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize(
    "contenido",
    ["corta", "zz" * 32, "ab" * 31, "ab" * 33, "ab" * 16],
    ids=["texto", "no_hexadecimal", "31_bytes", "33_bytes", "16_bytes"],
)
def test_la_aplicacion_no_arranca_si_la_clave_de_documentos_no_mide_32_bytes(contenido, tmp_path):
    archivo = tmp_path / "documentos_clave"
    archivo.write_text(contenido, encoding="utf-8")
    entorno = os.environ.copy()
    entorno["DJANGO_SETTINGS_MODULE"] = "altiro.settings"
    entorno["ALTIRO_DOCUMENTOS_CLAVE_FILE"] = str(archivo)

    resultado = _manage_check(entorno)

    assert resultado.returncode != 0
    salida = resultado.stdout + resultado.stderr
    assert "ALTIRO_DOCUMENTOS_CLAVE_FILE" in salida
    assert contenido not in salida
    for secreto in _secretos_actuales():
        assert secreto not in salida


def test_la_aplicacion_no_arranca_sin_el_directorio_de_documentos():
    entorno = os.environ.copy()
    entorno["DJANGO_SETTINGS_MODULE"] = "altiro.settings"
    entorno.pop("ALTIRO_DOCUMENTOS_DIR", None)

    resultado = _manage_check(entorno)

    assert resultado.returncode != 0
    assert "ALTIRO_DOCUMENTOS_DIR" in resultado.stdout + resultado.stderr


def test_la_clave_de_documentos_mide_32_bytes():
    assert isinstance(settings.ALTIRO_DOCUMENTOS_KEY, bytes)
    assert len(settings.ALTIRO_DOCUMENTOS_KEY) == 32


def test_leer_clave_aes256_acepta_64_caracteres_hexadecimales(tmp_path, monkeypatch):
    from altiro.configuracion import leer_clave_aes256

    archivo = tmp_path / "clave"
    archivo.write_text("0f" * 32 + "\n", encoding="utf-8")
    monkeypatch.setenv("PRUEBA_CLAVE_FILE", str(archivo))

    assert leer_clave_aes256("PRUEBA_CLAVE") == bytes([15]) * 32


def test_las_subidas_quedan_en_memoria_y_nunca_en_tmp():
    # ADR-015, D-3: dos archivos de 8 MB caben en memoria; no hay manejador a disco.
    assert settings.FILE_UPLOAD_MAX_MEMORY_SIZE >= 2 * settings.ALTIRO_DOCUMENTO_MAXIMO_BYTES
    assert settings.ALTIRO_DOCUMENTO_MAXIMO_BYTES == 8 * 1024 * 1024
    assert settings.FILE_UPLOAD_HANDLERS == ["django.core.files.uploadhandler.MemoryFileUploadHandler"]
    assert settings.DATA_UPLOAD_MAX_NUMBER_FILES == 2
