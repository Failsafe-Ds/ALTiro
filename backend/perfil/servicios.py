"""Servicios del maestro sobre sus servicios ofrecidos (RF-05, HU-12, CA-12.1; ADR-019, puntos 1 y 3).

- ``crear_perfil_publico_para``: la llama ``identidad.servicios`` en la misma
  transacción que crea ``perfil_maestro`` (igual que el expediente).
- ``ofrecer_servicio``, ``cambiar_servicio`` y ``retirar_servicio``: el maestro
  administra sus servicios en cualquier estado del expediente salvo
  ``rechazado`` (409, D-7). Solo un expediente ``aprobado`` publica, y eso lo
  decide ``perfil.publicacion`` al leer.

Sin borradores: si falta la modalidad o el monto, 400 en ese campo (CA-12.1).
Mensajes en el lenguaje del oficio (RNF-15, RNF-17).
"""
import re
import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone

from catalogo.models import MONTO_MAXIMO, Modalidad, Servicio, ServicioModalidad
from expediente.errores import ErrorEstado, ErroresValidacion
from expediente.models import EstadoExpediente, Expediente, OficioMaestro
from perfil.models import PerfilPublico, ServicioMaestro

MENSAJE_SERVICIO_FALTA = "Elige un servicio de la lista."
MENSAJE_SERVICIO_OFICIO_NO_DECLARADO = (
    "Este servicio es de un oficio que no está entre tus oficios. Elige un servicio de tus oficios."
)
MENSAJE_SERVICIO_REPETIDO = "Ya ofreces este servicio. Cambia su precio en tu lista en vez de agregarlo otra vez."
MENSAJE_MODALIDAD_FALTA = "Elige si cobras por trabajo o por hora."
MENSAJE_MODALIDAD_NO_ADMITIDA = "Este servicio no se cobra de esa forma. Elige {opciones}."
MENSAJE_MONTO_FALTA = "Escribe cuánto cobras, en pesos."
MENSAJE_MONTO_INVALIDO = "Escribe el monto en pesos, solo con números, mayor que cero y hasta 10.000.000."
MENSAJE_SIN_CAMBIOS = "Cambia la forma de cobro o el monto antes de guardar."
MENSAJE_RECHAZADO = "Tu postulación no fue aprobada, así que ya no puedes ofrecer servicios."
MENSAJE_RETIRADO = "Ya quitaste este servicio. Si quieres ofrecerlo otra vez, agrégalo de nuevo."

_TEXTO_MODALIDAD = {Modalidad.POR_TRABAJO: "por trabajo", Modalidad.POR_HORA: "por hora"}
_MONTO_TEXTO = re.compile(r"[0-9]{1,9}")


def crear_perfil_publico_para(perfil_maestro):
    """Crea el perfil público del maestro. Debe ejecutarse dentro de la transacción del perfil."""
    return PerfilPublico.objects.create(perfil_maestro=perfil_maestro)


# --- Validación ---


def _monto(datos, errores):
    """Entero en pesos, > 0 y <= 10.000.000 (ADR-019, punto 1). Acepta un número o un texto de solo dígitos."""
    if "monto" not in datos or datos["monto"] in (None, ""):
        errores["monto"] = MENSAJE_MONTO_FALTA
        return None
    valor = datos["monto"]
    if isinstance(valor, str) and _MONTO_TEXTO.fullmatch(valor):
        valor = int(valor)
    if not isinstance(valor, int) or isinstance(valor, bool) or not 0 < valor <= MONTO_MAXIMO:
        errores["monto"] = MENSAJE_MONTO_INVALIDO
        return None
    return valor


def _modalidad(datos, errores):
    valor = datos.get("modalidad")
    if valor in (None, ""):
        errores["modalidad"] = MENSAJE_MODALIDAD_FALTA
        return None
    if not isinstance(valor, str) or valor not in Modalidad.values:
        errores["modalidad"] = MENSAJE_MODALIDAD_FALTA
        return None
    return valor


def _servicio_del_catalogo(datos, errores):
    """Servicio activo del catálogo (de un oficio activo) por su ``ref``."""
    valor = datos.get("servicio")
    try:
        ref = uuid.UUID(valor) if isinstance(valor, str) else None
    except ValueError:
        ref = None
    servicio = (
        Servicio.objects.select_related("oficio").filter(ref=ref, activo=True, oficio__activo=True).first()
        if ref
        else None
    )
    if servicio is None:
        errores["servicio"] = MENSAJE_SERVICIO_FALTA
    return servicio


def _exigir_modalidad_admitida(servicio, modalidad, errores):
    admitidas = sorted(
        ServicioModalidad.objects.filter(servicio=servicio).values_list("modalidad", flat=True)
    )
    if modalidad not in admitidas:
        opciones = " o ".join(_TEXTO_MODALIDAD[Modalidad(m)] for m in admitidas) or "otro servicio"
        errores["modalidad"] = MENSAJE_MODALIDAD_NO_ADMITIDA.format(opciones=opciones)


def expediente_editable(maestro_id, mensaje_rechazado):
    """Bloquea el expediente del maestro y exige que no esté ``rechazado`` (D-7).

    Es el bloqueo por maestro de servicios, cobertura, agenda y foto: hay un
    expediente por maestro, así que ``select_for_update`` sobre esa fila
    serializa las escrituras del mismo maestro entre sí y con curatoría
    (ADR-020, punto 3).
    """
    expediente = Expediente.objects.select_for_update().get(perfil_maestro_id=maestro_id)
    if expediente.estado == EstadoExpediente.RECHAZADO:
        raise ErrorEstado(mensaje_rechazado)
    return expediente


def _expediente_editable(maestro_id):
    return expediente_editable(maestro_id, MENSAJE_RECHAZADO)


# --- Casos de uso ---


def ofrecer_servicio(usuario, datos):
    """El maestro agrega un servicio del catálogo con modalidad y monto (RF-05, CA-12.1, CA-20.1).

    ``datos``: ``servicio`` (ref del catálogo), ``modalidad`` y ``monto``, todos obligatorios.
    - Expediente ``rechazado``: ``ErrorEstado`` (409).
    - Falta o no es válido un dato: ``ErroresValidacion`` (400 por campo).
    - El servicio no es de un oficio declarado, o la modalidad no la admite el
      catálogo: 400 en ese campo.
    - Ya ofrece ese servicio (activo): 400 en ``servicio``.
    """
    with transaction.atomic():
        _expediente_editable(usuario.pk)
        errores = {}
        servicio = _servicio_del_catalogo(datos, errores)
        modalidad = _modalidad(datos, errores)
        monto = _monto(datos, errores)
        if servicio is not None:
            if not OficioMaestro.objects.filter(maestro_id=usuario.pk, oficio_id=servicio.oficio_id).exists():
                errores["servicio"] = MENSAJE_SERVICIO_OFICIO_NO_DECLARADO
            elif ServicioMaestro.objects.filter(
                maestro_id=usuario.pk, servicio=servicio, retirado_en__isnull=True
            ).exists():
                errores["servicio"] = MENSAJE_SERVICIO_REPETIDO
            if modalidad is not None:
                _exigir_modalidad_admitida(servicio, modalidad, errores)
        if errores:
            raise ErroresValidacion(errores)
        try:
            with transaction.atomic():
                return ServicioMaestro.objects.create(
                    maestro_id=usuario.pk, servicio=servicio, modalidad=modalidad, monto=monto
                )
        except IntegrityError:
            # Carrera con otra petición del mismo maestro (único parcial en la BD).
            raise ErroresValidacion({"servicio": MENSAJE_SERVICIO_REPETIDO}) from None


def cambiar_servicio(servicio_maestro, datos):
    """El maestro cambia la modalidad o el monto de su servicio (al menos uno)."""
    with transaction.atomic():
        _expediente_editable(servicio_maestro.maestro_id)
        servicio_maestro = (
            ServicioMaestro.objects.select_for_update().select_related("servicio").get(pk=servicio_maestro.pk)
        )
        if servicio_maestro.retirado_en is not None:
            raise ErrorEstado(MENSAJE_RETIRADO)
        errores = {}
        if "modalidad" not in datos and "monto" not in datos:
            errores["monto"] = MENSAJE_SIN_CAMBIOS
        modalidad = _modalidad(datos, errores) if "modalidad" in datos else servicio_maestro.modalidad
        monto = _monto(datos, errores) if "monto" in datos else servicio_maestro.monto
        if modalidad is not None and "modalidad" in datos:
            _exigir_modalidad_admitida(servicio_maestro.servicio, modalidad, errores)
        if errores:
            raise ErroresValidacion(errores)
        servicio_maestro.modalidad = modalidad
        servicio_maestro.monto = monto
        servicio_maestro.actualizado_en = timezone.now()
        servicio_maestro.save(update_fields=["modalidad", "monto", "actualizado_en"])
    return servicio_maestro


def retirar_servicio(servicio_maestro):
    """Baja lógica (``retirado_en``): el servicio deja de mostrarse y se conserva para S4 (ADR-019, punto 1)."""
    with transaction.atomic():
        _expediente_editable(servicio_maestro.maestro_id)
        servicio_maestro = ServicioMaestro.objects.select_for_update().get(pk=servicio_maestro.pk)
        if servicio_maestro.retirado_en is not None:
            raise ErrorEstado(MENSAJE_RETIRADO)
        servicio_maestro.retirado_en = timezone.now()
        servicio_maestro.save(update_fields=["retirado_en"])
    return servicio_maestro
