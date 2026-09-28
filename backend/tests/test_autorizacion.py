"""Autorización centralizada sobre el recurso ficticio (RNF-07, CA-25.3, RF-02; ADR-010, ADR-011, ADR-013 punto 2).

Sin ``transaction=True``: las filas de ``acceso_denegado`` se revierten con la
transacción de cada prueba.
"""
import uuid

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import Client

from autorizacion.decoradores import requiere_rol
from autorizacion.middleware import MENSAJE_SIN_ROL
from autorizacion.models import RegistroAccesoDenegado
from comun.api import publica
from identidad import servicios
from identidad.models import Rol
from tests.ayudas import CONTRASENA, crear_cliente, crear_maestro, iniciar_sesion, sin_texto_prohibido
from tests.recurso_prueba.models import RecursoPrueba

pytestmark = pytest.mark.django_db

PATRON_RECURSO = "GET api/prueba/recursos/<uuid:ref>"
URL_SOLO_CURATORIA = "/api/prueba/solo-curatoria"


def _url(ref):
    return f"/api/prueba/recursos/{ref}"


def _curatoria(correo="cura@example.com"):
    return servicios.crear_cuenta_administrativa(
        nombre="Cura Prueba", correo=correo, roles=[Rol.CURATORIA], contrasena=CONTRASENA
    )


def _sesion(identificador):
    client = Client()
    assert iniciar_sesion(client, identificador).status_code == 200
    return client


@pytest.fixture
def dueno():
    return crear_cliente()


@pytest.fixture
def recurso(dueno):
    return RecursoPrueba.objects.create(dueno=dueno)


# --- Recurso por referencia (CA-25.3, RNF-07, ADR-011) ---


def test_el_dueno_accede_y_no_se_registra_nada(recurso):
    respuesta = _sesion("ana.prueba@example.com").get(_url(recurso.ref))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"recurso": {"ref": str(recurso.ref)}}
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.terceros("prueba_recurso")
def test_recurso_ajeno_responde_el_mismo_404_que_uno_inexistente_y_se_registra(recurso):
    otro = crear_maestro()
    client = _sesion("11.111.111-1")

    ajeno = client.get(_url(recurso.ref) + "?dato=consulta")
    inexistente = client.get(_url(uuid.uuid4()))
    ruta_inexistente = client.get("/api/no-existe")

    assert ajeno.status_code == inexistente.status_code == 404
    assert ajeno.content == inexistente.content == ruta_inexistente.content
    assert ajeno["Content-Type"] == inexistente["Content-Type"]
    assert sin_texto_prohibido(ajeno)
    fila = RegistroAccesoDenegado.objects.get()
    assert fila.usuario_id == otro.pk
    assert fila.recurso == PATRON_RECURSO  # patrón, sin la ruta cruda ni la consulta
    assert fila.entidad == "recurso_prueba"
    assert fila.entidad_ref == str(recurso.ref)
    assert fila.fecha is not None


@pytest.mark.terceros("prueba_recurso")
def test_un_uuid_inexistente_no_se_registra(recurso):
    crear_maestro()

    respuesta = _sesion("11.111.111-1").get(_url(uuid.uuid4()))

    assert respuesta.status_code == 404
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.terceros("prueba_recurso")
def test_anonimo_recibe_401_y_no_se_registra(recurso):
    respuesta = Client().get(_url(recurso.ref))

    assert respuesta.status_code == 401
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.terceros("prueba_recurso")
def test_tener_el_rol_curatoria_no_da_acceso_a_un_recurso_sin_relacion(recurso):
    # ADR-013, punto 2: el rol es necesario, no suficiente.
    admin = _curatoria()

    respuesta = _sesion("cura@example.com").get(_url(recurso.ref))

    assert respuesta.status_code == 404
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad_ref) == (admin.pk, str(recurso.ref))


# --- Rol requerido (HU-25, ADR-011, punto 2) ---


def test_sin_el_rol_responde_403_accionable_y_se_registra_sin_referencia(dueno):
    respuesta = _sesion("ana.prueba@example.com").get(URL_SOLO_CURATORIA, HTTP_X_ROL="curatoria")

    assert respuesta.status_code == 403
    assert respuesta.json() == {"mensaje": MENSAJE_SIN_ROL, "errores": {}}
    assert sin_texto_prohibido(respuesta)
    fila = RegistroAccesoDenegado.objects.get()
    assert fila.usuario_id == dueno.pk
    assert fila.recurso == "GET api/prueba/solo-curatoria"
    assert fila.entidad_ref is None


def test_con_el_rol_responde_200_y_no_se_registra():
    _curatoria()

    respuesta = _sesion("cura@example.com").get(URL_SOLO_CURATORIA)

    assert respuesta.status_code == 200
    assert not RegistroAccesoDenegado.objects.exists()


def test_el_rol_se_lee_de_la_bd_para_una_cuenta_con_varios_roles():
    maestro = crear_maestro(correo="mae1@example.com")
    client = _sesion("mae1@example.com")
    assert client.get(URL_SOLO_CURATORIA).status_code == 403

    servicios.asignar_rol_administrativo(maestro, Rol.CURATORIA)

    assert client.get(URL_SOLO_CURATORIA).status_code == 200


def test_anonimo_en_ruta_con_rol_recibe_401_sin_registro():
    assert Client().get(URL_SOLO_CURATORIA).status_code == 401
    assert not RegistroAccesoDenegado.objects.exists()


def test_requiere_rol_sobre_una_vista_publica_falla_al_decorar():
    def vista(request):
        return None

    with pytest.raises(ImproperlyConfigured):
        requiere_rol("curatoria")(publica(vista))


def test_publica_sobre_una_vista_con_rol_falla_al_decorar():
    def vista(request):
        return None

    with pytest.raises(ImproperlyConfigured):
        publica(requiere_rol("curatoria")(vista))


@pytest.mark.parametrize("roles", [(), ("visitante",), ("sistema",)])
def test_requiere_rol_exige_roles_definidos(roles):
    with pytest.raises(ImproperlyConfigured):
        requiere_rol(*roles)
