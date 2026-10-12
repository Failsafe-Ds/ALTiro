// Conversación de un pedido aceptado (HU-07, RF-25, CA-07.1 a CA-07.3; ADR-026, E-2).
// - GET /api/tickets/<ref>: datos del pedido (abrir la página sí cuenta como actividad).
// - GET /api/tickets/<ref>/mensajes?despues=<ref>: cada 20 s y solo con la página
//   visible. El servidor no renueva la sesión con esta consulta (ADR-005).
// - POST /api/tickets/<ref>/mensajes {texto, clave_envio}: si falla, el texto se
//   conserva y el reintento usa la misma clave_envio (el servidor no duplica).
// - Finalizado: solo lectura, con el aviso escrito. Cerrado: "no hubo conversación".
"use strict";

(() => {
  const INTERVALO_MS = 20000;
  const QUIEN = { tu: "Tú", cliente: "Cliente", maestro: "Maestro" };

  const parametros = new URLSearchParams(window.location.search);
  const refTicket = parametros.get("ticket") || "";
  const rutaTicket = `/api/tickets/${encodeURIComponent(refTicket)}`;
  const rutaMensajes = `${rutaTicket}/mensajes`;
  const claveBorrador = `altiro.conversacion.${refTicket}`;

  const cargando = document.getElementById("cargando");
  const avisoPagina = document.getElementById("aviso-pagina");
  const contenido = document.getElementById("contenido");
  const avisoEstado = document.getElementById("aviso-estado");
  const lista = document.getElementById("lista-mensajes");
  const sinMensajes = document.getElementById("sin-mensajes");
  const formMensaje = document.getElementById("formulario-mensaje");
  const campoTexto = document.getElementById("texto");
  const errorTexto = document.getElementById("error-texto");
  const avisoEnvio = document.getElementById("aviso-envio");
  const botonEnviar = document.getElementById("enviar");

  let ultimoRef = null;
  const vistos = new Set();
  let temporizador = null;
  let cadena = Promise.resolve();
  // Envío pendiente: misma clave mientras el texto no cambie (reintento sin duplicar).
  let pendiente = null;
  let fallosSeguidos = 0;
  let ocultarNuevos = null;
  const avisoNuevos = document.getElementById("aviso-nuevos");
  const FALLO_CONSULTA = "No pudimos revisar mensajes nuevos. Revisa tu señal.";

  const elemento = dom.elemento;

  function nuevaClave() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    const b = window.crypto.getRandomValues(new Uint8Array(16));
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;
    const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
    return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
  }

  // El borrador vive en localStorage y vence a las 2 h del último cambio
  // (ADR-002 E-1); formulario.js lo guarda, lo vence y lo borra al salir.
  const leerBorrador = () => formulario.recuperarTexto(claveBorrador);
  const guardarBorrador = (texto) => formulario.guardarTexto(claveBorrador, texto);

  function fechaHora(iso) {
    return new Date(iso).toLocaleString("es-CL", {
      timeZone: "America/Santiago", weekday: "long", day: "numeric", month: "long",
      hour: "2-digit", minute: "2-digit", hour12: false,
    });
  }

  // --- Errores de página ---

  function detenerSondeo() {
    if (temporizador) {
      window.clearInterval(temporizador);
      temporizador = null;
    }
  }

  function errorPagina(texto, accion) {
    detenerSondeo();
    cargando.hidden = true;
    contenido.hidden = true;
    avisoPagina.className = "aviso aviso-error";
    avisoPagina.hidden = false;
    avisoPagina.replaceChildren(texto, " ", accion);
    avisoPagina.focus();
  }

  function sesionTerminada() {
    const enlace = dom.enlaceIngresar("conversacion", refTicket);
    errorPagina("Tu sesión terminó. Lo que escribiste quedó guardado en este teléfono. Vuelve a ingresar y abre de nuevo la conversación.", enlace);
  }

  function noEncontrada() {
    const enlace = elemento("a", "boton", "Ir a mi cuenta");
    enlace.href = "cuenta.html";
    errorPagina("No encontramos esta conversación. Ábrela desde tus pedidos o tus trabajos.", enlace);
  }

  function errorCarga() {
    const boton = elemento("button", "", "Reintentar");
    boton.type = "button";
    boton.addEventListener("click", cargar);
    errorPagina("No pudimos cargar la conversación. Revisa tu señal o tu wifi.", boton);
  }

  // --- Mensajes ---

  function lineaMensaje(mensaje) {
    const quien = QUIEN[mensaje.autor] || "";
    const item = elemento("li", `mensaje mensaje-${mensaje.autor === "tu" ? "propio" : "otro"}`);
    const cabeza = elemento("p", "mensaje-cabeza", elemento("strong", "", quien), ` · ${fechaHora(mensaje.enviado_en)}`);
    item.append(cabeza, elemento("p", "mensaje-texto", mensaje.texto));
    return item;
  }

  function agregar(mensajes) {
    let llegoAjeno = false;
    for (const mensaje of mensajes) {
      if (vistos.has(mensaje.ref)) {
        continue;
      }
      vistos.add(mensaje.ref);
      lista.append(lineaMensaje(mensaje));
      ultimoRef = mensaje.ref;
      llegoAjeno = llegoAjeno || mensaje.autor !== "tu";
    }
    return llegoAjeno;
    sinMensajes.hidden = vistos.size > 0 || formMensaje.hidden;
  }

  function pintarEstado(datos) {
    if (datos.aviso) {
      avisoEstado.hidden = false;
      avisoEstado.textContent = datos.aviso;
    } else {
      avisoEstado.hidden = true;
    }
    formMensaje.hidden = !datos.puede_escribir;
    if (!datos.puede_escribir) {
      detenerSondeo();
    }
  }

  function mostrarNuevos() {
    avisoNuevos.hidden = false;
    window.clearTimeout(ocultarNuevos);
    ocultarNuevos = window.setTimeout(() => { avisoNuevos.hidden = true; }, 8000);
  }

  function fallaConsulta(forzar) {
    fallosSeguidos += 1;
    if (forzar || fallosSeguidos >= 2) {
      avisoEstado.hidden = false;
      avisoEstado.className = "aviso aviso-error";
      avisoEstado.textContent = FALLO_CONSULTA;
    }
  }

  async function consultarUnaVez(forzar) {
    const ruta = ultimoRef ? `${rutaMensajes}?despues=${encodeURIComponent(ultimoRef)}` : rutaMensajes;
    const { estado, datos } = await api.obtener(ruta);
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado !== 200) {
      // Señal irregular: se vuelve a intentar en la próxima vuelta; se avisa si se pidió
      // a mano o si fallaron dos seguidas.
      fallaConsulta(forzar);
      return;
    }
    fallosSeguidos = 0;
    avisoEstado.className = "aviso";
    pintarEstado(datos);
    if (agregar(datos.mensajes)) {
      mostrarNuevos();
    }
  }

  // Las consultas van en fila: así nunca se salta un mensaje ni se desordena la lista.
  // Sin «forzar» (el sondeo), solo con la página visible.
  function consultarNuevos(forzar) {
    if (forzar === true || document.visibilityState === "visible") {
      cadena = cadena.then(() => consultarUnaVez(forzar === true));
    }
    return cadena;
  }

  function iniciarSondeo() {
    detenerSondeo();
    temporizador = window.setInterval(consultarNuevos, INTERVALO_MS);
  }

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && temporizador) {
      consultarNuevos();
    }
  });

  document.getElementById("actualizar").addEventListener("click", () => consultarNuevos(true));

  // --- Envío ---

  campoTexto.addEventListener("input", () => {
    guardarBorrador(campoTexto.value);
    if (pendiente && pendiente.texto !== campoTexto.value) {
      pendiente = null;
    }
    errorTexto.textContent = "";
    campoTexto.removeAttribute("aria-invalid");
  });

  formMensaje.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const texto = campoTexto.value;
    avisoEnvio.className = "aviso";
    avisoEnvio.setAttribute("role", "alert");
    avisoEnvio.replaceChildren();
    if (!texto.trim()) {
      errorTexto.textContent = "Escribe tu mensaje antes de enviarlo.";
      campoTexto.setAttribute("aria-invalid", "true");
      campoTexto.focus();
      return;
    }
    if (!pendiente || pendiente.texto !== texto) {
      pendiente = { texto, clave: nuevaClave() };
    }
    botonEnviar.disabled = true;
    botonEnviar.textContent = "Enviando…";
    const { estado, datos } = await api.enviar(rutaMensajes, { texto, clave_envio: pendiente.clave });
    botonEnviar.disabled = false;
    botonEnviar.textContent = "Enviar mensaje";
    if (estado === 201 || estado === 200) {
      pendiente = null;
      campoTexto.value = "";
      guardarBorrador("");
      // Mensaje de resultado (CLAUDE.md §9, punto 7).
      formulario.resultado(avisoEnvio, "Mensaje enviado.", "exito");
      await consultarNuevos(true);
      campoTexto.focus();
      return;
    }
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 400 && datos.errores && datos.errores.texto) {
      errorTexto.textContent = datos.errores.texto;
      campoTexto.setAttribute("aria-invalid", "true");
      campoTexto.focus();
      return;
    }
    avisoEnvio.className = "aviso aviso-error";
    if (estado === 0) {
      avisoEnvio.textContent = "No pudimos enviar tu mensaje. Revisa tu señal y toca «Enviar mensaje» de nuevo: no se enviará dos veces.";
    } else {
      avisoEnvio.textContent = datos.mensaje || "No pudimos enviar tu mensaje. Inténtalo de nuevo.";
    }
    avisoEnvio.focus();
    if (estado === 409) {
      // El pedido cambió de estado (por ejemplo, el trabajo terminó): se vuelve a leer.
      consultarNuevos(true);
    }
  });

  // --- Carga ---

  // Bandeja de la parte (sin botón «Volver» en el encabezado, ADR-002 E-3):
  // solo se ofrece como salida cuando la conversación no está disponible.
  let bandeja = { href: "cuenta.html", texto: "Ir a mi cuenta" };

  function pintarPedido(ticket) {
    const bloque = ticket.bloque;
    const esMaestro = Object.prototype.hasOwnProperty.call(ticket, "precio_registrable");
    bandeja = esMaestro
      ? { href: "mis-trabajos.html", texto: "Ir a mis trabajos" }
      : { href: "mis-pedidos.html", texto: "Ir a mis pedidos" };
    // Dos flujos (ADR-002 E-3.2): la marca vuelve al inicio de la parte.
    if (typeof window.altiroFlujo === "function") window.altiroFlujo(esMaestro ? "maestro" : "cliente");
    const con = esMaestro ? "" : (ticket.maestro ? ` con ${ticket.maestro.nombre}` : "");
    document.getElementById("subtitulo").textContent =
      `${ticket.servicio.nombre}${con}, ${formato.fechaConReferencia(bloque.fecha)}, de ${bloque.inicio} a ${bloque.fin}`;
  }

  async function cargar() {
    avisoPagina.className = "aviso";
    avisoPagina.hidden = true;
    avisoPagina.replaceChildren();
    cargando.hidden = false;
    if (!refTicket) {
      noEncontrada();
      return;
    }
    const pedido = await api.obtener(rutaTicket);
    if (pedido.estado === 401) {
      sesionTerminada();
      return;
    }
    if (pedido.estado === 404 || pedido.estado === 400) {
      noEncontrada();
      return;
    }
    if (pedido.estado !== 200) {
      errorCarga();
      return;
    }
    pintarPedido(pedido.datos.ticket);
    const { estado, datos } = await api.obtener(rutaMensajes);
    cargando.hidden = true;
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 409) {
      const enlace = elemento("a", "boton boton-secundario", bandeja.texto);
      enlace.href = bandeja.href;
      errorPagina(datos.mensaje || "Esta conversación ya no está disponible.", enlace);
      return;
    }
    if (estado !== 200) {
      errorCarga();
      return;
    }
    contenido.hidden = false;
    lista.replaceChildren();
    vistos.clear();
    ultimoRef = null;
    pintarEstado(datos);
    agregar(datos.mensajes);
    campoTexto.value = leerBorrador();
    if (datos.puede_escribir) {
      iniciarSondeo();
    }
    document.getElementById("titulo-pagina").focus();
  }

  cargar();
})();
