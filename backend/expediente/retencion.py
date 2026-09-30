"""Retención de documentos del maestro (RNF-26, RF-37; ADR-026, E-9; V-04, P-07, P-30).

Tarea del actor Sistema que corre el planificador. Es idempotente y recibe ``ahora``.

- **Plazo por tipo** en ``settings.RETENCION_DIAS`` (variables
  ``RETENCION_DIAS_<TIPO>``). Un tipo sin plazo no se elimina: se registra una
  advertencia si hay documentos que quedarían sujetos a él (E-9.3, P-30).
- **A qué aplica:** documentos no eliminados de expedientes ``rechazado`` o
  ``suspendido`` cuyo cambio a ese estado (``estado_cambiado_en``) ocurrió hace
  el plazo o más (E-9.2: "deja de estar activo", supuesto V-04/P-07). Un
  expediente en otro estado no se toca.
- **Qué hace**, por documento y en una transacción: bloquea primero el
  expediente y después el documento (mismo orden que la carga y la revisión),
  vuelve a comprobar estado y plazo, marca ``eliminado_en`` y
  ``motivo_eliminacion``, escribe la bitácora ``documento_eliminado_retencion``
  con autor Sistema (RF-37) y borra los archivos cifrados al confirmar.
  La fila se conserva (trazabilidad; ``PROTECT`` en avisos y reemplazos).
- Sus registros llevan solo conteos y tipos: sin refs ni datos personales (RNF-22).
"""
import datetime
import logging

from django.conf import settings
from django.db import transaction

from bitacora import servicios as bitacora
from expediente import almacenamiento
from expediente.models import Documento, EstadoExpediente, Expediente, TipoDocumento

logger = logging.getLogger(__name__)

ACCION = "documento_eliminado_retencion"
ESTADOS_INACTIVOS = (EstadoExpediente.RECHAZADO, EstadoExpediente.SUSPENDIDO)


def plazo_dias(tipo):
    """Días de retención configurados para ``tipo``, o ``None`` si no hay plazo."""
    return settings.RETENCION_DIAS.get(tipo)


def _sujetos(tipo):
    """Documentos de ``tipo`` sin eliminar en expedientes inactivos con fecha de estado."""
    return Documento.objects.filter(
        tipo=tipo,
        eliminado_en__isnull=True,
        expediente__estado__in=ESTADOS_INACTIVOS,
        expediente__estado_cambiado_en__isnull=False,
    )


def _motivo(dias, estado):
    return f"Plazo de retención cumplido: {dias} días desde que el expediente quedó {estado}."


def _eliminar(documento_pk, dias, limite, ahora):
    """Elimina un documento si sigue cumpliendo la regla. Devuelve 1 si lo eliminó."""
    with transaction.atomic():
        expediente_pk = Documento.objects.values_list("expediente_id", flat=True).get(pk=documento_pk)
        expediente = Expediente.objects.select_for_update().get(pk=expediente_pk)
        documento = Documento.objects.select_for_update().get(pk=documento_pk)
        if (
            documento.eliminado_en is not None
            or expediente.estado not in ESTADOS_INACTIVOS
            or expediente.estado_cambiado_en is None
            or expediente.estado_cambiado_en > limite
        ):
            return 0
        motivo = _motivo(dias, expediente.estado)
        documento.eliminado_en = ahora
        documento.motivo_eliminacion = motivo
        documento.save(update_fields=["eliminado_en", "motivo_eliminacion"])
        bitacora.registrar(
            autor=bitacora.SISTEMA,
            accion=ACCION,
            entidad="documento",
            entidad_ref=documento.ref,
            valor_anterior={"eliminado": False},
            valor_nuevo={
                "eliminado": True,
                "tipo": documento.tipo,
                "plazo_dias": dias,
                "estado_expediente": expediente.estado,
            },
            motivo=motivo,
        )
        almacenamiento.borrar_al_confirmar(documento.archivo, documento.archivo_reverso)
    return 1


def aplicar_retencion(ahora):
    """Elimina los documentos con el plazo cumplido y devuelve cuántos eliminó."""
    eliminados = 0
    for tipo in TipoDocumento.values:
        dias = plazo_dias(tipo)
        if dias is None:
            if _sujetos(tipo).exists():
                logger.warning(
                    "Retención: el tipo %s no tiene plazo configurado (RETENCION_DIAS_%s); no se elimina ningún documento.",
                    tipo,
                    tipo.upper(),
                )
            continue
        limite = ahora - datetime.timedelta(days=dias)
        pendientes = list(
            _sujetos(tipo).filter(expediente__estado_cambiado_en__lte=limite).order_by("pk").values_list("pk", flat=True)
        )
        for documento_pk in pendientes:
            eliminados += _eliminar(documento_pk, dias, limite, ahora)
    if eliminados:
        logger.info("Retención: documentos eliminados: %s.", eliminados)
    return eliminados
