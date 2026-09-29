"""Catálogo mínimo de oficios (ADR-017, punto 1; RF-33; DA-15)."""
import csv
import importlib

import pytest
from django.apps import apps as registro_apps

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
    # Lista provisional (P-01, P-02): nombres reales, sin rótulos de ejemplo.
    assert [f["codigo"] for f in filas] == [
        "gas", "electricidad", "gasfiteria", "carpinteria", "pintura", "albanileria", "cerrajeria", "jardineria",
    ]
    assert [int(f["orden"]) for f in filas] == list(range(1, 9))
    for fila in filas:
        assert "ejemplo" not in fila["nombre"].lower()
        assert "por confirmar" not in fila["nombre"]


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
def test_la_carga_solo_inserta_no_pisa_cambios_de_comercial_y_nunca_borra():
    """ADR-018, punto 3 (D-3): el CSV es solo la carga inicial."""
    Oficio.objects.filter(codigo="pintura").update(nombre="Pintura y barnizado", orden=40, activo=False)
    Oficio.objects.filter(codigo="electricidad").delete()
    Oficio.objects.create(codigo="fuera_del_csv", nombre="Fuera del CSV", regulado=False, orden=99)

    cargar(Oficio, leer_filas())

    pintura = Oficio.objects.get(codigo="pintura")
    assert (pintura.nombre, pintura.orden, pintura.activo) == ("Pintura y barnizado", 40, False)
    # El que faltaba se inserta, con su propio ref.
    assert Oficio.objects.get(codigo="electricidad").regulado is True
    assert Oficio.objects.filter(codigo="fuera_del_csv").exists()
    assert Oficio.objects.values("ref").distinct().count() == Oficio.objects.count()


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


# --- Migración 0003: renombra los oficios de ejemplo (P-01) ---

_migracion_0003 = importlib.import_module("catalogo.migrations.0003_renombra_oficios_de_ejemplo")


def _base_con_oficios_de_ejemplo():
    """Deja el catálogo como quedaba con el CSV anterior (ejemplo_1 a ejemplo_6)."""
    for anterior, nuevo in _migracion_0003.RENOMBRES:
        Oficio.objects.filter(codigo=nuevo).update(
            codigo=anterior, nombre=f"Oficio de ejemplo {anterior[-1]} (por confirmar)"
        )


@pytest.mark.django_db
def test_la_migracion_0003_renombra_en_la_misma_fila_y_conserva_las_declaraciones():
    from expediente.models import OficioMaestro
    from tests.ayudas import crear_maestro

    _base_con_oficios_de_ejemplo()
    maestro = crear_maestro()
    ejemplo_1 = Oficio.objects.get(codigo="ejemplo_1")
    OficioMaestro.objects.create(maestro=maestro.perfil_maestro, oficio=ejemplo_1)

    _migracion_0003.renombrar_oficios(registro_apps, None)

    assert not Oficio.objects.filter(codigo__startswith="ejemplo_").exists()
    gasfiteria = Oficio.objects.get(codigo="gasfiteria")
    assert gasfiteria.pk == ejemplo_1.pk
    # Desde el S3 ``cargar`` solo inserta (ADR-018, punto 3): en una base que
    # todavía tuviera los códigos de ejemplo, 0003 renombra el código en la misma
    # fila pero ya no pisa el nombre; lo corrige comercial desde la aplicación.
    assert (gasfiteria.nombre, gasfiteria.regulado) == ("Oficio de ejemplo 1 (por confirmar)", False)
    declaracion = OficioMaestro.objects.get(maestro=maestro.perfil_maestro)
    assert declaracion.oficio.codigo == "gasfiteria"
    assert Oficio.objects.count() == 8


@pytest.mark.django_db
def test_la_migracion_0003_es_idempotente():
    _base_con_oficios_de_ejemplo()
    _migracion_0003.renombrar_oficios(registro_apps, None)
    despues = list(Oficio.objects.values_list("pk", "codigo", "nombre", "regulado", "orden"))

    _migracion_0003.renombrar_oficios(registro_apps, None)

    assert list(Oficio.objects.values_list("pk", "codigo", "nombre", "regulado", "orden")) == despues
    assert not Oficio.objects.filter(codigo__startswith="ejemplo_").exists()


@pytest.mark.django_db
def test_la_migracion_0003_no_toca_un_ejemplo_si_su_codigo_nuevo_ya_existe():
    Oficio.objects.create(codigo="ejemplo_1", nombre="Oficio de ejemplo 1 (por confirmar)", regulado=False, orden=3)
    gasfiteria_pk = Oficio.objects.get(codigo="gasfiteria").pk

    _migracion_0003.renombrar_oficios(registro_apps, None)

    assert Oficio.objects.get(codigo="gasfiteria").pk == gasfiteria_pk
    assert Oficio.objects.filter(codigo="ejemplo_1").exists()
