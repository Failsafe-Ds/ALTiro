# ADR-002 — Estilo de interfaz

- Estado: **Aceptada** — 2026-09-27, aprobada por el equipo de desarrollo.
- Fecha: 2026-09-27
- Relacionado con: RF-02, RNF-02, RNF-07, RNF-08, RNF-20

## Contexto
El informe define frontend en HTML, CSS y JavaScript (§4.1). Hay que decidir si el servidor entrega plantillas o una API. RNF-08 se comprueba "revisando lo que el servidor manda y no lo que la pantalla muestra".

## Decisión propuesta
API JSON bajo `/api/` y un frontend estático (HTML/CSS/JS sin framework) servido por el proxy.

## Supuesto a validar
Con frontend estático, el HTML de una página privada puede descargarse sin sesión, pero no contiene datos: todos los datos privados se obtienen de `/api/`, que exige autenticación. Se interpreta que esto cumple RF-02 ("Un usuario no autenticado no accede a ninguna vista privada"). Si el equipo no acepta esta interpretación, la alternativa es servir las páginas privadas desde Django tras verificar la sesión.

## Alternativas consideradas
- **Plantillas renderizadas en el servidor**: menos JavaScript, pero verificar RNF-08 es más directo sobre JSON.

## Consecuencias
- Pruebas de privacidad y de autorización sobre respuestas JSON.
- El frontend maneja CSRF y los errores en `js/api.js`.
- Sin framework, el peso de página favorece RNF-02.
- Al conservar el progreso de formularios (RNF-20), nunca se guarda la contraseña y se minimizan los datos personales en `localStorage`, porque hay teléfonos compartidos.

## Enmiendas

### E-1 — Vencimiento del progreso guardado en el navegador (M-4)
- **Fecha:** 2026-09-28.
- **Motivo:** el progreso de los formularios (RNF-20) quedaba en sessionStorage sin vencimiento. En un teléfono compartido podía quedar el RUT, el correo o el teléfono escrito por otra persona. Es el hallazgo M-4 de la revisión `ux` (`docs/testing/saneamiento-sprint-1.md`, anexo).
- **Cambio:**
  - Todo lo guardado lleva la hora del último cambio y **vence a las 2 horas**. El plazo se reinicia con cada cambio.
  - Al cargar una página con formularios se borran las claves `altiro.*` vencidas.
  - Al cerrar sesión con éxito se borran todas las claves `altiro.*`.
  - Nunca se guarda la contraseña.
- **Por qué 2 horas:** la sesión vence a los 30 minutos (RNF-09) y la postulación debería tomar 10 minutos o menos (RNF-13). Dos horas dan margen para recuperar la señal y volver a ingresar (RNF-20) sin conservar los datos indefinidamente.
- **Aprobación:** equipo de desarrollo, 2026-09-28 (Sprint 2, incremento 0).

## Enmienda 2026-10-01: pie de página y «← Volver»

- Pie `<footer class="pie" role="contentinfo">` estático en todas las páginas (también `errores/`) con copyright y aviso de prueba de concepto. La versión sale de un solo archivo, `frontend/js/version.js` (`ALTIRO_VERSION`, se cambia en cada iteración), y `js/pie.js` la escribe en el pie.
- Enlace `← Volver` (`a[data-volver]`, `href` de respaldo real) en el encabezado de todas las páginas salvo `index.html`, `errores/*` y las tres que ya tienen enlace a su padre (`conversacion`, `evaluar`, `curatoria-expediente`). `js/volver.js` usa `history.back()` si el origen anterior es del mismo sitio o si hay un paso interno; si no, sigue el respaldo.
- Pasos internos con `history.pushState({altiroPaso})`: `buscar.js` (formulario, horario, resultados) y `formulario.porPasos` (postulación, pedir trabajo). Atrás del teléfono retrocede un paso sin perder lo escrito (RNF-20).
