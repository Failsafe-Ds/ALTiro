// Mis servicios del maestro (HU-12, RF-05, CA-12.1, CA-12.2, RF-34; ADR-019).
// - GET /api/maestros/servicios: servicios del maestro con "visible" y los
//   motivos (código y texto del servidor), más "pendientes" (lo que falta para
//   que los clientes lo vean). La página no calcula la visibilidad.
// - GET /api/maestros/expediente: oficios declarados (primer paso de agregar).
// - GET /api/catalogo: servicios de cada oficio, formas de cobro admitidas y
//   precios de referencia.
// - POST /api/maestros/servicios; PATCH y DELETE /api/maestros/servicios/<ref>.
// RNF-14: un dato por paso y botones grandes. RNF-15: errores junto al campo,
// con texto e ícono. RNF-16: el estado lleva ícono y texto. RNF-17: lenguaje
// del oficio ("forma de cobro", "comuna principal"). RNF-20: lo escrito al
// agregar se conserva (sessionStorage, con vencimiento) si se corta la señal o
// termina la sesión.
"use strict";

(() => {
  const RUTA = "/api/maestros/servicios";
  const CLAVE = "altiro.servicios.agregar";
  const PASOS = ["oficio", "servicio", "modalidad", "monto"];

  const MODALIDADES = { por_trabajo: "por trabajo", por_hora: "por hora" };
  const NOMBRE_MODALIDAD = { por_trabajo: "Por trabajo", por_hora: "Por hora" };

  // Respaldo por si el servidor no trae el texto de un motivo (RNF-17). El
  // texto del servidor tiene prioridad.
  const TEXTOS_MOTIVO = {
    retirado: () => "Quitaste este servicio.",
    catalogo_inactivo: () => "AlTiro dejó de ofrecer este servicio, así que los clientes no lo ven.",
    oficio_no_declarado: () => "Este servicio es de un oficio que no está entre tus oficios, así que los clientes no lo ven.",
    modalidad_no_admitida: () =>
      "Este servicio ya no se cobra de esa forma. Cambia la forma de cobro para que los clientes lo vean.",
    licencia_no_vigente: (s) =>
      `No lo ven los clientes: tu licencia de ${s.oficio.nombre} no está vigente. Sube una nueva en «Mis documentos».`,
    maestro_no_elegible: () => "Todavía no te ven los clientes. Revisa lo que te falta al comienzo de esta página.",
  };
  const TEXTOS_PENDIENTE = {
    postulacion_no_aprobada: "Tu postulación todavía no está aprobada.",
    sin_comuna_base: "Falta que elijas tu comuna principal.",
    sin_foto: "Falta que subas tu foto.",
  };
  // Página que resuelve cada pendiente (solo navegación).
  const ACCIONES_PENDIENTE = {
    postulacion_no_aprobada: { texto: "Ver mi postulación", href: "mi-postulacion.html" },
    sin_comuna_base: { texto: "Ir a mi cobertura", href: "mi-cobertura.html" },
    sin_foto: { texto: "Ir a mi perfil para subir tu foto", href: "mi-perfil.html" },
  };

  const cargando = document.getElementById("cargando");
  const avisoPagina = document.getElementById("aviso-pagina");
  const avisoResultado = document.getElementById("aviso-resultado");
  const contenido = document.getElementById("contenido");
  const listaServicios = document.getElementById("lista-servicios");
  const main = document.querySelector("main");

  const formAgregar = document.getElementById("form-agregar");
  const seccionAgregar = document.getElementById("seccion-agregar");
  const abrirAgregar = document.getElementById("abrir-agregar");
  const botonSiguiente = document.getElementById("agregar-siguiente");
  const botonGuardar = document.getElementById("agregar-guardar");
  const botonAtras = document.getElementById("agregar-atras");
  const campoMonto = document.getElementById("nuevo-monto");
  const pasos = Array.from(formAgregar.querySelectorAll(".paso"));

  const formCambiar = document.getElementById("form-cambiar");
  const confirmarQuitar = document.getElementById("confirmar-quitar");
  const avisoQuitar = document.getElementById("aviso-quitar");

  let servicios = [];
  let oficios = [];
  let catalogo = [];
  let paso = 0;
  // Elecciones del formulario de agregar (se guardan para no perderlas).
  const eleccion = { oficio: "", servicio: "", modalidad: "" };
  let editando = null; // servicio del maestro cuyo precio se cambia
  let quitando = null; // servicio del maestro que se va a quitar

  // --- Utilidades ---

  function elemento(etiqueta, clase, ...hijos) {
    const nodo = document.createElement(etiqueta);
    if (clase) {
      nodo.className = clase;
    }
    nodo.append(...hijos);
    return nodo;
  }

  function etiquetaVisible(visible) {
    const datos = visible
      ? { icono: "✓", texto: "Lo ven los clientes", clase: "estado-aprobado" }
      : { icono: "✕", texto: "No lo ven los clientes", clase: "estado-rechazado" };
    const icono = elemento("span", "", datos.icono);
    icono.setAttribute("aria-hidden", "true");
    return elemento("span", "estado " + datos.clase, icono, " " + datos.texto);
  }

  function textoModalidad(servicio) {
    return (servicio.modalidad_texto || NOMBRE_MODALIDAD[servicio.modalidad] || "").toLowerCase();
  }

  function textoPrecio(monto, modalidad) {
    return `${formato.monto(monto)} ${MODALIDADES[modalidad] || ""}`.trim();
  }

  // Precios de referencia de un servicio del catálogo: "$80.000 por trabajo · $15.000 por hora".
  function textoReferencias(servicioCatalogo) {
    return servicioCatalogo.modalidades.map((m) => textoPrecio(m.precio_referencia, m.modalidad)).join(" · ");
  }

  function oficioDelCatalogo(codigo) {
    return catalogo.find((o) => o.codigo === codigo) || null;
  }

  function servicioDelCatalogo(ref) {
    for (const oficio of catalogo) {
      const encontrado = oficio.servicios.find((s) => s.ref === ref);
      if (encontrado) {
        return encontrado;
      }
    }
    return null;
  }

  function avisarResultado(texto) {
    avisoResultado.className = "aviso aviso-exito";
    avisoResultado.textContent = texto;
    avisoResultado.focus();
  }

  function limpiarResultado() {
    avisoResultado.className = "aviso";
    avisoResultado.textContent = "";
  }

  // Los errores del servidor ("servicio", "monto"…) se muestran en los campos
  // de un formulario cuyos ids llevan un prefijo ("nuevo-", "cambiar-").
  function conPrefijo(datos, prefijo) {
    const errores = {};
    for (const [campo, texto] of Object.entries(datos.errores || {})) {
      errores[prefijo + campo] = texto;
    }
    return { mensaje: datos.mensaje, errores };
  }

  // Opción grande (casilla del pulgar) con un texto de apoyo opcional.
  function opcion(nombre, valor, texto, nota, marcada) {
    const etiqueta = elemento("label", "casilla casilla-grande");
    const entrada = document.createElement("input");
    entrada.type = "radio";
    entrada.name = nombre;
    entrada.value = valor;
    entrada.checked = Boolean(marcada);
    const textos = elemento("span", "casilla-texto", texto);
    if (nota) {
      textos.append(elemento("span", "nota-precio", nota));
    }
    etiqueta.append(entrada, textos);
    return etiqueta;
  }

  // --- Sesión y acceso ---

  function cerrarEdiciones() {
    guardarFormulariosFlotantes();
    editando = null;
    quitando = null;
  }

  function sesionTerminada() {
    cerrarEdiciones();
    contenido.hidden = true;
    limpiarResultado();
    expediente.avisarSesionTerminada(
      avisoPagina,
      "servicios",
      seccionAgregar.hidden ? "" : "Lo que escribiste para agregar un servicio seguirá aquí cuando vuelvas."
    );
  }

  function sinAcceso() {
    cerrarEdiciones();
    contenido.hidden = true;
    expediente.avisarNoMaestro(avisoPagina);
  }

  // --- Lista de servicios ---

  // El formulario de cambio y la confirmación de quitar se mueven dentro de la
  // tarjeta que se edita. Antes de volver a pintar la lista se devuelven a su
  // lugar (ocultos), para no perderlos.
  function guardarFormulariosFlotantes() {
    formCambiar.hidden = true;
    confirmarQuitar.hidden = true;
    main.append(formCambiar, confirmarQuitar);
  }

  function lineaMotivo(servicio, motivo) {
    const texto = motivo.mensaje || (TEXTOS_MOTIVO[motivo.codigo] || (() => ""))(servicio);
    const item = elemento("li", "aviso-vencimiento motivo-servicio");
    const icono = elemento("span", "icono-aviso", "⚠");
    icono.setAttribute("aria-hidden", "true");
    const detalle = elemento("span", "detalle-aviso", texto);
    if (motivo.codigo === "licencia_no_vigente") {
      const enlace = elemento("a", "boton boton-secundario", "Ir a mis documentos");
      enlace.href = "mis-documentos.html";
      detalle.append(enlace);
    } else if (motivo.codigo === "maestro_no_elegible") {
      const enlace = elemento("a", "boton boton-secundario", "Ver lo que te falta");
      enlace.href = "#titulo-pendientes";
      enlace.addEventListener("click", (evento) => {
        evento.preventDefault();
        const titulo = document.getElementById("titulo-pendientes");
        titulo.scrollIntoView();
        titulo.focus();
      });
      detalle.append(enlace);
    }
    item.append(icono, detalle);
    return item;
  }

  function tarjeta(servicio) {
    const item = elemento("li", "tarjeta documento");
    item.dataset.ref = servicio.ref;
    const titulo = elemento("h3", "", servicio.servicio.nombre);
    titulo.id = `servicio-${servicio.ref}`;
    titulo.tabIndex = -1;
    const precio = elemento("strong", "", `${formato.monto(servicio.monto)} ${textoModalidad(servicio)}`);
    item.append(
      titulo,
      elemento("p", "", `Oficio: ${servicio.oficio.nombre}`),
      elemento("p", "", "Cobras: ", precio),
      elemento("p", "", etiquetaVisible(servicio.visible))
    );
    if (!servicio.visible && servicio.motivos && servicio.motivos.length) {
      item.append(elemento("ul", "lista-avisos motivos-servicio", ...servicio.motivos.map((m) => lineaMotivo(servicio, m))));
    }
    const acciones = elemento("div", "acciones acciones-dobles");
    // Solo se ofrece cambiar el precio si el catálogo publica el servicio
    // (para mostrar sus formas de cobro); si AlTiro lo dejó de ofrecer, solo se puede quitar.
    if (servicioDelCatalogo(servicio.servicio.ref)) {
      const cambiar = elemento("button", "", "Cambiar precio");
      cambiar.type = "button";
      cambiar.setAttribute("aria-label", `Cambiar precio de ${servicio.servicio.nombre}`);
      cambiar.addEventListener("click", () => abrirCambio(servicio, item));
      acciones.append(cambiar);
    }
    const quitar = elemento("button", "boton-secundario", "Quitar");
    quitar.type = "button";
    quitar.setAttribute("aria-label", `Quitar ${servicio.servicio.nombre}`);
    quitar.addEventListener("click", () => abrirQuitar(servicio, item));
    acciones.append(quitar);
    item.append(acciones);
    return item;
  }

  function pintarPendientes(pendientes) {
    const seccion = document.getElementById("pendientes");
    const lista = document.getElementById("lista-pendientes");
    lista.replaceChildren(
      ...(pendientes || []).map((p) => {
        const item = elemento("li", "aviso-vencimiento");
        const icono = elemento("span", "icono-aviso", "⚠");
        icono.setAttribute("aria-hidden", "true");
        const detalle = elemento("span", "detalle-aviso", p.mensaje || TEXTOS_PENDIENTE[p.codigo] || "");
        const accion = ACCIONES_PENDIENTE[p.codigo];
        if (accion) {
          const enlace = elemento("a", "boton boton-secundario", accion.texto);
          enlace.href = accion.href;
          detalle.append(enlace);
        }
        item.append(icono, detalle);
        return item;
      })
    );
    seccion.hidden = lista.children.length === 0;
  }

  function pintarLista() {
    guardarFormulariosFlotantes();
    editando = null;
    quitando = null;
    listaServicios.replaceChildren(...servicios.map(tarjeta));
    document.getElementById("sin-servicios").hidden = servicios.length > 0;
  }

  function pintarAgregar() {
    const hayOficios = oficios.length > 0;
    document.getElementById("sin-oficios").hidden = hayOficios;
    document.getElementById("acciones-agregar").hidden = !hayOficios || !seccionAgregar.hidden;
    if (!hayOficios) {
      seccionAgregar.hidden = true;
    }
  }

  // --- Carga ---

  async function cargar() {
    expediente.limpiarAviso(avisoPagina);
    cargando.hidden = false;
    cargando.classList.remove("oculto");
    const [resServicios, resExpediente, resCatalogo] = await Promise.all([
      api.obtener(RUTA),
      api.obtener(expediente.RUTA),
      api.obtener("/api/catalogo"),
    ]);
    cargando.hidden = true;
    const estados = [resServicios.estado, resExpediente.estado];
    if (estados.includes(401)) {
      sesionTerminada();
      return false;
    }
    if (estados.includes(403)) {
      sinAcceso();
      return false;
    }
    const fallida = [resServicios, resExpediente, resCatalogo].find((r) => r.estado !== 200);
    if (fallida) {
      contenido.hidden = true;
      expediente.avisarErrorCarga(avisoPagina, fallida.datos.mensaje, cargar);
      return false;
    }
    servicios = resServicios.datos.servicios;
    oficios = resExpediente.datos.expediente.oficios || [];
    catalogo = resCatalogo.datos.oficios || [];
    pintarPendientes(resServicios.datos.pendientes);
    pintarLista();
    pintarAgregar();
    contenido.hidden = false;
    return true;
  }

  // Tras un 404 o 409 al cambiar o quitar: la lista se vuelve a leer y el aviso se mantiene.
  async function recargarLista() {
    const { estado, datos } = await api.obtener(RUTA);
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 200) {
      servicios = datos.servicios;
      pintarPendientes(datos.pendientes);
      pintarLista();
    }
  }

  // --- Agregar un servicio, por pasos ---

  function guardarProgreso() {
    formulario.guardarDatos(CLAVE, {
      paso,
      oficio: eleccion.oficio,
      servicio: eleccion.servicio,
      modalidad: eleccion.modalidad,
      monto: campoMonto.value,
    });
  }

  function servicioElegido() {
    return servicioDelCatalogo(eleccion.servicio);
  }

  function modalidadElegida() {
    const servicio = servicioElegido();
    return servicio ? servicio.modalidades.find((m) => m.modalidad === eleccion.modalidad) || null : null;
  }

  // Cada paso se arma con lo elegido en el anterior. Si una elección ya no
  // corresponde (por ejemplo, se cambió de oficio), se descarta.
  function prepararPaso(indice) {
    if (PASOS[indice] === "oficio") {
      document.getElementById("opciones-oficio").replaceChildren(
        ...oficios.map((o) =>
          opcion(
            "oficio",
            o.codigo,
            o.nombre,
            o.regulado ? "Necesita tu licencia de la SEC vigente para que te vean." : "",
            o.codigo === eleccion.oficio
          )
        )
      );
    } else if (PASOS[indice] === "servicio") {
      const oficio = oficioDelCatalogo(eleccion.oficio);
      const yaOfrece = new Set(servicios.map((s) => s.servicio.ref));
      const disponibles = oficio ? oficio.servicios.filter((s) => !yaOfrece.has(s.ref)) : [];
      if (!disponibles.some((s) => s.ref === eleccion.servicio)) {
        eleccion.servicio = "";
      }
      const contenedor = document.getElementById("opciones-servicio");
      if (!disponibles.length) {
        const texto = oficio && oficio.servicios.length
          ? "Ya ofreces todos los servicios de este oficio. Puedes cambiar sus precios en tu lista."
          : "Por ahora AlTiro no tiene servicios de este oficio. Vuelve al paso anterior y elige otro oficio.";
        contenedor.replaceChildren(elemento("p", "", texto));
      } else {
        contenedor.replaceChildren(
          ...disponibles.map((s) =>
            opcion("servicio", s.ref, s.nombre, `Precio de referencia: ${textoReferencias(s)}`, s.ref === eleccion.servicio)
          )
        );
      }
    } else if (PASOS[indice] === "modalidad") {
      const servicio = servicioElegido();
      const admitidas = servicio ? servicio.modalidades : [];
      if (!admitidas.some((m) => m.modalidad === eleccion.modalidad)) {
        // Si el servicio admite una sola forma de cobro, se deja marcada.
        eleccion.modalidad = admitidas.length === 1 ? admitidas[0].modalidad : "";
      }
      document.getElementById("opciones-modalidad").replaceChildren(
        ...admitidas.map((m) =>
          opcion(
            "modalidad",
            m.modalidad,
            NOMBRE_MODALIDAD[m.modalidad] || m.modalidad,
            `Precio de referencia: ${formato.monto(m.precio_referencia)}`,
            m.modalidad === eleccion.modalidad
          )
        )
      );
    } else if (PASOS[indice] === "monto") {
      const servicio = servicioElegido();
      const modalidad = modalidadElegida();
      document.getElementById("etiqueta-nuevo-monto").textContent = modalidad
        ? `Tu precio ${MODALIDADES[modalidad.modalidad]}, en pesos (obligatorio)`
        : "Tu precio en pesos (obligatorio)";
      document.getElementById("ayuda-nuevo-monto").textContent =
        (servicio ? `${servicio.nombre}. ` : "") +
        "Solo números. " +
        (modalidad ? `Precio de referencia: ${textoPrecio(modalidad.precio_referencia, modalidad.modalidad)}.` : "");
    }
  }

  function mostrarPaso(indice, enfocar = true) {
    paso = indice;
    prepararPaso(indice);
    pasos.forEach((fieldset, i) => {
      fieldset.hidden = i !== indice;
    });
    document.getElementById("progreso-agregar").textContent = `Paso ${indice + 1} de ${pasos.length}`;
    const ultimo = indice === pasos.length - 1;
    botonSiguiente.hidden = ultimo;
    botonGuardar.hidden = !ultimo;
    botonAtras.hidden = indice === 0;
    guardarProgreso();
    if (enfocar) {
      pasos[indice].querySelector("legend").focus();
    }
  }

  // "Continuar" solo exige que se haya elegido una opción (experiencia de uso).
  // Las reglas (oficio declarado, forma de cobro admitida, monto) las vuelve a
  // revisar el servidor al agregar.
  const FALTA_ELEGIR = {
    oficio: "Elige un oficio de la lista.",
    servicio: "Elige un servicio de la lista.",
    modalidad: "Elige si cobras por trabajo o por hora.",
  };

  function siguiente() {
    const campo = PASOS[paso];
    formulario.limpiarErrores(formAgregar);
    if (!eleccion[campo]) {
      formulario.mostrarErrores(formAgregar, {
        mensaje: "Elige una opción para continuar.",
        errores: { [`nuevo-${campo}`]: FALTA_ELEGIR[campo] },
      });
      const primera = pasos[paso].querySelector("input");
      (primera || pasos[paso].querySelector("legend")).focus();
      return;
    }
    mostrarPaso(paso + 1);
  }

  function abrirFormularioAgregar(previo) {
    limpiarResultado();
    cerrarEdiciones();
    seccionAgregar.hidden = false;
    pintarAgregar();
    formulario.limpiarErrores(formAgregar);
    if (previo) {
      eleccion.oficio = previo.oficio || "";
      eleccion.servicio = previo.servicio || "";
      eleccion.modalidad = previo.modalidad || "";
      campoMonto.value = previo.monto || "";
      // Se rearman los pasos en orden para descartar elecciones que ya no corresponden.
      const hasta = Math.min(Math.max(0, previo.paso || 0), pasos.length - 1);
      for (let i = 0; i <= hasta; i += 1) {
        prepararPaso(i);
      }
      mostrarPaso(hasta, false);
      return;
    }
    // Con un solo oficio declarado, se deja marcado.
    eleccion.oficio = oficios.length === 1 ? oficios[0].codigo : "";
    eleccion.servicio = "";
    eleccion.modalidad = "";
    campoMonto.value = "";
    mostrarPaso(0);
  }

  function cerrarFormularioAgregar() {
    seccionAgregar.hidden = true;
    formulario.limpiarErrores(formAgregar);
    formulario.olvidar(CLAVE);
    pintarAgregar();
  }

  formAgregar.addEventListener("change", (evento) => {
    const campo = evento.target;
    if (campo.type === "radio" && Object.prototype.hasOwnProperty.call(eleccion, campo.name)) {
      eleccion[campo.name] = campo.value;
      guardarProgreso();
    }
  });
  campoMonto.addEventListener("input", guardarProgreso);

  botonSiguiente.addEventListener("click", siguiente);
  botonAtras.addEventListener("click", () => {
    formulario.limpiarErrores(formAgregar);
    mostrarPaso(Math.max(0, paso - 1));
  });
  document.getElementById("agregar-cancelar").addEventListener("click", () => {
    cerrarFormularioAgregar();
    abrirAgregar.focus();
  });
  abrirAgregar.addEventListener("click", () => abrirFormularioAgregar(null));

  // Enter en un paso intermedio avanza en vez de enviar.
  formAgregar.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" && paso < pasos.length - 1 && evento.target.tagName === "INPUT") {
      evento.preventDefault();
      siguiente();
    }
  });

  formAgregar.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (paso < pasos.length - 1) {
      siguiente();
      return;
    }
    formulario.limpiarErrores(formAgregar);
    formulario.ocupado(formAgregar, true);
    // CA-12.1: si falta la forma de cobro o el monto, lo dice el servidor junto al campo.
    const { estado, datos } = await api.enviar(RUTA, {
      servicio: eleccion.servicio,
      modalidad: eleccion.modalidad,
      monto: formato.leerMonto(campoMonto.value),
    });
    formulario.ocupado(formAgregar, false);
    if (estado === 201) {
      const nuevo = datos.servicio;
      servicios.push(nuevo);
      cerrarFormularioAgregar();
      pintarLista();
      avisarResultado(
        `Listo: agregaste «${nuevo.servicio.nombre}» a tus servicios, a ${formato.monto(nuevo.monto)} ${textoModalidad(nuevo)}.` +
          (nuevo.visible ? " Los clientes ya lo ven." : " Todavía no lo ven los clientes: el motivo está en tu lista.")
      );
      return;
    }
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 403) {
      sinAcceso();
      return;
    }
    if (estado === 400) {
      const conCampos = conPrefijo(datos, "nuevo-");
      // Se vuelve al primer paso con error; los demás errores quedan en sus campos.
      const conError = PASOS.findIndex((campo) => conCampos.errores[`nuevo-${campo}`]);
      if (conError >= 0 && conError !== paso) {
        mostrarPaso(conError, false);
      }
      const campo = formulario.mostrarErrores(formAgregar, conCampos);
      if (campo) {
        (campo.tagName === "FIELDSET" ? campo.querySelector("input") || campo.querySelector("legend") : campo).focus();
      }
      return;
    }
    // 409 (la postulación no fue aprobada), sin conexión u otro error: el aviso
    // del servidor y lo escrito se conserva.
    formulario.avisar(formAgregar, datos.mensaje, "error");
  });

  // --- Cambiar forma de cobro o monto ---

  function actualizarAyudaCambio() {
    const catalogoServicio = editando && servicioDelCatalogo(editando.servicio.ref);
    const marcada = formCambiar.querySelector('input[name="cambiar-modalidad"]:checked');
    const modalidad = catalogoServicio && marcada
      ? catalogoServicio.modalidades.find((m) => m.modalidad === marcada.value)
      : null;
    document.getElementById("ayuda-cambiar-monto").textContent =
      "Solo números." +
      (modalidad ? ` Precio de referencia: ${textoPrecio(modalidad.precio_referencia, modalidad.modalidad)}.` : "");
  }

  function abrirCambio(servicio, item) {
    limpiarResultado();
    guardarFormulariosFlotantes();
    quitando = null;
    editando = servicio;
    formulario.limpiarErrores(formCambiar);
    const catalogoServicio = servicioDelCatalogo(servicio.servicio.ref);
    const admitidas = catalogoServicio ? catalogoServicio.modalidades : [];
    document.getElementById("cambiar-opciones-modalidad").replaceChildren(
      ...admitidas.map((m) =>
        opcion(
          "cambiar-modalidad",
          m.modalidad,
          NOMBRE_MODALIDAD[m.modalidad] || m.modalidad,
          `Precio de referencia: ${formato.monto(m.precio_referencia)}`,
          m.modalidad === servicio.modalidad
        )
      )
    );
    document.getElementById("cambiar-monto").value = String(servicio.monto);
    actualizarAyudaCambio();
    item.querySelector(".acciones").before(formCambiar);
    formCambiar.hidden = false;
    document.getElementById("titulo-cambiar").focus();
  }

  function cerrarCambio() {
    const ref = editando && editando.ref;
    guardarFormulariosFlotantes();
    editando = null;
    const item = ref && listaServicios.querySelector(`[data-ref="${ref}"]`);
    const boton = item && item.querySelector("button");
    if (boton) {
      boton.focus();
    }
  }

  formCambiar.addEventListener("change", actualizarAyudaCambio);
  document.getElementById("cambiar-cancelar").addEventListener("click", cerrarCambio);

  formCambiar.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (!editando) {
      return;
    }
    formulario.limpiarErrores(formCambiar);
    const marcada = formCambiar.querySelector('input[name="cambiar-modalidad"]:checked');
    const cuerpo = { monto: formato.leerMonto(document.getElementById("cambiar-monto").value) };
    cuerpo.modalidad = marcada ? marcada.value : "";
    formulario.ocupado(formCambiar, true);
    const { estado, datos } = await api.modificar(`${RUTA}/${encodeURIComponent(editando.ref)}`, cuerpo);
    formulario.ocupado(formCambiar, false);
    if (estado === 200) {
      const actualizado = datos.servicio;
      servicios = servicios.map((s) => (s.ref === actualizado.ref ? actualizado : s));
      pintarLista();
      avisarResultado(
        `Listo: ahora cobras ${formato.monto(actualizado.monto)} ${textoModalidad(actualizado)} por «${actualizado.servicio.nombre}».`
      );
      return;
    }
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 400) {
      const campo = formulario.mostrarErrores(formCambiar, conPrefijo(datos, "cambiar-"));
      if (campo) {
        (campo.tagName === "FIELDSET" ? campo.querySelector("input") || campo : campo).focus();
      }
      return;
    }
    if (estado === 404 || estado === 409) {
      // El servicio ya no existe o ya no se puede cambiar (por ejemplo, se quitó
      // desde otro teléfono): se avisa y se vuelve a leer la lista.
      const mensaje =
        estado === 404 ? "No encontramos este servicio. Puede que lo hayas quitado desde otro teléfono." : datos.mensaje;
      await recargarLista();
      avisarAviso(mensaje);
      return;
    }
    formulario.avisar(formCambiar, datos.mensaje, "error");
  });

  function avisarAviso(mensaje) {
    avisoPagina.className = "aviso aviso-error";
    avisoPagina.textContent = mensaje;
    avisoPagina.focus();
  }

  // --- Quitar un servicio, con confirmación en la página ---

  function abrirQuitar(servicio, item) {
    limpiarResultado();
    guardarFormulariosFlotantes();
    editando = null;
    quitando = servicio;
    expediente.limpiarAviso(avisoQuitar);
    document.getElementById("titulo-quitar").textContent = `¿Quitar «${servicio.servicio.nombre}» de tus servicios?`;
    item.querySelector(".acciones").before(confirmarQuitar);
    confirmarQuitar.hidden = false;
    document.getElementById("titulo-quitar").focus();
  }

  document.getElementById("quitar-no").addEventListener("click", () => {
    const ref = quitando && quitando.ref;
    guardarFormulariosFlotantes();
    quitando = null;
    const item = ref && listaServicios.querySelector(`[data-ref="${ref}"]`);
    const boton = item && item.querySelector(".boton-secundario");
    if (boton) {
      boton.focus();
    }
  });

  const botonQuitarSi = document.getElementById("quitar-si");
  const textoQuitarSi = botonQuitarSi.textContent;
  botonQuitarSi.addEventListener("click", async () => {
    if (!quitando) {
      return;
    }
    const servicio = quitando;
    expediente.limpiarAviso(avisoQuitar);
    botonQuitarSi.disabled = true;
    botonQuitarSi.textContent = "Quitando…";
    const { estado, datos } = await api.borrar(`${RUTA}/${encodeURIComponent(servicio.ref)}`);
    botonQuitarSi.disabled = false;
    botonQuitarSi.textContent = textoQuitarSi;
    if (estado === 204) {
      servicios = servicios.filter((s) => s.ref !== servicio.ref);
      pintarLista();
      avisarResultado(`Quitaste «${servicio.servicio.nombre}». Los clientes ya no lo ven.`);
      return;
    }
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 404 || estado === 409) {
      const mensaje =
        estado === 404 ? "No encontramos este servicio. Puede que ya lo hayas quitado desde otro teléfono." : datos.mensaje;
      await recargarLista();
      avisarAviso(mensaje);
      return;
    }
    avisoQuitar.className = "aviso aviso-error";
    avisoQuitar.textContent = datos.mensaje;
    avisoQuitar.focus();
  });

  // --- Inicio ---

  (async () => {
    if (!(await cargar())) {
      return;
    }
    // RNF-20: si quedó a medias un servicio por agregar, se retoma.
    const previo = formulario.recuperar(CLAVE);
    if (previo && oficios.length) {
      abrirFormularioAgregar(previo);
      formulario.avisar(formAgregar, "Recuperamos lo que habías elegido. Revísalo y sigue.", "exito");
    }
  })();
})();
