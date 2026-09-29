# Verificación de cierre — Sprint 3 (catálogo, cobertura y agenda)

- Fecha: **2026-09-29**. La verificación corrió entre las 17:50 y las 18:25 UTC (14:50 a 15:25, hora de Chile).
- Preparado por: agente `qa`.
- Código verificado: rama `main`, commit `3c5d357`. Este commit incluye además la búsqueda del S4 (incrementos 1 y 2), que aquí solo se revisa como regresión: su verificación formal corresponde al cierre del S4. Se agregó la prueba `backend/tests/test_qa_cierre_s3.py` (sin commit).
- Fuentes:
  - `docs/informe-altiro.md`: §3.2, §3.3, §4.2.1, §4.2.2, §4.3.4 y §5.3.5 (S3: "Catálogo, cobertura y agenda, con RF-05 a RF-07, RF-36 y RNF-18"; incremento: "Perfil de maestro completo y publicable").
  - `docs/decisions/sprint-3-propuesta-arquitectura.md`: Borrador con D-1 a D-16 provisionales, más §8 y §9.
  - ADR-018 a ADR-021 (Aceptadas, provisionales; ADR-019 E-1 y ADR-020 E-1), ADR-022 punto 4 (provisional, afecta al perfil público), ADR-010, ADR-011, ADR-012, ADR-015 y ADR-017.
  - `docs/alcance/bitacora-de-alcance.md` (DA-12 a DA-21) y `docs/alcance/preguntas-representante-s2.md` (P-12 a P-18).
  - `docs/testing/`: `cierre-sprint-2.md`, `rnf-18-compatibilidad.md`, `rnf-17-terminologia.md`, `rnf-16-contrastes.md`, `rnf-13-protocolo.md`, `rnf-23-medicion.md` y `revision-dependencias-s2.md`.

**Veredicto: listo con observaciones.** El incremento del informe, "perfil de maestro completo y publicable", funciona de extremo a extremo en el sistema levantado y también en una instalación limpia del commit:

1. comercial crea un servicio y cambia su precio, y el visitante ve el cambio aunque tenga un ETag viejo (CA-20.1 y CA-20.2);
2. el maestro declara el servicio nuevo, con los rechazos de CA-12.1 y el motivo de CA-12.2;
3. curatoría lo aprueba;
4. el maestro declara su cobertura (CA-13.1), su agenda de 24 horas (CA-14.1, CA-14.2 y CA-14.4) y su foto;
5. queda publicado y su perfil público respeta la lista de campos permitidos.

Cuando la licencia de Gas vence, Gas desaparece del perfil público y de la búsqueda, y Pintura sigue (RF-34, CA-24.1 y RNF-25 en su parte del S3). Una licencia sin vencimiento no desactiva nada, aunque corra el planificador (CA-24.3). Un maestro no publicado o suspendido responde el mismo 404, sin registro.

Cumplen con evidencia: RF-05, RF-36, RF-37 del catálogo, RNF-07 (rutas del S3), RNF-11, RNF-14 a RNF-17 y RNF-20 en las pantallas nuevas, y la evidencia automática de RNF-18. RNF-04, RNF-23 y RNF-27 se volvieron a medir y cumplen su umbral. Dos casos quedan como infraestructura preparada, porque su evidencia final depende de la búsqueda o de los tickets del S4 (DA-20):

- RF-06 y RF-07;
- CA-13.2 y CA-14.3.

Quedan BLOCKED el pase manual de RNF-18 (no hay equipo con navegadores de marca ni teléfono) y RNF-13.

Se encontraron **dos defectos nuevos**, ninguno en el código de producción:

- **DEF-QA-011 (baja):** no quedó registrada la revisión de avisos de dependencias al inicio del S3, que exige el umbral de RNF-27.
- **DEF-QA-012 (media):** venció el compromiso de DA-17 (ejecutar RNF-13 en la primera semana del S3) y no se registró el nuevo desplazamiento.

Hay además 7 observaciones (§6). La más relevante para la demostración: la pila principal sirve `frontend/` directo desde la carpeta de trabajo, que durante el QA tenía cambios sin commit de otro agente (OBS-S3-01). Por eso la evidencia de interfaz se repitió sobre la instalación limpia del commit.

---

## 1. Alcance verificado

| Tipo | Identificadores |
|---|---|
| RF | RF-05, RF-06, RF-07, RF-36; RF-34 (DA-12); RF-37 (entradas del catálogo) |
| HU | HU-12, HU-13, HU-14, HU-20, HU-24 |
| CA | CA-12.1, CA-12.2, CA-13.1, CA-13.2 (parcial), CA-14.1, CA-14.2, CA-14.4, CA-20.1, CA-20.2, CA-24.1, CA-24.3 |
| RNF del S3 | RNF-18 (DA-21: todas las pantallas) |
| Compromisos que llegan de sprints anteriores | RNF-25 (DA-14), RNF-13 (DA-17), RNF-07 (DA-03), RNF-11 |
| RNF en las pantallas nuevas | RNF-14, RNF-15, RNF-16, RNF-17, RNF-20 |
| Mediciones repetidas | RNF-04, RNF-23, RNF-27 |
| Adelantos | DA-18 (perfil público parcial, RF-14), DA-19 (foto, dato de RF-13) |
| Transversal | Registros, volumen de fotos, proxy, CSP y cabeceras, CSRF, 401/403/404, regresión del S1 y del S2 (verificación documental) |
| Regresión del S4 | `GET /api/busqueda` (solo que no se rompa; verificación formal en el cierre del S4) |

## 2. Ambiente de prueba

| Dato | Valor |
|---|---|
| Equipo | Equipo de desarrollo: Windows 11 Pro 10.0.26200, 16 CPU lógicas, 15,56 GiB asignados a Docker |
| Docker | Docker Desktop, motor 29.8.0, Compose 5.5.1 |
| Pila principal | `init`, `db` (postgres:16.15-bookworm), `app` (altiro-app:local, commit `3c5d357`, gunicorn con 2 workers), `planificador` y `proxy` (nginx:1.30.5-alpine). `docker compose up -d --build` a las 17:50 UTC: imágenes ya al día y todos los servicios healthy |
| Pila limpia del commit | Motor `docker:29-dind` aislado (`qa-rnf23-s3`) con `git archive HEAD`, sin `.env`. Se usó para RNF-23 y para repetir la interfaz sobre el código exacto del commit. Después se borró (ver §2.1) |
| Navegadores | Imagen `mcr.microsoft.com/playwright/python:v1.63.0-noble`: Chromium 153.0.8010.12 (contexto móvil) y Firefox 155.0 (ventana angosta). Anchos de 320, 390 y 1280 px |
| Cliente HTTP de QA | Python 3.13 (solo biblioteca estándar), en un contenedor efímero que comparte la red del proxy |
| Datos | Solo ficticios: correos `qa3.*@example.com`, RUT sintéticos aleatorios, teléfonos `+56 9 2000 xxxx`, imágenes sintéticas con un segmento EXIF ficticio (`GPSQA-MUESTRA`) |

### 2.1 Acciones con efecto en el ambiente
- **Cuentas ficticias en la base principal:**
  - curatoría, comercial, moderación y control de gestión (`qa3/prep.sh`, contraseña aleatoria por entrada estándar);
  - un cliente;
  - el maestro M (aprobado, publicado, con Gas y Pintura);
  - el maestro M2 (en revisión);
  - las cuentas de los scripts `perfil_prep.sh`, `com_prep.sh` y `cur_prep.sh`.
- **Catálogo:** comercial creó el servicio "Pintura de rejas QA3 2391720542" (queda activo) y el oficio "Oficio QA3 2391720542" (dado de baja, sin borrado físico), con 4 entradas en la bitácora.
- **Cambios directos en la base de datos**, para simular el paso del tiempo sin tocar el código:
  - se cambió la `fecha_vencimiento` de la licencia ficticia de Gas de M (documento 288): hoy, ayer, mañana y sin fecha;
  - al final quedó restaurada en 2027-11-03.
- **Cambios de estado con la API:** curatoría suspendió a M y luego lo volvió a aprobar (P-04), con motivo y bitácora.
- **Registros de accesos denegados:** quedaron 68 filas nuevas en `acceso_denegado` por las pruebas de RNF-07.
- **Suite de pytest en la pila:** `docker compose exec -T app pytest` ya no toca los volúmenes reales (DEF-QA-008 corregido). Antes había 30 fotos y 246 documentos, y después 32 y 253: las diferencias son las subidas propias del QA.
- **Motor aislado de RNF-23:** se borraron **solo** el contenedor `qa-rnf23-s3` (id comprobado) y su volumen anónimo. No se tocaron imágenes, volúmenes ni bases del equipo.
- **Motor aparte `altiro-volumen`:** no se tocó.
- **Archivos temporales:** las contraseñas temporales del scratchpad se borraron al terminar.

## 3. Pruebas ejecutadas

### 3.1 Automatizadas (pytest, pytest-django y time-machine; ADR-014)

| Ejecución | Resultado |
|---|---|
| `docker compose exec -T app pytest -q` (código de la imagen, 17:50 UTC) | **1511 passed** en 379 s. Volumen de fotos: 30 archivos antes y 32 después; documentos: 246 y 253 (subidas del QA en paralelo). Ningún archivo real borrado |
| Suite completa en un contenedor aislado (`docker compose run --rm --no-deps`, `backend/tests` montado, `--create-db`), incluida `test_qa_cierre_s3.py` | **1514 passed** en 381 s |
| `manage.py makemigrations --check --dry-run` | Sin cambios pendientes |
| `manage.py check --deploy` | Los mismos 3 avisos justificados del S1 (W002, W004, W008) |

**Pruebas nuevas** (`backend/tests/test_qa_cierre_s3.py`, 3 pruebas en verde):
- `test_qa_s3_foto_con_etag_valido_de_un_maestro_que_dejo_de_estar_publicado_responde_404` (propuesta del S3, §9.1). Con el ETag de cuando el maestro estaba publicado, la foto de un maestro suspendido responde el 404 neutro, nunca 304.
- `test_qa_s3_ca24_1_el_servicio_regulado_se_oculta_a_la_medianoche_de_santiago`. A las 23:59:59 de la víspera, hora de Chile, Gas se ve; a las 00:00 del día del vencimiento, ya no.
- `test_qa_s3_ca24_3_licencia_sin_vencimiento_no_desactiva_nada_aunque_corra_el_planificador`. Se corren todas las tareas del planificador con el reloj adelantado 1, 5 y 30 años: Gas sigue visible.

### 3.2 Sobre el sistema levantado (API)

Scripts del scratchpad de la sesión, carpeta `qa3/`:

| Script | Qué cubre | Resultado |
|---|---|---|
| `e2e3.py fase1` | CA-20.x con ETag, errores de comercial, RF-37, CA-12.x, CA-13.1, CA-14.x, foto con EXIF, perfil público, privacidad y foto pública | **99 OK, 0 fallos** en la pila principal y **99 OK, 0 fallos** en la instalación limpia del commit |
| `e2e3.py gas …` (5 corridas) | RF-34, CA-24.1 y CA-24.3 con la licencia vencida hoy, vencida ayer, que vence mañana, sin fecha más el planificador, y restaurada | 0 fallos |
| `e2e3.py suspender` | Maestro suspendido, foto con ETag válido, M2 no aprobado, sin registro | 13 OK, 0 fallos; `acceso_denegado` 307 → 307 |
| `e2e3.py terceros` | RNF-07 por ruta y por rol, CSRF | 94 OK, 0 fallos; 68 filas nuevas en `acceso_denegado`, con el detalle en §4.2 |
| `cabeceras.py` | CSP y cabeceras de las pantallas nuevas, foto HTML disfrazada, 413 del proxy y foto ausente | 0 fallos |
| `carga.py` (2 veces) | 10 usuarios simultáneos para RNF-04 | 300 respuestas (282 × 200 y 18 × 201), 0 errores |

### 3.3 Interfaz (Playwright 1.63.0; Chromium 153 y Firefox 155)

Se corrió en la pila principal y **se repitió sobre la instalación limpia del commit** (OBS-S3-01). Los números son los del commit; en la pila principal los resultados fueron los mismos.

| Script | Chromium | Firefox |
|---|---|---|
| `s3_perfil.py`: cobertura, agenda, mi perfil y perfil público, a 390, 320 y 1280 px | 53/53 estados sin desplazamiento lateral; 241 verificaciones OK; **2 fallidas** que son la misma expectativa desactualizada en dos anchos (OBS-S3-04); 0 errores de JS | Igual: 53/53, 241 OK y las 2 de OBS-S3-04; 0 errores de JS |
| `s3_ui.py`: comercial y mis servicios, a 1280, 390 y 320 px | 48/48, 0 verificaciones fallidas, 0 errores de JS | 48/48, 0, 0 |
| `rnf18.py`: pantallas del S1 y del S2, a 320 y 390 px | 106/106 estados, 16/16 chequeos de compatibilidad, 0 errores de JS | 106/106, 16/16, 0 |
| `axe_s3.py`: axe-core 4.10.3, WCAG 2.0, 2.1 y 2.2, A y AA, más objetivos de 44 px y textos de programador visibles | 22 vistas (11 estados × 390 y 320 px): **0 violaciones**, 0 objetivos chicos, 0 textos técnicos | — |
| Regresión del S1 y del S2 (`flujo_s2.py`, `s2_maestro.py`, `cur_ui.py`) | Sin fallos (`FALLOS: ninguno`; solo avisos de consola 4xx esperados) | — |

---

## 4. Resultados por requisito

Clasificación: PASS, FAIL, BLOCKED o NOT IN SCOPE. Lo que el diseño cierra en un sprint posterior se marca como «infraestructura preparada / evidencia final pendiente».

### 4.1 Requerimientos funcionales y criterios de aceptación

| Req. | Criterio del informe | Método y evidencia | Resultado |
|---|---|---|---|
| RF-36 (HU-20) | "Un servicio nuevo queda disponible para los maestros sin intervención en el código" | En vivo: comercial crea "Pintura de rejas QA3 …" (201). Sin tocar el código, aparece en `GET /api/catalogo` y el maestro lo declara (201) y lo publica. Lo mismo en la instalación limpia. pytest: `test_catalogo_administrable.py` (42 pruebas) | **PASS** |
| CA-20.1 | Servicio nuevo disponible para que los maestros lo declaren | Ídem. Con el ETag anterior, el visitante recibe 200, no 304, y ve el servicio nuevo | **PASS** |
| CA-20.2 | "Cuando un visitante consulta el catálogo, ve el valor actualizado" | En vivo: el precio pasa de 25.000 a 30.000, con versión y motivo. El visitante que revalida con el ETag anterior recibe 200 con 30.000. `Cache-Control: no-cache` y ETag en `/api/catalogo` y `/api/oficios` (D-16); sin cambios, 304. El visitante consulta el catálogo por la API pública: no hay una pantalla del catálogo para visitantes (OBS-S3-02) | **PASS** |
| RF-37 (catálogo) | "Autor, acción, entidad, valores anterior y nuevo, motivo y fecha" | En la base: 4 entradas (`catalogo.servicio.crear`, `catalogo.servicio.modificar`, `catalogo.oficio.crear` y `catalogo.oficio.modificar`) con `autor_tipo = usuario`, autor «QA comercial …», `entidad_ref`, `valor_anterior` y `valor_nuevo` (solo campos del catálogo, sin datos personales), motivo y fecha. Los intentos rechazados (400 sin motivo, 409 por versión, 400 sin cambios, 400 `regulado`) **no** dejaron entradas. pytest: la bitácora va en la misma transacción que el cambio | **PASS** para el catálogo (RF-37 completo en S5) |
| ADR-018, punto 2 (RNF-25) | `regulado` obligatorio e inmutable | En vivo: crear un oficio sin `regulado` da 400 en el campo; cambiar `regulado` en un oficio nuevo o en **Gas** da 400 "no se cambia desde aquí". Baja lógica con motivo; sin `DELETE` ni `PUT` (405). El oficio dado de baja sale de `/api/oficios` y comercial lo sigue viendo | **PASS** |
| Versión (D-4) | 409 si la versión no coincide | En vivo: 409 con mensaje accionable, sin cambios ni bitácora | **PASS** |
| RF-05 (HU-12) | "Cada servicio publicado tiene modalidad y monto; no se publica sin ambos" | En la API: sin borradores. En la base: `NOT NULL`, `CHECK monto > 0 AND <= 10000000` y `CHECK modalidad IN (por_trabajo, por_hora)` en `servicio_maestro`, más un índice único parcial por (maestro, servicio) activo | **PASS** |
| CA-12.1 | "No lo publica y señala qué falta" | En vivo: sin modalidad, 400 `{"modalidad": "Elige si cobras por trabajo o por hora."}`; sin monto, 400 `{"monto": "Escribe cuánto cobras, en pesos."}`; sin ambos, los dos campos. Una modalidad que el catálogo no admite y un monto 0 dan 400. Después de los rechazos no hay nada guardado. En la interfaz, el error aparece junto al campo (`s3_ui.py`) | **PASS** |
| CA-12.2 | "El servicio no queda visible para los clientes" sin licencia vigente | En vivo: con la licencia en revisión, el servicio de Gas tiene `visible: false` y el motivo "Los clientes no lo ven: falta tu licencia de Gas vigente y revisada por AlTiro. Sube tu licencia vigente." Gas no aparece en el perfil público hasta que curatoría valida la licencia | **PASS** |
| RF-34 (HU-24, DA-12) | "Deja de aparecer en ese oficio y sigue apareciendo en los no regulados" | En vivo, con el mismo maestro M: la licencia de Gas vence hoy (hora de Chile). En la siguiente lectura, el perfil público muestra solo `['pintura']`; el maestro ve Gas con `licencia_no_vigente`; `GET /api/busqueda?oficio=gas` ya no lo trae y `?oficio=pintura` sí. Lo mismo con la licencia vencida ayer. Si vence mañana, Gas se ve. Al restaurar la fecha, vuelve solo. pytest: `test_rnf25_ca24_1_…` y la nueva prueba de medianoche en Santiago | **PASS** en los servicios y el perfil público. La parte de búsqueda es CA-24.4 (DA-13, S4) |
| CA-24.1 | "Quedan inactivos automáticamente" al cumplirse la fecha | Ídem. La visibilidad se calcula en cada lectura (ADR-019, punto 2): no hay hora de exposición | **PASS** |
| CA-24.3 | Sin fecha de vencimiento, "no se desactiva ningún servicio" | En vivo: licencia sin fecha y `planificador --una-vez` (`tareas_fallidas=0`): Gas y Pintura siguen visibles. pytest: la prueba nueva lo comprueba 1, 5 y 30 años después | **PASS** |
| CA-24.4 | Búsqueda | DA-13. La regresión muestra el comportamiento esperado (§4.6) | **NOT IN SCOPE** (S4) |
| RF-06 (HU-13) | "Un maestro sin comuna base no aparece en resultados" | En vivo: el maestro aprobado sin comuna base ni foto responde el 404 idéntico en el perfil público. Con comuna base pero sin foto, también 404. "Resultados" de búsqueda: DA-20 | **infraestructura preparada / evidencia final pendiente (S4)** |
| CA-13.1 | Sin comuna base, "no me deja guardar" | En vivo: 400 `{"comunas": "Marca cuál de tus comunas es tu comuna principal. Sin ella no puedes guardar."}`, sin nada guardado. Dos comunas base y una comuna fuera de la lista cerrada también dan 400. Con base, 200 con exactamente una. En la base: `UNIQUE (perfil_maestro_id) WHERE es_base` y `UNIQUE (maestro, comuna)`. En la interfaz: error junto al campo (`s3_perfil.py`) | **PASS** |
| CA-13.2 | Quitar una comuna y dejar de aparecer en el filtro | DA-20. La cobertura se reemplaza completa (pytest) | **infraestructura preparada / evidencia final pendiente (S4)** |
| RF-07 (HU-14) | "Se rechaza un rango cuya hora de término no sea posterior a la de inicio" | Ver CA-14.2. En la base: `CHECK (inicio_min >= 0 AND inicio_min < fin_min AND fin_min <= 1440)`, múltiplos de 30 y día ISO de 1 a 7 | **PASS** en la declaración. HU-14 no se cierra completa: CA-14.3 es de S4 |
| CA-14.1 | 24 horas "en todas las pantallas del sistema" | En vivo: 13:00–20:30 se guarda y vuelve como `"13:00"`/`"20:30"`; 20:30–24:00 como `"24:00"`; `"8:00 AM"` da 400. El perfil público muestra la agenda en `HH:MM`. En la interfaz: sin `input type="time"`, horas de 00 a 24, sin AM/PM (`s3_perfil.py`, en los dos motores) | **PASS** |
| CA-14.2 | Término anterior o igual al inicio: rechazo "con un mensaje comprensible" | En vivo: 12:00–12:00 da 400 en `fin` ("Elegiste de 12:00 a 12:00: la hora de término debe ser después de la hora de inicio…"); 22:00–02:00 da 400 con la sugerencia para pasar la medianoche. El solapamiento da 400 en `inicio`; 08:15 da 400 (granularidad). Los bloques contiguos se aceptan | **PASS** |
| CA-14.4 | Se conservan los bloques ya guardados al volver a entrar | En vivo: nueva sesión, `GET` con los 4 bloques guardados (uno por petición, ADR-020, punto 5). En la interfaz: progreso recuperado tras volver a cargar | **PASS** |
| CA-14.3 | Bloque ocupado tras aceptar | DA-20 (tickets del S4) | **NOT IN SCOPE** (S4) |
| DA-18 (RF-14 parcial) | Perfil público: maestro no publicado, 404 idéntico sin registro | En vivo: antes de aprobar, sin foto, suspendido y sin aprobar (M2), responde el 404 **idéntico byte a byte** al de una ref aleatoria. La foto de un suspendido, aun con un ETag válido, da 404 (no 304). `acceso_denegado` 307 → 307. Al reactivarlo (P-04), 200 | **PASS** (adelanto; RF-14 no se declara cumplido) |
| DA-19 (dato de RF-13) | Foto sin EXIF, variantes, solo si está publicado | En vivo: la foto con EXIF y un rótulo GPS ficticio sale sin `Exif` ni rótulo; variantes 160 y 480; `no-cache`, ETag, `nosniff`, `CSP: sandbox`, `CORP: same-origin`; revalidación 304; tamaño no admitido, 404. Un HTML disfrazado da 400 "Envía una foto…"; sin archivo, 400; 10 MB, 413 JSON en español desde el proxy. El maestro solo recibe `tiene_foto` | **PASS** |

### 4.2 RNF-07, RNF-11 y RNF-25

| RNF | Umbral exacto | Método y evidencia | Resultado |
|---|---|---|---|
| RNF-07 | "Cada pantalla o función que recibe un número de registro tiene una prueba automática que confirma que un tercero no puede abrirla" | **Control:** `test_toda_ruta_con_identificador_tiene_prueba_de_terceros_y_usa_uuid` en verde; sin exenciones nuevas (solo la ruta pública de comunas). Rutas del S3 con marca `terceros`: `comercial_modificar_oficio` (3), `comercial_modificar_servicio` (3), `mi_servicio` (4), `mi_bloque` (4), `perfil_publico` (2) y `foto_publica` (2). **En vivo:** otro maestro, en `PATCH` y `DELETE /api/maestros/servicios/<ref>` y en `DELETE /api/maestros/disponibilidad/<ref>`, recibe el 404 **idéntico** al de una ref inexistente, registrado (`servicio_maestro` ×2, `disponibilidad` ×1); la ref inexistente no se registra. Cliente, curatoría, comercial, moderación y control de gestión reciben 403 registrado (entidad `ruta`); anónimo, 401. En las rutas de comercial, el maestro, el cliente y los demás roles reciben 403 registrado y el anónimo 401; una ref inexistente para comercial da 404. En las rutas "me" (`servicios`, `cobertura`, `disponibilidad`, `perfil` y `perfil/foto`), 403 para los demás roles y 401 sin sesión; M2 nunca ve lo de M. El recurso quedó intacto después de todos los intentos | **PASS** para las rutas del S3 (acumulativo hasta S5, DA-03) |
| RNF-11 | "El sistema no ofrece ninguna forma de editar ni borrar una entrada de la bitácora" | No hay rutas nuevas que lean o escriban la bitácora (pytest `test_la_unica_ruta_que_lee_la_bitacora_…` en verde). En la base: los 4 triggers habilitados (`tgenabled = O`). Un `UPDATE` o un `DELETE` directo sobre una entrada del catálogo (dentro de una transacción revertida) da "La bitácora no admite UPDATE (RNF-11)" | **PASS** |
| RNF-25 (DA-14) | "Ningún servicio de gas o electricidad queda visible sin licencia vigente asociada" | En vivo: RF-34 y CA-12.2 (arriba) sobre el perfil público y la búsqueda. pytest: `test_rnf25_ningun_servicio_regulado_visible_sin_licencia_habilitante` recorre todas las rutas públicas del enrutador, incluida `/api/busqueda`, con 20 combinaciones | **PASS** en la parte del S3. La evidencia en la búsqueda se formaliza en el cierre del S4 |

### 4.3 RNF-18 (compromiso del S3) y RNF de usabilidad en las pantallas nuevas

| RNF | Umbral exacto | Método y evidencia | Resultado |
|---|---|---|---|
| RNF-18: evidencia automática (D-15) | "Las dos últimas versiones de Chrome y Firefox, y Chrome en Android, sin que haya que desplazar la pantalla de lado en celulares angostos" | Revisada la evidencia del equipo (`rnf-18-compatibilidad.md`): 4 imágenes × 2 motores, 53 estados por ancho en el S1 y el S2, y las pantallas del S3 en la 1.63.0. **Repetida por QA** con la 1.63.0 (Chromium 153 y Firefox 155), sobre el commit limpio: pantallas del S1 y del S2, 106/106; comercial y mis servicios, 48/48; cobertura, agenda, perfil y perfil público, 53/53. `scrollWidth` igual al ancho (320 o 390), ningún elemento fuera de la pantalla, 16/16 chequeos de compatibilidad y 0 errores de JS | **PASS** |
| RNF-18: pase manual y cierre del umbral | Ídem (navegadores de marca y un teléfono Android real) | `rnf-18-compatibilidad.md` §5 sigue "Pendiente": QA no tiene Chrome ni Firefox de marca en dos versiones ni un teléfono. El Chromium de Playwright no es Google Chrome ni reemplaza a Chrome en Android | **BLOCKED** (sin equipo) |
| RNF-14 | "Botones de al menos 44 por 44 puntos y formularios divididos en pasos de máximo 5 campos" | `axe_s3.py` y los scripts del S3: ningún objetivo menor a 44 px en las 11 vistas nuevas a 320 y 390 px (solo quedan los enlaces dentro de una frase ya conocidos del S1). Pasos: agenda con 5 controles (día, hora y minutos de inicio y de término); servicio de comercial con 5 campos como máximo (nombre, dos precios, disponible y motivo) | **PASS** |
| RNF-15 | "Ningún mensaje muestra códigos internos ni texto de programador" | pytest `test_rnf15_mensajes_maestro.py` (incluye cobertura, agenda, foto y perfil) en verde. En vivo: todos los 400, 403, 404, 409 y 413 del S3 sin trazas ni nombres de restricciones; el 413 del proxy es JSON en español. En pantalla no aparecen `undefined`, `null`, códigos HTTP ni nombres de campo | **PASS** |
| RNF-16 | Contraste WCAG 2.2 y "ningún estado indicado solo con color" | axe-core 4.10.3 en 22 vistas: **0 violaciones**. "Por revisar a mano": los íconos `✓` con `aria-hidden` (siempre acompañan un texto) y el fondo de `#oficio-motivo` cuando otro elemento lo tapa en parte. Los estados van con ícono y texto ("✓ Los clientes ya pueden ver tu perfil", "⚠ Todavía no te ven los clientes", el motivo de la licencia) | **PASS**. `rnf-16-contrastes.md` no tiene tabla del S3 (OBS-S3-05). Sigue pendiente la prueba con lector de pantalla |
| RNF-17 | "Revisión de terminología sobre todas las vistas del maestro" | `rnf-17-terminologia.md` §5 y §6 cubren las pantallas nuevas ("comuna principal", "forma de cobro", "horario"). En vivo, los textos del servidor usan ese lenguaje. Queda "bloque" en los errores de agenda del servidor (OBS-S3-06) | **PASS**, con la condición de la pregunta del protocolo de RNF-13 |
| RNF-20 | "Los pasos completados se conservan al reingresar" | CA-14.4 (arriba). Foto con corte de red: "Reintentar" y la foto se conserva (`s3_perfil.py`, en los dos motores) | **PASS** |
| RNF-13 (DA-17) | "Al menos 2 de 3 participantes de prueba la completan en ≤ 10 minutos" | No existe `docs/testing/rnf-13-prueba-usabilidad.md` y ninguna sesión quedó registrada. El compromiso de DA-17 (primera semana del S3) venció sin actualizarse (DEF-QA-012) | **BLOCKED** (personas externas y teléfono) |

### 4.4 RNF de recursos, instalación y dependencias

| RNF | Umbral exacto | Método, entorno y evidencia | Resultado |
|---|---|---|---|
| RNF-04 | "No más de 2 GB de memoria para todo el sistema" | `docker stats` con la pila completa: 20 muestras durante las pruebas de interfaz, y 30 muestras durante `carga.py` (10 usuarios simultáneos con búsqueda, perfil público, catálogo y 18 subidas de fotos de 1,4 MB). Máximos: app 205,3 MiB, db 96,2 MiB, planificador 48,1 MiB y proxy 27,0 MiB (**≈ 377 MiB**). `memory.peak` desde el arranque, que incluye la suite de pytest: app 367 MiB, db 344 MiB (base de pruebas en el mismo contenedor), planificador 94 MiB y proxy 37 MiB. Aun sumando los picos, **≈ 842 MiB** | **PASS** (la evidencia con el volumen de prueba del informe es del S4) |
| RNF-23 | "Un solo comando deja el sistema andando en 10 minutos o menos, con las instrucciones escritas junto al código" | Motor `docker:29-dind` limpio (0 imágenes, 0 volúmenes, 0 contenedores), `git archive HEAD` de `3c5d357`, sin `.env`, `docker compose up -d --build` con código 0. `/api/health/` por HTTPS responde OK a los **44 s**; los cinco servicios sanos a los 54 s. Detalle en `rnf-23-medicion.md` | **PASS** (confirmar en el laboratorio) |
| RNF-27 | "Cada librería queda declarada con versión exacta y hay una revisión de avisos registrada al inicio de cada sprint" | Sin cambios en `requirements*.txt` desde el S2 (`git diff fd6449b HEAD`); todas con `==`. `pip-audit` 2.10.1, en un contenedor efímero `python:3.13.15-slim-bookworm`, sobre los dos archivos: "No known vulnerabilities found" con PyPI y con OSV (29-09-2026, 18:1x UTC). **No hay una revisión registrada al inicio del S3**: `revision-dependencias-s2.md` la dejó pendiente ("Próxima revisión: inicio del Sprint 3") y no existe otro registro (DEF-QA-011) | Versiones y avisos: **PASS**. Registro al inicio del S3: **FAIL** (DEF-QA-011) |

### 4.5 Seguridad y privacidad transversal, y regresión del S1 y del S2

| Verificación | Evidencia | Resultado |
|---|---|---|
| Privacidad del perfil público | La respuesta trae solo `ref`, `nombre`, `foto`, `servicios`, `comunas`, `agenda` y `bloques` (este último agregado por ADR-022, punto 4). Sin RUT (con o sin guion), teléfono, correo, `+56`, `es_base`, vencimiento, licencia, documento, expediente, la ref del expediente, `"id"`, estado ni motivo. Comunas ordenadas por nombre: la base no se deduce (D-14). La ref pública es distinta de la del expediente. `no-store` | **PASS** |
| Datos personales y secretos en registros | 18.347 líneas de `app`, `proxy`, `planificador` y `db`: 0 apariciones de los RUT de QA, `@example.com`, nombres «Maestro QA3» o «Cliente QA3», `MUESTRA`, `GPSQA`, `+56 9`, `sessionid`, `csrftoken`, `argon2`, `contrasena`, `Traceback`, `t=eyJ` ni de ninguna de las contraseñas generadas. El planificador solo registra conteos | **PASS** (OBS-S3-07) |
| Volumen de fotos | `altiro_fotos` montado **solo** en `app` (`docker inspect`: el planificador monta `documentos` y `secretos`; el proxy, solo plantillas, frontend y certificados). Directorio `700 altiro`, archivos `600` de dueño 10001, nombres UUID. Rutas adivinables (`/fotos/`, `/media/fotos/`, `/fotos/<ref>-480.jpg`, `/api/fotos/`): 404, sin imagen | **PASS** |
| Proxy sin cuerpos a disco | La subida de la foto tiene su propia `location` (`client_max_body_size 9m`, `client_body_buffer_size 9m`); la foto pública usa `proxy_max_temp_file_size 0`. Tras las subidas de 1,4 MB: `find /var/cache/nginx -type f` da 0 archivos; 0 líneas "buffered to a temporary file" o "client request body is buffered". La descarga de documentos del S2 se mantiene (DEF-QA-009 corregido) | **PASS** |
| CSP y cabeceras | `mi-perfil`, `mi-agenda`, `mi-cobertura`, `mis-servicios`, `comercial`, `perfil-maestro`, `/api/catalogo`, perfil público y 404: CSP sin `unsafe-inline` en `script-src`, `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: same-origin`, `Server: nginx` sin versión y sin HSTS (ADR-008). El frontend no usa `innerHTML` | **PASS** |
| CSRF | `POST /api/maestros/disponibilidad` y `POST /api/comercial/oficios` sin token: 403 (`AlTiro-Rechazo: csrf` en el primero) | **PASS** |
| Base de datos del S3 | Revisión de `\d` de `oficio`, `servicio`, `servicio_modalidad`, `servicio_maestro`, `cobertura`, `disponibilidad` y `perfil_publico`: unicidades, CHECK de rango y modalidad, índices parciales, y FK sin `ON DELETE CASCADE` (Django `PROTECT`/`DEFERRABLE`) | **PASS** |
| Regresión del S2 (verificación documental) | `e2e3.py` hizo el recorrido postular, documentos, validar y aprobar en las dos pilas; `s2_maestro.py` y `cur_ui.py` sobre el commit limpio: `FALLOS: ninguno`; pytest completo en verde | **PASS** |
| Regresión del S1 | `flujo_s2.py`: registro por pasos, progreso tras recargar, errores, ingreso, cuenta, perfil de maestro y cierre de sesión; `rnf18.py` a 320 y 390 px; pytest completo | **PASS** |

### 4.6 Regresión de la búsqueda del S4 (no es la verificación formal)

| Verificación | Resultado |
|---|---|
| `GET /api/busqueda?oficio=pintura&comuna=<base>` trae al maestro publicado M | OK |
| Con la licencia de Gas vencida: `?oficio=gas` no trae a M y `?oficio=pintura` sí; al restaurar, vuelve | OK |
| Maestro suspendido: fuera de la búsqueda | OK |
| 10 usuarios simultáneos (`carga.py`, 2 corridas): 94 búsquedas, todas con 200 | OK |

La búsqueda no rompe nada del S3. RNF-01, CA-24.4, CA-13.2 y los demás del S4 se verifican en su cierre.

---

## 5. Recorrido extremo a extremo (incremento del informe)

Una sola secuencia con `e2e3.py`, repetida idéntica en la instalación limpia del commit. En la interfaz la cubren `s3_ui.py` y `s3_perfil.py`.

1. **Comercial crea** el servicio "Pintura de rejas QA3 …" por trabajo a $25.000 (201, con bitácora). El visitante con un ETag viejo lo ve (CA-20.1).
2. **Comercial cambia el precio** a $30.000, con versión y motivo. El visitante que revalida ve $30.000 (CA-20.2). Una versión vieja da 409 y sin motivo da 400, sin bitácora.
3. **El maestro postula**, declara Gas y Pintura y sube la cédula, los antecedentes y la licencia de Gas.
4. **Servicios:**
   - CA-12.1: sin modalidad o sin monto, 400 en el campo y nada guardado;
   - declara el servicio nuevo a $28.000, que es visible cuando corresponda;
   - Gas queda con el motivo de la licencia (CA-12.2);
   - el perfil público responde 404.
5. **Curatoría valida y aprueba.**
6. **Cobertura:** sin comuna principal, 400 (CA-13.1); con Concepción como base, más Talcahuano y Chiguayante, 200.
7. **Agenda:**
   - 13:00–20:30 y 20:30–24:00 los martes; 08:00–12:00 los jueves y los sábados;
   - rechazos de CA-14.2, del solapamiento, de la granularidad y de AM/PM;
   - al volver a entrar, siguen los 4 bloques (CA-14.4).
8. **Foto con EXIF:** 201. El maestro queda publicado.
9. **El perfil público** muestra Pintura ($28.000) y Gas, las comunas sin indicar la base y la agenda en 24 horas, sin datos personales. La foto sale sin EXIF.
10. **Vencimiento:** con la licencia de Gas vencida, Gas desaparece y Pintura sigue (RF-34, CA-24.1). Sin fecha de vencimiento y después del planificador, sigue visible (CA-24.3).
11. **Suspensión:** 404 idéntico, también en la foto con ETag. Al reactivarlo, 200.

---

## 6. Defectos y observaciones

Numeración continuada desde DEF-QA-010.

### DEF-QA-011 — No hay revisión de avisos de dependencias registrada al inicio del S3
- **Afecta a:** RNF-27. Umbral: "hay una revisión de avisos registrada al inicio de cada sprint". También la propuesta del S3, §1.3 y §6 (paso 0: "RNF-27").
- **Severidad:** baja. Las dependencias no cambiaron desde el S2 y la revisión de QA al cierre no encontró avisos, pero el umbral pide un registro **al inicio** de cada sprint, y es un entregable de la Definición de Hecho.
- **Precondición:** Sprint 3 terminado (commit `3c5d357`).
- **Pasos:**
  1. `grep -rln "pip-audit" docs/`;
  2. revisar `docs/testing/` y `docs/alcance/`.
- **Esperado:** un registro fechado al inicio del S3 (por ejemplo, `revision-dependencias-s3.md`) con la herramienta, las fuentes y el resultado.
- **Observado:** solo `revision-dependencias-s2.md` (07:25 UTC del 29-09), que termina con "Próxima revisión: inicio del Sprint 3", y `cierre-sprint-2.md`. No hay registro del S3.
- **Evidencia de QA al cierre:** `pip-audit` 2.10.1 con PyPI y OSV sobre `requirements.txt` y `requirements-pruebas.txt`: "No known vulnerabilities found".
- **Área responsable:** equipo (quien corresponda a RNF-27: `backend` o `qa`). Registrar la revisión del S3, que puede usar el resultado de este cierre si el equipo lo acepta, y hacer la del S4 al empezar.

### DEF-QA-012 — Venció el compromiso de DA-17 (RNF-13) sin registrar un nuevo desplazamiento
- **Afecta a:** RNF-13 ("Al menos 2 de 3 participantes de prueba la completan en ≤ 10 minutos") y DA-17 ("la sesión… pasa a la **primera semana del S3**"). También el control de cambios (CLAUDE.md §11: "registrar cualquier desplazamiento de alcance con fecha, motivo y autorización") y la condición pendiente de RNF-17.
- **Severidad:** media. El informe (§4.3.3) señala RNF-13 como el requisito "que más discute la viabilidad del negocio". Al cierre del S3 sigue sin ninguna evidencia, y el registro de alcance todavía dice "S3, semana 1".
- **Pasos:**
  1. buscar `docs/testing/rnf-13-prueba-usabilidad.md`, que es donde el protocolo registra el resultado (§10);
  2. revisar DA-17 en `bitacora-de-alcance.md`.
- **Esperado:** el resultado de la sesión con 3 participantes o, si no se hizo, DA-17 actualizado con la nueva fecha, el motivo y la autorización.
- **Observado:** el archivo no existe y DA-17 no tiene estado nuevo. El flujo del maestro creció en el S3 (cobertura, agenda, foto y servicios) y el protocolo solo mide la postulación. Conviene decidir si la sesión incluye también "completar el perfil".
- **Área responsable:** equipo y representante del producto. No es un defecto de código.

### Observaciones (no son defectos)
- **OBS-S3-01 (entorno de la demostración):** el proxy monta `./frontend` desde la carpeta de trabajo. Durante este QA (desde las 17:54 UTC), la carpeta tenía cambios sin commit de otro agente:
  - archivos modificados: `base.css`, `index.html`, `agenda.js`, `formato.js`, `perfil-publico.js`, `mi-agenda.html` y `perfil-maestro.html`;
  - archivos nuevos: `buscar.html`, `buscar.js` y `ayuda-orden.html`.

  Por eso la interfaz del cierre se repitió sobre una instalación limpia de `3c5d357`, con los mismos resultados. Esos cambios quedaron después en el commit `a5ea358` (frontend de búsqueda del S4, incremento 3), que no forma parte de este cierre. Recomendación: no editar `frontend/` en la pila que se va a demostrar o verificar, o verificar siempre sobre un `git archive`.
- **OBS-S3-02 (CA-20.2, visitante):** el visitante ve el catálogo y los precios de referencia solo por la API pública (`GET /api/catalogo`). Ninguna pantalla pública los muestra: solo «Mis servicios» del maestro y «Comercial». CLAUDE.md dice que el visitante tiene "solo lectura de perfiles públicos y precios de referencia", y la propuesta del S3, §5, no planificó esa pantalla. Queda para que `architect` decida si entra con la búsqueda del S4.
- **OBS-S3-03 (instalación limpia):** una instalación nueva tiene los 8 oficios pero **ningún servicio**, así que ningún maestro se puede publicar hasta que comercial cree servicios (esperado por P-17). El comando `cargar_datos_demo`, que carga 15 servicios de demostración sin escribir en la bitácora (§8.5), no está en el `README.md`.
- **OBS-S3-04 (evidencia desactualizada):** `rnf-18-compatibilidad.md` §8.2 dice que "la API pública trae solo `ref`, `nombre`, `foto`, `servicios`, `comunas` y `agenda`". El script `s3_perfil.py` verifica exactamente eso, y por eso da 2 verificaciones fallidas: ADR-022, punto 4 (provisional), agregó `bloques`. El producto se ajusta a la decisión vigente (los bloques no llevan datos del ticket); hay que actualizar el script y el documento.
- **OBS-S3-05 (RNF-16):** `rnf-16-contrastes.md` no tiene la tabla de contrastes de los estilos nuevos del S3. axe-core no encontró violaciones, pero la tabla es la evidencia manual del umbral. Sigue pendiente la prueba con lector de pantalla del S2.
- **OBS-S3-06 (RNF-17):** los errores de agenda del servidor dicen "bloque" ("se cruza con tu bloque del martes…"), mientras la pantalla dice "horario". Ya estaba anotado en `rnf-17-terminologia.md` §6 y sigue igual. "Bloque" es la palabra de HU-14, así que se lleva a la pregunta del protocolo de RNF-13.
- **OBS-S3-07 (registros):** los avisos de Django incluyen la ruta con la ref pública o la del recurso (`Not Found: /api/maestros/publicos/<uuid>`) y el id numérico del usuario en "Inicio de sesión correcto del usuario N". No son datos personales en sí, pero se revisan en RNF-22 (S5), como OBS-04 del S2.

---

## 7. Desplazamientos de alcance

Confirmados en `docs/alcance/bitacora-de-alcance.md`, todos autorizados por el equipo de desarrollo y sin conformidad del representante todavía:

| ID | Estado verificado |
|---|---|
| DA-12 | **Cerrado en S3: confirmado.** RF-34, CA-24.1 y CA-24.3 (servicios) funcionan en vivo y en pytest, tal como describe el registro. Además, se verificó el borde de la medianoche de Santiago |
| DA-13 | Vigente (CA-24.4 en S4). La regresión de la búsqueda ya muestra el comportamiento esperado |
| DA-14 | **Parte S3 cerrada: confirmada** (perfil público, catálogo y la prueba de todas las rutas públicas). La parte de búsqueda, en S4 |
| DA-15 | **Cerrado: confirmado** (RF-36 en vivo; `/api/oficios` lista solo los oficios activos) |
| DA-16 | Vigente: planificador healthy; RNF-04 y RNF-23 medidos otra vez en este cierre |
| DA-17 | **Vencido sin actualizar** (DEF-QA-012) |
| DA-18 | Confirmado como adelanto parcial. Desde el S4 el perfil público también trae `bloques` (ADR-022, punto 4); conviene mencionarlo en DA-18 |
| DA-19 | Confirmado (foto sin EXIF, volumen solo en `app`, entregada solo si el maestro está publicado). Siguen abiertos P-14 y P-18 |
| DA-20 | Correcto: RF-06 en "resultados", CA-13.2 y CA-14.3 quedan para el cierre del S4 |
| DA-21 | Evidencia automática confirmada y repetida; pase manual pendiente |

**Faltantes o por actualizar:**
- DA-17 (DEF-QA-012).
- La revisión de RNF-27 del S3 (DEF-QA-011).
- DA-18: agregar que ADR-022 extendió el perfil con `bloques`.
- Siguen sin registro ni fecha, desde el S2: la prueba con lector de pantalla (RNF-16) y el pase manual de RNF-18.

## 8. Riesgos

- **RNF-13 sin ejecutar** (DEF-QA-012). Es el riesgo principal de viabilidad, y el flujo del maestro ahora es más largo (postulación, servicios, cobertura, agenda y foto).
- **RNF-18 sin pase manual:** el umbral nombra navegadores de marca y Chrome en Android; la evidencia automática no los reemplaza.
- **Fotos sin moderación** (P-18, ADR-021, punto 5). Una foto inapropiada queda pública apenas el maestro se publica.
- **Decisiones provisionales:** ADR-018 a ADR-021 sostienen reglas visibles (foto obligatoria, patrón semanal, `regulado` inmutable, nombre completo). Si el representante responde distinto, cambian el modelo o la interfaz.
- **Entorno de la demostración:** frontend servido desde la carpeta de trabajo (OBS-S3-01) y catálogo vacío en una instalación limpia (OBS-S3-03).
- **Respaldo:** los volúmenes `fotos` y `documentos` y la clave de cifrado siguen sin respaldo hasta RNF-19 (S5).

## 9. Supuestos provisionales pendientes de validar

**Preguntas al representante** (`preguntas-representante-s2.md`; fecha de envío: pendiente). Todas siguen sin respuesta y el sistema funciona con el supuesto indicado, que se verificó tal como está escrito:

| # | Pregunta | Supuesto vigente | Verificado en este cierre |
|---|---|---|---|
| P-12 | ¿Puede comercial declarar un oficio nuevo como regulado? | Sí, solo al crearlo; después es inmutable | `regulado` es obligatorio al crear y da 400 al intentar cambiarlo, también en Gas |
| P-13 | ¿Disponibilidad por semana o por fechas? | Patrón semanal | Agenda por día de la semana; el perfil muestra el patrón |
| P-14 | ¿Foto obligatoria para aparecer? | Sí | Sin foto, 404 y el pendiente "Falta que subas tu foto." |
| P-15 | ¿Nombre completo en el perfil público? | Sí, tal como está registrado | El perfil muestra el nombre registrado completo |
| P-16 | ¿Un maestro aprobado puede agregar un oficio? | No en el S3 | `declarar_oficios` solo admite `en_revision` u `observado`; en otro estado responde 409 (S2, sin cambios en el S3) |
| P-17 | ¿Servicios y precios de referencia de cada oficio? | Datos ficticios cargados por comercial | Instalación limpia sin servicios; `cargar_datos_demo` para la demostración (OBS-S3-03) |
| P-18 | ¿Hay moderación de fotos? | No definida | Riesgo abierto (§8) |

Siguen también P-01 a P-11 del S2 y los supuestos V-01 a V-05.

**Aclaraciones de implementación de la propuesta del S3** (provisionales; se revisan en la revisión del sprint). Todas se verificaron tal como están escritas y ninguna contradice al informe:

- **§8 (incrementos 1 y 2):**
  1. El código del oficio se deriva del nombre: `oficio_qa3_2391720542`.
  2. `orden` automático (91 y 17), nombre único sin distinguir mayúsculas (400) y tope de 10.000.000 (pytest).
  3. Las modalidades reemplazan el conjunto completo; una modificación sin cambios da 400; el alta concurrente da 409 (pytest).
  4. `/api/oficios` lista solo los oficios activos.
  5. `cargar_datos_demo` no escribe en la bitácora: en la base principal, 0 entradas `catalogo.*` con autor `sistema`; lo cubre una prueba.
  6. Migración 0003: sin efecto en bases actualizadas.
  7. Ningún servicio es visible sin cobertura y foto (pendientes en vivo).
- **§9 (incrementos 3 a 5):**
  1. Foto con `no-cache` y ETag, y se vuelve a exigir la publicación antes del 304: 404 con un ETag válido cuando el maestro está suspendido (en vivo y con prueba nueva).
  2. Variantes de 160 y 480 sin agrandar (pytest).
  3. Bloqueo por maestro y concurrencia (pytest).
  4. Foto con el expediente rechazado: 409 (pytest).
  5. El maestro solo recibe `tiene_foto`.
  6. Comunas por nombre, sin `es_base`.
  7. Claves de error `comunas`, `inicio` y `fin`.
  8. Ningún mensaje del servidor dice "Recarga la página" (`grep`: 0 en el código de producción).

## 10. Recomendación para el Sprint 4

1. **Antes de la revisión del S3:**
   - registrar la revisión de dependencias del S3 (DEF-QA-011) y hacer la del S4 al empezar;
   - actualizar DA-17 con la nueva fecha, el motivo y la autorización, y decidir si la sesión de RNF-13 incluye completar el perfil (DEF-QA-012).
2. **RNF-13:** ejecutar la sesión con 3 participantes lo antes posible, con la pregunta de terminología de RNF-17 ("perfil", "cobertura", "bloque").
3. **RNF-18:** hacer el pase manual de `rnf-18-compatibilidad.md` §5, que incluye las pantallas del S3 y las del S4 cuando existan.
4. **Documentos de prueba** (OBS-S3-04 y OBS-S3-05):
   - actualizar `s3_perfil.py` y `rnf-18-compatibilidad.md` §8.2 con `bloques`;
   - agregar a `rnf-16-contrastes.md` la tabla de los estilos del S3.
5. **Decisión de `architect`:** si el visitante tendrá una pantalla con el catálogo y los precios de referencia (OBS-S3-02).
6. **README:** documentar `cargar_datos_demo` (OBS-S3-03).
7. **Entorno:** no modificar `frontend/` en la pila de la demostración mientras se verifica (OBS-S3-01).
8. **Preguntas al representante:** enviar el paquete de P-01 a P-23, cuya fecha de envío sigue pendiente.
