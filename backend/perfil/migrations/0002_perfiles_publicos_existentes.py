"""Crea el perfil público de cada maestro registrado antes del S3 (ADR-019; propuesta del S3, §3).

Idempotente: solo crea los que faltan, con un UUID v4 distinto por fila (el
valor por defecto se evalúa por instancia en ``bulk_create``). Sin reversa de
datos. Autocontenida (modelos históricos): no depende del código actual de los
servicios.
"""
import uuid

from django.db import migrations


def crear_perfiles_publicos(apps, schema_editor):
    PerfilPublico = apps.get_model("perfil", "PerfilPublico")
    PerfilMaestro = apps.get_model("identidad", "PerfilMaestro")
    sin_perfil = PerfilMaestro.objects.filter(perfil_publico__isnull=True).values_list("pk", flat=True)
    PerfilPublico.objects.bulk_create(
        [PerfilPublico(perfil_maestro_id=pk, ref=uuid.uuid4()) for pk in sin_perfil]
    )


class Migration(migrations.Migration):
    dependencies = [("perfil", "0001_inicial")]

    operations = [migrations.RunPython(crear_perfiles_publicos, migrations.RunPython.noop)]
