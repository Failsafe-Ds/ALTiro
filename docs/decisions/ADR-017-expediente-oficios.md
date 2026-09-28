# ADR-017 — Expediente del maestro, revisión de documentos y catálogo mínimo de oficios

- Estado: **Aceptada** — 2026-09-28, aprobada por el equipo de desarrollo. La lista de oficios y los documentos obligatorios quedan como **supuestos a validar con el representante del producto**.
- Fecha: 2026-09-28
- Relacionado con: RF-04, RF-08, RF-32, RF-33, RF-34, RNF-25, HU-11, HU-17, HU-19, HU-24, CA-17.2, CA-19.1 a CA-19.4, M-05
- Origen: propuesta del S2, decisiones D-1, D-2, D-10 y D-11.

## Decisión
1. **Catálogo mínimo de oficios (D-1):**
   - Nueva app `catalogo` con la tabla `oficio(codigo, nombre, regulado, orden)`.
   - Se carga desde un CSV versionado con una migración idempotente. Es de solo lectura y no tiene endpoints de escritura (mismo patrón que ADR-012).
   - Es un **adelanto de datos** del S3. No adelanta RF-36.
   - El informe confirma como regulados Gas y Electricidad (§3.4, RNF-25). Los otros seis oficios de la red (§2.2) son un **supuesto a validar**.
2. **Estados (D-2):**
   - **Expediente:**
     - `en_revision`: estado inicial; se crea junto con `perfil_maestro`.
     - `observado`, `aprobado` y `suspendido`.
     - `rechazado`: terminal.
   - **Documento:** `en_revision`, `observado`, `validado` y `reemplazado`. La vigencia se calcula y no es un estado.
   - Todas las transiciones del expediente cumplen estas condiciones:
     - las ejecuta curatoría, y quien las ejecuta no es el dueño del expediente (CA-19.4);
     - exigen un motivo escrito (CA-19.1);
     - registran la entrada en la bitácora en la misma transacción (CA-19.3).
   - La tabla de transiciones está en la propuesta del S2, §3.
   - En S2, ni el maestro ni el actor Sistema cambian nunca el estado del expediente.
3. **Requisitos para aprobar:**
   - Documentos exigidos: cédula por ambos lados, certificado de antecedentes y una licencia SEC por cada oficio regulado declarado.
   - Todos deben estar `validado`, y las licencias deben estar vigentes (RF-33).
   - Solo RF-33 es textual; el resto es un **supuesto a validar**.
   - Al pasar de `suspendido` a `aprobado` se vuelve a verificar RF-33.
4. **Revisión por documento (D-10):**
   - Curatoría valida u observa cada documento.
   - Observar exige un motivo (CA-17.2). Validar registra un motivo fijo que se puede completar.
   - Un oficio regulado está habilitado si tiene una licencia `validado` y vigente para ese oficio. La regla es única, vive en `expediente/vigencia.py` y la reutilizarán S3 y S4.
5. **Reemplazo (D-11):**
   - Hay un solo documento actual por (expediente, tipo, oficio), garantizado con un índice único parcial.
   - Subir otro del mismo tipo reemplaza al actual:
     - si el actual no se había revisado, su archivo se borra;
     - si ya estaba revisado, queda `reemplazado` y se conserva hasta RNF-26 y V-04.

## Pendiente — [VALIDA REPRESENTANTE]
- Nombres de los ocho oficios, y si "gasfitería" es regulada o solo lo es "gas".
- Documentos obligatorios, reactivación de un expediente suspendido y rechazo terminal (el RUT es único: CA-11.3).
