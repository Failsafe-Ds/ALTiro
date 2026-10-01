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
  E-6.5 de ADR-026, provisional).
- ``ordenes_finalizadas`` entre 1 y ``K - 1`` queda vacía (y su mediana
  también). Si en un mes queda **una sola** de esas celdas vacía, se vacía
  además la menor de las demás de ese mes (supresión complementaria): el total
  del mes que da el indicador de concreción no permite despejarla (E-6.6).
- El período son meses calendario completos y cerrados (``vistas.leer_periodo``):
  dos exportaciones no se solapan a medias (E-6.6).
- Las celdas que empiezan con ``= + - @`` (y tabulador o retorno) se
  neutralizan con un apóstrofo inicial (inyección de fórmulas).
"""
import csv
import io
from collections import defaultdict

from django.db.models import Count, F
from django.db.models.functions import TruncMonth

from expediente.vigencia import ZONA_NEGOCIO
from gestion.indicadores import FILTRO_CONCRETADO, K, Mediana, pequeno, tickets_del_periodo

COLUMNAS = (
    "mes", "region", "comuna", "oficio", "tickets_enviados", "ordenes_finalizadas", "mediana_monto_final",
)
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


def _publicables(grupos):
    """Filas que superan la supresión (P-29) y marca de celdas ``finalizadas`` ocultas (E-6.6)."""
    publicadas, suprimidas = [], 0
    for grupo in grupos:
        if grupo["maestros"] < K or grupo["clientes"] < K:
            suprimidas += 1
            continue
        grupo["oculta"] = pequeno(grupo["finalizadas"])
        publicadas.append(grupo)
    por_mes = defaultdict(list)
    for grupo in publicadas:
        por_mes[grupo["mes"]].append(grupo)
    for del_mes in por_mes.values():
        visibles = [g for g in del_mes if not g["oculta"]]
        if len(del_mes) - len(visibles) == 1 and visibles:
            min(visibles, key=lambda g: g["finalizadas"])["oculta"] = True  # supresión complementaria
    return publicadas, suprimidas


def generar(inicio, fin):
    """Devuelve ``(texto_csv, filas, filas_suprimidas, celdas_suprimidas)``."""
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\r\n")
    escritor.writerow(COLUMNAS)
    publicadas, suprimidas = _publicables(_grupos(inicio, fin))
    for grupo in publicadas:
        oculta = grupo["oculta"]
        mediana = grupo["mediana"] if not oculta and _mediana_publicable(grupo) else None
        escritor.writerow([
            neutralizar(valor)
            for valor in (
                grupo["mes"].astimezone(ZONA_NEGOCIO).strftime("%Y-%m"),
                grupo["region_nombre"],
                grupo["comuna_nombre"],
                grupo["oficio_nombre"],
                grupo["enviados"],
                "" if oculta else grupo["finalizadas"],
                "" if mediana is None else int(mediana + 0.5),  # mitad hacia arriba
            )
        ])
    celdas = sum(grupo["oculta"] for grupo in publicadas)
    return salida.getvalue(), len(publicadas), suprimidas, celdas
