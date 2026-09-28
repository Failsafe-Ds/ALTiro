from django.apps import AppConfig


class CatalogoConfig(AppConfig):
    """Catálogo mínimo de oficios, de solo lectura (ADR-017, punto 1)."""

    name = "catalogo"
    default_auto_field = "django.db.models.BigAutoField"
