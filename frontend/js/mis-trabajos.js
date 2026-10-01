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

  const cargando = document.getElementById("cargando");
  const avisoPagina = document.getElementById("aviso-pagina");
  const avisoResultado = document.getElementById("aviso-resultado");
  const contenido = document.getElementById("contenido");

  const listaAvisos = document.getElementById("lista-avisos");
  const contadorAvisos = document.getElementById("contador-avisos");

  const detalle = document.getElementById("detalle-pedido");
  const confirmarAccion = document.getElementById("confirmar-accion");
  const avisoDetalle = document.getElementById("aviso-detalle");
  const avisoAccion = document.getElementById("aviso-accion");
  const botonAceptar = document.getElementById("aceptar-pedido");
  const botonRechazar = document.getElementById("rechazar-pedido");

  const ESTADOS_TAB = { pendiente: "pendiente", aceptado: "aceptado", historial: "historial" };
  const paginas = { pendiente: 1, aceptado: 1, historial: 1 };

  const bloquePrecio = document.getElementById("bloque-precio");
  const formPrecio = document.getElementById("form-precio");
  const campoMonto = document.getElementById("monto-final");
  const avisoPrecio = document.getElementById("aviso-precio");
  let ticketAbierto = null;
  let tabActual = "pendiente";
  let refAbierto = null;
  let accionPendiente = null; // "aceptacion" | "rechazo"

  const elemento = dom.elemento;

  // --- Sesión y acceso ---

  function sesionTerminada() {
    contenido.hidden = true;
    const enlace = elemento("a", "boton", "Ingresar de nuevo");
    enlace.href = "ingresar.html?aviso=sesion&siguiente=trabajos";
    avisoPagina.className = "aviso aviso-error";
    avisoPagina.replaceChildren("Tu sesión terminó. Vuelve a ingresar para ver tus trabajos.", enlace);
    avisoPagina.focus();
  }

  function sinAcceso() {
    contenido.hidden = true;
    const enlace = elemento("a", "boton", "Ir a mi cuenta");
    enlace.href = "cuenta.html";
    avisoPagina.className = "aviso aviso-error";
    avisoPagina.replaceChildren(
      "Esta página es para maestros. Si quieres trabajar como maestro, postula desde «Mi cuenta».",
      enlace
    );
    avisoPagina.focus();
  }

  function errorCarga() {
    contenido.hidden = true;
    const boton = elemento("button", "", "Reintentar");
    boton.type = "button";
    boton.addEventListener("click", cargar);
    avisoPagina.className = "aviso aviso-error";
    avisoPagina.replaceChildren(
      "No pudimos cargar tus trabajos. Revisa tu señal o tu wifi e inténtalo de nuevo. ",
      boton
    );
    avisoPagina.focus();
  }

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
    if (!refAbierto) {
      return;
    }
    const boton = document.getElementById("registrar-precio");
    boton.disabled = true;
    const { estado, datos } = await api.enviar(
      `/api/tickets/${encodeURIComponent(refAbierto)}/precio-final`,
      { monto: formato.leerEntero(campoMonto.value) }
    );
    boton.disabled = false;
    if (estado === 401) {
      sesionTerminada();
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
    guardarDetalleFlotante();
    refAbierto = null;
    cargarTab(tabActual);
    avisoResultado.focus();
  });

  // --- Tarjeta resumen de un pedido ---

  function lineaFecha(ticket) {
    return `${formato.fechaConReferencia(ticket.bloque.fecha)}, de ${ticket.bloque.inicio} a ${ticket.bloque.fin}`;
  }

  function tarjeta(ticket) {
    const item = elemento("li", "tarjeta");
    item.dataset.ref = ticket.ref;
    const titulo = elemento("h3", "", `${ticket.servicio.nombre} en ${ticket.comuna.nombre}`);
    titulo.tabIndex = -1;
    const info = elemento(
      "dl", "datos",
      elemento("dt", "", "Cuándo"), elemento("dd", "", lineaFecha(ticket)),
      elemento("dt", "", "Estado"), elemento("dd", "", estadoPedido.etiqueta(ticket.estado))
    );
    item.append(titulo, info);
    const precio = textoPrecio(ticket);
    if (precio) {
      item.append(elemento("p", "", precio));
    }
    if (ticket.motivo_cierre_texto) {
      item.append(elemento("p", "", `Se cerró: ${ticket.motivo_cierre_texto}.`));
    }
    const boton = elemento("button", "boton-secundario", "Ver detalle");
    boton.type = "button";
    boton.setAttribute("aria-label", `Ver detalle del pedido de ${ticket.servicio.nombre} en ${ticket.comuna.nombre}`);
    boton.addEventListener("click", () => abrirDetalle(ticket.ref, item));
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

  function guardarDetalleFlotante() {
    detalle.hidden = true;
    bloquePrecio.hidden = true;
    ticketAbierto = null;
    confirmarAccion.hidden = true;
    document.querySelector("main").append(detalle, confirmarAccion);
  }

  function pintarDetalle(ticket) {
    document.getElementById("titulo-detalle").textContent = `${ticket.servicio.nombre} en ${ticket.comuna.nombre}`;
    const filas = [
      ["Cuándo", lineaFecha(ticket)],
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

  async function abrirDetalle(ref, item) {
    guardarDetalleFlotante();
    refAbierto = ref;
    detalle.hidden = false;
    item.append(detalle);
    document.getElementById("titulo-detalle").focus();
    avisoDetalle.className = "aviso";
    avisoDetalle.replaceChildren("Cargando…");
    const { estado, datos } = await api.obtener(`/api/tickets/${encodeURIComponent(ref)}`);
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado !== 200) {
      avisoDetalle.className = "aviso aviso-error";
      avisoDetalle.textContent = "No pudimos cargar el detalle. Vuelve a intentarlo.";
      return;
    }
    pintarDetalle(datos.ticket);
  }

  document.getElementById("cerrar-detalle").addEventListener("click", () => {
    guardarDetalleFlotante();
    refAbierto = null;
  });

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
    detalle.querySelector(".acciones").after(confirmarAccion);
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
    if (!refAbierto || !accionPendiente) {
      return;
    }
    const textos = TEXTOS_ACCION[accionPendiente];
    const boton = document.getElementById("accion-si");
    boton.disabled = true;
    const { estado, datos } = await api.enviar(`/api/tickets/${encodeURIComponent(refAbierto)}/${textos.ruta}`);
    boton.disabled = false;
    if (estado === 401) {
      sesionTerminada();
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
      guardarDetalleFlotante();
      refAbierto = null;
      cargarTab(tabActual);
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
    guardarDetalleFlotante();
    refAbierto = null;
    cargarTab(tabActual);
  });

  // --- Listas por pestaña ---

  function pintarLista(estado, tickets, total) {
    const lista = document.getElementById(`lista-${estado}`);
    lista.replaceChildren(...tickets.map(tarjeta));
    document.getElementById(`sin-${estado}`).hidden = tickets.length > 0;
    const nav = document.getElementById(`paginacion-${estado}`);
    const paginasTotales = Math.max(1, Math.ceil(total / 20));
    nav.hidden = paginasTotales <= 1;
    document.getElementById(`texto-pagina-${estado}`).textContent = `Página ${paginas[estado]} de ${paginasTotales}`;
    nav.querySelector("[data-anterior]").disabled = paginas[estado] <= 1;
    nav.querySelector("[data-siguiente]").disabled = paginas[estado] >= paginasTotales;
  }

  async function cargarListaEstado(estado) {
    // Historial: sin «estado», el servidor devuelve todos los pedidos (CA-08.1).
    const filtro = estado === "historial" ? "" : `estado=${estado}&`;
    const { estado: cod, datos } = await api.obtener(`${RUTA}?${filtro}pagina=${paginas[estado]}`);
    if (cod === 401) {
      sesionTerminada();
      return false;
    }
    if (cod === 403) {
      sinAcceso();
      return false;
    }
    if (cod !== 200) {
      errorCarga();
      return false;
    }
    guardarDetalleFlotante();
    refAbierto = null;
    pintarLista(estado, datos.tickets, datos.total);
    return true;
  }

  async function cargarTab(tab) {
    tabActual = tab;
    for (const seccion of Object.keys(ESTADOS_TAB)) {
      document.getElementById(`tab-${seccion}`).classList.toggle("oculto", seccion !== tab);
    }
    await cargarListaEstado(ESTADOS_TAB[tab]);
  }

  document.getElementById("pestanas").addEventListener("click", (evento) => {
    const boton = evento.target.closest("[data-tab]");
    if (!boton) {
      return;
    }
    for (const otro of document.querySelectorAll("#pestanas .filtro")) {
      otro.setAttribute("aria-pressed", String(otro === boton));
    }
    cargarTab(boton.dataset.tab);
  });

  for (const nav of document.querySelectorAll("[id^='paginacion-']")) {
    const estado = nav.id.replace("paginacion-", "");
    nav.querySelector("[data-anterior]").addEventListener("click", () => {
      paginas[estado] = Math.max(1, paginas[estado] - 1);
      cargarListaEstado(estado);
    });
    nav.querySelector("[data-siguiente]").addEventListener("click", () => {
      paginas[estado] += 1;
      cargarListaEstado(estado);
    });
  }

  // --- Avisos (ADR-024) ---

  function lineaAviso(aviso) {
    const item = elemento("li", "aviso-vencimiento");
    const icono = elemento("span", "icono-aviso", "🔔");
    icono.setAttribute("aria-hidden", "true");
    // Nunca solo el color: lo no visto lleva además la palabra "Nuevo" (RNF-16).
    const detalleTexto = elemento("span", "detalle-aviso", aviso.visto ? "" : "Nuevo: ", aviso.texto);
    if (aviso.enlace && aviso.enlace.startsWith("/buscar.html")) {
      const enlace = elemento("a", "boton boton-secundario", "Buscar otro maestro");
      enlace.href = aviso.enlace;
      detalleTexto.append(" ", enlace);
    }
    if (aviso.enlace && aviso.enlace.startsWith("/conversacion.html")) {
      const enlace = elemento("a", "boton boton-secundario", "Ver conversación");
      enlace.href = aviso.enlace;
      detalleTexto.append(" ", enlace);
    }
    item.append(icono, detalleTexto);
    return item;
  }

  async function cargarAvisos() {
    const { estado, datos } = await api.obtener("/api/avisos");
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado !== 200) {
      listaAvisos.replaceChildren();
      document.getElementById("sin-avisos").hidden = false;
      document.getElementById("sin-avisos").textContent = "No pudimos cargar tus avisos.";
      return;
    }
    document.getElementById("sin-avisos").hidden = datos.avisos.length > 0;
    document.getElementById("sin-avisos").textContent = "No tienes avisos.";
    listaAvisos.replaceChildren(...datos.avisos.map(lineaAviso));
    contadorAvisos.textContent = datos.sin_ver > 0 ? `(${datos.sin_ver} sin ver)` : "";
    const sinVer = datos.avisos.filter((a) => !a.visto).map((a) => a.ref);
    if (sinVer.length > 0) {
      const marcados = await api.enviar("/api/avisos/vistos", { avisos: sinVer });
      if (marcados.estado === 200) {
        contadorAvisos.textContent = marcados.datos.sin_ver > 0 ? `(${marcados.datos.sin_ver} sin ver)` : "";
      }
    }
  }

  document.getElementById("actualizar-avisos").addEventListener("click", cargarAvisos);

  // --- Carga inicial ---

  async function cargar() {
    cargando.hidden = false;
    avisoPagina.className = "aviso";
    avisoPagina.replaceChildren();
    const ok = await cargarListaEstado("pendiente");
    cargando.hidden = true;
    if (!ok) {
      return;
    }
    contenido.hidden = false;
    cargarAvisos();
  }

  cargar();
})();
