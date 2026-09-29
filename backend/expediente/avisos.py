"""Muestra de los avisos de RF-35 (ADR-016, punto 2; propuesta del S2, §3 y §4).

La tabla ``aviso`` no guarda texto ni datos personales: el mensaje se arma
aquí, al mostrarlo, en español y sin jerga (RNF-15, RNF-17). Se arma en el
servidor, y no en cada pantalla, para que la redacción y la regla de "mañana"
o "en N días" vivan en un solo lugar para el maestro y para curatoría.

Solo se muestran los avisos cuyo documento sigue en seguimiento
(``vigencia.en_seguimiento``): vigente, y actual o licencia que sigue contando
por ADR-017, E-1. Cuando el documento vence o deja de contar, el aviso deja de
mostrarse; la fila se conserva para que no se emita otra vez.
"""
from expediente import vigencia
from expediente.models import Aviso, EstadoDocumento, RolDestinatarioAviso, TipoAviso, TipoDocumento

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

NOMBRES_DOCUMENTO = {
    TipoDocumento.CEDULA_IDENTIDAD: "cédula de identidad",
    TipoDocumento.CERTIFICADO_ANTECEDENTES: "certificado de antecedentes",
    TipoDocumento.LICENCIA_SEC: "licencia SEC",
}
ARTICULOS = {
    TipoDocumento.CEDULA_IDENTIDAD: "La",
    TipoDocumento.CERTIFICADO_ANTECEDENTES: "El",
    TipoDocumento.LICENCIA_SEC: "La",
}


def _fecha_larga(fecha):
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


def _nombre_documento(documento):
    nombre = NOMBRES_DOCUMENTO[documento.tipo]
    if documento.oficio is not None:
        nombre += f" de {documento.oficio.nombre}"
    return nombre


def _cuando(dias):
    return "mañana" if dias == 1 else f"en {dias} días"


def mensaje(documento, hoy, para_maestro):
    """Texto del aviso ``documento_por_vencer``, armado al mostrarlo."""
    dias = vigencia.dias_restantes(documento.fecha_vencimiento, hoy)
    nombre = _nombre_documento(documento)
    fecha = _fecha_larga(documento.fecha_vencimiento)
    reemplazado = documento.estado == EstadoDocumento.REEMPLAZADO
    if para_maestro:
        texto = f"Tu {nombre} vence {_cuando(dias)}, el {fecha}."
        if reemplazado:
            return texto + " Ya subiste la nueva: falta que la revisen."
        return texto + " Sube el documento nuevo antes de esa fecha."
    texto = f"{ARTICULOS[documento.tipo]} {nombre} vence {_cuando(dias)}, el {fecha}."
    if reemplazado:
        return texto + " Hay una licencia nueva sin validar."
    return texto


def _datos(aviso, hoy, para_maestro):
    """Lista explícita: sin ids internos, archivos ni datos de contacto."""
    documento = aviso.documento
    return {
        "tipo": aviso.tipo,
        "documento": {
            "ref": str(documento.ref),
            "tipo": documento.tipo,
            "oficio": {"codigo": documento.oficio.codigo, "nombre": documento.oficio.nombre}
            if documento.oficio
            else None,
        },
        "fecha_vencimiento": documento.fecha_vencimiento.isoformat(),
        "dias_restantes": vigencia.dias_restantes(documento.fecha_vencimiento, hoy),
        "creado_en": aviso.creado_en.isoformat(),
        "mensaje": mensaje(documento, hoy, para_maestro),
    }


def _vigentes(consulta, hoy):
    avisos = [aviso for aviso in consulta if vigencia.en_seguimiento(aviso.documento, hoy)]
    return sorted(avisos, key=lambda a: (a.documento.fecha_vencimiento, a.creado_en, a.pk))


def del_maestro(usuario_id, hoy):
    """Avisos dirigidos a la cuenta ``usuario_id`` (el maestro dueño)."""
    consulta = Aviso.objects.filter(
        tipo=TipoAviso.DOCUMENTO_POR_VENCER, destinatario_id=usuario_id
    ).select_related("documento__expediente", "documento__oficio")
    return [_datos(aviso, hoy, para_maestro=True) for aviso in _vigentes(consulta, hoy)]


def de_curatoria(usuario, hoy):
    """Avisos del rol curatoría, sin los del expediente propio (conflicto de interés; ADR-011, E-2)."""
    consulta = (
        Aviso.objects.filter(tipo=TipoAviso.DOCUMENTO_POR_VENCER, destinatario_rol=RolDestinatarioAviso.CURATORIA)
        .exclude(documento__expediente__perfil_maestro_id=usuario.pk)
        .select_related("documento__expediente__perfil_maestro__usuario", "documento__oficio")
    )
    return [
        {
            **_datos(aviso, hoy, para_maestro=False),
            "expediente": {
                "ref": str(aviso.documento.expediente.ref),
                "nombre": aviso.documento.expediente.perfil_maestro.usuario.nombre,
            },
        }
        for aviso in _vigentes(consulta, hoy)
    ]
