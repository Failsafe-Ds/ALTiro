# Propuesta de arquitectura — Sprint 2: expediente del maestro y curatoría

- Estado: **Borrador — decisiones D-1 a D-13 aprobadas por el equipo de desarrollo el 2026-09-28** (ADR-015, ADR-016, ADR-017, ADR-010 E-1 y ADR-011 E-2; D-6 en ADR-016; D-12 y D-13 sin ADR). Los puntos [VALIDA REPRESENTANTE] están en `docs/alcance/preguntas-representante-s2.md`.
- Fecha: 2026-09-28.
- Preparado por: agente `architect`, sobre el commit `ef4be30` (Sprint 1 cerrado).
- Alcance (informe §5.3.5): "Expediente del maestro y curatoría, con RF-04, RF-08 y RF-32 a RF-35, más RNF-25, RNF-13 a RNF-17 y RNF-20". Incremento esperado: "Verificación documental funcionando de extremo a extremo".
- Compromisos que llegan desde el S1: DA-01 (evidencia de RNF-06), DA-03 (RNF-07 acumulativo), DA-05 (CA-25.2) y DA-10 (la bitácora se usa desde S2, CA-19.3).

> Nada de este documento está implementado ni aprobado.

---

## 1. Alcance

### 1.1 Requerimientos funcionales

| ID | Texto del informe | Criterio de verificación | HU | S2 |
|---|---|---|---|---|
| RF-04 | "El sistema debe permitir cargar documentos como fotografía, indicando tipo, fecha de emisión y, opcionalmente, fecha de vencimiento" | "Un documento sin vencimiento se guarda y no genera alertas de expiración" | HU-11 | Completo |
| RF-08 | "El sistema debe mostrar al maestro el estado y la vigencia de cada documento que entregó" | "Cada documento muestra estado y, si corresponde, días restantes" | HU-17 | Completo |
| RF-32 | "El sistema debe permitir al administrador de curatoría cambiar el estado de un expediente exigiendo un motivo escrito" | "No se guarda un cambio de estado sin motivo" | HU-19 | Completo |
| RF-33 | "El sistema debe impedir aprobar un oficio regulado si no hay licencia SEC cargada y vigente" | "El intento de aprobación se rechaza con mensaje explícito" | HU-19, HU-24 | Completo, con el catálogo mínimo de oficios (D-1) |
| RF-34 | "El sistema debe desactivar automáticamente los servicios de oficios regulados cuando la licencia asociada deja de estar vigente" | "El maestro deja de aparecer en ese oficio y sigue apareciendo en los no regulados" | HU-24 | Solo la regla de vigencia y la tarea programada. Los servicios existen desde S3 y la búsqueda desde S4: **requiere un registro en la bitácora de alcance** |
| RF-35 | "El sistema debe avisar al maestro y al administrador 30 días antes del vencimiento de un documento" | "El aviso se emite una vez alcanzado el umbral" | HU-24 | Completo, con avisos dentro de la aplicación (D-7) |
| RF-37 | (S5) Bitácora de toda acción administrativa sobre expedientes | — | HU-19 | Se usa para expedientes y documentos (DA-10) |

### 1.2 Criterios de aceptación

| CA | S2 |
|---|---|
| CA-11.1 (pasos conservados al perder la conexión) | Sí |
| CA-11.2 (vencimiento opcional) | Sí |
| CA-11.3 (RUT repetido) | Ya en S1, con regresión |
| CA-17.1 (estado y días restantes) | Sí |
| CA-17.2 (motivo de la observación) | Sí |
| CA-19.1 (motivo escrito obligatorio) | Sí |
| CA-19.2 (sin licencia SEC no se aprueba) | Sí |
| CA-19.3 (bitácora con autor, fecha, anterior, nuevo y motivo) | Sí, con lectura del historial por expediente (D-9) |
| CA-19.4 (un maestro no cambia su propio expediente) | Sí, también con rol `curatoria` (ADR-013, punto 2.5) |
| CA-24.1 (servicios regulados inactivos) | No: S3 |
| CA-24.2 (aviso 30 días antes, revisión diaria) | Sí |
| CA-24.3 (sin vencimiento no desactiva) | Parcial: sin aviso en S2; servicios en S3 |
| CA-24.4 (búsqueda sin el servicio) | No: S4 |
| CA-25.2 (un cliente no abre el documento de identidad de un maestro) | Sí: cierra la parte S2 de DA-05 |
| CA-25.3 | Ya en S1; sigue "Terminado sin validar" (DA-04) |

Reglas del informe que se tratan como invariantes: "Ningún maestro se auto aprueba. Los registros de la bitácora no se editan ni se eliminan" (HU-19); "La distinción entre documentos con y sin vencimiento es obligatoria" (HU-24); "curatoría puede revisar documentos por su función… cualquier otro acceso se deniega y queda registrado" (HU-25).

### 1.3 Requerimientos no funcionales

| RNF | Umbral | S2 |
|---|---|---|
| RNF-06 | "Guardados fuera de las carpetas accesibles desde internet y entregados con un enlace que caduca a los 10 minutos" | Cierre completo (DA-01) |
| RNF-07 | "cada pantalla o función que recibe un número de registro tiene una prueba automática que confirma que un tercero no puede abrirla" | Todas las rutas nuevas (DA-03) |
| RNF-11 | "El sistema no ofrece ninguna forma de editar ni borrar una entrada de la bitácora" | Se mantiene; la lectura nueva es solo GET |
| RNF-13 | "Al menos 2 de 3 participantes de prueba la completan en ≤ 10 minutos" | Prueba con participantes |
| RNF-14 | "Botones de al menos 44 por 44 puntos y formularios divididos en pasos de máximo 5 campos" | Todas las pantallas nuevas |
| RNF-15 | "Ningún mensaje muestra códigos internos ni texto de programador, y se revisa en todos los formularios" | Todos los formularios, incluidos los 413 del proxy |
| RNF-16 | Contraste WCAG 2.2 y ningún estado indicado solo con color | Estados de expediente y documentos; hallazgo O-5 |
| RNF-17 | "Revisión de terminología sobre todas las vistas del maestro; sin siglas técnicas ni jerga de desarrollo" | Revisión con lista de términos (condicionado en §2.9.3) |
| RNF-20 | "Los pasos completados se conservan al reingresar" | Se entrega, porque CA-11.1 lo exige |
| RNF-25 | "Ningún servicio de gas o electricidad queda visible sin licencia vigente asociada" | Solo la regla y RF-33; **la evidencia pasa a S3 y S4 (registro de alcance)** |

---

## 2. Supuestos y decisiones abiertas

- **V-01** no bloquea: el modelo admite documentos con y sin vencimiento.
- **V-04** bloquea la eliminación de documentos, no el S2. En S2 se conservan todos los archivos (R-09 crece hasta RNF-26 en S5). V-04 no cubre al postulante rechazado. **[VALIDA REPRESENTANTE]**
- V-02, V-03 y V-05 no afectan al S2.

| ID | Decisión | Recomendación | Quién |
|---|---|---|---|
| D-1 | Oficios regulados antes del catálogo de S3 | App `catalogo` con tabla `oficio(codigo, nombre, regulado)` cargada desde CSV por migración, de solo lectura (patrón ADR-012). Es un adelanto de datos, no de RF-36. Alternativas: diferir RF-33 a S3 (no recomendado) o una casilla genérica | DECIDE EQUIPO; los ocho nombres y si "gasfitería" es regulada: VALIDA REPRESENTANTE |
| D-2 | Estados | Expediente: `en_revision` (inicial), `observado`, `aprobado`, `rechazado` (terminal) y `suspendido`. Documento: `en_revision`, `observado`, `validado` y `reemplazado`; la vigencia se calcula. Para aprobar: cédula por ambos lados, certificado de antecedentes y licencia SEC por oficio regulado declarado, todos validados y las licencias vigentes | DECIDE EQUIPO; obligatorios, reactivación y rechazo terminal: VALIDA REPRESENTANTE |
| D-3 | Almacenamiento (RNF-06, M-02) | Volumen `documentos` montado solo en `app` (y `planificador`), nombres UUID4 sin el nombre original, permisos 0600, entrega por una vista de Django. Alternativas: `X-Accel-Redirect` o `bytea` | DECIDE EQUIPO (ADR nuevo) |
| D-4 | Cifrado en reposo (M-02, §2.8) | AES-256-GCM por archivo con `cryptography`, datos asociados ref más cara, clave en `/secretos/documentos_clave` generada por `init`. Alternativa: sin cifrado de aplicación, con la desviación documentada | DECIDE EQUIPO (ADR nuevo) |
| D-5 | Formatos, tamaño y validación | JPEG y PNG por contenido; Pillow con límite de píxeles y recodificación a JPEG sin metadatos (quita el GPS); compresión en el cliente; hasta 8 MB por archivo; 413 en JSON; se rechaza un documento ya vencido. ClamAV descartado por RNF-04 | DECIDE EQUIPO (ADR nuevo); PDF: VALIDA REPRESENTANTE |
| D-6 | Zona horaria de negocio | "Hoy" en `America/Santiago`; vigente si no tiene vencimiento o si `hoy < vencimiento` | DECIDE EQUIPO |
| D-7 | Planificador y avisos (RF-35) | Servicio `planificador` con la misma imagen y un comando que cada hora corre tareas idempotentes (avisos, purga de `acceso_denegado` que cierra DA-06, huérfanos). Avisos dentro de la aplicación (tabla `aviso`); no hay correo ni SMS | DECIDE EQUIPO (ADR nuevo) |
| D-8 | Conflicto de interés (CA-19.4) | 403 con mensaje accionable, registrado en `acceso_denegado`; también se deniega la lectura del propio expediente desde curatoría | DECIDE EQUIPO (enmienda de ADR-011) |
| D-9 | Lectura de la bitácora (CA-19.3) | Un único GET del historial de un expediente, solo curatoría; se reescribe explícitamente la prueba de "ninguna ruta expone la bitácora"; el maestro no lee la bitácora | DECIDE EQUIPO (enmienda de ADR-010) |
| D-10 | Revisión por documento | Curatoría valida u observa cada documento, con motivo al observar; habilitación de oficio regulado = licencia validada y vigente | DECIDE EQUIPO |
| D-11 | Reemplazo y reintentos | Un documento actual por (expediente, tipo, oficio); subir otro reemplaza; si nadie lo revisó se borra, si no queda `reemplazado` | DECIDE EQUIPO |
| D-12 | Curatoría para la demo | Sin código nuevo: `crear_usuario_administrativo`; documentar el procedimiento con datos ficticios | DECIDE EQUIPO |
| D-13 | Ingreso tras postular | Mantener ADR-013 E-8 (la postulación no inicia sesión) y redirigir a ingresar sin el RUT en la URL | DECIDE EQUIPO |

---

## 3. Modelo de datos

- **`catalogo.oficio`**: `id`, `codigo` UNIQUE, `nombre`, `regulado`, `orden`. CSV versionado; sin escritura en S2.
- **`expediente`**: `ref` UUID4, OneToOne con `perfil_maestro` (PROTECT), `estado` (CHECK), `estado_motivo`, `estado_cambiado_en`, `estado_cambiado_por_id`, `creado_en`; CHECK de motivo no vacío cuando hay autor. Se crea en la misma transacción que `perfil_maestro`; una migración de datos crea los de los maestros existentes.
- **`oficio_maestro`**: (maestro, oficio) UNIQUE; editable solo en `en_revision` u `observado`.
- **`documento`**: `ref` UUID4, `expediente_id`, `tipo` (cédula, antecedentes, licencia SEC), `oficio_id` (solo licencia), `fecha_emision`, `fecha_vencimiento` NULL (CHECK posterior a la emisión), `estado`, `motivo_observacion` (obligatorio si está observado), `archivo` y `archivo_reverso` (solo la cédula), `cargado_en`, `revisado_en`, `revisado_por_id`, `reemplaza_a_id`; índice único parcial de documento actual.
- **`aviso`**: destinatario (usuario o rol `curatoria`), `tipo`, `documento_id`, `creado_en`; UNIQUE para emitir una sola vez; sin datos personales.
- **Reglas calculadas únicas** en `expediente/vigencia.py`: `hoy_negocio`, `vigente`, `dias_restantes`, `oficio_habilitado`, `faltantes_para_aprobar` (S3 y S4 las reutilizan).

Transiciones del expediente (todas por curatoría distinta del dueño, con motivo, `select_for_update`, estado esperado y bitácora en la misma transacción):

| De | A | Condición |
|---|---|---|
| `en_revision`, `observado` | `aprobado` | Sin faltantes; RF-33 con mensaje que nombra el oficio |
| `en_revision` | `observado` | — |
| `observado` | `en_revision` | — |
| `en_revision`, `observado` | `rechazado` | Terminal (D-2) |
| `aprobado` | `suspendido` | — |
| `suspendido` | `aprobado` | Se vuelve a verificar RF-33 |

Cualquier otra transición responde 409. El maestro nunca cambia el estado del expediente; el actor Sistema tampoco en S2.

Quién ve qué: el dueño y curatoría (distinta del dueño) ven estado, motivos, metadatos y el archivo (enlace de 600 s). El historial y quién revisó solo los ve curatoría. Clientes y demás roles: 404 con registro (CA-25.2).

---

## 4. Interfaz del servidor

| Método y ruta | Autorización | Notas |
|---|---|---|
| GET `/api/oficios` | Pública | Catálogo sin datos personales |
| GET `/api/maestros/expediente` | Dueño (patrón "me") | Estado, oficios, documentos con vigencia, faltantes y avisos; `no-store` |
| POST `/api/maestros/expediente/oficios` | Dueño | Solo en `en_revision` u `observado` |
| POST `/api/maestros/expediente/documentos` (multipart) | Dueño | Validación de contenido, cifrado y reemplazo; 413 en JSON |
| GET `/api/documentos/<uuid:ref>/enlace` | `obtener_autorizado` + `PoliticaDocumento` (dueño o curatoría) | Resto: 404 idéntico con registro (CA-25.2) |
| GET `/api/documentos/<uuid:ref>/archivo?t=…` | Token de 600 s + la política otra vez | Cabeceras `no-store`, `nosniff`, CSP `sandbox` |
| GET `/api/curatoria/expedientes` | `@requiere_rol("curatoria")` | Excluye el expediente propio; sin RUT |
| GET `/api/curatoria/expedientes/<uuid:ref>` | Rol + conflicto de interés (D-8) | Detalle |
| POST `/api/curatoria/expedientes/<uuid:ref>/estado` | Ídem | RF-32, CA-19.1, CA-19.2, CA-19.3, CA-19.4 |
| GET `/api/curatoria/expedientes/<uuid:ref>/historial` | Ídem | CA-19.3, solo lectura |
| POST `/api/curatoria/documentos/<uuid:ref>/revision` | Rol + no es dueño | Validar u observar (CA-17.2) |
| GET `/api/curatoria/avisos` | Rol | RF-35 |

- Conflicto de interés: `Politica.conflicto(usuario, objeto)`, evaluado por `obtener_autorizado`, y `ConflictoDeInteres` traducido a 403 con registro.
- Cada ruta con `<uuid:ref>` tiene prueba `@pytest.mark.terceros`: cliente, otro maestro, comercial, moderación y control de gestión; en el archivo, además, token de otro usuario, de otra `ref` y vencido; en curatoría, el dueño con rol (403 sin efectos).
- Proxy: límites de subida solo en la ruta de subida, 413 en JSON, páginas de error en español (DEF-QA-006) y `log_format` sin la cadena de consulta (el token `t` no queda en los registros).

---

## 5. Frontend

- **Maestro** (mobile-first): oficios con casillas grandes y "necesita licencia SEC" en texto; un paso por documento (5 campos o menos); captura con "Tomar foto" y "Elegir de la galería", compresión en el cliente, vista previa, progreso y reintento sin perder la foto; resumen con estados en lenguaje del oficio. Cada paso se guarda en el servidor (RNF-20, CA-11.1).
- **Curatoría** (notebook): cola con filtros, detalle con visor mediante enlace de 600 s, validar u observar por documento, acciones de expediente con motivo obligatorio, mensaje de RF-33 e historial.
- **Backlog UX al inicio del S2**: DEF-QA-006, O-5 (contraste del foco, WCAG 1.4.11), M-2, M-4 y O-1. Durante las revisiones de RNF-15 a RNF-17: M-3, M-5, M-6, M-7 y O-2.

---

## 6. Pruebas y criterios de terminado

Pruebas automatizadas (solo datos e imágenes sintéticas): vigencia y zona horaria; RF-04 y CA-11.2; contenido del archivo (HTML disfrazado, EXIF con GPS eliminado, bomba de descompresión, tamaño, archivo cifrado, intercambio entre registros); RNF-06 (600 y 601 s, política reaplicada); transiciones, motivo, RF-33, bitácora, conflicto de interés, 409 por estado desactualizado y concurrencia; RF-35 una sola vez; reemplazo sin duplicar; CA-25.2 y terceros por ruta; RNF-11; RNF-15; privacidad de las respuestas.

| RNF | Evidencia |
|---|---|
| RNF-06 | Volumen solo en `app`; rutas adivinables 404; 600/601 s; enlace caducado en vivo; archivo cifrado. Cierra DA-01 |
| RNF-07 | Prueba de control en verde con las rutas nuevas |
| RNF-13 | Protocolo con 3 participantes externos en teléfono real con documentos falsos rotulados "MUESTRA": al menos 2 de 3 en 10 minutos o menos |
| RNF-14 | Playwright a 320 y 390 px |
| RNF-15 | Revisión de formularios y prueba automática; 413 y 404 del proxy en español |
| RNF-16 | Tabla de contrastes, revisión con axe y estados con texto o icono |
| RNF-17 | Lista de términos revisada en todas las vistas del maestro |
| RNF-20 | Recorrido con red cortada a mitad del asistente |
| RNF-25 | En S2 solo la regla y RF-33; evidencia en S3 y S4 |
| RNF-04, RNF-23 | Sin degradación: `docker stats` con 10 subidas simultáneas y nueva medición en motor limpio |

---

## 7. Orden de implementación

0. Inicio: revisión de avisos de dependencias (RNF-27); aprobar los ADR de D-3 a D-5 y D-7 y las enmiendas de ADR-010 y ADR-011; resolver DEF-QA-006, O-5, M-2, M-4 y O-1; enviar al representante las preguntas de D-1, D-2, D-5 y V-04 en un solo paquete (CP-01).
1. Catálogo de oficios y expediente.
2. Subida segura (volumen, cifrado, Pillow, límites, asistente con foto).
3. Enlace y descarga (RNF-06, CA-25.2, terceros).
4. Curatoría (cola, detalle, revisión, estados, RF-33, historial): incremento del informe.
5. Vigencia y avisos (RF-08, planificador, RF-35).
6. Cierre de UX (RNF-14 a RNF-17, RNF-20 y la prueba de RNF-13).
7. QA y registros en la bitácora de alcance.

---

## 8. Riesgos y registros de alcance

- **Riesgos:** R-01 (un defecto en `PoliticaDocumento` expone cédulas); R-09 (archivos conservados hasta S5); pérdida de la clave de cifrado; certificado autofirmado en Android para RNF-13; memoria (RNF-04); RNF-13 fuera de umbral por el ingreso intermedio (D-13); nombres de oficios sin confirmar.
- **Registros para la bitácora de alcance** (§5.3.6): RF-34, CA-24.1 y la parte de servicios de CA-24.3 a S3; CA-24.4 a S4; evidencia de RNF-25 a S3 y S4; adelanto del catálogo mínimo de oficios (S3 → S2) y del planificador (S4 → S2, cierra DA-06); cierre de DA-01 y de la parte S2 de DA-05; eventual desplazamiento de la evidencia de RNF-13; desviación de M-02 si se elige D-4 B.
