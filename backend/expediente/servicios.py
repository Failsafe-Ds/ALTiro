"""Servicios del expediente del maestro (ADR-017; propuesta del S2, §3).

- ``crear_para``: la llama ``identidad.servicios`` en la misma transacción que
  crea ``perfil_maestro`` (invariante perfil_maestro <=> expediente).
- ``declarar_oficios``: el maestro reemplaza su declaración de oficios, solo
  en ``en_revision`` u ``observado``.
"""
import re

from django.db import transaction

from catalogo.models import Oficio
from expediente.errores import ErrorEstado
from expediente.models import ESTADOS_EDITABLES, EstadoExpediente, Expediente, OficioMaestro
from identidad.errores import ErrorValidacion

_CODIGO = re.compile(r"[a-z0-9_]{1,40}")
# Tope defensivo del tamaño de la lista recibida (el catálogo tiene 8 oficios).
_MAXIMO_RECIBIDOS = 50

_MENSAJE_ELIGE = "Elige al menos un oficio de la lista."
_MENSAJE_NO_EXISTE = "Uno de los oficios elegidos no está en la lista. Elige tus oficios de la lista."
_TEXTO_ESTADO = {
    EstadoExpediente.APROBADO: "aprobado",
    EstadoExpediente.RECHAZADO: "rechazado",
    EstadoExpediente.SUSPENDIDO: "suspendido",
}


def crear_para(perfil_maestro):
    """Crea el expediente ``en_revision`` del perfil. Debe ejecutarse dentro de la transacción del perfil."""
    return Expediente.objects.create(perfil_maestro=perfil_maestro)


def _oficios_de(codigos):
    """Valida la lista recibida y devuelve los ``Oficio`` elegidos, sin repetir."""
    if not isinstance(codigos, list) or not codigos:
        raise ErrorValidacion("oficios", _MENSAJE_ELIGE)
    if len(codigos) > _MAXIMO_RECIBIDOS or not all(
        isinstance(c, str) and _CODIGO.fullmatch(c) for c in codigos
    ):
        raise ErrorValidacion("oficios", _MENSAJE_NO_EXISTE)
    elegidos = set(codigos)
    oficios = list(Oficio.objects.filter(codigo__in=elegidos))
    if len(oficios) != len(elegidos):
        raise ErrorValidacion("oficios", _MENSAJE_NO_EXISTE)
    return oficios


@transaction.atomic
def declarar_oficios(expediente, codigos):
    """Reemplaza los oficios declarados por el maestro dueño de ``expediente``.

    - ``codigos``: lista de códigos del catálogo, al menos uno (400 si no).
    - Solo en ``en_revision`` u ``observado``; en otro estado, ``ErrorEstado`` (409).
    El estado se lee con la fila bloqueada para no competir con un cambio de
    estado de curatoría.
    """
    oficios = _oficios_de(codigos)
    expediente = Expediente.objects.select_for_update().get(pk=expediente.pk)
    if expediente.estado not in ESTADOS_EDITABLES:
        raise ErrorEstado(
            f"Tu expediente está {_TEXTO_ESTADO[expediente.estado]}, así que ya no puedes cambiar tus oficios."
        )
    maestro_id = expediente.perfil_maestro_id
    nuevos = {oficio.pk for oficio in oficios}
    OficioMaestro.objects.filter(maestro_id=maestro_id).exclude(oficio_id__in=nuevos).delete()
    actuales = set(OficioMaestro.objects.filter(maestro_id=maestro_id).values_list("oficio_id", flat=True))
    OficioMaestro.objects.bulk_create(
        [OficioMaestro(maestro_id=maestro_id, oficio_id=pk) for pk in sorted(nuevos - actuales)]
    )
    return expediente
