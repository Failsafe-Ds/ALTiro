# AlTiro — prueba de concepto

Plataforma web que conecta hogares con maestros independientes verificados.
La documentación funcional está en `docs/` (`docs/informe-altiro.md`) y las
decisiones técnicas en `docs/decisions/`. Los desplazamientos de alcance
(informe §5.3.6) se registran en `docs/alcance/bitacora-de-alcance.md`.

Estado actual: **los cinco sprints del informe están construidos** (etiquetas `sprint-1` a
`sprint-5`; cierres en `docs/testing/cierre-sprint-*.md`). Hoja corta del estado:
`docs/estado-actual.md`. Material de defensa: `docs/defensa/guion-defensa.md`.
Pendientes del equipo: RNF-13 con personas, RNF-18 manual, plazos de RNF-26 y
preguntas P-01 a P-33.

## Requisitos

- Docker Desktop (o Docker Engine) con Docker Compose v2.
- Puertos 80 y 443 libres en el equipo (configurables, ver `.env.example`).

## Levantar el sistema (un solo comando)

```sh
docker compose up -d --build
```

Luego abra <https://127.0.0.1/> (o <https://localhost/>).

No hace falta crear `.env`: `docker-compose.yml` trae valores por defecto.
Para cambiarlos, cree un `.env` a partir de `.env.example` (el `.env` no se versiona).

## Pantallas

| Página | Uso |
|---|---|
| `/` | Inicio |
| `/registro-cliente.html` | Crear cuenta de cliente, en 3 pasos (RF-01) |
| `/postulacion-maestro.html` | Postular como maestro, en 2 pasos (RF-03) |
| `/ingresar.html` | Ingresar con correo o RUT (RF-02) |
| `/cuenta.html` | Datos propios, agregar el otro perfil y cerrar sesión |
| `/mi-postulacion.html`, `/mis-documentos.html` | Maestro: estado del expediente y documentos (RF-04, RF-35) |
| `/mis-servicios.html`, `/mi-cobertura.html`, `/mi-agenda.html`, `/mi-perfil.html` | Maestro: servicios, comunas, horarios y foto (RF-05 a RF-07) |
| `/curatoria.html`, `/curatoria-expediente.html` | Curatoría: revisión de expedientes (RF-08) |
| `/comercial.html` | Comercial: catálogo de oficios y servicios (RF-36) |
| `/buscar.html`, `/perfil-maestro.html` | Público: búsqueda y ficha del maestro (RF-09 a RF-11, RF-14) |
| `/pedir-trabajo.html`, `/mis-pedidos.html` | Cliente: pedir un horario, seguir pedidos, aceptar el precio e historial |
| `/mis-trabajos.html` | Maestro: pedidos recibidos, aceptar o rechazar, precio final e historial |
| `/conversacion.html`, `/evaluar.html` | Cliente y maestro: conversación del pedido aceptado y evaluación (RF-25, RF-29) |
| `/moderacion.html` | Moderación: denuncias de evaluaciones (RF-31) |
| `/indicadores.html` | Control de gestión: indicadores y exportación anonimizada (RF-38) |
| `/recuperar.html`, `/nueva-contrasena.html` | Olvidé mi contraseña y crear una nueva con el enlace (ADR-027) |

## Datos de demostración

Una instalación limpia tiene oficios y comunas, pero **no tiene servicios, maestros ni cuentas**.
Todo lo que sigue es ficticio y va rotulado "(demo)" (ADR-028).

1. Levanta la pila con el código al día (el comando vive en la imagen de `app`):

   ```sh
   docker compose up -d --build
   ```

2. Carga el catálogo de demostración **y** las cuentas para probar el flujo completo:

   ```sh
   docker compose exec app python manage.py cargar_datos_demo --con-cuentas
   ```

   Crea 10 maestros publicados (7 en el Gran Concepción y 3 en Santiago, con foto, cobertura,
   agenda de lunes a sábado y servicios de oficios no regulados), 2 clientes y 4 pedidos de
   ejemplo (pendiente, aceptado con conversación, finalizado sin evaluar y cerrado). Es
   idempotente: volver a ejecutarlo no duplica nada. Sin `--con-cuentas` solo carga los servicios del catálogo.

3. **Anota la contraseña que imprime la consola**: aparece una sola vez, no se guarda en
   ningún archivo ni registro y es la misma para las tres cuentas con ingreso:

   | Quién | Ingresa con |
   |---|---|
   | Maestro | RUT `49990001-5` o `maestro.demo@example.com` |
   | Clienta (Concepción) | `cliente.demo.1@example.com` |
   | Cliente (Santiago) | `cliente.demo.2@example.com` |

   Entra en `https://localhost/ingresar.html`: el campo acepta correo o RUT.
   Si perdiste la contraseña, genera otra para esas cuentas con
   `cargar_datos_demo --con-cuentas --restablecer-contrasenas`.
   Esa opción cierra las sesiones abiertas de esas cuentas.

4. Prueba la búsqueda, por ejemplo "Gasfitería" en Concepción o "Pintura" en Santiago. El
   maestro con ingreso atiende Concepción, Talcahuano, San Pedro de la Paz y Chiguayante.

5. Para curatoría, comercial, moderación o control de gestión, crea una cuenta
   administrativa con `crear_usuario_administrativo` (ver "Crear una cuenta administrativa").
   La contraseña la eliges tú y se pide oculta.

Si la base tiene oficios `oficio_prueba_s3_…` u `oficio_qa3_…` (restos de pruebas de navegador
del S3), `docker compose exec app python manage.py limpiar_oficios_de_prueba` los lista.
Con `--confirmo` los borra. Solo toca oficios desactivados con esos códigos exactos.

El volumen sintético de medición (RNF-01, RNF-03) se genera con `generar_volumen_prueba`,
**solo en una pila aparte** (`-p altiro-volumen`), nunca en la de demostración. Las instrucciones
están al inicio de `backend/busqueda/management/commands/generar_volumen_prueba.py`.
Las pruebas de navegador también deben correr en una pila aparte o limpiar lo que crean.

## Correos y recuperación de contraseña (ADR-027)

No se usan servicios externos: los correos (enlace de recuperación y avisos de
cambio) se escriben como archivos en el volumen `buzon`. Para leer el último:

```sh
docker compose exec app sh -c 'cat "/buzon/$(ls -t /buzon | head -1)"'
```

Los correos llevan datos personales. El planificador borra los que tienen más
de **30 min (vigencia del enlace) + 24 h** de antigüedad (`ALTIRO_BUZON_MARGEN_HORAS`;
ADR-030, B9). También purga cada 5 minutos las sesiones expiradas de
`django_session` (B5). Solo registra conteos.

Una persona sin correo en su cuenta (por ejemplo, un maestro que ingresa con RUT)
recupera su contraseña con ayuda. **Antes**, verifique su identidad fuera del
sistema (llamada al teléfono registrado). Después genere el enlace y hágaselo llegar:

```sh
docker compose exec app python manage.py crear_enlace_recuperacion --cuenta 12.345.678-5
```

## Crear una cuenta administrativa

No hay pantalla para esto (ADR-013, punto 8). La contraseña se pide oculta:

```sh
docker compose exec app python manage.py crear_usuario_administrativo \
    --nombre "Nombre Apellido" --correo admin@example.com --rol curatoria
# Agregar un rol a una cuenta existente (correo o RUT):
docker compose exec app python manage.py crear_usuario_administrativo --agregar-a admin@example.com --rol comercial
```

Roles: `curatoria`, `comercial`, `moderacion`, `control_gestion`.

## Certificado propio de demostración

La conexión es siempre cifrada (RNF-12). En la demostración local se usa un
**certificado propio, autofirmado, identificado como "AlTiro demo local,
autofirmado"**. No lo emite ninguna autoridad de certificación, por lo que el
navegador mostrará una advertencia: es esperado en esta demostración.

- Lo genera automáticamente el servicio `init` si no existe.
- Su nombre alternativo (SAN) se configura con `ALTIRO_TLS_SAN`.
- La configuración de demostración **no emite** `Strict-Transport-Security` (ADR-008).
- El puerto 80 solo redirige a HTTPS (307).
- Por defecto solo se publica en `127.0.0.1`; para exponerlo a la red local
  defina `ALTIRO_BIND_ADDR` y agregue la IP al SAN y a `DJANGO_ALLOWED_HOSTS`.

> **Demo en red local con Docker Desktop (ADR-030, B4).** En Windows y macOS
> los puertos publicados pasan por el proxy de red de Docker Desktop (NAT).
> Nginx y la app pueden ver a **todos** los teléfonos con una misma IP, la del
> gateway de Docker. Como los límites de intentos y de solicitudes son por
> origen (ADR-007, ADR-029), esos clientes **comparten** el cupo: si uno
> bloquea, se bloquean todos. Antes de la demo, revise en
> `docker compose logs proxy` qué IP llega. Si es siempre la misma, demuestre
> la limitación desde un solo equipo o use un host Linux, que conserva la IP
> de origen.

## Servicios

| Servicio | Función | Puertos publicados |
|---|---|---|
| `init` | Genera secretos y certificado si no existen (se ejecuta y termina) | ninguno |
| `db` | PostgreSQL 16 | ninguno |
| `roles_db` | Deja los roles y dueños de la base (ADR-030, B8); se ejecuta y termina en cada `up` | ninguno |
| `migrador` | Aplica las migraciones con el rol dueño `altiro_migrador`; se ejecuta y termina | ninguno |
| `app` | Backend Django (API JSON bajo `/api/`); solo comprueba que no falten migraciones | ninguno |
| `planificador` | Tareas del actor Sistema cada 5 min (avisos, cierres, purgas) | ninguno |
| `respaldo` | Respaldo diario cifrado (ver «Respaldo y restauración») | ninguno |
| `pruebas` | Suite de pruebas (perfil `pruebas`; no se levanta con `up`) | ninguno |
| `proxy` | Nginx: HTTPS y frontend estático | 80, 443 en `127.0.0.1` |

Secretos (contraseñas de la base y clave de Django) y certificado viven en los
volúmenes `secretos` y `certificados`, nunca en el repositorio.

## Roles de PostgreSQL

La aplicación **no** se conecta como superusuario.

| Rol | Uso | Atributos |
|---|---|---|
| `altiro_admin` (`POSTGRES_USER`) | Solo inicializa la base; la app no conoce su contraseña | superusuario de la imagen |
| `altiro_migrador` (`ALTIRO_DB_MIGRADOR_USER`) | Dueño de tablas, secuencias y funciones; solo lo usa el servicio `migrador` | `NOSUPERUSER NOCREATEROLE NOCREATEDB NOREPLICATION NOBYPASSRLS` |
| `altiro_app` (`ALTIRO_DB_APP_USER`) | Conexión de Django | `NOSUPERUSER NOCREATEROLE NOREPLICATION NOBYPASSRLS CREATEDB` |

- En la base `altiro`, `altiro_app` tiene `CONNECT` y `TEMPORARY`. En el
  esquema `public` tiene **solo `USAGE`** y, en tablas y secuencias, solo DML
  (`SELECT`, `INSERT`, `UPDATE`, `DELETE`; sin `TRUNCATE` ni `TRIGGER`). **No es
  dueña de nada** (ADR-030, B8), así que no puede desactivar los triggers de
  solo inserción de `bitacora`, `ticket_evento`, `acceso_denegado`, etc.
- `altiro_migrador` es el dueño y aplica las migraciones. Su contraseña
  (`secretos/db_migrador_password`) no la puede leer la app. Para migrar:
  `docker compose up -d` o `docker compose run --rm migrador`
  (`docker compose exec app python manage.py migrate` ya no sirve para crear o
  alterar tablas).
- Se quita `CONNECT` a `PUBLIC` en `postgres`, `template1` y `altiro`: la app no
  puede conectarse a otras bases.
- `CREATEDB` existe solo para que pytest-django cree la base de pruebas
  `test_altiro`, que se conserva entre ejecuciones (`pytest --create-db` la recrea).

Lo hace `infra/db/initdb/10-rol-app.sh`, que es idempotente. Corre en dos
momentos: lo ejecuta la imagen de PostgreSQL cuando el volumen `datos_db` está
vacío, y lo ejecuta el servicio `roles_db` en **cada** `docker compose up`.
Así un volumen ya existente queda con el mismo reparto, sin borrar datos: las
tablas que eran de `altiro_app` pasan a `altiro_migrador`.

> **Volumen `datos_db` ya existente:** basta con `docker compose up -d`. Esto requiere que el volumen se haya creado con el mismo `POSTGRES_USER`. Si
> no es así, habrá que decidir explícitamente si se recrea el volumen (se
> pierden los datos).
>
> Las contraseñas de la base se aplican al inicializar el volumen `datos_db`
> (las de `altiro_app` y `altiro_migrador`, también en cada `up` con `roles_db`). Si se elimina
> el volumen `secretos` y se conserva `datos_db`, la aplicación no podrá
> conectarse a la base.

**Registros de PostgreSQL** (ADR-003, E-1): por defecto no escriben la sentencia
ni el detalle de los errores. Para diagnosticar, y solo con datos ficticios, ponga
`ALTIRO_DB_LOG_MIN_ERROR_STATEMENT=error` y `ALTIRO_DB_LOG_ERROR_VERBOSITY=default`
en `.env`, ejecute `docker compose up -d db`, y al terminar vuelva a `panic`/`terse`
y repita el comando.

## Verificaciones rápidas

```sh
docker compose ps
curl -k https://127.0.0.1/api/health/        # {"estado": "ok", "base_datos": "ok"}
curl -I http://127.0.0.1/                     # 307 hacia https://
```

**Pruebas** (ADR-014; ADR-030, B7). La imagen `app` de la demo no trae pytest.
La suite corre en el servicio `pruebas`. Desde Git Bash, en la raíz:

```sh
MSYS_NO_PATHCONV=1 docker compose run --rm -v "$(pwd -W)/backend:/app" -v "$(pwd -W)/frontend:/frontend:ro" pruebas -q
# una prueba dirigida: ... pruebas -q tests/test_planificador_purgas.py -k b5
# tras cambiar requirements-pruebas.txt: docker compose build pruebas
```

## Respaldo y restauración (RNF-19; ADR-026 E-7; ADR-030 B6)

- El servicio `respaldo` corre todos los días a las 03:00 (`ALTIRO_RESPALDO_HORA`)
  y conserva 7 días en `ALTIRO_RESPALDO_DIR` (por defecto `../altiro-respaldos`,
  fuera del repositorio). Para un respaldo inmediato:
  `docker compose exec respaldo bash /usr/local/bin/altiro-respaldo.sh --una-vez`.
- Cada respaldo tiene `base.dump.gpg`, `fotos.tar.gz.gpg`, `documentos.tar.gpg`
  (GnuPG simétrico, AES-256 con control de integridad), `conteos.tsv`, `CIFRADO`
  y `SHA256SUMS`. Nada con datos personales queda en claro en el host.
- **La clave** es el archivo `respaldo_clave` del volumen Docker `altiro_secretos`.
  La genera `init` y **no** está junto a los respaldos. **Sin esa clave, un
  respaldo no se puede restaurar.** Guarde una copia del volumen `secretos`
  aparte de los respaldos (lleva también la clave de documentos). Dónde se
  guarda esa copia sigue pendiente (ADR-026, E-7.2).
- **Restaurar** en un proyecto vacío (se niega si ya existe algún volumen del
  destino; nunca sobrescribe):

  ```sh
  ALTIRO_RESTAURAR_SECRETOS_VOLUMEN=altiro_secretos scripts/restaurar.sh ../altiro-respaldos/altiro-AAAAMMDDTHHMMSSZ [proyecto]
  ```

  Comprueba las sumas y descifra completos los tres archivos. Un archivo
  alterado o una clave incorrecta lo detienen antes de crear nada. Después
  restaura y espera a que `app` esté sana.
- **Simulacro verificado** (sin tocar la base de la demo, proyecto
  `altiro-restauracion`): `scripts/simulacro-restauracion.sh` compara conteos y
  descifra los documentos. El 2026-10-01 tardó 25 s (umbral RNF-19: 30 min o menos).
- Los respaldos **anteriores** al 2026-10-01 (`altiro-20260930T*`) están **en
  claro**. No se borran a mano. La retención de 7 días los elimina sola, y
  `restaurar.sh` todavía los acepta con un aviso.

> **Cambios en `infra/proxy/templates/`**: Nginx lee la plantilla al arrancar.
> Como está montada (no se copia a la imagen), `docker compose up -d` no la
> recarga sola: después de cambiarla ejecute `docker compose restart proxy`.
