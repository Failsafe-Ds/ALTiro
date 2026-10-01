"""``cargar_datos_demo --con-cuentas`` y ``limpiar_oficios_de_prueba`` (ADR-028): datos ficticios de la demostración."""
import re

import pytest
from django.core.management import CommandError, call_command
from django.test import Client

from busqueda import cuentas_demo
from catalogo.models import Oficio, Servicio, ServicioModalidad
from expediente.models import EstadoExpediente, Expediente
from identidad.models import PerfilMaestro, Usuario
from perfil import publicacion
from perfil.models import ServicioMaestro
from tests.ayudas import iniciar_sesion
from tickets.models import EstadoTicket, Ticket, TicketEvento

pytestmark = pytest.mark.django_db

PATRON_CLAVE = re.compile(r"Contraseña de las cuentas nuevas o restablecidas: (\S+)")


def _cargar(capsys, *extra):
    call_command("cargar_datos_demo", "--con-cuentas", *extra)
    salida = capsys.readouterr().out
    encontrada = PATRON_CLAVE.search(salida)
    return salida, encontrada.group(1) if encontrada else None


def test_crea_maestros_publicados_clientes_y_tickets_idempotente(capsys):
    salida, clave = _cargar(capsys)
    assert "Maestros de demostración nuevos: 10. Tickets de demostración nuevos: 4." in salida
    assert clave is not None

    maestros = list(PerfilMaestro.objects.select_related("usuario"))
    assert len(maestros) == len(cuentas_demo.MAESTROS)
    for perfil in maestros:
        assert perfil.usuario.nombre.endswith("(demo)")
        assert Expediente.objects.get(perfil_maestro=perfil).estado == EstadoExpediente.APROBADO
        assert publicacion.maestro_publicado(perfil.pk)
        visibles = publicacion.servicios_visibles(perfil.pk)
        assert visibles and not any(s.servicio.oficio.regulado for s in visibles)
        # Solo el maestro con ingreso tiene contraseña usable.
        assert perfil.usuario.has_usable_password() == (perfil.usuario.correo == cuentas_demo.CORREO_MAESTRO)
    assert {u.correo for u in Usuario.objects.filter(correo__isnull=False)} == {
        cuentas_demo.CORREO_MAESTRO, *[c[0] for c in cuentas_demo.CLIENTES],
        *[c[1] for c in cuentas_demo.ADMINISTRATIVAS],
    }
    estados = sorted(Ticket.objects.values_list("estado", flat=True))
    assert estados == sorted([EstadoTicket.PENDIENTE, EstadoTicket.ACEPTADO, EstadoTicket.FINALIZADO,
                              EstadoTicket.CERRADO])
    assert TicketEvento.objects.filter(ticket_id__in=Ticket.objects.values("pk")).count() == 4 + 1 + 2 + 1

    # Segunda vez: nada nuevo y nadie cambia de contraseña.
    antes = sorted(ServicioMaestro.objects.values_list("pk", "monto"))
    salida, otra = _cargar(capsys)
    assert "Maestros de demostración nuevos: 0. Tickets de demostración nuevos: 0." in salida
    assert otra is None and "Conservan la contraseña que tenían" in salida
    assert sorted(ServicioMaestro.objects.values_list("pk", "monto")) == antes
    assert Ticket.objects.count() == 4
    assert Usuario.objects.get(correo="cliente.demo.1@example.com").check_password(clave)


def test_la_contrasena_es_aleatoria_cumple_la_politica_y_solo_se_imprime(capsys, caplog):
    claves = {cuentas_demo.contrasena_aleatoria() for _ in range(20)}
    assert len(claves) == 20 and all(len(c) == 19 for c in claves)
    _, clave = _cargar(capsys)
    assert clave not in caplog.text
    _, restablecida = _cargar(capsys, "--restablecer-contrasenas")
    assert restablecida is not None and restablecida != clave
    for correo in ("cliente.demo.1@example.com", "cliente.demo.2@example.com", cuentas_demo.CORREO_MAESTRO,
                   *[c[1] for c in cuentas_demo.ADMINISTRATIVAS]):
        usuario = Usuario.objects.get(correo=correo)
        assert usuario.check_password(restablecida) and not usuario.check_password(clave)


def test_restablecer_exige_con_cuentas():
    with pytest.raises(CommandError, match="--con-cuentas"):
        call_command("cargar_datos_demo", "--restablecer-contrasenas")


def test_las_cuentas_pueden_ingresar_por_la_api(capsys):
    _, clave = _cargar(capsys)
    rut = cuentas_demo.rut_demo(cuentas_demo.MAESTRO_CON_INGRESO)
    for identificador in ("cliente.demo.1@example.com", "cliente.demo.2@example.com", rut, cuentas_demo.CORREO_MAESTRO):
        respuesta = iniciar_sesion(Client(enforce_csrf_checks=False), identificador, clave)
        assert respuesta.status_code == 200, identificador


def test_los_maestros_demo_aparecen_en_la_busqueda_por_oficio_y_comuna(capsys):
    _cargar(capsys)
    cliente = Client()
    for comuna in (8101, 13101):
        servicios = ServicioMaestro.objects.filter(maestro__coberturas__comuna_id=comuna).select_related(
            "servicio__oficio"
        )
        oficio = servicios.first().servicio.oficio.codigo
        respuesta = cliente.get("/api/busqueda", {"oficio": oficio, "comuna": comuna})
        assert respuesta.status_code == 200 and respuesta.json()["total"] >= 1, (oficio, comuna)


def test_los_rut_demo_no_chocan_con_el_volumen_de_prueba():
    from busqueda.management.commands.generar_volumen_prueba import RUT_BASE

    cuerpos = [int(cuentas_demo.rut_demo(n).split("-")[0]) for n in range(len(cuentas_demo.MAESTROS))]
    assert max(cuerpos) < RUT_BASE


def test_limpieza_lista_por_defecto_y_borra_solo_oficios_de_prueba_desactivados(capsys):
    basura = Oficio.objects.create(codigo="oficio_prueba_s3_chromium_123", nombre="Oficio Prueba S3 x",
                                   activo=False, regulado=False, orden=900)
    servicio = Servicio.objects.create(oficio=basura, nombre="Servicio x", orden=1)
    ServicioModalidad.objects.create(servicio=servicio, modalidad="por_trabajo", precio_referencia=1000)
    activo = Oficio.objects.create(codigo="oficio_qa3_999", nombre="Oficio QA3 activo", activo=True, regulado=False, orden=901)
    parecido = Oficio.objects.create(codigo="oficio_qa3_999_real", nombre="Otro", activo=False, regulado=False, orden=902)

    call_command("limpiar_oficios_de_prueba")
    assert "No se borró nada" in capsys.readouterr().out
    assert Oficio.objects.filter(pk=basura.pk).exists()

    call_command("limpiar_oficios_de_prueba", "--confirmo")
    assert "borrados: 1" in capsys.readouterr().out
    assert not Oficio.objects.filter(pk=basura.pk).exists()
    assert Oficio.objects.filter(pk__in=[activo.pk, parecido.pk]).count() == 2

    call_command("limpiar_oficios_de_prueba", "--confirmo")
    assert "No hay oficios de prueba" in capsys.readouterr().out


# --- Enmienda E-1: cuentas administrativas demo ---


def test_crea_una_cuenta_administrativa_por_rol_con_la_misma_contrasena(capsys):
    from identidad.models import ROLES_ADMINISTRATIVOS, UsuarioRol

    salida, clave = _cargar(capsys)
    assert {rol for rol, _, _ in cuentas_demo.ADMINISTRATIVAS} == set(ROLES_ADMINISTRATIVOS)
    for rol, correo, _ in cuentas_demo.ADMINISTRATIVAS:
        usuario = Usuario.objects.get(correo=correo)
        assert correo.endswith("@example.com") and correo in salida
        assert set(UsuarioRol.objects.filter(usuario=usuario).values_list("rol", flat=True)) == {rol}
        assert usuario.check_password(clave)
        assert iniciar_sesion(Client(enforce_csrf_checks=False), correo, clave).status_code == 200
    # Idempotente: no se duplican ni cambian de contraseña.
    _cargar(capsys)
    assert Usuario.objects.filter(correo__in=[c[1] for c in cuentas_demo.ADMINISTRATIVAS]).count() == len(
        cuentas_demo.ADMINISTRATIVAS
    )
    assert all(Usuario.objects.get(correo=c[1]).check_password(clave) for c in cuentas_demo.ADMINISTRATIVAS)
