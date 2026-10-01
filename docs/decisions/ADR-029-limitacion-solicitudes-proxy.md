# ADR-029 — Limitación de solicitudes en el proxy y endurecimiento de cabeceras

- Estado: **Borrador** (propuesta, 2026-10-01). Lo pidió el usuario el 2026-10-01 ("protege contra esos ataques típicos de mandar demasiadas solicitudes") y ya está implementado; falta que el equipo lo acepte.
- Relacionado con: RNF-10, RNF-02, RNF-01, RNF-15, RNF-20; R-03; ADR-007 (limitación de intentos), ADR-008 (proxy y HTTPS local), ADR-015 y ADR-021 (tamaños de subida); hallazgos B-1 a B-4 de la auditoría del frontend y del proxy.

## Contexto
La app limita los intentos **fallidos** de inicio de sesión por cuenta y origen (ADR-007) y los pedidos de recuperación (ADR-027). Nada limitaba el volumen de solicitudes en general: un solo origen podía inundar el registro, la recuperación o cualquier ruta de la API y ocupar los 2 workers de la app. La auditoría además observó: caché sin política explícita (B-1), redirección http→https con el `Host` de la petición (B-2), faltan `Permissions-Policy` y `Cross-Origin-Opener-Policy` (B-3) y enlaces de avisos validados con `startsWith` (B-4).

**Limitación conocida (ADR-007, cierre del S1):** en Docker Desktop todos los clientes del equipo anfitrión llegan al proxy con la IP del gateway (p. ej. `172.18.0.1`). Toda clave por IP agrupa a todas las personas que usan la demostración desde ese equipo; por eso los umbrales son holgados.

## Decisión
1. **Capa extra, no reemplazo.** El limitador de ADR-007 sigue igual y actúa primero en los casos que cubre. El proxy solo corta inundaciones.
2. **Zonas** (`infra/proxy/templates/default.conf.template`, clave `$binary_remote_addr`):

   | Zona | Dónde | Ritmo | Ráfaga sin espera | Por qué |
   |---|---|---|---|---|
   | `altiro_general` | todo el sitio (páginas, JS, CSS, API) | 100/s | 200 | La medición de RNF-01 (10 hilos de búsqueda) llega a ~53/s con 0 respuestas distintas de 200; una página con sus JS y CSS son ~12 solicitudes. Una inundación de un solo origen (cientos o miles por segundo) se corta. |
   | `altiro_estricta` | solo **POST** a `/api/sesion`, `/api/clientes`, `/api/maestros/postulaciones`, `/api/recuperacion`, `/api/recuperacion/contrasena` | 20/min | 30 | 10 personas tras la misma IP pueden ingresar o registrarse a la vez. La ráfaga (30) supera los 20 fallos por origen de ADR-007, así el bloqueo de la app (con su mensaje de minutos) sigue siendo el primero. Los GET usan clave vacía y no cuentan. |
   | `altiro_conexiones` (`limit_conn`) | todo el sitio | 50 solicitudes en curso por IP | — | Acota subidas lentas simultáneas o conexiones colgadas desde un origen; 10 personas cargando páginas o subiendo fotos quedan muy por debajo. |

3. **Conexiones lentas:** `client_header_timeout 10s`, `client_body_timeout 30s`, `send_timeout 30s` (entre lecturas o escrituras sucesivas, no el total: una foto de 8 MB con señal débil sigue mientras avance, RNF-20), `keepalive_timeout 30s` (15 s en el puerto 80), `reset_timedout_connection on`. `client_max_body_size 1m` explícito; se mantienen 17 MB en documentos y 9 MB en la foto (ADR-015, ADR-021).
4. **Respuesta 429:** `limit_req_status` y `limit_conn_status` 429.
   - `/api/`: JSON con el formato común `{mensaje, errores}`, `Retry-After: 30` y `Cache-Control: no-store`. El 429 propio de la app (ADR-007) pasa sin cambios.
   - Páginas: `frontend/errores/429.html`, en español y sin códigos.
   - `js/api.js` muestra el `mensaje` del cuerpo; si no se puede leer, arma uno con `Retry-After`.
5. **Registro sin datos personales:** el aviso de Nginx en `error_log` (que lleva IP, línea de petición con consulta y Referer) se baja a `info` y no se escribe. Los 429 se registran en `access_log` con un formato propio sin IP, agente ni consulta: `limitacion 429 "MÉTODO ruta" req=… conn=…` (`REJECTED` = proxy; `PASSED` = 429 de la app).
6. **Caché (B-1):** el frontend estático va con `Cache-Control: no-cache` (revalidación con ETag: 304 sin cuerpo si no cambió, RNF-02); los nombres de JS y CSS no llevan versión, por eso no hay `max-age`. Las páginas de error van con `no-store`. La API conserva la política de la app.
7. **Redirección http→https (B-2):** el destino solo conserva `localhost` y las IPv4 de loopback o de red privada (10/8, 172.16/12, 192.168/16; acceso desde teléfonos de la red local, ADR-008). Cualquier otro `Host` redirige a `localhost`. Sin variables nuevas en `docker-compose.yml`.
8. **Cabeceras (B-3):** en `altiro-cabeceras.inc` (incluido en el server y en cada location con `add_header` propio): las de ADR-008 más `Permissions-Policy` (cámara, micrófono, ubicación, pago, USB, captura de pantalla y sensores desactivados) y `Cross-Origin-Opener-Policy: same-origin`. La foto se toma con `<input type="file">`, que abre la cámara del sistema y no depende de esta política. La API oculta las mismas cabeceras de Django para no duplicarlas (`altiro-api.inc`).
9. **Enlaces de avisos y descargas (B-4):** `dom.enlaceInterno(valor, rutas)` usa `new URL(valor, location.origin)` y acepta solo mismo origen y ruta exacta en lista cerrada (`/buscar.html`, `/conversacion.html`). El nombre del CSV de `indicadores.js` se filtra a `[A-Za-z0-9._-]`.

## Consecuencias
- Con la NAT de Docker Desktop, una sola persona que haga más de 30 POST de ingreso o registro en poco tiempo frena a todas las del mismo equipo durante segundos (20 por minuto se recuperan). Es aceptable en la demostración; en un despliegue real la IP sería la de cada cliente.
- Si se vuelve a medir RNF-01 con más hilos o en un equipo mucho más rápido, podría superarse 100/s desde una sola IP: el script informaría respuestas distintas de 200. Ajustar el ritmo o medir desde la red interna.
- Verificación reproducible: `python infra/proxy/verificar_proxy.py` (cabeceras, 304, redirección, uso normal y ráfaga estricta).

## Preguntas abiertas para el equipo
1. ¿Los umbrales (100/s y 20/min) son aceptables o se prefieren otros?
2. ¿Se acepta `no-cache` para JS y CSS, o se versionan los nombres para usar `max-age` largo (mejor para RNF-02)?
