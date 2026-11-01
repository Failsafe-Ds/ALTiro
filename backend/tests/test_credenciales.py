"""Cambio de contraseña, cambio de correo y recuperación de contraseña (RNF-09, RNF-10; ADR-027).

Datos ficticios: @example.com y RUT sintéticos.
"""
import datetime
import io
import logging
import re

import pytest
import time_machine
from django.core.management import CommandError, call_command
from django.test import Client
from django.utils import timezone

from identidad import recuperacion
from identidad.models import Rol, SolicitudRecuperacion, Usuario, UsuarioRol
from tests.ayudas import (
    CONTRASENA,
    URL_CUENTA,
    crear_cliente,
    crear_maestro,
    iniciar_sesion,
    post_json,
    sin_texto_prohibido,
)

URL_CONTRASENA = "/api/cuenta/contrasena"
URL_CORREO = "/api/cuenta/correo"
URL_RECUPERACION = "/api/recuperacion"
URL_RESTABLECER = "/api/recuperacion/contrasena"
NUEVA = "otra clave bien larga"
CORREO_CLIENTE = "ana.prueba@example.com"
RUT_MAESTRO = "10.000.013-K"

pytestmark = pytest.mark.django_db


@pytest.fixture
def cliente():
    return crear_cliente()


@pytest.fixture
def con_sesion(client, cliente):
    assert iniciar_sesion(client, CORREO_CLIENTE).status_code == 200
    return client


def _token_del_correo(correo):
    coincidencia = re.search(r"nueva-contrasena\.html#t=([A-Za-z0-9_-]+)", correo.body)
    assert coincidencia, "el correo debe traer el enlace"
    return coincidencia.group(1)


def _pedir_enlace(client, identificador, **extra):
    return post_json(client, URL_RECUPERACION, {"identificador": identificador}, **extra)


# --- Cambio de contraseña (ADR-027, punto 1) ---


@pytest.mark.regla("A-26", "A-28")
def test_cambiar_contrasena_con_la_actual_cierra_las_demas_sesiones(con_sesion, mailoutbox):
    otra = Client()
    iniciar_sesion(otra, CORREO_CLIENTE)

    respuesta = post_json(con_sesion, URL_CONTRASENA, {"contrasena": CONTRASENA, "contrasena_nueva": NUEVA})

    assert respuesta.status_code == 200
    assert con_sesion.get(URL_CUENTA).status_code == 200  # la propia sigue
    assert otra.get(URL_CUENTA).status_code == 401  # las demás no
    assert iniciar_sesion(Client(), CORREO_CLIENTE).status_code == 401
    assert iniciar_sesion(Client(), CORREO_CLIENTE, NUEVA).status_code == 200
    assert [m.subject for m in mailoutbox] == ["Tu contraseña de AlTiro cambió"]
    assert mailoutbox[0].to == [CORREO_CLIENTE]


@pytest.mark.regla("A-26")
def test_cambiar_contrasena_con_la_actual_equivocada_da_400_y_no_cambia(con_sesion):
    respuesta = post_json(con_sesion, URL_CONTRASENA, {"contrasena": "no es la mía de verdad", "contrasena_nueva": NUEVA})

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"contrasena": "La contraseña actual no es correcta. Revísala e inténtalo de nuevo."}
    assert iniciar_sesion(Client(), CORREO_CLIENTE).status_code == 200


@pytest.mark.regla("A-26")
def test_cambiar_contrasena_sin_la_actual_da_400_en_ese_campo(con_sesion):
    respuesta = post_json(con_sesion, URL_CONTRASENA, {"contrasena_nueva": NUEVA})

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"contrasena"}


@pytest.mark.regla("A-27")
def test_cinco_fallos_de_reautenticacion_bloquean_aunque_luego_sea_correcta(con_sesion):
    for _ in range(5):
        assert post_json(con_sesion, URL_CONTRASENA, {"contrasena": "equivocada pero larga", "contrasena_nueva": NUEVA}).status_code == 400

    respuesta = post_json(con_sesion, URL_CONTRASENA, {"contrasena": CONTRASENA, "contrasena_nueva": NUEVA})

    assert respuesta.status_code == 429
    assert respuesta["Retry-After"] == "900"
    assert "15 minutos" in respuesta.json()["mensaje"]
    assert iniciar_sesion(Client(), CORREO_CLIENTE).status_code == 200  # no cambió


def test_la_contrasena_nueva_sigue_la_politica_y_debe_ser_distinta(con_sesion):
    corta = post_json(con_sesion, URL_CONTRASENA, {"contrasena": CONTRASENA, "contrasena_nueva": "corta"})
    igual = post_json(con_sesion, URL_CONTRASENA, {"contrasena": CONTRASENA, "contrasena_nueva": CONTRASENA})

    assert corta.status_code == 400 and set(corta.json()["errores"]) == {"contrasena_nueva"}
    assert "muy corta" in corta.json()["errores"]["contrasena_nueva"]
    assert igual.json()["errores"] == {"contrasena_nueva": "Elige una contraseña distinta de la actual."}


def test_las_rutas_de_cuenta_exigen_sesion(client):
    for url in (URL_CONTRASENA, URL_CORREO):
        assert post_json(client, url, {"contrasena": CONTRASENA}).status_code == 401


def test_campos_ajenos_al_cambio_de_contrasena_dan_400(con_sesion):
    respuesta = post_json(con_sesion, URL_CONTRASENA, {"contrasena": CONTRASENA, "contrasena_nueva": NUEVA, "correo": "x@example.com"})

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"correo"}


# --- Cambio de correo (ADR-027, punto 2) ---


@pytest.mark.regla("A-26")
def test_cambiar_correo_con_la_contrasena_avisa_al_anterior(con_sesion, mailoutbox):
    respuesta = post_json(con_sesion, URL_CORREO, {"contrasena": CONTRASENA, "correo": " Nuevo.Correo@Example.com "})

    assert respuesta.status_code == 200
    assert respuesta.json()["cuenta"]["correo"] == "nuevo.correo@example.com"
    assert con_sesion.get(URL_CUENTA).status_code == 200  # la sesión sigue
    assert iniciar_sesion(Client(), "nuevo.correo@example.com").status_code == 200
    assert iniciar_sesion(Client(), CORREO_CLIENTE).status_code == 401
    assert [(m.subject, m.to) for m in mailoutbox] == [("Tu correo de AlTiro cambió", [CORREO_CLIENTE])]


@pytest.mark.regla("A-26")
def test_cambiar_correo_sin_la_contrasena_correcta_no_cambia(con_sesion):
    respuesta = post_json(con_sesion, URL_CORREO, {"contrasena": "equivocada pero larga", "correo": "otro@example.com"})

    assert respuesta.status_code == 400
    assert Usuario.objects.get().correo == CORREO_CLIENTE


def test_cambiar_correo_a_uno_ajeno_o_al_mismo_da_400(con_sesion):
    crear_cliente(correo="ocupado@example.com", telefono="+56 9 1000 0002")

    ajeno = post_json(con_sesion, URL_CORREO, {"contrasena": CONTRASENA, "correo": "ocupado@example.com"})
    mismo = post_json(con_sesion, URL_CORREO, {"contrasena": CONTRASENA, "correo": CORREO_CLIENTE})

    assert ajeno.status_code == 400 and "ya está registrado" in ajeno.json()["errores"]["correo"]
    assert mismo.json()["errores"] == {"correo": "Ese ya es tu correo. Escribe el correo nuevo que quieres usar."}
    assert sin_texto_prohibido(ajeno)


def test_un_maestro_sin_correo_puede_agregarlo_con_su_contrasena(client, mailoutbox):
    crear_maestro(rut=RUT_MAESTRO)
    iniciar_sesion(client, RUT_MAESTRO)

    respuesta = post_json(client, URL_CORREO, {"contrasena": CONTRASENA, "correo": "maestro@example.com"})

    assert respuesta.status_code == 200
    assert respuesta.json()["cuenta"]["correo"] == "maestro@example.com"
    assert mailoutbox == []  # no había correo anterior que avisar


# --- Primer correo con el perfil de cliente (RNF-09; ADR-013, E-10; auditoría de seguridad run-1, 3.1) ---

URL_CLIENTES = "/api/clientes"


def _maestro_sin_correo_con_sesion(client):
    maestro = crear_maestro(rut=RUT_MAESTRO)
    assert iniciar_sesion(client, RUT_MAESTRO).status_code == 200
    return maestro


@pytest.mark.regla("A-26")
def test_primer_correo_con_perfil_de_cliente_sin_contrasena_da_400_y_no_guarda(client):
    maestro = _maestro_sin_correo_con_sesion(client)

    respuesta = post_json(client, URL_CLIENTES, {"comuna": "8101", "correo": "ajeno@example.com"})

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"contrasena"}
    assert "contraseña actual" in respuesta.json()["errores"]["contrasena"]
    assert sin_texto_prohibido(respuesta)
    maestro.refresh_from_db()
    assert maestro.correo is None
    assert not UsuarioRol.objects.filter(usuario=maestro, rol=Rol.CLIENTE).exists()


@pytest.mark.regla("A-26")
def test_primer_correo_con_contrasena_equivocada_da_400_y_no_guarda(client):
    maestro = _maestro_sin_correo_con_sesion(client)

    respuesta = post_json(
        client, URL_CLIENTES, {"comuna": "8101", "correo": "ajeno@example.com", "contrasena": "equivocada pero larga"}
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"contrasena": "La contraseña actual no es correcta. Revísala e inténtalo de nuevo."}
    maestro.refresh_from_db()
    assert maestro.correo is None


def test_primer_correo_sin_correo_ni_contrasena_marca_los_dos_campos(client):
    _maestro_sin_correo_con_sesion(client)

    respuesta = post_json(client, URL_CLIENTES, {"comuna": "8101"})

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"correo", "contrasena"}


@pytest.mark.regla("A-27")
def test_primer_correo_comparte_el_limitador_de_reautenticacion(client):
    maestro = _maestro_sin_correo_con_sesion(client)
    for _ in range(5):
        cuerpo = {"comuna": "8101", "correo": "ajeno@example.com", "contrasena": "equivocada pero larga"}
        assert post_json(client, URL_CLIENTES, cuerpo).status_code == 400

    # El bloqueo alcanza también a /api/cuenta/correo: es la misma cuenta.
    respuesta = post_json(client, URL_CORREO, {"contrasena": CONTRASENA, "correo": "ajeno@example.com"})
    con_perfil = post_json(client, URL_CLIENTES, {"comuna": "8101", "correo": "ajeno@example.com", "contrasena": CONTRASENA})

    assert respuesta.status_code == 429 and con_perfil.status_code == 429
    maestro.refresh_from_db()
    assert maestro.correo is None


def test_primer_correo_con_la_contrasena_lo_guarda_y_sirve_para_recuperar(client, mailoutbox):
    _maestro_sin_correo_con_sesion(client)

    respuesta = post_json(client, URL_CLIENTES, {"comuna": "8101", "correo": "maestro@example.com", "contrasena": CONTRASENA})

    assert respuesta.status_code == 201
    assert respuesta.json()["cuenta"]["correo"] == "maestro@example.com"
    assert "cliente" in respuesta.json()["cuenta"]["roles"]
    assert _pedir_enlace(Client(), RUT_MAESTRO).status_code == 202
    assert [m.to for m in mailoutbox] == [["maestro@example.com"]]


def test_con_correo_la_contrasena_no_va_en_el_perfil_de_cliente(client):
    crear_maestro(rut=RUT_MAESTRO, correo="mae@example.com")
    iniciar_sesion(client, "mae@example.com")

    respuesta = post_json(client, URL_CLIENTES, {"comuna": "8101", "contrasena": CONTRASENA})
    sin_ella = post_json(client, URL_CLIENTES, {"comuna": "8101"})

    assert respuesta.status_code == 400 and set(respuesta.json()["errores"]) == {"contrasena"}
    assert sin_ella.status_code == 201


# --- Tope de intentos de guardar un correo (ADR-027, E-2; auditoría de seguridad run-1, 3.2) ---


@pytest.mark.regla("A-27")
def test_cambiar_correo_tiene_tope_por_cuenta(con_sesion):
    crear_cliente(correo="ocupado@example.com", telefono="+56 9 1000 0002")
    for _ in range(20):
        sonda = post_json(con_sesion, URL_CORREO, {"contrasena": CONTRASENA, "correo": "ocupado@example.com"})
        assert sonda.status_code == 400

    respuesta = post_json(con_sesion, URL_CORREO, {"contrasena": CONTRASENA, "correo": "ocupado@example.com"})

    assert respuesta.status_code == 429
    assert respuesta["Retry-After"] == "3600"
    assert "varias veces seguidas" in respuesta.json()["mensaje"]
    assert "registrado" not in respuesta.content.decode()
    assert sin_texto_prohibido(respuesta)


@pytest.mark.regla("A-27")
def test_cambiar_correo_tiene_tope_por_origen_aunque_cambie_la_cuenta(client, cliente):
    crear_cliente(correo="ocupado@example.com", telefono="+56 9 1000 0002")
    for indice in range(4):
        crear_cliente(correo=f"c{indice}@example.com", telefono=f"+56 9 1000 001{indice}")
    sesiones = []
    for indice in range(4):
        navegador = Client()
        assert iniciar_sesion(navegador, f"c{indice}@example.com").status_code == 200
        sesiones.append(navegador)
    for indice in range(20):
        sonda = post_json(sesiones[indice % 4], URL_CORREO, {"contrasena": CONTRASENA, "correo": "ocupado@example.com"})
        assert sonda.status_code == 400

    iniciar_sesion(client, CORREO_CLIENTE)
    respuesta = post_json(client, URL_CORREO, {"contrasena": CONTRASENA, "correo": "ocupado@example.com"})

    assert respuesta.status_code == 429


def test_un_correo_mal_escrito_no_gasta_el_tope_de_correo(con_sesion):
    for _ in range(25):
        assert post_json(con_sesion, URL_CORREO, {"contrasena": CONTRASENA, "correo": "sin-arroba"}).status_code == 400

    respuesta = post_json(con_sesion, URL_CORREO, {"contrasena": CONTRASENA, "correo": "nuevo@example.com"})

    assert respuesta.status_code == 200


# --- Recuperación por correo (ADR-027, punto 3) ---


@pytest.mark.regla("A-29")
def test_pedir_recuperacion_responde_igual_exista_o_no_la_cuenta(client, cliente, mailoutbox):
    crear_maestro(rut=RUT_MAESTRO)  # sin correo
    respuestas = [
        _pedir_enlace(client, CORREO_CLIENTE),
        _pedir_enlace(client, "nadie@example.com"),
        _pedir_enlace(client, RUT_MAESTRO),
    ]

    assert {r.status_code for r in respuestas} == {202}
    assert len({r.content for r in respuestas}) == 1
    assert [m.to for m in mailoutbox] == [[CORREO_CLIENTE]]


@pytest.mark.regla("A-28", "A-30")
def test_el_enlace_cambia_la_contrasena_una_sola_vez_y_cierra_las_sesiones(client, cliente, mailoutbox):
    abierta = Client()
    iniciar_sesion(abierta, CORREO_CLIENTE)
    _pedir_enlace(client, CORREO_CLIENTE)
    token = _token_del_correo(mailoutbox[0])

    primera = post_json(client, URL_RESTABLECER, {"token": token, "contrasena_nueva": NUEVA})
    segunda = post_json(client, URL_RESTABLECER, {"token": token, "contrasena_nueva": "y otra más todavía"})

    assert primera.status_code == 200
    assert client.get(URL_CUENTA).status_code == 401  # no inicia sesión
    assert abierta.get(URL_CUENTA).status_code == 401
    assert iniciar_sesion(Client(), CORREO_CLIENTE, NUEVA).status_code == 200
    assert segunda.status_code == 400 and set(segunda.json()["errores"]) == {"token"}
    assert mailoutbox[-1].subject == "Tu contraseña de AlTiro cambió"


@pytest.mark.regla("A-30")
def test_el_enlace_vence(client, cliente, mailoutbox):
    _pedir_enlace(client, CORREO_CLIENTE)
    token = _token_del_correo(mailoutbox[0])

    with time_machine.travel(timezone.now() + datetime.timedelta(minutes=31)):
        respuesta = post_json(client, URL_RESTABLECER, {"token": token, "contrasena_nueva": NUEVA})

    assert respuesta.status_code == 400
    assert "Pide uno nuevo" in respuesta.json()["errores"]["token"]


@pytest.mark.regla("A-30")
def test_un_enlace_nuevo_o_un_cambio_de_contrasena_anulan_los_anteriores(client, cliente, mailoutbox):
    _pedir_enlace(client, CORREO_CLIENTE)
    _pedir_enlace(client, CORREO_CLIENTE)
    viejo, nuevo = (_token_del_correo(m) for m in mailoutbox)

    assert post_json(client, URL_RESTABLECER, {"token": viejo, "contrasena_nueva": NUEVA}).status_code == 400

    iniciar_sesion(client, CORREO_CLIENTE)
    post_json(client, URL_CONTRASENA, {"contrasena": CONTRASENA, "contrasena_nueva": NUEVA})
    assert post_json(Client(), URL_RESTABLECER, {"token": nuevo, "contrasena_nueva": "y otra más todavía"}).status_code == 400


@pytest.mark.regla("A-30")
def test_cambiar_el_correo_anula_el_enlace_enviado_al_anterior(client, cliente, mailoutbox):
    _pedir_enlace(client, CORREO_CLIENTE)
    token = _token_del_correo(mailoutbox[0])

    iniciar_sesion(client, CORREO_CLIENTE)
    assert post_json(client, URL_CORREO, {"contrasena": CONTRASENA, "correo": "nuevo.correo@example.com"}).status_code == 200

    assert post_json(Client(), URL_RESTABLECER, {"token": token, "contrasena_nueva": NUEVA}).status_code == 400
    assert iniciar_sesion(Client(), "nuevo.correo@example.com").status_code == 200


def test_una_contrasena_invalida_no_gasta_el_enlace(client, cliente, mailoutbox):
    _pedir_enlace(client, CORREO_CLIENTE)
    token = _token_del_correo(mailoutbox[0])

    corta = post_json(client, URL_RESTABLECER, {"token": token, "contrasena_nueva": "corta"})

    assert corta.status_code == 400 and set(corta.json()["errores"]) == {"contrasena_nueva"}
    assert post_json(client, URL_RESTABLECER, {"token": token, "contrasena_nueva": NUEVA}).status_code == 200


def test_el_token_no_se_guarda_y_el_enlace_lo_lleva_en_el_fragmento(client, cliente, mailoutbox):
    _pedir_enlace(client, CORREO_CLIENTE)
    token = _token_del_correo(mailoutbox[0])
    fila = SolicitudRecuperacion.objects.get(token_hash__isnull=False)

    assert token not in (fila.token_hash or "")
    assert len(fila.token_hash) == 64
    assert "#t=" in mailoutbox[0].body and "?t=" not in mailoutbox[0].body


@pytest.mark.parametrize("token", ["", "inventado", "x" * 101, 5])
def test_un_token_invalido_da_400_en_token(client, token):
    respuesta = post_json(client, URL_RESTABLECER, {"token": token, "contrasena_nueva": NUEVA})

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"token"}


def test_un_maestro_con_correo_recupera_con_su_rut(client, mailoutbox):
    crear_maestro(rut=RUT_MAESTRO, correo="mae1@example.com")

    _pedir_enlace(client, "10000013k")

    assert [m.to for m in mailoutbox] == [["mae1@example.com"]]


@pytest.mark.regla("A-29")
def test_mas_de_cinco_solicitudes_desde_un_origen_dan_429_aunque_no_existan(client):
    for _ in range(5):
        assert _pedir_enlace(client, "nadie@example.com").status_code == 202

    respuesta = _pedir_enlace(client, "nadie@example.com")

    assert respuesta.status_code == 429
    assert int(respuesta["Retry-After"]) > 0
    assert _pedir_enlace(client, "nadie@example.com", REMOTE_ADDR="10.0.0.9").status_code == 202


def test_una_cuenta_recibe_como_maximo_tres_enlaces_por_hora(client, cliente, mailoutbox):
    for i in range(4):
        assert _pedir_enlace(client, CORREO_CLIENTE, REMOTE_ADDR=f"10.0.0.{i + 1}").status_code == 202

    assert len(mailoutbox) == 3


def test_las_solicitudes_de_mas_de_24_horas_se_borran(client, cliente):
    with time_machine.travel(timezone.now() - datetime.timedelta(hours=25)):
        _pedir_enlace(client, CORREO_CLIENTE)

    _pedir_enlace(client, "nadie@example.com")

    assert SolicitudRecuperacion.objects.count() == 1


def test_identificador_invalido_da_400(client):
    respuesta = _pedir_enlace(client, "no es un rut")

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"identificador"}


def test_ni_el_token_ni_la_contrasena_llegan_al_registro(client, cliente, mailoutbox, caplog):
    caplog.set_level(logging.DEBUG)
    _pedir_enlace(client, CORREO_CLIENTE)
    token = _token_del_correo(mailoutbox[0])
    post_json(client, URL_RESTABLECER, {"token": token, "contrasena_nueva": NUEVA})

    texto = "\n".join(r.getMessage() for r in caplog.records)
    for dato in (token, NUEVA, CORREO_CLIENTE):
        assert dato not in texto


def test_un_buzon_que_falla_no_cambia_la_respuesta(client, cliente, settings, caplog):
    settings.EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    settings.ALTIRO_BUZON_DIR = "/proc/no-se-puede-escribir"

    respuesta = _pedir_enlace(client, CORREO_CLIENTE)

    assert respuesta.status_code == 202
    assert any("No se pudo escribir un correo" in r.getMessage() for r in caplog.records)


def test_el_buzon_local_escribe_el_correo_en_su_directorio(client, cliente, settings, tmp_path):
    settings.EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    buzon = tmp_path / "buzon"
    settings.ALTIRO_BUZON_DIR = buzon

    _pedir_enlace(client, CORREO_CLIENTE)

    (archivo,) = buzon.iterdir()
    assert "nueva-contrasena.html#t=" in archivo.read_text(encoding="utf-8")


# --- Recuperación asistida (ADR-027, punto 3) ---


@pytest.mark.regla("A-30")
def test_el_comando_crea_un_enlace_asistido_que_sirve_una_vez(client, caplog):
    crear_maestro(rut=RUT_MAESTRO)
    caplog.set_level(logging.INFO)
    salida = io.StringIO()

    call_command("crear_enlace_recuperacion", "--cuenta", "10.000.013-K", stdout=salida)

    token = re.search(r"#t=([A-Za-z0-9_-]+)", salida.getvalue()).group(1)
    assert SolicitudRecuperacion.objects.get().via == "asistida"
    assert all(token not in r.getMessage() for r in caplog.records)
    assert post_json(client, URL_RESTABLECER, {"token": token, "contrasena_nueva": NUEVA}).status_code == 200
    assert iniciar_sesion(Client(), RUT_MAESTRO, NUEVA).status_code == 200


def test_el_comando_con_una_cuenta_inexistente_falla_sin_crear_nada():
    with pytest.raises(CommandError, match="No existe una cuenta"):
        call_command("crear_enlace_recuperacion", "--cuenta", "nadie@example.com", stdout=io.StringIO())

    assert not SolicitudRecuperacion.objects.exists()


def test_el_enlace_usa_la_direccion_publica_configurada(settings):
    settings.ALTIRO_URL_PUBLICA = "https://altiro.example"

    assert recuperacion.enlace("abc") == "https://altiro.example/nueva-contrasena.html#t=abc"
