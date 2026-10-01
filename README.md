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

Una instalación limpia tiene oficios y comunas, pero **no tiene servicios** en el catálogo.
Para cargar servicios ficticios (rotulados "(demo)", idempotente):

```sh
docker compose exec app python manage.py cargar_datos_demo
```

El volumen sintético de medición (RNF-01, RNF-03) se genera con `generar_volumen_prueba`,
**solo en una pila aparte** (`-p altiro-volumen`), nunca en la de demostración. Las instrucciones
están al inicio de `backend/busqueda/management/commands/generar_volumen_prueba.py`.

## Correos y recuperación de contraseña (ADR-027)

No se usan servicios externos: los correos (enlace de recuperación y avisos de
cambio) se escriben como archivos en el volumen `buzon`. Para leer el último:

```sh
docker compose exec app sh -c 'cat "/buzon/$(ls -t /buzon | head -1)"'
```

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

## Servicios

| Servicio | Función | Puertos publicados |
|---|---|---|
| `init` | Genera secretos y certificado si no existen (se ejecuta y termina) | ninguno |
| `db` | PostgreSQL 16 | ninguno |
| `app` | Backend Django (API JSON bajo `/api/`) | ninguno |
| `proxy` | Nginx: HTTPS y frontend estático | 80, 443 en `127.0.0.1` |

Secretos (contraseñas de la base y clave de Django) y certificado viven en los
volúmenes `secretos` y `certificados`, nunca en el repositorio.

## Roles de PostgreSQL

La aplicación **no** se conecta como superusuario.

| Rol | Uso | Atributos |
|---|---|---|
| `altiro_admin` (`POSTGRES_USER`) | Solo inicializa la base; la app no conoce su contraseña | superusuario de la imagen |
| `altiro_app` (`ALTIRO_DB_APP_USER`) | Conexión de Django | `NOSUPERUSER NOCREATEROLE NOREPLICATION NOBYPASSRLS CREATEDB` |

- En la base `altiro`, `altiro_app` tiene `CONNECT` y `TEMPORARY`, y en el
  esquema `public`, `USAGE` y `CREATE`: las tablas que crean las migraciones
  quedan a su nombre.
- Se quita `CONNECT` a `PUBLIC` en `postgres`, `template1` y `altiro`: la app no
  puede conectarse a otras bases.
- `CREATEDB` existe solo para que pytest-django cree la base de pruebas
  `test_altiro`, que se conserva entre ejecuciones (`pytest --create-db` la recrea).

Lo hace `infra/db/initdb/10-rol-app.sh`, que la imagen de PostgreSQL ejecuta
**solo cuando el volumen `datos_db` está vacío**.

> **Volumen `datos_db` ya existente** (creado antes de este cambio o con otros
> nombres de rol): el script no se ejecuta solo. Como es idempotente, puede
> aplicarse a mano sin borrar datos:
>
> ```sh
> docker compose up -d db
> docker compose exec -u postgres db sh /docker-entrypoint-initdb.d/10-rol-app.sh
> docker compose up -d
> ```
>
> Esto requiere que el volumen se haya creado con el mismo `POSTGRES_USER`. Si
> no es así, habrá que decidir explícitamente si se recrea el volumen (se
> pierden los datos).
>
> Las contraseñas de la base se aplican al inicializar el volumen `datos_db`
> (la de `altiro_app`, también al volver a ejecutar el script). Si se elimina
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
docker compose exec app pytest                # pruebas del backend
```

> **Cambios en `infra/proxy/templates/`**: Nginx lee la plantilla al arrancar.
> Como está montada (no se copia a la imagen), `docker compose up -d` no la
> recarga sola: después de cambiarla ejecute `docker compose restart proxy`.
