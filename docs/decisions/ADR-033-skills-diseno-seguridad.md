# ADR-033 — Skills de diseño (`impeccable`) y de seguridad (`security-audit`) para los agentes

- Estado: **Propuesta** — 2026-10-31; instaladas a pedido del usuario (sesión del 2026-10-30).
- Fecha: 2026-10-31
- Relacionado con: ADR-002 (E-3, E-4.4), ADR-025 (graphify como herramienta del equipo), CLAUDE.md §8, §13 y §15

## Contexto
- Hasta el 2026-10-30 el agente `frontend` usaba el plugin UI/UX Pro Max (ADR-002 E-3, pila `html-css`).
- El usuario pidió reemplazarlo por una skill de refinamiento de interfaz y sumar una skill de auditoría de seguridad.
- Las skills son herramientas de trabajo de los agentes: no forman parte del producto, no se despliegan y no agregan dependencias a la imagen `app`.

## Decisión
1. **Diseño:** se retira UI/UX Pro Max y se instala `impeccable` 4.8.0 en `.claude/skills/impeccable/` (licencia Apache 2.0, incluida en la carpeta).
   - El agente `frontend` la usa en modo *Operate* y solo como **refinamiento** (`.claude/agents/frontend.md`): conserva la identidad de ADR-002 E-3 y `design-system/altiro/MASTER.md`.
   - No se usan `visualize`, `live` ni `generate`, ni sus hooks, ni servicios externos para generar imágenes (CLAUDE.md §13).
2. **Seguridad:** se instala `security-audit` en `.claude/skills/security-audit/` (Cloudflare, licencia MIT, incluida en la carpeta).
   - Sus artefactos de trabajo (`docs/testing/security-audit/`) no se versionan (`.gitignore`): pueden contener rutas, cargas de prueba y detalle de hallazgos aún abiertos.
   - Lo que el equipo quiera conservar se resume en `docs/testing/` sin datos personales ni secretos.
3. Las dos skills se versionan en el repositorio, como graphify (ADR-025), para que los tres integrantes trabajen con la misma versión.

## Consecuencias
- Primeros usos: `docs/testing/auditoria-diseno-impeccable-2026-10-30.md` (M-01 a M-15) y la auditoría de seguridad `run-1` (2 hallazgos confirmados de severidad baja, en corrección).
- Los hallazgos de una skill no cambian reglas de negocio ni el alcance: se tratan como cualquier defecto o cambio (CLAUDE.md §11).
- Actualizar una skill es un cambio de versión que se anota como enmienda de este ADR.

## Pendiente / preguntas abiertas
- Confirmación del equipo (revisión de sprint o representante del producto).
