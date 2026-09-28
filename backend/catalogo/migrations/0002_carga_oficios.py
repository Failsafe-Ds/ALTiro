"""Carga el catálogo mínimo de oficios (ADR-017, punto 1). Idempotente; sin reversa de datos."""
from django.db import migrations

from catalogo.carga import cargar, leer_filas


def cargar_oficios(apps, schema_editor):
    cargar(apps.get_model("catalogo", "Oficio"), leer_filas())


class Migration(migrations.Migration):
    dependencies = [("catalogo", "0001_inicial")]

    operations = [migrations.RunPython(cargar_oficios, migrations.RunPython.noop)]
