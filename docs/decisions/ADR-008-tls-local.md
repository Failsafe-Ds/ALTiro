# ADR-008 — TLS en la demostración local

- Estado: **Aceptada** — 2026-09-27, aprobada por el equipo de desarrollo.
- Fecha: 2026-09-27
- Relacionado con: RNF-12, R-11, RNF-02, RNF-18

## Contexto
RNF-12: "Conexión cifrada obligatoria, y en la demostración local con un certificado propio declarado como tal". RNF-12 no exige HSTS.

## Decisión propuesta
- **Nginx** como proxy inverso, único servicio con puertos publicados.
- Publicación en `127.0.0.1` por defecto; exponer a la red local solo mediante una variable de entorno. Publicar en `0.0.0.0` dejaría la demo accesible a toda la red del laboratorio.
- Certificado autofirmado generado automáticamente al levantar (si no existe), identificado como "AlTiro demo local, autofirmado", con **SAN configurable** (IP de la red local o nombre del equipo). Chrome ignora el CN, así que sin SAN falla incluso con la CA instalada.
- Puerto 80 solo redirige a 443. Se sugiere 302/307 en la demo, porque un 301 queda en la caché del navegador.
- Cookies `Secure`.
- Cabeceras: CSP sin scripts inline, `X-Content-Type-Options`, `frame-ancestors 'none'`, `Referrer-Policy`.
- El README declara que el certificado es propio y de demostración.

### Sin HSTS en la demostración
- Con certificado autofirmado sin CA instalada, el navegador ignora HSTS: no aporta nada.
- Con mkcert o la CA instalada sobre `localhost`, HSTS sí se guarda y afecta a todos los puertos de `localhost`, lo que rompería otros servidores `http://localhost` en PC de laboratorio compartidos.
- Por eso la configuración de demostración **no emite** `Strict-Transport-Security`. Si se necesita en otro entorno, se activará mediante un ajuste por entorno, desactivado por defecto, emitido en un solo lugar (Nginx), sin `includeSubDomains` ni `preload`.

## Alternativas consideradas
- **Caddy con CA interna**: viable.
- **mkcert**: certificado confiable, pero requiere instalar la CA en cada equipo. Opción para pruebas en Android real.

## Riesgos
- Chrome en Android mostrará advertencias con el certificado autofirmado (afecta pruebas móviles de RNF-02 y RNF-18).
