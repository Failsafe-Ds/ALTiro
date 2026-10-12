// Mis pedidos (cliente): bandejas por estado, avisos y cancelar (HU-06, RF-18
// a RF-20, RF-23, CA-06.3, CA-08.2, CA-10.2, CA-23.5, CA-23.7; ADR-023, ADR-024).
// - GET /api/clientes/tickets?estado=…&pagina=…: 20 por página (servidor).
// - GET /api/tickets/<ref>: detalle fresco antes de ofrecer «Cancelar»
//   (protección al actuar: el estado pudo cambiar desde que se pintó la lista).
// - GET /api/avisos y POST /api/avisos/vistos: sin consultas periódicas (D-16);
//   se marcan vistos apenas se muestran.
// - Historial (HU-08, CA-08.1): GET sin «estado» trae todos los pedidos, con
//   «precio» y «motivo_cierre_texto» del servidor.
// - Precio por aceptar (HU-16, RF-27, CA-16.2): «Aceptar» envía el monto que se
//   muestra (POST …/precio-final/aceptacion {monto}); si el maestro lo cambió,
//   el servidor responde 409 y la lista se recarga. «No estoy de acuerdo»:
//   POST …/precio-final/objecion.
// RNF-16: cada estado lleva ícono y texto. RNF-17: "pedido" y "horario".
"use strict";

(() => {
  const RUTA = "/api/clientes/tickets";

  const avisoResultado = document.getElementById("aviso-resultado");

  const detalle = document.getElementById("detalle-pedido");
  const confirmarCancelar = document.getElementById("confirmar-cancelar");
  const avisoDetalle = document.getElementById("aviso-detalle");
  const avisoCancelar = document.getElementById("aviso-cancelar");
  const botonCancelar = document.getElementById("cancelar-pedido");

  const elemento = dom.elemento;

  // --- Precio final (el mismo monto que ve el maestro, RF-28) ---

  function textoPrecio(ticket) {
    if (!ticket.precio) {
      return "";
    }
    const monto = formato.monto(ticket.precio.monto);
    return ticket.precio.estado === "acordado" ? `Precio final acordado: ${monto}.` : `Precio final por aceptar: ${monto}.`;
  }

  async function responderPrecio(ticket, accion, zona) {
    const ruta = `/api/tickets/${encodeURIComponent(ticket.ref)}/precio-final/${accion}`;
    const cuerpo = accion === "aceptacion" ? { monto: ticket.precio.monto } : undefined;
    for (const boton of zona.querySelectorAll("button")) {
      boton.disabled = true;
    }
    const { estado, datos } = await api.enviar(ruta, cuerpo);
    for (const boton of zona.querySelectorAll("button")) {
      boton.disabled = false;
    }
    if (estado === 401) {
      vista.sesionTerminada();
      return;
    }
    if (estado !== 200) {
      // 409: el maestro cambió el monto o el trabajo ya terminó. Se avisa y se recarga.
      avisoResultado.className = "aviso aviso-error";
      avisoResultado.textContent = datos.mensaje || "No pudimos enviar tu respuesta. Vuelve a intentarlo.";
      avisoResultado.focus();
      vista.recargar();
      return;
    }
    avisoResultado.className = "aviso aviso-exito";
    avisoResultado.textContent = accion === "aceptacion"
      ? "Aceptaste el precio final. El trabajo quedó terminado."
      : "Le avisamos al maestro que no estás de acuerdo con el precio. Coordínalo con él.";
    avisoResultado.focus();
    vista.recargar();
  }

  // Paso de confirmación: aceptar u objetar el precio no se puede deshacer.
  function pedirConfirmacion(ticket, accion, zona, acciones) {
    const monto = formato.monto(ticket.precio.monto);
    const pregunta = accion === "aceptacion"
      ? `¿Aceptas ${monto}? Después no se puede cambiar.`
      : `¿Confirmas que no estás de acuerdo con ${monto}? Le avisaremos al maestro.`;
    const si = elemento("button", "", accion === "aceptacion" ? "Sí, aceptar" : "Sí, no estoy de acuerdo");
    si.type = "button";
    const volver = elemento("button", "boton-secundario", "No, volver");
    volver.type = "button";
    const confirmacion = elemento("div", "", elemento("p", "", elemento("strong", "", pregunta)),
      elemento("div", "acciones", si, volver));
    confirmacion.tabIndex = -1;
    acciones.hidden = true;
    zona.append(confirmacion);
    confirmacion.focus();
    si.addEventListener("click", () => responderPrecio(ticket, accion, zona));
    volver.addEventListener("click", () => {
      confirmacion.remove();
      acciones.hidden = false;
      acciones.querySelector("button").focus();
    });
  }

  // Tarjeta «Precio por aceptar» (CA-16.2): dos botones con texto, sin depender del color.
  function tarjetaPrecio(ticket) {
    const zona = elemento("section", "confirmacion");
    const titulo = elemento("h4", "", "Precio por aceptar");
    const publicado = `${formato.monto(ticket.monto_publicado)} ${(ticket.modalidad_texto || "").toLowerCase()}`.trim();
    const texto = elemento(
      "p", "",
      `${ticket.maestro.nombre} registró un precio final de ${formato.monto(ticket.precio.monto)}. ` +
      `El precio publicado era ${publicado}. Si lo aceptas, el trabajo queda terminado.`
    );
    const aceptar = elemento("button", "", "Aceptar");
    aceptar.type = "button";
    aceptar.setAttribute("aria-label", `Aceptar el precio final de ${formato.monto(ticket.precio.monto)}`);
    aceptar.addEventListener("click", () => pedirConfirmacion(ticket, "aceptacion", zona, acciones));
    const objetar = elemento("button", "boton-secundario", "No estoy de acuerdo");
    objetar.type = "button";
    objetar.addEventListener("click", () => pedirConfirmacion(ticket, "objecion", zona, acciones));
    const acciones = elemento("div", "acciones", aceptar, objetar);
    zona.append(titulo, texto, acciones);
    return zona;
  }

  function tarjeta(ticket) {
    const item = elemento("li", "tarjeta");
    item.dataset.ref = ticket.ref;
    const titulo = elemento("h3", "", `${ticket.servicio.nombre} con ${ticket.maestro.nombre}`);
    titulo.tabIndex = -1;
    const info = elemento(
      "dl", "datos",
      elemento("dt", "", "Cuándo"), elemento("dd", "", bandeja.lineaFecha(ticket)),
      elemento("dt", "", "Estado"), elemento("dd", "", estadoPedido.etiqueta(ticket.estado))
    );
    item.append(titulo, info);
    const precio = textoPrecio(ticket);
    if (ticket.estado === "aceptado" && ticket.precio && ticket.precio.estado === "por_aceptar") {
      item.append(tarjetaPrecio(ticket));
    } else if (precio) {
      item.append(elemento("p", "", precio));
    }
    if (ticket.motivo_cierre_texto) {
      item.append(elemento("p", "", `Se cerró: ${ticket.motivo_cierre_texto}.`));
    }
    const boton = elemento("button", "boton-secundario", "Ver detalle");
    boton.type = "button";
    boton.setAttribute("aria-label", `Ver detalle del pedido de ${ticket.servicio.nombre} con ${ticket.maestro.nombre}`);
    boton.addEventListener("click", () => vista.abrirDetalle(ticket.ref, item));
    const acciones = elemento("div", "acciones", boton);
    // Conversación (HU-07, CA-07.3): solo desde aceptado; en finalizado, para leerla.
    if (ticket.estado === "aceptado" || ticket.estado === "finalizado") {
      const conversacion = elemento("a", "boton boton-secundario", "Ver conversación");
      conversacion.href = `conversacion.html?ticket=${encodeURIComponent(ticket.ref)}`;
      conversacion.setAttribute("aria-label", `Ver conversación del pedido de ${ticket.servicio.nombre} con ${ticket.maestro.nombre}`);
      acciones.append(conversacion);
    }
    // Evaluación (HU-09, HU-18, RF-29, RF-31): solo en una orden finalizada. En evaluar.html
    // se ve la evaluación propia, la recibida y el botón "Denunciar".
    if (ticket.estado === "finalizado") {
      const evaluar = elemento("a", "boton boton-secundario", "Evaluar al maestro");
      evaluar.href = `evaluar.html?ticket=${encodeURIComponent(ticket.ref)}`;
      evaluar.setAttribute("aria-label", `Evaluar al maestro: evaluación del pedido de ${ticket.servicio.nombre} con ${ticket.maestro.nombre}`);
      const recibida = elemento("a", "boton boton-secundario", "Ver evaluación recibida o denunciar");
      recibida.href = `evaluar.html?ticket=${encodeURIComponent(ticket.ref)}#recibida`;
      recibida.setAttribute("aria-label", `Ver la evaluación que recibiste del pedido de ${ticket.servicio.nombre} con ${ticket.maestro.nombre}, o denunciarla`);
      acciones.append(evaluar, recibida);
    }
    item.append(acciones);
    return item;
  }

  // --- Detalle (fresco, GET /api/tickets/<ref>) ---

  function pintarDetalle(ticket) {
    document.getElementById("titulo-detalle").textContent = `${ticket.servicio.nombre} con ${ticket.maestro.nombre}`;
    const filas = [
      ["Cuándo", bandeja.lineaFecha(ticket)],
      ["Comuna", ticket.comuna.nombre],
      ["Dirección", ticket.direccion],
      ["Qué necesitas", ticket.descripcion],
      ["Materiales", ticket.materiales ? "Dijiste que tú los tienes" : "Dijiste que el maestro debe llevarlos"],
      ["Precio de referencia acordado", `${formato.monto(ticket.monto_publicado)} ${(ticket.modalidad_texto || "").toLowerCase()}`.trim()],
    ];
    if (ticket.contacto) {
      filas.push(["Teléfono del maestro", ticket.contacto.telefono]);
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
    botonCancelar.hidden = ticket.estado !== "pendiente";
    avisoDetalle.className = "aviso";
    avisoDetalle.replaceChildren();
  }

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
    if (!vista.refAbierto) {
      return;
    }
    const boton = document.getElementById("cancelar-si");
    boton.disabled = true;
    const { estado, datos } = await api.enviar(`/api/tickets/${encodeURIComponent(vista.refAbierto)}/cancelacion`);
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
      confirmarCancelar.hidden = true;
      avisoResultado.className = "aviso aviso-error";
      avisoResultado.textContent = datos.mensaje;
      vista.guardarDetalleFlotante();
      vista.refAbierto = null;
      vista.recargar();
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
    vista.guardarDetalleFlotante();
    vista.refAbierto = null;
    vista.recargar();
  });

  // --- Carga inicial ---

  const vista = bandeja.crear({
    ruta: RUTA,
    siguiente: "pedidos",
    textos: {
      sesion: "Tu sesión terminó. Vuelve a ingresar para ver tus pedidos.",
      sinAcceso: "Esta página muestra los trabajos que pediste. Para pedir trabajos con esta misma cuenta, entra a «Mi cuenta» y completa «Quiero pedir trabajos».",
      errorCarga: "No pudimos cargar tus pedidos. Revisa tu señal o tu wifi e inténtalo de nuevo. ",
    },
    tarjeta,
    pintarDetalle,
    flotantes: [confirmarCancelar],
    alMostrar() {
      if (new URLSearchParams(location.search).get("enviado") === "1") {
        avisoResultado.className = "aviso aviso-exito";
        avisoResultado.textContent = "Tu pedido fue enviado. Cuando el maestro responda, lo verás aquí.";
      }
    },
  });

  vista.iniciar();
})();
