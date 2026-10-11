// Cola de expedientes de curatoría (HU-19; propuesta del S2, §4, §5 y §9.7).
// - GET /api/curatoria/expedientes?estado=&pagina=: páginas de 20, del más
//   antiguo al más reciente. La API ya excluye el expediente propio (CA-19.4)
//   y no entrega el RUT: la cola tampoco lo muestra.
// - El filtro y la página viven en la dirección (?estado=&pagina=) para que
//   el botón Atrás del navegador desde el detalle regrese al mismo lugar. Son solo
//   navegación: el servidor valida el filtro (400 si no lo reconoce).
// - El resultado se anuncia con aria-live; ningún estado depende solo del color.
"use strict";

(() => {
  const FILTRO_INICIAL = "en_revision";

  const avisoPagina = document.getElementById("aviso-pagina");
  const contenido = document.getElementById("contenido");
  const resultado = document.getElementById("resultado");
  const lista = document.getElementById("lista-expedientes");
  const paginacion = document.getElementById("paginacion");
  const anterior = document.getElementById("pagina-anterior");
  const siguiente = document.getElementById("pagina-siguiente");
  const contenedorFiltros = document.getElementById("filtros");

  const valoresFiltro = curatoria.FILTROS.map((f) => f.valor);
  let estado = FILTRO_INICIAL;
  let pagina = 1;
  let totalPaginas = 1;
  let consulta = 0; // Descarta respuestas de consultas anteriores.

  // "estado" guarda el filtro elegido: un estado del expediente, "" (todos) o
  // curatoria.POR_VENCER, que se pide como ?por_vencer=1.
  function leerDireccion() {
    const parametros = new URLSearchParams(location.search);
    const pedido = parametros.get("estado");
    if (parametros.get("por_vencer") === "1") {
      estado = curatoria.POR_VENCER;
    } else {
      estado = pedido !== null && pedido !== curatoria.POR_VENCER && valoresFiltro.includes(pedido) ? pedido : FILTRO_INICIAL;
    }
    const numero = Number(parametros.get("pagina"));
    pagina = Number.isInteger(numero) && numero >= 1 ? numero : 1;
  }

  // Parámetros de la consulta (y de la dirección de la página).
  function parametrosFiltro() {
    const parametros = new URLSearchParams();
    if (estado === curatoria.POR_VENCER) {
      parametros.set("por_vencer", "1");
    } else if (estado) {
      parametros.set("estado", estado);
    }
    parametros.set("pagina", String(pagina));
    return parametros;
  }

  function escribirDireccion() {
    const parametros = parametrosFiltro();
    if (!estado) {
      parametros.set("estado", "");
    }
    history.replaceState(null, "", `curatoria.html?${parametros}`);
  }

  // --- Filtros ---

  function pintarFiltros() {
    contenedorFiltros.replaceChildren(
      ...curatoria.FILTROS.map((filtro) => {
        const boton = document.createElement("button");
        boton.type = "button";
        boton.className = "filtro";
        boton.dataset.estado = filtro.valor;
        boton.textContent = filtro.texto;
        boton.addEventListener("click", () => {
          if (filtro.valor === estado && pagina === 1) {
            return;
          }
          estado = filtro.valor;
          pagina = 1;
          marcarFiltro();
          cargar();
        });
        return boton;
      })
    );
    marcarFiltro();
  }

  // aria-pressed indica el filtro activo; el estilo agrega un ✓ (no solo color, RNF-16).
  function marcarFiltro() {
    for (const boton of contenedorFiltros.querySelectorAll("button")) {
      boton.setAttribute("aria-pressed", String(boton.dataset.estado === estado));
    }
  }

  function textoFiltro() {
    return curatoria.FILTROS.find((f) => f.valor === estado).texto;
  }

  // --- Lista ---

  const parrafo = (clase, ...hijos) => dom.elemento("p", clase, ...hijos);

  function textoOficios(oficios) {
    if (!oficios.length) {
      return "Sin oficios declarados";
    }
    return oficios.map((o) => (o.regulado ? `${o.nombre} (necesita licencia SEC)` : o.nombre)).join(", ");
  }

  function fila(item) {
    const li = document.createElement("li");
    li.className = "tarjeta documento";
    const titulo = document.createElement("h2");
    titulo.textContent = item.nombre;

    const porRevisar = item.documentos_en_revision;
    const revisar = parrafo(
      porRevisar > 0 ? "cuenta-pendiente" : "",
      porRevisar === 0
        ? "Sin documentos por revisar"
        : porRevisar === 1
          ? "1 documento espera revisión"
          : `${porRevisar} documentos esperan revisión`
    );
    const faltan = item.faltantes_para_aprobar;
    const requisitos = parrafo(
      "ayuda",
      faltan === 0
        ? "Tiene todos los requisitos para aprobar"
        : faltan === 1
          ? "Le falta 1 requisito para aprobar"
          : `Le faltan ${faltan} requisitos para aprobar`
    );

    const ir = curatoria.enlaceBoton(
      "Revisar expediente",
      `curatoria-expediente.html?ref=${encodeURIComponent(item.ref)}`
    );
    ir.setAttribute("aria-label", `Revisar el expediente de ${item.nombre}`);
    const acciones = document.createElement("div");
    acciones.className = "acciones";
    acciones.append(ir);

    li.append(
      titulo,
      parrafo("", "Estado: ", expediente.etiquetaEstado(item.estado, curatoria.ESTADOS_EXPEDIENTE)),
      parrafo("", `Postuló el ${expediente.formatearFechaHora(item.creado_en)}`),
      parrafo("", `Oficios: ${textoOficios(item.oficios)}`),
      revisar,
      requisitos,
      acciones
    );
    return li;
  }

  function pintar(datos) {
    totalPaginas = Math.max(1, Math.ceil(datos.total / datos.tamano_pagina));
    lista.replaceChildren(...datos.expedientes.map(fila));
    const filtro = textoFiltro().toLowerCase();
    if (datos.total === 0) {
      resultado.textContent =
        estado === "" ? "No hay expedientes de otros maestros." : `No hay expedientes con el filtro «${filtro}».`;
    } else if (datos.expedientes.length === 0) {
      resultado.textContent = `No hay expedientes en la página ${pagina}. Vuelve a la página anterior.`;
    } else {
      const cuantos = datos.total === 1 ? "1 expediente" : `${datos.total} expedientes`;
      resultado.textContent = `${cuantos} con el filtro «${filtro}». Página ${pagina} de ${totalPaginas}.`;
    }
    const hayPaginas = totalPaginas > 1 || pagina > 1;
    paginacion.hidden = !hayPaginas;
    anterior.disabled = pagina <= 1;
    siguiente.disabled = pagina >= totalPaginas;
  }

  async function cargar() {
    const esta = ++consulta;
    escribirDireccion();
    curatoria.limpiar(avisoPagina);
    contenido.hidden = false;
    resultado.textContent = "Cargando expedientes…";
    lista.setAttribute("aria-busy", "true");
    const { estado: codigo, datos } = await api.obtener(`${curatoria.RUTA}/expedientes?${parametrosFiltro()}`);
    if (esta !== consulta) {
      return;
    }
    lista.removeAttribute("aria-busy");
    if (codigo === 200) {
      pintar(datos);
      return true;
    }
    lista.replaceChildren();
    paginacion.hidden = true;
    resultado.textContent = "";
    if (codigo === 401) {
      contenido.hidden = true;
      curatoria.avisarSesionTerminada(avisoPagina);
    } else if (codigo === 403) {
      contenido.hidden = true;
      curatoria.avisarSinRol(avisoPagina);
    } else {
      curatoria.avisarErrorCarga(avisoPagina, datos.mensaje, cargar);
    }
    return false;
  }

  // Tras cambiar de página, el foco va al resumen del resultado (se lee la página nueva).
  async function irAPagina(nueva) {
    pagina = nueva;
    if (await cargar()) {
      resultado.focus();
    }
  }

  anterior.addEventListener("click", () => irAPagina(Math.max(1, pagina - 1)));
  siguiente.addEventListener("click", () => irAPagina(pagina + 1));

  // --- Avisos de vencimiento (RF-35; GET /api/curatoria/avisos) ---
  // El texto de cada aviso lo arma el servidor. Se agrega el nombre del
  // maestro y el enlace a su expediente (la API ya excluye el propio, CA-19.4).
  const seccionAvisos = document.getElementById("avisos");
  const estadoAvisos = document.getElementById("estado-avisos");
  const listaAvisos = document.getElementById("lista-avisos");

  async function cargarAvisos() {
    estadoAvisos.textContent = "Cargando avisos…";
    const { estado: codigo, datos } = await api.obtener(`${curatoria.RUTA}/avisos`);
    if (codigo === 401 || codigo === 403) {
      // La cola ya muestra el aviso de sesión o de acceso.
      seccionAvisos.hidden = true;
      return;
    }
    if (codigo !== 200) {
      listaAvisos.replaceChildren();
      const reintentar = document.createElement("button");
      reintentar.type = "button";
      reintentar.className = "boton-secundario";
      reintentar.textContent = "Reintentar";
      reintentar.addEventListener("click", cargarAvisos);
      const error = document.createElement("span");
      error.className = "error-campo";
      error.textContent = datos.mensaje || "No pudimos cargar los avisos.";
      estadoAvisos.replaceChildren(error, reintentar);
      return;
    }
    expediente.pintarAvisos(seccionAvisos, listaAvisos, datos.avisos, (aviso, texto) => {
      const nombre = document.createElement("strong");
      nombre.textContent = aviso.expediente.nombre;
      const ir = curatoria.enlaceBoton(
        "Revisar expediente",
        `curatoria-expediente.html?ref=${encodeURIComponent(aviso.expediente.ref)}`,
        true
      );
      ir.setAttribute("aria-label", `Revisar el expediente de ${aviso.expediente.nombre}`);
      return [nombre, texto, ir];
    });
    // La sección queda visible también sin avisos, para decir que no hay.
    seccionAvisos.classList.remove("oculto");
    const cuantos = datos.avisos.length;
    estadoAvisos.textContent =
      cuantos === 0
        ? "No hay documentos por vencer."
        : cuantos === 1
          ? "1 documento está por vencer."
          : `${cuantos} documentos están por vencer.`;
  }

  leerDireccion();
  pintarFiltros();
  cargar();
  cargarAvisos();
})();
