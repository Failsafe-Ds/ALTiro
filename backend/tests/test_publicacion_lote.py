"""ADR-019, Enmienda E-1: la regla pura con contexto en lote equivale al envoltorio uno a uno.

Escenario generado (``tests/busqueda_ayudas.escenario_aleatorio``): estados del
expediente, comuna base, foto, licencias vencidas u observadas, servicios
retirados y oficios no declarados. Además, modalidad no admitida y catálogo inactivo.
"""
import pytest
import time_machine

from catalogo.models import ServicioModalidad
from expediente.models import OficioMaestro
from perfil import publicacion
from perfil.models import ServicioMaestro
from tests import busqueda_ayudas as ay

pytestmark = pytest.mark.django_db


@pytest.fixture
def reloj():
    with time_machine.travel(ay.AHORA, tick=False):
        yield


@pytest.mark.regla("F-12")
def test_lote_y_uno_a_uno_dan_los_mismos_motivos(reloj):
    catalogo = ay.catalogo_basico()
    ay.escenario_aleatorio(catalogo)
    # Modalidad que el catálogo deja de admitir y servicio de catálogo inactivo.
    ServicioModalidad.objects.filter(servicio=catalogo["gasfiteria"]).update(modalidad="por_hora")
    catalogo["electricidad"].activo = False
    catalogo["electricidad"].save()
    # Y un maestro que deja de declarar sus oficios (servicio activo, oficio no declarado).
    activo = ServicioMaestro.objects.filter(retirado_en__isnull=True).order_by("pk").first()
    OficioMaestro.objects.filter(maestro_id=activo.maestro_id).delete()

    servicios = list(ServicioMaestro.objects.select_related("servicio__oficio").order_by("pk"))
    contextos = publicacion.contextos_en_lote({s.maestro_id for s in servicios})
    vistos = set()
    for servicio in servicios:
        uno = publicacion.motivos_no_visible(servicio, ay.HOY)
        lote = publicacion.motivos_no_visible_de(servicio, contextos[servicio.maestro_id], ay.HOY)
        assert uno == lote, servicio.pk
        vistos.update(uno or ["visible"])
    # El escenario ejercita todos los motivos y también servicios visibles.
    assert vistos == set(publicacion.MOTIVOS) | {"visible"}


def test_contextos_en_lote_usa_consultas_constantes(reloj, django_assert_max_num_queries):
    catalogo = ay.catalogo_basico()
    maestros = ay.escenario_aleatorio(catalogo, cantidad=12)
    with django_assert_max_num_queries(6):
        publicacion.contextos_en_lote([m.pk for m in maestros])


def test_elegibilidad_pura_coincide_con_la_del_maestro(reloj):
    catalogo = ay.catalogo_basico()
    maestros = ay.escenario_aleatorio(catalogo, cantidad=12)
    contextos = publicacion.contextos_en_lote([m.pk for m in maestros])
    for usuario in maestros:
        assert contextos[usuario.pk].elegible is publicacion.maestro_elegible(usuario.pk)
