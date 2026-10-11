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

## Enmiendas

### E-1 — Renovación de una licencia en un expediente aprobado
- **Fecha:** 2026-09-28.
- **Motivo:** la implementación del incremento 2 mostró que, si un maestro aprobado sube una licencia SEC nueva, la anterior validada pasa a `reemplazado`. Con eso el oficio regulado quedaría sin habilitar hasta que curatoría revisara la nueva, y renovar a tiempo suspendería al maestro. Este caso no estaba decidido.
- **Cambio:**
  - Una licencia `reemplazado` que estaba `validado` **sigue contando** para habilitar el oficio y para `faltantes_para_aprobar` mientras se cumplan dos condiciones:
    - (a) sigue vigente;
    - (b) la licencia que la reemplazó todavía no está `validado`.
  - Cuando curatoría valida la nueva, cuenta solo la nueva.
  - Si curatoría observa la nueva, la anterior sigue contando hasta que venza.
  - Nunca se habilita un oficio con una licencia sin revisar (punto 4).
  - La regla vive solo en `expediente/vigencia.py`.
- **Aprobación:** equipo de desarrollo, 2026-09-28.

### E-2 — Documentos faltantes que ve el maestro
- **Fecha:** 2026-09-28.
- **Motivo:** no estaba definido si un documento en revisión cuenta como entregado en la lista de faltantes que ve el maestro.
- **Cambio:**
  - En la vista del maestro, un documento `en_revision` u `observado` cuenta como **entregado**, y su estado se muestra aparte, por documento (RF-08, CA-17.2).
  - La regla para aprobar no cambia: exige documentos `validado` y licencias vigentes (punto 3).
- **Aprobación:** equipo de desarrollo, 2026-09-28.

### E-3 — Acceso a documentos reemplazados
- **Fecha:** 2026-09-28.
- **Motivo:** no estaba definido si un documento `reemplazado` (conservado según el punto 5) se puede abrir. Surgió al implementar la descarga (incremento 3), donde se entrega solo el documento actual.
- **Cambio:**
  - Curatoría puede abrir los documentos reemplazados desde el historial del expediente, con el mismo enlace de 600 s (ADR-015) y el conflicto de interés de ADR-011 E-2. Nunca puede abrirlos quien sea dueño del expediente.
  - El dueño ve y abre solo sus documentos actuales.
  - Los demás usuarios reciben el 404 neutro con registro (CA-25.2).
- **Motivo del acceso:** comparar una licencia renovada con la anterior (E-1).
- **Aprobación:** equipo de desarrollo, 2026-09-28.

### E-4 — La cédula exige fecha de vencimiento; cada paso explica qué documento pide (PROVISIONAL)
- **Fecha:** 2026-10-11 (pulido post-S5). Pedido del usuario: «en el paso 2 no se explica qué documento pide fecha de caducidad y emisión; ¿la cédula? Esas siempre vencen».
- **Cambio:**
  - la **cédula de identidad** exige `fecha_vencimiento`; el servidor responde 400 en el campo si falta. Para el certificado de antecedentes y la licencia SEC sigue siendo opcional (RF-04 y CA-11.2 se mantienen: «un documento puede tener o no vencimiento»);
  - cada paso de documento dice qué documento es, y dónde se lee cada fecha en él. Por ejemplo, «Fecha de emisión: aparece como "Fecha de emisión" en tu cédula» y «Fecha de vencimiento: aparece como "Fecha de vencimiento"»; la fecha opcional se marca como «(si tiene)»;
  - al ir al paso siguiente y volver, el paso conserva las fotos ya elegidas y las fechas escritas mientras la página siga abierta. Al recargar, las fotos no se pueden conservar (el navegador no lo permite) y el paso lo dice.
- **Datos existentes:** las cédulas ya cargadas sin vencimiento siguen siendo válidas; la regla aplica a las cargas nuevas. No hay migración que altere datos.
