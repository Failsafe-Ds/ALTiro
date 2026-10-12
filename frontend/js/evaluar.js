// Evaluar una orden finalizada y ver o denunciar la evaluación recibida
// (HU-09, HU-18, HU-21; RF-29, RF-31; CA-09.1, CA-09.2, CA-18.1; ADR-026, E-3 y E-4).
// - GET /api/tickets/<ref>: datos del pedido (título).
// - GET /api/tickets/<ref>/evaluaciones: {mia, recibida, puede_evaluar, aviso, evalua_a}.
// - POST /api/tickets/<ref>/evaluacion {puntualidad, trabajo, cordialidad, comentario}.
// - POST /api/tickets/<ref>/evaluacion-recibida/denuncia {motivo}.
// El servidor decide todo (estado, una sola vez, parte); la página solo lo muestra.
"use strict";

(() => {
  const PALABRAS = ["Muy mal", "Mal", "Regular", "Bien", "Muy bien"];
  const PREGUNTAS = {
    maestro: {
      puntualidad: "¿Llegó a la hora acordada?",
      trabajo: "¿Cómo quedó el trabajo?",
      cordialidad: "¿Cómo fue el trato?",
    },
    cliente: {
      puntualidad: "¿Te recibió a la hora acordada?",
      trabajo: "¿Fue claro con lo que necesitaba?",
      cordialidad: "¿Cómo fue el trato?",
    },
  };
  const NOMBRES = { puntualidad: "Puntualidad", trabajo: "Trabajo", cordialidad: "Trato" };

  const parametros = new URLSearchParams(window.location.search);
  const refTicket = parametros.get("ticket") || "";
  const rutaTicket = `/api/tickets/${encodeURIComponent(refTicket)}`;

  // Borradores en este teléfono (patrón altiro.<pantalla>.<ref>, como conversacion.js):
  // se borran al enviar con éxito y al cerrar sesión (formulario.olvidarTodo).
  const claveNotas = `altiro.evaluar.${refTicket}`;
  const claveMotivo = `altiro.evaluar.${refTicket}.denuncia`;

  // Cada borrador vive en localStorage y vence a las 2 h del último cambio
  // (ADR-002 E-1); formulario.js lo guarda, lo vence y lo borra al salir.
  const leerBorrador = (clave) => formulario.recuperarTexto(clave);
  const escribirBorrador = (clave, valor) => formulario.guardarTexto(clave, valor);

  const cargando = document.getElementById("cargando");
  const avisoPagina = document.getElementById("aviso-pagina");
  const contenido = document.getElementById("contenido");
  const avisoEvaluar = document.getElementById("aviso-evaluar");
  const resultadoEnvio = document.getElementById("resultado-envio");
  const mia = document.getElementById("mia");
  const formEvaluacion = document.getElementById("formulario-evaluacion");
  const sinRecibida = document.getElementById("sin-recibida");
  const recibidaDatos = document.getElementById("recibida-datos");
  const formDenuncia = document.getElementById("formulario-denuncia");

  const elemento = dom.elemento;

  function errorPagina(texto, accion) {
    cargando.hidden = true;
    contenido.hidden = true;
    avisoPagina.className = "aviso aviso-error";
    avisoPagina.hidden = false;
    avisoPagina.replaceChildren(texto, " ", accion);
    avisoPagina.focus();
  }

  function sesionTerminada() {
    const enlace = dom.enlaceIngresar("evaluar", refTicket);
    errorPagina("Tu sesión terminó. Vuelve a ingresar para seguir.", enlace);
  }

  function noEncontrado() {
    const enlace = elemento("a", "boton", "Ir a mi cuenta");
    enlace.href = "cuenta.html";
    errorPagina("No encontramos este pedido. Ábrelo desde tus pedidos o tus trabajos.", enlace);
  }

  function errorCarga() {
    const boton = elemento("button", "", "Reintentar");
    boton.type = "button";
    boton.addEventListener("click", cargar);
    errorPagina("No pudimos cargar la evaluación. Revisa tu señal o tu wifi.", boton);
  }

  // --- Formulario de notas: cinco opciones grandes con número y palabra ---

  function armarNotas(evaluaA) {
    for (const grupo of formEvaluacion.querySelectorAll("fieldset[data-dimension]")) {
      const dimension = grupo.dataset.dimension;
      grupo.querySelector("legend").textContent = PREGUNTAS[evaluaA][dimension];
      const opciones = PALABRAS.map((palabra, indice) => {
        const entrada = document.createElement("input");
        entrada.type = "radio";
        entrada.name = dimension;
        entrada.value = String(indice + 1);
        return elemento(
          "label",
          "nota",
          entrada,
          elemento("span", "nota-numero", String(indice + 1)),
          elemento("span", "nota-palabra", palabra)
        );
      });
      grupo.querySelector(".notas").replaceChildren(...opciones);
    }
  }

  function guardarNotas() {
    const valores = { comentario: document.getElementById("comentario").value };
    for (const dimension of Object.keys(NOMBRES)) {
      valores[dimension] = notaElegida(dimension);
    }
    const vacio = !valores.comentario && Object.keys(NOMBRES).every((d) => valores[d] === null);
    escribirBorrador(claveNotas, vacio ? "" : JSON.stringify(valores));
  }

  function restaurarNotas() {
    let valores = null;
    try {
      valores = JSON.parse(leerBorrador(claveNotas));
    } catch (error) {
      valores = null;
    }
    if (!valores || typeof valores !== "object") {
      return;
    }
    for (const dimension of Object.keys(NOMBRES)) {
      const entrada = formEvaluacion.querySelector(`input[name="${dimension}"][value="${Number(valores[dimension])}"]`);
      if (entrada) {
        entrada.checked = true;
      }
    }
    if (typeof valores.comentario === "string") {
      document.getElementById("comentario").value = valores.comentario;
    }
  }

  function notaElegida(dimension) {
    const marcada = formEvaluacion.querySelector(`input[name="${dimension}"]:checked`);
    return marcada ? Number(marcada.value) : null;
  }

  function resumen(evaluacion) {
    const lista = elemento("dl", "datos");
    for (const clave of ["puntualidad", "trabajo", "cordialidad"]) {
      const valor = evaluacion[clave];
      lista.append(elemento("dt", "", NOMBRES[clave]), elemento("dd", "", `${valor} de 5 (${PALABRAS[valor - 1]})`));
    }
    const partes = [lista];
    if (evaluacion.comentario) {
      partes.push(elemento("p", "", `Comentario: «${evaluacion.comentario}»`));
    }
    if (evaluacion.estado === "retirada") {
      partes.push(elemento("p", "estado", `Estado: ${evaluacion.estado_texto}. No cuenta en la calificación.`));
    }
    return partes;
  }

  function pintar(datos) {
    armarNotas(datos.evalua_a);
    // Dos flujos (ADR-002 E-3.2): quien evalúa al maestro es el cliente del pedido.
    if (typeof window.altiroFlujo === "function") window.altiroFlujo(datos.evalua_a === "maestro" ? "cliente" : "maestro");
    document.getElementById("titulo-mia").textContent =
      datos.evalua_a === "maestro" ? "Tu evaluación del maestro" : "Tu evaluación del cliente";
    // Tu evaluación: ya hecha (solo lectura), por hacer, o todavía no disponible.
    mia.hidden = !datos.mia;
    if (datos.mia) {
      mia.replaceChildren(elemento("p", "", "Ya evaluaste este trabajo. Esta es tu evaluación:"), ...resumen(datos.mia));
    }
    formEvaluacion.hidden = !datos.puede_evaluar;
    if (datos.puede_evaluar) {
      restaurarNotas();
    }
    if (datos.recibida && datos.recibida.puede_denunciar && !document.getElementById("motivo").value) {
      document.getElementById("motivo").value = leerBorrador(claveMotivo) || "";
    }
    avisoEvaluar.hidden = !datos.aviso;
    avisoEvaluar.textContent = datos.aviso || "";

    // Evaluación recibida y denuncia (HU-21).
    const recibida = datos.recibida;
    sinRecibida.hidden = Boolean(recibida);
    recibidaDatos.hidden = !recibida;
    formDenuncia.hidden = !(recibida && recibida.puede_denunciar);
    if (recibida) {
      const partes = resumen(recibida);
      if (recibida.denuncia) {
        const d = recibida.denuncia;
        const texto = d.decision_texto
          ? `Tu denuncia: ${d.estado_texto}. ${d.decision_texto}.`
          : `Tu denuncia: ${d.estado_texto}. Moderación la está revisando.`;
        partes.push(elemento("p", "estado", texto));
      }
      recibidaDatos.replaceChildren(...partes);
    }
  }

  async function cargarEvaluaciones() {
    const { estado, datos } = await api.obtener(`${rutaTicket}/evaluaciones`);
    if (estado === 401) {
      sesionTerminada();
      return false;
    }
    if (estado === 404 || estado === 400) {
      noEncontrado();
      return false;
    }
    if (estado !== 200) {
      errorCarga();
      return false;
    }
    pintar(datos);
    return true;
  }

  async function cargar() {
    avisoPagina.className = "aviso";
    avisoPagina.hidden = true;
    avisoPagina.replaceChildren();
    cargando.hidden = false;
    if (!refTicket) {
      noEncontrado();
      return;
    }
    const pedido = await api.obtener(rutaTicket);
    if (pedido.estado === 401) {
      sesionTerminada();
      return;
    }
    if (pedido.estado === 404 || pedido.estado === 400) {
      noEncontrado();
      return;
    }
    if (pedido.estado !== 200) {
      errorCarga();
      return;
    }
    const ticket = pedido.datos.ticket;
    document.getElementById("subtitulo").textContent =
      `${ticket.servicio.nombre}, ${formato.fechaConReferencia(ticket.bloque.fecha)}, de ${ticket.bloque.inicio} a ${ticket.bloque.fin}`;
    if (!(await cargarEvaluaciones())) {
      return;
    }
    cargando.hidden = true;
    contenido.hidden = false;
    if (window.location.hash === "#recibida") {
      document.getElementById("recibida").focus();
    } else {
      document.getElementById("titulo-pagina").focus();
    }
  }

  // --- Envíos ---

  formulario.prepararBoton(formEvaluacion);
  formulario.prepararBoton(formDenuncia);

  formEvaluacion.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(formEvaluacion);
    // Ayuda de experiencia: avisa qué nota falta sin enviar; el servidor vuelve a validar todo.
    const faltan = Object.keys(NOMBRES).filter((d) => notaElegida(d) === null);
    if (faltan.length > 0) {
      for (const dimension of faltan) {
        document.getElementById(`error-${dimension}`).textContent = `Elige una nota de 1 a 5 para ${NOMBRES[dimension]}.`;
      }
      formEvaluacion.querySelector(`input[name="${faltan[0]}"]`).focus();
      return;
    }
    const cuerpo = {
      puntualidad: notaElegida("puntualidad"),
      trabajo: notaElegida("trabajo"),
      cordialidad: notaElegida("cordialidad"),
      comentario: document.getElementById("comentario").value,
    };
    formulario.ocupado(formEvaluacion, true);
    const { estado, datos } = await api.enviar(`${rutaTicket}/evaluacion`, cuerpo);
    formulario.ocupado(formEvaluacion, false);
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 201 || estado === 409) {
      escribirBorrador(claveNotas, "");
      // 409: ya evaluaste o el trabajo no está terminado; se muestra lo que dice el servidor.
      await cargarEvaluaciones();
      if (estado === 409) {
        avisoEvaluar.hidden = false;
        avisoEvaluar.textContent = datos.mensaje || "No pudimos guardar tu evaluación. Vuelve a abrir el pedido.";
      }
      if (estado === 201) {
        formulario.resultado(resultadoEnvio, "Tu evaluación quedó registrada.", "exito");
      }
      document.getElementById("titulo-mia").focus();
      return;
    }
    const campo = formulario.mostrarErrores(formEvaluacion, datos);
    if (campo) {
      (campo.tagName === "FIELDSET" ? campo.querySelector("input") : campo).focus();
    }
  });

  formDenuncia.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(formDenuncia);
    formulario.ocupado(formDenuncia, true);
    const { estado, datos } = await api.enviar(`${rutaTicket}/evaluacion-recibida/denuncia`, {
      motivo: document.getElementById("motivo").value,
    });
    formulario.ocupado(formDenuncia, false);
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 201) {
      escribirBorrador(claveMotivo, "");
      await cargarEvaluaciones();
      formulario.resultado(resultadoEnvio, "Tu denuncia quedó registrada.", "exito");
      document.getElementById("recibida").focus();
      return;
    }
    if (estado === 409) {
      formulario.avisar(formDenuncia, datos.mensaje || "No pudimos registrar tu denuncia. Vuelve a abrir el pedido.", "error");
      return;
    }
    const campo = formulario.mostrarErrores(formDenuncia, datos);
    if (campo) {
      campo.focus();
    }
  });

  formEvaluacion.addEventListener("change", guardarNotas);
  formEvaluacion.addEventListener("input", guardarNotas);
  document.getElementById("motivo").addEventListener("input", (evento) => escribirBorrador(claveMotivo, evento.target.value));
  document.getElementById("titulo-mia").tabIndex = -1;
  cargar();
})();
