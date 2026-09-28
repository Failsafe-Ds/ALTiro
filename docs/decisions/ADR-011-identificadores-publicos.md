# ADR-011 — Identificadores públicos y respuesta ante acceso denegado

- Estado: **Aceptada** — 2026-09-28, aprobada por el equipo de desarrollo (ver «Decisión»).
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

## Decisión (2026-09-28)
Aprobada por el equipo de desarrollo a partir del análisis del agente `architect`. Relacionado además con HU-25, M-08 y RNF-22.

1. **UUID en la URL:** desde S2, toda ruta con identificador usa un `ref` UUID v4, único y no editable, junto a la clave numérica interna. Excepción: los códigos CUT públicos del catálogo territorial. El ticket conserva su número visible (§2.3), que nunca va en la URL. La prueba de control de RNF-07 verifica que esas rutas usen el convertidor `uuid`.
2. **Respuesta:** el 404 es **idéntico** (byte a byte) para un recurso inexistente y para uno ajeno, y es la denegación que exigen CA-25.1 y CA-25.2. Si falta el rol en una ruta cuya existencia no es secreta, se responde 403.
3. **Qué se registra en `acceso_denegado`:** el recurso ajeno denegado por la política y el 403 por falta de rol de un usuario autenticado (regla de HU-25: "cualquier otro acceso se deniega y queda registrado"). Nunca se registran los 401 anónimos, los fallos de CSRF, los 404 de referencias inexistentes ni los rechazos por reglas de negocio (400/409).
4. **Recurso:** se guarda el método más el **patrón** de la ruta, nunca la ruta cruda ni la cadena de consulta (minimización).
5. `obtener_autorizado` busca por `ref` sin filtrar por dueño y después aplica la política, para distinguir un recurso inexistente de uno ajeno.
