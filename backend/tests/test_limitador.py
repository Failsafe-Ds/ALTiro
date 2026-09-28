"""Limitación de intentos fallidos (RNF-10, M-07, M-08; ADR-007 «Decisión»).

Identificadores PI-230 a PI-238 del plan de pruebas. El origen se envía en
``X-Real-IP`` y en ``REMOTE_ADDR``: la prueba no depende de si el entorno
confía en la cabecera del proxy.
"""
import datetime

import pytest
import time_machine
from django.test import Client, RequestFactory, override_settings
from django.utils import timezone

from identidad import limitador
from identidad.models import IntentoAutenticacion, Usuario
from tests.ayudas import CONTRASENA, crear_cliente, iniciar_sesion

CORREO = "ana.prueba@example.com"
MALA = "contraseña equivocada"


def _desde(ip):
    return {"HTTP_X_REAL_IP": ip, "REMOTE_ADDR": ip}


def _intentar(contrasena, ip="203.0.113.10", identificador=CORREO):
    return iniciar_sesion(Client(), identificador, contrasena, **_desde(ip))


def _fallar(veces, **kwargs):
    for _ in range(veces):
        assert _intentar(MALA, **kwargs).status_code == 401


@pytest.fixture(autouse=True)
def cuenta(request):
    if request.node.get_closest_marker("django_db") is None:
        return None
    return crear_cliente()


@pytest.mark.django_db
def test_pi230_cinco_fallos_bloquean_aunque_la_contrasena_sea_correcta():
    _fallar(5)

    respuesta = _intentar(CONTRASENA)

    assert respuesta.status_code == 429
    assert "espera 15 minutos" in respuesta.json()["mensaje"]
    assert respuesta["Retry-After"] == "900"
    assert "sessionid" not in respuesta.cookies


@pytest.mark.django_db
def test_pi231_cuatro_fallos_no_bloquean():
    _fallar(4)

    assert _intentar(CONTRASENA).status_code == 200


@pytest.mark.django_db
def test_pi232_fallos_espaciados_fuera_de_la_ventana_no_bloquean():
    inicio = timezone.now()
    for minuto in (0, 4, 8, 12, 16):
        with time_machine.travel(inicio + datetime.timedelta(minutes=minuto), tick=False):
            _fallar(1)

    with time_machine.travel(inicio + datetime.timedelta(minutes=16), tick=False):
        assert _intentar(CONTRASENA).status_code == 200


@pytest.mark.django_db
def test_pi233_otro_origen_no_queda_bloqueado():
    _fallar(5, ip="203.0.113.10")

    assert _intentar(CONTRASENA, ip="198.51.100.7").status_code == 200


@pytest.mark.django_db
def test_otra_cuenta_desde_el_mismo_origen_no_queda_bloqueada():
    crear_cliente(correo="otra@example.com", telefono="+56 9 1000 0002")
    _fallar(5, identificador=CORREO)

    assert _intentar(CONTRASENA, identificador="otra@example.com").status_code == 200


@pytest.mark.django_db
def test_veinte_fallos_desde_un_origen_bloquean_todo_ese_origen():
    for numero in range(20):
        _fallar(1, identificador=f"persona{numero}@example.com")

    assert _intentar(CONTRASENA).status_code == 429
    assert _intentar(CONTRASENA, ip="198.51.100.7").status_code == 200


@pytest.mark.django_db
def test_pi234_el_bloqueo_nunca_deshabilita_la_cuenta(cuenta):
    _fallar(5)

    columnas = {campo.name for campo in Usuario._meta.get_fields()}
    assert not columnas & {"activo", "is_active", "bloqueado"}
    assert Usuario.objects.get(pk=cuenta.pk).check_password(CONTRASENA)


@pytest.mark.django_db
def test_pi235_el_bloqueo_dura_15_minutos_desde_el_quinto_fallo():
    inicio = timezone.now()
    with time_machine.travel(inicio, tick=False):
        _fallar(5)
    with time_machine.travel(inicio + datetime.timedelta(minutes=14, seconds=59), tick=False):
        assert _intentar(CONTRASENA).status_code == 429
    with time_machine.travel(inicio + datetime.timedelta(minutes=15, seconds=1), tick=False):
        assert _intentar(CONTRASENA).status_code == 200


@pytest.mark.django_db
def test_adr007_punto2_los_429_no_cuentan_ni_alargan_el_bloqueo():
    inicio = timezone.now()
    with time_machine.travel(inicio, tick=False):
        _fallar(5)
    with time_machine.travel(inicio + datetime.timedelta(minutes=10), tick=False):
        assert _intentar(MALA).status_code == 429
    assert IntentoAutenticacion.objects.count() == 5
    with time_machine.travel(inicio + datetime.timedelta(minutes=16), tick=False):
        assert _intentar(CONTRASENA).status_code == 200


@pytest.mark.django_db
def test_adr007_punto3_un_ingreso_correcto_no_reinicia_el_contador():
    _fallar(4)
    assert _intentar(CONTRASENA).status_code == 200

    _fallar(1)

    assert _intentar(CONTRASENA).status_code == 429


@pytest.mark.django_db
def test_adr007_punto8_los_400_no_cuentan():
    for _ in range(6):
        assert iniciar_sesion(Client(), "11.111.111-2", MALA, **_desde("203.0.113.10")).status_code == 400

    assert IntentoAutenticacion.objects.count() == 0


@pytest.mark.django_db
def test_pi236_no_se_guarda_el_correo_ni_el_rut_en_claro():
    _fallar(1, identificador=CORREO)
    _fallar(1, identificador="11.111.111-1")

    for intento in IntentoAutenticacion.objects.all():
        assert CORREO not in intento.clave
        assert "111111111" not in intento.clave
        assert len(intento.clave) == 64


@pytest.mark.django_db
def test_adr007_punto7_se_borran_los_fallos_de_mas_de_24_horas():
    inicio = timezone.now()
    with time_machine.travel(inicio, tick=False):
        _fallar(2)
    with time_machine.travel(inicio + datetime.timedelta(hours=25), tick=False):
        _fallar(1)

    assert IntentoAutenticacion.objects.count() == 1


@override_settings(ALTIRO_CONFIAR_X_REAL_IP=False)
def test_sin_confianza_en_el_proxy_se_ignora_x_real_ip():
    peticion = RequestFactory().get("/", HTTP_X_REAL_IP="203.0.113.10", REMOTE_ADDR="172.19.0.1")

    assert limitador.origen_de(peticion) == "172.19.0.1"


@override_settings(ALTIRO_CONFIAR_X_REAL_IP=True)
def test_con_confianza_en_el_proxy_se_usa_x_real_ip_valida():
    assert limitador.origen_de(RequestFactory().get("/", HTTP_X_REAL_IP="203.0.113.10")) == "203.0.113.10"
    invalida = RequestFactory().get("/", HTTP_X_REAL_IP="no es ip", REMOTE_ADDR="172.19.0.1")
    assert limitador.origen_de(invalida) == "172.19.0.1"
