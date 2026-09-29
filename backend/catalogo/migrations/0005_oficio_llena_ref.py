"""Oficio, paso 2 de 3: un UUID v4 distinto por fila (ADR-011; ADR-018).

Idempotente: solo llena las filas sin ``ref``. No recarga el CSV (ADR-018,
punto 3). Sin reversa de datos.
"""
import uuid

from django.db import migrations


def llenar_ref(apps, schema_editor):
    Oficio = apps.get_model("catalogo", "Oficio")
    for pk in Oficio.objects.filter(ref__isnull=True).values_list("pk", flat=True):
        Oficio.objects.filter(pk=pk).update(ref=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [("catalogo", "0004_oficio_ref_activo_version")]

    operations = [migrations.RunPython(llenar_ref, migrations.RunPython.noop)]
