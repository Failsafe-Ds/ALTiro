"""Carga el catálogo CUT 2018 (ADR-012). Idempotente; sin reversa de datos."""
from django.db import migrations

from territorio.carga import cargar, leer_filas


def cargar_cut(apps, schema_editor):
    cargar(
        apps.get_model("territorio", "Region"),
        apps.get_model("territorio", "Provincia"),
        apps.get_model("territorio", "Comuna"),
        leer_filas(),
    )


class Migration(migrations.Migration):
    dependencies = [("territorio", "0001_inicial")]

    operations = [migrations.RunPython(cargar_cut, migrations.RunPython.noop)]
