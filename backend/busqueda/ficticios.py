"""Piezas compartidas para crear datos **FICTICIOS** de maestros, clientes y tickets.

Las usan ``generar_volumen_prueba`` (RNF-01, RNF-03; pila aparte) y
``cargar_datos_demo --con-cuentas`` (ADR-028; pila de demostración). Aquí
están las reglas que ambos deben respetar una sola vez:

- RUT sintético con dígito verificador válido (módulo 11);
- foto sintética procesada con ``perfil.fotos`` (sin EXIF, ADR-015/ADR-019);
- solo servicios de oficios **no regulados** (los regulados exigen licencia
  vigente con archivo cifrado, que no se fabrica);
- maestro publicado = expediente aprobado + comuna base + foto (ADR-019);
- tickets con ``vence_en`` de ADR-023 y su historial en ``ticket_evento``.

Ninguna función escribe la bitácora (ADR-010): son cargas de consola, no
acciones de una persona en la aplicación.
"""
import datetime
import io
import secrets

from django.db import transaction
from django.utils import timezone
from PIL import Image

from catalogo.models import Servicio, ServicioModalidad
from expediente.models import EstadoExpediente, Expediente, OficioMaestro
from identidad import servicios as identidad
from perfil import fotos
from perfil.models import Cobertura, Disponibilidad, PerfilPublico, ServicioMaestro
from tickets.models import AutorTipo, Ticket, TicketEvento
from tickets.servicios import calcular_vence_en


def rut_con_dv(cuerpo):
    """RUT sin puntos ``cuerpo-DV`` con el dígito verificador correcto."""
    suma, factor = 0, 2
    for digito in reversed(str(cuerpo)):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    dv = 11 - suma % 11
    return f"{cuerpo}-{'0' if dv == 11 else 'K' if dv == 10 else dv}"


def foto_sintetica(azar):
    """Variantes de una foto JPEG de un solo color (no es una persona)."""
    salida = io.BytesIO()
    color = tuple(azar.randint(40, 220) for _ in range(3))
    Image.new("RGB", (320, 320), color).save(salida, format="JPEG", quality=80)
    return fotos.variantes(salida.getvalue())


def servicios_por_oficio():
    """``{oficio: [Servicio]}`` de los oficios **no regulados** activos con servicios activos y modalidades."""
    por_oficio = {}
    for servicio in Servicio.objects.filter(activo=True, oficio__activo=True, oficio__regulado=False).select_related(
        "oficio"
    ).order_by("oficio__orden", "orden", "pk"):
        if ServicioModalidad.objects.filter(servicio=servicio).exists():
            por_oficio.setdefault(servicio.oficio, []).append(servicio)
    return por_oficio


def crear_maestro_publicado(*, nombre, telefono, rut, servicios, montos, base, extra, agenda, foto, motivo,
                            correo=identidad.AUSENTE, contrasena=None):
    """Crea un maestro ficticio publicado en una transacción y devuelve su ``Usuario``.

    ``servicios`` son ``Servicio`` de oficios no regulados (se rechaza otro caso);
    ``montos`` el monto de cada uno; ``base`` la comuna base y ``extra`` las demás
    de cobertura; ``agenda`` una lista de ``(dia_semana, inicio_min, fin_min)``;
    ``foto`` las variantes de ``foto_sintetica``.
    Sin ``contrasena`` la cuenta queda con contraseña inutilizable.
    """
    if any(s.oficio.regulado for s in servicios):
        raise ValueError("Los datos ficticios no publican servicios de oficios regulados.")
    nombre_foto = fotos.guardar(foto)
    try:
        with transaction.atomic():
            usuario = identidad.crear_cuenta_maestro(
                nombre=nombre, telefono=telefono, rut=rut, correo=correo,
                contrasena=contrasena or secrets.token_urlsafe(24),
            )
            if contrasena is None:
                usuario.set_unusable_password()
                usuario.save(update_fields=["password"])
            OficioMaestro.objects.bulk_create(
                [OficioMaestro(maestro_id=usuario.pk, oficio=o) for o in {s.oficio for s in servicios}]
            )
            ServicioMaestro.objects.bulk_create(
                [
                    ServicioMaestro(
                        maestro_id=usuario.pk,
                        servicio=s,
                        modalidad=ServicioModalidad.objects.filter(servicio=s).order_by("modalidad").first().modalidad,
                        monto=monto,
                    )
                    for s, monto in zip(servicios, montos, strict=True)
                ]
            )
            Cobertura.objects.bulk_create(
                [Cobertura(maestro_id=usuario.pk, comuna_id=base, es_base=True)]
                + [Cobertura(maestro_id=usuario.pk, comuna_id=c, es_base=False) for c in extra if c != base]
            )
            Disponibilidad.objects.bulk_create(
                [Disponibilidad(maestro_id=usuario.pk, dia_semana=d, inicio_min=i, fin_min=f) for d, i, f in agenda]
            )
            PerfilPublico.objects.filter(perfil_maestro_id=usuario.pk).update(
                foto=nombre_foto, foto_actualizada_en=timezone.now()
            )
            Expediente.objects.filter(perfil_maestro_id=usuario.pk).update(
                estado=EstadoExpediente.APROBADO, estado_motivo=motivo, estado_cambiado_en=timezone.now()
            )
    except BaseException:
        fotos.borrar(nombre_foto)
        raise
    return usuario


def evento(ticket, fecha, anterior, nuevo, autor_id=None, motivo=None):
    """Fila de ``ticket_evento``; sin autor es el actor Sistema."""
    return TicketEvento(
        ticket_id=ticket.pk,
        fecha=fecha,
        estado_anterior=anterior,
        estado_nuevo=nuevo,
        motivo=motivo,
        autor_tipo=AutorTipo.SISTEMA if autor_id is None else AutorTipo.USUARIO,
        autor_id=autor_id,
    )


def entre(azar, desde, hasta):
    """Instante al azar en ``[desde, hasta)``, con segundos enteros."""
    segundos = max(1, int((hasta - desde).total_seconds()))
    return desde + datetime.timedelta(seconds=azar.randrange(segundos))


def ticket(*, perfil, cliente, servicio, comuna, una, estado, enviado_en, direccion, descripcion, materiales):
    """``Ticket`` sin guardar con la copia de modalidad y monto publicados y ``vence_en`` de ADR-023."""
    return Ticket(
        cliente_id=cliente.pk,
        perfil_maestro_id=perfil.pk,
        servicio_maestro=servicio,
        modalidad=servicio.modalidad,
        monto_publicado=servicio.monto,
        fecha=una.fecha,
        inicio_min=una.inicio_min,
        fin_min=una.fin_min,
        inicio_en=una.inicio_en,
        fin_en=una.fin_en,
        comuna_id=comuna,
        direccion=direccion,
        descripcion=descripcion,
        materiales=materiales,
        estado=estado,
        enviado_en=enviado_en,
        vence_en=calcular_vence_en(enviado_en, una.inicio_en),
    )
