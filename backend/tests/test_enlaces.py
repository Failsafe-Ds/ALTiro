"""Enlaces firmados (RNF-06, base; propuesta del S1, §5, punto 6). Hora de Python con time_machine (ADR-014)."""
import datetime
import uuid

import pytest
import time_machine
from django.core.signing import TimestampSigner

from autorizacion.enlaces import VIGENCIA_SEGUNDOS, EnlaceInvalido, firmar, verificar

INICIO = datetime.datetime(2026, 9, 28, 12, 0, 0, tzinfo=datetime.timezone.utc)
REF = uuid.UUID("00000000-0000-4000-8000-000000000001")


def test_vigencia_de_diez_minutos():
    assert VIGENCIA_SEGUNDOS == 600


def test_aceptado_a_los_600_segundos_y_rechazado_a_los_601():
    with time_machine.travel(INICIO, tick=False) as viaje:
        token = firmar(REF, 7)
        viaje.shift(600)
        assert verificar(token, 7) == str(REF)
        viaje.shift(1)
        with pytest.raises(EnlaceInvalido):
            verificar(token, 7)


def test_enlace_alterado_es_rechazado():
    with time_machine.travel(INICIO, tick=False):
        token = firmar(REF, 7)
        medio = len(token) // 2
        alterado = token[:medio] + ("A" if token[medio] != "A" else "B") + token[medio + 1:]
        with pytest.raises(EnlaceInvalido):
            verificar(alterado, 7)


def test_enlace_de_otro_usuario_es_rechazado():
    with time_machine.travel(INICIO, tick=False):
        token = firmar(REF, 7)
        with pytest.raises(EnlaceInvalido):
            verificar(token, 8)


@pytest.mark.parametrize("token", ["", "basura", None, 123])
def test_token_mal_formado_es_rechazado(token):
    with pytest.raises(EnlaceInvalido):
        verificar(token, 7)


def test_firma_con_otra_sal_es_rechazada():
    token = TimestampSigner().sign_object({"d": str(REF), "u": 7})

    with pytest.raises(EnlaceInvalido):
        verificar(token, 7)


# --- Cara del archivo (incremento 3 del S2) ---


def test_enlace_con_cara_se_acepta_solo_para_esa_cara():
    with time_machine.travel(INICIO, tick=False):
        token = firmar(REF, 7, "anverso")
        assert verificar(token, 7, "anverso") == str(REF)
        for otra in ("reverso", None):
            with pytest.raises(EnlaceInvalido):
                verificar(token, 7, otra)


def test_enlace_sin_cara_no_sirve_para_una_cara():
    with time_machine.travel(INICIO, tick=False):
        token = firmar(REF, 7)
        with pytest.raises(EnlaceInvalido):
            verificar(token, 7, "anverso")


def test_enlace_con_cara_caduca_igual_a_los_600_segundos():
    with time_machine.travel(INICIO, tick=False) as viaje:
        token = firmar(REF, 7, "reverso")
        viaje.shift(600)
        assert verificar(token, 7, "reverso") == str(REF)
        viaje.shift(1)
        with pytest.raises(EnlaceInvalido):
            verificar(token, 7, "reverso")
