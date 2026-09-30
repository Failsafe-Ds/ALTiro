# RNF-02 — Página de resultados con red móvil limitada (S4, incremento 3)

- **Requisito (informe §4.2.2):** "La página de resultados debe quedar utilizable en menos de 3 segundos sobre conexión móvil limitada". Umbral: "3 segundos o menos con una conexión móvil de 4 Mbps, y la primera pantalla no debe pesar más de 1,5 MB".
- **Método acordado:** propuesta del S4, §7, y ADR-022, punto 8: Playwright con CDP a 4 Mbps de bajada, 1 Mbps de subida y 150 ms de latencia, más la suma de `transferSize`.
- **Presupuesto de diseño (propuesta del S4, §6):** JS de 30 KB o menos, fotos de 160 px con carga diferida, 20 tarjetas por página y JSON de 50 KB o menos.
- **Estado:** medición **preliminar**, sin los 1.000 tickets (llegan con la app `tickets`, incremento 4). Se repite en el cierre del sprint.
- **Preparado por:** agente `frontend`, 2026-09-29.

## 1. Condiciones

| Dato | Valor |
|---|---|
| Commit | `3c5d357` más los cambios sin confirmar del incremento 3 (`buscar.html`, `js/buscar.js`, `js/hora24.js`, `ayuda-orden.html`, ficha con bloques) |
| Equipo | AMD Ryzen 7 5700X (8 núcleos, 16 hilos), 31,9 GB de RAM, Windows 11 Pro, Docker Desktop (motor 29.8.0) |
| Navegador | Chromium 153.0.8010.12 de la imagen `mcr.microsoft.com/playwright/python:v1.63.0-noble`, en un contenedor de la red de la pila (`altiro_frontal` o `altiro-volumen_frontal`). El script reenvía `127.0.0.1:443` a `proxy:443`, así la página se abre como `https://localhost` |
| Red emulada | `Network.emulateNetworkConditions`: bajada 4.000.000 bit/s (500.000 B/s), subida 1.000.000 bit/s (125.000 B/s), latencia 150 ms. `Network.setCacheDisabled: true` |
| Estado inicial | Contexto de navegador nuevo en cada corrida: sin caché, sin cookies ni sesión y sin conexiones abiertas (cada corrida paga DNS local, TCP y TLS con la latencia emulada) |
| Pantalla | 390 × 800 px, `is_mobile`, `has_touch`, `es-CL` |
| Corridas | 1 de calentamiento del servidor (no se cuenta) + 5 medidas por pila |
| Script | `rnf02.py <etiqueta> <ruta> [corridas]` (scratchpad de la sesión, igual que `rnf18.py`; no está en el repositorio) |

### 1.1 Qué se mide

- **Tiempo hasta "utilizable":** `buscar.js` marca `performance.mark('resultados-listos')` dos cuadros de animación después de pintar las tarjetas de la respuesta de `GET /api/busqueda` (es decir, cuando la lista ya se ve y se puede tocar «Ver perfil»). Se informa `startTime` de esa marca, medido desde el inicio de la navegación (incluye la conexión, el HTML, el CSS, los JS y la búsqueda). Como control, el tiempo de pared desde `page.goto` hasta ver la marca.
- **Peso de la primera pantalla:** con la red en reposo y **sin desplazarse**, la suma de `transferSize` de la navegación y de todos los recursos (HTML, CSS, JS, JSON de la API y fotos que el navegador pidió). Como control, la suma de `encodedDataLength` de CDP (`Network.loadingFinished`), que además cuenta las cabeceras de la conexión.
- Se comprueba además que las fotos de las tarjetas visibles terminaron de cargar.

## 2. Resultados

### 2.1 Pila principal (maestros demo)

`/buscar.html?oficio=pintura&region=8&comuna=8101`: 4 tarjetas.

| Corrida | resultados-listos | Pared | Bytes (`transferSize`) | Bytes (CDP) | Peticiones | Fotos |
|---|---|---|---|---|---|---|
| 1 | 0,693 s | 0,713 s | 99.658 | 101.050 | 16 | 4 |
| 2 | 0,678 s | 0,698 s | 99.658 | 101.050 | 16 | 4 |
| 3 | 0,693 s | 0,713 s | 99.658 | 101.050 | 16 | 4 |
| 4 | 0,688 s | 0,708 s | 99.658 | 101.050 | 16 | 4 |
| 5 | 0,683 s | 0,703 s | 99.658 | 101.050 | 16 | 4 |
| **Mediana / máximo** | **0,688 s / 0,693 s** | | **97,3 KiB** | | | |

### 2.2 Pila aparte `altiro-volumen` (100 maestros sintéticos)

Levantada con `ALTIRO_HTTP_PORT=8080 ALTIRO_HTTPS_PORT=8443 DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost:8443,https://127.0.0.1:8443 docker compose -p altiro-volumen up -d` (sobre los volúmenes que dejó la medición de RNF-01, `rnf-01-medicion.md`) y detenida después con `docker compose -p altiro-volumen down`, **sin** `-v`.

Ninguna combinación de oficio y comuna del volumen supera 20 resultados (el máximo encontrado fue 16), así que se midió la búsqueda con más tarjetas: `/buscar.html?oficio=cerrajeria&region=8&comuna=8111` (16 tarjetas).

| Corrida | resultados-listos | Pared | Bytes (`transferSize`) | Bytes (CDP) | Peticiones | Fotos |
|---|---|---|---|---|---|---|
| 1 | 0,696 s | 0,715 s | 97.546 | 99.637 | 20 | 8 |
| 2 | 0,687 s | 0,706 s | 97.546 | 99.637 | 20 | 8 |
| 3 | 0,687 s | 0,707 s | 97.546 | 99.637 | 20 | 8 |
| 4 | 0,700 s | 0,720 s | 97.546 | 99.637 | 20 | 8 |
| 5 | 0,690 s | 0,710 s | 97.546 | 99.637 | 20 | 8 |
| **Mediana / máximo** | **0,690 s / 0,700 s** | | **95,3 KiB** | | | |

Con 16 tarjetas el navegador pidió solo 8 fotos: `loading="lazy"` deja las demás para cuando la persona se desplaza.

### 2.3 Desglose (última corrida de la pila principal)

| Recurso | Bytes transferidos |
|---|---|
| `css/base.css` | 22.167 |
| `js/buscar.js` | 20.730 |
| `js/formulario.js` | 12.476 |
| `js/api.js` | 6.480 |
| `js/formato.js` | 4.460 |
| `js/territorio.js` | 4.415 |
| `js/hora24.js` | 2.862 |
| **JS en total** | **51.423** |
| `GET /api/busqueda` (4 tarjetas / 16 tarjetas en el volumen) | 1.632 / 5.704 |
| `GET /api/oficios`, regiones y comunas | 5.395 |
| 4 fotos de 160 px | 12.079 |

### 2.4 Veredicto

| Umbral | Medido (peor caso) | Resultado |
|---|---|---|
| 3 s o menos a 4 Mbps | 0,700 s | **Cumple** |
| Primera pantalla de 1,5 MB o menos | 97,3 KiB (≈ 0,1 MB) | **Cumple** |

## 3. Validez y limitaciones

- **Servidor local.** El servidor está en el mismo equipo: el tiempo de respuesta del servidor es casi nulo y lo que domina es la red emulada (latencia y ancho de banda). En un servidor real se sumaría su tiempo de respuesta; RNF-01 lo mide aparte (p95 de 0,168 s con 10 personas a la vez). Aun sumando 2 s de búsqueda lenta (el límite de RNF-01) quedaría bajo 3 s.
- **Sin tickets.** Hoy la ocupación de agenda responde vacío (propuesta del S4, §11.8). Con los 1.000 tickets la búsqueda agrega una consulta en lote; se repite la medición en el cierre del sprint.
- **Fotos sintéticas.** Las fotos del volumen pesan unos 740 bytes y las de los maestros demo entre 0,7 y 4,5 KB. Una foto real de 160 px en JPEG puede pesar 5 a 10 KB: aun con 20 fotos de 10 KB (200 KB) la primera pantalla seguiría muy por debajo de 1,5 MB.
- **Página de 20 tarjetas.** No hay datos reales con más de 16 resultados. El JSON crece unos 340 bytes por tarjeta: 20 tarjetas son unos 7 KB, lejos del presupuesto de 50 KB.
- **Sin compresión.** El proxy no comprime (`gzip` no está activado en `infra/proxy`). Los tiempos y pesos medidos ya son sin comprimir.
- **Presupuesto de JS de la propuesta (30 KB): no se cumple.** La página carga 51,4 KB de JS sin comprimir (buscar.js 20,7 KB, más los módulos compartidos `formulario.js`, `api.js`, `formato.js`, `territorio.js` y `hora24.js`, que no se duplican). Ese presupuesto es una meta de diseño de la propuesta, no el umbral del informe, que se cumple con holgura. Opciones para el arquitecto: activar `gzip` en el proxy (el JS quedaría cerca de 15 KB transferidos) o aceptar el presupuesto como "30 KB comprimidos". **No se cambió `infra/`**: queda para `architect` o `backend`.
- **Chromium de Playwright, no un teléfono.** La emulación de red de CDP no reproduce la CPU lenta de un teléfono de gama baja ni la pérdida de paquetes. El pase manual de RNF-18 en Chrome de Android (con la red limitada del navegador) sirve de contraste.
- **Firefox no se midió:** Playwright no ofrece emulación de red en Firefox. RNF-02 no nombra un navegador; se usó el mismo motor que Chrome en Android.

## 4. Medición de cierre S4 (volumen completo: 100 maestros, 1.000 tickets)

Preparado por: agente `qa`, 2026-09-30. Commit `f3e4fed`. Pila `altiro-volumen` con los 1.000 tickets de `rnf-01-medicion.md`.

- Método: el de D-19 / §1 de este documento. Playwright 1.63.0 con Chromium 153.0.8010.12 (imagen `mcr.microsoft.com/playwright/python:v1.63.0-noble`), 390 × 800 móvil, sin caché, contexto nuevo por corrida, CDP a 4 Mbps de bajada, 1 Mbps de subida y 150 ms. 1 corrida de calentamiento y 5 medidas. Script: `scripts/qa-s4/rnf02.py`. "Utilizable": buscar = tarjetas pintadas (`resultados-listos` equivalente, dos cuadros después de ver el enlace «Ver perfil»); ficha = perfil visible y al menos un horario listado.
- Cambio respecto de §2: el proxy ahora comprime con gzip, por lo que los bytes bajan.

| Pantalla | Utilizable (mediana / máximo) | Primera pantalla (`transferSize`) | Peticiones | Umbral |
|---|---|---|---|---|
| `buscar.html?oficio=cerrajeria&region=8&comuna=8111` (16 tarjetas) | 0,554 s / 0,567 s | 35,8 KiB (36.687 B; CDP 38.836 B) | 20 | 3 s y 1,5 MB |
| `perfil-maestro.html?m=<ref>` (ficha con horarios libres y ocupados) | 0,530 s / 0,535 s | 17,8 KiB (18.240 B; CDP 18.758 B) | 7 | 3 s y 1,5 MB |

**Veredicto RNF-02: cumple** con el volumen completo (peor caso 0,567 s frente a 3 s; 35,8 KiB frente a 1,5 MB). Las limitaciones de §3 siguen vigentes (servidor local, Chromium y no un teléfono, fotos sintéticas). Con gzip, el presupuesto de JS de 30 KB de la propuesta se cumple como "comprimido": toda la primera pantalla de buscar pesa 35,8 KiB.
