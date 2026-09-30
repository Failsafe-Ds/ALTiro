# ADR-025 — graphify como herramienta del equipo (grafo de conocimiento del repositorio)

- Estado: **Aceptada** — 2026-09-29, decisión del equipo.
- Fecha: 2026-09-29
- Relacionado con: RNF-27 (no aplica a la aplicación; ver Consecuencias), CLAUDE.md §13 y §14

## Contexto
- Los agentes gastan muchos tokens en orientarse: leen archivos enteros y recorren el código con búsquedas amplias. El consumo creció con cada sprint.
- graphify (<https://github.com/Graphify-Labs/graphify>, CLI 0.9.72) construye un grafo de conocimiento del repositorio y responde consultas acotadas con `query`, `path` y `explain`.

## Decisión
1. **Herramienta del equipo, no de la aplicación:**
   - se instala en el equipo de cada integrante;
   - no entra en la imagen Docker, ni en `requirements*.txt`, ni en `docker-compose.yml`.
2. **Grafo del código:** `graphify update .` hace extracción estructural (AST). Corre en local, sin modelos ni red. Se actualiza después de cada cambio de código.
3. **Grafo de la documentación** (informe, ADR y documentos de pruebas):
   - se extrae **solo con agentes de la sesión de Claude Code**;
   - **no se usa Gemini ni ningún otro proveedor externo**: no se configuran `GEMINI_API_KEY` ni `GOOGLE_API_KEY`, para que el informe y los documentos no salgan a otro servicio.
4. **`graphify-out/` no se versiona** (`.gitignore`). Cada integrante lo regenera (unos 11 s para el código).
5. **Configuración versionada:**
   - la sección "graphify" de `CLAUDE.md`;
   - `.claude/CLAUDE.md`;
   - `.claude/settings.json`, con avisos antes de buscar o leer;
   - `.claude/skills/graphify/`.
6. **Prioridad de fuentes:** el grafo orienta, pero **no es fuente de verdad**.
   - Ante una duda de negocio, prevalecen `docs/informe-altiro.md` y el `.docx` (CLAUDE.md §2).
   - Antes de modificar código, se leen las líneas reales.

## Consecuencias
- Hay menos lecturas amplias. Las respuestas de `query` están truncadas por presupuesto: si el grafo no alcanza, se vuelve a leer el archivo.
- RNF-27 no aplica, porque la aplicación no depende de graphify. Su versión queda registrada aquí y se actualiza a mano.
- El grafo puede quedar desactualizado. Si una respuesta no coincide con el código, manda el código y se corre `graphify update .`.

## Enmiendas

### E-1 — El grafo cubre solo el código
- **Fecha:** 2026-09-30. Decisión del equipo.
- **Cambio:**
  - se reemplaza el punto 3 de la decisión: **no se extrae documentación**, ni con agentes ni con scripts. Se detuvo el intento del 2026-09-29/30 y se descartaron sus resultados;
  - el grafo se mantiene solo con `graphify update .` (código, sin LLM);
  - la documentación se consulta con `docs/estado-actual.md` y con lecturas puntuales del informe y de los ADR.
- **Motivo:** la extracción semántica cuesta cientos de miles de tokens y el ahorro que da en las consultas es incierto.
