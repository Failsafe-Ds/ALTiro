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
- `login()` rota el token CSRF: el frontend debe volver a pedirlo después de iniciar sesión.

## Alternativas consideradas
- **Doble envío implementado a mano**: posible, pero innecesario si el framework ya lo trae.
