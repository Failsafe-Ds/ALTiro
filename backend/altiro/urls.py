from django.urls import path

from altiro.salud import salud
from catalogo import vistas as catalogo
from catalogo import vistas_comercial as comercial
from expediente import vistas as expediente
from expediente import vistas_curatoria as curatoria
from expediente import vistas_documentos as documentos
from identidad import vistas as identidad
from perfil import vistas as perfil
from perfil import vistas_maestro as perfil_maestro
from perfil import vistas_publicas as perfil_publico
from busqueda import vistas as busqueda
from territorio import vistas as territorio
from tickets import vistas as tickets

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
    # Catálogo público, de solo lectura (ADR-017, punto 1; ADR-018, puntos 5 y 6; CA-20.2).
    path("api/oficios", catalogo.oficios, name="oficios"),
    path("api/catalogo", catalogo.catalogo, name="catalogo"),
    # Administración del catálogo: rol comercial, versión, motivo y bitácora (RF-36, RF-37; ADR-018).
    path("api/comercial/catalogo", comercial.catalogo_comercial, name="comercial_catalogo"),
    path("api/comercial/oficios", comercial.crear_oficio, name="comercial_crear_oficio"),
    path("api/comercial/oficios/<uuid:ref>", comercial.modificar_oficio, name="comercial_modificar_oficio"),
    path("api/comercial/servicios", comercial.crear_servicio, name="comercial_crear_servicio"),
    path("api/comercial/servicios/<uuid:ref>", comercial.modificar_servicio, name="comercial_modificar_servicio"),
    # Servicios del maestro, patrón "me" y política de dueño (RF-05, HU-12; ADR-019).
    path("api/maestros/servicios", perfil.mis_servicios, name="mis_servicios"),
    path("api/maestros/servicios/<uuid:ref>", perfil.mi_servicio, name="mi_servicio"),
    # Cobertura, agenda, foto y perfil del maestro (RF-06, RF-07; ADR-019 a ADR-021).
    path("api/maestros/cobertura", perfil_maestro.mi_cobertura, name="mi_cobertura"),
    path("api/maestros/disponibilidad", perfil_maestro.mi_disponibilidad, name="mi_disponibilidad"),
    path("api/maestros/disponibilidad/<uuid:ref>", perfil_maestro.mi_bloque, name="mi_bloque"),
    path("api/maestros/perfil", perfil_maestro.mi_perfil, name="mi_perfil"),
    path("api/maestros/perfil/foto", perfil_maestro.mi_foto, name="mi_foto"),
    # Perfil público: solo si el maestro está publicado; si no, 404 neutro sin registro (ADR-019, punto 5).
    path("api/maestros/publicos/<uuid:ref>", perfil_publico.perfil_publico, name="perfil_publico"),
    path("api/maestros/publicos/<uuid:ref>/foto", perfil_publico.foto_publica, name="foto_publica"),
    # Búsqueda pública: filtros excluyentes, puntaje oculto y sugerencias aparte (RF-09 a RF-13; ADR-022).
    path("api/busqueda", busqueda.busqueda, name="busqueda"),
    # Ticket: crear (rol cliente), ver (solo sus partes; tercero -> 404 idéntico con registro) y listas propias
    # (RF-15 a RF-18, CA-25.1; ADR-023). Avisos de tickets dentro de la aplicación (ADR-024).
    path("api/tickets", tickets.crear, name="tickets"),
    path("api/tickets/<uuid:ref>", tickets.detalle, name="ticket"),
    path("api/tickets/<uuid:ref>/aceptacion", tickets.aceptacion, name="ticket_aceptacion"),
    path("api/tickets/<uuid:ref>/rechazo", tickets.rechazo, name="ticket_rechazo"),
    path("api/tickets/<uuid:ref>/cancelacion", tickets.cancelacion, name="ticket_cancelacion"),
    path("api/clientes/tickets", tickets.del_cliente, name="tickets_del_cliente"),
    path("api/maestros/tickets", tickets.del_maestro, name="tickets_del_maestro"),
    path("api/avisos", tickets.avisos, name="avisos"),
    path("api/avisos/vistos", tickets.avisos_vistos, name="avisos_vistos"),
    # Expediente propio del maestro, patrón "me" (ADR-011; propuesta del S2, §4).
    path("api/maestros/expediente", expediente.mi_expediente, name="mi_expediente"),
    path("api/maestros/expediente/oficios", expediente.mis_oficios, name="mis_oficios"),
    # Carga de documentos, multipart (ADR-015; ADR-017, punto 5).
    path("api/maestros/expediente/documentos", expediente.mis_documentos, name="mis_documentos"),
    # Enlace de 600 s y descarga de un documento: dueño o curatoría (RNF-06, CA-25.2; ADR-015).
    path("api/documentos/<uuid:ref>/enlace", documentos.documento_enlace, name="documento_enlace"),
    path("api/documentos/<uuid:ref>/archivo", documentos.documento_archivo, name="documento_archivo"),
    # Curatoría: rol curatoria y conflicto de interés (HU-19, CA-19.4; ADR-011, E-2; propuesta del S2, §4).
    path("api/curatoria/expedientes", curatoria.cola, name="curatoria_cola"),
    path("api/curatoria/expedientes/<uuid:ref>", curatoria.detalle, name="curatoria_detalle"),
    path(
        "api/curatoria/expedientes/<uuid:ref>/estado",
        curatoria.cambiar_estado,
        name="curatoria_cambiar_estado",
    ),
    # Historial de solo lectura (CA-19.3; ADR-010, E-1).
    path("api/curatoria/expedientes/<uuid:ref>/historial", curatoria.historial, name="curatoria_historial"),
    path(
        "api/curatoria/documentos/<uuid:ref>/revision",
        curatoria.revisar_documento,
        name="curatoria_revisar_documento",
    ),
    # Avisos de documentos por vencer para curatoría (RF-35; ADR-016, punto 2).
    path("api/curatoria/avisos", curatoria.avisos_curatoria, name="curatoria_avisos"),
    # Enlace de 600 s también para documentos reemplazados (ADR-017, E-3).
    path(
        "api/curatoria/documentos/<uuid:ref>/enlace",
        documentos.curatoria_documento_enlace,
        name="curatoria_documento_enlace",
    ),
]

handler400 = "comun.api.solicitud_invalida"
handler404 = "comun.api.no_encontrado"
handler500 = "comun.api.error_interno"
