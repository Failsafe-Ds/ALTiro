"""Verificación de credenciales (RF-02; ADR-013, puntos 1 y 4, Enmienda E-5).

Un único campo ``identificador``: con "@" es correo; sin "@" es RUT. El
teléfono nunca es identificador.
"""
from django.contrib.auth.hashers import make_password

from identidad.errores import ErrorValidacion
from identidad.models import PerfilMaestro, Usuario
from identidad.validadores import CONTRASENA_LARGO_MAXIMO, normalizar_correo, normalizar_rut


def interpretar_identificador(valor):
    """Devuelve ``(tipo, valor_normalizado)`` o lanza ``ErrorValidacion`` en ``identificador``."""
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorValidacion("identificador", "Ingresa tu correo o tu RUT.")
    if "@" in valor:
        try:
            return "correo", normalizar_correo(valor)
        except ErrorValidacion:
            raise ErrorValidacion(
                "identificador", "El correo no es válido. Revísalo, por ejemplo nombre@dominio.cl."
            ) from None
    try:
        return "rut", normalizar_rut(valor)
    except ErrorValidacion:
        raise ErrorValidacion(
            "identificador",
            "Revisa tu RUT y su dígito verificador, por ejemplo 12.345.678-5. Si usas correo, escríbelo completo.",
        ) from None


def validar_contrasena_ingreso(valor):
    """Límite estructural del inicio de sesión (E-5), revisado antes de calcular el hash."""
    if not isinstance(valor, str) or valor == "":
        raise ErrorValidacion("contrasena", "Ingresa tu contraseña.")
    if len(valor) > CONTRASENA_LARGO_MAXIMO:
        raise ErrorValidacion(
            "contrasena",
            f"La contraseña tiene más de {CONTRASENA_LARGO_MAXIMO} caracteres. Revisa que esté bien escrita.",
        )
    try:
        valor.encode("utf-8")
    except UnicodeEncodeError:
        raise ErrorValidacion(
            "contrasena", "La contraseña tiene caracteres que no se pueden usar. Escríbela de nuevo."
        ) from None


def autenticar(tipo, valor, contrasena):
    """Devuelve el usuario si las credenciales son correctas; si no, ``None``.

    Si el identificador no existe se calcula igual un hash (señuelo), para que
    el tiempo de respuesta no revele si la cuenta existe (propuesta del S1, §6).
    """
    if tipo == "correo":
        usuario = Usuario.objects.filter(correo=valor).first()
    else:
        perfil = PerfilMaestro.objects.select_related("usuario").filter(rut=valor).first()
        usuario = perfil.usuario if perfil else None
    if usuario is None:
        make_password(contrasena)
        return None
    return usuario if usuario.check_password(contrasena) else None
