"""Registro de cliente (RF-01, HU-01) y postulación de maestro, paso 1 (RF-03, HU-11).

ADR-013 (puntos 2, 5, 6 y 7; Enmiendas E-1, E-2, E-7 y E-8), ADR-012 y
propuesta del S1, §4. Los identificadores PI-xxx son del plan de pruebas.
"""
import json

import pytest
from django.test import Client

from identidad.models import PerfilCliente, PerfilMaestro, Rol, Usuario, UsuarioRol
from identidad.servicios import verificar_invariantes
from tests.ayudas import (
    CONTRASENA,
    TEL_B,
    URL_CLIENTES,
    URL_CUENTA,
    URL_POSTULACIONES,
    crear_cliente,
    crear_maestro,
    datos_cliente,
    datos_maestro,
    iniciar_sesion,
    post_json,
    sin_texto_prohibido,
)


@pytest.fixture(autouse=True)
def invariantes_al_final(request):
    """PI-130: al terminar cada prueba, todas las cuentas cumplen ADR-013 §9."""
    yield
    if request.node.get_closest_marker("django_db") is None:
        return
    for usuario in Usuario.objects.all():
        assert verificar_invariantes(usuario) == [], f"usuario {usuario.pk}"


def _roles(usuario):
    return set(UsuarioRol.objects.filter(usuario=usuario).values_list("rol", flat=True))


def _con_sesion(client, identificador):
    assert iniciar_sesion(client, identificador).status_code == 200
    return client


# --- A. Registro de cliente sin sesión ---


@pytest.mark.django_db
def test_pi001_registro_valido_crea_cuenta_perfil_rol_y_comuna(client):
    respuesta = post_json(client, URL_CLIENTES, datos_cliente())

    assert respuesta.status_code == 201
    usuario = Usuario.objects.get()
    assert usuario.correo == "ana.prueba@example.com"
    assert usuario.telefono == "+56910000001"
    assert _roles(usuario) == {Rol.CLIENTE}
    assert PerfilCliente.objects.get(usuario=usuario).comuna_id == 8101


@pytest.mark.django_db
@pytest.mark.parametrize("campo", ["nombre", "telefono", "correo", "contrasena"])
def test_pi002_a_pi006_campo_obligatorio_ausente_responde_400_en_el_campo(client, campo):
    respuesta = post_json(client, URL_CLIENTES, datos_cliente(**{campo: None}))

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {campo}
    assert Usuario.objects.count() == 0


@pytest.mark.django_db
def test_pi007_ca011_sin_comuna_se_impide_guardar_e_indica_que_es_obligatoria(client):
    respuesta = post_json(client, URL_CLIENTES, datos_cliente(comuna=None))

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"comuna": "Elige tu comuna para continuar."}
    assert Usuario.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("comuna", ["99999", "8101; DROP TABLE comuna", 3.5, ["8101"], ""])
def test_pi008_comuna_fuera_de_la_lista_cerrada_se_rechaza(client, comuna):
    respuesta = post_json(client, URL_CLIENTES, datos_cliente(comuna=comuna))

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"comuna"}
    assert Usuario.objects.count() == 0


@pytest.mark.django_db
def test_la_comuna_puede_enviarse_como_numero(client):
    assert post_json(client, URL_CLIENTES, datos_cliente(comuna=8101)).status_code == 201


@pytest.mark.django_db
def test_se_informan_todos_los_campos_con_error_a_la_vez(client):
    respuesta = post_json(
        client, URL_CLIENTES, {"nombre": "", "telefono": "12", "correo": "ana@", "contrasena": "corta", "comuna": "1"}
    )

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"nombre", "telefono", "correo", "contrasena", "comuna"}


@pytest.mark.django_db
@pytest.mark.parametrize("extra", [{"roles": ["curatoria"]}, {"es_administrador": True}, {"id": 1}, {"<script>": "x"}])
def test_pi010_pi273_clave_desconocida_responde_400_general_sin_repetirla(client, extra):
    respuesta = post_json(client, URL_CLIENTES, {**datos_cliente(), **extra})

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["errores"] == {}
    assert "no usa" in cuerpo["mensaje"]
    for clave in extra:
        assert clave not in respuesta.content.decode("utf-8")
    assert Usuario.objects.count() == 0


@pytest.mark.django_db
def test_pi011_sin_token_csrf_responde_403_y_no_crea_nada():
    cliente_http = Client(enforce_csrf_checks=True)

    respuesta = post_json(cliente_http, URL_CLIENTES, datos_cliente())

    assert respuesta.status_code == 403
    assert "Recarga la página" in respuesta.json()["mensaje"]
    assert Usuario.objects.count() == 0


@pytest.mark.django_db
def test_con_token_csrf_el_registro_funciona():
    cliente_http = Client(enforce_csrf_checks=True)
    cliente_http.get("/api/sesion/csrf")
    token = cliente_http.cookies["csrftoken"].value

    respuesta = post_json(cliente_http, URL_CLIENTES, datos_cliente(), HTTP_X_CSRFTOKEN=token)

    assert respuesta.status_code == 201


@pytest.mark.django_db
def test_pi012_la_respuesta_no_contiene_la_contrasena_ni_el_hash(client):
    respuesta = post_json(client, URL_CLIENTES, datos_cliente())

    texto = respuesta.content.decode("utf-8")
    assert CONTRASENA not in texto
    assert "argon2" not in texto


@pytest.mark.django_db
def test_pi013_el_registro_no_inicia_sesion(client):
    respuesta = post_json(client, URL_CLIENTES, datos_cliente())

    assert respuesta.status_code == 201
    assert "sessionid" not in respuesta.cookies
    assert client.get(URL_CUENTA).status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("campo, valor", [("rut", "11.111.111-1"), ("identificador", "ana@example.com")])
def test_pi014_campo_conocido_no_permitido_sin_sesion_responde_400_en_ese_campo(client, campo, valor):
    respuesta = post_json(client, URL_CLIENTES, {**datos_cliente(), campo: valor})

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {campo}
    assert Usuario.objects.count() == 0


@pytest.mark.django_db
def test_pi051_correo_repetido_con_otras_mayusculas_responde_400_en_correo(client):
    crear_cliente(correo="ana.prueba@example.com")

    respuesta = post_json(client, URL_CLIENTES, datos_cliente(correo="Ana.Prueba@EXAMPLE.com", telefono=TEL_B))

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"correo"}
    assert sin_texto_prohibido(respuesta)
    assert Usuario.objects.count() == 1


@pytest.mark.django_db
def test_pi060_telefono_repetido_crea_otra_cuenta_sin_unirlas(client):
    existente = crear_cliente(correo="a@example.com")

    respuesta = post_json(client, URL_CLIENTES, datos_cliente(correo="b@example.com"))

    assert respuesta.status_code == 201
    assert Usuario.objects.count() == 2
    assert Usuario.objects.exclude(pk=existente.pk).get().correo == "b@example.com"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "cuerpo, tipo",
    [
        ("no es json", "application/json"),
        ("[1, 2]", "application/json"),
        ('{"a": 1}', "text/plain"),
        (b"\xff", "application/json"),
    ],
)
def test_pi271_cuerpo_invalido_responde_400_general(client, cuerpo, tipo):
    respuesta = client.post(URL_CLIENTES, data=cuerpo, content_type=tipo)

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {}
    assert sin_texto_prohibido(respuesta)


@pytest.mark.django_db
def test_pi165_contrasena_con_sustituto_aislado_responde_400_nunca_500(client):
    cuerpo = json.dumps(datos_cliente()).replace(CONTRASENA, "clave de prueba \\ud800 segura")

    respuesta = client.post(URL_CLIENTES, data=cuerpo, content_type="application/json")

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"contrasena"}
    assert Usuario.objects.count() == 0


@pytest.mark.django_db
def test_texto_con_sustituto_aislado_en_otro_campo_responde_400_en_ese_campo(client):
    cuerpo = json.dumps(datos_cliente()).replace("Ana Prueba", "Ana \\udfff Prueba")

    respuesta = client.post(URL_CLIENTES, data=cuerpo, content_type="application/json")

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"nombre"}


@pytest.mark.django_db
def test_pi154_contrasena_enorme_responde_400_sin_invocar_el_hasher(client, monkeypatch):
    llamadas = []
    monkeypatch.setattr("identidad.hashers.Argon2idAlTiro.encode", lambda *a, **k: llamadas.append(1))

    respuesta = post_json(client, URL_CLIENTES, datos_cliente(contrasena="x" * 10_000))

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"contrasena"}
    assert llamadas == []


# --- B. Postulación de maestro sin sesión ---


@pytest.mark.django_db
def test_pi020_postulacion_sin_correo_crea_maestro_con_correo_nulo(client):
    respuesta = post_json(client, URL_POSTULACIONES, datos_maestro())

    assert respuesta.status_code == 201
    usuario = Usuario.objects.get()
    assert usuario.correo is None
    assert _roles(usuario) == {Rol.MAESTRO}
    assert PerfilMaestro.objects.get(usuario=usuario).rut == "111111111"


@pytest.mark.django_db
def test_pi021_correo_opcional_se_normaliza(client):
    respuesta = post_json(client, URL_POSTULACIONES, datos_maestro(correo=" Mae1@Example.COM "))

    assert respuesta.status_code == 201
    assert Usuario.objects.get().correo == "mae1@example.com"


@pytest.mark.django_db
@pytest.mark.parametrize("campo", ["rut", "nombre", "telefono", "contrasena"])
def test_pi022_campo_obligatorio_ausente(client, campo):
    respuesta = post_json(client, URL_POSTULACIONES, datos_maestro(**{campo: None}))

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {campo}
    assert Usuario.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("rut", ["11.111.111-2", "10.000.013-1"])
def test_pi023_rut_con_dv_incorrecto(client, rut):
    respuesta = post_json(client, URL_POSTULACIONES, datos_maestro(rut=rut))

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"rut"}


@pytest.mark.django_db
@pytest.mark.parametrize("rut", ["11.111.111-1", "111111111", "11111111-1"])
def test_pi024_pi025_ca113_rut_ya_registrado_indica_que_tiene_una_postulacion(client, rut):
    crear_maestro(rut="11.111.111-1")

    respuesta = post_json(client, URL_POSTULACIONES, datos_maestro(rut=rut, telefono=TEL_B))

    assert respuesta.status_code == 400
    assert "ya tiene una postulación" in respuesta.json()["errores"]["rut"]
    assert Usuario.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("correo", ["", "   "])
def test_pi028_correo_vacio_en_postulacion_responde_400(client, correo):
    respuesta = post_json(client, URL_POSTULACIONES, datos_maestro(correo=correo))

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"correo"}
    assert Usuario.objects.count() == 0


@pytest.mark.django_db
def test_pi029_la_postulacion_no_inicia_sesion(client):
    assert post_json(client, URL_POSTULACIONES, datos_maestro()).status_code == 201

    assert client.get(URL_CUENTA).status_code == 401


@pytest.mark.django_db
# "activo" es un campo conocido desde el catálogo del S3 (ADR-018): aquí no está
# permitido y se informa en su campo; una clave desconocida sigue siendo error general.
@pytest.mark.parametrize(
    "extra, errores",
    [({"comuna": "8101"}, {"comuna"}), ({"es_administrador": True}, set()), ({"activo": True}, {"activo"})],
)
def test_pi030_campos_no_permitidos_en_la_postulacion(client, extra, errores):
    respuesta = post_json(client, URL_POSTULACIONES, {**datos_maestro(), **extra})

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == errores
    assert Usuario.objects.count() == 0


# --- G. Agregar un segundo perfil con sesión (ADR-013, punto 2) ---


@pytest.mark.django_db
def test_pi080_cliente_autenticado_postula_solo_con_rut_y_conserva_su_cuenta(client):
    cliente = crear_cliente()
    _con_sesion(client, "ana.prueba@example.com")

    respuesta = post_json(client, URL_POSTULACIONES, {"rut": "22.222.222-2"})

    assert respuesta.status_code == 201
    assert Usuario.objects.count() == 1
    assert _roles(cliente) == {Rol.CLIENTE, Rol.MAESTRO}
    assert respuesta.json()["cuenta"]["perfil_maestro"] == {"rut": "222222222"}


@pytest.mark.django_db
@pytest.mark.parametrize("campo, valor", [("telefono", TEL_B), ("nombre", "Otro"), ("contrasena", "otra clave distinta")])
def test_pi081_con_sesion_no_se_admiten_otros_datos(client, campo, valor):
    cliente = crear_cliente()
    _con_sesion(client, "ana.prueba@example.com")

    respuesta = post_json(client, URL_POSTULACIONES, {"rut": "22.222.222-2", campo: valor})

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {campo}
    assert _roles(cliente) == {Rol.CLIENTE}


@pytest.mark.django_db
def test_pi084_cuenta_que_ya_es_maestro_no_puede_postular_de_nuevo(client):
    crear_maestro(correo="mae1@example.com")
    _con_sesion(client, "mae1@example.com")

    respuesta = post_json(client, URL_POSTULACIONES, {"rut": "22.222.222-2"})

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"]["perfil"] == "Ya postulaste como maestro con esta cuenta."


@pytest.mark.django_db
def test_pi090_maestro_con_correo_agrega_perfil_de_cliente_solo_con_comuna(client):
    maestro = crear_maestro(correo="mae1@example.com")
    _con_sesion(client, "11.111.111-1")

    respuesta = post_json(client, URL_CLIENTES, {"comuna": "8110"})

    assert respuesta.status_code == 201
    assert _roles(maestro) == {Rol.MAESTRO, Rol.CLIENTE}
    assert respuesta.json()["cuenta"]["perfil_cliente"]["comuna"] == {"codigo": 8110, "nombre": "Talcahuano"}


@pytest.mark.django_db
@pytest.mark.parametrize("correo", ["otro@example.com", "mae1@example.com"])
def test_pi091_maestro_con_correo_que_envia_correo_recibe_400_y_no_cambia(client, correo):
    maestro = crear_maestro(correo="mae1@example.com")
    _con_sesion(client, "mae1@example.com")

    respuesta = post_json(client, URL_CLIENTES, {"comuna": "8101", "correo": correo})

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"correo"}
    maestro.refresh_from_db()
    assert maestro.correo == "mae1@example.com"
    assert _roles(maestro) == {Rol.MAESTRO}


@pytest.mark.django_db
def test_pi092_maestro_sin_correo_agrega_perfil_de_cliente_con_su_primer_correo(client):
    maestro = crear_maestro()
    _con_sesion(client, "11.111.111-1")

    respuesta = post_json(client, URL_CLIENTES, {"comuna": "8101", "correo": " Nuevo@Example.com "})

    assert respuesta.status_code == 201
    maestro.refresh_from_db()
    assert maestro.correo == "nuevo@example.com"
    # PI-098: después se puede entrar con el correo nuevo y con el RUT.
    otro = Client()
    assert iniciar_sesion(otro, "nuevo@example.com").status_code == 200


@pytest.mark.django_db
def test_pi093_maestro_sin_correo_que_no_envia_correo_recibe_400(client):
    maestro = crear_maestro()
    _con_sesion(client, "11.111.111-1")

    respuesta = post_json(client, URL_CLIENTES, {"comuna": "8101"})

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"correo"}
    assert _roles(maestro) == {Rol.MAESTRO}


@pytest.mark.django_db
def test_pi099_cuenta_que_ya_es_cliente_recibe_400(client):
    crear_cliente()
    _con_sesion(client, "ana.prueba@example.com")

    respuesta = post_json(client, URL_CLIENTES, {"comuna": "8101"})

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"]["perfil"] == "Tu cuenta ya puede pedir trabajos."


@pytest.mark.django_db
def test_pi100_con_sesion_sin_comuna_responde_400_en_comuna(client):
    crear_maestro(correo="mae1@example.com")
    _con_sesion(client, "mae1@example.com")

    respuesta = post_json(client, URL_CLIENTES, {})

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"comuna"}


# --- Q. Autorización básica ---


@pytest.mark.django_db
def test_pi290_sin_sesion_solo_con_comuna_no_toca_cuentas_existentes(client):
    existente = crear_cliente()

    respuesta = post_json(client, URL_CLIENTES, {"comuna": "8101"})

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) >= {"nombre", "telefono", "correo", "contrasena"}
    assert Usuario.objects.get() == existente


@pytest.mark.django_db
def test_pi293_el_rol_enviado_por_el_cliente_no_tiene_efecto(client):
    cliente = crear_cliente()
    _con_sesion(client, "ana.prueba@example.com")

    respuesta = post_json(client, URL_POSTULACIONES, {"rut": "22.222.222-2", "rol": "curatoria"})
    respuesta_cabecera = post_json(client, URL_POSTULACIONES, {"rut": "22.222.222-2"}, HTTP_ROL="curatoria")

    assert respuesta.status_code == 400
    assert respuesta_cabecera.status_code == 201
    assert _roles(cliente) == {Rol.CLIENTE, Rol.MAESTRO}
