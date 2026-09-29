"""Foto del maestro: variantes y almacenamiento (ADR-021; patrón de ADR-015).

- ``variantes(datos)``: valida y recodifica la foto subida con
  ``expediente.imagenes.recodificar`` (tipo por el contenido, límite de peso y
  de píxeles, sin EXIF ni GPS, sin ICC, políglotas neutralizados) y genera
  las variantes de ``TAMANOS`` px: el lado mayor mide como máximo ese valor,
  sin recortar ni agrandar (supuesto: la pantalla decide el encuadre). Cada
  variante es una imagen nueva generada desde los píxeles, sin metadatos.
- Volumen ``settings.ALTIRO_FOTOS_DIR``, montado solo en ``app``. **Sin
  cifrar** (ADR-021, punto 3): su finalidad es ser pública, pero solo se
  entrega por una vista que exige que el maestro esté publicado.
- Nombre: ``<uuid>-<tamaño>.jpg``, con el UUID generado aquí; el nombre
  original no se guarda.
- Escritura atómica (temporal en el mismo directorio, ``fsync``, ``os.replace``)
  con permisos 0600, igual que ``expediente.almacenamiento``.
- ``borrar_al_confirmar``: borra una foto anterior solo cuando la transacción
  que la reemplazó se confirma.
"""
import io
import os
import tempfile
import uuid
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from PIL import Image

from expediente import imagenes
from expediente.errores import ErroresValidacion
from perfil.models import PerfilPublico
from perfil.servicios import expediente_editable

TAMANOS = (160, 480)
CALIDAD_JPEG = 85
PERMISOS = 0o600
PREFIJO_TEMPORAL = ".subiendo-"


class FotoIlegible(Exception):
    """La variante pedida no existe o no se puede leer."""


def _directorio():
    return Path(settings.ALTIRO_FOTOS_DIR)


def _ruta(nombre, tamano):
    # ``nombre`` siempre es un UUID (lo valida uuid.UUID) y ``tamano`` uno de
    # TAMANOS: la ruta nunca sale del directorio.
    if tamano not in TAMANOS:
        raise ValueError("tamaño no admitido")
    return _directorio() / f"{uuid.UUID(str(nombre))}-{tamano}.jpg"


def _variante(imagen, tamano):
    reducida = imagen.copy()
    reducida.thumbnail((tamano, tamano), Image.Resampling.LANCZOS)
    # Imagen nueva sin ``info``: ningún metadato llega al guardar.
    limpia = Image.new(reducida.mode, reducida.size)
    limpia.paste(reducida)
    salida = io.BytesIO()
    limpia.save(salida, format="JPEG", quality=CALIDAD_JPEG, optimize=True)
    return salida.getvalue()


def variantes(datos):
    """Devuelve ``{tamaño: bytes JPEG}``. ``imagenes.ImagenInvalida`` si la foto no se acepta."""
    recodificada = imagenes.recodificar(datos)
    with Image.open(io.BytesIO(recodificada), formats=("JPEG",)) as imagen:
        imagen.load()
        return {tamano: _variante(imagen, tamano) for tamano in TAMANOS}


def _escribir(ruta, contenido):
    descriptor, temporal = tempfile.mkstemp(dir=_directorio(), prefix=PREFIJO_TEMPORAL)
    try:
        with os.fdopen(descriptor, "wb") as archivo:
            archivo.write(contenido)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.chmod(temporal, PERMISOS)
        os.replace(temporal, ruta)
    except BaseException:
        try:
            os.unlink(temporal)
        except OSError:
            pass
        raise


def guardar(por_tamano):
    """Escribe todas las variantes con un nombre nuevo y lo devuelve. Si una falla, no deja ninguna."""
    nombre = uuid.uuid4()
    try:
        for tamano in TAMANOS:
            _escribir(_ruta(nombre, tamano), por_tamano[tamano])
    except BaseException:
        borrar(nombre)
        raise
    return nombre


def leer(nombre, tamano):
    try:
        return _ruta(nombre, tamano).read_bytes()
    except (OSError, ValueError):
        raise FotoIlegible() from None


def borrar(nombre):
    """Borra todas las variantes de ``nombre`` que existan (sin error si ya no están)."""
    for tamano in TAMANOS:
        try:
            _ruta(nombre, tamano).unlink()
        except FileNotFoundError:
            pass


def borrar_al_confirmar(nombre):
    if nombre is not None:
        transaction.on_commit(lambda: borrar(nombre))


# --- Caso de uso: el maestro sube o cambia su foto (ADR-021) ---

MENSAJE_FOTO_FALTA = "Adjunta tu foto."
MENSAJE_RECHAZADO = "Tu postulación no fue aprobada, así que ya no puedes cambiar tu foto."


def subir_foto(usuario, archivo):
    """Guarda la foto del maestro ``usuario`` y reemplaza la anterior (ADR-021, puntos 2 y 3).

    - ``archivo``: el archivo subido (``read()`` y ``size``), o ``None``.
    - Foto inválida: ``ErroresValidacion`` en ``archivo`` (400); expediente
      ``rechazado``: ``ErrorEstado`` (409). En ambos casos no queda nada escrito.
    - La foto anterior se borra solo si la transacción se confirma; si se
      revierte, se borran las variantes nuevas y queda la anterior.
    Devuelve el ``PerfilPublico`` actualizado.
    """
    if archivo is None:
        raise ErroresValidacion({"archivo": MENSAJE_FOTO_FALTA})
    if archivo.size > settings.ALTIRO_DOCUMENTO_MAXIMO_BYTES:
        raise ErroresValidacion({"archivo": imagenes.MENSAJE_PESO})
    try:
        por_tamano = variantes(archivo.read())
    except imagenes.ImagenInvalida as error:
        raise ErroresValidacion({"archivo": error.mensaje}) from None
    nombre = None
    try:
        with transaction.atomic():
            expediente_editable(usuario.pk, MENSAJE_RECHAZADO)
            perfil = PerfilPublico.objects.select_for_update().get(perfil_maestro_id=usuario.pk)
            anterior = perfil.foto
            nombre = guardar(por_tamano)
            perfil.foto = nombre
            perfil.foto_actualizada_en = timezone.now()
            perfil.save(update_fields=["foto", "foto_actualizada_en"])
            borrar_al_confirmar(anterior)
    except BaseException:
        # La transacción no se confirmó: las variantes nuevas no quedan huérfanas.
        if nombre is not None:
            borrar(nombre)
        raise
    return perfil
