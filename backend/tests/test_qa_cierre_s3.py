"""Pruebas agregadas por QA en el cierre del Sprint 3 (docs/testing/cierre-sprint-3.md).

Cubren bordes que el QA verificó en vivo y que no tenían una prueba propia:

- Propuesta del S3, §9.1: la foto pública con un ETag válido de cuando el
  maestro estaba publicado responde el 404 neutro (nunca 304) si ya no lo está.
- CA-24.1 en el borde de la medianoche de Santiago (no de UTC): el servicio
  regulado deja de verse a las 00:00 del día del vencimiento, hora de Chile.
- CA-24.3 con el planificador: una licencia sin vencimiento no desactiva
  ningún servicio aunque corran todas las tareas años después.

Datos ficticios (@example.com, RUT sintéticos), imágenes sintéticas.
"""
import datetime
import zoneinfo

import pytest
import time_machine
from django.test import Client

from expediente.management.commands.planificador import correr_tareas
from expediente.models import Documento, EstadoExpediente, Expediente
from expediente.vigencia import hoy_negocio
from perfil import publicacion
from tests.test_perfil_publico import (  # noqa: F401 (fixtures)
    NO_ENCONTRADO,
    _licencia,
    _url,
    catalogo,
    maestro,
    publicado,
)

pytestmark = pytest.mark.django_db

SANTIAGO = zoneinfo.ZoneInfo("America/Santiago")


def _oficios_visibles(usuario):
    respuesta = Client().get(_url(usuario))
    if respuesta.status_code != 200:
        return None
    return sorted(s["oficio"]["codigo"] for s in respuesta.json()["maestro"]["servicios"])


def test_qa_s3_foto_con_etag_valido_de_un_maestro_que_dejo_de_estar_publicado_responde_404(publicado):
    url = f"{_url(publicado)}/foto"
    primera = Client().get(url, {"tam": 480})
    assert primera.status_code == 200
    etag = primera["ETag"]
    assert Client().get(url, {"tam": 480}, HTTP_IF_NONE_MATCH=etag).status_code == 304

    Expediente.objects.filter(perfil_maestro_id=publicado.pk).update(estado=EstadoExpediente.SUSPENDIDO)

    revalidada = Client().get(url, {"tam": 480}, HTTP_IF_NONE_MATCH=etag)
    assert revalidada.status_code == 404
    assert revalidada.content == NO_ENCONTRADO
    assert "ETag" not in revalidada


def test_qa_s3_ca24_1_el_servicio_regulado_se_oculta_a_la_medianoche_de_santiago(publicado):
    Documento.objects.filter(expediente__perfil_maestro_id=publicado.pk).delete()
    manana = hoy_negocio() + datetime.timedelta(days=2)
    _licencia(publicado, "gas", vencimiento=manana)
    medianoche = datetime.datetime.combine(manana, datetime.time(0, 0), tzinfo=SANTIAGO)

    with time_machine.travel(medianoche - datetime.timedelta(seconds=1), tick=False):
        assert _oficios_visibles(publicado) == ["gas", "pintura"]
    with time_machine.travel(medianoche, tick=False):
        assert _oficios_visibles(publicado) == ["pintura"]


def test_qa_s3_ca24_3_licencia_sin_vencimiento_no_desactiva_nada_aunque_corra_el_planificador(publicado):
    Documento.objects.filter(expediente__perfil_maestro_id=publicado.pk).update(fecha_vencimiento=None)
    assert _oficios_visibles(publicado) == ["gas", "pintura"]

    for anos in (1, 5, 30):
        futuro = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365 * anos)
        with time_machine.travel(futuro, tick=False):
            _, fallidas = correr_tareas()
            assert fallidas == []
            assert _oficios_visibles(publicado) == ["gas", "pintura"]
            assert publicacion.maestro_publicado(publicado.pk)
