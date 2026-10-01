"""``cargar_datos_demo --maestros-por-comuna`` (ADR-028, Enmienda E-1): maestros ficticios en cada comuna.

Se usa la región de Arica y Parinacota (15: 4 comunas) para que las pruebas sean rápidas.
"""
import pytest
from django.core.management import CommandError, call_command
from django.test import Client

from busqueda import cuentas_demo, maestros_por_comuna
from busqueda.management.commands.generar_volumen_prueba import RUT_BASE as RUT_BASE_VOLUMEN
from catalogo.models import Oficio
from evaluaciones.models import Evaluacion, ParteEvaluacion
from expediente import almacenamiento
from expediente.models import Documento, EstadoDocumento, TipoDocumento
from identidad.models import PerfilMaestro
from perfil import publicacion
from perfil.models import Cobertura, ServicioMaestro
from territorio.models import Comuna
from tickets.models import EstadoTicket, Ticket

pytestmark = pytest.mark.django_db

REGION = 15


@pytest.fixture(autouse=True)
def catalogo_demo():
    from catalogo.management.commands.cargar_datos_demo import cargar_datos_demo

    cargar_datos_demo()


def _comunas():
    return list(Comuna.objects.filter(provincia__region_id=REGION).values_list("codigo", flat=True))


def _demo_de_la_region():
    return list(
        PerfilMaestro.objects.select_related("usuario").filter(
            coberturas__es_base=True, coberturas__comuna__provincia__region_id=REGION
        )
    )


def test_garantiza_n_por_comuna_publicados_y_es_idempotente(capsys):
    call_command("cargar_datos_demo", "--maestros-por-comuna", "--region", str(REGION))
    salida = capsys.readouterr().out
    comunas = _comunas()
    assert f"{3 * len(comunas)} nuevos en {len(comunas)} comunas" in salida
    conteo = maestros_por_comuna.demo_publicados_por_comuna(comunas)
    assert all(conteo.get(c, 0) == 3 for c in comunas)
    for perfil in _demo_de_la_region():
        assert publicacion.maestro_publicado(perfil.pk)
        assert perfil.usuario.nombre.endswith("(datos de prueba)")
        assert perfil.usuario.correo is None
        assert not perfil.usuario.has_usable_password()

    call_command("cargar_datos_demo", "--maestros-por-comuna", "--region", str(REGION))
    assert f"0 nuevos en {len(comunas)} comunas" in capsys.readouterr().out
    assert len(_demo_de_la_region()) == 3 * len(comunas)


def test_cuenta_los_existentes_y_crea_solo_los_que_faltan():
    comunas = _comunas()[:2]
    primero = maestros_por_comuna.cargar_maestros_por_comuna(2, comunas=comunas)
    assert primero.maestros == 4 and primero.minimo == 2
    segundo = maestros_por_comuna.cargar_maestros_por_comuna(3, comunas=comunas)
    assert segundo.maestros == 2 and segundo.minimo == 3 and not segundo.faltantes


def test_variedad_oficios_cobertura_y_combinaciones_vacias():
    comunas = _comunas()
    maestros_por_comuna.cargar_maestros_por_comuna(3, comunas=comunas)
    oficios_por_comuna = {
        c: set(ServicioMaestro.objects.filter(maestro__coberturas__comuna_id=c, maestro__coberturas__es_base=True)
               .values_list("servicio__oficio__codigo", flat=True))
        for c in comunas
    }
    activos = set(Oficio.objects.filter(activo=True).values_list("codigo", flat=True))
    assert all(len(o) >= 2 for o in oficios_por_comuna.values())
    # Algunas combinaciones oficio + comuna quedan sin maestro con base allí (para ver las sugerencias).
    assert any(activos - o for o in oficios_por_comuna.values())
    # La cobertura extra es siempre de la misma provincia que la base.
    for perfil in _demo_de_la_region():
        base = Cobertura.objects.select_related("comuna").get(maestro=perfil, es_base=True).comuna
        otras = Cobertura.objects.filter(maestro=perfil, es_base=False).select_related("comuna")
        assert len(otras) <= 2 and all(o.comuna.provincia_id == base.provincia_id for o in otras)


def test_oficios_regulados_con_licencia_cifrada_vigente_y_visibles():
    maestros_por_comuna.cargar_maestros_por_comuna(3, comunas=_comunas())
    licencias = Documento.objects.filter(tipo=TipoDocumento.LICENCIA_SEC).select_related("expediente")
    assert licencias.exists()
    for licencia in licencias:
        assert licencia.estado == EstadoDocumento.VALIDADO and licencia.fecha_vencimiento is not None
        assert almacenamiento.leer(licencia.ref, almacenamiento.ANVERSO, licencia.archivo)  # cifrada y legible
    regulados = ServicioMaestro.objects.filter(servicio__oficio__regulado=True)
    assert regulados.exists()
    for servicio in regulados:
        assert publicacion.visible(servicio)


def test_tickets_y_evaluaciones_coherentes():
    maestros_por_comuna.cargar_maestros_por_comuna(3, comunas=_comunas())
    assert Ticket.objects.filter(estado=EstadoTicket.FINALIZADO).exists()
    for evaluacion in Evaluacion.objects.select_related("ticket"):
        assert evaluacion.ticket.estado == EstadoTicket.FINALIZADO
        assert evaluacion.parte == ParteEvaluacion.CLIENTE
        assert evaluacion.autor_id == evaluacion.ticket.cliente_id
        assert evaluacion.evaluado_id == evaluacion.ticket.perfil_maestro_id
    for ticket in Ticket.objects.filter(estado=EstadoTicket.ACEPTADO):
        assert ticket.comuna_id in Cobertura.objects.filter(maestro_id=ticket.perfil_maestro_id).values_list(
            "comuna_id", flat=True
        )
    for ticket in Ticket.objects.select_related("cliente__usuario"):
        assert not ticket.cliente.usuario.has_usable_password()


def test_la_busqueda_respeta_los_filtros_con_el_volumen():
    comunas = _comunas()
    maestros_por_comuna.cargar_maestros_por_comuna(3, comunas=comunas)
    cliente = Client()
    vacias = 0
    for oficio in Oficio.objects.filter(activo=True):
        for comuna in comunas:
            datos = cliente.get("/api/busqueda", {"oficio": oficio.codigo, "comuna": comuna}).json()
            con_cobertura = ServicioMaestro.objects.filter(
                servicio__oficio=oficio, maestro__coberturas__comuna_id=comuna
            ).values("maestro_id").distinct().count()
            assert datos["total"] == con_cobertura
            vacias += datos["total"] == 0
    assert vacias > 0


def test_rut_sin_choques_con_otras_cargas():
    comunas = Comuna.objects.order_by("codigo").values_list("codigo", flat=True)
    menor = maestros_por_comuna.cuerpo_rut(comunas.first(), 0)
    mayor = maestros_por_comuna.cuerpo_rut(comunas.last(), maestros_por_comuna.PUESTOS - 1)
    assert menor >= maestros_por_comuna.RUT_BASE
    assert mayor < cuentas_demo.RUT_BASE_DEMO < RUT_BASE_VOLUMEN


def test_opciones_invalidas():
    with pytest.raises(CommandError, match="--maestros-por-comuna"):
        call_command("cargar_datos_demo", "--region", "15")
    with pytest.raises(CommandError, match="entre 1 y"):
        call_command("cargar_datos_demo", "--maestros-por-comuna", "0")
    with pytest.raises(CommandError, match="región"):
        call_command("cargar_datos_demo", "--maestros-por-comuna", "--region", "99")
