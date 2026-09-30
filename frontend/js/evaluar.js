// Evaluar una orden finalizada y ver o denunciar la evaluación recibida
// (HU-09, HU-18, HU-21; RF-29, RF-31; CA-09.1, CA-09.2, CA-18.1; ADR-026, E-3 y E-4).
// - GET /api/tickets/<ref>: datos del pedido (título y botón Volver).
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

  const cargando = document.getElementById("cargando");
  const avisoPagina = document.getElementById("aviso-pagina");
  const contenido = document.getElementById("contenido");
  const avisoEvaluar = document.getElementById("aviso-evaluar");
  const mia = document.getElementById("mia");
  const formEvaluacion = document.getElementById("formulario-evaluacion");
  const sinRecibida = document.getElementById("sin-recibida");
  const recibidaDatos = document.getElementById("recibida-datos");
  const formDenuncia = document.getElementById("formulario-denuncia");

  function elemento(etiqueta, clase, ...hijos) {
    const nodo = document.createElement(etiqueta);
    if (clase) {
      nodo.className = clase;
    }
    nodo.append(...hijos);
    return nodo;
  }

  function errorPagina(texto, accion) {
    cargando.hidden = true;
    contenido.hidden = true;
    avisoPagina.className = "aviso aviso-error";
    avisoPagina.replaceChildren(texto, " ", accion);
    avisoPagina.focus();
  }

  function sesionTerminada() {
    const enlace = elemento("a", "boton", "Ingresar de nuevo");
    enlace.href = `ingresar.html?aviso=sesion&siguiente=evaluar&ticket=${encodeURIComponent(refTicket)}`;
    errorPagina("Tu sesión terminó. Vuelve a ingresar para seguir.", enlace);
  }

  function noEncontrado() {
    const enlace = elemento("a", "boton", "Ir a mi cuenta");
    enlace.href = "cuenta.html";
    errorPagina("No encontramos este trabajo. Ábrelo desde tus pedidos o tus trabajos.", enlace);
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
        entrada.setAttribute("aria-describedby", `error-${dimension}`);
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
    document.getElementById("titulo-mia").textContent =
      datos.evalua_a === "maestro" ? "Tu evaluación del maestro" : "Tu evaluación del cliente";
    // Tu evaluación: ya hecha (solo lectura), por hacer, o todavía no disponible.
    mia.hidden = !datos.mia;
    if (datos.mia) {
      mia.replaceChildren(elemento("p", "", "Ya evaluaste este trabajo. Esta es tu evaluación:"), ...resumen(datos.mia));
    }
    formEvaluacion.hidden = !datos.puede_evaluar;
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
    const esMaestro = Object.prototype.hasOwnProperty.call(ticket, "precio_registrable");
    const volver = document.getElementById("volver");
    volver.href = esMaestro ? "mis-trabajos.html" : "mis-pedidos.html";
    volver.textContent = esMaestro ? "Mis trabajos" : "Mis pedidos";
    document.getElementById("subtitulo").textContent =
      `${ticket.servicio.nombre}, ${formato.fechaConReferencia(ticket.bloque.fecha)}, de ${ticket.bloque.inicio} a ${ticket.bloque.fin}`;
    if (!(await cargarEvaluaciones())) {
      return;
    }
    cargando.hidden = true;
    contenido.hidden = false;
    if (window.location.hash === "#recibida") {
      document.getElementById("recibida").focus();
    }
  }

  // --- Envíos ---

  formulario.prepararBoton(formEvaluacion);
  formulario.prepararBoton(formDenuncia);

  formEvaluacion.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(formEvaluacion);
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
      // 409: ya evaluaste o el trabajo no está terminado; se muestra lo que dice el servidor.
      await cargarEvaluaciones();
      if (estado === 409) {
        avisoEvaluar.hidden = false;
        avisoEvaluar.textContent = datos.mensaje;
      }
      document.getElementById("titulo-mia").focus();
      return;
    }
    const campo = formulario.mostrarErrores(formEvaluacion, datos);
    if (campo) {
      campo.focus();
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
      await cargarEvaluaciones();
      document.getElementById("recibida").focus();
      return;
    }
    if (estado === 409) {
      formulario.avisar(formDenuncia, datos.mensaje, "error");
      return;
    }
    const campo = formulario.mostrarErrores(formDenuncia, datos);
    if (campo) {
      campo.focus();
    }
  });

  document.getElementById("titulo-mia").tabIndex = -1;
  cargar();
})();
