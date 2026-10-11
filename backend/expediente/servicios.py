"""Servicios del expediente del maestro (ADR-017; propuesta del S2, §3).

- ``crear_para``: la llama ``identidad.servicios`` en la misma transacción que
  crea ``perfil_maestro`` (invariante perfil_maestro <=> expediente).
- ``declarar_oficios``: el maestro reemplaza su declaración de oficios, solo
  en ``en_revision`` u ``observado``.
- ``cargar_documento``: el maestro carga un documento (RF-04; ADR-015; ADR-017).
- ``cambiar_estado``: curatoría cambia el estado del expediente (RF-32, RF-33,
  CA-19.1 a CA-19.4; ADR-017, punto 2; propuesta del S2, §3).
- ``revisar_documento``: curatoría valida u observa un documento (CA-17.2;
  ADR-017, punto 4).
"""
import datetime
import re
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from autorizacion.excepciones import ConflictoDeInteres
from bitacora import servicios as bitacora
from catalogo.models import Oficio
from comun.texto import FALTA, INVALIDO, LARGO, limpiar_texto, recortar
from expediente import almacenamiento, imagenes, vigencia
from expediente.politicas import PoliticaDocumentoCuratoria, PoliticaExpedienteCuratoria
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
MENSAJE_OFICIO_DADO_DE_BAJA = (
    "Uno de los oficios elegidos ya no se ofrece en AlTiro. Quítalo y elige tus oficios de la lista."
)
# Lo ve el maestro (RNF-17): sin "expediente".
MENSAJES_OFICIOS_NO_EDITABLES = {
    EstadoExpediente.APROBADO: "Tu postulación ya fue aprobada, así que no puedes cambiar tus oficios aquí.",
    EstadoExpediente.RECHAZADO: "Tu postulación no fue aprobada, así que ya no puedes cambiar tus oficios.",
    EstadoExpediente.SUSPENDIDO: "Tu cuenta de maestro está suspendida, así que no puedes cambiar tus oficios.",
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
    - Un oficio dado de baja por comercial (``activo=false``) no se agrega en
      una declaración nueva (400 en ``oficios``); si ya estaba declarado, se
      conserva (propuesta del S3, §8.4).
    El estado se lee con la fila bloqueada para no competir con un cambio de
    estado de curatoría.
    """
    oficios = _oficios_de(codigos)
    expediente = Expediente.objects.select_for_update().get(pk=expediente.pk)
    if expediente.estado not in ESTADOS_EDITABLES:
        raise ErrorEstado(MENSAJES_OFICIOS_NO_EDITABLES[expediente.estado])
    maestro_id = expediente.perfil_maestro_id
    nuevos = {oficio.pk for oficio in oficios}
    actuales = set(OficioMaestro.objects.filter(maestro_id=maestro_id).values_list("oficio_id", flat=True))
    if any(not oficio.activo and oficio.pk not in actuales for oficio in oficios):
        raise ErrorValidacion("oficios", MENSAJE_OFICIO_DADO_DE_BAJA)
    OficioMaestro.objects.filter(maestro_id=maestro_id).exclude(oficio_id__in=nuevos).delete()
    actuales &= nuevos
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
MENSAJE_OFICIO_NO_REGULADO = (
    "Elige un oficio que necesite licencia de la Superintendencia de Electricidad y Combustibles (SEC), "
    "como gas o electricidad."
)
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
MENSAJE_RECHAZADO = "Tu postulación no fue aprobada, así que ya no puedes enviar documentos."


def _fecha(texto, errores, campo):
    """Fecha en formato AAAA-MM-DD (recortada); si no es válida, anota el error y devuelve ``None``."""
    texto = recortar(texto)
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

    # Las fechas se recortan antes de validar: solo espacios cuenta como vacío (CLAUDE.md §8-§9).
    emision = None
    if not recortar(datos.get("fecha_emision")):
        errores["fecha_emision"] = MENSAJE_FECHA_EMISION_FALTA
    else:
        emision = _fecha(datos["fecha_emision"], errores, "fecha_emision")
        if emision is not None and emision > hoy:
            errores["fecha_emision"] = MENSAJE_EMISION_FUTURA

    # Vencimiento opcional (RF-04, CA-11.2): vacío o ausente = sin vencimiento.
    vencimiento = None
    if recortar(datos.get("fecha_vencimiento")):
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


# --- Curatoría: estado del expediente y revisión de documentos ---

# Tabla de transiciones de la propuesta del S2, §3 (ADR-017, punto 2). Cualquier
# otra, incluida la que no cambia el estado, responde 409. ``rechazado`` es terminal.
TRANSICIONES = {
    EstadoExpediente.EN_REVISION: frozenset(
        {EstadoExpediente.APROBADO, EstadoExpediente.OBSERVADO, EstadoExpediente.RECHAZADO}
    ),
    EstadoExpediente.OBSERVADO: frozenset(
        {EstadoExpediente.APROBADO, EstadoExpediente.EN_REVISION, EstadoExpediente.RECHAZADO}
    ),
    EstadoExpediente.APROBADO: frozenset({EstadoExpediente.SUSPENDIDO}),
    EstadoExpediente.SUSPENDIDO: frozenset({EstadoExpediente.APROBADO}),
    EstadoExpediente.RECHAZADO: frozenset(),
}

# Tope defensivo del motivo escrito (validación de entrada; no es una regla del informe).
MOTIVO_LARGO_MAXIMO = 1000

RESULTADO_VALIDAR = "validar"
RESULTADO_OBSERVAR = "observar"
MOTIVO_VALIDADO = "Documento revisado y validado"

MENSAJE_MOTIVO_FALTA = "Escribe el motivo. Es obligatorio y queda registrado."
MENSAJE_MOTIVO_OBSERVACION_FALTA = "Escribe qué debe corregir el maestro. Es obligatorio y el maestro lo verá."
MENSAJE_MOTIVO_LARGO = (
    f"El motivo puede tener hasta {MOTIVO_LARGO_MAXIMO} caracteres. Acórtalo e inténtalo de nuevo."
)
MENSAJE_MOTIVO_INVALIDO = "El motivo tiene caracteres que no se pueden usar. Escríbelo de nuevo."
MENSAJE_ESTADO_NUEVO = "Elige el nuevo estado del expediente."
MENSAJE_RESULTADO = "Elige si validas u observas el documento."
MENSAJE_RECARGA = "Vuelve a cargar la página e inténtalo de nuevo."
MENSAJE_EXPEDIENTE_CAMBIO = "El expediente cambió mientras lo revisabas. Vuelve a cargar la página."
MENSAJE_DOCUMENTO_CAMBIO = "El documento cambió mientras lo revisabas. Vuelve a cargar la página."
MENSAJE_DOCUMENTO_REVISADO = (
    "Este documento ya fue revisado. Si hay que corregir algo, cambia el estado del expediente con un motivo."
)
MENSAJE_DOCUMENTO_ELIMINADO = (
    "Este documento se eliminó al cumplirse su plazo de retención y ya no se puede revisar."
)

_DESCRIPCION_REQUISITO = {
    vigencia.CEDULA: "la cédula de identidad por ambos lados, validada",
    vigencia.ANTECEDENTES: "el certificado de antecedentes, validado",
}


def _texto_motivo(valor, obligatorio, mensaje_falta):
    """Motivo escrito sin espacios sobrantes. Devuelve ``(texto, mensaje_de_error)``."""
    texto, problema = limpiar_texto(valor, MOTIVO_LARGO_MAXIMO, obligatorio=obligatorio)
    if problema:
        return None, {FALTA: mensaje_falta, INVALIDO: MENSAJE_MOTIVO_INVALIDO, LARGO: MENSAJE_MOTIVO_LARGO}[problema]
    return texto, None


def _opcion(valor, opciones):
    return valor if isinstance(valor, str) and valor in opciones else None


def mensaje_transicion(actual, nuevo):
    return (
        f"Un expediente «{EstadoExpediente(actual).label.lower()}» no puede pasar a "
        f"«{EstadoExpediente(nuevo).label.lower()}». Elige otro estado."
    )


def describir_faltante(tipo, oficio):
    if tipo == vigencia.LICENCIA_SEC:
        return f"la licencia SEC de {oficio.nombre}, validada y vigente"
    return _DESCRIPCION_REQUISITO[tipo]


def mensaje_faltantes(faltantes):
    """Mensaje explícito de RF-33 y CA-19.2: nombra cada documento y oficio que falta."""
    detalle = "; ".join(describir_faltante(tipo, oficio) for tipo, oficio in faltantes)
    return f"No se puede aprobar el expediente: falta {detalle}."


def _sin_conflicto(politica, usuario, objeto):
    """Defensa en profundidad dentro de la transacción: la misma regla que aplica la vista."""
    if politica.conflicto(usuario, objeto):
        raise ConflictoDeInteres(politica.entidad, objeto.ref)


def cambiar_estado(usuario, expediente, datos):
    """Curatoría cambia el estado de ``expediente`` (RF-32, RF-33, CA-19.1 a CA-19.4).

    ``datos``: ``estado_nuevo``, ``estado_actual`` (el que vio quien revisa) y ``motivo``.

    - Datos inválidos o motivo vacío: ``ErroresValidacion`` (400, CA-19.1).
    - Quien cambia es el dueño: ``ConflictoDeInteres`` (403, CA-19.4).
    - ``estado_actual`` distinto del guardado: ``ErrorEstado`` (409).
    - Transición fuera de ``TRANSICIONES``: ``ErrorEstado`` (409).
    - Aprobar (desde ``en_revision``, ``observado`` o ``suspendido``) con
      requisitos faltantes: ``ErrorEstado`` (409) con un mensaje que nombra
      cada documento y oficio (RF-33, CA-19.2; ADR-017, punto 3 y E-1).
    En esos casos no cambia nada ni se escribe la bitácora. Si cambia, la
    entrada de la bitácora va en la misma transacción (CA-19.3).
    Devuelve el expediente actualizado.
    """
    errores = {}
    estado_nuevo = _opcion(datos.get("estado_nuevo"), EstadoExpediente.values)
    if estado_nuevo is None:
        errores["estado_nuevo"] = MENSAJE_ESTADO_NUEVO
    estado_actual = _opcion(datos.get("estado_actual"), EstadoExpediente.values)
    if estado_actual is None:
        errores["estado_actual"] = MENSAJE_RECARGA
    motivo, error = _texto_motivo(datos.get("motivo"), True, MENSAJE_MOTIVO_FALTA)
    if error:
        errores["motivo"] = error
    if errores:
        raise ErroresValidacion(errores)

    with transaction.atomic():
        expediente = Expediente.objects.select_for_update().get(pk=expediente.pk)
        _sin_conflicto(PoliticaExpedienteCuratoria(), usuario, expediente)
        anterior = expediente.estado
        if anterior != estado_actual:
            raise ErrorEstado(MENSAJE_EXPEDIENTE_CAMBIO)
        if estado_nuevo not in TRANSICIONES[anterior]:
            raise ErrorEstado(mensaje_transicion(anterior, estado_nuevo))
        if estado_nuevo == EstadoExpediente.APROBADO:
            faltantes = vigencia.faltantes_para_aprobar(expediente)
            if faltantes:
                raise ErrorEstado(mensaje_faltantes(faltantes))
        expediente.estado = estado_nuevo
        expediente.estado_motivo = motivo
        expediente.estado_cambiado_en = timezone.now()
        expediente.estado_cambiado_por = usuario
        expediente.save(update_fields=["estado", "estado_motivo", "estado_cambiado_en", "estado_cambiado_por"])
        # Solo el estado: sin datos personales (ADR-010).
        bitacora.registrar(
            autor=usuario,
            accion="expediente.cambiar_estado",
            entidad="expediente",
            entidad_ref=expediente.ref,
            valor_anterior={"estado": anterior},
            valor_nuevo={"estado": estado_nuevo},
            motivo=motivo,
        )
    return expediente


def revisar_documento(usuario, documento, datos):
    """Curatoría valida u observa un documento en revisión (CA-17.2; ADR-017, punto 4).

    ``datos``: ``resultado`` (``validar`` u ``observar``), ``estado_actual`` y ``motivo``.

    - Observar exige motivo; se guarda en ``motivo_observacion`` y el dueño lo
      ve (CA-17.2), sin saber quién revisó (ADR-010, E-1).
    - Validar registra en la bitácora el motivo fijo "Documento revisado y
      validado", completado con el texto opcional.
    - Solo se revisa un documento ``en_revision``, una vez.
    Errores: 400 (``ErroresValidacion``), 403 (``ConflictoDeInteres``) o 409
    (``ErrorEstado``), sin cambios ni bitácora. Devuelve el documento.
    """
    errores = {}
    resultado = _opcion(datos.get("resultado"), {RESULTADO_VALIDAR, RESULTADO_OBSERVAR})
    if resultado is None:
        errores["resultado"] = MENSAJE_RESULTADO
    estado_actual = _opcion(datos.get("estado_actual"), EstadoDocumento.values)
    if estado_actual is None:
        errores["estado_actual"] = MENSAJE_RECARGA
    observar = resultado == RESULTADO_OBSERVAR
    motivo, error = _texto_motivo(datos.get("motivo"), observar, MENSAJE_MOTIVO_OBSERVACION_FALTA)
    if error:
        errores["motivo"] = error
    if errores:
        raise ErroresValidacion(errores)

    with transaction.atomic():
        # Mismo orden de bloqueo que la carga: primero el expediente, después el documento.
        Expediente.objects.select_for_update().get(pk=documento.expediente_id)
        documento = Documento.objects.select_for_update().select_related("expediente").get(pk=documento.pk)
        _sin_conflicto(PoliticaDocumentoCuratoria(), usuario, documento)
        anterior = documento.estado
        if anterior != estado_actual:
            raise ErrorEstado(MENSAJE_DOCUMENTO_CAMBIO)
        if anterior != EstadoDocumento.EN_REVISION:
            raise ErrorEstado(MENSAJE_DOCUMENTO_REVISADO)
        # RNF-26 (ADR-026, E-9): sin archivo no hay nada que revisar.
        if documento.eliminado_en is not None:
            raise ErrorEstado(MENSAJE_DOCUMENTO_ELIMINADO)
        if observar:
            documento.estado = EstadoDocumento.OBSERVADO
            documento.motivo_observacion = motivo
            motivo_bitacora = motivo
        else:
            documento.estado = EstadoDocumento.VALIDADO
            documento.motivo_observacion = ""
            motivo_bitacora = f"{MOTIVO_VALIDADO}. {motivo}" if motivo else MOTIVO_VALIDADO
        documento.revisado_en = timezone.now()
        documento.revisado_por = usuario
        documento.save(update_fields=["estado", "motivo_observacion", "revisado_en", "revisado_por"])
        bitacora.registrar(
            autor=usuario,
            accion="documento.observar" if observar else "documento.validar",
            entidad="documento",
            entidad_ref=documento.ref,
            valor_anterior={"estado": anterior},
            valor_nuevo={"estado": documento.estado},
            motivo=motivo_bitacora,
        )
    return documento
