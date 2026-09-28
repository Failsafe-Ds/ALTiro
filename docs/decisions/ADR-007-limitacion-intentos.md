# ADR-007 — Limitación de intentos de autenticación

- Estado: **Borrador** — no aprobar hasta resolver las preguntas abiertas
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

## Alternativas consideradas
- **django-axes**: suma una dependencia.
- **Redis**: suma un contenedor.
