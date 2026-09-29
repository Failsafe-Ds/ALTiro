"""Tareas del actor Sistema que ejecuta el planificador (ADR-016, punto 1).

Cada tarea es **idempotente**, recibe ``ahora`` (aware) para poder probarla con
time-machine (ADR-014) y devuelve un conteo. No escribe en la bitácora
administrativa: no son acciones sobre expedientes (ADR-010, punto 3; RF-37).
Sus registros llevan solo conteos, sin datos personales (RNF-22, en parte).

- ``emitir_avisos_por_vencer``: avisos de RF-35 al maestro dueño y al rol
  curatoría, una sola vez por documento (CA-24.2); nunca por documentos sin
  vencimiento (CA-24.3).
- La purga de ``acceso_denegado`` está en ``autorizacion.tareas`` (M-08: ningún
  módulo fuera de ``autorizacion`` usa ese registro).
- ``limpiar_archivos_huerfanos``: borra del volumen de documentos los archivos
  que ningún documento referencia (ADR-015), con un margen para no tocar una
  subida en curso.
"""
import logging
import os
import uuid

from django.conf import settings

from expediente import vigencia
from expediente.models import Aviso, Documento, RolDestinatarioAviso, TipoAviso

logger = logging.getLogger(__name__)

# Antigüedad mínima de un archivo sin referencia para borrarlo. Una subida
# escribe el archivo y confirma la fila en la misma petición (segundos); una
# hora deja un margen amplio.
MARGEN_HUERFANOS_SEGUNDOS = 3600

# Prefijo de los temporales de ``expediente.almacenamiento.guardar``.
PREFIJO_TEMPORAL = ".subiendo-"


# --- RF-35 ---


def _emitir(documento, ahora, destinatario_id=None, destinatario_rol=None):
    """Crea el aviso si no existe. Devuelve 1 si lo creó y 0 si ya estaba."""
    _, creado = Aviso.objects.get_or_create(
        tipo=TipoAviso.DOCUMENTO_POR_VENCER,
        documento=documento,
        destinatario_id=destinatario_id,
        destinatario_rol=destinatario_rol,
        defaults={"creado_en": ahora},
    )
    return int(creado)


def emitir_avisos_por_vencer(ahora):
    """Crea los avisos que falten y devuelve cuántos creó.

    Idempotente: el UNIQUE ``aviso_una_vez`` y ``get_or_create`` (que ante un
    choque de UNIQUE relee la fila) garantizan una sola emisión aunque la tarea
    corra dos veces o en paralelo.
    """
    hoy = vigencia.hoy_negocio(ahora)
    creados = 0
    for documento in vigencia.candidatos_a_aviso(hoy):
        if not vigencia.requiere_aviso(documento, hoy):
            continue
        # perfil_maestro comparte la clave primaria con su usuario: el dueño.
        dueno_id = documento.expediente.perfil_maestro_id
        creados += _emitir(documento, ahora, destinatario_id=dueno_id)
        creados += _emitir(documento, ahora, destinatario_rol=RolDestinatarioAviso.CURATORIA)
    if creados:
        logger.info("Avisos de documentos por vencer creados: %s.", creados)
    return creados


# --- Archivos huérfanos del volumen de documentos (ADR-015) ---


def _es_candidato(nombre):
    """Solo archivos que la aplicación crea: UUID o temporal de subida. Nunca otros."""
    if nombre.startswith(PREFIJO_TEMPORAL):
        return True
    try:
        return str(uuid.UUID(nombre)) == nombre
    except ValueError:
        return False


def _referenciados():
    nombres = set()
    for archivo, reverso in Documento.objects.values_list("archivo", "archivo_reverso"):
        nombres.add(str(archivo))
        if reverso is not None:
            nombres.add(str(reverso))
    return nombres


def limpiar_archivos_huerfanos(ahora):
    """Borra los archivos del volumen sin documento que los referencie y devuelve cuántos borró.

    - Solo considera nombres UUID (archivos cifrados) y temporales ``.subiendo-``
      de ``expediente.almacenamiento``; cualquier otro archivo se deja.
    - Solo borra los que tienen más de ``MARGEN_HUERFANOS_SEGUNDOS`` de
      antigüedad respecto de ``ahora``: nunca una subida en curso.
    - Nunca borra un archivo referenciado por un documento, actual o
      reemplazado (se conservan hasta RNF-26 y V-04).
    - Las referencias se leen **después** de listar el directorio: un archivo
      listado cuya fila se confirma antes de la consulta queda referenciado.
    """
    directorio = settings.ALTIRO_DOCUMENTOS_DIR
    limite = ahora.timestamp() - MARGEN_HUERFANOS_SEGUNDOS
    antiguos = []
    with os.scandir(directorio) as entradas:
        for entrada in entradas:
            if not entrada.is_file(follow_symlinks=False) or not _es_candidato(entrada.name):
                continue
            if entrada.stat(follow_symlinks=False).st_mtime < limite:
                antiguos.append(entrada.name)
    if not antiguos:
        return 0
    referenciados = _referenciados()
    borrados = 0
    for nombre in antiguos:
        if nombre in referenciados:
            continue
        try:
            os.unlink(os.path.join(directorio, nombre))
        except FileNotFoundError:
            continue
        borrados += 1
    if borrados:
        # Solo el conteo: nunca nombres de archivo (ADR-015).
        logger.info("Archivos huérfanos de documentos eliminados: %s.", borrados)
    return borrados
