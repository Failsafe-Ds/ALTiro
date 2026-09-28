"""Registro de accesos denegados (CA-25.3, HU-25; ADR-010, «Decisión»; ADR-011, «Decisión», punto 3).

Separado de la bitácora administrativa. Registra:
- el recurso existente que la política deniega a un usuario autenticado;
- el 403 por falta de rol de un usuario autenticado (``entidad_ref`` NULL).

Nunca registra 401 anónimos, fallos de CSRF, 404 de referencias inexistentes
ni rechazos por reglas de negocio.

Tabla creada con SQL explícito (``managed=False``): sin FK hacia ``usuario``,
UPDATE y TRUNCATE rechazados por trigger, DELETE permitido solo para filas de
más de 90 días (M-08). Ningún proceso fuera de ``autorizacion`` la lee (M-08);
no hay ruta ni pantalla: el equipo la revisa con psql (ADR-010, punto 6).
"""
from django.db import models
from django.db.models.functions import Now

from comun.solo_insercion import ModeloSoloInsercion


class RegistroAccesoDenegado(ModeloSoloInsercion):
    id = models.BigAutoField(primary_key=True)
    # La fecha la pone la BD (DEFAULT now()), el mismo reloj que usa la purga.
    fecha = models.DateTimeField(db_default=Now())
    # Sin FK (ADR-010, «Decisión», punto 4).
    usuario_id = models.BigIntegerField()
    # Método y patrón de la ruta; nunca la ruta cruda ni la cadena de consulta (ADR-011, punto 4).
    recurso = models.CharField(max_length=200)
    entidad = models.CharField(max_length=40)
    entidad_ref = models.CharField(max_length=64, null=True)

    class Meta:
        managed = False
        db_table = "acceso_denegado"

    def __str__(self):
        return f"Acceso denegado {self.pk}"
