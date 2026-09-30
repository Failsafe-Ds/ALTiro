"""Mensajes de la conversación de un ticket (RF-25, CA-07.x; ADR-026, E-2).

Solo inserción (RNF-11; patrón de ADR-010, ``ticket_evento`` y
``precio_final_evento``): ``managed=False``, sin FK y con triggers que rechazan
UPDATE, DELETE y TRUNCATE. Los mensajes no se editan ni se borran porque son
evidencia en una disputa (M-04). La tabla se crea con SQL explícito en
``mensajeria/migrations/0001_inicial.py``.
"""
import uuid

from django.db import models

from comun.solo_insercion import ModeloSoloInsercion

LARGO_MAXIMO = 1000


class Mensaje(ModeloSoloInsercion):
    id = models.BigAutoField(primary_key=True)
    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    # Sin FK (ver el docstring del módulo).
    ticket_id = models.BigIntegerField()
    autor_id = models.BigIntegerField()
    texto = models.CharField(max_length=LARGO_MAXIMO)
    enviado_en = models.DateTimeField()
    # Generada por el navegador: un reenvío con conexión irregular no duplica el mensaje (E-2.4).
    clave_envio = models.UUIDField()

    class Meta:
        managed = False
        db_table = "mensaje"

    def __str__(self):
        # Sin el texto: puede terminar en registros.
        return f"Mensaje {self.ref}"
