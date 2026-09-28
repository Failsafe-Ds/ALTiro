"""Ayudas para las pruebas de la API. Datos ficticios: @example.com, RUT sintéticos y +56 9 1000 000N."""
import json

from identidad import servicios

CONTRASENA = "clave de prueba segura"
COMUNA = "8101"  # Concepción (CUT 2018)
TEL_A = "+56 9 1000 0001"
TEL_B = "+56 9 1000 0002"

URL_CLIENTES = "/api/clientes"
URL_POSTULACIONES = "/api/maestros/postulaciones"
URL_SESION = "/api/sesion"
URL_CUENTA = "/api/cuenta"
URL_CSRF = "/api/sesion/csrf"

# RNF-15 / PI-270: texto de programador que nunca debe llegar a la persona.
TEXTO_PROHIBIDO = [
    "Traceback", "IntegrityError", "duplicate key", "violates", "unique constraint",
    "null value", "SQLSTATE", "23505", "ValidationError", "This field is required",
    "Enter a valid", "usuario_correo_unico", "perfil_maestro", "password",
]


def post_json(client, url, datos, **extra):
    return client.post(url, data=json.dumps(datos), content_type="application/json", **extra)


def datos_cliente(**cambios):
    datos = {
        "nombre": "Ana Prueba",
        "telefono": TEL_A,
        "correo": "ana.prueba@example.com",
        "contrasena": CONTRASENA,
        "comuna": COMUNA,
    }
    datos.update(cambios)
    return {k: v for k, v in datos.items() if v is not None}


def datos_maestro(**cambios):
    datos = {"rut": "11.111.111-1", "nombre": "Maestro Uno", "telefono": TEL_A, "contrasena": CONTRASENA}
    datos.update(cambios)
    return {k: v for k, v in datos.items() if v is not None}


def crear_cliente(correo="ana.prueba@example.com", telefono=TEL_A):
    return servicios.crear_cuenta_cliente(
        nombre="Ana Prueba", telefono=telefono, correo=correo, contrasena=CONTRASENA, comuna=COMUNA
    )


def crear_maestro(rut="11.111.111-1", correo=servicios.AUSENTE, telefono=TEL_A):
    return servicios.crear_cuenta_maestro(
        nombre="Maestro Uno", telefono=telefono, rut=rut, correo=correo, contrasena=CONTRASENA
    )


def iniciar_sesion(client, identificador, contrasena=CONTRASENA, **extra):
    return post_json(client, URL_SESION, {"identificador": identificador, "contrasena": contrasena}, **extra)


def sin_texto_prohibido(respuesta):
    texto = respuesta.content.decode("utf-8")
    return not [t for t in TEXTO_PROHIBIDO if t in texto]
