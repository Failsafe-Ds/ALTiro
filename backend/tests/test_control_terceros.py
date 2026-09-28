"""Prueba de control de RNF-07: toda ruta con identificador tiene prueba de terceros y usa uuid (ADR-011, punto 1)."""
from django.urls import include, path

from tests import control_terceros
from tests.control_terceros import RUTAS_EXENTAS, marcas_terceros, problemas, rutas


def _vista(request, **kwargs):
    return None


def test_toda_ruta_con_identificador_tiene_prueba_de_terceros_y_usa_uuid():
    todas = rutas()
    con_identificador = [r for r in todas if r.convertidores and r.patron not in RUTAS_EXENTAS]

    # El control no es vacío: al menos el recurso ficticio tiene identificador.
    assert "prueba_recurso" in {r.nombre for r in con_identificador}
    assert problemas(todas, marcas_terceros()) == []


def test_las_exenciones_son_solo_las_declaradas_y_publicas():
    assert RUTAS_EXENTAS == {"api/territorio/regiones/<int:codigo>/comunas"}
    exentas = [r for r in rutas() if r.patron in RUTAS_EXENTAS]
    assert len(exentas) == len(RUTAS_EXENTAS)
    assert all(r.publica for r in exentas)


def test_meta_detecta_ruta_sin_marca_y_convertidor_no_uuid_dentro_de_un_include():
    patrones = [
        path("api/x/<int:id>", _vista, name="x"),
        path("", include([path("api/y/<uuid:ref>", _vista, name="y")])),
        path("api/z", _vista, name="z"),
    ]
    lista = rutas(patrones)
    assert {r.patron for r in lista} == {"api/x/<int:id>", "api/y/<uuid:ref>", "api/z"}

    sin_marcas = problemas(lista, marcas=set(), exentas=set())
    assert any(p.startswith("api/x/<int:id>") and "sin prueba" in p for p in sin_marcas)
    assert any(p.startswith("api/x/<int:id>") and "uuid" in p for p in sin_marcas)
    assert any(p.startswith("api/y/<uuid:ref>") and "sin prueba" in p for p in sin_marcas)
    assert not any(p.startswith("api/z") for p in sin_marcas)

    con_marca_y = problemas(lista, marcas={"y"}, exentas=set())
    assert not any(p.startswith("api/y/") for p in con_marca_y)
    assert any(p.startswith("api/x/") for p in con_marca_y)


def test_meta_lee_las_marcas_de_forma_estatica(tmp_path):
    (tmp_path / "test_ejemplo.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.terceros('ruta_a')\n"
        "def test_a():\n    pass\n\n"
        "@pytest.mark.otra('ruta_b')\n"
        "def test_b():\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "ayuda.py").write_text(
        "import pytest\n\n@pytest.mark.terceros('ruta_c')\ndef test_c():\n    pass\n", encoding="utf-8"
    )

    assert marcas_terceros(tmp_path) == {"ruta_a"}


def test_url_de_ejemplo_usa_valores_validos():
    assert control_terceros.url_de_ejemplo("api/prueba/recursos/<uuid:ref>") == (
        "/api/prueba/recursos/00000000-0000-0000-0000-000000000001"
    )
    assert control_terceros.url_de_ejemplo("api/r/<int:codigo>/c") == "/api/r/1/c"
