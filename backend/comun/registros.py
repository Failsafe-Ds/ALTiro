"""Trazas seguras en los registros de la aplicación (ADR-003, Enmienda E-2; DEF-QA-007).

Ante una excepción no traducida, la traza que escribe ``logging`` incluye
``str(exc)``. En un error de base de datos ese texto trae el ``DETAIL`` que arma
PostgreSQL (``Failing row contains (...)``, ``Key (correo)=(...)``), con datos
personales y el hash de la contraseña. CLAUDE.md §8, NTI-09 y RNF-05 lo prohíben.

``FiltroTrazasSeguras`` reemplaza la traza por una versión segura:

- conserva la cadena de excepciones (tipo y módulo) y la traza estructural
  (archivo, línea, función y línea de código), sin variables locales ni notas;
- de un error de base de datos conserva solo una lista positiva de campos de
  ``diag`` y, en la clase 23 y en 42501, el mensaje primario (no trae valores);
  nunca ``str(exc)``, ``message_detail``, ``message_hint``, ``context``,
  ``internal_query`` ni parámetros SQL;
- de un ``ValidationError`` conserva solo sus códigos;
- del resto, el mensaje truncado a ``LARGO_MAXIMO_MENSAJE`` caracteres.

Además elimina ``request`` del registro (cookies, token CSRF, cuerpo, META) y
deja solo el método y el estado. No silencia nada: devuelve siempre ``True``.

Este módulo lo importa ``dictConfig`` antes de ``apps.populate()``: no debe
importar modelos.
"""
import logging
import traceback

import psycopg
from django.core.exceptions import ValidationError
from django.db import Error as ErrorBaseDatosDjango

# Atributos de ``psycopg.errors.Diagnostic`` que se conservan, con su etiqueta.
# Lista positiva: todo lo que no esté aquí se omite.
CAMPOS_DIAGNOSTICO_BD = [
    ("sqlstate", "sqlstate"),
    ("severity_nonlocalized", "severidad"),
    ("schema_name", "esquema"),
    ("table_name", "tabla"),
    ("column_name", "columna"),
    ("datatype_name", "tipo_dato"),
    ("constraint_name", "restriccion"),
]

# Clase 23 (integridad) y 42501 (mensajes de los triggers de solo inserción):
# su mensaje primario no trae valores de la fila.
SQLSTATE_CON_MENSAJE_PRIMARIO = {"clase": "23", "codigos": ("42501",)}

LARGO_MAXIMO_MENSAJE = 200
MAXIMO_EXCEPCIONES_ENCADENADAS = 10

_MENSAJE_BD_OMITIDO = "(mensaje de base de datos omitido)"
_MENSAJE_NO_DISPONIBLE = "(mensaje no disponible)"

# Separadores de la cadena de excepciones, los mismos de Python.
_SEPARADOR_CAUSA = "\nThe above exception was the direct cause of the following exception:\n\n"
_SEPARADOR_CONTEXTO = "\nDuring handling of the above exception, another exception occurred:\n\n"


def _diagnostico_bd(exc):
    """``diag`` de psycopg de la excepción, o de su causa si es de Django."""
    if isinstance(exc, psycopg.Error):
        return exc.diag
    if isinstance(exc, ErrorBaseDatosDjango) and isinstance(exc.__cause__, psycopg.Error):
        return exc.__cause__.diag
    return None


def _mensaje_primario_permitido(sqlstate):
    if not sqlstate:
        return False
    return (
        sqlstate.startswith(SQLSTATE_CON_MENSAJE_PRIMARIO["clase"])
        or sqlstate in SQLSTATE_CON_MENSAJE_PRIMARIO["codigos"]
    )


def _describir_diagnostico(diag):
    partes = []
    for atributo, etiqueta in CAMPOS_DIAGNOSTICO_BD:
        valor = getattr(diag, atributo, None)
        if valor is not None:
            partes.append(f"{etiqueta}={valor}")
    if _mensaje_primario_permitido(getattr(diag, "sqlstate", None)):
        mensaje = getattr(diag, "message_primary", None)
        if mensaje is not None:
            partes.append(f"mensaje={mensaje}")
    return " ".join(partes) if partes else _MENSAJE_BD_OMITIDO


def _codigos_validacion(exc):
    if hasattr(exc, "error_dict"):
        return {campo: [e.code for e in errores] for campo, errores in exc.error_dict.items()}
    return [e.code for e in exc.error_list]


def _texto_seguro(exc):
    try:
        texto = str(exc)
    except Exception:  # noqa: BLE001 — como traceback: un __str__ roto no debe impedir registrar la traza.
        return _MENSAJE_NO_DISPONIBLE
    if len(texto) > LARGO_MAXIMO_MENSAJE:
        return texto[:LARGO_MAXIMO_MENSAJE] + " (truncado)"
    return texto


def _mensaje_seguro(exc):
    if isinstance(exc, (psycopg.Error, ErrorBaseDatosDjango)):
        diag = _diagnostico_bd(exc)
        return _describir_diagnostico(diag) if diag is not None else _MENSAJE_BD_OMITIDO
    if isinstance(exc, ValidationError):
        return f"codigos={_codigos_validacion(exc)}"
    if isinstance(exc, UnicodeError):
        razon = getattr(exc, "reason", None)
        return str(razon) if isinstance(razon, str) else _MENSAJE_NO_DISPONIBLE
    return _texto_seguro(exc)


def describir_excepcion(exc):
    """``<modulo>.<qualname>: <mensaje seguro>`` de una excepción."""
    tipo = type(exc)
    return f"{tipo.__module__}.{tipo.__qualname__}: {_mensaje_seguro(exc)}"


def _cadena(exc):
    """Excepciones de la cadena, de la más interna a la más externa, con su separador."""
    cadena = []
    vistas = set()
    separador = None
    actual = exc
    while actual is not None and id(actual) not in vistas and len(cadena) < MAXIMO_EXCEPCIONES_ENCADENADAS:
        vistas.add(id(actual))
        cadena.append((actual, separador))
        if actual.__cause__ is not None:
            actual, separador = actual.__cause__, _SEPARADOR_CAUSA
        elif actual.__context__ is not None and not actual.__suppress_context__:
            actual, separador = actual.__context__, _SEPARADOR_CONTEXTO
        else:
            actual = None
    return list(reversed(cadena))


def formatear_traza_segura(exc_info):
    """Traza equivalente a ``traceback.format_exception``, sin mensajes inseguros."""
    exc = exc_info[1]
    if exc is None:
        return "NoneType: None"
    partes = []
    for excepcion, separador_siguiente in _cadena(exc):
        marcos = "".join(traceback.extract_tb(excepcion.__traceback__).format())
        partes.append("Traceback (most recent call last):\n" + marcos + describir_excepcion(excepcion) + "\n")
        # El separador une esta excepción con la que la envuelve.
        if separador_siguiente is not None:
            partes.append(separador_siguiente)
    return "".join(partes).rstrip("\n")


class FiltroTrazasSeguras(logging.Filter):
    """Reemplaza la traza por una segura y quita ``request`` del registro (ADR-003 E-2)."""

    def filter(self, record):
        request = record.__dict__.pop("request", None)
        if record.exc_info:
            traza = formatear_traza_segura(record.exc_info)
            if request is not None:
                metodo = getattr(request, "method", None)
                estado = getattr(record, "status_code", None)
                traza = f"Contexto: método={metodo} estado={estado}\n" + traza
            record.exc_text = traza
            record.exc_info = None
        return True
