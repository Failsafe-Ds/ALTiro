# ADR-019 — Servicios del maestro, cobertura y regla única de publicación

- Estado: **Aceptada — PROVISIONAL** (2026-09-29). Se tomó la opción recomendada sin respuesta del equipo, según `docs/Reanudar.md`. Se revisa en la revisión del Sprint 3.
- Relacionado con: RF-05, RF-06, RF-33, RF-34, RF-13 y RF-14 (parciales), RNF-25, HU-12, HU-13, HU-24, HU-25, CA-12.1, CA-12.2, CA-13.1, CA-24.1, CA-24.3, NTI-09, DA-12, DA-14
- Origen: propuesta del S3, decisiones D-5 a D-8, D-12 y D-14.

## Decisión
1. **Servicio del maestro (D-5):**
   - Hay uno por (maestro, servicio del catálogo), y la modalidad debe estar entre las que admite ese servicio.
   - El monto es un entero en pesos, mayor que 0, con un tope técnico de 10.000.000 (validación de entrada, no regla de negocio).
   - No hay borradores: si falta la modalidad o el monto, responde 400 en el campo (CA-12.1). La base de datos lo garantiza además con NOT NULL y CHECK.
   - Baja lógica mediante `retirado_en`. Así S4 puede enlazar el servicio desde el ticket, que de todos modos copia la modalidad y el monto (RF-15).
   - No hay FK hacia `oficio_maestro`: si el maestro deja de declarar un oficio, el servicio deja de ser visible por cálculo.
2. **Visibilidad calculada (D-6):**
   - Una única función (`perfil/publicacion.py`) calcula en cada lectura si un servicio es visible y, si no, por qué:
     - retirado;
     - catálogo inactivo;
     - oficio no declarado;
     - modalidad no admitida;
     - licencia no vigente (reutiliza `oficio_habilitado` y ADR-017 E-1);
     - maestro no elegible.
   - No se guarda una marca de "inactivo": un planificador que corre cada hora dejaría una hora de exposición, y eso incumpliría RNF-25 y CA-24.1.
   - La reactivación ocurre sola cuando curatoría valida una licencia nueva.
   - "Hoy" se toma de `hoy_negocio()`. El día del vencimiento la licencia ya no está vigente.
   - La búsqueda de S4 reutiliza esta misma función.
3. **Edición (D-7):**
   - El maestro edita servicios, cobertura y agenda en cualquier estado salvo `rechazado` (409).
   - Solo un expediente `aprobado` publica.
   - Maestro elegible = aprobado + comuna base + foto (ADR-021). Maestro publicado = elegible + al menos un servicio visible.
4. **Cobertura (D-8):**
   - Tabla `cobertura(maestro, comuna, es_base)`, que se reemplaza completa en cada guardado.
   - Exactamente una comuna base (CA-13.1), garantizada con un índice único parcial más la verificación del servicio.
   - Las comunas son las del catálogo de ADR-012. No hay tope de comunas.
5. **Perfil público (D-12):**
   - `GET /api/maestros/publicos/<uuid:ref>` usa una `ref` pública propia, distinta de la del expediente.
   - Si el maestro no está publicado, responde el mismo 404 que una ref inexistente, sin registro.
   - Es un adelanto parcial de RF-14: sin calificaciones (S5) ni bloques ocupados (S4).
6. **Minimización (D-14):**
   - Se muestra el nombre tal como está registrado, la foto, los servicios visibles con modalidad y monto, las comunas atendidas **sin indicar cuál es la base**, y la agenda semanal.
   - Nunca se muestra RUT, teléfono, correo, documentos, estado o motivos del expediente, fechas de licencia ni identificadores internos.
   - **[VALIDA REPRESENTANTE] P-15:** nombre completo o parcial.

## Enmiendas

### E-1 — Regla de visibilidad pura con contexto cargado en lote (PROVISIONAL)
- **Fecha:** 2026-09-29.
- **Cambio:**
  - `motivos_no_visible(servicio_maestro, hoy)` se divide en dos:
    - una parte pura, `motivos_no_visible_de(servicio_maestro, ctx, hoy)`, que recibe ya cargados los oficios declarados, las modalidades admitidas, las licencias (evaluadas con `licencia_habilitante_de`) y la elegibilidad;
    - un envoltorio que arma `ctx` con consultas y llama a la parte pura.
  - La búsqueda de S4 arma `ctx` en lote (RNF-01).
  - El comportamiento no cambia: las pruebas del S3 siguen en verde.
- **Aprobación:** equipo de desarrollo (provisional), 2026-09-29.
