"""Perfil público del maestro, sin sesión (RF-14 y RF-13 parciales; ADR-019, puntos 5 y 6; ADR-021; RNF-25).

- ``GET /api/maestros/publicos/<uuid:ref>``: solo si el maestro está publicado
  (``perfil.publicacion``: aprobado, comuna base, foto y al menos un servicio
  visible, calculado en esta lectura). Si no, el mismo 404 que una ref
  inexistente, **sin registro** de acceso denegado: una ruta pública no
  deniega a nadie, solo no encuentra (ADR-019, punto 5).
- ``GET /api/maestros/publicos/<uuid:ref>/foto?tam=160|480``: misma condición.

Lista explícita de campos (D-14): nombre registrado, foto, servicios visibles
(oficio, servicio, modalidad y monto), comunas atendidas **sin indicar cuál es
la base** (por nombre, así el orden tampoco la revela) y agenda semanal en
"HH:MM". Nunca RUT, teléfono, correo, documentos, estado o motivos del
expediente, fechas de licencia, ids internos ni la ref del expediente.

Caché:
- Perfil: ``no-store``. Una licencia que vence o una suspensión deben quitar
  el servicio o el perfil en la siguiente lectura (RNF-25, CA-24.1).
- Foto: ``no-cache`` + ``ETag`` (decisión de este incremento). El navegador
  puede guardar la foto (su finalidad es ser pública), pero debe revalidarla
  en cada uso: el servidor vuelve a exigir que el maestro esté publicado antes
  de responder 304, así que un maestro que deja de estar publicado deja de
  entregar su foto en la siguiente consulta, y en red móvil una foto sin
  cambios cuesta solo la revalidación (RNF-02).
"""
import hashlib

from django.http import HttpResponse, JsonResponse

from catalogo.models import Modalidad
from comun.api import metodos, publica, respuesta_no_encontrado
from expediente import vigencia
from perfil import agenda, cobertura, fotos, publicacion
from perfil.models import PerfilPublico

CABECERAS_FOTO = {
    "Content-Disposition": 'inline; filename="foto.jpg"',
    "Cache-Control": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "sandbox; default-src 'none'",
    "Cross-Origin-Resource-Policy": "same-origin",
}
TAMANO_POR_DEFECTO = 480


def _publicado(ref):
    """``PerfilPublico`` de ``ref`` si el maestro está publicado; si no, ``None`` (sin registro)."""
    perfil = PerfilPublico.objects.select_related("perfil_maestro__usuario").filter(ref=ref).first()
    if perfil is None or perfil.foto is None:
        return None
    if not publicacion.maestro_publicado(perfil.perfil_maestro_id):
        return None
    return perfil


def url_foto(perfil, tamano):
    return f"/api/maestros/publicos/{perfil.ref}/foto?tam={tamano}"


def datos_publicos(perfil, hoy):
    maestro_id = perfil.perfil_maestro_id
    servicios = publicacion.servicios_visibles(maestro_id, hoy)
    return {
        "ref": str(perfil.ref),
        "nombre": perfil.perfil_maestro.usuario.nombre,
        "foto": {str(tamano): url_foto(perfil, tamano) for tamano in fotos.TAMANOS},
        "servicios": [
            {
                "oficio": {"codigo": s.servicio.oficio.codigo, "nombre": s.servicio.oficio.nombre},
                "servicio": s.servicio.nombre,
                "modalidad": s.modalidad,
                "modalidad_texto": Modalidad(s.modalidad).label,
                "monto": s.monto,
            }
            for s in servicios
        ],
        # Sin "es_base" (D-14).
        "comunas": [
            {"codigo": str(c.comuna.codigo), "nombre": c.comuna.nombre} for c in cobertura.cobertura_de(maestro_id)
        ],
        "agenda": [
            {
                "dia_semana": b.dia_semana,
                "dia": agenda.DIAS[b.dia_semana],
                "inicio": agenda.formato_hora(b.inicio_min),
                "fin": agenda.formato_hora(b.fin_min),
            }
            for b in agenda.bloques_activos(maestro_id)
        ],
    }


@publica
@metodos("GET")
def perfil_publico(request, ref):
    perfil = _publicado(ref)
    if perfil is None:
        return respuesta_no_encontrado()
    respuesta = JsonResponse({"maestro": datos_publicos(perfil, vigencia.hoy_negocio())})
    respuesta["Cache-Control"] = "no-store"
    return respuesta


@publica
@metodos("GET")
def foto_publica(request, ref):
    tam = request.GET.get("tam", str(TAMANO_POR_DEFECTO))
    tamano = int(tam) if tam in {str(t) for t in fotos.TAMANOS} else None
    if tamano is None or set(request.GET) - {"tam"} or len(request.GET.getlist("tam")) > 1:
        return respuesta_no_encontrado()
    perfil = _publicado(ref)
    if perfil is None:
        return respuesta_no_encontrado()
    # Resumen del nombre: el ETag no expone el nombre interno del archivo.
    etag = '"' + hashlib.sha256(f"{perfil.foto}-{tamano}".encode("ascii")).hexdigest()[:32] + '"'
    if etag in [valor.strip() for valor in request.headers.get("If-None-Match", "").split(",")]:
        respuesta = HttpResponse(status=304)
    else:
        try:
            contenido = fotos.leer(perfil.foto, tamano)
        except fotos.FotoIlegible:
            return respuesta_no_encontrado()
        respuesta = HttpResponse(contenido, content_type="image/jpeg")
    respuesta["ETag"] = etag
    for cabecera, valor in CABECERAS_FOTO.items():
        respuesta[cabecera] = valor
    return respuesta
