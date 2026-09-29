"""Vigencia y días restantes (RF-08, CA-17.1; ADR-016, punto 3; incremento 5 del S2).

Reglas en ``expediente.vigencia``:
- "hoy" en ``America/Santiago``, aunque ``TIME_ZONE`` sea UTC;
- vigente si no vence o si ``hoy < fecha_vencimiento``;
- ``dias_restantes``: ``None`` si no vence; el día del vencimiento vale 0 y el
  documento ya no está vigente.

Sin base de datos: funciones puras. La hora sale de Python (ADR-014).
"""
import datetime

import pytest
import time_machine
from django.utils import timezone

from expediente import vigencia

UTC = datetime.timezone.utc
HOY = datetime.date(2026, 10, 14)


def _en(dias):
    return HOY + datetime.timedelta(days=dias)


@pytest.mark.parametrize(
    ("vencimiento", "dias", "vigente"),
    [
        (None, None, True),  # sin vencimiento (RF-04, CA-11.2)
        (_en(-1), -1, False),  # venció ayer
        (_en(0), 0, False),  # vence hoy: ya no está vigente
        (_en(1), 1, True),  # vence mañana
        (_en(30), 30, True),  # umbral de RF-35
        (_en(31), 31, True),
    ],
)
def test_dias_restantes_y_vigencia_en_los_bordes(vencimiento, dias, vigente):
    assert vigencia.dias_restantes(vencimiento, HOY) == dias
    assert vigencia.vigente(vencimiento, HOY) is vigente


@pytest.mark.parametrize("dias", range(-3, 40))
def test_vigente_si_y_solo_si_quedan_dias(dias):
    assert vigencia.vigente(_en(dias), HOY) is (vigencia.dias_restantes(_en(dias), HOY) > 0)


@pytest.mark.parametrize(
    ("ahora_utc", "hoy_esperado"),
    [
        # Horario de verano (UTC-3): 02:30 UTC del 15 son las 23:30 del 14 en Santiago.
        (datetime.datetime(2026, 10, 15, 2, 30, tzinfo=UTC), datetime.date(2026, 10, 14)),
        (datetime.datetime(2026, 10, 15, 3, 30, tzinfo=UTC), datetime.date(2026, 10, 15)),
        # Horario de invierno (UTC-4): 03:30 UTC del 15 son las 23:30 del 14.
        (datetime.datetime(2026, 7, 15, 3, 30, tzinfo=UTC), datetime.date(2026, 7, 14)),
        (datetime.datetime(2026, 7, 15, 4, 30, tzinfo=UTC), datetime.date(2026, 7, 15)),
        # Inicio del horario de verano 2026 (domingo 6 de septiembre, 04:00 UTC).
        (datetime.datetime(2026, 9, 6, 3, 59, tzinfo=UTC), datetime.date(2026, 9, 5)),
        (datetime.datetime(2026, 9, 6, 4, 0, tzinfo=UTC), datetime.date(2026, 9, 6)),
        # Fin del horario de verano 2026 (domingo 5 de abril, 03:00 UTC): la hora
        # 23:00-24:00 del sábado se repite y sigue siendo el sábado 4.
        (datetime.datetime(2026, 4, 5, 2, 30, tzinfo=UTC), datetime.date(2026, 4, 4)),
        (datetime.datetime(2026, 4, 5, 3, 30, tzinfo=UTC), datetime.date(2026, 4, 4)),
        (datetime.datetime(2026, 4, 5, 4, 0, tzinfo=UTC), datetime.date(2026, 4, 5)),
    ],
)
def test_hoy_es_la_fecha_de_santiago_y_no_la_de_utc(ahora_utc, hoy_esperado):
    assert vigencia.hoy_negocio(ahora_utc) == hoy_esperado
    with time_machine.travel(ahora_utc, tick=False):
        assert vigencia.hoy_negocio() == hoy_esperado


def test_cerca_de_medianoche_utc_el_documento_sigue_vigente_en_santiago():
    # En UTC ya es el día del vencimiento; en Santiago todavía queda un día.
    ahora = datetime.datetime(2026, 10, 15, 2, 30, tzinfo=UTC)
    vencimiento = datetime.date(2026, 10, 15)
    with time_machine.travel(ahora, tick=False):
        assert timezone.now().date() == vencimiento
        hoy = vigencia.hoy_negocio()
    assert vigencia.dias_restantes(vencimiento, hoy) == 1
    assert vigencia.vigente(vencimiento, hoy)


def test_el_cambio_de_hora_no_altera_los_dias_restantes():
    # Del sábado 5 al lunes 7 de septiembre de 2026 hay un día de 23 horas: siguen siendo 2 días.
    hoy = vigencia.hoy_negocio(datetime.datetime(2026, 9, 5, 15, 0, tzinfo=UTC))
    assert vigencia.dias_restantes(datetime.date(2026, 9, 7), hoy) == 2
