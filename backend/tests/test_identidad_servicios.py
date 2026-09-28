"""Servicios de dominio de identidad e invariantes que cruzan tablas.

ADR-013, puntos 2, 5 a 9, y Enmiendas E-1, E-2, E-3, E-6 y E-7. No son pruebas
de endpoints: RF-01, RF-02 y RF-03 completos no existen todavía.
Datos ficticios: RUT sintéticos del plan, correos @example.com y teléfonos
+56 9 1000 000N.
"""
import threading

import pytest
from django.db import connection

from identidad import servicios
from identidad.errores import ErrorValidacion, InvarianteVioladaError
from identidad.models import PerfilCliente, PerfilMaestro, Rol, Usuario, UsuarioRol
from identidad.servicios import (
    AUSENTE,
    agregar_perfil_cliente,
    agregar_perfil_maestro,
    asignar_rol_administrativo,
    crear_cuenta_administrativa,
    crear_cuenta_cliente,
    crear_cuenta_maestro,
    verificar_invariantes,
)

# Datos ficticios: contraseña de prueba y comuna del catálogo CUT (Concepción).
CONTRASENA = "clave de prueba segura"
COMUNA = "8101"
TEL_A = "+56 9 1000 0001"
TEL_B = "+56 9 1000 0002"
TEL_A_CANONICO = "+56910000001"
TEL_B_CANONICO = "+56910000002"


@pytest.fixture(autouse=True)
def invariantes_al_final(request):
    """PI-130: al terminar cada prueba con BD, todas las cuentas cumplen ADR-013 §9."""
    yield
    if "django_db" not in {marca.name for marca in request.node.iter_markers()}:
        return
    for usuario in Usuario.objects.all():
        assert verificar_invariantes(usuario) == [], f"usuario {usuario.pk}"


def _roles(usuario):
    return set(UsuarioRol.objects.filter(usuario=usuario).values_list("rol", flat=True))


def _sin_cambios_de_identidad(total_usuarios):
    assert Usuario.objects.count() == total_usuarios


def _cliente(correo="ana.prueba@example.com", telefono=TEL_A):
    return crear_cuenta_cliente(
        nombre="Ana Prueba", telefono=telefono, correo=correo, contrasena=CONTRASENA, comuna=COMUNA
    )


def _maestro(rut="11.111.111-1", correo=AUSENTE, telefono=TEL_A):
    return crear_cuenta_maestro(
        nombre="Maestro Uno", telefono=telefono, rut=rut, correo=correo, contrasena=CONTRASENA
    )


def _admin(roles=(Rol.CURATORIA,), **campos):
    return crear_cuenta_administrativa(
        nombre="Admin Prueba",
        correo="admin@example.com",
        roles=list(roles),
        contrasena=CONTRASENA,
        **campos,
    )


def _fallar_al_asignar_rol(monkeypatch):
    def falla(usuario, rol):
        raise RuntimeError("fallo forzado")

    monkeypatch.setattr(servicios, "_asignar_rol", falla)


# --- Cuenta de cliente ---


@pytest.mark.django_db
def test_crear_cuenta_cliente_crea_perfil_y_rol_con_datos_normalizados():
    usuario = crear_cuenta_cliente(
        contrasena=CONTRASENA, comuna=COMUNA,
        nombre="  Ana Prueba ", telefono=TEL_A, correo="  Ana.Prueba@Example.COM  "
    )

    usuario.refresh_from_db()
    assert usuario.correo == "ana.prueba@example.com"  # PI-050
    assert usuario.telefono == TEL_A_CANONICO  # PI-061
    assert usuario.nombre == "Ana Prueba"
    assert _roles(usuario) == {Rol.CLIENTE}
    assert PerfilCliente.objects.filter(usuario=usuario).exists()
    assert not PerfilMaestro.objects.filter(usuario=usuario).exists()


@pytest.mark.django_db
def test_rnf05_la_contrasena_se_guarda_con_argon2id_y_no_en_claro():
    usuario = _cliente()

    usuario.refresh_from_db()
    assert "$argon2id$" in usuario.password  # PI-172, ADR-004
    assert "m=65536,t=3,p=1" in usuario.password
    assert CONTRASENA not in usuario.password
    assert usuario.check_password(CONTRASENA)


@pytest.mark.django_db
def test_pi171_misma_contrasena_produce_hashes_distintos():
    uno = _cliente(correo="uno@example.com")
    dos = _cliente(correo="dos@example.com", telefono=TEL_B)

    assert Usuario.objects.get(pk=uno.pk).password != Usuario.objects.get(pk=dos.pk).password


@pytest.mark.django_db
def test_la_cuenta_nueva_aplica_la_politica_de_contrasena():
    with pytest.raises(ErrorValidacion) as error:
        crear_cuenta_cliente(
            nombre="Ana Prueba", telefono=TEL_A, correo="ana@example.com", contrasena="corta", comuna=COMUNA
        )

    assert error.value.campo == "contrasena"
    _sin_cambios_de_identidad(0)


@pytest.mark.django_db
@pytest.mark.parametrize("comuna", [None, "", "99999", "abc", True])
def test_ca011_cuenta_cliente_exige_comuna_de_la_lista(comuna):
    with pytest.raises(ErrorValidacion) as error:
        crear_cuenta_cliente(
            nombre="Ana Prueba", telefono=TEL_A, correo="ana@example.com", contrasena=CONTRASENA, comuna=comuna
        )

    assert error.value.campo == "comuna"
    _sin_cambios_de_identidad(0)


@pytest.mark.django_db
def test_pi051_correo_repetido_sin_distinguir_mayusculas_se_rechaza():
    _cliente(correo="ana.prueba@example.com")

    with pytest.raises(ErrorValidacion) as error:
        _cliente(correo="Ana.Prueba@EXAMPLE.com", telefono=TEL_B)

    assert error.value.campo == "correo"
    assert Usuario.objects.filter(correo="ana.prueba@example.com").count() == 1
    _sin_cambios_de_identidad(1)


@pytest.mark.django_db
@pytest.mark.parametrize("correo", [None, "", "   "])
def test_cuenta_cliente_exige_correo(correo):
    with pytest.raises(ErrorValidacion) as error:
        _cliente(correo=correo)

    assert error.value.campo == "correo"
    _sin_cambios_de_identidad(0)


@pytest.mark.django_db
@pytest.mark.parametrize("telefono", [None, "", "12345"])
def test_cuenta_cliente_exige_telefono_valido(telefono):
    with pytest.raises(ErrorValidacion) as error:
        _cliente(telefono=telefono)

    assert error.value.campo == "telefono"
    _sin_cambios_de_identidad(0)


@pytest.mark.django_db
def test_pi060_mismo_telefono_en_otra_forma_crea_otra_cuenta_sin_unirlas():
    cliente_a = _cliente(correo="a@example.com", telefono=TEL_A)

    cliente_b = _cliente(correo="b@example.com", telefono="9 1000 0001")

    assert cliente_a.pk != cliente_b.pk
    cliente_a.refresh_from_db()
    cliente_b.refresh_from_db()
    assert cliente_a.correo == "a@example.com"
    assert cliente_a.telefono == cliente_b.telefono == TEL_A_CANONICO
    _sin_cambios_de_identidad(2)


# --- Cuenta de maestro ---


@pytest.mark.django_db
def test_crear_cuenta_maestro_sin_correo_guarda_rut_y_telefono_normalizados():
    usuario = _maestro(rut="10.000.013-k", telefono=TEL_B)

    usuario.refresh_from_db()
    assert usuario.correo is None
    assert usuario.telefono == TEL_B_CANONICO
    assert usuario.perfil_maestro.rut == "10000013K"
    assert _roles(usuario) == {Rol.MAESTRO}
    assert not PerfilCliente.objects.filter(usuario=usuario).exists()


@pytest.mark.django_db
def test_crear_cuenta_maestro_con_correo_opcional_lo_normaliza():
    usuario = _maestro(correo=" Mae1@Example.com ")

    usuario.refresh_from_db()
    assert usuario.correo == "mae1@example.com"


@pytest.mark.django_db
@pytest.mark.parametrize("correo", ["", "   ", None])
def test_pi028_correo_recibido_vacio_o_nulo_se_rechaza_y_nunca_queda_null(correo):
    # E-7: solo el correo ausente deja NULL; lo recibido se valida.
    with pytest.raises(ErrorValidacion) as error:
        _maestro(correo=correo)

    assert error.value.campo == "correo"
    _sin_cambios_de_identidad(0)


@pytest.mark.django_db
def test_rut_repetido_en_otra_forma_se_rechaza_ca_11_3():
    _maestro(rut="11.111.111-1")

    with pytest.raises(ErrorValidacion) as error:
        _maestro(rut="111111111", telefono=TEL_B)

    assert error.value.campo == "rut"
    _sin_cambios_de_identidad(1)


@pytest.mark.django_db
def test_rut_con_dv_invalido_no_crea_nada():
    with pytest.raises(ErrorValidacion) as error:
        _maestro(rut="11.111.111-2")

    assert error.value.campo == "rut"
    _sin_cambios_de_identidad(0)


@pytest.mark.django_db
@pytest.mark.parametrize("telefono", ["", "56 9 1000 0001"])
def test_cuenta_maestro_exige_telefono_valido(telefono):
    with pytest.raises(ErrorValidacion) as error:
        _maestro(telefono=telefono)

    assert error.value.campo == "telefono"
    _sin_cambios_de_identidad(0)


# --- Nunca unir cuentas (ADR-013, invariante 10) ---


@pytest.mark.django_db
def test_pi070_cliente_con_telefono_y_nombre_de_un_maestro_es_otra_cuenta():
    maestro = crear_cuenta_maestro(
        nombre="Ana Prueba", telefono=TEL_A, rut="11.111.111-1", contrasena=CONTRASENA
    )

    cliente = crear_cuenta_cliente(
        nombre="Ana Prueba", telefono=TEL_A, correo="ana@example.com", contrasena=CONTRASENA, comuna=COMUNA
    )

    assert cliente.pk != maestro.pk
    assert _roles(maestro) == {Rol.MAESTRO}
    assert not PerfilCliente.objects.filter(usuario=maestro).exists()


@pytest.mark.django_db
def test_pi071_maestro_con_correo_de_un_cliente_se_rechaza_sin_unir():
    cliente = _cliente(correo="x@example.com")

    with pytest.raises(ErrorValidacion) as error:
        _maestro(correo="X@example.com", telefono=TEL_B)

    assert error.value.campo == "correo"
    assert not PerfilMaestro.objects.filter(usuario=cliente).exists()
    assert _roles(cliente) == {Rol.CLIENTE}
    _sin_cambios_de_identidad(1)


@pytest.mark.django_db
def test_pi072_rut_de_otro_maestro_no_une_la_cuenta():
    maestro = _maestro(rut="11.111.111-1")
    cliente = _cliente(telefono=TEL_B)

    with pytest.raises(ErrorValidacion) as error:
        agregar_perfil_maestro(cliente, rut="11.111.111-1")

    assert error.value.campo == "rut"
    assert _roles(cliente) == {Rol.CLIENTE}
    assert PerfilMaestro.objects.get(rut="111111111").usuario_id == maestro.pk


# --- Agregar perfil de maestro a una cuenta existente ---


@pytest.mark.django_db
def test_pi080_cliente_agrega_perfil_de_maestro_en_la_misma_cuenta():
    cliente = _cliente()

    usuario = agregar_perfil_maestro(cliente, rut="22.222.222-2")

    assert usuario.pk == cliente.pk
    assert _roles(usuario) == {Rol.CLIENTE, Rol.MAESTRO}
    usuario.refresh_from_db()
    assert (usuario.nombre, usuario.telefono, usuario.correo) == (
        "Ana Prueba",
        TEL_A_CANONICO,
        "ana.prueba@example.com",
    )
    assert usuario.perfil_maestro.rut == "222222222"
    _sin_cambios_de_identidad(1)


@pytest.mark.django_db
def test_pi083_rut_invalido_al_agregar_perfil_no_crea_nada():
    cliente = _cliente()

    with pytest.raises(ErrorValidacion) as error:
        agregar_perfil_maestro(cliente, rut="10.000.013-1")

    assert error.value.campo == "rut"
    assert _roles(cliente) == {Rol.CLIENTE}


@pytest.mark.django_db
def test_pi084_cuenta_que_ya_es_maestro_no_agrega_otro_perfil():
    maestro = _maestro()

    with pytest.raises(ErrorValidacion) as error:
        agregar_perfil_maestro(maestro, rut="22.222.222-2")

    assert error.value.campo == "perfil"
    assert PerfilMaestro.objects.count() == 1


@pytest.mark.django_db
def test_pi085_fallo_al_asignar_el_rol_revierte_el_perfil(monkeypatch):
    cliente = _cliente()
    _fallar_al_asignar_rol(monkeypatch)

    with pytest.raises(RuntimeError):
        agregar_perfil_maestro(cliente, rut="22.222.222-2")

    assert not PerfilMaestro.objects.filter(usuario=cliente).exists()
    assert _roles(cliente) == {Rol.CLIENTE}


# --- Agregar perfil de cliente a una cuenta existente (ADR-013, punto 7; E-2) ---


@pytest.mark.django_db
def test_pi090_maestro_con_correo_agrega_perfil_de_cliente():
    maestro = _maestro(correo="mae1@example.com")

    usuario = agregar_perfil_cliente(maestro, comuna=COMUNA)

    assert usuario.pk == maestro.pk
    assert _roles(usuario) == {Rol.MAESTRO, Rol.CLIENTE}
    usuario.refresh_from_db()
    assert usuario.correo == "mae1@example.com"


@pytest.mark.django_db
@pytest.mark.parametrize("correo", ["otro@example.com", "mae1@example.com"])
def test_pi091_cuenta_con_correo_que_envia_correo_se_rechaza_sin_cambios(correo):
    maestro = _maestro(correo="mae1@example.com")

    with pytest.raises(ErrorValidacion) as error:
        agregar_perfil_cliente(maestro, comuna=COMUNA, correo=correo)

    assert error.value.campo == "correo"
    maestro.refresh_from_db()
    assert maestro.correo == "mae1@example.com"
    assert not PerfilCliente.objects.filter(usuario=maestro).exists()
    assert _roles(maestro) == {Rol.MAESTRO}


@pytest.mark.django_db
def test_pi092_maestro_sin_correo_agrega_su_primer_correo_con_el_perfil():
    maestro = _maestro()

    agregar_perfil_cliente(maestro, comuna=COMUNA, correo=" Nuevo@Example.com ")

    maestro.refresh_from_db()
    assert maestro.correo == "nuevo@example.com"
    assert _roles(maestro) == {Rol.MAESTRO, Rol.CLIENTE}
    assert PerfilCliente.objects.filter(usuario=maestro).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("correo", [AUSENTE, None, "", "   "])
def test_pi093_pi094_maestro_sin_correo_debe_entregarlo(correo):
    maestro = _maestro()

    with pytest.raises(ErrorValidacion) as error:
        agregar_perfil_cliente(maestro, comuna=COMUNA, correo=correo)

    assert error.value.campo == "correo"
    maestro.refresh_from_db()
    assert maestro.correo is None
    assert not PerfilCliente.objects.filter(usuario=maestro).exists()
    assert _roles(maestro) == {Rol.MAESTRO}


@pytest.mark.django_db
def test_pi095_correo_de_otra_cuenta_se_rechaza_sin_cambios():
    _cliente(correo="x@example.com", telefono=TEL_B)
    maestro = _maestro()

    with pytest.raises(ErrorValidacion) as error:
        agregar_perfil_cliente(maestro, comuna=COMUNA, correo="X@Example.com")

    assert error.value.campo == "correo"
    maestro.refresh_from_db()
    assert maestro.correo is None
    assert not PerfilCliente.objects.filter(usuario=maestro).exists()


@pytest.mark.django_db
def test_pi096_fallo_despues_de_guardar_el_correo_revierte_todo(monkeypatch):
    maestro = _maestro()
    _fallar_al_asignar_rol(monkeypatch)

    with pytest.raises(RuntimeError):
        agregar_perfil_cliente(maestro, comuna=COMUNA, correo="nuevo@example.com")

    maestro.refresh_from_db()
    assert maestro.correo is None
    assert not PerfilCliente.objects.filter(usuario=maestro).exists()
    assert _roles(maestro) == {Rol.MAESTRO}


@pytest.mark.django_db
def test_pi099_cuenta_que_ya_es_cliente_no_agrega_otro_perfil():
    cliente = _cliente()

    with pytest.raises(ErrorValidacion) as error:
        agregar_perfil_cliente(cliente, comuna=COMUNA)

    assert error.value.campo == "perfil"
    assert PerfilCliente.objects.count() == 1


# --- Teléfono al agregar un perfil (E-1, E-2) ---


def _agregar(perfil, usuario, **campos):
    if perfil == "cliente":
        return agregar_perfil_cliente(usuario, comuna=COMUNA, **campos)
    return agregar_perfil_maestro(usuario, rut="11.111.111-1", **campos)


@pytest.mark.django_db
@pytest.mark.parametrize("perfil", ["cliente", "maestro"])
def test_pi065_cuenta_sin_telefono_que_no_lo_entrega_no_recibe_perfil(perfil):
    admin = _admin(roles=[Rol.MODERACION])

    with pytest.raises(ErrorValidacion) as error:
        _agregar(perfil, admin)

    assert error.value.campo == "telefono"
    admin.refresh_from_db()
    assert admin.telefono is None
    assert _roles(admin) == {Rol.MODERACION}
    assert not PerfilCliente.objects.exists()
    assert not PerfilMaestro.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("perfil", ["cliente", "maestro"])
def test_pi116c_cuenta_administrativa_entrega_su_telefono_y_recibe_el_perfil(perfil):
    admin = _admin()

    usuario = _agregar(perfil, admin, telefono="9 1000 0001")

    assert usuario.pk == admin.pk
    admin.refresh_from_db()
    assert admin.telefono == TEL_A_CANONICO
    assert _roles(admin) == {Rol.CURATORIA, perfil}
    modelo = PerfilCliente if perfil == "cliente" else PerfilMaestro
    assert modelo.objects.filter(usuario=admin).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("perfil", ["cliente", "maestro"])
@pytest.mark.parametrize("telefono", [None, "", "12345", "56 9 1000 0001"])
def test_pi116b_telefono_invalido_no_crea_nada(perfil, telefono):
    admin = _admin()

    with pytest.raises(ErrorValidacion) as error:
        _agregar(perfil, admin, telefono=telefono)

    assert error.value.campo == "telefono"
    admin.refresh_from_db()
    assert admin.telefono is None
    assert _roles(admin) == {Rol.CURATORIA}
    assert not PerfilCliente.objects.exists()
    assert not PerfilMaestro.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("perfil", ["cliente", "maestro"])
def test_pi118_fallo_despues_de_guardar_el_telefono_revierte_todo(perfil, monkeypatch):
    admin = _admin()
    _fallar_al_asignar_rol(monkeypatch)

    with pytest.raises(RuntimeError):
        _agregar(perfil, admin, telefono=TEL_A)

    admin.refresh_from_db()
    assert admin.telefono is None
    assert not PerfilCliente.objects.exists()
    assert not PerfilMaestro.objects.exists()
    assert _roles(admin) == {Rol.CURATORIA}


@pytest.mark.django_db
@pytest.mark.parametrize("perfil", ["cliente", "maestro"])
@pytest.mark.parametrize("telefono", [TEL_A, TEL_B])
def test_pi066_cuenta_con_telefono_que_lo_envia_se_rechaza_sin_cambios(perfil, telefono):
    # La cuenta ya tiene teléfono TEL_A y todavía no tiene el perfil que agrega.
    if perfil == "cliente":
        cuenta, roles_previos = _maestro(correo="mae1@example.com", telefono=TEL_A), {Rol.MAESTRO}
    else:
        cuenta, roles_previos = _cliente(telefono=TEL_A), {Rol.CLIENTE}

    with pytest.raises(ErrorValidacion) as error:
        if perfil == "cliente":
            agregar_perfil_cliente(cuenta, comuna=COMUNA, telefono=telefono)
        else:
            agregar_perfil_maestro(cuenta, rut="22.222.222-2", telefono=telefono)

    assert error.value.campo == "telefono"
    cuenta.refresh_from_db()
    assert cuenta.telefono == TEL_A_CANONICO
    assert _roles(cuenta) == roles_previos
    assert PerfilCliente.objects.count() + PerfilMaestro.objects.count() == 1


# --- Cuenta administrativa (ADR-013, punto 8) ---


@pytest.mark.django_db
@pytest.mark.parametrize("correo", [None, "", "  "])
def test_pi110_cuenta_administrativa_exige_correo(correo):
    with pytest.raises(ErrorValidacion) as error:
        crear_cuenta_administrativa(
            nombre="Admin Prueba", correo=correo, roles=[Rol.CURATORIA], contrasena=CONTRASENA
        )

    assert error.value.campo == "correo"
    _sin_cambios_de_identidad(0)


@pytest.mark.django_db
def test_pi111_cuenta_administrativa_sin_telefono():
    usuario = _admin()

    usuario.refresh_from_db()
    assert usuario.telefono is None


@pytest.mark.django_db
def test_cuenta_administrativa_con_telefono_lo_normaliza():
    usuario = _admin(telefono=TEL_B)

    usuario.refresh_from_db()
    assert usuario.telefono == TEL_B_CANONICO


@pytest.mark.django_db
@pytest.mark.parametrize("telefono", [None, "", "12345"])
def test_cuenta_administrativa_con_telefono_invalido_no_se_crea(telefono):
    with pytest.raises(ErrorValidacion) as error:
        _admin(telefono=telefono)

    assert error.value.campo == "telefono"
    _sin_cambios_de_identidad(0)


@pytest.mark.django_db
def test_pi112_varios_roles_administrativos_en_una_cuenta_sin_perfiles():
    usuario = _admin(roles=["curatoria", "comercial"])

    assert Usuario.objects.count() == 1
    assert _roles(usuario) == {Rol.CURATORIA, Rol.COMERCIAL}
    assert not PerfilCliente.objects.exists()
    assert not PerfilMaestro.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("roles", [[], ["cliente"], ["maestro"], ["curatoria", "maestro"], ["visitante"]])
def test_cuenta_administrativa_solo_con_roles_administrativos(roles):
    with pytest.raises(ErrorValidacion) as error:
        _admin(roles=roles)

    assert error.value.campo == "roles"
    _sin_cambios_de_identidad(0)


@pytest.mark.django_db
@pytest.mark.parametrize("rol", ["cliente", "maestro"])
def test_pi113_no_se_asigna_cliente_ni_maestro_sin_su_perfil(rol):
    admin = _admin()

    with pytest.raises(ErrorValidacion):
        asignar_rol_administrativo(admin, rol)

    assert _roles(admin) == {Rol.CURATORIA}


@pytest.mark.django_db
def test_pi115_maestro_sin_correo_puede_recibir_un_rol_administrativo():
    maestro = _maestro()

    asignar_rol_administrativo(maestro, Rol.CURATORIA)

    assert _roles(maestro) == {Rol.MAESTRO, Rol.CURATORIA}


@pytest.mark.django_db
def test_rol_administrativo_repetido_se_rechaza():
    admin = _admin()

    with pytest.raises(ErrorValidacion):
        asignar_rol_administrativo(admin, Rol.CURATORIA)

    assert _roles(admin) == {Rol.CURATORIA}


# --- verificar_invariantes (PI-130, PI-133) ---


def _usuario_directo(**campos):
    datos = {"nombre": "Persona Prueba", "telefono": TEL_A_CANONICO, "correo": "p@example.com"}
    datos.update(campos)
    return Usuario.objects.create(**datos)


@pytest.mark.django_db
def test_verificar_invariantes_detecta_escrituras_que_saltan_el_servicio():
    rol_sin_perfil = _usuario_directo(correo="a@example.com")
    UsuarioRol.objects.create(usuario=rol_sin_perfil, rol=Rol.CLIENTE)
    perfil_sin_rol = _usuario_directo(correo="b@example.com")
    PerfilMaestro.objects.create(usuario=perfil_sin_rol, rut="111111111")
    sin_identificador = _usuario_directo(correo=None)
    cliente_sin_telefono = _usuario_directo(correo="c@example.com", telefono=None)
    PerfilCliente.objects.create(usuario=cliente_sin_telefono, comuna_id=8101)
    UsuarioRol.objects.create(usuario=cliente_sin_telefono, rol=Rol.CLIENTE)
    admin_sin_correo = _usuario_directo(correo=None, telefono=None)
    UsuarioRol.objects.create(usuario=admin_sin_correo, rol=Rol.CURATORIA)

    for usuario in (rol_sin_perfil, perfil_sin_rol, sin_identificador, cliente_sin_telefono, admin_sin_correo):
        assert verificar_invariantes(usuario), f"usuario {usuario.pk}"

    # Se limpian para que la verificación final (PI-130) solo mire cuentas creadas por servicios.
    UsuarioRol.objects.all().delete()
    PerfilCliente.objects.all().delete()
    PerfilMaestro.objects.all().delete()
    Usuario.objects.all().delete()


@pytest.mark.django_db
def test_si_un_invariante_falla_el_servicio_revierte_todo(monkeypatch):
    monkeypatch.setattr(servicios, "verificar_invariantes", lambda usuario: ["forzado"])

    with pytest.raises(InvarianteVioladaError):
        _cliente()

    monkeypatch.undo()
    _sin_cambios_de_identidad(0)
    assert not UsuarioRol.objects.exists()


# --- Concurrencia (PI-280, PI-281, PI-284) ---


def _en_paralelo(*funciones):
    """Ejecuta las funciones a la vez; devuelve el resultado o la excepción de cada una."""
    barrera = threading.Barrier(len(funciones))
    resultados = [None] * len(funciones)

    def ejecutar(indice, funcion):
        try:
            barrera.wait(timeout=10)
            resultados[indice] = funcion()
        except Exception as error:  # noqa: BLE001 - se inspecciona en la prueba
            resultados[indice] = error
        finally:
            connection.close()

    hilos = [threading.Thread(target=ejecutar, args=(i, f)) for i, f in enumerate(funciones)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)
    return resultados


def _un_exito_y_un_error_en(resultados, campo):
    exitos = [r for r in resultados if isinstance(r, Usuario)]
    errores = [r for r in resultados if isinstance(r, ErrorValidacion)]
    assert len(exitos) == 1, resultados
    assert len(errores) == 1, resultados
    assert errores[0].campo == campo


@pytest.mark.django_db(transaction=True)
def test_pi280_dos_registros_simultaneos_con_el_mismo_correo():
    resultados = _en_paralelo(
        lambda: _cliente(correo="a@example.com", telefono=TEL_A),
        lambda: _cliente(correo="A@example.com", telefono=TEL_B),
    )

    _un_exito_y_un_error_en(resultados, "correo")
    assert Usuario.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_pi281_dos_postulaciones_simultaneas_con_el_mismo_rut():
    resultados = _en_paralelo(
        lambda: _maestro(rut="11.111.111-1", telefono=TEL_A),
        lambda: _maestro(rut="111111111", telefono=TEL_B),
    )

    _un_exito_y_un_error_en(resultados, "rut")
    assert Usuario.objects.count() == 1
    assert UsuarioRol.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_pi284_misma_cuenta_agrega_perfil_de_cliente_dos_veces_a_la_vez():
    maestro = _maestro(correo="mae1@example.com")

    resultados = _en_paralelo(
        lambda: agregar_perfil_cliente(maestro, comuna=COMUNA),
        lambda: agregar_perfil_cliente(maestro, comuna=COMUNA),
    )

    _un_exito_y_un_error_en(resultados, "perfil")
    assert PerfilCliente.objects.count() == 1
    assert _roles(maestro) == {Rol.MAESTRO, Rol.CLIENTE}
