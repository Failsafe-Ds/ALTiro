# ADR-016 — Planificador de tareas y avisos dentro de la aplicación

- Estado: **Aceptada** — 2026-09-28, aprobada por el equipo de desarrollo.
- Fecha: 2026-09-28
- Relacionado con: RF-35, CA-24.2, CA-24.3, RF-08, CA-17.1, M-08, RNF-04, RNF-23, DA-06
- Origen: propuesta del S2, decisiones D-6 y D-7.

## Contexto
- RF-35 exige avisar "30 días antes del vencimiento"; CA-24.2 habla de una "revisión diaria".
- El planificador estaba previsto para S4 (DA-06).
- No hay servicio de correo (ADR-013, punto 10), varios maestros no tienen correo (§3.4) y el SMS es un servicio pagado.

## Decisión
1. **Planificador:**
   - Servicio `planificador` en `docker-compose.yml`, con la misma imagen `altiro-app:local`, sin puertos, en la red `interna`.
   - Ejecuta `manage.py planificador`: un bucle que cada hora corre tareas **idempotentes**. Cada tarea recibe `ahora` como parámetro, para poder probarla con time-machine (ADR-014).
   - Tareas:
     - avisos de RF-35;
     - purga de `acceso_denegado` (ADR-010; cierra DA-06);
     - limpieza de archivos huérfanos (ADR-015).
2. **Avisos:**
   - Se guardan en la tabla `aviso` y se muestran en "Mis documentos" y en el panel de curatoría.
   - Un UNIQUE garantiza que cada aviso se emita una sola vez, como pide RF-35: "el aviso se emite una vez alcanzado el umbral".
   - La tabla no guarda datos personales: el texto se arma al mostrarlo.
3. **Fechas de negocio:**
   - `TIME_ZONE` sigue en UTC. "Hoy" se calcula en `America/Santiago` con una sola función.
   - Un documento está vigente si no tiene vencimiento o si `hoy < fecha_vencimiento`.
   - Un documento sin vencimiento nunca genera aviso (RF-04, CA-24.3).

## Consecuencias
- Hay un contenedor más: se vuelve a medir RNF-04 y RNF-23.
- El planificador se adelanta de S4 a S2. Queda registrado en la bitácora de alcance.

## Enmiendas

### E-1 — Intervalo del planificador de 300 s y tarea de cierre de tickets (PROVISIONAL)
- **Fecha:** 2026-09-29. Opción recomendada, aplicada como provisional (`docs/Reanudar.md`).
- **Cambio:**
  - El valor por defecto de `ALTIRO_PLANIFICADOR_INTERVALO_SEGUNDOS` pasa de 3600 a **300**. Así los avisos de cierre (RF-21, RF-22, RF-24) llegan en 5 minutos o menos.
  - Se agrega la tarea idempotente de cierre de tickets vencidos, con `skip_locked` (ADR-023).
  - Hay además una protección al actuar: una acción sobre un ticket ya vencido lo cierra en ese momento.
  - Tras el cambio se vuelve a medir RNF-04.
- **Aprobación:** equipo de desarrollo (provisional), 2026-09-29.
