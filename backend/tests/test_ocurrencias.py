"""Ocurrencias concretas y horario de verano (ADR-020, Enmienda E-1; RF-16). Módulo puro.

Las transiciones de ``America/Santiago`` se buscan por programa con
``zoneinfo`` (no se escriben fechas a mano): así la prueba sigue valiendo si
cambia la regla del horario de verano.
"""
import datetime
from types import SimpleNamespace

import pytest
import time_machine

from perfil import ocurrencias
from perfil.ocurrencias import UTC, ZONA

HORA = datetime.timedelta(hours=1)


def transiciones(anio):
    """``[(instante_utc, offset_antes, offset_despues)]`` de ``anio``, buscadas hora a hora."""
    encontradas = []
    t = datetime.datetime(anio, 1, 1, tzinfo=UTC)
    fin = datetime.datetime(anio + 1, 1, 1, tzinfo=UTC)
    anterior = t.astimezone(ZONA).utcoffset()
    while t < fin:
        t += HORA
        actual = t.astimezone(ZONA).utcoffset()
        if actual != anterior:
            encontradas.append((t, anterior, actual))
        anterior = actual
    return encontradas


def _salto(adelante):
    anio = datetime.date.today().year
    for t, antes, despues in transiciones(anio) + transiciones(anio + 1):
        if (despues > antes) == adelante:
            return t, antes, despues
    pytest.skip("America/Santiago sin horario de verano en estos años")


def _minutos(reloj):
    return reloj.hour * 60 + reloj.minute


def _patron(dia, inicio, fin):
    return SimpleNamespace(ref="p", dia_semana=dia, inicio_min=inicio, fin_min=fin)


def test_se_encuentran_las_dos_transiciones_del_anio():
    tipos = {despues > antes for _, antes, despues in transiciones(2026)}
    assert tipos == {True, False}


@pytest.mark.regla("F-14")
def test_hora_inexistente_no_se_ofrece():
    t, antes, despues = _salto(adelante=True)
    # Hora de reloj que "desaparece": desde la hora vieja hasta la nueva.
    vieja = (t + antes).replace(tzinfo=None)
    fecha, minuto = vieja.date(), _minutos(vieja)
    assert ocurrencias.instante(fecha, minuto) is None
    # Un bloque que empieza en la hora que no existe no se ofrece ese día.
    assert ocurrencias.ocurrencia("p", fecha.isoweekday(), minuto, minuto + 60, fecha) is None
    # Un bloque que termina en ella tampoco (si es medianoche, es el 24:00 del día anterior).
    if minuto == 0:
        dia_antes = fecha - datetime.timedelta(days=1)
        assert ocurrencias.ocurrencia("p", dia_antes.isoweekday(), 1320, 1440, dia_antes) is None
    else:
        assert ocurrencias.ocurrencia("p", fecha.isoweekday(), minuto - 60, minuto, fecha) is None
    # La semana siguiente, el mismo patrón sí se ofrece.
    semana = fecha + datetime.timedelta(days=7)
    assert ocurrencias.ocurrencia("p", semana.isoweekday(), minuto, minuto + 60, semana) is not None


def test_hora_repetida_usa_la_primera():
    t, antes, despues = _salto(adelante=False)
    repetida = (t + despues).replace(tzinfo=None)  # la hora de reloj que se repite empieza aquí
    instante = ocurrencias.instante(repetida.date(), _minutos(repetida))
    assert instante is not None and instante.fold == 0
    assert instante.utcoffset() == antes
    # La primera de las dos es la de antes del cambio: ocurre (antes - despues) antes de la transición.
    assert instante.astimezone(UTC) == t - (antes - despues)


def test_fin_1440_es_las_cero_horas_del_dia_siguiente():
    fecha = datetime.date(2026, 10, 7)
    una = ocurrencias.ocurrencia("p", 3, 1320, 1440, fecha)
    assert una.fin_en == datetime.datetime(2026, 10, 8, 0, 0, tzinfo=ZONA)
    assert una.fin_en - una.inicio_en == 2 * HORA


def test_la_ocurrencia_solo_existe_el_dia_de_la_semana_del_patron():
    fecha = datetime.date(2026, 10, 7)  # miércoles
    assert ocurrencias.ocurrencia("p", 4, 480, 720, fecha) is None
    una = ocurrencias.ocurrencia("p", 3, 480, 720, fecha)
    assert (una.inicio_en.hour, una.fin_en.hour) == (8, 12)


def test_ocurrencias_de_catorce_dias_en_orden():
    patrones = [_patron(3, 480, 720), _patron(1, 600, 660)]
    lista = ocurrencias.ocurrencias(patrones, datetime.date(2026, 10, 7), ocurrencias.HORIZONTE_DIAS)
    assert [u.fecha.isoformat() for u in lista] == ["2026-10-07", "2026-10-12", "2026-10-14", "2026-10-19"]


@pytest.mark.regla("F-09")
def test_cuatro_horas_exactas_no_es_anticipacion_suficiente():
    una = ocurrencias.ocurrencia("p", 3, 720, 840, datetime.date(2026, 10, 7))
    with time_machine.travel(una.inicio_en - ocurrencias.ANTICIPACION_MINIMA, tick=False):
        ahora = datetime.datetime.now(UTC)
        assert not ocurrencias.empieza_con_anticipacion(una, ahora)
    with time_machine.travel(una.inicio_en - ocurrencias.ANTICIPACION_MINIMA - datetime.timedelta(minutes=1), tick=False):
        assert ocurrencias.empieza_con_anticipacion(una, datetime.datetime.now(UTC))


@pytest.mark.regla("F-09", "F-14")
def test_las_cuatro_horas_se_miden_en_tiempo_real_al_cambiar_la_hora():
    t, antes, despues = _salto(adelante=True)
    nueva = (t + despues).replace(tzinfo=None)  # primera hora de reloj después del salto
    fecha = nueva.date()
    inicio = _minutos(nueva) + 180  # tres horas de reloj después del salto
    una = ocurrencias.ocurrencia("p", fecha.isoweekday(), inicio, inicio + 60, fecha)
    # Media hora antes del salto: por reloj faltan 4 h 30 min, pero en tiempo real solo 3 h 30 min.
    with time_machine.travel(t - datetime.timedelta(minutes=30), tick=False):
        ahora = datetime.datetime.now(UTC)
        por_reloj = datetime.datetime.combine(fecha, datetime.time(inicio // 60)) - (
            (t - datetime.timedelta(minutes=30)) + antes
        ).replace(tzinfo=None)
        assert por_reloj > ocurrencias.ANTICIPACION_MINIMA
        assert una.inicio_en - ahora < ocurrencias.ANTICIPACION_MINIMA
        assert not ocurrencias.ofrecible(una, ahora, ())


@pytest.mark.regla("F-10")
def test_un_rango_ocupado_que_se_cruza_la_quita_y_uno_contiguo_no():
    una = ocurrencias.ocurrencia("p", 3, 720, 840, datetime.date(2026, 10, 7))
    ahora = una.inicio_en - datetime.timedelta(days=1)
    assert ocurrencias.ofrecible(una, ahora, [])
    assert not ocurrencias.ofrecible(una, ahora, [(una.inicio_en + HORA, una.fin_en + HORA)])
    assert ocurrencias.ofrecible(una, ahora, [(una.fin_en, una.fin_en + HORA)])
    assert ocurrencias.ofrecible(una, ahora, [(una.inicio_en - HORA, una.inicio_en)])
