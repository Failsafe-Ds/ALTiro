// Revisión de un expediente por curatoría (HU-19, HU-25, RF-32, RF-33;
// CA-17.2, CA-19.1 a CA-19.4; propuesta del S2, §3 a §5 y §9; ADR-010 E-1,
// ADR-011 E-1 y E-2, ADR-015, ADR-017 E-1 a E-3).
// - Detalle: GET /api/curatoria/expedientes/<ref> (nombre, RUT, oficios con
//   "habilitado", documentos actuales, faltantes y estados_siguientes).
// - Fotos: GET /api/curatoria/documentos/<ref>/enlace (10 minutos; también
//   documentos reemplazados, desde el historial) con el visor compartido.
// - Revisión de un documento en revisión: POST …/documentos/<ref>/revision.
//   Observar exige motivo (el maestro lo ve, CA-17.2); validar lo admite opcional.
// - Cambio de estado: POST …/expedientes/<ref>/estado con motivo obligatorio
//   (CA-19.1). Las opciones son las que el servidor informa en
//   estados_siguientes; la página no decide transiciones. Rechazar pide un paso
//   de confirmación en la página (es definitivo).
// - 409: se muestra el mensaje del servidor (RF-33 nombra lo que falta,
//   CA-19.2; o "el expediente cambió… recarga") y se conserva lo escrito.
// - 403 en el propio expediente (CA-19.4): mensaje del servidor, sin acciones.
// - Historial (CA-19.3): GET …/historial, de solo lectura.
"use strict";

(() => {
  const cargando = document.getElementById("cargando");
  const avisoPagina = document.getElementById("aviso-pagina");
  const avisoResultado = document.getElementById("aviso-resultado");
  const contenido = document.getElementById("contenido");
  const tituloPagina = document.getElementById("titulo-pagina");
  const formEstado = document.getElementById("form-estado");
  const avisoEstado = formEstado.querySelector(".aviso");
  const opcionesEstado = document.getElementById("opciones-estado");
  const motivoEstado = document.getElementById("motivo-estado");
  const guardarEstado = document.getElementById("guardar-estado");
  const confirmarRechazo = document.getElementById("confirmar-rechazo");
  const estadoHistorial = document.getElementById("estado-historial");
  const listaHistorial = document.getElementById("lista-historial");

  const MOTIVO_FALTA = "Escribe el motivo. Es obligatorio y queda registrado.";
  const MOTIVO_OBSERVACION_FALTA = "Escribe qué debe corregir el maestro. Es obligatorio y el maestro lo verá.";
  const ELIGE_ESTADO = "Elige el nuevo estado del expediente.";

  // Opciones de cambio de estado: texto de la opción y del botón. Qué opciones
  // aparecen lo decide el servidor (estados_siguientes).
  function accion(destino, actual) {
    switch (destino) {
      case "aprobado":
        return actual === "suspendido"
          ? { opcion: "Reactivar (vuelve a «Aprobado»)", boton: "Reactivar el expediente" }
          : { opcion: "Aprobar", boton: "Aprobar el expediente" };
      case "observado":
        return { opcion: "Observar (pedir correcciones al maestro)", boton: "Observar el expediente" };
      case "en_revision":
        return { opcion: "Volver a revisión", boton: "Volver a revisión" };
      case "rechazado":
        return { opcion: "Rechazar (definitivo)", boton: "Rechazar el expediente…" };
      case "suspendido":
        return { opcion: "Suspender", boton: "Suspender el expediente" };
      default:
        return { opcion: "Otro estado", boton: "Guardar el cambio de estado" };
    }
  }

  const ref = new URLSearchParams(location.search).get("ref") || "";
  let detalle = null;
  let sinAcciones = false;
  let enviando = false;

  const visor = visorFotos.crear({
    rutaEnlace: (refDocumento, cara) =>
      `${curatoria.RUTA}/documentos/${encodeURIComponent(refDocumento)}/enlace?cara=${cara}`,
    alSesionTerminada: sesionTerminada,
  });

  // --- Utilidades de interfaz ---

  function elemento(etiqueta, clase, ...hijos) {
    const nodo = document.createElement(etiqueta);
    if (clase) {
      nodo.className = clase;
    }
    nodo.append(...hijos);
    return nodo;
  }

  // Hallazgo UX M-3: con la sesión terminada no queda a la vista el expediente
  // (nombre, RUT, motivos): se oculta y se vacía antes de avisar.
  function sesionTerminada() {
    visor.cerrar();
    contenido.hidden = true;
    for (const dato of contenido.querySelectorAll("[id^='dato-']")) {
      dato.textContent = "";
    }
    for (const lista of contenido.querySelectorAll("ul, ol")) {
      lista.replaceChildren();
    }
    tituloPagina.textContent = "Revisar expediente";
    document.title = "Revisar expediente — AlTiro";
    curatoria.limpiar(avisoResultado);
    curatoria.avisarSesionTerminada(avisoPagina);
  }

  function avisarExito(texto) {
    curatoria.avisar(avisoResultado, "exito", texto);
  }

  function botonRecargar() {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "boton-secundario";
    boton.textContent = "Recargar el expediente";
    boton.addEventListener("click", () => cargar({ conservarAvisos: false }));
    return boton;
  }

  // aria-invalid solo en el campo de texto; en el fieldset de opciones el
  // error queda enlazado con aria-describedby.
  function mostrarErrorCampo(campo, destino, texto) {
    if (campo.tagName !== "FIELDSET") {
      campo.setAttribute("aria-invalid", "true");
    }
    destino.textContent = texto;
  }

  function limpiarErrorCampo(campo, destino) {
    campo.removeAttribute("aria-invalid");
    destino.textContent = "";
  }

  // --- Datos del expediente ---

  function textoFaltante(faltante) {
    if (faltante.tipo === "cedula_identidad") {
      return "Cédula de identidad por ambos lados, validada";
    }
    if (faltante.tipo === "certificado_antecedentes") {
      return "Certificado de antecedentes, validado";
    }
    if (faltante.tipo === "licencia_sec") {
      return `Licencia SEC de ${faltante.oficio ? faltante.oficio.nombre : "un oficio regulado"}, validada y vigente`;
    }
    return "Un documento pendiente";
  }

  function etiquetaOficio(oficio) {
    if (oficio.habilitado) {
      const texto = oficio.regulado ? "Habilitado" : "Habilitado (no necesita licencia)";
      return expediente.etiquetaEstado("ok", { ok: { texto, icono: "✓", clase: "estado-aprobado" } });
    }
    return expediente.etiquetaEstado("falta", {
      falta: { texto: "Falta licencia vigente", icono: "⚠", clase: "estado-observado" },
    });
  }

  function pintarDatos(det) {
    tituloPagina.textContent = `Expediente de ${det.nombre}`;
    document.title = `Expediente de ${det.nombre} — AlTiro`;
    document.getElementById("dato-nombre").textContent = det.nombre;
    document.getElementById("dato-rut").textContent = expediente.formatearRut(det.rut);
    document
      .getElementById("dato-estado")
      .replaceChildren(expediente.etiquetaEstado(det.estado, curatoria.ESTADOS_EXPEDIENTE));
    const conMotivo = Boolean(det.motivo);
    document.getElementById("titulo-motivo").classList.toggle("oculto", !conMotivo);
    const motivo = document.getElementById("dato-motivo");
    motivo.classList.toggle("oculto", !conMotivo);
    motivo.textContent = conMotivo
      ? `${det.motivo}${det.estado_cambiado_en ? ` (${expediente.formatearFechaHora(det.estado_cambiado_en)})` : ""}`
      : "";
    document.getElementById("dato-creado").textContent = expediente.formatearFechaHora(det.creado_en);

    const oficios = document.getElementById("lista-oficios");
    oficios.replaceChildren(
      ...det.oficios.map((oficio) =>
        elemento("li", "linea-oficio", elemento("span", "documento-nombre", oficio.nombre), " ", etiquetaOficio(oficio))
      )
    );
    document.getElementById("sin-oficios").classList.toggle("oculto", det.oficios.length > 0);

    const faltantes = det.faltantes_para_aprobar;
    document.getElementById("sin-faltantes").classList.toggle("oculto", faltantes.length > 0);
    document.getElementById("bloque-faltantes").classList.toggle("oculto", faltantes.length === 0);
    document
      .getElementById("lista-faltantes")
      .replaceChildren(...faltantes.map((f) => elemento("li", "", textoFaltante(f))));
  }

  // --- Documentos ---

  function botonVer(documento, nombre, sufijo) {
    const ver = document.createElement("button");
    ver.type = "button";
    ver.className = "boton-secundario";
    ver.textContent = visorFotos.tieneReverso(documento) ? "Ver fotos" : "Ver foto";
    ver.setAttribute("aria-label", `${ver.textContent}: ${nombre}${sufijo || ""}`);
    ver.addEventListener("click", () => visor.abrir(documento, nombre + (sufijo || ""), "anverso", ver));
    return ver;
  }

  function formularioRevision(documento, nombre, indice, textoPrevio) {
    const id = `motivo-documento-${indice}`;
    const form = elemento("form", "revision");
    form.noValidate = true;
    const aviso = elemento("div", "aviso");
    aviso.setAttribute("role", "alert");
    aviso.tabIndex = -1;
    const etiqueta = elemento("label", "", "Motivo de la revisión");
    etiqueta.htmlFor = id;
    const ayuda = elemento(
      "span",
      "ayuda",
      "Obligatorio para observar: el maestro verá este texto; escríbelo simple, diciendo qué debe hacer el maestro. Opcional para validar: queda solo en el historial."
    );
    ayuda.id = `${id}-ayuda`;
    const texto = document.createElement("textarea");
    texto.id = id;
    texto.name = "motivo";
    texto.rows = 3;
    texto.maxLength = 1000;
    texto.dataset.documento = documento.ref;
    texto.value = textoPrevio || "";
    const error = elemento("span", "error-campo");
    error.id = `${id}-error`;
    texto.setAttribute("aria-describedby", `${ayuda.id} ${error.id}`);
    const campo = elemento("div", "campo", etiqueta, ayuda, texto, error);

    const validar = elemento("button", "", "Validar documento");
    validar.type = "button";
    validar.setAttribute("aria-label", `Validar documento: ${nombre}`);
    const observar = elemento("button", "boton-secundario", "Observar documento");
    observar.type = "button";
    observar.setAttribute("aria-label", `Observar documento: ${nombre}`);
    const acciones = elemento("div", "acciones acciones-dobles", validar, observar);

    form.append(elemento("h4", "", "Revisar este documento"), aviso, campo, acciones);
    const partes = { form, aviso, texto, error, botones: [validar, observar] };
    validar.addEventListener("click", () => revisarDocumento(documento, nombre, "validar", partes));
    observar.addEventListener("click", () => revisarDocumento(documento, nombre, "observar", partes));
    form.addEventListener("submit", (evento) => evento.preventDefault());
    return form;
  }

  function tarjetaDocumento(documento, indice, textosPrevios) {
    const nombre = expediente.nombreDocumento(documento.tipo, documento.oficio);
    const item = elemento("li", "tarjeta documento");
    item.dataset.ref = documento.ref;
    const titulo = elemento("h3", "", nombre);
    titulo.tabIndex = -1;
    item.append(
      titulo,
      elemento("p", "", "Estado: ", expediente.etiquetaEstado(documento.estado, curatoria.ESTADOS_DOCUMENTO)),
      // CA-17.1: "Vence el …. Quedan N días." o "Venció el …" con "Vencido" (servidor: vigente, dias_restantes).
      elemento("p", "", expediente.vigencia(documento)),
      elemento("p", "ayuda", `Emitido el ${expediente.formatearFecha(documento.fecha_emision)}`),
      elemento("p", "ayuda", `Recibido el ${expediente.formatearFechaHora(documento.cargado_en)}`)
    );
    if (documento.revisado_en) {
      item.append(elemento("p", "ayuda", `Revisado el ${expediente.formatearFechaHora(documento.revisado_en)}`));
    }
    if (documento.estado === "observado" && documento.motivo_observacion) {
      const motivo = elemento("p", "motivo");
      motivo.append(elemento("strong", "", "Observación enviada al maestro: "), documento.motivo_observacion);
      item.append(motivo);
    }
    item.append(elemento("div", "acciones", botonVer(documento, nombre)));
    if (documento.estado === "en_revision" && !sinAcciones) {
      item.append(formularioRevision(documento, nombre, indice, textosPrevios.get(documento.ref)));
    }
    return item;
  }

  function pintarDocumentos(det) {
    const lista = document.getElementById("lista-documentos");
    // Lo escrito en los motivos de otros documentos se conserva al repintar.
    const textosPrevios = new Map(
      Array.from(lista.querySelectorAll("textarea[data-documento]"), (t) => [t.dataset.documento, t.value])
    );
    lista.replaceChildren(...det.documentos.map((d, i) => tarjetaDocumento(d, i, textosPrevios)));
    document.getElementById("sin-documentos").classList.toggle("oculto", det.documentos.length > 0);
  }

  async function revisarDocumento(documento, nombre, resultado, partes) {
    if (enviando) {
      return;
    }
    partes.aviso.className = "aviso";
    partes.aviso.replaceChildren();
    limpiarErrorCampo(partes.texto, partes.error);
    const motivo = partes.texto.value.trim();
    if (resultado === "observar" && !motivo) {
      mostrarErrorCampo(partes.texto, partes.error, MOTIVO_OBSERVACION_FALTA);
      partes.texto.focus();
      return;
    }
    const cuerpo = { resultado, estado_actual: documento.estado };
    if (motivo) {
      cuerpo.motivo = motivo;
    }
    enviando = true;
    const boton = partes.botones[resultado === "validar" ? 0 : 1];
    const textoBoton = boton.textContent;
    boton.textContent = "Guardando…";
    partes.botones.forEach((b) => (b.disabled = true));
    const { estado, datos } = await api.enviar(
      `${curatoria.RUTA}/documentos/${encodeURIComponent(documento.ref)}/revision`,
      cuerpo
    );
    enviando = false;
    boton.textContent = textoBoton;
    partes.botones.forEach((b) => (b.disabled = false));

    if (estado === 200) {
      partes.texto.value = "";
      const lista = document.getElementById("lista-documentos");
      const orden = Array.from(lista.children, (li) => li.dataset.ref);
      pintar(datos.expediente);
      const texto =
        resultado === "validar"
          ? `Listo: validaste «${nombre}». Quedó registrado en el historial.`
          : `Listo: observaste «${nombre}». El maestro verá el motivo en «Mis documentos».`;
      enfocarTrasRevision(documento.ref, orden, texto);
      cargarHistorial();
      return;
    }
    manejarErrorAccion(estado, datos, {
      aviso: partes.aviso,
      campos: { motivo: [partes.texto, partes.error] },
    });
  }

  // Hallazgo UX O-2: tras validar u observar, la página no salta arriba.
  // El resultado queda junto al documento revisado y se anuncia (role=status);
  // el foco pasa al siguiente documento que espera revisión (primero los que
  // venían después, luego los anteriores) o, si no queda ninguno, al resultado.
  function enfocarTrasRevision(refRevisado, ordenPrevio, texto) {
    const lista = document.getElementById("lista-documentos");
    const tarjetas = Array.from(lista.children);
    const revisada = tarjetas.find((li) => li.dataset.ref === refRevisado);
    let nota = null;
    curatoria.limpiar(avisoResultado);
    if (revisada) {
      nota = elemento("p", "resultado-documento", texto);
      nota.setAttribute("role", "status");
      nota.tabIndex = -1;
      revisada.append(nota);
    } else {
      // El documento ya no está en la lista (no debería ocurrir): aviso general.
      avisarExito(texto);
    }
    const posicion = ordenPrevio.indexOf(refRevisado);
    const pendientes = tarjetas.filter((li) => li.querySelector("form.revision"));
    const indice = (li) => ordenPrevio.indexOf(li.dataset.ref);
    const siguiente =
      pendientes.find((li) => indice(li) > posicion) || pendientes.find((li) => indice(li) < posicion) || null;
    if (siguiente) {
      siguiente.querySelector("h3").focus();
    } else if (nota) {
      nota.focus();
    }
  }

  // --- Cambio de estado del expediente ---

  function pintarEstado(det) {
    const siguientes = sinAcciones ? [] : det.estados_siguientes;
    const sinTransiciones = document.getElementById("sin-transiciones");
    formEstado.classList.toggle("oculto", siguientes.length === 0);
    sinTransiciones.classList.toggle("oculto", siguientes.length > 0 || sinAcciones);
    if (det.estado === "rechazado") {
      sinTransiciones.textContent =
        "Este expediente fue rechazado. Es una decisión definitiva y no admite más cambios de estado.";
    } else {
      sinTransiciones.textContent = "Este expediente no admite cambios de estado.";
    }
    const elegido = formEstado.querySelector("input[name=estado_nuevo]:checked");
    const previo = elegido ? elegido.value : "";
    opcionesEstado.replaceChildren(
      ...siguientes.map((destino) => {
        const entrada = document.createElement("input");
        entrada.type = "radio";
        entrada.name = "estado_nuevo";
        entrada.value = destino;
        entrada.checked = destino === previo;
        entrada.addEventListener("change", actualizarBotonEstado);
        const etiqueta = elemento("label", "casilla casilla-grande", entrada, elemento("span", "", accion(destino, det.estado).opcion));
        return etiqueta;
      })
    );
    ocultarConfirmacion(false);
    actualizarBotonEstado();
  }

  function destinoElegido() {
    const elegido = formEstado.querySelector("input[name=estado_nuevo]:checked");
    return elegido ? elegido.value : "";
  }

  function actualizarBotonEstado() {
    const destino = destinoElegido();
    guardarEstado.textContent = destino ? accion(destino, detalle.estado).boton : "Guardar el cambio de estado";
    guardarEstado.classList.toggle("boton-peligro", destino === "rechazado");
    if (destino) {
      limpiarErrorCampo(opcionesEstado.closest("fieldset"), document.getElementById("error-estado_nuevo"));
    }
  }

  function limpiarFormEstado() {
    avisoEstado.className = "aviso";
    avisoEstado.replaceChildren();
    limpiarErrorCampo(motivoEstado, document.getElementById("error-motivo"));
    limpiarErrorCampo(opcionesEstado.closest("fieldset"), document.getElementById("error-estado_nuevo"));
  }

  function mostrarConfirmacion() {
    document.getElementById("confirmar-motivo").textContent = motivoEstado.value.trim();
    formEstado.hidden = true;
    confirmarRechazo.hidden = false;
    document.getElementById("titulo-confirmar").focus();
  }

  function ocultarConfirmacion(devolverFoco) {
    confirmarRechazo.hidden = true;
    formEstado.hidden = false;
    if (devolverFoco) {
      const rechazo = formEstado.querySelector("input[value=rechazado]");
      (rechazo || guardarEstado).focus();
    }
  }

  formEstado.addEventListener("submit", (evento) => {
    evento.preventDefault();
    if (enviando) {
      return;
    }
    limpiarFormEstado();
    const destino = destinoElegido();
    const motivo = motivoEstado.value.trim();
    let primero = null;
    if (!destino) {
      mostrarErrorCampo(opcionesEstado.closest("fieldset"), document.getElementById("error-estado_nuevo"), ELIGE_ESTADO);
      primero = opcionesEstado.querySelector("input");
    }
    if (!motivo) {
      mostrarErrorCampo(motivoEstado, document.getElementById("error-motivo"), MOTIVO_FALTA);
      primero = primero || motivoEstado;
    }
    if (primero) {
      primero.focus();
      return;
    }
    if (destino === "rechazado") {
      mostrarConfirmacion();
      return;
    }
    enviarEstado(destino, motivo);
  });

  document.getElementById("confirmar-no").addEventListener("click", () => ocultarConfirmacion(true));
  document.getElementById("confirmar-si").addEventListener("click", () => {
    enviarEstado("rechazado", motivoEstado.value.trim());
  });

  async function enviarEstado(destino, motivo) {
    if (enviando) {
      return;
    }
    enviando = true;
    const botones = [guardarEstado, document.getElementById("confirmar-si"), document.getElementById("confirmar-no")];
    const textos = botones.map((b) => b.textContent);
    botones.forEach((b) => (b.disabled = true));
    guardarEstado.textContent = "Guardando…";
    document.getElementById("confirmar-si").textContent = "Guardando…";
    const { estado, datos } = await api.enviar(`${curatoria.RUTA}/expedientes/${encodeURIComponent(ref)}/estado`, {
      estado_nuevo: destino,
      estado_actual: detalle.estado,
      motivo,
    });
    enviando = false;
    botones.forEach((b, i) => {
      b.disabled = false;
      b.textContent = textos[i];
    });

    if (estado === 200) {
      motivoEstado.value = "";
      for (const opcion of formEstado.querySelectorAll("input[name=estado_nuevo]")) {
        opcion.checked = false;
      }
      pintar(datos.expediente);
      const nuevo = curatoria.ESTADOS_EXPEDIENTE[datos.expediente.estado];
      avisarExito(
        `Listo: el expediente quedó «${nuevo ? nuevo.texto : "actualizado"}». El cambio y su motivo quedaron en el historial.`
      );
      cargarHistorial();
      return;
    }
    ocultarConfirmacion(false);
    manejarErrorAccion(estado, datos, {
      aviso: avisoEstado,
      campos: {
        motivo: [motivoEstado, document.getElementById("error-motivo")],
        estado_nuevo: [opcionesEstado.closest("fieldset"), document.getElementById("error-estado_nuevo")],
      },
    });
  }

  // Respuesta de error de una acción. Lo escrito siempre se conserva.
  function manejarErrorAccion(estado, datos, destino) {
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 403) {
      // Conflicto de interés (CA-19.4) o rol retirado: el mensaje del servidor y sin acciones.
      sinAcciones = true;
      curatoria.avisar(avisoPagina, "error", datos.mensaje, curatoria.enlaceBoton("Volver a la cola", "curatoria.html"));
      if (detalle) {
        pintar(detalle);
      }
      return;
    }
    const aviso = destino.aviso;
    aviso.className = "aviso aviso-error";
    let primero = null;
    const sinCampo = [];
    if (estado === 400) {
      for (const [nombre, texto] of Object.entries(datos.errores || {})) {
        const par = destino.campos[nombre];
        if (par) {
          mostrarErrorCampo(par[0], par[1], texto);
          primero = primero || par[0];
        } else {
          sinCampo.push(texto);
        }
      }
    }
    // 409 (RF-33, estado desactualizado, documento ya revisado) y 404: se ofrece recargar.
    const conRecarga = estado === 409 || estado === 404;
    // Hallazgo UX E-1: si ningún campo quedó marcado, solo los errores (sin
    // "revisa los campos marcados").
    const partes = primero || sinCampo.length === 0 ? [datos.mensaje, ...sinCampo] : sinCampo;
    const texto =
      estado === 404
        ? "No encontramos este expediente o documento. Toca «Recargar el expediente» para ver la información actual."
        : partes.filter(Boolean).join(" ");
    aviso.replaceChildren(texto, ...(conRecarga ? [botonRecargar()] : []));
    if (primero && sinCampo.length === 0 && estado === 400) {
      primero.focus();
    } else {
      aviso.focus();
    }
  }

  // --- Historial (CA-19.3) ---

  function textoAccion(entrada) {
    const nombre = entrada.documento
      ? expediente.nombreDocumento(entrada.documento.tipo, entrada.documento.oficio)
      : "";
    switch (entrada.accion) {
      case "expediente.cambiar_estado":
        return "Cambio de estado del expediente";
      case "documento.validar":
        return `Documento validado: ${nombre}`;
      case "documento.observar":
        return `Documento observado: ${nombre}`;
      default:
        return entrada.documento ? `Acción sobre un documento: ${nombre}` : "Acción administrativa";
    }
  }

  function textoEstado(valor, tabla) {
    if (!valor) {
      return "Sin dato";
    }
    return tabla[valor] ? tabla[valor].texto : "Sin dato";
  }

  function entradaHistorial(entrada) {
    const tabla = entrada.documento ? curatoria.ESTADOS_DOCUMENTO : curatoria.ESTADOS_EXPEDIENTE;
    const datos = elemento("dl", "datos");
    const filas = [
      ["Fecha", expediente.formatearFechaHora(entrada.fecha)],
      ["Autor", entrada.autor],
      ["Acción", textoAccion(entrada)],
      ["Estado anterior", textoEstado(entrada.estado_anterior, tabla)],
      ["Estado nuevo", textoEstado(entrada.estado_nuevo, tabla)],
      ["Motivo", entrada.motivo || "Sin motivo"],
    ];
    for (const [titulo, valor] of filas) {
      datos.append(elemento("dt", "", titulo), elemento("dd", "", valor));
    }
    const item = elemento("li", "entrada-historial", datos);
    if (entrada.documento) {
      // ADR-017, E-3: también documentos reemplazados (p. ej., la licencia anterior).
      const nombre = expediente.nombreDocumento(entrada.documento.tipo, entrada.documento.oficio);
      const reemplazado = entrada.documento.estado === "reemplazado";
      if (reemplazado) {
        item.append(elemento("p", "ayuda", "Este documento fue reemplazado por uno más reciente."));
      }
      item.append(elemento("div", "acciones", botonVer(entrada.documento, nombre, reemplazado ? " (reemplazado)" : "")));
    }
    return item;
  }

  async function cargarHistorial() {
    estadoHistorial.textContent = "Cargando el historial…";
    const { estado, datos } = await api.obtener(`${curatoria.RUTA}/expedientes/${encodeURIComponent(ref)}/historial`);
    if (estado === 401) {
      estadoHistorial.textContent = "";
      sesionTerminada();
      return;
    }
    if (estado !== 200) {
      const reintentar = elemento("button", "boton-secundario", "Reintentar");
      reintentar.type = "button";
      reintentar.addEventListener("click", cargarHistorial);
      estadoHistorial.replaceChildren(
        elemento("span", "error-campo", datos.mensaje || "No pudimos cargar el historial."),
        reintentar
      );
      return;
    }
    listaHistorial.replaceChildren(...datos.historial.map(entradaHistorial));
    estadoHistorial.textContent =
      datos.historial.length === 0
        ? "Todavía no hay acciones registradas."
        : `${datos.historial.length} ${datos.historial.length === 1 ? "acción registrada" : "acciones registradas"}, de la más reciente a la más antigua.`;
  }

  // --- Carga ---

  function pintar(det) {
    detalle = det;
    pintarDatos(det);
    pintarDocumentos(det);
    pintarEstado(det);
    contenido.hidden = false;
  }

  // 403 al abrir: conflicto de interés (tiene el rol, CA-19.4) o falta del rol.
  async function avisarProhibido(datos) {
    const cuenta = await api.obtener("/api/cuenta");
    const roles = cuenta.estado === 200 && Array.isArray(cuenta.datos.cuenta.roles) ? cuenta.datos.cuenta.roles : [];
    if (roles.includes("curatoria")) {
      curatoria.avisar(avisoPagina, "error", datos.mensaje, curatoria.enlaceBoton("Volver a la cola", "curatoria.html"));
    } else {
      curatoria.avisarSinRol(avisoPagina);
    }
  }

  function avisarNoEncontrado() {
    curatoria.avisar(
      avisoPagina,
      "error",
      "No encontramos este expediente. Vuelve a la cola y ábrelo desde la lista.",
      curatoria.enlaceBoton("Volver a la cola", "curatoria.html")
    );
  }

  async function cargar(opciones) {
    if (!opciones || opciones.conservarAvisos === false) {
      curatoria.limpiar(avisoResultado);
    }
    curatoria.limpiar(avisoPagina);
    limpiarFormEstado();
    if (!curatoria.FORMATO_REF.test(ref)) {
      cargando.classList.add("oculto");
      avisarNoEncontrado();
      return;
    }
    cargando.classList.remove("oculto");
    const { estado, datos } = await api.obtener(`${curatoria.RUTA}/expedientes/${encodeURIComponent(ref)}`);
    cargando.classList.add("oculto");
    if (estado === 200) {
      pintar(datos.expediente);
      cargarHistorial();
      return;
    }
    contenido.hidden = true;
    if (estado === 401) {
      sesionTerminada();
    } else if (estado === 403) {
      sinAcciones = true;
      await avisarProhibido(datos);
    } else if (estado === 404) {
      avisarNoEncontrado();
    } else {
      curatoria.avisarErrorCarga(avisoPagina, datos.mensaje, () => cargar());
    }
  }

  // "Volver a la cola" regresa al filtro y la página de donde se vino.
  if (document.referrer) {
    try {
      const origen = new URL(document.referrer);
      if (origen.origin === location.origin && origen.pathname.endsWith("/curatoria.html")) {
        document.getElementById("volver-cola").href = `curatoria.html${origen.search}`;
      }
    } catch (error) {
      // Dirección de origen ilegible: se usa la cola sin filtro.
    }
  }

  cargar();
})();
