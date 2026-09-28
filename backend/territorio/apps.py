from django.apps import AppConfig


class TerritorioConfig(AppConfig):
    """Catálogo territorial de solo lectura: región, provincia y comuna (ADR-012)."""

    name = "territorio"
    default_auto_field = "django.db.models.BigAutoField"
