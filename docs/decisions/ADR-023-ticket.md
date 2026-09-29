# ADR-023 — Ticket y orden: modelo, transiciones, privacidad y doble reserva

- Estado: **Aceptada — PROVISIONAL** (2026-09-29). Se aplicó la opción recomendada sin respuesta del equipo, según `docs/Reanudar.md`. Se revisa en la revisión del Sprint 4.
- Relacionado con: RF-15 a RF-24, RNF-07, RNF-08, HU-06, HU-10, HU-15, HU-23, HU-25, CA-06.x, CA-10.x, CA-14.3, CA-15.x, CA-23.x, CA-25.1, V-03; ADR-010, ADR-011, ADR-013 E-9, ADR-020 E-1
- Origen: propuesta del S4, D-9 a D-13, D-21 y D-22.

## Decisión
1. **Modelo (app `tickets`):**
   - `ticket` es el mismo registro lógico para ticket y orden (§2.3).
   - Identidad: `id` es el número visible, pero nunca va en la URL ni se acepta como entrada. Las URL usan `ref` UUID (ADR-011).
   - Copias al crear:
     - `modalidad` y `monto_publicado` (RF-15);
     - `fecha`, `inicio_min` y `fin_min` del bloque (ADR-020), con `inicio_en` y `fin_en` en timestamptz (ADR-020 E-1).
   - Datos del pedido: `comuna` (debe estar en la cobertura), `direccion`, `descripcion` y `materiales`. `materiales` es booleano NOT NULL y la interfaz no le pone valor por defecto (CA-06.4).
   - Estados: `pendiente`, `aceptado`, `finalizado` y `cerrado`.
   - `motivo_cierre` ∈ {`vencido_plazo`, `vencido_proximidad`, `cancelado_cliente`, `rechazado_maestro`, `bloque_tomado`}. Hay un CHECK de que existe si y solo si el estado es `cerrado`.
   - Plazo: `vence_en = LEAST(enviado_en + 24 h, inicio_en − 4 h)`, con `enviado_en` calculado en Python (ADR-014).
   - CHECK de defensa en la base:
     - `inicio_en > enviado_en + 4 h` (RF-16);
     - la fórmula de `vence_en`;
     - `inicio_min < fin_min`;
     - coherencia entre estado y fechas;
     - `cliente ≠ maestro` (ADR-013 E-9).
2. **Historial:** `ticket_evento` es de solo inserción. Usa triggers y `managed=False`, sin FK de autor (patrón de ADR-010).
   - Guarda estado anterior, estado nuevo, motivo, autor (`usuario` o `sistema`) y fecha.
   - No es la bitácora administrativa (RF-37, M-03).
3. **Transiciones:**

   | De | A | Quién y condiciones |
   |---|---|---|
   | — | pendiente | El cliente. Se exige: maestro publicado, servicio visible, comuna en la cobertura, ocurrencia ofrecible (CA-06.2) y datos completos (CA-06.4) |
   | pendiente | aceptado | El maestro del ticket, con `ahora < vence_en`, el servicio todavía visible (D-11: si no, 409) y sin cruce con otro aceptado |
   | pendiente | cerrado | Tres casos:<br>• el maestro lo rechaza → `rechazado_maestro`;<br>• el cliente lo cancela → `cancelado_cliente` (CA-23.3);<br>• un efecto de aceptación sobre otro pendiente del mismo maestro con rangos que se cruzan (D-12) → `bloque_tomado`, con autor el maestro que aceptó |
   | pendiente | cerrado | El Sistema, o la **protección al actuar**, cuando `ahora ≥ vence_en`:<br>• `vencido_proximidad` si `inicio_en − 4 h ≤ enviado_en + 24 h` (a las 28 horas exactas cuenta como proximidad, CA-23.6);<br>• si no, `vencido_plazo` |
   | aceptado | finalizado | S5 (RF-26 y RF-27) |

   - Cualquier otra transición responde 409 con un mensaje accionable.
   - El cliente no puede cancelar un ticket aceptado (CA-10.2).
   - Repetir una acción que ya se aplicó responde 200 con el estado actual (idempotencia, D-10).
   - Un pendiente cuyo servicio dejó de ser visible se queda pendiente: se puede rechazar y vence solo. No se inventa un sexto motivo.
4. **Doble reserva (D-9):**
   - Primero se bloquea (`select_for_update`) la fila del `expediente` del maestro y después los tickets por id ascendente.
   - En la base:
     - único parcial `(perfil_maestro, inicio_en) WHERE estado IN ('aceptado','finalizado')`;
     - único parcial de pendiente `(cliente, maestro, inicio_en) WHERE estado='pendiente'` (D-10).
   - **Sin `EXCLUDE USING gist`:** `btree_gist` es *trusted* (verificado el 2026-09-29), pero `altiro_app` no tiene CREATE sobre la base. El cruce de rangos lo protege el bloqueo por maestro, con su prueba de concurrencia.
   - La tarea de cierre usa `skip_locked`.
5. **Privacidad (RF-17, RNF-08):** hay dos serializaciones con lista explícita de campos, según la relación con **ese** ticket (ADR-013, punto 2.6).
   - El bloque de contacto solo existe si el ticket fue **aceptado**:
     - para el maestro: dirección, teléfono y nombre del cliente;
     - para el cliente: el teléfono del maestro (D-21, contacto mutuo; P-20).
   - Mientras está pendiente, el maestro ve servicio, descripción, comuna, bloque y materiales, **sin el nombre del cliente** (D-13; P-20).
   - Un ticket cerrado desde pendiente nunca revela la dirección.
6. **Autorización:**
   - `PoliticaTicket`: solo el cliente o el maestro de ese ticket. Cualquier otro, incluidos los roles administrativos, recibe el 404 idéntico con registro (CA-25.1).
   - La parte equivocada de una acción (por ejemplo, el cliente que intenta aceptar) recibe 403 registrado.
7. **Precio final (D-22):** se queda en el S5 (RF-26 y RF-27). En el S4 solo se preparan las copias, el estado `finalizado` y `finalizado_en`.
