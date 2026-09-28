"""Carga idempotente del catálogo mínimo de oficios desde el CSV versionado (ADR-017, punto 1)."""
import csv
from pathlib import Path

ARCHIVO_OFICIOS = Path(__file__).resolve().parent / "datos" / "oficios.csv"

_REGULADO = {"si": True, "no": False}


def leer_filas(ruta=ARCHIVO_OFICIOS):
    with open(ruta, encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def cargar(Oficio, filas):
    """Crea o actualiza los oficios por ``codigo`` en una sola inserción.

    Idempotente (``ON CONFLICT DO UPDATE``). Nunca borra: un oficio declarado
    por un maestro no desaparece en silencio.
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
    Oficio.objects.bulk_create(
        oficios, update_conflicts=True, unique_fields=["codigo"], update_fields=["nombre", "regulado", "orden"]
    )
