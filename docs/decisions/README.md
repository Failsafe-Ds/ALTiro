# Decisiones técnicas (ADR)

Registro de decisiones técnicas que el informe (`docs/informe-altiro.md`) no define, según CLAUDE.md §15.

## Estados

- **Borrador**: propuesta sin aprobar. No debe implementarse como hecho.
- **Aceptada**: aprobada por el equipo; indicar fecha y quién aprobó.
- **Reemplazada**: sustituida materialmente por una ADR posterior; indicar cuál. Su texto se conserva (ver «Enmiendas y reemplazos»).

## Enmiendas y reemplazos

- La historia de una decisión **Aceptada** no se reescribe en silencio.
- Una decisión aceptada puede recibir una sección **"Enmiendas"** al final, para aclaraciones o refinamientos compatibles con lo decidido. Cada enmienda lleva un identificador (E-1, E-2…) y registra fecha, motivo, cambio, impacto y aprobación (quién aprobó y cuándo).
- En el cuerpo del ADR no se borra el texto original. Donde quedaría engañoso, se agrega una nota breve de remisión "(ver Enmienda E-x)". Donde una enmienda precisa el texto original, prevalece la enmienda.
- Una enmienda no cambia el estado: el ADR sigue **Aceptada**.
- Si una decisión posterior contradice o sustituye materialmente una decisión aceptada, se crea un **ADR nuevo** que la reemplaza e indica cuál reemplaza. El anterior se marca **Reemplazada por ADR-YYY** y conserva su texto.

## Índice

| ADR | Tema | Estado |
|---|---|---|
| — | [Propuesta de arquitectura del Sprint 1](sprint-1-propuesta-arquitectura.md) | Borrador |
| [ADR-001](ADR-001-framework-web.md) | Framework web | Aceptada (2026-09-27) |
| [ADR-002](ADR-002-estilo-interfaz.md) | Estilo de interfaz (API JSON + frontend estático) | Aceptada (2026-09-27) |
| [ADR-003](ADR-003-motor-base-datos.md) | Motor de base de datos relacional (PostgreSQL 16) | Aceptada (2026-09-27); Enmienda E-1 (2026-09-28) |
| [ADR-004](ADR-004-hash-contrasenas.md) | Hash de contraseñas (Argon2id, 64 MiB, t=3) | Aceptada (2026-09-28) |
| [ADR-005](ADR-005-sesiones.md) | Manejo de sesiones | Aceptada (2026-09-28) |
| [ADR-006](ADR-006-csrf.md) | Protección CSRF | Aceptada (2026-09-27); Enmienda E-1 (2026-09-28) |
| [ADR-007](ADR-007-limitacion-intentos.md) | Limitación de intentos de autenticación | Aceptada (2026-09-28) |
| [ADR-008](ADR-008-tls-local.md) | TLS en la demostración local | Aceptada (2026-09-27) |
| [ADR-009](ADR-009-configuracion-secretos.md) | Configuración y secretos | Aceptada (2026-09-27) |
| [ADR-010](ADR-010-bitacora-solo-escritura.md) | Bitácora administrativa y registro de accesos denegados | Aceptada (2026-09-28); CA-25.3 a validar con el representante |
| [ADR-011](ADR-011-identificadores-publicos.md) | Identificadores públicos y respuesta ante acceso denegado | Aceptada (2026-09-28); Enmienda E-1 (2026-09-28) |
| [ADR-012](ADR-012-catalogo-territorial.md) | Catálogo territorial (nacional, CUT 2018) | Aceptada (2026-09-28); alcance nacional a validar con la contraparte |
| [ADR-013](ADR-013-acceso-politica-contrasena.md) | Identificador de acceso, unicidad de datos de contacto, roles múltiples y política de contraseña | Aceptada (2026-09-27); Enmiendas E-1 a E-8 (2026-09-27) |
| [ADR-014](ADR-014-herramienta-pruebas.md) | Herramienta de pruebas | Aceptada (2026-09-27) |

## Plantilla

```
# ADR-XXX — Título

- Estado: Borrador | Aceptada (fecha, aprobó) | Reemplazada por ADR-YYY
- Fecha: AAAA-MM-DD
- Relacionado con: HU-XX, RF-XX, RNF-XX, NTI-XX, R-XX

## Contexto
## Decisión propuesta
## Alternativas consideradas
## Consecuencias
## Pendiente / preguntas abiertas
## Enmiendas (solo en decisiones aceptadas; ver «Enmiendas y reemplazos»)
```
