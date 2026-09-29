"""Pruebas del QA de cierre del Sprint 2 (docs/testing/cierre-sprint-2.md).

DEF-QA-008 (corregido): la suite de pruebas usaba el directorio de documentos
configurado por el entorno (el volumen real ``documentos`` cuando se corre con
``docker compose exec -T app pytest``) en las pruebas que no pedían la fixture
``directorio_documentos``. La prueba
``test_avisos_planificador.py::test_un_error_de_base_de_datos_en_una_tarea_se_registra_sin_datos``
corría ``limpiar_archivos_huerfanos`` sobre ese directorio con la base de
pruebas, donde ningún documento referencia los archivos reales, y los borraba.

Corrección:
- ``tests/conftest.py`` apunta cada ``ALTIRO_*_DIR`` a un directorio temporal
  en toda la sesión y en cada prueba (fixtures autouse);
- ``expediente.tareas.limpiar_archivos_huerfanos`` se niega a operar si el
  directorio es el del entorno y la base en uso no es la del entorno.
"""
import datetime
import os
import uuid
from pathlib import Path

import pytest
from django.conf import settings
from django.db import connection

from expediente import tareas
from expediente.management.commands import planificador
from tests.conftest import directorios_de_datos

AHORA = datetime.datetime(2026, 10, 14, 15, 0, tzinfo=datetime.timezone.utc)


def _dentro_de(ruta, base):
    ruta, base = Path(ruta).resolve(), Path(base).resolve()
    return ruta == base or base in ruta.parents


def test_las_pruebas_nunca_usan_el_directorio_real_de_documentos(tmp_path_factory):
    # settings exige ALTIRO_DOCUMENTOS_DIR en el entorno: siempre hay un directorio real que proteger.
    real = Path(os.environ["ALTIRO_DOCUMENTOS_DIR"]).resolve()
    assert Path(settings.ALTIRO_DOCUMENTOS_DIR).resolve() != real
    assert _dentro_de(settings.ALTIRO_DOCUMENTOS_DIR, tmp_path_factory.getbasetemp())


def test_todo_directorio_de_datos_queda_en_el_temporal_de_pytest(tmp_path_factory):
    nombres = directorios_de_datos()
    assert "ALTIRO_DOCUMENTOS_DIR" in nombres
    for nombre in nombres:
        assert _dentro_de(getattr(settings, nombre), tmp_path_factory.getbasetemp()), nombre
        real = os.environ.get(nombre)
        if real:
            assert Path(getattr(settings, nombre)).resolve() != Path(real).resolve(), nombre


def _huerfano_antiguo(directorio):
    ruta = directorio / str(uuid.uuid4())
    ruta.write_bytes(b"cifrado-ficticio")
    marca = AHORA.timestamp() - 90 * 86400
    os.utime(ruta, (marca, marca))
    return ruta


@pytest.fixture
def directorio_real_simulado(settings, tmp_path, monkeypatch):
    """Simula que el directorio de las pruebas es el "real" del entorno (sin tocar el volumen)."""
    directorio = tmp_path / "real"
    directorio.mkdir(mode=0o700)
    monkeypatch.setenv("ALTIRO_DOCUMENTOS_DIR", str(directorio))
    settings.ALTIRO_DOCUMENTOS_DIR = directorio
    return directorio


@pytest.mark.django_db
def test_la_limpieza_se_niega_si_el_directorio_real_se_usa_con_otra_base(directorio_real_simulado):
    # La base de pruebas (test_*) no es la del entorno (ALTIRO_DB_NAME).
    assert connection.settings_dict["NAME"] != os.environ["ALTIRO_DB_NAME"]
    archivo = _huerfano_antiguo(directorio_real_simulado)

    with pytest.raises(tareas.DirectorioDeOtraBase) as error:
        tareas.limpiar_archivos_huerfanos(AHORA)

    assert archivo.exists()
    # El mensaje no revela rutas ni nombres de base.
    assert str(directorio_real_simulado) not in str(error.value)
    assert connection.settings_dict["NAME"] not in str(error.value)


@pytest.mark.django_db
def test_el_planificador_registra_la_negativa_como_tarea_fallida(directorio_real_simulado):
    archivo = _huerfano_antiguo(directorio_real_simulado)

    conteos, fallidas = planificador.correr_tareas(AHORA)

    assert fallidas == ["archivos_huerfanos_borrados"]
    assert "archivos_huerfanos_borrados" not in conteos
    assert archivo.exists()


@pytest.mark.django_db
def test_la_limpieza_opera_si_la_base_en_uso_es_la_del_entorno(directorio_real_simulado, monkeypatch):
    """El par del entorno (directorio real y su base) es el caso del servicio planificador."""
    monkeypatch.setenv("ALTIRO_DB_NAME", connection.settings_dict["NAME"])
    archivo = _huerfano_antiguo(directorio_real_simulado)

    assert tareas.limpiar_archivos_huerfanos(AHORA) == 1
    assert not archivo.exists()


@pytest.mark.django_db
def test_la_limpieza_opera_sobre_un_directorio_que_no_es_el_del_entorno(settings, tmp_path):
    directorio = tmp_path / "otro"
    directorio.mkdir(mode=0o700)
    settings.ALTIRO_DOCUMENTOS_DIR = directorio
    archivo = _huerfano_antiguo(directorio)

    assert tareas.limpiar_archivos_huerfanos(AHORA) == 1
    assert not archivo.exists()
