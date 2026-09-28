"""Trazas seguras en los registros de la aplicación (ADR-003, Enmienda E-2; DEF-QA-007).

Sin ``transaction=True``: las excepciones de base de datos se provocan dentro
de ``transaction.atomic()`` y las filas se revierten con la transacción de cada
prueba (la de la bitácora incluida).
"""
import io
import logging
import sys

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import Client, RequestFactory

from comun.registros import (
    LARGO_MAXIMO_MENSAJE,
    FiltroTrazasSeguras,
    describir_excepcion,
    formatear_traza_segura,
)
from identidad import servicios
from identidad.models import Usuario
from tests.ayudas import CONTRASENA, URL_CLIENTES, crear_cliente, datos_cliente, post_json

NOMBRE = "Nombre Ficticio Registro"
CORREO = "registro.def007@example.com"
TELEFONO_INVALIDO = "+00910000078"  # 12 caracteres, viola usuario_telefono_formato
CORREO_EXISTENTE = "ana.prueba@example.com"  # el de crear_cliente()
SESION = "sesionficticia0123456789abcdef"
CSRF = "csrfficticio0123456789abcdefABCDEF"


def _consola():
    return next(h for h in logging.getLogger().handlers if h.get_name() == "consola")


def _capturar(excepcion_esperada, funcion):
    """Ejecuta ``funcion`` dentro de ``transaction.atomic()`` y devuelve la excepción."""
    with pytest.raises(excepcion_esperada) as error:
        with transaction.atomic():
            funcion()
    return error.value


def _exc_info(exc):
    return (type(exc), exc, exc.__traceback__)


def _traza(exc):
    return formatear_traza_segura(_exc_info(exc))


def _sql(sentencia, parametros=()):
    with connection.cursor() as cursor:
        cursor.execute(sentencia, parametros)
        return cursor.fetchone() if cursor.description else None


def _violar_check():
    usuario = Usuario(nombre=NOMBRE, telefono=TELEFONO_INVALIDO, correo=CORREO)
    usuario.set_password(CONTRASENA)
    usuario.save(force_insert=True)


def _violar_unicidad():
    usuario = Usuario(nombre=NOMBRE, correo=CORREO_EXISTENTE)
    usuario.set_password(CONTRASENA)
    usuario.save(force_insert=True)


def _registro(exc=None, request=None, msg="Internal Server Error: %s", args=("/api/clientes",)):
    extra = {"status_code": 500}
    if request is not None:
        extra["request"] = request
    return logging.getLogger("django.request").makeRecord(
        "django.request", logging.ERROR, __file__, 1, msg, args,
        _exc_info(exc) if exc is not None else None, extra=extra,
    )


def _request_con_secretos():
    peticion = RequestFactory().post(
        URL_CLIENTES,
        data=f'{{"correo": "{CORREO}", "contrasena": "{CONTRASENA}"}}',
        content_type="application/json",
        HTTP_X_CSRFTOKEN=CSRF,
    )
    peticion.COOKIES = {"sessionid": SESION, "csrftoken": CSRF}
    return peticion


# --- Salida textual final, con el handler y el formatter reales ---


@pytest.mark.django_db
def test_el_handler_consola_escribe_la_traza_segura_del_500(monkeypatch):
    monkeypatch.setattr(servicios, "normalizar_telefono", lambda telefono: TELEFONO_INVALIDO)
    salida = io.StringIO()
    consola = _consola()
    anterior = consola.setStream(salida)
    try:
        respuesta = post_json(
            Client(raise_request_exception=False), URL_CLIENTES, datos_cliente(nombre=NOMBRE, correo=CORREO)
        )
    finally:
        consola.setStream(anterior)

    assert respuesta.status_code == 500
    texto = salida.getvalue()
    assert "ERROR django.request Internal Server Error: /api/clientes" in texto
    assert "Contexto: método=POST estado=500" in texto
    for presente in (
        "Traceback (most recent call last):", "psycopg.errors.CheckViolation", "django.db.utils.IntegrityError",
        "sqlstate=23514", "restriccion=usuario_telefono_formato", "tabla=usuario", "servicios.py",
        "The above exception was the direct cause of the following exception:",
    ):
        assert presente in texto, presente
    for ausente in (
        "DETAIL", "Failing row", NOMBRE, CORREO, TELEFONO_INVALIDO, "+56 9 1000 0001", CONTRASENA,
        "argon2", "INSERT INTO", "sessionid", "csrftoken",
    ):
        assert ausente not in texto, ausente


# --- Excepciones reales de la base de datos ---


@pytest.mark.django_db
def test_check_conserva_sqlstate_y_restriccion_sin_la_fila():
    exc = _capturar(IntegrityError, _violar_check)

    traza = _traza(exc)

    assert "sqlstate=23514" in traza
    assert "restriccion=usuario_telefono_formato" in traza
    assert 'violates check constraint "usuario_telefono_formato"' in traza  # mensaje primario, clase 23
    for ausente in ("DETAIL", "Failing row", NOMBRE, CORREO, TELEFONO_INVALIDO, "argon2"):
        assert ausente not in traza, ausente


@pytest.mark.django_db
def test_unicidad_conserva_la_restriccion_sin_la_clave_ni_el_correo():
    crear_cliente()
    exc = _capturar(IntegrityError, _violar_unicidad)

    traza = _traza(exc)

    assert "psycopg.errors.UniqueViolation" in traza
    assert "sqlstate=23505" in traza
    assert "restriccion=usuario_correo_unico" in traza
    for ausente in ("DETAIL", "Key (correo)=", CORREO_EXISTENTE, NOMBRE, "argon2"):
        assert ausente not in traza, ausente


@pytest.mark.django_db
def test_conversion_invalida_omite_el_valor_y_el_mensaje():
    # El valor va como parámetro: la línea de código de la traza no lo contiene.
    valor = "".join(["a", "b", "c"])
    exc = _capturar(DatabaseError, lambda: _sql("SELECT %s::int", [valor]))

    traza = _traza(exc)

    assert "22P02" in traza
    assert "abc" not in traza
    assert "invalid input syntax" not in traza
    assert "mensaje=" not in traza  # fuera de la clase 23 y de 42501, sin mensaje primario


@pytest.mark.django_db
def test_trigger_de_la_bitacora_conserva_su_mensaje():
    (pk,) = _sql(
        "INSERT INTO bitacora (fecha, autor_tipo, autor_id, accion, entidad, entidad_ref, motivo) "
        "VALUES (now(), 'sistema', NULL, 'prueba', 'expediente', 'ref-1', 'Motivo de prueba') RETURNING id"
    )
    exc = _capturar(DatabaseError, lambda: _sql("UPDATE bitacora SET motivo = 'otro' WHERE id = %s", [pk]))

    traza = _traza(exc)

    assert "sqlstate=42501" in traza
    assert "La bitácora no admite UPDATE (RNF-11)" in traza


def test_error_de_bd_sin_diagnostico_omite_el_mensaje():
    exc = DatabaseError(f"Failing row contains ({CORREO})")

    descripcion = describir_excepcion(exc)

    assert descripcion == "django.db.utils.DatabaseError: (mensaje de base de datos omitido)"


# --- Otras excepciones ---


def test_validation_error_conserva_solo_los_codigos():
    exc = ValidationError("%(valor)s no es válido", code="invalido", params={"valor": CORREO})

    descripcion = describir_excepcion(exc)

    assert "invalido" in descripcion
    assert CORREO not in descripcion


def test_validation_error_por_campo_conserva_solo_los_codigos():
    exc = ValidationError({"correo": ValidationError(f"{CORREO} ya existe", code="unico")})

    descripcion = describir_excepcion(exc)

    assert "unico" in descripcion and "correo" in descripcion
    assert CORREO not in descripcion


def test_unicode_error_conserva_solo_la_razon():
    exc = UnicodeDecodeError("utf-8", CORREO.encode() + b"\xff", len(CORREO), len(CORREO) + 1, "invalid start byte")

    descripcion = describir_excepcion(exc)

    assert "invalid start byte" in descripcion
    assert CORREO not in descripcion


def test_value_error_conserva_el_mensaje_truncado():
    mensaje = "x" * LARGO_MAXIMO_MENSAJE + "RESTO_OMITIDO"
    corto = ValueError("Formato de bloque horario inválido")

    assert describir_excepcion(corto) == "builtins.ValueError: Formato de bloque horario inválido"
    descripcion = describir_excepcion(ValueError(mensaje))
    assert "x" * LARGO_MAXIMO_MENSAJE in descripcion
    assert "RESTO_OMITIDO" not in descripcion


def test_str_que_falla_no_impide_describir():
    class ErrorRaro(Exception):
        def __str__(self):
            raise RuntimeError("roto")

    assert describir_excepcion(ErrorRaro()).endswith(": (mensaje no disponible)")


def test_cadena_con_ciclo_termina():
    a = ValueError("a")
    b = KeyError("b")
    a.__context__ = b
    b.__context__ = a

    traza = _traza(a)

    assert traza.count("Traceback (most recent call last):") == 2


def test_cadena_larga_se_limita_a_diez_niveles():
    exc = ValueError("0")
    for i in range(1, 30):
        nueva = ValueError(str(i))
        nueva.__cause__ = exc
        exc = nueva

    assert _traza(exc).count("Traceback (most recent call last):") == 10


def test_traza_sigue_el_formato_de_python_con_contexto_suprimido():
    try:
        try:
            raise KeyError("interna")
        except KeyError:
            raise ValueError("externa") from None
    except ValueError:
        exc_info = sys.exc_info()

    traza = formatear_traza_segura(exc_info)

    assert "interna" not in traza
    assert traza.startswith("Traceback (most recent call last):\n")
    assert traza.endswith("builtins.ValueError: externa")
    assert "test_registros_aplicacion.py" in traza


# --- Contrato del filtro ---


@pytest.mark.django_db
def test_ningun_secreto_llega_al_texto_final():
    crear_cliente()
    exc = _capturar(IntegrityError, _violar_unicidad)
    registro = _registro(exc, request=_request_con_secretos())

    FiltroTrazasSeguras().filter(registro)
    texto = _consola().formatter.format(registro)

    assert "Contexto: método=POST estado=500" in texto
    for ausente in (CORREO_EXISTENTE, CORREO, CONTRASENA, SESION, CSRF, "sessionid", "csrftoken", "DETAIL"):
        assert ausente not in texto, ausente
    for valor in vars(registro).values():
        for ausente in (CORREO_EXISTENTE, CORREO, CONTRASENA, SESION, CSRF):
            assert ausente not in str(valor), ausente


def test_filtro_reemplaza_la_traza_y_quita_request():
    exc = DatabaseError(f"Failing row contains ({CORREO})")
    registro = _registro(exc, request=_request_con_secretos())

    assert FiltroTrazasSeguras().filter(registro) is True

    assert registro.exc_info is None
    assert "(mensaje de base de datos omitido)" in registro.exc_text
    assert CORREO not in registro.exc_text
    assert not hasattr(registro, "request")
    assert registro.msg == "Internal Server Error: %s"
    assert registro.args == ("/api/clientes",)
    assert registro.status_code == 500


def test_filtro_es_idempotente():
    registro = _registro(ValueError("uno"), request=_request_con_secretos())
    filtro = FiltroTrazasSeguras()

    filtro.filter(registro)
    primera = dict(vars(registro))
    assert filtro.filter(registro) is True

    assert vars(registro) == primera


def test_registro_sin_excepcion_no_cambia():
    registro = _registro(msg="Evento %s", args=("sin datos",))
    antes = dict(vars(registro))

    assert FiltroTrazasSeguras().filter(registro) is True

    assert vars(registro) == antes


# --- Configuración ---


def test_django_request_tiene_el_filtro():
    assert any(isinstance(f, FiltroTrazasSeguras) for f in logging.getLogger("django.request").filters)


def test_el_handler_consola_tiene_el_filtro():
    assert any(isinstance(f, FiltroTrazasSeguras) for f in _consola().filters)


def test_django_db_backends_no_escribe_sql():
    assert logging.getLogger("django.db.backends").getEffectiveLevel() >= logging.INFO
