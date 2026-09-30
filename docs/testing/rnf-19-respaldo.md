# RNF-19 — Respaldo y restauración: evidencia (S5, incremento 3)

Umbral (informe §4.2.2): respaldo diario automatizado, retención de 7 días y restauración completa probada en 30 minutos o menos. Decisión: ADR-026, E-7 (con la enmienda a ADR-015 de E-7.2). Riesgo: R-04.

## Qué se construyó
| Pieza | Dónde | Qué hace |
|---|---|---|
| Servicio `respaldo` | `docker-compose.yml` | Imagen `postgres:16.15-bookworm` (la misma de `db`: sin imágenes nuevas). Todos los días a `ALTIRO_RESPALDO_HORA` (03:00, `America/Santiago`) |
| Respaldo | `scripts/respaldo.sh` | `pg_dump -Fc`, `conteos.tsv` (filas por tabla), `tar` de `fotos` y `documentos`, `SHA256SUMS`. Escribe en `.en-curso-*` y renombra al terminar. Borra los de más de 7 días |
| Restauración | `scripts/restaurar.sh <respaldo> [proyecto]` | Verifica las sumas, crea volúmenes vacíos, copia los secretos (respaldados aparte), extrae los volúmenes, `pg_restore` y levanta `app` hasta `healthy`. **Se niega si cualquier volumen del proyecto destino ya existe** |
| Simulacro | `scripts/simulacro-restauracion.sh` | Restaura el último respaldo en `-p altiro-restauracion`, compara los conteos y descifra los documentos |

Montajes del servicio `respaldo` (verificados con `docker inspect`):
- `documentos` y `fotos`: solo lectura (`rw=false`); escribir en ellos falla.
- Del volumen de secretos, **solo** `db_admin_password` (subpath, solo lectura); `documentos_clave` no existe en el contenedor.
- Destino: `ALTIRO_RESPALDO_DIR` (por defecto `../altiro-respaldos`, fuera del repositorio; también en `.gitignore`).

## Ejecución (2026-09-30, equipo local, Docker 29.8.0, Compose 5.5.1)
Datos: base de desarrollo con datos ficticios (27 tablas, 5.024 filas, 302 documentos, 323 archivos cifrados).

| Paso | Resultado |
|---|---|
| Respaldo manual (`--una-vez`) | 1 s. `base.dump` 292 KB, `documentos.tar` 22 MB, `fotos.tar.gz` 196 KB |
| Retención | Con un directorio de 8 días y otro de 6: se borró solo el de 8 ("eliminados: 1") |
| Restauración completa (`restaurar.sh`) | **19 s** hasta `app` healthy (sumas 1 s; volúmenes 3 s; db sana 7 s; `pg_restore` 1 s; app sana 7 s) |
| Simulacro completo (restauración + verificación) | **20 s**. Umbral: 30 min |
| Conteos de filas | Iguales en las 27 tablas (5.024 filas) respecto de `conteos.tsv` |
| Descifrado de documentos | 240 descifrados, primera foto 15.557 bytes con firma JPEG. 62 ilegibles: **igual que en el proyecto principal** (240/62, medido con la misma consulta de solo lectura). Son filas de datos de prueba sin archivo; no los causa el respaldo |
| Protección | Una segunda restauración sobre `altiro-restauracion` con volúmenes existentes se niega (salida 1) |
| Limpieza | `docker compose -p altiro-restauracion down -v`: solo los 5 volúmenes con prefijo `altiro-restauracion_` (verificado antes por etiqueta). Los volúmenes `altiro_*` y los servicios principales siguieron sanos |

## Cómo repetirlo
```sh
docker compose up -d respaldo
MSYS_NO_PATHCONV=1 docker compose exec respaldo sh /usr/local/bin/altiro-respaldo.sh --una-vez
bash scripts/simulacro-restauracion.sh          # usa altiro_secretos de solo lectura
docker volume ls --filter label=com.docker.compose.project=altiro-restauracion
docker compose -p altiro-restauracion down -v   # solo tras verificar el prefijo
```

## Observaciones
- El simulacro copia los secretos desde `altiro_secretos` (solo lectura) porque en este equipo no hay otra copia. En la operación real, la clave de documentos y las contraseñas se respaldan **aparte** (E-7.2) y `ALTIRO_RESTAURAR_SECRETOS_VOLUMEN` apunta a esa copia. Falta definir dónde guarda el equipo esa copia.
- `base.dump` no va cifrado: contiene datos personales (ficticios en la prueba de concepto). El directorio de respaldos debe tener acceso restringido.
- La app restaurada usa la imagen `altiro-app:local` que ya existe; al arrancar aplica las migraciones pendientes.
- No se probó `restaurar.sh` contra el proyecto principal, a propósito (CLAUDE.md §14). La protección por volúmenes existentes se probó sobre `altiro-restauracion`.
