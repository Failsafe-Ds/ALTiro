# ADR-020 — Agenda: disponibilidad semanal por bloques de 24 horas

- Estado: **Aceptada — PROVISIONAL** (2026-09-29). Se tomó la opción recomendada sin respuesta del equipo, según `docs/Reanudar.md`. Se revisa en la revisión del Sprint 3.
- Relacionado con: RF-07, HU-14, CA-14.1, CA-14.2, CA-14.4, NTI-02, NTI-11, RNF-20; S4: RF-15, RF-16, CA-14.3
- Origen: propuesta del S3, decisiones D-9 a D-11.

## Decisión
1. **Patrón semanal (D-9):**
   - La disponibilidad se declara como `disponibilidad(dia_semana ISO 1–7, inicio, fin)`, sin fechas concretas ni excepciones.
   - HU-14 habla de declarar "mis días y bloques". La regla de HU-14 dice que declarar "no compromete su asistencia".
   - Con fechas concretas, un maestro con baja alfabetización digital tendría que declarar de nuevo cada semana (NTI-11).
   - **Contrato con S4:** el bloque concreto es (patrón, fecha), y el ticket guarda una copia de fecha, inicio y fin.
   - **[VALIDA REPRESENTANTE] P-13:** cómo organizan la semana los maestros.
2. **Formato (D-10):**
   - Minutos desde la medianoche (`inicio_min`, `fin_min`), en múltiplos de 30, con `0 ≤ inicio < fin ≤ 1440` (CHECK en la base de datos).
   - Un bloque no cruza la medianoche: CA-14.2 rechaza un término que no sea posterior al inicio.
   - Se muestra en formato "HH:MM" de 24 horas; el fin de día se muestra como 24:00.
   - Se elige con un **selector propio de 24 horas**, no con `<input type="time">`, que en Android con configuración regional en inglés muestra AM/PM e incumpliría CA-14.1.
   - La granularidad de 30 minutos es una decisión del equipo.
3. **Solapamiento (D-11):**
   - El servicio rechaza un bloque que se solape con otro bloque activo del mismo maestro y día. Usa `select_for_update` sobre el maestro (NTI-02: "validación de solapamiento en el servidor").
   - Se permiten bloques contiguos (08:00–12:00 y 12:00–16:00).
   - Una restricción `EXCLUDE USING gist` es defensa en profundidad y solo se agrega si `altiro_app` puede crear `btree_gist`.
4. **Inmutabilidad:** las filas no se modifican. Editar es dar de baja (`retirado_en`) y crear otra, para que un ticket de S4 no vea cambiar el bloque bajo él.
5. **Guardado por paso (CA-14.4):** cada bloque se guarda en una petición propia.
6. **Fuera del S3:** "bloque ocupado" (CA-14.3), la doble reserva y el cierre de tickets incompatibles son de S4.

## Enmiendas

### E-1 — Ocurrencias concretas y horario de verano (PROVISIONAL)
- **Fecha:** 2026-09-29.
- **Cambio:**
  - El módulo puro `perfil/ocurrencias.py` convierte el par (patrón, fecha) en instantes en `America/Santiago`.
  - Un `fin_min = 1440` corresponde a las 00:00 del día siguiente.
  - **Hora inexistente** (el salto hacia adelante): esa ocurrencia no se ofrece ese día.
  - **Hora repetida:** se usa `fold=0`, es decir, la primera de las dos.
  - Los plazos de 24 y 4 horas se miden en tiempo real transcurrido (UTC). "Hoy" y el día de la semana se calculan en Santiago.
  - Las pruebas buscan las transiciones de horario por programa, con `zoneinfo`.
- **Aprobación:** equipo de desarrollo (provisional), 2026-09-29.
