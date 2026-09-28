# Verificación de cierre — Sprint 1 (identidad, roles y control de acceso)

- Fecha: 2026-09-28
- Preparado por: agente `qa`
- Código verificado: rama `main`, commit `3a18002`, más la prueba nueva `backend/tests/test_qa_cierre_s1.py` (sin commit).
- Fuentes: `docs/informe-altiro.md` (§3.2, §3.3, §4.2.1, §4.2.2, §5.3.3, §5.3.5, §5.3.6), ADR-001 a ADR-014 (todas Aceptadas; se aplicaron sus secciones «Decisión» y «Enmiendas»), `docs/decisions/sprint-1-propuesta-arquitectura.md` (Borrador; §1.1, §1.2, §1.5, §8) y `docs/testing/plan-identidad-sprint-1.md`.

**Veredicto: listo con observaciones.** RF-01, RF-02 y RF-03, y los RNF que el S1 debe cerrar (RNF-05, la expiración de RNF-09, RNF-10, RNF-11, RNF-12 y RNF-24), cumplen con evidencia. No hay defectos críticos ni altos. Quedan tres defectos medios o bajos de interfaz, tres defectos bajos de registros, documentación y páginas de error, una observación sobre una fila manual en la bitácora, RNF-23 sin medir en un equipo limpio y los desplazamientos de alcance de la sección 6, que deben registrarse antes de cerrar el sprint.

---

## 1. Alcance verificado

| Tipo | Identificadores |
|---|---|
| RF | RF-01, RF-02, RF-03 |
| HU | HU-01, HU-11 (paso de identificación), HU-25 (base de autorización) |
| CA | CA-01.1, CA-01.2, CA-11.3, CA-25.1, CA-25.2, CA-25.3 |
| RNF del S1 | RNF-05 a RNF-12, RNF-23, RNF-24 |
| Revisión anticipada pedida (fuera del S1) | RNF-04 (S4), RNF-14 y RNF-15 (S2), solo en lo que toca a las pantallas del S1 |

Fuera de esta verificación: CA-11.1 y CA-11.2 (S2), RNF-13 y RNF-16 a RNF-21, y RNF-25 a RNF-27, salvo las notas de la sección 3.4.

## 2. Ambiente de prueba

| Dato | Valor |
|---|---|
| Equipo | Equipo de desarrollo, Windows 11 Pro 10.0.26200, 16 CPU lógicas, 15,56 GiB asignados a Docker |
| Docker | Docker Desktop, Engine 29.8.0, Compose v2 |
| Servicios | `init` (alpine 3.24.2), `db` (postgres:16.15-bookworm), `app` (python:3.13.15-slim-bookworm, Django 5.2.17, gunicorn 26.2.0 con 2 workers), `proxy` (nginx:1.30.5-alpine) |
| Levantado con | `docker compose up -d --build` (servicios sanos; `app` se recreó durante la verificación, sección 3.3) |
| Navegador | Chromium de `mcr.microsoft.com/playwright/python:v1.55.0-noble`, en la red `altiro_frontal`, con viewport de teléfono (390×844 y 320×640) |
| Datos | Solo ficticios (`@example.com`, RUT sintéticos, teléfonos `+56 9 1000 09xx`). En la base principal quedaron cuentas de prueba creadas por los recorridos (`qa.*@example.com`, `navegador*@example.com`) |

## 3. Pruebas ejecutadas

### 3.1 Automatizadas (pytest, pytest-django y time-machine; ADR-014)

| Ejecución | Resultado |
|---|---|
| `docker compose exec -T app pytest -q` (código de la imagen, commit `3a18002`) | **476 passed** en 45 s |
| Con el código montado, incluida `tests/test_qa_cierre_s1.py` | **482 passed** en 49 s |
| `tests/test_qa_cierre_s1.py`, 5 repeticiones (concurrencia) | 6 passed en las 5 |
| `manage.py makemigrations --check --dry-run` | Sin cambios pendientes |
| `manage.py check --deploy` | 3 avisos, todos justificados: W002 (sin `X-Frame-Options`; lo cubre `frame-ancestors 'none'` de la CSP en Nginx), W004 (sin HSTS, ADR-008), W008 (sin `SECURE_SSL_REDIRECT`; la redirección la hace Nginx) |

**Prueba nueva** (`backend/tests/test_qa_cierre_s1.py`): cubre cuatro casos de prioridad Alta del plan que no tenían prueba automatizada.
- PI-282: una cuenta con sesión y un visitante postulan a la vez con el mismo RUT.
- PI-283: dos maestros sin correo agregan `perfil_cliente` a la vez con el mismo correo.
- PI-291: sesión expirada a los 31 minutos, o cookie inválida, se trata como visitante y no se crea nada.
- PI-292: con sesión, no se opera sobre otra cuenta enviando su id, su correo o su RUT.

Todas pasan: no revelan defectos de backend.

### 3.2 Sobre el sistema levantado

| Verificación | Método |
|---|---|
| RNF-12 y cabeceras | `curl -sI http://127.0.0.1/…`, `curl -skI https://127.0.0.1/…` en 6 rutas, `openssl s_client`/`x509`, `nginx -T` |
| `X-Real-IP` | 2 inicios de sesión fallidos con `X-Real-IP: 203.0.113.77` y `X-Forwarded-For: 203.0.113.78`; lectura de `intento_autenticacion` con psql |
| Puertos | `docker inspect` (PortBindings), conexión TCP a 127.0.0.1:5432 y :8000, `docker network inspect altiro_interna` |
| RNF-24 | `git grep` de patrones de secreto, claves privadas y hex largos; revisión del historial (7 commits); `manage.py check` sin `DJANGO_SECRET_KEY_FILE`; host de BD por entorno |
| RNF-05 | Consulta SQL sobre `usuario` en la base principal |
| RNF-11 | psql sobre la base de pruebas `test_altiro`, dentro de una transacción revertida; estado de triggers en la base principal |
| RNF-09 y RF-02 | Inicio de sesión, `Set-Cookie`, cierre de sesión y reutilización de la cookie anterior con curl |
| RNF-10 | 6 fallos y luego la contraseña correcta desde el navegador (Playwright) |
| CA-01.2 | `GET /api/territorio/regiones` y `/regiones/{8,16}/comunas` |
| CA-11.3 | Postulación con el mismo RUT en tres formatos |
| RNF-15 (API) | 16 respuestas de error (CSRF, cuerpo no JSON, JSON mal formado, clave desconocida, tipos incorrectos, 404, 405, comuna, RUT, sustituto Unicode, cuerpos de 0,9 MB y 1,1 MB) |
| Pantallas | `flujo.py` (recorrido provisto) y `qa_ui.py` (QA): 320 px, objetivos táctiles, campos por paso, textos de error, registro con sesión, sesión terminada, cierre de sesión sin conexión, bloqueo por intentos |
| RNF-04 | `docker stats --no-stream` en reposo y durante 50 inicios de sesión con 10 simultáneos; `memory.peak` de cgroup v2 |
| Registros | `docker compose logs app proxy db` (2.983 líneas), búsqueda de contraseñas, cookies, tokens y hashes |

### 3.3 Acciones con efecto en el ambiente
- `docker compose build --no-cache init app` y `docker compose up -d --build --wait`: se recrearon las imágenes y el contenedor `app` (sin estado). No se borraron volúmenes, imágenes ni bases.
- Se insertaron filas en `intento_autenticacion` (fallos ficticios; se purgan a las 24 h, ADR-007) y cuentas ficticias en la base principal.
- La demostración de triggers se hizo en `test_altiro`, dentro de `BEGIN … ROLLBACK`. En la base principal no se intentó ningún UPDATE, DELETE ni TRUNCATE.

---

## 4. Resultados por requisito

Clasificación: PASS, FAIL, BLOCKED o NOT IN SCOPE. Para lo que el diseño cierra en un sprint posterior se usa «infraestructura preparada / evidencia final pendiente».

### 4.1 Requerimientos funcionales y criterios de aceptación

| Req. | Umbral o criterio del informe | Método y evidencia | Resultado |
|---|---|---|---|
| RF-01 (HU-01) | "El registro falla si falta comuna; la comuna proviene de una lista cerrada" | pytest PI-001 a PI-014, PI-050 a PI-054 y PI-090 a PI-100. En vivo: sin comuna, 400 `{"comuna": "Elige tu comuna para continuar."}`; comuna 99999, 400 `"Esa comuna no está en la lista…"`. Registro por pasos completo en Chromium | **PASS** |
| CA-01.1 | Sin comuna "el sistema impide guardar e indica que la comuna es obligatoria" | En la interfaz, "Continuar" sin región marca el campo ("Completa este dato."). En la API, 400 en el campo comuna | **PASS** |
| CA-01.2 | "Solo aparecen las comunas de esa región según la división político-administrativa oficial" | En vivo: 16 regiones; Biobío (8) 33 comunas y Ñuble (16) 21, ninguna de otra región. Códigos CUT 2018 v04, contrastados con dos fuentes (ADR-012) | **PASS**. Nota: sigue pendiente el cotejo manual de nombres con la planilla oficial (ADR-012, «Pendiente») y el alcance nacional es un supuesto a validar |
| RF-02 (HU-01, HU-25) | "Un usuario no autenticado no accede a ninguna vista privada" | pytest `test_toda_ruta_privada_responde_401_sin_sesion` (recorre todas las rutas), PI-190 a PI-206 y PI-291. En vivo: `/api/cuenta` sin sesión, 401; tras `DELETE /api/sesion` (204), la cookie anterior responde 401; `cuenta.html` sin sesión redirige a `ingresar.html?aviso=sesion` | **PASS**, con la interpretación de "vista privada" de ADR-002 (el HTML estático no trae datos). Ver DEF-QA-002 y DEF-QA-003 |
| RF-03 (HU-11) | "El RUT se valida con su dígito verificador y es único" | pytest PI-020 a PI-046, PI-080 a PI-086, PI-281 y PI-282. En la BD: UNIQUE `perfil_maestro_rut_unico` y CHECK de forma canónica. Postulación en 2 pasos | **PASS** |
| CA-11.3 | RUT ya registrado: "lo rechaza indicando que ese RUT ya tiene una postulación" | En vivo: `7.654.321-6` da 201; `76543216` y `7654321-6` dan 400 `"Ese RUT ya tiene una postulación. Si es tuyo, inicia sesión con tu RUT."` | **PASS** |
| CA-25.1 | Orden ajena por número de registro: acceso denegado | `obtener_autorizado` y 404 idéntico para lo ajeno y lo inexistente (`test_recurso_ajeno_responde_el_mismo_404…`) sobre el recurso ficticio `tests.recurso_prueba`. No existen órdenes (S4) | **infraestructura preparada / evidencia final pendiente (S4)** |
| CA-25.2 | Cliente que abre la cédula de un maestro: acceso denegado | Enlaces firmados y políticas base. No existen documentos (S2) | **infraestructura preparada / evidencia final pendiente (S2)** |
| CA-25.3 | "Queda en la bitácora con usuario, recurso y fecha" | `acceso_denegado` (usuario, método más patrón de la ruta, fecha). pytest: registro del 404 ajeno y del 403 por falta de rol; sin registro para 401 anónimos ni para 404 de referencias inexistentes; triggers de UPDATE, DELETE y TRUNCATE; purga a los 90 días | **BLOCKED: "Terminado sin validar"** (§5.3.3). Técnicamente verificado; falta que el representante del producto valide que el registro separado cumple "queda en la bitácora" (ADR-010, «Decisión», punto 1) |

### 4.2 Requerimientos no funcionales del S1

| RNF | Umbral exacto | Método, entorno y evidencia | Resultado |
|---|---|---|---|
| RNF-05 | "Ninguna contraseña se puede recuperar desde la base de datos, porque se almacena mediante un hash adaptativo diseñado para resistir ataques" | SQL en la base principal (9 usuarios): 0 hashes fuera de `argon2$argon2id$v=19$m=65536,t=3,p=1$`; 0 hashes repetidos; 0 contraseñas en claro. pytest PI-170 a PI-176 (incluye todas las columnas de texto de todas las tablas y los registros de la aplicación) | **PASS**. Ver DEF-QA-004 (el hash puede llegar a los registros de PostgreSQL) |
| RNF-06 | "Guardados fuera de las carpetas accesibles desde internet y entregados con un enlace que caduca a los 10 minutos" | `autorizacion/enlaces.py`: pytest acepta a los 600 s y rechaza a los 601 s; rechaza enlaces alterados, de otro usuario o con otra sal. El volumen `documentos` y la descarga llegan en S2 | **infraestructura preparada / evidencia final pendiente (S2)** |
| RNF-07 | "cada pantalla o función que recibe un número de registro tiene una prueba automática que confirma que un tercero no puede abrirla" | Prueba de control `test_toda_ruta_con_identificador_tiene_prueba_de_terceros_y_usa_uuid` (marca `terceros` y convertidor `uuid`). En S1 no hay rutas de negocio con identificador; las únicas exentas son las CUT públicas del territorio | **infraestructura preparada / evidencia final pendiente (acumulativo)** |
| RNF-08 | "Esos datos no se envían al dispositivo del maestro, y se comprueba revisando lo que el servidor manda y no lo que la pantalla muestra" | Utilidad `tests/privacidad.py` probada (claves anidadas, escapes Unicode, listas); serialización con lista explícita (`datos_cuenta`). No hay tickets (S4) | **infraestructura preparada / evidencia final pendiente (S4)** |
| RNF-09 (expiración) | "Expiración a los 30 minutos" | pytest PI-250 (válida a los 29 min, 401 a los 31), PI-251 (deslizante), PI-202 (rotación del ID), PI-203. En vivo: `Set-Cookie: sessionid=…; HttpOnly; Max-Age=1800; Path=/; SameSite=Lax; Secure` | **PASS** |
| RNF-09 (reautenticación) | "Reautenticación al cambiar contraseña o correo" | No existen funciones de cambio de contraseña ni de correo (PI-252: 404/405). Depende de la pregunta de alcance (propuesta §2.1) | **BLOCKED** (decisión de alcance pendiente) |
| RNF-10 | "Bloqueo temporal tras 5 intentos fallidos en 15 minutos desde el mismo lugar" | pytest PI-230 a PI-236 y los puntos 2, 3, 7 y 8 de ADR-007. En vivo, en Chromium: 6 fallos y luego la contraseña correcta dan "Hubo varios intentos fallidos. Por seguridad, espera 15 minutos e inténtalo de nuevo." (429 con `Retry-After`). El origen lo fija Nginx (sección 4.3) | **PASS** |
| RNF-11 | "El sistema no ofrece ninguna forma de editar ni borrar una entrada de la bitácora" | Barrera 1: sin rutas (`test_ninguna_ruta_de_la_api_expone_la_bitacora…`), sin panel de administración, ORM de solo inserción (pytest). Barrera 2: en psql sobre `test_altiro`, UPDATE, DELETE y TRUNCATE rechazados con `La bitácora no admite … (RNF-11)` (lo mismo en `acceso_denegado`); en la base principal los 4 triggers están habilitados (`tgenabled = O`). Barrera 3 no implementada (riesgo aceptado, ADR-010, punto 8) | **PASS**. Ver la observación OBS-01 |
| RNF-12 | "Conexión cifrada obligatoria, y en la demostración local con un certificado propio declarado como tal" | `http://127.0.0.1/cuenta.html?x=1` da `307` a `https://127.0.0.1:443/cuenta.html?x=1`. Certificado `O=CN=AlTiro demo local, autofirmado`, SAN `DNS:localhost, IP:127.0.0.1`, `CA:FALSE`, 365 días; curl sin `-k` lo rechaza. Solo TLSv1.2 y TLSv1.3 (`nginx -T`). `Strict-Transport-Security` ausente en 6 rutas (estáticas, API, 404). Cookies `sessionid` y `csrftoken` con `Secure`. El README declara el certificado | **PASS** |
| RNF-23 | "Un solo comando deja el sistema andando en 10 minutos o menos, con las instrucciones escritas junto al código" | Un solo comando y README presentes. Medición parcial en este equipo (no es un equipo limpio): `docker compose build --no-cache init app` en 14 s (con descarga de dependencias de pip); `docker compose up -d --build --wait` con caché en 10 s. Imágenes base por descargar en un equipo limpio: postgres 622 MB, python-slim 184 MB, nginx 93,6 MB y alpine | **BLOCKED**: exige equipo limpio. Procedimiento en la sección 7. Ver DEF-QA-005 |
| RNF-24 | "Contraseñas, rutas y ajustes guardados fuera del código, de modo que cambiar de servidor no obligue a reprogramar" | `git grep`: sin secretos, claves privadas ni certificados versionados (los únicos aciertos son la lectura de `*_FILE` en `10-rol-app.sh`); historial sin claves. En vivo: sin `DJANGO_SECRET_KEY_FILE`, `ImproperlyConfigured: Falta el secreto DJANGO_SECRET_KEY…` y código de salida 1; con `ALTIRO_DB_HOST=servidor-nuevo.example.com` y `ALTIRO_DB_PORT=6543` la configuración los toma sin cambiar código. pytest `test_la_aplicacion_no_arranca_si_falta_un_secreto` | **PASS** |

### 4.3 Otras verificaciones de infraestructura pedidas

| Verificación | Evidencia | Resultado |
|---|---|---|
| Cabeceras de seguridad (ADR-008) | En estáticos y API: `Content-Security-Policy` sin scripts inline y con `frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `server_tokens off` | **PASS** |
| Nginx sobrescribe `X-Real-IP` (ADR-007, punto 5) | Con `X-Real-IP: 203.0.113.77` enviado por el cliente, `intento_autenticacion.origen` quedó en `172.19.0.1` (la IP que ve Nginx). `X-Forwarded-For` no se usa | **PASS** |
| `db` y `app` sin puertos al host | `PortBindings` vacíos en `db` y `app`; 127.0.0.1:5432 y :8000 rechazan la conexión; red `altiro_interna` con `internal: true`; `proxy` publica solo en `127.0.0.1:80/443` | **PASS** |
| Rol de BD de la aplicación | `altiro_app`: sin superusuario, sin `CREATEROLE`, sin `BYPASSRLS`; `CREATEDB` solo para pytest | **PASS** (según el diseño documentado) |
| Registros de la aplicación | No aparecen contraseñas, cookies, tokens ni cuerpos de login en `app` ni `proxy` (se registra "Inicio de sesión correcto del usuario N") | **PASS**. En `db`, ver DEF-QA-004 |

### 4.4 Revisión anticipada (fuera del alcance del S1)

| RNF | Umbral | Hallazgo | Resultado |
|---|---|---|---|
| RNF-04 (S4) | "No más de 2 GB de memoria para todo el sistema" | En reposo: app 96 MiB, db 65 MiB y proxy 22 MiB (183 MiB). Máximo observado con 10 inicios de sesión simultáneos (Argon2id de 64 MiB; 50 peticiones, todas 200; p50 0,75 s y máximo 0,78 s): 218 + 68 + 27 = 313 MiB. Pico de cgroup desde el arranque (incluye una corrida de pytest y la caché de páginas de la BD): 286 + 216 + 35 = 536 MiB | **NOT IN SCOPE** (S4). Indicio favorable; la evidencia formal requiere el volumen de prueba del S4 |
| RNF-14 (S2) | "Botones de al menos 44 por 44 puntos y formularios divididos en pasos de máximo 5 campos" | A 320 px: sin desplazamiento lateral en las 5 páginas; ningún botón, campo, select ni casilla con etiqueta por debajo de 44 px; campos por paso: registro 3/2/1, postulación 3/2, ingreso 2, formularios de cuenta ≤ 4. Solo los enlaces dentro de texto ("Ingresa aquí", 91×21; "Ingresa con tu RUT", 141×21) quedan bajo 44 px; no son botones | **NOT IN SCOPE** (S2). Sin incumplimientos en lo revisado |
| RNF-15 (S2) | "Ningún mensaje muestra códigos internos ni texto de programador, y se revisa en todos los formularios" | API: las 16 respuestas probadas están en español, con campo y acción, sin texto prohibido (lista de PI-270). Pantallas: ningún texto prohibido en los errores observados. Hay mensajes no accionables en dos situaciones (DEF-QA-001, DEF-QA-002) y páginas de error técnicas fuera de los formularios (DEF-QA-006) | **NOT IN SCOPE** (S2). Defectos registrados para corregir antes del S2 |
| RNF-22 (S5) | "Cada entrada incluye nivel, marca de tiempo, usuario y operación" | El formato de registro incluye fecha, nivel y módulo; el usuario solo aparece en algunos eventos | **NOT IN SCOPE** (S5, parcial) |
| RNF-27 (S5; adelanto comprometido en la propuesta §1.2) | "Cada librería queda declarada con versión exacta y hay una revisión de avisos registrada al inicio de cada sprint" | Versiones exactas en `requirements*.txt` y en las etiquetas de imagen. No se encontró en `docs/` el registro de la revisión de avisos del inicio del S1 | **NOT IN SCOPE** (S5). Se recomienda registrar la revisión |

---

## 5. Defectos y observaciones

### DEF-QA-001 — Con sesión iniciada, los formularios de registro muestran un error no accionable
- **Afecta:** HU-01, HU-11, RNF-15 (revisión anticipada); ADR-013, Enmienda E-2 (el mensaje es correcto para la API, pero llega así a la persona).
- **Severidad:** media.
- **Precondición:** cuenta de cliente con sesión iniciada.
- **Pasos:** 1) ir a `/registro-cliente.html` (o a `/postulacion-maestro.html`); 2) completar todos los pasos; 3) enviar.
- **Esperado:** la pantalla indica que ya hay una sesión y cómo continuar (por ejemplo, agregar el perfil desde "Mi cuenta"), o no ofrece el formulario de visitante.
- **Observado:** vuelve al paso 1 con "Revisa los campos marcados." y, en nombre y correo (o contraseña), "Este dato no corresponde aquí: quítalo e inténtalo de nuevo.". La persona no puede quitar esos campos y no sabe qué hacer. No se crea ni se modifica nada (el backend se comporta según E-2).
- **Evidencia:** `qa_ui.py`, casos `[registro con sesión]` y `[postulación con sesión]`.
- **Área:** frontend (detectar la sesión con `GET /api/cuenta` y derivar a `cuenta.html`); revisión de `ux`.
- **Estado (2026-09-28): corregido en `6a10c27`.** Verificado en `docs/testing/saneamiento-sprint-1.md` (punto B).

### DEF-QA-002 — Si la sesión termina en "Mi cuenta", el error pide datos que no existen en la pantalla
- **Afecta:** RF-02, RNF-09, RNF-15; propuesta §6 ("El frontend, al recibir 401, avisa y conserva lo escrito"); hueco HQ-18 del plan, todavía abierto.
- **Severidad:** media.
- **Precondición:** sesión iniciada en `cuenta.html`, que luego expira (simulado borrando la cookie `sessionid`).
- **Pasos:** 1) escribir un RUT en "Quiero trabajar como maestro"; 2) pulsar "Postular".
- **Esperado:** aviso de que la sesión terminó y camino para volver a ingresar, conservando lo escrito.
- **Observado:** como `POST /api/maestros/postulaciones` es pública, el servidor trata la petición como de visitante y responde 400. La pantalla muestra "Revisa los campos marcados. Ingresa tu nombre. Ingresa una contraseña." y un error de teléfono en un campo oculto. No se crea nada (PI-291 pasa).
- **Evidencia:** `qa_ui.py`, caso `[sesión terminada, agregar maestro]`.
- **Área:** frontend (comprobar la sesión antes de enviar, o ante 400 con campos que el formulario no tiene). Si se prefiere una señal del servidor, lo decide `architect` (HQ-18).
- **Estado (2026-09-28): corregido en `6a10c27`.** Verificado en `docs/testing/saneamiento-sprint-1.md` (punto C).

### DEF-QA-003 — "Cerrar sesión" sin conexión deja la sesión abierta sin avisar
- **Afecta:** RF-02 ("permitir el cierre de sesión"); teléfonos compartidos (ADR-002).
- **Severidad:** baja.
- **Precondición:** sesión iniciada en `cuenta.html`.
- **Pasos:** 1) quitar la conexión; 2) pulsar "Cerrar sesión"; 3) recuperar la conexión y abrir `/`.
- **Esperado:** si el cierre falla, un aviso para reintentar; la sesión no debe quedar abierta en silencio.
- **Observado:** `cuenta.js` ignora el resultado de `DELETE /api/sesion` y navega a `index.html`, que sin conexión muestra la página de error del navegador. Con la conexión de vuelta, `/api/cuenta` responde 200 y el inicio ofrece "Ir a mi cuenta".
- **Evidencia:** `qa_ui.py`, caso `[cerrar sesión sin conexión]`.
- **Área:** frontend.
- **Estado (2026-09-28): corregido en `6a10c27`.** Verificado en `docs/testing/saneamiento-sprint-1.md` (punto D).

### DEF-QA-004 — PostgreSQL registra la sentencia completa, con el hash y datos personales, cuando falla una restricción
- **Afecta:** CLAUDE.md §8 (registros sin secretos ni datos personales innecesarios); RNF-05 (el hash es material de ataque fuera de línea); R-03.
- **Severidad:** baja (requiere una carrera entre registros y acceso a los registros del contenedor).
- **Precondición:** dos registros simultáneos con el mismo correo (PI-280); el servicio llega a la BD y la UNIQUE rechaza uno.
- **Esperado:** el registro de la BD no contiene el hash ni datos personales.
- **Observado:** `docker compose logs db` muestra `STATEMENT: INSERT INTO "usuario" ("password", …) VALUES ('argon2$argon2id$v=19$m=65536,t=3,p=1$…', NULL, 'Ana Prueba', '+56910000002', 'a@example.com')` y `DETAIL: Key (correo)=(…) already exists.` (5 casos en la base de pruebas, datos ficticios). La cuenta perdedora se revierte, pero su hash queda en el registro.
- **Evidencia:** `docker compose logs db`, líneas `STATEMENT` de las 12:26 a las 12:36 UTC del 2026-09-28.
- **Área:** infraestructura (configuración de `db`, por ejemplo `log_min_error_statement` y `log_error_verbosity`). La decisión de qué registrar la toma `architect`.
- **Estado (2026-09-28): corregido en `ff323ad`** (ADR-003, Enmienda E-1). Verificado en `docs/testing/saneamiento-sprint-1.md` (punto E). Queda un caso análogo del lado de la aplicación: DEF-QA-007, en ese mismo informe.

### DEF-QA-005 — README y propuesta del S1 describen como pendiente lo que ya está implementado
- **Afecta:** RNF-23 ("instrucciones escritas junto al código"); trazabilidad (CLAUDE.md §15).
- **Severidad:** baja.
- **Observado:** `README.md` dice "Pendiente del sprint: bitácora, respuesta ante acceso denegado y reautenticación". La línea "Estado de implementación" de la propuesta del S1 menciona ADR-010 y ADR-011 "en Borrador" y lista como pendientes `@requiere_rol`, `obtener_autorizado`, los enlaces firmados y `assert_campos_ausentes`. Todo eso está en el commit `3a18002` y ambas ADR están Aceptadas. La reautenticación sí sigue pendiente.
- **Área:** implementador o documentación (la propuesta la actualiza su autor; QA no la modifica).
- **Estado (2026-09-28): corregido en `b6dea6d`.**

### DEF-QA-006 — Las páginas de error del proxy y el 400 por Host no permitido son técnicas y en inglés
- **Afecta:** CLAUDE.md §9 ("ningún error debe mostrar códigos internos al usuario"); RNF-15 (S2).
- **Severidad:** baja.
- **Observado:** una ruta estática inexistente muestra la página de Nginx "404 Not Found / nginx"; un cuerpo mayor de 1 MB, "413 Request Entity Too Large"; un Host no permitido, "Bad Request (400)" en HTML de Django. Dentro de los formularios no afecta: `api.js` convierte una respuesta ilegible en un mensaje en español.
- **Área:** infraestructura (`error_page` en Nginx) o backend. Prioridad baja.
- **Estado (2026-09-28): abierto.** Sigue presente en `e776b70` (ver `docs/testing/saneamiento-sprint-1.md`, sección 6).

### OBS-01 — Fila manual en la bitácora de la base principal (uso indebido del autor `sistema`)
- **Hecho:** durante el despliegue del 2026-09-28 se insertó a mano, en la base principal, `bitacora.id = 1`: fecha 2026-09-28 13:53:57 UTC, `autor_tipo = 'sistema'`, `autor_id` NULL, `accion = 'verificacion'`, `entidad = 'despliegue'`, `entidad_ref = '0'`, `motivo = 'verificación de triggers'`. Además, `docker compose logs db` registra a las 13:55:40 dos intentos rechazados por `bitacora_autor_coherente`.
- **Qué incumple:** ADR-010 reserva `autor_tipo='sistema'` a las tareas programadas del actor Sistema (§3.1) y prohíbe atribuirle una acción de una persona. La fila tampoco es una acción administrativa sobre expedientes, evaluaciones ni catálogo (RF-37, M-03). Por diseño no puede borrarse ni corregirse (RNF-11, HU-19). QA no intentó borrarla ni desactivar triggers.
- **Recomendación:**
  1. Registrar el hecho en el registro de decisiones y preguntas abiertas (§5.3.4), con fecha, autor real, motivo y la advertencia de que la entrada no es una acción del actor Sistema.
  2. No agregar filas "de corrección" a mano: repetiría el problema.
  3. Verificar triggers solo en la base de pruebas, dentro de una transacción revertida (procedimiento de la sección 3.2), o con `pytest tests/test_bitacora.py`.
  4. Si el equipo necesita una base principal limpia para la revisión del sprint o la demostración, la única vía coherente con RNF-11 es recrear el volumen `datos_db`. Hoy solo tiene datos ficticios. Debe hacerse por decisión explícita y registrada del equipo, no como corrección silenciosa.
  5. Cuando existan vistas de la bitácora (CA-19.3 en S2, RF-37 en S5), la fila aparecerá: el registro del punto 1 permite explicarla.
- **Estado (2026-09-28): resuelta.** Por decisión del equipo de desarrollo, y como la base local solo tenía datos ficticios, se recreó el volumen `altiro_datos_db` (recomendación 4). Se aplicaron las 8 migraciones desde cero y `bitacora` y `acceso_denegado` quedaron vacías. No se conserva como incidente permanente.

### Otras observaciones (no son defectos)
- El puerto 80 refleja la cabecera `Host` en la redirección (`Location: https://evil.example.com:443/`). Solo lo explota quien controla la cabecera Host del propio navegador; el riesgo es mínimo en la demostración.
- Dentro del contenedor `db`, `pg_hba` de la imagen oficial permite conexiones locales sin contraseña. Solo es alcanzable con `docker exec` (la BD no publica puertos).

---

## 6. Desplazamientos que deben registrarse en la bitácora de alcance (§5.3.6)

> **Registrados el 2026-09-28** en `docs/alcance/bitacora-de-alcance.md` (DA-01 a DA-11).

El informe asigna al S1 "RF-01 a RF-03, RNF-05 a RNF-12 y RNF-23 a RNF-24" (§5.3.5). Cada punto se registra con fecha, motivo y quién lo autorizó. QA no los registra.

| # | Desplazamiento | Motivo | Nuevo cierre |
|---|---|---|---|
| 1 | RNF-06: evidencia del umbral | Los documentos de identidad existen desde S2; en S1 solo se entrega la utilidad de enlace firmado | S2 |
| 2 | RNF-08: evidencia del umbral | Los tickets pendientes existen desde S4; en S1 solo se entregan la serialización explícita y la utilidad de prueba | S4 |
| 3 | RNF-07: cumplimiento acumulativo | Cada ruta con identificador llega con su sprint; la prueba de control la exige desde su creación | S2 a S5 |
| 4 | CA-25.3 en "Terminado sin validar" | Interpretación de "bitácora" como registro separado `acceso_denegado` (ADR-010) | Revisión del sprint, con el representante del producto |
| 5 | CA-25.1 y CA-25.2 | Dependen de órdenes (S4) y documentos (S2) | S4 y S2 |
| 6 | Purga automática de `acceso_denegado` | S1 no tiene planificador; hoy purga al registrar una denegación y con el comando `purgar_accesos_denegados` | S4 (planificador) |
| 7 | RNF-22 parcial | El evento de purga existe; el formato completo (nivel, marca de tiempo, usuario y operación) es de S5 | S5 |
| 8 | Barrera 3 de la bitácora no implementada | Rol de BD con solo INSERT y SELECT; riesgo aceptado en ADR-010, punto 8 | Evaluar en S5 |
| 9 | Reautenticación de RNF-09 | Sin funciones de cambio de contraseña ni de correo; pregunta de alcance de la propuesta §2.1 (opciones A a D) sin resolver | Según la decisión |
| 10 | Uso de la bitácora desde S2 (CA-19.3) y no solo en S5 | Propuesta §1.5, punto 2 | S2 |
| 11 | RNF-23 sin medir en equipo limpio | Requiere un equipo sin imágenes ni volúmenes | Antes de la revisión del sprint |

Además, en el registro de decisiones y preguntas abiertas: OBS-01; los supuestos a validar de ADR-002 (vista privada), ADR-012 (alcance nacional y cotejo de nombres) y ADR-010 (CA-25.3); y los huecos del plan HQ-04, HQ-11, HQ-12, HQ-18 y HQ-19.

## 7. Procedimiento pendiente para RNF-23

En un equipo con Docker instalado y sin las imágenes ni los volúmenes de AlTiro (idealmente del laboratorio):
1. `git clone` del repositorio y `cd` a su carpeta.
2. Iniciar el cronómetro y ejecutar `docker compose up -d --build --wait`.
3. Detenerlo cuando termine y `https://127.0.0.1/api/health/` responda `{"estado": "ok", "base_datos": "ok"}`.
4. Registrar la fecha, el equipo (CPU, RAM y sistema operativo), la versión de Docker, la conexión y el tiempo total, incluida la descarga de imágenes. Umbral: 10 minutos o menos.

## 8. Riesgos que permanecen

1. **Origen compartido en Docker Desktop** (ADR-007): todos los clientes del equipo anfitrión llegan como `172.19.0.1`, así que 20 fallos de cualquier combinación de identificadores bloquean a todos durante 15 minutos. Es un riesgo aceptado. El acceso desde teléfonos por `ALTIRO_BIND_ADDR` sigue sin verificarse.
2. **`api.js` reintenta cualquier 403 de una operación que cambia datos**, pensando en el CSRF vencido. Desde S2, un 403 por falta de rol (`@requiere_rol`) repetiría la petición y dejaría dos filas en `acceso_denegado`. Conviene distinguir el 403 de CSRF antes de usar `@requiere_rol`.
3. **`altiro_app` es dueño de `bitacora` y `acceso_denegado`** y podría desactivar los triggers (ADR-010, punto 8; riesgo aceptado).
4. **Interpretaciones sin validar:** "vista privada" con frontend estático (ADR-002), CA-25.3 (ADR-010) y el alcance nacional del catálogo (ADR-012).
5. **Sin recuperación de contraseña ni verificación de correo** (ADR-013, punto 10): quien olvide su contraseña no puede volver a postular con su RUT.
6. **HQ-11 y HQ-12** siguen abiertos: correo fuera de ASCII y formatos raros de RUT. El sistema los rechaza (falla cerrado).

## 9. Recomendación

1. Registrar los desplazamientos de la sección 6 y la observación OBS-01 antes de declarar cerrado el S1.
2. Corregir DEF-QA-001, DEF-QA-002 y DEF-QA-003 (agente `frontend`, con revisión de `ux`) antes del S2, cuando RNF-14 y RNF-15 entran formalmente.
3. Que `architect` decida la configuración de registros de PostgreSQL (DEF-QA-004), qué hacer con HQ-18 y el ajuste del reintento ante 403 (riesgo 2).
4. Medir RNF-23 en un equipo limpio (sección 7).
5. Actualizar el README y la línea de estado de la propuesta (DEF-QA-005).
6. Registrar la revisión de avisos de dependencias del inicio del sprint (adelanto de RNF-27).
7. Hacer commit de `backend/tests/test_qa_cierre_s1.py` (PI-282, PI-283, PI-291 y PI-292).
