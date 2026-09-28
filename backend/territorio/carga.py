"""Carga idempotente del catálogo territorial desde el CSV versionado (ADR-012)."""
import csv
from pathlib import Path

ARCHIVO_CUT = Path(__file__).resolve().parent / "datos" / "cut_2018.csv"

# Orden de norte a sur por código de región CUT.
ORDEN_REGIONES = [15, 1, 2, 3, 4, 5, 13, 6, 7, 16, 8, 9, 14, 10, 11, 12]


def leer_filas(ruta=ARCHIVO_CUT):
    with open(ruta, encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def cargar(Region, Provincia, Comuna, filas):
    """Crea o actualiza regiones, provincias y comunas en tres inserciones.

    Idempotente: ejecutarla dos veces no cambia nada (``ON CONFLICT DO UPDATE``).
    """
    regiones, provincias, comunas = {}, {}, {}
    for fila in filas:
        codigo_region = int(fila["region_codigo"])
        regiones[codigo_region] = Region(
            codigo=codigo_region,
            nombre=fila["region_nombre"],
            orden=ORDEN_REGIONES.index(codigo_region) + 1,
        )
        provincias[int(fila["provincia_codigo"])] = Provincia(
            codigo=int(fila["provincia_codigo"]), region_id=codigo_region, nombre=fila["provincia_nombre"]
        )
        comunas[int(fila["comuna_codigo"])] = Comuna(
            codigo=int(fila["comuna_codigo"]),
            provincia_id=int(fila["provincia_codigo"]),
            nombre=fila["comuna_nombre"],
        )
    Region.objects.bulk_create(
        regiones.values(), update_conflicts=True, unique_fields=["codigo"], update_fields=["nombre", "orden"]
    )
    Provincia.objects.bulk_create(
        provincias.values(), update_conflicts=True, unique_fields=["codigo"], update_fields=["region", "nombre"]
    )
    Comuna.objects.bulk_create(
        comunas.values(), update_conflicts=True, unique_fields=["codigo"], update_fields=["provincia", "nombre"]
    )
