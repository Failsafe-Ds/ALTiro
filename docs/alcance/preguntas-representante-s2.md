# Preguntas para el representante del producto — Sprint 2

Paquete único de preguntas (CP-01: la contraparte está disponible cada tres o cuatro semanas). Mientras no haya respuesta, el sistema funciona con el supuesto indicado, registrado como tal. Fecha de envío: pendiente.

| # | Pregunta | Supuesto vigente | Origen |
|---|---|---|---|
| P-01 | ¿Cuáles son los ocho oficios de la red (§2.2)? | Solo "Gas" y "Electricidad" (regulados) están confirmados; los otros seis son datos ficticios rotulados como tales en la demostración | ADR-017, D-1 |
| P-02 | ¿"Gasfitería" es un oficio regulado o solo lo es "gas"? | Solo "gas" es regulado | ADR-017, D-1 |
| P-03 | ¿Qué documentos son obligatorios para aprobar un expediente? | Cédula por ambos lados, certificado de antecedentes y licencia SEC por cada oficio regulado declarado | ADR-017, D-2 |
| P-04 | ¿Un expediente suspendido puede volver a aprobarse, con motivo? | Sí, verificando de nuevo RF-33 (M-05 menciona una "vía de apelación") | ADR-017, D-2 |
| P-05 | ¿El rechazo es definitivo? (el RUT es único, CA-11.3) | Sí, es terminal | ADR-017, D-2 |
| P-06 | ¿Se acepta PDF para el certificado de antecedentes? (RF-04 dice "como fotografía") | No: solo JPEG y PNG | ADR-015, D-5 |
| P-07 | ¿Cuánto tiempo se conservan los documentos de un postulante **rechazado**? (V-04 solo cubre al maestro activo) | Se conservan hasta definir RNF-26 (S5) | ADR-015; V-04 |
| P-08 | ¿Se acepta que el registro separado `acceso_denegado` cumple "queda en la bitácora" de CA-25.3? | Sí (pendiente desde el S1, DA-04) | ADR-010 |
| P-09 | ¿Se acepta el alcance nacional del catálogo territorial? | Sí (pendiente desde el S1) | ADR-012 |
| P-10 | ¿Se acepta que el HTML estático de una página privada sin datos cumple RF-02 ("vista privada")? | Sí (pendiente desde el S1) | ADR-002 |
| P-11 | ¿Qué opción de alcance se elige para la reautenticación de RNF-09 (A a D)? | **Resuelta por el equipo (2026-09-30):** A, más recuperación de contraseña (ADR-027, DA-27). Falta la conformidad del representante | Propuesta del S1, §2.1; DA-09 |

## Decisión provisional sobre P-01 y P-02 (2026-09-28)
Sin respuesta del representante, y siguiendo la instrucción del equipo de tomar la opción recomendada, se usa una **lista provisional** de ocho oficios comunes del hogar en Chile, que aparece en pantalla sin rótulos:
- Gas (regulado);
- Electricidad (regulado);
- Gasfitería (agua y alcantarillado, no regulado);
- Carpintería;
- Pintura;
- Albañilería;
- Cerrajería;
- Jardinería.

El informe solo nombra al "gasfíter" y al "eléctrico" (§1) y confirma como regulados el gas y la electricidad (§3.4, RNF-25). El resto es un **supuesto** hasta que responda el representante. Para P-02, la gasfitería de agua no es regulada; la de gas queda cubierta por el oficio "Gas".

## Preguntas del Sprint 3 (2026-09-29)

| # | Pregunta | Supuesto vigente (provisional) | Origen |
|---|---|---|---|
| P-12 | ¿Puede el administrador comercial declarar un oficio nuevo como regulado? | Sí, pero solo al crearlo; después no se puede cambiar desde la aplicación | ADR-018, D-2 |
| P-13 | ¿Los maestros organizan su disponibilidad por semana (mismos días y horas) o por fechas concretas? | Patrón semanal | ADR-020, D-9 |
| P-14 | ¿La foto de perfil es obligatoria para aparecer? | Sí | ADR-021, D-13 |
| P-15 | ¿Se muestra el nombre completo del maestro en su perfil público? | Sí, tal como está registrado | ADR-019, D-14 |
| P-16 | ¿Puede un maestro ya aprobado agregar un oficio nuevo? ¿Con qué revisión? | No en el S3 (no hay HU ni RF) | Propuesta del S3, D-17 |
| P-17 | ¿Qué servicios tiene cada oficio y con qué precios de referencia? | Datos ficticios de demostración, cargados por comercial | ADR-018 |
| P-18 | ¿Hay moderación de las fotos de perfil? | No definida | ADR-021 |

## Preguntas del Sprint 4 (2026-09-29)

| # | Pregunta | Supuesto vigente (provisional) | Origen |
|---|---|---|---|
| P-19 | ¿Con cuántos días de anticipación puede pedirse un trabajo? | 14 días | ADR-022, D-5 |
| P-20 | ¿El cliente ve el teléfono del maestro al ser aceptado? ¿El maestro ve el nombre del cliente antes de aceptar? | Sí (contacto mutuo al aceptar) / No | ADR-023, D-13 y D-21 |
| P-21 | ¿Qué pasa si el cliente no acepta el precio final? | No definido (S5) | Propuesta del S4, §3.7 |
| P-22 | ¿Qué pasa con un trabajo aceptado que nunca registra precio final? | No definido; no se inventa un cierre | Propuesta del S4 |
| P-23 | ¿Qué pasa con los trabajos aceptados de un maestro que después es suspendido? | No definido | Propuesta del S4 |

## Sprint 5 (ADR-026, propuesta del S5 §8)

P-21 queda con supuesto provisional: el cliente puede objetar el precio y el ticket vuelve a `aceptado` sin precio (ADR-026 E-1.5). P-22 se reformula como P-28.

| # | Pregunta | Supuesto vigente (provisional) | Origen |
|---|---|---|---|
| P-24 | ¿Escala de evaluación? | Enteros de 1 a 5 por dimensión | ADR-026 E-3 |
| P-25 | La evaluación del maestro al cliente (HU-18), ¿quién la ve? | Las partes y moderación; no otros maestros | ADR-026 E-3.6 |
| P-26 | ¿Quién puede denunciar una evaluación? | Solo la parte evaluada, una vez | ADR-026 E-4.2 |
| P-27 | ¿Desde cuándo se registra el precio final? | Desde el inicio del bloque | ADR-026 E-1.6 |
| P-28 | ¿Qué pasa con una orden aceptada que nunca se finaliza? | Queda `aceptado`, sin cierre automático | ADR-026 E-1.9 |
| P-29 | ¿Umbral y agregación de la exportación? | k=5 maestros y 5 clientes, por mes y comuna; la mediana del monto solo con 5 o más finalizadas de 5 o más maestros y 5 o más clientes distintos (si no, celda vacía; DEF-QA-014, provisional del coordinador) | ADR-026 E-6, E-6.5 |
| P-30 | ¿Plazo de retención por tipo de documento? (V-04, P-07) | Configurable; sin valor no se elimina nada | ADR-026 E-9 |
| P-31 | ¿Se puede escribir después de finalizar? | No, solo lectura | ADR-026 E-2.2 |
| P-32 | Primera respuesta: ¿mediana o promedio? ¿cuenta `bloque_tomado`? | Mediana, sin `bloque_tomado` | ADR-026 E-6.1 |
| P-33 | ¿Basta un aviso en la aplicación de que moderación leyó la conversación? | Sí, `conversacion_revisada` | ADR-026 E-4.4 |
