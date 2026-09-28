"""Comando crear_usuario_administrativo (ADR-013, punto 8; plan de pruebas, sección H)."""
import io

import pytest
from django.core.management import CommandError, call_command
from django.test import Client

from identidad.models import Rol, Usuario, UsuarioRol
from tests.ayudas import CONTRASENA, crear_maestro, iniciar_sesion

COMANDO = "crear_usuario_administrativo"


@pytest.fixture
def contrasena_oculta(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda texto="": CONTRASENA)


def _ejecutar(*argumentos):
    salida = io.StringIO()
    call_command(COMANDO, *argumentos, stdout=salida, stderr=salida)
    return salida.getvalue()


@pytest.mark.django_db
def test_pi112_crea_cuenta_administrativa_con_varios_roles_sin_perfiles(contrasena_oculta):
    salida = _ejecutar("--nombre", "Admin Prueba", "--correo", "Admin@Example.com", "--rol", "curatoria", "--rol", "comercial")

    usuario = Usuario.objects.get()
    assert usuario.correo == "admin@example.com"
    assert set(UsuarioRol.objects.filter(usuario=usuario).values_list("rol", flat=True)) == {"curatoria", "comercial"}
    assert usuario.telefono is None  # PI-111
    assert CONTRASENA not in salida  # PI-117
    assert iniciar_sesion(Client(), "admin@example.com").status_code == 200  # PI-114


@pytest.mark.django_db
def test_pi110_sin_correo_no_se_crea(contrasena_oculta):
    with pytest.raises(CommandError):
        _ejecutar("--nombre", "Admin Prueba", "--rol", "curatoria")

    assert Usuario.objects.count() == 0


@pytest.mark.django_db
def test_pi113_no_asigna_roles_de_cliente_ni_maestro(contrasena_oculta):
    with pytest.raises(CommandError):
        _ejecutar("--nombre", "Admin", "--correo", "admin@example.com", "--rol", "cliente")

    assert Usuario.objects.count() == 0


@pytest.mark.django_db
def test_la_politica_de_contrasena_se_aplica_en_el_comando(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda texto="": "corta")

    with pytest.raises(CommandError, match="contrasena"):
        _ejecutar("--nombre", "Admin", "--correo", "admin@example.com", "--rol", "curatoria")

    assert Usuario.objects.count() == 0


@pytest.mark.django_db
def test_contrasenas_distintas_no_crean_la_cuenta(monkeypatch):
    respuestas = iter([CONTRASENA, "otra clave de prueba"])
    monkeypatch.setattr("getpass.getpass", lambda texto="": next(respuestas))

    with pytest.raises(CommandError, match="no coinciden"):
        _ejecutar("--nombre", "Admin", "--correo", "admin@example.com", "--rol", "curatoria")


def test_la_contrasena_no_se_acepta_como_argumento():
    with pytest.raises(CommandError):
        call_command(COMANDO, "--contrasena", "x", "--rol", "curatoria")


@pytest.mark.django_db
def test_pi115_agrega_un_rol_administrativo_a_un_maestro_existente_por_rut():
    maestro = crear_maestro()

    _ejecutar("--agregar-a", "11.111.111-1", "--rol", "curatoria")

    assert set(UsuarioRol.objects.filter(usuario=maestro).values_list("rol", flat=True)) == {Rol.MAESTRO, Rol.CURATORIA}


@pytest.mark.django_db
def test_agregar_a_una_cuenta_inexistente_falla():
    with pytest.raises(CommandError, match="No existe"):
        _ejecutar("--agregar-a", "nadie@example.com", "--rol", "curatoria")
