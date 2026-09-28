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
