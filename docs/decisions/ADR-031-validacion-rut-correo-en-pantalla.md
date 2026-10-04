# ADR-031 — Validación en pantalla de RUT y correo

- Estado: **Propuesta** (2026-10-03). Implementada a pedido del usuario; se revisa con el equipo.
- Relacionado con: RF-01, RF-02, RF-03, RNF-13, RNF-15, RNF-20; ADR-013 (puntos 1 y 5), ADR-027.

## Contexto
El servidor ya valida el RUT con el dígito verificador módulo 11 (`identidad/validadores.py`, `normalizar_rut`), sin dependencias externas. También valida el correo (`normalizar_correo`) y el identificador de ingreso, que puede ser correo o RUT (`identidad/autenticacion.py`, `interpretar_identificador`). Pero la pantalla no revisaba nada: un RUT o un correo mal escrito se descubría recién después del viaje al servidor. En un formulario por pasos, el error aparecía al final, en un paso que ya se había dejado atrás. Con conexión irregular, eso cuesta un envío completo.

El usuario pidió validar el RUT y el correo también en pantalla, sin dependencias. Se descartó pedir RUT al cliente: RF-01 y HU-01 no lo incluyen, y agregarlo sería un cambio de alcance.

## Decisión
1. `frontend/js/formulario.js` incorpora `errorRut`, `errorCorreo`, `errorIdentificador` y `revisar(form, zona)`. No usa bibliotecas.
2. Cada campo se marca con `data-validar="rut" | "correo" | "identificador"`. Se revisa:
   - al pulsar «Continuar», solo los campos del paso actual;
   - antes de cada envío, todo el formulario.

   Si hay error, no se llama al servidor: el mensaje queda junto a su campo (RNF-15) y el foco va al campo. Los campos vacíos los resuelven `required` o el servidor.
3. **El servidor sigue siendo la validación que vale.** Para no duplicar la regla con criterios distintos, la pantalla replica exactamente `normalizar_rut` y `interpretar_identificador`, con los mismos textos de error:
   - quita puntos y guion;
   - exige 1 a 8 dígitos más el DV (0-9 o K);
   - rechaza el cero inicial (HQ-12);
   - calcula el DV con módulo 11, con factores 2 a 7 desde la derecha: 11 → "0" y 10 → "K".
4. El correo se revisa de forma **básica**. Exige:
   - una @ con texto antes;
   - un dominio con punto, sin etiquetas vacías y con terminación de 2 o más caracteres;
   - ningún espacio, y no más de 254 caracteres.

   La regla completa la aplica `EmailValidator` en el servidor. La pantalla nunca rechaza un correo común que el servidor acepte. Solo serían rechazadas en pantalla y aceptadas por el servidor estas formas raras: parte local entre comillas, dominio `localhost` y dominio IPv6 literal.
5. Formularios cubiertos:
   - Ingresar e «Olvidé mi contraseña» (`identificador`);
   - registro de cliente (`correo`);
   - postulación de maestro (`rut` y `correo` opcional);
   - «Mi cuenta»: agregar perfil de cliente (`correo`), agregar perfil de maestro (`rut`) y cambiar correo (`correo`).

## Consecuencias
- Si cambia la regla del servidor (HQ-11, HQ-12), hay que cambiar también la de pantalla. El script `scripts/validacion-pantalla/verificar.sh` detecta cualquier diferencia: genera los resultados con los validadores reales del servidor y los compara con `formulario.js` en Node.
- Ninguna regla de negocio nueva. El modelo, la API y los RF no cambian.

## Verificación (2026-10-03)
- **Comparación servidor/pantalla:** 3.085 casos (1.520 RUT con DV correcto o alterado y en distintos formatos, correos límite e identificadores). Resultado: 0 diferencias en RUT e identificador con RUT, y 0 casos en que la pantalla sea más estricta que el servidor. 4 casos de correo los deja pasar la pantalla y los rechaza el servidor («ñandú@…», TLD con dígito); se toleran y el servidor responde.
- **Navegador:** Chromium 360 px con Playwright, 17 comprobaciones. En las 6 pantallas, un dato inválido no llama a la API y el mensaje queda en el campo; un dato válido sigue el flujo normal; no hay errores de JavaScript.
- `tests/test_frontend_pie_volver.py`: 59 aprobadas.
