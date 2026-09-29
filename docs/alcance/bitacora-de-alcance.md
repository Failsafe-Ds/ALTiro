# Bitácora de alcance

Registro de desplazamientos de alcance exigido por el informe (§5.3.6, Control de cambios): todo lo que desplaza algo comprometido queda anotado "con fecha, motivo y quién lo autorizó, de manera que nada se saca del alcance de forma tácita".

- Alcance comprometido del Sprint 1 (informe §5.3.5): "Identidad, roles y control de acceso, con RF-01 a RF-03, RNF-05 a RNF-12 y RNF-23 a RNF-24".
- Origen de esta lista: `docs/testing/cierre-sprint-1.md`, §6, con respaldo en la propuesta del S1 (§1.2, §1.5 y §2.1) y en ADR-010 («Decisión»).
- **Ningún registro cambia una HU, un RF ni un RNF.** Cada uno mueve la *evidencia* o el *momento* del cumplimiento, o declara una medida aún no tomada.
- **Autorización:** todos los registros los autorizó el equipo de desarrollo. **Ninguno tiene todavía la conformidad del representante del producto ni de la contraparte**; se presentan en la revisión del Sprint 1 (informe §5.4.1: las decisiones del representante son provisorias hasta que la contraparte las confirme).
- **Fecha:** se usa la fecha de la decisión documentada cuando existe. Si solo existe el registro de este documento, se indica "fecha de formalización documental".

## Resumen

| ID | Desplazamiento | Nuevo cierre | Tipo |
|---|---|---|---|
| DA-01 | Evidencia de RNF-06 | S2 (cerrado el 2026-09-28) | Temporal (cerrado) |
| DA-02 | Evidencia de RNF-08 | S4 | Temporal |
| DA-03 | RNF-07 se cumple de forma acumulativa | S2 a S5 | Temporal |
| DA-04 | CA-25.3 en "Terminado sin validar" | Revisión del S1 | Temporal |
| DA-05 | CA-25.1 y CA-25.2 | S4 y S2 | Temporal |
| DA-06 | Purga automática de `acceso_denegado` | S2 (cerrado el 2026-09-28, con el planificador de DA-16) | Temporal (cerrado) |
| DA-07 | RNF-22 parcial | S5 | Temporal |
| DA-08 | Barrera 3 de la bitácora no implementada | Evaluar en S5 | Temporal, condicionado a capacidad |
| DA-09 | Reautenticación de RNF-09 | Según decisión de alcance | Pendiente de decisión |
| DA-10 | Uso de la bitácora desde S2 | S2 | Adelanto (definitivo) |
| DA-11 | RNF-23 sin medir en equipo limpio | Medido el 2026-09-28 (47 s); confirmar en el laboratorio | Temporal (cerrado) |
| DA-12 | RF-34, CA-24.1 y CA-24.3 (servicios) pasan a S3 | S3 (cerrado el 2026-09-29) | Temporal (cerrado) |
| DA-13 | CA-24.4 pasa a S4 | S4 | Temporal |
| DA-14 | Evidencia de RNF-25 pasa a S3 y S4 | S3 (parte S3 cerrada el 2026-09-29) y S4 | Temporal |
| DA-15 | Adelanto: catálogo mínimo de oficios (S3 → S2) | S2; RF-36 cerrado en S3 el 2026-09-29 | Adelanto (cerrado) |
| DA-16 | Adelanto: planificador (S4 → S2) | S2 (implementado el 2026-09-28) | Adelanto |
| DA-17 | Ejecución de RNF-13 al inicio del S3 | S3, semana 1 | Temporal |
| DA-18 | Adelanto: perfil público parcial (RF-14) de S4 a S3 | S3 | Adelanto |
| DA-19 | Adelanto: foto del maestro (dato de RF-13) de S4 a S3 | S3 | Adelanto |
| DA-20 | Evidencia de RF-06 en "resultados", CA-13.2 y CA-14.3 pasan a S4 | S4 | Temporal |
| DA-21 | RNF-18 se aplica retroactivamente a las pantallas de S1 y S2 | S3 | Ampliación de verificación |

## Registros

### DA-01 — Evidencia de RNF-06 pasa a S2
- **Fecha:** 2026-09-27 (propuesta del S1, §1.2 y §1.5, punto 1).
- **Alcance original:** RNF-06 en S1 (§5.3.5). Umbral: "Guardados fuera de las carpetas accesibles desde internet y entregados con un enlace que caduca a los 10 minutos".
- **Cambio:** en S1 se entrega solo la utilidad de enlace firmado (`autorizacion/enlaces.py`, 600 s) con sus pruebas. El volumen de documentos, la descarga y la evidencia del umbral se cierran en S2.
- **Motivo:** los documentos que protege RNF-06 (cédula, antecedentes, licencias) existen desde S2 (RF-04).
- **Impacto:** RNF-06 queda "infraestructura preparada / evidencia final pendiente" al cierre del S1. Sin riesgo de exposición: en S1 no hay documentos.
- **Estado (2026-09-28): cerrado en S2, incremento 3.** Volumen `documentos` montado solo en `app`; entrega por vista con la política reaplicada; enlace válido a los 590 s y rechazado a los 605 s en vivo (600 y 601 s en pruebas); el token no queda en el registro de acceso de Nginx ni en el de la aplicación.
- **Corrección (2026-09-29, DEF-QA-009):** el QA de cierre del S2 encontró el token en el **registro de errores** de Nginx (`[warn] an upstream response is buffered to a temporary file … archivo?cara=…&t=…`) y la foto descifrada escrita temporalmente en `/var/cache/nginx/proxy_temp`. La ruta de descarga (`location ~ ^/api/documentos/[^/]+/archivo$`, única que entrega documentos o fotos privadas) ahora usa `proxy_max_temp_file_size 0` con buffers en memoria de 8 MB (el cuerpo nunca pasa por el disco del proxy) y `error_log /dev/null` (Nginx no registra en esa ruta ningún aviso ni error, que llevarían la línea de petición completa). Evidencia en vivo (07:43 UTC): maestro ficticio nuevo, foto de 1,7 MB (1,26 MB tras recodificar), descarga a 150 KB/s con respuesta 200; `docker compose logs proxy` desde el reinicio: 0 líneas `buffered to a temporary`, 0 con `t=` y 0 con el prefijo del token; el registro de acceso muestra la ruta sin consulta; `/var/cache/nginx/proxy_temp` sin archivos ni cambios de fecha. **Riesgo residual:** los errores de Nginx en esa ruta (por ejemplo, la app caída) ya no quedan en su registro; los de la aplicación sí, sin la consulta. Los mensajes de Nginx previos a la selección de la ruta (petición o cabeceras mal formadas) son, en general, de nivel `info`, por debajo del nivel `notice` de la imagen; no se verificó cada caso posible.
- **Autorización:** equipo de desarrollo.
- **Relacionado:** RNF-06, RF-04, HU-11, R-01, M-02; ADR-001, ADR-011.

### DA-02 — Evidencia de RNF-08 pasa a S4
- **Fecha:** 2026-09-27 (propuesta del S1, §1.2 y §1.5, punto 1).
- **Alcance original:** RNF-08 en S1. Umbral: "Esos datos no se envían al dispositivo del maestro, y se comprueba revisando lo que el servidor manda y no lo que la pantalla muestra".
- **Cambio:** en S1 se entregan la serialización con lista explícita de campos y la utilidad de prueba `assert_campos_ausentes`. La evidencia del umbral se cierra en S4.
- **Motivo:** los tickets pendientes, con la dirección y el teléfono que se ocultan, existen desde S4 (RF-17).
- **Impacto:** RNF-08 queda "infraestructura preparada / evidencia final pendiente".
- **Autorización:** equipo de desarrollo.
- **Relacionado:** RNF-08, RF-17, R-02; ADR-002.

### DA-03 — RNF-07 se cumple de forma acumulativa
- **Fecha:** 2026-09-27 (propuesta del S1, §1.2).
- **Alcance original:** RNF-07 en S1. Umbral: "cada pantalla o función que recibe un número de registro tiene una prueba automática que confirma que un tercero no puede abrirla".
- **Cambio:** en S1 se entregan la autorización centralizada y la prueba de control, que falla si una ruta con identificador no tiene su prueba de acceso de terceros. El umbral se cumple a medida que cada sprint agrega rutas (S2 a S5).
- **Motivo:** en S1 no hay recursos de negocio con identificador en la ruta; el mecanismo se verifica sobre un recurso ficticio solo de pruebas.
- **Impacto:** el umbral no puede declararse cumplido del todo hasta S5, pero ninguna ruta nueva puede quedar sin prueba.
- **Autorización:** equipo de desarrollo.
- **Relacionado:** RNF-07, CA-25.1, CA-25.2, R-01, R-05; ADR-011.

### DA-04 — CA-25.3 en "Terminado sin validar"
- **Fecha:** 2026-09-28 (ADR-010, «Decisión», punto 1).
- **Alcance original:** CA-25.3 (HU-25): "Dado un intento de acceso denegado, cuando se registra el evento, entonces queda en la bitácora con usuario, recurso y fecha".
- **Cambio:** se implementa como registro separado `acceso_denegado`, con retención de 90 días, y no en la bitácora administrativa. El criterio queda "Terminado sin validar" hasta que el representante del producto confirme esa interpretación de "bitácora".
- **Motivo:** tensión entre la inmutabilidad de la bitácora (RNF-11, regla de HU-19), la retención acotada (M-08) y el alcance de la bitácora (M-03).
- **Impacto:** si no se valida, habrá que reabrir ADR-010.
- **Autorización:** equipo de desarrollo; falta la validación del representante del producto.
- **Relacionado:** CA-25.3, HU-25, RNF-11, RF-37, M-03, M-08; ADR-010, ADR-011.

### DA-05 — CA-25.1 y CA-25.2 pasan a S4 y S2
- **Fecha:** 2026-09-27 (propuesta del S1, §1.1: "CA-25.1 y CA-25.2 dependen de objetos de S2 y S4").
- **Alcance original:** HU-25 está trazada al S1 por NTI-09.
- **Cambio:** CA-25.1 (órdenes) se demuestra en S4 y CA-25.2 (documentos) en S2. En S1 el mecanismo se prueba sobre el recurso ficticio.
- **Motivo:** las órdenes y los documentos no existen en S1.
- **Impacto:** HU-25 no se cierra en S1; solo CA-25.3 (ver DA-04).
- **Estado (2026-09-28):** CA-25.2 **cerrado en S2, incremento 3**. Un cliente, otro maestro y los roles comercial, moderación y control de gestión reciben el 404 neutro al pedir el documento de identidad de un maestro, y queda una fila en `acceso_denegado`. CA-25.1 sigue pendiente para S4.
- **Autorización:** equipo de desarrollo.
- **Relacionado:** HU-25, CA-25.1, CA-25.2, NTI-09; ADR-011.

### DA-06 — Purga automática de `acceso_denegado` pasa a S4
- **Fecha:** 2026-09-28 (ADR-010, «Decisión», punto 3).
- **Alcance original:** M-08 (§6.2), "retención acotada del registro".
- **Cambio:** en S1 la purga de filas con más de 90 días ocurre al registrar una nueva denegación y con el comando `purgar_accesos_denegados`. La ejecución periódica llegará con el planificador de S4.
- **Motivo:** S1 no tiene planificador de tareas.
- **Impacto:** si no hay denegaciones ni se ejecuta el comando, las filas vencidas pueden quedar más de 90 días. Riesgo bajo en la prueba de concepto.
- **Estado (2026-09-28): cerrado en S2, incremento 5 (DA-16).** El servicio `planificador` corre cada hora `autorizacion.tareas.purgar_accesos_denegados`, que reutiliza `purgar_vencidos()` (condición con `now()` de SQL, ADR-010, punto 3). Evidencia: prueba automática (fila de 91 días borrada; filas de 89 y 0 días conservadas; segunda corrida sin cambios) y corrida en vivo con el conteo en el registro del planificador (`accesos_denegados_purgados=0`, sin filas vencidas en la base local).
- **Autorización:** equipo de desarrollo.
- **Relacionado:** M-08, CA-25.3, RNF-22; ADR-010.

### DA-07 — RNF-22 parcial hasta S5
- **Fecha:** fecha de formalización documental 2026-09-28. Se basa en ADR-010, «Decisión», punto 3, y en el análisis de arquitectura de esa fecha.
- **Alcance original:** RNF-22 está planificado para S5. En S1 solo se emiten los eventos de purga y de asignación de roles.
- **Cambio:** esos eventos existen desde S1, pero el formato completo de RNF-22 (usuario en cada entrada) llega en S5. Hasta entonces cumplen solo en parte.
- **Motivo:** el formato de registros de la aplicación se define en S5.
- **Impacto:** los eventos anteriores a S5 no tendrán todos los campos del formato final.
- **Autorización:** equipo de desarrollo.
- **Relacionado:** RNF-22; ADR-010.

### DA-08 — Barrera 3 de la bitácora no implementada
- **Fecha:** 2026-09-28 (ADR-010, «Decisión», punto 8).
- **Alcance original:** ADR-010 §1, barrera 3 (opcional): rol de base de datos con solo INSERT y SELECT sobre la bitácora.
- **Cambio:** no se implementa en S1. Riesgo aceptado: el rol `altiro_app`, dueño de las tablas, podría desactivar los triggers. Se evalúa en S5 si sobra capacidad.
- **Motivo:** RNF-11 se cumple con la barrera 1 ("el sistema no ofrece ninguna forma…"). La barrera 3 exige separar roles de BD y cambiar la infraestructura (CP-10).
- **Impacto:** los triggers siguen como defensa en profundidad, no como garantía absoluta.
- **Autorización:** equipo de desarrollo.
- **Relacionado:** RNF-11, R-10; ADR-010.

### DA-09 — Reautenticación de RNF-09 sin cerrar
- **Fecha:** 2026-09-27 (propuesta del S1, §2.1, y ADR-013, punto 7).
- **Alcance original:** RNF-09 en S1. Umbral: "Expiración a los 30 minutos; Reautenticación al cambiar contraseña o correo".
- **Cambio:** la expiración se cumple en S1. La segunda mitad no tiene evidencia, porque ninguna HU ni RF pide cambiar la contraseña o el correo y esas funciones están fuera del alcance actual (ADR-013, punto 7). Queda sujeta a la pregunta de alcance de la propuesta §2.1 (opciones A a D).
- **Motivo:** un RNF establece una condición sobre una función; no crea la función.
- **Impacto:** RNF-09 no puede declararse cumplido del todo. Si se elige la opción A, B o C, será una ampliación de alcance y seguirá este mismo procedimiento.
- **Autorización:** equipo de desarrollo; falta la decisión de alcance del representante del producto.
- **Relacionado:** RNF-09, HQ-04; ADR-005, ADR-013.

### DA-10 — La bitácora se usa desde S2
- **Fecha:** 2026-09-27 (propuesta del S1, §1.5, punto 2).
- **Alcance original:** RF-37 (bitácora administrativa) está planificado para S5.
- **Cambio:** la bitácora se construye en S1 y se usa desde S2, porque CA-19.3 (S2) exige mostrar autor, fecha, estado anterior, nuevo y motivo. RF-37 se completa en S5.
- **Motivo:** dependencia de CA-19.3.
- **Impacto:** adelanta infraestructura; no saca nada del alcance.
- **Autorización:** equipo de desarrollo.
- **Relacionado:** RF-37, RNF-11, CA-19.3, NTI-12; ADR-010.

### DA-11 — RNF-23 sin medir en un equipo limpio
- **Fecha:** fecha de formalización documental 2026-09-28 (`docs/testing/cierre-sprint-1.md`, §7).
- **Alcance original:** RNF-23 en S1. Umbral: "Un solo comando deja el sistema andando en 10 minutos o menos, con las instrucciones escritas junto al código".
- **Cambio:** el comando único y las instrucciones existen. Falta cronometrar en un equipo sin imágenes ni volúmenes, idealmente del laboratorio; el procedimiento está en `cierre-sprint-1.md` §7.
- **Motivo:** el equipo de desarrollo tiene imágenes en caché, así que la medición ahí no es válida.
- **Impacto:** RNF-23 queda BLOCKED hasta la medición.
- **Estado (2026-09-28): cerrado con evidencia del equipo de desarrollo.** 47 s en un motor Docker sin caché (`docs/testing/rnf-23-medicion.md`). Queda recomendado confirmarlo en un equipo del laboratorio.
- **Autorización:** equipo de desarrollo.
- **Relacionado:** RNF-23.

## Sprint 2

Origen: `docs/decisions/sprint-2-propuesta-arquitectura.md`, §8, y las decisiones aprobadas por el equipo el 2026-09-28 (ADR-016 y ADR-017). Alcance comprometido del Sprint 2 (informe §5.3.5): "Expediente del maestro y curatoría, con RF-04, RF-08 y RF-32 a RF-35, más RNF-25, RNF-13 a RNF-17 y RNF-20".

### DA-12 — RF-34, CA-24.1 y la parte de servicios de CA-24.3 pasan a S3
- **Fecha:** 2026-09-28 (aprobación de la propuesta del S2 y de ADR-017).
- **Alcance original:** RF-34 en S2: "desactivar automáticamente los servicios de oficios regulados cuando la licencia asociada deja de estar vigente".
- **Cambio:** en S2 se entrega la regla única de vigencia y habilitación del oficio (`oficio_habilitado`) y la tarea programada. La desactivación de servicios se completa en S3, cuando existan los servicios (RF-05, HU-12).
- **Motivo:** los servicios del maestro no existen hasta S3.
- **Impacto:** RF-34, CA-24.1 y CA-24.3 (en la parte de servicios) no se cierran en S2.
- **Autorización:** equipo de desarrollo.
- **Estado (2026-09-29): cerrado en S3 (incrementos 2 y 5).** Los servicios del maestro existen (RF-05) y su visibilidad se calcula en cada lectura con la regla única `perfil.publicacion` (ADR-019, punto 2), sin marca guardada ni tarea: una licencia deja de habilitar el día de su vencimiento (hora de Santiago) y la reactivación ocurre sola al validar una nueva. Evidencia: pruebas de CA-24.1 (borde de la medianoche UTC), CA-24.3 (licencia sin vencimiento nunca desactiva) y RF-34 (gas oculto y pintura visible en el mismo maestro), y en vivo sobre el perfil público: maestro ficticio con gas y pintura; al dejar su licencia de gas vencida, gas desaparece del perfil público en la siguiente lectura y pintura sigue; al restaurar la vigencia, gas vuelve. La parte de búsqueda sigue en DA-13 (S4).
- **Relacionado:** RF-34, RF-05, HU-12, HU-24, CA-24.1, CA-24.3; ADR-017.

### DA-13 — CA-24.4 pasa a S4
- **Fecha:** 2026-09-28.
- **Alcance original:** CA-24.4, trazado a HU-24 del S2.
- **Cambio:** se demuestra en S4, con la búsqueda (RF-09 a RF-11).
- **Motivo:** la búsqueda no existe hasta S4.
- **Impacto:** HU-24 no se cierra completa en S2.
- **Autorización:** equipo de desarrollo.
- **Relacionado:** CA-24.4, HU-24, RF-09.

### DA-14 — La evidencia de RNF-25 pasa a S3 y S4
- **Fecha:** 2026-09-28.
- **Alcance original:** RNF-25 en S2: "Ningún servicio de gas o electricidad queda visible sin licencia vigente asociada".
- **Cambio:** en S2 se entregan RF-33 y la regla de habilitación, con pruebas unitarias. La evidencia del umbral (servicio visible o no) se cierra en S3 (servicios) y en S4 (búsqueda).
- **Motivo:** sin servicios ni búsqueda no hay nada "visible" que verificar.
- **Impacto:** RNF-25 queda como "infraestructura preparada / evidencia final pendiente". Es un desplazamiento temporal, no un recorte.
- **Autorización:** equipo de desarrollo.
- **Estado (2026-09-29): parte S3 cerrada.** Evidencia en las rutas públicas que existen en S3 (`/api/catalogo`, `/api/oficios`, perfil público y su foto): la prueba `test_rnf25_ningun_servicio_regulado_visible_sin_licencia_habilitante` recorre **todas** las rutas públicas declaradas (se obtienen del enrutador, así que una ruta pública nueva entra sola) con 20 combinaciones generadas (gas y electricidad × 10 escenarios de licencia: sin licencia, en revisión, observada, vencida ayer, vence hoy, de otro oficio, validada vigente, sin vencimiento y las dos variantes de renovación de ADR-017 E-1), con y sin sesión; el servicio regulado aparece solo cuando hay licencia habilitante. Más la evidencia en vivo descrita en DA-12. La parte de búsqueda queda para S4.
- **Relacionado:** RNF-25, RF-33, NTI-01; ADR-017.

### DA-15 — Adelanto: catálogo mínimo de oficios de S3 a S2
- **Fecha:** 2026-09-28 (ADR-017, punto 1).
- **Alcance original:** el catálogo de oficios corresponde al S3 (RF-36, administrable por el área comercial).
- **Cambio:** en S2 se carga una tabla `oficio` de solo lectura desde un CSV (código, nombre, regulado), sin administración. RF-36 sigue en S3.
- **Motivo:** RF-33 (S2) necesita saber qué oficios son regulados.
- **Impacto:** adelanta datos, no funcionalidad. Los seis oficios no regulados son un supuesto a validar.
- **Autorización:** equipo de desarrollo; los nombres de los oficios están pendientes del representante del producto.
- **Estado (2026-09-29): cerrado.** RF-36 se implementó en S3, incremento 1 (catálogo administrable por comercial, ADR-018, commit `98cadce`): el CSV quedó solo como carga inicial. Desde el incremento 3, un oficio dado de baja por comercial no se puede declarar en una declaración nueva y las declaraciones que ya existían se conservan (propuesta del S3, §8.4).
- **Relacionado:** RF-33, RF-36, RNF-25; ADR-017.

### DA-16 — Adelanto: planificador de S4 a S2
- **Fecha:** 2026-09-28 (ADR-016).
- **Alcance original:** el planificador estaba previsto para S4 (DA-06).
- **Cambio:** el servicio `planificador` llega en S2 para la "revisión diaria" de RF-35 y CA-24.2. También ejecuta la purga de `acceso_denegado`, lo que **cierra DA-06** cuando se implemente.
- **Motivo:** RF-35 está comprometido en S2.
- **Impacto:** un contenedor más; se vuelven a verificar RNF-04 y RNF-23.
- **Estado (2026-09-28): implementado en S2, incremento 5.** Servicio `planificador` (misma imagen `altiro-app:local`, sin puertos publicados, solo red `interna`, secretos de solo lectura, volumen `documentos`, espera a `app` sano, sin volver a migrar, healthcheck por archivo de latido) con `manage.py planificador` (intervalo `ALTIRO_PLANIFICADOR_INTERVALO_SEGUNDOS`, 3600 por defecto; `--una-vez`; SIGTERM limpio). Tareas: avisos de RF-35 (tabla `aviso`), purga de `acceso_denegado` (cierra DA-06) y archivos huérfanos (ADR-015). Evidencia en vivo: servicio `healthy`; `docker port` vacío; corrida manual con `avisos_creados=2` (maestro y curatoría) para un documento ficticio que vence en 20 días, segunda corrida con `avisos_creados=0`; avisos visibles en `GET /api/maestros/expediente` y `GET /api/curatoria/avisos`; parada con `docker compose stop` con código 0 y "Planificador detenido"; registros sin datos personales. **RNF-04:** `docker stats` con la pila completa: planificador 47,2 MiB, app 103,9 MiB, db 71,6 MiB, proxy 23,8 MiB (≈ 247 MiB en total, bajo 2 GB). RNF-23 no se volvió a medir en equipo limpio en este incremento.
- **Autorización:** equipo de desarrollo.
- **Relacionado:** RF-35, CA-24.2, M-08; ADR-016, DA-06.

### DA-17 — La ejecución de la prueba de usabilidad de RNF-13 pasa al inicio del S3
- **Fecha:** 2026-09-28 (cierre de UX del S2, incremento 6).
- **Alcance original:** RNF-13 en S2. Umbral: "Al menos 2 de 3 participantes de prueba la completan en ≤ 10 minutos".
- **Cambio:** en S2 se entrega el flujo completo del maestro y el protocolo listo para ejecutar (`docs/testing/rnf-13-protocolo.md`). La sesión con tres participantes externos, en un teléfono real, pasa a la **primera semana del S3**.
- **Motivo:** la prueba exige personas externas, un teléfono real y la preparación del certificado (ADR-008). El trabajo automatizado del sprint no puede producirla.
- **Impacto:** RNF-13 queda sin evidencia al cierre del S2. El informe lo señala como el requisito que más discute la viabilidad. No se declara cumplido sin la prueba.
- **Autorización:** equipo de desarrollo, informando al representante del producto.
- **Relacionado:** RNF-13, NTI-11, HU-11; ADR-008, ADR-013 E-8.

## Sprint 3

Origen: `docs/decisions/sprint-3-propuesta-arquitectura.md`, §7, y las decisiones provisionales del 2026-09-29 (ADR-018 a ADR-021). Alcance comprometido del Sprint 3 (informe §5.3.5): "Catálogo, cobertura y agenda, con RF-05 a RF-07, RF-36 y RNF-18"; incremento esperado: "Perfil de maestro completo y publicable".

### DA-18 — Adelanto: perfil público parcial (RF-14) de S4 a S3
- **Fecha:** 2026-09-29 (propuesta del S3, D-12; ADR-019, punto 5).
- **Alcance original:** RF-14 ("ficha del maestro con calificación por dimensión, comentarios, precios, bloques libres y bloques ocupados") está en S4, con la búsqueda.
- **Cambio:** en S3 se entrega `GET /api/maestros/publicos/<uuid:ref>` con nombre, foto, servicios visibles (oficio, servicio, modalidad y monto), comunas atendidas sin indicar la base (D-14) y agenda semanal en "HH:MM". Sin calificaciones (S5) ni bloques ocupados (S4). Un maestro no publicado responde el mismo 404 que una ref inexistente, sin registro.
- **Motivo:** el incremento del S3 es "perfil de maestro completo y publicable", y RF-06 ("no aparece en resultados") y RNF-25 necesitan una superficie pública donde verificarse antes de la búsqueda.
- **Impacto:** adelanta una parte de RF-14; RF-14 no se declara cumplido hasta S4 y S5. La ruta es pública y entra en la lista cerrada de `test_api_privado_por_defecto.py`.
- **Autorización:** equipo de desarrollo (decisión provisional).
- **Relacionado:** RF-14, RF-06, RNF-25, HU-05; ADR-019.

### DA-19 — Adelanto: foto del maestro (dato de RF-13) de S4 a S3
- **Fecha:** 2026-09-29 (propuesta del S3, D-13; ADR-021).
- **Alcance original:** RF-13 (tarjeta de resultado con "fotografía, nombre, calificación promedio y oficio") está en S4.
- **Cambio:** en S3 se captura la foto (`POST /api/maestros/perfil/foto`), recodificada sin EXIF ni GPS en variantes de 160 y 480 px, en el volumen `fotos` montado solo en `app`, y es requisito para que el maestro sea elegible. Se entrega solo si el maestro está publicado.
- **Motivo:** RF-13 exige la foto en cada tarjeta y S4 ya es el sprint más cargado.
- **Impacto:** un volumen más (respaldo en RNF-19); la tarjeta de RF-13 sigue en S4. Riesgo abierto: no hay moderación de fotos definida (pregunta al representante, ADR-021, punto 5); que la foto sea obligatoria es P-14.
- **Autorización:** equipo de desarrollo (decisión provisional).
- **Relacionado:** RF-13, RNF-02, RNF-24; ADR-021, ADR-015.

### DA-20 — La evidencia de RF-06 en "resultados", CA-13.2 y CA-14.3 pasan a S4
- **Fecha:** 2026-09-29 (propuesta del S3, §1.2).
- **Alcance original:** RF-06 (criterio: "Un maestro sin comuna base no aparece en resultados") y HU-13, HU-14 están en S3.
- **Cambio:** en S3 se entregan la declaración de cobertura con exactamente una comuna base (CA-13.1) y la agenda (CA-14.1, CA-14.2, CA-14.4). "No aparece" se verifica en S3 sobre el perfil público (sin comuna base responde 404). La verificación en los resultados de búsqueda, CA-13.2 ("dejo de aparecer en sus resultados" al quitar una comuna) y CA-14.3 (bloque ocupado tras aceptar una oferta) se cierran en S4.
- **Motivo:** la búsqueda (RF-09 a RF-11) y los tickets (RF-15 a RF-24) son de S4.
- **Impacto:** RF-06, HU-13 y HU-14 no se cierran completos en S3. La base ya está: la cobertura se reemplaza completa y la comuna quitada deja de estar registrada.
- **Autorización:** equipo de desarrollo (decisión provisional).
- **Relacionado:** RF-06, RF-07, HU-13, HU-14, CA-13.2, CA-14.3; ADR-019, ADR-020.

### DA-21 — RNF-18 se aplica retroactivamente a las pantallas de S1 y S2
- **Fecha:** 2026-09-29 (propuesta del S3, §1.3 y D-15).
- **Alcance original:** RNF-18 está planificado en S3.
- **Cambio:** se verifica en todas las pantallas del sistema, incluidas las de S1 y S2, y no solo en las nuevas ("celular angosto" = 320 px CSS; Chromium y Firefox en dos versiones más un pase manual).
- **Motivo:** el umbral ("sin que haya que desplazar la pantalla de lado en celulares angostos") se refiere al sistema, y las pantallas anteriores no se verificaron con ese criterio.
- **Impacto:** más trabajo de verificación en S3; si una pantalla de S1 o S2 no cumple, su corrección entra al S3.
- **Autorización:** equipo de desarrollo (decisión provisional).
- **Relacionado:** RNF-18, NTI-11.
