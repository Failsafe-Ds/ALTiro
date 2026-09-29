"""Agenda del maestro: bloques semanales en formato de 24 horas (RF-07, HU-14, CA-14.1, CA-14.2, CA-14.4; ADR-020).

- ``agregar_bloque(usuario, datos)``: un bloque por petición (CA-14.4: lo ya
  guardado se conserva aunque se corte la conexión). ``datos``:
  ``dia_semana`` (1 = lunes ... 7 = domingo), ``inicio`` y ``fin`` en
  "HH:MM" de 24 horas; el fin del día se escribe "24:00".
- Reglas en el servidor (NTI-02): la hora de término debe ser posterior a la
  de inicio (CA-14.2), por lo tanto un bloque no cruza la medianoche; horas en
  punto o y media (granularidad de 30 minutos, ADR-020, punto 2); sin
  solaparse con otro bloque activo del mismo día (se permiten bloques
  contiguos, 08:00-12:00 y 12:00-16:00).
- El solapamiento se verifica con el maestro bloqueado (``expediente_editable``,
  ``select_for_update``): dos peticiones simultáneas del mismo maestro se
  serializan y la segunda ve el bloque de la primera (ADR-020, punto 3).
- ``retirar_bloque``: baja lógica (``retirado_en``); las filas no se
  modifican (ADR-020, punto 4).
- Todo en cualquier estado salvo ``rechazado`` (409, D-7).
Mensajes en el lenguaje del oficio y con las horas en formato de 24 horas
(CA-14.1, RNF-15, RNF-17).
"""
import re

from django.db import transaction
from django.utils import timezone

from expediente.errores import ErrorEstado, ErroresValidacion
from perfil.models import GRANULARIDAD_MINUTOS, MINUTOS_DIA, Disponibilidad
from perfil.servicios import expediente_editable

DIAS = {1: "lunes", 2: "martes", 3: "miércoles", 4: "jueves", 5: "viernes", 6: "sábado", 7: "domingo"}
_HORA = re.compile(r"([0-9]{2}):([0-9]{2})")

MENSAJE_DIA = "Elige el día de la semana."
MENSAJE_HORA_FALTA = "Elige la hora, en formato de 24 horas (por ejemplo, 08:00 o 17:30)."
MENSAJE_HORA_INVALIDA = "Escribe la hora en formato de 24 horas, entre 00:00 y 24:00 (por ejemplo, 08:00 o 17:30)."
MENSAJE_GRANULARIDAD = "Elige una hora en punto o y media (por ejemplo, 08:00 o 08:30)."
MENSAJE_INICIO_FIN_DE_DIA = "La hora de inicio debe ser entre 00:00 y 23:30."
MENSAJE_FIN_NO_POSTERIOR = (
    "Elegiste de {inicio} a {fin}: la hora de término debe ser después de la hora de inicio. "
    "Por ejemplo, de 08:00 a 12:00."
)
MENSAJE_CRUCE_MEDIANOCHE = (
    " Si trabajas pasada la medianoche, guarda dos bloques: uno hasta las 24:00 y otro desde las 00:00 "
    "del día siguiente."
)
MENSAJE_SOLAPAMIENTO = (
    "Este horario se cruza con tu bloque del {dia} de {inicio} a {fin}. "
    "Elige otro horario o quita ese bloque primero."
)
MENSAJE_RECHAZADO = "Tu postulación no fue aprobada, así que ya no puedes cambiar tus horarios."
MENSAJE_RETIRADO = "Ya quitaste este horario."


def formato_hora(minutos):
    """Minutos desde la medianoche a "HH:MM" de 24 horas; 1440 es "24:00" (ADR-020, punto 2)."""
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def _dia(valor, errores):
    if isinstance(valor, str) and valor.isascii() and valor.isdigit() and len(valor) == 1:
        valor = int(valor)
    if isinstance(valor, bool) or not isinstance(valor, int) or valor not in DIAS:
        errores["dia_semana"] = MENSAJE_DIA
        return None
    return valor


def _minutos(datos, campo, errores):
    """"HH:MM" de 24 horas a minutos; anota el error del campo y devuelve ``None`` si no sirve."""
    valor = datos.get(campo)
    if valor in (None, ""):
        errores[campo] = MENSAJE_HORA_FALTA
        return None
    coincidencia = _HORA.fullmatch(valor) if isinstance(valor, str) else None
    if coincidencia is None:
        errores[campo] = MENSAJE_HORA_INVALIDA
        return None
    horas, minutos = int(coincidencia.group(1)), int(coincidencia.group(2))
    if minutos > 59 or horas > 24 or (horas == 24 and minutos != 0):
        errores[campo] = MENSAJE_HORA_INVALIDA
        return None
    total = horas * 60 + minutos
    if total % GRANULARIDAD_MINUTOS:
        errores[campo] = MENSAJE_GRANULARIDAD
        return None
    return total


def _validar(datos):
    errores = {}
    dia = _dia(datos.get("dia_semana"), errores)
    inicio = _minutos(datos, "inicio", errores)
    fin = _minutos(datos, "fin", errores)
    if inicio is not None and inicio >= MINUTOS_DIA:
        errores["inicio"] = MENSAJE_INICIO_FIN_DE_DIA
    elif inicio is not None and fin is not None and fin <= inicio:
        # CA-14.2: término anterior o igual al inicio. Un término anterior
        # suele ser un horario que pasa la medianoche.
        mensaje = MENSAJE_FIN_NO_POSTERIOR.format(inicio=formato_hora(inicio), fin=formato_hora(fin))
        errores["fin"] = mensaje + (MENSAJE_CRUCE_MEDIANOCHE if fin < inicio else "")
    if errores:
        raise ErroresValidacion(errores)
    return dia, inicio, fin


def agregar_bloque(usuario, datos):
    """Guarda un bloque del maestro ``usuario`` (CA-14.1, CA-14.2, CA-14.4). Devuelve la fila creada."""
    with transaction.atomic():
        expediente_editable(usuario.pk, MENSAJE_RECHAZADO)
        dia, inicio, fin = _validar(datos)
        choque = (
            bloques_activos(usuario.pk)
            .filter(dia_semana=dia, inicio_min__lt=fin, fin_min__gt=inicio)
            .first()
        )
        if choque is not None:
            raise ErroresValidacion({"inicio": MENSAJE_SOLAPAMIENTO.format(
                dia=DIAS[choque.dia_semana], inicio=formato_hora(choque.inicio_min), fin=formato_hora(choque.fin_min)
            )})
        return Disponibilidad.objects.create(maestro_id=usuario.pk, dia_semana=dia, inicio_min=inicio, fin_min=fin)


def retirar_bloque(bloque):
    """Baja lógica del bloque (ADR-020, punto 4)."""
    with transaction.atomic():
        expediente_editable(bloque.maestro_id, MENSAJE_RECHAZADO)
        bloque = Disponibilidad.objects.select_for_update().get(pk=bloque.pk)
        if bloque.retirado_en is not None:
            raise ErrorEstado(MENSAJE_RETIRADO)
        bloque.retirado_en = timezone.now()
        bloque.save(update_fields=["retirado_en"])
    return bloque


def bloques_activos(maestro_id):
    """Bloques no retirados del maestro, por día y hora de inicio."""
    return Disponibilidad.objects.filter(maestro_id=maestro_id, retirado_en__isnull=True).order_by(
        "dia_semana", "inicio_min", "pk"
    )
