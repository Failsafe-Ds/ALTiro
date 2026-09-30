# QA S4, incremento 7: bandejas y pantallas de pedidos

Fecha: 2026-09-30. Alcance: filtro `estado` de las bandejas, `pedir-trabajo`, `mis-pedidos`, `mis-trabajos`, `estado-pedido.js`, navegación (`cuenta`, `ingresar`). HU-06, RF-17/18/19/20, CA-23.5, RNF-08, RNF-14, RNF-17.

## Entorno
- Docker Compose local. El contenedor `app` estaba con una imagen anterior al filtro `estado` (la bandeja respondía 400 a `?estado=`); se reconstruyó con `docker compose up -d --build app` (sin tocar volúmenes).
- Playwright 1.55 (imagen oficial, Chromium móvil 360 x 800, `es-CL`, tacto), axe-core 4.10.3, contra `https://localhost`.
- Datos ficticios (`@example.com`, RUT sintéticos), 2 maestros y 3 clientes por corrida, creados con las ayudas de `backend/tests`. Fotos sintéticas sin archivo: los 404 de `/foto` son del fixture.
- Las corridas usaron usuarios nuevos cada vez para no heredar tickets. Scripts en el directorio temporal de la sesión (no se versionan).

## Resultado
| Verificación | Resultado |
|---|---|
| Filtro `estado` en ambas bandejas: valor válido 200; valor desconocido, repetido u otro parámetro 400 | PASS (cliente en navegador; maestro por `test_las_bandejas_filtran_por_estado`) |
| Pestañas consultan `?estado=pendiente|aceptado|cerrado|finalizado` | PASS |
| Ficha, pedir-trabajo: resumen, 4 pasos (0/1/2/1 campos, RNF-14), errores por campo, progreso tras recarga | PASS |
| Enviar el pedido desde el navegador | FAIL en la 1.ª corrida (DEF-QA-001); PASS tras la corrección, ver Re-verificación |
| Pedido repetido no duplica (D-10); 409 con horarios libres | PASS (repetido); 409 de bloques no se ejercitó |
| Maestro, pendiente: HTML y JSON de red (`/api/maestros/tickets`, `/api/tickets/<ref>`) sin dirección, teléfono, nombre, correo (RNF-08) | PASS |
| Aceptar: confirmación, "No, volver", contacto aparece solo después | PASS |
| Rechazar y cancelar: confirmación, cerrados con estado en texto (icono + "Cerrado" + motivo), sin códigos internos | PASS |
| 409 al repetir sobre un cerrado (maestro y cliente): mensaje accionable | PASS (ver DEF-QA-004) |
| Aviso de bloque tomado con `enlace` a `/buscar.html?oficio&region&comuna&fecha&inicio&fin`, abre con filtros (CA-23.5) | PASS |
| Sin datos: mensajes vacíos en las 3 pestañas, cliente y maestro | PASS |
| Sesión expirada (avisos, cambio de pestaña, envío): enlace `ingresar.html?aviso=sesion&siguiente=pedidos|trabajos`; anónimo igual | PASS |
| `ingresar?siguiente=pedidos|trabajos` lleva a la pantalla; rol cruzado cae en `cuenta.html` | PASS |
| `cuenta`: bloque `accesos-cliente` y enlace "Mis trabajos" | PASS |
| CSP: 0 `pageerror`, 0 violaciones, 0 scripts/handlers/estilos inline en las 3 páginas | PASS |
| Sin scroll horizontal a 360 px (4 páginas y detalles) | PASS |
| axe-core (pedir paso 4, mis-pedidos lista y detalle, mis-trabajos lista, detalle y aceptado, cuenta cliente y maestro) | PASS, 0 violaciones |
| Objetivos táctiles de al menos 44 px (mis-pedidos, mis-trabajos) | PASS |
| RNF-17 (lenguaje del oficio, sin jerga) | PASS en los textos vistos; sin barrido de contrastes nuevo |

## Defectos
- **DEF-QA-001 (alta). Pedido imposible de enviar desde el navegador.** HU-06, RF-15, RNF-20. `frontend/js/formulario.js` `campos()` solo toma `input[name], select[name]`: el `textarea#descripcion` no se lee (`leer`) ni se guarda (`guardar`). El POST sale sin `descripcion` y el servidor responde 400 "Cuenta qué trabajo necesitas.". Siempre falla, con la descripción escrita. Además la descripción no se conserva tras recargar. Reproducir: ficha, elegir horario, completar los 4 pasos, Enviar. Causa: `formulario.js` (frontend). El resto del flujo se verificó inyectando `descripcion` en la petición (solo en la prueba).
- **DEF-QA-002 (media). El borrador se arrastra a otro pedido.** RNF-20. `pedir-trabajo.js` usa la clave fija `altiro.pedir-trabajo`. Al elegir otro horario u otro maestro se restauran paso 3 y dirección del borrador anterior, y se salta el resumen del nuevo horario. Esperado: borrador por (maestro, bloque) o descartar si cambian `m`/`b`. Causa: frontend.
- **DEF-QA-003 (baja). Texto equivocado para un maestro.** En `mis-pedidos` y `pedir-trabajo`, una cuenta maestro lee "Agrega tu comuna en «Mi cuenta»". No aplica a un maestro. Causa: frontend (copy).
- **DEF-QA-004 (baja). Aviso de éxito viejo junto al error.** `aviso-resultado` ("Rechazaste el pedido.", "Tu pedido fue enviado...") no se limpia cuando la siguiente acción responde 409; además, tras el 409 la lista no se recarga y el pedido cerrado sigue en "Nuevos"/"Pendientes" hasta recargar. Causa: `mis-trabajos.js`, `mis-pedidos.js`.

## Observaciones (no defectos)
- En `pedir-trabajo` el enlace "Ingresar" no lleva `siguiente` (el destino exige `m`, `b`, `f`, `s`); tras ingresar se cae en `cuenta.html` y el borrador queda guardado. Decidir si se quiere un destino con retorno.
- Los nuevos defectos de borrador dependen de DEF-QA-001 para verse completos.

## Recomendación
Corregir DEF-QA-001 antes de cerrar el incremento; DEF-QA-002 a 004 pueden ir en el mismo paso. Luego repetir solo el envío desde el navegador y el reinicio del borrador. La suite completa la corre el coordinador.

## Re-verificación tras las correcciones (2026-09-30)
Mismo entorno (frontend montado, Chromium 360 px, usuarios nuevos). Solo lo corregido.

| Defecto | Resultado |
|---|---|
| DEF-QA-001: envío real desde pedir-trabajo sin inyectar `descripcion` (POST con descripción, ticket creado, aparece en Pendientes); la descripción sobrevive a una recarga | PASS |
| DEF-QA-002: con un borrador a medias en un horario, otro horario abre en el paso 1 con dirección vacía | PASS |
| DEF-QA-003: cuenta maestro en `mis-pedidos` y en `pedir-trabajo` lee «entra a «Mi cuenta» y completa «Quiero pedir trabajos»»; ya no dice "Agrega tu comuna" | PASS |
| DEF-QA-004: 409 sobre un pedido cerrado (maestro al aceptar, cliente al cancelar): el error accionable queda arriba, sin "Rechazaste el pedido." ni "Tu pedido fue enviado" viejos, confirmación cerrada, pestaña recargada | PASS |
| CA-06.2: con el horario tomado por otro cliente mientras se llenaba el formulario, el envío responde 409 y muestra "Ese horario ya no está disponible" con los horarios libres vigentes (el tomado no aparece) y el enfoque en el título; sin scroll horizontal | PASS |
| axe (pedir paso 4, mis-pedidos lista y detalle, mis-trabajos, cuenta) y CSP (0 errores de página, 0 inline) tras los cambios | PASS |

Notas: los horarios alternativos de CA-06.2 se muestran como texto; para elegir uno se sigue el enlace a la ficha (no son enlaces directos). No es defecto según la propuesta, pero conviene confirmarlo con el representante del producto.
Estado: DEF-QA-001 a 004 cerrados.
