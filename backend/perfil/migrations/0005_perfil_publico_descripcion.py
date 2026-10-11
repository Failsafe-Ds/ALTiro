# «Sobre mí» del maestro (DA-30): texto opcional de hasta 500 caracteres.
# Los perfiles existentes quedan con la descripción vacía.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('perfil', '0004_indices_busqueda'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfilpublico',
            name='descripcion',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
