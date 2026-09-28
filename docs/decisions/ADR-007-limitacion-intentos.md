# ADR-007 — Limitación de intentos de autenticación

- Estado: **Aceptada** — 2026-09-28, aprobada por el equipo de desarrollo (ver «Decisión»).
- Fecha: 2026-09-27
- Relacionado con: RNF-10, R-03, M-07, M-08

## Contexto
- RNF-10: "Bloqueo temporal tras 5 intentos fallidos en 15 minutos desde el mismo lugar".
- M-07 (§6.2): bloqueo "temporal y asociado al origen del intento, nunca deshabilitación permanente de la cuenta".
- M-08 (§6.2): "Retención acotada del registro y prohibición de usarlo para decisiones automáticas sobre una persona".
- El informe **no define la duración del bloqueo**.

## Propuesta base
- Tabla propia `intento_autenticacion(origen inet, exitoso, fecha)`.
- La IP la fija Nginx (`X-Real-IP`); la aplicación solo confía en esa cabecera si viene del proxy.
- Respuesta 429 con mensaje accionable mientras el origen esté bloqueado, aunque la contraseña sea correcta.
- Nunca se deshabilita la cuenta.
- El limitador **no lee** la tabla `acceso_denegado` (M-08).
- Las consultas de la ventana usan la hora de Python, no `now()` de SQL, para poder controlar el tiempo en las pruebas.

## Preguntas abiertas (bloquean la aprobación)
1. **Duración del bloqueo.** Opciones:
   - Ventana móvil: bloqueo mientras haya 5 o más fallos en los últimos 15 minutos. El desbloqueo ocurre 15 minutos después del **primer** fallo de la serie, no del último.
   - Duración fija: por ejemplo, 15 minutos desde el quinto fallo. Más fácil de explicar al usuario ("Espera N minutos") y de probar.
2. **Intentos rechazados con 429.** Propuesta: no cuentan como fallos; si contaran, el bloqueo se renovaría solo mientras alguien siga intentando.
3. **Inicio de sesión exitoso.** Definir si reinicia el contador del origen.
4. **Clave de conteo.** Solo IP, o el par (IP, HMAC del identificador normalizado: correo o RUT según ADR-013, punto 1) para la regla 5/15, complementado con un límite por IP más alto. En cualquier opción la clave incluye el origen (M-07, RNF-10) y el limitador nunca guarda el correo ni el RUT en claro (ADR-013). El par sigue asociado "al origen" (M-07) y evita el bloqueo colectivo.
5. **IP real.** En la red del laboratorio varios equipos pueden compartir IP. Además, en Docker Desktop sobre Windows el contenedor podría ver la IP del gateway de Docker y no la del cliente; en ese caso 5 fallos de cualquiera bloquearían a todos. **A verificar el primer día**, antes de implementar.
6. **Reautenticación.** Si se aprueba alguna función de cambio de contraseña o correo, sus fallos deberían contarse por cuenta y sesión, no solo por IP.
7. **Limpieza de registros.** S1 no tiene planificador de tareas: hacerla al insertar un intento o posponerla al planificador de S4. Definir el plazo.
8. **Respuestas 400.** Definir si un intento rechazado con 400 (campo ausente o identificador con formato inválido, ADR-013, punto 4) cuenta como fallo, y confirmar que el 401 sí cuenta.

## Verificación de la pregunta 5 (2026-09-28)
- Entorno: Windows 11, Docker Engine 29.8.0 (Docker Desktop), stack de `docker-compose.yml`, peticiones desde el mismo equipo a `https://127.0.0.1/`.
- Resultado: Nginx registra como origen `172.19.0.1` (gateway de la red de Docker), no la IP del cliente. Además, la plantilla de Nginx todavía no envía `X-Real-IP`.
- Consecuencia: en este entorno, una clave de conteo **solo por IP** agrupa a todos los clientes que entran por el host, y 5 fallos de cualquiera bloquearían a todos. No se verificó aún el acceso desde teléfonos de la red local (`ALTIRO_BIND_ADDR`). Este resultado favorece la opción del par (IP, HMAC del identificador) de la pregunta 4; la decisión sigue siendo del equipo.

## Alternativas consideradas
- **django-axes**: suma una dependencia.
- **Redis**: suma un contenedor.

## Decisión (2026-09-28)
Respuestas del equipo a las preguntas abiertas:
1. **Duración:** bloqueo fijo de 15 minutos contados desde el quinto fallo que ocurre dentro de 15 minutos.
2. **429:** los intentos rechazados por bloqueo no cuentan como fallos.
3. **Inicio de sesión exitoso:** no reinicia el contador.
4. **Clave de conteo:** el par (origen, HMAC del identificador normalizado) para la regla 5 en 15 minutos, más un tope por origen de 20 fallos en 15 minutos (bloqueo de 15 minutos desde el vigésimo fallo). El limitador no guarda el correo ni el RUT en claro.
5. **IP real:** Nginx envía `X-Real-IP`; la aplicación solo la usa si `ALTIRO_CONFIAR_X_REAL_IP=true` (solo se activa en `docker-compose.yml`, donde la aplicación solo es accesible desde el proxy por la red interna). Ver «Verificación de la pregunta 5».
6. **Reautenticación:** no aplica; no hay funciones de cambio de contraseña ni de correo.
7. **Limpieza:** al registrar un fallo se eliminan los registros de más de 24 horas.
8. **Respuestas 400:** no cuentan como fallo. El 401 sí cuenta.

Tabla `intento_autenticacion(origen, clave, fecha)`: solo guarda fallos 401. Nunca se deshabilita la cuenta (M-07) y el limitador no lee `acceso_denegado` (M-08).
