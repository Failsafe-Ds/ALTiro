# Material de defensa — prueba de concepto AlTiro

Preparado por Claude a pedido del equipo (2026-09-30), para la fila S5 de §5.3.5 ("Sistema completo y material de defensa preparado"). Es un borrador: el equipo lo ajusta, reparte y ensaya.

Fuentes: informe (§3.2, §3.3, §4.2, §5.3.5, §6), `docs/estado-actual.md`, `docs/testing/cierre-sprint-1.md` a `cierre-sprint-5.md`, mediciones `docs/testing/rnf-*.md`, `docs/alcance/bitacora-de-alcance.md`.

---

## 1. Mensaje central (1 minuto)

- **Problema:** hoy los expedientes, los contactos y los acuerdos de precio viven en carpetas personales, en una planilla de 31 columnas y en chats de WhatsApp. No hay una vista única, confiable ni trazable.
- **Solución construida:** una plataforma web, pensada primero para el teléfono, que cubre todo el recorrido. El maestro postula y curatoría lo verifica. El cliente busca y pide un horario. El maestro acepta, conversan y acuerdan el precio. Ambos se evalúan. Moderación, control de gestión y la bitácora dan el control administrativo.
- **Cómo se trabajó:** Scrum adaptado, cinco sprints con los objetivos de §5.3.5. Cada sprint cerró con QA, mediciones RNF y un informe de cierre en `docs/testing/`.
- **Qué la hace defendible:**
  - 26 ADR que registran las decisiones técnicas;
  - una bitácora de alcance (DA-xx) con cada desplazamiento;
  - una suite automática de 1.888 pruebas;
  - las 83 reglas críticas catalogadas de RNF-21, todas cubiertas.

## 2. Preparación antes de la defensa (checklist)

Hacerlo el día anterior y repetirlo una hora antes.

1. `docker compose up -d --build` y comprobar `https://localhost/` (advertencia de certificado autofirmado esperada, RNF-12).
2. `docker compose exec app python manage.py cargar_datos_demo` (servicios "(demo)").
3. Cuentas administrativas, con `crear_usuario_administrativo` (README):
   - curatoría;
   - comercial;
   - moderación;
   - control de gestión.
   Correos `@example.com` y contraseñas que solo conozca el equipo, sin datos reales.
4. Dejar preparado por la interfaz, con datos ficticios:
   - **dos maestros**, ambos aprobados por curatoría, con:
     - comuna base;
     - foto;
     - un servicio;
     - disponibilidad.
     Uno queda "por trabajo" y el otro "por hora".
   - **dos clientes**.
5. Tener un pedido ya **aceptado** y otro **finalizado y evaluado**. Así la demo no depende de esperar plazos (un pedido no se puede crear a 4 h o menos del horario, y el precio final se registra recién desde el inicio del horario, P-27).
6. Ventanas listas:
   - una del navegador en modo teléfono, a 360 px, con la red limitada de DevTools (4 Mbps, RNF-02);
   - una normal para los roles administrativos;
   - la pestaña Red de DevTools abierta para la prueba de privacidad.
7. Plan B: capturas o un video corto de cada paso del guion, por si falla la red o el equipo.

## 3. Guion de la demostración (≈ 15 minutos)

Cada paso nombra lo que se muestra y el requerimiento que prueba.

| # | Rol | Qué se hace | Qué se señala | Trazabilidad |
|---|---|---|---|---|
| 1 | Visitante (teléfono) | `buscar.html`: oficio + comuna + horario | Ningún resultado incumple un filtro; las sugerencias van aparte y dicen qué condición no cumplen; la calificación aparece en la tarjeta | RF-09 a RF-11, RF-13, CA-03.x, RNF-01, RNF-02 |
| 2 | Visitante | Ficha del maestro | Dimensiones de la calificación y comentarios sin autor; los servicios regulados solo aparecen con licencia vigente | RF-14, RF-30, RNF-25 |
| 3 | Cliente | `pedir-trabajo.html`: servicio, descripción, dirección, horario y materiales | El pedido copia la modalidad y el monto publicados; un horario a ≤ 4 h se rechaza con un mensaje accionable | HU de ticket, RF del ticket (§4.2.1), ADR-023 |
| 4 | Maestro (teléfono) | `mis-trabajos.html`, pedido pendiente | **Pestaña Red:** la respuesta del servidor no trae dirección, teléfono ni nombre del cliente, solo la comuna | **RNF-08**, CLAUDE.md §7 |
| 5 | Maestro | Aceptar | El estado pasa a «Aceptado», el horario queda ocupado y los pedidos incompatibles se cierran con motivo; ahora sí llegan los datos de contacto | ADR-023, CA-23.x |
| 6 | Cliente y maestro | `conversacion.html` | Mensajes asociados al pedido; un pedido cerrado dice "No hubo conversación" | RF-25, CA-07.x, CA-15.2 |
| 7 | Maestro → Cliente | El maestro registra un precio final distinto del publicado → el cliente lo acepta | No finaliza sin la aceptación obligatoria; quedan la fecha y el autor; la orden finalizada no cambia de precio | RF-26 a RF-28, CA-16.x, NTI-04 |
| 8 | Ambos | `evaluar.html` | Una evaluación por parte; solo sobre una orden finalizada; un segundo intento da "Ya evaluaste este trabajo" | RF-29, RF-30, CA-09.x |
| 9 | Moderación | El maestro denuncia la evaluación → moderación la revisa y abre la conversación → la resuelve | Solo ve la conversación con la denuncia abierta; avisa a ambas partes; la resolución queda en la bitácora | RF-31, RF-37, CA-21.x |
| 10 | Curatoría | Expediente: ver un documento, observar, aprobar | Las fotos se abren con un enlace que caduca a los 10 minutos; el motivo es obligatorio; queda en la bitácora | RF-08, RF-32, RF-33, RNF-06, RNF-11 |
| 11 | Control de gestión | `indicadores.html` y exportación CSV | Tres indicadores con su definición; el CSV no trae identificadores y suprime los grupos de menos de 5 | RF-38, CA-22.x |
| 12 | Seguridad (en vivo) | Cambiar la `ref` de un pedido en la URL por la de otro cliente | Responde el mismo 404 que un pedido inexistente y queda registrado en `acceso_denegado` | **RNF-07**, ADR-011 |
| 13 | Seguridad (opcional) | 6 contraseñas erróneas | "Espera 15 minutos…" (429) | RNF-10 |

Si falta tiempo, se acortan los pasos 9 a 11, nunca el 4 ni el 12, que son el núcleo de seguridad.

## 4. Evidencia por RNF (resumen para la lámina)

Valores tomados de los informes de cierre y las mediciones. Todo se midió en el equipo local de desarrollo, que es el entorno que define la prueba de concepto.

| RNF | Umbral del informe | Resultado | Estado | Evidencia |
|---|---|---|---|---|
| RNF-01 | 19 de 20 búsquedas en ≤ 2 s con el volumen de prueba | 100 % en ≤ 2 s; p95 ≈ 0,22 s (400 búsquedas, 10 hilos) | Cumple | `rnf-01-medicion.md` |
| RNF-02 | ≤ 3 s y ≤ 1,5 MB a 4 Mbps | búsqueda 0,57 s y 35,8 KiB; ficha 0,54 s | Cumple | `rnf-02-medicion.md` |
| RNF-03 | 100 maestros, 1.000 tickets, 5.000 mensajes | generado y medido sin degradar RNF-01 | Cumple | `rnf-03-volumen.md` |
| RNF-04 | ≤ 2 GB para toda la pila | suma de picos ≈ 235 MiB | Cumple | `cierre-sprint-4.md` |
| RNF-05 | hash adaptativo | Argon2id; 0 contraseñas en claro | Cumple | `cierre-sprint-1.md` |
| RNF-06 | fuera de rutas públicas; enlace de 10 min | AES-256-GCM; enlace válido a los 600 s y rechazado a los 601 s | Cumple | `cierre-sprint-2.md` |
| RNF-07 | prueba de terceros por cada ruta con identificador | prueba de control de rutas sin exenciones; 404 idéntico | Cumple | suite; `cierre-sprint-5.md` §2 |
| RNF-08 | dirección y teléfono no viajan mientras está pendiente | verificado en la respuesta del servidor | Cumple | `cierre-sprint-4.md`, `cierre-sprint-5.md` |
| RNF-09 | expiración a 30 min; reautenticación al cambiar contraseña o correo | expiración: cumple. Reautenticación: no existe la función de cambio | **Parcial** (DA-09, P-11) | `bitacora-de-alcance.md` |
| RNF-10 | bloqueo tras 5 fallos en 15 min | 429 con `Retry-After` | Cumple | `cierre-sprint-1.md` |
| RNF-11 | bitácora sin edición ni borrado | triggers de solo inserción en la base | Cumple | suite |
| RNF-12 | cifrado; certificado propio declarado | HTTP → 307 a HTTPS; certificado "AlTiro demo local, autofirmado" | Cumple | `cierre-sprint-1.md` |
| RNF-13 | 2 de 3 participantes en ≤ 10 min | **sin ejecutar** (requiere personas) | **Pendiente** | `rnf-13-protocolo.md` |
| RNF-14 a RNF-17 | pulgar, errores accionables, WCAG 2.2, vocabulario del oficio | 0 objetivos < 44 px; axe-core 0 violaciones; 0 jerga | Cumple | cierres S2 a S5 |
| RNF-18 | Chrome, Firefox y Chrome Android vigentes | automático en Chromium y Firefox: cumple. Pase manual en marca y Android: pendiente | **Parcial** | `rnf-18-compatibilidad.md` |
| RNF-19 | respaldo diario, 7 días, restauración ≤ 30 min | restauración en 19 s; retención de 7 días probada; primer respaldo automático: 2026-10-01 03:00 | **Parcial** (revisar ese día) | `rnf-19-respaldo.md` |
| RNF-20 | se conservan los pasos al reconectar | borradores y "Reintentar" sin perder datos | Cumple | `cierre-sprint-2.md`, `cierre-sprint-3.md` |
| RNF-21 | ≥ 60 % de las reglas críticas con pruebas | 83 de 83 (100 %) | Cumple | `tests/reglas_rnf21.py` |
| RNF-22 | nivel, marca de tiempo, usuario y operación | registro JSON por línea, sin datos personales | Cumple | `cierre-sprint-5.md` |
| RNF-23 | un comando, ≤ 10 min en un equipo limpio | 43 a 47 s en un motor Docker limpio | Cumple (falta confirmar en el laboratorio) | `rnf-23-medicion.md` |
| RNF-24 | configuración fuera del código | sin secretos versionados | Cumple | `cierre-sprint-1.md` |
| RNF-25 | ningún servicio regulado visible sin licencia vigente | prueba que recorre todas las rutas públicas | Cumple | `cierre-sprint-3.md`, `cierre-sprint-4.md` |
| RNF-26 | plazo escrito por tipo y eliminación registrada | mecanismo listo; **plazos sin definir** (V-04, P-07) | **Pendiente** | `plazos-retencion.md` |
| RNF-27 | versiones exactas y revisión de avisos | 19 dependencias con `==`; `pip-audit` sin vulnerabilidades | Cumple | `revision-dependencias-s5.md` |

## 5. Lo que se dice con honestidad (límites declarados)

Conviene decirlo antes de que lo pregunten: muestra control del proyecto.

- **RNF-13 sin ejecutar.** Es el riesgo más alto que queda. El protocolo está escrito. Faltan 3 participantes. Si se ejecuta antes de la defensa, reemplazar esta línea con el resultado.
- **Decisiones provisionales.** ADR-016 E-1, ADR-018 a ADR-024 y ADR-026 están en "Aceptada — PROVISIONAL". Las preguntas P-01 a P-33 al representante siguen sin respuesta. Es la consecuencia esperada del riesgo de §5.4.1 (el representante no tiene autoridad real).
- **Supuestos V-01 a V-05** siguen sin validar. Por ejemplo, V-04 bloquea los plazos de RNF-26.
- **RNF-09:** la reautenticación depende de que exista el cambio de contraseña o de correo, que no está en ninguna HU (DA-09). No se amplió el alcance sin autorización (§5.3.6).
- **Entorno:** todo se midió en el equipo local, como define la prueba de concepto. No hay nube ni carga real.
- **Fuera de alcance:** pagos, facturación y publicidad (CLAUDE.md §4).

## 6. Preguntas probables y respuesta corta

- **¿Por qué ticket y orden son el mismo registro?** El informe los modela como estados del mismo registro lógico (Pendiente → Aceptado → Finalizado). Un solo registro conserva toda la trazabilidad sin copiar datos (ADR-023).
- **¿Cómo garantizan que el maestro no vea la dirección?** El servidor no la envía mientras el pedido está pendiente. No es un ocultamiento en la pantalla. Se demuestra en la pestaña Red (paso 4) y hay pruebas automáticas.
- **¿Qué pasa si alguien cambia el identificador en la URL?** Las URL usan un `ref` UUID. El servidor verifica identidad, rol, propiedad y estado. Un recurso ajeno responde el mismo 404 que uno inexistente, para no revelar que existe, y queda registrado (ADR-011, RNF-07).
- **¿Por qué la exportación es anónima de verdad?** Las columnas son cerradas y no hay identificadores. Se aplica supresión k=5 sobre maestros y clientes distintos. La mediana del monto queda vacía si hay menos de 5 órdenes finalizadas (DEF-QA-014, E-6.5). Las celdas que empiezan con `= + - @` se neutralizan.
- **¿Cómo se protegen los documentos?** Van cifrados con AES-256-GCM, sin EXIF y fuera de las rutas públicas. Se entregan con un enlace firmado de 10 minutos ligado al usuario. La clave nunca se monta en el contenedor de respaldo.
- **¿Qué pasa si se cae el equipo?** Hay respaldo diario con retención de 7 días. La restauración probada tomó 19 s (el umbral es 30 min).
- **¿Cómo controlaron el alcance?** Ningún cambio entró al sprint en curso. Cada desplazamiento quedó en la bitácora de alcance (DA-01 a DA-26) con fecha, motivo y estado.
- **¿Qué recortarían si faltara tiempo?** Lo que ya prevé §5.3.5: la mensajería y la evaluación ceden primero; RF-26 a RF-28 (precio) están protegidos.
- **¿Por qué Django y PostgreSQL?** Cumplen el stack que fija el informe (Python, base relacional en contenedor). La justificación está en ADR-001 y ADR-003.

## 7. Reparto sugerido (3 personas)

- **Persona 1:**
  - problema y solución;
  - metodología y control de cambios;
  - límites declarados (§1 y §5).
- **Persona 2:** demo de los pasos 1 a 8 (flujo principal).
- **Persona 3:**
  - demo de los pasos 9 a 13 (administración y seguridad);
  - evidencia RNF (§4).

Todos preparan las preguntas de §6.
