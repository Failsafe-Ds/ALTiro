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
| DA-01 | Evidencia de RNF-06 | S2 | Temporal |
| DA-02 | Evidencia de RNF-08 | S4 | Temporal |
| DA-03 | RNF-07 se cumple de forma acumulativa | S2 a S5 | Temporal |
| DA-04 | CA-25.3 en "Terminado sin validar" | Revisión del S1 | Temporal |
| DA-05 | CA-25.1 y CA-25.2 | S4 y S2 | Temporal |
| DA-06 | Purga automática de `acceso_denegado` | S4 | Temporal |
| DA-07 | RNF-22 parcial | S5 | Temporal |
| DA-08 | Barrera 3 de la bitácora no implementada | Evaluar en S5 | Temporal, condicionado a capacidad |
| DA-09 | Reautenticación de RNF-09 | Según decisión de alcance | Pendiente de decisión |
| DA-10 | Uso de la bitácora desde S2 | S2 | Adelanto (definitivo) |
| DA-11 | RNF-23 sin medir en equipo limpio | Antes de la revisión del S1 | Temporal |

## Registros

### DA-01 — Evidencia de RNF-06 pasa a S2
- **Fecha:** 2026-09-27 (propuesta del S1, §1.2 y §1.5, punto 1).
- **Alcance original:** RNF-06 en S1 (§5.3.5). Umbral: "Guardados fuera de las carpetas accesibles desde internet y entregados con un enlace que caduca a los 10 minutos".
- **Cambio:** en S1 se entrega solo la utilidad de enlace firmado (`autorizacion/enlaces.py`, 600 s) con sus pruebas. El volumen de documentos, la descarga y la evidencia del umbral se cierran en S2.
- **Motivo:** los documentos que protege RNF-06 (cédula, antecedentes, licencias) existen desde S2 (RF-04).
- **Impacto:** RNF-06 queda "infraestructura preparada / evidencia final pendiente" al cierre del S1. Sin riesgo de exposición: en S1 no hay documentos.
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
- **Autorización:** equipo de desarrollo.
- **Relacionado:** HU-25, CA-25.1, CA-25.2, NTI-09; ADR-011.

### DA-06 — Purga automática de `acceso_denegado` pasa a S4
- **Fecha:** 2026-09-28 (ADR-010, «Decisión», punto 3).
- **Alcance original:** M-08 (§6.2), "retención acotada del registro".
- **Cambio:** en S1 la purga de filas con más de 90 días ocurre al registrar una nueva denegación y con el comando `purgar_accesos_denegados`. La ejecución periódica llegará con el planificador de S4.
- **Motivo:** S1 no tiene planificador de tareas.
- **Impacto:** si no hay denegaciones ni se ejecuta el comando, las filas vencidas pueden quedar más de 90 días. Riesgo bajo en la prueba de concepto.
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
- **Autorización:** equipo de desarrollo.
- **Relacionado:** RNF-23.
