"""Purgas operativas del planificador (ADR-030, B5 y B9).

- B5: las sesiones expiradas de ``django_session`` se borran en cada corrida;
  las vigentes se conservan.
- B9: los correos del buzón local (ADR-027, punto 4) se borran pasado el
  vencimiento del enlace de recuperación más el margen.
- El registro de la corrida lleva solo conteos (RNF-22, en parte).

``ALTIRO_BUZON_DIR`` ya apunta a un directorio temporal en cada prueba
(``conftest.directorios_de_datos_aislados``). Datos ficticios.
"""
import datetime
import os

import pytest
from django.contrib.sessions.models import Session

from expediente.management.commands import planificador

AHORA = datetime.datetime(2026, 10, 1, 12, 0, tzinfo=datetime.timezone.utc)


def _sesion(clave, expira):
    Session.objects.create(session_key=clave, session_data="e30:ficticio", expire_date=expira)


@pytest.mark.django_db
def test_b5_purga_solo_las_sesiones_expiradas():
    _sesion("vencida1", AHORA - datetime.timedelta(seconds=1))
    _sesion("vencida2", AHORA - datetime.timedelta(days=40))
    _sesion("vigente1", AHORA + datetime.timedelta(minutes=10))

    assert planificador.purgar_sesiones_expiradas(AHORA) == 2
    assert list(Session.objects.values_list("session_key", flat=True)) == ["vigente1"]


@pytest.mark.django_db
def test_b5_la_purga_de_sesiones_es_idempotente():
    _sesion("vencida1", AHORA - datetime.timedelta(minutes=1))
    assert planificador.purgar_sesiones_expiradas(AHORA) == 1
    assert planificador.purgar_sesiones_expiradas(AHORA) == 0


def _correo(directorio, nombre, antiguedad):
    ruta = directorio / nombre
    ruta.write_text("Para: ficticio@example.com\n", encoding="utf-8")
    marca = (AHORA - antiguedad).timestamp()
    os.utime(ruta, (marca, marca))
    return ruta


def test_b9_la_antiguedad_maxima_es_el_vencimiento_del_enlace_mas_el_margen(settings):
    settings.ALTIRO_RECUPERACION_MINUTOS = 30
    settings.ALTIRO_BUZON_MARGEN_HORAS = 24
    assert planificador.antiguedad_maxima_buzon() == datetime.timedelta(hours=24, minutes=30)


def test_b9_purga_solo_los_correos_mas_viejos_que_el_limite(settings):
    settings.ALTIRO_RECUPERACION_MINUTOS = 30
    settings.ALTIRO_BUZON_MARGEN_HORAS = 24
    buzon = settings.ALTIRO_BUZON_DIR
    viejo = _correo(buzon, "20260929-100000-1.log", datetime.timedelta(hours=24, minutes=31))
    reciente = _correo(buzon, "20260930-120000-2.log", datetime.timedelta(hours=24, minutes=29))
    otro = _correo(buzon, "nota.txt", datetime.timedelta(days=10))
    (buzon / "carpeta.log").mkdir()

    assert planificador.purgar_buzon(AHORA) == 1
    assert not viejo.exists()
    assert reciente.exists() and otro.exists() and (buzon / "carpeta.log").is_dir()
    assert planificador.purgar_buzon(AHORA) == 0


def test_b9_sin_directorio_de_buzon_no_falla(settings, tmp_path):
    settings.ALTIRO_BUZON_DIR = tmp_path / "no-existe"
    assert planificador.purgar_buzon(AHORA) == 0


def test_b9_un_correo_reciente_de_recuperacion_se_conserva(settings):
    """Un enlace todavía vigente nunca se borra, aunque el margen sea mínimo."""
    settings.ALTIRO_RECUPERACION_MINUTOS = 30
    settings.ALTIRO_BUZON_MARGEN_HORAS = 1
    correo = _correo(settings.ALTIRO_BUZON_DIR, "20261001-115000-3.log", datetime.timedelta(minutes=29))
    assert planificador.purgar_buzon(AHORA) == 0
    assert correo.exists()


@pytest.mark.django_db
def test_la_corrida_registra_los_conteos_de_las_purgas_sin_datos(settings, caplog):
    _sesion("clave-secreta-ficticia", AHORA - datetime.timedelta(minutes=5))
    _correo(settings.ALTIRO_BUZON_DIR, "20260920-100000-9.log", datetime.timedelta(days=11))

    with caplog.at_level("INFO", logger="expediente.planificador"):
        conteos, fallidas = planificador.correr_tareas(AHORA)

    assert fallidas == []
    assert conteos["sesiones_expiradas_purgadas"] == 1
    assert conteos["correos_buzon_purgados"] == 1
    texto = caplog.text
    assert "sesiones_expiradas_purgadas=1" in texto and "correos_buzon_purgados=1" in texto
    for ausente in ("clave-secreta-ficticia", "ficticio@example.com", "20260920-100000-9.log"):
        assert ausente not in texto
