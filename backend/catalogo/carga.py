"""Carga inicial del catálogo de oficios desde el CSV versionado (ADR-017, punto 1; ADR-018, punto 3).

Desde el S3 el CSV es **solo la carga inicial**: comercial administra el
catálogo desde la aplicación (RF-36), y recargar el CSV pisaría sus cambios.
Por eso ``cargar`` solo inserta los códigos que faltan (``ON CONFLICT DO
NOTHING``) y nunca actualiza ni borra. Ninguna migración posterior a
``0003`` recarga el CSV (lo verifica ``tests/test_catalogo_administrable.py``).
"""
import csv
from pathlib import Path

ARCHIVO_OFICIOS = Path(__file__).resolve().parent / "datos" / "oficios.csv"

_REGULADO = {"si": True, "no": False}


def leer_filas(ruta=ARCHIVO_OFICIOS):
    with open(ruta, encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def cargar(Oficio, filas):
    """Inserta los oficios cuyo ``codigo`` todavía no existe, en una sola sentencia.

    Idempotente. Nunca actualiza (no pisa lo que cambió comercial) ni borra
    (un oficio declarado por un maestro no desaparece en silencio). Cada fila
    nueva recibe su propio ``ref`` cuando el modelo lo tiene.
    """
    oficios = [
        Oficio(
            codigo=fila["codigo"],
            nombre=fila["nombre"],
            regulado=_REGULADO[fila["regulado"]],
            orden=int(fila["orden"]),
        )
        for fila in filas
    ]
    Oficio.objects.bulk_create(oficios, ignore_conflicts=True)
