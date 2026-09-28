"""Validadores puros de identidad (ADR-013, puntos 1, 3, 5 y 6; Enmiendas E-3 y E-4; RF-01, RF-03).

Datos ficticios: RUT sintéticos del plan de pruebas, correos @example.com y
teléfonos +56 9 1000 000N.
Los casos no decididos (HQ-11, HQ-12) no se fijan aquí, salvo el mínimo que el
plan exige (PI-044: nunca un valor no ASCII) y la unicidad del RUT.
"""
import re
import socket

import pytest
from django.contrib.auth.password_validation import CommonPasswordValidator

from identidad import validadores
from identidad.errores import ErrorValidacion
from identidad.validadores import (
    calcular_digito_verificador,
    normalizar_correo,
    normalizar_nombre,
    normalizar_rut,
    normalizar_telefono,
    validar_contrasena_nueva,
)

# --- RUT ---


@pytest.mark.parametrize("entrada", ["11.111.111-1", "11111111-1", "111111111"])
def test_pi040_variantes_del_mismo_rut_normalizan_igual(entrada):
    assert normalizar_rut(entrada) == "111111111"


@pytest.mark.parametrize("entrada", ["10.000.013-k", "10.000.013-K", "10000013k"])
def test_pi041_dv_k_se_acepta_y_queda_en_mayuscula(entrada):
    assert normalizar_rut(entrada) == "10000013K"


def test_pi042_dv_cero_es_valido():
    assert normalizar_rut("10.000.004-0") == "100000040"


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [("22.222.222-2", "222222222"), ("12.345.678-5", "123456785")],
)
def test_otros_rut_sinteticos_validos(entrada, esperado):
    assert normalizar_rut(entrada) == esperado


@pytest.mark.parametrize(
    ("cuerpo", "dv"),
    [("11111111", "1"), ("22222222", "2"), ("10000013", "K"), ("10000004", "0"), ("12345678", "5")],
)
def test_digito_verificador_modulo_11(cuerpo, dv):
    assert calcular_digito_verificador(cuerpo) == dv


@pytest.mark.parametrize(
    "entrada",
    ["11.111.111-2", "10.000.013-1", "11.111.111-K", "1A.111.111-1", "", "-1", None, 11111111],
)
def test_pi043_rut_invalido_se_rechaza_en_el_campo_rut(entrada):
    with pytest.raises(ErrorValidacion) as error:
        normalizar_rut(entrada)

    assert error.value.campo == "rut"
    assert error.value.mensaje


@pytest.mark.parametrize(
    "entrada",
    [
        "１１.１１１.１１１-１",  # dígitos de ancho completo
        "١" * 8 + "-١",  # dígitos arábigo-índicos
        "11.111.111–1",  # guion largo
        " 11.111.111-1 ",
        "11,111,111-1",
    ],
)
def test_pi044_minimo_nunca_produce_un_rut_no_ascii(entrada):
    # Aceptar o rechazar cada caso no está definido (HQ-12). Solo se exige que,
    # si se acepta, el resultado sea la forma canónica ASCII.
    try:
        resultado = normalizar_rut(entrada)
    except ErrorValidacion:
        return
    assert resultado.isascii()
    assert re.fullmatch(r"[0-9]{1,8}[0-9K]", resultado)


def test_un_cero_a_la_izquierda_no_crea_una_segunda_forma_del_mismo_rut():
    # Unicidad del RUT (RF-03): rechazar o normalizar al mismo valor son
    # comportamientos compatibles; cuál se elige es HQ-12.
    try:
        resultado = normalizar_rut("011.111.111-1")
    except ErrorValidacion:
        return
    assert resultado == "111111111"


# --- Correo ---


def test_pi050_correo_se_recorta_y_pasa_a_minusculas():
    assert normalizar_correo("  Ana.Prueba@Example.COM  ") == "ana.prueba@example.com"


@pytest.mark.parametrize("entrada", ["", "   ", None])
def test_correo_vacio_o_ausente_se_rechaza_y_nunca_devuelve_cadena_vacia(entrada):
    with pytest.raises(ErrorValidacion) as error:
        normalizar_correo(entrada)

    assert error.value.campo == "correo"


@pytest.mark.parametrize(
    "entrada", ["ana prueba@example.com", "ana@", "@example.com", "anaexample.com"]
)
def test_pi054_correo_mal_formado_se_rechaza_en_el_campo_correo(entrada):
    with pytest.raises(ErrorValidacion) as error:
        normalizar_correo(entrada)

    assert error.value.campo == "correo"
    assert error.value.mensaje


# --- Teléfono (ADR-013, Enmienda E-3) ---


@pytest.mark.parametrize(
    "entrada", ["+56 9 1000 0001", "+56910000001", "9 1000 0001", "(9) 1000-0001"]
)
def test_pi061_variantes_del_mismo_movil_quedan_en_forma_canonica(entrada):
    assert normalizar_telefono(entrada) == "+56910000001"


def test_pi062_se_acepta_un_fijo():
    assert normalizar_telefono("+56 41 200 0001") == "+56412000001"


def test_56_sin_mas_no_tiene_trato_especial_y_cuenta_como_digitos_del_numero():
    assert normalizar_telefono("569100000") == "+56569100000"


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "   ",
        None,
        910000001,
        "nueve uno cero",
        "91000000",  # 8 dígitos
        "9100000011",  # 10 dígitos
        "+5691000000",  # +56 con 8 dígitos
        "+569100000011",  # +56 con 10 dígitos
        "56 9 1000 0001",  # 56 sin "+": 11 dígitos
        "+54 9 1000 0001",
        "9+56 1000 0001",
        "+56 ９ 1000 0001",  # dígito de ancho completo
        "9.1000.0001",
        "9/1000/0001",
        "9\t1000\t0001",  # tabulador
        "9 1000 0001",  # NBSP
    ],
)
def test_pi063_telefono_invalido_se_rechaza_en_el_campo_telefono(entrada):
    with pytest.raises(ErrorValidacion) as error:
        normalizar_telefono(entrada)

    assert error.value.campo == "telefono"
    assert "9 dígitos" in error.value.mensaje
    if isinstance(entrada, str) and entrada.strip():
        assert entrada not in error.value.mensaje


# --- Contraseña nueva (ADR-013, punto 3 y Enmienda E-4) ---

_LISTA_COMUN = CommonPasswordValidator().passwords
_TEXTOS_DJANGO_EN_INGLES = ("password", "This", "common", "too", "characters")


def _no_comun(texto):
    assert texto.lower().strip() not in _LISTA_COMUN
    return texto


def _base(largo):
    return _no_comun(("kq7vzr2mxw9p" * 20)[:largo])


def _error_contrasena(valor):
    with pytest.raises(ErrorValidacion) as error:
        validar_contrasena_nueva(valor)
    assert error.value.campo == "contrasena"
    return error.value


def _entrada_comun_de_al_menos_12():
    candidatas = sorted(
        p for p in _LISTA_COMUN if 12 <= len(p) <= 124 and p.isascii() and p.isalnum()
    )
    assert candidatas, "la lista de Django no tiene entradas de 12 o más caracteres"
    return candidatas[0]


def test_pi150_11_caracteres_se_rechaza_indicando_el_minimo():
    assert "12" in _error_contrasena(_base(11)).mensaje


@pytest.mark.parametrize("largo", [12, 128])
def test_pi151_pi152_12_y_128_caracteres_se_aceptan(largo):
    assert validar_contrasena_nueva(_base(largo)) is None


def test_pi153_129_caracteres_se_rechaza_indicando_el_maximo():
    assert "128" in _error_contrasena(_base(129)).mensaje


def test_10000_caracteres_se_rechaza_antes_de_cualquier_otro_proceso(monkeypatch):
    def no_debe_llamarse(valor):
        raise AssertionError("la lista común no debe consultarse")

    monkeypatch.setattr(validadores._validador_contrasena_comun, "validate", no_debe_llamarse)

    assert "128" in _error_contrasena("a" * 10_000).mensaje


@pytest.mark.parametrize("valor", [None, 123456789012, b"kq7vzr2mxw9p"])
def test_contrasena_que_no_es_texto_se_rechaza(valor):
    _error_contrasena(valor)


@pytest.mark.parametrize(
    "valor",
    [
        " " * 12,
        " " * 128,
        "\t" * 12,
        " " * 12,
        "　" * 12,
        "\t\n 　  " * 2,
    ],
)
def test_pi158_contrasena_solo_con_espacios_se_rechaza(valor):
    assert "espacios" in _error_contrasena(valor).mensaje


@pytest.mark.parametrize("valor", ["mi casa azul grande", "  clave de prueba  "])
def test_pi156_pi157_espacios_internos_y_en_los_extremos_se_aceptan_sin_alterar(valor):
    original = str(valor)
    _no_comun(valor)

    assert validar_contrasena_nueva(valor) is None
    assert valor == original


@pytest.mark.parametrize(
    "valor",
    ["contraseña ñandú", "árbol café pingüino", "llave \U0001f511 de mi casa"],
)
def test_pi162_unicode_se_acepta(valor):
    assert validar_contrasena_nueva(_no_comun(valor)) is None


def test_pi162_se_cuentan_caracteres_y_no_bytes():
    assert validar_contrasena_nueva("ñ" * 128) is None
    assert "128" in _error_contrasena("ñ" * 129).mensaje


def test_pi165_sustituto_aislado_da_error_de_validacion_y_nunca_otra_excepcion():
    assert _error_contrasena("\ud800" * 12).mensaje


def test_pi159_entrada_de_la_lista_comun_se_rechaza():
    _error_contrasena(_entrada_comun_de_al_menos_12())


@pytest.mark.parametrize(
    "variante", [str.upper, str.title, lambda p: "  " + p, lambda p: p + "  "]
)
def test_pi160_variantes_de_la_entrada_comun_tambien_se_rechazan(variante):
    _error_contrasena(variante(_entrada_comun_de_al_menos_12()))


def test_pi166_solo_digitos_se_acepta_si_no_esta_en_la_lista():
    digitos = next(
        d for d in (str(n) * 2 for n in range(918273645, 918273745)) if d not in _LISTA_COMUN
    )

    assert validar_contrasena_nueva(digitos) is None


def test_pi166_contrasena_con_nombre_o_correo_de_la_persona_se_acepta():
    assert validar_contrasena_nueva(_no_comun("Ana.Prueba@example.com 2026")) is None


def test_pi161_la_validacion_no_abre_conexiones(monkeypatch):
    def sin_red(*args, **kwargs):
        raise AssertionError("no debe usar la red")

    monkeypatch.setattr(socket, "socket", sin_red)
    monkeypatch.setattr(socket, "create_connection", sin_red)
    monkeypatch.setattr(socket, "getaddrinfo", sin_red)

    assert validar_contrasena_nueva(_base(16)) is None
    _error_contrasena(_entrada_comun_de_al_menos_12())


@pytest.mark.parametrize(
    "caso", ["corta", "larga", "espacios", "sustituto", "comun", "no_texto"]
)
def test_mensajes_en_espanol_sin_el_valor_ni_textos_de_django(caso):
    valor = {
        "corta": "kq7vzr2",
        "larga": "kq7vzr2mxw9p" * 11,
        "espacios": " " * 12,
        "sustituto": "\ud800" * 12,
        "comun": _entrada_comun_de_al_menos_12(),
        "no_texto": None,
    }[caso]

    mensaje = _error_contrasena(valor).mensaje

    if isinstance(valor, str) and valor.strip():
        assert valor not in mensaje
    assert "contraseña" in mensaje.lower()
    for texto in _TEXTOS_DJANGO_EN_INGLES:
        assert texto not in mensaje


# --- Nombre ---


def test_nombre_se_recorta():
    assert normalizar_nombre("  Ana Prueba ") == "Ana Prueba"


@pytest.mark.parametrize("entrada", ["", "   ", None])
def test_nombre_vacio_se_rechaza(entrada):
    with pytest.raises(ErrorValidacion) as error:
        normalizar_nombre(entrada)

    assert error.value.campo == "nombre"
