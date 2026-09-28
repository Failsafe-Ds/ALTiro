"""Catálogo mínimo de oficios (ADR-017, punto 1; RF-33; DA-15)."""
import csv

import pytest

from catalogo.carga import ARCHIVO_OFICIOS, cargar, leer_filas
from catalogo.models import Oficio

URL_OFICIOS = "/api/oficios"


def test_el_csv_versionado_solo_confirma_gas_y_electricidad_como_regulados():
    with open(ARCHIVO_OFICIOS, encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))

    assert len(filas) == 8
    assert len({f["codigo"] for f in filas}) == 8
    assert {f["codigo"] for f in filas if f["regulado"] == "si"} == {"gas", "electricidad"}
    assert {f["regulado"] for f in filas} == {"si", "no"}
    # P-01 sin respuesta: los no regulados son ficticios y se rotulan como tales.
    for fila in filas:
        if fila["regulado"] == "no":
            assert "(por confirmar)" in fila["nombre"]


@pytest.mark.django_db
def test_la_migracion_carga_el_catalogo():
    assert Oficio.objects.count() == 8
    assert Oficio.objects.get(codigo="gas").regulado is True
    assert Oficio.objects.get(codigo="electricidad").regulado is True
    assert Oficio.objects.filter(regulado=True).count() == 2


@pytest.mark.django_db
def test_la_carga_es_idempotente_y_no_duplica():
    antes = dict(Oficio.objects.values_list("codigo", "pk"))

    cargar(Oficio, leer_filas())
    cargar(Oficio, leer_filas())

    assert Oficio.objects.count() == 8
    assert dict(Oficio.objects.values_list("codigo", "pk")) == antes


@pytest.mark.django_db
def test_la_carga_actualiza_por_codigo_y_nunca_borra():
    Oficio.objects.filter(codigo="gas").update(nombre="Otro nombre", regulado=False)
    Oficio.objects.create(codigo="fuera_del_csv", nombre="Fuera del CSV", regulado=False, orden=99)

    cargar(Oficio, leer_filas())

    gas = Oficio.objects.get(codigo="gas")
    assert (gas.nombre, gas.regulado) == ("Gas", True)
    assert Oficio.objects.filter(codigo="fuera_del_csv").exists()


@pytest.mark.django_db
def test_oficios_es_publica_ordenada_y_con_lista_explicita_de_campos(client):
    respuesta = client.get(URL_OFICIOS)

    assert respuesta.status_code == 200
    oficios = respuesta.json()["oficios"]
    assert [o["codigo"] for o in oficios][:2] == ["gas", "electricidad"]
    assert len(oficios) == 8
    assert oficios[0] == {"codigo": "gas", "nombre": "Gas", "regulado": True}
    assert all(set(o) == {"codigo", "nombre", "regulado"} for o in oficios)


@pytest.mark.django_db
@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_oficios_es_de_solo_lectura(client, metodo):
    respuesta = getattr(client, metodo)(URL_OFICIOS)

    assert respuesta.status_code == 405
    assert Oficio.objects.count() == 8
