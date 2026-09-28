"""Normalizadores y validadores puros de identidad (ADR-013, puntos 1, 3, 5 y 6; Enmiendas E-3 y E-4).

Funciones sin acceso a base de datos. Cada una devuelve el valor canónico o
lanza ``ErrorValidacion`` con el campo afectado y una acción correctiva.

Criterio para los casos de correo y RUT que ninguna decisión define (HQ-11, HQ-12): se
rechazan (fallar cerrado), nunca se aceptan transformándolos de forma
inventada. Las pruebas no fijan esos casos; cuando se decidan, se ajusta aquí.
"""
import re

from django.contrib.auth.password_validation import CommonPasswordValidator
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

from identidad.errores import ErrorValidacion

# --- Correo (ADR-013, punto 5) ---

# Largo de la columna usuario.correo (valor por defecto de EmailField en Django).
# El largo máximo no está decidido (HQ-11); evita un error de BD por desborde.
CORREO_LARGO_MAXIMO = 254

_validador_correo = EmailValidator()


def normalizar_correo(valor):
    """Recorta espacios al inicio y al final y pasa a minúsculas; valida el formato.

    ``None`` no es un correo: quien llame decide si el correo es opcional.
    Nunca devuelve cadena vacía.
    """
    if not isinstance(valor, str):
        raise ErrorValidacion("correo", "Ingresa tu correo, por ejemplo nombre@dominio.cl.")
    correo = valor.strip().lower()
    if not correo:
        raise ErrorValidacion("correo", "Ingresa tu correo, por ejemplo nombre@dominio.cl.")
    if len(correo) > CORREO_LARGO_MAXIMO:
        raise ErrorValidacion("correo", "El correo es demasiado largo. Revisa que esté bien escrito.")
    try:
        _validador_correo(correo)
    except ValidationError:
        raise ErrorValidacion(
            "correo", "El correo no es válido. Revísalo, por ejemplo nombre@dominio.cl."
        ) from None
    return correo


# --- RUT (ADR-013, punto 1; RF-03) ---

# Cuerpo de 1 a 8 dígitos ASCII más el dígito verificador (0-9 o K), igual
# que el CHECK perfil_maestro_rut_formato (E-6). Los formatos raros de entrada
# no están decididos (HQ-12); lo que no calza con este patrón se rechaza.
RUT_LARGO_MAXIMO = 9
_PATRON_RUT = re.compile(r"[0-9]{1,8}[0-9K]", re.ASCII)
_PATRON_CERO_INICIAL = re.compile(r"0[0-9]*[0-9K]", re.ASCII)


def calcular_digito_verificador(cuerpo):
    """Dígito verificador módulo 11 de un cuerpo de RUT (solo dígitos ASCII)."""
    suma = 0
    factor = 2
    for digito in reversed(cuerpo):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def normalizar_rut(valor):
    """Devuelve el RUT sin puntos ni guion y con el DV en mayúscula.

    Acepta el RUT con o sin puntos y guion. Rechaza el DV incorrecto.
    """
    mensaje_formato = "Ingresa tu RUT con su dígito verificador, por ejemplo 12.345.678-5."
    if not isinstance(valor, str):
        raise ErrorValidacion("rut", mensaje_formato)
    rut = valor.replace(".", "").replace("-", "").upper()
    if not _PATRON_RUT.fullmatch(rut):
        raise ErrorValidacion("rut", mensaje_formato)
    # Un cero a la izquierda daría una segunda forma del mismo RUT y burlaría la
    # unicidad. Cómo tratarlo no está decidido (HQ-12): se rechaza.
    if _PATRON_CERO_INICIAL.fullmatch(rut):
        raise ErrorValidacion("rut", mensaje_formato)
    cuerpo, dv = rut[:-1], rut[-1]
    if calcular_digito_verificador(cuerpo) != dv:
        raise ErrorValidacion(
            "rut", "El RUT no es válido: revisa los números y el dígito verificador."
        )
    return rut


# --- Teléfono (ADR-013, punto 6 y Enmienda E-3) ---

# Forma canónica: "+56" seguido de 9 dígitos ASCII (E-3). Mismo largo que la
# columna usuario.telefono y que el CHECK usuario_telefono_formato (E-6).
TELEFONO_LARGO_MAXIMO = 12
# Solo se eliminan el espacio ASCII, el guion y los paréntesis (decisión del
# equipo). Tabuladores, NBSP u otros espacios Unicode quedan y hacen fallar.
_PRESENTACION_TELEFONO = str.maketrans("", "", " -()")
_PATRON_TELEFONO_CANONICO = re.compile(r"\+56[0-9]{9}", re.ASCII)
_PATRON_TELEFONO_NACIONAL = re.compile(r"[0-9]{9}", re.ASCII)
_MENSAJE_TELEFONO = (
    "Ingresa tu teléfono con 9 dígitos, con o sin +56 al inicio, por ejemplo 9 1234 5678."
)


def normalizar_telefono(valor):
    """Devuelve el teléfono en forma canónica "+56" + 9 dígitos.

    ``56`` sin "+" no tiene trato especial: cuenta como dígitos del número.
    """
    if not isinstance(valor, str):
        raise ErrorValidacion("telefono", _MENSAJE_TELEFONO)
    telefono = valor.translate(_PRESENTACION_TELEFONO)
    if _PATRON_TELEFONO_CANONICO.fullmatch(telefono):
        return telefono
    if _PATRON_TELEFONO_NACIONAL.fullmatch(telefono):
        return "+56" + telefono
    raise ErrorValidacion("telefono", _MENSAJE_TELEFONO)


# --- Contraseña nueva (ADR-013, punto 3 y Enmienda E-4) ---

CONTRASENA_LARGO_MINIMO = 12
CONTRASENA_LARGO_MAXIMO = 128
# Instanciado directamente: no depende de AUTH_PASSWORD_VALIDATORS ni de que
# django.contrib.auth esté instalada. Lee su lista local (sin red).
_validador_contrasena_comun = CommonPasswordValidator()


def validar_contrasena_nueva(valor):
    """Valida una contraseña al crearla. Devuelve None o lanza ``ErrorValidacion``.

    No normaliza, no recorta y no devuelve una versión alterada. No se usa en
    el inicio de sesión (E-5) ni se conecta todavía a los servicios: el hash
    final depende de ADR-004.
    """
    if not isinstance(valor, str):
        raise ErrorValidacion("contrasena", "Ingresa una contraseña.")
    # El largo se revisa antes que cualquier otro proceso.
    if len(valor) > CONTRASENA_LARGO_MAXIMO:
        raise ErrorValidacion(
            "contrasena",
            f"La contraseña es demasiado larga. Usa como máximo {CONTRASENA_LARGO_MAXIMO} caracteres.",
        )
    if len(valor) < CONTRASENA_LARGO_MINIMO:
        raise ErrorValidacion(
            "contrasena",
            f"La contraseña es muy corta. Usa al menos {CONTRASENA_LARGO_MINIMO} caracteres.",
        )
    if valor.isspace():
        raise ErrorValidacion(
            "contrasena", "La contraseña no puede tener solo espacios. Agrega letras, números u otros signos."
        )
    try:
        valor.encode("utf-8")
    except UnicodeEncodeError:
        raise ErrorValidacion(
            "contrasena",
            "La contraseña tiene caracteres que no se pueden usar. Escríbela de nuevo con otros caracteres.",
        ) from None
    try:
        _validador_contrasena_comun.validate(valor)
    except ValidationError:
        raise ErrorValidacion(
            "contrasena", "Esa contraseña es muy común y fácil de adivinar. Elige otra."
        ) from None


# --- Nombre (RF-01, RF-03) ---

NOMBRE_LARGO_MAXIMO = 150


def normalizar_nombre(valor):
    """Exige un nombre no vacío; recorta espacios al inicio y al final."""
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorValidacion("nombre", "Ingresa tu nombre.")
    nombre = valor.strip()
    if len(nombre) > NOMBRE_LARGO_MAXIMO:
        raise ErrorValidacion(
            "nombre", f"El nombre es demasiado largo. Usa como máximo {NOMBRE_LARGO_MAXIMO} caracteres."
        )
    return nombre
