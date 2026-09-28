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


# --- Rastro de la asignación de roles (ADR-010, «Decisión», punto 7) ---

_LOGGER = "identidad.management.commands.crear_usuario_administrativo"


def _eventos(caplog):
    return [r.getMessage() for r in caplog.records if r.name == _LOGGER]


@pytest.mark.django_db
def test_crear_cuenta_registra_evento_por_rol_sin_datos_personales(contrasena_oculta, caplog):
    caplog.set_level("INFO", logger=_LOGGER)

    _ejecutar("--nombre", "Admin Prueba", "--correo", "admin@example.com", "--rol", "curatoria", "--rol", "comercial")

    usuario = Usuario.objects.get()
    eventos = _eventos(caplog)
    assert len(eventos) == 2
    assert any(f"usuario {usuario.pk}" in e and "rol comercial" in e for e in eventos)
    assert any(f"usuario {usuario.pk}" in e and "rol curatoria" in e for e in eventos)
    todo = " ".join(r.getMessage() for r in caplog.records)
    for prohibido in (CONTRASENA, "admin@example.com", "Admin Prueba", "sistema", "Sistema"):
        assert prohibido not in todo
    assert all(r.asignado_en is not None for r in UsuarioRol.objects.filter(usuario=usuario))


@pytest.mark.django_db
def test_agregar_rol_registra_evento_con_usuario_y_rol(caplog):
    maestro = crear_maestro()
    caplog.set_level("INFO", logger=_LOGGER)

    _ejecutar("--agregar-a", "11.111.111-1", "--rol", "moderacion")

    assert _eventos(caplog) == [f"Rol administrativo asignado por comando de consola: usuario {maestro.pk}, rol moderacion."]
    todo = " ".join(r.getMessage() for r in caplog.records)
    assert "111111111" not in todo and "sistema" not in todo.lower()


@pytest.mark.django_db
def test_si_la_asignacion_falla_no_se_registra_evento(contrasena_oculta, caplog):
    caplog.set_level("INFO", logger=_LOGGER)

    with pytest.raises(CommandError):
        _ejecutar("--nombre", "Admin", "--rol", "curatoria")

    assert _eventos(caplog) == []
