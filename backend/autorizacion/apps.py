from django.apps import AppConfig


class AutorizacionConfig(AppConfig):
    """Autorización centralizada y registro de accesos denegados (RNF-07, CA-25.3; ADR-010, ADR-011)."""

    name = "autorizacion"
    default_auto_field = "django.db.models.BigAutoField"
