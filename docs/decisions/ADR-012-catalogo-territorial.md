# ADR-012 — Catálogo territorial

- Estado: **Aceptada** — 2026-09-28, aprobada por el equipo de desarrollo. El alcance nacional queda como supuesto a validar con la contraparte (ver «Decisión»).
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

## Decisión (2026-09-28)
- **Alcance nacional completo**: 16 regiones, 56 provincias y 346 comunas. Que se acepten clientes fuera del Gran Concepción sigue siendo un **supuesto a validar con la contraparte**; si se restringe, se filtra el catálogo sin cambiar el modelo.
- **Códigos:** planilla de Códigos Únicos Territoriales **CUT 2018 v04** (SUBDERE, publicada por IDE Chile), incluida la región de Ñuble (códigos 16xxx).
- **Archivo versionado:** `backend/territorio/datos/cut_2018.csv`, cargado por una migración de datos idempotente.
- **Cómo se obtuvo** (el sitio de SUBDERE rechaza la descarga automática, 403):
  1. Transcripción de la planilla CUT 2018 v04: gist `enoc1218/04764b8fc24952654d3dde135d32c6cd` (revisión `63aae87`, SHA-256 del archivo `66e99e71…eeab`), que cita como origen `ide.cl/descarga/capas/item/planilla-codigos-unicos-territoriales.html`.
  2. Contraste independiente con el CodeSystem `CSCodComunasCL` de HL7 Chile (Core 1.8.1, SHA-256 `44c5dbba…d4e2`): **los 346 códigos coinciden** y la jerarquía es coherente (provincia = región × 10 + n; comuna = provincia × 100 + n).
  3. Erratas de la transcripción corregidas en los nombres: Ollagüe (2202), Los Álamos (8206), Los Ángeles (8301), Chonchi (10203), O'Higgins (11302), Quinta Normal (13126), Ránquil (16206), San Nicolás (16305) y la provincia Tierra del Fuego (123).
- **Pendiente:** cotejar los nombres con la planilla oficial descargada a mano desde SUBDERE o IDE Chile. Los códigos, que son la clave, ya están verificados con dos fuentes.
- **Campos del registro:** `POST /api/clientes` recibe solo `comuna` (su código CUT); la región y la provincia se derivan de la comuna, así que no se reciben ni pueden quedar incoherentes. La región se usa en la interfaz para filtrar las comunas (CA-01.2).
