// Mis trabajos (maestro): bandejas por estado, avisos, aceptar y rechazar
// (HU-07, RF-18 a RF-20, RF-24, CA-15.1, CA-08.2, CA-23.5, CA-23.7; ADR-023, ADR-024).
// - GET /api/maestros/tickets?estado=…&pagina=…: 20 por página (servidor).
// - Mientras el pedido está pendiente el servidor nunca envía la dirección,
//   el nombre ni el teléfono del cliente (RF-17, RNF-08): esta página no los
//   pide ni los muestra hasta que el pedido queda aceptado.
// - GET /api/tickets/<ref>: detalle fresco antes de ofrecer aceptar o rechazar
//   (protección al actuar: el estado pudo cambiar desde que se pintó la lista).
// - GET /api/avisos y POST /api/avisos/vistos: sin consultas periódicas (D-16);
//   se marcan vistos apenas se muestran.
// - Historial (HU-08, CA-08.1): GET sin «estado» trae todos los pedidos, con
//   «precio» y «motivo_cierre_texto» del servidor.
// - Precio final (HU-16, RF-26, RF-27): POST /api/tickets/<ref>/precio-final
//   {monto}. La página solo explica si el cliente tendrá que aceptarlo; quien
//   decide si el trabajo termina es el servidor.
// RNF-16: cada estado lleva ícono y texto. RNF-17: "pedido" y "horario".
"use strict";

(() => {
  const RUTA = "/api/maestros/tickets";

  const avisoResultado = document.getElementById("aviso-resultado");

  const detalle = document.getElementById("detalle-pedido");
  const confirmarAccion = document.getElementById("confirmar-accion");
  const avisoDetalle = document.getElementById("aviso-detalle");
  const avisoAccion = document.getElementById("aviso-accion");
  const botonAceptar = document.getElementById("aceptar-pedido");
  const botonRechazar = document.getElementById("rechazar-pedido");

  const bloquePrecio = document.getElementById("bloque-precio");
  const formPrecio = document.getElementById("form-precio");
  const campoMonto = document.getElementById("monto-final");
  const avisoPrecio = document.getElementById("aviso-precio");
  let ticketAbierto = null;
  let accionPendiente = null; // "aceptacion" | "rechazo"

  const elemento = dom.elemento;

  // --- Precio final (texto del servidor: el mismo monto para ambas partes, RF-28) ---

  function textoPrecio(ticket) {
    if (!ticket.precio) {
      return "";
    }
    const monto = formato.monto(ticket.precio.monto);
    return ticket.precio.estado === "acordado"
      ? `Precio final acordado: ${monto}.`
      : `Precio final: ${monto}, esperando que el cliente lo acepte.`;
  }

  // Solo explica; si el trabajo termina o no, lo decide el servidor (RF-27).
  function explicarPrecio() {
    const ticket = ticketAbierto;
    if (!ticket) {
      return;
    }
    const explicacion = document.getElementById("explicacion-precio");
    const escrito = formato.leerMonto(campoMonto.value);
    const publicado = formato.monto(ticket.monto_publicado);
    if (ticket.modalidad === "por_hora") {
      explicacion.textContent = "Como cobras por hora, el cliente tendrá que aceptar este precio. " +
        "El trabajo queda terminado cuando lo acepte.";
    } else if (!/^\d+$/.test(escrito)) {
      explicacion.textContent = `Si es el mismo precio publicado (${publicado}), el trabajo queda terminado al ` +
        "registrarlo. Si es distinto, el cliente tendrá que aceptarlo.";
    } else if (Number(escrito) === ticket.monto_publicado) {
      explicacion.textContent = "Es el mismo precio publicado: al registrarlo, el trabajo queda terminado.";
    } else {
      explicacion.textContent = `Es distinto del precio publicado (${publicado}): el cliente tendrá que ` +
        "aceptarlo antes de que el trabajo quede terminado.";
    }
  }

  function pintarPrecio(ticket) {
    ticketAbierto = ticket;
    bloquePrecio.hidden = ticket.estado !== "aceptado";
    if (bloquePrecio.hidden) {
      return;
    }
    const estadoPrecio = document.getElementById("precio-estado");
    formPrecio.hidden = !ticket.precio_registrable;
    if (!ticket.precio_registrable) {
      estadoPrecio.textContent = "Podrás registrar el precio final cuando empiece el horario del trabajo.";
      return;
    }
    estadoPrecio.textContent = ticket.precio
      ? `Registraste ${formato.monto(ticket.precio.monto)}. Esperando que el cliente lo acepte. ` +
        "Si te equivocaste, registra el monto correcto."
      : "Cuando termines el trabajo, escribe cuánto cobraste en total.";
    document.getElementById("precio-publicado").textContent =
      `Precio publicado: ${formato.monto(ticket.monto_publicado)} ${(ticket.modalidad_texto || "").toLowerCase()}`.trim() + ".";
    campoMonto.value = "";
    campoMonto.removeAttribute("aria-invalid");
    avisoPrecio.className = "aviso";
    avisoPrecio.replaceChildren();
    explicarPrecio();
  }

  campoMonto.addEventListener("input", explicarPrecio);

  formPrecio.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (!vista.refAbierto) {
      return;
    }
    const boton = document.getElementById("registrar-precio");
    boton.disabled = true;
    const { estado, datos } = await api.enviar(
      `/api/tickets/${encodeURIComponent(vista.refAbierto)}/precio-final`,
      { monto: formato.leerEntero(campoMonto.value) }
    );
    boton.disabled = false;
    if (estado === 401) {
      vista.sesionTerminada();
      return;
    }
    if (estado === 400) {
      campoMonto.setAttribute("aria-invalid", "true");
      avisoPrecio.className = "aviso aviso-error";
      avisoPrecio.textContent = (datos.errores && datos.errores.monto) || datos.mensaje;
      campoMonto.focus();
      return;
    }
    if (estado !== 200) {
      avisoPrecio.className = "aviso aviso-error";
      avisoPrecio.textContent = estado === 0
        ? "No pudimos confirmar si se guardó. Revisa tu señal y toca Registrar de nuevo: el precio no se duplica."
        : (datos.mensaje || "No pudimos registrar el precio. Vuelve a intentarlo.");
      avisoPrecio.focus();
      return;
    }
    avisoResultado.className = "aviso aviso-exito";
    avisoResultado.textContent = datos.ticket.estado === "finalizado"
      ? "Registraste el precio final. El trabajo quedó terminado."
      : "Registraste el precio final. Le avisamos al cliente para que lo acepte.";
    vista.guardarDetalleFlotante();
    vista.refAbierto = null;
    vista.recargar();
    avisoResultado.focus();
  });

  // --- Plazo de respuesta de un pedido nuevo (M-02) ---
  // Solo presentación: el servidor entrega «vence_en» y es quien cierra el pedido.

  function textoPlazo(ticket) {
    const vence = ticket.vence_en ? new Date(ticket.vence_en) : null;
    if (!vence || Number.isNaN(vence.getTime())) {
      return "";
    }
    const minutos = Math.floor((vence.getTime() - Date.now()) / 60000);
    if (minutos <= 0) {
      return "El plazo para responder ya terminó. El pedido se cerrará solo.";
    }
    const horas = Math.floor(minutos / 60);
    const resto = minutos % 60;
    const cuanto = horas > 0 ? `${horas} h${resto ? ` ${resto} min` : ""}` : `${minutos} min`;
    const dia = ticket.vence_en.slice(0, 10);
    const hoy = formato.hoyEnChile();
    const cuando = dia === hoy ? "hoy" : dia === formato.sumarDias(hoy, 1) ? "mañana" : formato.fechaLarga(dia);
    return `Vence en ${cuanto}: responde antes de las ${ticket.vence_en.slice(11, 16)} (${cuando}).`;
  }

  // --- Tarjeta resumen de un pedido ---

  function tarjeta(ticket) {
    const esNuevo = ticket.estado === "pendiente";
    const item = elemento("li", esNuevo ? "tarjeta pedido-nuevo" : "tarjeta");
    item.dataset.ref = ticket.ref;
    const titulo = elemento("h3", "", `${ticket.servicio.nombre} en ${ticket.comuna.nombre}`);
    titulo.tabIndex = -1;
    const info = elemento(
      "dl", "datos",
      elemento("dt", "", "Cuándo"), elemento("dd", "", bandeja.lineaFecha(ticket)),
      elemento("dt", "", "Estado"), elemento("dd", "", estadoPedido.etiqueta(ticket.estado))
    );
    item.append(titulo);
    const plazo = esNuevo ? textoPlazo(ticket) : "";
    if (plazo) {
      item.append(elemento("p", "plazo-respuesta", plazo));
    }
    item.append(info);
    const precio = textoPrecio(ticket);
    if (precio) {
      item.append(elemento("p", "", precio));
    }
    if (ticket.motivo_cierre_texto) {
      item.append(elemento("p", "", `Se cerró: ${ticket.motivo_cierre_texto}.`));
    }
    const boton = elemento("button", esNuevo ? "" : "boton-secundario", esNuevo ? "Ver el pedido y responder" : "Ver detalle");
    boton.type = "button";
    boton.setAttribute("aria-label", `${esNuevo ? "Ver y responder" : "Ver detalle"} del pedido de ${ticket.servicio.nombre} en ${ticket.comuna.nombre}`);
    boton.addEventListener("click", () => vista.abrirDetalle(ticket.ref, item));
    const acciones = elemento("div", "acciones", boton);
    // Conversación (HU-07, CA-07.3): solo desde aceptado; en finalizado, para leerla.
    if (ticket.estado === "aceptado" || ticket.estado === "finalizado") {
      const conversacion = elemento("a", "boton boton-secundario", "Ver conversación");
      conversacion.href = `conversacion.html?ticket=${encodeURIComponent(ticket.ref)}`;
      conversacion.setAttribute("aria-label", `Ver conversación del pedido de ${ticket.servicio.nombre} en ${ticket.comuna.nombre}`);
      acciones.append(conversacion);
    }
    // Evaluación (HU-09, HU-18, RF-29, RF-31): solo en una orden finalizada. En evaluar.html
    // se ve la evaluación propia, la recibida y el botón "Denunciar".
    if (ticket.estado === "finalizado") {
      const evaluar = elemento("a", "boton boton-secundario", "Evaluar al cliente");
      evaluar.href = `evaluar.html?ticket=${encodeURIComponent(ticket.ref)}`;
      evaluar.setAttribute("aria-label", `Evaluar al cliente: evaluación del trabajo de ${ticket.servicio.nombre} en ${ticket.comuna.nombre}`);
      const recibida = elemento("a", "boton boton-secundario", "Ver evaluación recibida o denunciar");
      recibida.href = `evaluar.html?ticket=${encodeURIComponent(ticket.ref)}#recibida`;
      recibida.setAttribute("aria-label", `Ver la evaluación que recibiste del trabajo de ${ticket.servicio.nombre} en ${ticket.comuna.nombre}, o denunciarla`);
      acciones.append(evaluar, recibida);
    }
    item.append(acciones);
    return item;
  }

  // --- Detalle (fresco, GET /api/tickets/<ref>) ---

  function pintarDetalle(ticket) {
    document.getElementById("titulo-detalle").textContent = `${ticket.servicio.nombre} en ${ticket.comuna.nombre}`;
    const filas = [
      ["Cuándo", bandeja.lineaFecha(ticket)],
      ["Comuna", ticket.comuna.nombre],
      ["Qué necesita", ticket.descripcion],
      ["Materiales", ticket.materiales ? "El cliente tiene los materiales" : "Tienes que llevar los materiales"],
      ["Precio de referencia acordado", `${formato.monto(ticket.monto_publicado)} ${(ticket.modalidad_texto || "").toLowerCase()}`.trim()],
    ];
    if (ticket.contacto) {
      filas.push(
        ["Cliente", ticket.contacto.nombre],
        ["Dirección", ticket.contacto.direccion],
        ["Teléfono del cliente", ticket.contacto.telefono]
      );
    }
    if (ticket.precio) {
      filas.push(["Precio final", textoPrecio(ticket)]);
    }
    if (ticket.motivo_cierre_texto) {
      filas.push(["Por qué se cerró", ticket.motivo_cierre_texto]);
    }
    const datosDetalle = document.getElementById("datos-detalle");
    datosDetalle.replaceChildren();
    for (const [etiqueta, valor] of filas) {
      datosDetalle.append(elemento("dt", "", etiqueta), elemento("dd", "", String(valor || "—")));
    }
    datosDetalle.append(elemento("dt", "", "Estado"), elemento("dd", "", estadoPedido.etiqueta(ticket.estado)));
    const esNuevo = ticket.estado === "pendiente";
    botonAceptar.hidden = !esNuevo;
    botonRechazar.hidden = !esNuevo;
    avisoDetalle.className = "aviso";
    avisoDetalle.replaceChildren();
    pintarPrecio(ticket);
  }

  // --- Aceptar y rechazar (RF-19, RF-20), con confirmación previa ---

  const TEXTOS_ACCION = {
    aceptacion: {
      titulo: "¿Aceptar este pedido?",
      texto: "El horario quedará ocupado y verás los datos de contacto del cliente.",
      boton: "Sí, aceptar",
      ruta: "aceptacion",
      exito: "Aceptaste el pedido.",
    },
    rechazo: {
      titulo: "¿Rechazar este pedido?",
      texto: "El cliente sabrá que no puedes tomarlo y el horario quedará libre otra vez.",
      boton: "Sí, rechazar",
      ruta: "rechazo",
      exito: "Rechazaste el pedido.",
    },
  };

  function abrirConfirmacion(tipo) {
    accionPendiente = tipo;
    const textos = TEXTOS_ACCION[tipo];
    document.getElementById("titulo-confirmar-accion").textContent = textos.titulo;
    document.getElementById("texto-confirmar-accion").textContent = textos.texto;
    document.getElementById("accion-si").textContent = textos.boton;
    avisoAccion.className = "aviso";
    avisoAccion.replaceChildren();
    botonAceptar.closest(".acciones").after(confirmarAccion);
    confirmarAccion.hidden = false;
    document.getElementById("titulo-confirmar-accion").focus();
  }

  botonAceptar.addEventListener("click", () => abrirConfirmacion("aceptacion"));
  botonRechazar.addEventListener("click", () => abrirConfirmacion("rechazo"));

  document.getElementById("accion-no").addEventListener("click", () => {
    confirmarAccion.hidden = true;
    accionPendiente = null;
  });

  document.getElementById("accion-si").addEventListener("click", async () => {
    if (!vista.refAbierto || !accionPendiente) {
      return;
    }
    const textos = TEXTOS_ACCION[accionPendiente];
    const boton = document.getElementById("accion-si");
    boton.disabled = true;
    const { estado, datos } = await api.enviar(`/api/tickets/${encodeURIComponent(vista.refAbierto)}/${textos.ruta}`);
    boton.disabled = false;
    if (estado === 401) {
      vista.sesionTerminada();
      return;
    }
    avisoResultado.className = "aviso";
    avisoResultado.replaceChildren();
    if (estado === 409) {
      // El pedido cambió (por ejemplo, se cerró): se avisa arriba y se
      // recarga la lista para que deje de aparecer en la pestaña equivocada.
      confirmarAccion.hidden = true;
      accionPendiente = null;
      avisoResultado.className = "aviso aviso-error";
      avisoResultado.textContent = datos.mensaje;
      vista.guardarDetalleFlotante();
      vista.refAbierto = null;
      vista.recargar();
      return;
    }
    if (estado !== 200) {
      avisoAccion.className = "aviso aviso-error";
      avisoAccion.textContent = datos.mensaje;
      return;
    }
    confirmarAccion.hidden = true;
    accionPendiente = null;
    avisoResultado.className = "aviso aviso-exito";
    avisoResultado.textContent = textos.exito;
    vista.guardarDetalleFlotante();
    vista.refAbierto = null;
    vista.recargar();
  });

  // --- Carga inicial ---

  const vista = bandeja.crear({
    ruta: RUTA,
    siguiente: "trabajos",
    textos: {
      sesion: "Tu sesión terminó. Vuelve a ingresar para ver tus trabajos.",
      sinAcceso: "Esta página es para maestros. Si quieres trabajar como maestro, postula desde «Mi cuenta».",
      errorCarga: "No pudimos cargar tus trabajos. Revisa tu señal o tu wifi e inténtalo de nuevo. ",
    },
    tarjeta,
    pintarDetalle,
    flotantes: [confirmarAccion],
    alGuardarDetalle() {
      bloquePrecio.hidden = true;
      ticketAbierto = null;
    },
  });

  vista.iniciar();
})();
