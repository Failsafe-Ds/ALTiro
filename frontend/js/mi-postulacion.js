// Asistente de postulación documental del maestro (HU-11, RF-04; CA-11.1, CA-11.2;
// RNF-13 a RNF-17, RNF-20; NTI-11).
// - Cada paso se guarda en el servidor al completarlo (RNF-20, CA-11.1): al
//   volver a entrar, el asistente continúa en el primer documento que falta
//   según GET /api/maestros/expediente. En el navegador no se guarda nada:
//   ni fotos ni fechas de documentos (minimización, ADR-002).
// - Pasos: (a) oficios; (b) un paso por documento (cédula, antecedentes y una
//   licencia por cada oficio que la necesite, según lo que informa el
//   servidor); (c) resumen con el estado en lenguaje del oficio.
// - Si falla la conexión al enviar, la foto sigue en memoria y se puede
//   reintentar sin tomarla de nuevo.
// - "Subir de nuevo" desde mis-documentos.html llega como
//   ?subir=<tipo>[&oficio=<código>] y se acepta solo si coincide con un
//   documento o faltante informado por el servidor.
"use strict";

(() => {
  const RUTA_OFICIOS = "/api/maestros/expediente/oficios";
  const RUTA_DOCUMENTOS = "/api/maestros/expediente/documentos";
  const EDITABLES_OFICIOS = ["en_revision", "observado"];

  // Textos por documento (RNF-17: sin siglas sueltas ni jerga).
  const CONSEJO_FOTO = "Pon el documento sobre una mesa, con buena luz, y que se lean todas las letras.";
  const TEXTOS = {
    cedula_identidad: {
      ayuda: "Necesitamos una foto de cada lado de tu cédula.",
      fotos: [
        { campo: "archivo", titulo: "Foto del frente de tu cédula", falta: "Toma o elige la foto del frente de tu cédula." },
        {
          campo: "archivo_reverso",
          titulo: "Foto de la parte de atrás de tu cédula",
          falta: "Toma o elige la foto de la parte de atrás de tu cédula.",
        },
      ],
    },
    certificado_antecedentes: {
      ayuda: "Necesitamos una foto de tu certificado de antecedentes.",
      fotos: [{ campo: "archivo", titulo: "Foto del certificado", falta: "Toma o elige la foto del certificado." }],
    },
    licencia_sec: {
      ayuda: `Este oficio necesita la ${expediente.TEXTO_SEC}. Necesitamos una foto de tu licencia.`,
      fotos: [{ campo: "archivo", titulo: "Foto de la licencia", falta: "Toma o elige la foto de tu licencia." }],
    },
  };

  const MENSAJE_SIN_CONEXION_FOTO =
    "No se pudo enviar. Revisa tu señal y toca «Reintentar». Tus fotos y fechas siguen aquí.";
  const MENSAJE_PESADA =
    "Las fotos son muy pesadas para enviarlas. Tómalas de nuevo o elige otras de la galería y vuelve a enviar.";

  const cargando = document.getElementById("cargando");
  const avisoPagina = document.getElementById("aviso-pagina");
  const formOficios = document.getElementById("form-oficios");
  const formDocumento = document.getElementById("form-documento");
  const resumen = document.getElementById("resumen");
  const botonEnviar = document.getElementById("enviar-documento");

  let datos = null; // expediente según el servidor
  let catalogo = null; // oficios del catálogo
  let pasoDocumento = null; // { tipo, oficio, documento, reemplazo }
  let selectores = [];

  // --- Utilidades ---

  function mostrarSolo(elemento) {
    for (const seccion of [formOficios, formDocumento, resumen]) {
      seccion.classList.toggle("oculto", seccion !== elemento);
    }
    cargando.classList.add("oculto");
  }

  function enfocarTitulo(elemento) {
    const titulo = elemento.querySelector("legend, h2");
    if (titulo) {
      titulo.focus();
    }
    window.scrollTo(0, 0);
  }

  function avisoDe(form) {
    return form.querySelector(".aviso");
  }

  // Hallazgo UX E-4: si había fotos elegidas en el paso abierto, se avisa que
  // habrá que tomarlas de nuevo (no se guardan en el teléfono, ADR-002).
  function sesionTerminada() {
    const habiaFotos = !formDocumento.classList.contains("oculto") && selectores.some((s) => Boolean(s.blob()));
    liberarFotos();
    mostrarSolo(null);
    expediente.avisarSesionTerminada(
      avisoPagina,
      "postulacion",
      "Los pasos que ya enviaste están guardados." +
        (habiaFotos ? " Las fotos de este paso tendrás que tomarlas de nuevo." : "")
    );
  }

  // Hallazgo UX E-5: mientras se envía, ningún botón del paso responde
  // (fotos, "Volver", "Seguir sin cambiarlo", casillas), para no cambiar de
  // paso ni de foto a mitad del envío.
  function bloquearPaso(form, bloquear) {
    for (const control of form.querySelectorAll("button, input")) {
      if (bloquear) {
        control.dataset.bloqueado = control.disabled ? "antes" : "si";
        control.disabled = true;
      } else if (control.dataset.bloqueado) {
        control.disabled = control.dataset.bloqueado === "antes";
        delete control.dataset.bloqueado;
      }
    }
  }

  function oficiosEditables() {
    return EDITABLES_OFICIOS.includes(datos.estado);
  }

  function puedeSubir() {
    return datos.estado !== "rechazado";
  }

  // Número de paso: 1 = oficios; luego un paso por documento.
  function textoProgreso(indiceDocumento) {
    const total = 1 + expediente.requisitos(datos).length;
    return `Paso ${indiceDocumento + 2} de ${total}`;
  }

  // --- Carga inicial ---

  async function cargar() {
    expediente.limpiarAviso(avisoPagina);
    cargando.classList.remove("oculto");
    const [respuesta, respuestaOficios] = await Promise.all([api.obtener(expediente.RUTA), api.obtener("/api/oficios")]);
    cargando.classList.add("oculto");
    if (respuesta.estado === 401) {
      sesionTerminada();
      return;
    }
    if (respuesta.estado === 403) {
      expediente.avisarNoMaestro(avisoPagina);
      return;
    }
    if (respuesta.estado !== 200 || respuestaOficios.estado !== 200) {
      const mensaje = (respuesta.estado !== 200 ? respuesta : respuestaOficios).datos.mensaje;
      expediente.avisarErrorCarga(avisoPagina, mensaje, cargar);
      return;
    }
    datos = respuesta.datos.expediente;
    catalogo = respuestaOficios.datos.oficios;
    // CA-11.1: si ya había pasos guardados, se dice que se conservaron.
    const retomar = datos.oficios.length > 0 ? "Tus pasos anteriores están guardados. Sigue desde aquí." : null;
    decidir(pedidoDeLaDireccion(), null, retomar);
  }

  // ?subir=<tipo>[&oficio=<código>]: solo se acepta un requisito que el servidor informó.
  function pedidoDeLaDireccion() {
    const parametros = new URLSearchParams(location.search);
    const tipo = parametros.get("subir");
    if (!tipo) {
      return null;
    }
    history.replaceState(null, "", location.pathname);
    const oficio = parametros.get("oficio");
    return (
      expediente
        .requisitos(datos)
        .find((r) => r.tipo === tipo && (r.oficio ? r.oficio.codigo === oficio : !oficio)) || null
    );
  }

  // Siguiente pantalla según el estado guardado en el servidor (RNF-20, CA-11.1).
  // avisoRetomar solo se muestra si se continúa en un documento pendiente.
  function decidir(pedido, avisoExito, avisoRetomar) {
    if (pedido && puedeSubir()) {
      mostrarDocumento(pedido, true);
      return;
    }
    if (datos.oficios.length === 0 && oficiosEditables()) {
      mostrarOficios(false);
      return;
    }
    const faltante = puedeSubir() ? primerFaltante() : null;
    if (faltante) {
      mostrarDocumento(faltante, false, avisoExito || avisoRetomar);
      return;
    }
    mostrarResumen(avisoExito);
  }

  function primerFaltante() {
    return expediente.requisitos(datos).find((r) => !r.documento) || null;
  }

  // --- Paso: oficios ---

  function mostrarOficios(desdeResumen) {
    const lista = document.getElementById("lista-oficios");
    const declarados = new Set(datos.oficios.map((o) => o.codigo));
    lista.replaceChildren();
    for (const oficio of catalogo) {
      const etiqueta = document.createElement("label");
      etiqueta.className = "casilla casilla-grande";
      const casilla = document.createElement("input");
      casilla.type = "checkbox";
      casilla.value = oficio.codigo;
      casilla.checked = declarados.has(oficio.codigo);
      const texto = document.createElement("span");
      texto.className = "casilla-texto";
      texto.append(oficio.nombre);
      if (oficio.regulado) {
        const nota = document.createElement("span");
        nota.className = "nota-licencia";
        nota.textContent = "Necesita licencia de la SEC";
        texto.append(nota);
      }
      etiqueta.append(casilla, texto);
      lista.append(etiqueta);
    }
    formulario.limpiarErrores(formOficios);
    formOficios.querySelector(".progreso").textContent = `Paso 1 de ${1 + expediente.requisitos(datos).length}`;
    document.getElementById("oficios-volver").classList.toggle("oculto", !desdeResumen);
    mostrarSolo(formOficios);
    enfocarTitulo(formOficios);
  }

  formulario.prepararBoton(formOficios);
  formOficios.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(formOficios);
    const elegidos = Array.from(formOficios.querySelectorAll('input[type="checkbox"]:checked'), (c) => c.value);
    const primera = formOficios.querySelector('input[type="checkbox"]');
    if (elegidos.length === 0) {
      mostrarErrorOficios("Marca al menos un oficio para continuar.");
      if (primera) {
        primera.focus();
      }
      return;
    }
    bloquearPaso(formOficios, true);
    formulario.ocupado(formOficios, true);
    const { estado, datos: respuesta } = await api.enviar(RUTA_OFICIOS, { oficios: elegidos });
    formulario.ocupado(formOficios, false);
    bloquearPaso(formOficios, false);
    if (estado === 200) {
      datos = respuesta.expediente;
      decidir(null, "Guardamos tus oficios.");
      return;
    }
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 409) {
      // El expediente cambió de estado: ya no se pueden cambiar los oficios.
      await recargarYResumir(respuesta.mensaje);
      return;
    }
    if (respuesta.errores && respuesta.errores.oficios) {
      mostrarErrorOficios(respuesta.errores.oficios, respuesta.mensaje);
      if (primera) {
        primera.focus();
      }
      return;
    }
    formulario.avisar(formOficios, respuesta.mensaje, "error");
  });

  function mostrarErrorOficios(texto, mensaje) {
    document.getElementById("error-oficios").textContent = texto;
    formulario.avisar(formOficios, mensaje || "Revisa tus oficios.", "error");
  }

  document.getElementById("oficios-volver").addEventListener("click", () => mostrarResumen());

  // --- Paso: documento ---

  function liberarFotos() {
    for (const selector of selectores) {
      selector.quitar();
    }
    selectores = [];
  }

  function mostrarDocumento(requisito, reemplazo, avisoExito) {
    liberarFotos();
    pasoDocumento = Object.assign({}, requisito, { reemplazo });
    const textos = TEXTOS[requisito.tipo];
    const indice = expediente.requisitos(datos).findIndex(
      (r) => expediente.clave(r.tipo, r.oficio) === expediente.clave(requisito.tipo, requisito.oficio)
    );
    formulario.limpiarErrores(formDocumento);
    formDocumento.reset();
    formDocumento.querySelector(".progreso").textContent = reemplazo ? "Subir de nuevo" : textoProgreso(indice);
    document.getElementById("titulo-documento").textContent = expediente.nombreDocumento(requisito.tipo, requisito.oficio);
    document.getElementById("ayuda-documento").textContent = `${textos.ayuda} ${CONSEJO_FOTO}`;
    document.getElementById("progreso-envio").textContent = "";

    // Documento ya entregado: se muestra su estado y se puede seguir sin cambiarlo.
    const entregado = document.getElementById("documento-entregado");
    const documento = requisito.documento;
    entregado.classList.toggle("oculto", !documento);
    if (documento) {
      entregado.replaceChildren(
        "Ya enviaste este documento. Estado: ",
        expediente.etiquetaEstado(documento.estado, expediente.ESTADOS_DOCUMENTO),
        ". Si quieres cambiarlo, envía las fotos de nuevo."
      );
    }
    document.getElementById("documento-seguir").classList.toggle("oculto", !documento || reemplazo);
    document.getElementById("documento-volver").textContent = reemplazo ? "Volver al resumen" : "Volver";
    botonEnviar.textContent = documento ? "Enviar de nuevo" : "Enviar documento";
    botonEnviar.dataset.texto = botonEnviar.textContent;

    const contenedor = document.getElementById("fotos");
    selectores = textos.fotos.map((opciones) =>
      Object.assign(foto.crearSelector(contenedor, Object.assign({ ayuda: "Toca un botón para tomar o elegir la foto." }, opciones)), {
        falta: opciones.falta,
      })
    );
    mostrarSolo(formDocumento);
    if (avisoExito) {
      formulario.avisar(formDocumento, avisoExito, "exito");
    }
    enfocarTitulo(formDocumento);
  }

  function siguienteDespuesDe(requisito) {
    const lista = expediente.requisitos(datos);
    const i = lista.findIndex(
      (r) => expediente.clave(r.tipo, r.oficio) === expediente.clave(requisito.tipo, requisito.oficio)
    );
    return lista.slice(i + 1).find((r) => !r.documento) || null;
  }

  document.getElementById("documento-seguir").addEventListener("click", () => {
    const siguiente = siguienteDespuesDe(pasoDocumento);
    liberarFotos();
    if (siguiente) {
      mostrarDocumento(siguiente, false);
    } else {
      mostrarResumen();
    }
  });

  document.getElementById("documento-volver").addEventListener("click", () => {
    const actual = pasoDocumento;
    liberarFotos();
    if (actual.reemplazo) {
      mostrarResumen();
      return;
    }
    const lista = expediente.requisitos(datos);
    const i = lista.findIndex(
      (r) => expediente.clave(r.tipo, r.oficio) === expediente.clave(actual.tipo, actual.oficio)
    );
    if (i > 0) {
      mostrarDocumento(lista[i - 1], false);
    } else if (oficiosEditables()) {
      mostrarOficios(false);
    } else {
      mostrarResumen();
    }
  });

  // Al corregir una fecha se quita su aviso de error; si ya no queda ningún
  // error en el paso, también el aviso general.
  formDocumento.addEventListener("input", (evento) => {
    const campo = evento.target;
    if (!campo.name || campo.getAttribute("aria-invalid") !== "true") {
      return;
    }
    campo.removeAttribute("aria-invalid");
    const error = document.getElementById(`error-${campo.name}`);
    if (error) {
      error.textContent = "";
    }
    limpiarAvisoSiNoHayErrores();
  });
  formDocumento.addEventListener("foto-lista", limpiarAvisoSiNoHayErrores);

  function limpiarAvisoSiNoHayErrores() {
    const aviso = avisoDe(formDocumento);
    if (aviso.classList.contains("aviso-error") && !formDocumento.querySelector(".error-campo:not(:empty)")) {
      expediente.limpiarAviso(aviso);
    }
  }

  function textoEnvio(fraccion) {
    const varias = selectores.length > 1;
    if (fraccion >= 1) {
      return varias ? "Revisando las fotos…" : "Revisando la foto…";
    }
    return `${varias ? "Enviando fotos…" : "Enviando foto…"} ${Math.floor(fraccion * 10) * 10} %`;
  }

  formDocumento.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(formDocumento);
    const progresoEnvio = document.getElementById("progreso-envio");
    progresoEnvio.textContent = "";

    // Revisión mínima para no gastar datos enviando algo incompleto; el
    // servidor valida todo de nuevo (fechas, fotos y reglas del documento).
    const errores = {};
    for (const selector of selectores) {
      if (!(await selector.lista())) {
        errores[selector.campo] = selector.falta;
      }
    }
    const emision = formDocumento.fecha_emision.value;
    if (!emision) {
      errores.fecha_emision = "Escribe la fecha de emisión del documento.";
    }
    if (Object.keys(errores).length) {
      const campo = formulario.mostrarErrores(formDocumento, {
        mensaje: "Faltan datos para enviar este documento.",
        errores,
      });
      if (campo) {
        campo.focus();
      }
      return;
    }

    const envio = new FormData();
    envio.append("tipo", pasoDocumento.tipo);
    if (pasoDocumento.oficio) {
      envio.append("oficio", pasoDocumento.oficio.codigo);
    }
    envio.append("fecha_emision", emision);
    if (formDocumento.fecha_vencimiento.value) {
      envio.append("fecha_vencimiento", formDocumento.fecha_vencimiento.value);
    }
    for (const selector of selectores) {
      envio.append(selector.campo, selector.blob(), `${selector.campo}.jpg`);
    }

    bloquearPaso(formDocumento, true);
    formulario.ocupado(formDocumento, true);
    progresoEnvio.textContent = textoEnvio(0);
    let ultimo = "";
    const { estado, datos: respuesta } = await api.enviarArchivo(RUTA_DOCUMENTOS, envio, (fraccion) => {
      const texto = textoEnvio(fraccion);
      if (texto !== ultimo) {
        ultimo = texto;
        progresoEnvio.textContent = texto;
      }
    });
    formulario.ocupado(formDocumento, false);
    bloquearPaso(formDocumento, false);
    progresoEnvio.textContent = "";

    if (estado === 201) {
      const nombre = expediente.nombreDocumento(pasoDocumento.tipo, pasoDocumento.oficio);
      const reemplazo = pasoDocumento.reemplazo;
      liberarFotos();
      datos = respuesta.expediente;
      const exito = `Recibimos tu ${nombre.charAt(0).toLowerCase()}${nombre.slice(1)}.`;
      if (reemplazo) {
        mostrarResumen(exito);
      } else {
        decidir(null, exito);
      }
      return;
    }
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 409) {
      await recargarYResumir(respuesta.mensaje);
      return;
    }
    if (estado === 0) {
      // La foto sigue en memoria: se reintenta con el mismo botón.
      botonEnviar.textContent = "Reintentar";
      formulario.avisar(formDocumento, MENSAJE_SIN_CONEXION_FOTO, "error");
      return;
    }
    if (estado === 413) {
      formulario.avisar(formDocumento, MENSAJE_PESADA, "error");
      return;
    }
    const campo = formulario.mostrarErrores(formDocumento, respuesta);
    if (campo) {
      campo.focus();
    } else if (estado >= 500) {
      botonEnviar.textContent = "Reintentar";
    }
  });

  async function recargarYResumir(mensaje) {
    liberarFotos();
    const { estado, datos: respuesta } = await api.obtener(expediente.RUTA);
    if (estado === 200) {
      datos = respuesta.expediente;
    }
    mostrarResumen();
    const aviso = document.getElementById("aviso-resumen");
    aviso.className = "aviso aviso-error";
    aviso.textContent = mensaje;
    aviso.focus();
  }

  // --- Resumen (HU-17; CA-17.2) ---

  const RESUMEN = {
    en_revision: {
      titulo: "Tu postulación está en revisión",
      texto: "Ya recibimos tus documentos. Los vamos a revisar y te contaremos el resultado aquí. Puedes volver cuando quieras para ver cómo va.",
    },
    observado: {
      titulo: "Te pedimos corregir algo",
      texto: "Lee el motivo, corrige lo que te pedimos y vuelve a enviar el documento.",
    },
    aprobado: { titulo: "Tu postulación fue aprobada", texto: "Tus documentos fueron revisados y aprobados." },
    rechazado: { titulo: "Tu postulación no fue aprobada", texto: "Lee el motivo más abajo." },
    suspendido: {
      titulo: "Tu cuenta de maestro está suspendida",
      texto: "Lee el motivo más abajo. Si te pedimos un documento nuevo, puedes enviarlo desde aquí.",
    },
  };
  // Estados en que el motivo que escribió curatoría se muestra al maestro.
  const CON_MOTIVO = ["observado", "rechazado", "suspendido"];

  function mostrarResumen(avisoExito) {
    liberarFotos();
    const textos = RESUMEN[datos.estado] || RESUMEN.en_revision;
    const faltan = puedeSubir() ? expediente.requisitos(datos).filter((r) => !r.documento) : [];
    const titulo = document.getElementById("titulo-resumen");
    titulo.textContent =
      datos.estado === "en_revision" && faltan.length ? "Tu postulación está incompleta" : textos.titulo;
    document.getElementById("estado-expediente").replaceChildren(
      expediente.etiquetaEstado(datos.estado, expediente.ESTADOS_EXPEDIENTE)
    );
    document.getElementById("texto-resumen").textContent =
      datos.estado === "en_revision" && faltan.length
        ? "Para revisar tu postulación necesitamos todos tus documentos."
        : textos.texto;

    // RF-35: avisos de vencimiento con el texto del servidor.
    expediente.pintarAvisos(document.getElementById("avisos"), document.getElementById("lista-avisos"), datos.avisos);

    const motivo = document.getElementById("motivo-expediente");
    const conMotivo = CON_MOTIVO.includes(datos.estado) && Boolean(datos.motivo);
    motivo.classList.toggle("oculto", !conMotivo);
    motivo.textContent = conMotivo ? `Motivo: ${datos.motivo}` : "";

    document.getElementById("bloque-faltan").classList.toggle("oculto", faltan.length === 0);
    document.getElementById("lista-faltan").replaceChildren(
      ...faltan.map((r) => {
        const item = document.createElement("li");
        item.textContent = expediente.nombreDocumento(r.tipo, r.oficio);
        return item;
      })
    );

    const lista = document.getElementById("lista-resumen");
    lista.replaceChildren();
    for (const requisito of expediente.requisitos(datos).filter((r) => r.documento)) {
      const item = document.createElement("li");
      item.className = "documento-resumen";
      const nombre = document.createElement("span");
      nombre.className = "documento-nombre";
      nombre.textContent = expediente.nombreDocumento(requisito.tipo, requisito.oficio);
      item.append(nombre, expediente.etiquetaEstado(requisito.documento.estado, expediente.ESTADOS_DOCUMENTO));
      if (requisito.documento.estado === "observado" && puedeSubir()) {
        const boton = document.createElement("button");
        boton.type = "button";
        boton.className = "boton-secundario";
        boton.textContent = "Subir de nuevo";
        boton.addEventListener("click", () => mostrarDocumento(requisito, true));
        item.append(boton);
      }
      lista.append(item);
    }
    document.getElementById("sin-documentos").classList.toggle("oculto", lista.children.length > 0);
    document.getElementById("cambiar-oficios").classList.toggle("oculto", !oficiosEditables());

    const aviso = document.getElementById("aviso-resumen");
    expediente.limpiarAviso(aviso);
    mostrarSolo(resumen);
    if (avisoExito) {
      aviso.className = "aviso aviso-exito";
      aviso.textContent = avisoExito;
    }
    titulo.focus();
    window.scrollTo(0, 0);
  }

  document.getElementById("continuar").addEventListener("click", () => decidir(null));
  document.getElementById("cambiar-oficios").addEventListener("click", () => mostrarOficios(true));

  // Al salir de la página se sueltan las fotos que no se enviaron.
  window.addEventListener("pagehide", liberarFotos);

  cargar();
})();
