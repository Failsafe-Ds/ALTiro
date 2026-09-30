"""Aviso ``mensaje_nuevo`` (S5, incremento 4; ADR-026, E-2.6; propuesta del S5, §3.1)."""
from django.db import migrations, models

TIPOS = ['ticket_nuevo', 'ticket_cerrado', 'ticket_aceptado', 'precio_registrado', 'precio_objetado',
         'orden_finalizada', 'mensaje_nuevo']


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0002_precio_final'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='avisoticket',
            name='aviso_ticket_tipo_valido',
        ),
        migrations.AlterField(
            model_name='avisoticket',
            name='tipo',
            field=models.CharField(choices=[('ticket_nuevo', 'Pedido nuevo'), ('ticket_cerrado', 'Pedido cerrado'), ('ticket_aceptado', 'Pedido aceptado'), ('precio_registrado', 'Precio por aceptar'), ('precio_objetado', 'Precio no aceptado'), ('orden_finalizada', 'Trabajo terminado'), ('mensaje_nuevo', 'Mensaje nuevo')], max_length=20),
        ),
        migrations.AddConstraint(
            model_name='avisoticket',
            constraint=models.CheckConstraint(condition=models.Q(('tipo__in', TIPOS)), name='aviso_ticket_tipo_valido'),
        ),
    ]
