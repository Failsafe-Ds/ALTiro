"""Piezas compartidas para crear datos **FICTICIOS** de maestros, clientes y tickets.

Las usan ``generar_volumen_prueba`` (RNF-01, RNF-03; pila aparte) y
``cargar_datos_demo --con-cuentas`` (ADR-028; pila de demostración). Aquí
están las reglas que ambos deben respetar una sola vez:

- RUT sintético con dígito verificador válido (módulo 11);
- foto sintética procesada con ``perfil.fotos`` (sin EXIF, ADR-015/ADR-019);
- servicios de oficios **no regulados**; los regulados solo con
  ``licencias=True``: la licencia SEC se carga con el servicio real
  (``expediente.servicios.cargar_documento``: recodificación y cifrado
  AES-256-GCM, ADR-015) a partir de una imagen sintética y queda validada y
  vigente (ADR-017, punto 4; ADR-028, Enmienda E-1);
- maestro publicado = expediente aprobado + comuna base + foto (ADR-019);
- tickets con ``vence_en`` de ADR-023 y su historial en ``ticket_evento``.

Ninguna función escribe la bitácora (ADR-010): son cargas de consola, no
acciones de una persona en la aplicación.
"""
import datetime
import io
import secrets

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from PIL import Image

from catalogo.models import Modalidad, Servicio, ServicioModalidad
from expediente import almacenamiento, vigencia
from expediente import servicios as expedientes
from expediente.models import Documento, EstadoDocumento, EstadoExpediente, Expediente, OficioMaestro, TipoDocumento
from identidad import servicios as identidad
from perfil import fotos
from perfil.models import Cobertura, Disponibilidad, PerfilPublico, ServicioMaestro
from tickets.models import AutorTipo, EstadoTicket, Ticket, TicketEvento
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


def servicios_por_oficio(incluir_regulados=False):
    """``{oficio: [Servicio]}`` de los oficios activos con servicios activos y modalidades.

    Por defecto solo oficios **no regulados**; con ``incluir_regulados`` también
    los regulados (quien publica sus servicios debe pedir ``licencias=True``).
    """
    filtro = {} if incluir_regulados else {"oficio__regulado": False}
    por_oficio = {}
    for servicio in Servicio.objects.filter(activo=True, oficio__activo=True, **filtro).select_related(
        "oficio"
    ).order_by("oficio__orden", "orden", "pk"):
        if ServicioModalidad.objects.filter(servicio=servicio).exists():
            por_oficio.setdefault(servicio.oficio, []).append(servicio)
    return por_oficio


def imagen_licencia_sintetica():
    """JPEG sintético de una "licencia" (rectángulos de color, sin texto ni datos de nadie)."""
    salida = io.BytesIO()
    imagen = Image.new("RGB", (480, 300), (235, 235, 225))
    imagen.paste((40, 90, 160), (0, 0, 480, 60))
    imagen.paste((200, 200, 190), (30, 100, 450, 260))
    imagen.save(salida, format="JPEG", quality=80)
    return salida.getvalue()


def _cargar_licencia_validada(usuario, oficio, archivos_escritos):
    """Licencia SEC vigente del ``oficio`` regulado: carga real (cifrada) y validación ficticia.

    La carga usa ``expediente.servicios.cargar_documento`` (validación de datos,
    recodificación y cifrado, ADR-015). La validación se marca directamente,
    sin revisor ni bitácora: no hubo una persona de curatoría (ADR-010), igual
    que el expediente ``aprobado`` de estos maestros. Vence en dos años, así no
    genera avisos de vencimiento (RF-35).
    """
    hoy = vigencia.hoy_negocio()
    expedientes.cargar_documento(
        usuario,
        {
            "tipo": TipoDocumento.LICENCIA_SEC,
            "oficio": oficio.codigo,
            "fecha_emision": (hoy - datetime.timedelta(days=365)).isoformat(),
            "fecha_vencimiento": (hoy + datetime.timedelta(days=730)).isoformat(),
        },
        {"archivo": SimpleUploadedFile("licencia.jpg", imagen_licencia_sintetica(), content_type="image/jpeg")},
    )
    documento = Documento.objects.get(
        expediente__perfil_maestro_id=usuario.pk, tipo=TipoDocumento.LICENCIA_SEC, oficio=oficio,
        estado=EstadoDocumento.EN_REVISION,
    )
    archivos_escritos.append(documento.archivo)
    Documento.objects.filter(pk=documento.pk).update(estado=EstadoDocumento.VALIDADO, revisado_en=timezone.now())


def _modalidad_de(servicio, pedida):
    """La modalidad ``pedida`` (o la primera) entre las que admite el catálogo para ``servicio``."""
    admitidas = list(
        ServicioModalidad.objects.filter(servicio=servicio).order_by("modalidad").values_list("modalidad", flat=True)
    )
    if pedida is None:
        return admitidas[0]
    if pedida not in admitidas:
        raise ValueError("La modalidad pedida no está admitida en el catálogo para ese servicio.")
    return pedida


def crear_maestro_publicado(*, nombre, telefono, rut, servicios, montos, base, extra, agenda, foto, motivo,
                            correo=identidad.AUSENTE, contrasena=None, modalidades=None, licencias=False):
    """Crea un maestro ficticio publicado en una transacción y devuelve su ``Usuario``.

    ``servicios`` son ``Servicio`` del catálogo; los de oficios regulados exigen
    ``licencias=True`` (si no, se rechaza), que carga una licencia SEC vigente por
    oficio regulado (``_cargar_licencia_validada``). ``montos`` el monto de cada
    uno y ``modalidades`` (opcional) la modalidad de cada uno, admitida en el
    catálogo (por defecto, la primera); ``base`` la comuna base y ``extra`` las
    demás de cobertura; ``agenda`` una lista de ``(dia_semana, inicio_min,
    fin_min)``; ``foto`` las variantes de ``foto_sintetica``.
    Sin ``contrasena`` la cuenta queda con contraseña inutilizable.
    """
    regulados = {s.oficio for s in servicios if s.oficio.regulado}
    if regulados and not licencias:
        raise ValueError("Los datos ficticios no publican servicios de oficios regulados sin licencia.")
    modalidades = modalidades or [None] * len(servicios)
    nombre_foto = fotos.guardar(foto)
    archivos_escritos = []
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
                        modalidad=_modalidad_de(s, modalidad),
                        monto=monto,
                    )
                    for s, monto, modalidad in zip(servicios, montos, modalidades, strict=True)
                ]
            )
            Cobertura.objects.bulk_create(
                [Cobertura(maestro_id=usuario.pk, comuna_id=base, es_base=True)]
                + [Cobertura(maestro_id=usuario.pk, comuna_id=c, es_base=False) for c in extra if c != base]
            )
            Disponibilidad.objects.bulk_create(
                [Disponibilidad(maestro_id=usuario.pk, dia_semana=d, inicio_min=i, fin_min=f) for d, i, f in agenda]
            )
            for oficio in sorted(regulados, key=lambda o: o.pk):
                _cargar_licencia_validada(usuario, oficio, archivos_escritos)
            PerfilPublico.objects.filter(perfil_maestro_id=usuario.pk).update(
                foto=nombre_foto, foto_actualizada_en=timezone.now()
            )
            Expediente.objects.filter(perfil_maestro_id=usuario.pk).update(
                estado=EstadoExpediente.APROBADO, estado_motivo=motivo, estado_cambiado_en=timezone.now()
            )
    except BaseException:
        fotos.borrar(nombre_foto)
        for archivo in archivos_escritos:
            almacenamiento.borrar(archivo)
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


def finalizar(ticket, perfil_id, aceptado_en, finalizado_en):
    """Deja ``ticket`` ``finalizado`` con datos coherentes con el CHECK de ADR-026, E-1.

    Precio final = monto publicado, registrado por el maestro; si es por hora,
    aceptado al finalizar. Devuelve los pasos de su historial (aceptar y finalizar)
    para ``evento``.
    """
    ticket.estado = EstadoTicket.FINALIZADO
    ticket.aceptado_en, ticket.finalizado_en = aceptado_en, finalizado_en
    ticket.monto_final, ticket.monto_final_en = ticket.monto_publicado, finalizado_en
    ticket.monto_final_autor_id = perfil_id
    if ticket.modalidad == Modalidad.POR_HORA:
        ticket.precio_aceptado_en = finalizado_en
    return [
        (aceptado_en, EstadoTicket.PENDIENTE, EstadoTicket.ACEPTADO, perfil_id, None),
        (finalizado_en, EstadoTicket.ACEPTADO, EstadoTicket.FINALIZADO, perfil_id, None),
    ]


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
