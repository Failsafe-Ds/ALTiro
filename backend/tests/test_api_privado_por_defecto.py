"""Toda ruta /api/ es privada salvo las declaradas públicas (RF-02, CA-25.3; propuesta del S1, §5)."""
import pytest

from tests.control_terceros import rutas, url_de_ejemplo

# Lista cerrada de rutas públicas. Agregar una ruta pública exige cambiar esta prueba.
RUTAS_PUBLICAS = {
    "api/health/",
    "api/territorio/regiones",
    "api/territorio/regiones/<int:codigo>/comunas",
    "api/sesion/csrf",
    "api/sesion",
    "api/clientes",
    "api/maestros/postulaciones",
}


def _rutas_api():
    """Patrón -> vista de todas las rutas, entrando en los include."""
    return {ruta.patron: ruta.vista for ruta in rutas()}


def test_las_unicas_vistas_publicas_son_las_declaradas():
    publicas = {ruta for ruta, vista in _rutas_api().items() if getattr(vista, "publica", False)}

    assert publicas == RUTAS_PUBLICAS


@pytest.mark.django_db
@pytest.mark.parametrize("metodo", ["get", "post", "put", "patch", "delete"])
def test_toda_ruta_privada_responde_401_sin_sesion(client, metodo):
    privadas = [ruta for ruta in _rutas_api() if ruta not in RUTAS_PUBLICAS]
    assert privadas, "debe existir al menos una ruta privada"

    for ruta in privadas:
        respuesta = getattr(client, metodo)(url_de_ejemplo(ruta))
        assert respuesta.status_code == 401, ruta
        assert "Inicia sesión" in respuesta.json()["mensaje"]


@pytest.mark.django_db
def test_ruta_inexistente_responde_404_en_json_sin_detalles(client):
    respuesta = client.get("/api/no-existe")

    assert respuesta.status_code == 404
    assert set(respuesta.json()) == {"mensaje", "errores"}
