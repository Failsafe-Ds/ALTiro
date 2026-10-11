// Formularios por pasos, errores por campo y progreso guardado.
// - RNF-14: pasos de máximo 5 campos.
// - RNF-15: cada error se muestra junto a su campo, con texto (no solo color).
// - RNF-20: los pasos completados se conservan si se pierde la conexión o se
//   recarga la página. Se usa sessionStorage (se borra al cerrar la pestaña,
//   pensando en teléfonos compartidos) y nunca se guarda la contraseña (ADR-002).
"use strict";

const formulario = (() => {
  function campos(form) {
    return Array.from(form.querySelectorAll("input[name], select[name], textarea[name]"));
  }

  // CLAUDE.md §9, punto 2: los espacios al inicio y al final se quitan antes de
  // validar y enviar. La contraseña nunca se recorta (ADR-013, punto 3).
  function recortable(campo) {
    return (
      (campo.tagName === "TEXTAREA" || campo.tagName === "INPUT") &&
      !/^(password|file|checkbox|radio|hidden)$/.test(campo.type)
    );
  }

  function valor(campo) {
    return recortable(campo) ? campo.value.trim() : campo.value;
  }

  // Al salir del campo se ve el valor ya recortado (el mismo que se envía).
  document.addEventListener("change", (evento) => {
    const campo = evento.target;
    if (campo && recortable(campo) && campo.value !== campo.value.trim()) {
      campo.value = campo.value.trim();
    }
  });

  // Lee todos los campos, incluidos los de pasos ya completados (ocultos).
  // Se omiten los marcados con data-no-enviar (por ejemplo, la región, que
  // solo filtra la lista de comunas) y los de secciones .oculto.
  function leer(form) {
    const datos = {};
    for (const campo of campos(form)) {
      if (campo.dataset.noEnviar !== undefined || campo.closest(".oculto")) {
        continue;
      }
      const escrito = valor(campo);
      if (escrito !== "") {
        datos[campo.name] = escrito;
      }
    }
    return datos;
  }

  function limpiarErrores(form) {
    for (const campo of campos(form)) {
      campo.removeAttribute("aria-invalid");
    }
    for (const error of form.querySelectorAll(".error-campo")) {
      error.textContent = "";
    }
    const aviso = form.querySelector(".aviso");
    if (aviso) {
      aviso.textContent = "";
      aviso.className = "aviso";
    }
  }

  function avisar(form, texto, tipo) {
    const aviso = form.querySelector(".aviso");
    aviso.className = "aviso aviso-" + tipo;
    aviso.textContent = texto;
    if (tipo === "error") {
      aviso.focus();
    } else if (!aviso.hasAttribute("role")) {
      aviso.setAttribute("role", "status");
    }
  }

  // Botón que vuelve a cargar la página (hallazgo UX T-11): en vez de pedir
  // "recarga la página", se ofrece la acción. Lo escrito en los pasos se
  // conserva (RNF-20); la contraseña no.
  function botonVolverACargar(texto = "Volver a cargar") {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "boton-secundario";
    boton.textContent = texto;
    boton.addEventListener("click", () => location.reload());
    return boton;
  }

  // aria-invalid solo vale en campos que se escriben o eligen; en un botón
  // (fotos) o un fieldset el error se enlaza con aria-describedby.
  function admiteInvalido(campo) {
    return /^(INPUT|SELECT|TEXTAREA)$/.test(campo.tagName);
  }

  // Muestra { mensaje, errores } del servidor. Devuelve el primer campo con error.
  // Si datos.recargar es true, el aviso ofrece el botón "Volver a cargar".
  function mostrarErrores(form, datos) {
    limpiarErrores(form);
    let primero = null;
    const sinCampo = [];
    for (const [nombre, texto] of Object.entries(datos.errores || {})) {
      const destino = form.querySelector(`#error-${nombre}`);
      const campo =
        form.querySelector(`[aria-describedby~="error-${nombre}"]`) || form.querySelector(`[name="${nombre}"]`);
      if (campo && destino) {
        if (admiteInvalido(campo)) {
          campo.setAttribute("aria-invalid", "true");
        }
        destino.textContent = texto;
        primero = primero || campo;
      } else {
        sinCampo.push(texto);
      }
    }
    // Hallazgo UX E-1: si ningún campo quedó marcado, el mensaje general
    // ("revisa los campos marcados") no sirve; se muestran solo los errores.
    const marcados = Object.keys(datos.errores || {}).length - sinCampo.length;
    // Resumen arriba (CLAUDE.md §9, punto 4): con varios campos marcados se dice cuántos.
    const resumen = marcados > 1 ? `Hay ${marcados} datos por corregir; cada uno tiene su mensaje junto al campo.` : "";
    const partes = primero || sinCampo.length === 0 ? [datos.mensaje, resumen, ...sinCampo] : sinCampo;
    avisar(form, partes.filter(Boolean).join(" "), "error");
    if (datos.recargar) {
      form.querySelector(".aviso").append(" ", botonVolverACargar());
    }
    // El foco va al primer campo con error si está a la vista; si no (por
    // ejemplo, en otro paso), queda en el resumen y la página lo lleva al campo.
    if (primero && primero.getClientRects().length && typeof primero.focus === "function") {
      primero.focus();
    }
    return primero;
  }

  // CLAUDE.md §9, puntos 6 y 7: tras el éxito, mensaje de resultado anunciado,
  // campos limpios y borrador borrado (si se indica su clave).
  function terminado(form, texto, clave) {
    form.reset();
    for (const campo of campos(form)) {
      campo.removeAttribute("aria-invalid");
    }
    if (clave) {
      olvidar(clave);
    }
    avisar(form, texto, "exito");
  }

  // Mensaje de resultado de una operación que no es un formulario (aceptar,
  // rechazar, cancelar, exportar…): caja .aviso con role="status" o "alert".
  function resultado(caja, texto, tipo) {
    caja.hidden = false;
    caja.className = "aviso aviso-" + tipo;
    caja.setAttribute("role", tipo === "error" ? "alert" : "status");
    caja.textContent = texto;
  }

  // --- Sesión iniciada en páginas de cuenta nueva (DEF-QA-001; ADR-013, punto 2 y E-2) ---

  // Texto de comun.api.MENSAJE_CAMPO_NO_PERMITIDO. La API no entrega un código
  // de error, así que se reconoce por su texto. Es solo un respaldo: las páginas
  // primero consultan GET /api/cuenta para conocer la causa real.
  const NO_PERMITIDO = "Este dato no corresponde aquí: quítalo e inténtalo de nuevo.";

  // Reemplaza el mensaje genérico de campo no permitido por uno que la persona
  // pueda seguir en este contexto (textos = { mensaje, campo }), con el botón
  // "Volver a cargar" (hallazgo UX T-4). No descarta ningún error: cada campo
  // afectado conserva su aviso.
  function traducirNoPermitido(datos, textos) {
    let hubo = false;
    const errores = {};
    for (const [campo, texto] of Object.entries(datos.errores || {})) {
      hubo = hubo || texto === NO_PERMITIDO;
      errores[campo] = texto === NO_PERMITIDO ? textos.campo : texto;
    }
    return hubo ? { mensaje: textos.mensaje, errores, recargar: true } : datos;
  }

  // Con sesión iniciada no se ofrece el formulario de visitante: se explica cómo
  // seguir desde "Mi cuenta" (textos = { perfil, conPerfil, sinPerfil }).
  // La contraseña escrita se borra del DOM.
  function derivarACuenta(cuenta, textos, enfocar) {
    for (const campo of document.querySelectorAll('input[type="password"]')) {
      campo.value = "";
    }
    for (const elemento of document.querySelectorAll(".solo-visitante")) {
      elemento.classList.add("oculto");
    }
    document.getElementById("con-sesion-texto").textContent = cuenta[textos.perfil]
      ? textos.conPerfil
      : textos.sinPerfil;
    document.getElementById("cargando").classList.add("oculto");
    document.getElementById("con-sesion").classList.remove("oculto");
    if (enfocar) {
      document.getElementById("titulo-con-sesion").focus();
    }
  }

  // Sin sesión (o sin poder saberlo, por ejemplo sin conexión): se muestra el
  // formulario de visitante, que la página deja oculto mientras consulta.
  function mostrarVisitante() {
    document.getElementById("cargando").classList.add("oculto");
    for (const elemento of document.querySelectorAll(".solo-visitante")) {
      elemento.classList.remove("oculto");
    }
  }

  // --- Progreso guardado (RNF-20) ---
  // Hallazgo UX M-4: todo lo guardado lleva la hora ("guardado") y vence
  // VIGENCIA_MS después del último cambio. Así, en un teléfono compartido no
  // queda indefinidamente un RUT, correo o teléfono escrito por otra persona
  // (ADR-002), y quien perdió la señal o la sesión (30 min, RNF-09) tiene
  // tiempo de sobra para volver y seguir (RNF-20). Lo vencido o sin hora se
  // descarta. Al cerrar sesión con éxito se borran todas las claves altiro.*.

  const PREFIJO = "altiro.";
  const VIGENCIA_MS = 2 * 60 * 60 * 1000;

  // Guarda un objeto con la hora actual. Nunca debe incluir contraseñas.
  function guardarDatos(clave, datos) {
    try {
      sessionStorage.setItem(clave, JSON.stringify(Object.assign({}, datos, { guardado: Date.now() })));
      return true;
    } catch (error) {
      // Almacenamiento no disponible: el formulario sigue funcionando.
      return false;
    }
  }

  function guardar(form, clave, paso) {
    const valores = {};
    for (const campo of campos(form)) {
      if (campo.type !== "password" && campo.value !== "") {
        valores[campo.name] = campo.value;
      }
    }
    guardarDatos(clave, { paso, valores });
  }

  function vigente(guardado) {
    const edad = Date.now() - guardado;
    return typeof guardado === "number" && edad >= 0 && edad <= VIGENCIA_MS;
  }

  function olvidar(clave) {
    try {
      sessionStorage.removeItem(clave);
    } catch (error) {
      // Nada que hacer.
    }
  }

  // Devuelve lo guardado solo si no venció; si venció, lo borra.
  function recuperar(clave) {
    let previo = null;
    try {
      previo = JSON.parse(sessionStorage.getItem(clave));
    } catch (error) {
      previo = null;
    }
    if (!previo || typeof previo !== "object") {
      return null;
    }
    if (!vigente(previo.guardado)) {
      olvidar(clave);
      return null;
    }
    return previo;
  }

  function clavesPropias() {
    try {
      return Object.keys(sessionStorage).filter((clave) => clave.startsWith(PREFIJO));
    } catch (error) {
      return [];
    }
  }

  // Tras cerrar sesión con éxito: no queda nada escrito en este teléfono.
  function olvidarTodo() {
    for (const clave of clavesPropias()) {
      olvidar(clave);
    }
    // Borradores de conversación y evaluación (UX-S5-09): viven en localStorage.
    try {
      for (const clave of Object.keys(localStorage)) {
        if (clave.startsWith("altiro.conversacion.") || clave.startsWith("altiro.evaluar.")) {
          localStorage.removeItem(clave);
        }
      }
    } catch (error) {
      // Sin almacenamiento: nada que borrar.
    }
  }

  // Al cargar cualquier página con formularios se descarta lo vencido, aunque
  // la persona no vuelva al formulario que lo guardó.
  for (const clave of clavesPropias()) {
    recuperar(clave);
  }

  // --- Pasos ---
  // Cada paso es un <fieldset class="paso">. "Continuar" solo exige los campos
  // marcados como required de ese paso; la validación real la hace el servidor.
  function porPasos(form, { clave, alRestaurar }) {
    const pasos = Array.from(form.querySelectorAll(".paso"));
    const progreso = form.querySelector(".progreso");
    let actual = 0;

    function mostrar(indice, enfocar = true) {
      actual = indice;
      pasos.forEach((paso, i) => {
        paso.hidden = i !== indice;
      });
      if (progreso) {
        progreso.textContent = `Paso ${indice + 1} de ${pasos.length}`;
      }
      guardar(form, clave, actual);
      if (enfocar) {
        const titulo = pasos[indice].querySelector("legend");
        if (titulo) {
          titulo.setAttribute("tabindex", "-1");
          titulo.focus();
        }
      }
    }

    function pasoDe(campo) {
      return pasos.findIndex((paso) => paso.contains(campo));
    }

    form.addEventListener("click", (evento) => {
      const boton = evento.target.closest("[data-paso]");
      if (!boton) {
        return;
      }
      evento.preventDefault();
      if (boton.dataset.paso === "siguiente") {
        const faltantes = Array.from(pasos[actual].querySelectorAll("[required]")).filter((c) => !valor(c));
        if (faltantes.length) {
          mostrarErrores(form, {
            mensaje: "Completa los datos marcados para continuar.",
            errores: Object.fromEntries(faltantes.map((c) => [c.name, "Completa este dato."])),
          });
          faltantes[0].focus();
          return;
        }
        const revision = revisar(form, pasos[actual]);
        if (revision) {
          const campo = mostrarErrores(form, revision);
          if (campo) {
            campo.focus();
          }
          return;
        }
        limpiarErrores(form);
        // Cada paso deja una entrada en el historial: Atrás retrocede un paso.
        history.pushState({ altiroPaso: "paso", numero: actual + 1 }, "", location.href);
        mostrar(actual + 1);
      } else {
        limpiarErrores(form);
        if (history.state && history.state.altiroPaso === "paso") {
          history.back();
        } else {
          mostrar(actual - 1);
        }
      }
    });

    window.addEventListener("popstate", (evento) => {
      const estado = evento.state;
      const indice = estado && estado.altiroPaso === "paso" ? estado.numero : 0;
      if (indice !== actual && indice >= 0 && indice < pasos.length && !form.hidden) {
        limpiarErrores(form);
        mostrar(indice);
      }
    });

    form.addEventListener("input", () => guardar(form, clave, actual));
    form.addEventListener("change", () => guardar(form, clave, actual));

    const previo = recuperar(clave);
    if (previo) {
      for (const [nombre, valor] of Object.entries(previo.valores || {})) {
        const campo = form.querySelector(`[name="${nombre}"]`);
        if (campo && campo.type !== "password") {
          campo.value = valor;
        }
      }
      Promise.resolve(alRestaurar ? alRestaurar(previo.valores || {}) : null).then(() => {
        mostrar(Math.min(previo.paso || 0, pasos.length - 1), false);
      });
    } else {
      mostrar(0, false);
    }

    return {
      irAlCampo(campo) {
        const indice = pasoDe(campo);
        if (indice >= 0 && indice !== actual) {
          mostrar(indice, false);
        }
        campo.focus();
      },
      terminar() {
        olvidar(clave);
      },
    };
  }

  // --- Validación en pantalla de RUT y correo (ADR-031) ---
  // Solo adelanta el aviso para no esperar al servidor, que sigue siendo quien
  // valida (identidad/validadores.py y autenticacion.py). Mismas reglas y mismos
  // textos. El correo se revisa de forma básica: solo rechaza lo que el servidor
  // también rechaza, salvo formas raras que el ADR-031 enumera. Campo con data-validar="rut",
  // "correo" o "identificador" (correo o RUT, como al ingresar).
  const RUT_FORMATO =
    "Ingresa tu RUT con su dígito verificador (el número o la K después del guion), por ejemplo 12.345.678-5.";
  const RUT_INVALIDO =
    "El RUT no es válido: revisa los números y el dígito verificador (el número o la K después del guion).";
  const CORREO_INVALIDO = "El correo no es válido. Revísalo, por ejemplo nombre@dominio.cl.";
  const CORREO_LARGO = "El correo es demasiado largo. Revisa que esté bien escrito.";
  const IDENTIFICADOR_RUT =
    "Revisa tu RUT y su dígito verificador (el número o la K después del guion), por ejemplo 12.345.678-5. " +
    "Si usas correo, escríbelo completo.";

  // Dígito verificador módulo 11: factores 2 a 7 desde la derecha; 11 -> "0", 10 -> "K".
  function digitoVerificador(cuerpo) {
    let suma = 0;
    let factor = 2;
    for (let i = cuerpo.length - 1; i >= 0; i--) {
      suma += Number(cuerpo[i]) * factor;
      factor = factor === 7 ? 2 : factor + 1;
    }
    const resto = 11 - (suma % 11);
    return resto === 11 ? "0" : resto === 10 ? "K" : String(resto);
  }

  // Igual que normalizar_rut: sin puntos ni guion, 1 a 8 dígitos más el DV,
  // sin cero inicial (HQ-12). Devuelve el texto del error o null.
  // Los espacios al inicio y al final no cuentan (como en el servidor desde la
  // auditoría del backend, hallazgo 3).
  function errorRut(valor) {
    const rut = valor.trim().replace(/[.-]/g, "").toUpperCase();
    if (!/^[0-9]{1,8}[0-9K]$/.test(rut) || rut[0] === "0") {
      return RUT_FORMATO;
    }
    return digitoVerificador(rut.slice(0, -1)) === rut.slice(-1) ? null : RUT_INVALIDO;
  }

  // Revisión básica: el servidor aplica la regla completa (EmailValidator).
  function errorCorreo(valor) {
    const correo = valor.trim();
    if (correo.length > 254) {
      return CORREO_LARGO;
    }
    const arroba = correo.lastIndexOf("@");
    const local = correo.slice(0, arroba);
    const etiquetas = correo.slice(arroba + 1).split(".");
    const valido =
      arroba > 0 &&
      !local.includes("@") &&
      !/\s/.test(correo) &&
      etiquetas.length >= 2 &&
      etiquetas.every((etiqueta) => etiqueta !== "") &&
      etiquetas[etiquetas.length - 1].length >= 2 &&
      !local.startsWith(".") &&
      !local.endsWith(".") &&
      !local.includes("..");
    return valido ? null : CORREO_INVALIDO;
  }

  // Igual que interpretar_identificador: con "@" es correo; sin "@" es RUT.
  function errorIdentificador(texto) {
    const valor = texto.trim();
    if (valor.includes("@")) {
      return errorCorreo(valor) && CORREO_INVALIDO;
    }
    return errorRut(valor) && IDENTIFICADOR_RUT;
  }

  const VALIDADORES = { rut: errorRut, correo: errorCorreo, identificador: errorIdentificador };

  // Nombre del error de un campo: el id "error-…" de su aria-describedby (en
  // "Mi cuenta" no coincide con el name) o, si no tiene, su name.
  function nombreDeError(campo) {
    const id = (campo.getAttribute("aria-describedby") || "").split(/\s+/).find((t) => t.startsWith("error-"));
    return id ? id.slice("error-".length) : campo.name;
  }

  // Revisa los campos con data-validar dentro de "zona" (el formulario o un paso).
  // Los vacíos los resuelve "required" o el servidor. Devuelve { mensaje, errores }
  // para mostrarErrores, o null si no hay errores.
  function revisar(form, zona = form) {
    const errores = {};
    for (const campo of zona.querySelectorAll("[data-validar]")) {
      if (campo.closest(".oculto") || !valor(campo)) {
        continue;
      }
      const validador = VALIDADORES[campo.dataset.validar];
      const error = validador ? validador(valor(campo)) : null;
      if (error) {
        errores[nombreDeError(campo)] = error;
      }
    }
    return Object.keys(errores).length ? { mensaje: "Revisa los campos marcados.", errores } : null;
  }

  // CLAUDE.md §9, punto 3: botón desactivado y con el texto de la espera.
  function ocupado(form, sí, texto = "Enviando…") {
    const boton = form.querySelector('button[type="submit"]');
    form.setAttribute("aria-busy", String(sí));
    if (boton) {
      if (sí && !boton.dataset.texto) {
        boton.dataset.texto = boton.textContent;
      }
      boton.disabled = sí;
      boton.textContent = sí ? texto : boton.dataset.texto || boton.textContent;
    }
  }

  function prepararBoton(form) {
    const boton = form.querySelector('button[type="submit"]');
    if (boton) {
      boton.dataset.texto = boton.textContent;
    }
  }

  // Casillas "Mostrar contraseña": <input type="checkbox" data-mostrar="id-del-campo">.
  document.addEventListener("change", (evento) => {
    const casilla = evento.target.closest("[data-mostrar]");
    if (casilla) {
      document.getElementById(casilla.dataset.mostrar).type = casilla.checked ? "text" : "password";
    }
  });

  return {
    leer,
    valor,
    revisar,
    terminado,
    resultado,
    errorRut,
    errorCorreo,
    errorIdentificador,
    limpiarErrores,
    mostrarErrores,
    avisar,
    porPasos,
    ocupado,
    prepararBoton,
    guardarDatos,
    recuperar,
    olvidar,
    olvidarTodo,
    traducirNoPermitido,
    botonVolverACargar,
    derivarACuenta,
    mostrarVisitante,
  };
})();
