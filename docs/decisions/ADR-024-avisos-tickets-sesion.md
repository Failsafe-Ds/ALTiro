# ADR-024 — Avisos de tickets, vocabulario y sesión

- Estado: **Aceptada — PROVISIONAL** (2026-09-29). Se tomó la opción recomendada sin respuesta del equipo, según `docs/Reanudar.md`. Se revisa en la revisión del Sprint 4.
- Relacionado con: RF-18, RF-24, RNF-09, RNF-17, CA-15.3, CA-23.5, CA-23.7; ADR-005, ADR-016
- Origen: propuesta del S4, D-14 a D-17.

## Decisión
1. **Tabla nueva `aviso_ticket`** (D-14): `ticket`, `destinatario`, `tipo`, `creado_en` y `visto_en`.
   - No guarda datos personales: el texto se arma al mostrarlo, con la serialización de quien lo lee (ADR-023, punto 5).
   - No reutiliza `aviso` (RF-35), que exige un documento.
2. **Tipos de aviso:**
   - `ticket_nuevo`: para el maestro, en la misma transacción que crea el ticket (RF-18).
   - `ticket_cerrado`: para **ambas partes**, con el motivo (RF-24, CA-23.7). En `bloque_tomado`, el aviso lleva un enlace a la búsqueda con alternativas (CA-23.5).
   - `ticket_aceptado`: para el cliente (D-15).
   - No hay correo ni SMS.
3. **Sesión (D-16):** no hay consultas periódicas. Los avisos se cargan al abrir cada pantalla y con el botón "Actualizar". Así se cumple ADR-005: las consultas que no hace el usuario no renuevan la sesión.
4. **Vocabulario (D-17, RNF-17):** en pantalla se dice "pedido" en vez de "ticket" y "trabajo aceptado" en vez de "orden". En el código se mantienen los términos del informe.
