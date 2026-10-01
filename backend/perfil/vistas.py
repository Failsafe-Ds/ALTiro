"""Rutas del maestro sobre sus servicios (RF-05, HU-12, CA-12.1, CA-12.2, RF-34; ADR-019).

- ``GET`` y ``POST /api/maestros/servicios``: patrón "me" (ADR-011), sin
  identificador; siempre los servicios de la cuenta de la sesión.
- ``PATCH`` y ``DELETE /api/maestros/servicios/<uuid:ref>``: ``obtener_autorizado``
  con ``PoliticaServicioMaestro`` (solo el dueño; otro maestro recibe el 404
  idéntico y queda registrado).

Exigen el rol ``maestro`` (403 registrado si falta; 401 sin sesión). Cada
servicio dice si los clientes lo ven y, si no, por qué, en el lenguaje del
oficio (RNF-17), con la regla única de ``perfil.publicacion``. Lista explícita
de campos: nunca RUT, contacto ni ids internos. ``Cache-Control: no-store``.
"""
from django.http import HttpResponse

from autorizacion.acceso import obtener_autorizado
from autorizacion.decoradores import requiere_rol
from catalogo.models import Modalidad
from comun.api import ErroresDeCampo, leer_json, manejar_errores, metodos, respuesta_error, respuesta_json
from expediente import vigencia
from expediente.errores import ErrorEstado, ErroresValidacion
from expediente.models import EstadoExpediente, Expediente
from perfil import publicacion, servicios
from perfil.models import ServicioMaestro
from perfil.politicas import PoliticaServicioMaestro

CAMPOS_OFRECER = {"servicio", "modalidad", "monto"}
CAMPOS_CAMBIAR = {"modalidad", "monto"}

# Lo que ve el maestro (RNF-17): sin "perfil", "expediente" ni jerga.
MENSAJES_MOTIVO = {
    publicacion.RETIRADO: "Quitaste este servicio.",
    publicacion.CATALOGO_INACTIVO: "AlTiro dejó de ofrecer este servicio, así que los clientes no lo ven.",
    publicacion.OFICIO_NO_DECLARADO: (
        "Este servicio es de un oficio que no está entre tus oficios, así que los clientes no lo ven."
    ),
    publicacion.MODALIDAD_NO_ADMITIDA: (
        "Este servicio ya no se cobra de esa forma. Cambia la forma de cobro para que los clientes lo vean."
    ),
    publicacion.LICENCIA_NO_VIGENTE: (
        "Los clientes no lo ven: falta tu licencia de {oficio} vigente y revisada por AlTiro. "
        "Sube tu licencia vigente."
    ),
    publicacion.MAESTRO_NO_ELEGIBLE: "Los clientes todavía no ven tus servicios. Revisa lo que te falta.",
}
MENSAJES_PENDIENTE = {
    publicacion.POSTULACION_NO_APROBADA: "Tu postulación todavía no está aprobada.",
    publicacion.SIN_COMUNA_BASE: "Falta que elijas tu comuna principal.",
    publicacion.SIN_FOTO: "Falta que subas tu foto.",
}
MENSAJES_POSTULACION = {
    EstadoExpediente.SUSPENDIDO: "Tu cuenta de maestro está suspendida.",
    EstadoExpediente.RECHAZADO: "Tu postulación no fue aprobada.",
}


def _motivo(codigo, servicio_maestro):
    mensaje = MENSAJES_MOTIVO[codigo].format(oficio=servicio_maestro.servicio.oficio.nombre)
    return {"codigo": codigo, "mensaje": mensaje}


def datos_servicio_maestro(servicio_maestro, hoy, elegible):
    motivos = publicacion.motivos_no_visible(servicio_maestro, hoy, elegible=elegible)
    servicio = servicio_maestro.servicio
    return {
        "ref": str(servicio_maestro.ref),
        "servicio": {"ref": str(servicio.ref), "nombre": servicio.nombre},
        "oficio": {"codigo": servicio.oficio.codigo, "nombre": servicio.oficio.nombre},
        "modalidad": servicio_maestro.modalidad,
        "modalidad_texto": Modalidad(servicio_maestro.modalidad).label,
        "monto": servicio_maestro.monto,
        "visible": not motivos,
        "motivos": [_motivo(codigo, servicio_maestro) for codigo in motivos],
    }


def _pendientes(maestro_id):
    estado = Expediente.objects.filter(perfil_maestro_id=maestro_id).values_list("estado", flat=True).first()
    resultado = []
    for codigo in publicacion.pendientes_del_maestro(maestro_id):
        mensaje = MENSAJES_PENDIENTE[codigo]
        if codigo == publicacion.POSTULACION_NO_APROBADA:
            mensaje = MENSAJES_POSTULACION.get(estado, mensaje)
        resultado.append({"codigo": codigo, "mensaje": mensaje})
    return resultado


def _uno(servicio_maestro, estado=200):
    servicio_maestro = ServicioMaestro.objects.select_related("servicio__oficio").get(pk=servicio_maestro.pk)
    elegible = publicacion.maestro_elegible(servicio_maestro.maestro_id)
    return respuesta_json({"servicio": datos_servicio_maestro(servicio_maestro, vigencia.hoy_negocio(), elegible)}, estado)


def _con_errores_de_dominio(funcion):
    try:
        return funcion()
    except ErroresValidacion as error:
        raise ErroresDeCampo(error.errores) from None
    except ErrorEstado as error:
        return respuesta_error(409, error.mensaje)


@metodos("GET", "POST")
@requiere_rol("maestro")
@manejar_errores
def mis_servicios(request):
    maestro_id = request.usuario.pk
    if request.method == "POST":
        datos = leer_json(request, CAMPOS_OFRECER)
        return _con_errores_de_dominio(lambda: _uno(servicios.ofrecer_servicio(request.usuario, datos), 201))
    hoy = vigencia.hoy_negocio()
    elegible = publicacion.maestro_elegible(maestro_id)
    return respuesta_json(
        {
            "servicios": [
                datos_servicio_maestro(s, hoy, elegible) for s in publicacion.servicios_activos(maestro_id)
            ],
            "pendientes": _pendientes(maestro_id),
        }
    )


@metodos("PATCH", "DELETE")
@requiere_rol("maestro")
@manejar_errores
def mi_servicio(request, ref):
    """Primero la referencia y la política; después el cuerpo."""
    servicio_maestro = obtener_autorizado(
        ServicioMaestro.objects.all(), ref, request.usuario, PoliticaServicioMaestro()
    )
    if request.method == "DELETE":
        def retirar():
            servicios.retirar_servicio(servicio_maestro)
            return HttpResponse(status=204)

        return _con_errores_de_dominio(retirar)
    datos = leer_json(request, CAMPOS_CAMBIAR)
    return _con_errores_de_dominio(lambda: _uno(servicios.cambiar_servicio(servicio_maestro, datos)))
