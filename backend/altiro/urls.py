from django.urls import path

from altiro.salud import salud
from catalogo import vistas as catalogo
from expediente import vistas as expediente
from expediente import vistas_documentos as documentos
from identidad import vistas as identidad
from territorio import vistas as territorio

# Toda ruta /api/ es privada salvo las marcadas con comun.api.publica.
urlpatterns = [
    path("api/health/", salud, name="salud"),
    path("api/territorio/regiones", territorio.regiones, name="regiones"),
    path(
        "api/territorio/regiones/<int:codigo>/comunas",
        territorio.comunas_de_region,
        name="comunas_de_region",
    ),
    path("api/sesion/csrf", identidad.csrf, name="csrf"),
    path("api/sesion", identidad.sesion, name="sesion"),
    path("api/cuenta", identidad.cuenta, name="cuenta"),
    path("api/clientes", identidad.clientes, name="clientes"),
    path("api/maestros/postulaciones", identidad.postulaciones, name="postulaciones"),
    # Catálogo mínimo de oficios, público (ADR-017, punto 1).
    path("api/oficios", catalogo.oficios, name="oficios"),
    # Expediente propio del maestro, patrón "me" (ADR-011; propuesta del S2, §4).
    path("api/maestros/expediente", expediente.mi_expediente, name="mi_expediente"),
    path("api/maestros/expediente/oficios", expediente.mis_oficios, name="mis_oficios"),
    # Carga de documentos, multipart (ADR-015; ADR-017, punto 5).
    path("api/maestros/expediente/documentos", expediente.mis_documentos, name="mis_documentos"),
    # Enlace de 600 s y descarga de un documento: dueño o curatoría (RNF-06, CA-25.2; ADR-015).
    path("api/documentos/<uuid:ref>/enlace", documentos.documento_enlace, name="documento_enlace"),
    path("api/documentos/<uuid:ref>/archivo", documentos.documento_archivo, name="documento_archivo"),
]

handler400 = "comun.api.solicitud_invalida"
handler404 = "comun.api.no_encontrado"
handler500 = "comun.api.error_interno"
