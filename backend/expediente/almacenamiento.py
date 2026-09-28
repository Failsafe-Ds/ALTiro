"""Almacenamiento cifrado de los archivos de documentos (ADR-015, D-3 y D-4).

- Volumen ``settings.ALTIRO_DOCUMENTOS_DIR``, montado solo en app (y en el
  planificador), nunca en el proxy. No hay ruta pública a estos archivos: se
  entregan solo por una vista que vuelve a aplicar la autorización (incremento 3).
- Nombre del archivo: UUID4 generado aquí. El nombre original no se guarda.
- Contenido: ``nonce (12 bytes) || AES-256-GCM(texto, datos asociados)``, con
  nonce aleatorio por archivo. Datos asociados: ``ref`` del documento y la cara
  (``anverso`` o ``reverso``); un archivo movido a otro registro o a la otra
  cara no se descifra (``ArchivoIlegible``).
- Escritura atómica: archivo temporal en el mismo directorio, ``fsync`` y
  ``os.replace``. Permisos 0600 (dueño: el UID 10001 de la app).
- Borrado: ``borrar_al_confirmar`` lo agenda con ``transaction.on_commit``; si la
  transacción se revierte, el archivo se conserva.
La clave (``settings.ALTIRO_DOCUMENTOS_KEY``) nunca se escribe en registros ni
en mensajes de error.
"""
import os
import tempfile
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.db import transaction

ANVERSO = "anverso"
REVERSO = "reverso"
_CARAS = frozenset({ANVERSO, REVERSO})
LARGO_NONCE = 12
PERMISOS = 0o600


class ArchivoIlegible(Exception):
    """El archivo no existe, está dañado o no corresponde a ese documento y cara."""


def _directorio():
    return Path(settings.ALTIRO_DOCUMENTOS_DIR)


def _ruta(nombre):
    # ``nombre`` siempre es un UUID (lo valida uuid.UUID): nunca sale del directorio.
    return _directorio() / str(uuid.UUID(str(nombre)))


def _datos_asociados(documento_ref, cara):
    if cara not in _CARAS:
        raise ValueError("cara desconocida")
    return f"{uuid.UUID(str(documento_ref))}:{cara}".encode("ascii")


def _cifrador():
    return AESGCM(settings.ALTIRO_DOCUMENTOS_KEY)


def guardar(documento_ref, cara, contenido):
    """Cifra ``contenido`` y lo escribe de forma atómica. Devuelve el nombre (UUID) del archivo."""
    nonce = os.urandom(LARGO_NONCE)
    cifrado = nonce + _cifrador().encrypt(nonce, contenido, _datos_asociados(documento_ref, cara))
    nombre = uuid.uuid4()
    descriptor, temporal = tempfile.mkstemp(dir=_directorio(), prefix=".subiendo-")
    try:
        with os.fdopen(descriptor, "wb") as archivo:
            archivo.write(cifrado)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.chmod(temporal, PERMISOS)
        os.replace(temporal, _ruta(nombre))
    except BaseException:
        try:
            os.unlink(temporal)
        except OSError:
            pass
        raise
    return nombre


def leer(documento_ref, cara, nombre):
    """Devuelve el contenido descifrado del archivo ``nombre`` de ese documento y cara."""
    try:
        cifrado = _ruta(nombre).read_bytes()
    except (OSError, ValueError):
        raise ArchivoIlegible() from None
    if len(cifrado) <= LARGO_NONCE:
        raise ArchivoIlegible()
    try:
        return _cifrador().decrypt(
            cifrado[:LARGO_NONCE], cifrado[LARGO_NONCE:], _datos_asociados(documento_ref, cara)
        )
    except InvalidTag:
        raise ArchivoIlegible() from None


def borrar(nombre):
    """Borra el archivo ``nombre`` si existe (sin error si ya no está)."""
    try:
        _ruta(nombre).unlink()
    except FileNotFoundError:
        pass


def borrar_al_confirmar(*nombres):
    """Borra los archivos cuando la transacción en curso se confirma (D-11)."""
    for nombre in nombres:
        if nombre is not None:
            transaction.on_commit(lambda nombre=nombre: borrar(nombre))
