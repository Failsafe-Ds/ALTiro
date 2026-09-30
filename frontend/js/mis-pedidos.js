// Mis pedidos (cliente): bandejas por estado, avisos y cancelar (HU-06, RF-18
// a RF-20, RF-23, CA-06.3, CA-08.2, CA-10.2, CA-23.5, CA-23.7; ADR-023, ADR-024).
// - GET /api/clientes/tickets?estado=…&pagina=…: 20 por página (servidor).
// - GET /api/tickets/<ref>: detalle fresco antes de ofrecer «Cancelar»
//   (protección al actuar: el estado pudo cambiar desde que se pintó la lista).
// - GET /api/avisos y POST /api/avisos/vistos: sin consultas periódicas (D-16);
//   se marcan vistos apenas se muestran.
// RNF-16: cada estado lleva ícono y texto. RNF-17: "pedido" y "horario".
"use strict";

(() => {
  const RUTA = "/api/clientes/tickets";

  const cargando = document.getElementById("cargando");
  const avisoPagina = document.getElementById("aviso-pagina");
  const avisoResultado = document.getElementById("aviso-resultado");
  const contenido = document.getElementById("contenido");

  const listaAvisos = document.getElementById("lista-avisos");
  const contadorAvisos = document.getElementById("contador-avisos");

  const detalle = document.getElementById("detalle-pedido");
  const confirmarCancelar = document.getElementById("confirmar-cancelar");
  const avisoDetalle = document.getElementById("aviso-detalle");
  const avisoCancelar = document.getElementById("aviso-cancelar");
  const botonCancelar = document.getElementById("cancelar-pedido");

  const ESTADOS_TAB = { pendiente: ["pendiente"], aceptado: ["aceptado"], cerrado: ["finalizado", "cerrado"] };
  const paginas = { pendiente: 1, aceptado: 1, finalizado: 1, cerrado: 1 };
  let tabActual = "pendiente";
  let refAbierto = null;

  function elemento(etiqueta, clase, ...hijos) {
    const nodo = document.createElement(etiqueta);
    if (clase) {
      nodo.className = clase;
    }
    nodo.append(...hijos);
    return nodo;
  }

  // --- Sesión y acceso ---

  function sesionTerminada() {
    contenido.hidden = true;
    const enlace = elemento("a", "boton", "Ingresar de nuevo");
    enlace.href = "ingresar.html?aviso=sesion&siguiente=pedidos";
    avisoPagina.className = "aviso aviso-error";
    avisoPagina.replaceChildren("Tu sesión terminó. Vuelve a ingresar para ver tus pedidos.", enlace);
    avisoPagina.focus();
  }

  function sinAcceso() {
    contenido.hidden = true;
    const enlace = elemento("a", "boton", "Ir a mi cuenta");
    enlace.href = "cuenta.html";
    avisoPagina.className = "aviso aviso-error";
    avisoPagina.replaceChildren(
      "Esta página muestra los trabajos que pediste. Para pedir trabajos con esta misma cuenta, entra a «Mi cuenta» y completa «Quiero pedir trabajos».",
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
      "No pudimos cargar tus pedidos. Revisa tu señal o tu wifi e inténtalo de nuevo. ",
      boton
    );
    avisoPagina.focus();
  }

  // --- Tarjeta resumen de un pedido ---

  function lineaFecha(ticket) {
    return `${formato.fechaConReferencia(ticket.bloque.fecha)}, de ${ticket.bloque.inicio} a ${ticket.bloque.fin}`;
  }

  function tarjeta(ticket) {
    const item = elemento("li", "tarjeta");
    item.dataset.ref = ticket.ref;
    const titulo = elemento("h3", "", `${ticket.servicio.nombre} con ${ticket.maestro.nombre}`);
    titulo.tabIndex = -1;
    const info = elemento(
      "dl", "datos",
      elemento("dt", "", "Cuándo"), elemento("dd", "", lineaFecha(ticket)),
      elemento("dt", "", "Estado"), elemento("dd", "", estadoPedido.etiqueta(ticket.estado))
    );
    item.append(titulo, info);
    if (ticket.estado === "cerrado" && ticket.motivo_cierre) {
      item.append(elemento("p", "", `Se cerró: ${estadoPedido.motivo(ticket.motivo_cierre, false)}.`));
    }
    const boton = elemento("button", "boton-secundario", "Ver detalle");
    boton.type = "button";
    boton.setAttribute("aria-label", `Ver detalle del pedido de ${ticket.servicio.nombre} con ${ticket.maestro.nombre}`);
    boton.addEventListener("click", () => abrirDetalle(ticket.ref, item));
    item.append(elemento("div", "acciones", boton));
    return item;
  }

  // --- Detalle (fresco, GET /api/tickets/<ref>) ---

  function guardarDetalleFlotante() {
    detalle.hidden = true;
    confirmarCancelar.hidden = true;
    document.querySelector("main").append(detalle, confirmarCancelar);
  }

  function pintarDetalle(ticket) {
    document.getElementById("titulo-detalle").textContent = `${ticket.servicio.nombre} con ${ticket.maestro.nombre}`;
    const filas = [
      ["Cuándo", lineaFecha(ticket)],
      ["Comuna", ticket.comuna.nombre],
      ["Dirección", ticket.direccion],
      ["Qué necesitas", ticket.descripcion],
      ["Materiales", ticket.materiales ? "Dijiste que tú los tienes" : "Dijiste que el maestro debe llevarlos"],
      ["Precio de referencia acordado", `${formato.monto(ticket.monto_publicado)} ${(ticket.modalidad_texto || "").toLowerCase()}`.trim()],
    ];
    if (ticket.contacto) {
      filas.push(["Teléfono del maestro", ticket.contacto.telefono]);
    }
    if (ticket.estado === "cerrado" && ticket.motivo_cierre) {
      filas.push(["Por qué se cerró", estadoPedido.motivo(ticket.motivo_cierre, false)]);
    }
    const datosDetalle = document.getElementById("datos-detalle");
    datosDetalle.replaceChildren();
    for (const [etiqueta, valor] of filas) {
      datosDetalle.append(elemento("dt", "", etiqueta), elemento("dd", "", String(valor || "—")));
    }
    datosDetalle.append(elemento("dt", "", "Estado"), elemento("dd", "", estadoPedido.etiqueta(ticket.estado)));
    botonCancelar.hidden = ticket.estado !== "pendiente";
    avisoDetalle.className = "aviso";
    avisoDetalle.replaceChildren();
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

  // --- Cancelar (RF-23, CA-10.2) ---

  botonCancelar.addEventListener("click", () => {
    detalle.querySelector(".acciones").after(confirmarCancelar);
    confirmarCancelar.hidden = false;
    avisoCancelar.className = "aviso";
    avisoCancelar.replaceChildren();
    document.getElementById("titulo-confirmar-cancelar").focus();
  });

  document.getElementById("cancelar-no").addEventListener("click", () => {
    confirmarCancelar.hidden = true;
  });

  document.getElementById("cancelar-si").addEventListener("click", async () => {
    if (!refAbierto) {
      return;
    }
    const boton = document.getElementById("cancelar-si");
    boton.disabled = true;
    const { estado, datos } = await api.enviar(`/api/tickets/${encodeURIComponent(refAbierto)}/cancelacion`);
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
      confirmarCancelar.hidden = true;
      avisoResultado.className = "aviso aviso-error";
      avisoResultado.textContent = datos.mensaje;
      guardarDetalleFlotante();
      refAbierto = null;
      cargarTab(tabActual, true);
      return;
    }
    if (estado !== 200) {
      avisoCancelar.className = "aviso aviso-error";
      avisoCancelar.textContent = datos.mensaje;
      return;
    }
    confirmarCancelar.hidden = true;
    avisoResultado.className = "aviso aviso-exito";
    avisoResultado.textContent = "Cancelaste tu pedido.";
    guardarDetalleFlotante();
    refAbierto = null;
    cargarTab(tabActual, true);
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
    const { estado: cod, datos } = await api.obtener(`${RUTA}?estado=${estado}&pagina=${paginas[estado]}`);
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
    // Evita perder o duplicar el panel de detalle si estaba abierto en una
    // tarjeta que esta lista va a reemplazar (cambio de pestaña o de página).
    guardarDetalleFlotante();
    refAbierto = null;
    pintarLista(estado, datos.tickets, datos.total);
    return true;
  }

  async function cargarTab(tab, forzar) {
    tabActual = tab;
    for (const seccion of Object.keys(ESTADOS_TAB)) {
      document.getElementById(`tab-${seccion}`).classList.toggle("oculto", seccion !== tab);
    }
    for (const estado of ESTADOS_TAB[tab]) {
      if (forzar) {
        paginas[estado] = paginas[estado] || 1;
      }
      await cargarListaEstado(estado);
    }
  }

  document.getElementById("pestanas").addEventListener("click", (evento) => {
    const boton = evento.target.closest("[data-tab]");
    if (!boton) {
      return;
    }
    for (const otro of document.querySelectorAll("#pestanas .filtro")) {
      otro.setAttribute("aria-pressed", String(otro === boton));
    }
    cargarTab(boton.dataset.tab, false);
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
    // Se marcan vistos apenas se muestran (D-16): no hace falta repintar la
    // lista, el contador es lo único que cambia con la confirmación del servidor.
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
    if (new URLSearchParams(location.search).get("enviado") === "1") {
      avisoResultado.className = "aviso aviso-exito";
      avisoResultado.textContent = "Tu pedido fue enviado. Cuando el maestro responda, lo verás aquí.";
    }
    cargarAvisos();
  }

  cargar();
})();
