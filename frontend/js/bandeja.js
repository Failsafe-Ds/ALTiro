// Bandeja de pedidos compartida por «Mis pedidos» (cliente) y «Mis trabajos»
// (maestro) (hallazgo 6, auditoría 2: antes eran dos copias de unas 300 líneas).
// Lo común: pestañas por estado con paginación de 20 (servidor), detalle fresco
// (GET /api/tickets/<ref>), avisos (ADR-024; GET /api/avisos y POST
// /api/avisos/vistos, sin consultas periódicas, D-16) y los avisos de sesión
// terminada, sin acceso y error de carga. Cada página entrega lo propio: la
// tarjeta, el detalle, las acciones y sus textos.
//
// bandeja.crear(opciones) devuelve la vista:
// - opciones.ruta: "/api/clientes/tickets" o "/api/maestros/tickets".
// - opciones.siguiente: clave de ingresar.js para volver tras ingresar.
// - opciones.textos: { sesion, sinAcceso, errorCarga }.
// - opciones.tarjeta(ticket) y opciones.pintarDetalle(ticket).
// - opciones.flotantes: paneles que viajan con el detalle (confirmaciones).
// - opciones.alGuardarDetalle(): lo propio de la página al cerrar el detalle.
// - opciones.alMostrar(): tras la primera carga correcta.
"use strict";

const bandeja = (() => {
  const elemento = dom.elemento;

  function lineaFecha(ticket) {
    return `${formato.fechaConReferencia(ticket.bloque.fecha)}, de ${ticket.bloque.inicio} a ${ticket.bloque.fin}`;
  }

  function crear(opciones) {
    const cargando = document.getElementById("cargando");
    const avisoPagina = document.getElementById("aviso-pagina");
    const contenido = document.getElementById("contenido");
    const listaAvisos = document.getElementById("lista-avisos");
    const contadorAvisos = document.getElementById("contador-avisos");
    const detalle = document.getElementById("detalle-pedido");
    const avisoDetalle = document.getElementById("aviso-detalle");

    const TABS = ["pendiente", "aceptado", "historial"];
    const paginas = { pendiente: 1, aceptado: 1, historial: 1 };
    const vista = { tabActual: "pendiente", refAbierto: null };

    // --- Sesión y acceso ---

    function sesionTerminada() {
      contenido.hidden = true;
      dom.sesionTerminada(avisoPagina, opciones.siguiente, opciones.textos.sesion);
    }

    function sinAcceso() {
      contenido.hidden = true;
      const enlace = elemento("a", "boton", "Ir a mi cuenta");
      enlace.href = "cuenta.html";
      avisoPagina.className = "aviso aviso-error";
      avisoPagina.replaceChildren(opciones.textos.sinAcceso, enlace);
      avisoPagina.focus();
    }

    function errorCarga() {
      contenido.hidden = true;
      const boton = elemento("button", "", "Reintentar");
      boton.type = "button";
      boton.addEventListener("click", cargar);
      avisoPagina.className = "aviso aviso-error";
      avisoPagina.replaceChildren(opciones.textos.errorCarga, boton);
      avisoPagina.focus();
    }

    // --- Detalle (fresco, GET /api/tickets/<ref>) ---

    function guardarDetalleFlotante() {
      detalle.hidden = true;
      if (opciones.alGuardarDetalle) {
        opciones.alGuardarDetalle();
      }
      for (const panel of opciones.flotantes || []) {
        panel.hidden = true;
      }
      document.querySelector("main").append(detalle, ...(opciones.flotantes || []));
    }

    async function abrirDetalle(ref, item) {
      guardarDetalleFlotante();
      vista.refAbierto = ref;
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
      opciones.pintarDetalle(datos.ticket);
    }

    document.getElementById("cerrar-detalle").addEventListener("click", () => {
      guardarDetalleFlotante();
      vista.refAbierto = null;
    });

    // --- Listas por pestaña ---

    function pintarLista(estado, tickets, total) {
      const lista = document.getElementById(`lista-${estado}`);
      lista.replaceChildren(...tickets.map(opciones.tarjeta));
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
      const { estado: cod, datos } = await api.obtener(`${opciones.ruta}?${filtro}pagina=${paginas[estado]}`);
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
      vista.refAbierto = null;
      pintarLista(estado, datos.tickets, datos.total);
      return true;
    }

    async function cargarTab(tab) {
      vista.tabActual = tab;
      for (const seccion of TABS) {
        document.getElementById(`tab-${seccion}`).classList.toggle("oculto", seccion !== tab);
      }
      await cargarListaEstado(tab);
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
      // Solo enlaces del mismo origen y de rutas conocidas (hallazgo B-4).
      const destinoBuscar = dom.enlaceInterno(aviso.enlace, ["/buscar.html"]);
      if (destinoBuscar) {
        const enlace = elemento("a", "boton boton-secundario", "Buscar otro maestro");
        enlace.href = destinoBuscar;
        detalleTexto.append(" ", enlace);
      }
      const destinoConversacion = dom.enlaceInterno(aviso.enlace, ["/conversacion.html"]);
      if (destinoConversacion) {
        const enlace = elemento("a", "boton boton-secundario", "Ver conversación");
        enlace.href = destinoConversacion;
        detalleTexto.append(" ", enlace);
      }
      item.append(icono, detalleTexto);
      return item;
    }

    // Panel plegable de avisos (solo en «Mis trabajos»; «Mis pedidos» no lo tiene).
    function abrirAvisos(abrir) {
      const panel = document.getElementById("detalles-avisos");
      if (panel) {
        panel.open = abrir;
      }
    }

    async function cargarAvisos() {
      const { estado, datos } = await api.obtener("/api/avisos");
      if (estado === 401) {
        sesionTerminada();
        return;
      }
      const sinAvisos = document.getElementById("sin-avisos");
      if (estado !== 200) {
        listaAvisos.replaceChildren();
        sinAvisos.hidden = false;
        sinAvisos.textContent = "No pudimos cargar tus avisos.";
        abrirAvisos(true);
        return;
      }
      sinAvisos.hidden = datos.avisos.length > 0;
      sinAvisos.textContent = "No tienes avisos.";
      listaAvisos.replaceChildren(...datos.avisos.map(lineaAviso));
      contadorAvisos.textContent = datos.sin_ver > 0 ? `(${datos.sin_ver} sin ver)` : "";
      // M-02: el panel se pliega solo si no hay nada sin ver; si lo hay, queda abierto
      // y los avisos se marcan vistos igual que antes (apenas se muestran).
      abrirAvisos(datos.sin_ver > 0 || datos.avisos.length === 0);
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
      if (opciones.alMostrar) {
        opciones.alMostrar();
      }
      cargarAvisos();
    }

    return Object.assign(vista, {
      sesionTerminada,
      abrirDetalle,
      guardarDetalleFlotante,
      recargar: () => cargarTab(vista.tabActual),
      iniciar: cargar,
    });
  }

  return { lineaFecha, crear };
})();
