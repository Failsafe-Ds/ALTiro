from django.urls import path

from altiro.salud import salud
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
]

handler404 = "comun.api.no_encontrado"
handler500 = "comun.api.error_interno"
