# QA: recorrido de punta a punta en Chrome (2026-10-30)

Entorno: `altiro-dev`, https://localhost:8443, v0.6.8, Chrome (extensión Claude in Chrome), ventana de 1920x889. Solo observación; no se modificó código. Datos ficticios (@example.com). Sin contraseñas en este informe.

## (a) Pasos

| Paso | Resultado |
|---|---|
| 1 Visitante: inicio, carrusel, búsqueda (oficio, comuna, bloque), sugerencias, ficha, precios, vistas privadas | PASS. Las páginas privadas cargan como HTML estático pero toda API privada responde 401 y la pantalla muestra «Tu sesión terminó». |
| 2 Registro cliente y maestro, validaciones | PASS con DEF-CHR-03 y 04 (UX). Vacío, solo espacios, largo (150, 254, 1000, 200), RUT inválido, correo duplicado, contraseña corta y contraseña sin recorte verificados. |
| 3 Cliente: ticket, rechazo ≤4 h, historial, cancelar | PASS. El rechazo ≤4 h se probó con un bloque de hoy 23:00 creado por el maestro (409 accionable), luego borrado. |
| 4 Maestro: ticket pendiente sin datos del cliente, aceptar, contacto, mensajes, precio final | PASS por API. FAIL en UI: DEF-CHR-01 (aceptar/rechazar no funcionan). Sin dirección, teléfono ni nombre en lista, detalle ni avisos; aparecen solo tras aceptar. Precio por trabajo distinto exige aceptación del cliente; monto distinto del vigente da 409. |
| 5 Cliente: aceptar precio, finalizar, evaluar, evaluar dos veces | PASS (la aceptación finaliza; segunda evaluación 409; denuncia y resolución OK). |
| 6 Maestro: perfil, servicios, cobertura, agenda, documentos | PASS parcial de cobertura: agenda (invertido, igual, no múltiplo, traslape, formato) 400 accionables; montos inválidos 400; «Sobre mí» de 501 caracteres da 400 en el campo y recorta espacios. NO VERIFICADO: carga real de documentos (requiere archivo) y pantalla de cobertura. |
| 7 Curatoría, comercial, moderación, control de gestión | PASS. Aprobar sin documentos se rechaza con mensaje claro; observar exige motivo; moderación y exportación CSV (sin identificadores). La descarga CSV desde el botón no se probó (se leyó por fetch). |
| 8 IDOR con cliente 2 | PASS: 404 idéntico en ticket, mensajes, evaluaciones, cancelación, mensaje y evaluación ajenos; inexistente igual; 403 para rutas de otro rol. |
| 9 Vista móvil 390x844 | NO COMPLETADO: `resize_window` no cambió el viewport (siguió en 1920) y `frame-ancestors 'none'` impide emularlo con un iframe. Solo se verificó por código: meta viewport, CSS con `min-width`, alturas táctiles ≥44 px, sin scroll horizontal. |

Consola: sin errores JS en las pantallas visitadas.

## (b) Defectos

**DEF-CHR-01 (ALTA). El maestro no puede aceptar ni rechazar un pedido desde la pantalla.**
- HU/RF: aceptación y rechazo de tickets (flujo principal, ADR-023); RNF de usabilidad móvil.
- Pasos: ingresar como maestro → Mis trabajos → «Ver detalle» de un pedido pendiente → «Aceptar este pedido» (o «Rechazar»).
- Esperado: aparece «¿Aceptar este pedido?» con botón de confirmar.
- Obtenido: no pasa nada visible y no se envía ninguna petición. El panel de confirmación se mueve a un contenedor oculto: `detalle.querySelector(".acciones")` en `frontend/js/mis-trabajos.js` (línea ~255) devuelve el primer `.acciones`, que es el de `#form-precio` (con `hidden`).
- Área: frontend. Posible regresión del rediseño reciente. La aceptación solo funcionó por API.

**DEF-CHR-02 (MEDIA). «Mis trabajos» entierra el pedido nuevo bajo avisos viejos.** Seis avisos antiguos (algunos de hace semanas) ocupan toda la primera pantalla y las pestañas «Nuevos/Aceptados/Historial» quedan bajo el pliegue; en teléfono el maestro con poca alfabetización digital no ve el pedido. UX móvil (CLAUDE.md §9). Frontend.

**DEF-CHR-03 (BAJA). Enter en el paso 1 de los formularios por pasos avanza y muestra de inmediato errores en el paso 2.** En registro de cliente y postulación de maestro, pulsar Enter en el último campo pasa al paso siguiente y ya muestra el resumen «Revisa los campos marcados» y «Ingresa una contraseña» sin que la persona haya escrito. Esperado: paso limpio (CLAUDE.md §9.4). Frontend.

**DEF-CHR-04 (BAJA). El resumen de errores queda desactualizado.** En `buscar.html` el resumen «Hay 2 datos por corregir» sigue visible después de corregir los campos, hasta el siguiente envío. En la postulación de maestro, un RUT inválido no se marca en el primer intento (solo se marca el teléfono vacío) y aparece recién en el segundo. Frontend.

**DEF-CHR-05 (BAJA). Mensaje engañoso en indicadores.** Con `desde` posterior a `hasta` el error dice «El período debe tener entre 1 y 12 meses», en vez de decir que «Hasta» debe ser igual o posterior a «Desde». Backend/frontend (RF de indicadores).

**DEF-CHR-06 (BAJA). «Ya evaluaste este trabajo» (409) no dice qué hacer.** Añadir «Puedes ver tu evaluación en esta pantalla». Backend.

## Observaciones (no son defectos, requieren decisión)
- El mensaje de correo ya registrado en el registro de cliente permite saber si un correo existe (enumeración); lo mismo con el RUT en la postulación. Revisar contra ADR-013/RNF-10 y dejarlo documentado como decisión.
- Un cliente puede enviar un pedido repetido al mismo bloque: el servidor responde 200 con el mismo ticket (idempotente). Correcto.
- Los números de pedido (5677, 5678) son globales y revelan volumen; bajo.
- Datos demo: el maestro «Demo Uno» figura Aprobado pero «Mis documentos» dice «Todavía no has enviado documentos»; incoherencia de los datos de demostración.
- El CSV exportado y los indicadores no contienen identificadores personales (revisión por expresión regular: sin correos, teléfonos, RUT ni nombres).
- Descripción «Sobre mí» del maestro Demo Uno quedó vacía por una prueba (se escribió un valor y luego vacío).
- Sin credenciales en el código (grep): las coincidencias son ids de campos. Reingresar tras cerrar la ventana: `ingresar.html` con sesión vigente muestra el formulario normal. CSRF sin token se rechaza.
- Validaciones mínimas §9: 1 (largo) PASS, 2 (espacios; contraseña sin recortar) PASS, 3 (indicador «Enviando…» con botón desactivado, probado con red retardada) PASS, 4 y 5 (mensajes junto al campo, formulario conservado) PASS, 6 PASS, 7 PASS (`role=status/alert`, `aria-live`).

## Datos que dejó la prueba
Cliente `qa.chrome.1@example.com`, postulación RUT 12.345.678-5 (observada), pedido 5677 cancelado, pedido 5678 aceptado con un mensaje, evaluación y denuncia resuelta sobre el pedido 2 (precio final 36.000).
