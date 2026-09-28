"""Lectura de configuración desde el entorno (RNF-24, ADR-009).

- Los ajustes se leen de variables de entorno.
- Los secretos se leen solo desde archivos indicados en variables ``<NOMBRE>_FILE``.
- Si falta un ajuste obligatorio o un secreto, se lanza ``ImproperlyConfigured``
  y la aplicación no arranca. Los mensajes nunca incluyen el valor de un secreto.
"""
import os

from django.core.exceptions import ImproperlyConfigured

_VERDADEROS = {"true", "1"}
_FALSOS = {"false", "0"}


def leer_secreto(nombre):
    """Devuelve el contenido del archivo indicado en ``<nombre>_FILE``."""
    variable = f"{nombre}_FILE"
    ruta = os.environ.get(variable, "").strip()
    if not ruta:
        raise ImproperlyConfigured(
            f"Falta el secreto {nombre}: defina {variable} con la ruta del archivo que lo contiene."
        )
    try:
        with open(ruta, encoding="utf-8") as archivo:
            valor = archivo.read().strip()
    except OSError:
        raise ImproperlyConfigured(
            f"No se pudo leer el archivo indicado en {variable}. Verifique que exista y sea legible."
        ) from None
    if not valor:
        raise ImproperlyConfigured(f"El archivo indicado en {variable} está vacío.")
    return valor


def leer_variable(nombre):
    """Devuelve una variable de entorno obligatoria y no vacía."""
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise ImproperlyConfigured(f"Falta la variable de entorno {nombre}.")
    return valor


def leer_lista(nombre):
    """Devuelve una variable obligatoria separada por comas como lista no vacía."""
    elementos = [e.strip() for e in leer_variable(nombre).split(",") if e.strip()]
    if not elementos:
        raise ImproperlyConfigured(f"La variable de entorno {nombre} no contiene valores.")
    return elementos


def leer_booleano(nombre, por_defecto):
    """Devuelve una variable booleana ('true'/'false', '1'/'0'); si no existe, ``por_defecto``."""
    valor = os.environ.get(nombre, "").strip().lower()
    if not valor:
        return por_defecto
    if valor in _VERDADEROS:
        return True
    if valor in _FALSOS:
        return False
    raise ImproperlyConfigured(f"La variable de entorno {nombre} debe ser 'true' o 'false'.")


def leer_entero(nombre, por_defecto):
    """Devuelve una variable entera positiva; si no existe, ``por_defecto``."""
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        return por_defecto
    try:
        entero = int(valor)
    except ValueError:
        raise ImproperlyConfigured(f"La variable de entorno {nombre} debe ser un número entero.") from None
    if entero <= 0:
        raise ImproperlyConfigured(f"La variable de entorno {nombre} debe ser mayor que cero.")
    return entero


def leer_clave_aes256(nombre):
    """Devuelve la clave de 32 bytes del secreto ``nombre`` (ADR-015, D-4).

    El archivo guarda los 32 bytes en hexadecimal (64 caracteres), como los
    demás secretos que genera ``init``. Si falta o no mide 32 bytes, la
    aplicación no arranca (RNF-24). El mensaje nunca incluye el valor.
    """
    texto = leer_secreto(nombre)
    try:
        clave = bytes.fromhex(texto)
    except ValueError:
        clave = b""
    if len(clave) != 32:
        raise ImproperlyConfigured(
            f"El archivo indicado en {nombre}_FILE debe contener 32 bytes en hexadecimal (64 caracteres)."
        )
    return clave
