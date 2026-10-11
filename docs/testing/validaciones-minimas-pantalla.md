# Validaciones mínimas en pantalla (CLAUDE.md §9) — inventario

Fecha: 2026-10-11 (v0.6.1, rediseño parte 2, ADR-002 E-3.1). Revisión del código de cada pantalla y pase en navegador (Chromium 360 y 1280 px, Playwright) donde se indica. El servidor sigue siendo la validación que vale.

Puntos de §9: **1** largo máximo · **2** espacios sobrantes (salvo contraseña) · **3** indicador de carga y botón desactivado · **4** mensaje junto al campo, resumen arriba y foco en el primer error · **5** no borrar lo escrito ante un error · **6** limpiar al terminar bien (y borrar el borrador) · **7** mensaje de resultado con `aria-live`.

Estados: **Sí** (en el código), **Sí·V** (además verificado en navegador en esta iteración), **N/A** (la pantalla no tiene esa situación), **Parcial** (ver nota).

## Común (`frontend/js/formulario.js`, cargado en todas las pantallas con formularios)
- **2:** al salir de un campo de texto se ve el valor recortado (evento `change`), y `leer` y `revisar` recortan antes de validar y enviar. Contraseñas, archivos, casillas y opciones nunca se recortan. `errorRut` y `errorIdentificador` aceptan espacios en los bordes (paridad con `normalizar_rut` del servidor, auditoría del backend, hallazgo 3).
- **3:** `ocupado(form, sí, texto)` desactiva el botón, cambia su texto («Enviando…» u otro) y marca `aria-busy`.
- **4:** `mostrarErrores` deja cada error junto a su campo, agrega «Hay N datos por corregir…» cuando hay más de uno y lleva el foco al primer campo con error si está a la vista (si no, al resumen).
- **6 y 7:** `terminado(form, texto, clave)` (mensaje, `reset` y borrador fuera) y `resultado(caja, texto, tipo)` para operaciones que no son formularios (`role="status"` o `"alert"`).

## Largos máximos (punto 1), tomados del servidor
| Campo | `maxlength` | Fuente en el servidor |
|---|---|---|
| Nombre | 150 | `identidad/validadores.py`, `NOMBRE_LARGO_MAXIMO` |
| Correo, identificador de ingreso y recuperación | 254 | `CORREO_LARGO_MAXIMO` |
| Contraseña (todas) | 128 | `CONTRASENA_LARGO_MAXIMO` (nunca se recorta) |
| RUT | 12 | `RUT_LARGO_MAXIMO` = 9 sin formato; 12 es la forma escrita más larga que acepta `normalizar_rut` («12.345.678-K») |
| Teléfono | 15 | `TELEFONO_LARGO_MAXIMO` = 12 canónico («+56912345678»); 15 es la forma escrita del ejemplo de ayuda «+56 9 1234 5678» (el servidor quita espacios, guiones y paréntesis) |
| Montos y precios de referencia | 12 | `MONTO_MAXIMO` = 10.000.000; 12 es «$ 10.000.000» (`formato.leerMonto` quita `$`, puntos y espacios) |
| Oficio y servicio (comercial) | 100 | `catalogo/servicios.py`, `NOMBRE_LARGO_MAXIMO` |
| Motivos (comercial, curatoría) | 1000 | `MOTIVO_LARGO_MAXIMO`; curatoría `expediente/servicios.py` |
| Dirección / descripción del pedido | 200 / 1000 | `tickets` `LARGO_DIRECCION` / `LARGO_DESCRIPCION` |
| Mensaje | 1000 | `mensajeria/models.py`, `LARGO_MAXIMO` |
| Comentario de evaluación / motivo de denuncia y de resolución | 500 / 500 | `evaluaciones/models.py` |

Teléfono, RUT y montos: el largo de pantalla es el de la forma escrita, no el guardado; con el canónico no se podrían escribir los puntos o espacios que el propio servidor acepta. Revisar si el servidor fija un largo de entrada distinto.

## Por pantalla
| Pantalla | 1 | 2 | 3 | 4 | 5 | 6 | 7 | Nota |
|---|---|---|---|---|---|---|---|---|
| `registro-cliente` | Sí | Sí·V | Sí | Sí·V | Sí·V | Sí | Sí | 6-7: el borrador se borra y la pantalla pasa a «Ingresar» con aviso «registrado». Verificado: vacío → resumen «Hay 3 datos…» y foco en Nombre; correo con espacios recortado; «← Paso anterior» tras recargar en el paso 2 |
| `postulacion-maestro` | Sí | Sí | Sí | Sí | Sí | Sí | Sí | Igual que el registro (va a «Ingresar» con aviso) |
| `ingresar` | Sí | Sí | Sí | Sí | Sí | N/A | Sí | Tras ingresar se cambia de página; la contraseña no se conserva. Verificado: cliente nuevo → `categorias.html` |
| `recuperar` | Sí | Sí | Sí | Sí | Sí | Sí | Sí | Mensaje 202 único |
| `nueva-contrasena` | Sí | N/A | Sí | Sí | Sí | Sí | Sí | Solo contraseña (no se recorta) |
| `cuenta` (datos, seguridad, perfiles) | Sí | Sí·V | Sí | Sí·V | Sí·V | Sí | Sí | Verificado: contraseña equivocada al cambiar correo → error y foco en la contraseña, correo conservado y recortado |
| `pedir-trabajo` | Sí | Sí | Sí | Sí | Sí | Sí | Sí | Éxito → `mis-pedidos.html?enviado=1` con aviso; borrador borrado |
| `mis-pedidos` (aceptar/objetar precio, cancelar) | N/A | N/A | Sí | Sí | N/A | N/A | Sí | Operaciones con confirmación y aviso de resultado |
| `mis-trabajos` (aceptar, rechazar, precio final) | Sí | Sí | Sí | Sí | Sí | Sí | Sí | No verificado en navegador: falta cuenta de maestro |
| `conversacion` | Sí | Sí | Sí | Sí | Sí | Sí | Sí | Nuevo: «Mensaje enviado.» tras enviar. No verificado en navegador (sin pedido aceptado) |
| `evaluar` (evaluación y denuncia) | Sí | Sí | Sí | Sí | Sí | Sí | Sí | No verificado en navegador |
| `mi-perfil` (foto) | N/A | N/A | Sí | Sí | Sí | N/A | Sí | No verificado: falta cuenta de maestro |
| `mis-servicios` | Sí | Sí | Sí | Sí | Sí | Sí | Sí | No verificado: falta cuenta de maestro |
| `mi-cobertura` | N/A | N/A | Sí | Sí | Sí | N/A | Sí | Solo listas cerradas |
| `mi-agenda` | N/A | N/A | Sí | Sí | Sí | Sí | Sí | Horas por selector |
| `mi-postulacion` / `mis-documentos` | N/A | N/A | Sí | Sí | Sí | Sí | Sí | Archivos y fechas; sin texto libre |
| `curatoria-expediente` | Sí | Sí | Sí | Sí | Sí | Sí | Sí | No verificado: falta cuenta de curatoría |
| `comercial` | Sí | Sí | Sí | Sí | Sí | Sí | Sí | No verificado: falta cuenta comercial |
| `moderacion` | Sí | Sí | Sí | Sí | Sí | Sí | Sí | No verificado: falta cuenta de moderación |
| `indicadores` (consulta y exportación) | N/A | N/A | Sí | Sí | Sí | N/A | Sí | Exportar: «Preparando archivo…» y «Listo: se descargó …» |
| `buscar` | N/A | N/A | Sí | Sí | Sí | N/A | Sí | Listas cerradas («Buscando…») |
| `curatoria` (cola) | N/A | N/A | Sí | N/A | N/A | N/A | Sí | Solo filtros |

## Pendiente
- Pase en navegador con cuentas de maestro y administrativas (sin contraseña disponible; no se restablecieron las demo).
- `scripts/validacion-pantalla/verificar.sh` muestra 2 diferencias en identificador con espacios en los bordes porque el contenedor `app` en ejecución todavía no tiene el cambio del backend (el código en disco ya acepta esos espacios; comprobado con el servicio `pruebas`). Volver a correrlo tras reconstruir `app`.
