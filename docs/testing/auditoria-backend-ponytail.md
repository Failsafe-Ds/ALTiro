# Auditoría de calidad del backend (ponytail-audit)

- **Fecha:** 2026-10-11
- **Preparado por:** Claude, con la skill `ponytail-audit` (adaptación AlTiro).
- **Alcance:** `backend/` (apps `identidad`, `autorizacion`, `bitacora`, `territorio`, `catalogo`, `expediente`, `perfil`, `busqueda`, `tickets`, `mensajeria`, `evaluaciones`, `gestion`, `comun`), y de `infra/` y `scripts/` solo lo que toca al backend (gunicorn, límites del proxy, scripts que crean cuentas).
- **Carga supuesta:** la de la prueba de concepto (CLAUDE.md §3): 10 usuarios simultáneos; 100 maestros, 300 servicios, 1.000 tickets y 5.000 mensajes. La pila corre con 2 procesos de gunicorn (`backend/entrypoint.sh`).
- **Método:** lectura dirigida de los caminos de mayor costo (sesión, recuperación, autorización, transiciones del ticket y del precio, cierre por vencimiento, documentos cifrados, exportación anonimizada, limitadores, carga de datos de demostración) y de todas las entradas de texto (`leer_json` y `leer_multipart`). Se verificaron tres casos con una prueba temporal montada desde fuera del repositorio (no quedó en el código). No se corrió la suite completa ni se cambió código.

---

**Qué hace este repositorio:** AlTiro es el backend en Django de una plataforma que conecta hogares con maestros verificados. Guarda cuentas y sesiones, el expediente cifrado del maestro, su catálogo, cobertura y agenda, y el pedido completo: el ticket, su precio final, la conversación, las evaluaciones y la moderación. También entrega indicadores y una exportación anonimizada. Se asumió la carga de la prueba de concepto descrita arriba.

En general el backend está sano: la autorización pasa siempre por `obtener_autorizado` con el 404 idéntico, las transiciones del ticket bloquean primero el expediente y después los tickets, el cierre por vencimiento usa `skip_locked`, las fotos se recodifican con tope de píxeles, los documentos se cifran y la exportación aplica supresión k=5 y neutraliza fórmulas. Los hallazgos se concentran en las **validaciones mínimas de texto** (CLAUDE.md §8-§9) y en un script de QA.

## Debe corregirse

1. **Un carácter nulo en un texto rompe el servidor (500) en vez de dar 400** (`backend/comun/api.py:107-115`, `backend/identidad/validadores.py:183-192`, `backend/mensajeria/vistas.py:76-89`, `backend/evaluaciones/vistas.py:73-95`)
   - **Qué es:** `leer_json` revisa que cada texto se pueda codificar, pero no rechaza el carácter nulo (`\u0000`). Solo `leer_multipart` (línea 168) y algunos validadores sueltos (curatoría, catálogo, ticket) lo rechazan.
   - **Problema:** PostgreSQL no guarda el carácter nulo. Verificado: `POST /api/clientes` (pública, sin sesión) con `"nombre": "Ana\u0000Prueba"` responde **500** «Tuvimos un problema…» y deja una traza de `DataError` en el registro. Lo mismo ocurre por el mismo camino en `nombre` de la postulación de maestro, `texto` del mensaje, `comentario` de la evaluación y `motivo` de la denuncia y de la resolución de moderación. Incumple RNF-15 (ningún error interno a la persona) y la regla (b) de CLAUDE.md (400 en el campo, nunca 500).
   - **Arreglo:** en `_texto_procesable` agregar `if "\x00" in valor: return False`. Una línea; con eso `leer_json` responde 400 en el campo con `MENSAJE_TEXTO_INVALIDO`, igual que `leer_multipart`. Las contraseñas siguen fuera de esta revisión (ADR-013).
   - **Si no se corrige:** cualquiera puede provocar errores 500 en una ruta pública y llenar el registro de errores. En la defensa, un 500 a la vista contradice RNF-15.
   - **Estado (2026-10-11): corregido.** `backend/comun/api.py` (`_texto_procesable` rechaza el nulo en `leer_json` y `leer_multipart`) y `backend/comun/texto.py` (`limpiar_texto`, para quien llame sin pasar por `leer_json`). Prueba: `tests/test_validacion_texto.py`, caso «nulo» en los 9 campos de texto escritos a mano; `tests/test_curatoria.py::test_motivo_demasiado_largo_o_con_caracter_nulo_responde_400` ahora espera el mensaje común del nulo y conserva el del motivo para otro carácter de control.

2. **Un script de QA crea cuentas administrativas con una contraseña fija escrita en el repositorio** (`scripts/qa-s5/preparar_datos.py:11` y `:32-35`; `scripts/qa-s5/exportacion_volumen.py:11`)
   - **Qué es:** el script dice «crea datos ficticios en la pila en marcha». Crea cuentas de moderación, curatoría y control de gestión con `PWD = "clave de prueba segura"`, la misma contraseña de `tests/ayudas.py`. El otro script ingresa con ella.
   - **Problema:** si alguien lo corre sobre la copia de demostración (ADR-032), quedan cuentas con roles administrativos cuya contraseña está publicada en GitHub. Incumple la regla (a) de las validaciones mínimas y CLAUDE.md §8 (sin secretos en el repositorio). Hoy la base `altiro-dev` no tiene ninguna de esas cuentas (consulta de solo lectura: 0 filas).
   - **Arreglo:** usar `busqueda.cuentas_demo.contrasena_aleatoria()` e imprimirla una vez, como `cargar_datos_demo` (ADR-028); `exportacion_volumen.py` la lee de una variable de entorno. Cerca de 4 líneas.
   - **Si no se corrige:** un descuido en la demostración deja curatoría y moderación abiertas a cualquiera que lea el repositorio.
   - **Estado (2026-10-11): corregido.** `scripts/qa-s5/preparar_datos.py` usa `contrasena_aleatoria()` y la imprime una vez en el JSON final (ADR-028); `scripts/qa-s5/exportacion_volumen.py` la lee de `QA_S5_CONTRASENA` y se detiene si falta. Revisión con `grep` de `scripts/`: no queda otra contraseña fija (los demás scripts leen `pwd` del JSON que imprime la preparación).

## Conviene corregir

3. **El RUT con espacios al inicio o al final se rechaza** (`backend/identidad/validadores.py:82-86`)
   - **Qué es:** `normalizar_rut` quita puntos y guion, pero no los espacios de los extremos. Lo usan el ingreso (`interpretar_identificador`), la postulación y el perfil de maestro de una cuenta existente.
   - **Problema:** verificado: `POST /api/maestros/postulaciones` con `"rut": " 11.111.111-1 "` responde 400 «Ingresa tu RUT con su dígito verificador…», aunque el RUT es válido. Un maestro que pega su RUT o cuyo teclado agrega un espacio no puede postular ni ingresar, y el mensaje no le dice por qué. HQ-12 lo dejaba abierto; CLAUDE.md §8-§9 (2026-10-11) ya lo decide: recortar.
   - **Arreglo:** `rut = valor.strip().replace(".", "")…` en la línea 84 y el mismo `trim()` en `frontend/js/formulario.js`, que por ADR-031 replica exactamente esta función. `test_pi044` ya admite ambos resultados.
   - **Si no se corrige:** el maestro con poca práctica digital, que es el usuario principal (CLAUDE.md §9), queda trabado en el primer paso.
   - **Estado (2026-10-11): corregido en el servidor.** `backend/identidad/validadores.py` (`normalizar_rut` recorta), lo que cubre ingreso, postulación, perfil de maestro de una cuenta existente y recuperación. Prueba: `tests/test_validacion_texto.py::test_el_rut_con_espacios_en_los_bordes_se_acepta_al_postular_e_ingresar`. **Pendiente:** el mismo `trim()` en `frontend/js/formulario.js` (ADR-031), no tocado por el trabajo en curso de otro agente en `frontend/`.

4. **El mensaje del chat no se recorta y su largo se mide antes de recortar** (`backend/mensajeria/vistas.py:76-84`)
   - **Qué es:** `_envio` revisa que haya un carácter visible y que el texto tenga como máximo 1.000 caracteres, y guarda el texto tal como llegó.
   - **Problema:** `"  hola  "` se guarda con los espacios. Un texto de 999 caracteres con tres espacios al final da 400 «Tu mensaje puede tener hasta 1000 caracteres», aunque su contenido cabe. Incumple la regla (c).
   - **Arreglo:** `texto = texto.strip()` antes de las dos revisiones. El CHECK `mensaje_texto_valido` se sigue cumpliendo.
   - **Si no se corrige:** la conversación guarda espacios sobrantes y hay un 400 confuso en el borde del límite.
   - **Estado (2026-10-11): corregido.** `backend/mensajeria/vistas.py` (`_envio` usa `limpiar_texto`: recorta antes de medir y de guardar; nulo y control → 400). Prueba: `tests/test_validacion_texto.py`, fila «mensaje-texto».

5. **El monto escrito con espacios da «monto inválido», y solo espacios no se trata como vacío** (`backend/perfil/servicios.py:49-60`, también usado por `backend/tickets/vistas.py:48` y `:201-207`)
   - **Qué es:** `_monto` acepta un número o un texto de solo dígitos. Lo usan el servicio publicado y el precio final (RF-26, RF-27).
   - **Problema:** `"monto": " 25000"` da 400 «inválido». `"monto": "   "` da también «inválido» en vez de «falta», cuando un obligatorio con solo espacios debe contar como vacío (regla c). El maestro escribe este dato a mano en el teléfono.
   - **Arreglo:** si es texto, `valor = valor.strip()` al comienzo y tratar `""` como falta. De paso, renombrar `_monto` a `validar_monto`: hoy otra app importa una función privada.
   - **Si no se corrige:** el maestro no puede registrar el precio final por un espacio invisible y no entiende el mensaje.
   - **Estado (2026-10-11): corregido.** `backend/perfil/servicios.py` (`_monto` → `validar_monto`, pública; recorta y solo espacios → «falta»); `backend/tickets/vistas.py` la importa por su nombre público. Pruebas: `test_el_monto_se_recorta_y_solo_espacios_cuenta_como_que_falta` y `test_el_precio_final_con_solo_espacios_dice_que_falta`.

6. **Seis copias de «validar texto libre», cada una con reglas distintas** (`backend/tickets/servicios.py:191-205`, `backend/catalogo/servicios.py:84-99` y `:131-148`, `backend/expediente/servicios.py:346-360`, `backend/evaluaciones/vistas.py:73-95`, `backend/mensajeria/vistas.py:76-84`, `backend/identidad/validadores.py:183-192`)
   - **Qué es:** cada app escribe su propia revisión de nombre, motivo, comentario, dirección o mensaje.
   - **Problema:** como son copias, se separaron. Unas rechazan el carácter nulo y otras no (hallazgo 1). Unas recortan y otras no (hallazgo 4). Unas rechazan caracteres de control (ticket, catálogo) y otras guardan un salto de línea dentro de un nombre de persona (`"Ana\nPrueba"`). Cada regla nueva de CLAUDE.md §8-§9 hay que repetirla seis veces.
   - **Arreglo:** mover `tickets/servicios.py::_texto` (ya recorta, rechaza control y mide el largo después de recortar) a `comun/api.py` como `limpiar_texto(valor, largo, una_linea)` y llamarla desde las seis partes con sus propios mensajes. No se quita ninguna validación: todas quedan iguales o más estrictas.
   - **Si no se corrige:** la próxima regla de texto vuelve a quedar aplicada a medias.
   - **Estado (2026-10-11): corregido.** Ayudante único `backend/comun/texto.py` (`limpiar_texto` y `recortar`), usado por `tickets/servicios.py`, `catalogo/servicios.py` (nombre y motivo), `expediente/servicios.py` (motivo de curatoría), `evaluaciones/vistas.py` (comentario y motivos), `mensajeria/vistas.py` e `identidad/validadores.py` (nombre de persona). Cada uno conserva sus mensajes; ninguna validación se quitó: los motivos y el mensaje ahora también rechazan otros caracteres de control, y el nombre de persona rechaza saltos de línea y tabulaciones. La contraseña no pasa por el ayudante (ADR-013).

7. **Ninguna prueba recorre todos los campos de texto con nulo, solo espacios y largo + 1** (`backend/tests/`)
   - **Qué es:** solo curatoría (`tests/test_curatoria.py:298`) y el ticket prueban el carácter nulo. Las pruebas de espacios cubren el correo y la contraseña.
   - **Problema:** los hallazgos 1, 3, 4 y 5 no los detecta ninguna prueba. La regla (b) exige «400, nunca 500» y hoy nada falla si un campo nuevo la incumple.
   - **Arreglo:** una prueba parametrizada (`@pytest.mark.regla`) con una fila por campo de la tabla de inventario de abajo y tres casos: `"\u0000"` → 400 en el campo, `"   "` → 400 «falta» y largo máximo + 1 → 400 en el campo. Una prueba, unas 40 líneas.
   - **Si no se corrige:** las validaciones mínimas siguen «sin verificar en todas las pantallas» (`docs/estado-actual.md`, punto pendiente de QA).
   - **Estado (2026-10-11): corregido.** `backend/tests/test_validacion_texto.py`: prueba parametrizada (9 campos × 4 casos: nulo, solo espacios, espacios en los bordes con el largo máximo, largo + 1) y pruebas de formato fijo. Sin marca `regla`: el catálogo de `tests/reglas_rnf21.py` (filtros, puntaje, cierre, acceso…) no tiene una regla de validación de texto y no se inventaron identificadores. El motivo de curatoría ya se prueba igual en `test_curatoria.py`.

## Mejoras menores

8. **Los campos de formato fijo no recortan los espacios** (`backend/expediente/servicios.py:134-142` fechas del documento; `backend/perfil/agenda.py:83-87` horas; `backend/gestion/vistas.py:42-49` meses; `backend/tickets/servicios.py:151-162` comuna del pedido)
   - **Qué es:** estos valores los produce un selector o un campo de fecha de la pantalla, no la persona escribiendo.
   - **Problema:** `"fecha_emision": " 2026-01-05"` da 400 «fecha no válida». No llega a ser un 500 y es raro desde la interfaz, pero no cumple la regla (c) al pie de la letra.
   - **Arreglo:** cuando se haga el hallazgo 6, aplicar `.strip()` antes del patrón en estas cuatro funciones.
   - **Si no se corrige:** solo lo nota quien llame a la API a mano (QA, Playwright).
   - **Estado (2026-10-11): corregido.** `recortar` antes del patrón en `expediente/servicios.py` (fechas del documento; solo espacios = vacío), `perfil/agenda.py::minutos_de_hora` (horas de la agenda, del ticket y de la búsqueda), `gestion/vistas.py::_mes` y `tickets/servicios.py` (comuna y fecha del pedido). Prueba: `test_fechas_horas_meses_y_comuna_con_espacios_se_aceptan`.

Se dejaron fuera 2 observaciones menores. La primera: el limitador de ingreso revisa y después escribe sin bloqueo, así que con 2 procesos de gunicorn dos intentos simultáneos pueden sumar un sexto intento antes del bloqueo (máximo un intento extra). La segunda: en un comentario de evaluación que no es texto, el mensaje habla del largo.

**Veredicto:** el backend está sano en autorización, transiciones y privacidad. Lo primero es corregir el 500 por carácter nulo (1, una línea) y quitar la contraseña fija del script de QA (2). Después conviene unificar la validación de texto (6) con su prueba (7), lo que cierra 3, 4 y 5.

**Lean:** se pueden quitar unas 40 líneas (hallazgo 6, las seis copias quedan en una) y 0 dependencias.

**Sin revisar:** frontend (salvo la nota de ADR-031); detalle de `perfil/publicacion.py`, `perfil/fotos.py`, `gestion/indicadores.py` (SQL de percentiles) y `expediente/retencion.py`; los triggers de las migraciones; `busqueda/maestros_por_comuna.py` y `generar_volumen_prueba.py` más allá de sus credenciales (aleatorias o inutilizables: correcto); scripts de `scripts/qa-s4`, `respaldo.sh` y `restaurar.sh`; la configuración completa del proxy. No se corrió la suite completa.

---

## Validaciones mínimas del servidor: inventario

Reglas (CLAUDE.md §8-§9): **(a)** sin credenciales fijas; **(b)** largo máximo validado en el servidor, con 400 en el campo; **(c)** recorte de espacios antes de validar y guardar (salvo contraseñas), y solo espacios cuenta como vacío. Toda entrada JSON pasa por `leer_json`: cuerpo máximo de 1 MB (`DATA_UPLOAD_MAX_MEMORY_SIZE`) y clave desconocida → 400.

### (a) Credenciales fijas

| Lugar | Estado |
|---|---|
| `backend/altiro/settings.py`, `docker-compose.yml`, `infra/init/generar.sh` | Cumple: secretos desde archivos generados (`leer_secreto`), sin valores por defecto. |
| Migraciones y fixtures | Cumple: no hay fixtures ni cuentas en las migraciones. |
| `cargar_datos_demo`, `cuentas_demo.py`, `maestros_por_comuna.py`, `ficticios.py`, `generar_volumen_prueba.py` | Cumple: contraseña con `secrets` impresa una vez, o inutilizable. |
| `crear_usuario_administrativo` | Cumple: la pide con `getpass`, sin argumento de línea de comandos. |
| `backend/tests/ayudas.py:6` | Cumple (solo pruebas, base desechable). |
| `scripts/qa-s5/preparar_datos.py:11`, `scripts/qa-s5/exportacion_volumen.py:11` | **No cumple** (hallazgo 2). |
| Atajos de ingreso o suplantación | Cumple: no hay ninguno (búsqueda de `login_as`, `autologin`, `impersonat` y `backdoor` sin resultados). |

### (b) y (c) por endpoint y campo

| Endpoint | Campo | Largo (b) | Recorte (c) | Estado |
|---|---|---|---|---|
| `POST /api/clientes` (sin sesión) | `nombre` | 150 | sí | **falta rechazar nulo** (500, hallazgo 1) |
| | `telefono` | patrón fijo de 9 dígitos | quita espacios ASCII (ADR-013 E-3) | cumple |
| | `correo` | 254 | sí | cumple |
| | `comuna` | 6 dígitos | sí | cumple |
| | `contrasena` | 128 | no se recorta (ADR-013) | cumple |
| `POST /api/clientes` (con sesión) | `comuna`, `correo`, `telefono` | igual que arriba | igual | cumple |
| `POST /api/maestros/postulaciones` (sin sesión) | `rut` | patrón de 9 caracteres | **no** | **falta recorte** (hallazgo 3) |
| | `nombre` | 150 | sí | **falta rechazar nulo** (hallazgo 1) |
| | `telefono`, `correo`, `contrasena` | como en clientes | | cumple |
| `POST /api/maestros/postulaciones` (con sesión) | `rut` | patrón | **no** | **falta recorte** |
| | `telefono` | patrón | sí | cumple |
| `POST /api/sesion` | `identificador` (correo) | 254 | sí | cumple |
| | `identificador` (RUT) | patrón | **no** | **falta recorte** (hallazgo 3) |
| | `contrasena` | 128 | no se recorta | cumple |
| `POST /api/cuenta/contrasena` | `contrasena`, `contrasena_nueva` | 128 | no se recortan | cumple |
| `POST /api/cuenta/correo` | `correo` | 254 | sí | cumple |
| `POST /api/recuperacion` | `identificador` | como en sesión | RUT sin recorte | **falta recorte** (RUT) |
| `POST /api/recuperacion/contrasena` | `token` | 100 | no aplica (valor de máquina) | cumple |
| `POST /api/tickets` | `direccion` | 200 | sí, sin control ni saltos | cumple |
| | `descripcion` | 1.000 | sí, sin control | cumple |
| | `comuna` | 6 dígitos | no | falta recorte (menor, valor elegido; hallazgo 8) |
| | `fecha`, `inicio`, `fin` | formato fijo | no | falta recorte (menor, valor elegido) |
| | `maestro`, `servicio` | UUID | no aplica | cumple |
| `POST /api/tickets/<ref>/precio-final`, `…/aceptacion` | `monto` | ≤ 10.000.000 | **no** | **falta recorte** (hallazgo 5) |
| `POST /api/tickets/<ref>/mensajes` | `texto` | 1.000 (medido sin recortar) | **no** | **falta recorte y rechazar nulo** (hallazgos 1 y 4) |
| | `clave_envio` | UUID | no aplica | cumple |
| `POST /api/tickets/<ref>/evaluacion` | `comentario` | 500 | sí | **falta rechazar nulo** (hallazgo 1) |
| `POST /api/tickets/<ref>/evaluacion-recibida/denuncia` | `motivo` | 500 | sí | **falta rechazar nulo** (hallazgo 1) |
| `POST /api/moderacion/denuncias/<ref>/resolucion` | `motivo` | 500 | sí | **falta rechazar nulo** (hallazgo 1) |
| | `decision` | lista cerrada | no aplica | cumple |
| `POST /api/avisos/vistos` | `avisos` | ≤ `MAXIMO_VISTOS` UUID | no aplica | cumple |
| Comercial: crear/modificar oficio y servicio | `nombre` | 100 | sí (también espacios internos), sin control | cumple |
| | `motivo` | 1.000 | sí, sin nulo | cumple |
| | `orden`, `version`, `activo`, `regulado`, `modalidades`, `oficio` | números, booleanos o listas cerradas | no aplica | cumple |
| Curatoría: estado del expediente y revisión de documento | `motivo` | 1.000 | sí, sin nulo | cumple |
| | `estado_nuevo`, `estado_actual`, `resultado` | lista cerrada | no aplica | cumple |
| `POST /api/maestros/expediente/oficios` | `oficios` | lista acotada de códigos | no aplica | cumple |
| Carga de documento (multipart) | `tipo`, `oficio` | lista cerrada o código | no | cumple (elegidos) |
| | `fecha_emision`, `fecha_vencimiento` | formato fijo | no | falta recorte (menor, hallazgo 8) |
| | `archivo`, `archivo_reverso` | 8 MB y 25 MP | no aplica | cumple |
| Servicio del maestro: ofrecer y cambiar | `monto` | ≤ 10.000.000 | **no** | **falta recorte** (hallazgo 5) |
| | `servicio`, `modalidad` | UUID o lista cerrada | no aplica | cumple |
| Cobertura | `comunas[].comuna` | 6 dígitos y máximo de comunas | sí | cumple |
| Agenda: bloque | `inicio`, `fin` | `HH:MM` | no | falta recorte (menor, valor elegido) |
| | `dia_semana` | 1 dígito | no aplica | cumple |
| Foto de perfil (multipart) | `archivo` | tope de bytes y píxeles | no aplica | cumple |
| `GET /api/busqueda` (parámetros) | todos | 40 | sí, sin nulo | cumple |
| `GET /api/gestion/indicadores`, `…/exportacion` | `desde`, `hasta` | `AAAA-MM` | no | falta recorte (menor, valor elegido) |
| `GET /api/tickets/<ref>/mensajes` | `despues` | UUID | no aplica | cumple |

**Resumen del inventario:** 5 campos escritos a mano devuelven 500 con un carácter nulo (`nombre` en dos endpoints, `texto`, `comentario` y dos `motivo`). Hay 4 campos escritos a mano sin recorte (`rut` en cuatro endpoints, `monto` en dos endpoints y `texto`). 5 campos de formato fijo, elegidos en pantalla, no se recortan (impacto bajo). Todos los campos tienen un largo máximo en el servidor; ninguno se recorta en silencio.
