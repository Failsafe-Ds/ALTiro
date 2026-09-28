"""Rutas de curatoría (HU-19, RF-32, RF-33, CA-17.2, CA-19.1 a CA-19.4, HU-25; propuesta del S2, §4).

Todas exigen el rol ``curatoria`` (``@requiere_rol``: 403 registrado si falta)
y, cuando reciben una referencia, aplican la política con conflicto de interés
(``obtener_autorizado``; ADR-011, E-2): quien es dueño del expediente recibe un
403 accionable y registrado, también en lectura, y su expediente no aparece en
la cola. Una referencia inexistente responde el 404 neutro, sin registro.

Minimización de datos (CLAUDE.md §8; HU-25: "función administrativa justificada"):

- La cola no entrega el RUT.
- El detalle entrega nombre y RUT, que curatoría necesita para contrastar la
  identidad con la cédula y el certificado de antecedentes. No entrega
  teléfono ni correo: ninguna HU ni RF asigna a curatoría una función de
  contacto; la comunicación con el maestro es el motivo escrito del estado y
  de cada observación (CA-17.2), que el maestro ve en su expediente.
- Nunca se entregan ids internos, nombres de archivo ni rutas del volumen.
- Quién revisó solo aparece en el historial, que solo ve curatoría (ADR-010, E-1).

Todas las respuestas llevan ``Cache-Control: no-store``.
"""
from django.db.models import Count, Q
from django.http import JsonResponse

from autorizacion.acceso import obtener_autorizado
from autorizacion.decoradores import requiere_rol
from bitacora.models import AutorTipo, Bitacora
from catalogo.vistas import datos_oficio
from comun.api import ErrorSolicitud, ErroresDeCampo, leer_json, manejar_errores, metodos, respuesta_error
from expediente import servicios, vigencia
from expediente.errores import ErrorEstado, ErroresValidacion
from expediente.models import Documento, EstadoDocumento, EstadoExpediente, Expediente, OficioMaestro
from expediente.politicas import PoliticaDocumentoCuratoria, PoliticaExpedienteCuratoria
from identidad.models import Usuario

TAMANO_PAGINA = 20
PARAMETROS_COLA = frozenset({"estado", "pagina"})
CAMPOS_CAMBIAR_ESTADO = {"estado_nuevo", "estado_actual", "motivo"}
CAMPOS_REVISION = {"resultado", "estado_actual", "motivo"}

MENSAJE_FILTRO_INVALIDO = "Uno de los filtros no es válido. Recarga la página e inténtalo de nuevo."
AUTOR_SISTEMA = "Sistema"
AUTOR_DESCONOCIDO = "Persona no disponible"


def _json(datos, estado=200):
    respuesta = JsonResponse(datos, status=estado)
    respuesta["Cache-Control"] = "no-store"
    return respuesta


def _fecha(valor):
    return valor.isoformat() if valor else None


def _oficio_resumido(oficio):
    return {"codigo": oficio.codigo, "nombre": oficio.nombre} if oficio else None


def _oficios_de(expediente):
    return [
        om.oficio
        for om in OficioMaestro.objects.filter(maestro_id=expediente.perfil_maestro_id)
        .select_related("oficio")
        .order_by("oficio__orden", "oficio__codigo")
    ]


def _faltantes(faltantes):
    return [{"tipo": tipo, "oficio": _oficio_resumido(oficio)} for tipo, oficio in faltantes]


# --- Cola ---


def _filtros_cola(request):
    parametros = request.GET
    if set(parametros) - PARAMETROS_COLA or any(len(parametros.getlist(p)) > 1 for p in parametros):
        raise ErrorSolicitud(MENSAJE_FILTRO_INVALIDO)
    estado = parametros.get("estado")
    if estado is not None and estado not in EstadoExpediente.values:
        raise ErrorSolicitud(MENSAJE_FILTRO_INVALIDO)
    texto_pagina = parametros.get("pagina", "1")
    if not texto_pagina.isascii() or not texto_pagina.isdigit() or int(texto_pagina) < 1:
        raise ErrorSolicitud(MENSAJE_FILTRO_INVALIDO)
    return estado, int(texto_pagina)


def _datos_en_cola(expediente, hoy):
    """Lista explícita de la cola: sin RUT, sin contacto, sin ids internos."""
    return {
        "ref": str(expediente.ref),
        "nombre": expediente.perfil_maestro.usuario.nombre,
        "estado": expediente.estado,
        "creado_en": _fecha(expediente.creado_en),
        "oficios": [datos_oficio(oficio) for oficio in _oficios_de(expediente)],
        "faltantes_para_aprobar": len(vigencia.faltantes_para_aprobar(expediente, hoy)),
        "documentos_en_revision": expediente.documentos_en_revision,
    }


@metodos("GET")
@requiere_rol("curatoria")
@manejar_errores
def cola(request):
    """Cola de expedientes, paginada, con filtro ``?estado=``. Excluye el expediente propio (ADR-011, E-2)."""
    estado, pagina = _filtros_cola(request)
    consulta = Expediente.objects.exclude(perfil_maestro_id=request.usuario.pk)
    if estado is not None:
        consulta = consulta.filter(estado=estado)
    total = consulta.count()
    inicio = (pagina - 1) * TAMANO_PAGINA
    expedientes = (
        consulta.select_related("perfil_maestro__usuario")
        .annotate(
            documentos_en_revision=Count("documentos", filter=Q(documentos__estado=EstadoDocumento.EN_REVISION))
        )
        .order_by("creado_en", "pk")[inicio : inicio + TAMANO_PAGINA]
    )
    hoy = vigencia.hoy_negocio()
    return _json(
        {
            "expedientes": [_datos_en_cola(expediente, hoy) for expediente in expedientes],
            "pagina": pagina,
            "tamano_pagina": TAMANO_PAGINA,
            "total": total,
        }
    )


# --- Detalle ---


def _datos_documento(documento, hoy):
    """Lista explícita para curatoría: sin archivos, rutas ni ids internos."""
    return {
        "ref": str(documento.ref),
        "tipo": documento.tipo,
        "oficio": _oficio_resumido(documento.oficio),
        "estado": documento.estado,
        "fecha_emision": documento.fecha_emision.isoformat(),
        "fecha_vencimiento": _fecha(documento.fecha_vencimiento),
        "vigente": vigencia.vigente(documento.fecha_vencimiento, hoy),
        "motivo_observacion": documento.motivo_observacion,
        "tiene_reverso": documento.archivo_reverso is not None,
        "cargado_en": _fecha(documento.cargado_en),
        "revisado_en": _fecha(documento.revisado_en),
    }


def datos_detalle(expediente):
    hoy = vigencia.hoy_negocio()
    usuario = Usuario.objects.only("nombre").get(pk=expediente.perfil_maestro_id)
    rut = expediente.perfil_maestro.rut
    return {
        "ref": str(expediente.ref),
        "nombre": usuario.nombre,
        "rut": rut,
        "estado": expediente.estado,
        "motivo": expediente.estado_motivo,
        "estado_cambiado_en": _fecha(expediente.estado_cambiado_en),
        "creado_en": _fecha(expediente.creado_en),
        "oficios": [
            {**datos_oficio(oficio), "habilitado": vigencia.oficio_habilitado(expediente, oficio, hoy)}
            for oficio in _oficios_de(expediente)
        ],
        "documentos": [_datos_documento(d, hoy) for d in vigencia.documentos_actuales(expediente)],
        "faltantes_para_aprobar": _faltantes(vigencia.faltantes_para_aprobar(expediente, hoy)),
        # Estados a los que puede pasar según la tabla de transiciones (propuesta del S2, §3).
        "estados_siguientes": sorted(servicios.TRANSICIONES[EstadoExpediente(expediente.estado)]),
    }


def _expediente_autorizado(request, ref):
    return obtener_autorizado(
        Expediente.objects.select_related("perfil_maestro"), ref, request.usuario, PoliticaExpedienteCuratoria()
    )


@metodos("GET")
@requiere_rol("curatoria")
def detalle(request, ref):
    return _json({"expediente": datos_detalle(_expediente_autorizado(request, ref))})


# --- Cambio de estado ---


@metodos("POST")
@requiere_rol("curatoria")
@manejar_errores
def cambiar_estado(request, ref):
    """RF-32, RF-33, CA-19.1 a CA-19.4. Primero la política y después el cuerpo."""
    expediente = _expediente_autorizado(request, ref)
    datos = leer_json(request, CAMPOS_CAMBIAR_ESTADO)
    try:
        expediente = servicios.cambiar_estado(request.usuario, expediente, datos)
    except ErroresValidacion as error:
        raise ErroresDeCampo(error.errores) from None
    except ErrorEstado as error:
        return respuesta_error(409, error.mensaje)
    return _json({"expediente": datos_detalle(expediente)})


# --- Revisión de un documento ---


@metodos("POST")
@requiere_rol("curatoria")
@manejar_errores
def revisar_documento(request, ref):
    """Validar u observar un documento (CA-17.2; ADR-017, punto 4). Responde el detalle del expediente."""
    documento = obtener_autorizado(
        Documento.objects.select_related("expediente"), ref, request.usuario, PoliticaDocumentoCuratoria()
    )
    datos = leer_json(request, CAMPOS_REVISION)
    try:
        documento = servicios.revisar_documento(request.usuario, documento, datos)
    except ErroresValidacion as error:
        raise ErroresDeCampo(error.errores) from None
    except ErrorEstado as error:
        return respuesta_error(409, error.mensaje)
    expediente = Expediente.objects.select_related("perfil_maestro").get(pk=documento.expediente_id)
    return _json({"expediente": datos_detalle(expediente)})


# --- Historial (bitácora de solo lectura; ADR-010, E-1) ---


def _estado_de(valor):
    return valor.get("estado") if isinstance(valor, dict) else None


def _autores(entradas):
    ids = {entrada.autor_id for entrada in entradas if entrada.autor_tipo == AutorTipo.USUARIO}
    return dict(Usuario.objects.filter(pk__in=ids).values_list("pk", "nombre"))


def _datos_entrada(entrada, autores, documentos):
    if entrada.autor_tipo == AutorTipo.SISTEMA:
        autor = AUTOR_SISTEMA
    else:
        autor = autores.get(entrada.autor_id, AUTOR_DESCONOCIDO)
    documento = documentos.get(entrada.entidad_ref) if entrada.entidad == "documento" else None
    return {
        "fecha": _fecha(entrada.fecha),
        "autor": autor,
        "accion": entrada.accion,
        "estado_anterior": _estado_de(entrada.valor_anterior),
        "estado_nuevo": _estado_de(entrada.valor_nuevo),
        "motivo": entrada.motivo,
        # Referencia para abrir el documento, también si fue reemplazado (ADR-017, E-3).
        "documento": None
        if documento is None
        else {
            "ref": str(documento.ref),
            "tipo": documento.tipo,
            "oficio": _oficio_resumido(documento.oficio),
            "estado": documento.estado,
            "tiene_reverso": documento.archivo_reverso is not None,
        },
    }


@metodos("GET")
@requiere_rol("curatoria")
def historial(request, ref):
    """Bitácora del expediente y de sus documentos, del más reciente al más antiguo (CA-19.3)."""
    expediente = _expediente_autorizado(request, ref)
    documentos = {
        str(documento.ref): documento
        for documento in Documento.objects.filter(expediente=expediente).select_related("oficio")
    }
    entradas = list(
        Bitacora.objects.filter(
            Q(entidad="expediente", entidad_ref=str(expediente.ref))
            | Q(entidad="documento", entidad_ref__in=list(documentos))
        ).order_by("-fecha", "-id")
    )
    autores = _autores(entradas)
    return _json({"historial": [_datos_entrada(entrada, autores, documentos) for entrada in entradas]})
