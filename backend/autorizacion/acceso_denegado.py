"""Registro y purga de accesos denegados (CA-25.3, M-08, RNF-22; ADR-010, «Decisión», puntos 2, 3 y 5).

- ``RETENCION_DIAS``: política del equipo (90 días), no un ajuste del servidor.
  El trigger de la tabla usa el mismo literal; una prueba verifica que coincidan.
- ``purgar_vencidos()``: única función de purga. Se llama al registrar una
  denegación y desde el comando ``purgar_accesos_denegados``; en S4 la llamará
  el planificador. Es una purga automática por retención: no se atribuye al
  usuario de la petición. La condición usa ``now()`` de SQL, igual que el trigger.
- Ningún módulo fuera de ``autorizacion`` usa este registro (M-08).
"""
import logging

from django.db import connection, transaction

from autorizacion.models import RegistroAccesoDenegado

logger = logging.getLogger(__name__)

RETENCION_DIAS = 90

_LARGO_RECURSO = 200


def purgar_vencidos():
    """Borra las filas con más de ``RETENCION_DIAS`` días y devuelve cuántas borró."""
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM acceso_denegado WHERE fecha < now() - make_interval(days => %s)",
            [RETENCION_DIAS],
        )
        borradas = cursor.rowcount
    if borradas:
        # Evento de aplicación (RNF-22): fecha (del registro) y conteo, sin datos personales.
        logger.info("Purga automática por retención de accesos denegados: %s filas eliminadas.", borradas)
    return borradas


@transaction.atomic
def registrar(usuario, recurso, entidad, entidad_ref=None):
    """Registra una denegación de un usuario autenticado (antes purga las vencidas)."""
    purgar_vencidos()
    return RegistroAccesoDenegado.objects.create(
        usuario_id=usuario.pk,
        recurso=recurso[:_LARGO_RECURSO],
        entidad=entidad,
        entidad_ref=None if entidad_ref is None else str(entidad_ref),
    )
