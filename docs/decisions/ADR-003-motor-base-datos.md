# ADR-003 — Motor de base de datos relacional

- Estado: **Aceptada** — 2026-09-27, aprobada por el equipo de desarrollo.
- Fecha: 2026-09-27
- Relacionado con: RNF-04, RNF-10, RNF-11, RNF-19, RF-03

## Contexto
El informe exige un motor relacional en contenedor con volumen local (§4.1), sin fijar cuál.

## Decisión
**PostgreSQL 16**. La imagen se fija en `docker-compose.yml` con la etiqueta exacta de una versión menor de la serie 16 (RNF-27); cambiar de versión menor dentro de la serie 16 no reabre este ADR. Aporta:
- triggers sobre UPDATE, DELETE y TRUNCATE (bitácora y `acceso_denegado`);
- restricciones CHECK;
- tipo `inet` (origen de intentos de autenticación);
- DDL transaccional en las migraciones;
- bajo consumo de memoria (RNF-04).

Para el correo sin distinguir mayúsculas, ADR-013 cerró la elección: normalización a minúsculas antes de guardar y restricción `UNIQUE` sobre la columna normalizada. No se usa `citext`.

## Alternativas consideradas
- **MariaDB/MySQL**: viable, pero no tiene triggers sobre TRUNCATE (y TRUNCATE no dispara los triggers de DELETE), no tiene `citext` ni `inet`, y el DDL no es transaccional en las migraciones.

## Consecuencias
- El contenedor `db` no publica puertos al host.
- Respaldo con `pg_dump` para RNF-19 (S5).

## Enmiendas

### E-1 — Registros del servidor sin datos personales (DEF-QA-004)
- **Fecha:** 2026-09-28.
- **Motivo:** con los valores por defecto de la imagen (`log_min_error_statement=error`, `log_error_verbosity=default`), una colisión de unicidad entre peticiones simultáneas (por ejemplo, un doble envío) hace que PostgreSQL escriba en su log la sentencia completa (`STATEMENT:`, con hash, nombre, teléfono, correo y RUT) y el `DETAIL` con el valor duplicado. Contradice CLAUDE.md §8 y la minimización de NTI-09. Análisis del agente `architect` del 2026-09-28; valores confirmados con `SHOW` en el contenedor.
- **Cambio:**
  - `log_min_error_statement=panic`: no se escribe la sentencia en los errores.
  - `log_error_verbosity=terse`: se omiten DETAIL, HINT, CONTEXT y QUERY.
  - Ambos van en el `command:` del servicio `db`, configurables con `ALTIRO_DB_LOG_MIN_ERROR_STATEMENT` y `ALTIRO_DB_LOG_ERROR_VERBOSITY` (ADR-009). Los valores de diagnóstico (`error`, `default`) solo se usan localmente con datos ficticios.
  - `log_min_messages` (`warning`), `log_statement` (`none`) y `log_min_duration_statement` (`-1`) no cambian: siguen registrándose todos los ERROR, FATAL y PANIC, con el nombre de la restricción, los fallos de autenticación, los deadlocks y los mensajes de los triggers.
  - El cliente sigue recibiendo `diag.constraint_name`: la verbosidad hacia el cliente la fija libpq.
- **Impacto:** se pierden el DETAIL de los deadlocks y el CONTEXT de las funciones en el log del servidor; para diagnosticar se sube la verbosidad localmente. Aplicarlo recrea el contenedor `db`, y con eso se borran sus logs anteriores.
- **Sin decidir (no forman parte de esta enmienda):** `log_line_prefix` con usuario y base, y la rotación de logs de Docker. La retención de logs técnicos es una política que el informe no fija.
- **Aprobación:** equipo de desarrollo, 2026-09-28 (saneamiento del Sprint 1).

### E-2 — Errores de base de datos en los registros de la aplicación (DEF-QA-007)
- **Fecha:** 2026-09-28.
- **Motivo:** E-1 limpió el log del servidor PostgreSQL, pero libpq entrega igual el `DETAIL` al cliente. Ante una excepción de BD no traducida (por ejemplo, un CHECK violado por un error de programación), el logger `django.request` escribía la traza con `DETAIL: Failing row contains (…)`: la fila completa con el hash de la contraseña, nombre, teléfono y correo, dos veces porque Django encadena la excepción de psycopg. Contradice CLAUDE.md §8, NTI-09 y RNF-05. Análisis del agente `architect` del 2026-09-28.
- **Alternativa descartada:** fijar la verbosidad TERSE de libpq en cada conexión. psycopg 3.3.6 no ofrece API para hacerlo (se comprobó en el contenedor).
- **Cambio:** filtro de logging `comun.registros.FiltroTrazasSeguras`, aplicado al logger `django.request` (actúa antes de cualquier handler) y al handler `consola` (cubre todo lo que llega a root):
  - **Qué se filtra:** reemplaza la traza por una versión segura y deja `exc_info = None`, para que ningún formatter vuelva a generar la traza original. Elimina `request` del registro (cookies, token CSRF, cuerpo, META). Nunca se escriben `str(exc)` de un error de BD, `message_detail`, `message_hint`, `context`, `internal_query`, parámetros SQL ni variables locales.
  - **Qué se conserva:**
    - la cadena completa de excepciones, con tipo y módulo;
    - la traza estructural (archivo, línea, función y línea de código);
    - de `exc.diag`, solo una lista positiva: `sqlstate`, severidad, esquema, tabla, columna, tipo de dato y restricción;
    - el mensaje primario de PostgreSQL solo en la clase 23 (integridad) y 42501 (mensajes de los triggers de solo inserción), donde no trae valores;
    - de un `ValidationError`, solo sus códigos;
    - el mensaje de las demás excepciones, truncado a 200 caracteres;
    - el nivel, la fecha y hora, el logger, el método, la ruta y el estado.
  - **No silencia nada:** el filtro devuelve siempre verdadero y los 500 se siguen registrando como `ERROR django.request`.
  - `django.db.backends` queda fijo en INFO: nunca escribe SQL con sus argumentos.
- **Sin cambios:** la respuesta al cliente (500 genérico, RNF-15), los contratos de la API y la traducción de unicidad por `diag.constraint_name`.
- **Riesgos residuales:**
  - `gunicorn.error` y `sys.excepthook` de los comandos `manage.py` no pasan por el filtro.
  - El mensaje truncado de excepciones de otras librerías podría traer datos.
  - `DEBUG=True` o `ADMINS` configurado reabren la exposición y no deben usarse con datos reales.
  - Regla de código: no interpolar datos personales en mensajes de registro ni de excepción.
  - Un identificador de petición, el usuario y la operación en cada entrada quedan para RNF-22 (S5).
- **Aprobación:** equipo de desarrollo, 2026-09-28.
