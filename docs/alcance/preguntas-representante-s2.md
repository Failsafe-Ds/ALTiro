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
| P-11 | ¿Qué opción de alcance se elige para la reautenticación de RNF-09 (A a D)? | D: sin funciones de cambio de contraseña ni de correo | Propuesta del S1, §2.1; DA-09 |
