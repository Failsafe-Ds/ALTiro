"""Modelo de identidad y restricciones de la base de datos (ADR-001, ADR-003, ADR-013).

Estas pruebas escriben directamente con el ORM, saltando los servicios, para
comprobar lo que garantiza la BD por sí sola (ADR-013, punto 9 y Enmienda E-6).
"""
import io

import pytest
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DataError, IntegrityError, connection, transaction
from django.db.models import ProtectedError

from identidad.models import PerfilCliente, PerfilMaestro, Rol, Usuario, UsuarioRol

TEL_A = "+56910000001"
TEL_B = "+56910000002"


def _usuario(**campos):
    datos = {"nombre": "Persona Prueba", "telefono": TEL_A, "correo": None}
    datos.update(campos)
    return Usuario.objects.create(**datos)


def _falla_en_bd(funcion, errores=IntegrityError):
    with pytest.raises(errores):
        with transaction.atomic():
            funcion()


# --- Configuración (ADR-001) ---


def test_auth_user_model_es_el_usuario_propio():
    assert settings.AUTH_USER_MODEL == "identidad.Usuario"
    assert get_user_model() is Usuario


def test_usuario_sin_permissions_mixin_ni_campos_de_roles_de_django():
    # django.contrib.auth.models no se importa: requiere auth instalada.
    assert "PermissionsMixin" not in {clase.__name__ for clase in Usuario.__mro__}
    assert "AbstractBaseUser" in {clase.__name__ for clase in Usuario.__mro__}
    nombres = {campo.name for campo in Usuario._meta.get_fields()}
    assert not nombres & {"is_superuser", "is_staff", "groups", "user_permissions"}


def test_no_se_instalan_admin_auth_ni_contenttypes():
    for etiqueta in ("admin", "auth", "contenttypes"):
        assert not apps.is_installed(f"django.contrib.{etiqueta}")


def test_sesiones_de_django_instaladas_adr_005():
    assert apps.is_installed("django.contrib.sessions")


@pytest.mark.django_db
def test_no_hay_migraciones_pendientes():
    salida = io.StringIO()
    call_command("makemigrations", "--check", "--dry-run", stdout=salida)


RESTRICCIONES_ESPERADAS = {
    "usuario": {"usuario_correo_unico", "usuario_correo_no_vacio", "usuario_telefono_formato"},
    "perfil_maestro": {"perfil_maestro_rut_unico", "perfil_maestro_rut_formato"},
    "usuario_rol": {"usuario_rol_unico", "usuario_rol_valido"},
}


@pytest.mark.django_db
def test_la_bd_tiene_las_siete_restricciones_con_nombre():
    with connection.cursor() as cursor:
        for tabla, esperadas in RESTRICCIONES_ESPERADAS.items():
            nombres = set(connection.introspection.get_constraints(cursor, tabla))
            assert esperadas <= nombres, tabla


@pytest.mark.django_db
def test_no_existen_columnas_sin_respaldo_aprobado():
    # Decisión del equipo: activo, creado_en y asignado_en no entran todavía.
    with connection.cursor() as cursor:
        for tabla in ("usuario", "usuario_rol", "perfil_cliente", "perfil_maestro"):
            columnas = {c.name for c in connection.introspection.get_table_description(cursor, tabla)}
            assert not columnas & {"activo", "creado_en", "asignado_en"}, tabla


@pytest.mark.django_db
def test_tablas_de_identidad_creadas_y_sin_tablas_de_auth():
    tablas = set(connection.introspection.table_names())

    assert {"usuario", "usuario_rol", "perfil_cliente", "perfil_maestro"} <= tablas
    assert not {t for t in tablas if t.startswith(("auth_", "django_content_type"))}
    assert "django_session" in tablas  # ADR-005


# --- Correo (PI-052, PI-053 parcial) ---


def test_clean_no_modifica_el_correo_en_silencio():
    # AbstractBaseUser.clean() aplicaría NFKC al USERNAME_FIELD (HQ-11 abierto).
    correo = "ａna@example.com"  # "a" de ancho completo
    usuario = Usuario(nombre="Ana Prueba", correo=correo)

    usuario.clean()

    assert usuario.correo == correo


@pytest.mark.django_db
def test_pi052_la_bd_rechaza_dos_usuarios_con_el_mismo_correo():
    _usuario(correo="ana.prueba@example.com")

    _falla_en_bd(lambda: _usuario(correo="ana.prueba@example.com"))
    assert Usuario.objects.filter(correo="ana.prueba@example.com").count() == 1


@pytest.mark.django_db
def test_varias_cuentas_pueden_no_tener_correo():
    _usuario(correo=None)
    _usuario(correo=None)

    assert Usuario.objects.filter(correo__isnull=True).count() == 2


@pytest.mark.django_db
def test_pi053_la_bd_rechaza_el_correo_cadena_vacia():
    _falla_en_bd(lambda: _usuario(correo=""))


@pytest.mark.django_db
def test_pi053_sin_check_de_minusculas_la_bd_acepta_un_correo_en_mayusculas():
    # E-6: la normalización la garantiza el servicio; la BD no tiene CHECK de minúsculas.
    usuario = _usuario(correo="Ana.Prueba@EXAMPLE.com")

    usuario.refresh_from_db()
    assert usuario.correo == "Ana.Prueba@EXAMPLE.com"


# --- Teléfono (ADR-013, punto 6 y Enmiendas E-3 y E-6) ---


@pytest.mark.django_db
def test_el_telefono_no_es_unico():
    _usuario(telefono=TEL_B, correo="a@example.com")
    _usuario(telefono=TEL_B, correo="b@example.com")

    assert Usuario.objects.filter(telefono=TEL_B).count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "telefono",
    ["+56 9 1000 0001", "56910000001", "+5691000000", "+569100000011", "", "+5691000000１"],
)
def test_pi134_el_check_rechaza_un_telefono_fuera_de_la_forma_canonica(telefono):
    _falla_en_bd(lambda: _usuario(telefono=telefono, correo="a@example.com"), errores=(IntegrityError, DataError))


@pytest.mark.django_db
@pytest.mark.parametrize("telefono", [None, "+56910000001"])
def test_pi134_la_bd_acepta_null_y_la_forma_canonica(telefono):
    usuario = _usuario(telefono=telefono, correo="a@example.com")

    usuario.refresh_from_db()
    assert usuario.telefono == telefono


# --- RUT (PI-045, PI-046) ---


@pytest.mark.django_db
def test_pi045_la_bd_rechaza_dos_perfiles_de_maestro_con_el_mismo_rut():
    PerfilMaestro.objects.create(usuario=_usuario(), rut="111111111")
    otro = _usuario()

    _falla_en_bd(lambda: PerfilMaestro.objects.create(usuario=otro, rut="111111111"))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rut", ["1111111-1", "1.111.111", "10000013k", "", "-", "K", "1", "１" * 8 + "1"]
)
def test_pi046_el_check_rechaza_un_rut_fuera_de_la_forma_canonica(rut):
    # Valores de largo válido para la columna: los rechaza el CHECK de formato.
    usuario = _usuario()

    _falla_en_bd(lambda: PerfilMaestro.objects.create(usuario=usuario, rut=rut))


@pytest.mark.django_db
@pytest.mark.parametrize("rut", ["11.111.111-1", "11111111-1"])
def test_pi046_la_bd_rechaza_un_rut_con_puntos_o_guion(rut):
    # Más largos que la columna: la BD los rechaza por largo antes que por el CHECK.
    usuario = _usuario()

    _falla_en_bd(
        lambda: PerfilMaestro.objects.create(usuario=usuario, rut=rut), errores=(IntegrityError, DataError)
    )


# --- Roles y perfiles (PI-131, PI-132) ---


@pytest.mark.django_db
def test_pi131_la_bd_rechaza_un_rol_duplicado_para_el_mismo_usuario():
    usuario = _usuario(correo="c@example.com")
    UsuarioRol.objects.create(usuario=usuario, rol=Rol.CURATORIA)

    _falla_en_bd(lambda: UsuarioRol.objects.create(usuario=usuario, rol=Rol.CURATORIA))


@pytest.mark.django_db
def test_pi131_la_bd_rechaza_un_segundo_perfil_de_cliente_para_el_mismo_usuario():
    usuario = _usuario(correo="c@example.com")
    PerfilCliente.objects.create(usuario=usuario, comuna_id=8101)

    _falla_en_bd(lambda: PerfilCliente.objects.create(usuario=usuario, comuna_id=8101))
    assert PerfilCliente.objects.filter(usuario=usuario).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("rol", ["visitante", "sistema", "admin", ""])
def test_pi132_la_bd_rechaza_roles_no_definidos(rol):
    usuario = _usuario(correo="c@example.com")

    _falla_en_bd(lambda: UsuarioRol.objects.create(usuario=usuario, rol=rol))


@pytest.mark.django_db
def test_un_usuario_puede_tener_varios_roles():
    usuario = _usuario(correo="c@example.com")
    UsuarioRol.objects.create(usuario=usuario, rol=Rol.CURATORIA)
    UsuarioRol.objects.create(usuario=usuario, rol=Rol.COMERCIAL)

    assert set(usuario.roles.values_list("rol", flat=True)) == {"curatoria", "comercial"}


# --- Trazabilidad y privacidad ---


@pytest.mark.django_db
def test_borrar_un_usuario_con_perfil_o_rol_no_borra_en_cascada():
    usuario = _usuario()
    PerfilMaestro.objects.create(usuario=usuario, rut="111111111")
    UsuarioRol.objects.create(usuario=usuario, rol=Rol.MAESTRO)

    with pytest.raises(ProtectedError):
        usuario.delete()
    assert PerfilMaestro.objects.filter(usuario=usuario).exists()


@pytest.mark.django_db
def test_la_representacion_textual_no_incluye_datos_personales():
    usuario = _usuario(nombre="Ana Prueba", correo="ana.prueba@example.com")
    perfil = PerfilMaestro.objects.create(usuario=usuario, rut="111111111")
    textos = str(usuario) + str(perfil)

    for dato in ("Ana", "ana.prueba@example.com", "111111111", TEL_A):
        assert dato not in textos
