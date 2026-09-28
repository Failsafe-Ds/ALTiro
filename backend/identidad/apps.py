from django.apps import AppConfig


class IdentidadConfig(AppConfig):
    """Identidad: usuario, roles y perfiles (ADR-001, ADR-013)."""

    name = "identidad"
    default_auto_field = "django.db.models.BigAutoField"
