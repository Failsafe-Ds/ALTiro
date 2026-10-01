# ADR-030 — Endurecimiento operativo: purgas, respaldo cifrado, imagen sin pruebas y rol dueño separado

- Estado: **Propuesta** (2026-10-01). Implementada a pedido del usuario para corregir los hallazgos B4 a B9 de la auditoría; se revisa con el equipo.
- Relacionado con: RNF-11, RNF-12, RNF-19, RNF-22, RNF-24, RNF-27, R-04, R-10, NTI-09; ADR-003, ADR-005, ADR-007, ADR-008, ADR-009, ADR-010 (punto 8), ADR-014, ADR-015, ADR-016, ADR-026 (E-7), ADR-027 (punto 4).

## Contexto
La auditoría posterior al S5 encontró seis brechas operativas:
- **B5:** `django_session` nunca se purga y crece sin límite (en la demo había 704 sesiones vencidas).
- **B9:** los correos del buzón local (ADR-027, punto 4) no se borran nunca y llevan nombre, correo y enlace de recuperación.
- **B6:** el respaldo diario (ADR-026, E-7) queda en claro en el host (`../altiro-respaldos`): volcado de la base con datos personales y fotos.
- **B7:** la imagen de ejecución instala `requirements-pruebas.txt` (pytest y compañía), que la demo no necesita.
- **B8:** `altiro_app` es dueño de las tablas y aplica las migraciones; como dueño podría desactivar los triggers de solo inserción (riesgo aceptado en ADR-010, punto 8).
- **B4:** con `ALTIRO_BIND_ADDR` expuesto a la LAN detrás del NAT de Docker Desktop, todos los clientes pueden llegar con la IP del gateway.

## Decisión

### 1. Purga de sesiones expiradas (B5)
- Nueva tarea `sesiones_expiradas_purgadas` en el planificador (`expediente/management/commands/planificador.py`, `purgar_sesiones_expiradas`). Borra las filas de `django_session` con `expire_date < ahora`, igual que `clearsessions` con el motor de base de datos, pero devuelve el conteo.
- **Frecuencia:** en cada corrida del planificador (300 s, ADR-016 E-1). La consulta usa el índice de `expire_date` y es barata. Una sesión vencida ya no autentica, así que borrarla no cierra ninguna sesión vigente.
- **Registro:** solo el conteo en la línea de la corrida. Sin claves de sesión ni datos personales (RNF-22).

### 2. Purga del buzón local (B9)
- Nueva tarea `correos_buzon_purgados` (`purgar_buzon`). Borra los `*.log` regulares del primer nivel de `ALTIRO_BUZON_DIR` cuya antigüedad supere **`ALTIRO_RECUPERACION_MINUTOS` (30) + `ALTIRO_BUZON_MARGEN_HORAS` (24 por defecto)**. No sigue enlaces.
- **Justificación:** el enlace vence a los 30 minutos, y después el correo ya no sirve para recuperar la cuenta. El margen de 24 horas deja revisar los avisos durante una demostración y limita a un día la vida de los datos personales.
- **Enmienda a ADR-027, punto 4:** el volumen `buzon` se monta también en `planificador`, con el mismo UID 10001.
- `purgar_accesos_denegados` (90 días, ADR-010 punto 3) ya corría en el planificador. Se verificó que sigue en `TAREAS`.

### 3. Respaldo cifrado (B6)
- `init` genera `secretos/respaldo_clave`: 256 bits aleatorios, dueño root, modo 0400, y nunca se regenera. Sigue el patrón de ADR-009. La clave vive en el volumen `secretos`, **no** en el directorio de respaldos. El servicio `respaldo` monta solo ese archivo (subpath), de solo lectura.
- `scripts/respaldo.sh` (ahora bash con `pipefail`) cifra en tubería con **GnuPG simétrico, AES-256 con MDC**: `base.dump.gpg`, `fotos.tar.gz.gpg` y `documentos.tar.gpg`. El texto en claro nunca toca el disco del host. `conteos.tsv` (nombre de tabla y número) y `CIFRADO` (formato, sin secretos) quedan en claro, y `SHA256SUMS` cubre todo.
- Se eligió GnuPG porque ya está en `postgres:16.15-bookworm`: no hay imagen ni dependencia nueva. Además, el MDC detecta cualquier alteración al descifrar. `openssl enc` no tiene modo autenticado y habría exigido un HMAC aparte.
- `scripts/restaurar.sh`:
  - comprueba las sumas;
  - exige `respaldo_clave` en `ALTIRO_RESTAURAR_SECRETOS_VOLUMEN`;
  - descifra completos los tres archivos, y un MDC inválido o una clave incorrecta detienen la restauración antes de crear volúmenes;
  - descifra en tubería hacia `tar` y `pg_restore`;
  - sigue aceptando los respaldos antiguos en claro, con un aviso.
- **Sin la clave, el respaldo no sirve.** Dónde se guarda la copia de `secretos` sigue pendiente (ADR-026, E-7.2).
- Respaldos en claro anteriores (`altiro-20260930T*`): **no se borran a mano**. La retención de 7 días de `respaldo.sh` (RNF-19) los elimina sola a partir del 2026-10-07.

### 4. Imagen de ejecución sin herramientas de prueba (B7)
- `backend/Dockerfile` en etapas:
  - `base`, con `requirements.txt`;
  - `pruebas`, que agrega `requirements-pruebas.txt` y usa `pytest` como entrypoint;
  - `ejecucion`, la última y por defecto.
- `app`, `planificador` y `migrador` usan `altiro-app:local` (target `ejecucion`), que no tiene pytest.
- El nuevo servicio `pruebas` (perfil `pruebas`, imagen `altiro-app-pruebas:local`) tiene el mismo entorno que `app` (ancla YAML) y no se levanta con `up`.
- Suite:
  `MSYS_NO_PATHCONV=1 docker compose run --rm -v "$(pwd -W)/backend:/app" -v "$(pwd -W)/frontend:/frontend:ro" pruebas -q`.
  Tras cambiar `requirements-pruebas.txt`: `docker compose build pruebas`.

### 5. Rol migrador dueño del esquema; la app solo con DML (B8)
- Nuevo rol `altiro_migrador`: LOGIN, sin SUPERUSER, CREATEDB, CREATEROLE ni BYPASSRLS. Su contraseña es `secretos/db_migrador_password`, de dueño 10002, grupo postgres y modo 0440: la app (UID 10001) no puede leerla.
- `infra/db/initdb/10-rol-app.sh` sigue siendo idempotente y hace lo siguiente:
  - crea o actualiza los dos roles;
  - da al migrador USAGE y CREATE en `public`;
  - a `altiro_app` le deja solo USAGE, le quita CREATE y le da SELECT, INSERT, UPDATE y DELETE sobre todas las tablas y USAGE, SELECT y UPDATE sobre las secuencias, más privilegios por defecto para lo que cree el migrador. Sin TRUNCATE, REFERENCES ni TRIGGER;
  - **reasigna al migrador, objeto por objeto**, las tablas, vistas, secuencias y funciones de `public` que todavía sean de `altiro_app`. No usa `REASSIGN OWNED`, porque eso movería también la base de pruebas de pytest-django, que es de la app.
- El script corre en dos contextos:
  - initdb, en volúmenes nuevos;
  - el nuevo servicio único **`roles_db`** (postgres:16, por TCP con el superusuario), en **cada** `up`. Así el volumen existente de la demo quedó migrado sin recrearse.
- El nuevo servicio único **`migrador`** (misma imagen, `user: 10002:10001`) aplica `migrate` con el rol dueño. El grupo 10001 lee la clave de Django y la de documentos, que `init` pasa a modo 0440 y que settings exige al cargar.
- `app` depende de `migrador` y ya no migra: `entrypoint.sh` ejecuta `migrate --check` y no arranca si falta alguna migración.
- **Migrar a mano:** `docker compose up -d` o `docker compose run --rm migrador`. `docker compose exec app python manage.py migrate` **ya no funciona** para migraciones con DDL.
- Efecto: la app ya no puede ejecutar `ALTER TABLE … DISABLE TRIGGER`, `TRUNCATE`, `CREATE` ni `CREATE OR REPLACE FUNCTION` sobre las funciones de los triggers. Se cierra el riesgo aceptado de ADR-010, punto 8, frente a un compromiso de la app. Los triggers siguen rechazando UPDATE y DELETE.

### 6. Origen compartido detrás del NAT (B4, solo documentación)
- Con Docker Desktop (Windows y macOS), el puerto publicado pasa por el proxy de red de Docker. Nginx puede ver a **todos** los clientes de la LAN con la misma IP (la del gateway). Los límites por origen (ADR-007; ADR-029 en el proxy) se comparten entonces entre todos los teléfonos de la demo: un bloqueo por intentos afecta a todos.
- Esto queda documentado en `README.md`. No se cambia el código.
- Para una demo en LAN:
  - comprobar con el registro del proxy qué IP llega;
  - si es una sola, demostrar la limitación desde un solo equipo;
  - o ejecutar en un host Linux, donde Docker conserva la IP de origen.

## Alternativas consideradas
- **B5:** correr `clearsessions` una vez al día. Se descartó porque obliga a llevar un estado de "última ejecución". La purga por corrida es barata.
- **B9:** borrar al vencer el enlace, sin margen. Impide mostrar los correos en la demo. Se descartó también conservarlos 7 días, porque prolonga sin motivo los datos personales.
- **B6:**
  - `openssl enc -aes-256-cbc -pbkdf2`: sin autenticación;
  - `age`: no está en la imagen;
  - guardar la clave en el directorio de respaldos: anula el cifrado.
- **B7:** un build-arg `INSTALAR_PRUEBAS`. Obliga a reconstruir la imagen de la demo para correr la suite. Se eligió un target aparte.
- **B8:**
  - `REASSIGN OWNED BY altiro_app`: mueve la base de pruebas;
  - recrear el volumen: prohibido (CLAUDE.md §14);
  - revocar además UPDATE y DELETE por tabla en las tablas de solo inserción: se deja pendiente, porque `select_for_update` exige UPDATE y no se auditó cada uso.

## Consecuencias
- La pila tiene dos servicios únicos más (`roles_db` y `migrador`) y uno de perfil (`pruebas`). `up -d --build` los ejecuta en orden: `init` → `db` → `roles_db` → `migrador` → `app` → `planificador`/`proxy`.
- **Flujo de los agentes y del equipo:** el comando de la suite cambia de `app` a `pruebas`. La imagen `app` ya no tiene pytest, así que el comando anterior falla con "pytest no encontrado". Para migrar, usar `docker compose up -d`.
- Si se recrea `app`, el proxy sigue apuntando a la IP anterior hasta reiniciarlo (`docker compose restart proxy`). Es un comportamiento previo de Nginx, que resuelve el upstream al arrancar, y es independiente de este ADR.
- Sin `respaldo_clave` no hay restauración. La copia del volumen `secretos` es ahora imprescindible (pendiente ADR-026, E-7.2).
- **Verificación (2026-10-01):**
  - `up -d --build` con todo sano;
  - respaldo cifrado en 3 s (cabecera OpenPGP AES-256);
  - simulacro en `-p altiro-restauracion`: 25 s, menos que los 30 min de RNF-19; conteos iguales (32 tablas, 4.820 filas); 240 documentos descifrados, la misma cifra que en el origen;
  - un byte alterado o una clave incorrecta hacen fallar a gpg;
  - como `altiro_app`: UPDATE y DELETE sobre `bitacora` → error del trigger; `ALTER TABLE … DISABLE TRIGGER` → "must be owner"; `TRUNCATE` → "permission denied"; `CREATE TABLE` → "permission denied for schema public";
  - la app lee y escribe;
  - pruebas en `tests/test_planificador_purgas.py` y `tests/test_roles_base_datos.py`.

## Pendiente
- Dónde se guarda la copia de `secretos` (incluida `respaldo_clave`): ADR-026, E-7.2.
- Revocar UPDATE y DELETE por tabla en `bitacora`, `ticket_evento`, `precio_final_evento` y `mensaje`, y UPDATE en `acceso_denegado`, tras auditar `select_for_update`.
- Borrar los volúmenes del simulacro (`altiro-restauracion_*`) cuando el equipo lo autorice.
