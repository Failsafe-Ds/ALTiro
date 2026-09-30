"""Evaluaciones y denuncias (RF-29, RF-30, RF-31; ADR-026, E-3 y E-4; propuesta del S5, §3.1).

- ``evaluacion``: una por parte y por orden (único ``(ticket, parte)``); la
  ``parte`` es quien evalúa. Escala entera de 1 a 5 en tres dimensiones y
  comentario opcional de hasta 500 caracteres. La API no la modifica: solo
  moderación cambia ``estado`` a ``retirada`` (queda en la bitácora) y nunca
  se borra (FK PROTECT).
- ``denuncia``: la presenta la parte evaluada, una vez (único
  ``(evaluacion, denunciante)``). ``resuelta`` si y solo si tiene decisión,
  motivo, autor y fecha.
"""
import uuid

from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Length
from django.db.models.lookups import GreaterThanOrEqual, LessThanOrEqual
from django.utils import timezone

from identidad.models import Usuario
from tickets.models import Ticket

LARGO_COMENTARIO = 500
LARGO_MOTIVO = 500
NOTA_MINIMA = 1
NOTA_MAXIMA = 5
DIMENSIONES = ("puntualidad", "trabajo", "cordialidad")


class ParteEvaluacion(models.TextChoices):
    CLIENTE = "cliente", "Cliente"
    MAESTRO = "maestro", "Maestro"


class EstadoEvaluacion(models.TextChoices):
    PUBLICADA = "publicada", "Publicada"
    RETIRADA = "retirada", "Retirada por moderación"


class EstadoDenuncia(models.TextChoices):
    ABIERTA = "abierta", "En revisión"
    RESUELTA = "resuelta", "Resuelta"


class DecisionDenuncia(models.TextChoices):
    MANTENER = "mantener", "Se mantiene la evaluación"
    RETIRAR = "retirar", "Se retira la evaluación"


def _valores(opciones):
    return [valor for valor, _ in opciones.choices]


def _nota(campo):
    return Q(**{f"{campo}__gte": NOTA_MINIMA, f"{campo}__lte": NOTA_MAXIMA})


class Evaluacion(models.Model):
    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name="+", db_column="ticket_id",
                               db_index=False)
    parte = models.CharField(max_length=10, choices=ParteEvaluacion.choices)
    autor = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="+", db_column="autor_id",
                              db_index=False)
    evaluado = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="+", db_column="evaluado_id",
                                 db_index=False)
    puntualidad = models.PositiveSmallIntegerField()
    trabajo = models.PositiveSmallIntegerField()
    cordialidad = models.PositiveSmallIntegerField()
    comentario = models.CharField(max_length=LARGO_COMENTARIO, blank=True, default="")
    creada_en = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=10, choices=EstadoEvaluacion.choices, default=EstadoEvaluacion.PUBLICADA)

    class Meta:
        db_table = "evaluacion"
        indexes = [models.Index(fields=["evaluado", "parte", "estado"], name="evaluacion_evaluado_idx")]
        constraints = [
            # RF-29, CA-09.2, CA-18.1: una sola evaluación por parte y por orden.
            models.UniqueConstraint(fields=["ticket", "parte"], name="evaluacion_una_por_parte"),
            models.CheckConstraint(condition=Q(parte__in=_valores(ParteEvaluacion)), name="evaluacion_parte_valida"),
            models.CheckConstraint(condition=Q(estado__in=_valores(EstadoEvaluacion)),
                                   name="evaluacion_estado_valido"),
            models.CheckConstraint(condition=~Q(autor=F("evaluado")), name="evaluacion_autor_no_evaluado"),
            models.CheckConstraint(condition=_nota("puntualidad") & _nota("trabajo") & _nota("cordialidad"),
                                   name="evaluacion_notas_validas"),
            models.CheckConstraint(condition=LessThanOrEqual(Length("comentario"), LARGO_COMENTARIO),
                                   name="evaluacion_comentario_largo"),
        ]

    def __str__(self):
        # Sin el comentario: puede terminar en registros.
        return f"Evaluación {self.ref}"


class Denuncia(models.Model):
    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    evaluacion = models.ForeignKey(Evaluacion, on_delete=models.PROTECT, related_name="denuncias",
                                   db_column="evaluacion_id", db_index=False)
    denunciante = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="+",
                                    db_column="denunciante_id", db_index=False)
    motivo = models.CharField(max_length=LARGO_MOTIVO)
    creada_en = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=10, choices=EstadoDenuncia.choices, default=EstadoDenuncia.ABIERTA)
    decision = models.CharField(max_length=10, choices=DecisionDenuncia.choices, null=True, blank=True)
    motivo_resolucion = models.CharField(max_length=LARGO_MOTIVO, null=True, blank=True)
    resuelta_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="+", null=True, blank=True,
                                     db_column="resuelta_por_id", db_index=False)
    resuelta_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "denuncia"
        indexes = [
            models.Index(fields=["creada_en"], name="denuncia_abierta_idx", condition=Q(estado="abierta")),
        ]
        constraints = [
            # P-26: una denuncia por evaluación y denunciante.
            models.UniqueConstraint(fields=["evaluacion", "denunciante"], name="denuncia_una_por_denunciante"),
            models.CheckConstraint(condition=Q(estado__in=_valores(EstadoDenuncia)), name="denuncia_estado_valido"),
            models.CheckConstraint(condition=Q(decision__isnull=True) | Q(decision__in=_valores(DecisionDenuncia)),
                                   name="denuncia_decision_valida"),
            models.CheckConstraint(
                condition=Q(GreaterThanOrEqual(Length("motivo"), 1)) & Q(LessThanOrEqual(Length("motivo"), LARGO_MOTIVO)),
                name="denuncia_motivo_largo",
            ),
            # CA-21.2: resuelta si y solo si hay decisión, motivo, autor y fecha.
            models.CheckConstraint(
                condition=(
                    Q(estado="resuelta", decision__isnull=False, motivo_resolucion__isnull=False,
                      resuelta_por__isnull=False, resuelta_en__isnull=False)
                    & ~Q(motivo_resolucion="")
                )
                | Q(estado="abierta", decision__isnull=True, motivo_resolucion__isnull=True,
                    resuelta_por__isnull=True, resuelta_en__isnull=True),
                name="denuncia_resolucion_completa",
            ),
        ]

    def __str__(self):
        return f"Denuncia {self.ref}"


