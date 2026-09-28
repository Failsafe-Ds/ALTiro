# ADR-011 — Identificadores públicos y respuesta ante acceso denegado

- Estado: **Borrador** (pendiente de revisión final del equipo)
- Fecha: 2026-09-27
- Relacionado con: RNF-07, CA-25.1, CA-25.3, R-01, R-05

## Contexto
R-01 (§6.1.2) menciona que "los registros se numeran de forma predecible". El control principal contra el acceso a recursos ajenos es la autorización en servidor (RNF-07).

## Decisión propuesta

### Identificadores
- Clave numérica interna y **UUID en las URL** de los recursos sensibles a partir de S2, como defensa en profundidad.
- En S1 las rutas de cuenta no reciben identificador (patrón "me").
- El ticket conserva su número visible, porque es "la unidad que el sistema numera" (§2.3). El UUID es solo para la URL y no reemplaza ese número.

### Respuesta ante denegación
- **404** con mensaje neutro cuando el recurso existe pero pertenece a otro usuario, para no revelar su existencia.
- **403** cuando falta el rol en una ruta cuya existencia no es secreta.
- Solo en el primer caso (recurso existente denegado por la política) se inserta una fila en `acceso_denegado` (ADR-010).

## Alternativas consideradas
- **Solo IDs secuenciales**: más simple, pero facilita la enumeración.
- **403 uniforme**: revela que el recurso existe.

## Consecuencias
- Afecta a documentos (S2), tickets (S4) y conversaciones (S5).
