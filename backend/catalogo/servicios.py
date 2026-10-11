"""Casos de uso de comercial sobre el catálogo (RF-36, RF-37, HU-20, CA-20.1, CA-20.2; ADR-018).

- ``crear_oficio`` y ``modificar_oficio``: ``regulado`` es obligatorio al crear
  e inmutable después (ADR-018, punto 2).
- ``crear_servicio`` y ``modificar_servicio``: nombre, estado y modalidades
  con precio de referencia (ADR-018, punto 1). Todo servicio tiene al menos
  una modalidad.

Reglas comunes (ADR-018, punto 4):

- Modificar (incluida la baja, ``activo=false``) exige ``version`` y un motivo
  escrito. Si la versión no coincide con la guardada: ``ErrorVersion`` (409).
- Crear registra un motivo fijo que se puede completar.
- Sin borrado físico de oficios ni servicios.
- La entrada de la bitácora va en la misma transacción que el cambio: si una
  falla, no queda ninguno de los dos. Los valores guardados son solo campos del
  catálogo (sin datos personales).

Errores: ``ErroresDeCampo`` (400 por campo), ``ErrorSolicitud`` (400 general)
o ``ErrorVersion`` (409), siempre sin cambios ni bitácora.
"""
import re
import unicodedata

from django.db import IntegrityError, transaction
from django.db.models import Max

from bitacora import servicios as bitacora
from catalogo.errores import ErrorVersion
from catalogo.models import MONTO_MAXIMO, Modalidad, Oficio, Servicio, ServicioModalidad
from comun.api import ErrorSolicitud, ErroresDeCampo
from comun.texto import FALTA, INVALIDO, LARGO, limpiar_texto

NOMBRE_LARGO_MAXIMO = 100
MOTIVO_LARGO_MAXIMO = 1000
ORDEN_MAXIMO = 32767

MOTIVO_ALTA_OFICIO = "Alta del oficio en el catálogo"
MOTIVO_ALTA_SERVICIO = "Alta del servicio en el catálogo"

MENSAJE_NOMBRE_FALTA = "Escribe el nombre."
MENSAJE_NOMBRE_LARGO = f"El nombre puede tener hasta {NOMBRE_LARGO_MAXIMO} caracteres. Acórtalo."
MENSAJE_NOMBRE_INVALIDO = "El nombre tiene caracteres que no se pueden usar. Escríbelo de nuevo."
MENSAJE_OFICIO_REPETIDO = "Ya existe un oficio con ese nombre. Usa otro nombre o edita el que existe."
MENSAJE_SERVICIO_REPETIDO = (
    "Este oficio ya tiene un servicio con ese nombre. Usa otro nombre o edita el que existe."
)
MENSAJE_REGULADO_FALTA = "Indica si el oficio necesita licencia SEC para ofrecerse (sí o no)."
MENSAJE_REGULADO_INMUTABLE = (
    "Si un oficio necesita licencia SEC no se cambia desde aquí. Quita este dato e inténtalo de nuevo; "
    "para cambiarlo, pídelo al equipo de desarrollo."
)
MENSAJE_ORDEN = f"Escribe la posición en la lista con un número entero entre 1 y {ORDEN_MAXIMO}."
MENSAJE_ACTIVO = "Indica si queda disponible (sí o no)."
MENSAJE_MODALIDADES = (
    "Indica al menos una forma de cobro, por trabajo o por hora, sin repetirla y con su precio de "
    "referencia en pesos: un número entero mayor que cero y hasta 10.000.000."
)
MENSAJE_OFICIO_NO_EXISTE = "Elige un oficio de la lista."
MENSAJE_OFICIO_INMUTABLE = (
    "El oficio de un servicio no se cambia. Da de baja este servicio y créalo en el otro oficio."
)
MENSAJE_MOTIVO_FALTA = "Escribe el motivo del cambio. Es obligatorio y queda registrado."
MENSAJE_MOTIVO_LARGO = f"El motivo puede tener hasta {MOTIVO_LARGO_MAXIMO} caracteres. Acórtalo e inténtalo de nuevo."
MENSAJE_MOTIVO_INVALIDO = "El motivo tiene caracteres que no se pueden usar. Escríbelo de nuevo."
MENSAJE_RECARGA = "Vuelve a cargar la página e inténtalo de nuevo."
MENSAJE_VERSION = (
    "Otra persona cambió este dato mientras lo editabas. Vuelve a cargar la página, revisa los cambios e inténtalo de nuevo."
)
MENSAJE_SIN_CAMBIOS = "No cambiaste ningún dato. Modifica algo o cancela."

_CAMPOS_EDITABLES_OFICIO = ("nombre", "orden", "activo")
_CAMPOS_EDITABLES_SERVICIO = ("nombre", "orden", "activo", "modalidades")


# --- Lectura y validación de campos ---


def _es_entero(valor):
    return isinstance(valor, int) and not isinstance(valor, bool)


def _nombre(datos, errores, obligatorio):
    if "nombre" not in datos:
        if obligatorio:
            errores["nombre"] = MENSAJE_NOMBRE_FALTA
        return None
    valor = datos["nombre"]
    if isinstance(valor, str):
        valor = " ".join(valor.split())  # también los espacios internos repetidos
    texto, problema = limpiar_texto(valor, NOMBRE_LARGO_MAXIMO, una_linea=True)
    if problema is None and any(unicodedata.category(c).startswith("C") for c in texto):
        problema = INVALIDO
    if problema:
        errores["nombre"] = {
            FALTA: MENSAJE_NOMBRE_FALTA, INVALIDO: MENSAJE_NOMBRE_INVALIDO, LARGO: MENSAJE_NOMBRE_LARGO,
        }[problema]
        return None
    return texto


def _entero(datos, campo, errores, mensaje, minimo, maximo):
    if campo not in datos:
        return None
    valor = datos[campo]
    if not _es_entero(valor) or not minimo <= valor <= maximo:
        errores[campo] = mensaje
        return None
    return valor


def _booleano(datos, campo, errores, mensaje, obligatorio=False):
    if campo not in datos:
        if obligatorio:
            errores[campo] = mensaje
        return None
    valor = datos[campo]
    if not isinstance(valor, bool):
        errores[campo] = mensaje
        return None
    return valor


def _version(datos, errores):
    valor = datos.get("version")
    if not _es_entero(valor) or valor < 1:
        errores["version"] = MENSAJE_RECARGA
        return None
    return valor


def _motivo(datos, errores, obligatorio):
    texto, problema = limpiar_texto(datos.get("motivo"), MOTIVO_LARGO_MAXIMO, obligatorio=obligatorio)
    if problema:
        errores["motivo"] = {
            FALTA: MENSAJE_MOTIVO_FALTA, INVALIDO: MENSAJE_MOTIVO_INVALIDO, LARGO: MENSAJE_MOTIVO_LARGO,
        }[problema]
        return None
    return texto


def _modalidades(datos, errores, obligatorio):
    """Lista ``[{"modalidad", "precio_referencia"}]`` -> ``{modalidad: precio}``; al menos una, sin repetir."""
    if "modalidades" not in datos:
        if obligatorio:
            errores["modalidades"] = MENSAJE_MODALIDADES
        return None
    valor = datos["modalidades"]
    resultado = {}
    if not isinstance(valor, list) or not 1 <= len(valor) <= len(Modalidad.values):
        errores["modalidades"] = MENSAJE_MODALIDADES
        return None
    for elemento in valor:
        if (
            not isinstance(elemento, dict)
            or set(elemento) != {"modalidad", "precio_referencia"}
            or elemento["modalidad"] not in Modalidad.values
            or elemento["modalidad"] in resultado
            or not _es_entero(elemento["precio_referencia"])
            or not 0 < elemento["precio_referencia"] <= MONTO_MAXIMO
        ):
            errores["modalidades"] = MENSAJE_MODALIDADES
            return None
        resultado[elemento["modalidad"]] = elemento["precio_referencia"]
    return resultado


def _con_motivo_fijo(fijo, complemento):
    return f"{fijo}. {complemento}" if complemento else fijo


# --- Valores para la bitácora: solo campos del catálogo ---


def valores_oficio(oficio):
    return {
        "codigo": oficio.codigo,
        "nombre": oficio.nombre,
        "regulado": oficio.regulado,
        "orden": oficio.orden,
        "activo": oficio.activo,
    }


def modalidades_de(servicio):
    return [
        {"modalidad": m.modalidad, "precio_referencia": m.precio_referencia}
        for m in ServicioModalidad.objects.filter(servicio=servicio).order_by("modalidad")
    ]


def valores_servicio(servicio):
    return {
        "oficio": servicio.oficio.codigo,
        "nombre": servicio.nombre,
        "orden": servicio.orden,
        "activo": servicio.activo,
        "modalidades": modalidades_de(servicio),
    }


# --- Oficios ---


def _codigo_desde(nombre):
    """Código interno estable derivado del nombre (``[a-z0-9_]``), único entre los oficios."""
    ascii_ = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "_", ascii_).strip("_")[:34] or "oficio"
    codigo, sufijo = base, 2
    while Oficio.objects.filter(codigo=codigo).exists():
        codigo, sufijo = f"{base}_{sufijo}", sufijo + 1
    return codigo


def _siguiente_orden(consulta):
    return min((consulta.aggregate(maximo=Max("orden"))["maximo"] or 0) + 1, ORDEN_MAXIMO)


def _oficio_repetido(nombre, excepto=None):
    consulta = Oficio.objects.filter(nombre__iexact=nombre)
    if excepto is not None:
        consulta = consulta.exclude(pk=excepto.pk)
    return consulta.exists()


def crear_oficio(usuario, datos):
    """Alta de un oficio (RF-36). ``datos``: ``nombre``, ``regulado`` (obligatorios), ``orden`` y ``motivo`` opcionales."""
    errores = {}
    nombre = _nombre(datos, errores, obligatorio=True)
    regulado = _booleano(datos, "regulado", errores, MENSAJE_REGULADO_FALTA, obligatorio=True)
    orden = _entero(datos, "orden", errores, MENSAJE_ORDEN, 1, ORDEN_MAXIMO)
    complemento = _motivo(datos, errores, obligatorio=False)
    if errores:
        raise ErroresDeCampo(errores)
    try:
        # Dos altas simultáneas con el mismo nombre derivan el mismo código: la
        # unicidad de ``codigo`` rechaza la segunda (409, sin cambios).
        with transaction.atomic():
            if _oficio_repetido(nombre):
                raise ErroresDeCampo({"nombre": MENSAJE_OFICIO_REPETIDO})
            oficio = Oficio.objects.create(
                codigo=_codigo_desde(nombre),
                nombre=nombre,
                regulado=regulado,
                orden=orden if orden is not None else _siguiente_orden(Oficio.objects.all()),
            )
            bitacora.registrar(
                autor=usuario,
                accion="catalogo.oficio.crear",
                entidad="oficio",
                entidad_ref=oficio.ref,
                valor_nuevo=valores_oficio(oficio),
                motivo=_con_motivo_fijo(MOTIVO_ALTA_OFICIO, complemento),
            )
    except IntegrityError:
        raise ErrorVersion(MENSAJE_VERSION) from None
    return oficio


def modificar_oficio(usuario, oficio, datos):
    """Modifica nombre, orden o ``activo`` (baja lógica) de un oficio. ``regulado`` no se cambia (ADR-018, punto 2)."""
    errores = {}
    if "regulado" in datos:
        errores["regulado"] = MENSAJE_REGULADO_INMUTABLE
    version = _version(datos, errores)
    motivo = _motivo(datos, errores, obligatorio=True)
    cambios = {
        "nombre": _nombre(datos, errores, obligatorio=False),
        "orden": _entero(datos, "orden", errores, MENSAJE_ORDEN, 1, ORDEN_MAXIMO),
        "activo": _booleano(datos, "activo", errores, MENSAJE_ACTIVO),
    }
    if errores:
        raise ErroresDeCampo(errores)
    if not any(campo in datos for campo in _CAMPOS_EDITABLES_OFICIO):
        raise ErrorSolicitud(MENSAJE_SIN_CAMBIOS)
    with transaction.atomic():
        oficio = Oficio.objects.select_for_update().get(pk=oficio.pk)
        if oficio.version != version:
            raise ErrorVersion(MENSAJE_VERSION)
        anterior = valores_oficio(oficio)
        for campo, valor in cambios.items():
            if valor is not None:
                setattr(oficio, campo, valor)
        if oficio.nombre != anterior["nombre"] and _oficio_repetido(oficio.nombre, excepto=oficio):
            raise ErroresDeCampo({"nombre": MENSAJE_OFICIO_REPETIDO})
        nuevo = valores_oficio(oficio)
        if nuevo == anterior:
            raise ErrorSolicitud(MENSAJE_SIN_CAMBIOS)
        oficio.version += 1
        oficio.save(update_fields=["nombre", "orden", "activo", "version"])
        bitacora.registrar(
            autor=usuario,
            accion="catalogo.oficio.modificar",
            entidad="oficio",
            entidad_ref=oficio.ref,
            valor_anterior=anterior,
            valor_nuevo=nuevo,
            motivo=motivo,
        )
    return oficio


# --- Servicios ---


def _servicio_repetido(oficio, nombre, excepto=None):
    consulta = Servicio.objects.filter(oficio=oficio, nombre__iexact=nombre)
    if excepto is not None:
        consulta = consulta.exclude(pk=excepto.pk)
    return consulta.exists()


def _oficio_por_codigo(datos, errores):
    codigo = datos.get("oficio")
    if not isinstance(codigo, str) or not re.fullmatch(r"[a-z0-9_]{1,40}", codigo):
        errores["oficio"] = MENSAJE_OFICIO_NO_EXISTE
        return None
    oficio = Oficio.objects.filter(codigo=codigo).first()
    if oficio is None:
        errores["oficio"] = MENSAJE_OFICIO_NO_EXISTE
    return oficio


def _guardar_modalidades(servicio, modalidades):
    """Deja en ``servicio_modalidad`` exactamente ``modalidades`` (``{modalidad: precio}``)."""
    ServicioModalidad.objects.filter(servicio=servicio).exclude(modalidad__in=list(modalidades)).delete()
    for modalidad, precio in modalidades.items():
        ServicioModalidad.objects.update_or_create(
            servicio=servicio, modalidad=modalidad, defaults={"precio_referencia": precio}
        )


def crear_servicio(usuario, datos):
    """Alta de un servicio del catálogo (RF-36, CA-20.1).

    ``datos``: ``oficio`` (código), ``nombre`` y ``modalidades`` obligatorios;
    ``orden`` y ``motivo`` opcionales. Queda activo y disponible para que los
    maestros lo declaren, sin cambios de código.
    """
    errores = {}
    oficio = _oficio_por_codigo(datos, errores)
    nombre = _nombre(datos, errores, obligatorio=True)
    modalidades = _modalidades(datos, errores, obligatorio=True)
    orden = _entero(datos, "orden", errores, MENSAJE_ORDEN, 1, ORDEN_MAXIMO)
    complemento = _motivo(datos, errores, obligatorio=False)
    if errores:
        raise ErroresDeCampo(errores)
    try:
        with transaction.atomic():
            # Serializa las altas de servicios del mismo oficio (nombre y orden).
            oficio = Oficio.objects.select_for_update().get(pk=oficio.pk)
            if _servicio_repetido(oficio, nombre):
                raise ErroresDeCampo({"nombre": MENSAJE_SERVICIO_REPETIDO})
            servicio = Servicio.objects.create(
                oficio=oficio,
                nombre=nombre,
                orden=orden if orden is not None else _siguiente_orden(Servicio.objects.filter(oficio=oficio)),
            )
            _guardar_modalidades(servicio, modalidades)
            bitacora.registrar(
                autor=usuario,
                accion="catalogo.servicio.crear",
                entidad="servicio",
                entidad_ref=servicio.ref,
                valor_nuevo=valores_servicio(servicio),
                motivo=_con_motivo_fijo(MOTIVO_ALTA_SERVICIO, complemento),
            )
    except IntegrityError:
        raise ErrorVersion(MENSAJE_VERSION) from None
    return servicio


def modificar_servicio(usuario, servicio, datos):
    """Modifica nombre, orden, ``activo`` (baja lógica) o modalidades y precios de referencia (CA-20.2).

    ``modalidades`` reemplaza el conjunto completo; siempre queda al menos una.
    El oficio del servicio no se cambia.
    """
    errores = {}
    if "oficio" in datos:
        errores["oficio"] = MENSAJE_OFICIO_INMUTABLE
    version = _version(datos, errores)
    motivo = _motivo(datos, errores, obligatorio=True)
    nombre = _nombre(datos, errores, obligatorio=False)
    orden = _entero(datos, "orden", errores, MENSAJE_ORDEN, 1, ORDEN_MAXIMO)
    activo = _booleano(datos, "activo", errores, MENSAJE_ACTIVO)
    modalidades = _modalidades(datos, errores, obligatorio=False)
    if errores:
        raise ErroresDeCampo(errores)
    if not any(campo in datos for campo in _CAMPOS_EDITABLES_SERVICIO):
        raise ErrorSolicitud(MENSAJE_SIN_CAMBIOS)
    with transaction.atomic():
        servicio = Servicio.objects.select_for_update().select_related("oficio").get(pk=servicio.pk)
        if servicio.version != version:
            raise ErrorVersion(MENSAJE_VERSION)
        anterior = valores_servicio(servicio)
        if nombre is not None:
            if nombre != servicio.nombre and _servicio_repetido(servicio.oficio, nombre, excepto=servicio):
                raise ErroresDeCampo({"nombre": MENSAJE_SERVICIO_REPETIDO})
            servicio.nombre = nombre
        if orden is not None:
            servicio.orden = orden
        if activo is not None:
            servicio.activo = activo
        if modalidades is not None:
            _guardar_modalidades(servicio, modalidades)
        nuevo = valores_servicio(servicio)
        if nuevo == anterior:
            raise ErrorSolicitud(MENSAJE_SIN_CAMBIOS)
        servicio.version += 1
        servicio.save(update_fields=["nombre", "orden", "activo", "version"])
        bitacora.registrar(
            autor=usuario,
            accion="catalogo.servicio.modificar",
            entidad="servicio",
            entidad_ref=servicio.ref,
            valor_anterior=anterior,
            valor_nuevo=nuevo,
            motivo=motivo,
        )
    return servicio
