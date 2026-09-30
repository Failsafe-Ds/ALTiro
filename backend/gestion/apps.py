from django.apps import AppConfig


class GestionConfig(AppConfig):
    """Indicadores base y exportación agregada, sin modelos (HU-22, RF-38; ADR-026, E-6)."""

    name = "gestion"
    default_auto_field = "django.db.models.BigAutoField"
