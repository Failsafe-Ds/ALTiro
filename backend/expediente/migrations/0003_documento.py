"""Documento del expediente (RF-04; ADR-015; ADR-017, puntos 2 y 5). Generada por Django 5.2.17."""

import django.db.models.deletion
import django.db.models.functions.datetime
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo', '0002_carga_oficios'),
        ('expediente', '0002_expedientes_existentes'),
        ('identidad', '0003_usuario_rol_asignado_en'),
    ]

    operations = [
        migrations.CreateModel(
            name='Documento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ref', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('tipo', models.CharField(choices=[('cedula_identidad', 'Cédula de identidad'), ('certificado_antecedentes', 'Certificado de antecedentes'), ('licencia_sec', 'Licencia SEC')], max_length=30)),
                ('fecha_emision', models.DateField()),
                ('fecha_vencimiento', models.DateField(blank=True, null=True)),
                ('estado', models.CharField(choices=[('en_revision', 'En revisión'), ('observado', 'Observado'), ('validado', 'Validado'), ('reemplazado', 'Reemplazado')], default='en_revision', max_length=20)),
                ('motivo_observacion', models.TextField(blank=True, default='')),
                ('archivo', models.UUIDField(unique=True)),
                ('archivo_reverso', models.UUIDField(blank=True, null=True, unique=True)),
                ('cargado_en', models.DateTimeField(db_default=django.db.models.functions.datetime.Now(), default=django.utils.timezone.now)),
                ('revisado_en', models.DateTimeField(blank=True, null=True)),
                ('expediente', models.ForeignKey(db_column='expediente_id', on_delete=django.db.models.deletion.PROTECT, related_name='documentos', to='expediente.expediente')),
                ('oficio', models.ForeignKey(blank=True, db_column='oficio_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='catalogo.oficio')),
                ('reemplaza_a', models.ForeignKey(blank=True, db_column='reemplaza_a_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='expediente.documento')),
                ('revisado_por', models.ForeignKey(blank=True, db_column='revisado_por_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='identidad.usuario')),
            ],
            options={
                'db_table': 'documento',
                'constraints': [models.CheckConstraint(condition=models.Q(('tipo__in', ['cedula_identidad', 'certificado_antecedentes', 'licencia_sec'])), name='documento_tipo_valido'), models.CheckConstraint(condition=models.Q(('estado__in', ['en_revision', 'observado', 'validado', 'reemplazado'])), name='documento_estado_valido'), models.CheckConstraint(condition=models.Q(models.Q(('tipo', 'licencia_sec'), ('oficio__isnull', False)), models.Q(models.Q(('tipo', 'licencia_sec'), _negated=True), ('oficio__isnull', True)), _connector='OR'), name='documento_oficio_solo_licencia'), models.CheckConstraint(condition=models.Q(('fecha_vencimiento__isnull', True), ('fecha_vencimiento__gt', models.F('fecha_emision')), _connector='OR'), name='documento_vencimiento_posterior'), models.CheckConstraint(condition=models.Q(models.Q(('estado', 'observado'), _negated=True), ('motivo_observacion__regex', '\\S'), _connector='OR'), name='documento_motivo_observacion'), models.CheckConstraint(condition=models.Q(models.Q(('tipo', 'cedula_identidad'), ('archivo_reverso__isnull', False)), models.Q(models.Q(('tipo', 'cedula_identidad'), _negated=True), ('archivo_reverso__isnull', True)), _connector='OR'), name='documento_reverso_solo_cedula'), models.UniqueConstraint(condition=models.Q(('estado', 'reemplazado'), _negated=True), fields=('expediente', 'tipo', 'oficio'), name='documento_actual_unico', nulls_distinct=False)],
            },
        ),
    ]
