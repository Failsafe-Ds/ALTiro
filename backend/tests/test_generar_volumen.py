"""Comando ``generar_volumen_prueba`` (RNF-01, RNF-03; propuesta del S4, §2): datos ficticios, idempotente."""
import pytest
from django.core.management import CommandError, call_command
from django.test import Client

from expediente.models import EstadoExpediente, Expediente
from identidad.models import PerfilMaestro, Usuario
from perfil import publicacion
from perfil.models import ServicioMaestro

pytestmark = pytest.mark.django_db


def test_se_niega_sin_la_confirmacion():
    with pytest.raises(CommandError, match="confirmo-datos-ficticios"):
        call_command("generar_volumen_prueba", "--semilla", "42", "--maestros", "1")
    assert not PerfilMaestro.objects.exists()


def test_crea_maestros_ficticios_publicados_e_idempotentes(capsys):
    call_command("generar_volumen_prueba", "--semilla", "42", "--confirmo-datos-ficticios", "--maestros", "3")
    assert "Maestros ficticios nuevos: 3 de 3" in capsys.readouterr().out

    maestros = list(PerfilMaestro.objects.select_related("usuario"))
    assert len(maestros) == 3
    for perfil in maestros:
        assert "Ficticio" in perfil.usuario.nombre and "(datos de prueba)" in perfil.usuario.nombre
        assert perfil.usuario.correo is None and perfil.usuario.telefono.startswith("+5690000")
        assert not perfil.usuario.has_usable_password()
        assert Expediente.objects.get(perfil_maestro=perfil).estado == EstadoExpediente.APROBADO
        assert publicacion.maestro_publicado(perfil.pk)
        visibles = publicacion.servicios_visibles(perfil.pk)
        assert len(visibles) == 3 and not any(s.servicio.oficio.regulado for s in visibles)

    # Misma semilla: no crea nada nuevo ni cambia lo existente.
    antes = sorted(ServicioMaestro.objects.values_list("pk", "monto"))
    call_command("generar_volumen_prueba", "--semilla", "42", "--confirmo-datos-ficticios", "--maestros", "3")
    assert "Maestros ficticios nuevos: 0 de 3" in capsys.readouterr().out
    assert PerfilMaestro.objects.count() == 3 and Usuario.objects.count() == 3
    assert sorted(ServicioMaestro.objects.values_list("pk", "monto")) == antes


def test_los_maestros_ficticios_aparecen_en_la_busqueda():
    call_command("generar_volumen_prueba", "--semilla", "7", "--confirmo-datos-ficticios", "--maestros", "4")
    servicio = ServicioMaestro.objects.select_related("servicio__oficio").first()
    comuna = servicio.maestro.coberturas.get(es_base=True).comuna_id
    respuesta = Client().get("/api/busqueda", {"oficio": servicio.servicio.oficio.codigo, "comuna": comuna})
    assert respuesta.status_code == 200 and respuesta.json()["total"] >= 1
