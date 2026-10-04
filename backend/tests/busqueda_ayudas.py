"""Ayudas para las pruebas de búsqueda y de la regla en lote (S4, incrementos 1 y 2).

Datos ficticios: RUT sintéticos, @example.com, teléfono de prueba. La foto se
marca con un UUID sin archivo (la búsqueda no lee la imagen), salvo donde la
prueba necesita la foto real.
"""
import datetime
import random
import uuid

from django.utils import timezone

from catalogo.models import Modalidad, Oficio, Servicio, ServicioModalidad
from expediente.models import Documento, EstadoDocumento, EstadoExpediente, Expediente, OficioMaestro, TipoDocumento
from identidad import servicios as servicios_identidad
from perfil import agenda, ocurrencias
from perfil.models import Cobertura, Disponibilidad, PerfilPublico, ServicioMaestro
from tests.ayudas import CONTRASENA, TEL_A

T = Modalidad.POR_TRABAJO
URL = "/api/busqueda"
# Provincia de Concepción (CUT 81): Concepción, Coronel, Chiguayante, Hualpén.
CONCEPCION, CORONEL, CHIGUAYANTE, HUALPEN, TALCAHUANO = 8101, 8102, 8103, 8112, 8110
# Otra provincia (Arauco, 82) de la misma región del Biobío: Lebu.
LEBU = 8201
# Otra región (Metropolitana, 13): Santiago.
SANTIAGO = 13101
# Miércoles 7 de octubre de 2026, 08:00 en Santiago (horario de verano, -03).
AHORA = datetime.datetime(2026, 10, 7, 8, 0, tzinfo=ocurrencias.ZONA)
HOY = AHORA.date()


def rut(n):
    """RUT sintético válido con dígito verificador (sin puntos): 30.000.000 + n."""
    cuerpo = 30_000_000 + n
    suma, factor = 0, 2
    for digito in reversed(str(cuerpo)):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    dv = 11 - suma % 11
    return f"{cuerpo}-{'0' if dv == 11 else 'K' if dv == 10 else dv}"


def servicio_catalogo(oficio, nombre):
    servicio = Servicio.objects.create(oficio=Oficio.objects.get(codigo=oficio), nombre=nombre, orden=1)
    ServicioModalidad.objects.create(servicio=servicio, modalidad=T, precio_referencia=30000)
    return servicio


def catalogo_basico():
    return {
        "gas": servicio_catalogo("gas", "Instalación de cocina"),
        "electricidad": servicio_catalogo("electricidad", "Cambio de enchufe"),
        "pintura": servicio_catalogo("pintura", "Pintura de habitación"),
        "gasfiteria": servicio_catalogo("gasfiteria", "Cambio de llave"),
    }


def licencia(maestro_id, oficio, estado=EstadoDocumento.VALIDADO, vencimiento=None, cargado_en=None):
    return Documento.objects.create(
        expediente=Expediente.objects.get(perfil_maestro_id=maestro_id),
        tipo=TipoDocumento.LICENCIA_SEC,
        oficio=Oficio.objects.get(codigo=oficio),
        fecha_emision=datetime.date(2020, 1, 10),
        fecha_vencimiento=vencimiento,
        estado=estado,
        motivo_observacion="Foto borrosa" if estado == EstadoDocumento.OBSERVADO else "",
        archivo=uuid.uuid4(),
        cargado_en=cargado_en or timezone.now(),
    )


def maestro(
    n,
    catalogo,
    servicios=("pintura",),
    comunas=((CONCEPCION, True),),
    bloques=((3, "14:00", "18:00"),),
    estado=EstadoExpediente.APROBADO,
    foto=True,
    nombre=None,
):
    """Maestro ficticio número ``n``: expediente, oficios, servicios, cobertura, agenda y foto marcada."""
    usuario = servicios_identidad.crear_cuenta_maestro(
        nombre=nombre or f"Maestro Prueba {n:03d}", telefono=TEL_A, rut=rut(n), contrasena=CONTRASENA
    )
    oficios = {catalogo[s].oficio_id for s in servicios}
    OficioMaestro.objects.bulk_create([OficioMaestro(maestro_id=usuario.pk, oficio_id=o) for o in oficios])
    Expediente.objects.filter(perfil_maestro_id=usuario.pk).update(estado=estado)
    for oficio in {catalogo[s].oficio.codigo for s in servicios} & {"gas", "electricidad"}:
        licencia(usuario.pk, oficio, vencimiento=HOY + datetime.timedelta(days=300))
    ServicioMaestro.objects.bulk_create(
        [ServicioMaestro(maestro_id=usuario.pk, servicio=catalogo[s], modalidad=T, monto=20000 + n) for s in servicios]
    )
    Cobertura.objects.bulk_create(
        [Cobertura(maestro_id=usuario.pk, comuna_id=codigo, es_base=base) for codigo, base in comunas]
    )
    Disponibilidad.objects.bulk_create(
        [
            Disponibilidad(
                maestro_id=usuario.pk, dia_semana=dia,
                inicio_min=agenda.minutos_de_hora(inicio), fin_min=agenda.minutos_de_hora(fin),
            )
            for dia, inicio, fin in bloques
        ]
    )
    if foto:
        PerfilPublico.objects.filter(perfil_maestro_id=usuario.pk).update(
            foto=uuid.uuid4(), foto_actualizada_en=timezone.now()
        )
    return usuario


def ref(usuario):
    return str(PerfilPublico.objects.get(perfil_maestro_id=usuario.pk).ref)


def refs(respuesta, clave="resultados"):
    return [tarjeta["ref"] for tarjeta in respuesta.json()[clave]]


def escenario_aleatorio(catalogo, semilla=7, cantidad=24):
    """Maestros con combinaciones generadas de estado, base, foto, cobertura, servicios, licencias y agenda."""
    azar = random.Random(semilla)
    estados = [EstadoExpediente.APROBADO] * 4 + [EstadoExpediente.SUSPENDIDO, EstadoExpediente.OBSERVADO]
    comunas = [CONCEPCION, CORONEL, CHIGUAYANTE, HUALPEN, LEBU]
    creados = []
    for n in range(cantidad):
        elegidas = azar.sample(comunas, azar.randint(1, 3))
        con_base = azar.random() > 0.15
        servicios = azar.sample(["gas", "pintura", "gasfiteria", "electricidad"], azar.randint(1, 3))
        bloques = []
        for dia in azar.sample(range(1, 8), azar.randint(0, 3)):
            inicio = azar.choice(range(0, 44)) * 30
            fin = azar.choice(range(inicio // 30 + 1, 49)) * 30
            bloques.append((dia, agenda.formato_hora(inicio), agenda.formato_hora(fin)))
        usuario = maestro(
            100 + n, catalogo, servicios=servicios,
            comunas=[(c, con_base and i == 0) for i, c in enumerate(elegidas)],
            bloques=bloques, estado=azar.choice(estados), foto=azar.random() > 0.15,
        )
        # Licencias: a veces vencida u observada; a veces un servicio retirado u oficio no declarado.
        suerte = azar.random()
        if suerte < 0.2:
            Documento.objects.filter(expediente__perfil_maestro_id=usuario.pk).update(fecha_vencimiento=HOY)
        elif suerte < 0.3:
            Documento.objects.filter(expediente__perfil_maestro_id=usuario.pk).update(
                estado=EstadoDocumento.OBSERVADO, motivo_observacion="Ilegible"
            )
        elif suerte < 0.4:
            ServicioMaestro.objects.filter(maestro_id=usuario.pk).update(retirado_en=timezone.now())
        elif suerte < 0.5:
            OficioMaestro.objects.filter(maestro_id=usuario.pk).delete()
        creados.append(usuario)
    return creados
