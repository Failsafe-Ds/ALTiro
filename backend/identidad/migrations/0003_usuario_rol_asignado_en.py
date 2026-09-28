"""Fecha de asignación del rol (ADR-010, «Decisión», punto 7).

``usuario_rol.asignado_en`` con DEFAULT now() en la BD. Las filas existentes
reciben la fecha de la migración: la fecha real de su asignación no se conoce.
"""
import django.db.models.functions.datetime
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identidad", "0002_comuna_e_intentos"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuariorol",
            name="asignado_en",
            field=models.DateTimeField(
                db_default=django.db.models.functions.datetime.Now(),
                default=django.utils.timezone.now,
            ),
        ),
    ]
