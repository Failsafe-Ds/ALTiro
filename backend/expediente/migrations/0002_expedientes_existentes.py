"""Crea el expediente ``en_revision`` de cada maestro registrado antes del S2 (ADR-017, punto 2).

Idempotente: solo crea los que faltan. Sin reversa de datos. Autocontenida
(modelos históricos): no depende del código actual de los servicios.
"""
from django.db import migrations


def crear_expedientes(apps, schema_editor):
    Expediente = apps.get_model("expediente", "Expediente")
    PerfilMaestro = apps.get_model("identidad", "PerfilMaestro")
    sin_expediente = PerfilMaestro.objects.filter(expediente__isnull=True).values_list("pk", flat=True)
    Expediente.objects.bulk_create([Expediente(perfil_maestro_id=pk) for pk in sin_expediente])


class Migration(migrations.Migration):
    dependencies = [("expediente", "0001_inicial")]

    operations = [migrations.RunPython(crear_expedientes, migrations.RunPython.noop)]
