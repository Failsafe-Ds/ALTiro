# QA acotado v0.6.9 (ADR-002 E-4.4), 2026-10-31

Entorno: altiro-dev (https://localhost:8443, Docker), Playwright 1.63 / Chromium en la red del proxy. Sin cambios al código del producto. Cuentas demo regeneradas por comando; sin contraseñas en este informe.

| # | Tarea | Resultado |
|---|-------|-----------|
| 1 | Suite completa (pytest) | PASS: `2129 passed in 764.04s (0:12:44)`, sin fallas |
| 2 | DEF-CHR-01 de punta a punta | PASS (ver abajo) |
| 3 | Revisión visual 390 y 1280 px | PASS sin defectos de diseño; 1 observación baja |
| 4a | Contraste/accesibilidad (axe-core 4.10.2, wcag2a/aa/21aa/22aa, incl. color-contrast) en index, buscar, mis-trabajos a 390 y 1280 | PASS: 0 violaciones en las 6 combinaciones |
| 4b | Peso de la portada (RNF-02: primera pantalla <= 1,5 MB) | PASS: 12 recursos, 368 KB (suma de content-length o cuerpo). El tiempo <= 3 s a 4 Mbps no se midió: BLOCKED a la medición con red emulada (pendiente de QA de cierre) |

## Tarea 2 (DEF-CHR-01)
- Cliente demo 1 creó por API dos pedidos nuevos al maestro demo (201 y 201; marcas «QA ACEPTAR» / «QA RECHAZAR»).
- Maestro, por pantalla a 390 px: Mis trabajos > Ver detalle > «Aceptar este pedido»: aparece «¿Aceptar este pedido?» con botón visible; «Sí» envía `POST /api/tickets/<ref>/aceptacion` (200); aviso «Aceptaste el pedido.» (`aria-live=polite`).
- Igual con «Rechazar»: `POST /api/tickets/<ref>/rechazo` (200); aviso «Rechazaste el pedido.».
- Aceptados +1 y Historial +1. En estado Pendiente el detalle no mostró dirección ni teléfono del cliente.
- Conclusión: DEF-CHR-01 corregido (frontend/js/mis-trabajos.js:255).

## Tarea 3
Páginas: ficha del maestro, curatoría, comercial, agenda, cobertura, documentos, moderación, indicadores (más portada, buscar, mis-trabajos). Medición por DOM: sin desborde horizontal (scrollWidth = ancho), sin elementos fuera de pantalla, sin errores JS, sin objetivos <44 px salvo lo siguiente. Capturas en el scratchpad (`...\scratchpad\cap\*.png`), no en el repo.
- Observación (baja, DEF-QA-001): en `perfil-maestro.html` los 3 `input[type=radio]` de servicio miden 28x28 px (`frontend/js/perfil-publico.js:199`; `accent-color` en `frontend/css/base.css:2724`). El control dentro de una tarjeta-etiqueta completa mide más de 44 px, por lo que el área táctil real cumple; no hay incumplimiento comprobado. Sin solapes ni textos cortados visibles (los `solo-lector` son texto oculto a propósito).

## Pendientes / no verificado
- Tiempo <= 3 s con red limitada (RNF-02) y el barrido completo de compatibilidad quedan para el QA de cierre de sprint.
- Defectos DEF-CHR-02, 03, 04 siguen abiertos (no son parte de v0.6.9).

## Veredicto
Sin defectos nuevos de severidad alta o media. v0.6.9 puede ir a commit.
