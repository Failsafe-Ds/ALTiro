# Sistema visual de AlTiro (MASTER)

Fuente única de los valores visuales del rediseño (ADR-002 E-3, 2026-10-11). Si una página necesita algo distinto, va en `design-system/altiro/pages/<pagina>.md` y prevalece sobre este archivo solo para esa página.

Preparado por Claude con la skill UI/UX Pro Max (pila `html-css`). La skill sugirió azul corporativo; se reemplazó por rojo según la decisión del usuario. Contrastes calculados con la fórmula de WCAG 2.2 (RNF-16).

## Dirección
- **Referencia:** Fiverr. Fondo blanco y mucho aire, texto casi negro, el color de marca solo en la marca, las acciones principales, los enlaces activos y los acentos. Estilo plano: sin degradados, sombras mínimas (solo al pasar el cursor o en menús desplegables).
- **Tono:** cercano y confiable. Es un marketplace de maestros del hogar en Chile; la confianza (verificado, estrellas, precio claro) pesa más que el adorno.
- **Mobile-first:** se diseña a 360 px y se amplía a 768 px y 1024 px. Sin scroll horizontal (RNF-18).

## Color (variables CSS en `frontend/css/base.css`, `:root`)
| Variable | Valor | Uso | Contraste |
|---|---|---|---|
| `--marca` | `#C8102E` | botón principal, marca, enlace activo, acentos | blanco sobre él 5,88:1; él sobre blanco 5,88:1 |
| `--marca-oscura` | `#A50E26` | botón principal al pasar el cursor o presionado | blanco 7,8:1 |
| `--marca-suave` | `#FFF4F4` | fondo de sección destacada, ítem activo del menú lateral | `--marca` sobre él 5,46:1 |
| `--texto` | `#1F1F1F` | texto principal | 16,5:1 |
| `--texto-suave` | `#5A5A5A` | texto secundario (comuna, cantidad de evaluaciones) | 6,9:1 (6,4:1 sobre `--marca-suave`) |
| `--fondo` | `#FFFFFF` | fondo general | — |
| `--fondo-suave` | `#F6F6F6` | bandas, pie, fondo del menú lateral | `--marca` sobre él 5,44:1 |
| `--borde` | `#767676` | bordes de campos y controles (≥ 3:1) | 4,54:1 |
| `--linea` | `#E4E4E4` | separadores decorativos (no son límites de control) | decorativo |
| `--estrella` | `#8A4B00` | ícono de estrella y nota | 6,8:1 |
| `--error` / `--error-fondo` | `#7A0A1C` / `#FDECEE` | mensajes de error, siempre con ícono y la palabra «Error» o el texto del problema | 9,75:1 |
| `--exito` / `--exito-fondo` | `#1B6E20` / `#E8F5E9` | mensajes de éxito, con ícono | 5,66:1 |
| `--foco` | `#000000` | anillo de foco de 2 px con separación de 2 px | 3,57:1 contra `--marca`; 21:1 contra blanco |

- El error usa un rojo vino distinto de la marca **y** siempre lleva ícono y texto: nunca se distingue solo por el color (RNF-16).
- Nada de hex sueltos en las reglas: todo pasa por estas variables.

## Tipografía
- **Fuente:** Plus Jakarta Sans (licencia OFL), **alojada en el sitio** (`frontend/fuentes/`, woff2, solo el subconjunto latino, pesos 400 a 700 en un archivo variable). La CSP solo permite `font-src 'self'`; no se usa Google Fonts.
- Respaldo: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`, con `font-display: swap`.
- Tamaños (rem): cuerpo 1,0625 (17 px), pequeño 0,9375, h1 1,75 (2 en ≥ 768 px), h2 1,3, h3 1,1. Interlineado 1,5 en el cuerpo y 1,25 en los títulos. Nunca menos de 0,875 rem.
- Pesos: 400 cuerpo, 600 nombres y etiquetas, 700 títulos y marca.

## Espaciado, forma y movimiento
- Escala: 0,25 · 0,5 · 0,75 · 1 · 1,5 · 2 · 3 rem (`--esp-1` a `--esp-7`).
- Radio: 0,5 rem en controles; 0,75 rem en fotos de maestro; botones con radio 0,5 rem (no píldora).
- Objetivos táctiles de 44 × 44 px mínimo y 8 px entre ellos (RNF-14).
- Transiciones de 150 a 200 ms solo en color y opacidad; con `prefers-reduced-motion: reduce`, ninguna.
- Íconos: SVG en línea dentro de los archivos JS/HTML (nunca emoji), `aria-hidden="true"` cuando acompañan texto.

## Componentes
- **Encabezado sin sesión:** solo la marca «AlTiro» (700, en blanco sobre el rojo del encabezado), enlace a `index.html`. Nada más.
- **Encabezado con sesión:** marca a la izquierda (lleva al inicio del flujo, E-3.2) y botón «Menú» a la derecha (E-2).
- **Fondo del encabezado (ambas versiones, E-4.1):** degradado vertical de `--encabezado-arriba` (`#A50E26`) a `--encabezado-abajo` (`#C8102E`), sin línea inferior. Marca en blanco (5,88:1 o más). Botones del encabezado con relleno blanco, texto y contorno negros de 2 px. Anillo de foco blanco dentro del encabezado (el negro no llega a 3:1 sobre el rojo oscuro).
- **Pie:** fondo `--fondo-suave`, texto `--texto-suave`, «© 2026 AlTiro» + aviso de prueba de concepto + versión.
- **Maestro en resultados (estilo Fiverr, sin tarjeta):** foto 4:3 con radio 0,75 rem arriba; debajo, nombre (600) con la insignia «Verificado» (ícono + texto); oficio; fila de estrellas (`--estrella`) con nota y cantidad entre paréntesis (`4,8 (23)`), o «Sin evaluaciones aún»; «Atiende en: …» en `--texto-suave`; precio «Desde $X» en 600. Todo el bloque es un solo enlace al perfil (un solo destino de tabulación). Grilla: 1 columna en 360 px, 2 en ≥ 560 px, 3 en ≥ 900 px y 4 en ≥ 1200 px.
- **Categorías (inicio del cliente), E-4.1:** carrusel en abanico (solo en esta página): tarjeta grande al centro (17 rem; ícono de 6 rem, nombre 700 y «Ver maestros» como botón principal), blanca con borde `--marca` y sombra; a los lados, dos más chicas (escala 0,8 y 0,62), giradas en 3D e inclinadas en diagonal, en `--fondo-suave` (en el celular, una por lado). Avanza solo cada 4 s y se detiene con mouse encima, foco o toque. Sin botones (E-4.2): debajo, solo un punto por oficio (44 px en PC, 32 px en el celular).
- **Página de opciones (estilo Steam):** en ≥ 768 px, menú lateral de 14 a 16 rem a la izquierda (fondo `--fondo-suave`, ítem activo con `--marca-suave`, barra izquierda de 3 px `--marca` y `aria-current="page"`) y contenido a la derecha. En celular, el menú va arriba como lista de enlaces o `<details>` plegable.
- **Botones:** principal (fondo `--marca`, texto blanco, 600); secundario (borde `--borde`, texto `--texto`); peligro (texto `--error` con borde). Desactivado: opacidad 0,6 y `cursor: not-allowed`, con el texto de la carga («Enviando…»).
- **Indicador de carga:** botón desactivado con texto de espera, y en las listas un aviso «Cargando…» con `aria-live="polite"`. Sin rueditas que giren solas sin texto.
- **Mensajes:** caja con ícono, borde izquierdo de 4 px, título breve y la acción a seguir; `role="alert"` para errores y `role="status"` para éxitos.

## Prohibido
- Tailwind, shadcn u otra biblioteca de componentes que no sea Bootstrap 5.3 (ADR-002 E-4). Bootstrap toma los colores de este archivo mediante las variables `--bs-*` de `base.css`; sus colores propios (azul `primary`, etc.) no se usan.
- Estilos o scripts en línea (CSP); fuentes, imágenes o íconos desde otros dominios.
- Emoji como ícono, estados comunicados solo con color, texto gris claro sobre blanco con menos de 4,5:1.
