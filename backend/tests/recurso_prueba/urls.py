"""URLconf de pruebas: todas las rutas de ``altiro.urls`` más las del recurso ficticio."""
from django.urls import include, path

from altiro.urls import handler400, handler404, handler500  # noqa: F401
from tests.recurso_prueba import vistas

urlpatterns = [
    path("", include("altiro.urls")),
    path("api/prueba/recursos/<uuid:ref>", vistas.recurso, name="prueba_recurso"),
    path("api/prueba/solo-curatoria", vistas.solo_curatoria, name="prueba_solo_curatoria"),
    path("api/prueba/solo-curatoria/accion", vistas.accion_solo_curatoria, name="prueba_accion_solo_curatoria"),
]
