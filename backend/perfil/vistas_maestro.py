"""Rutas del maestro sobre su cobertura, agenda, foto y perfil (RF-06, RF-07, HU-13, HU-14; ADR-019 a ADR-021).

Patrón "me" (ADR-011): sin identificador, siempre la cuenta de la sesión,
salvo ``DELETE /api/maestros/disponibilidad/<uuid:ref>``, que usa
``obtener_autorizado`` con ``PoliticaDisponibilidad`` (otro maestro recibe el
404 idéntico y queda registrado). Exigen el rol ``maestro`` (403 registrado si
falta; 401 sin sesión). Lista explícita de campos; ``Cache-Control: no-store``.

- ``GET`` y ``PUT /api/maestros/cobertura``: ``{"comunas": [{"comuna": "8101", "es_base": true}, ...]}``.
- ``GET`` y ``POST /api/maestros/disponibilidad``: ``{"dia_semana": 1, "inicio": "08:00", "fin": "12:00"}``.
- ``POST /api/maestros/perfil/foto``: multipart con el archivo en ``archivo``.
- ``GET /api/maestros/perfil``: ref pública, si está publicado, lo que le falta y su «Sobre mí».
- ``PUT /api/maestros/perfil``: ``{"descripcion": "..."}`` (DA-30), hasta 500 caracteres;
  vacío o ``null`` la borra; sin la clave, 400 en ``descripcion``. Responde el perfil como el ``GET``.
"""
from django.conf import settings
from django.http import HttpResponse

from autorizacion.acceso import obtener_autorizado
from autorizacion.decoradores import requiere_rol
from comun.api import ErroresDeCampo, leer_json, leer_multipart, manejar_errores, metodos, respuesta_error, respuesta_json
from expediente.errores import ErrorEstado, ErroresValidacion
from expediente.models import EstadoExpediente, Expediente
from perfil import agenda, cobertura, fotos, publicacion
from perfil import servicios as servicios_perfil
from perfil.models import Disponibilidad, PerfilPublico
from perfil.politicas import PoliticaDisponibilidad

CAMPOS_COBERTURA = {"comunas"}
CAMPOS_BLOQUE = {"dia_semana", "inicio", "fin"}
ARCHIVOS_FOTO = {"archivo"}
CAMPOS_PERFIL = {"descripcion"}
# Una foto de hasta ALTIRO_DOCUMENTO_MAXIMO_BYTES más el resto del formulario;
# igual que client_max_body_size de la ruta en el proxy (9m).
MAXIMO_CUERPO_FOTO = settings.ALTIRO_DOCUMENTO_MAXIMO_BYTES + 1024 * 1024

MENSAJE_FOTO_GRANDE = "La foto es muy pesada. Tómala de nuevo o elige otra."

# Lo que ve el maestro (RNF-17): "comuna principal" por "comuna base".
MENSAJES_PENDIENTE = {
    publicacion.POSTULACION_NO_APROBADA: "Tu postulación todavía no está aprobada.",
    publicacion.SIN_COMUNA_BASE: "Falta que elijas tu comuna principal.",
    publicacion.SIN_FOTO: "Falta que subas tu foto.",
    publicacion.SIN_SERVICIO_VISIBLE: "Falta que ofrezcas al menos un servicio que los clientes puedan ver.",
}
MENSAJES_POSTULACION = {
    EstadoExpediente.SUSPENDIDO: "Tu cuenta de maestro está suspendida.",
    EstadoExpediente.RECHAZADO: "Tu postulación no fue aprobada.",
}


def _con_errores_de_dominio(funcion):
    try:
        return funcion()
    except ErroresValidacion as error:
        raise ErroresDeCampo(error.errores) from None
    except ErrorEstado as error:
        return respuesta_error(409, error.mensaje)


# --- Cobertura ---


def datos_comuna(comuna):
    """Comuna del catálogo territorial (datos públicos, ADR-012)."""
    return {"codigo": str(comuna.codigo), "nombre": comuna.nombre}


def _cobertura(maestro_id, estado=200):
    return respuesta_json(
        {
            "comunas": [
                {**datos_comuna(c.comuna), "es_base": c.es_base} for c in cobertura.cobertura_de(maestro_id)
            ]
        },
        estado,
    )


@metodos("GET", "PUT")
@requiere_rol("maestro")
@manejar_errores
def mi_cobertura(request):
    if request.method == "PUT":
        datos = leer_json(request, CAMPOS_COBERTURA)

        def reemplazar():
            cobertura.reemplazar_cobertura(request.usuario, datos.get("comunas"))
            return _cobertura(request.usuario.pk)

        return _con_errores_de_dominio(reemplazar)
    return _cobertura(request.usuario.pk)


# --- Agenda ---


def datos_bloque(bloque):
    """Bloque en formato de 24 horas (CA-14.1); los minutos se incluyen para la pantalla."""
    return {
        "ref": str(bloque.ref),
        "dia_semana": bloque.dia_semana,
        "dia": agenda.DIAS[bloque.dia_semana],
        "inicio": agenda.formato_hora(bloque.inicio_min),
        "fin": agenda.formato_hora(bloque.fin_min),
        "inicio_min": bloque.inicio_min,
        "fin_min": bloque.fin_min,
    }


@metodos("GET", "POST")
@requiere_rol("maestro")
@manejar_errores
def mi_disponibilidad(request):
    if request.method == "POST":
        datos = leer_json(request, CAMPOS_BLOQUE)
        return _con_errores_de_dominio(
            lambda: respuesta_json({"bloque": datos_bloque(agenda.agregar_bloque(request.usuario, datos))}, 201)
        )
    return respuesta_json({"bloques": [datos_bloque(b) for b in agenda.bloques_activos(request.usuario.pk)]})


@metodos("DELETE")
@requiere_rol("maestro")
@manejar_errores
def mi_bloque(request, ref):
    bloque = obtener_autorizado(Disponibilidad.objects.all(), ref, request.usuario, PoliticaDisponibilidad())

    def retirar():
        agenda.retirar_bloque(bloque)
        return HttpResponse(status=204)

    return _con_errores_de_dominio(retirar)


# --- Foto y perfil ---


def _pendientes(maestro_id):
    estado = Expediente.objects.filter(perfil_maestro_id=maestro_id).values_list("estado", flat=True).first()
    resultado = []
    for codigo in publicacion.pendientes_para_publicarse(maestro_id):
        mensaje = MENSAJES_PENDIENTE[codigo]
        if codigo == publicacion.POSTULACION_NO_APROBADA:
            mensaje = MENSAJES_POSTULACION.get(estado, mensaje)
        resultado.append({"codigo": codigo, "mensaje": mensaje})
    return resultado


def _perfil(maestro_id, estado=200):
    perfil = PerfilPublico.objects.get(perfil_maestro_id=maestro_id)
    pendientes = _pendientes(maestro_id)
    return respuesta_json(
        {
            "perfil": {
                "ref": str(perfil.ref),
                "publicado": not pendientes,
                "tiene_foto": perfil.foto is not None,
                "pendientes": pendientes,
                "descripcion": perfil.descripcion,
            }
        },
        estado,
    )


@metodos("GET", "PUT")
@requiere_rol("maestro")
@manejar_errores
def mi_perfil(request):
    if request.method == "PUT":
        datos = leer_json(request, CAMPOS_PERFIL)

        def guardar():
            # Clave ausente: 400 en el campo, nunca borrado implícito (ADR-013).
            if "descripcion" not in datos:
                raise ErroresValidacion({"descripcion": servicios_perfil.MENSAJE_DESCRIPCION_FALTA})
            servicios_perfil.cambiar_descripcion(request.usuario.pk, datos["descripcion"])
            return _perfil(request.usuario.pk)

        return _con_errores_de_dominio(guardar)
    return _perfil(request.usuario.pk)


def _largo_declarado(request):
    try:
        return int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return 0


@metodos("POST")
@requiere_rol("maestro")
@manejar_errores
def mi_foto(request):
    """Sube o cambia la foto (ADR-021). 201 con el perfil."""
    if _largo_declarado(request) > MAXIMO_CUERPO_FOTO:
        return respuesta_error(413, MENSAJE_FOTO_GRANDE)
    _, archivos = leer_multipart(request, set(), ARCHIVOS_FOTO)

    def subir():
        fotos.subir_foto(request.usuario, archivos.get("archivo"))
        return _perfil(request.usuario.pk, 201)

    return _con_errores_de_dominio(subir)
