"""Expediente del maestro y oficios declarados (ADR-017; propuesta del S2, §3). Generada por Django 5.2.17."""

import django.db.models.deletion
import django.db.models.functions.datetime
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('catalogo', '0001_inicial'),
        ('identidad', '0003_usuario_rol_asignado_en'),
    ]

    operations = [
        migrations.CreateModel(
            name='Expediente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ref', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('estado', models.CharField(choices=[('en_revision', 'En revisión'), ('observado', 'Observado'), ('aprobado', 'Aprobado'), ('rechazado', 'Rechazado'), ('suspendido', 'Suspendido')], default='en_revision', max_length=20)),
                ('estado_motivo', models.TextField(blank=True, default='')),
                ('estado_cambiado_en', models.DateTimeField(blank=True, null=True)),
                ('creado_en', models.DateTimeField(db_default=django.db.models.functions.datetime.Now(), default=django.utils.timezone.now)),
                ('estado_cambiado_por', models.ForeignKey(blank=True, db_column='estado_cambiado_por_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='identidad.usuario')),
                ('perfil_maestro', models.OneToOneField(db_column='perfil_maestro_id', on_delete=django.db.models.deletion.PROTECT, related_name='expediente', to='identidad.perfilmaestro')),
            ],
            options={
                'db_table': 'expediente',
                'constraints': [models.CheckConstraint(condition=models.Q(('estado__in', ['en_revision', 'observado', 'aprobado', 'rechazado', 'suspendido'])), name='expediente_estado_valido'), models.CheckConstraint(condition=models.Q(('estado_cambiado_por__isnull', True), ('estado_motivo__regex', '\\S'), _connector='OR'), name='expediente_motivo_con_autor')],
            },
        ),
        migrations.CreateModel(
            name='OficioMaestro',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('maestro', models.ForeignKey(db_column='perfil_maestro_id', db_index=False, on_delete=django.db.models.deletion.PROTECT, related_name='oficios', to='identidad.perfilmaestro')),
                ('oficio', models.ForeignKey(db_column='oficio_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='catalogo.oficio')),
            ],
            options={
                'db_table': 'oficio_maestro',
                'constraints': [models.UniqueConstraint(fields=('maestro', 'oficio'), name='oficio_maestro_unico')],
            },
        ),
    ]
