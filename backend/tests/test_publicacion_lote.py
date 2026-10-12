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


def test_el_camino_de_a_uno_usa_el_mismo_contexto_que_el_lote(reloj, monkeypatch):
    """Auditoría ponytail 2, hallazgo 7: un solo camino arma el ``Contexto``.

    Si alguien vuelve a armar el contexto de a uno por otra vía, esta prueba
    falla aunque hoy den lo mismo; ``test_lote_y_uno_a_uno_dan_los_mismos_motivos``
    compara los resultados.
    """
    catalogo = ay.catalogo_basico()
    ay.escenario_aleatorio(catalogo)
    servicio = ServicioMaestro.objects.select_related("servicio__oficio").order_by("pk").first()
    original = publicacion.contextos_en_lote
    llamadas = []

    def espia(maestro_ids, servicio_ids=None):
        llamadas.append((list(maestro_ids), servicio_ids))
        return original(maestro_ids, servicio_ids)

    monkeypatch.setattr(publicacion, "contextos_en_lote", espia)
    lote = original([servicio.maestro_id])[servicio.maestro_id]

    assert publicacion.motivos_no_visible(servicio, ay.HOY) == publicacion.motivos_no_visible_de(servicio, lote, ay.HOY)
    assert llamadas == [([servicio.maestro_id], {servicio.servicio_id})]
    # El ``elegible`` ya calculado reemplaza al del lote, sin tocar lo demás.
    con_elegible = publicacion.motivos_no_visible(servicio, ay.HOY, elegible=False)
    assert publicacion.MAESTRO_NO_ELEGIBLE in con_elegible


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
