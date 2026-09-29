// Mis documentos: estado y vigencia de cada documento entregado (HU-17, RF-08;
// CA-17.1, CA-17.2; RNF-16, RNF-17).
// - Todo viene de GET /api/maestros/expediente: la página no calcula vigencias
//   ni estados.
// - "Ver foto" pide un enlace temporal (GET /api/documentos/<ref>/enlace, 10
//   minutos, RNF-06) y muestra la imagen dentro de la página con el visor
//   compartido (js/visor.js). Si el enlace caducó, se pide otro.
// - Un documento observado muestra el motivo que escribió curatoría (CA-17.2).
// - "Subir de nuevo" lleva al asistente (mi-postulacion.html?subir=…).
"use strict";

(() => {
  const cargando = document.getElementById("cargando");
  const avisoPagina = document.getElementById("aviso-pagina");
  const contenido = document.getElementById("contenido");

  function sesionTerminada() {
    visor.cerrar();
    contenido.classList.add("oculto");
    expediente.avisarSesionTerminada(avisoPagina, "documentos", "");
  }

  // Visor compartido: enlace de 10 minutos pedido como dueño del documento.
  const visor = visorFotos.crear({
    rutaEnlace: (ref, cara) => `/api/documentos/${encodeURIComponent(ref)}/enlace?cara=${cara}`,
    alSesionTerminada: sesionTerminada,
  });

  // --- Lista ---

  function textoVigencia(documento) {
    if (!documento.fecha_vencimiento) {
      return "No vence";
    }
    let texto = `Vence el ${expediente.formatearFecha(documento.fecha_vencimiento)}`;
    // Punto de extensión (CA-17.1): los días restantes los calcula el servidor
    // (incremento 5 del S2). Si la respuesta aún no los trae, se muestra solo la fecha.
    if (documento.vigente === false || (typeof documento.dias_restantes === "number" && documento.dias_restantes <= 0)) {
      texto += " (ya venció)";
    } else if (typeof documento.dias_restantes === "number") {
      texto +=documento.dias_restantes === 1 ? " (queda 1 día)" : ` (quedan ${documento.dias_restantes} días)`;
    }
    return texto;
  }

  function parrafo(clase, ...hijos) {
    const p = document.createElement("p");
    if (clase) {
      p.className = clase;
    }
    p.append(...hijos);
    return p;
  }

  function enlaceSubir(documento) {
    const parametros = new URLSearchParams({ subir: documento.tipo });
    if (documento.oficio) {
      parametros.set("oficio", documento.oficio.codigo);
    }
    const enlace = document.createElement("a");
    enlace.className = "boton boton-secundario";
    enlace.href = `mi-postulacion.html?${parametros}`;
    enlace.textContent = "Subir de nuevo";
    return enlace;
  }

  function tarjeta(documento, puedeSubir) {
    const nombre = expediente.nombreDocumento(documento.tipo, documento.oficio);
    const item = document.createElement("li");
    item.className = "tarjeta documento";
    const titulo = document.createElement("h2");
    titulo.textContent = nombre;
    item.append(
      titulo,
      parrafo("", "Estado: ", expediente.etiquetaEstado(documento.estado, expediente.ESTADOS_DOCUMENTO)),
      parrafo("", textoVigencia(documento)),
      parrafo("ayuda", `Emitido el ${expediente.formatearFecha(documento.fecha_emision)}`)
    );
    if (documento.estado === "observado") {
      // CA-17.2: el motivo escrito por curatoría, tal como lo escribió (texto, nunca HTML).
      if (documento.motivo_observacion) {
        const motivo = parrafo("motivo");
        const etiqueta = document.createElement("strong");
        etiqueta.textContent = "Qué debes corregir: ";
        motivo.append(etiqueta, documento.motivo_observacion);
        item.append(motivo);
      } else {
        item.append(parrafo("motivo", "Revisamos este documento y necesitamos que lo envíes de nuevo."));
      }
      if (puedeSubir) {
        item.append(parrafo("ayuda", "Corrige lo indicado y toca «Subir de nuevo»."));
      }
    }
    const acciones = document.createElement("div");
    acciones.className = "acciones";
    const ver = document.createElement("button");
    ver.type = "button";
    ver.textContent = documento.tipo === "cedula_identidad" ? "Ver fotos" : "Ver foto";
    ver.setAttribute("aria-label", `${ver.textContent}: ${nombre}`);
    ver.addEventListener("click", () => visor.abrir(documento, nombre, "anverso", ver));
    acciones.append(ver);
    if (puedeSubir) {
      acciones.append(enlaceSubir(documento));
    }
    item.append(acciones);
    return item;
  }

  function pintar(datos) {
    document
      .getElementById("estado-expediente")
      .replaceChildren(expediente.etiquetaEstado(datos.estado, expediente.ESTADOS_EXPEDIENTE));
    const puedeSubir = datos.estado !== "rechazado";
    const lista = document.getElementById("lista-documentos");
    const requisitos = expediente.requisitos(datos);
    lista.replaceChildren(...requisitos.filter((r) => r.documento).map((r) => tarjeta(r.documento, puedeSubir)));
    document.getElementById("sin-documentos").classList.toggle("oculto", lista.children.length > 0);
    const faltan = puedeSubir ? requisitos.filter((r) => !r.documento) : [];
    document.getElementById("bloque-faltan").classList.toggle("oculto", faltan.length === 0);
    document.getElementById("lista-faltan").replaceChildren(
      ...faltan.map((r) => {
        const li = document.createElement("li");
        li.textContent = expediente.nombreDocumento(r.tipo, r.oficio);
        return li;
      })
    );
    contenido.classList.remove("oculto");
  }

  async function cargar() {
    expediente.limpiarAviso(avisoPagina);
    cargando.classList.remove("oculto");
    const { estado, datos } = await api.obtener(expediente.RUTA);
    cargando.classList.add("oculto");
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 403) {
      expediente.avisarNoMaestro(avisoPagina);
      return;
    }
    if (estado !== 200) {
      expediente.avisarErrorCarga(avisoPagina, datos.mensaje, cargar);
      return;
    }
    pintar(datos.expediente);
  }

  cargar();
})();
