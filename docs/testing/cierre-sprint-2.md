# Verificación de cierre — Sprint 2 (expediente del maestro y curatoría)

- Fecha: **2026-09-29** (hora de Chile; la verificación corrió entre las 23:59 del 28 y las 04:35 del 29, hora de Chile, es decir, 02:59 a 07:35 UTC del 29).
- Preparado por: agente `qa`.
- Código verificado: rama `main`, commit `fd6449b` (cierre de UX del S2). Durante la verificación apareció el commit `709e7ba`, que solo agrega documentos del Sprint 3 (propuesta y ADR-018 a ADR-021); **el código es el mismo**. La medición de RNF-23 se hizo sobre `709e7ba`. Se agregó la prueba `backend/tests/test_qa_cierre_s2.py` (sin commit).
- Fuentes: `docs/informe-altiro.md` (§3.2, §3.3, §4.2.1, §4.2.2, §4.3.3, §4.3.4, §5.3.5); `docs/decisions/sprint-2-propuesta-arquitectura.md` (Borrador con D-1 a D-13 aprobadas; §9 y §10 provisionales); ADR-015, ADR-016 y ADR-017 (E-1 a E-3), ADR-010 E-1, ADR-011 E-1 y E-2, ADR-002 E-1 (todas Aceptadas); `docs/alcance/bitacora-de-alcance.md` (DA-01 a DA-17); `docs/alcance/preguntas-representante-s2.md`; `docs/testing/` (rnf-13-protocolo, rnf-16-contrastes, rnf-17-terminologia, revision-dependencias-s2, rnf-23-medicion).

**Veredicto: listo con observaciones.** El incremento del informe, "verificación documental funcionando de extremo a extremo", funciona en el sistema levantado: postular, documentos, observación con motivo visible al maestro, reemplazo, validación, RF-33 con 409 explícito, aprobación, historial de la bitácora, conflicto de interés 403 y avisos de RF-35 con el planificador. RF-04, RF-08, RF-32, RF-33, RF-35, los CA del S2, RNF-06, CA-25.2, RNF-07 (rutas del S2), RNF-11, RNF-14, RNF-15, RNF-16, RNF-17 y RNF-20 cumplen con evidencia; RNF-04, RNF-23 y RNF-27 se volvieron a medir y cumplen. RNF-13 queda BLOCKED (DA-17), y RF-34, CA-24.1, CA-24.3 (servicios), CA-24.4 y RNF-25 quedan como infraestructura preparada o fuera de alcance según DA-12 a DA-14.

Se encontraron **tres defectos nuevos**: uno **alto** (DEF-QA-008: correr la suite de pruebas contra la pila borra los archivos cifrados reales del volumen `documentos`), uno **medio** (DEF-QA-009: el token del enlace de 600 s queda en el registro de errores de Nginx, y la foto descifrada se escribe temporalmente en el disco del proxy) y uno **bajo** (DEF-QA-010: una prueba falla si la suite cruza la medianoche de Chile). **Condición antes de la revisión del sprint:** corregir DEF-QA-008, o no volver a correr `docker compose exec -T app pytest` sobre la pila de la demostración, y corregir DEF-QA-009.

---

## 1. Alcance verificado

| Tipo | Identificadores |
|---|---|
| RF | RF-04, RF-08, RF-32, RF-33, RF-34, RF-35 |
| HU | HU-11, HU-17, HU-19, HU-24, HU-25 (CA-25.2) |
| CA | CA-11.1, CA-11.2, CA-11.3 (regresión), CA-17.1, CA-17.2, CA-19.1 a CA-19.4, CA-24.1 a CA-24.4, CA-25.2 |
| RNF del S2 | RNF-13 a RNF-17, RNF-20, RNF-25 |
| Compromisos que llegan del S1 | RNF-06 (DA-01), RNF-07 (DA-03), CA-25.2 (DA-05), bitácora desde S2 (DA-10), purga de `acceso_denegado` (DA-06) |
| Re-mediciones pedidas | RNF-04, RNF-11, RNF-23, RNF-27 |
| Transversal | Seguridad y privacidad (registros, CSP, cabeceras, 403/404, CSRF, limitador) y regresión del S1 |

## 2. Ambiente de prueba

| Dato | Valor |
|---|---|
| Equipo | Equipo de desarrollo, Windows 11 Pro 10.0.26200, 16 CPU lógicas, 15,56 GiB asignados a Docker |
| Docker | Docker Desktop, motor 29.8.0, Compose 5.5.1 |
| Servicios | `init`, `db` (postgres:16.15-bookworm), `app` (altiro-app:local, Django 5.2.17, gunicorn 26.2.0, 2 workers), `planificador` (misma imagen), `proxy` (nginx:1.30.5-alpine) |
| Levantado con | `docker compose up -d --build` al inicio (02:59 UTC): se recrearon `app` y `planificador`; todos los servicios healthy |
| Navegador | Chromium de `mcr.microsoft.com/playwright/python:v1.55.0-noble` en la red `altiro_frontal`, 320×640, 390×844 y 1280×800 |
| Cliente HTTP de QA | Python 3.13 (solo biblioteca estándar) en un contenedor efímero que comparte la red del proxy (`https://localhost` → Nginx) |
| Datos | Solo ficticios: `qa.*.144011844@example.com`, RUT sintéticos (`22040414-5`, `23200936-5`, `24222128-1`), teléfonos `+56 9 1000 xxxx`, imágenes sintéticas rotuladas "MUESTRA" |

### Acciones con efecto en el ambiente
- Se crearon en la base principal cuentas ficticias: un cliente, tres maestros (uno con el rol `curatoria` agregado), y cuentas de curatoría, comercial, moderación y control de gestión, con el procedimiento de `cur_prep.sh` (contraseña aleatoria por entrada estándar desde un archivo temporal que se borra). Los scripts de interfaz crearon además sus propias cuentas ficticias.
- Se cargaron documentos ficticios, se cambiaron estados y se escribieron entradas de bitácora, avisos y filas de `acceso_denegado`.
- **Pérdida de datos ficticios por DEF-QA-008:** la primera corrida de `docker compose exec -T app pytest -q` (03:00 UTC) borró del volumen los archivos de los documentos ficticios cargados antes por el equipo (65 documentos en la base; 86 archivos faltantes). Sus descargas responden 500. No había datos reales. Las corridas siguientes de la suite se hicieron en un contenedor aislado (`docker compose run --rm --no-deps` con `ALTIRO_DOCUMENTOS_DIR=/tmp/docs`) para no repetir el borrado.
- El limitador quedó bloqueando 15 minutos el identificador ficticio `qa.limitador.inexistente@example.com`.
- RNF-23 se midió en un contenedor `docker:29-dind` propio, que se eliminó junto con su volumen anónimo (sección 4.4). No se borraron imágenes, volúmenes ni bases del equipo.
- En el scratchpad se ajustó `aviso_fechas.json` a la fecha del 29 (copia de la anterior en `aviso_fechas.bak`) para volver a correr `aviso_prep.py`.

## 3. Pruebas ejecutadas

### 3.1 Automatizadas (pytest, pytest-django y time-machine; ADR-014)

| Ejecución | Resultado |
|---|---|
| `docker compose exec -T app pytest -q` (código de la imagen, 03:00 UTC) | **1052 passed, 1 failed** en 186 s. La falla es `test_documentos.py::test_campo_invalido_responde_400_en_el_campo_sin_guardar[cambios5-fecha_emision]` (DEF-QA-010); la misma parametrización, repetida, da **14 passed** |
| Suite completa en contenedor aislado (`ALTIRO_DOCUMENTOS_DIR=/tmp/docs`, `backend/tests` montado), incluida `test_qa_cierre_s2.py` | **1053 passed, 1 xfailed** en 182 s. El xfail es DEF-QA-008 |
| `test_control_terceros.py`, `test_bitacora.py`, `test_rnf15_mensajes_maestro.py`, `test_vigencia.py` | 98 passed |
| `manage.py makemigrations --check --dry-run` | Sin cambios pendientes |
| `manage.py check --deploy` | Los mismos 3 avisos justificados del S1 (W002, W004, W008) |

**Prueba nueva** (`backend/tests/test_qa_cierre_s2.py`): `test_las_pruebas_nunca_usan_el_directorio_real_de_documentos`, xfail estricto que documenta DEF-QA-008. Pasará cuando la suite nunca apunte al directorio configurado por el entorno.

### 3.2 Sobre el sistema levantado

| Verificación | Método | Resultado |
|---|---|---|
| Recorrido extremo a extremo por la API | `qa2/e2e.py` (fases 1 a 3): 115 comprobaciones | **0 fallos** |
| Maestro en el navegador | `s2_maestro.py` (oficios, cédula, antecedentes, licencia, corte de red, resumen, mis documentos, visor, 320 y 390 px) | 55 OK, **0 fallos** |
| Curatoría en el navegador | `cur_prep.sh` y `cur_ui.py` (cola, detalle, visor, observar, RF-33, 409, aprobar, historial, E-3, rechazo, CA-19.4) | 76 OK, **0 fallos** |
| Avisos en el navegador | `aviso_prep.py`, planificador `--una-vez` y `aviso_ui.py` | 71 OK, **0 fallos** |
| Accesibilidad | `axe_s2.py` con axe-core 4.10.3 (WCAG 2.0, 2.1 y 2.2, A y AA) sobre 16 vistas | **0 violaciones** |
| Regresión del S1 | `flujo_s2.py`, `defectos_s2.py` y `csrf_m1.py` | Sin fallos |
| Planificador | `manage.py planificador --una-vez` dos veces | `avisos_creados=2` y luego `0` |
| Volumen, permisos y cifrado | `docker inspect` de montajes; `ls -ln`, `stat` y lectura de bytes dentro de `app` | Sección 4.2 |
| Registros | `docker compose logs app proxy planificador db` (15.767 líneas) y búsqueda de patrones | Sección 4.5 |
| RNF-04 | `docker stats` (25 muestras) durante 30 subidas de 1,4 MB en tres rondas de 10 simultáneas; `memory.peak` de `app` | Sección 4.4 |
| RNF-23 | Motor `docker:29-dind` limpio, `git archive HEAD`, un solo comando | 43 s |
| RNF-27 | `pip-audit` 2.10.1 en un contenedor efímero, fuentes PyPI y OSV | Sin avisos |

Los scripts y sus salidas están en el scratchpad de la sesión, carpeta `qa2/` (`salida_fase2.txt`, `salida_fase3.txt`, `ui_*.txt`).

---

## 4. Resultados por requisito

Clasificación: PASS, FAIL, BLOCKED o NOT IN SCOPE. Para lo que el diseño cierra en un sprint posterior se usa «infraestructura preparada / evidencia final pendiente».

### 4.1 Requerimientos funcionales y criterios de aceptación

| Req. | Criterio del informe | Método y evidencia | Resultado |
|---|---|---|---|
| RF-04 (HU-11) | "Un documento sin vencimiento se guarda y no genera alertas de expiración" | En vivo: cédula sin vencimiento, 201, con `dias_restantes: null`. Tras dos corridas del planificador, el maestro solo tiene el aviso de la licencia; ningún aviso por la cédula ni por los antecedentes. HTML disfrazado de JPEG: 400 "Envía una foto. Este archivo no es una foto que podamos leer.". pytest: `test_documentos.py` (formatos, EXIF con GPS eliminado, bomba de descompresión, tamaño, cifrado) y `test_avisos_planificador.py` | **PASS** |
| CA-11.2 | "La fecha de vencimiento queda como campo opcional" | En vivo: antecedentes con `fecha_vencimiento` vacía, 201. En el navegador, la ayuda dice "Si tu documento no tiene fecha de término, déjala en blanco." | **PASS** |
| CA-11.1 | "Al volver a entrar los pasos ya guardados se conservan" | Ver RNF-20 (sección 4.3): corte de red a mitad del paso de cédula, reintento sin perder la foto ni la fecha; al volver, "Tus pasos anteriores están guardados. Sigue desde aquí." y la reanudación en el primer faltante | **PASS** |
| CA-11.3 | RUT repetido | Regresión en pytest (PI-020 a PI-046) | **PASS** |
| RF-08 (HU-17) | "Cada documento muestra estado y, si corresponde, días restantes" | En vivo: licencia con `dias_restantes: 20`, cédula con `null`, estado por documento. En el navegador: "Vence el 1 de mayo de 2031. Quedan 1675 días.", "No vence" y el estado con ícono y texto | **PASS** |
| CA-17.1 | "Veo su estado y, si tiene vencimiento, los días que le quedan" | Ídem | **PASS** |
| CA-17.2 | "Veo el motivo escrito de la observación" | En vivo: el maestro recibe `motivo_observacion` con el texto exacto que escribió curatoría y no ve quién revisó. En el navegador: "Qué debes corregir: La foto del certificado está borrosa…" | **PASS** |
| RF-32 (HU-19) | "No se guarda un cambio de estado sin motivo" | En vivo: motivo de solo espacios, 400 `{"motivo": "Escribe el motivo. Es obligatorio y queda registrado."}` sin cambio. Observar un documento sin motivo, 400. Con motivo, 200. En la base: CHECK de motivo en `expediente` y `bitacora` (pytest) | **PASS** |
| CA-19.1 | Motivo escrito antes de guardar | Ídem, también en la interfaz (error junto al campo) | **PASS** |
| RF-33 (HU-19, HU-24) | "El intento de aprobación se rechaza con mensaje explícito" | En vivo: con cédula y antecedentes validados y la licencia de gas sin validar, 409 "No se puede aprobar el expediente: falta la licencia SEC de Gas, validada y vigente." Tras validar la licencia, el oficio pasa a habilitado y la aprobación da 200. pytest: licencia vencida, día del vencimiento (vale 0 y no está vigente), E-1, `suspendido` → `aprobado` | **PASS** |
| CA-19.2 | Oficio regulado sin licencia SEC: no se aprueba | Ídem | **PASS** |
| CA-19.3 | "Figura el autor, la fecha, el estado anterior, el nuevo y el motivo" | En vivo: `GET …/historial` con 6 entradas; la última es `{"autor": "QA curatoria 144011844", "estado_anterior": "observado", "estado_nuevo": "aprobado", "motivo": "Documentos completos (MUESTRA …)", "fecha": …}`; incluye el documento reemplazado. En la base, `bitacora` con `autor_tipo = usuario` en cada fila | **PASS** |
| CA-19.4 | Un maestro no cambia su propio expediente | En vivo: el maestro sin rol recibe 403 (falta rol) en `POST …/estado` de su expediente. La maestra con rol `curatoria` recibe 403 "No puedes revisar ni resolver tu propio expediente. Otra persona de curatoría debe hacerlo." en el detalle, el historial y el cambio de estado, sin `AlTiro-Rechazo`; su expediente no aparece en su cola (todas las páginas) y sigue `en_revision`. Queda una fila en `acceso_denegado` por cada intento | **PASS** |
| RF-35 (HU-24) | "El aviso se emite una vez alcanzado el umbral" | En vivo: licencia que vence en 20 días; primera corrida del planificador `avisos_creados=2` (maestro y rol curatoría), segunda `avisos_creados=0`. Texto al maestro: "Tu licencia de la Superintendencia de Electricidad y Combustibles (SEC) de Gas vence en 20 días, el 19 de octubre de 2026. Sube el documento nuevo antes de esa fecha." Curatoría lo ve en `/api/curatoria/avisos` y con `?por_vencer=1`. En la base: UNIQUE `aviso_una_vez` (NULLS NOT DISTINCT) y CHECK de un solo destinatario | **PASS** |
| CA-24.2 | "Revisión diaria… avisa al maestro y al administrador de curatoría" | Planificador cada 3600 s (más frecuente que diario), healthy; ídem | **PASS** |
| CA-24.3 | Sin vencimiento no se desactiva ningún servicio | La parte de avisos cumple (sin aviso). La parte de servicios no existe hasta S3 (DA-12); `oficio_habilitado` trata la licencia sin vencimiento como vigente (pytest `test_vigencia.py`) | **infraestructura preparada / evidencia final pendiente (S3)** |
| RF-34 | "El maestro deja de aparecer en ese oficio…" | DA-12: en S2 existen la regla `oficio_habilitado` y el planificador. Verificado: la regla funciona en vivo (el detalle pasa Gas de `habilitado: false` a `true`) y en pytest | **infraestructura preparada / evidencia final pendiente (S3)** |
| CA-24.1 | Servicios regulados inactivos al vencer | DA-12 | **infraestructura preparada / evidencia final pendiente (S3)** |
| CA-24.4 | Búsqueda sin el servicio | DA-13: la búsqueda llega en S4 | **NOT IN SCOPE** (S4) |
| CA-25.2 (HU-25) | Un cliente no abre el documento de identidad de un maestro | En vivo, cédula de otro maestro: cliente, otro maestro, comercial, moderación y control de gestión reciben 404 en el enlace, **idéntico byte a byte** al de una referencia inexistente, y 404 en el archivo con un token ajeno. En `acceso_denegado` quedan exactamente 10 filas con esa `ref` (5 en `enlace` y 5 en `archivo`), con método y patrón de la ruta | **PASS**. Cierra la parte S2 de DA-05 |
| CA-25.3 | Denegación registrada | Sigue "Terminado sin validar" (DA-04, P-08) | **BLOCKED** (validación del representante) |

### 4.2 RNF-06 (cierre de DA-01), RNF-07 y RNF-11

| RNF | Umbral exacto | Método y evidencia | Resultado |
|---|---|---|---|
| RNF-06 | "Guardados fuera de las carpetas accesibles desde internet y entregados con un enlace que caduca a los 10 minutos" | **Volumen:** `altiro_documentos` montado solo en `app` y `planificador` (`docker inspect`); el proxy solo monta plantillas, frontend y certificados. **Archivos:** directorio `drwx------ altiro`, archivos con nombre UUID, dueño 10001 y modo 600 (5 de 5); ninguno empieza con la cabecera JPEG ni contiene "MUESTRA" en claro. **Rutas adivinables:** `/documentos/`, `/documentos/<ref>`, `/media/`, `/api/documentos/`, `/api/documentos/<ref>`, `/static/../documentos` responden 404 y `/../documentos/` 400, sin imagen. **Enlace:** `caduca_en` a 600 s; el archivo sale con `Cache-Control: no-store, private`, `nosniff` y `Content-Security-Policy: sandbox; default-src 'none'`, sin EXIF. Token de otro usuario, de la otra cara, alterado o ausente: 404. 600 y 601 s en pytest. **Token en registros:** el registro de acceso de Nginx y el de la aplicación no lo guardan, pero **el registro de errores de Nginx sí** (DEF-QA-009) | **PASS** para el umbral del informe (fuera de carpetas públicas y enlace de 10 minutos). El compromiso adicional de la propuesta (§4: "el token `t` no queda en los registros") **no se cumple**: DEF-QA-009 |
| RNF-07 | "cada pantalla o función que recibe un número de registro tiene una prueba automática que confirma que un tercero no puede abrirla" | `test_toda_ruta_con_identificador_tiene_prueba_de_terceros_y_usa_uuid` en verde. Las 7 rutas nuevas con `<uuid:ref>` tienen marcas `terceros`: `documento_enlace` (5), `documento_archivo` (10), `curatoria_detalle` (3), `curatoria_cambiar_estado` (3), `curatoria_historial` (3), `curatoria_revisar_documento` (3), `curatoria_documento_enlace` (5). Comprobado además en vivo (sección 4.1 y 4.5) | **PASS** para las rutas del S2. El umbral global sigue acumulativo hasta S5 (DA-03) |
| RNF-11 | "El sistema no ofrece ninguna forma de editar ni borrar una entrada de la bitácora" | Barrera 1: la única ruta que lee la bitácora es el historial (ADR-010 E-1); en vivo `PUT`, `PATCH`, `DELETE` y `POST` sobre él responden 405, y el maestro recibe 403. pytest `test_la_unica_ruta_que_lee_la_bitacora_es_el_historial_y_solo_acepta_get` y `test_el_historial_no_acepta_metodos_de_escritura`. Barrera 2: los 4 triggers (`bitacora_sin_cambios`, `bitacora_sin_truncate`, `acceso_denegado_sin_cambios`, `acceso_denegado_sin_truncate`) habilitados (`tgenabled = O`) en la base principal | **PASS** |

### 4.3 RNF del S2 (usabilidad y fiabilidad)

| RNF | Umbral exacto | Método y evidencia | Resultado |
|---|---|---|---|
| RNF-13 | "Al menos 2 de 3 participantes de prueba la completan en ≤ 10 minutos" | Protocolo `rnf-13-protocolo.md` revisado: participantes y selección, consentimiento, materiales "MUESTRA", preparación del teléfono y del certificado, guion, T0 y T1, criterio de éxito, qué observar, hojas de registro y dónde se registra el resultado. Está completo y ejecutable. La sesión no se ha hecho (DA-17) | **BLOCKED** (DA-17: primera semana del S3) |
| RNF-14 | "Botones de al menos 44 por 44 puntos y formularios divididos en pasos de máximo 5 campos" | Playwright a 320 y 390 px (maestro) y a 390 y 1280 px (curatoría): ningún objetivo menor a 44 px en oficios, cédula, licencia, resumen, mis documentos, visor, cuenta, cola, detalle y confirmación de rechazo; paso de cédula con 4 campos (el más cargado); sin scroll horizontal | **PASS** |
| RNF-15 | "Ningún mensaje muestra códigos internos ni texto de programador, y se revisa en todos los formularios" | pytest `test_rnf15_mensajes_maestro.py` (recorre por AST todos los mensajes del backend y provoca por la API cada error del maestro). En vivo: los 400, 403, 404, 405, 409 y 413 revisados no contienen trazas, nombres de restricciones ni rutas; 413 del proxy en JSON y en español; 404 del proxy con página en español ("No encontramos esta página") | **PASS**. Observación OBS-02 |
| RNF-16 | Contraste WCAG 2.2 y "ningún estado indicado solo con color" | `rnf-16-contrastes.md` (todos los textos sobre 4,5:1; foco 3,15:1). axe-core 4.10.3 sobre 16 vistas: **0 violaciones**. "Por revisar a mano" solo `color-contrast` en el detalle de curatoría (texto sobre fondo que axe no calcula; cubierto por la tabla). Estados con ícono y texto: "⏳ En revisión", "⚠ Te pedimos corregir algo", "✓ Aprobado", "✕ No aprobado", "⏸ Suspendido" | **PASS**. Sigue pendiente la prueba con lector de pantalla real (limitación declarada en rnf-16) |
| RNF-17 | "Revisión de terminología sobre todas las vistas del maestro; sin siglas técnicas ni jerga de desarrollo" | Revisión del frontend en `rnf-17-terminologia.md`; los textos del servidor los cubre `test_rnf15_mensajes_maestro.py` con `TERMINOS_RNF17` (en verde). En vivo, "SEC" aparece siempre con "Superintendencia de Electricidad y Combustibles" | **PASS**. `rnf-17-terminologia.md` pide además la pregunta "¿Hubo palabras que no entendió?" del protocolo de RNF-13, que depende de DA-17. Observación OBS-02 |
| RNF-20 | "Los pasos completados se conservan al reingresar" | Chromium sin conexión a mitad del envío de la cédula: "No se pudo enviar. Revisa tu señal y toca «Reintentar». Tus fotos y fechas siguen aquí."; la foto y la fecha siguen; al reintentar, 201 y paso 3 de 4. Corte y recarga en antecedentes: "Paso 3 de 4 · Tus pasos anteriores están guardados"; al volver a entrar, el resumen con todo guardado | **PASS** |
| RNF-25 | "Ningún servicio de gas o electricidad queda visible sin licencia vigente asociada" | DA-14: en S2, RF-33 y `oficio_habilitado` funcionan (sección 4.1). No hay servicios ni búsqueda | **infraestructura preparada / evidencia final pendiente (S3 y S4)** |

### 4.4 RNF de recursos, instalación y dependencias

| RNF | Umbral exacto | Método, entorno y evidencia | Resultado |
|---|---|---|---|
| RNF-04 | "No más de 2 GB de memoria para todo el sistema" | `docker stats`, 25 muestras durante 30 subidas de una foto de 1,4 MB (3 rondas de 10 simultáneas, todas 201). Máximos: app 181,7 MiB, db 71,8 MiB, planificador 50,5 MiB, proxy 25,4 MiB (**≈ 329 MiB**). `memory.peak` de `app` desde su arranque, que incluye la suite de pytest: 319 MiB. Aun sumando ese pico, ≈ 467 MiB | **PASS** (la evidencia final con el volumen de prueba del informe es del S4) |
| RNF-23 | "Un solo comando deja el sistema andando en 10 minutos o menos, con las instrucciones escritas junto al código" | Motor `docker:29-dind` limpio (0 imágenes, 0 volúmenes), `git archive HEAD` del commit `709e7ba`, sin `.env`, `docker compose up -d --build` con código 0; `/api/health/` por HTTPS OK a los **43 s**; los cinco servicios sanos a los 50 s. Se borraron solo el contenedor `qa-rnf23-s2` (id verificado) y su volumen anónimo. Detalle en `rnf-23-medicion.md` | **PASS** (confirmar en el laboratorio, como en el S1) |
| RNF-27 | "Cada librería queda declarada con versión exacta y hay una revisión de avisos registrada al inicio de cada sprint" | `pip-audit` 2.10.1 (PyPI y OSV) sobre `requirements.txt` y `requirements-pruebas.txt`, con Pillow 12.3.0 y cryptography 50.0.1: sin avisos. Todas las versiones con `==`. Registrado en `revision-dependencias-s2.md` | **PASS** para el S2 (RNF-27 se cierra en S5 según §5.3.5) |

### 4.5 Seguridad y privacidad transversal, y regresión del S1

| Verificación | Evidencia | Resultado |
|---|---|---|
| Datos personales y secretos en registros | 15.767 líneas de `app`, `proxy`, `planificador` y `db`: 0 apariciones de los RUT, correos `@example.com`, nombres "Maestro QA", "MUESTRA", `sessionid`, `csrftoken`, `argon2`, `contrasena`, `Traceback` ni de las contraseñas generadas. El planificador solo registra conteos | **PASS**, salvo el token de DEF-QA-009 |
| Token del enlace en registros | Registro de acceso de Nginx (`altiro_sin_consulta`): sin cadena de consulta. Aplicación: `Not Found: /api/documentos/<ref>/archivo`, sin consulta. **Registro de errores de Nginx: 17 líneas `[warn] an upstream response is buffered to a temporary file` con `archivo?cara=…&t=<token>` completo**, reproducido en vivo a las 07:24 y 07:25 UTC | **FAIL** (DEF-QA-009) |
| CSP y cabeceras | `mis-documentos.html`, `curatoria.html`, `curatoria-expediente.html`, API y 404: `Content-Security-Policy` sin scripts inline y con `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: same-origin`, `Server: nginx` sin versión, sin HSTS (ADR-008) | **PASS** |
| 403 y 404 sin información | 404 de un documento ajeno idéntico al de uno inexistente; 403 de rol sin `AlTiro-Rechazo`; 403 de conflicto con mensaje accionable; ninguna respuesta con rutas del volumen ni nombres de archivo | **PASS** |
| Minimización | La cola no trae RUT; el detalle de curatoría trae nombre y RUT, sin teléfono ni correo (§9.6); el maestro no ve quién revisó; las respuestas del maestro no traen RUT ni ids internos | **PASS** |
| CSRF | `POST` sin token: 403 con `AlTiro-Rechazo: csrf` y mensaje sin texto técnico; `csrf_m1.py` sin fallos | **PASS** |
| Sin sesión | 401 en `/api/maestros/expediente`, `/api/documentos/<ref>/enlace` y `/api/curatoria/expedientes/<ref>` | **PASS** |
| Limitador (RNF-10) | En vivo: 5 fallos dan 401 y el sexto 429 con `Retry-After: 900` y "Hubo varios intentos fallidos. Por seguridad, espera 15 minutos e inténtalo de nuevo." | **PASS** |
| Regresión del S1 | `flujo_s2.py`: registro de cliente por pasos, progreso tras recargar, ingreso con error y correcto, cuenta, perfil de maestro, cierre de sesión y objetivos de 44 px; pytest completo en verde | **PASS** |

---

## 5. Recorrido extremo a extremo (incremento del informe)

Una sola secuencia sobre el sistema levantado, con la API y en el navegador (`e2e.py` y `cur_ui.py`):

1. **Postular:** 201, sin iniciar sesión (ADR-013 E-8). El maestro ingresa: expediente `en_revision`, `no-store`.
2. **Documentos:** declara Gas y Carpintería; carga la cédula (sin vencimiento), los antecedentes (vencimiento vacío) y la licencia de Gas (vence en 20 días): 201 cada una. La licencia de un oficio no declarado da 400 accionable.
3. **Curatoría observa:** sin motivo, 400; con motivo, el documento queda `observado` y el expediente pasa a `observado`. **El maestro ve el motivo** exacto (CA-17.2), sin saber quién revisó.
4. **El maestro reemplaza** los antecedentes: 201, un solo documento actual, el anterior queda `reemplazado`.
5. **Valida** la cédula y los antecedentes nuevos; revisar otra vez un documento validado da 409.
6. **RF-33:** aprobar sin la licencia validada da **409** con "falta la licencia SEC de Gas, validada y vigente". Una transición inválida y un `estado_actual` desactualizado también dan 409.
7. **Aprueba** tras validar la licencia: 200, `aprobado`.
8. **Historial:** 6 entradas con autor, fecha, anterior, nuevo y motivo, incluido el documento reemplazado, que curatoría puede abrir (E-3) y el dueño no.
9. **Conflicto de interés:** la maestra con rol `curatoria` recibe 403 en su propio expediente (lectura, historial y cambio) y no lo ve en su cola.
10. **Avisos de RF-35:** el planificador crea 2 avisos una sola vez; el maestro y curatoría los ven con el texto en lenguaje del oficio.

---

## 6. Defectos

Numeración continuada desde DEF-QA-007.

### DEF-QA-008 — La suite de pruebas borra los archivos reales del volumen de documentos
- **Afecta a:** RF-04, RF-08 y RNF-06 en el ambiente de la demostración (integridad de los documentos); NTI-01; decisión ADR-015, punto 1.
- **Severidad:** alta. Correr el comando de pruebas documentado (`docker compose exec -T app pytest -q`) deja todos los documentos cargados sin foto: la descarga responde 500 y no hay forma de recuperarlos (no hay respaldo hasta RNF-19, S5). Si pasa antes de la revisión del sprint, la demostración pierde sus expedientes.
- **Precondición:** pila levantada con documentos cargados en el volumen `documentos`.
- **Pasos:** 1) contar los archivos de `/documentos` en `app`; 2) `docker compose exec -T app pytest -q`; 3) contar de nuevo; 4) pedir el enlace y el archivo de un documento anterior.
- **Esperado:** las pruebas nunca tocan el volumen real (ADR-015: "Nunca borra un archivo referenciado por un documento").
- **Observado:** tras la suite, 65 documentos de la base principal tenían 86 archivos faltantes; en el volumen solo quedaban los 5 subidos después. La descarga de uno anterior (`d91acbad-…`) responde 500 "Tuvimos un problema…" y la aplicación registra "No se pudo leer el archivo de un documento".
- **Reproducción aislada** (sin tocar el volumen): en un contenedor `docker compose run --no-deps` con `ALTIRO_DOCUMENTOS_DIR=/tmp/docs`, con un archivo `11111111-2222-4333-8444-555555555555` y otro `notas.txt`, al correr solo `test_avisos_planificador.py::test_un_error_de_base_de_datos_en_una_tarea_se_registra_sin_datos` el primero desaparece y el segundo queda.
- **Causa probable:** esa prueba reemplaza solo la primera tarea del planificador y corre la real `limpiar_archivos_huerfanos` con `AHORA = 2026-10-14` sobre `settings.ALTIRO_DOCUMENTOS_DIR`, que en el contenedor es el volumen real, y con la base de pruebas, donde ningún documento referencia esos archivos. Así, todos son "huérfanos antiguos". No hay una fixture autouse que aísle el directorio en todas las pruebas.
- **Evidencia automatizada:** `backend/tests/test_qa_cierre_s2.py` (xfail estricto).
- **Área responsable:** `backend` (pruebas; `tests/test_avisos_planificador.py` y `conftest.py`). Mientras no se corrija, la suite debe correrse en un contenedor aislado (ver sección 3.1).

### DEF-QA-009 — El token del enlace de 600 s queda en el registro de errores de Nginx, y la foto descifrada pasa por el disco del proxy
- **Afecta a:** RNF-06 (compromiso de la propuesta del S2, §4: "`log_format` sin la cadena de consulta (el token `t` no queda en los registros)"; DA-01 afirma "el token no queda en los registros de Nginx"); ADR-015, punto 1 (volumen "nunca en `proxy`"); CLAUDE.md §8 (no escribir tokens en registros).
- **Severidad:** media. El token está ligado al usuario y caduca a los 600 s, así que reutilizarlo exige además la sesión de ese usuario. Pero incumple un compromiso explícito, y la foto descifrada de una cédula se escribe en claro, aunque sea temporalmente, en `/var/cache/nginx/proxy_temp` del contenedor `proxy`.
- **Precondición:** documento con foto de más de unos 64 KB (cualquier foto real de teléfono) y un navegador (HTTP/2).
- **Pasos:** abrir el visor de un documento en Chromium; `docker compose logs proxy | grep "buffered to a temporary"`.
- **Esperado:** ningún registro contiene `t=`; el contenido descifrado no se escribe en el disco del proxy.
- **Observado:** 17 líneas `[warn] … an upstream response is buffered to a temporary file /var/cache/nginx/proxy_temp/… request: "GET /api/documentos/<ref>/archivo?cara=anverso&t=eyJ…"` (la última del 29/09 a las 02:57 UTC); reproducido en vivo con Chromium a las 07:24:41 y 07:25:02 UTC (`*5738`, `*5754`), con la línea completa y el `upstream:` también con el token.
- **Causa probable:** el `error_log` de Nginx (nivel `notice`) escribe la línea de petición completa, y `log_format altiro_sin_consulta` solo aplica al registro de acceso. La ruta `/archivo` usa el buffering por defecto, que vuelca a disco las respuestas grandes.
- **Área responsable:** infraestructura (`infra/proxy/templates`), a cargo de `backend`. Si la corrección requiere cambiar ADR-015 u otra decisión, lo revisa `architect`.

### DEF-QA-010 — Una prueba falla si la suite cruza la medianoche de Chile
- **Afecta a:** confiabilidad de la evidencia automática de RF-04 (ADR-014).
- **Severidad:** baja.
- **Pasos:** correr la suite de modo que la recolección ocurra antes de las 00:00 de Santiago y la prueba después (aquí la suite empezó a las 23:59:5x del 28).
- **Esperado:** 400 para una fecha de emisión futura.
- **Observado:** `test_campo_invalido_responde_400_en_el_campo_sin_guardar[cambios5-fecha_emision]` recibe 201: `_dias(1)` se calcula al importar el módulo (en la parametrización) y ya no es futura cuando la prueba corre. Repetida, pasa (14 passed).
- **Área responsable:** `backend` (pruebas: calcular las fechas dentro de la prueba o fijar el reloj con time-machine).

### Observaciones (no son defectos)
- **OBS-01:** al comenzar, `planificador` corría con una imagen anterior (id sin etiqueta) mientras `app` usaba la nueva; `docker compose up -d --build` lo recreó. Conviene recordar en el README que un cambio de código exige ese comando y no solo reiniciar `app`.
- **OBS-02:** el 413 de Nginx para la subida dice "cada una puede pesar hasta 8 MB", y " MB" está en la lista de términos de RNF-17. La interfaz no lo muestra: usa su propio mensaje. También quedan textos del servidor con "Recarga la página", que la lista de RNF-17 del frontend trató como jerga. Revisarlo en la próxima pasada de terminología.
- **OBS-03:** en S2, curatoría puede aprobar un expediente sin ningún oficio declarado si tiene cédula y antecedentes validados. El informe no lo prohíbe; se agrega a P-03.
- **OBS-04:** el registro de la aplicación incluye la `ref` (UUID) del documento en los 404 y en el error de lectura. No es un dato personal, pero conviene tenerlo presente para RNF-22 (S5).

---

## 7. Desplazamientos de alcance

Confirmados en `docs/alcance/bitacora-de-alcance.md`, todos autorizados por el equipo de desarrollo y sin conformidad del representante todavía:

| ID | Estado verificado |
|---|---|
| DA-01 | Cerrado en S2. Se confirma el umbral de RNF-06, **pero su texto dice que el token no queda en los registros de Nginx, y eso no se cumple en el registro de errores (DEF-QA-009)**. Actualizarlo al corregir |
| DA-03 | Vigente: rutas del S2 con prueba de terceros |
| DA-05 | Parte S2 (CA-25.2) cerrada; CA-25.1 sigue para S4 |
| DA-06 | Cerrado (purga en el planificador; `accesos_denegados_purgados` en cada corrida) |
| DA-10 | Cumplido (bitácora en uso con historial) |
| DA-11 | Reconfirmado: 43 s con el planificador |
| DA-12 | RF-34, CA-24.1 y CA-24.3 (servicios) a S3: correcto |
| DA-13 | CA-24.4 a S4: correcto |
| DA-14 | Evidencia de RNF-25 a S3 y S4: correcto |
| DA-15 | Catálogo mínimo de 8 oficios, de solo lectura (`/api/oficios`); lista provisional por P-01 y P-02 |
| DA-16 | Planificador implementado y healthy; RNF-04 y RNF-23 vueltos a medir en este cierre |
| DA-17 | Ejecución de RNF-13 a la primera semana del S3; el protocolo está completo |

**Faltantes o por actualizar:**
- No hay registro para la **evidencia pendiente de RNF-17** que `rnf-17-terminologia.md` condiciona a la pregunta del protocolo de RNF-13. Queda cubierta de hecho por DA-17, pero conviene mencionarla ahí.
- La **prueba con lector de pantalla** de RNF-16 (limitación de `rnf-16-contrastes.md`) no tiene un registro ni una fecha.
- DA-01 debe corregirse cuando se resuelva DEF-QA-009 (ver arriba).

## 8. Riesgos

- **R-01** (documentos de otro maestro): mitigado en S2. `PoliticaDocumento`, el 404 idéntico con registro y el token ligado al usuario y a la cara quedaron verificados en vivo y en pruebas.
- **Pérdida de documentos:** DEF-QA-008, y la clave de cifrado sin respaldo hasta RNF-19 (S5). Un volumen perdido o una clave perdida no tienen recuperación.
- **R-09:** los documentos reemplazados y los de postulantes rechazados se conservan (P-07, V-04, RNF-26 en S5).
- **RNF-13:** sin ejecutar; es el requisito que más discute la viabilidad (§4.3.3 y §8 del informe). El ingreso intermedio tras postular (D-13) puede alargar el tiempo.
- **Registros:** DEF-QA-009 y OBS-04 hasta RNF-22 (S5).
- **Supuestos sin validar** que sostienen reglas del S2 (sección 9).

## 9. Supuestos provisionales pendientes de validar

**Preguntas al representante** (`preguntas-representante-s2.md`; fecha de envío: pendiente):
- P-01: los ocho oficios (lista provisional: Gas, Electricidad, Gasfitería, Carpintería, Pintura, Albañilería, Cerrajería, Jardinería).
- P-02: si "gasfitería" es regulada (supuesto: solo gas).
- P-03: documentos obligatorios para aprobar (más OBS-03).
- P-04: si un suspendido puede volver a aprobarse (supuesto: sí, con RF-33 otra vez).
- P-05: si el rechazo es terminal (supuesto: sí).
- P-06: si se acepta PDF (supuesto: no).
- P-07: retención de documentos de rechazados (supuesto: se conservan hasta RNF-26).
- P-08: CA-25.3 con `acceso_denegado` (DA-04).
- P-09: alcance nacional del catálogo territorial.
- P-10: HTML estático como "vista privada" (RF-02).
- P-11: opción de reautenticación de RNF-09 (supuesto: D).

**Aclaraciones de implementación** de la propuesta del S2, que se revisan en la revisión del sprint:
- §9 (incremento 4), sin contradicción con lo verificado:
  - ruta adicional de enlace de curatoría;
  - licencia reemplazada validada reconocida por no tener motivo;
  - revisión única de cada documento;
  - de suspendido a aprobado con la lista completa;
  - motivo de hasta 1000 caracteres;
  - minimización del detalle;
  - cola de 20, del más antiguo al más reciente.
- §10 (incremento 5), **provisionales**:
  - el día del vencimiento vale 0 y ya no está vigente;
  - la purga vive en `autorizacion`;
  - la licencia reemplazada que sigue contando genera aviso;
  - se avisa aunque el expediente esté rechazado;
  - el texto del aviso se arma en el servidor;
  - el aviso se muestra solo mientras el documento siga vigente y actual;
  - `?por_vencer` acepta solo `1`;
  - los huérfanos se borran con una hora de margen;
  - latido de 180 s para la salud del planificador.
  
  Todas se verificaron tal como están escritas. La regla de huérfanos es la que, combinada con la prueba, produce DEF-QA-008.
- V-01 a V-05 siguen como supuestos.

## 10. Recomendación para el Sprint 3

1. **Antes de la revisión del S2:** corregir DEF-QA-008 (aislar `ALTIRO_DOCUMENTOS_DIR` en toda la suite con una fixture autouse) y DEF-QA-009 (sin token en el `error_log` y sin volcar a disco la respuesta de `/archivo`); luego repetir `grep "t=eyJ"` sobre los registros del proxy. Corregir DEF-QA-010 en la misma tanda.
2. **Primera semana del S3:** ejecutar RNF-13 con el protocolo (DA-17) y registrar la respuesta a "¿hubo palabras que no entendió?" para cerrar la condición de RNF-17. Hacer la prueba con TalkBack de RNF-16.
3. Enviar el paquete de preguntas P-01 a P-11 (y las nuevas del S3) al representante; su fecha de envío sigue pendiente.
4. En el S3, cerrar DA-12 y DA-14 en parte: servicios que usen `oficio_habilitado` como regla única, la desactivación de RF-34 en el planificador y pruebas de terceros para cada ruta nueva con identificador (RNF-07).
5. Revisión de avisos de dependencias al inicio del S3 (RNF-27) y confirmación de RNF-23 en un equipo del laboratorio.
6. Mantener la suite fuera de la pila de la demostración (contenedor aislado) hasta que DEF-QA-008 quede corregido.
