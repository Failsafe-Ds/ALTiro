"""Reemplaza los seis oficios de ejemplo por la lista provisional (P-01; ADR-017, punto 1).

``0002`` carga el CSV y nunca borra, así que en una base ya cargada seguirían
existiendo ``ejemplo_1`` a ``ejemplo_6``. Esta migración les cambia el código
en su misma fila (mismo ``id``): las declaraciones ``oficio_maestro`` y los
documentos que los apuntan siguen apuntando a un oficio válido. Después
recarga el CSV para dejar nombre, ``regulado`` y orden al día.

Idempotente:
- base nueva: ``0002`` ya creó los códigos nuevos y no hay ``ejemplo_N``;
- se renombra solo si existe ``ejemplo_N`` y no existe todavía su código nuevo.
  Si ya existieran ambos, no se toca nada (nunca se borra ni se mueven
  declaraciones en silencio).
Sin reversa de datos.
"""
from django.db import migrations

from catalogo.carga import cargar, leer_filas

# Fijo en la migración: no depende de futuros cambios del CSV.
RENOMBRES = (
    ("ejemplo_1", "gasfiteria"),
    ("ejemplo_2", "carpinteria"),
    ("ejemplo_3", "pintura"),
    ("ejemplo_4", "albanileria"),
    ("ejemplo_5", "cerrajeria"),
    ("ejemplo_6", "jardineria"),
)


def renombrar_oficios(apps, schema_editor):
    Oficio = apps.get_model("catalogo", "Oficio")
    for anterior, nuevo in RENOMBRES:
        if not Oficio.objects.filter(codigo=nuevo).exists():
            Oficio.objects.filter(codigo=anterior).update(codigo=nuevo)
    cargar(Oficio, leer_filas())


class Migration(migrations.Migration):
    dependencies = [("catalogo", "0002_carga_oficios")]

    operations = [migrations.RunPython(renombrar_oficios, migrations.RunPython.noop)]
