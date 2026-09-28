from django.apps import AppConfig


class RecursoPruebaConfig(AppConfig):
    """Recurso ficticio con dueño, solo para pruebas de autorización (RNF-07). Sin funcionalidad de negocio."""

    name = "tests.recurso_prueba"
    label = "recurso_prueba"
    default_auto_field = "django.db.models.BigAutoField"
