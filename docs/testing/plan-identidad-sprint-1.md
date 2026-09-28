# Plan de pruebas — Modelo de identidad del Sprint 1

- Estado: **Plan — ejecución parcial** (2026-09-28). Implementadas y aprobadas, en la capa de modelo y servicios (sin API): PI-044 (solo el mínimo definido), PI-045, PI-046, PI-050, PI-052, PI-053, PI-061, PI-130, PI-131, PI-132, PI-133, PI-280, PI-281 y PI-284 (estas tres últimas sobre los servicios, no por HTTP). El resto sigue pendiente.
- Fecha: 2026-09-27
- Referencia: [ADR-013](../decisions/ADR-013-acceso-politica-contrasena.md) (Aceptada, 2026-09-27)
- Requisitos: RF-01, RF-02, RF-03, RNF-05, RNF-09, RNF-10, RNF-15
- Preparado por: agente `qa`, sobre las decisiones aprobadas para ADR-013. La sección 8 concilia el plan con el texto de ADR-013 ya escrito.

## 0. Leyenda y datos de prueba

**Estado de dependencia**
- **E13**: ejecutable con ADR-013 Aceptada.
- **E13†**: ejecutable con ADR-013; necesita una comuna de prueba creada por fixture. Cómo se referencia la comuna en el cuerpo lo fija ADR-012 (Borrador); la prueba no verifica comportamiento de comuna.
- **E13-P**: ejecutable con ADR-013, pero la ruta o el mecanismo solo aparece en la propuesta del S1 (Borrador): `POST/DELETE /api/sesion`, `GET /api/cuenta`, comando `crear_usuario_administrativo`, formato JSON de error. Si cambian, se ajusta el nombre y no el objetivo de la prueba.
- **PD(HQ-xx)**: ningún documento fija todavía el resultado esperado (sección 6). No se ejecuta como aprobación hasta que exista la definición.
- **B-004 / B-005 / B-007 / B-012**: bloqueada por ese ADR en Borrador.

**Datos ficticios**
- RUT sintéticos válidos por dígito verificador (módulo 11): `11.111.111-1`, `22.222.222-2`, `33.333.333-3`, `10.000.013-K` (DV K), `10.000.004-0` (DV 0), `12.345.678-5`.
- RUT inválidos: `11.111.111-2`, `10.000.013-1`, `11.111.111-K`.
- Correos: dominio reservado `example.com` (por ejemplo, `ana.prueba@example.com`, `mae1@example.com`).
- Teléfonos sintéticos: `+56 9 1000 0001`; fijo `+56 41 200 0001`. Forma canónica: `+56910000001` y `+56412000001` (ADR-013, Enmienda E-3).
- Nombres inventados: "Ana Prueba", "Maestro Uno".

**Herramientas (ADR-014)**: pytest, pytest-django, time-machine. Concurrencia: `django_db(transaction=True)` con hilos y barrera.

## 1. Tablas del plan

### A. Registro de cliente por visitante — `POST /api/clientes` sin sesión (RF-01, HU-01)

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-001 | RF-01; ADR-013 cuenta única | BD vacía | nombre, teléfono, correo, contraseña válida, comuna | 201. Se crea 1 `usuario`, 1 `perfil_cliente` y el rol `cliente` | Integración API+BD | Alta | E13† |
| PI-002 | RF-01; RNF-15 | — | Sin `nombre` | 400 con error en el campo nombre y acción correctiva. No se crea nada | Integración API | Alta | E13† |
| PI-003 | RF-01; RNF-15 | — | Sin `telefono` | 400 en el campo teléfono. No se crea nada | Integración API | Alta | E13† |
| PI-004 | RF-01; ADR-013 (perfil_cliente exige correo) | — | Sin `correo` | 400 en el campo correo. No se crea nada | Integración API | Alta | E13† |
| PI-005 | ADR-013 (vacío prohibido) | — | `correo=""` y `correo="   "` | 400 en el campo correo. En la BD no queda ninguna fila con `""` | Integración API+BD | Alta | E13† |
| PI-006 | ADR-013 política | — | Sin `contrasena` | 400 en el campo contraseña | Integración API | Alta | E13† |
| PI-007 | CA-01.1 | — | Sin comuna | 400 que indica que la comuna es obligatoria | Integración API | Alta | B-012 |
| PI-008 | RF-01 (lista cerrada) | — | Comuna inexistente | 400 en el campo comuna | Integración API | Alta | B-012 |
| PI-009 | RF-01; CA-01.2 | Catálogo cargado | Región o provincia incoherente con la comuna; listado de comunas por región | 400 si hay incoherencia; el listado solo trae comunas de la región | Integración API | Media | B-012 |
| PI-010 | HU-25; ADR-013, Enmienda E-2 | — | Cuerpo válido más `roles:["curatoria"]`, `activo:false`, `id:<otro>` | 400 general que indica que la solicitud contiene campos no permitidos, sin error por campo. No se crea nada | Seguridad (asignación masiva) | Alta | E13† |
| PI-011 | ADR-006 | — | POST válido sin token CSRF | 403. No se crea nada | Seguridad | Alta | E13† |
| PI-012 | RNF-05; privacidad | — | Registro válido | La respuesta 201 no contiene la contraseña, el hash ni datos de otras cuentas | Seguridad | Alta | E13† |
| PI-013 | RF-01; ADR-013, Enmienda E-8 | Sin sesión | Registro válido | 201. No se crea una sesión autenticada (no se emite cookie de sesión) y `GET /api/cuenta` con el mismo cliente HTTP responde 401 | Integración | Alta | E13† / E13-P |
| PI-014 | ADR-013, Enmienda E-2; RNF-15 | — | Cuerpo válido más `rut` o `identificador` (campos conocidos que este contexto no permite) | 400 con error en ese campo y acción correctiva. No se crea nada | Integración | Alta | E13† |

### B. Postulación de maestro por visitante — `POST /api/maestros/postulaciones` sin sesión (RF-03, HU-11)

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-020 | RF-03; §3.4 (correo opcional) | — | RUT `11.111.111-1`, nombre, teléfono, contraseña; sin correo | 201. `usuario.correo IS NULL` (no `""`); se crean `perfil_maestro` y el rol `maestro` | Integración API+BD | Alta | E13 |
| PI-021 | ADR-013 normalización | — | Lo mismo más `correo=" Mae1@Example.COM "` | 201. Se guarda `mae1@example.com` | Integración | Alta | E13 |
| PI-022 | RF-03; RNF-15 | — | Sin RUT, sin nombre o sin teléfono (un caso por campo) | 400 en el campo correspondiente. No se crea nada | Integración | Alta | E13 |
| PI-023 | RF-03 (DV) | — | `11.111.111-2`, `10.000.013-1` | 400 en el campo RUT, con acción correctiva | Integración | Alta | E13 |
| PI-024 | CA-11.3 | Existe un maestro con `11.111.111-1` | Mismo RUT | 400 "ese RUT ya tiene una postulación". No se crea un nuevo usuario | Integración | Alta | E13 |
| PI-025 | CA-11.3; normalización | Existe `11.111.111-1` | `111111111` y `11111111-1` | 400 CA-11.3, igual que PI-024 | Integración | Alta | E13 |
| PI-026 | ADR-013 unicidad del correo | Existe una cuenta con `ana.prueba@example.com` | Postulación con `ANA.PRUEBA@example.com` | 400 en el campo correo. No se crea perfil; la cuenta existente queda intacta | Integración | Alta | E13 |
| PI-027 | ADR-013 (NULL = ausencia) | Existe un maestro sin correo | Otro maestro sin correo | 201. Dos usuarios con correo NULL; UNIQUE no lo impide | BD | Alta | E13 |
| PI-028 | ADR-013, Enmienda E-7 | — | Maestro con `correo=""` o `"  "` | 400 en el campo correo, con acción correctiva. No se crea nada; nunca se guarda `""` ni se convierte en NULL | Integración | Media | E13 |
| PI-029 | RF-03; ADR-013, Enmienda E-8 | Sin sesión | Postulación válida | 201. No se crea una sesión autenticada; `GET /api/cuenta` con el mismo cliente HTTP responde 401 | Integración | Alta | E13-P |
| PI-030 | ADR-013, Enmienda E-2; RNF-15 | — | Postulación válida más `comuna` o `identificador`; postulación válida más una clave desconocida (`activo`) | Campo conocido: 400 en ese campo, con acción correctiva. Clave desconocida: 400 general. No se crea nada | Integración | Alta | E13 |

### C. Normalización y validación del RUT (RF-03)

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-040 | RF-03 | — | `11.111.111-1`, `11111111-1`, `111111111` | Los tres normalizan al mismo valor canónico (sin puntos ni guion) | Unitaria | Alta | E13 |
| PI-041 | RF-03 (DV K) | — | `10.000.013-k`, `10.000.013-K`, `10000013k` | Válidos; normalizados con DV en mayúscula | Unitaria | Alta | E13 |
| PI-042 | RF-03 (DV 0) | — | `10.000.004-0` | Válido | Unitaria | Media | E13 |
| PI-043 | RF-03 | — | DV equivocado; `11.111.111-K`; letras en el cuerpo (`1A.111.111-1`); vacío; solo `-1` | Se rechazan | Unitaria | Alta | E13 |
| PI-044 | RF-03 | — | Espacios alrededor, ceros a la izquierda (`011.111.111-1`), separadores raros (`–`, `,`), dígitos Unicode no ASCII | Como mínimo, nunca se guarda un valor con caracteres no ASCII. Aceptar o rechazar cada caso no está definido | Unitaria/seguridad | Media | PD(HQ-12) |
| PI-045 | RF-03; ADR-013 | — | Inserción directa (ORM o SQL) de dos `perfil_maestro` con el mismo RUT | IntegrityError por la restricción UNIQUE de la BD, no solo por validación en Python | BD | Alta | E13 |
| PI-046 | ADR-013, Enmienda E-6 (CHECK `^[0-9]{1,8}[0-9K]$`) | — | Inserción directa de `11.111.111-1` sin normalizar, de un DV `k` en minúscula, de dígitos no ASCII y de un valor sin cuerpo (`K`) | La BD lo rechaza (IntegrityError, o DataError si excede el largo de la columna) | BD | Media | E13 |

### D. Correo: normalización y unicidad

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-050 | ADR-013 | — | `"  Ana.Prueba@Example.CL  "` | Se guarda `ana.prueba@example.cl` | Unitaria+integración | Alta | E13† |
| PI-051 | ADR-013 (case-insensitive) | Existe `ana.prueba@example.com` | Nuevo registro con `Ana.Prueba@EXAMPLE.com` | 400 en el campo correo. Sigue habiendo un solo usuario con ese correo | Integración | Alta | E13† |
| PI-052 | ADR-013 (UNIQUE sin CITEXT) | — | Inserción directa de dos usuarios con el mismo correo normalizado | IntegrityError de la BD | BD | Alta | E13 |
| PI-053 | ADR-013, Enmienda E-6 | — | Inserción directa de `""` o de un correo en mayúsculas, saltando el servicio | `""`: la BD lo rechaza (CHECK). Correo en mayúsculas: la BD lo acepta, porque por decisión no hay CHECK de minúsculas; la normalización es responsabilidad del servicio (PI-050) | BD | Media | E13 |
| PI-054 | RNF-15 | — | `ana prueba@example.com`, `ana@`, `@example.com`, `anaexample.com` | 400 en el campo correo, con acción correctiva | Integración | Alta | E13† |
| PI-055 | ADR-013 | — | Mayúsculas no ASCII (`ÁNA@example.com`), `ß`, dominio IDN, tabulador o salto de línea al borde | "Case-insensitive" no está definido fuera de ASCII, ni qué espacios se recortan | Unitaria | Baja | PD(HQ-11) |

### E. Teléfono

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-060 | ADR-013 (no único; nunca unir) | Existe el cliente A con `+56 9 1000 0001` | Visitante registra un cliente B con el mismo teléfono y otro correo | 201. Quedan 2 usuarios distintos y A no cambia | Integración | Alta | E13† |
| PI-061 | ADR-013, Enmienda E-3 (forma canónica) | — | `+56 9 1000 0001`, `+56910000001`, `9 1000 0001`, `(9) 1000-0001` | Las cuatro variantes se guardan como `+56910000001` | Unitaria | Alta | E13 |
| PI-062 | ADR-013 (se aceptan fijos); Enmienda E-3 | — | `+56 41 200 0001` | Se acepta y se guarda como `+56412000001` | Unitaria+integración | Alta | E13 |
| PI-063 | RNF-15; ADR-013, Enmienda E-3 | — | Letras; vacío; 8 o 10 dígitos nacionales; `+56` con 8 o 10 dígitos; `56 9 1000 0001` (prefijo 56 sin `+`); `+54 9 1000 0001`; `+` fuera del inicio; dígitos no ASCII; separadores distintos de espacio, guion y paréntesis (`.`, `/`) | 400 en el campo teléfono, con acción correctiva. Además, 9 dígitos que empiezan con `56` se tratan como número nacional (`+56` antepuesto), sin trato especial | Unitaria | Media | E13 |
| PI-064 | ADR-013 (teléfono no es identificador) | Existe una cuenta con ese teléfono | Login con `identificador=<teléfono>` y la contraseña correcta | Nunca 200: 400 si no pasa el DV del RUT; 401 si por azar coincide con un RUT válido no registrado | Seguridad | Alta | E13-P |
| PI-065 | ADR-013 (teléfono obligatorio para perfiles); Enmienda E-1 | — | Servicio que crea `perfil_cliente` o `perfil_maestro` en un usuario con teléfono NULL, sin entregar el teléfono en la misma operación | 400 en el campo teléfono. No se crea nada | Servicio/BD | Alta | E13 |
| PI-066 | ADR-013, Enmiendas E-1 y E-2 | Cuenta autenticada con teléfono T | `POST /api/clientes` o postulación que además envía `telefono` (igual o distinto de T) | 400 en el campo teléfono. El teléfono sigue siendo T; no se crea perfil ni rol | Integración | Alta | E13 / E13† |

### F. No unión automática de cuentas

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-070 | ADR-013 | Existe el maestro M (correo NULL, teléfono T) | Visitante registra un cliente con teléfono T y el mismo nombre | Se crea una cuenta nueva. M no gana `perfil_cliente` ni el rol `cliente` | Integración | Alta | E13† |
| PI-071 | ADR-013 | Existe el cliente C con correo X | Visitante postula como maestro con correo X | 400 en el campo correo. C no gana `perfil_maestro` | Integración | Alta | E13 |
| PI-072 | ADR-013; CA-11.3 | Existe el maestro con `11.111.111-1` | Visitante registra un cliente y luego postula con ese RUT | La postulación responde 400 CA-11.3 y la cuenta nueva no se une a la del maestro | Integración | Alta | E13† |
| PI-073 | ADR-013 | Existe el maestro M con correo X | Visitante registra un cliente con correo X y la misma contraseña que M | 400 en el campo correo. No hay inicio de sesión implícito ni se agrega perfil a M | Seguridad | Alta | E13† |
| PI-074 | ADR-013, Enmienda E-2; HU-25 | Existe la cuenta A | Registro sin sesión con `usuario_id`, `cuenta` o `id` apuntando a A | 400 general (claves desconocidas). No se crea una cuenta y nunca se agrega un perfil a A | Seguridad | Alta | E13† |

### G. Cuenta con múltiples roles: agregar un segundo perfil

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-080 | ADR-013 pto 2; RF-03 | Cliente autenticado | Postulación solo con RUT `22.222.222-2` | 201. Mismo `usuario.id`, roles {cliente, maestro}, el número de usuarios no cambia; teléfono y nombre se toman de la cuenta | Integración | Alta | E13† |
| PI-081 | ADR-013 pto 2; Enmienda E-2 | Cliente autenticado | Postulación que además envía otro teléfono, nombre o contraseña (un caso por campo) | 400 en el campo enviado, con acción correctiva. Teléfono, nombre y hash no cambian; no se crea perfil ni rol | Integración | Media | E13† |
| PI-082 | CA-11.3; ADR-013 | Cliente autenticado; `11.111.111-1` pertenece a otra cuenta | Postulación con ese RUT | 400 CA-11.3. No se crea perfil ni rol | Integración | Alta | E13† |
| PI-083 | RF-03 | Cliente autenticado | DV inválido | 400 en el campo RUT | Integración | Alta | E13† |
| PI-084 | ADR-013 pto 2 | Cuenta que ya es maestro | Nueva postulación | 400 accionable. No se crea nada | Integración | Alta | E13 |
| PI-085 | Atomicidad (ADR-013 pto 2) | Cliente autenticado | Fallo forzado al insertar el rol (monkeypatch) | No queda `perfil_maestro` ni rol | Integración/BD | Alta | E13† |
| PI-086 | ADR-013 (identificador) | Cuenta con los dos perfiles | Login con el correo y login con el RUT | Ambos resuelven al mismo `usuario.id` (vía `GET /api/cuenta`) | Integración | Alta | E13-P |
| PI-090 | ADR-013 pto 2; RF-01 | Maestro con correo, autenticado | `POST /api/clientes` solo con comuna | 201. Mismo usuario, roles {maestro, cliente}, correo sin cambios | Integración | Alta | E13† |
| PI-091 | ADR-013 pto 7; Enmienda E-2; RNF-09 (cambiar correo fuera de alcance) | Maestro con correo X, autenticado | Comuna más `correo=Y` (también con `correo=X`) | 400 en el campo correo. El correo sigue siendo X; no se crea perfil ni rol | Seguridad | Alta | E13† — ver sección 8.1 |
| PI-092 | ADR-013 (primer correo) | Maestro sin correo, autenticado | Comuna más `correo=" Nuevo@Example.com "` | 201. `usuario.correo = nuevo@example.com`; se crean perfil y rol | Integración | Alta | E13† |
| PI-093 | ADR-013 | Maestro sin correo, autenticado | Solo comuna | 400 en el campo correo. El correo sigue NULL; no se crea perfil ni rol | Integración | Alta | E13† |
| PI-094 | ADR-013 | Maestro sin correo, autenticado | `correo=""` o `"   "` | 400 en el campo correo | Integración | Alta | E13† |
| PI-095 | ADR-013 (colisión) | Maestro sin correo; otra cuenta tiene `x@example.com` | `correo="X@Example.com"` | 400 en el campo correo. El correo sigue NULL; no se crea perfil ni rol | Integración | Alta | E13† |
| PI-096 | ADR-013 (atomicidad perfil + rol + usuario) | Maestro sin correo | Fallo forzado después de actualizar el correo y antes de insertar el rol | Rollback completo: correo NULL, sin perfil y sin rol | Integración/BD | Alta | E13† |
| PI-097 | RNF-09 (primer correo no es "cambiar correo") | Maestro sin correo, sesión activa, sin volver a autenticarse | PI-092 sin contraseña en el cuerpo | 201. No se pide reautenticación | Integración | Media | E13† |
| PI-098 | ADR-013 | Después de PI-092 | Login con el correo nuevo y login con el RUT | Los dos llegan a la misma cuenta | Integración | Alta | E13-P |
| PI-099 | ADR-013 pto 2 | Cuenta que ya es cliente | `POST /api/clientes` | 400 accionable. No se crea nada | Integración | Alta | E13† |
| PI-100 | CA-01.1 | Maestro autenticado | `POST /api/clientes` sin comuna | 400 en el campo comuna | Integración | Media | B-012 |

### H. Cuenta administrativa

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-110 | ADR-013 (cuenta solo administrativa debe tener correo) | — | Comando de alta sin correo | Se rechaza. No se crea el usuario | Integración (comando) | Alta | E13-P |
| PI-111 | ADR-013 (teléfono opcional) | — | Alta con correo, sin teléfono | Se crea con `telefono IS NULL` | Integración/BD | Media | E13-P |
| PI-112 | ADR-013; §3.1 | — | Alta con los roles `curatoria` y `comercial` | 1 usuario, 2 filas en `usuario_rol`, ninguna fila de perfil | BD | Alta | E13-P |
| PI-113 | Invariante rol <=> perfil | Existe una cuenta administrativa | El comando intenta asignar el rol `cliente` o `maestro` | Se rechaza, porque no existiría el perfil correspondiente | Integración | Alta | PD(HQ-15) — ver sección 8 |
| PI-114 | ADR-013 | Cuenta administrativa | Login con el correo; login con un RUT válido cualquiera | 200 con el correo; 401 genérico con el RUT | Integración | Media | E13-P |
| PI-115 | Invariantes | Un maestro sin correo recibe `curatoria` por comando | — | Se permite: la cuenta tiene `perfil_maestro` y RUT | Integración | Media | E13-P |
| PI-116 | ADR-013 (teléfono obligatorio para perfil); Enmienda E-1 | Cuenta administrativa sin teléfono, autenticada | `POST /api/clientes` o postulación: (a) sin `telefono`; (b) con `telefono` inválido; (c) con `telefono="9 1000 0001"` | (a) y (b): 400 en el campo teléfono; no se crea nada y el teléfono sigue NULL. (c): 201; `usuario.telefono = +56910000001`; perfil y rol creados en la misma cuenta | Integración | Media | E13 / E13† |
| PI-117 | CLAUDE.md §8 (registros) | — | Comando de alta | La contraseña no se recibe como argumento ni aparece en la salida o los registros | Seguridad | Media | E13-P |
| PI-118 | ADR-013, Enmienda E-1 (atomicidad perfil + rol + teléfono) | Cuenta administrativa sin teléfono | Fallo forzado después de guardar el teléfono y antes de insertar el rol | Rollback completo: teléfono NULL, sin perfil y sin rol | Integración/BD | Alta | E13 |

### I. Invariantes y restricciones de la BD

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-130 | Todas las invariantes de ADR-013 | Fixture autouse al final de cada prueba de integración | Recorre todos los usuarios | Se cumplen: rol cliente <=> perfil_cliente; rol maestro <=> perfil_maestro; correo NULL implica perfil_maestro con RUT; cuenta administrativa sin perfil_maestro tiene correo; perfil_cliente tiene correo y teléfono; perfil_maestro tiene RUT y teléfono; al menos un identificador | Servicio/BD | Alta | E13 |
| PI-131 | ADR-013 | — | Rol duplicado para el mismo usuario; segundo `perfil_cliente` para el mismo usuario | IntegrityError (PK o UNIQUE) | BD | Alta | E13 |
| PI-132 | ADR-013 (Visitante no persistido; Sistema no humano) | — | Insertar el rol `visitante` o `sistema`; buscar un usuario "Sistema" | Se rechaza el rol y no existe ese usuario | BD | Media | E13 (CHECK de roles, ADR-013, Enmienda E-6) |
| PI-133 | Invariante rol <=> perfil; ADR-013, Enmienda E-6 | — | ORM o SQL que inserta el rol `cliente` sin perfil | La BD lo acepta, porque la invariante es del servicio. `verificar_invariantes` lo detecta y ninguna vía del servicio lo deja confirmado (PI-130) | BD | Media | E13 |
| PI-134 | ADR-013, Enmienda E-6 (CHECK `^\+56[0-9]{9}$`) | — | Inserción directa en `usuario.telefono` de `+56 9 1000 0001`, `56910000001`, `+5691000000`, `+569100000011`, `""` y de NULL | La BD rechaza los cinco primeros (IntegrityError, o DataError si exceden el largo de la columna) y acepta NULL | BD | Alta | E13 |

### J. Política de contraseña (decisión del equipo en ADR-013)

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-150 | ADR-013 (mínimo 12); RNF-15 | — | 11 caracteres ASCII que no están en la lista | 400 en el campo contraseña, con mensaje que indica el mínimo | Unitaria+integración | Alta | E13 |
| PI-151 | ADR-013 | — | 12 caracteres | Se acepta | Unitaria+integración | Alta | E13 |
| PI-152 | ADR-013 (máximo 128) | — | 128 caracteres | Se acepta y el login posterior funciona | Unitaria+integración | Alta | E13 |
| PI-153 | ADR-013 | — | 129 caracteres | 400 con mensaje que indica el máximo | Unitaria+integración | Alta | E13 |
| PI-154 | Seguridad (DoS del hasher) | — | 10 000 caracteres y 1 MB en registro y en login | Nunca 500. El registro y el login responden 400 en el campo contraseña (ADR-013, Enmiendas E-4 y E-5). Se verifica que el hasher no se invoque en ninguno de los dos | Seguridad | Alta | E13 (login: E13-P) |
| PI-155 | ADR-013 (sin reglas de composición) | — | 12 minúsculas que no están en la lista | Se acepta | Unitaria | Media | E13 |
| PI-156 | ADR-013 (espacios permitidos) | — | `mi casa azul grande` | Se acepta; login con el texto exacto da 200 | Integración | Media | E13 |
| PI-157 | ADR-013 (no se recorta) | — | Registro con `"  clave de prueba  "` | Login con el texto exacto: 200. Login con el texto recortado: 401 | Integración | Alta | E13-P |
| PI-158 | ADR-013, Enmienda E-4 | — | 12 espacios; 128 espacios | 400 en el campo contraseña, con acción correctiva | Unitaria | Baja | E13 |
| PI-159 | ADR-013 (lista local) | Lista versionada en el repositorio | Una entrada de 12 o más caracteres tomada de esa lista | 400 accionable | Unitaria+integración | Alta | E13 (datos de la lista final) |
| PI-160 | ADR-013, Enmienda E-4 | — | La misma entrada de PI-159 con otras mayúsculas o con espacios al inicio o al final | Se rechaza (400 accionable). Es un hecho de implementación de `CommonPasswordValidator` en la versión de Django fijada (compara en minúsculas y sin espacios al borde), no una regla adicional; la contraseña guardada no se recorta | Unitaria | Baja | E13 |
| PI-161 | ADR-013 (sin servicios externos) | Red bloqueada (módulo socket parcheado) | Validar una contraseña | La validación funciona sin abrir conexiones | Seguridad | Media | E13 |
| PI-162 | ADR-013, Enmienda E-4 | — | Contraseña con `ñ`, tildes o emoji; 128 y 129 veces `ñ` (un carácter de varios bytes); registro en NFC y login con la misma contraseña en NFD | Se aceptan las contraseñas con `ñ`, tildes o emoji; 128 `ñ` se acepta y 129 se rechaza (se cuentan caracteres, no bytes). Sin normalización Unicode: el login en NFC responde 200 y en NFD, 401 | Unitaria+integración | Baja | E13 (login: E13-P) |
| PI-163 | ADR-013 (sin expiración) | Usuario creado | time-machine adelanta 400 días y se hace login | 200. No se exige cambiar la contraseña | Integración | Baja | E13-P |
| PI-164 | ADR-013 | — | La misma política en los dos endpoints de registro y en el comando | Se comporta igual en los tres | Integración | Media | E13 / E13-P |
| PI-165 | ADR-013, Enmiendas E-4 y E-5; RNF-15 | — | Contraseña con una secuencia Unicode que no puede procesarse (sustituto aislado, p. ej. `\ud800` escapado en el JSON), en el registro y en el login | 400 en el campo contraseña, en español y accionable; nunca 500 ni traza; el hasher no se invoca; no se crea nada | Seguridad | Alta | E13 (login: E13-P) |
| PI-166 | ADR-013, Enmienda E-4 (sin `NumericPasswordValidator` ni `UserAttributeSimilarityValidator`) | Verificar antes que los datos no estén en la lista común | 12 o más dígitos; contraseña que contiene el nombre o el correo del usuario | Se aceptan | Unitaria+integración | Media | E13 |

### K. RNF-05: la contraseña no se guarda en claro (independiente del algoritmo)

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-170 | RNF-05 | Usuario registrado con contraseña conocida | Se revisan todas las columnas de texto de todas las tablas, incluidas sesión e intentos | La contraseña en claro no aparece en ninguna parte, ni como subcadena | BD/seguridad | Alta | E13 |
| PI-171 | RNF-05 (con sal) | — | Dos usuarios con la misma contraseña | Valores guardados distintos | BD | Alta | E13 |
| PI-172 | RNF-05 (hash adaptativo) | — | Se identifica el algoritmo del valor guardado | Formato adaptativo con sal y factor de trabajo; no texto plano ni hash rápido o sin sal (MD5, SHA1, crypt). No se verifica cuál algoritmo | Seguridad | Alta | E13 |
| PI-173 | RNF-05 / RNF-04 | — | Parámetros concretos (memoria, iteraciones, tiempo) | — | Rendimiento/seguridad | Media | **B-004** |
| PI-174 | RNF-05; CLAUDE.md §8 | caplog en todos los niveles | Registro, login fallido y login exitoso | La contraseña no aparece en los registros; tampoco el cuerpo del login | Seguridad | Alta | E13-P |
| PI-175 | RNF-05; RNF-15 | — | Errores 400 de la contraseña | La respuesta no repite el valor enviado | Seguridad | Alta | E13 |
| PI-176 | Privacidad | Sesión activa | `GET /api/cuenta` | No incluye el hash; solo campos propios y explícitos | Seguridad | Alta | E13-P |

### L. Inicio y cierre de sesión (RF-02)

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-190 | RF-02; ADR-013 | Cliente registrado | `identificador=correo` y la contraseña | 200 y se crea la sesión | Integración | Alta | E13-P |
| PI-191 | ADR-013 (case-insensitive y recorte) | Ídem | `"  ANA.Prueba@Example.com "` | 200 con la misma cuenta | Integración | Alta | E13-P |
| PI-192 | ADR-013 (RUT) | Maestro `10.000.013-K` | `10.000.013-k`, `10000013K`, `10.000.013-K` | 200 con la misma cuenta en los tres casos | Integración | Alta | E13-P |
| PI-193 | ADR-013 (mismo 401) | Existe la cuenta A | (a) correo inexistente; (b) correo de A con contraseña incorrecta; (c) RUT válido no registrado; (d) RUT de A con contraseña incorrecta | Los cuatro dan 401 con cuerpo idéntico byte a byte, mismas cabeceras relevantes y sin sesión creada | Seguridad | Alta | E13-P |
| PI-194 | ADR-013; RNF-15 | — | Falta el identificador, falta la contraseña o faltan los dos | 400 con error en cada campo afectado | Integración | Alta | E13-P |
| PI-195 | ADR-013 (formato) | — | Sin "@" y con DV inválido (`11.111.111-2`); con "@" mal formado (`a@`, `@b.cl`); `""` o solo espacios | 400 en el campo identificador, con acción correctiva | Integración | Alta | E13-P |
| PI-196 | ADR-013 | Existe una cuenta parecida | Los 400 de PI-195 | El cuerpo no cambia según exista o no una cuenta parecida | Seguridad | Media | E13-P |
| PI-197 | RNF-15 (excepción documentada) | — | Texto del 401 | En español, genérico, con acción correctiva y sin códigos internos | Revisión | Alta | E13-P |
| PI-198 | ADR-006 | — | Login sin CSRF | 403 | Seguridad | Alta | E13-P |
| PI-199 | Robustez | — | Identificador `' OR 1=1 --@x.cl`, JSON mal formado, tipos incorrectos | 400 o 401, nunca 500 ni trazas | Seguridad | Alta | E13-P |
| PI-200 | RF-02 (logout) | Sesión activa | `DELETE /api/sesion` y luego `GET /api/cuenta` con la cookie anterior | 204 y después 401. La sesión se borra en el servidor | Integración | Alta | E13-P |
| PI-201 | RF-02 | Sin sesión | `GET /api/cuenta` | 401 | Seguridad | Alta | E13-P |
| PI-202 | Fijación de sesión | Cookie de sesión previa | Login | El ID de sesión cambia | Seguridad | Alta | **B-005** |
| PI-203 | Cookies | — | Login | Cookies con `Secure`, `HttpOnly` y `SameSite` | Seguridad | Media | **B-005** |
| PI-204 | Hash señuelo | — | Tiempo de respuesta con cuenta inexistente frente a contraseña incorrecta | Tiempos comparables. Solo informativa (puede ser inestable) | Seguridad | Baja | E13-P |
| PI-205 | RF-02; ADR-013, Enmienda E-5 | Cliente registrado | (a) `contrasena=""`; (b) 129 caracteres; (c) 10 000 caracteres; (d) 1 carácter; (e) solo espacios | (a) a (c): 400 en el campo contraseña, sin invocar el hasher (espía) y sin crear sesión. (d) y (e): se verifican contra el hash y responden el 401 genérico, porque en el login no se aplica la política de creación | Seguridad | Alta | E13-P (si los 400 cuentan para RNF-10: **B-007**) |
| PI-206 | RF-02; ADR-013, Enmienda E-2; RNF-15 | — | Login con `identificador`, `contrasena` y además `correo` o `rut`; login con una clave desconocida (`recordar`) | Campo conocido no permitido: 400 en ese campo, con acción correctiva. Clave desconocida: 400 general. En ambos casos no se crea sesión | Integración | Media | E13-P |

### M. RNF-10: limitación de intentos (M-07)

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-230 | RNF-10 | Mismo origen y mismo identificador; time-machine | 5 fallos 401 en menos de 15 min y luego la contraseña correcta | No se autentica (no se crea sesión). Código y mensaje del bloqueo dependen de ADR-007 | Seguridad | Alta | Núcleo E13-P; respuesta **B-007** |
| PI-231 | RNF-10 | Ídem | 4 fallos y luego la contraseña correcta | 200 | Seguridad | Alta | E13-P |
| PI-232 | RNF-10 (ventana de 15 min) | time-machine | Fallos en t = 0, 4, 8, 12 y 16 min; login correcto en t = 16 | 200: nunca hubo 5 fallos dentro de 15 minutos | Seguridad | Media | E13-P |
| PI-233 | M-07 (asociado al origen) | Origen A bloqueado | Login correcto desde el origen B | 200 | Seguridad | Alta | E13-P (cómo se fija el origen: B-007) |
| PI-234 | M-07 (nunca permanente) | Después del bloqueo | Revisar el estado de la cuenta | `activo` no cambia y no existe un campo de bloqueo en la cuenta | BD | Alta | E13 |
| PI-235 | M-07 | Después del bloqueo | Esperar la duración del bloqueo y volver a intentar | Se desbloquea | Seguridad | Alta | **B-007** |
| PI-236 | Decisión sobre el limitador | Después de fallos con correo y con RUT | Revisar la tabla de intentos | No guarda el correo ni el RUT en claro | BD/privacidad | Alta | E13 |
| PI-237 | RNF-10 | — | Si cuentan los 400 y los 429, si un login exitoso reinicia el contador, la clave (IP o IP con identificador), la confianza en `X-Real-IP` y la limpieza | — | Seguridad | Media | **B-007** |
| PI-238 | RNF-15 | Origen bloqueado | Mensaje de bloqueo | Accionable y sin códigos internos | Revisión | Media | **B-007** |

### N. RNF-09 y funciones fuera de alcance

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-250 | RNF-09 | Sesión activa; time-machine | Inactividad de 29 min y de 31 min | Válida a los 29 min; 401 a los 31 min | Integración | Alta | **B-005** |
| PI-251 | RNF-09 | Ídem | Petición en el minuto 20 y otra en el 45 | Sigue válida si la expiración es deslizante (qué cuenta como actividad está abierto) | Integración | Media | **B-005** |
| PI-252 | Fuera de alcance (prueba negativa) | — | Rutas de cambio de correo, cambio de contraseña, recuperación o verificación de correo; `PUT/PATCH /api/cuenta` | No existen: 404 o 405 | Seguridad | Baja | E13-P |

### O. RNF-15 en todos los endpoints

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-270 | RNF-15 | — | Todos los 400 de las secciones A a M | Cada error indica el campo y la acción correctiva, en español. Lista de texto prohibido: `Traceback`, `IntegrityError`, `duplicate key`, `violates`, `unique constraint`, `null value`, `SQLSTATE`, `23505`, `ValidationError`, `This field is required`, `Enter a valid` | Integración | Alta | E13 (formato JSON: E13-P) |
| PI-271 | RNF-15 | — | Cuerpo que no es JSON; `Content-Type` incorrecto | 400 genérico y accionable, sin traza | Integración | Media | E13-P |
| PI-272 | RNF-15 ("se revisa en todos los formularios") | Cuando exista frontend | Revisión manual de los formularios | — | Manual | Media | Fuera de este plan hasta que exista frontend |
| PI-273 | RNF-15 (interpretación en ADR-013, Enmienda E-2) | — | En `POST /api/clientes`, `POST /api/maestros/postulaciones` y `POST /api/sesion`, con y sin sesión: una clave desconocida con un nombre llamativo (p. ej. `<script>` o `password_hash`) | 400 general, en español y accionable, que no repite la clave ni el valor enviados ni muestra nombres internos, SQL o trazas (lista de texto prohibido de PI-270). No se crea ni se modifica nada | Seguridad | Alta | E13-P |

### P. Concurrencia

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-280 | ADR-013 (UNIQUE del correo) | `transaction=True` | Dos registros simultáneos: `a@example.com` y `A@example.com` | Uno 201 y otro 400 en el campo correo, nunca 500. Queda 1 usuario | Concurrencia/BD | Alta | E13† |
| PI-281 | RF-03; CA-11.3 | Ídem | Dos postulaciones simultáneas: `11.111.111-1` y `111111111` | Una 201 y otra 400 CA-11.3. Queda 1 usuario | Concurrencia/BD | Alta | E13 |
| PI-282 | ADR-013 | Ídem | Un cliente autenticado y un visitante postulan a la vez con el mismo RUT | Solo uno tiene éxito. No quedan filas huérfanas | Concurrencia | Media | E13† |
| PI-283 | ADR-013 | Ídem | Dos maestros sin correo agregan `perfil_cliente` a la vez con el mismo correo | Uno 201 y otro 400. En el perdedor, correo NULL y sin perfil | Concurrencia | Alta | E13† |
| PI-284 | ADR-013 | Ídem | La misma sesión envía dos `POST /api/clientes` a la vez | Un solo perfil y un solo rol. El segundo responde 400, no 500 | Concurrencia | Media | E13† |

### Q. Autorización básica

| ID | Requisito | Precondición | Entrada | Resultado esperado | Tipo | Prio | Dep. |
|---|---|---|---|---|---|---|---|
| PI-290 | ADR-013 (agregar perfil solo con sesión) | Existe la cuenta A | Sin sesión, `POST /api/clientes` solo con la comuna | 400 por faltar nombre, teléfono, correo y contraseña. No se crea cuenta y A no cambia | Seguridad | Alta | E13† |
| PI-291 | ADR-013 | Sesión expirada o cookie inválida | Lo mismo que PI-290 | Se trata como visitante y responde 400. No se crea nada | Seguridad | Alta | E13† (expiración real: B-005) |
| PI-292 | HU-25; ADR-013, Enmienda E-2 | Sesión de A (con correo); existe B | Postulación o `POST /api/clientes` con el id, correo o RUT de B | 400: general si trae `id` (clave desconocida); en el campo correo si trae un correo (A ya tiene uno); CA-11.3 si trae el RUT de B. A y B no cambian | Seguridad | Alta | E13† |
| PI-293 | Regla general (no confiar en el rol del cliente); ADR-013, Enmienda E-2 | Sesión de un cliente | Cuerpo con `rol=curatoria`; cabecera con `rol: curatoria` | Cuerpo: 400 general. Cabecera: sin efecto. En ambos casos sus roles no cambian | Seguridad | Alta | E13† |

## 2. Resumen de cobertura por requisito

| Requisito | Pruebas | Situación |
|---|---|---|
| RF-01 / HU-01 | PI-001 a PI-014, PI-050 a PI-054, PI-090 a PI-100 | Casi todo ejecutable con una comuna de prueba. Lo que prueba la comuna (CA-01.1, CA-01.2, lista cerrada, coherencia) está bloqueado por ADR-012 |
| CA-01.1 / CA-01.2 | PI-007, PI-009, PI-100 | Bloqueados por ADR-012 |
| RF-02 | PI-190 a PI-206 | Ejecutable con las rutas de la propuesta. Rotación de sesión y cookies: ADR-005 |
| RF-03 / HU-11 | PI-020 a PI-046, PI-080 a PI-086, PI-281 | Ejecutable. Faltan casos límite de formato (HQ-12) |
| CA-11.3 | PI-024, PI-025, PI-072, PI-082, PI-281 | Ejecutable. CA-11.1 y CA-11.2 son del S2 |
| RNF-05 | PI-170 a PI-176 | Ejecutable sin depender del algoritmo. Parámetros: ADR-004 |
| RNF-09 | PI-097, PI-250 a PI-252 | Expiración bloqueada por ADR-005. "El primer correo no exige reautenticación" es ejecutable. Reautenticación al cambiar correo o contraseña: fuera de alcance por decisión |
| RNF-10 / M-07 | PI-230 a PI-238 | Núcleo del informe (5 fallos en 15 min, mismo origen, nunca permanente) ejecutable. Duración, código, clave y tipos de intento: ADR-007 |
| RNF-15 | PI-002 a PI-006, PI-014, PI-030, PI-054, PI-063, PI-150, PI-153, PI-165, PI-194, PI-195, PI-197, PI-205, PI-206, PI-270, PI-271, PI-273 | Ejecutable en el backend. Formularios: espera al frontend |
| ADR-013: cuenta única y roles múltiples | PI-080 a PI-100, PI-110 a PI-118, PI-130 a PI-133 | Ejecutable, con los huecos de la sección 6 |
| ADR-013: unicidad y normalización | PI-050 a PI-066, PI-027, PI-045, PI-134, PI-280 a PI-283 | Ejecutable, salvo el correo fuera de ASCII (HQ-11) y los formatos raros del RUT (HQ-12) |
| ADR-013: no unión automática | PI-070 a PI-074, PI-290 a PI-292 | Ejecutable |
| ADR-013: política de contraseña | PI-150 a PI-166 | Ejecutable (ADR-013, Enmiendas E-4 y E-5) |
| ADR-006 | PI-011, PI-198 | Ejecutable |
| HU-25 (base) | PI-010, PI-074, PI-292, PI-293 | Ejecutable |

## 3. Pruebas bloqueadas

- **B-004 (hash)**: PI-173.
- **B-005 (sesiones)**: PI-202, PI-203, PI-250, PI-251 y la parte de expiración real de PI-291.
- **B-007 (limitador)**: PI-235, PI-237, PI-238, el código de respuesta de PI-230, cómo se determina el origen en PI-233 y si los 400 de PI-205 y PI-206 cuentan como intento fallido (ADR-007, punto 8).
- **B-012 (territorio)**: PI-007, PI-008, PI-009, PI-100. Las pruebas E13† dependen de ADR-012 solo en la forma de referenciar la comuna.
- **Pendientes de definición** (actualizado el 2026-09-27, sección 8.1): PI-044 (HQ-12) y PI-055 (HQ-11). PI-091 y PI-113 salieron por la conciliación de la sección 8. PI-028, PI-053, PI-063, PI-081, PI-116, PI-133, PI-158, PI-160, PI-162 y el código de login de PI-154 salieron por las decisiones del 2026-09-27.

## 4. Supuestos del plan

1. Se usan como nombres de trabajo las rutas `POST/DELETE /api/sesion`, `GET /api/cuenta` y `GET /api/sesion/csrf`, el comando `crear_usuario_administrativo` y el formato de error `{"mensaje", "errores": {campo: texto}}`, que solo aparecen en la propuesta del S1 (Borrador). `POST /api/clientes` y `POST /api/maestros/postulaciones` están en ADR-013, punto 2.
2. Nombres de campo: `nombre`, `telefono`, `correo`, `contrasena`, `rut`, `comuna`, `identificador`.
3. Las pruebas de integración usan PostgreSQL con pytest-django y el `pytest.ini` actual (`--reuse-db`). Las de concurrencia necesitan `transaction=True`: hay que confirmar que funcionan con `--reuse-db` y con el rol de BD sin superusuario.
4. Los RUT de ejemplo son valores de relleno convencionales. No se puede garantizar que no pertenezcan a una persona real; se declaran como ficticios en los fixtures.
5. PI-064 asume que un teléfono, al no tener "@", se interpreta como RUT, según la regla aprobada.

## 5. Fuera del alcance de este plan

CA-11.1 y CA-11.2 (S2); RNF-06, RNF-07 y RNF-08 salvo la base de autorización; RNF-11 y `acceso_denegado` (ADR-010 y ADR-011 en Borrador); RNF-12, RNF-23 y RNF-24 (infraestructura); RNF-14 y la usabilidad del frontend; los flujos de recuperación de contraseña y de verificación de correo (solo existe la prueba negativa PI-252).

## 6. Huecos en la documentación (señalados por QA, no resueltos)

- **HQ-01**: ADR-013 y el README seguían en Borrador al preparar el plan. Ver sección 8.
- **HQ-02**: la propuesta del S1 definía `usuario.telefono` NOT NULL, pero la decisión permite NULL en cuentas solo administrativas. Ver sección 8.
- **HQ-03**: la propuesta del S1 no reflejaba el correo en `POST /api/clientes` con sesión ni el identificador del login. Ver sección 8.
- **HQ-04**: la reautenticación de RNF-09 al cambiar contraseña o correo queda sin evidencia porque esas funciones están fuera de alcance. Ese desplazamiento debe registrarse en la bitácora de alcance (§5.3.6) con fecha, motivo y autorización.
- **HQ-05**: una cuenta administrativa sin teléfono no puede agregar un perfil: el teléfono es obligatorio y el endpoint con sesión no lo recibe. **Cerrado el 2026-09-27 (sección 8.1).**
- **HQ-06**: qué pasa si un maestro con correo envía un correo distinto en `POST /api/clientes`. Ver sección 8. **Cerrado definitivamente el 2026-09-27 (sección 8.1).**
- **HQ-07**: qué pasa si llegan campos no esperados (teléfono, nombre, contraseña) en las peticiones con sesión: ignorarlos o 400. **Cerrado el 2026-09-27 (sección 8.1).**
- **HQ-08**: qué pasa si un maestro envía `correo=""` o solo espacios siendo el correo opcional: 400 o NULL. **Cerrado el 2026-09-27 (sección 8.1).**
- **HQ-09**: forma canónica del teléfono y sus reglas: prefijo, longitud, código de área de fijos, si se acepta sin `+56`. **Cerrado el 2026-09-27 (sección 8.1).**
- **HQ-10**: política de contraseña: cómo se cuentan los caracteres, si se normaliza Unicode, fuente/versión de la lista común y si distingue mayúsculas, si se permite una contraseña de solo espacios. **Cerrado el 2026-09-27 (sección 8.1).**
- **HQ-11**: correo "case-insensitive" fuera de ASCII (`lower` frente a `casefold`, IDN), qué espacios se recortan, gramática y largo máximo.
- **HQ-12**: formatos de entrada del RUT fuera de "con o sin puntos y guion": espacios, ceros a la izquierda, rango, dígitos Unicode, separadores alternativos.
- **HQ-13**: enumeración por correo duplicado en el registro. Ver sección 8.
- **HQ-14**: qué capa exige las invariantes entre tablas (rol <=> perfil; correo NULL implica perfil_maestro) y si hay CHECK de minúsculas o de cadena vacía en `usuario.correo`. **Cerrado el 2026-09-27 (sección 8.1).**
- **HQ-15**: si el comando puede asignar los roles `cliente` o `maestro`. Ver sección 8.
- **HQ-16**: qué responde el login con una contraseña de más de 128 caracteres (400 o 401), y si cuenta para RNF-10. **Cerrado el 2026-09-27 en cuanto a la respuesta (sección 8.1). Si cuenta para RNF-10 sigue en ADR-007 (punto 8).**
- **HQ-17**: si al registrarse se inicia sesión automáticamente. **Cerrado el 2026-09-27 (sección 8.1).**
- **HQ-18**: si la sesión expira a mitad de "agregar perfil", el usuario recibe un 400 por campos faltantes y no un mensaje que le indique iniciar sesión (RNF-15).
- **HQ-19**: "el RUT es identificador mientras exista perfil_maestro" solo es verificable en el caso trivial, porque ningún flujo del alcance elimina un `perfil_maestro`.

## 7. Siguiente paso recomendado

1. HQ-05, HQ-07 y HQ-14 quedaron resueltos el 2026-09-27 (sección 8.1).
2. El formato del teléfono (HQ-09) y la política de contraseña (HQ-10) quedaron fijados el 2026-09-27 (sección 8.1). Antes de fijar los datos de PI-159 y PI-166, se revisan contra la lista de `CommonPasswordValidator` de la versión de Django fijada.
3. Implementar primero las pruebas E13 y E13† de prioridad Alta (secciones B, C, D, F, G, I, J, K, P y Q). Las B-005 y B-007 se escriben con `xfail` o skip citando el ADR, sin fijar el comportamiento.

## 8. Conciliación con ADR-013 Aceptada (2026-09-27)

El plan se preparó antes de que ADR-013 quedara escrita en disco. Con el texto aceptado:

- **HQ-01, HQ-02, HQ-03**: resueltos. ADR-013 está Aceptada; la propuesta del S1 permite `telefono` NULL en cuentas exclusivamente administrativas, recibe el correo en `POST /api/clientes` con sesión cuando la cuenta no lo tiene y define el identificador del login.
- **HQ-06 → PI-091 pasa a E13†**: ADR-013, punto 7: "Si la cuenta ya tiene correo, esta operación no lo lee ni lo modifica". Resultado esperado: el correo sigue siendo X y la operación responde 201. Queda sujeto a lo que se decida en HQ-07.
- **HQ-13**: registrado como riesgo aceptado 4 en ADR-013.
- **HQ-15 → PI-113 pasa a E13-P**: la propuesta del S1 dice que el comando puede agregar un rol administrativo a un usuario existente y que "`cliente` y `maestro` solo nacen con su perfil".
- Siguen abiertos: HQ-04, HQ-05, HQ-07, HQ-08, HQ-09, HQ-10, HQ-11, HQ-12, HQ-14, HQ-16, HQ-17, HQ-18, HQ-19.

### 8.1 Decisiones del equipo de desarrollo (2026-09-27)

Fuente: ADR-013, sección "Enmiendas" (E-1 a E-8), y la propuesta del S1 (§3, §4, §6 y §8) actualizada. Esta subsección prevalece sobre la lista anterior.

- **HQ-05 → cerrado (E-1).** Con sesión, una cuenta sin teléfono lo entrega en la misma petición; se guarda en forma canónica en la misma transacción. PI-116 pasa de PD(HQ-05) a E13 / E13†. PI-065 precisa su entrada. Nuevas: PI-066 y PI-118.
- **HQ-06 → cerrado definitivamente (E-2).** PI-091 responde 400 en el campo correo; esto reemplaza el 201 anotado arriba.
- **HQ-07 → cerrado (E-2).** Campo conocido no permitido: 400 en el campo. Clave desconocida: 400 general. Nunca se ignoran campos. Cambian su resultado esperado PI-010, PI-074, PI-081 (pasa a E13†), PI-292 y PI-293. Nuevas: PI-014, PI-030, PI-206 y PI-273.
- **HQ-08 → cerrado (E-7).** PI-028 pasa a E13 con 400.
- **HQ-09 → cerrado (E-3).** PI-061 y PI-062 fijan el literal canónico. PI-063 pasa a E13. Nueva: PI-134.
- **HQ-10 → cerrado (E-4).** PI-158, PI-160 y PI-162 pasan a E13. Nuevas: PI-165 y PI-166.
- **HQ-14 → cerrado (E-6).** PI-053 y PI-133 pasan a E13. PI-046 y PI-132 pasan de E13-P a E13.
- **HQ-16 → cerrado en cuanto a la respuesta (E-5).** El código de login de PI-154 queda definido. Nueva: PI-205. Si esos 400 cuentan para RNF-10 sigue en **B-007** (ADR-007, punto 8).
- **HQ-17 → cerrado (E-8).** El registro no inicia sesión. Nuevas: PI-013 y PI-029.
- **RNF-15**: la interpretación de seguridad está en E-2; RNF-15 no cambia. La lista de texto prohibido de PI-270 también se aplica al 400 general.
- Siguen abiertos: HQ-04, HQ-11, HQ-12, HQ-18 y HQ-19, además de la parte de HQ-16 que depende de ADR-007.
