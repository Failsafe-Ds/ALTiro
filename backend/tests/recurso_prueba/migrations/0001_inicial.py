"""Tabla del recurso ficticio de pruebas (solo existe en la base de pruebas; RNF-07)."""

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('identidad', '0003_usuario_rol_asignado_en'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecursoPrueba',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ref', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('dueno', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='identidad.usuario')),
            ],
            options={
                'db_table': 'recurso_prueba',
            },
        ),
    ]
