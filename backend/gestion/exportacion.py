"""Exportación CSV agregada y anonimizada (HU-22, RF-38, CA-22.2; ADR-026, E-6.2; R-08).

- Columnas en lista cerrada (``COLUMNAS``); nunca ``ref``, ids ni texto libre.
  Región, comuna y oficio salen de sus listas cerradas.
- Una fila por mes (de ``enviado_en`` en ``America/Santiago``), región y comuna
  del pedido y oficio del servicio. Agregación en la base.
- Se **suprime** la fila con menos de ``K`` maestros distintos o menos de ``K``
  clientes distintos (P-29). Sin totales, mínimos ni máximos.
- ``mediana_monto_final`` solo se publica si la fila tiene ``K`` o más órdenes
  finalizadas con monto y, entre ellas, ``K`` o más maestros y ``K`` o más
  clientes distintos; si no, la celda queda vacía (DEF-QA-014; enmienda
  E-6.5 de ADR-026, provisional). ``ordenes_finalizadas`` se publica igual.
- Las celdas que empiezan con ``= + - @`` (y tabulador o retorno) se
  neutralizan con un apóstrofo inicial (inyección de fórmulas).
"""
import csv
import io

from django.db.models import Count, F
from django.db.models.functions import TruncMonth

from expediente.vigencia import ZONA_NEGOCIO
from gestion.indicadores import FILTRO_CONCRETADO, Mediana, tickets_del_periodo

COLUMNAS = (
    "mes", "region", "comuna", "oficio", "tickets_enviados", "ordenes_finalizadas", "mediana_monto_final",
)
K = 5
_PELIGROSOS = ("=", "+", "-", "@", "\t", "\r")


def neutralizar(valor):
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto.startswith(_PELIGROSOS) else texto


def _grupos(inicio, fin):
    return (
        tickets_del_periodo(inicio, fin)
        .annotate(mes=TruncMonth("enviado_en", tzinfo=ZONA_NEGOCIO))
        .values(
            "mes",
            region_nombre=F("comuna__provincia__region__nombre"),
            comuna_nombre=F("comuna__nombre"),
            oficio_nombre=F("servicio_maestro__servicio__oficio__nombre"),
        )
        .annotate(
            enviados=Count("id"),
            finalizadas=Count("id", filter=FILTRO_CONCRETADO),
            maestros=Count("perfil_maestro_id", distinct=True),
            clientes=Count("cliente_id", distinct=True),
            maestros_finalizadas=Count("perfil_maestro_id", filter=FILTRO_CONCRETADO, distinct=True),
            clientes_finalizadas=Count("cliente_id", filter=FILTRO_CONCRETADO, distinct=True),
            mediana=Mediana("monto_final", filter=FILTRO_CONCRETADO),
        )
        .order_by("mes", "region_nombre", "comuna_nombre", "oficio_nombre")
    )


def _mediana_publicable(grupo):
    """La mediana no depende de menos de ``K`` órdenes, maestros ni clientes (E-6.5)."""
    return (
        grupo["mediana"] is not None
        and grupo["finalizadas"] >= K
        and grupo["maestros_finalizadas"] >= K
        and grupo["clientes_finalizadas"] >= K
    )


def generar(inicio, fin):
    """Devuelve ``(texto_csv, filas, suprimidas)``."""
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\r\n")
    escritor.writerow(COLUMNAS)
    filas = suprimidas = 0
    for grupo in _grupos(inicio, fin):
        if grupo["maestros"] < K or grupo["clientes"] < K:
            suprimidas += 1
            continue
        mediana = grupo["mediana"] if _mediana_publicable(grupo) else None
        escritor.writerow([
            neutralizar(valor)
            for valor in (
                grupo["mes"].astimezone(ZONA_NEGOCIO).strftime("%Y-%m"),
                grupo["region_nombre"],
                grupo["comuna_nombre"],
                grupo["oficio_nombre"],
                grupo["enviados"],
                grupo["finalizadas"],
                "" if mediana is None else int(mediana + 0.5),  # mitad hacia arriba
            )
        ])
        filas += 1
    return salida.getvalue(), filas, suprimidas
