"""Perfil público y servicios del maestro (ADR-019, puntos 1 y 5; ADR-021). Generada por Django 5.2.17."""

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('catalogo', '0007_servicio'),
        ('identidad', '0003_usuario_rol_asignado_en'),
    ]

    operations = [
        migrations.CreateModel(
            name='PerfilPublico',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ref', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('foto', models.UUIDField(blank=True, null=True, unique=True)),
                ('foto_actualizada_en', models.DateTimeField(blank=True, null=True)),
                ('perfil_maestro', models.OneToOneField(db_column='perfil_maestro_id', on_delete=django.db.models.deletion.PROTECT, related_name='perfil_publico', to='identidad.perfilmaestro')),
            ],
            options={
                'db_table': 'perfil_publico',
                'constraints': [models.CheckConstraint(condition=models.Q(('foto__isnull', True), ('foto_actualizada_en__isnull', False), _connector='OR'), name='perfil_publico_foto_con_fecha')],
            },
        ),
        migrations.CreateModel(
            name='ServicioMaestro',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ref', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('modalidad', models.CharField(choices=[('por_trabajo', 'Por trabajo'), ('por_hora', 'Por hora')], max_length=20)),
                ('monto', models.PositiveIntegerField()),
                ('creado_en', models.DateTimeField(default=django.utils.timezone.now)),
                ('actualizado_en', models.DateTimeField(default=django.utils.timezone.now)),
                ('retirado_en', models.DateTimeField(blank=True, null=True)),
                ('maestro', models.ForeignKey(db_column='perfil_maestro_id', db_index=False, on_delete=django.db.models.deletion.PROTECT, related_name='servicios', to='identidad.perfilmaestro')),
                ('servicio', models.ForeignKey(db_column='servicio_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='catalogo.servicio')),
            ],
            options={
                'db_table': 'servicio_maestro',
                'constraints': [models.CheckConstraint(condition=models.Q(('modalidad__in', ['por_trabajo', 'por_hora'])), name='servicio_maestro_modalidad_valida'), models.CheckConstraint(condition=models.Q(('monto__gt', 0), ('monto__lte', 10000000)), name='servicio_maestro_monto_valido'), models.UniqueConstraint(condition=models.Q(('retirado_en__isnull', True)), fields=('maestro', 'servicio'), name='servicio_maestro_activo_unico')],
            },
        ),
    ]
