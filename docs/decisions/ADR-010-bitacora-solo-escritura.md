# ADR-010 — Bitácora administrativa y registro de accesos denegados

- Estado: **Aceptada** — 2026-09-28, aprobada por el equipo de desarrollo (ver «Decisión»).
- Fecha: 2026-09-27
- Relacionado con: RNF-11, CA-25.3, HU-19, CA-19.3, NTI-12, RF-37, RNF-22, R-10, M-03, M-08

## Contexto
- RNF-11: "El sistema no ofrece ninguna forma de editar ni borrar una entrada de la bitácora".
- Regla de HU-19 (§3.3.8): "Los registros de la bitácora no se editan ni se eliminan".
- CA-19.3 (S2) exige que la bitácora muestre autor, fecha, estado anterior, nuevo y motivo.
- CA-25.3: "Dado un intento de acceso denegado… queda en la bitácora con usuario, recurso y fecha".
- M-03 (§6.2): "La bitácora registra acciones sobre expedientes, no actividad general de la persona".
- M-08 (§6.2): "Retención acotada del registro y prohibición de usarlo para decisiones automáticas sobre una persona".

Hay tensión entre la inmutabilidad (RNF-11, HU-19), la retención acotada (M-08) y el alcance limitado de la bitácora (M-03).

## Decisión propuesta

### 1. Bitácora administrativa (`bitacora`)
- Campos: `fecha`, `autor_tipo` (`usuario`/`sistema`), `autor_id`, `accion`, `entidad`, `entidad_ref`, `valor_anterior`, `valor_nuevo`, `motivo`. Cubren lo que exigen CA-19.3 (S2) y RF-37 (S5).
- Barreras:
  1. Modelo sin operaciones de actualización ni borrado; sin rutas PUT/PATCH/DELETE; panel de administración de Django no instalado (ADR-001). **Esta barrera es la que cumple RNF-11** ("el sistema no ofrece…").
  2. Trigger de PostgreSQL `BEFORE UPDATE OR DELETE` y `BEFORE TRUNCATE` que lanza error. Es defensa en profundidad: el dueño de la tabla puede desactivarlo (`ALTER TABLE … DISABLE TRIGGER`).
  3. (Opcional) Rol de base de datos de la aplicación con solo INSERT y SELECT sobre la tabla.
- Sin purga.
- `autor_id` sin `ON DELETE CASCADE` (el trigger bloquearía el borrado del usuario): usar PROTECT o no declarar FK.
- No guardar hashes ni datos innecesarios en `valor_anterior`/`valor_nuevo`.
- `autor_tipo='sistema'` se reserva para el actor Sistema de §3.1 (tareas programadas). Una acción ejecutada por una persona nunca se registra como `sistema`.
- La asignación de roles administrativos (`curatoria`, `comercial`, `moderacion`, `control_gestion`) **no se registra en esta bitácora**: RF-37 exige registrar "toda acción administrativa sobre expedientes, evaluaciones y catálogo" y M-03 excluye la "actividad general de la persona"; asignar un rol no es ninguna de ellas. Toda asignación, la del primer administrador y las posteriores, se hace solo con el comando de consola `crear_usuario_administrativo`; no hay endpoint de asignación porque ninguna HU ni RF lo pide. La ejecuta una persona con acceso al equipo y al contenedor, no el actor Sistema (§3.1), por lo que nunca se registra con `autor_tipo='sistema'`; como el comando no tiene sesión, la aplicación no puede identificar a esa persona y no se inventa un autor. Queda solo la fecha en `usuario_rol.asignado_en` (ver Pendiente).

### 2. Registro de accesos denegados (`acceso_denegado`), separado
- Campos: `fecha`, `usuario_id` (sin borrado en cascada), `recurso`, `entidad`, `entidad_ref`.
- Solo registra denegaciones de **usuarios autenticados** cuando el recurso existe y la política lo deniega (CA-25.3 exige "usuario"). No registra 401 anónimos.
- Solo inserción desde la aplicación; sin rutas de edición ni borrado.
- Trigger que rechaza UPDATE y solo permite DELETE de filas con `fecha` anterior al plazo de retención.
- La purga la ejecuta el actor Sistema (planificador de S4); cada purga deja un evento técnico de aplicación (RNF-22) con la fecha y el conteo de filas eliminadas, sin datos personales. No se registra en la bitácora administrativa: la purga no es una acción sobre expedientes, evaluaciones ni catálogo (RF-37, M-03).
- Ningún proceso automático, incluido el limitador de intentos, lee esta tabla para decidir sobre una persona (M-08).

## Alternativas consideradas
| Opción | Evaluación |
|---|---|
| Misma tabla, sin purga | Incumple M-08 y M-03. |
| Misma tabla, purga por procedimiento de base de datos | Obliga a desactivar el trigger; contradice la regla de HU-19 y debilita la evidencia de inmutabilidad. |
| **Tabla separada con purga acotada** (propuesta) | La bitácora administrativa queda realmente inmutable. |
| Seudonimizar tras el plazo | Requiere UPDATE; más compleja y también choca con RNF-11. |

## Pendiente
- Validar con el representante del producto que "queda en la bitácora" de CA-25.3 se cumple con el registro de seguridad separado `acceso_denegado`.
- Plazo de retención de `acceso_denegado`: no está en el informe; decisión del equipo a validar. No se vincula con V-04, que trata de documentos de identidad.
- Registro de la asignación de roles administrativos: no lo exige RF-37; pregunta abierta para el equipo. Si se decide registrarla, sería un registro de seguridad separado de la bitácora administrativa (como `acceso_denegado`), no la bitácora de RF-37, y nunca con autor `sistema`. Autor según el caso: (1) primer administrador: no existe cuenta administrativa previa, así que el autor solo puede ser un dato declarado por quien ejecuta el comando (por ejemplo, un argumento obligatorio); (2) asignaciones posteriores: el comando podría exigir además la referencia a un usuario administrativo existente como autor declarado. En ambos casos el dato no es verificable por la aplicación porque el comando no tiene sesión; el control efectivo es el acceso al equipo y al contenedor. Asignar roles desde la aplicación no tiene respaldo en HU ni RF; sería ampliación de alcance según §5.3.6. Mientras no se decida, no se registra.

## Decisión (2026-09-28)
Aprobada por el equipo de desarrollo a partir del análisis del agente `architect`. Donde este apartado precisa el texto anterior, prevalece.

1. **CA-25.3:** se cumple con la tabla separada `acceso_denegado` (usuario, recurso y fecha). "Bitácora" se entiende en sentido amplio. **Pendiente de validación con el representante del producto**: hasta entonces, CA-25.3 queda "Terminado sin validar" (§5.3).
2. **Retención de `acceso_denegado`: 90 días.** Es una política, no un ajuste del servidor: va como constante en el código y como literal en el trigger, y una prueba verifica que coincidan.
3. **Purga en S1:** una única función `purgar_vencidos()`. Se llama al insertar una denegación y desde el comando `purgar_accesos_denegados`; en S4 la llamará el planificador. La condición usa `now()` de SQL, igual que el trigger. Se registra como "purga automática por retención", sin atribuirla al usuario de la petición. Cada purga que elimina filas deja un evento de aplicación con el conteo y sin datos personales (RNF-22, en parte hasta S5).
4. **Sin FK hacia `usuario`** en `bitacora.autor_id` ni en `acceso_denegado.usuario_id`. Esto corrige "usar PROTECT o no declarar FK". Ambas tablas se crean con SQL explícito y modelos `managed=False`, porque con una FK o un trigger `BEFORE TRUNCATE` las pruebas `transaction=True` no pueden vaciar la base.
5. **`acceso_denegado` también rechaza `TRUNCATE`.** El DELETE solo se permite para filas con más de 90 días.
6. **Lectura de `acceso_denegado`:** no hay ruta ni pantalla (ninguna HU la pide). El equipo la revisa con psql.
7. **Asignación de roles administrativos:** se agrega `usuario_rol.asignado_en` (fecha, con valor por defecto) y el comando `crear_usuario_administrativo` emite un evento de aplicación con usuario y rol, nunca con autor `sistema`. No va a la bitácora administrativa (RF-37, M-03). Esto revierte la decisión previa de no agregar `asignado_en`, que se citaba como rastro pero no existía.
8. **Barrera 3 (rol de BD con solo INSERT y SELECT): no en S1. Riesgo aceptado:** `altiro_app` es dueño de las tablas y podría desactivar los triggers. RNF-11 se cumple con la barrera 1; el trigger es defensa en profundidad. Se puede evaluar en S5 si sobra capacidad.
