# Protocolo de prueba de usabilidad — RNF-13

- **Requisito:** RNF-13. Umbral literal: "Al menos 2 de 3 participantes de prueba la completan en ≤ 10 minutos" (la postulación del maestro, sin ayuda).
- **Estado:** protocolo listo (2026-09-28), **sin ejecutar**. Requiere personas externas y un teléfono real, así que no lo puede ejecutar un agente. Ver DA-17 en la bitácora de alcance.
- **Preparado por:** agente `ux`, revisión del cierre del Sprint 2 (incremento 6).
- **Resultado:** se registra en `docs/testing/rnf-13-prueba-usabilidad.md` (sección 10).

## 1. Participantes
- **Quiénes:** tres personas externas al equipo, mayores de edad, que nunca hayan visto AlTiro.
- **Perfil (NTI-11):** trabaja en un oficio o algo afín, usa un teléfono Android a diario (WhatsApp) y casi nunca llena formularios web. Lo ideal es que no tenga correo activo ni use computador.
- **Selección:** tres preguntas orales, anotadas como sí o no:
  - ¿Usa computador?
  - ¿Tiene un correo que revise?
  - ¿Ha hecho algún trámite por internet desde el celular?
- **Reclutamiento:** por contactos del equipo. Si se usa la red de maestros de la empresa, pasa por el representante del producto (CP-01).
- **Piloto:** una persona interna, sin contar para el resultado.

## 2. Consentimiento
Se lee en voz alta y en lenguaje simple. La persona firma o da su consentimiento verbal, y el moderador lo anota. Los papeles no entran al repositorio.

Lo que se lee:
- Se evalúa la aplicación, no a la persona.
- Puede detenerse cuando quiera.
- Usará solo datos ficticios de una tarjeta y documentos impresos rotulados **"MUESTRA — DOCUMENTO FICTICIO"**.
- No se fotografían sus documentos reales ni su cara.
- Si se graba, será solo la pantalla, sin audio.
- En los resultados aparece como P1, P2 o P3.
- El entorno de prueba se descarta al final.

Nunca escribe su propia contraseña: se le entrega una en la tarjeta.

## 3. Materiales (un juego por participante)
- **Tarjeta con datos ficticios:**
  - nombre;
  - RUT con dígito verificador válido y distinto para cada participante (CA-11.3);
  - teléfono de 9 dígitos;
  - la indicación "no tienes correo: deja ese dato en blanco";
  - una contraseña frase de 12 o más caracteres.
- **Documentos impresos rotulados MUESTRA en diagonal, sin escudos ni diseño oficial:**
  - cédula por ambos lados: emisión pasada, vencimiento futuro;
  - certificado de antecedentes: emisión pasada, sin vencimiento;
  - licencia SEC de Gas: emisión pasada, vencimiento futuro.

  Las fechas deben pasar las validaciones del servidor: la emisión no puede ser futura, el vencimiento debe ser posterior a la emisión y el documento no puede estar vencido.
- **Lugar:** una mesa con buena luz.

## 4. Preparación del entorno y del teléfono
1. **Proyecto separado:** `docker compose -p altiro-usabilidad …`, para descartar después sus volúmenes. Borrar volúmenes requiere autorización explícita (CLAUDE.md §14).
2. **Red:** una wifi que controle el equipo (router o punto de acceso propio), con IP fija para el PC. En Windows hay que permitir la entrada al 443 en el perfil privado.
3. **`.env`:**
   - `ALTIRO_BIND_ADDR=<IP del PC>` (nunca `0.0.0.0`, ADR-008);
   - `ALTIRO_TLS_SAN=DNS:localhost,IP:127.0.0.1,IP:<IP>`;
   - la IP en `DJANGO_ALLOWED_HOSTS` y `https://<IP>` en `DJANGO_CSRF_TRUSTED_ORIGINS`.

   Si falta el origen de CSRF, cada envío responde "Tu formulario venció".
4. **Certificado:** el autofirmado de la demostración (`CA:FALSE`) no se puede instalar como autoridad en Android ni en iOS, y la advertencia del navegador alteraría el resultado.
   - **Opción A, recomendada:** mkcert, que ADR-008 ya menciona como alternativa.
     1. `mkcert -install`.
     2. `mkcert -cert-file cert.pem -key-file key.pem <IP> localhost 127.0.0.1`.
     3. Copiar `cert.pem` y `key.pem` al volumen `certificados` del proyecto de prueba, junto con un `san.txt` idéntico a `ALTIRO_TLS_SAN`, para que `init` no lo regenere.
     4. En el **teléfono del equipo**, instalar **solo** el `rootCA.pem` público:
        - Android: Ajustes › Seguridad › Cifrado y credenciales › Instalar un certificado › Certificado de CA. Usar Chrome.
        - iOS: instalarlo y luego activar la confianza total en Información › Ajustes de confianza de certificados.
     5. Nunca compartir `rootCA-key.pem` ni subirlo al repositorio.
     6. Quitar la autoridad del teléfono al terminar.
   - **Opción C, respaldo:** el moderador acepta la advertencia antes de cada sesión. Se registra como desviación.
5. **Teléfono:** uno del equipo, Android de gama media, en español, con Chrome actualizado, "No molestar" activo y el tamaño de letra por defecto. Entre participantes se borran los datos del sitio (sesión, almacenamiento y permiso de cámara).
6. **Limitador de intentos (ADR-007):** detrás de Docker Desktop todos los clientes pueden llegar con el mismo origen. No se baja la seguridad: si ocurre un bloqueo, se anota como incidente.
7. **Ensayo previo:** el moderador hace el flujo completo con un RUT de repuesto y mide el tiempo de un experto.

## 5. Guion
1. Bienvenida y consentimiento (no se cronometra).
2. Tarjeta de escenario, leída en voz alta: "Usted trabaja en gas y quiere entrar a AlTiro para recibir trabajos. Postule como maestro con sus documentos. Use los datos de esta tarjeta y estos documentos de muestra. Avíseme cuando crea que terminó."
3. Se entrega el teléfono en `https://<IP>/`, sin sesión.
4. La persona no piensa en voz alta durante la tarea. Las preguntas van al final.
5. Solo se permiten intervenciones neutras: "Haga lo que haría si estuviera solo" y "Puede seguir o avisar si quiere dejarlo". Cualquier pista cuenta como "con ayuda".
6. El límite de observación es de 15 minutos. Pasados los 10 minutos ya es fracaso, pero se sigue observando para aprender.
7. Preguntas finales:
   - ¿Qué fue lo más difícil?
   - ¿Hubo palabras que no entendió? (evidencia para RNF-17)
   - ¿Se sintió seguro de poner sus datos?

## 6. Qué se cronometra
- **T0:** cuando toca "Soy maestro: quiero postular" (inicio).
- **T1:** cuando aparece el resumen "Tu postulación está en revisión" con el estado "⏳ En revisión". "Tu postulación está incompleta" no cuenta.
- El ingreso intermedio (ADR-013 E-8) queda dentro del tiempo.
- Parciales: T0 → ingreso → "¿Qué oficios haces?" → cada documento → T1.

## 7. Criterio de éxito
- **Por participante:** llega a T1, sin ayuda, con T1 − T0 ≤ 600 s.
- **RNF-13:** PASS si 2 o 3 de 3 tienen éxito.
- **Término falso:** declarar que terminó antes de T1 cuenta como fracaso. Por ejemplo, al ver el aviso de cuenta creada.
- **Validez de la sesión:**
  - si falla por el entorno de prueba (router, PC), la sesión no vale y se reemplaza al participante;
  - si falla por el producto, la sesión cuenta.
- Se informan todas las sesiones.

## 8. Qué observar
- Si entiende que después de postular debe ingresar (riesgo de término falso).
- Cuánto le cuesta reescribir el RUT y la contraseña.
- Si encuentra su oficio.
- Si entiende "SEC" y "fecha de emisión".
- Cómo usa el selector de fecha.
- Cámara o galería, y cuántas fotos repite.
- Qué pasa con el permiso de cámara.
- Si la pestaña se recarga al volver de la cámara (RNF-20).
- Tiempos de subida.
- Toques fallidos, teclado que tapa botones, desplazamientos para encontrar "Continuar".
- Cómo lee "Paso X de N".
- Cada mensaje de error: texto exacto, si entendió la acción y cuánto tardó.
- Desconfianza por advertencias del navegador.

## 9. Hojas de registro

**Encabezado por sesión**

| Campo | Valor |
|---|---|
| Participante | P1 / P2 / P3 |
| Fecha y hora | |
| Moderador / observador | |
| Teléfono, Android, Chrome | |
| Red / opción de certificado (A/C) | |
| Selección: usa computador / tiene correo / hizo trámites web | Sí o no ×3 |
| Consentimiento | Sí |

**Tiempos**

| Tramo | Inicio (mm:ss) | Fin (mm:ss) | Duración | Notas |
|---|---|---|---|---|
| Registro (T0 → ingreso) | | | | |
| Ingreso | | | | |
| Oficios | | | | |
| Cédula | | | | |
| Antecedentes | | | | |
| Licencia de Gas | | | | |
| **Total T0 → T1** | | | | |

**Incidentes**

| Hora | Pantalla | Qué pasó | Mensaje exacto | ¿Intervención? | Causa (producto / entorno / persona) | Hallazgo |
|---|---|---|---|---|---|---|

**Resultado:** ¿llegó a T1? / ¿sin ayuda? / tiempo total / ¿éxito (≤ 600 s)? / ¿término falso?

## 10. Registro del resultado
- Crear `docs/testing/rnf-13-prueba-usabilidad.md` con:
  - commit y versión del protocolo;
  - entorno y opción de certificado;
  - participantes anonimizados;
  - las tablas;
  - resultado contra el umbral literal;
  - hallazgos y desviaciones.
- No incluir fotos, grabaciones ni consentimientos. Basta con anotar que el equipo los archivó fuera del repositorio.
- Si el resultado es FAIL: corregir y repetir con **3 personas nuevas**.
- No declarar RNF-13 cumplido sin la prueba.
