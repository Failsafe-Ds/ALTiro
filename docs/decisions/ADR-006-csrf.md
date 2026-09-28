# ADR-006 — Protección CSRF

- Estado: **Aceptada** — 2026-09-27, aprobada por el equipo.
- Fecha: 2026-09-27
- Relacionado con: RF-02, RNF-09

## Contexto
Las sesiones se basan en cookies (ADR-005), por lo que las operaciones que cambian datos necesitan protección CSRF. El informe no lo exige directamente; se deriva del uso de cookies.

## Decisión
Middleware CSRF de Django, con cookie y cabecera `X-CSRFToken` enviada desde `fetch`. Aplica también al inicio de sesión. `GET /api/sesion/csrf` entrega la cookie.

## Notas de implementación
- `CSRF_TRUSTED_ORIGINS` y `SECURE_PROXY_SSL_HEADER` se configuran por entorno, porque la aplicación está detrás de Nginx.
- La cookie CSRF no puede ser `HttpOnly` (el frontend debe leerla), o el token debe entregarse en el cuerpo de la respuesta.
- `login()` rota el token CSRF: el frontend debe volver a pedirlo después de iniciar sesión (ver Enmienda E-1).

## Alternativas consideradas
- **Doble envío implementado a mano**: posible, pero innecesario si el framework ya lo trae.

## Enmiendas

### E-1 — Señal de rechazo CSRF y un único reintento
- **Fecha:** 2026-09-28.
- **Motivo:** `frontend/js/api.js` reintentaba cualquier 403 suponiendo un token vencido. Desde ADR-011, un 403 también significa falta de rol, y reintentarlo duplica la fila en `acceso_denegado`. Análisis del agente `architect` del 2026-09-28.
- **Cambio:**
  - `comun.api.fallo_csrf` (CSRF_FAILURE_VIEW) agrega la cabecera de respuesta `AlTiro-Rechazo: csrf`. El cuerpo no cambia y no incluye el motivo interno. Ninguna otra respuesta lleva esa cabecera.
  - El cliente reintenta **una sola vez**, tras `GET /api/sesion/csrf`, y solo si se cumplen las tres condiciones: método distinto de GET, estado 403 y cabecera `AlTiro-Rechazo: csrf`. Ningún otro 403 se reintenta.
  - **Invariante:** `CsrfViewMiddleware` rechaza en `process_view`, antes de ejecutar la vista, así que un 403 con esa cabecera no tuvo efectos ni dejó registro. Si una ruta que cambia datos se exime de CSRF, esta garantía no le aplica.
- **Impacto:** la protección CSRF no cambia. Precisa la nota "el frontend debe volver a pedirlo después de iniciar sesión".
- **Aprobación:** equipo de desarrollo, 2026-09-28.
