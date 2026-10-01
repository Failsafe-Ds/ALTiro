"""Inicio y cierre de sesión, cuenta y expiración (RF-02, RNF-05, RNF-09; ADR-005, ADR-013).

Identificadores PI-xxx del plan de pruebas (sección L y N).
"""
import datetime
import logging

import pytest
import time_machine
from django.test import Client
from django.utils import timezone

from identidad.models import IntentoAutenticacion
from tests.ayudas import (
    CONTRASENA,
    TEL_A,
    URL_CUENTA,
    URL_SESION,
    crear_cliente,
    crear_maestro,
    iniciar_sesion,
    post_json,
    sin_texto_prohibido,
)

MENSAJE_401 = "No pudimos iniciar sesión. Revisa tu correo o RUT y tu contraseña e inténtalo de nuevo."


@pytest.fixture
def cliente():
    return crear_cliente()


@pytest.fixture
def maestro():
    return crear_maestro(rut="10.000.013-K", correo="mae1@example.com")


# --- Inicio de sesión correcto ---


@pytest.mark.django_db
def test_pi190_inicio_de_sesion_con_correo(client, cliente):
    respuesta = iniciar_sesion(client, "ana.prueba@example.com")

    assert respuesta.status_code == 200
    assert respuesta.json()["cuenta"]["correo"] == "ana.prueba@example.com"
    assert client.get(URL_CUENTA).status_code == 200


@pytest.mark.django_db
def test_pi191_el_correo_se_normaliza_al_iniciar_sesion(client, cliente):
    assert iniciar_sesion(client, "  ANA.Prueba@Example.com ").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("rut", ["10.000.013-k", "10000013K", "10.000.013-K"])
def test_pi192_inicio_de_sesion_con_rut_en_cualquier_formato(client, maestro, rut):
    assert iniciar_sesion(client, rut).status_code == 200


@pytest.mark.django_db
def test_pi086_correo_y_rut_llevan_a_la_misma_cuenta(maestro):
    con_correo, con_rut = Client(), Client()
    iniciar_sesion(con_correo, "mae1@example.com")
    iniciar_sesion(con_rut, "10000013K")

    assert con_correo.get(URL_CUENTA).json() == con_rut.get(URL_CUENTA).json()


# --- Errores (ADR-013, punto 4) ---


@pytest.mark.django_db
def test_pi193_cuenta_inexistente_y_contrasena_incorrecta_dan_el_mismo_401(cliente, maestro):
    casos = [
        ("nadie@example.com", CONTRASENA),
        ("ana.prueba@example.com", "contraseña equivocada"),
        ("22.222.222-2", CONTRASENA),
        ("10.000.013-K", "contraseña equivocada"),
    ]
    respuestas = [iniciar_sesion(Client(), identificador, contrasena) for identificador, contrasena in casos]

    assert {r.status_code for r in respuestas} == {401}
    assert len({r.content for r in respuestas}) == 1
    assert respuestas[0].json() == {"mensaje": MENSAJE_401, "errores": {}}
    assert all("sessionid" not in r.cookies for r in respuestas)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "datos, campos",
    [
        ({"contrasena": CONTRASENA}, {"identificador"}),
        ({"identificador": "ana@example.com"}, {"contrasena"}),
        ({}, {"identificador", "contrasena"}),
    ],
)
def test_pi194_campos_ausentes_responden_400_por_campo(client, datos, campos):
    respuesta = post_json(client, URL_SESION, datos)

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == campos


@pytest.mark.django_db
@pytest.mark.parametrize("identificador", ["11.111.111-2", "a@", "@b.cl", "", "   "])
def test_pi195_identificador_con_formato_invalido_responde_400(client, identificador):
    respuesta = iniciar_sesion(client, identificador)

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"identificador"}


@pytest.mark.django_db
def test_pi064_el_telefono_nunca_sirve_para_iniciar_sesion(client, cliente):
    for identificador in [TEL_A, "+56910000001", "910000001"]:
        assert iniciar_sesion(client, identificador).status_code in (400, 401)
    assert client.get(URL_CUENTA).status_code == 401


@pytest.mark.django_db
def test_pi198_inicio_de_sesion_sin_csrf_responde_403(cliente):
    respuesta = iniciar_sesion(Client(enforce_csrf_checks=True), "ana.prueba@example.com")

    assert respuesta.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "datos",
    [
        {"identificador": "' OR 1=1 --@x.cl", "contrasena": CONTRASENA},
        {"identificador": 123, "contrasena": CONTRASENA},
        {"identificador": ["a@example.com"], "contrasena": {"x": 1}},
        {"identificador": None, "contrasena": None},
    ],
)
def test_pi199_entradas_maliciosas_nunca_dan_500(client, datos):
    respuesta = post_json(client, URL_SESION, datos)

    assert respuesta.status_code in (400, 401)
    assert sin_texto_prohibido(respuesta)


@pytest.mark.django_db
@pytest.mark.parametrize("contrasena", ["", "x" * 129, "x" * 10_000])
def test_pi205_contrasena_vacia_o_larga_responde_400_sin_calcular_hash(client, cliente, monkeypatch, contrasena):
    llamadas = []
    monkeypatch.setattr("identidad.hashers.Argon2idAlTiro.verify", lambda *a: llamadas.append(1))
    monkeypatch.setattr("identidad.hashers.Argon2idAlTiro.encode", lambda *a, **k: llamadas.append(1))

    respuesta = iniciar_sesion(client, "ana.prueba@example.com", contrasena)

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"contrasena"}
    assert llamadas == []
    assert IntentoAutenticacion.objects.count() == 0  # ADR-007, punto 8


@pytest.mark.django_db
@pytest.mark.parametrize("contrasena", ["x", "            "])
def test_pi205_contrasena_corta_o_de_espacios_se_verifica_y_da_401(client, cliente, contrasena):
    assert iniciar_sesion(client, "ana.prueba@example.com", contrasena).status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("extra, errores", [({"correo": "a@example.com"}, {"correo"}), ({"recordar": True}, set())])
def test_pi206_campos_no_permitidos_en_el_inicio_de_sesion(client, cliente, extra, errores):
    datos = {"identificador": "ana.prueba@example.com", "contrasena": CONTRASENA, **extra}

    respuesta = post_json(client, URL_SESION, datos)

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == errores
    assert client.get(URL_CUENTA).status_code == 401


@pytest.mark.django_db
def test_pi157_la_contrasena_no_se_recorta():
    from identidad.servicios import crear_cuenta_cliente

    crear_cuenta_cliente(
        nombre="Ana", telefono=TEL_A, correo="espacios@example.com", contrasena="  clave de prueba  ", comuna="8101"
    )

    assert iniciar_sesion(Client(), "espacios@example.com", "  clave de prueba  ").status_code == 200
    assert iniciar_sesion(Client(), "espacios@example.com", "clave de prueba").status_code == 401


@pytest.mark.django_db
def test_pi163_la_contrasena_no_expira(client, cliente):
    with time_machine.travel(timezone.now() + datetime.timedelta(days=400)):
        assert iniciar_sesion(client, "ana.prueba@example.com").status_code == 200


# --- Sesión (RF-02, ADR-005) ---


@pytest.mark.django_db
def test_pi200_cerrar_sesion_la_borra_en_el_servidor(client, cliente):
    iniciar_sesion(client, "ana.prueba@example.com")
    cookie_anterior = client.cookies["sessionid"].value

    assert client.delete(URL_SESION).status_code == 204
    assert client.get(URL_CUENTA).status_code == 401
    otro = Client()
    otro.cookies["sessionid"] = cookie_anterior
    assert otro.get(URL_CUENTA).status_code == 401


@pytest.mark.django_db
def test_cerrar_sesion_sin_sesion_responde_401(client):
    assert client.delete(URL_SESION).status_code == 401


@pytest.mark.django_db
def test_pi201_cuenta_sin_sesion_responde_401(client):
    assert client.get(URL_CUENTA).status_code == 401


@pytest.mark.django_db
def test_pi202_el_id_de_sesion_cambia_al_iniciar_sesion(client, cliente):
    sesion = client.session
    sesion["previa"] = "x"
    sesion.save()
    anterior = sesion.session_key

    iniciar_sesion(client, "ana.prueba@example.com")

    assert client.cookies["sessionid"].value != anterior


@pytest.mark.django_db
def test_pi203_cookie_de_sesion_segura(client, cliente):
    respuesta = iniciar_sesion(client, "ana.prueba@example.com")

    cookie = respuesta.cookies["sessionid"]
    assert cookie["secure"]
    assert cookie["httponly"]
    assert cookie["samesite"] == "Lax"
    assert int(cookie["max-age"]) == 1800


@pytest.mark.django_db
def test_pi176_la_cuenta_solo_trae_campos_propios_y_explicitos(client, cliente):
    iniciar_sesion(client, "ana.prueba@example.com")

    cuenta = client.get(URL_CUENTA).json()["cuenta"]

    assert set(cuenta) == {"nombre", "correo", "telefono", "roles", "perfil_cliente", "perfil_maestro"}
    assert cuenta["roles"] == ["cliente"]
    assert cuenta["perfil_cliente"]["region"] == {"codigo": 8, "nombre": "Biobío"}
    assert "argon2" not in client.get(URL_CUENTA).content.decode("utf-8")


@pytest.mark.django_db
def test_cambiar_el_hash_invalida_las_sesiones_abiertas(client, cliente):
    iniciar_sesion(client, "ana.prueba@example.com")

    cliente.set_password("otra clave de prueba")
    cliente.save()

    assert client.get(URL_CUENTA).status_code == 401


@pytest.mark.django_db
def test_pi250_la_sesion_expira_tras_30_minutos_de_inactividad(cliente):
    inicio = timezone.now()
    a_los_29, a_los_31 = Client(), Client()
    with time_machine.travel(inicio, tick=False):
        iniciar_sesion(a_los_29, "ana.prueba@example.com")
        iniciar_sesion(a_los_31, "ana.prueba@example.com")

    with time_machine.travel(inicio + datetime.timedelta(minutes=29), tick=False):
        assert a_los_29.get(URL_CUENTA).status_code == 200
    with time_machine.travel(inicio + datetime.timedelta(minutes=31), tick=False):
        assert a_los_31.get(URL_CUENTA).status_code == 401


@pytest.mark.django_db
def test_pi251_la_actividad_renueva_el_plazo(client, cliente):
    inicio = timezone.now()
    with time_machine.travel(inicio, tick=False):
        iniciar_sesion(client, "ana.prueba@example.com")
    with time_machine.travel(inicio + datetime.timedelta(minutes=20), tick=False):
        assert client.get(URL_CUENTA).status_code == 200
    with time_machine.travel(inicio + datetime.timedelta(minutes=45), tick=False):
        assert client.get(URL_CUENTA).status_code == 200
    with time_machine.travel(inicio + datetime.timedelta(minutes=76), tick=False):
        assert client.get(URL_CUENTA).status_code == 401


@pytest.mark.django_db
def test_pi252_la_cuenta_no_se_edita_en_bloque(client, cliente):
    """Desde ADR-027 (DA-27) el cambio de contraseña y de correo tiene rutas propias con
    reautenticación (``tests/test_credenciales.py``); ``/api/cuenta`` sigue sin edición genérica."""
    iniciar_sesion(client, "ana.prueba@example.com")

    assert client.put(URL_CUENTA).status_code == 405
    assert client.patch(URL_CUENTA).status_code == 405


# --- Registros (CLAUDE.md §8, PI-174) ---


@pytest.mark.django_db
def test_pi174_la_contrasena_no_aparece_en_los_registros(client, cliente, caplog):
    with caplog.at_level(logging.DEBUG):
        iniciar_sesion(client, "ana.prueba@example.com", "contraseña equivocada")
        iniciar_sesion(client, "ana.prueba@example.com")

    assert CONTRASENA not in caplog.text
    assert "contraseña equivocada" not in caplog.text
    assert "ana.prueba@example.com" not in caplog.text
