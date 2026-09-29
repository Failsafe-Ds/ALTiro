from django.apps import AppConfig


class PerfilConfig(AppConfig):
    """Perfil público del maestro, sus servicios y la regla única de publicación (ADR-019; propuesta del S3)."""

    name = "perfil"
    default_auto_field = "django.db.models.BigAutoField"
