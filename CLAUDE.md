# CLAUDE.md — Proyecto AlTiro

## 1. Propósito del proyecto

AlTiro es una plataforma web responsiva para una empresa de intermediación digital que conecta hogares con maestros independientes verificados.

El objetivo del sistema es entregar una vista única, confiable y trazable de:
- los maestros y sus antecedentes;
- su disponibilidad y cobertura;
- las solicitudes/tickets;
- el acuerdo de precio;
- el estado de cada trabajo;
- la mensajería asociada;
- las evaluaciones;
- las acciones administrativas.

La solución debe priorizar el uso desde teléfono móvil, especialmente para maestros con baja alfabetización digital y conectividad irregular.

---

## 2. Fuente de verdad

La documentación del proyecto ubicada en `docs/` es la fuente de verdad funcional y de negocio.

- `docs/informe-altiro.md`: versión Markdown del informe. **Usar este archivo para consultar el informe**; tiene un índice rápido al inicio (HU en §3.2, criterios de aceptación en §3.3, RF en §4.2.1, RNF con umbrales en §4.2.2, trazabilidad en §4.4.2, sprints en §5.3.5, riesgos en §6).
- `docs/InformeALTiroDanielSebastianLuciano.docx`: documento original. Si hay discrepancia con la versión Markdown, prevalece el `.docx`.

Antes de diseñar o implementar una funcionalidad:
1. revisar la documentación relacionada;
2. identificar la historia de usuario (HU), requerimiento funcional (RF), requerimiento no funcional (RNF) y/o necesidad TI (NTI) correspondiente;
3. respetar los criterios de aceptación y umbrales definidos;
4. no inventar reglas de negocio ni ampliar el alcance sin autorización explícita.

Si existe contradicción entre una decisión técnica propuesta y el informe, prevalece el informe hasta que el equipo documente formalmente un cambio.

Los supuestos V-01 a V-05 deben tratarse como supuestos pendientes de validación, no como hechos confirmados.

---

## 3. Estado y entorno base de la prueba de concepto

El informe define para esta etapa:

- Despliegue: Docker + Docker Compose.
- Ejecución: equipo local del equipo de desarrollo.
- Persistencia: motor de base de datos relacional en contenedor, con volumen local.
- Servicios de nube pagados: no requeridos para la prueba de concepto.
- Backend: Python.
- Frontend: HTML, CSS y JavaScript.
- Volumen de prueba:
  - 100 maestros;
  - 300 servicios publicados;
  - 1.000 tickets;
  - 5.000 mensajes.
- Concurrencia objetivo: 10 usuarios simultáneos.
- Red móvil de referencia: conexión limitada/emulada desde navegador.

No sustituir estas decisiones por otro stack sin una decisión explícita y documentada del equipo.

---

## 4. Alcance funcional

El proyecto cubre el proceso desde que un cliente genera una solicitud hasta que la orden queda cerrada/finalizada con precio acordado y evaluación, además de la administración del expediente del maestro.

Incluye, entre otros:

- registro y autenticación;
- perfiles y permisos;
- postulación de maestros;
- carga y control de documentos;
- verificación y curatoría;
- catálogo de oficios y servicios;
- cobertura territorial;
- disponibilidad por bloques horarios;
- búsqueda, filtros y ordenamiento de maestros;
- creación y gestión de tickets;
- aceptación y rechazo de tickets;
- cierre automático de tickets;
- registro y aceptación del precio final;
- historial de tickets y órdenes;
- mensajería asociada al ticket aceptado;
- evaluaciones;
- denuncias y moderación;
- auditoría de acciones administrativas;
- indicadores y exportación de datos agregados y anonimizados.

### Fuera de alcance

No implementar salvo cambio formalmente aprobado:

- contabilidad;
- facturación electrónica;
- pagos dentro de la plataforma;
- integración de publicidad;
- venta efectiva de datos;
- funciones que no estén respaldadas por HU, RF, RNF, NTI o una decisión documentada posterior.

---

## 5. Actores y control de acceso

El sistema distingue los siguientes actores:

### Visitante
- Puede consultar información pública.
- Solo lectura de perfiles públicos y precios de referencia.
- No posee acceso a vistas privadas.

### Cliente
- Registra solicitudes/tickets.
- Busca maestros.
- Agenda.
- Conversa cuando corresponda.
- Cancela/cierra sus tickets cuando la regla de negocio lo permita.
- Evalúa.
- Solo puede operar sobre sus propios recursos.

### Maestro
- Mantiene su perfil.
- Declara servicios, cobertura, disponibilidad y precios.
- Postula y administra sus documentos.
- Acepta o rechaza tickets dirigidos a él.
- Solo puede acceder a sus propios tickets/órdenes y datos permitidos según el estado.

### Administrador de curatoría
- Revisa expedientes.
- Aprueba, observa, rechaza o suspende.
- Todo cambio de estado debe quedar motivado y auditado.

### Administrador comercial
- Administra catálogo de oficios, servicios, modalidades y precios de referencia.

### Moderación
- Gestiona denuncias sobre evaluaciones.
- Puede acceder a la conversación de un ticket únicamente cuando exista una disputa abierta y según las reglas definidas.

### Control de gestión
- Consulta indicadores.
- Exporta datos agregados sin identificadores personales.

### Sistema
Actor no humano encargado de tareas automáticas:
- cierre/expiración de tickets;
- avisos de vencimiento;
- desactivación de servicios regulados;
- demás tareas programadas expresamente documentadas.

### Regla general de autorización

Nunca confiar solo en el rol mostrado por la interfaz.

Toda operación sobre un recurso debe verificar en el servidor:
- identidad;
- rol cuando corresponda;
- propiedad/autorización específica sobre el recurso;
- estado actual del recurso;
- reglas de negocio aplicables.

Un usuario nunca debe acceder a un recurso ajeno modificando un identificador en una URL o petición.

---

## 6. Modelo conceptual del flujo principal

Usar consistentemente la terminología del informe:

### Solicitud
Necesidad expresada inicialmente por el cliente. Se formaliza como registro cuando se crea un ticket.

### Ticket
Solicitud formalizada y dirigida a un maestro concreto.

Debe contener, según corresponda:
- servicio;
- descripción;
- dirección;
- bloque horario;
- declaración de materiales;
- modalidad y monto publicados al momento del envío.

El ticket nace en estado `Pendiente`.

### Orden
No crear necesariamente una entidad desconectada solo por cambiar de etapa.

Según el modelo del informe, el ticket aceptado continúa como el mismo registro lógico:
- `Pendiente`
- `Aceptado`
- `Finalizado`

Debe conservar trazabilidad de estados, precio final, conversación y evaluaciones.

### Trabajo
Es la ejecución física en terreno. Ocurre fuera del sistema.

El sistema conserva la evidencia digital relevante:
- estado;
- precio final;
- aceptación del precio cuando corresponda;
- conversación;
- evaluaciones.

---

## 7. Reglas de negocio críticas

Estas reglas deben tratarse como invariantes, salvo modificación formal del informe.

### Registro y autenticación
- El cliente registra nombre, teléfono, correo y ubicación por región/provincia/comuna.
- La comuna debe provenir de una lista cerrada.
- El maestro debe registrar un RUT válido y único.
- Las vistas privadas requieren autenticación.

### Documentos del maestro
- Un documento puede tener o no fecha de vencimiento.
- Un documento sin vencimiento no debe generar alertas de expiración.
- Oficios regulados requieren la licencia correspondiente cargada y vigente antes de ser aprobados.
- Si una licencia regulada deja de estar vigente, los servicios regulados asociados deben desactivarse automáticamente.
- Debe notificarse el vencimiento según el umbral definido en los requerimientos.

### Servicios, cobertura y agenda
- Todo servicio publicado debe tener modalidad de precio y monto.
- El maestro debe declarar una comuna base para aparecer en resultados.
- Los bloques horarios deben validarse en servidor y no pueden tener rangos inválidos.
- Debe impedirse la doble reserva.

### Búsqueda
- Los filtros por oficio, comuna y bloque horario son excluyentes.
- Ningún resultado principal puede incumplir un filtro aplicado.
- El ordenamiento usa el criterio definido en RF-10 y RF-11.
- Si no existen resultados, las sugerencias deben estar claramente separadas e indicar qué condición incumplen.

### Tickets
- No crear un ticket para un bloque que comience en 4 horas o menos.
- Mientras esté `Pendiente`, no entregar al maestro la dirección exacta ni el teléfono del cliente; mostrar solo la comuna.
- La protección debe ocurrir en la respuesta del servidor, no solo ocultando datos en la interfaz.
- Al aceptar:
  - el ticket pasa a `Aceptado`;
  - el bloque queda ocupado;
  - se cierran los demás tickets pendientes incompatibles sobre ese bloque según la regla documentada;
  - se revelan los datos de contacto permitidos.
- Al rechazar, el bloque queda nuevamente disponible.
- Un ticket pendiente puede cerrarse automáticamente:
  - al cumplirse 24 horas desde el envío;
  - cuando falten 4 horas para el inicio del bloque;
  - según las reglas y motivos establecidos.
- Todo cierre debe registrar motivo y notificar a las partes correspondientes.

### Precio y finalización
- El ticket conserva una copia de la modalidad y monto publicados al momento de su creación.
- El precio final debe quedar registrado con fecha y autor.
- Para modalidad por trabajo, si el monto final difiere del monto original, se exige aceptación explícita del cliente.
- Para modalidad por hora, debe aplicarse la regla de aceptación definida en RF-27.
- No finalizar la orden mientras falte una aceptación obligatoria.

### Evaluaciones
- Solo pueden originarse sobre órdenes `Finalizadas`.
- Una sola evaluación por parte y por orden.
- La calificación del maestro se obtiene a partir de las dimensiones definidas en el informe.
- Las denuncias y resoluciones deben quedar registradas con autor y motivo.

### Auditoría
Las acciones administrativas relevantes deben generar una entrada de bitácora con:
- autor;
- acción;
- entidad;
- valor anterior;
- valor nuevo;
- motivo;
- fecha.

La bitácora no debe ser editable ni eliminable desde la aplicación.

---

## 8. Seguridad y privacidad

La seguridad es requisito estructural del proyecto, no una fase posterior.

Activos especialmente sensibles:
- fotografías de cédula;
- certificados de antecedentes;
- licencias;
- datos de contacto;
- dirección exacta;
- credenciales;
- conversaciones;
- órdenes;
- precios;
- bitácora;
- base de datos;
- código y configuración;
- datos agregados.

### Reglas mínimas

- Nunca guardar contraseñas en texto plano.
- Usar hash adaptativo apropiado para contraseñas.
- Verificar autorización y propiedad del recurso en servidor.
- No exponer documentos sensibles mediante rutas públicas directas.
- Los accesos temporales a documentos deben expirar según el RNF correspondiente.
- Dirección y teléfono del cliente no deben viajar al dispositivo del maestro mientras el ticket esté pendiente.
- La sesión debe expirar según los umbrales definidos.
- Las operaciones sensibles requieren las validaciones/reautenticaciones definidas.
- Limitar intentos de autenticación según los requerimientos.
- Usar transporte cifrado.
- No escribir secretos, contraseñas, tokens, documentos ni datos personales innecesarios en logs.
- Mantener dependencias controladas y versionadas.
- Implementar y verificar respaldo/restauración según los RNF.
- Aplicar minimización de datos.
- La exportación agregada nunca debe incluir identificadores personales.
- Prevenir reidentificación en conjuntos supuestamente anonimizados.
- La autenticación se valida siempre contra las cuentas guardadas en la base de datos (hash, ADR-004/ADR-013). Nunca usuarios, contraseñas ni "cuentas maestras" escritos en el código fuente, en el frontend ni en archivos versionados; las cuentas de demostración se crean por comando con contraseña aleatoria (ADR-028).
- Cerrar la pestaña o la ventana de ingreso (o el navegador) no debe dejar a nadie bloqueado: al volver, la persona puede ingresar de nuevo con normalidad, ya sea retomando una sesión vigente o iniciando una nueva.

No bajar requisitos de seguridad para simplificar una demostración sin dejar la desviación documentada.

---

## 9. UX, accesibilidad y diseño móvil

El sistema debe diseñarse mobile-first.

Consideraciones obligatorias:
- maestro operando principalmente desde teléfono;
- posible conexión irregular;
- formularios simples y por pasos;
- lenguaje del oficio, no jerga técnica;
- mensajes de error accionables;
- ningún error debe mostrar códigos internos al usuario;
- objetivos táctiles adecuados;
- contraste conforme a los criterios definidos;
- ningún estado debe depender exclusivamente del color;
- compatibilidad con los navegadores especificados en los RNF;
- conservar progreso de formularios cuando corresponda.

### Validaciones mínimas de formularios y operaciones

Pedidas por el equipo (2026-10-11); concretan RNF-14 y RNF-15. Se aplican a **todo** formulario y a toda operación que llame al servidor:

1. **Largo de los campos:** cada campo de texto tiene un largo máximo definido en el servidor (y en la base cuando corresponda) y el mismo `maxlength` en pantalla. Superarlo da un mensaje en el campo, nunca un recorte silencioso ni un 500.
2. **Espacios sobrantes:** los espacios al inicio y al final se eliminan antes de validar y guardar (el servidor siempre; la pantalla puede hacerlo también). Un campo obligatorio con solo espacios cuenta como vacío. **Excepción: la contraseña nunca se recorta** (ADR-013, punto 3).
3. **Indicador de carga:** toda espera (envío, búsqueda, carga de página o de archivo) muestra un indicador visible con texto ("Enviando…", "Buscando…"), y el botón queda desactivado mientras dura, para evitar envíos dobles.
4. **Mensajes claros y visibles:** cada error dice qué falló, por qué y qué debe hacer la persona, junto al campo afectado y en un lugar visible sin desplazarse (resumen arriba con foco cuando hay varios). Sin códigos internos (RNF-15).
5. **No borrar el formulario por un error:** si falta o falla un dato, se conserva todo lo demás que se escribió y solo se marca lo que hay que corregir.
6. **Limpiar al terminar bien:** cuando la operación se completó con éxito, los campos se limpian (y se borra el borrador guardado, si existía) para que no se envíe dos veces lo mismo. Si la pantalla cambia tras el éxito, basta con no volver a mostrar los datos ya enviados. **Excepción:** en los formularios que editan un dato vigente (por ejemplo «Sobre mí» o los datos de la cuenta), tras guardar se muestra el valor guardado, no un campo vacío.
7. **Mensaje de resultado:** toda operación termina con un mensaje visible de éxito o de error en lenguaje simple ("Tu pedido fue enviado", "No pudimos guardar: …"), anunciado también a lectores de pantalla (`aria-live`) y sin depender solo del color.

No diseñar primero para escritorio y adaptar después si eso perjudica el flujo móvil.

---

## 10. Requerimientos no funcionales

El proyecto define 27 RNF clasificados usando ISO/IEC 25010:2023.

Los umbrales del informe son requisitos verificables, no recomendaciones.

Al implementar una HU/RF:
1. identificar los RNF relacionados;
2. incluir pruebas o evidencia cuando sea razonable;
3. no declarar una funcionalidad terminada si incumple un RNF asociado.

Ejemplos relevantes definidos por el informe:
- tiempo de respuesta de búsquedas;
- carga sobre red móvil limitada;
- capacidad del volumen de prueba;
- límite de recursos;
- almacenamiento seguro de contraseñas;
- privacidad de documentos;
- autorización por recurso;
- ocultamiento de dirección y teléfono;
- expiración de sesión;
- limitación de intentos;
- bitácora inmutable desde la aplicación;
- cifrado en tránsito;
- usabilidad móvil;
- accesibilidad;
- compatibilidad;
- respaldo y restauración.

Consultar el informe para el valor exacto de cada umbral antes de implementar o probar.

---

## 11. Metodología de trabajo del proyecto

El informe selecciona Scrum adaptado, con sprints de tres semanas.

Adaptaciones principales:
- sincronización de 15 minutos dos veces por semana en lugar de reunión diaria;
- evidencia documental incluida en la Definición de Hecho;
- representante del producto para concentrar preguntas y decisiones provisorias;
- registro explícito de supuestos y preguntas abiertas;
- límites de trabajo en curso.

### Control de cambios

Un cambio no entra automáticamente al sprint en curso.

Procedimiento:
1. registrar el cambio;
2. incorporarlo al Product Backlog;
3. priorizarlo;
4. analizar impacto;
5. registrar cualquier desplazamiento de alcance con fecha, motivo y autorización.

No modificar silenciosamente el alcance.

---

## 12. Orden inicial de implementación

Respetar las dependencias definidas en la planificación del informe.

### Sprint 1
Identidad, roles y control de acceso.

### Sprint 2
Expediente del maestro y curatoría.

### Sprint 3
Catálogo, cobertura y agenda.

### Sprint 4
Búsqueda, ordenamiento y flujo de ticket/orden.

### Sprint 5
Mensajería, evaluación, bitácora e indicadores.

La seguridad y el control de acceso deben construirse temprano.

No adelantar mensajería, documentos sensibles u otras funciones que dependan de autorización antes de tener correctamente implementada la base de identidad y control de acceso.

---

## 13. Reglas para Claude Code y subagentes

### Antes de modificar código
- Leer este archivo.
- Revisar los documentos relevantes de `docs/`.
- Identificar qué HU/RF/RNF/NTI se implementan.
- Examinar la arquitectura y código existentes.
- Explicar brevemente el plan cuando el cambio sea significativo.

### Durante la implementación
- No inventar funcionalidades.
- No alterar reglas de negocio para facilitar el código.
- Preferir soluciones simples y mantenibles.
- Mantener validaciones críticas en servidor.
- No duplicar reglas de negocio entre múltiples capas sin necesidad.
- Mantener nombres alineados con el vocabulario del informe.
- No introducir servicios de pago o infraestructura externa no aprobada.
- No introducir dependencias innecesarias.
- No almacenar secretos en el repositorio.
- No usar datos personales reales en fixtures o pruebas.
- Crear pruebas para reglas críticas.

### Al finalizar
Informar:
1. qué se implementó;
2. HU/RF/RNF relacionados;
3. archivos modificados;
4. pruebas ejecutadas;
5. resultados;
6. decisiones o supuestos introducidos;
7. riesgos o trabajo pendiente.

No afirmar que algo está terminado si no fue probado.

---

## 14. Límites operativos del agente

Trabajar únicamente dentro de este repositorio salvo autorización explícita.

No ejecutar sin autorización explícita:
- `git push`;
- `git push --force`;
- `git reset --hard`;
- eliminación masiva de archivos;
- borrado de bases de datos o volúmenes;
- comandos destructivos;
- cambios fuera del repositorio;
- despliegues externos;
- operaciones con credenciales reales.

No cambiar archivos de configuración global del sistema operativo sin autorización.

---

## 15. Convenciones de documentación y trazabilidad

Cuando se implemente una funcionalidad, usar referencias como:

- `HU-XX`
- `RF-XX`
- `RNF-XX`
- `NTI-XX`

No inventar nuevos identificadores de requerimientos.

Las decisiones técnicas relevantes que no estén definidas por el informe deben registrarse explícitamente en `docs/decisions/` antes o junto con su implementación.

Cuando exista información no confirmada:
- no convertirla en hecho;
- marcarla como supuesto;
- relacionarla con V-01 a V-05 cuando corresponda;
- solicitar validación si bloquea una decisión importante.

---

## 16. Principio rector

La meta no es generar la mayor cantidad de código posible.

La meta es construir una prueba de concepto coherente con el informe, trazable, demostrable, segura y suficientemente simple para que un equipo académico de tres personas pueda comprenderla, probarla, documentarla y defenderla.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
