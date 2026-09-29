"""Servicio y ServicioModalidad del catálogo administrable (RF-36; ADR-018, punto 1). Generada por Django 5.2.17."""

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo', '0006_oficio_ref_unico'),
    ]

    operations = [
        migrations.CreateModel(
            name='Servicio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ref', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('nombre', models.CharField(max_length=100)),
                ('activo', models.BooleanField(default=True)),
                ('orden', models.PositiveSmallIntegerField()),
                ('version', models.PositiveIntegerField(default=1)),
                ('oficio', models.ForeignKey(db_column='oficio_id', on_delete=django.db.models.deletion.PROTECT, related_name='servicios', to='catalogo.oficio')),
            ],
            options={
                'db_table': 'servicio',
                'ordering': ['orden', 'nombre'],
            },
        ),
        migrations.CreateModel(
            name='ServicioModalidad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('modalidad', models.CharField(choices=[('por_trabajo', 'Por trabajo'), ('por_hora', 'Por hora')], max_length=20)),
                ('precio_referencia', models.PositiveIntegerField()),
                ('servicio', models.ForeignKey(db_column='servicio_id', db_index=False, on_delete=django.db.models.deletion.PROTECT, related_name='modalidades', to='catalogo.servicio')),
            ],
            options={
                'db_table': 'servicio_modalidad',
                'ordering': ['modalidad'],
            },
        ),
        migrations.AddConstraint(
            model_name='servicio',
            constraint=models.UniqueConstraint(fields=('oficio', 'nombre'), name='servicio_oficio_nombre_unico'),
        ),
        migrations.AddConstraint(
            model_name='servicio',
            constraint=models.CheckConstraint(condition=models.Q(('nombre__regex', '\\S')), name='servicio_nombre_no_vacio'),
        ),
        migrations.AddConstraint(
            model_name='serviciomodalidad',
            constraint=models.UniqueConstraint(fields=('servicio', 'modalidad'), name='servicio_modalidad_unica'),
        ),
        migrations.AddConstraint(
            model_name='serviciomodalidad',
            constraint=models.CheckConstraint(condition=models.Q(('modalidad__in', ['por_trabajo', 'por_hora'])), name='servicio_modalidad_valida'),
        ),
        migrations.AddConstraint(
            model_name='serviciomodalidad',
            constraint=models.CheckConstraint(condition=models.Q(('precio_referencia__gt', 0), ('precio_referencia__lte', 10000000)), name='servicio_modalidad_precio_valido'),
        ),
    ]
