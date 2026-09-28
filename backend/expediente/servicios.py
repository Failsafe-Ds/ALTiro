"""Servicios del expediente del maestro (ADR-017; propuesta del S2, §3).

- ``crear_para``: la llama ``identidad.servicios`` en la misma transacción que
  crea ``perfil_maestro`` (invariante perfil_maestro <=> expediente).
- ``declarar_oficios``: el maestro reemplaza su declaración de oficios, solo
  en ``en_revision`` u ``observado``.
- ``cargar_documento``: el maestro carga un documento (RF-04; ADR-015; ADR-017).
"""
import datetime
import re
import uuid

from django.conf import settings
from django.db import transaction

from catalogo.models import Oficio
from expediente import almacenamiento, imagenes, vigencia
from expediente.errores import ErrorEstado, ErroresValidacion
from expediente.models import (
    ESTADOS_EDITABLES,
    Documento,
    EstadoDocumento,
    EstadoExpediente,
    Expediente,
    OficioMaestro,
    TipoDocumento,
)
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


# --- Carga de documentos (RF-04; ADR-015; ADR-017, punto 5) ---

# El maestro puede cargar documentos en todo estado salvo ``rechazado`` (terminal).
ESTADOS_CON_CARGA = frozenset(
    {EstadoExpediente.EN_REVISION, EstadoExpediente.OBSERVADO, EstadoExpediente.APROBADO,
     EstadoExpediente.SUSPENDIDO}
)
_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}")

MENSAJE_TIPO = "Elige qué documento vas a subir."
MENSAJE_NO_CORRESPONDE = "Este dato no corresponde a este documento: quítalo e inténtalo de nuevo."
MENSAJE_OFICIO_FALTA = "Elige el oficio al que corresponde esta licencia."
MENSAJE_OFICIO_NO_REGULADO = "Elige un oficio que necesite licencia SEC, como gas o electricidad."
MENSAJE_OFICIO_NO_DECLARADO = "Primero agrega este oficio a tus oficios y después sube su licencia."
MENSAJE_FECHA_EMISION_FALTA = "Escribe la fecha en que se emitió el documento."
MENSAJE_FECHA_INVALIDA = "Escribe una fecha válida, con día, mes y año."
MENSAJE_EMISION_FUTURA = "La fecha de emisión no puede ser posterior a hoy. Revisa la fecha del documento."
MENSAJE_VENCIMIENTO_ANTERIOR = "La fecha de vencimiento debe ser posterior a la de emisión. Revisa las fechas."
MENSAJE_YA_VENCIDO = (
    "Este documento ya venció. Consigue uno vigente y súbelo. Si tu documento no vence, deja vacía esta fecha."
)
MENSAJE_FOTO_FALTA = "Adjunta la foto del documento."
MENSAJE_ANVERSO_FALTA = "Adjunta la foto del frente de tu cédula."
MENSAJE_REVERSO_FALTA = "Adjunta la foto de la parte de atrás de tu cédula."
MENSAJE_RECHAZADO = "Tu expediente fue rechazado, así que ya no puedes subir documentos."


def _fecha(texto, errores, campo):
    """Fecha en formato AAAA-MM-DD; si no es válida, anota el error y devuelve ``None``."""
    try:
        if not _FECHA.fullmatch(texto):
            raise ValueError
        return datetime.date.fromisoformat(texto)
    except ValueError:
        errores[campo] = MENSAJE_FECHA_INVALIDA
        return None


def _validar_datos(datos, archivos, hoy):
    """Valida los campos de texto y la presencia de fotos. Devuelve ``(limpios, errores)``."""
    errores = {}
    tipo = datos.get("tipo", "")
    if tipo not in TipoDocumento.values:
        errores["tipo"] = MENSAJE_TIPO
        tipo = None

    oficio = None
    codigo = datos.get("oficio", "")
    if tipo == TipoDocumento.LICENCIA_SEC:
        if not codigo:
            errores["oficio"] = MENSAJE_OFICIO_FALTA
        else:
            if _CODIGO.fullmatch(codigo):
                oficio = Oficio.objects.filter(codigo=codigo, regulado=True).first()
            if oficio is None:
                errores["oficio"] = MENSAJE_OFICIO_NO_REGULADO
    elif tipo is not None and codigo:
        errores["oficio"] = MENSAJE_NO_CORRESPONDE

    emision = None
    if not datos.get("fecha_emision"):
        errores["fecha_emision"] = MENSAJE_FECHA_EMISION_FALTA
    else:
        emision = _fecha(datos["fecha_emision"], errores, "fecha_emision")
        if emision is not None and emision > hoy:
            errores["fecha_emision"] = MENSAJE_EMISION_FUTURA

    # Vencimiento opcional (RF-04, CA-11.2): vacío o ausente = sin vencimiento.
    vencimiento = None
    if datos.get("fecha_vencimiento"):
        vencimiento = _fecha(datos["fecha_vencimiento"], errores, "fecha_vencimiento")
        if vencimiento is not None:
            if emision is not None and vencimiento <= emision:
                errores["fecha_vencimiento"] = MENSAJE_VENCIMIENTO_ANTERIOR
            elif not vigencia.vigente(vencimiento, hoy):
                # Decisión del equipo (ADR-015, D-5): no se acepta un documento ya vencido.
                errores["fecha_vencimiento"] = MENSAJE_YA_VENCIDO

    es_cedula = tipo == TipoDocumento.CEDULA_IDENTIDAD
    if "archivo" not in archivos:
        errores["archivo"] = MENSAJE_ANVERSO_FALTA if es_cedula else MENSAJE_FOTO_FALTA
    if es_cedula and "archivo_reverso" not in archivos:
        errores["archivo_reverso"] = MENSAJE_REVERSO_FALTA
    elif tipo is not None and not es_cedula and "archivo_reverso" in archivos:
        errores["archivo_reverso"] = MENSAJE_NO_CORRESPONDE

    limpios = {"tipo": tipo, "oficio": oficio, "fecha_emision": emision, "fecha_vencimiento": vencimiento}
    return limpios, errores


def _recodificar_fotos(archivos, errores):
    """Recodifica cada foto recibida (ADR-015, D-5). Los bytes originales no se conservan."""
    fotos = {}
    for campo in ("archivo", "archivo_reverso"):
        if campo not in archivos or campo in errores:
            continue
        subido = archivos[campo]
        if subido.size > settings.ALTIRO_DOCUMENTO_MAXIMO_BYTES:
            errores[campo] = imagenes.MENSAJE_PESO
            continue
        try:
            fotos[campo] = imagenes.recodificar(subido.read())
        except imagenes.ImagenInvalida as error:
            errores[campo] = error.mensaje
    return fotos


def _reemplazar_actual(expediente, tipo, oficio):
    """Aplica D-11 al documento actual del mismo (tipo, oficio). Devuelve el id para ``reemplaza_a``.

    - Sin revisar (``en_revision``): se borran la fila y sus archivos (estos,
      al confirmar la transacción). Nadie lo revisó, no hay revisión que
      conservar, y ``archivo`` es obligatorio: no existe una fila sin archivo.
      El nuevo documento hereda su ``reemplaza_a`` (el último documento
      revisado, si lo hay), así la cadena de revisados no se corta.
    - Revisado (``observado`` o ``validado``): queda ``reemplazado`` y conserva
      su archivo hasta RNF-26 y V-04.
    """
    actual = (
        Documento.objects.select_for_update()
        .filter(expediente=expediente, tipo=tipo, oficio=oficio)
        .exclude(estado=EstadoDocumento.REEMPLAZADO)
        .first()
    )
    if actual is None:
        return None
    if actual.estado == EstadoDocumento.EN_REVISION:
        anterior = actual.reemplaza_a_id
        almacenamiento.borrar_al_confirmar(actual.archivo, actual.archivo_reverso)
        actual.delete()
        return anterior
    actual.estado = EstadoDocumento.REEMPLAZADO
    actual.save(update_fields=["estado"])
    return actual.pk


def cargar_documento(usuario, datos, archivos):
    """Carga un documento en el expediente propio de ``usuario`` (RF-04; ADR-015; ADR-017, punto 5).

    - ``datos``: textos ``tipo``, ``oficio`` (solo licencia), ``fecha_emision``
      y ``fecha_vencimiento`` (opcional). ``archivos``: ``archivo`` y
      ``archivo_reverso`` (solo cédula), con ``read()`` y ``size``.
    - Datos inválidos: ``ErroresValidacion`` (400, por campo). Expediente
      ``rechazado``: ``ErrorEstado`` (409). En ambos casos no se guarda nada.
    - El expediente se bloquea (``select_for_update``): las cargas del mismo
      maestro y los cambios de curatoría se serializan.
    - Reemplazo según D-11 (``_reemplazar_actual``): nunca hay dos documentos
      actuales del mismo (tipo, oficio); repetir la misma subida no duplica.
    - El maestro nunca cambia el estado del expediente (ADR-017, punto 2).
    Devuelve el expediente.
    """
    hoy = vigencia.hoy_negocio()
    limpios, errores = _validar_datos(datos, archivos, hoy)
    fotos = _recodificar_fotos(archivos, errores)
    if errores:
        raise ErroresValidacion(errores)

    tipo, oficio = limpios["tipo"], limpios["oficio"]
    ref = uuid.uuid4()
    escritos = []
    try:
        with transaction.atomic():
            expediente = Expediente.objects.select_for_update().get(perfil_maestro_id=usuario.pk)
            if expediente.estado not in ESTADOS_CON_CARGA:
                raise ErrorEstado(MENSAJE_RECHAZADO)
            if oficio is not None and not OficioMaestro.objects.filter(
                maestro_id=expediente.perfil_maestro_id, oficio=oficio
            ).exists():
                raise ErroresValidacion({"oficio": MENSAJE_OFICIO_NO_DECLARADO})
            reemplaza_a_id = _reemplazar_actual(expediente, tipo, oficio)
            escritos.append(almacenamiento.guardar(ref, almacenamiento.ANVERSO, fotos["archivo"]))
            if "archivo_reverso" in fotos:
                escritos.append(almacenamiento.guardar(ref, almacenamiento.REVERSO, fotos["archivo_reverso"]))
            Documento.objects.create(
                ref=ref,
                expediente=expediente,
                tipo=tipo,
                oficio=oficio,
                fecha_emision=limpios["fecha_emision"],
                fecha_vencimiento=limpios["fecha_vencimiento"],
                archivo=escritos[0],
                archivo_reverso=escritos[1] if len(escritos) > 1 else None,
                reemplaza_a_id=reemplaza_a_id,
            )
    except BaseException:
        # La transacción no se confirmó: los archivos nuevos no quedan huérfanos.
        for nombre in escritos:
            almacenamiento.borrar(nombre)
        raise
    return expediente
