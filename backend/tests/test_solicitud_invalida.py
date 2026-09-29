"""handler400 en JSON y en español (DEF-QA-006, parte backend; RNF-15).

Con DEBUG=False, Django responde 400 ante un Host no permitido
(DisallowedHost), un cuerpo multipart ilegible o demasiados campos o archivos.
Sin handler400 propio, esa respuesta era el HTML de Django.
"""
import pytest

from tests.ayudas import sin_texto_prohibido

MENSAJE = "No pudimos leer lo que enviaste. Vuelve a cargar la página e inténtalo de nuevo."


@pytest.mark.django_db
@pytest.mark.parametrize("ruta", ["/api/health/", "/api/sesion/csrf", "/api/no-existe"])
def test_host_no_permitido_responde_400_en_json_sin_texto_tecnico(client, ruta):
    respuesta = client.get(ruta, HTTP_HOST="evil.example")

    assert respuesta.status_code == 400
    assert respuesta["Content-Type"].startswith("application/json")
    assert respuesta.json() == {"mensaje": MENSAJE, "errores": {}}
    texto = respuesta.content.decode("utf-8")
    assert sin_texto_prohibido(respuesta)
    for tecnico in ("DisallowedHost", "ALLOWED_HOSTS", "Bad Request", "evil.example", "<html"):
        assert tecnico not in texto
