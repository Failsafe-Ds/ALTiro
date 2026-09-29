# Evidencia RNF-16 — Contraste y codificación de estados

- **Requisito:** RNF-16. Umbral literal: "Contraste suficiente entre texto y fondo según la guía de accesibilidad WCAG 2.2, y ningún estado indicado solo con color".
- **Criterios usados:** WCAG 2.2 AA. Texto: 4,5:1 (1.4.3). Bordes, íconos y foco: 3:1 (1.4.11). Estados: texto además del color (1.4.1).
- **Fecha:** 2026-09-28, cierre de UX del Sprint 2 (frontend). Base: commit `e06d2d2` más los cambios de este cierre, sin commit.
- **Preparado por:** agente `frontend`, a partir de la tabla de la revisión `ux` del cierre del Sprint 2. Las razones se recalcularon con la fórmula de luminancia relativa de WCAG.

## 1. Tabla de contrastes

Colores de `frontend/css/base.css`, en los pares que aparecen en pantalla.

| Par | Primer plano | Fondo | Razón |
|---|---|---|---|
| Texto normal | `#1a1a1a` | `#ffffff` | 17,40:1 |
| Texto suave (ayudas, progreso, `dt`) | `#4a4a4a` | `#ffffff` | 8,86:1 |
| Texto suave sobre fondo suave (estado Suspendido) | `#4a4a4a` | `#f3f4f6` | 8,05:1 |
| Texto sobre fondo suave (estado En revisión, casilla marcada) | `#1a1a1a` | `#f3f4f6` | 15,81:1 |
| Enlace / botón secundario | `#0b5cad` | `#ffffff` | 6,67:1 |
| Botón secundario en hover | `#0b5cad` | `#f3f4f6` | 6,06:1 |
| Botón primario (texto blanco) | `#ffffff` | `#0b5cad` | 6,67:1 |
| Botón primario hover | `#ffffff` | `#084a8c` | 8,87:1 |
| Filtro activo de la cola (blanco sobre azul, con ✓) | `#ffffff` | `#0b5cad` | 6,67:1 |
| Aviso de error | `#b00020` | `#fdecee` | 6,42:1 |
| Error de campo sobre blanco | `#b00020` | `#ffffff` | 7,33:1 |
| Botón peligro (rechazar) | `#ffffff` | `#b00020` | 7,33:1 |
| Botón peligro hover | `#ffffff` | `#8c0019` | 9,86:1 |
| Aviso de éxito, estado Aprobado y resultado junto al documento | `#1b6e20` | `#e8f5e9` | 5,66:1 |
| Estado Observado | `#8a4b00` | `#fff4e5` | 6,26:1 |
| Avisos de vencimiento y motivo (texto) | `#1a1a1a` | `#fff4e5` | 16,02:1 |
| Ícono ⚠ del aviso de vencimiento | `#8a4b00` | `#fff4e5` | 6,26:1 |
| Estado Rechazado / Vencido | `#b00020` | `#fdecee` | 6,42:1 |
| Borde de campos y tarjetas (no texto) | `#6b7280` | `#ffffff` | 4,83:1 |
| Foco (contorno negro) sobre blanco | `#000000` | `#ffffff` | 21,00:1 |
| Foco contra el botón primario | `#000000` | `#0b5cad` | 3,15:1 |
| Borde de campo con error (3 px) | `#b00020` | `#ffffff` | 7,33:1 |
| Borde izquierdo de la sección "Avisos" | `#8a4b00` | `#fff4e5` | 6,26:1 |

**Resultado:** todos los textos superan 4,5:1. Todos los bordes, íconos y el foco superan 3:1. El par más ajustado es el foco contra el botón primario (3,15:1), que cumple 1.4.11.

## 2. Estados sin depender del color (1.4.1)

| Estado | Cómo se distingue sin color |
|---|---|
| Estados del expediente y del documento | Ícono y texto (⏳ En revisión, ⚠ Observado / Te pedimos corregir algo, ✓ Aprobado / Validado, ✕ Rechazado / No aprobado, ⏸ Suspendido con borde punteado, ↺ Reemplazado) |
| Documento vencido | "Venció el …" y etiqueta "⚠ Vencido". Nunca "quedan 0 días" ni números negativos |
| Días restantes | Texto: "Quedan N días." o "Queda 1 día." |
| Avisos de vencimiento (RF-35) | Sección titulada "Avisos" y cada aviso con ⚠ y el texto completo |
| Error de campo | Texto "⚠ …" junto al campo, `aria-describedby`; borde de 3 px. `aria-invalid` solo en campos de texto y listas |
| Foto con error | Texto junto a los botones, enlazado con `aria-describedby`, y borde de 3 px en el bloque de la foto |
| Filtro activo | `aria-pressed="true"` y "✓" antes del texto |
| Botón ocupado | Texto "Enviando…" / "Guardando…" y borde punteado |
| Aviso de éxito o de error | "✓" o "⚠" y texto, más el borde izquierdo |

Las marcas decorativas en CSS (`.nota-licencia`, `.cuenta-pendiente`) usan un carácter antiguo de Unicode ("►") con texto alternativo vacío (`content: "► " / ""`), para que el lector de pantalla no lea la descripción de un emoji. Así se cerró el hallazgo del 🪪.

## 3. Pasada automática con axe-core

- **Herramienta:** axe-core 4.10.3, descargado dentro del contenedor de Playwright (`mcr.microsoft.com/playwright/python:v1.55.0-noble`) desde jsDelivr. SHA-256 `880970c081707360e64f34cea25ff91892f5bc95675b0776925b9709dd8a68bb`. **No se agregó ninguna dependencia al proyecto.**
- **Reglas:** etiquetas `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa` y `wcag22aa`.
- **Entorno:** Chromium en contexto móvil de 390 × 844 px. Curatoría también a 1280 px. Stack local por Docker Compose. Datos ficticios.
- **Script:** `axe_s2.py` (scratchpad de la sesión; no está en el repositorio).

| Página | Ancho | Violaciones | Por revisar a mano |
|---|---|---|---|
| Inicio | 390 | 0 | — |
| Ingresar | 390 | 0 | — |
| Ingresar tras postular (aviso "Primer paso listo") | 390 | 0 | — |
| Registro de cliente | 390 | 0 | — |
| Postulación de maestro | 390 | 0 | — |
| Postulación con errores visibles | 390 | 0 | — |
| 404 | 390 | 0 | — |
| Mis documentos (con aviso) | 390 | 0 | color-contrast (íconos) |
| Visor de foto | 390 | 0 | — |
| Mi postulación: resumen (con aviso) | 390 | 0 | color-contrast (íconos) |
| Mi postulación: paso de documento con errores | 390 | 0 | color-contrast (ícono) |
| Mi cuenta | 390 | 0 | — |
| Curatoría: cola con avisos | 390 y 1280 | 0 | — |
| Curatoría: detalle del expediente | 390 y 1280 | 0 | color-contrast (íconos y áreas de texto) |

**Total: 0 violaciones.**

Casos "por revisar" (axe no puede decidirlos) y cómo se resolvieron a mano:

1. **Íconos de estado** (`.estado > span[aria-hidden]`, "Element content contains only non-text characters"). El ícono es decorativo y va junto al texto del estado, con el mismo color. Los colores están en la tabla del §1: entre 5,66:1 y 15,81:1. **Cumple.**
2. **Áreas de texto de curatoría** (`#motivo-documento-N`, `#motivo-estado`, "background … partially obscured"). El texto `#1a1a1a` va sobre fondo `#ffffff`: 17,40:1. **Cumple.**

## 4. Limitaciones

- axe no reemplaza la revisión manual del orden de foco ni la prueba con lector de pantalla real (TalkBack o VoiceOver). Esa prueba queda pendiente.
- La pasada se hizo en Chromium. Firefox y Safari (RNF de compatibilidad) no se probaron aquí.
- La sintaxis `content: "…" / ""` requiere Chrome 77+, Safari 17.4+ o Firefox 128+. En navegadores anteriores se usa la primera declaración y el lector puede leer "►". Es texto, no un emoji, así que el impacto es menor.
