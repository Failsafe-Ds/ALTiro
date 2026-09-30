"""Expediente del maestro y oficios declarados (ADR-017; propuesta del S2, §3).

- ``Expediente``: uno por ``perfil_maestro`` (invariante perfil_maestro <=>
  expediente, verificado por ``identidad.servicios.verificar_invariantes``).
  Se crea en la misma transacción que el perfil (``expediente.servicios.crear_para``).
  ``ref`` es el identificador público (ADR-011); la clave numérica es interna.
- ``OficioMaestro``: oficios que el maestro declara; editable solo en
  ``en_revision`` u ``observado`` (``expediente.servicios.declarar_oficios``).

Sin borrado en cascada (PROTECT): la trazabilidad del expediente no se pierde
al borrar un perfil o un usuario.
"""
import uuid

from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Now
from django.utils import timezone

from catalogo.models import Oficio
from identidad.models import PerfilMaestro, Usuario


class EstadoExpediente(models.TextChoices):
    """ADR-017, punto 2. ``rechazado`` es terminal."""

    EN_REVISION = "en_revision", "En revisión"
    OBSERVADO = "observado", "Observado"
    APROBADO = "aprobado", "Aprobado"
    RECHAZADO = "rechazado", "Rechazado"
    SUSPENDIDO = "suspendido", "Suspendido"


# Estados en que el maestro puede cambiar su declaración de oficios (propuesta del S2, §3).
ESTADOS_EDITABLES = frozenset({EstadoExpediente.EN_REVISION, EstadoExpediente.OBSERVADO})


class Expediente(models.Model):
    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    perfil_maestro = models.OneToOneField(
        PerfilMaestro,
        on_delete=models.PROTECT,
        related_name="expediente",
        db_column="perfil_maestro_id",
    )
    estado = models.CharField(
        max_length=20, choices=EstadoExpediente.choices, default=EstadoExpediente.EN_REVISION
    )
    # Motivo del último cambio de estado (CA-19.1). Vacío mientras nadie lo cambió.
    estado_motivo = models.TextField(default="", blank=True)
    estado_cambiado_en = models.DateTimeField(null=True, blank=True)
    # Quién cambió el estado (curatoría). Nunca se entrega al maestro (ADR-010, E-1).
    estado_cambiado_por = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="estado_cambiado_por_id",
    )
    creado_en = models.DateTimeField(default=timezone.now, db_default=Now())

    class Meta:
        db_table = "expediente"
        constraints = [
            models.CheckConstraint(
                condition=Q(estado__in=[valor for valor, _ in EstadoExpediente.choices]),
                name="expediente_estado_valido",
            ),
            # Todo cambio de estado con autor exige un motivo escrito (RF-32, CA-19.1).
            models.CheckConstraint(
                condition=Q(estado_cambiado_por__isnull=True) | Q(estado_motivo__regex=r"\S"),
                name="expediente_motivo_con_autor",
            ),
        ]

    def __str__(self):
        # Sin datos personales: este texto puede terminar en registros.
        return f"Expediente {self.ref}"


class OficioMaestro(models.Model):
    """Oficio declarado por un maestro. Un oficio no se repite para un maestro."""

    # Sin índice propio: lo cubre oficio_maestro_unico (perfil_maestro_id, oficio_id).
    maestro = models.ForeignKey(
        PerfilMaestro,
        on_delete=models.PROTECT,
        related_name="oficios",
        db_column="perfil_maestro_id",
        db_index=False,
    )
    oficio = models.ForeignKey(Oficio, on_delete=models.PROTECT, related_name="+", db_column="oficio_id")

    class Meta:
        db_table = "oficio_maestro"
        constraints = [
            models.UniqueConstraint(fields=["maestro", "oficio"], name="oficio_maestro_unico"),
        ]

    def __str__(self):
        return f"Oficio {self.oficio_id} del maestro {self.maestro_id}"


class TipoDocumento(models.TextChoices):
    """Documentos exigidos (ADR-017, punto 3; supuesto a validar, P-03)."""

    CEDULA_IDENTIDAD = "cedula_identidad", "Cédula de identidad"
    CERTIFICADO_ANTECEDENTES = "certificado_antecedentes", "Certificado de antecedentes"
    LICENCIA_SEC = "licencia_sec", "Licencia SEC"


class EstadoDocumento(models.TextChoices):
    """ADR-017, punto 2. La vigencia se calcula (``expediente.vigencia``), no es un estado."""

    EN_REVISION = "en_revision", "En revisión"
    OBSERVADO = "observado", "Observado"
    VALIDADO = "validado", "Validado"
    REEMPLAZADO = "reemplazado", "Reemplazado"


class Documento(models.Model):
    """Documento del expediente (RF-04; ADR-015; ADR-017, puntos 2, 4 y 5).

    - ``archivo`` y ``archivo_reverso`` son el nombre UUID4 del archivo cifrado
      en el volumen de documentos (``expediente.almacenamiento``); nunca el
      nombre original ni una ruta, y nunca se entregan al cliente.
    - Un solo documento actual (estado distinto de ``reemplazado``) por
      (expediente, tipo, oficio), con ``oficio`` nulo tratado como un valor
      (D-11). Un documento ``reemplazado`` conserva su archivo hasta RNF-26/V-04.
    """

    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    expediente = models.ForeignKey(
        Expediente, on_delete=models.PROTECT, related_name="documentos", db_column="expediente_id"
    )
    tipo = models.CharField(max_length=30, choices=TipoDocumento.choices)
    # Solo en la licencia SEC: el oficio regulado que habilita.
    oficio = models.ForeignKey(
        Oficio, on_delete=models.PROTECT, null=True, blank=True, related_name="+", db_column="oficio_id"
    )
    fecha_emision = models.DateField()
    # Opcional (RF-04, CA-11.2): sin vencimiento, el documento siempre está vigente.
    fecha_vencimiento = models.DateField(null=True, blank=True)
    estado = models.CharField(
        max_length=20, choices=EstadoDocumento.choices, default=EstadoDocumento.EN_REVISION
    )
    # Motivo de curatoría al observar (CA-17.2).
    motivo_observacion = models.TextField(default="", blank=True)
    archivo = models.UUIDField(unique=True)
    # Solo en la cédula: la parte de atrás (ADR-017, punto 3: "por ambos lados").
    archivo_reverso = models.UUIDField(unique=True, null=True, blank=True)
    cargado_en = models.DateTimeField(default=timezone.now, db_default=Now())
    revisado_en = models.DateTimeField(null=True, blank=True)
    # Quién revisó: solo lo ve curatoría (ADR-010, E-1).
    revisado_por = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, null=True, blank=True, related_name="+", db_column="revisado_por_id"
    )
    # Documento revisado al que este sustituye (D-11).
    reemplaza_a = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="+", db_column="reemplaza_a_id"
    )
    # Retención (RNF-26; ADR-026, E-9): cuándo y por qué el actor Sistema borró
    # los archivos cifrados. La fila se conserva para la trazabilidad (RF-37).
    eliminado_en = models.DateTimeField(null=True, blank=True)
    motivo_eliminacion = models.TextField(default="", blank=True)

    class Meta:
        db_table = "documento"
        constraints = [
            models.CheckConstraint(
                condition=Q(tipo__in=[valor for valor, _ in TipoDocumento.choices]),
                name="documento_tipo_valido",
            ),
            models.CheckConstraint(
                condition=Q(estado__in=[valor for valor, _ in EstadoDocumento.choices]),
                name="documento_estado_valido",
            ),
            # El oficio va solo, y siempre, en la licencia SEC (RF-33).
            models.CheckConstraint(
                condition=(Q(tipo=TipoDocumento.LICENCIA_SEC) & Q(oficio__isnull=False))
                | (~Q(tipo=TipoDocumento.LICENCIA_SEC) & Q(oficio__isnull=True)),
                name="documento_oficio_solo_licencia",
            ),
            models.CheckConstraint(
                condition=Q(fecha_vencimiento__isnull=True) | Q(fecha_vencimiento__gt=F("fecha_emision")),
                name="documento_vencimiento_posterior",
            ),
            # Observar exige un motivo (CA-17.2).
            models.CheckConstraint(
                condition=~Q(estado=EstadoDocumento.OBSERVADO) | Q(motivo_observacion__regex=r"\S"),
                name="documento_motivo_observacion",
            ),
            # Validar no deja motivo de observación: así un documento reemplazado
            # sin ese motivo estaba validado (ADR-017, E-1; expediente.vigencia.fue_validado).
            models.CheckConstraint(
                condition=~Q(estado=EstadoDocumento.VALIDADO) | Q(motivo_observacion=""),
                name="documento_validado_sin_observacion",
            ),
            # La cédula lleva las dos caras; los demás documentos, una.
            models.CheckConstraint(
                condition=(Q(tipo=TipoDocumento.CEDULA_IDENTIDAD) & Q(archivo_reverso__isnull=False))
                | (~Q(tipo=TipoDocumento.CEDULA_IDENTIDAD) & Q(archivo_reverso__isnull=True)),
                name="documento_reverso_solo_cedula",
            ),
            # Eliminado por retención: fecha y motivo van juntos (RNF-26; ADR-026, E-9).
            models.CheckConstraint(
                condition=(Q(eliminado_en__isnull=True) & Q(motivo_eliminacion=""))
                | (Q(eliminado_en__isnull=False) & Q(motivo_eliminacion__regex=r"\S")),
                name="documento_eliminacion_con_motivo",
            ),
            # Un documento actual por (expediente, tipo, oficio) (D-11).
            models.UniqueConstraint(
                fields=["expediente", "tipo", "oficio"],
                condition=~Q(estado=EstadoDocumento.REEMPLAZADO),
                nulls_distinct=False,
                name="documento_actual_unico",
            ),
        ]

    def __str__(self):
        # Sin datos personales ni nombres de archivo: este texto puede terminar en registros.
        return f"Documento {self.ref}"


class TipoAviso(models.TextChoices):
    """RF-35: único tipo en S2."""

    DOCUMENTO_POR_VENCER = "documento_por_vencer", "Documento por vencer"


class RolDestinatarioAviso(models.TextChoices):
    """Rol destinatario de un aviso (RF-35: "al administrador"). Solo curatoría en S2."""

    CURATORIA = "curatoria", "Curatoría"


class Aviso(models.Model):
    """Aviso dentro de la aplicación (RF-35, CA-24.2; ADR-016, punto 2).

    - Destinatario: una cuenta (el maestro dueño del documento) **o** un rol
      (``curatoria``), exactamente uno de los dos.
    - UNIQUE (tipo, documento, destinatario, destinatario_rol), con los nulos
      tratados como un valor: cada aviso se emite una sola vez ("el aviso se
      emite una vez alcanzado el umbral"), aunque la tarea corra dos veces o en
      paralelo.
    - Sin datos personales: el texto se arma al mostrarlo
      (``expediente.avisos.mensaje``). Lo escribe solo el actor Sistema
      (``expediente.tareas.emitir_avisos_por_vencer``).
    - PROTECT: un aviso no se pierde por borrar el documento o la cuenta.
    """

    tipo = models.CharField(max_length=30, choices=TipoAviso.choices)
    documento = models.ForeignKey(Documento, on_delete=models.PROTECT, related_name="+", db_column="documento_id")
    destinatario = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, null=True, blank=True, related_name="+", db_column="destinatario_id"
    )
    destinatario_rol = models.CharField(max_length=20, choices=RolDestinatarioAviso.choices, null=True, blank=True)
    creado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "aviso"
        constraints = [
            models.CheckConstraint(
                condition=Q(tipo__in=[valor for valor, _ in TipoAviso.choices]),
                name="aviso_tipo_valido",
            ),
            models.CheckConstraint(
                condition=Q(destinatario_rol__isnull=True)
                | Q(destinatario_rol__in=[valor for valor, _ in RolDestinatarioAviso.choices]),
                name="aviso_destinatario_rol_valido",
            ),
            # Exactamente un destinatario: una cuenta o un rol.
            models.CheckConstraint(
                condition=(Q(destinatario__isnull=False) & Q(destinatario_rol__isnull=True))
                | (Q(destinatario__isnull=True) & Q(destinatario_rol__isnull=False)),
                name="aviso_un_destinatario",
            ),
            # Una sola emisión por (tipo, documento, destinatario) (RF-35).
            models.UniqueConstraint(
                fields=["tipo", "documento", "destinatario", "destinatario_rol"],
                nulls_distinct=False,
                name="aviso_una_vez",
            ),
        ]

    def __str__(self):
        # Sin datos personales: este texto puede terminar en registros.
        return f"Aviso {self.pk} ({self.tipo})"
