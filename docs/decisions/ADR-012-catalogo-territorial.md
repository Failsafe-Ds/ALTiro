# ADR-012 — Catálogo territorial

- Estado: **Borrador** — requiere decisión del equipo y validación con la contraparte
- Fecha: 2026-09-27
- Relacionado con: RF-01, CA-01.1, CA-01.2, RF-06, RF-09, RF-10, RF-38, M-06

## Contexto
- RF-01 exige que la comuna provenga de una lista cerrada.
- CA-01.2: al elegir región "solo aparecen las comunas de esa región según la división político-administrativa oficial".
- El informe declara como fuente la **Biblioteca del Congreso Nacional (BCN), división político-administrativa de Chile** (§2.8).
- Cobertura piloto: región del Biobío, Gran Concepción (§2.2, §3.4).

## Propuesta base
- Tablas `region`, `provincia`, `comuna` con códigos oficiales (CUT), de solo lectura.
- Carga idempotente desde un CSV versionado en el repositorio, citando la BCN y la versión o fecha de la tabla de códigos CUT usada.
- Endpoints: `GET /api/territorio/regiones` y `GET /api/territorio/regiones/{codigo}/comunas` (cada comuna incluye su provincia). No se necesita la ruta provincia → comunas.

## Opciones de alcance
- **Nacional completo**: el CSV puede compararse completo contra la fuente, lo que facilita verificar CA-01.2. Permite registrar clientes de regiones sin maestros, con resultados vacíos en la búsqueda.
- **Solo región del Biobío**: coincide con la cobertura piloto. CA-01.2 se sigue cumpliendo, porque las comunas mostradas son las oficiales de esa región.

Técnicamente ambas cuestan lo mismo.

## Pendiente (bloquea la aprobación)
- Pregunta a la contraparte: ¿se aceptan clientes fuera del Gran Concepción?
- Fijar la versión o fecha de los códigos CUT tomados de la fuente.

## Dependencias
- S3: cobertura y comuna base del maestro (RF-06) usan el mismo catálogo.
- S4: cercanía en búsqueda y ordenamiento (RF-09, RF-10).
- S5: agregación por comuna en la exportación (RF-38) y umbral de M-06.
