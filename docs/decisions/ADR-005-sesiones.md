# ADR-005 — Manejo de sesiones

- Estado: **Aceptada** — 2026-09-28, aprobada por el equipo de desarrollo.
- Fecha: 2026-09-27
- Relacionado con: RF-02, RNF-09, RF-18

## Contexto
RNF-09: la sesión debe expirar por inactividad. Umbral: "Expiración a los 30 minutos; Reautenticación al cambiar contraseña o correo". RF-02 exige cierre de sesión.

La expiración por inactividad a los 30 minutos **la define el informe**; no es un supuesto.

## Decisión propuesta
- Sesiones del lado del servidor, guardadas en la base de datos (backend de sesiones de Django).
- Cookie `HttpOnly`, `Secure`, `SameSite=Lax`.
- Expiración por inactividad deslizante de 1800 s (`SESSION_COOKIE_AGE=1800`, `SESSION_SAVE_EVERY_REQUEST=True`), configurable por entorno. `SESSION_SAVE_EVERY_REQUEST` escribe en la base en cada petición; es aceptable a la escala de la prueba de concepto.
- Rotación del ID de sesión al iniciar sesión.
- No se agrega tabla auxiliar sesión–usuario: Django invalida las demás sesiones al cambiar la contraseña mediante `get_session_auth_hash()`. Si en el futuro se aprueba el cambio de correo, basta con sobrescribir ese método para incluirlo.

## Reautenticación
Depende de la pregunta de alcance sobre las funciones de cambio de contraseña y de correo (propuesta §2.1). En S1 no se incluyen endpoints de cambio. Agregar el primer correo a una cuenta sin correo (al sumar `perfil_cliente`) no se considera "cambiar correo" y no exige reautenticación (ADR-013, punto 7).

## Alternativas consideradas
- **JWT**: revocar al cerrar sesión o al cambiar la contraseña, y medir inactividad, es más complejo.

## Pendiente
- Definir qué cuenta como "actividad". Propuesta: solo peticiones iniciadas por el usuario. Si en S4 se agregan consultas periódicas de notificaciones (RF-18), no deben renovar la sesión, o la mantendrían viva indefinidamente.

## Decisión (2026-09-28)
Se aprueba la propuesta tal como está:
- Sesiones en base de datos (`django.contrib.sessions`), cookie `HttpOnly`, `Secure`, `SameSite=Lax`.
- Expiración deslizante por inactividad de 1800 s, configurable con `ALTIRO_SESION_INACTIVIDAD_SEGUNDOS`.
- Rotación del ID de sesión al iniciar sesión.
- **Actividad**: solo cuentan las peticiones iniciadas por el usuario. Hoy todas lo son; si en S4 se agregan consultas periódicas (RF-18), no deben renovar la sesión.
- Implementación: como `django.contrib.auth` no está instalada (ADR-001), el inicio y la verificación de la sesión los hace `identidad.sesion`, que guarda el id del usuario y `get_session_auth_hash()` en la sesión y la invalida si el hash deja de coincidir.
