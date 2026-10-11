"""Validación mínima de texto recibido del cliente (CLAUDE.md §8-§9; ADR-013).

Un solo lugar para las reglas comunes de todo campo de texto:

- recorta los espacios del inicio y del final antes de validar y guardar;
- un texto con solo espacios cuenta como vacío;
- rechaza el carácter nulo y los demás caracteres de control (PostgreSQL no guarda
  el nulo: sin esta revisión el error sería un 500, RNF-15);
- mide el largo máximo después de recortar.

Cada llamador traduce el problema devuelto a su propio mensaje en el campo.
**La contraseña nunca pasa por aquí: no se recorta (ADR-013).**
"""

import re

FALTA = "falta"
INVALIDO = "invalido"
LARGO = "largo"

# Control C0 y DEL, salvo tabulación y salto de línea (que decide ``una_linea``).
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def recortar(valor):
    """Quita los espacios de los extremos si es texto; otro tipo vuelve sin cambios.

    Para los campos de formato fijo (fechas, horas, meses, códigos, RUT, monto).
    """
    return valor.strip() if isinstance(valor, str) else valor


def limpiar_texto(valor, largo, *, una_linea=False, obligatorio=True):
    """Devuelve ``(texto, problema)``; ``problema`` es ``None``, ``FALTA``, ``INVALIDO`` o ``LARGO``.

    - ``None`` o solo espacios: ``FALTA`` si es obligatorio; si no, ``("", None)``.
    - Otro tipo que no sea texto: ``FALTA``.
    - Caracteres de control (incluido el nulo), o salto de línea o tabulación
      cuando ``una_linea``: ``INVALIDO``.
    - Más de ``largo`` caracteres tras recortar: ``LARGO``.
    """
    if valor is None:
        valor = ""
    if not isinstance(valor, str):
        return None, FALTA
    texto = valor.strip()
    if not texto:
        return (None, FALTA) if obligatorio else ("", None)
    if _CONTROL.search(texto) or (una_linea and ("\n" in texto or "\t" in texto)):
        return None, INVALIDO
    if len(texto) > largo:
        return None, LARGO
    return texto, None
