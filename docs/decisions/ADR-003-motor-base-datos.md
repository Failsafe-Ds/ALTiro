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
