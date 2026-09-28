from django.apps import AppConfig


class ExpedienteConfig(AppConfig):
    """Expediente del maestro y curatoría (ADR-017; propuesta del S2)."""

    name = "expediente"
    default_auto_field = "django.db.models.BigAutoField"
