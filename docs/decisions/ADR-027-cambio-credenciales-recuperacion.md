# ADR-027 — Cambio de contraseña, cambio de correo y recuperación de contraseña

- Estado: **Aceptada** (2026-09-30, aprobó el equipo de desarrollo). Ampliación de alcance registrada en DA-27.
- Relacionado con: RNF-09, RNF-10, RNF-05, RNF-12, RNF-15, RNF-24, R-03, NTI-09, NTI-11; ADR-004, ADR-005, ADR-007, ADR-010, ADR-013 (puntos 7 y 10); P-11; DA-09, DA-27.

## Contexto
RNF-09 fija "Reautenticación al cambiar contraseña o correo", pero ninguna HU ni RF creaba esas funciones (DA-09, P-11, propuesta del S1 §2.1). ADR-013 (punto 10) dejaba también fuera la recuperación de contraseña: quien la olvidaba no tenía salida. El 2026-09-30 el equipo pidió construir las tres funciones (opción A de §2.1, más recuperación). Para la recuperación eligió un **buzón local más recuperación asistida**:
- el informe no admite servicios externos pagados en la prueba de concepto (CLAUDE.md §3);
- varios maestros no tienen correo (NTI-11, ADR-013).

## Decisión

### 1. Cambio de contraseña — `POST /api/cuenta/contrasena`
- Requiere sesión. Cuerpo: `{contrasena, contrasena_nueva}`.
- **Reautenticación (RNF-09):** `contrasena` es la contraseña actual. Si es incorrecta, responde 400 en `contrasena` ("La contraseña actual no es correcta…").
- **Limitación (RNF-10, ADR-007):** el fallo cuenta en el limitador con la clave `HMAC("cuenta:<id>")` y el origen. Bloqueado → 429 con el mismo texto y `Retry-After` que el inicio de sesión. Un 400 de formato no cuenta.
- La nueva pasa la política de ADR-013 (punto 3). Los errores van en `contrasena_nueva`. Si es igual a la actual → 400 ("Elige una contraseña distinta de la actual").
- **Efecto:**
  - se guarda con el hasher de ADR-004;
  - cambia `get_session_auth_hash()`, así que **todas las demás sesiones de la cuenta dejan de valer** (ADR-005);
  - la sesión actual se renueva con un ID nuevo y un token CSRF nuevo;
  - se anulan los enlaces de recuperación pendientes de la cuenta.
- Si la cuenta tiene correo, se envía un aviso al buzón (punto 4) sin datos sensibles.

### 2. Cambio de correo — `POST /api/cuenta/correo`
- Requiere sesión. Cuerpo: `{contrasena, correo}`.
- Reautenticación y limitación iguales a las del punto 1.
- `correo` se normaliza y debe ser único (ADR-013, punto 5). Si ya es el correo de la cuenta → 400 ("Ese ya es tu correo").
- **Enmienda a ADR-013, punto 7:**
  - también sirve para agregar el primer correo a una cuenta de maestro que no tenía, ahora con reautenticación, para poder recuperar la contraseña por correo;
  - quitar el correo no es posible (los invariantes de ADR-013, punto 9, se verifican igual);
  - la regla de `POST /api/clientes` (el correo entra con el perfil de cliente, sin reautenticación) no cambia. *(Reemplazado por la Enmienda E-2: también exige la contraseña actual.)*
- Si había un correo anterior, se le envía un aviso de cambio. La sesión sigue válida: el hash de sesión no depende del correo.
- No se verifica la propiedad del correo nuevo. Sigue fuera de alcance (ADR-013, punto 10), con riesgo aceptado.

### 3. Recuperación de contraseña
- **Pedir el enlace — `POST /api/recuperacion {identificador}`** (pública; correo o RUT, como el inicio de sesión):
  - **Siempre** responde 202 con el mismo mensaje, exista o no la cuenta y tenga o no correo. No revela qué cuentas existen. El mensaje orienta a quien no tiene correo hacia la recuperación asistida.
  - Si la cuenta existe y tiene correo:
    - se crea un token de 256 bits (`secrets.token_urlsafe(32)`) y se guarda solo su SHA-256;
    - vence a los `ALTIRO_RECUPERACION_MINUTOS` (30 por defecto) y es de un solo uso;
    - un token nuevo anula los anteriores sin usar de la misma cuenta;
    - el enlace se envía al buzón.
  - **Límites:**
    - por origen, 5 solicitudes en 15 minutos → 429 (cuentan también las de cuentas inexistentes, para que el 429 no revele nada);
    - por cuenta, 3 enlaces por hora: lo que pase de eso no se envía, con la misma respuesta 202.
  - Cada solicitud deja una fila en `solicitud_recuperacion` (origen, cuenta si existe, hash si hubo enlace). Las filas de más de 24 horas se borran al insertar (M-08).
- **Usar el enlace — `POST /api/recuperacion/contrasena {token, contrasena_nueva}`** (pública):
  - token inexistente, vencido, usado o anulado → 400 en `token`, con la acción "pide uno nuevo";
  - si es válido:
    - guarda la contraseña (política de ADR-013) y marca el token como usado;
    - anula los demás tokens de la cuenta;
    - cierra todas las sesiones por el cambio de hash;
    - avisa al correo de la cuenta.
  - **No inicia sesión** (coherente con ADR-013, E-8).
- **Enlace:** `<ALTIRO_URL_PUBLICA>/nueva-contrasena.html#t=<token>`. El token va en el **fragmento**:
  - el navegador no lo envía al servidor, así que no aparece en los registros del proxy ni en `Referer`;
  - la página lo lee, lo borra de la barra de direcciones con `history.replaceState` y lo envía en el cuerpo.
- **Recuperación asistida (maestros sin correo):**
  - el comando `python manage.py crear_enlace_recuperacion --cuenta <correo o RUT>` genera el mismo tipo de enlace (`via = asistida`) y lo muestra en la consola;
  - antes, quien lo ejecuta verifica la identidad de la persona fuera del sistema, por ejemplo con una llamada al teléfono registrado y preguntando el RUT;
  - después le hace llegar el enlace por el canal que usen hoy;
  - igual que `crear_usuario_administrativo` (ADR-010), no se escribe en la bitácora administrativa ni se atribuye al actor Sistema: queda un evento de aplicación con el id de la cuenta, sin token ni datos personales.

### 4. Buzón local (sin servicios externos)
- `EMAIL_BACKEND = django.core.mail.backends.filebased.EmailBackend`, que escribe cada correo como archivo en `ALTIRO_BUZON_DIR`. En la pila es el volumen `buzon`, montado solo en `app` con dueño 10001 y modo 0700, como `fotos`.
- Para leerlo en la demostración: `docker compose exec app sh -c 'ls -t /buzon | head -1 | xargs -I{} cat /buzon/{}'`.
- El buzón no se respalda (RNF-19 no lo exige; los enlaces vencen en 30 minutos).
- Pasar a un servidor SMTP real solo exige cambiar la configuración (RNF-24), no el código. Contratar un proveedor queda fuera de la prueba de concepto.
- Un error al escribir el correo no cambia la respuesta: se registra un ERROR sin datos personales ni token.

### 5. Lo que no se registra
- Ni tokens, ni contraseñas, ni correos en los registros (CLAUDE.md §8).
- La bitácora administrativa no registra estas acciones: son actividad de la propia persona sobre su cuenta, no acciones administrativas sobre expedientes (M-03, ADR-010).

## Alternativas consideradas
- **Mailpit en un contenedor:** se ve mejor en la demo, pero suma una imagen al stack. El equipo eligió el buzón de archivos.
- **Solo recuperación asistida:** no ofrece autoservicio a clientes y administradores, que sí tienen correo.
- **Token en la consulta (`?t=`):** quedaría en los registros del proxy y en el historial. Por eso va en el fragmento.
- **Contar las solicitudes de recuperación en `intento_autenticacion`:** bloquearía inicios de sesión legítimos del mismo origen. Se usa una tabla propia.

## Consecuencias
- RNF-09 queda con evidencia completa: expiración (S1) y reautenticación (este ADR). DA-09 se cierra y P-11 se responde con "A, más recuperación".
- **Riesgo aceptado:** la diferencia de tiempo de respuesta entre una cuenta con correo, que escribe un archivo, y una sin correo podría insinuar qué cuentas existen. En la prueba de concepto se acepta. Con un SMTP real, el envío debería ir a una cola.
- Quien controle el correo de una cuenta puede tomarla. Es el modelo habitual de recuperación y no tiene mitigación adicional en la prueba de concepto.

## Enmiendas

### E-1 — Carreras y tiempo de respuesta en la recuperación
- **Fecha:** 2026-10-01.
- **Motivo:** auditoría de seguridad, hallazgos B2 (enumeración de cuentas por el tiempo de respuesta, el riesgo aceptado en «Consecuencias») y B3 (dos solicitudes simultáneas podían superar los límites del punto 3 o dejar dos enlaces vigentes).
- **Cambio B3:** la solicitud toma, dentro de su transacción, un bloqueo consultivo de PostgreSQL por origen y después bloquea la fila del usuario (`select_for_update`), siempre en ese orden. Las solicitudes simultáneas del mismo origen o de la misma cuenta se ordenan: no se supera el tope de 5 por origen ni el de 3 enlaces por cuenta, y "un token nuevo anula los anteriores" se cumple también en paralelo. El enlace asistido bloquea la misma fila.
- **Cambio B2:** el correo del enlace se escribe en un hilo aparte, después de confirmar la transacción; la respuesta 202 no espera la escritura del archivo (ni, en el futuro, la de un SMTP). Las pruebas lo ejecutan en línea (`ALTIRO_CORREO_EN_SEGUNDO_PLANO=False` en `settings_pruebas`) para leer el buzón, y una prueba verifica el hilo.
- **Riesgo residual:** la cuenta existente con correo hace todavía algunas consultas más (bloqueo de la fila, anulación y creación del token), del orden de un milisegundo en la red interna, por debajo de la variación normal de una red móvil. Se acepta en la prueba de concepto. Un hilo que falla al escribir solo registra el error sin datos (punto 4).
- **Aprobación:** pendiente de ratificación del equipo de desarrollo; implementado a pedido del usuario el 2026-10-01.

### E-2 — Primer correo con reautenticación y tope de intentos de guardar un correo
- **Fecha:** 2026-10-31.
- **Motivo:** auditoría de seguridad `docs/testing/security-audit/run-1`, hallazgos 3.1 y 3.2 (severidad baja).
- **Cambio al punto 2 (primer correo):** se reemplaza la viñeta «la regla de `POST /api/clientes` (el correo entra con el perfil de cliente, sin reautenticación) no cambia». Ahora el primer correo que entra con el perfil de cliente también exige la contraseña actual, con la misma reautenticación y el mismo limitador (ADR-013, E-10).
- **Cambio al punto 2 (tope):** `POST /api/cuenta/correo` revela si un correo ya tiene cuenta («Este correo ya está registrado…»), como el registro (ADR-013, Riesgos aceptados 4), pero sin el tope de registros de ADR-007, E-1. Se agrega el ámbito `correo` de `identidad/frecuencia.py`:
  - claves por cuenta (`cuenta:<id>`) y por origen (`origen:<ip>`), 20 intentos por hora cada una, igual que el registro;
  - cuenta cada intento que pasa el formato del correo y la reautenticación, termine guardando o no; un 429 no cuenta en ninguna de las dos claves;
  - lo consumen `POST /api/cuenta/correo` y el primer correo de `POST /api/clientes`;
  - al superarlo: 429 con `Retry-After` y el mensaje «Intentaste guardar un correo varias veces seguidas…», sin decir si el correo tiene cuenta.
- **Proxy:** `/api/cuenta/correo` entra a la zona `altiro_estricta` (POST, 20/min por origen, ráfaga 30) en `infra/proxy/templates/default.conf.template`. La tabla de ADR-029, punto 2, no lo nombra todavía; ADR-029 sigue en Borrador.
- **Enumeración no eliminada:** responder igual exista o no la cuenta haría creer a la persona que su correo cambió cuando no cambió (RNF-15) y no cerraría la fuga, porque el registro ya la revela (CA-11.3; ADR-013, Riesgos aceptados 4). Queda acotada por el tope.
- **Aprobación:** corrección pedida a partir de la auditoría (2026-10-31); pendiente de ratificación del equipo de desarrollo.
