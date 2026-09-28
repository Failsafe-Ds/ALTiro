# Informe 1 — Proyecto Integrado: Caso AlTiro

> Versión Markdown de `docs/InformeALTiroDanielSebastianLuciano.docx`, convertida para consulta rápida. El contenido es el del informe original sin cambios de fondo; si hay discrepancia, prevalece el `.docx`. Las figuras del original no se incluyen.

| Campo | Dato |
|---|---|
| Asignatura | Proyecto Integrado |
| Sección | D-IEI-N4-P2-C2 |
| Académico guía | Yasna Leon Foitzick |
| Integrantes | Sebastián Fuica, Daniel Sánchez, Luciano Vargas |
| Fecha de entrega | 21/09/2026 |

## Índice rápido para desarrollo

| Qué busco | Sección |
|---|---|
| Vocabulario solicitud / ticket / orden / trabajo | 2.3 |
| Necesidades TI (NTI-01 a NTI-12) y qué está comprometido | 2.6, 2.9.3 |
| Supuestos pendientes V-01 a V-05 | 2.7 |
| Actores y permisos | 3.1 |
| Historias de usuario HU-01 a HU-25 | 3.2 |
| Criterios de aceptación (CA-xx.y) | 3.3 |
| Fórmula de ordenamiento de búsqueda | 3.3.2 |
| Condiciones de cierre de tickets | 3.3.9 |
| Entorno de la prueba de concepto (stack) | 4.1 |
| Requerimientos funcionales RF-01 a RF-38 | 4.2.1 |
| Requerimientos no funcionales RNF-01 a RNF-27 (umbrales) | 4.2.2 |
| Matriz de trazabilidad NTI → HU → RF/RNF | 4.4.2 |
| Planificación de sprints | 5.3.5 |
| Activos, riesgos y medidas de seguridad | 6.1, 6.2 |

## 1. Introducción

AlTiro Servicios SpA es una empresa de intermediación digital constituida en marzo de 2026 en Concepción que conecta hogares con maestros independientes de ocho oficios, y su promesa comercial es concreta, que contratar a un gasfíter o a un eléctrico deje de ser una apuesta, promesa que hoy no tiene cómo sostenerse porque la empresa coordina 63 maestros con una planilla de 31 columnas, un grupo de WhatsApp de tres personas por trabajo y carpetas personales donde viven las cédulas y las licencias de sus prestadores.

El problema de fondo es la ausencia de registro, porque nadie puede decir en qué estado está una orden sin reconstruirla a mano, la disponibilidad de un maestro se averigua llamándolo 2,7 veces en promedio por trabajo, el precio se acuerda de palabra en terreno y el 78% de los trabajos no recibe evaluación alguna, con una consecuencia que se puede medir, ya que el 45% de las solicitudes no se concreta, el 18% se pierde solo por demora en responder y el proceso satura a los doce trabajos diarios.

Este informe documenta el análisis previo a la construcción de una plataforma web responsiva que resuelva ese vacío, un trabajo que partió por entender el negocio antes de proponer nada y de cuyas brechas salieron doce necesidades de tecnologías de información, contrastadas con las tendencias realmente aplicables al caso y ordenadas con una matriz ponderada para decidir qué aborda el proyecto y qué queda fuera con una razón escrita, necesidades que después se tradujeron en veinticinco historias de usuario con criterios de aceptación verificables, pensadas para quienes van a usar el sistema, es decir un maestro que solo tiene teléfono, un cliente con un problema encima y dos socios que administran toda la operación en media jornada, de donde salieron 38 requerimientos funcionales y 27 no funcionales clasificados según ISO/IEC 25010:2023 y con umbrales medibles contra el entorno de la prueba de concepto, mientras la forma de trabajo se eligió comparando tres metodologías con criterios ponderados y el análisis de seguridad se hizo junto al de sus implicancias éticas, en un semestre que coincide con la fecha prevista de entrada en vigor de la Ley 21.719 sobre datos personales, sujeta al supuesto V-02.

El desafío que atraviesa todo el documento se puede formular en una pregunta: cómo entregar una vista única, confiable y trazable de cada maestro verificado y de cada trabajo solicitado, sin exigirle a un usuario con baja alfabetización digital más de lo que un teléfono en terreno permite.

## 2. Contexto, necesidades y tendencias de TI

### 2.1. Descripción del negocio y situación actual

AlTiro Servicios SpA es una empresa de intermediación digital constituida en marzo de 2026 mediante el registro "Tu Empresa en un Día", que conecta hogares del Gran Concepción con maestros independientes verificados sin ejecutar ella misma ningún oficio y responde por la calidad de esa conexión, con un modelo de ingreso que conviene leer en tres planos distintos, porque el informe los trata de manera diferente. Lo actual es que la empresa no cobra comisión ni vende información: el acuerdo económico se cierra directamente entre cliente y maestro y no existe registro consolidado que se pueda explotar, de modo que hoy no hay ingreso por datos. Lo proyectado es que la plataforma conserve lo solicitado y el precio acordado, y que ese conjunto, agregado y anonimizado, se convierta en información de mercado sobre demanda, precios y cobertura por comuna. Lo supuesto, registrado como V-05 y no demostrable en esta etapa, es que ese conjunto alcance volumen y comprador; la publicidad segmentada pertenece al mismo plano y queda fuera del alcance según 2.4. El proyecto construye el registro y la exportación agregada, que son la condición del modelo, y no la venta en sí.

### 2.2. Ficha de la organización

| Antecedente | Dato |
|---|---|
| Razón social | AlTiro Servicios SpA |
| Constitución | Marzo de 2026, Sociedad por Acciones |
| Giro | Intermediación digital y publicidad de servicios para el hogar |
| Domicilio | Oficina compartida, Barrio Estación, Concepción |
| Capital inicial | $32.000.000 CLP |
| Dotación | 2 socios a tiempo completo y 1 asistente a media jornada |
| Red de prestadores | 63 maestros activos (de 200 contactados), 8 oficios |
| Cobertura piloto | Concepción, Talcahuano, Hualpén, San Pedro de la Paz, Chiguayante y Penco |
| Volumen de operación | Satura a los 12 trabajos diarios |
| Situación tecnológica | Sin plataforma propia; opera con WhatsApp Business, Instagram y una planilla de Google Sheets |

El tamaño importa para el resto del informe: dos socios y media jornada de asistente significan que cualquier solución que exija administración intensiva fracasa por falta de personas antes que por falta de funcionalidad.

### 2.3. Vocabulario del proceso

El proceso actual mezcla estos cuatro términos y el sistema necesita separarlos, porque cada paso de uno al siguiente es una de las pérdidas que el diagnóstico midió: una solicitud puede no llegar a ticket, un ticket puede no llegar a orden y una orden puede no llegar a trabajo. De aquí en adelante se usan siempre con este sentido.

| Término | Qué significa en este informe |
|---|---|
| Solicitud | La necesidad que el cliente expresa antes de elegir a alguien. Hoy es un mensaje de WhatsApp y en el sistema es lo que el cliente escribe al buscar y al completar el formulario. No existe como registro numerado: se convierte en registro cuando pasa a ticket |
| Ticket | La solicitud ya formalizada y dirigida a un maestro concreto, con servicio, descripción, dirección, bloque horario y declaración de materiales. Nace en estado Pendiente y es la unidad que el sistema numera, traza y cierra |
| Orden | El ticket que el maestro aceptó es el mismo registro en estado Aceptado y luego Finalizado, y es lo que conserva el precio final, la conversación y las evaluaciones |
| Trabajo | La ejecución en terreno, que ocurre fuera del sistema. De ella quedan en la orden el precio final acordado y la evaluación de ambas partes |

### 2.4. Proceso actual (AS-IS)

El flujo vigente desde abril de 2026 es enteramente manual:

1. El cliente escribe por WhatsApp Business, canal difundido desde Instagram.
2. La asistente transcribe la solicitud a una planilla de Google Sheets de 31 columnas, con datos inconsistentes entre filas.
3. Un socio busca en esa planilla y en su memoria qué maestro podría atender el oficio y la comuna.
4. Llama a los candidatos hasta conseguir uno disponible, con un promedio de 2,7 llamadas por trabajo, porque la agenda real del maestro solo se conoce preguntando.
5. Se arma un grupo de WhatsApp de tres personas, cliente, maestro y socio, para coordinar dirección, hora y precio, un grupo que no deja historial consolidado ni queda asociado a ningún registro.
6. El maestro ejecuta y el monto final se acuerda de palabra en terreno.
7. El monto final se informa por mensaje, sin respaldo asociado a la solicitud original.
8. La evaluación se pide por mensaje y responde el 22% de los clientes.
9. Los expedientes de los maestros, que incluyen fotos de cédula por ambos lados, certificado de antecedentes y licencia SEC cuando corresponde, viven en carpetas personales y correos de los socios.

*Figura 1 (no incluida en esta versión). Flujo actual de una solicitud y puntos donde se pierde demanda. Elaboración propia a partir del dossier del cliente.*

### 2.5. Delimitación del proyecto

El proyecto se origina en el proceso de gestión de la orden de servicio y del expediente del maestro, desde que entra una solicitud hasta que la orden se cierra con su precio acordado y su evaluación, quedan fuera del alcance la contabilidad, la facturación electrónica, el pago dentro de la plataforma y la integración de posible publicidad a no ser que se llegue a un acuerdo más adelante.

### 2.6. Identificación de necesidades TI y buenas prácticas

Las necesidades se derivaron de las brechas observadas en el proceso AS-IS, de modo que cada una responde a una causa visible en la operación actual y se asocia a una práctica reconocida de la industria o a una obligación normativa vigente en Chile.

| ID | Necesidad TI | Evidencia / causa | Impacto | Usuarios | Objetivo del negocio | Buena práctica que la orienta |
|---|---|---|---|---|---|---|
| NTI-01 | Verificación documentada de identidad y habilitación del maestro, con control de vigencia | Expedientes en carpetas y correos personales; sin control de vencimientos; 2 oficios regulados por SEC | Riesgo legal directo si se ejecuta un trabajo regulado sin licencia vigente | Administrador de curatoría, maestro | Sostener la promesa de "maestro verificado" | Verificación de credenciales contra fuente oficial: Registro Nacional de Instaladores e Inspectores (e-RNII) de la SEC; estados de expediente con transiciones controladas |
| NTI-02 | Agenda declarada por bloques horarios, consultable y sin doble reserva | 2,7 llamadas telefónicas por trabajo para saber si el maestro puede | 5,5 h/día de un socio en coordinación; 18% de solicitudes perdidas por demora | Maestro, cliente, operaciones | Responder rápido y comprometer solo bloques que el maestro declaró libres | Gestión de calendario con bloqueo de recursos y holgura de traslado; validación de solapamiento en el servidor, no en la interfaz |
| NTI-03 | Registro único y trazable del ticket y de la orden que nace de él, con historial de estados | Planilla de 31 columnas y un grupo de WhatsApp de tres personas por trabajo, sin vista única | Imposible saber en qué estado está una orden sin reconstruirla a mano | Todos los actores | Escalar sobre 12 trabajos diarios | Fuente única de verdad; registro de eventos de estado con autor, fecha y motivo |
| NTI-04 | Registro auditable del acuerdo de precio y alcance, incluida la cotización complementaria | El monto se acuerda verbalmente en terreno; no existe respaldo | 11% de reclamos sin evidencia para resolver | Cliente, maestro, moderación | Reducir conflictividad y cumplir con el cliente | Ley 19.496 (texto refundido, DFL 3/2021): derecho a información veraz y oportuna sobre el precio antes de contratar; aceptación explícita del precio final cuando este difiera del precio inicialmente declarado |
| NTI-05 | Búsqueda y descubrimiento de maestros con ordenamiento por cercanía, disponibilidad y reputación | Hoy la selección la hace un socio de memoria; el cliente no elige | Sesgo de asignación y pérdida de demanda | Visitante, cliente | Convertir solicitudes en órdenes | Ordenamiento explicable con criterios declarados; degradación elegante cuando el filtro no arroja resultados |
| NTI-06 | Reputación verificada y bidireccional, vinculada a órdenes reales | 78% de trabajos sin evaluación; 22% de respuesta a la solicitud por mensaje | La propuesta de valor no tiene evidencia que mostrar | Cliente, maestro, moderación | Respaldar la promesa de maestro verificado | Evaluación restringida a participantes de una transacción finalizada, una evaluación por orden y por parte, moderación con derecho a respuesta |
| NTI-07 | Datos operacionales agregados y anonimizados, explotables comercialmente | El ingreso proyectado del negocio descansa en la información que genera la operación; hoy no existe ingreso por este concepto y que llegue a existir es el supuesto V-05 | Sin datos limpios y disociados no hay producto que vender ni base legal para hacerlo | Control de gestión, socios | Sostener el modelo de ingreso | Ley 21.719: el dato estadístico, que no puede asociarse a un titular identificable, queda fuera del régimen de datos personales; anonimización y agregación previas a cualquier explotación |
| NTI-08 | Comunicación asociada a la orden, con historial y adjuntos conservados | Grupos de WhatsApp de tres personas sin historial consolidado | Sin evidencia de lo conversado ante una disputa | Cliente, maestro, moderación | Resolver reclamos con antecedentes | Mensajería contextual por transacción; enmascaramiento de datos de contacto mientras la orden no se confirma |
| NTI-09 | Control de acceso por propiedad del recurso y tratamiento responsable de datos personales | Cédulas y antecedentes en correos personales; sin control de quién ve qué | Exposición de datos sensibles y sanción bajo la nueva ley | Todos | Operar sin riesgo regulatorio | Ley 21.719: finalidad, minimización, medidas de seguridad y notificación de brechas. Autorización verificada por recurso, no solo por rol |
| NTI-10 | Indicadores operacionales calculados sobre los datos de la operación | "Sin datos no hay decisiones de captación ni argumento para inversión" | Decisiones comerciales a ciegas | Control de gestión, socios | Priorizar dónde captar maestros | Indicadores derivados del proceso, no capturados aparte; definición escrita de cada cálculo |
| NTI-11 | Interfaz operable desde teléfono por usuarios con baja alfabetización digital | 91% de los maestros usa solo móvil; varios sin correo activo | Si el maestro no adopta la herramienta, la red no existe | Maestro | Incorporar maestros sin costo de soporte | Diseño web responsivo con enfoque móvil primero; WCAG 2.2 nivel AA en contraste, tamaño de objetivo táctil y mensajes de error; formularios divididos en pasos |
| NTI-12 | Bitácora inmutable de acciones administrativas sensibles | Aprobaciones y suspensiones sin registro de quién ni por qué | No se puede auditar ni revertir una decisión | Curatoría, administración | Responder ante una fiscalización o un reclamo | Registro de auditoría con autor, entidad, valores antes y después, motivo y fecha, según prácticas de gestión de registros (NIST SP 800-92) |

Hay dos antecedentes que no son necesidades TI y por eso no entran en la tabla, aunque condicionan el diseño, el primero es la vigencia de las licencias SEC según la ficha oficial del trámite, las licencias de instalador son indefinidas, salvo las obtenidas por certificación de competencias laborales, que se renuevan cada cinco años, mientras el dossier las trata a todas como si vencieran, el sistema tiene que aceptar documentos con fecha de vencimiento y sin ella, y lo que queda por confirmar con el cliente es cuántos maestros tienen cada tipo de licencia (supuesto V-01).

El segundo antecedente es la Ley 21.719, cuyo texto fija la entrada en vigor para el 1 de diciembre de 2026 y crea una agencia con facultad para sancionar, pero el 1 de septiembre de 2026 ingresó a tramitación un proyecto que propone postergarla hasta el 1 de diciembre de 2027, por eso la fecha queda registrada como supuesto V-02, esta incertidumbre no cambia el diseño porque las medidas previstas por la ley son las mismas que la empresa necesita para sostener su promesa de confianza y construirlas desde el inicio cuesta menos que agregarlas después.

### 2.7. Supuestos declarados del levantamiento

Lo que sigue no está confirmado por la contraparte y se trabaja igual, con el supuesto escrito y con la fecha en que se declaró, de modo que cada revisión de sprint pueda cerrarlo o corregirlo.

| ID | Supuesto | Por qué no está confirmado | Qué se asumió para avanzar y cómo se confirma |
|---|---|---|---|
| V-01 | Vigencia de las licencias SEC | El dossier trata todas las licencias como si vencieran, pero la ficha oficial del trámite las declara indefinidas salvo las obtenidas por certificación de competencias laborales, que se renuevan cada cinco años | El modelo admite documentos con y sin fecha de término, y RF-04 lo refleja. Se confirma consultando a la contraparte y revisando los expedientes ya recibidos, en la primera revisión de sprint |
| V-02 | Fecha de entrada en vigor de la Ley 21.719 | La ley fija el 1 de diciembre de 2026, pero el 1 de septiembre de 2026 ingresó a tramitación un proyecto que propone postergarla hasta el 1 de diciembre de 2027 | Se diseña como si la ley ya estuviera vigente porque adelantarse no tiene costo y llegar tarde sí, se confirma siguiendo la tramitación y no altera el diseño, solo la urgencia declarada en NTI-09 |
| V-03 | Atención de urgencias con cuatro horas o menos | RF-16 impide crear un ticket para un bloque que comience en cuatro horas o menos, y hoy el negocio atiende urgencias por teléfono | Esos bloques se ocultan en el formulario y la urgencia queda fuera del alcance de esta etapa. Se confirma con la decisión de la contraparte sobre si quiere una vía distinta para urgencias |
| V-04 | Plazo de retención de los documentos de identidad | Ni el dossier ni la ley fijan un plazo concreto, y la medida M-09 lo ata al período de garantía y al plazo de reclamo | Se asume retención mientras el maestro esté activo, más el plazo de reclamo del consumidor. Se confirma con una definición escrita acordada antes de implementar RNF-26 |
| V-05 | Alcance de la explotación comercial de los datos agregados | El modelo de ingreso descansa en vender información de mercado, y la publicidad segmentada aparece como posibilidad posterior | Se construye la exportación agregada y se deja fuera cualquier integración publicitaria. Se confirma con el acuerdo sobre qué se comercializa y con qué base de licitud |

### 2.8. Tendencias TI aplicables e impacto

Se seleccionaron tendencias que resuelven una necesidad concreta del listado anterior, dejando fuera blockchain, IA generativa, IoT y modelos predictivos, que no resuelven ninguna de las brechas encontradas.

| Tendencia | Aplicación al negocio | Impacto esperado | Riesgos | Condiciones de adopción | Fuente |
|---|---|---|---|---|---|
| Diseño web responsivo con enfoque móvil primero | El maestro opera desde el teléfono; el cliente solicita desde donde esté | Adopción efectiva de la red (NTI-11); menos soporte telefónico | Sobreestimar la conectividad en terreno; interfaz de escritorio adaptada a la fuerza | Probar en equipos de gama de entrada; tolerar formularios incompletos y reintentos | Subtel (2026), estadísticas del primer semestre: 22,59 millones de accesos a internet móvil, penetración de 112,1 por cada 100 habitantes, frente a un 70,36% de hogares con internet fija |
| Verificación de credenciales contra registros oficiales | Consultar la licencia del instalador en el e-RNII de la SEC en vez de confiar en una foto | Elimina la verificación artesanal (NTI-01) y reduce riesgo legal | Dependencia de un servicio externo sin acuerdo formal; no existe API pública documentada | Iniciar con verificación manual asistida y registro del comprobante; dejar la integración como evolución | Superintendencia de Electricidad y Combustibles, sección Licencia de Instaladora o Instalador; ficha ChileAtiende N 2662 |
| Búsqueda y ordenamiento por proximidad geográfica | Priorizar maestros cercanos y disponibles en los primeros resultados | Más solicitudes concretadas (NTI-05); menos viajes imposibles | Convertir el ordenamiento en una caja negra que nadie pueda explicar al cliente | Usar la división político-administrativa oficial (región, provincia, comuna) y documentar la fórmula de ordenamiento | Biblioteca del Congreso Nacional, división político-administrativa de Chile |
| Privacidad y seguridad desde el diseño | Minimizar datos, cifrar documentos de identidad, enmascarar contacto hasta confirmar la orden | Cumplimiento de la Ley 21.719 (NTI-09) y protección reputacional | Tratar la privacidad como una política escrita sin controles técnicos que la respalden | Inventario de datos personales y base de licitud declarada por cada dato recolectado | Ley N 21.719, BCN |
| Accesibilidad digital como requisito, no como extra | Contraste, tamaño de objetivo táctil, mensajes de error comprensibles | Habilita a maestros con baja alfabetización digital (NTI-11) | Verificarla solo al final del desarrollo, cuando corregir cuesta más | Incorporar criterios WCAG 2.2 AA a los criterios de aceptación desde el inicio | W3C (2023), Web Content Accessibility Guidelines 2.2 |
| Analítica operacional sobre el propio proceso | Calcular tasa de concreción, demanda por comuna y precios de referencia desde las órdenes | Decisiones de captación con evidencia y base del modelo de ingreso (NTI-10, NTI-07) | Construir tableros antes de tener datos limpios que alimentarlos | Definir por escrito cada indicador antes de programarlo; exigir primero calidad del registro | Dossier AlTiro, tabla de indicadores; ISO/IEC 25010:2023 para atributos medibles |

### 2.9. Priorización justificada de necesidades TI

#### 2.9.1. Criterios y escala

Todas las necesidades se evaluaron con los mismos cinco criterios, en escala de 1 a 5, donde 5 indica siempre mayor prioridad.

| Criterio | Peso | Qué mide | Escala |
|---|---|---|---|
| Impacto en el negocio | 30% | Efecto sobre ingreso, costo operacional o capacidad de escalar | 1 = marginal · 5 = afecta la viabilidad del modelo |
| Urgencia | 20% | Qué tan pronto duele si no se resuelve | 1 = puede esperar un año · 5 = ya está generando pérdida |
| Alineación estratégica | 20% | Correspondencia con la promesa de confianza verificada | 1 = tangencial · 5 = sostiene el núcleo del negocio |
| Riesgo de no abordarla | 20% | Exposición legal, reputacional o de continuidad | 1 = sin consecuencia · 5 = sanción o cierre |
| Viabilidad en el semestre | 10% | Posibilidad real de construirlo con 3 personas y el tiempo disponible | 1 = inabordable · 5 = alcanzable sin dependencias externas |

Puntaje = (0,30 × Impacto) + (0,20 × Urgencia) + (0,20 × Alineación) + (0,20 × Riesgo) + (0,10 × Viabilidad)

Regla de desempate: ante puntajes iguales prima la necesidad de la que dependen otras, y si el empate persiste, el mayor impacto.

Cortes: Alta ≥ 4,0 · Media entre 3,2 y 3,9 · Baja < 3,2

#### 2.9.2. Matriz de priorización

| ID | Impacto | Urgencia | Alineación | Riesgo | Viabilidad | Puntaje | Prioridad |
|---|---|---|---|---|---|---|---|
| NTI-01 Verificación y habilitación | 5 | 5 | 5 | 5 | 4 | 4,90 | Alta |
| NTI-03 Orden única y trazable | 5 | 5 | 5 | 4 | 4 | 4,70 | Alta |
| NTI-09 Acceso y datos personales | 4 | 5 | 4 | 5 | 4 | 4,40 | Alta |
| NTI-02 Disponibilidad declarada | 5 | 4 | 5 | 3 | 4 | 4,30 | Alta |
| NTI-04 Acuerdo de precio auditable | 4 | 4 | 5 | 4 | 5 | 4,30 | Alta |
| NTI-05 Búsqueda con ordenamiento | 5 | 4 | 4 | 2 | 4 | 3,90 | Media |
| NTI-11 Usabilidad web en móvil | 4 | 4 | 4 | 3 | 4 | 3,80 | Media |
| NTI-06 Reputación verificada | 4 | 3 | 5 | 2 | 5 | 3,70 | Media |
| NTI-07 Datos agregados y anonimizados | 4 | 2 | 3 | 5 | 3 | 3,50 | Media |
| NTI-12 Bitácora de auditoría | 3 | 3 | 3 | 4 | 5 | 3,40 | Media |
| NTI-08 Comunicación por orden | 3 | 3 | 4 | 3 | 4 | 3,30 | Media |
| NTI-10 Indicadores de gestión | 4 | 2 | 3 | 2 | 3 | 2,90 | Baja |

#### 2.9.3. Lectura del resultado

Las cinco necesidades de prioridad alta llegaron ahí por razones concretas, NTI-01 y NTI-09 concentran el riesgo legal del negocio en un semestre en que está prevista la entrada en vigor de la nueva ley de datos personales según el supuesto V-02, NTI-03 encabeza el orden de construcción porque sin una orden única y trazable ni la reputación ni la información agregada tienen de dónde calcularse, mientras NTI-02 y NTI-04 atacan las dos pérdidas cuantificadas del diagnóstico, el 18% de demanda perdida por demora y el 11% de reclamos sin evidencia.

El empate en 4,30 entre NTI-02 y NTI-04 se resolvió a favor de NTI-02 por la regla de dependencia: la búsqueda con ordenamiento por disponibilidad (NTI-05) y el agendamiento no pueden construirse sin que la disponibilidad exista como dato declarado.

NTI-10 quedó al final porque los indicadores se calculan sobre datos que todavía no existen, y un tablero construido antes de tener la orden bien registrada mostraría cifras poco confiables. Quedar al final no significa quedar fuera: se implementa un subconjunto mínimo de tres indicadores, tasa de concreción, tiempo de primera respuesta y vigencia documental, elegidos porque se derivan de datos que las necesidades altas producen de todas formas y no obligan a capturar nada aparte. El tablero de gestión completo, con cortes por comuna, por oficio y por período, se posterga.

Los tres son la tasa de concreción, que divide las órdenes finalizadas con precio registrado por el total de tickets enviados en el período; el tiempo de primera respuesta, medido entre el envío del ticket y la primera acción del maestro sobre él; y la vigencia documental, que es el porcentaje de maestros aprobados cuyos documentos obligatorios están vigentes a la fecha de cálculo. Los tres se calculan sobre la orden, no se capturan aparte.

Los puntajes de la matriz corresponden al juicio del equipo aplicado sobre la evidencia del diagnóstico, de modo que lo exigible es que el criterio sea el mismo para todas las necesidades y que cada valor pueda explicarse con un hecho del apartado 2.1.

El puntaje ordena las necesidades, pero no decide por sí solo qué se construye, porque dos de las medias sostienen el flujo principal y la única baja aporta tres indicadores que salen gratis de las altas. La tabla siguiente separa lo comprometido de lo condicionado, y esa separación es la que rige el resto del informe.

| Necesidad | Prioridad | Qué se compromete en este proyecto |
|---|---|---|
| NTI-01 Verificación y habilitación | Alta | Comprometido |
| NTI-03 Orden única y trazable | Alta | Comprometido |
| NTI-09 Acceso y datos personales | Alta | Comprometido |
| NTI-02 Disponibilidad declarada | Alta | Comprometido |
| NTI-04 Acuerdo de precio auditable | Alta | Comprometido |
| NTI-05 Búsqueda con ordenamiento | Media | Comprometido en su núcleo: filtro excluyente, ordenamiento y ficha del maestro (RF-09 a RF-14). Sin búsqueda no hay forma de llegar a un ticket. El catálogo administrable (RF-36) y la respuesta al resultado vacío (RF-12) quedan condicionados a capacidad |
| NTI-11 Usabilidad web en móvil | Media | Comprometido en su núcleo: postulación por pasos, tamaño de objetivo táctil, mensajes de error y contraste (RNF-13 a RNF-16). Si el maestro no logra registrarse, la red no existe. El resto de los umbrales queda condicionado |
| NTI-06 Reputación verificada | Media | Condicionado a capacidad |
| NTI-07 Datos agregados y anonimizados | Media | Condicionado a capacidad, limitado a la exportación agregada de RF-38 |
| NTI-12 Bitácora de auditoría | Media | Comprometido, porque NTI-01 y NTI-09 no se pueden auditar sin ella |
| NTI-08 Comunicación por orden | Media | Condicionado a capacidad |
| NTI-10 Indicadores de gestión | Baja | Subconjunto mínimo comprometido: los tres indicadores base, que se calculan sobre datos que las necesidades altas ya producen. El tablero de gestión completo queda fuera del alcance |

Lo comprometido se construye aunque el semestre se apriete y solo puede recortarse con acuerdo escrito en la bitácora de alcance lo condicionado entra según la capacidad que quede después, en el orden del puntaje fuera de todo esto quedan la contabilidad, la facturación electrónica, el pago dentro de la plataforma y la publicidad, según la delimitación del apartado 2.4.

## 3. Historias de usuario

### 3.1. Actores, roles y necesidades de usuarios finales

La plataforma distingue tres perfiles de usuario final, cuatro funciones administrativas que hoy recaen sobre las mismas dos personas y un actor no humano que ejecuta las tareas programadas ,separarlas importa aunque las personas sean las mismas, porque los permisos que necesita quien aprueba un expediente no son los de quien administra el catálogo de oficios, ni los de quien resuelve una denuncia sobre una evaluación.

| Actor | Responsabilidad | Objetivo al usar el sistema | Contexto de uso | Dificultad principal | Permisos | Necesidades |
|---|---|---|---|---|---|---|
| Visitante | Ninguna | Evaluar si vale la pena registrarse | Navegador de escritorio o móvil, sin cuenta | No puede comparar precios sin exponerse | Solo lectura de perfiles públicos y precios de referencia | NTI-05, NTI-06 |
| Cliente | Describir el trabajo y acordar el precio | Encontrar un maestro confiable y disponible sin hacer cinco llamadas | Desde la casa, con el problema encima y a veces con urgencia | No sabe qué oficio corresponde a su problema | Crea solicitudes, agenda, conversa, cancela, evalúa; solo sobre sus propias órdenes | NTI-03, NTI-04, NTI-05, NTI-06, NTI-08 |
| Maestro | Ejecutar el trabajo y mantener su perfil al día | Recibir trabajo constante sin pagar publicidad | Teléfono móvil, en terreno, con las manos sucias y conexión irregular | Baja alfabetización digital; el 91% no usa computador y varios no tienen correo | Mantiene su perfil, cobertura, agenda y precios; acepta o rechaza solicitudes; solo ve las suyas | NTI-01, NTI-02, NTI-04, NTI-11 |
| Administrador de curatoría | Decidir quién entra a la red | Aprobar sin exponer a la empresa | Notebook, revisión por lotes | Debe interpretar documentos y detectar vencimientos a mano | Revisa expedientes, aprueba, observa, rechaza y suspende con motivo | NTI-01, NTI-12 |
| Administrador comercial | Mantener el catálogo y los precios de referencia | Que la oferta publicada refleje la realidad del mercado | Notebook, ajustes esporádicos | Sin vista de qué oficios tienen demanda insatisfecha | Administra oficios, servicios, modalidades y precios de referencia | NTI-05, NTI-10 |
| Moderación | Resolver denuncias sobre evaluaciones | Cerrar una disputa con antecedentes y no con la palabra de uno contra otro | Notebook, casos esporádicos | Debe leer conversaciones privadas sin que eso se convierta en vigilancia | Revisa evaluaciones denunciadas y accede a la conversación del ticket solo con una disputa abierta | NTI-06, NTI-08 |
| Control de gestión | Leer los indicadores y exportar datos agregados | Decidir dónde captar maestros y sostener el modelo de ingreso | Notebook, revisión periódica | No distingue por sí solo cuándo un dato agregado deja de ser anónimo | Consulta los tres indicadores base y exporta datos sin identificadores personales | NTI-07, NTI-10 |
| Sistema | Tareas automáticas | Que el estado del sistema no dependa de que alguien se acuerde | Procesos programados | Ninguna | Expira solicitudes, avisa vencimientos, desactiva servicios regulados | NTI-01, NTI-02, NTI-03 |

Algo que afecta a todas las historias del maestro es que él trabaja por su cuenta, de modo que el sistema puede ofrecerle trabajo y guardar lo que acordó, pero no puede obligarlo a coordinar todo dentro de la plataforma, y por eso sus historias están escritas como opciones que él decide usar, mientras las del cliente aseguran que la solicitud y el precio queden registrados de todas formas.

### 3.2. Redacción y catálogo de historias de usuario

| ID | Rol | Quiero | Para | Necesidad | Prioridad |
|---|---|---|---|---|---|
| HU-01 | Cliente | Registrarme indicando mi nombre, contacto y ubicación por región, provincia y comuna | Que el sistema sepa dónde buscar maestros y cómo contactarme | NTI-05, NTI-09 | Alta |
| HU-02 | Cliente | Filtrar maestros por oficio, comuna y bloque horario | Ver solo a quienes efectivamente podrían tomar mi trabajo | NTI-05 | Alta |
| HU-03 | Cliente | Que los resultados aparezcan ordenados dando prioridad a quien está disponible y luego a quien está cerca | Elegir sin revisar cincuenta perfiles | NTI-05, NTI-02 | Alta |
| HU-04 | Cliente | Que se me avise cuando nadie cumple mis filtros y se me muestren alternativas cercanas | No quedarme sin ninguna opción frente a una pantalla vacía | NTI-05 | Media |
| HU-05 | Cliente | Ver la ficha completa de un maestro con su calificación por dimensión, comentarios, precios y horas ya tomadas | Decidir con información en vez de con una corazonada | NTI-01, NTI-06 | Alta |
| HU-06 | Cliente | Enviar un ticket indicando el trabajo, la dirección, el bloque horario y si tengo los materiales | Que el maestro decida con toda la información si puede tomarlo | NTI-03, NTI-02 | Alta |
| HU-07 | Cliente | Conversar con el maestro por un canal privado una vez que acepta | Coordinar dirección y detalles sin entregar mi teléfono a desconocidos | NTI-08, NTI-09 | Media |
| HU-08 | Cliente | Consultar el historial de mis tickets y de mis órdenes con el precio acordado en cada una | Tener respaldo de lo que pedí y de lo que me cobraron | NTI-03, NTI-04 | Alta |
| HU-09 | Cliente | Evaluar al maestro en puntualidad, trabajo y cordialidad al finalizar la orden | Que el próximo cliente decida mejor que yo | NTI-06 | Media |
| HU-10 | Cliente | Cancelar un ticket mientras el maestro todavía no lo acepta | No comprometer a alguien cuando ya resolví el problema | NTI-03 | Media |
| HU-11 | Maestro | Postular en pasos cortos cargando fotos de mi cédula, antecedentes y licencia | Entrar a la red desde el teléfono sin ayuda de nadie | NTI-01, NTI-11 | Alta |
| HU-12 | Maestro | Declarar mis oficios y el precio de cada servicio, por trabajo o por hora | Que el cliente sepa cuánto cuesta antes de que yo me mueva | NTI-04 | Alta |
| HU-13 | Maestro | Declarar en qué comunas atiendo | No recibir solicitudes de lugares a los que no viajo | NTI-05 | Alta |
| HU-14 | Maestro | Declarar mis días y bloques disponibles en formato de 24 horas | Recibir ofertas solo en horarios que me sirven | NTI-02 | Alta |
| HU-15 | Maestro | Recibir un ticket y aceptarlo o rechazarlo | Decidir si puedo llegar y si me conviene | NTI-02, NTI-03 | Alta |
| HU-16 | Maestro | Registrar el precio finalmente acordado y finalizar la orden | Dejar constancia de lo que se convino | NTI-04, NTI-03 | Alta |
| HU-17 | Maestro | Ver el estado y la vigencia de los documentos que entregué | Saber qué me falta y cuándo se me vence algo | NTI-01 | Media |
| HU-18 | Maestro | Evaluar al cliente después de un trabajo finalizado | Advertir a otros maestros sobre clientes problemáticos | NTI-06 | Baja |
| HU-19 | Administrador de curatoría | Revisar un expediente y aprobarlo, observarlo, rechazarlo o suspenderlo indicando el motivo | Que la decisión quede registrada y se pueda auditar | NTI-01, NTI-12 | Alta |
| HU-20 | Administrador comercial | Administrar oficios, servicios, modalidad de precio y precios de referencia | Mantener el catálogo alineado con el mercado local | NTI-05 | Media |
| HU-21 | Moderación | Revisar una evaluación denunciada y resolver la denuncia con la conversación de la orden a la vista | Resolver con antecedentes y no con la palabra de uno contra otro | NTI-06, NTI-08 | Media |
| HU-22 | Control de gestión | Consultar los indicadores base y exportar datos agregados de demanda y precios | Decidir dónde captar maestros y sostener el modelo de ingreso | NTI-10, NTI-07 | Media |
| HU-23 | Sistema | Cerrar automáticamente los tickets que no se resolvieron | Que el cliente no quede esperando ni el bloque quede retenido | NTI-02, NTI-03 | Media |
| HU-24 | Sistema | Desactivar los servicios regulados de un maestro cuando su licencia deja de estar vigente | Evitar que se ofrezca un trabajo que la ley no permite ejecutar | NTI-01 | Alta |
| HU-25 | Maestro | Que mis documentos, órdenes y conversaciones solo puedan ser vistos por mí y por roles autorizados para una finalidad concreta | Que mi cédula y mis conversaciones no queden expuestas a usuarios sin autorización | NTI-09 | Alta |

### 3.3. Objetivos y criterios de aceptación

Todas las historias tienen criterios que se pueden comprobar, y las que siguen son las que definen lo principal del funcionamiento, desarrolladas completas en esta sección

#### 3.3.1. HU-02 Filtros

| Campo | Contenido |
|---|---|
| Historia | Como cliente, quiero filtrar maestros por oficio, comuna y bloque horario, para ver solo a quienes efectivamente podrían tomar mi trabajo. |
| CA-02.1 | Dado que aplico un filtro de comuna, cuando se muestran los resultados, entonces ningún maestro que no declaró esa comuna en su cobertura aparece en la lista. |
| CA-02.2 | Dado que aplico un filtro de oficio, cuando el maestro tiene ese oficio pero su expediente no está aprobado, entonces no aparece en los resultados. |
| CA-02.3 | Dado que aplico un filtro de bloque horario, cuando el maestro no declaró ese bloque como disponible, entonces no aparece en la lista filtrada. |
| CA-02.4 | Dado que aplico varios filtros, cuando reviso los resultados, entonces todos cumplen simultáneamente las tres condiciones. |
| Reglas | Los filtros son excluyentes: eliminan por completo a quien no cumple. Ninguna combinación de filtros puede devolver un maestro que incumpla uno de ellos. La validación se ejecuta en el servidor, no en la interfaz. |

#### 3.3.2. HU-03 Ordenamiento de resultados

| Campo | Contenido |
|---|---|
| Historia | Como cliente, quiero que los resultados aparezcan ordenados dando prioridad a quien está disponible y luego a quien está cerca, para elegir sin revisar cincuenta perfiles. |
| CA-03.1 | Dado un conjunto de maestros que pasó los filtros, cuando se calcula el orden, entonces cada uno recibe un puntaje según la fórmula declarada y la lista se ordena de mayor a menor. |
| CA-03.2 | Dado que el cliente no aplicó filtro de horario, cuando un maestro tiene un bloque libre el mismo día en una comuna secundaria de su cobertura y otro pertenece a la comuna base pero solo tiene disponibilidad dentro de los tres días siguientes, entonces el primero aparece antes según la fórmula declarada. |
| CA-03.3 | Dado un empate en el puntaje, cuando se resuelve el orden, entonces se ubica primero el de mayor calificación promedio y, si persiste, el de mayor número de evaluaciones recibidas. |
| CA-03.4 | Dado que el cliente no aplicó filtro de horario, cuando se calcula la disponibilidad, entonces se evalúa sobre los próximos tres días, que es el horizonte que define la escala de disponibilidad. |
| Reglas | Fórmula del puntaje definida por el equipo y documentada para el cliente, si se aplica un filtro de bloque horario exacto todos los resultados que pasan el filtro reciben 100 en disponibilidad y el orden se resuelve con cercanía y los criterios de desempate. |

Puntaje = (0,6 × Disponibilidad) + (0,4 × Cercanía)

| Componente | Valor | Condición |
|---|---|---|
| Disponibilidad | 100 | Tiene libre el bloque horario exacto solicitado |
| Disponibilidad | 60 | Tiene libre otro bloque del mismo día |
| Disponibilidad | 30 | Tiene libre algún bloque dentro de los tres días siguientes |
| Disponibilidad | 0 | Sin bloques libres en el horizonte evaluado |
| Cercanía | 100 | La comuna solicitada es su comuna base |
| Cercanía | 60 | La comuna solicitada está en su cobertura declarada, pero no es la base |
| Cercanía | 0 | Fuera de cobertura, caso que el filtro ya descartó |

La disponibilidad pesa más a propósito porque hoy se pierde el 18% de los pedidos por demora en responder y un maestro cercano que no puede ir no le sirve al cliente, cuando el cliente no aplica un filtro horario un maestro con un bloque libre el mismo día en una comuna secundaria obtiene 60 puntos, mientras uno de la comuna base con disponibilidad solo dentro de los tres días siguientes obtiene 58, si el cliente aplica un bloque horario exacto el filtro elimina a quien no lo tiene disponible y los resultados que quedan reciben 100 en disponibilidad.

La fórmula queda escrita y a la vista del equipo de AlTiro, porque si un maestro reclama que no aparece en los resultados, alguien tiene que poder explicarle por qué.

#### 3.3.3. HU-04 Resultado vacío

| Campo | Contenido |
|---|---|
| Historia | Como cliente, quiero que se me avise cuando nadie cumple mis filtros y se me muestren alternativas cercanas, para no quedarme sin ninguna opción. |
| CA-04.1 | Dado que ningún maestro cumple los filtros aplicados, cuando se muestra la página, entonces aparece un mensaje explícito indicando que no hubo resultados con esos criterios. |
| CA-04.2 | Dado ese mismo caso, cuando se despliegan alternativas, entonces se presentan en una sección separada y rotulada como sugerencias fuera del filtro. |
| CA-04.3 | Dado que se muestran sugerencias, cuando el cliente las revisa, entonces cada tarjeta indica qué criterio no cumple. |
| Reglas | Las sugerencias nunca se mezclan con los resultados filtrados ni se presentan como si los cumplieran. Si tampoco hay sugerencias razonables, se muestra únicamente el mensaje. |

#### 3.3.4. HU-06 Envío del ticket de trabajo

| Campo | Contenido |
|---|---|
| Historia | Como cliente, quiero enviar un ticket a un maestro indicando qué necesito, dónde, a qué hora y si tengo los materiales, para que él decida con toda la información si puede tomarlo. |
| CA-06.1 | Dado que selecciono un maestro y un bloque de su agenda declarada, cuando envío el ticket con descripción, dirección y la casilla de materiales respondida, entonces queda registrado en estado pendiente y el maestro recibe el aviso. |
| CA-06.2 | Dado que el maestro aceptó otra oferta en ese bloque mientras yo completaba el formulario, cuando envío el ticket, entonces el sistema lo rechaza indicando que el bloque ya no está libre y ofrece los bloques vigentes. |
| CA-06.3 | Dado que envío un ticket, cuando reviso mi historial, entonces aparece con fecha, maestro, servicio, bloque solicitado, dirección, descripción y respuesta sobre materiales. |
| CA-06.4 | Dado que dejo vacía la descripción o no respondo la casilla de materiales, cuando intento enviar, entonces el sistema lo impide señalando qué falta. |
| Reglas | El ticket contiene servicio solicitado, descripción libre del trabajo, dirección exacta, bloque horario pedido y si el cliente dispone de los materiales, la dirección exacta y el teléfono permanecen ocultos para el maestro hasta que acepta y antes de eso solo ve la comuna, al crear el ticket se guarda también una copia de la modalidad de precio y del monto publicado, un ticket pendiente no ocupa el bloque y solo la aceptación lo hace. |

#### 3.3.5. HU-14 Declaración de disponibilidad

| Campo | Contenido |
|---|---|
| Historia | Como maestro, quiero declarar mis días y bloques disponibles en formato de 24 horas, para que los clientes me envíen ofertas en horarios que me sirven. |
| CA-14.1 | Dado que ingreso a mi agenda, cuando declaro un día y un rango horario, entonces se guarda en formato de 24 horas y se muestra así en todas las pantallas del sistema. |
| CA-14.2 | Dado que intento declarar un rango cuya hora de término es anterior o igual a la de inicio, cuando guardo, entonces el sistema lo rechaza con un mensaje comprensible. |
| CA-14.3 | Dado que acepté una oferta en un bloque, cuando un cliente consulta mi disponibilidad, entonces ese bloque aparece ocupado y no puede recibir otra oferta. |
| CA-14.4 | Dado que pierdo conexión mientras declaro mi agenda, cuando vuelvo a entrar, entonces los bloques ya guardados se conservan. |
| Reglas | La agenda declarada indica cuándo el maestro está dispuesto a recibir ofertas; no compromete su asistencia. El sistema no calcula tiempos de desplazamiento ni decide si el maestro alcanza a llegar: esa evaluación la hace él al recibir la oferta. La única validación automática es que un bloque ya aceptado no admite una segunda aceptación. |

#### 3.3.6. HU-15 Aceptación de la oferta

| Campo | Contenido |
|---|---|
| Historia | Como maestro, quiero recibir un ticket y aceptarlo o rechazarlo, para decidir si puedo llegar y si me conviene el trabajo. |
| CA-15.1 | Dado que recibo un ticket pendiente, cuando lo reviso, entonces veo el servicio, la descripción, la comuna, el bloque solicitado y si el cliente tiene los materiales. |
| CA-15.2 | Dado un ticket pendiente, cuando lo acepto, entonces el bloque queda ocupado, se revela la dirección exacta y se habilita la conversación privada con el cliente. |
| CA-15.3 | Dado un ticket pendiente, cuando lo rechazo, entonces el cliente recibe el aviso y el bloque permanece libre para otras ofertas. |
| CA-15.4 | Dado un ticket pendiente, cuando se cumple cualquiera de las condiciones de término, entonces pasa a estado cerrado con el motivo correspondiente y el cliente es notificado. |
| Reglas | La decisión de si alcanza a desplazarse hasta el lugar es del maestro, no del sistema, un ticket pasa de Pendiente a Aceptado cuando el maestro lo acepta y permanece en Aceptado hasta que se registra el precio final y la orden pasa a Finalizado, desde Pendiente puede terminar en Cerrado por rechazo del maestro, cancelación del cliente o vencimiento, cada cambio de estado se registra con estado anterior, estado nuevo, autor, fecha y motivo cuando corresponda. |

#### 3.3.7. HU-16 Registro del precio acordado

| Campo | Contenido |
|---|---|
| Historia | Como maestro, quiero registrar el precio finalmente acordado y finalizar la orden, para dejar constancia de lo que se convino. |
| CA-16.1 | Dado un trabajo ejecutado, cuando registro el monto final, entonces queda asociado a la orden junto con la fecha y el autor del registro. |
| CA-16.2 | Cuando la modalidad es por trabajo y el monto final difiere del monto guardado al crear el ticket, el sistema exige aceptación explícita del cliente, cuando la modalidad es por hora exige esa aceptación sobre el monto final antes de finalizar. |
| CA-16.3 | Dado que la orden queda Finalizada, cuando el cliente o el maestro consultan su historial, entonces ambos ven el mismo monto y no pueden modificarlo. |
| Reglas | Al crear el ticket se guarda una copia de la modalidad y del monto publicado, el precio acordado es inmutable una vez finalizada la orden y una corrección genera un nuevo registro con motivo en lugar de una sobreescritura. |

#### 3.3.8. HU-19 Resolución de expedientes

| Campo | Contenido |
|---|---|
| Historia | Como administrador de curatoría, quiero revisar un expediente y aprobarlo, observarlo, rechazarlo o suspenderlo indicando el motivo, para que la decisión quede registrada y se pueda auditar. |
| CA-19.1 | Dado un expediente en revisión, cuando cambio su estado, entonces el sistema exige un motivo escrito antes de guardar. |
| CA-19.2 | Dado un expediente de un oficio regulado sin licencia SEC cargada, cuando intento aprobarlo, entonces el sistema lo impide. |
| CA-19.3 | Dado cualquier cambio de estado, cuando reviso la bitácora, entonces figura el autor, la fecha, el estado anterior, el nuevo y el motivo. |
| CA-19.4 | Dado que un maestro intenta cambiar el estado de su propio expediente, cuando lo hace, entonces el sistema lo rechaza. |
| Reglas | Ningún maestro se auto aprueba. Los registros de la bitácora no se editan ni se eliminan. |

#### 3.3.9. HU-23 Cierre del ticket pendiente

| Campo | Contenido |
|---|---|
| Historia | Como sistema, quiero cerrar automáticamente los tickets que no se resolvieron, para que el cliente no quede esperando ni el bloque quede retenido sin motivo. |
| CA-23.1 | Dado un ticket pendiente, cuando transcurren 24 horas desde su envío, entonces se cierra por vencimiento de plazo. |
| CA-23.2 | Dado un ticket pendiente, cuando faltan 4 horas para el inicio del bloque solicitado, entonces se cierra por proximidad del horario. |
| CA-23.3 | Dado un ticket pendiente, cuando el cliente lo cierra, entonces queda cerrado por cancelación del cliente y no admite aceptación posterior. |
| CA-23.4 | Dado un ticket pendiente, cuando el maestro lo rechaza, entonces queda cerrado por rechazo del maestro y el bloque permanece libre. |
| CA-23.5 | Dado un ticket pendiente, cuando el maestro acepta otro ticket sobre el mismo bloque, entonces este queda cerrado por bloque tomado y el cliente es notificado con alternativas. |
| CA-23.6 | Dado un ticket que cumple más de una condición, cuando se evalúa el cierre, entonces se aplica la que ocurre primero, si dos condiciones automáticas coinciden exactamente se registra proximidad del horario como motivo. |
| CA-23.7 | Dado cualquier cierre, cuando se notifica, entonces ambas partes reciben el aviso indicando el motivo. |

Condiciones de término de un ticket pendiente. Cierra la primera que ocurra:

| Condición | Momento | Motivo registrado |
|---|---|---|
| Plazo de respuesta | 24 horas después del envío | Vencido por plazo |
| Proximidad del horario | 4 horas antes del inicio del bloque solicitado | Vencido por proximidad |
| Decisión del cliente | Cuando el cliente cierra el ticket | Cancelado por el cliente |
| Decisión del maestro | Cuando el maestro rechaza | Rechazado por el maestro |
| Bloque comprometido | Cuando el maestro acepta otro ticket para ese mismo bloque | Bloque tomado por otra aceptación |

Cerrar no es lo mismo que finalizar, los cinco motivos de arriba terminan un ticket que nunca llegó a ejecutarse y lo dejan en estado Cerrado con su motivo, mientras la orden que el maestro aceptó y ejecutó pasa a estado Finalizado al registrar el precio final descrito en HU-16, el historial de HU-08 distingue ambos casos.

Las dos condiciones automáticas se comparan por el momento en que ocurren, si el bloque comienza antes de 28 horas la regla de las 4 horas cierra primero, si comienza después cierra primero la regla de las 24 horas, si ambas coinciden exactamente a las 28 horas se registra proximidad del horario para mantener un criterio único.

Decisión del equipo: no se puede enviar un ticket para un bloque que comienza en 4 horas o menos porque el plazo de respuesta ya estaría vencido al momento de crearlo, el formulario oculta esos bloques y queda pendiente validar con la contraparte si conviene habilitar una vía distinta para urgencias.

#### 3.3.10. HU-24 Vencimiento de licencia

| Campo | Contenido |
|---|---|
| Historia | Como sistema, quiero desactivar los servicios regulados de un maestro cuando su licencia deja de estar vigente, para evitar que se ofrezca un trabajo que la ley no permite ejecutar. |
| CA-24.1 | Dado un documento con fecha de vencimiento registrada, cuando esa fecha se cumple, entonces los servicios del oficio regulado asociado quedan inactivos automáticamente. |
| CA-24.2 | Dado que faltan 30 días para el vencimiento, cuando el sistema ejecuta la revisión diaria, entonces avisa al maestro y al administrador de curatoría. |
| CA-24.3 | Dado un documento sin fecha de vencimiento por ser de vigencia indefinida, cuando se ejecuta la revisión, entonces no se desactiva ningún servicio por esa causa. |
| CA-24.4 | Dado un servicio desactivado por vencimiento, cuando un cliente busca ese oficio, entonces el maestro no aparece para ese servicio, aunque sí para sus oficios no regulados. |
| Reglas | La distinción entre documentos con y sin vencimiento es obligatoria: las licencias de instalador de la SEC son indefinidas salvo las obtenidas por certificación de competencias laborales, que se renuevan cada cinco años. |

#### 3.3.11. HU-25 Privacidad

| Campo | Contenido |
|---|---|
| Historia | Como maestro, quiero que mis documentos, órdenes y conversaciones solo puedan ser consultados por mí y por roles autorizados para una finalidad concreta, para que mis datos no queden expuestos a usuarios sin autorización. |
| CA-25.1 | Dado que estoy autenticado, cuando intento acceder a una orden que no es mía cambiando el número de registro en la dirección web, entonces el sistema deniega el acceso. |
| CA-25.2 | Dado que soy un cliente autenticado, cuando intento abrir el documento de identidad de un maestro, entonces el sistema deniega el acceso. |
| CA-25.3 | Dado un intento de acceso denegado, cuando se registra el evento, entonces queda en la bitácora con usuario, recurso y fecha. |
| Reglas | La autorización verifica propiedad del recurso o una función administrativa justificada, no solo el rol, curatoría puede revisar documentos por su función y moderación puede revisar una conversación solo con una disputa abierta, cualquier otro acceso se deniega y queda registrado. |

#### 3.3.12. Criterios de aceptación complementarios

| Historia | Criterio | Contenido |
|---|---|---|
| HU-01 | CA-01.1 | Dado que me registro, cuando dejo la comuna sin seleccionar, entonces el sistema impide guardar e indica que la comuna es obligatoria. |
| HU-01 | CA-01.2 | Dado que selecciono una región, cuando abro el listado de comunas, entonces solo aparecen las comunas de esa región según la división político-administrativa oficial. |
| HU-05 | CA-05.1 | Dado un maestro con expediente aprobado, cuando abro su ficha, entonces veo su calificación en puntualidad, trabajo y cordialidad por separado, los comentarios recibidos, sus precios por servicio y sus bloques libres y ocupados. |
| HU-05 | CA-05.2 | Dado un maestro sin evaluaciones, cuando abro su ficha, entonces el sistema indica que todavía no tiene evaluaciones en lugar de mostrar un promedio en cero. |
| HU-08 | CA-08.1 | Dado que consulto mi historial, cuando reviso una orden finalizada, entonces veo la fecha, el maestro, el servicio, el estado y el precio final registrado. |
| HU-08 | CA-08.2 | Dado un ticket cerrado sin ejecutarse, cuando aparece en mi historial, entonces se distingue del finalizado e indica el motivo de cierre. |
| HU-10 | CA-10.1 | Dado un ticket que envié y sigue pendiente, cuando lo cancelo, entonces queda cerrado por cancelación del cliente y el maestro recibe el aviso. |
| HU-10 | CA-10.2 | Dado un ticket que el maestro ya aceptó, cuando intento cancelarlo, entonces el sistema lo impide y me indica que debo coordinarlo por la conversación de la orden. |
| HU-11 | CA-11.1 | Dado que postulo desde el teléfono, cuando completo un paso y pierdo la conexión, entonces al volver a entrar los pasos ya guardados se conservan. |
| HU-11 | CA-11.2 | Dado que cargo una fotografía de un documento, cuando indico su tipo y su fecha de emisión, entonces la fecha de vencimiento queda como campo opcional. |
| HU-11 | CA-11.3 | Dado que ingreso un RUT ya registrado, cuando intento continuar, entonces el sistema lo rechaza indicando que ese RUT ya tiene una postulación. |
| HU-12 | CA-12.1 | Dado que declaro un servicio, cuando no indico modalidad de precio o monto, entonces el sistema no lo publica y señala qué falta. |
| HU-12 | CA-12.2 | Dado un servicio de un oficio regulado, cuando no tengo licencia vigente cargada, entonces el servicio no queda visible para los clientes. |
| HU-13 | CA-13.1 | Dado que declaro mis comunas de cobertura, cuando no marco ninguna como comuna base, entonces el sistema no me deja guardar. |
| HU-13 | CA-13.2 | Dado que quito una comuna de mi cobertura, cuando un cliente filtra por esa comuna, entonces dejo de aparecer en sus resultados. |
| HU-17 | CA-17.1 | Dado que consulto mis documentos, cuando reviso cada uno, entonces veo su estado y, si tiene vencimiento, los días que le quedan. |
| HU-17 | CA-17.2 | Dado un documento observado por curatoría, cuando lo reviso, entonces veo el motivo escrito de la observación. |
| HU-20 | CA-20.1 | Dado que agrego un servicio al catálogo, cuando lo guardo, entonces queda disponible para que los maestros lo declaren sin intervención en el código. |
| HU-20 | CA-20.2 | Dado que modifico un precio de referencia, cuando un visitante consulta el catálogo, entonces ve el valor actualizado. |
| HU-07 | CA-07.1 | Dado que un ticket fue aceptado, cuando cliente y maestro acceden a la conversación, entonces ambos pueden enviar y recibir mensajes asociados a ese ticket. |
| HU-07 | CA-07.2 | Dado que un mensaje fue enviado, cuando cualquiera de las partes consulta la conversación, entonces el mensaje aparece asociado al ticket correspondiente. |
| HU-07 | CA-07.3 | Dado que el ticket quedó Cerrado o la orden quedó Finalizada, cuando cualquiera de las partes consulta su historial, entonces puede visualizar la conversación asociada. |
| HU-09 | CA-09.1 | Dada una orden Finalizada, cuando el cliente evalúa al maestro, entonces puede registrar una calificación en puntualidad, trabajo y cordialidad. |
| HU-09 | CA-09.2 | Dado que el cliente ya evaluó ese ticket, cuando intenta evaluarlo nuevamente, entonces el sistema rechaza la segunda evaluación. |
| HU-18 | CA-18.1 | Dada una orden Finalizada, cuando el maestro decide evaluar al cliente, entonces puede registrar su evaluación una sola vez para esa orden. |
| HU-21 | CA-21.1 | Dada una evaluación denunciada, cuando el moderador la revisa, entonces puede consultar la conversación asociada al ticket. |
| HU-21 | CA-21.2 | Dada una denuncia revisada, cuando el moderador resuelve el caso, entonces el sistema registra la decisión, el autor y el motivo. |
| HU-22 | CA-22.1 | Dado que existen datos suficientes para calcular los indicadores, cuando el usuario de control de gestión consulta el panel, entonces se muestran los tres indicadores base definidos para el proyecto. |
| HU-22 | CA-22.2 | Dado que el usuario exporta información, cuando se genera el archivo, entonces este no contiene identificadores personales directos. |

### 3.4. Adaptación al negocio y a los usuarios finales

Las historias anteriores no son reutilizables en otra organización sin cambios, y lo que sigue identifica qué particularidad de AlTiro condiciona cada una y qué ajuste concreto produjo.

| Historia | Particularidad del negocio o del usuario | Ajuste realizado |
|---|---|---|
| HU-01, HU-13 | La división territorial chilena reconoce región, provincia y comuna, y la cobertura de AlTiro se define por comuna dentro del Gran Concepción | La ubicación se captura y se filtra por comuna, no por dirección libre ni por radio en kilómetros |
| HU-03 | El 18% de la demanda se pierde por demora en responder | La disponibilidad pesa 0,6 y la cercanía 0,4 cuando no hay filtro horario, si se aplica un bloque exacto el filtro elimina primero a quien no lo tiene disponible y el orden se resuelve entre quienes sí cumplen. |
| HU-04 | La red tiene 63 maestros en ocho oficios y seis comunas; hay combinaciones sin cobertura | Se diseñó una respuesta explícita para el resultado vacío en vez de una lista en blanco |
| HU-05, HU-09 | La evaluación se define sobre tres dimensiones: puntualidad, trabajo y cordialidad | La calificación visible es el promedio de esas tres y no una sola estrella agregada |
| HU-06, HU-07 | La confianza es el producto que vende la empresa, y el cliente entrega su dirección a un desconocido | El maestro ve la comuna mientras evalúa el ticket, la dirección exacta y el teléfono se revelan solo al aceptar y la conversación queda asociada a la orden. |
| HU-06 | En oficios de reparación es habitual que el cliente ya tenga los materiales o que el maestro deba llevarlos, y eso cambia el precio y el tiempo | El ticket incluye una casilla obligatoria que declara si el cliente dispone de los materiales |
| HU-11, HU-14, HU-17 | El 91% de los maestros usa exclusivamente teléfono móvil y varios no tienen correo activo | Postulación dividida en pasos cortos, carga de documentos por fotografía, teléfono como identificador de contacto obligatorio y correo opcional |
| HU-12, HU-16 | El precio se acuerda de palabra en terreno y puede cambiar respecto de lo publicado cuando el maestro ve el trabajo en persona, y hoy el 11% de los reclamos no tiene evidencia con que resolverse | El ticket conserva una copia de la modalidad y del monto publicado, si el precio es por trabajo el cliente acepta cuando el monto final cambia, si es por hora acepta siempre el monto final antes de finalizar la orden. |
| HU-14 | Los maestros manejan su día en horas corridas y no en formatos de 12 horas con AM/PM | Declaración y despliegue en formato de 24 horas en todo el sistema |
| HU-14, HU-15 | El maestro es un prestador independiente que conoce sus tiempos de desplazamiento mejor que cualquier cálculo automático | El sistema no valida si alcanza a llegar: le entrega la información del ticket y él decide. La única regla automática es que un bloque aceptado no admite otra aceptación |
| HU-19, HU-24 | Gas y electricidad son oficios regulados por la SEC, y sus licencias pueden ser indefinidas o renovables cada cinco años | El expediente exige licencia vigente para aprobar oficios regulados y el modelo admite documentos con y sin fecha de vencimiento |
| HU-25 | El sistema custodia cédulas de identidad y certificados de antecedentes de 63 personas | La autorización se verifica por propiedad del recurso y los intentos denegados quedan registrados |
| Todas | Conexión intermitente en terreno y equipos de gama de entrada | Formularios que conservan lo ya guardado y mensajes de error comprensibles sin vocabulario técnico |

## 4. Requerimientos del software

### 4.1. Entorno base simulado

Los umbrales que siguen se miden contra el entorno de la prueba de concepto descrito a continuación, y no contra el de una eventual puesta en producción.

| Aspecto | Definición para esta etapa |
|---|---|
| Despliegue | Contenedores Docker orquestados con Docker Compose, ejecutados en un equipo del equipo de desarrollo |
| Equipo de referencia | PC de laboratorio INACAP |
| Persistencia | Motor relacional en contenedor, con volumen local; sin servicios de nube pagados |
| Tecnologías | Backend en Python, interfaz en HTML, CSS y JavaScript |
| Volumen de prueba | 100 maestros, 300 servicios publicados, 1.000 tickets y 5.000 mensajes |
| Concurrencia objetivo | 10 usuarios simultáneos |
| Red de referencia del cliente | Conexión móvil, emulada con limitación de ancho de banda en el navegador |

Estos valores corresponden a supuestos del equipo y reproducen la escala real del negocio con margen, ya que AlTiro tiene 63 maestros y se satura a los 12 trabajos diarios, de modo que 100 maestros y 1.000 tickets permiten probar una carga superior a la operación actual y representan aproximadamente tres meses de actividad al nivel de saturación.

Para ordenar los requerimientos no funcionales se usó la norma ISO/IEC 25010:2023, que agrupa la calidad de un software en nueve características, es decir adecuación funcional, eficiencia de desempeño, compatibilidad, capacidad de interacción, fiabilidad, seguridad, mantenibilidad, flexibilidad y seguridad operacional (Safety), y en esta edición de 2023 la clasificación usa las denominaciones capacidad de interacción, flexibilidad y seguridad operacional para estas áreas de calidad.

### 4.2. Requerimientos funcionales y no funcionales

#### 4.2.1. Requerimientos funcionales

| ID | Descripción verificable | Fuente | Prioridad | Criterio de verificación | Estado |
|---|---|---|---|---|---|
| RF-01 | El sistema debe permitir el registro de un cliente con nombre, teléfono, correo y ubicación expresada como región, provincia y comuna | HU-01 | Alta | El registro falla si falta comuna; la comuna proviene de una lista cerrada | Propuesto |
| RF-02 | El sistema debe autenticar usuarios mediante credenciales y permitir el cierre de sesión | HU-01, HU-25 | Alta | Un usuario no autenticado no accede a ninguna vista privada | Propuesto |
| RF-03 | El sistema debe permitir al maestro postular en pasos, registrando RUT, nombres y teléfono | HU-11 | Alta | El RUT se valida con su dígito verificador y es único | Propuesto |
| RF-04 | El sistema debe permitir cargar documentos como fotografía, indicando tipo, fecha de emisión y, opcionalmente, fecha de vencimiento | HU-11 | Alta | Un documento sin vencimiento se guarda y no genera alertas de expiración | Propuesto |
| RF-05 | El sistema debe permitir al maestro declarar sus servicios con modalidad de precio por trabajo o por hora y su monto | HU-12 | Alta | Cada servicio publicado tiene modalidad y monto; no se publica sin ambos | Propuesto |
| RF-06 | El sistema debe permitir al maestro declarar sus comunas de cobertura e identificar una como comuna base | HU-13 | Alta | Un maestro sin comuna base no aparece en resultados | Propuesto |
| RF-07 | El sistema debe permitir al maestro declarar días y bloques disponibles en formato de 24 horas | HU-14 | Alta | Se rechaza un rango cuya hora de término no sea posterior a la de inicio | Propuesto |
| RF-08 | El sistema debe mostrar al maestro el estado y la vigencia de cada documento que entregó | HU-17 | Media | Cada documento muestra estado y, si corresponde, días restantes | Propuesto |
| RF-09 | El sistema debe filtrar los resultados de búsqueda por oficio, comuna y bloque horario de forma excluyente | HU-02 | Alta | Ningún resultado incumple alguno de los filtros aplicados | Propuesto |
| RF-10 | El sistema debe calcular un puntaje por maestro y ordenar los resultados de mayor a menor | HU-03 | Alta | El puntaje corresponde a 0,6 × disponibilidad + 0,4 × cercanía según la escala definida | Propuesto |
| RF-11 | El sistema debe resolver empates de puntaje por calificación promedio y luego por cantidad de evaluaciones | HU-03 | Media | Dos maestros con igual puntaje se ordenan por el criterio declarado | Propuesto |
| RF-12 | El sistema debe informar explícitamente cuando ningún maestro cumple los filtros y mostrar sugerencias en una sección separada | HU-04 | Media | Las sugerencias aparecen rotuladas y cada una indica qué criterio incumple | Propuesto |
| RF-13 | El sistema debe presentar cada resultado como una tarjeta con fotografía, nombre, calificación promedio y oficio | HU-03, HU-05 | Alta | Los cuatro elementos están presentes en cada tarjeta | Propuesto |
| RF-14 | El sistema debe mostrar la ficha del maestro con calificación por dimensión, comentarios, precios, bloques libres y bloques ocupados | HU-05 | Alta | La ficha distingue visualmente bloques libres de ocupados | Propuesto |
| RF-15 | El sistema debe permitir crear un ticket con servicio, descripción, dirección, bloque horario y declaración de materiales, además debe guardar la modalidad de precio y el monto publicados al momento del envío | HU-06 | Alta | El envío falla si falta descripción, dirección o respuesta sobre materiales, y el ticket conserva modalidad y monto aunque el maestro cambie su publicación después | Propuesto |
| RF-16 | El sistema debe impedir la creación de un ticket para un bloque que comience en 4 horas o menos | HU-06, HU-23 | Alta | Esos bloques no se ofrecen en el formulario | Propuesto |
| RF-17 | El sistema debe ocultar al maestro la dirección exacta y el teléfono del cliente mientras el ticket esté pendiente, mostrando solo la comuna | HU-06, HU-25 | Alta | La respuesta del servidor no contiene esos campos en estado pendiente | Propuesto |
| RF-18 | El sistema debe notificar al maestro la llegada de un ticket nuevo | HU-06 | Alta | La notificación se emite al crear el ticket | Propuesto |
| RF-19 | El sistema debe permitir al maestro aceptar un ticket, pasando la orden a estado Aceptado, ocupando el bloque, cerrando los demás tickets pendientes sobre ese mismo bloque y revelando los datos de contacto | HU-15 | Alta | Tras aceptar, el bloque no admite otro ticket y el contacto queda visible | Propuesto |
| RF-20 | El sistema debe permitir al maestro rechazar un ticket, dejando el bloque libre | HU-15 | Alta | El bloque vuelve a ofrecerse a otros clientes | Propuesto |
| RF-21 | El sistema debe cerrar automáticamente un ticket pendiente al cumplirse 24 horas desde su envío | HU-23 | Alta | El cierre ocurre en la ejecución programada siguiente al vencimiento | Propuesto |
| RF-22 | El sistema debe cerrar automáticamente un ticket pendiente cuando falten 4 horas para el inicio del bloque solicitado | HU-23 | Alta | Para bloques a menos de 28 horas esta condición ocurre antes que RF-21, a las 28 horas exactas ambas coinciden y se registra proximidad del horario | Propuesto |
| RF-23 | El sistema debe permitir al cliente cerrar un ticket pendiente | HU-10, HU-23 | Media | Un ticket cerrado por el cliente no admite aceptación posterior | Propuesto |
| RF-24 | El sistema debe registrar el motivo de cierre de cada ticket y notificar a ambas partes | HU-23 | Alta | Los cinco motivos de cierre en estado pendiente se registran de forma distinguible | Propuesto |
| RF-25 | El sistema debe habilitar un canal de mensajería privado asociado al ticket aceptado, conservando el historial | HU-07 | Media | Los mensajes quedan vinculados al ticket y son recuperables tras el cierre o la finalización | Propuesto |
| RF-26 | El sistema debe permitir registrar el precio final acordado y pasar la orden a estado Finalizado una vez ejecutado el trabajo | HU-16 | Alta | El monto queda asociado al ticket con fecha y autor | Propuesto |
| RF-27 | El sistema debe exigir aceptación explícita del cliente cuando el precio final de una modalidad por trabajo difiera del monto guardado al crear el ticket, y siempre sobre el monto final cuando la modalidad sea por hora | HU-16 | Alta | La finalización se bloquea hasta que exista la aceptación requerida según la modalidad de precio | Propuesto |
| RF-28 | El sistema debe mostrar al cliente el historial de sus tickets con estado, fecha y precio acordado | HU-08 | Alta | El historial incluye los tickets cerrados por cualquiera de los cinco motivos y las órdenes finalizadas con precio registrado | Propuesto |
| RF-29 | El sistema debe permitir evaluar en puntualidad, trabajo y cordialidad, una vez por parte y por orden Finalizada | HU-09, HU-18 | Media | Un segundo intento de evaluación sobre la misma orden se rechaza | Propuesto |
| RF-30 | El sistema debe calcular y mostrar la calificación promedio del maestro a partir de las tres dimensiones | HU-05, HU-09 | Media | El promedio mostrado coincide con el cálculo sobre las evaluaciones publicadas | Propuesto |
| RF-31 | El sistema debe permitir denunciar una evaluación y resolverla desde moderación con la conversación del ticket a la vista | HU-21 | Media | La resolución queda registrada con autor y motivo | Propuesto |
| RF-32 | El sistema debe permitir al administrador de curatoría cambiar el estado de un expediente exigiendo un motivo escrito | HU-19 | Alta | No se guarda un cambio de estado sin motivo | Propuesto |
| RF-33 | El sistema debe impedir aprobar un oficio regulado si no hay licencia SEC cargada y vigente | HU-19, HU-24 | Alta | El intento de aprobación se rechaza con mensaje explícito | Propuesto |
| RF-34 | El sistema debe desactivar automáticamente los servicios de oficios regulados cuando la licencia asociada deja de estar vigente | HU-24 | Alta | El maestro deja de aparecer en ese oficio y sigue apareciendo en los no regulados | Propuesto |
| RF-35 | El sistema debe avisar al maestro y al administrador 30 días antes del vencimiento de un documento | HU-24 | Media | El aviso se emite una vez alcanzado el umbral | Propuesto |
| RF-36 | El sistema debe permitir administrar el catálogo de oficios, servicios, modalidad de precio y precios de referencia | HU-20 | Media | Un servicio nuevo queda disponible para los maestros sin intervención en el código | Propuesto |
| RF-37 | El sistema debe registrar en bitácora toda acción administrativa sobre expedientes, evaluaciones y catálogo | HU-19, HU-25 | Alta | Cada entrada contiene autor, acción, entidad, valores anterior y nuevo, motivo y fecha | Propuesto |
| RF-38 | El sistema debe presentar los tres indicadores base y permitir exportar datos agregados sin identificadores personales | HU-22 | Media | El archivo exportado no contiene RUT, nombre, teléfono ni dirección | Propuesto |

#### 4.2.2. Requerimientos no funcionales

| ID | Característica ISO 25010:2023 | Descripción verificable | Fuente | Prioridad | Umbral medible | Estado |
|---|---|---|---|---|---|---|
| RNF-01 | Eficiencia de desempeño · comportamiento temporal | La búsqueda con filtros y ordenamiento debe responder en menos de 2 segundos casi siempre | NTI-05 | Alta | Al menos 19 de cada 20 búsquedas responden en 2 segundos o menos, con 100 maestros, 1.000 tickets y 10 personas usando el sistema a la vez | Propuesto |
| RNF-02 | Eficiencia de desempeño · comportamiento temporal | La página de resultados debe quedar utilizable en menos de 3 segundos sobre conexión móvil limitada | NTI-11 | Alta | 3 segundos o menos con una conexión móvil de 4 Mbps, y la primera pantalla no debe pesar más de 1,5 MB | Propuesto |
| RNF-03 | Eficiencia de desempeño · capacidad | El sistema debe sostener el volumen de prueba sin degradar RNF-01 | NTI-03 | Media | 100 maestros, 1.000 tickets y 5.000 mensajes | Propuesto |
| RNF-04 | Eficiencia de desempeño · utilización de recursos | La pila completa debe operar dentro de los recursos del equipo de referencia | Restricción del equipo | Media | No más de 2 GB de memoria para todo el sistema | Propuesto |
| RNF-05 | Seguridad · confidencialidad | Las contraseñas nunca deben guardarse tal como se escriben | NTI-09 | Alta | Ninguna contraseña se puede recuperar desde la base de datos, porque se almacena mediante un hash adaptativo diseñado para resistir ataques | Propuesto |
| RNF-06 | Seguridad · confidencialidad | Los documentos de identidad no deben poder abrirse escribiendo su dirección en el navegador | NTI-09, NTI-01 | Alta | Guardados fuera de las carpetas accesibles desde internet y entregados con un enlace que caduca a los 10 minutos | Propuesto |
| RNF-07 | Seguridad · integridad | Toda operación sobre un recurso debe verificar propiedad en el servidor, no solo el rol | NTI-09 | Alta | cada pantalla o función que recibe un número de registro tiene una prueba automática que confirma que un tercero no puede abrirla | Propuesto |
| RNF-08 | Seguridad · confidencialidad | El teléfono y la dirección exacta no deben enviarse al dispositivo del maestro mientras el ticket siga pendiente | NTI-09 | Alta | Esos datos no se envían al dispositivo del maestro, y se comprueba revisando lo que el servidor manda y no lo que la pantalla muestra | Propuesto |
| RNF-09 | Seguridad · autenticidad | La sesión debe expirar por inactividad y exigir reautenticación para operaciones sensibles | NTI-09 | Media | Expiración a los 30 minutos; Reautenticación al cambiar contraseña o correo | Propuesto |
| RNF-10 | Seguridad · resistencia | El sistema debe limitar los intentos fallidos de autenticación | NTI-09 | Media | Bloqueo temporal tras 5 intentos fallidos en 15 minutos desde el mismo lugar | Propuesto |
| RNF-11 | Seguridad · integridad | La bitácora debe ser de solo escritura | NTI-12 | Alta | El sistema no ofrece ninguna forma de editar ni borrar una entrada de la bitácora | Propuesto |
| RNF-12 | Seguridad · confidencialidad | Los datos deben viajar cifrados entre el teléfono y el servidor | NTI-09 | Alta | Conexión cifrada obligatoria, y en la demostración local con un certificado propio declarado como tal | Propuesto |
| RNF-13 | Capacidad de interacción · aprendizaje | Un maestro sin experiencia previa debe completar su postulación sin ayuda | NTI-11 | Alta | Al menos 2 de 3 participantes de prueba la completan en ≤ 10 minutos | Propuesto |
| RNF-14 | Capacidad de interacción · operabilidad | La interfaz debe ser operable con el pulgar en un teléfono | NTI-11 | Alta | Botones de al menos 44 por 44 puntos y formularios divididos en pasos de máximo 5 campos | Propuesto |
| RNF-15 | Capacidad de interacción · protección contra errores del usuario | Todo mensaje de error debe indicar el campo afectado y la acción correctiva | NTI-11 | Alta | Ningún mensaje muestra códigos internos ni texto de programador, y se revisa en todos los formularios | Propuesto |
| RNF-16 | Capacidad de interacción · inclusividad | El contraste y la codificación de estados deben cumplir criterios de accesibilidad | NTI-11 | Alta | Contraste suficiente entre texto y fondo según la guía de accesibilidad WCAG 2.2, y ningún estado indicado solo con color | Propuesto |
| RNF-17 | Capacidad de interacción · autodescripción | El vocabulario debe ser el del oficio y no el del sistema | NTI-11 | Media | Revisión de terminología sobre todas las vistas del maestro; sin siglas técnicas ni jerga de desarrollo | Propuesto |
| RNF-18 | Compatibilidad · coexistencia | La interfaz debe operar en navegadores móviles y de escritorio vigentes | NTI-11 | Media | Las dos últimas versiones de Chrome y Firefox, y Chrome en Android, sin que haya que desplazar la pantalla de lado en celulares angostos | Propuesto |
| RNF-19 | Fiabilidad · recuperabilidad | El sistema debe contar con respaldo y restauración verificada | NTI-03 | Alta | Respaldo diario automatizado, retención de 7 días y restauración completa probada en ≤ 30 minutos | Propuesto |
| RNF-20 | Fiabilidad · tolerancia a fallos | La pérdida de conexión durante un formulario por pasos no debe descartar lo ya guardado | NTI-11 | Media | Los pasos completados se conservan al reingresar | Propuesto |
| RNF-21 | Mantenibilidad · capacidad de prueba | Las reglas de negocio críticas deben estar cubiertas por pruebas automatizadas | NTI-03 | Alta | Al menos el 60% de las reglas de filtros, puntaje, cierre de tickets y control de acceso cubiertas por pruebas automáticas | Propuesto |
| RNF-22 | Mantenibilidad · analizabilidad | El sistema debe registrar eventos de aplicación con información suficiente para diagnóstico | NTI-12 | Media | Cada entrada incluye nivel, marca de tiempo, usuario y operación | Propuesto |
| RNF-23 | Flexibilidad · instalabilidad | El sistema debe levantarse completo en un equipo limpio con un solo comando | Restricción del equipo | Alta | Un solo comando deja el sistema andando en 10 minutos o menos, con las instrucciones escritas junto al código | Propuesto |
| RNF-24 | Flexibilidad · escalabilidad | La configuración no debe estar embebida en el código | Restricción del equipo | Media | Contraseñas, rutas y ajustes guardados fuera del código, de modo que cambiar de servidor no obligue a reprogramar | Propuesto |
| RNF-25 | Seguridad operacional (Safety) · advertencia de riesgo | El sistema debe impedir la oferta de servicios de oficios regulados sin habilitación vigente | NTI-01 | Alta | Ningún servicio de gas o electricidad queda visible sin licencia vigente asociada | Propuesto |
| RNF-26 | Seguridad · confidencialidad | Los documentos de identidad deben eliminarse al cumplirse el plazo de retención definido para cada tipo | NTI-09 | Media | Existe un plazo escrito por tipo de documento y cada eliminación queda registrada en la bitácora con fecha y motivo | Propuesto |
| RNF-27 | Seguridad · integridad | Las dependencias externas deben estar fijadas en una versión concreta y revisadas ante avisos de seguridad | NTI-09 | Media | Cada librería queda declarada con versión exacta y hay una revisión de avisos registrada al inicio de cada sprint | Propuesto |

#### 4.2.3. Requerimiento explícitamente no comprometido

No se establece un objetivo de disponibilidad, porque en una prueba de concepto que corre en el computador de uno de los integrantes, comprometer un porcentaje sería una cifra sin respaldo, y se prefiere declarar la ausencia antes que inventar un valor.

### 4.3. Ejemplos y relevancia de cada tipo de requerimiento

#### 4.3.1. RF-17 Enmascaramiento de la dirección

También es funcional, aunque parezca una medida de seguridad, porque describe qué información muestra el sistema en cada estado del ticket, mientras su contraparte no funcional es RNF-08, que fija cómo se comprueba, RF-17 indica que el maestro ve la comuna antes de aceptar y RNF-08 exige que la dirección exacta ni siquiera se envíe al teléfono del maestro, porque un sistema puede esconder el dato en la pantalla y mandarlo igual, quedando a la vista de cualquiera que sepa dónde mirar.

#### 4.3.2. RNF-01 Tiempo de respuesta de la búsqueda

Es no funcional porque no agrega una función nueva, ya que la búsqueda existe como RF-09 y RF-10 y acá solo se le pone una exigencia de calidad, que es responder en menos de 2 segundos en al menos diecinueve de cada veinte búsquedas con diez personas usando el sistema a la vez, un límite elegido porque bajo ese tiempo la espera pasa desapercibida y sobre él la persona empieza a dudar si su clic funcionó, y se mide revisando todos los tiempos y no el promedio, porque el promedio esconde justamente las búsquedas lentas que el usuario recuerda.

Importa para el negocio porque la búsqueda es la primera pantalla que ve un cliente con un problema urgente, y si demora termina volviendo a los grupos vecinales de siempre.

#### 4.3.3. RNF-13 Tiempo de postulación de un maestro

Este es el requerimiento que más discute la viabilidad del negocio y el que más cuesta redactar bien, porque decir que el sistema debe ser fácil de usar no es verificable, mientras que decir que dos de cada tres maestros de prueba completan la postulación sin ayuda en menos de diez minutos sí lo es y además se puede ejecutar con tres personas y un cronómetro.

Corresponde a la capacidad de interacción en la norma ISO/IEC 25010:2023, y el riesgo que reduce amenaza al proyecto entero, porque si el 91% de los maestros usa solo el celular y registrarse exige un computador o media hora de paciencia, no entra nadie a la red y el resto del sistema queda vacío.

#### 4.3.4. RNF-25 Bloqueo de oficios regulados sin habilitación

Se clasifica bajo seguridad operacional (Safety), una de las características del modelo ISO/IEC 25010:2023, porque este requerimiento busca evitar una consecuencia física derivada de que un servicio regulado sea ofrecido sin habilitación vigente. A diferencia de los requerimientos centrados en confidencialidad e integridad de la información, aquí el resultado que se busca prevenir es un riesgo físico para las personas.

### 4.4. Trazabilidad con necesidades y objetivos del negocio

#### 4.4.1. Objetivos del Proyecto

| ID | Objetivo |
|---|---|
| OBJ-01 | Garantizar que todo maestro visible en la plataforma esté verificado y habilitado para el oficio que ofrece |
| OBJ-02 | Reducir el tiempo entre la solicitud del cliente y la respuesta del maestro |
| OBJ-03 | Dejar registro trazable de cada trabajo solicitado y del precio acordado |
| OBJ-04 | Proteger los datos personales de clientes y maestros |
| OBJ-05 | Generar información agregada de demanda, precios y cobertura explotable comercialmente |

#### 4.4.2. Matriz de trazabilidad

| Necesidad | Objetivo | Historia | Requerimientos | Criterio | Cobertura | Justificación |
|---|---|---|---|---|---|---|
| NTI-01 | OBJ-01 | HU-11, HU-17, HU-19, HU-24 | RF-03, RF-04, RF-08, RF-32, RF-33, RF-34, RF-35, RNF-06, RNF-25 | CA-11.1 a CA-11.3, CA-17.1 a CA-17.2, CA-19.1 a CA-19.4 y CA-24.1 a CA-24.4 | Total comprometida | La verificación cubre carga, revisión, estado, vigencia y desactivación automática |
| NTI-02 | OBJ-02 | HU-14, HU-15, HU-23 | RF-07, RF-16, RF-18, RF-19, RF-20, RF-21, RF-22, RF-24 | CA-14.1 a CA-14.4, CA-15.1 a CA-15.4, CA-23.1 a CA-23.7 | Total comprometida | La disponibilidad pasa de dato telefónico a dato declarado y consultable, con la salvedad de que declarar un bloque no compromete la asistencia del maestro |
| NTI-03 | OBJ-03 | HU-06, HU-08, HU-10, HU-16 | RF-15, RF-23, RF-26, RF-28, RNF-03, RNF-19, RNF-21 | CA-06.1 a CA-06.4, CA-08.1 a CA-08.2, CA-10.1 a CA-10.2 y CA-16.1 a CA-16.3 | Total comprometida | Cada ticket conserva su historia completa y es recuperable por ambas partes |
| NTI-04 | OBJ-03 | HU-12, HU-16 | RF-05, RF-26, RF-27 | CA-12.1 y CA-16.1 a CA-16.3 | Total comprometida | El ticket conserva la modalidad y el monto publicado, el precio final queda registrado y la aceptación del cliente se exige según la modalidad |
| NTI-05 | OBJ-02 | HU-02, HU-03, HU-04, HU-05, HU-13, HU-20 | RF-06, RF-09, RF-10, RF-11, RF-12, RF-13, RF-14, RF-36, RNF-01, RNF-02 | CA-02.1 a CA-02.4, CA-03.1 a CA-03.4, CA-04.1 a CA-04.3, CA-05.1 a CA-05.2, CA-13.1 a CA-13.2 y CA-20.1 a CA-20.2 | Parcial comprometida | El filtro, el ordenamiento y la ficha del maestro quedan comprometidos, la respuesta al resultado vacío y el catálogo administrable quedan condicionados a capacidad |
| NTI-06 | OBJ-03 | HU-09, HU-18, HU-21 | RF-29, RF-30, RF-31 | CA-09.1 a CA-09.2, CA-18.1, CA-21.1 a CA-21.2 | Condicionada | La reputación tiene historias y requisitos definidos, pero su implementación queda condicionada a capacidad y además depende de que las partes evalúen |
| NTI-07 | OBJ-05 | HU-22 | RF-38 | CA-22.1 a CA-22.2 | Condicionada | La exportación agregada está definida, su implementación queda condicionada a capacidad y la venta de la información excede el alcance del sistema |
| NTI-08 | OBJ-03 | HU-07 | RF-25 | CA-07.1 a CA-07.3 | Condicionada | La conversación queda definida y asociada al ticket, pero su implementación queda condicionada a capacidad |
| NTI-09 | OBJ-04 | HU-01, HU-25 | RF-01, RF-02, RF-17, RNF-05 a RNF-12, RNF-26 y RNF-27 | CA-01.1 a CA-01.2 y CA-25.1 a CA-25.3 | Total comprometida | Autenticación, autorización por propiedad, enmascaramiento y cifrado |
| NTI-10 | OBJ-05 | HU-22 | RF-38 | CA-22.1 a CA-22.2 | Parcial comprometida | Subconjunto mínimo comprometido pese a la prioridad baja: los tres indicadores base. El tablero completo quedó fuera del alcance |
| NTI-11 | OBJ-02 | HU-11, HU-14 | RNF-02, RNF-13 a RNF-18, RNF-20 | CA-11.1 a CA-11.3, CA-14.1 a CA-14.4 y criterios transversales de 3.3 | Parcial comprometida | La postulación desde navegador móvil, los objetivos táctiles, los mensajes de error y el contraste quedan comprometidos, los demás umbrales de usabilidad quedan condicionados |
| NTI-12 | OBJ-01, OBJ-04 | HU-19 | RF-37, RNF-11, RNF-22 | CA-19.3 | Total comprometida | Bitácora de solo escritura sobre acciones administrativas |

RNF-04, RNF-23 y RNF-24 no aparecen en la matriz porque su fuente es una restricción del equipo de desarrollo y no una necesidad del negocio: fijan el techo de memoria, la instalación con un solo comando y la configuración fuera del código. Se controlan igual en la Definición de Hecho, pero no trazan a ninguna necesidad TI y se declaran acá para que la ausencia no se lea como un olvido.

## 5. Selección de metodología TI

### 5.1. Características y necesidades metodológicas del proyecto

Antes de comparar metodologías conviene fijar contra qué se comparan, y las condiciones reales del proyecto son las siguientes, todas derivadas de algo ya documentado o de una restricción verificable del equipo.

| ID | Condición | Origen | Qué le exige a la metodología |
|---|---|---|---|
| CP-01 | La contraparte está disponible cada tres o cuatro semanas, no semanalmente | Restricción declarada del cliente | Que cada instancia de contacto rinda al máximo y que el trabajo no se detenga esperando la siguiente |
| CP-02 | Cinco puntos del negocio siguen sin confirmar (V-01 a V-05) | Tabla de supuestos del análisis de contexto | Un mecanismo explícito para avanzar sobre supuestos declarados y corregir cuando llegue la respuesta |
| CP-03 | Los 27 requerimientos no funcionales tienen umbrales fijados por el equipo | Catálogo de requerimientos | Revisión periódica de esos umbrales en lugar de tratarlos como cerrados |
| CP-04 | Equipo de tres personas sin roles especializados, donde todos desarrollan | Composición del equipo | Bajo costo de ceremonias y poca burocracia de proceso |
| CP-05 | Alcance amplio, con 38 requerimientos funcionales y 27 no funcionales, seis necesidades comprometidas de forma completa, tres parcialmente comprometidas y tres condicionadas a capacidad según la tabla de alcance de la priorización | Priorización y catálogo | Capacidad de ajustar el alcance sin rehacer la planificación completa |
| CP-06 | Las dependencias de construcción están definidas y son estrictas | Matriz de trazabilidad | Un orden de trabajo visible que impida adelantarse a lo que todavía no tiene base |
| CP-07 | Los hitos académicos son fechas fijas e inamovibles | Calendario de la asignatura | Entregas parciales funcionales en cada corte, con alcance variable y fecha fija |
| CP-08 | La evaluación exige documentación, trazabilidad y defensa oral | Pauta de evaluación | Que el proceso produzca evidencia documental como subproducto |
| CP-09 | Hay riesgo regulatorio concreto en datos personales y oficios regulados | NTI-01 y NTI-09 | Que lo riesgoso se aborde temprano y no quede para el final |
| CP-10 | La tecnología es conocida solo parcialmente por el equipo | Restricción del equipo | Tolerancia a estimaciones imprecisas durante las primeras semanas |

De estas condiciones salen los criterios con los que se evaluaron las alternativas, todos en escala de 1 a 5, donde 5 indica que la alternativa satisface plenamente el criterio.

| Criterio | Peso | Qué mide | Condición que lo origina |
|---|---|---|---|
| C1. Aprovechamiento de instancias de contacto escasas | 20% | Qué tan bien convierte pocas reuniones en decisiones validadas | CP-01, CP-02 |
| C2. Adaptación al cambio de requerimientos | 20% | Costo de incorporar un cambio una vez iniciado el desarrollo | CP-02, CP-03 |
| C3. Costo de ceremonias sobre un equipo de tres | 15% | Proporción del tiempo del equipo consumida por el proceso mismo | CP-04 |
| C4. Compatibilidad con fechas fijas | 15% | Capacidad de llegar a un hito con algo entregable | CP-07 |
| C5. Producción de documentación evaluable | 10% | Qué tanta evidencia genera el proceso por sí solo | CP-08 |
| C6. Tratamiento temprano del riesgo | 10% | Qué tan pronto aparecen los problemas regulatorios y técnicos | CP-09, CP-10 |
| C7. Visibilidad del avance y del trabajo en curso | 10% | Capacidad de ver dónde se atasca el trabajo | CP-05, CP-06 |

### 5.2. Comparación de metodologías alternativas

Se compararon tres formas de trabajar posibles para un equipo de este tamaño, dejando fuera los marcos pensados para coordinar varios equipos a la vez, porque aquí hay uno solo de tres personas.

- Scrum. Organiza el trabajo en ciclos de duración fija llamados sprints, define tres responsabilidades y, dentro del sprint que las contiene, cuatro eventos, y exige que al final de cada ciclo exista algo funcionando que se pueda mostrar, dejando libre la duración del sprint, que puede ser de hasta un mes.
- Método Kanban. Trabaja de forma continua sobre un tablero visible, limita cuántas tareas pueden estar empezadas al mismo tiempo y se adapta a la forma de trabajo que ya existe, sin exigir roles, ciclos ni reuniones de revisión obligatorias.
- Ciclo de vida secuencial (cascada). Avanza por etapas una después de otra, análisis, diseño, construcción, pruebas y puesta en marcha, revisando documentos al cierre de cada una, y se incluyó porque es la alternativa que aparece por defecto en la mayoría de los proyectos académicos.

#### 5.2.1. Tabla comparativa

| Criterio | Peso | Scrum | Kanban | Cascada | Análisis |
|---|---|---|---|---|---|
| C1. Aprovechamiento de instancias escasas | 20% | 5 | 3 | 2 | Con sprints de tres semanas, la revisión de sprint cae exactamente en la ventana de disponibilidad de la contraparte y llega con un incremento preparado, mientras Kanban deja la validación librada a que alguien la convoque y cascada la concentra al cierre de fases, cuando corregir ya cuesta caro |
| C2. Adaptación al cambio | 20% | 5 | 4 | 1 | Scrum está construido alrededor del cambio entre sprints y protege el trabajo en curso dentro de cada uno, Kanban admite reordenar en cualquier momento con el límite de lo ya iniciado, y en cascada un cambio posterior al análisis obliga a rehacer documentación aprobada |
| C3. Costo de ceremonias con tres personas | 15% | 3 | 5 | 4 | Los cuatro eventos sobre un equipo de tres consumen tiempo real, y aunque la revisión y la retrospectiva se justifican, la reunión diaria pierde sentido cuando el equipo ya se comunica varias veces al día, algo que obliga a una adaptación declarada |
| C4. Compatibilidad con fechas fijas | 15% | 5 | 3 | 4 | El sprint es una caja de tiempo cerrada que llega a la fecha con un incremento, Kanban fluye sin hitos propios y cascada depende de que las fases anteriores no se atrasen |
| C5. Documentación evaluable | 10% | 4 | 3 | 5 | Cascada produce documentación formal por diseño, Scrum genera artefactos aprovechables si la Definición de Hecho los exige, y Kanban deja el asunto enteramente a la disciplina del equipo |
| C6. Tratamiento temprano del riesgo | 10% | 5 | 3 | 2 | Scrum obliga a un incremento utilizable cada tres semanas, lo que fuerza a integrar y a descubrir problemas temprano, mientras Kanban permite priorizar lo riesgoso sin obligarlo y cascada revela los problemas de integración recién en la fase de pruebas |
| C7. Visibilidad del avance | 10% | 4 | 5 | 2 | El tablero con límites de trabajo en curso es el mecanismo más directo para ver dónde se atasca el trabajo, y Scrum lo incorpora como práctica habitual aunque no lo prescriba, mientras en cascada el avance se mide por documentos aprobados que no reflejan el estado real del software |
| Puntaje ponderado | 100% | 4,50 | 3,70 | 2,70 | Scrum encabeza los dos criterios de mayor peso |

#### 5.2.2. Conclusión de la comparación

Scrum obtiene el puntaje más alto y la diferencia se decide en los dos criterios de mayor peso, porque un sprint de tres semanas convierte la escasa disponibilidad de la contraparte en una fortaleza al hacer coincidir la revisión con la única ventana de contacto disponible, y porque la incertidumbre que dejaron los cinco supuestos sin confirmar y los veintisiete umbrales fijados por el equipo exige un marco que acepte el cambio entre iteraciones, algo que cascada no ofrece y que Kanban permite sin asegurar, mientras su única debilidad real aparece en C3, porque los cuatro eventos pesan mucho sobre un equipo de tres personas, y eso se resuelve con las adaptaciones que vienen a continuación.

### 5.3. Metodología seleccionada e idoneidad

Se selecciona Scrum con sprints de tres semanas, duración elegida para que la revisión de sprint coincida con la disponibilidad efectiva de la contraparte, el marco se aplica con adaptaciones declaradas de forma abierta para ajustarlo al equipo y al contexto académico.

Las principales adaptaciones son reemplazar la reunión diaria por una sincronización de quince minutos dos veces por semana, incorporar a la Definición de Hecho la evidencia documental que exige la rúbrica y usar un representante del producto que concentre las dudas y decisiones provisorias mientras la contraparte no está disponible, con esto la documentación queda dentro del trabajo de cada sprint y las decisiones pendientes se mantienen visibles.

#### 5.3.1. Responsabilidades

| Responsabilidad | Quién | Qué hace |
|---|---|---|
| Representante del producto | Docente | Ordena el Product Backlog con los criterios de priorización ya definidos, mantiene el registro de preguntas abiertas, prepara la revisión de sprint y comunica lo que la contraparte decide |
| Facilitador del proceso | Rota cada sprint | Convoca los eventos, retira impedimentos y vela por que la Definición de Hecho se cumpla antes de dar un ítem por terminado |
| Equipo de desarrollo | Los tres integrantes del grupo | Estima, construye, prueba y documenta |

La figura del representante del producto conviene explicarla porque en un proyecto real esa responsabilidad la asumiría alguien de AlTiro con autoridad para decidir, mientras acá la asume el docente que guía los proyectos del curso, quien junta las dudas, toma decisiones provisorias cuando hay que avanzar y lleva cada punto a confirmar en la siguiente revisión.

#### 5.3.2. Eventos

| Evento | Duración y frecuencia | Participantes | Propósito |
|---|---|---|---|
| Planificación del sprint | 2 horas, al inicio de cada sprint | Los tres integrantes | Definir el objetivo del sprint y seleccionar los ítems que caben |
| Sincronización | 15 minutos, dos veces por semana | Los tres integrantes | Revisar impedimentos y trabajo en curso |
| Refinamiento del backlog | 1 hora semanal | Los tres integrantes | Escribir criterios de aceptación y resolver dependencias de los ítems próximos |
| Revisión del sprint | 1 hora, al cierre de cada sprint | Los tres integrantes, el docente y la contraparte | Mostrar el incremento, resolver las preguntas acumuladas y revisar umbrales |
| Retrospectiva | 45 minutos, después de la revisión | Los tres integrantes | Ajustar acuerdos, estimaciones y forma de trabajo |

El refinamiento del Product Backlog no es un evento de la Guía Scrum sino una actividad continua, y se calendariza acá solo para que un equipo sin experiencia previa no lo deje de lado.

#### 5.3.3. Tablero y trabajo en curso

| Columna | Qué contiene | Límite |
|---|---|---|
| Sprint Backlog | Ítems comprometidos para el sprint en curso | El objetivo del sprint |
| En desarrollo | Implementación en curso | 3, uno por integrante |
| En pruebas | Verificación contra criterios de aceptación y umbrales no funcionales | 2 |
| Terminado sin validar | Cumple la Definición de Hecho, esperando la revisión con la contraparte | Sin límite |
| Hecho | Validado en revisión de sprint | Sin límite |

El límite de un ítem en desarrollo por persona es un acuerdo del equipo y no una regla de Scrum, adoptado porque con sesenta y cinco requerimientos la tentación de abrir varios frentes a la vez es alta y el resultado predecible, mucho trabajo empezado y nada terminado al cierre del sprint.

La columna Terminado sin validar responde directamente a CP-01, ya que un ítem puede cumplir la Definición de Hecho y aun así esperar hasta la revisión para que la contraparte lo confirme, y separarla de Hecho evita contar como cerrado algo que todavía no lo está sin frenar por eso el avance del equipo.

#### 5.3.4. Artefactos

Los tres artefactos de Scrum son el Product Backlog, el Sprint Backlog de cada iteración y el incremento, en este proyecto el Product Backlog reúne las veinticinco historias de usuario y sus requerimientos funcionales y no funcionales asociados, las historias ordenan el valor y los requerimientos detallan qué debe construirse y verificarse en cada sprint, además el equipo mantiene una bitácora de cambios de alcance y un registro de decisiones y preguntas abiertas donde quedan los cinco supuestos V-01 a V-05 y los veintisiete umbrales no funcionales, cada uno con su estado y la fecha en que cambió.

#### 5.3.5. Planificación inicial

Cinco sprints de tres semanas, con las fechas concretas completadas según el calendario de la asignatura.

| Sprint | Semanas | Objetivo | Incremento esperado |
|---|---|---|---|
| S1 | 1 a 3 | Identidad, roles y control de acceso, con RF-01 a RF-03, RNF-05 a RNF-12 y RNF-23 a RNF-24 | Base de seguridad operativa y primera confirmación de supuestos |
| S2 | 4 a 6 | Expediente del maestro y curatoría, con RF-04, RF-08 y RF-32 a RF-35, más RNF-25, RNF-13 a RNF-17 y RNF-20 | Verificación documental funcionando de extremo a extremo |
| S3 | 7 a 9 | Catálogo, cobertura y agenda, con RF-05 a RF-07, RF-36 y RNF-18 | Perfil de maestro completo y publicable |
| S4 | 10 a 12 | Búsqueda, ordenamiento y ticket, con RF-09 a RF-24, RNF-01 a RNF-04 y RNF-21 | Flujo principal operativo desde la búsqueda hasta el cierre |
| S5 | 13 a 15 | Mensajería, evaluación, bitácora e indicadores, con RF-25 a RF-31, RF-37, RF-38, RNF-19, RNF-22 y RNF-26 a RNF-27 | Sistema completo y material de defensa preparado |

El orden reproduce las dependencias de construcción ya identificadas y adelanta de forma deliberada lo riesgoso, por eso el control de acceso y la verificación documental ocupan los dos primeros sprints, si algo debe recortarse se recorta del quinto, con una salvedad, RF-26, RF-27 y RF-28 son de prioridad alta y sostienen NTI-04, así que quedan protegidos del recorte y lo que cede es la mensajería y la evaluación, que son necesidades condicionadas según la tabla de alcance de la priorización.

#### 5.3.6. Control de cambios

Un cambio nunca entra al sprint en curso, porque el objetivo comprometido se protege hasta el cierre, así que ingresa al Product Backlog, se prioriza con los mismos criterios ya definidos y, si desplaza algo comprometido, el desplazamiento queda registrado en la bitácora de alcance con fecha, motivo y quién lo autorizó, de manera que nada se saca del alcance de forma tácita.

### 5.4. Justificación según cliente y problemática

Cada elección metodológica responde a una condición verificable del cliente o del problema, y ninguna se justifica por preferencia del equipo.

| Condición del cliente o del problema | Respuesta metodológica | Riesgo que mitiga |
|---|---|---|
| La contraparte está disponible cada tres o cuatro semanas (CP-01) | Sprint de tres semanas cuya revisión coincide con esa ventana, más un representante del producto que acumula las preguntas entre reuniones | Que el equipo se detenga esperando respuestas o que decida por el cliente sin dejar constancia |
| Cinco puntos del negocio sin confirmar (CP-02) | Cada supuesto es un ítem del registro de decisiones con estado y fecha, revisado en cada revisión de sprint | Construir sobre un supuesto falso y descubrirlo al final |
| Veintisiete umbrales no funcionales fijados por el equipo (CP-03) | La revisión de umbrales es punto fijo de la agenda de cada revisión de sprint | Entregar un sistema que cumple métricas que a nadie le importan |
| Equipo de tres sin especialización (CP-04) | Reunión diaria reemplazada por sincronización dos veces por semana, facilitador rotativo y un ítem en desarrollo por persona | Que el proceso consuma más tiempo que el desarrollo |
| Alcance de sesenta y cinco requerimientos, con seis necesidades comprometidas de forma completa, tres parcialmente comprometidas y tres condicionadas a capacidad (CP-05) | Product Backlog ordenado por la priorización ya establecida, con recorte previsto desde el quinto sprint hacia atrás | Llegar al hito con muchas cosas a medias y ninguna terminada |
| Dependencias estrictas de construcción (CP-06) | La Definición de Listo exige dependencias resueltas antes de que un ítem entre a la planificación | Construir mensajería antes que control de acceso y exponer datos personales |
| Fechas académicas inamovibles (CP-07) | El sprint es una caja de tiempo cerrada con alcance variable y fecha fija, y cada uno termina con un incremento demostrable | Pedir prórroga, que no existe |
| La evaluación exige documentación y trazabilidad (CP-08) | La Definición de Hecho incluye la evidencia documental del ítem | Escribir el informe la semana previa a la entrega, con datos reconstruidos de memoria |
| Riesgo regulatorio en datos personales y oficios regulados (CP-09) | Los ítems de NTI-01 y NTI-09 se programan en los sprints uno y dos | Descubrir en el último sprint que la arquitectura no permite controlar el acceso por propiedad del recurso |
| Tecnología conocida parcialmente (CP-10) | Sin compromiso de velocidad durante los dos primeros sprints, midiendo lo que efectivamente se completa | Comprometer un plan basado en estimaciones sin fundamento |

Cómo se obtiene retroalimentación:

Cada revisión de sprint muestra software funcionando, y la columna Terminado sin validar asegura que siempre haya material concreto que revisar incluso si el equipo avanzó menos de lo previsto, con las preguntas llevadas por escrito y agrupadas, porque una reunión cada tres semanas no admite improvisación.

Cómo se gestiona el cambio y la incertidumbre:

Un cambio que llega en la semana dos entra al Product Backlog y se prioriza en la planificación siguiente sin tocar el objetivo del sprint en curso, lo que protege el compromiso que el equipo ya tomó, mientras la incertidumbre que no se puede resolver se declara como supuesto con fecha, de modo que siempre se sepa cuánto lleva pendiente una decisión.

#### 5.4.1. Riesgos que la elección no resuelve

El límite más importante del marco elegido es que el representante del producto no tiene la autoridad real que el rol supone, de manera que sus decisiones son provisorias hasta que la contraparte las confirme y un desacuerdo tardío puede obligar a rehacer trabajo ya terminado, a lo que se suma que la velocidad del equipo no será confiable antes del tercer sprint, así que cualquier proyección de alcance hecha en las primeras seis semanas debe leerse como referencia y no como compromiso.

## 6. Seguridad TI, ética y responsabilidad profesional

### 6.1. Necesidades de seguridad TI e importancia para el negocio

AlTiro guarda datos que la ley chilena protege, como fotografías de cédulas por ambos lados, certificados de antecedentes, licencias de instalador, direcciones de clientes y el registro de lo que cada persona contrató y pagó, todo lo cual hoy está en carpetas y correos personales de los socios, situación que el proyecto tiene que resolver mientras se mantiene como supuesto V-02 la fecha prevista de entrada en vigor de la Ley 21.719.

La seguridad aquí no es un agregado del final, porque lo que AlTiro ofrece es confianza verificada y sin protección de esos datos el producto pierde sentido.

#### 6.1.1. Inventario de activos

Los riesgos de la matriz siguiente se describen sobre estos activos, que son lo que el proyecto tiene que proteger y lo que hoy está desprotegido.

| ID | Activo | Qué contiene y dónde vive hoy |
|---|---|---|
| AC-01 | Expedientes de los maestros | Fotografías de cédula por ambos lados, certificado de antecedentes y licencia SEC cuando corresponde. Hoy viven en carpetas personales y correos de los socios |
| AC-02 | Datos de contacto y ubicación del cliente | Nombre, teléfono, dirección exacta y comuna. Hoy están repartidos entre la planilla de 31 columnas y los chats de WhatsApp |
| AC-03 | Credenciales de acceso | Contraseñas y sesiones de los perfiles de la plataforma. Hoy no existen, porque el acceso es la cuenta de WhatsApp de un socio |
| AC-04 | Conversaciones entre cliente y maestro | Mensajes y adjuntos de coordinación de cada trabajo. Hoy están en grupos de tres personas sin historial consolidado |
| AC-05 | Registro de órdenes y precios acordados | Servicio solicitado, bloque, estado y monto final de cada trabajo. Hoy es una fila de planilla y un acuerdo verbal |
| AC-06 | Bitácora de acciones administrativas | Aprobaciones, observaciones, suspensiones y resoluciones de denuncias con autor y motivo. Hoy no existe |
| AC-07 | Base de datos de la prueba de concepto | Motor relacional en contenedor con volumen local, alojado en un solo equipo del equipo de desarrollo |
| AC-08 | Código fuente y configuración | Repositorio, claves de base de datos, rutas de almacenamiento y dependencias externas del sistema |
| AC-09 | Disponibilidad del servicio | La plataforma en funcionamiento para clientes y maestros durante la etapa de prueba de concepto |
| AC-10 | Datos agregados y anonimizados | Demanda, precios de referencia y cobertura por comuna, calculados sobre la operación y base del modelo de ingreso |

#### 6.1.2. Matriz de riesgos

Impacto y probabilidad se miden en escala de 1 a 5 y el nivel se calcula como impacto por probabilidad, crítico desde 15, alto entre 8 y 14, medio entre 4 y 7 y bajo por debajo de 4, la amenaza describe qué puede ocurrir y la vulnerabilidad por qué puede ocurrir en este caso, la medida describe el control y la última columna indica el requerimiento que lo respalda, cuando el riesgo se acepta de forma explícita se indica.

| ID | Activo | Amenaza | Vulnerabilidad | Imp. | Prob. | Nivel | Medida propuesta | Requisito asociado |
|---|---|---|---|---|---|---|---|---|
| R-01 | AC-01 | Un usuario autenticado accede a documentos de otro maestro | El sistema confía solo en el tipo de usuario y los registros se numeran de forma predecible | 5 | 4 | 20 · Crítico | RNF-06, RNF-07 | RNF-06, RNF-07 |
| R-02 | AC-02 | Un maestro obtiene la dirección de un cliente sin haber aceptado el ticket | La dirección llega al teléfono del maestro y solo se esconde en la pantalla | 4 | 4 | 16 · Crítico | RF-17, RNF-08 | RF-17, RNF-08 |
| R-03 | AC-03 | Robo de credenciales por fuerza bruta o por filtración de la base | Contraseñas almacenadas de forma insegura y sin límite de intentos | 5 | 3 | 15 · Crítico | RNF-05, RNF-10 | RNF-05, RNF-10 |
| R-04 | AC-07 | Falla de disco o del equipo que aloja la prueba de concepto | La base de datos vive en un único equipo y no hay respaldo cuya restauración se haya probado | 5 | 3 | 15 · Crítico | RNF-19 | RNF-19 |
| R-05 | AC-04 | Lectura de conversaciones ajenas | Los identificadores de conversación son predecibles y la autorización comprueba el rol, no la participación en el ticket | 4 | 3 | 12 · Alto | RNF-07, RNF-22 | RNF-07, RNF-22 |
| R-06 | AC-08 | Un tercero entra a la base de datos con credenciales que encontró en el repositorio | Contraseñas y rutas escritas dentro del código versionado | 4 | 3 | 12 · Alto | RNF-24 | RNF-24 |
| R-07 | AC-08 | Alguien aprovecha una falla ya conocida en una librería externa | Se usan librerías externas sin fijar su versión ni revisar sus avisos de seguridad | 4 | 3 | 12 · Alto | RNF-27 | RNF-27 |
| R-08 | AC-10 | Reidentificación de personas a partir de datos supuestamente agregados | Agregación insuficiente en comunas con pocos maestros por oficio | 4 | 3 | 12 · Alto | RF-38 | RF-38 |
| R-09 | AC-01 | Conservación indefinida de documentos de maestros dados de baja | Ausencia de política de retención | 3 | 4 | 12 · Alto | RNF-06, RNF-26 | RNF-06, RNF-26 |
| R-10 | AC-06 | Alteración o borrado de registros de auditoría | Bitácora editable desde la interfaz administrativa | 4 | 2 | 8 · Alto | RNF-11 | RNF-11 |
| R-11 | AC-01, AC-02 | Alguien intercepta los datos en una red wifi abierta | Los datos viajan sin cifrar | 4 | 2 | 8 · Alto | RNF-12 | RNF-12 |
| R-12 | AC-09 | Caída del servicio | Un solo equipo, sin monitoreo ni redundancia | 2 | 3 | 6 · Medio | No aplica | No aplica |

R-01, R-02 y R-05 son variantes de lo mismo, un sistema que entrega un dato sin comprobar antes si quien lo pide es su dueño, y entre ellos están los dos riesgos de mayor nivel de toda la matriz. Los otros dos críticos apuntan a frentes distintos: R-03 al robo de credenciales y R-04 a la pérdida total de datos por falla del único equipo que aloja la prueba de concepto. Que la falla de autorización concentre el peso no es casualidad, porque la lista OWASP Top 10 de 2025 mantiene el control de acceso roto en el primer lugar, con una tasa de incidencia media de 3,73% en las aplicaciones evaluadas, y el propio dossier de AlTiro lo advierte a su manera cuando exige que un maestro no pueda abrir la orden de otro cambiando un número en la dirección web.

#### 6.1.3. Priorización e impacto en el negocio

| Orden de atención | Riesgos | Consecuencia si se materializa |
|---|---|---|
| 1 | R-01, R-02, R-05 | Legal: infracción a la Ley 21.719 con potestad sancionatoria de la Agencia. Reputacional: una filtración de cédulas destruye la única propuesta de valor que la empresa tiene. Operacional: pérdida de la red de maestros, que no volverá a entregar sus documentos |
| 2 | R-03, R-04 | Operacional: una pérdida total de datos deja a la empresa sin registro de órdenes en curso ni de expedientes aprobados. Financiero: rehacer la curatoría de 63 maestros consume semanas de los socios |
| 3 | R-08, R-09 | Legal: la información reidentificable pierde la condición de dato estadístico y arrastra consigo todo el modelo de ingreso. Ético: personas cuyos datos se comercializan sin base de licitud |
| 4 | R-06, R-07, R-10, R-11 | Operacional y legal: habilitan los riesgos anteriores o impiden demostrar lo ocurrido ante una fiscalización |
| 5 | R-12 | Reputacional menor en etapa de prueba de concepto |

El orden no reproduce el nivel calculado sino la familia de causa. R-01, R-02 y R-05 comparten la misma falla de autorización y se resuelven con el mismo control, así que se tratan como un frente único aunque R-05 quede en nivel alto y no crítico; separarlos llevaría a corregir dos veces el mismo defecto.

#### 6.1.4. Marco normativo y buenas prácticas aplicables

La Ley 21.719 alcanza a los activos AC-01 a AC-05, porque exige tener un motivo legal para guardar cada dato, usarlo solo para eso, pedir lo mínimo necesario, protegerlo y avisar si se filtra, y además define si AC-10 puede venderse, cosa que solo es posible cuando la información quedó realmente anónima y ya no permite reconocer a nadie, mientras la Ley 19.496 alcanza a AC-05 porque el registro del precio acordado es lo que le permite al cliente reclamar por lo que le cobraron, y la lista OWASP Top 10 de 2025 aportó el vocabulario con el que se nombraron las amenazas: control de acceso roto (A01) en R-01, R-02 y R-05; fallas de autenticación (A07) en R-03; configuración insegura (A02) en R-06; fallas en la cadena de suministro de software (A03) en R-07; fallas de registro y alerta (A09) en R-10; y fallas criptográficas (A04) en R-11.

### 6.2. Medidas propuestas e impacto ético y profesional

Cada medida de seguridad restringe algo, por eso el análisis considera a quién le cuesta y qué salvaguarda compensa ese costo, las salvaguardas pueden ser técnicas u operativas y no todas tienen que convertirse en un requerimiento funcional, lo importante es dejar claro quién responde por ellas y en qué momento se aplican.

| Medida | Beneficio | Riesgo ético | Afectados | Principio en juego | Salvaguarda | Responsable |
|---|---|---|---|---|---|---|
| M-01. Enmascarar dirección y teléfono hasta la aceptación | El cliente no expone su domicilio a desconocidos | El maestro decide sin saber la dirección exacta y puede rechazar por prejuicio sobre la comuna | Clientes de sectores estigmatizados | No discriminación | Monitorear la tasa de rechazo por comuna y revisarla en cada ciclo de validación; si aparece un patrón, informarlo a la empresa | Enlace con la contraparte |
| M-02. Custodia de documentos con enlace firmado y expiración | Las cédulas dejan de estar en carpetas personales | Concentrar documentos sensibles en un solo sistema aumenta el daño de una brecha única | Maestros | Proporcionalidad | Retención acotada, cifrado en reposo y acceso restringido a curatoría; ningún documento se abre escribiendo su dirección en el navegador | Responsable de verificación |
| M-03. Bitácora inmutable de acciones administrativas | Toda decisión sobre un expediente queda auditable | Vigilancia sobre el propio equipo administrativo | Socios y asistente | Rendición de cuentas | La bitácora registra acciones sobre expedientes, no actividad general de la persona; su finalidad se comunica al equipo | AlTiro |
| M-04. Conversaciones asociadas al ticket y accesibles para moderación | Las disputas se resuelven con antecedentes | Moderación lee conversaciones privadas entre dos personas | Clientes y maestros | Limitación de finalidad | El acceso se habilita solo con una disputa abierta, queda registrado con autor y motivo, y ambas partes son informadas de que ocurrió | Moderación |
| M-05. Suspensión automática de servicios al vencer la licencia | Ningún trabajo regulado se ofrece sin habilitación | Un maestro pierde ingresos de forma automática, posiblemente por un error de registro de la fecha | Maestros de oficios regulados | Debido proceso | Aviso 30 días antes, vía de apelación ante curatoría y suspensión acotada al oficio regulado: sus otros oficios siguen visibles | Curatoría |
| M-06. Exportación de datos agregados | Sostiene el modelo de ingreso | Comercializar información generada por personas que no participan del beneficio; riesgo de reidentificación | Clientes y maestros | Transparencia y consentimiento informado | Umbral mínimo de registros por grupo y exclusión de identificadores, cualquier explotación comercial se habilita solo después de cerrar V-05 y definir su base de licitud, en esta etapa solo se construye la exportación agregada | AlTiro |
| M-07. Bloqueo tras cinco intentos fallidos | Contiene los ataques por fuerza bruta | Puede usarse para dejar a un competidor fuera de su propia cuenta | Maestros | Proporcionalidad | Bloqueo temporal y asociado al origen del intento, nunca deshabilitación permanente de la cuenta | Equipo |
| M-08. Registro de accesos denegados | Permite detectar intentos de acceso a recursos ajenos | Registrar la conducta de los usuarios se acerca a la vigilancia | Todos | Minimización | Retención acotada del registro y prohibición de usarlo para decisiones automáticas sobre una persona | Equipo |
| M-09. Retención limitada de documentos de identidad | Reduce la superficie de una eventual brecha | Eliminar documentos puede borrar evidencia necesaria en una disputa posterior | Maestros | Proporcionalidad | El plazo de retención se define en función del período de garantía y del plazo de reclamo, no de una cifra arbitraria | AlTiro |

#### 6.2.1. Análisis propio

El algoritmo de ordenamiento decide quién trabaja: La fórmula de HU-03 tiene consecuencias económicas directas, porque determina qué maestro aparece primero y, en consecuencia, quién recibe ingresos, de manera que si nadie puede explicar el orden, los maestros quedan sujetos a una regla que no conocen, y por eso la fórmula se documenta, se les comunica y se revisa, para que si alguien pregunta por qué aparece en el lugar catorce exista una respuesta, con un efecto adicional que conviene vigilar, ya que el desempate por cantidad de evaluaciones favorece a quien ya tiene volumen y puede volverse una ventaja acumulativa que dificulte la entrada de maestros nuevos, algo detectable a tiempo midiendo la concentración de órdenes por maestro.

La reputación pública afecta el ingreso de una persona identificable, una evaluación injusta en una plataforma con 63 maestros pesa mucho más que en un sitio con miles, por eso la respuesta profesional pasa por garantizar el derecho a respuesta del maestro, exigir que quien evalúa haya participado en una orden finalizada y resolver las denuncias con la conversación a la vista en lugar de hacerlo con la palabra de uno contra la del otro.

#### 6.2.2. Responsabilidad profesional del equipo

Durante el desarrollo el equipo accede a datos personales reales si el sistema se prueba con la red de AlTiro, así que se adoptan tres compromisos explícitos, que son usar datos ficticios mientras sea posible, no almacenar ningún documento de identidad real en el repositorio ni en equipos personales fuera del entorno de desarrollo, y comunicar a la contraparte cualquier hallazgo de seguridad aunque implique reconocer un error propio.

## 7. Conclusiones

El análisis dejó a la vista que el registro y la coordinación son el mismo problema visto desde dos lados, y no que uno pese más que el otro. Las 2,7 llamadas por trabajo y las 5,5 horas diarias que un socio dedica a coordinar son costo de coordinación puro, y existen justamente porque no hay ningún registro que consultar; el 78% de trabajos sin evaluación y el 11% de reclamos sin evidencia son falta de registro sin más. Lo que ordena la priorización no es cuál duele más, sino la dependencia entre los dos: la coordinación no se puede arreglar sin un registro que consultar, mientras el registro rinde por sí solo aunque la coordinación siga a medias. Eso explica que NTI-03, la orden única y trazable, encabece el orden de construcción pese a quedar segunda en puntaje, porque sin ella ni la reputación ni los indicadores ni la información agregada tienen de dónde calcularse.

La decisión más importante fue poner la verificación y el control de acceso antes que la funcionalidad visible, algo poco habitual en un proyecto académico donde lo normal es mostrar pantallas pronto, pero que se sostiene en dos hechos concretos, dos de los ocho oficios están regulados por la SEC y la entrada en vigor de la Ley 21.719 está prevista para el semestre según el supuesto V-02, por eso la planificación ubica el control de acceso y la curatoría documental en los dos primeros sprints.

Quedan tres frentes abiertos, primero los cinco supuestos V-01 a V-05 que siguen sin confirmar y cuyo costo de corrección crece mientras no se resuelvan, luego los 27 umbrales no funcionales que son razonables para una prueba de concepto pero fueron fijados por el equipo, y por último el alcance que puede recortarse, NTI-06, NTI-07 y NTI-08 quedan condicionadas a capacidad, mientras NTI-05, NTI-10 y NTI-11 se comprometen solo en su núcleo, esta diferencia debe mantenerse visible en la planificación y en la trazabilidad.

La limitación principal del levantamiento es la disponibilidad de la contraparte, porque un contacto cada tres o cuatro semanas obliga a decidir con información incompleta más veces de las deseables, y la metodología se eligió justamente para hacerse cargo de eso en lugar de ignorarlo.

Los próximos pasos son el desarrollo según la planificación de cinco sprints, la validación de los supuestos pendientes en la primera instancia disponible y la medición temprana del requerimiento RNF-13, el tiempo de postulación de un maestro sin ayuda, que es el que más discute la viabilidad del proyecto, porque si un maestro con baja alfabetización digital no logra registrarse desde su teléfono el resto del sistema queda vacío por mucho que cumpla sus otros sesenta y cuatro requerimientos.

## 8. Referencias bibliográficas

Beck, K., Beedle, M., van Bennekum, A., Cockburn, A., Cunningham, W., Fowler, M., Grenning, J., Highsmith, J., Hunt, A., Jeffries, R., Kern, J., Marick, B., Martin, R. C., Mellor, S., Schwaber, K., Sutherland, J., & Thomas, D. (2001). Manifiesto por el desarrollo ágil de software. https://agilemanifesto.org/iso/es/manifesto.html

Biblioteca del Congreso Nacional de Chile. (2021). Decreto con Fuerza de Ley 3: Fija texto refundido, coordinado y sistematizado de la Ley N 19.496, que establece normas sobre protección de los derechos de los consumidores. https://www.bcn.cl/leychile/navegar?idNorma=1160403

Biblioteca del Congreso Nacional de Chile. (2024). Ley N 21.719: Regula la protección y el tratamiento de los datos personales y crea la Agencia de Protección de Datos Personales. https://www.bcn.cl/leychile/navegar?idNorma=1209272

Biblioteca del Congreso Nacional de Chile. (s.f.). División político-administrativa de Chile. https://www.bcn.cl

ChileAtiende. (s.f.). Licencia de instalador eléctrico (Ficha N 2662). Gobierno de Chile. https://www.chileatiende.gob.cl/fichas/2662-licencia-de-instalador-electrico

Kent, K., & Souppaya, M. (2006). Guide to computer security log management (NIST Special Publication 800-92). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-92

Organización Internacional de Normalización. (2023). ISO/IEC 25010:2023. Systems and software engineering. Systems and software Quality Requirements and Evaluation (SQuaRE). Product quality model. ISO.

OWASP Foundation. (2025). OWASP Top 10: 2025. https://owasp.org/Top10/2025/

Schwaber, K., & Sutherland, J. (2020). La guía de Scrum: Las reglas del juego. https://scrumguides.org/

Subsecretaría de Telecomunicaciones. (2026). Estadísticas del sector telecomunicaciones, primer semestre de 2026. Ministerio de Transportes y Telecomunicaciones. https://www.subtel.gob.cl

Superintendencia de Electricidad y Combustibles. (s.f.). Licencia de instaladora o instalador. https://www.sec.cl/area-ciudadana/licencia-de-instaladora-o-instalador/

World Wide Web Consortium. (2023). Web Content Accessibility Guidelines (WCAG) 2.2. https://www.w3.org/TR/WCAG22/

## 9. Anexos

### Declaración de uso de inteligencia artificial

Durante la elaboración de este informe se utilizó Claude (Anthropic, 2026) como apoyo en la revisión del documento. Las consultas realizadas se orientaron a detectar inconsistencias de valores numéricos internos entre tablas, y corregir errores de redacción como por ejemplo anotar mal una ley por un número. El análisis del negocio, la definición de necesidades TI, las historias de usuario, los requerimientos, la selección metodológica y las decisiones de alcance son trabajo propio del equipo. Las correcciones sugeridas fueron revisadas y validadas por los integrantes antes de incorporarlas.
