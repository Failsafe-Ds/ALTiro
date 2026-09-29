# Propuesta de arquitectura — Sprint 3: catálogo, cobertura y agenda

- Estado: **Borrador — decisiones D-1 a D-16 aplicadas como PROVISIONALES el 2026-09-29.** Se usó la opción recomendada sin respuesta del equipo, según la instrucción de `docs/Reanudar.md`. Quedaron registradas en ADR-018 a ADR-021 y se revisan en la revisión del sprint. D-17 y las preguntas P-12 a P-17 van al representante.
- Preparado por: agente `architect`, sobre `fd6449b`, con el S2 en QA.
- Alcance (informe §5.3.5): "Catálogo, cobertura y agenda, con RF-05 a RF-07, RF-36 y RNF-18". Incremento esperado: "Perfil de maestro completo y publicable".
- Compromisos que llegan desde sprints anteriores: DA-03, DA-12, DA-14, DA-15 y DA-17. P-01 y P-02 siguen provisionales.

---

## 1. Alcance

### 1.1 Requerimientos funcionales

| ID | Texto del informe | Criterio | HU | S3 |
|---|---|---|---|---|
| RF-05 | "…declarar sus servicios con modalidad de precio por trabajo o por hora y su monto" | "Cada servicio publicado tiene modalidad y monto; no se publica sin ambos" | HU-12 | Completo |
| RF-06 | "…declarar sus comunas de cobertura e identificar una como comuna base" | "Un maestro sin comuna base no aparece en resultados" | HU-13 | Completo. "Resultados" se verifica en el perfil público; la búsqueda es de S4 |
| RF-07 | "…declarar días y bloques disponibles en formato de 24 horas" | "Se rechaza un rango cuya hora de término no sea posterior a la de inicio" | HU-14 | Completo (solo la declaración) |
| RF-36 | "…administrar el catálogo de oficios, servicios, modalidad de precio y precios de referencia" | "Un servicio nuevo queda disponible para los maestros sin intervención en el código" | HU-20 | Completo; cierra DA-15 |
| RF-34 (DA-12) | Desactivar servicios regulados sin licencia vigente | "El maestro deja de aparecer en ese oficio y sigue apareciendo en los no regulados" | HU-24 | En servicios y perfil público; la búsqueda es de S4 (DA-13) |
| RF-37 | Bitácora de acciones sobre el catálogo | — | HU-19 | Se usa para el catálogo; RF-37 completo en S5 |

### 1.2 Criterios de aceptación
- **Se entregan en S3:** CA-12.1, CA-12.2, CA-13.1, CA-14.1, CA-14.2, CA-14.4, CA-20.1, CA-20.2, CA-24.1 y CA-24.3 (servicios).
- **Parcial:** CA-13.2, solo en el perfil público; en la búsqueda, S4.
- **No entran en S3:** CA-14.3 (necesita tickets) y CA-24.4 (búsqueda). Ambos son de S4.

### 1.3 Requerimientos no funcionales
- **RNF-18:** "Las dos últimas versiones de Chrome y Firefox, y Chrome en Android, sin que haya que desplazar la pantalla de lado en celulares angostos". Se aplica a todas las pantallas, incluidas las de S1 y S2.
- **RNF-25 (DA-14):** evidencia en el catálogo público y el perfil público. La búsqueda es de S4.
- **RNF-13 (DA-17):** se ejecuta en la semana 1.
- **RNF-07:** todas las rutas nuevas.
- **RNF-11:** se mantiene.
- **RNF-14 a RNF-17 y RNF-20:** en las pantallas nuevas.
- **RNF-04 y RNF-23:** sin degradación.
- **RNF-27:** revisión de avisos de dependencias al inicio.

### 1.4 Doble reserva
- **S3 (declarar disponibilidad):** validar en el servidor el rango (CA-14.2), la granularidad, que el bloque no cruce la medianoche y que no se solape con otros bloques propios (NTI-02). Declarar un bloque "no compromete su asistencia" (HU-14).
- **S4 (reservar):** solo la aceptación ocupa el bloque (HU-06). Incluye CA-14.3, CA-06.2, RF-16, RF-19, CA-23.5 y RF-20.

### 1.5 Fuera del S3
- **S4:** búsqueda y ordenamiento (RF-09 a RF-13), la ficha completa (RF-14) y los tickets (RF-15 a RF-24).
- **S5:** calificaciones y mensajería.
- **Fuera de alcance:** pagos.

---

## 2. Decisiones (provisionales, 2026-09-29)

| ID | Decisión aplicada | ADR |
|---|---|---|
| D-1 | Catálogo `oficio` + `servicio` + `servicio_modalidad(servicio, modalidad, precio_referencia)`, con la modalidad en una lista cerrada {`por_trabajo`, `por_hora`} (RF-05 fija esas dos) | ADR-018 |
| D-2 | `regulado` es obligatorio al crear el oficio e **inmutable** desde la aplicación; cambiarlo exige una migración y un ADR (RNF-25) | ADR-018 |
| D-3 | El CSV de oficios es solo la carga inicial; `carga.cargar` pasa a solo insertar, sin pisar lo que haya cambiado comercial | ADR-018 |
| D-4 | Motivo obligatorio para modificar o dar de baja (motivo fijo, que se puede completar, al crear); `version` con 409; sin borrado físico (`activo=false`); bitácora en la misma transacción | ADR-018 |
| D-5 | Un servicio por (maestro, servicio del catálogo); la modalidad debe ser una admitida; monto entero en pesos, mayor que 0, con tope técnico de 10.000.000; sin borradores; baja lógica | ADR-019 |
| D-6 | La visibilidad de un servicio regulado **se calcula en cada lectura**, con una sola función que reutiliza `oficio_habilitado`; no hay marca guardada ni tarea | ADR-019 |
| D-7 | El maestro edita servicios, cobertura y agenda en cualquier estado salvo `rechazado` (409); solo el expediente `aprobado` publica | ADR-019 |
| D-8 | `cobertura(maestro, comuna, es_base)`, con exactamente una comuna base (CA-13.1) y comunas del catálogo de ADR-012 | ADR-019 |
| D-9 | La agenda es un **patrón semanal** (`dia_semana`, rango). El ticket de S4 guarda una copia de fecha, inicio y fin | ADR-020 |
| D-10 | Minutos desde la medianoche, en múltiplos de 30, con `0 ≤ inicio < fin ≤ 1440`; sin cruce de medianoche; selector propio de 24 h (no `<input type="time">`) | ADR-020 |
| D-11 | El solapamiento de bloques propios lo verifica el servicio con `select_for_update`; se permiten bloques contiguos; `EXCLUDE` con gist solo si la extensión está disponible | ADR-020 |
| D-12 | Perfil público parcial con una `ref` pública propia (nombre, foto, servicios visibles, comunas, agenda semanal). Un maestro no publicado responde el mismo 404 que una ref inexistente, sin registro. Es un adelanto parcial de RF-14 | ADR-019 |
| D-13 | Foto de perfil obligatoria para publicarse. Se recodifica con Pillow sin EXIF, en variantes de 160 y 480 px, en un volumen `fotos` solo de `app`, sin cifrar (su finalidad es ser pública) y se entrega solo si el maestro está publicado. Es un adelanto del dato de RF-13 | ADR-021 |
| D-14 | Se muestra el nombre registrado y las comunas atendidas **sin indicar cuál es la comuna base** (minimización) | ADR-019 |
| D-15 | RNF-18: "celular angosto" = 320 px CSS. Playwright con Chromium y Firefox en dos versiones, y un pase manual en Chrome y Firefox de escritorio y en Chrome de Android | Documento de pruebas |
| D-16 | `GET /api/oficios` y `/api/catalogo` con `Cache-Control: no-cache` y ETag, porque la caché de una hora incumpliría CA-20.2 | ADR-018 |
| D-17 | Agregar un oficio después de aprobado: fuera del S3 | Pregunta P-16 |

Preguntas para el representante (P-12 a P-17): ver `docs/alcance/preguntas-representante-s2.md`.

---

## 3. Modelo de datos (resumen)
- **`oficio`:** se le agregan `ref` UUID único, `activo` y `version`. Atención: en Django, `AddField(UUIDField(default=uuid4))` asigna el **mismo** valor a todas las filas existentes. Hay que hacerlo en tres pasos: campo nulo, luego `RunPython` para llenarlo y al final `unique`.
- **`servicio`:** `ref`, `oficio` (PROTECT), `nombre`, `activo`, `orden`, `version`. UNIQUE(oficio, nombre).
- **`servicio_modalidad`:** `servicio`, `modalidad` (CHECK), `precio_referencia` > 0. UNIQUE(servicio, modalidad). Todo servicio activo tiene al menos una modalidad.
- **`perfil_publico`** (app `perfil`): OneToOne con `perfil_maestro`, `ref` pública, `foto`, `foto_actualizada_en`. Se crea junto con `perfil_maestro` y entra en el invariante; una migración de datos lo crea para los maestros que ya existen.
- **`servicio_maestro`:** `ref`, maestro, servicio (PROTECT), modalidad, monto, fechas, `retirado_en`. Único parcial (maestro, servicio) activo. Sin FK a `oficio_maestro`.
- **`cobertura`:** maestro, comuna, `es_base`. UNIQUE(maestro, comuna) y único parcial de la base.
- **`disponibilidad`:** `ref`, maestro, `dia_semana` (1–7, ISO), `inicio_min`, `fin_min` (CHECK), `retirado_en`. Las filas no se modifican: editar es dar de baja y crear otra.
- **Regla única de publicación** (`perfil/publicacion.py`): `motivos_no_visible(servicio_maestro, hoy)`, `visible`, `maestro_elegible` (aprobado, con comuna base y con foto) y `maestro_publicado`. La usan el maestro, el perfil público y la búsqueda de S4.
- **Refactor:** `licencia_habilitante_de(licencias, hoy)` pasa a ser una función pura en `expediente/vigencia.py`, para cargar en lote en S4 sin duplicar la regla E-1.

## 4. Interfaz del servidor (resumen)

**Públicas**
- `GET /api/catalogo` y `GET /api/oficios`.
- `GET /api/maestros/publicos/<uuid:ref>` y `/foto`. Un maestro no publicado responde el mismo 404 que una ref inexistente, sin registro, con lista explícita de campos: nunca RUT, contacto, documentos ni comuna base.

**Maestro (patrón "me")**
- `GET /api/maestros/perfil`, `POST /api/maestros/perfil/foto`.
- `GET` y `POST /api/maestros/servicios`; `PATCH` y `DELETE .../servicios/<uuid:ref>`, con política de dueño.
- `GET` y `PUT /api/maestros/cobertura`.
- `GET` y `POST /api/maestros/disponibilidad`; `DELETE .../<uuid:ref>`.

**Comercial**
- `GET /api/comercial/catalogo`.
- `POST` y `PATCH /api/comercial/oficios[/<uuid:ref>]`, `POST` y `PATCH /api/comercial/servicios[/<uuid:ref>]`, con bitácora, versión y motivo.

**Pruebas de terceros en todas las rutas con identificador (RNF-07, DA-03)**
- Otro maestro recibe el 404 idéntico, con registro.
- Los demás roles reciben 403, con registro.
- Un anónimo recibe 401.

## 5. Frontend (resumen)
- **Maestro:** `mi-perfil`, `mis-servicios`, `mi-cobertura` y `mi-agenda`. Mobile-first, con pasos de 5 campos o menos y guardado en el servidor en cada paso. El estado de cada servicio se muestra con texto e ícono ("No lo ven los clientes: tu licencia de Gas venció…").
- **Público:** `perfil-maestro.html?m=<uuid>`.
- **Comercial:** `comercial.html`.
- `js/formato.js` concentra la hora de 24 h y el monto en `es-CL`.
- En pantalla se dice "comuna principal" por la "comuna base" del informe (RNF-17).

## 6. Orden de implementación
0. **Inicio:** RNF-27, decisiones, ejecución de RNF-13 (DA-17), preguntas P-12 a P-17 y defectos de QA del S2.
1. Catálogo administrable (RF-36, CA-20.1, CA-20.2).
2. Servicios del maestro y regla de publicación (RF-05, CA-12.1, CA-12.2, RF-34, CA-24.1, CA-24.3).
3. Cobertura (RF-06, CA-13.1).
4. Agenda (RF-07, CA-14.1, CA-14.2, CA-14.4).
5. Foto, lista de pendientes y perfil público (evidencia de RNF-25).
6. RNF-18 en todas las pantallas, cierre de UX, RNF-04 y RNF-23, y QA.

## 7. Riesgos y registros de alcance
- **Riesgos:**
  - RNF-13 falla.
  - D-9 resulta equivocado (el ticket guarda una copia de fecha, inicio y fin, y eso aísla el cambio).
  - Fotos inapropiadas, sin moderación definida.
  - N+1 en S4.
  - Horario de verano en S4.
  - La trampa de UUID en `AddField`.
  - `CAMPOS_CONOCIDOS`.
- **Registros de alcance:**
  - Cierres: DA-12, DA-15, DA-17 y la parte S3 de DA-14.
  - Adelantos de S4 a S3: el perfil público parcial (RF-14) y la foto (dato de RF-13).
  - A S4: la evidencia de RF-06 en "resultados", CA-13.2 y CA-14.3.
  - RNF-18 retroactivo sobre S1 y S2.

## 8. Aclaraciones de implementación (incrementos 1 y 2, 2026-09-29, provisionales)
1. **Código de un oficio nuevo:** se deriva del nombre (ASCII, `[a-z0-9_]`, con sufijo `_2` si ya existe). Comercial no lo escribe.
2. **`orden` opcional:** si no se indica, toma el siguiente. Los nombres de servicio son únicos dentro de su oficio, sin distinguir mayúsculas. El precio de referencia tiene el mismo tope técnico de 10.000.000.
3. **Modalidades de un servicio:** cambiarlas reemplaza el conjunto completo; lo anterior queda en la bitácora. Una modificación sin cambios responde 400. Dos altas simultáneas con el mismo nombre: la segunda responde 409.
4. **`/api/oficios` lista solo oficios activos.** Declarar un oficio dado de baja se rechaza en el incremento 3. Las declaraciones que ya existían se conservan.
5. **El comando `cargar_datos_demo` no escribe en la bitácora**, igual que la carga del CSV: la consola no identifica a quien lo ejecuta (ADR-010). Deja un evento de aplicación con el conteo.
6. **Migración 0003:** como `cargar` ahora solo inserta, 0003 ya no corrige nombres en una base que siga con los códigos `ejemplo_N`. Eso solo afecta a bases no actualizadas desde antes del S2.
7. **Mientras no existan la cobertura (incremento 3) y la foto (incremento 5), ningún servicio es visible.** La regla ya las exige.

## 9. Aclaraciones de implementación (incrementos 3 a 5, 2026-09-29, provisionales)
1. **Caché de la foto pública:** `no-cache` + ETag (SHA-256, sin nombre de archivo). Antes de responder 304, el servidor vuelve a exigir que el maestro esté publicado: si deja de estarlo, la foto deja de entregarse de inmediato.
2. **Variantes de la foto:** el lado mayor queda en 160 o 480 px, sin recortar ni ampliar.
3. **Bloqueo por maestro:** `select_for_update` sobre la fila del expediente, que es una por maestro. Es la misma que ya protege servicios y estados, y serializa al maestro con curatoría. No se agregó `EXCLUDE USING gist`, porque `altiro_app` no es superusuario; la concurrencia la cubre el bloqueo, y tiene su prueba.
4. **Foto con el expediente rechazado:** responde 409, con el mismo criterio que servicios, cobertura y agenda (D-7).
5. **El maestro no ve su propia foto antes de publicarse.** Solo recibe `tiene_foto`.
6. **Perfil público:** las comunas van por nombre y sin `es_base`, de modo que el orden tampoco revela cuál es la base (D-14).
7. **Claves de error:** la cobertura usa `comunas`; en la agenda, el solapamiento va en `inicio` y el término no posterior en `fin`.
8. **"Recarga la página" → "Vuelve a cargar la página"** en todos los mensajes del servidor (RNF-17), en coherencia con el botón «Volver a cargar» del frontend.
