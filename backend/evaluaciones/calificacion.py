"""Calificación del maestro (RF-30, RF-13, RF-14, CA-05.1, CA-05.2; ADR-026, E-3.3 a E-3.5).

- Solo evaluaciones ``publicada`` con ``parte='cliente'`` (las que el cliente
  hizo del maestro). Una retirada por moderación no cuenta y no se borra.
- Promedio = media de ``(puntualidad + trabajo + cordialidad) / 3`` por
  evaluación, redondeado a 1 decimal (mitad hacia arriba). Como las tres notas
  pesan igual, es ``suma(p + t + c) / (3 · n)``. Cada dimensión, su media.
- Se calcula en cada lectura y nunca se guarda (patrón de ADR-019).
- ``de_maestros`` resuelve un lote en una sola consulta (búsqueda sin N+1).
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, F, Sum
from django.utils import timezone

from evaluaciones.models import EstadoEvaluacion, Evaluacion, ParteEvaluacion
from perfil import ocurrencias
from tickets.avisos import MESES

SIN_EVALUACIONES = "Todavía no tiene evaluaciones"
COMENTARIOS_EN_FICHA = 10
_DECIMAL = Decimal("0.1")


@dataclass(frozen=True)
class Calificacion:
    promedio: Decimal
    cantidad: int
    puntualidad: Decimal
    trabajo: Decimal
    cordialidad: Decimal


def redondear(numerador, denominador):
    return (Decimal(numerador) / Decimal(denominador)).quantize(_DECIMAL, rounding=ROUND_HALF_UP)


def publicadas_del_cliente():
    return Evaluacion.objects.filter(parte=ParteEvaluacion.CLIENTE, estado=EstadoEvaluacion.PUBLICADA)


def de_maestros(maestro_ids):
    """``{maestro_id: Calificacion}``; los maestros sin evaluaciones no aparecen."""
    ids = list(maestro_ids)
    if not ids:
        return {}
    filas = (
        publicadas_del_cliente()
        .filter(evaluado_id__in=ids)
        .values("evaluado_id")
        .annotate(
            n=Count("id"),
            p=Sum("puntualidad"),
            t=Sum("trabajo"),
            c=Sum("cordialidad"),
            total=Sum(F("puntualidad") + F("trabajo") + F("cordialidad")),
        )
    )
    return {
        f["evaluado_id"]: Calificacion(
            promedio=redondear(f["total"], 3 * f["n"]),
            cantidad=f["n"],
            puntualidad=redondear(f["p"], f["n"]),
            trabajo=redondear(f["t"], f["n"]),
            cordialidad=redondear(f["c"], f["n"]),
        )
        for f in filas
    }


def de_maestro(maestro_id):
    return de_maestros([maestro_id]).get(maestro_id)


def _numero(valor):
    """"4,3" (coma decimal, como se escribe en Chile)."""
    return f"{valor:.1f}".replace(".", ",")


def texto(calificacion):
    if calificacion is None:
        return SIN_EVALUACIONES
    evaluaciones = "1 evaluación" if calificacion.cantidad == 1 else f"{calificacion.cantidad} evaluaciones"
    return f"{_numero(calificacion.promedio)} de 5 ({evaluaciones})"


def datos_tarjeta(calificacion):
    """RF-13: promedio y cantidad, o ``None`` si no tiene evaluaciones (CA-05.2)."""
    if calificacion is None:
        return None
    return {"promedio": float(calificacion.promedio), "cantidad": calificacion.cantidad}


def datos_ficha(calificacion):
    """RF-14, CA-05.1: además, cada dimensión por separado."""
    if calificacion is None:
        return None
    return {
        **datos_tarjeta(calificacion),
        "puntualidad": float(calificacion.puntualidad),
        "trabajo": float(calificacion.trabajo),
        "cordialidad": float(calificacion.cordialidad),
    }


def mes_y_anio(instante):
    local = timezone.localtime(instante, ocurrencias.ZONA)
    return f"{MESES[local.month - 1]} de {local.year}"


def comentarios(maestro_id):
    """Últimos 10 comentarios con mes y año, sin nombre ni ref del autor (E-3.5, minimización)."""
    filas = (
        publicadas_del_cliente()
        .filter(evaluado_id=maestro_id)
        .exclude(comentario="")
        .order_by("-creada_en", "-id")
        .values("comentario", "creada_en")[:COMENTARIOS_EN_FICHA]
    )
    return [{"texto": f["comentario"], "fecha_texto": mes_y_anio(f["creada_en"])} for f in filas]
