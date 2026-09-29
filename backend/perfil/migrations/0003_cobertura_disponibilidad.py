"""Cobertura (RF-06, CA-13.1; ADR-019, punto 4) y disponibilidad semanal (RF-07, CA-14.2; ADR-020). Generada por Django 5.2.17."""

import django.db.models.deletion
import django.db.models.functions.math
import django.db.models.lookups
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('identidad', '0003_usuario_rol_asignado_en'),
        ('perfil', '0002_perfiles_publicos_existentes'),
        ('territorio', '0002_carga_cut_2018'),
    ]

    operations = [
        migrations.CreateModel(
            name='Cobertura',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('es_base', models.BooleanField(default=False)),
                ('comuna', models.ForeignKey(db_column='comuna_codigo', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='territorio.comuna')),
                ('maestro', models.ForeignKey(db_column='perfil_maestro_id', db_index=False, on_delete=django.db.models.deletion.PROTECT, related_name='coberturas', to='identidad.perfilmaestro')),
            ],
            options={
                'db_table': 'cobertura',
                'constraints': [models.UniqueConstraint(fields=('maestro', 'comuna'), name='cobertura_comuna_unica'), models.UniqueConstraint(condition=models.Q(('es_base', True)), fields=('maestro',), name='cobertura_una_comuna_base')],
            },
        ),
        migrations.CreateModel(
            name='Disponibilidad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ref', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('dia_semana', models.PositiveSmallIntegerField()),
                ('inicio_min', models.PositiveSmallIntegerField()),
                ('fin_min', models.PositiveSmallIntegerField()),
                ('creado_en', models.DateTimeField(default=django.utils.timezone.now)),
                ('retirado_en', models.DateTimeField(blank=True, null=True)),
                ('maestro', models.ForeignKey(db_column='perfil_maestro_id', db_index=False, on_delete=django.db.models.deletion.PROTECT, related_name='disponibilidades', to='identidad.perfilmaestro')),
            ],
            options={
                'db_table': 'disponibilidad',
                'indexes': [models.Index(condition=models.Q(('retirado_en__isnull', True)), fields=['maestro', 'dia_semana'], name='disponibilidad_activa_idx')],
                'constraints': [models.CheckConstraint(condition=models.Q(('dia_semana__gte', 1), ('dia_semana__lte', 7)), name='disponibilidad_dia_semana_iso'), models.CheckConstraint(condition=models.Q(('inicio_min__gte', 0), ('inicio_min__lt', models.F('fin_min')), ('fin_min__lte', 1440)), name='disponibilidad_rango_valido'), models.CheckConstraint(condition=models.Q(django.db.models.lookups.Exact(django.db.models.functions.math.Mod('inicio_min', 30), 0), django.db.models.lookups.Exact(django.db.models.functions.math.Mod('fin_min', 30), 0)), name='disponibilidad_multiplo_de_30')],
            },
        ),
    ]
