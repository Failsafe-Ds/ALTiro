// Mis documentos: estado y vigencia de cada documento entregado (HU-17, RF-08;
// CA-17.1, CA-17.2; RNF-16, RNF-17).
// - Todo viene de GET /api/maestros/expediente: la página no calcula vigencias
//   ni estados.
// - "Ver foto" pide un enlace temporal (GET /api/documentos/<ref>/enlace, 10
//   minutos, RNF-06) y muestra la imagen dentro de la página. Si el enlace
//   caducó, se pide otro.
// - "Subir de nuevo" lleva al asistente (mi-postulacion.html?subir=…).
"use strict";

(() => {
  // Margen para no usar un enlace a punto de caducar.
  const MARGEN_MS = 20 * 1000;

  const cargando = document.getElementById("cargando");
  const avisoPagina = document.getElementById("aviso-pagina");
  const contenido = document.getElementById("contenido");
  const visor = document.getElementById("visor");
  const tituloVisor = document.getElementById("titulo-visor");
  const estadoVisor = document.getElementById("estado-visor");
  const imagenVisor = document.getElementById("imagen-visor");
  const otraCara = document.getElementById("visor-otra-cara");

  // Enlaces ya pedidos: "ref:cara" => { url, caduca }. Solo en memoria.
  const enlaces = new Map();
  let fotoAbierta = null; // { documento, nombre, cara, reintentado }
  let origenFoco = null;

  function sesionTerminada() {
    cerrarVisor();
    contenido.classList.add("oculto");
    expediente.avisarSesionTerminada(avisoPagina, "documentos", "");
  }

  // --- Lista ---

  function textoVigencia(documento) {
    if (!documento.fecha_vencimiento) {
      return "No vence";
    }
    let texto = `Vence el ${expediente.formatearFecha(documento.fecha_vencimiento)}`;
    // Punto de extensión (CA-17.1): los días restantes los calcula el servidor
    // (incremento 5 del S2). Si la respuesta aún no los trae, se muestra solo la fecha.
    if (typeof documento.dias_restantes === "number") {
      texto += documento.dias_restantes === 1 ? " (queda 1 día)" : ` (quedan ${documento.dias_restantes} días)`;
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
      // CA-17.2: el motivo escrito de la observación. La respuesta actual de la
      // API no lo incluye (pendiente de backend); hasta entonces se indica qué hacer.
      item.append(parrafo("motivo", "Revisamos este documento y necesitamos que lo envíes de nuevo."));
    }
    const acciones = document.createElement("div");
    acciones.className = "acciones";
    const ver = document.createElement("button");
    ver.type = "button";
    ver.textContent = documento.tipo === "cedula_identidad" ? "Ver fotos" : "Ver foto";
    ver.setAttribute("aria-label", `${ver.textContent}: ${nombre}`);
    ver.addEventListener("click", () => abrirVisor(documento, nombre, "anverso", ver));
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

  // --- Visor ---

  async function pedirEnlace(ref, cara) {
    const clave = `${ref}:${cara}`;
    const guardado = enlaces.get(clave);
    if (guardado && Date.now() < guardado.caduca - MARGEN_MS) {
      return { estado: 200, url: guardado.url };
    }
    enlaces.delete(clave);
    const { estado, datos } = await api.obtener(`/api/documentos/${encodeURIComponent(ref)}/enlace?cara=${cara}`);
    if (estado !== 200) {
      return { estado, mensaje: datos.mensaje };
    }
    const caduca = Date.parse(datos.caduca_en);
    enlaces.set(clave, { url: datos.url, caduca: Number.isNaN(caduca) ? 0 : caduca });
    return { estado, url: datos.url };
  }

  function textoCara(cara) {
    return cara === "anverso" ? "frente" : "parte de atrás";
  }

  async function mostrarFoto() {
    const { documento, nombre, cara } = fotoAbierta;
    const esCedula = documento.tipo === "cedula_identidad";
    tituloVisor.textContent = esCedula ? `${nombre}: ${textoCara(cara)}` : nombre;
    imagenVisor.hidden = true;
    imagenVisor.removeAttribute("src");
    estadoVisor.textContent = "Cargando la foto…";
    otraCara.classList.toggle("oculto", !esCedula);
    otraCara.textContent = cara === "anverso" ? "Ver la parte de atrás" : "Ver el frente";

    const resultado = await pedirEnlace(documento.ref, cara);
    if (!fotoAbierta || fotoAbierta.cara !== cara || fotoAbierta.documento !== documento) {
      return; // Se cerró o se cambió de foto mientras cargaba.
    }
    if (resultado.estado === 401) {
      sesionTerminada();
      return;
    }
    if (resultado.estado !== 200) {
      estadoVisor.textContent =
        resultado.estado === 404
          ? "No encontramos esta foto. Cierra y recarga la página para ver tus documentos actualizados."
          : resultado.mensaje;
      return;
    }
    imagenVisor.alt = `Foto de ${nombre}${esCedula ? `, ${textoCara(cara)}` : ""}`;
    imagenVisor.src = resultado.url;
  }

  imagenVisor.addEventListener("load", () => {
    estadoVisor.textContent = "";
    imagenVisor.hidden = false;
  });

  // Enlace caducado o conexión cortada: se pide un enlace nuevo una sola vez.
  imagenVisor.addEventListener("error", () => {
    if (!fotoAbierta || !imagenVisor.getAttribute("src")) {
      return;
    }
    enlaces.delete(`${fotoAbierta.documento.ref}:${fotoAbierta.cara}`);
    if (!fotoAbierta.reintentado) {
      fotoAbierta.reintentado = true;
      mostrarFoto();
      return;
    }
    imagenVisor.removeAttribute("src");
    estadoVisor.textContent =
      "No pudimos mostrar la foto. Revisa tu señal, cierra esta ventana y toca «Ver foto» de nuevo.";
  });

  function abrirVisor(documento, nombre, cara, boton) {
    origenFoco = boton;
    fotoAbierta = { documento, nombre, cara, reintentado: false };
    if (typeof visor.showModal === "function") {
      if (!visor.open) {
        visor.showModal();
      }
    } else {
      visor.setAttribute("open", "");
    }
    mostrarFoto();
    document.getElementById("visor-cerrar").focus();
  }

  function cerrarVisor() {
    fotoAbierta = null;
    // Se suelta la imagen de la memoria.
    imagenVisor.removeAttribute("src");
    imagenVisor.hidden = true;
    if (visor.open) {
      if (typeof visor.close === "function") {
        visor.close();
      } else {
        visor.removeAttribute("open");
      }
    }
    if (origenFoco && document.contains(origenFoco)) {
      origenFoco.focus();
    }
    origenFoco = null;
  }

  otraCara.addEventListener("click", () => {
    if (!fotoAbierta) {
      return;
    }
    fotoAbierta.cara = fotoAbierta.cara === "anverso" ? "reverso" : "anverso";
    fotoAbierta.reintentado = false;
    mostrarFoto();
  });
  document.getElementById("visor-cerrar").addEventListener("click", cerrarVisor);
  // Tecla Escape: el navegador cierra el diálogo; se limpia igual.
  visor.addEventListener("close", () => {
    if (fotoAbierta) {
      cerrarVisor();
    }
  });

  cargar();
})();
