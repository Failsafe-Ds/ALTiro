"""Nada de prueba llega a la configuración real (ADR-014; propuesta del S1, §8)."""
from django.conf import settings

import altiro.settings as base
from altiro import urls
from tests.control_terceros import rutas


def test_los_ajustes_reales_no_incluyen_apps_ni_rutas_de_prueba():
    assert not [app for app in base.INSTALLED_APPS if app.startswith("tests")]
    assert base.ROOT_URLCONF == "altiro.urls"


def test_las_rutas_reales_no_incluyen_rutas_de_prueba():
    for ruta in rutas(urls.urlpatterns):
        assert "prueba" not in ruta.patron, ruta
        assert not getattr(ruta.vista, "__module__", "").startswith("tests"), ruta


def test_pytest_usa_los_ajustes_de_prueba():
    assert settings.ROOT_URLCONF == "tests.recurso_prueba.urls"
    assert "tests.recurso_prueba" in settings.INSTALLED_APPS
    assert "autorizacion" in settings.INSTALLED_APPS and "bitacora" in settings.INSTALLED_APPS
    assert "autorizacion.middleware.AutorizacionMiddleware" in settings.MIDDLEWARE
