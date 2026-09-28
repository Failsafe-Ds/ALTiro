"""Privacidad de las respuestas JSON (RNF-08, base; RNF-05; propuesta del S1, §5, punto 5)."""
import pytest
from django.http import HttpResponse, JsonResponse

from identidad.models import Usuario
from tests.ayudas import CONTRASENA, URL_CUENTA, crear_cliente, iniciar_sesion
from tests.privacidad import assert_campos_ausentes

CAMPOS_SENSIBLES = {"password", "contrasena", "hash", "last_login", "id"}


# --- El helper ---


def test_detecta_una_clave_anidada():
    respuesta = JsonResponse({"cuenta": {"perfiles": [{"datos": {"password": "x"}}]}})

    with pytest.raises(AssertionError, match="password"):
        assert_campos_ausentes(respuesta, {"password"})


def test_detecta_un_valor_unicode_escrito_con_escapes():
    respuesta = JsonResponse({"cliente": {"direccion": "Pasaje Ñuñoa 123"}})  # ensure_ascii: Ñ
    assert "Ñuñoa".encode("utf-8") not in respuesta.content

    with pytest.raises(AssertionError):
        assert_campos_ausentes(respuesta, set(), valores=["Ñuñoa"])


def test_detecta_un_valor_dentro_de_una_lista():
    respuesta = HttpResponse(b'{"telefonos": ["+56910000001"]}', content_type="application/json")

    with pytest.raises(AssertionError):
        assert_campos_ausentes(respuesta, set(), valores=["910000001"])


def test_no_falla_si_no_hay_datos_prohibidos():
    respuesta = JsonResponse({"cuenta": {"nombre": "Ana", "comuna": {"codigo": 8101}}})

    assert_campos_ausentes(respuesta, {"password"}, valores=["secreto"])


# --- Uso en /api/cuenta y /api/sesion ---


@pytest.mark.django_db
def test_sesion_y_cuenta_no_exponen_contrasena_ni_hash(client):
    crear_cliente()
    hash_guardado = Usuario.objects.get().password

    sesion = iniciar_sesion(client, "ana.prueba@example.com")
    cuenta = client.get(URL_CUENTA)

    for respuesta in (sesion, cuenta):
        assert respuesta.status_code == 200
        assert_campos_ausentes(respuesta, CAMPOS_SENSIBLES, valores=[CONTRASENA, hash_guardado, "$argon2"])
