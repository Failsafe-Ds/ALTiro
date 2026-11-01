# ADR-013 — Identificador de acceso, unicidad de datos de contacto, roles múltiples y política de contraseña

- Estado: **Aceptada** — 2026-09-27, aprobada por el equipo de desarrollo.
- Fecha: 2026-09-27
- Relacionado con: RF-01, RF-02, RF-03, RF-17, RF-38, RNF-05, RNF-07, RNF-09, RNF-10, RNF-15, NTI-09, NTI-11, HU-01, HU-11, HU-19, HU-25, CA-01.1, CA-11.3, CA-19.4, M-07, R-03

## Contexto
- RF-02 habla de "credenciales" sin definirlas.
- RF-01 exige al cliente "nombre, teléfono, correo y ubicación". RF-03 exige al maestro "RUT, nombres y teléfono".
- §3.4 define para el maestro el "teléfono como identificador de contacto obligatorio y correo opcional". **El informe no dice que el teléfono sea único ni que sirva para iniciar sesión.**
- La única unicidad que exige el informe es la del RUT (RF-03).
- §3.1: "cuatro funciones administrativas que hoy recaen sobre las mismas dos personas".
- El informe no define política de contraseñas, recuperación de contraseña ni verificación del correo.
- RNF-09: "Expiración a los 30 minutos; Reautenticación al cambiar contraseña o correo". Ninguna HU ni RF pide cambiar la contraseña o el correo.
- RNF-15: "Todo mensaje de error debe indicar el campo afectado y la acción correctiva".
- M-07: bloqueo "temporal y asociado al origen del intento, nunca deshabilitación permanente de la cuenta".

Todas las decisiones de este ADR son **decisiones del equipo**, no reglas textuales del informe, salvo donde se cita el informe.

## 1. Identificador de acceso — decidido
1. El inicio de sesión (RF-02) usa **un único campo `identificador`** más la contraseña.
2. El identificador puede ser **correo o RUT**:
   - si contiene "@", se interpreta como correo y se normaliza como en el punto 5;
   - si no contiene "@", se interpreta como RUT, se normaliza como en `perfil_maestro` (sin puntos ni guion, DV en mayúscula) y debe pasar la validación del dígito verificador.
3. Correo y RUT de una misma persona resuelven a **la misma cuenta**. Una cuenta con `perfil_cliente` y `perfil_maestro` puede iniciar sesión con cualquiera de los identificadores que tenga asociados.
4. El RUT es identificador de acceso mientras exista `perfil_maestro` (en el alcance actual no hay ninguna operación que lo elimine).
5. **El teléfono no es identificador de acceso** ni credencial.
6. La resolución del identificador se hace en el backend de autenticación propio previsto en la propuesta del S1 (§6), conservando el hash señuelo cuando el identificador no existe.
7. Este ADR no define estados de cuenta ni de suspensión.

## 2. Persona con varios roles — decidido por el equipo (2026-09-27)

### Contexto
- §3.1 respalda varios roles **administrativos** en una persona ("cuatro funciones administrativas que hoy recaen sobre las mismas dos personas").
- El informe no dice si una persona puede ser **cliente y maestro** a la vez, ni lo prohíbe. Es una decisión del equipo, no una regla del informe.

### Decisión
1. **Una persona, una cuenta.** Un `usuario` puede tener varios roles (`usuario_rol`, N:M).
2. **Cliente y maestro son perfiles o capacidades del mismo usuario** (`perfil_cliente`, `perfil_maestro`), no cuentas separadas. El rol `cliente` existe si y solo si existe `perfil_cliente`, y el rol `maestro` si y solo si existe `perfil_maestro`. Perfil y rol se crean en la misma transacción. Los datos comunes de la persona (nombre, teléfono, correo) viven en `usuario`; cada perfil guarda solo lo propio: `perfil_cliente` la comuna (RF-01) y `perfil_maestro` el RUT (RF-03). Los roles administrativos no tienen perfil: el informe no les asigna datos propios (§3.1). El teléfono puede faltar solo en cuentas exclusivamente administrativas (punto 6).
3. **Visitante no es un rol guardado**: es la ausencia de sesión (§3.1: "sin cuenta"). Sistema tampoco es un usuario.
4. **El segundo perfil se agrega solo con sesión iniciada**, reutilizando los casos de uso de RF-01 y RF-03, sin endpoints nuevos:
   - `POST /api/maestros/postulaciones` (RF-03) con la sesión de un usuario sin `perfil_maestro` agrega `perfil_maestro` (RUT) y el rol `maestro` a la misma cuenta. Las reglas del RUT (dígito verificador, unicidad, CA-11.3) no cambian.
   - `POST /api/clientes` (RF-01) con la sesión de un usuario sin `perfil_cliente` agrega `perfil_cliente` (comuna) y el rol `cliente` a la misma cuenta.
   - En ambos casos, con sesión, la petición no recibe contraseña, teléfono ni nombre: se usan los de la cuenta. **Excepción:** si la cuenta no tiene correo, `POST /api/clientes` debe recibirlo (punto 7). Cambiar el teléfono de contacto, el nombre o un correo ya existente no forma parte de esta decisión. (Ver Enmiendas E-1 y E-2: teléfono cuando la cuenta no lo tiene y campos no permitidos.)
   - Si la cuenta ya tiene ese perfil, se responde 400 con mensaje accionable y no se crea nada.
   - Sin sesión, ambos endpoints siguen creando una cuenta nueva (ver Enmienda E-8). **El sistema nunca une cuentas** por coincidencia de teléfono, correo o RUT; un perfil solo se agrega a una cuenta existente mediante sesión autenticada.
5. **Un rol administrativo no exime de las reglas de conflicto de interés.** Principio general de las políticas: el rol habilita una función, pero la política evalúa además la relación del usuario con el recurso, y una relación de conflicto de interés deniega aunque el usuario tenga el rol.
   - Ejemplo respaldado por el informe: un maestro no cambia el estado de su propio expediente aunque tenga el rol `curatoria` (regla de HU-19, "Ningún maestro se auto aprueba"; CA-19.4).
   - Aquí no se definen otras reglas de conflicto concretas. Cada una debe tener respaldo en el informe o en una decisión documentada.
6. **La autorización sigue verificando en el servidor** identidad, rol, relación con el recurso, propiedad cuando corresponda y estado. HU-25: "La autorización verifica propiedad del recurso o una función administrativa justificada, no solo el rol".
   - En un ticket, la política decide por la relación (cliente o maestro **de ese ticket**), nunca por el rol global ni por el perfil activo en la interfaz. Por ejemplo, RF-17 se aplica a quien es maestro de ese ticket.

### Dependencias resueltas por este ADR
- Registro sin sesión con un correo ya usado por otra cuenta: 400 en el campo correo (punto 5). Con un teléfono ya usado: se crea otra cuenta, sin unirla (punto 6).
- Maestro sin correo que agrega el perfil de cliente: punto 7.
- Inicio de sesión de una cuenta con dos perfiles: punto 1.

### Alternativas consideradas
- Cuentas separadas por perfil: descartada por el equipo. Duplica credenciales.
- Prohibir ser cliente y maestro a la vez: descartada por el equipo.

## 3. Política de contraseña — decidida por el equipo
**Decisión del equipo para la prueba de concepto, no requisito textual del informe.** No se atribuye a ninguna norma externa.
- Largo mínimo: 12 caracteres. Largo máximo: 128 caracteres. Se cuentan caracteres, no bytes.
- Sin obligación de mayúsculas, minúsculas, números ni símbolos.
- Se permiten espacios y caracteres normales (ver Enmienda E-4).
- La contraseña **nunca se recorta** ni se modifica en silencio: no se eliminan espacios ni se trunca, ni al registrar ni al iniciar sesión. Si excede el máximo, el registro responde 400 con mensaje accionable en el campo contraseña.
- Sin expiración periódica.
- Se rechazan las contraseñas incluidas en una **lista local de contraseñas comunes**. Por decisión del equipo (2026-09-27), se usa la lista que Django trae incluida, mediante `CommonPasswordValidator`. Queda versionada con la versión de Django fijada en las dependencias (RNF-27). Esta decisión de implementación no cambia ninguna otra regla de este punto.
- No se usan servicios externos para comprobar contraseñas.
- La política se aplica al crear una contraseña (registro de cliente, postulación sin sesión, comando `crear_usuario_administrativo`). En el inicio de sesión solo se exige que el campo no esté vacío (ver Enmienda E-5).
- **Algoritmo y parámetros del hash no se deciden aquí**: siguen en ADR-004 (Argon2id y parámetros medidos con benchmark).

## 4. Mensajes de error de inicio de sesión
- Identificador inexistente y contraseña incorrecta: **mismo 401 y mismo mensaje genérico**, con acción correctiva, sin revelar cuál ocurrió (por ejemplo: "No pudimos iniciar sesión. Revisa tu correo o RUT y tu contraseña e inténtalo de nuevo").
- Campos obligatorios ausentes, o identificador con formato inválido (RUT con dígito verificador incorrecto, correo mal formado): **400 con error accionable por campo** (formato común de la propuesta del S1, §4). Ver también Enmiendas E-2 y E-5.
- El 401 genérico es una **excepción de seguridad acotada** respecto de la lectura literal de RNF-15 ("indicar el campo afectado"): se aplica solo al resultado de la verificación de credenciales, para no revelar qué dato es incorrecto. RNF-15 no cambia. Los mensajes nunca muestran códigos internos. (Ver Enmienda E-2: interpretación de RNF-15 para campos no permitidos.)
- El 429 del limitador y la forma en que el limitador trata los 400 y 401 se deciden en ADR-007.

## 5. Correo
- **Único entre cuentas cuando existe.** La comparación no distingue mayúsculas de minúsculas.
- Antes de guardar se eliminan los espacios al inicio y al final y se guarda en minúsculas. Esa misma normalización se aplica al buscarlo para iniciar sesión.
- `NULL` representa la ausencia de correo. **No se permite cadena vacía.** (Ver Enmienda E-7.)
- Implementación para la prueba de concepto: normalización antes de guardar más restricción `UNIQUE` sobre la columna ya normalizada. **No se usa `citext`.** Toda vía de escritura (registro, agregar perfil y comando de consola) pasa por la misma normalización. (Ver Enmienda E-6.)
- Registro con un correo ya existente: 400 en el campo correo, con acción correctiva (por ejemplo, iniciar sesión y agregar el perfil desde la cuenta). No se crea nada.
- **Nunca se unen cuentas** automáticamente por coincidencia de correo.
- Obligatorio para `perfil_cliente` (RF-01) y para las cuentas exclusivamente administrativas (punto 8). Opcional para el maestro (§3.4).

## 6. Teléfono
- **No es único ni es credencial.** Varias cuentas pueden tener el mismo teléfono (familias, números reasignados).
- Se aceptan móviles y fijos.
- Se guarda en una única representación canónica. El formato exacto aceptado lo fija el validador `telefono` con sus pruebas unitarias (ver Enmienda E-3). No se usa ningún mecanismo externo de verificación.
- La verificación de que la persona es dueña del número queda **fuera de alcance**.
- Puede ser `NULL` en `usuario` solo si la cuenta es exclusivamente administrativa.
- Es obligatorio para crear `perfil_cliente` (RF-01) o `perfil_maestro` (RF-03). (Ver Enmienda E-1.)

## 7. Agregar el primer correo y RNF-09
- Si un usuario autenticado con `perfil_maestro` y sin correo ejecuta `POST /api/clientes` para agregar `perfil_cliente`, **debe entregar en esa misma petición el correo** que exige RF-01. Si falta, se responde 400 en el campo correo.
- El correo se guarda en `usuario` con la normalización y la unicidad del punto 5. Si ya pertenece a otra cuenta, se responde 400 y no se crea nada.
- La creación de `perfil_cliente`, la asignación del rol `cliente` y la actualización del correo en `usuario` forman **una sola operación atómica** (una transacción).
- Si la cuenta ya tiene correo, esta operación no lo lee ni lo modifica. (Ver Enmienda E-2.)
- No se crea un endpoint separado para "agregar correo" ni una función genérica de editar la cuenta. *(Enmendado por ADR-027, punto 2: `POST /api/cuenta/correo`, con reautenticación, cambia el correo o agrega el primero.)*
- **Interpretación de RNF-09:** agregar el primer correo a una cuenta con correo `NULL` **no es "cambiar correo"** y no exige reautenticación. Cambiar un correo ya existente es una operación distinta. *(Reemplazado por la Enmienda E-10: ahora exige la contraseña actual.)*
- Ninguna HU ni RF pide cambiar el correo ni la contraseña. **Ambas funciones quedan fuera del alcance actual** y no se diseñan endpoints para ellas. La evidencia de la segunda mitad de RNF-09 sigue dependiendo de la pregunta de alcance de la propuesta del S1 (§2.1).

## 8. Cuentas administrativas
- Una cuenta exclusivamente administrativa (roles `curatoria`, `comercial`, `moderacion` y `control_gestion`, sin `perfil_maestro`) **debe tener correo**, porque no tiene RUT con el que iniciar sesión.
- No necesita teléfono, salvo que además tenga `perfil_cliente` o `perfil_maestro`.
- No se crean perfiles administrativos adicionales.
- Se crean con el comando de consola `crear_usuario_administrativo` (propuesta del S1, §4), que aplica la normalización del correo y la política de contraseña.

## 9. Invariantes
1. Toda cuenta tiene al menos un identificador de acceso válido (correo, o RUT en `perfil_maestro`).
2. Una cuenta sin correo tiene `perfil_maestro` y, por lo tanto, RUT.
3. Una cuenta administrativa sin `perfil_maestro` tiene correo.
4. `perfil_cliente` exige correo y teléfono en `usuario`.
5. `perfil_maestro` exige RUT (en el perfil) y teléfono en `usuario`.
6. El correo es único entre cuentas cuando no es `NULL`; nunca es cadena vacía.
7. El RUT es único en `perfil_maestro`.
8. El teléfono no es único.
9. Rol `cliente` ⇔ `perfil_cliente`; rol `maestro` ⇔ `perfil_maestro`.
10. Nunca se unen cuentas automáticamente por coincidencia de correo, teléfono o RUT.

Cómo se garantizan:
- La base de datos garantiza la unicidad del correo y del RUT y que el correo no sea cadena vacía. (Ver Enmienda E-6.)
- Los invariantes 1 a 5 y 9 cruzan tablas (`usuario`, perfiles y `usuario_rol`), porque el teléfono y el correo pueden ser `NULL` en `usuario`. Son **invariantes del servicio**: se verifican dentro de la misma transacción en cada vía de creación (registro de cliente, postulación, agregar perfil con sesión y comando de consola).
- En el alcance actual ninguna operación elimina un correo, un teléfono ni un perfil, así que lo establecido al crearlos se mantiene.
- Cada vía de creación tiene pruebas automatizadas (RNF-21).

## 10. Fuera del alcance actual
> **Enmendado por ADR-027 (2026-09-30):** la recuperación de contraseña, el cambio de correo y el cambio de contraseña ya están dentro del alcance (DA-27). La verificación del correo sigue fuera.
- **Recuperación de contraseña**: ninguna HU ni RF la exige. No se crea endpoint ni flujo. Quien olvide su contraseña **no tendrá recuperación** dentro del alcance actual de la prueba de concepto. Se valida más adelante con la contraparte (por ejemplo, si procede un restablecimiento asistido por curatoría, planteado como pregunta, no como funcionalidad). **No bloquea RF-01, RF-02 ni RF-03.**
- **Verificación del correo**: ninguna HU ni RF la exige. No se implementa en el S1 ni en el alcance actual. No hay servicio de correo, token ni proveedor externo.
- **Cambio de correo y cambio de contraseña**: ver punto 7.
- **Verificación de la propiedad del teléfono**: ver punto 6.

## Alternativas descartadas
- **Teléfono único como identificador de acceso**: sin verificación por SMS, un tercero puede registrar un número ajeno y dejar fuera al dueño real. Además, hay teléfonos compartidos en familias y números reasignados por las operadoras, y el error de unicidad revelaría qué números tienen cuenta.
- **Acceso solo por correo**: por NTI-11, varios maestros no tienen correo.
- **Dos campos separados (correo y RUT) o un selector de tipo**: suma un paso sin necesidad. Un RUT nunca contiene "@", así que un solo campo basta.
- **`citext`**: suma una extensión. La normalización antes de guardar más `UNIQUE` basta y es más fácil de explicar y probar.
- **Reglas de composición y expiración periódica**: suman fricción para usuarios con baja alfabetización digital (NTI-11) sin un beneficio que el equipo haya podido justificar.
- **Servicio externo de contraseñas filtradas**: no se usan servicios externos y enviaría derivados de contraseñas a terceros.
- **Endpoint para agregar correo o función de editar cuenta**: no hay HU ni RF que lo pida.
- **Unir cuentas por coincidencia de correo, teléfono o RUT**: permitiría apropiarse de una cuenta ajena.

## Riesgos aceptados
1. **Correo sin verificar**: alguien puede registrar un correo que no controla. Como el correo es único, el dueño real no podrá registrarse con él, y el alcance actual no tiene forma de resolverlo dentro del sistema.
2. **Sin recuperación de contraseña**: quien la olvide queda fuera en la práctica. Un maestro no puede volver a postular con su RUT (CA-11.3) y un cliente no puede registrarse de nuevo con el mismo correo. Esto choca con el espíritu de M-07 ("nunca deshabilitación permanente de la cuenta").
3. **Sin cambio de contraseña**: una contraseña comprometida no se puede rotar desde la aplicación (propuesta del S1, §2.1).
4. **Enumeración en el registro**: el 400 por correo duplicado revela que ese correo tiene cuenta, y CA-11.3 revela que un RUT ya postuló (lo exige el informe). El inicio de sesión no lo revela (punto 4). Por eso el hash señuelo tiene un beneficio limitado.
5. **Minúsculas en todo el correo**: dos buzones que solo difieran en mayúsculas se tratan como uno.
6. **Lista local de contraseñas comunes**: se desactualiza si no se revisa junto con las dependencias (RNF-27).

## Dependencias
- **ADR-004** (Borrador): algoritmo y parámetros del hash (Argon2id, benchmark en el equipo de referencia). La política del punto 3 no depende de ellos. Una alternativa con límite de bytes (bcrypt, 72 bytes) no cubre 128 caracteres sin recorte.
- **ADR-005** (Borrador): sesiones. Agregar el primer correo no exige reautenticación (punto 7). *(Reemplazado por la Enmienda E-10.)* El registro no inicia sesión (ver Enmienda E-8).
- **ADR-007** (Borrador, no se cierra aquí): el limitador debe incluir en su clave el origen exigido por M-07 y RNF-10, y **no debe guardar el correo ni el RUT en claro**. La clave exacta, la ventana, la duración del bloqueo, el reinicio del contador y el tratamiento de los 400 y 401 se deciden en ADR-007.
- **Propuesta del S1, §2.1**: evidencia de la segunda mitad de RNF-09.
- **S2**: postulación (CA-11.1, el maestro debe volver a entrar), incluida la de un usuario ya autenticado como cliente (punto 2), y regla de no autoaprobación (CA-19.4).
- **S4**: RF-17 (cuándo se revela el teléfono) y la pregunta abierta del maestro que se envía tickets a sí mismo.
- **S5**: RF-38 (el archivo exportado no contiene RUT, nombre, teléfono ni dirección).

## Pendiente / preguntas abiertas
- **Maestro que se envía tickets a sí mismo** (punto 2): la cuenta única lo hace posible, pero no está definido si se permite. Debe resolverse antes de implementar el flujo del ticket (S4), porque si cliente y maestro del ticket son la misma persona, RF-17 pierde sentido.
- **Cuenta exclusivamente administrativa sin teléfono que agrega `perfil_cliente` o `perfil_maestro`**: con sesión, esos endpoints no reciben teléfono (punto 2), pero el perfil lo exige (punto 6). Mientras no se decida, el servicio responde 400 con mensaje accionable y no crea nada. Opción a evaluar: que la petición traiga el teléfono cuando la cuenta no lo tiene, igual que el correo en el punto 7. **Resuelto por la Enmienda E-1.**
- **Correo opcional en la postulación sin sesión** (§3.4): definir si el formulario de RF-03 lo pide. Si lo pide, se aplican las reglas del punto 5. **Resuelto por la Enmienda E-7.**
- **Recuperación de contraseña y verificación del correo**: preguntas para la contraparte (punto 10). No bloquean el S1.

## Enmiendas

Aclaraciones y refinamientos compatibles con las decisiones de este ADR, según la regla «Enmiendas y reemplazos» de `README.md`. El texto original de las secciones anteriores se conserva; las notas "(ver Enmienda E-x)" remiten aquí. Donde una enmienda precisa el texto original, prevalece la enmienda. Ninguna de estas enmiendas sustituye materialmente una decisión de este ADR, por lo que el estado sigue siendo **Aceptada**.

Origen común: huecos señalados por QA en `docs/testing/plan-identidad-sprint-1.md` (sección 6). Todas son **decisiones del equipo**, no reglas textuales del informe. No cambian ninguna HU, RF ni RNF.

### E-1 — Teléfono al agregar un perfil a una cuenta sin teléfono (HQ-05)
- **Fecha:** 2026-09-27.
- **Motivo:** una cuenta exclusivamente administrativa sin teléfono no podía agregar `perfil_cliente` ni `perfil_maestro`: el perfil exige teléfono (punto 6) y, con sesión, los endpoints no lo recibían (punto 2). Estaba en "Pendiente".
- **Cambio:**
  - Si una cuenta autenticada con `usuario.telefono` NULL agrega `perfil_cliente` (`POST /api/clientes`) o `perfil_maestro` (`POST /api/maestros/postulaciones`), la petición debe traer el teléfono. Si falta, responde 400 en el campo teléfono y no se crea nada.
  - El teléfono se normaliza según E-3 y se guarda en `usuario`. La creación del perfil, la asignación del rol y la actualización del usuario forman **una sola transacción**, igual que el correo en el punto 7.
  - Si `usuario.telefono` ya existe, el endpoint no lo modifica. Si la petición igual lo trae, se aplica E-2 (400 en el campo teléfono).
  - No se crea un endpoint de edición del teléfono.
- **Impacto:** resuelve el primer punto de "Pendiente" y amplía la excepción del punto 2.4, que antes solo cubría el correo. Los invariantes 4 y 5 del punto 9 no cambian. Afecta a los servicios `agregar_perfil_cliente` y `agregar_perfil_maestro`, a la propuesta del S1 (§4) y al plan de pruebas (PI-065, PI-066, PI-116, PI-118).
- **Aprobación:** equipo de desarrollo, 2026-09-27.

### E-2 — Campos permitidos por endpoint y contexto (HQ-07, HQ-06) e interpretación de RNF-15
- **Fecha:** 2026-09-27.
- **Motivo:** no estaba definido qué ocurre cuando llegan campos no esperados, por ejemplo teléfono, nombre, contraseña o un correo cuando la cuenta ya lo tiene. Ignorarlos en silencio oculta errores del usuario y facilita la asignación masiva.
- **Cambio:**
  - Cada endpoint y contexto (sin sesión o con sesión, y según los datos que ya tenga la cuenta) tiene una **lista explícita de campos permitidos**. Las listas están en la propuesta del S1, §4, y se derivan de este ADR:
    - con sesión no se admiten `contrasena` ni `nombre`;
    - `correo` y `telefono` solo se admiten si la cuenta no los tiene, y entonces son obligatorios donde el perfil los exige.
  - **Campo conocido pero no permitido en ese contexto:** 400 con error en ese campo y un mensaje accionable. No se crea ni se modifica nada.
  - **Clave desconocida:** 400 general que indica que la solicitud contiene campos no permitidos, sin error por campo y sin repetir las claves ni los valores recibidos.
  - Nunca se ignoran en silencio los campos inesperados. La regla se aplica con sesión y sin ella.
  - Consecuencia en el punto 7: si la cuenta ya tiene correo y la petición trae `correo`, se responde 400 en el campo correo. El correo **sigue sin modificarse**; lo que cambia es la respuesta, que ya no es 201.
- **Interpretación de RNF-15 (de seguridad; RNF-15 no cambia):**
  - El campo conocido no permitido se informa por campo.
  - La clave desconocida se informa con un error general, porque no corresponde a ningún campo que la persona pueda corregir en el formulario.
  - Ningún mensaje muestra nombres internos, SQL, trazas ni estructura sensible.
  - Es la segunda excepción acotada a la lectura literal de RNF-15 ("indicar el campo afectado"), junto con el 401 genérico del punto 4.
- **Impacto:** precisa los puntos 2.4 y 7. Cierra HQ-06 y HQ-07. Afecta a la propuesta del S1 (§4) y al plan de pruebas (PI-010, PI-014, PI-030, PI-066, PI-074, PI-081, PI-091, PI-206, PI-273, PI-292, PI-293).
- **Aprobación:** equipo de desarrollo, 2026-09-27.

### E-3 — Forma canónica del teléfono (HQ-09)
- **Fecha:** 2026-09-27.
- **Motivo:** el punto 6 delegaba el formato exacto al validador sin fijarlo.
- **Cambio:**
  - **Forma canónica:** `+56` seguido de exactamente 9 dígitos ASCII.
  - **Entrada:**
    - se aceptan espacios, guiones y paréntesis como caracteres de presentación y se eliminan antes de validar;
    - `+56` es opcional; si no viene, deben quedar exactamente 9 dígitos nacionales y se antepone `+56`;
    - el prefijo `56` sin "+" **no** recibe un trato especial: cuenta como dígitos del número, así que 11 dígitos se rechazan;
    - cualquier otra entrada responde 400 en el campo teléfono, con acción correctiva.
  - Se aceptan móviles y fijos. No se valida la propiedad del número ni se consultan servicios externos.
  - **Persistencia:** siempre `+56` seguido de 9 dígitos, con un CHECK en la base `^\+56[0-9]{9}$` cuando el teléfono no es NULL (E-6).
  - Es una regla estructural de la prueba de concepto, no una validación completa del plan de numeración chileno.
- **Impacto:** completa el punto 6. El validador `normalizar_telefono` deja de estar bloqueado. Plan de pruebas: PI-061, PI-062, PI-063 y PI-134.
- **Aprobación:** equipo de desarrollo, 2026-09-27.

### E-4 — Precisiones de la política de contraseña (HQ-10)
- **Fecha:** 2026-09-27.
- **Motivo:** el punto 3 no definía la contraseña formada solo por espacios, el tratamiento de Unicode ni qué validadores de Django se usan.
- **Cambio:**
  - Mínimo 12 y máximo 128 caracteres, contados como caracteres y no como bytes (punto 3).
  - Una contraseña formada **únicamente por espacios** es inválida.
  - Se permite Unicode. **No se normaliza** (ni NFC ni NFD) y la contraseña almacenada no se recorta ni se altera.
  - Si la contraseña contiene una secuencia Unicode que no puede procesarse correctamente, se responde 400 en el campo contraseña, **nunca 500**.
  - Validadores de Django:
    - se usa `CommonPasswordValidator`;
    - **no** se usan `NumericPasswordValidator` ni `UserAttributeSimilarityValidator`.
  - Los mensajes van en español y son accionables.
  - **Hecho de implementación, no regla adicional:** en Django 5.2.17, `CommonPasswordValidator` compara `password.lower().strip()` contra su lista. Por eso también rechaza una entrada de la lista escrita con otras mayúsculas o con espacios al borde. La contraseña guardada no se modifica.
  - El algoritmo y los parámetros del hash siguen en ADR-004.
- **Impacto:** precisa el punto 3. Plan de pruebas: PI-158, PI-160, PI-162, PI-165 y PI-166.
- **Aprobación:** equipo de desarrollo, 2026-09-27.

### E-5 — Contraseña en el inicio de sesión (HQ-16)
- **Fecha:** 2026-09-27.
- **Motivo:** el punto 3 solo exigía, en el inicio de sesión, que la contraseña no estuviera vacía, lo que permitía enviar al hasher entradas de tamaño arbitrario.
- **Cambio:** en `POST /api/sesion`:
  - contraseña vacía: 400 en el campo contraseña;
  - contraseña de más de 128 caracteres: 400 en el campo contraseña, **antes de calcular el hash**;
  - secuencia Unicode que no puede procesarse: 400, igual que en E-4.
  - Es un límite estructural de entrada: en el inicio de sesión no se vuelve a aplicar el resto de la política de creación. Una contraseña de 1 a 128 caracteres se verifica contra el hash normalmente, y si no coincide se responde el 401 genérico del punto 4.
  - Si estos 400 cuentan como intento fallido para RNF-10 se decide en ADR-007 (punto 8).
- **Impacto:** precisa el punto 3 (última viñeta) y el punto 4. Plan de pruebas: PI-154 y PI-205.
- **Aprobación:** equipo de desarrollo, 2026-09-27.

### E-6 — Qué garantiza la base de datos y qué garantiza el servicio (HQ-14)
- **Fecha:** 2026-09-27.
- **Motivo:** no estaba fijado en qué capa se exige cada invariante ni si existía un CHECK de minúsculas en el correo.
- **Cambio:**
  - **Base de datos:**
    - UNIQUE(correo), que admite varios NULL;
    - CHECK de que el correo no sea `''` cuando no es NULL;
    - UNIQUE(rut);
    - CHECK del RUT canónico `^[0-9]{1,8}[0-9K]$`;
    - CHECK del teléfono canónico `^\+56[0-9]{9}$` cuando existe;
    - UNIQUE(usuario_id, rol);
    - CHECK de los roles permitidos.
  - **No** se agrega un CHECK `correo = lower(correo)` ni se limita el correo a ASCII para poder crearlo.
  - **Servicio:**
    - normalización y validación del formato del correo;
    - normalización y dígito verificador del RUT;
    - normalización del teléfono;
    - rol `cliente` ⇔ `perfil_cliente` y rol `maestro` ⇔ `perfil_maestro`;
    - todos los invariantes que cruzan tablas (punto 9), dentro de la misma transacción.
- **Impacto:** precisa el punto 9 ("Cómo se garantizan") y la implementación del punto 5. Plan de pruebas: PI-046, PI-053, PI-132, PI-133 y PI-134.
- **Aprobación:** equipo de desarrollo, 2026-09-27.

### E-7 — Correo opcional en la postulación (HQ-08)
- **Fecha:** 2026-09-27.
- **Motivo:** el correo es opcional para el maestro (§3.4), pero no estaba definido qué hacer con una cadena vacía. Estaba en "Pendiente".
- **Cambio:** en RF-03 el correo es opcional:
  - campo ausente: el correo queda NULL;
  - correo válido: se normaliza y se guarda con las reglas del punto 5;
  - `correo=""` o solo espacios: 400 en el campo correo.
  - Nunca se transforma en silencio `""` en NULL.
- **Impacto:** resuelve el segundo punto de "Pendiente". Plan de pruebas: PI-028.
- **Aprobación:** equipo de desarrollo, 2026-09-27.

### E-8 — El registro no inicia sesión (HQ-17)
- **Fecha:** 2026-09-27.
- **Motivo:** no estaba definido si crear una cuenta inicia sesión automáticamente. Hacerlo acoplaría RF-01 y RF-03 a ADR-005 (Borrador).
- **Cambio:**
  - Crear una cuenta **no** inicia sesión. En RF-01 y RF-03 sin sesión, un registro exitoso responde 201 sin crear una sesión autenticada nueva.
  - La persona inicia sesión explícitamente mediante RF-02 (`POST /api/sesion`).
- **Impacto:** precisa el punto 2.4. La postulación por pasos del S2 (CA-11.1) deberá contar con este inicio de sesión explícito. Plan de pruebas: PI-013 y PI-029.
- **Aprobación:** equipo de desarrollo, 2026-09-27.

### E-9 — Un maestro no puede enviarse tickets a sí mismo (PROVISIONAL)
- **Fecha:** 2026-09-29. Opción recomendada, aplicada como provisional (`docs/Reanudar.md`).
- **Motivo:** cierra la pregunta abierta del punto 2 ("Maestro que se envía tickets a sí mismo"). Debía resolverse antes del S4.
- **Cambio:**
  - Se prohíbe con un CHECK `cliente_id <> perfil_maestro_id` en `ticket`, y la creación responde 400 con el mensaje "No puedes pedirte un trabajo a ti mismo".
  - Si cliente y maestro son la misma persona, RF-17 pierde sentido, se contamina la medición de NTI-10 y se abriría la autoevaluación (NTI-06).
- **Aprobación:** equipo de desarrollo (provisional), 2026-09-29.

### E-10 — El primer correo con el perfil de cliente exige la contraseña actual
- **Fecha:** 2026-10-31.
- **Motivo:** auditoría de seguridad `docs/testing/security-audit/run-1`, hallazgo 3.1 (severidad baja). Desde ADR-027 el correo sirve para recuperar la contraseña, así que agregar el primer correo ya no es un dato de contacto más: con solo una sesión prestada se podía fijar un correo ajeno, pedir el enlace por RUT y quedarse con la cuenta. La interpretación de RNF-09 del punto 7 es anterior a ADR-027.
- **Cambio (punto 7):**
  - si la cuenta no tiene correo, `POST /api/clientes` con sesión recibe también `contrasena` (la actual, sin recortar) y la verifica con la misma reautenticación y el mismo limitador que `POST /api/cuenta/correo` (RNF-09, RNF-10; ADR-027, punto 2);
  - correo y contraseña faltantes o mal formados se marcan juntos (RNF-15); una contraseña equivocada da 400 en `contrasena` y no se guarda nada; tras 5 fallos, 429;
  - cada intento que pasa el formato y la reautenticación cuenta en el tope de intentos de guardar un correo (ADR-027, E-2);
  - si la cuenta ya tiene correo, `contrasena` no debe venir: 400 en ese campo (E-2).
- **Se reemplaza:** la «Interpretación de RNF-09» del punto 7 (agregar el primer correo no exigía reautenticación) y la dependencia con ADR-005 que la repetía.
- **Pantalla:** «Mi cuenta», formulario para agregar el perfil de cliente: campo «Contraseña actual» junto al correo, visible solo cuando la cuenta no tiene correo; se vacía tras cada envío.
- **Aprobación:** corrección pedida a partir de la auditoría (2026-10-31); pendiente de ratificación del equipo de desarrollo.
