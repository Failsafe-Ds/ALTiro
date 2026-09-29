"""Oficio, paso 3 de 3: ``ref`` único y no nulo, con UUID v4 por defecto para las filas nuevas (ADR-011; ADR-018)."""
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalogo", "0005_oficio_llena_ref")]

    operations = [
        migrations.AlterField(
            model_name="oficio",
            name="ref",
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
    ]
