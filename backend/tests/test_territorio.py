"""Catálogo territorial (RF-01, CA-01.2, ADR-012)."""
import csv

import pytest

from territorio.carga import ARCHIVO_CUT, cargar, leer_filas
from territorio.models import Comuna, Provincia, Region

URL_REGIONES = "/api/territorio/regiones"


def _url_comunas(codigo):
    return f"/api/territorio/regiones/{codigo}/comunas"


def test_el_csv_versionado_tiene_la_division_oficial_y_codigos_coherentes():
    with open(ARCHIVO_CUT, encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))

    assert len(filas) == 346
    assert len({f["provincia_codigo"] for f in filas}) == 56
    assert len({f["region_codigo"] for f in filas}) == 16
    for fila in filas:
        # CUT: provincia = región * 10 + n; comuna = provincia * 100 + n.
        assert int(fila["provincia_codigo"]) // 10 == int(fila["region_codigo"])
        assert int(fila["comuna_codigo"]) // 100 == int(fila["provincia_codigo"])


@pytest.mark.django_db
def test_la_migracion_carga_el_catalogo_completo():
    assert Region.objects.count() == 16
    assert Provincia.objects.count() == 56
    assert Comuna.objects.count() == 346
    assert Comuna.objects.get(codigo=8101).nombre == "Concepción"
    assert Comuna.objects.get(codigo=16101).provincia.region.nombre == "Ñuble"


@pytest.mark.django_db
def test_la_carga_es_idempotente():
    cargar(Region, Provincia, Comuna, leer_filas())
    cargar(Region, Provincia, Comuna, leer_filas())

    assert Comuna.objects.count() == 346
    assert Region.objects.count() == 16


@pytest.mark.django_db
def test_regiones_es_publica_y_va_de_norte_a_sur(client):
    respuesta = client.get(URL_REGIONES)

    assert respuesta.status_code == 200
    regiones = respuesta.json()["regiones"]
    assert len(regiones) == 16
    assert regiones[0] == {"codigo": 15, "nombre": "Arica y Parinacota"}
    assert regiones[-1]["codigo"] == 12
    assert "max-age" in respuesta["Cache-Control"]


@pytest.mark.django_db
def test_ca012_solo_aparecen_las_comunas_de_la_region_elegida(client):
    respuesta = client.get(_url_comunas(8))

    assert respuesta.status_code == 200
    comunas = respuesta.json()["comunas"]
    codigos = {c["codigo"] for c in comunas}
    assert codigos == set(Comuna.objects.filter(provincia__region_id=8).values_list("codigo", flat=True))
    assert len(comunas) == 33
    assert all(c["codigo"] // 1000 == 8 for c in comunas)
    concepcion = next(c for c in comunas if c["codigo"] == 8101)
    assert concepcion == {"codigo": 8101, "nombre": "Concepción", "provincia": {"codigo": 81, "nombre": "Concepción"}}
    assert [c["nombre"] for c in comunas] == sorted(c["nombre"] for c in comunas)


@pytest.mark.django_db
def test_region_inexistente_responde_404_accionable(client):
    respuesta = client.get(_url_comunas(99))

    assert respuesta.status_code == 404
    assert "región" in respuesta.json()["mensaje"]


@pytest.mark.django_db
def test_el_catalogo_no_admite_escritura(client):
    assert client.post(URL_REGIONES).status_code == 405
    assert client.delete(_url_comunas(8)).status_code == 405
