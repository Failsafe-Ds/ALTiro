# Propuesta de arquitectura — Sprint 1: identidad, roles y control de acceso

- Estado: **Borrador** — pendiente de revisión final del equipo.
- Fecha: 2026-09-27 (revisada el mismo día tras la revisión crítica de arquitectura).
- Alcance: RF-01 a RF-03, RNF-05 a RNF-12, RNF-23 y RNF-24 (informe §5.3.5).
- Fuente: `docs/informe-altiro.md` (§2.2, §2.8, §3.1, §3.3, §3.4, §4.1, §4.2.1, §4.2.2, §4.4.2, §5.3.5, §5.3.6, §6.1.2, §6.2).

> Las decisiones técnicas se detallan en ADR-001 a ADR-014. No incluye diseño de sprints posteriores, salvo puntos de extensión.
>
> **Estado de implementación (2026-09-28):** implementados RF-01, RF-02 y RF-03 (API y pantallas), el catálogo territorial (ADR-012), Argon2id (ADR-004), sesiones (ADR-005), el limitador (ADR-007), las rutas privadas por defecto (§5, punto 1), el formato de error común y el comando `crear_usuario_administrativo`. **Pendiente:** bitácora y `acceso_denegado` (ADR-010, Borrador), respuesta 403/404 y `obtener_autorizado` (ADR-011, Borrador), `@requiere_rol`, enlaces firmados (RNF-06 base), `assert_campos_ausentes` (RNF-08 base), la prueba de control de RNF-07 y la reautenticación (§2.1). Diferencias con este documento: `POST /api/clientes` recibe solo `comuna` (ADR-012, «Decisión»); `intento_autenticacion` guarda `(origen, clave, fecha)` solo de fallos (ADR-007); no se agregaron `activo`, `creado_en` ni `asignado_en` (decisión del equipo).

---

## 1. Alcance y trazabilidad

### 1.1 Requerimientos funcionales

| ID | Texto del informe | Criterio de verificación | HU | Criterios de aceptación |
|---|---|---|---|---|
| RF-01 | "El sistema debe permitir el registro de un cliente con nombre, teléfono, correo y ubicación expresada como región, provincia y comuna" | "El registro falla si falta comuna; la comuna proviene de una lista cerrada" | HU-01 | CA-01.1, CA-01.2 |
| RF-02 | "El sistema debe autenticar usuarios mediante credenciales y permitir el cierre de sesión" | "Un usuario no autenticado no accede a ninguna vista privada" | HU-01, HU-25 | CA-25.3 (CA-25.1 y CA-25.2 dependen de objetos de S2 y S4) |
| RF-03 | "El sistema debe permitir al maestro postular en pasos, registrando RUT, nombres y teléfono" | "El RUT se valida con su dígito verificador y es único" | HU-11 | CA-11.3 (CA-11.1 y CA-11.2 dependen de RNF-20 y RF-04, de S2) |

### 1.2 Requerimientos no funcionales

| ID | Umbral del informe | Entrega en S1 |
|---|---|---|
| RNF-05 | "Ninguna contraseña se puede recuperar desde la base de datos, porque se almacena mediante un hash adaptativo diseñado para resistir ataques" | Completo |
| RNF-06 | "Guardados fuera de las carpetas accesibles desde internet y entregados con un enlace que caduca a los 10 minutos" | Solo la utilidad de enlace firmado y su prueba; volumen, descarga y evidencia final en S2 |
| RNF-07 | "cada pantalla o función que recibe un número de registro tiene una prueba automática que confirma que un tercero no puede abrirla" | Mecanismo centralizado y prueba de control; se cumple de forma acumulativa |
| RNF-08 | "Esos datos no se envían al dispositivo del maestro, y se comprueba revisando lo que el servidor manda y no lo que la pantalla muestra" | Patrón de serialización; evidencia final en S4 |
| RNF-09 | La sesión debe expirar por inactividad. Umbral: "Expiración a los 30 minutos; Reautenticación al cambiar contraseña o correo" | Expiración: completo. Reautenticación: **pendiente de decisión de alcance** (§2.1) |
| RNF-10 | "Bloqueo temporal tras 5 intentos fallidos en 15 minutos desde el mismo lugar" | Completo, sujeto a cerrar ADR-007 |
| RNF-11 | "El sistema no ofrece ninguna forma de editar ni borrar una entrada de la bitácora" | Completo como infraestructura. La bitácora se usa desde S2 (CA-19.3) y RF-37 se completa en S5 |
| RNF-12 | "Conexión cifrada obligatoria, y en la demostración local con un certificado propio declarado como tal" | Completo |
| RNF-23 | "Un solo comando deja el sistema andando en 10 minutos o menos, con las instrucciones escritas junto al código" | Completo |
| RNF-24 | "Contraseñas, rutas y ajustes guardados fuera del código, de modo que cambiar de servidor no obligue a reprogramar" | Completo |

**Adelanto de RNF-27** (planificado para S5): se fijan versiones exactas desde S1 y se realiza y registra la revisión de avisos de seguridad de dependencias al inicio de cada sprint, como exige su umbral. Respaldo: R-07.

### 1.3 Trazabilidad (§4.4.2)

- NTI-09 → HU-01, HU-25 → RF-01, RF-02, RF-17, RNF-05 a RNF-12, RNF-26, RNF-27 → CA-01.1, CA-01.2, CA-25.1 a CA-25.3.
- NTI-01 → HU-11 → RF-03, RNF-06.
- NTI-12 → HU-19 → RF-37, RNF-11, RNF-22 → CA-19.3.
- RNF-23 y RNF-24: restricción del equipo, controlados en la Definición de Hecho.

### 1.4 Riesgos y medidas del informe

- Riesgos (§6.1.2): R-01 y R-05 (RNF-07), R-03 (RNF-05, RNF-10), R-06 (RNF-24), R-07 (RNF-27), R-10 (RNF-11), R-11 (RNF-12).
- Medidas (§6.2):
  - M-03: "La bitácora registra acciones sobre expedientes, no actividad general de la persona".
  - M-07: bloqueo "temporal y asociado al origen del intento, nunca deshabilitación permanente de la cuenta".
  - M-08: "Retención acotada del registro y prohibición de usarlo para decisiones automáticas sobre una persona".

### 1.5 Registros pendientes en la bitácora de alcance (§5.3.6)

Estos puntos deben registrarse con fecha, motivo y autorización (no se registran desde este documento):

1. RNF-06 y RNF-08 están asignados a S1, pero los objetos que protegen existen en S2 y S4. En S1 se entrega el mecanismo con sus pruebas base; la evidencia del umbral se cierra en S2 (RNF-06) y S4 (RNF-08).
2. La bitácora se usa desde S2 (CA-19.3), no solo desde S5.
3. La decisión sobre las funciones de cambio de contraseña y de correo (§2.1), si se aprueba alguna.

---

## 2. Preguntas de alcance y decisiones abiertas

Ninguno de los supuestos V-01 a V-05 bloquea el S1. V-02 afecta la urgencia de NTI-09, no el diseño; V-04 es relevante desde S2.

### 2.1 Cambio de contraseña y de correo (pregunta de alcance)

Ninguna HU ni RF pide cambiar la contraseña o el correo. Solo RNF-09 las presupone ("Reautenticación al cambiar contraseña o correo"). Un RNF establece una condición de calidad sobre una función; no crea la función. Por eso **esta propuesta no incluye endpoints de cambio de contraseña ni de correo**.

Opciones para decisión del equipo y del representante del producto:

| Opción | Descripción |
|---|---|
| A | Construir ambas funciones como derivadas de RNF-09, registradas como ampliación de alcance. |
| B | Construir solo el cambio de contraseña (única forma de rotar una contraseña comprometida, dado que no hay recuperación). |
| C | Construir solo un mecanismo de reautenticación reutilizable, probado sin funcionalidad visible. |
| D | No construir nada; la segunda mitad de RNF-09 queda sin evidencia demostrable. |

Hasta resolverlo, la segunda mitad de RNF-09 queda pendiente. ADR-013 (punto 7) registra que agregar el primer correo a una cuenta sin correo no es "cambiar correo" y no exige reautenticación, y que el cambio de correo y el de contraseña quedan fuera del alcance actual.

### 2.2 Otras decisiones abiertas

1. **Identificador de acceso y unicidad de datos de contacto** (ADR-013, puntos 1, 5 y 6): **decidido por el equipo (2026-09-27)**. Se inicia sesión con un único campo que acepta correo o RUT. El teléfono no es único ni credencial. El correo es único cuando existe y se guarda normalizado en minúsculas. La unicidad del RUT la exige el informe (RF-03).
2. **Persona con varios roles** (ADR-013, punto 2): **decidido por el equipo (2026-09-27)**. Una persona usa una sola cuenta con varios roles; cliente y maestro son perfiles del mismo usuario (ver §3 y §4). Sigue abierta la pregunta del maestro que se envía tickets a sí mismo, que debe resolverse antes de S4.
3. **Duración y semántica del bloqueo** (ADR-007).
4. **Política de contraseñas** (ADR-013, punto 3): **decidida por el equipo (2026-09-27)**. Es decisión del equipo, no requisito textual del informe. Los parámetros de Argon2id siguen en ADR-004.
5. **Alcance del catálogo territorial** (ADR-012).
6. **Recuperación de contraseña**: sin HU ni RF; fuera del alcance actual de la prueba de concepto (ADR-013, punto 10). Quien olvide su contraseña no tiene recuperación. Pregunta para la contraparte; no bloquea RF-01 a RF-03.
7. **Verificación del correo**: sin HU ni RF; fuera del alcance actual de la prueba de concepto (ADR-013, punto 10), con riesgo aceptado.
8. **Plazo de retención de `acceso_denegado`** (ADR-010, M-08).
9. **Interpretación de "bitácora" en CA-25.3** como registro de seguridad separado (ADR-010). Debe validarse con el representante del producto.
10. **Qué cuenta como "actividad" para la expiración de sesión** (ADR-005).
11. **Interpretación de "vista privada"** con frontend estático (ADR-002).
12. **Registro de la asignación de roles administrativos**: no exigido por RF-37 ni cubierto por M-03. Toda asignación (primer administrador y posteriores) se hace por comando de consola y nunca se registra con autor `sistema`. Si se decide registrarla, sería un registro de seguridad separado con autor declarado por quien ejecuta el comando (ADR-010).

---

## 3. Modelo de datos (solo S1)

### Catálogo territorial (lista cerrada, solo lectura)
- `region(codigo PK, nombre, orden)`
- `provincia(codigo PK, region_codigo FK NOT NULL, nombre)`, UNIQUE(region_codigo, nombre)
- `comuna(codigo PK, provincia_codigo FK NOT NULL, nombre)`, UNIQUE(provincia_codigo, nombre), índice en provincia_codigo
- Carga idempotente desde un CSV versionado. Fuente: BCN, división político-administrativa de Chile (§2.8), más la versión de los códigos CUT usados. Alcance pendiente (ADR-012). Sin endpoints de escritura.

### `usuario`
- Modelo propio basado en `AbstractBaseUser` sin `PermissionsMixin`, fijado en la primera migración (ADR-001).
- `id`, `nombre` (NOT NULL, no único; un solo campo para el "nombre" de RF-01 y los "nombres" de RF-03, compartido por todos los perfiles de la cuenta), `telefono` (varchar(12); NULL permitido solo en cuentas exclusivamente administrativas; no único; forma canónica `+56` seguida de 9 dígitos, con CHECK `^\+56[0-9]{9}$` cuando no es NULL; ADR-013, punto 6 y Enmienda E-3), `correo` (NULL = sin correo, nunca cadena vacía; sin espacios al inicio ni al final y en minúsculas; UNIQUE, que admite varios NULL, y CHECK de no vacío; sin CHECK de minúsculas, porque la normalización la garantiza el servicio; ADR-013, punto 5 y Enmienda E-6), `password` (hash), `activo`, `creado_en`, `ultimo_acceso`.
- Invariantes de identificadores y datos de contacto: ADR-013, punto 9. Las que cruzan tablas (por ejemplo, que `perfil_cliente` exige correo y teléfono en `usuario`) las garantiza el servicio dentro de la misma transacción.
- Sin campo "bloqueado": el bloqueo es por origen (M-07).

### `usuario_rol`
- `usuario_id` FK, `rol` (CHECK: `cliente`, `maestro`, `curatoria`, `comercial`, `moderacion`, `control_gestion`), `asignado_en`. UNIQUE(usuario_id, rol) (ADR-013, Enmienda E-6).
- N:M. Los roles administrativos múltiples tienen respaldo en §3.1 ("cuatro funciones administrativas que hoy recaen sobre las mismas dos personas"). Que una misma cuenta sea cliente y maestro es una decisión del equipo (ADR-013, punto 2): una persona, una cuenta; `cliente` y `maestro` son perfiles de esa cuenta.
- Invariante: rol `cliente` ⇔ fila en `perfil_cliente`; rol `maestro` ⇔ fila en `perfil_maestro`. Perfil y rol se crean en la misma transacción. Esta invariante y las demás que cruzan tablas las garantiza el servicio, no la BD (ADR-013, Enmienda E-6). Los roles administrativos (`curatoria`, `comercial`, `moderacion`, `control_gestion`) no tienen tabla de perfil: el informe no les asigna datos propios (§3.1) y sus datos de persona son los de `usuario`.
- Visitante = sin sesión; **no es un rol guardado** y no figura en el CHECK. Sistema = constante usada como autor en la bitácora solo para tareas automáticas (§3.1), no un usuario; una acción ejecutada por una persona nunca se registra como Sistema.
- Las políticas de autorización deciden por la **relación con el recurso**, no por el rol global ni por el perfil activo en la interfaz. Principio general (ADR-013, punto 2): un rol administrativo no exime de las reglas de conflicto de interés; la política deniega aunque el usuario tenga el rol.
- Punto de extensión para S2, con respaldo en el informe: un maestro no cambia el estado de su propio expediente aunque tenga el rol `curatoria` (regla de HU-19, "Ningún maestro se auto aprueba"; CA-19.4). Otras reglas de conflicto solo se agregan con respaldo en el informe o en una decisión documentada.

### `perfil_cliente` (RF-01)
- `usuario_id` PK/FK, `comuna_codigo` FK NOT NULL. El nombre vive en `usuario`.
- Región y provincia se derivan de la comuna; si el formulario las envía, el servidor verifica coherencia.

### `perfil_maestro` (RF-03, paso 1)
- `usuario_id` PK/FK, `rut` (normalizado sin puntos ni guion, DV en mayúscula, UNIQUE NOT NULL, CHECK de forma canónica `^[0-9]{1,8}[0-9K]$`; el dígito verificador lo valida el servicio; ADR-013, Enmienda E-6), `creado_en`. Los nombres viven en `usuario.nombre`.
- Punto de extensión: el expediente y sus documentos (S2) colgarán de aquí.

### Sesión
- Sesiones de Django en base de datos. No se agrega tabla auxiliar (ADR-005).

### `intento_autenticacion` (RNF-10)
- `id`, `origen` (inet), `exitoso`, `fecha`. Índice (origen, fecha). Clave de conteo pendiente de ADR-007.
- No guarda contraseña. No es la bitácora.

### `acceso_denegado` (CA-25.3) — separado de la bitácora administrativa
- `id`, `fecha`, `usuario_id` (sin borrado en cascada), `recurso` (método y ruta), `entidad`, `entidad_ref`.
- Solo registra denegaciones de **usuarios autenticados** cuando el recurso existe y la política lo deniega. No registra 401 anónimos.
- Solo inserción desde la aplicación; sin rutas de lectura, edición ni borrado en S1.
- Trigger que rechaza UPDATE y solo permite DELETE de filas con `fecha` anterior al plazo de retención (plazo pendiente, M-08).
- Ningún proceso automático (incluido el limitador) lee esta tabla para decidir sobre una persona (M-08).
- Detalle en ADR-010.

### `bitacora` (bitácora administrativa; RNF-11; usada desde S2 por CA-19.3; RF-37 en S5)
- `id`, `fecha`, `autor_tipo` (`usuario`/`sistema`), `autor_id` (NULL permitido, sin borrado en cascada), `accion`, `entidad`, `entidad_ref`, `valor_anterior` (jsonb), `valor_nuevo` (jsonb), `motivo`.
- Índices en (fecha), (entidad, entidad_ref), (autor_id).
- Trigger que rechaza UPDATE, DELETE y TRUNCATE. Sin purga.
- Alcance: acciones administrativas sobre expedientes, evaluaciones y catálogo (RF-37); no actividad general de la persona (M-03).

En S1 no hay estados de negocio; el ciclo del ticket llega en S4.

---

## 4. Endpoints

Formato de error común (sin trazas ni códigos internos):

```json
{"mensaje": "Revisa los campos marcados",
 "errores": {"comuna": "Elige tu comuna para continuar"}}
```

Toda ruta `/api/` es privada por defecto; las públicas se marcan con `@publica`. Todas las operaciones que cambian datos exigen CSRF.

**Campos permitidos** (ADR-013, Enmienda E-2). Cada endpoint y contexto acepta solo su lista. Nunca se ignoran campos inesperados, con o sin sesión.

| Endpoint y contexto | Campos permitidos |
|---|---|
| `POST /api/clientes`, sin sesión | `nombre`, `telefono`, `correo`, `contrasena`, `comuna` (y región/provincia si ADR-012 las admite) |
| `POST /api/clientes`, con sesión | `comuna` (y región/provincia si ADR-012 las admite); `correo` solo si `usuario.correo` es NULL, y entonces es obligatorio; `telefono` solo si `usuario.telefono` es NULL, y entonces es obligatorio |
| `POST /api/maestros/postulaciones`, sin sesión | `nombre`, `telefono`, `rut`, `contrasena`; `correo` opcional (ADR-013, Enmienda E-7) |
| `POST /api/maestros/postulaciones`, con sesión | `rut`; `telefono` solo si `usuario.telefono` es NULL, y entonces es obligatorio. No se admite `correo`: toda cuenta sin `perfil_maestro` ya tiene correo (ADR-013, invariante 2) |
| `POST /api/sesion` | `identificador`, `contrasena` |

- **Campo conocido** es el que figura en alguna de estas listas. Si llega en un contexto que no lo permite, se responde 400 con error en ese campo y acción correctiva (por ejemplo, quitar el dato). No se crea ni se modifica nada.
- **Clave desconocida**: 400 general (`mensaje`, sin entradas en `errores`) que indica que la solicitud contiene campos no permitidos, sin repetir las claves ni los valores recibidos. Se revisa antes que las validaciones de cada campo.
- Ningún error muestra nombres internos, SQL, trazas ni estructura sensible (interpretación de RNF-15 en ADR-013, Enmienda E-2).
- Los nombres de campo de esta tabla forman parte del contrato de la API.

| Método y ruta | Actor | Reglas | Respuestas |
|---|---|---|---|
| `GET /api/territorio/regiones` | Público | Solo lectura | 200 |
| `GET /api/territorio/regiones/{codigo}/comunas` | Público | Solo comunas de la región (CA-01.2); cada comuna incluye su provincia | 200 / 404 |
| `GET /api/sesion/csrf` | Público | Entrega cookie CSRF | 204 |
| `POST /api/clientes` (RF-01) | Visitante, o autenticado sin `perfil_cliente` | Nombre, teléfono y correo obligatorios (RF-01), guardados en `usuario`; comuna obligatoria y existente (CA-01.1); región/provincia coherentes; una transacción. **Sin sesión**: crea `usuario`, `perfil_cliente` y rol `cliente`; contraseña según ADR-013 (punto 3 y Enmienda E-4); correo normalizado y único (si ya existe: 400 en el campo correo); teléfono no único y en forma canónica (ADR-013, puntos 5 y 6; Enmienda E-3); no inicia sesión (Enmienda E-8). **Con sesión** (ADR-013, puntos 2 y 7; Enmiendas E-1 y E-2): agrega `perfil_cliente` y rol `cliente` a la misma cuenta; contraseña y nombre no se admiten (400 en el campo; se usan los de la cuenta); si la cuenta no tiene correo, la petición debe traerlo y se guarda en `usuario` con la misma normalización y unicidad, en la misma transacción que el perfil y el rol, sin reautenticación; si la cuenta ya tiene correo y la petición trae `correo`, 400 en el campo correo y no se modifica; si la cuenta no tiene teléfono, la petición debe traerlo (400 en el campo teléfono si falta) y se guarda en forma canónica en la misma transacción; si ya lo tiene y la petición trae `telefono`, 400 en el campo teléfono; si ya tiene `perfil_cliente`, 400 | 201 (sin sesión nueva) / 400 por campo o general |
| `POST /api/maestros/postulaciones` (RF-03) | Visitante, o autenticado sin `perfil_maestro` | RUT con DV módulo 11, normalizado; unicidad garantizada por la base; nombres y teléfono obligatorios (RF-03), guardados en `usuario` (`nombre`, `telefono`). **Sin sesión**: crea `usuario`, `perfil_maestro` y rol `maestro`; contraseña según ADR-013 (punto 3 y Enmienda E-4); teléfono en forma canónica (Enmienda E-3); correo opcional: si falta, queda NULL; si es válido, se normaliza y debe ser único; `""` o solo espacios: 400 en el campo correo (Enmienda E-7); no inicia sesión (Enmienda E-8). **Con sesión** (ADR-013, punto 2; Enmiendas E-1 y E-2): agrega `perfil_maestro` y rol `maestro` a la misma cuenta; contraseña, nombre y correo no se admiten (400 en el campo; se usan los de la cuenta); si la cuenta no tiene teléfono, la petición debe traerlo (400 en el campo teléfono si falta) y se guarda en forma canónica en la misma transacción; si ya lo tiene y la petición trae `telefono`, 400 en el campo teléfono; si ya tiene `perfil_maestro`, 400 | 201 (sin sesión nueva) / 400 "Ese RUT ya tiene una postulación" (CA-11.3) / 400 por campo o general |
| `POST /api/sesion` (RF-02) | Visitante | Campo único `identificador` (correo si contiene "@"; si no, RUT validado) más contraseña (ADR-013, punto 1); limitador (ADR-007); Argon2id; identificador inexistente o contraseña incorrecta: mismo 401 con el mismo mensaje genérico accionable; campo ausente o identificador con formato inválido: 400 por campo (ADR-013, punto 4); contraseña vacía o de más de 128 caracteres: 400 en el campo contraseña, antes de calcular el hash y sin aplicar el resto de la política de creación (ADR-013, Enmienda E-5); campo no permitido o clave desconocida: 400 (Enmienda E-2); rota ID de sesión | 200 / 400 / 401 / 429 |
| `DELETE /api/sesion` (RF-02) | Autenticado | Borra la sesión en el servidor | 204 |
| `GET /api/cuenta` | Autenticado | Solo datos propios, sin identificador en la ruta; campos explícitos | 200 / 401 |

**No incluidos**: cambio de contraseña y cambio de correo (pregunta de alcance, §2.1), ni edición del teléfono (ADR-013, Enmienda E-1). Ningún registro inicia sesión automáticamente (Enmienda E-8).

**Sin unión implícita de cuentas** (ADR-013, punto 2): el sistema nunca asocia un registro nuevo a una cuenta existente por coincidencia de teléfono, correo o RUT. Un segundo perfil solo se agrega con sesión iniciada, mediante los mismos endpoints de RF-01 y RF-03, que son `@publica` pero leen la sesión si existe.

**Registro por pasos**: el registro del cliente tiene más de 5 campos. RNF-14 (máximo 5 campos por paso) es de S2, pero la interfaz de registro debe diseñarse por pasos desde S1 para no rehacerla.

**Alta de administradores y asignación de roles administrativos**: solo por comando de consola `crear_usuario_administrativo`, sin API, tanto para el primer administrador como para las asignaciones posteriores (ninguna HU ni RF pide administrar roles desde la aplicación). La contraseña se pide con entrada oculta o se genera, nunca como argumento. Pide el nombre de la persona (`usuario.nombre` es NOT NULL) y, para una cuenta nueva exclusivamente administrativa, el correo (obligatorio, normalizado y único); el teléfono es opcional (ADR-013, punto 8). La contraseña cumple la política de ADR-013 (punto 3). Puede agregar un rol administrativo a un usuario existente; `cliente` y `maestro` solo nacen con su perfil. El alta o la asignación **no se registra en la bitácora administrativa**: no es una acción sobre expedientes, evaluaciones ni catálogo (RF-37, M-03). Tampoco se atribuye al actor Sistema, que solo ejecuta tareas programadas (§3.1): la ejecuta una persona con acceso al equipo, que la aplicación no puede identificar porque el comando no tiene sesión. Queda la fecha en `usuario_rol.asignado_en`. Registrar quién asigna roles es una pregunta abierta (§2.2, ADR-010).

---

## 5. Autorización centralizada

1. **Privado por defecto**: middleware que responde 401 en toda ruta `/api/` no marcada `@publica`; prueba de control que recorre todas las rutas y exime explícitamente las públicas.
2. **Rol**: decorador `@requiere_rol(...)`; el rol se lee de `usuario_rol`, nunca del cliente. Tener el rol es condición necesaria, no suficiente: la política del recurso (punto 3) puede denegar por la relación del usuario con el recurso, incluido un conflicto de interés (ADR-013, punto 2).
3. **Propiedad del recurso (IDOR)**: punto único `obtener_autorizado(consulta_base, ref, usuario, politica)`; políticas por recurso en `autorizacion/politicas.py` que combinan identidad, relación con el recurso, rol, estado y finalidad. Consultas filtradas por dueño cuando sea posible.
4. **Respuesta ante denegación** (ADR-011): **404** con mensaje neutro cuando el recurso existe pero es ajeno; **403** cuando falta el rol en una ruta cuya existencia no es secreta. Solo en el primer caso se inserta en `acceso_denegado`.
5. **Serialización con lista explícita de campos**; helper de prueba `assert_campos_ausentes` (base de RNF-08).
6. **Enlaces firmados (RNF-06, base)**: utilidad con `TimestampSigner`, `max_age=600`, carga útil ligada al documento y al usuario, con prueba de caducidad y alteración. El volumen `documentos` y el endpoint de descarga llegan en S2.
7. **Prueba de control de RNF-07**: falla si alguna ruta con identificador no tiene una prueba de acceso de terceros registrada.

---

## 6. Autenticación y transporte

- **Hash (RNF-05)**: Argon2id con parámetros explícitos compatibles con RNF-04 (ADR-004).
- **Política de contraseña**: 12 a 128 caracteres, sin reglas de composición, sin recorte ni expiración, con lista local de contraseñas comunes, que es la incluida en Django mediante `CommonPasswordValidator` (ADR-013, punto 3; decisión del equipo, no requisito textual del informe). Una contraseña formada solo por espacios es inválida; se permite Unicode sin normalizarlo; una secuencia Unicode que no puede procesarse responde 400, nunca 500; no se usan `NumericPasswordValidator` ni `UserAttributeSimilarityValidator` (Enmienda E-4). En el inicio de sesión solo se exige de 1 a 128 caracteres; el máximo se revisa antes de calcular el hash (Enmienda E-5).
- **Sesión (RNF-09)**: expiración por inactividad a los 30 minutos (definida por el informe), deslizante, configurable por entorno; cookies `Secure`, `HttpOnly`, `SameSite=Lax`; rotación del ID al iniciar sesión. Definición de "actividad" pendiente (ADR-005). El frontend, al recibir 401, avisa y conserva lo escrito, sin guardar nunca la contraseña.
- **Reautenticación (RNF-09)**: pendiente de la decisión de alcance (§2.1).
- **Limitación (RNF-10, M-07)**: ver ADR-007 (en borrador). Nunca se deshabilita la cuenta.
- **Hash señuelo**: el backend de autenticación de Django ejecuta el hasher aunque el usuario no exista; el backend propio debe conservar ese comportamiento. Beneficio limitado, porque el registro revela si un RUT ya existe (CA-11.3) y si un correo ya está registrado (unicidad del correo; riesgo aceptado en ADR-013).
- **CSRF**: activo, incluido el inicio de sesión (ADR-006).
- **TLS (RNF-12)**: Nginx en 443 con certificado autofirmado declarado como de demostración, con SAN configurable; puerto 80 solo redirige. **Sin HSTS en la configuración de demostración** (ADR-008). Cabeceras: CSP sin scripts inline, `X-Content-Type-Options`, `frame-ancestors 'none'`, `Referrer-Policy`.
- **Registros**: nunca contraseñas, cuerpos de login, tokens ni cookies.

---

## 7. Estructura propuesta

```
docker-compose.yml          # init, db, app, proxy; volúmenes datos_db, secretos, certificados; no depende de que exista .env
.env.example                # solo nombres y valores no secretos
.gitignore
.gitattributes              # *.sh text eol=lf
README.md                   # un comando: docker compose up -d --build (RNF-23); aviso de certificado autofirmado
infra/init/generar.sh       # secretos y certificado autofirmado (SAN configurable) si no existen
infra/proxy/nginx.conf      # publicado en 127.0.0.1 por defecto
backend/Dockerfile, backend/entrypoint.sh
backend/requirements.txt    # versiones exactas
backend/altiro/             # settings (todo desde entorno), urls
backend/territorio/
backend/identidad/          # modelos, validadores (rut, telefono, correo, identificador, contraseña), servicios (registro, autenticacion, limitador), vistas, comando crear_usuario_administrativo
backend/autorizacion/       # roles, decoradores, politicas, middleware, acceso, enlaces, acceso_denegado
backend/bitacora/           # modelo, servicio registrar, migración con trigger
backend/comun/              # respuestas, serializacion
backend/tests/
frontend/                   # index, ingresar, registro-cliente (por pasos), postulacion-maestro, cuenta; css/base.css; js/api.js, territorio.js, formulario.js
docs/decisions/
```

Solo el proxy publica puertos; `db` no. El volumen `documentos` se agrega en S2.

---

## 8. Pruebas y evidencia

**Unitarias**: RUT (DV válido incluida K/k, inválido, formatos, normalización); teléfono (forma canónica `+56` seguida de 9 dígitos; entrada con y sin `+56`; espacios, guiones y paréntesis eliminados; `56` sin `+` sin trato especial; 8 y 10 dígitos rechazados; móviles y fijos; ADR-013, Enmienda E-3); correo (espacios al inicio y al final, minúsculas, cadena vacía rechazada); identificador (con "@" es correo, sin "@" es RUT validado); política de contraseña (11 y 129 caracteres rechazados, 12 y 128 aceptados, espacios conservados sin recorte, contraseña común rechazada, contraseña formada solo por espacios rechazada, Unicode sin normalizar, secuencia Unicode no procesable con 400 y nunca 500; ADR-013, Enmienda E-4); políticas de autorización, incluido que tener un rol no anula una denegación por relación con el recurso (política de control sobre un recurso ficticio, porque el expediente llega en S2); limitador (según la semántica que fije ADR-007). La hora de las pruebas dependientes del tiempo sale de Python, no de `now()` de SQL (ADR-014).

**Integración**: CA-01.1; comuna inexistente; región incoherente; CA-01.2; CA-11.3 con distinto formato de RUT; carrera de dos registros simultáneos con el mismo RUT; login correcto y fallido; logout invalida la cookie. Cuenta única (ADR-013, punto 2):
- un cliente autenticado postula y su cuenta queda con los roles `cliente` y `maestro` sin crear otro `usuario`;
- un maestro autenticado agrega `perfil_cliente`;
- un segundo intento de agregar el mismo perfil responde 400;
- un registro sin sesión con datos de una cuenta existente nunca queda unido a ella;
- el rol y el perfil existen siempre juntos;
- una cuenta sin teléfono que agrega un perfil debe enviar el teléfono, que se guarda en la misma transacción que el perfil y el rol; una cuenta con teléfono que lo envía recibe 400 en el campo teléfono (ADR-013, Enmienda E-1).

Identificador y datos de contacto (ADR-013):
- una cuenta con correo y `perfil_maestro` inicia sesión con el correo (en cualquier combinación de mayúsculas) y con el RUT (con o sin puntos y guion), y ambos resuelven a la misma cuenta;
- identificador inexistente y contraseña incorrecta responden el mismo 401 con el mismo mensaje; identificador ausente o RUT inválido responden 400 por campo;
- un registro con un correo ya existente, escrito con otras mayúsculas, responde 400 y no crea nada; un registro con un teléfono ya existente crea otra cuenta sin unirla;
- un maestro sin correo que agrega `perfil_cliente` sin enviar correo recibe 400; con un correo ya usado recibe 400 y no se crean perfil, rol ni correo; con un correo libre se crean los tres en una transacción;
- un teléfono usado como identificador nunca inicia sesión;
- una cuenta exclusivamente administrativa sin correo no se puede crear;
- un maestro con correo que envía `correo` al agregar `perfil_cliente` recibe 400 en el campo correo y su correo no cambia (Enmienda E-2);
- un campo conocido no permitido en el contexto responde 400 en ese campo, y una clave desconocida responde 400 general sin repetirla (Enmienda E-2);
- una postulación con `correo=""` o solo espacios responde 400 en el campo correo (Enmienda E-7);
- un registro o una postulación exitosos responden 201 sin crear sesión (Enmienda E-8);
- el inicio de sesión con contraseña vacía o de más de 128 caracteres responde 400 sin invocar el hasher (Enmienda E-5).

| RNF | Prueba | Evidencia |
|---|---|---|
| RNF-05 | Hash empieza con `$argon2id$`; misma contraseña, hashes distintos | Consulta SQL en la Definición de Hecho |
| RNF-06 (base) | Token a los 601 s rechazado; token alterado rechazado | Se cierra en S2 |
| RNF-07 | Rutas privadas dan 401 sin sesión; toda ruta con identificador tiene prueba de terceros; IDOR sobre recurso ficticio inserta en `acceso_denegado` | Reporte pytest |
| RNF-08 (base) | `assert_campos_ausentes` sobre JSON crudo | Se cierra en S4 |
| RNF-09 | 29 min válida, 31 min 401; la actividad extiende la sesión | Reporte pytest. Reautenticación: según §2.1 |
| RNF-10 | Según la semántica de ADR-007; cuenta nunca inactiva | Reporte pytest |
| RNF-11 | No hay rutas de edición ni borrado de la bitácora; el panel de administración de Django no está instalado; el trigger rechaza UPDATE/DELETE/TRUNCATE en SQL crudo (defensa adicional) | Reporte pytest + captura psql |
| `acceso_denegado` | UPDATE rechazado; DELETE de filas dentro del plazo rechazado | Reporte pytest |
| RNF-12 | `http://` redirige a `https://`; cookies `Secure`; certificado autofirmado; no se emite `Strict-Transport-Security` en la demo | Script de verificación y captura |
| RNF-23 | — | Cronometrar en equipo limpio con Docker instalado (idealmente laboratorio), incluyendo descarga de imágenes: fecha, equipo, tiempo |
| RNF-24 | App no arranca sin secreto; host de BD cambiable solo por entorno | Búsqueda de secretos en el repositorio |
| RNF-27 (adelanto) | — | Registro de la revisión de avisos de dependencias al inicio del sprint |
| Registros | Logs de login sin la contraseña | pytest |

---

## 9. Riesgos

1. Planificación de RNF-06 y RNF-08 (ver §1.5).
2. Certificado autofirmado en Android: advertencias en pruebas móviles; considerar mkcert con SAN adecuado.
3. IP de origen: en la red del laboratorio, y posiblemente en Docker Desktop sobre Windows, varios usuarios pueden llegar con la misma IP. **A verificar el primer día** (ADR-007).
4. Sin recuperación de contraseña (fuera del alcance actual, ADR-013, punto 10), quien la olvide queda fuera del sistema en la práctica: un maestro no puede volver a postular con su RUT (CA-11.3) y un cliente no puede registrarse de nuevo con el mismo correo. Tampoco se verifica el correo: alguien puede registrar un correo que no controla (riesgo aceptado en ADR-013).
5. Catálogo territorial sin fuente versionada: CA-01.2 no sería verificable.
6. Curva de aprendizaje de Django (CP-10): es la decisión más cara de revertir.
7. Dependencias hacia adelante: S2 usa sesiones, `@requiere_rol`, `obtener_autorizado`, bitácora (CA-19.3), `acceso_denegado` y enlaces firmados; S4 usa la serialización explícita y el planificador (purga de `acceso_denegado`, limpieza de intentos); S5 usa la bitácora (RF-37) y RNF-22.
8. Con la cuenta única (ADR-013, punto 2) queda abierta la pregunta del maestro que se envía tickets a sí mismo. Debe resolverse antes de S4 (afecta a RF-17).
