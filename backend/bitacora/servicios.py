"""Registro en la bitácora administrativa (RF-37, CA-19.3, RNF-11; ADR-010).

``registrar`` se llama dentro del mismo ``transaction.atomic()`` que el cambio
que documenta: si el cambio se revierte, la entrada también, y viceversa. En
S1 no tiene llamadores de negocio; los primeros llegan en S2 (CA-19.3).

- ``autor``: el ``Usuario`` que ejecuta la acción, o ``SISTEMA`` solo para
  tareas programadas del actor Sistema (§3.1). Una acción ejecutada por una
  persona nunca se registra como Sistema (ADR-010).
- ``motivo`` obligatorio (HU-19: todo cambio de estado queda motivado).
- ``valor_anterior``/``valor_nuevo`` sin hashes ni secretos (ADR-010).
- La fecha sale de Python (``timezone.now()``, ADR-014).
"""
from django.db import connection
from django.utils import timezone

from bitacora.models import AutorTipo, Bitacora
from identidad.models import Usuario


class _Sistema:
    """Actor Sistema (§3.1): no es un usuario ni un rol guardado."""

    def __repr__(self):
        return "SISTEMA"


SISTEMA = _Sistema()

# Fragmentos de clave que nunca se guardan en los valores (ADR-010; CLAUDE.md §8).
CLAVES_PROHIBIDAS = ("password", "contrasena", "contraseña", "hash", "token", "secreto", "secret", "cookie")


class ErrorBitacora(Exception):
    """Error de programación al registrar: la acción no debe completarse."""


def _autor(autor):
    if autor is SISTEMA:
        return AutorTipo.SISTEMA, None
    if isinstance(autor, Usuario) and autor.pk is not None:
        return AutorTipo.USUARIO, autor.pk
    raise ErrorBitacora("El autor debe ser un usuario guardado o SISTEMA.")


def _texto_obligatorio(nombre, valor):
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorBitacora(f"Falta {nombre}.")
    return valor


def _clave_prohibida(valor):
    """Verdadero si alguna clave (a cualquier profundidad) contiene un fragmento prohibido."""
    if isinstance(valor, dict):
        for clave, contenido in valor.items():
            texto = str(clave).casefold()
            if any(fragmento in texto for fragmento in CLAVES_PROHIBIDAS):
                return True
            if _clave_prohibida(contenido):
                return True
    elif isinstance(valor, (list, tuple)):
        return any(_clave_prohibida(elemento) for elemento in valor)
    return False


def registrar(*, autor, accion, entidad, entidad_ref, motivo, valor_anterior=None, valor_nuevo=None):
    """Inserta una entrada en la bitácora administrativa y la devuelve."""
    if not connection.in_atomic_block:
        raise ErrorBitacora("La bitácora se registra en la misma transacción que el cambio.")
    autor_tipo, autor_id = _autor(autor)
    _texto_obligatorio("la acción", accion)
    _texto_obligatorio("la entidad", entidad)
    _texto_obligatorio("el motivo", motivo)
    entidad_ref = _texto_obligatorio("la referencia de la entidad", str(entidad_ref) if entidad_ref is not None else "")
    if _clave_prohibida(valor_anterior) or _clave_prohibida(valor_nuevo):
        raise ErrorBitacora("Los valores de la bitácora no pueden incluir contraseñas, hashes ni secretos.")
    return Bitacora.objects.create(
        fecha=timezone.now(),
        autor_tipo=autor_tipo,
        autor_id=autor_id,
        accion=accion,
        entidad=entidad,
        entidad_ref=entidad_ref,
        valor_anterior=valor_anterior,
        valor_nuevo=valor_nuevo,
        motivo=motivo,
    )
