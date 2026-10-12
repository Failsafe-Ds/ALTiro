// Catálogo administrable del área comercial (HU-20, RF-36, CA-20.1, CA-20.2; ADR-018).
// - GET /api/comercial/catalogo: oficios y servicios, activos e inactivos, con su "version".
// - POST /api/comercial/oficios y PATCH /api/comercial/oficios/<ref>.
// - POST /api/comercial/servicios y PATCH /api/comercial/servicios/<ref>.
// Reglas que decide el servidor (aquí no se repiten): nombres únicos, al menos
// una forma de cobro, montos, motivo obligatorio al modificar o dar de baja,
// "regulado" obligatorio al crear e imposible de cambiar después (D-2), y la
// versión (409 si otra persona cambió el registro). La página solo muestra el
// dato "regulado" al editar, sin control para cambiarlo.
// RNF-15: errores junto al campo, con texto e ícono. RNF-16: estados con ícono
// y texto. Pensada para notebook, construida desde 320 px sin desplazamiento lateral.
"use strict";

(() => {
  const RUTA = "/api/comercial";
  const MODALIDADES = [
    { codigo: "por_trabajo", texto: "Por trabajo" },
    { codigo: "por_hora", texto: "Por hora" },
  ];
  const TEXTO_409 = "Otra persona cambió este registro. Vuelve a cargar para ver el cambio.";

  const cargando = document.getElementById("cargando");
  const avisoPagina = document.getElementById("aviso-pagina");
  const avisoResultado = document.getElementById("aviso-resultado");
  const contenido = document.getElementById("contenido");
  const listaOficios = document.getElementById("lista-oficios");
  const lugarOficioNuevo = document.getElementById("lugar-oficio-nuevo");
  const main = document.querySelector("main");

  const formOficio = document.getElementById("form-oficio");
  const formServicio = document.getElementById("form-servicio");
  formulario.prepararBoton(formOficio);
  formulario.prepararBoton(formServicio);

  let oficios = [];
  // Formulario abierto: { tipo: "oficio" | "servicio", accion: "crear" | "editar",
  // ref (registro editado), oficio (código, al crear un servicio), version }.
  let abierto = null;

  // --- Utilidades ---

  const elemento = dom.elemento;

  function etiqueta(icono, texto, clase) {
    const marca = elemento("span", "", icono);
    marca.setAttribute("aria-hidden", "true");
    return elemento("span", "estado " + clase, marca, " " + texto);
  }

  function etiquetaActivo(activo) {
    return activo ? etiqueta("✓", "Activo", "estado-aprobado") : etiqueta("⏸", "Inactivo (dado de baja)", "estado-suspendido");
  }

  function etiquetaRegulado(regulado) {
    return regulado
      ? etiqueta("⚠", "Necesita licencia de la SEC", "estado-observado")
      : etiqueta("•", "No necesita licencia", "estado-revision");
  }

  function boton(texto, clase, etiquetaAccesible, alPulsar) {
    const nodo = elemento("button", clase, texto);
    nodo.type = "button";
    if (etiquetaAccesible) {
      nodo.setAttribute("aria-label", etiquetaAccesible);
    }
    nodo.addEventListener("click", alPulsar);
    return nodo;
  }

  function avisar(aviso, tipo, texto, ...acciones) {
    aviso.className = "aviso aviso-" + tipo;
    aviso.replaceChildren(texto, ...acciones);
    aviso.focus();
  }

  function limpiar(aviso) {
    aviso.className = "aviso";
    aviso.replaceChildren();
  }

  function enlaceBoton(texto, href) {
    const enlace = elemento("a", "boton", texto);
    enlace.href = href;
    return enlace;
  }

  function avisarSesionTerminada() {
    cerrarFormulario(false);
    contenido.hidden = true;
    limpiar(avisoResultado);
    avisar(
      avisoPagina,
      "error",
      "Tu sesión terminó. Vuelve a ingresar para seguir con el catálogo.",
      dom.enlaceIngresar("comercial")
    );
  }

  function avisarSinRol() {
    cerrarFormulario(false);
    contenido.hidden = true;
    limpiar(avisoResultado);
    avisar(
      avisoPagina,
      "error",
      "Esta sección es para el área comercial. Tu cuenta no tiene acceso a ella.",
      enlaceBoton("Ir a mi cuenta", "cuenta.html")
    );
  }

  // Los errores del servidor ("nombre", "motivo"…) van a los campos del formulario, cuyos ids llevan prefijo.
  function conPrefijo(datos, prefijo) {
    const errores = {};
    for (const [campo, texto] of Object.entries(datos.errores || {})) {
      errores[prefijo + campo] = texto;
    }
    return { mensaje: datos.mensaje, errores };
  }

  function marcarRadio(form, nombre, valor) {
    for (const radio of form.querySelectorAll(`input[name="${nombre}"]`)) {
      radio.checked = radio.value === valor;
    }
  }

  function leerRadio(form, nombre) {
    const marcada = form.querySelector(`input[name="${nombre}"]:checked`);
    return marcada ? marcada.value === "si" : undefined;
  }

  function buscarOficio(ref) {
    return oficios.find((o) => o.ref === ref) || null;
  }

  function buscarServicio(ref) {
    for (const oficio of oficios) {
      const servicio = oficio.servicios.find((s) => s.ref === ref);
      if (servicio) {
        return { oficio, servicio };
      }
    }
    return null;
  }

  // --- Lista ---

  function filaServicio(servicio) {
    const item = elemento("li", "servicio-catalogo");
    item.dataset.ref = servicio.ref;
    const cabeza = elemento("div", "servicio-cabeza", elemento("h4", "", servicio.nombre), etiquetaActivo(servicio.activo));
    const precios = elemento(
      "ul",
      "lista-simple precios",
      ...servicio.modalidades.map((m) => {
        const nombre = (MODALIDADES.find((x) => x.codigo === m.modalidad) || { texto: m.modalidad }).texto;
        return elemento("li", "", `${nombre}: `, elemento("strong", "", formato.monto(m.precio_referencia)));
      })
    );
    const zonaPrecios = elemento("div", "", elemento("span", "ayuda", "Precio de referencia"), precios);
    const editar = boton("Editar servicio", "boton-secundario", `Editar el servicio ${servicio.nombre}`, () =>
      abrirServicio({ accion: "editar", ref: servicio.ref })
    );
    item.append(cabeza, zonaPrecios, elemento("div", "servicio-acciones", editar));
    return item;
  }

  function tarjetaOficio(oficio) {
    const item = elemento("li", "tarjeta documento oficio-catalogo");
    item.dataset.ref = oficio.ref;
    const titulo = elemento("h2", "", oficio.nombre);
    titulo.tabIndex = -1;
    const estados = elemento("p", "estados-oficio", etiquetaRegulado(oficio.regulado), " ", etiquetaActivo(oficio.activo));
    const acciones = elemento(
      "div",
      "acciones acciones-dobles",
      boton("Editar oficio", "", `Editar el oficio ${oficio.nombre}`, () => abrirOficio({ accion: "editar", ref: oficio.ref })),
      boton("Agregar servicio", "boton-secundario", `Agregar un servicio a ${oficio.nombre}`, () =>
        abrirServicio({ accion: "crear", oficio: oficio.codigo, ref: oficio.ref })
      )
    );
    const lugarForm = elemento("div", "lugar-form");
    const servicios = oficio.servicios.length
      ? elemento("ul", "lista-simple servicios-catalogo", ...oficio.servicios.map(filaServicio))
      : elemento("p", "", "Todavía no tiene servicios.");
    item.append(titulo, estados, acciones, lugarForm, elemento("h3", "", "Servicios"), servicios);
    return item;
  }

  // Los formularios se devuelven a su lugar (ocultos) antes de volver a pintar la lista.
  function guardarFormularios() {
    formOficio.hidden = true;
    formServicio.hidden = true;
    main.append(formOficio, formServicio);
  }

  // Lugar donde va el formulario abierto: junto al registro que se edita.
  function lugarDe(estado) {
    if (estado.tipo === "oficio" && estado.accion === "crear") {
      return lugarOficioNuevo;
    }
    const oficio = listaOficios.querySelector(`li.oficio-catalogo[data-ref="${estado.ref}"]`);
    if (estado.tipo === "servicio" && estado.accion === "editar") {
      return listaOficios.querySelector(`li.servicio-catalogo[data-ref="${estado.ref}"]`);
    }
    return oficio ? oficio.querySelector(".lugar-form") : null;
  }

  function pintar() {
    guardarFormularios();
    listaOficios.replaceChildren(...oficios.map(tarjetaOficio));
    document.getElementById("sin-oficios").hidden = oficios.length > 0;
    if (abierto) {
      const lugar = lugarDe(abierto);
      if (lugar) {
        const form = abierto.tipo === "oficio" ? formOficio : formServicio;
        lugar.append(form);
        form.hidden = false;
      } else {
        abierto = null;
      }
    }
    document.getElementById("acciones-oficio").hidden = Boolean(abierto && abierto.tipo === "oficio" && abierto.accion === "crear");
  }

  async function leerCatalogo() {
    const { estado, datos } = await api.obtener(`${RUTA}/catalogo`);
    if (estado === 200) {
      oficios = datos.oficios;
    }
    return { estado, datos };
  }

  async function cargar() {
    limpiar(avisoPagina);
    cargando.hidden = false;
    const { estado, datos } = await leerCatalogo();
    cargando.hidden = true;
    if (estado === 401) {
      avisarSesionTerminada();
      return;
    }
    if (estado === 403) {
      avisarSinRol();
      return;
    }
    if (estado !== 200) {
      contenido.hidden = true;
      avisar(avisoPagina, "error", datos.mensaje, boton("Reintentar", "", "", cargar));
      return;
    }
    pintar();
    contenido.hidden = false;
  }

  // --- Abrir y cerrar formularios ---

  function cerrarFormulario(enfocar = true) {
    const anterior = abierto;
    abierto = null;
    guardarFormularios();
    document.getElementById("acciones-oficio").hidden = false;
    if (!enfocar || !anterior) {
      return;
    }
    // El foco vuelve al botón que abrió el formulario.
    let destino = null;
    if (anterior.tipo === "oficio" && anterior.accion === "crear") {
      destino = document.getElementById("abrir-oficio");
    } else {
      const selector =
        anterior.tipo === "servicio" && anterior.accion === "editar"
          ? `li.servicio-catalogo[data-ref="${anterior.ref}"] button`
          : `li.oficio-catalogo[data-ref="${anterior.ref}"] .acciones button:${anterior.tipo === "oficio" ? "first-child" : "last-child"}`;
      destino = listaOficios.querySelector(selector);
    }
    if (destino) {
      destino.focus();
    }
  }

  function textoMotivo(form, prefijo, editar) {
    document.getElementById(`etiqueta-${prefijo}-motivo`).textContent = editar
      ? "Motivo del cambio (obligatorio)"
      : "Comentario (opcional)";
    const campo = document.getElementById(`${prefijo}-motivo`);
    campo.required = editar;
    campo.value = "";
  }

  function abrirOficio({ accion, ref }) {
    limpiar(avisoResultado);
    const oficio = accion === "editar" ? buscarOficio(ref) : null;
    abierto = { tipo: "oficio", accion, ref, version: oficio ? oficio.version : null };
    formulario.limpiarErrores(formOficio);
    const editar = accion === "editar";
    document.getElementById("titulo-form-oficio").textContent = editar ? `Editar el oficio «${oficio.nombre}»` : "Agregar un oficio";
    document.getElementById("oficio-nombre").value = editar ? oficio.nombre : "";
    document.getElementById("campo-regulado").hidden = editar;
    marcarRadio(formOficio, "regulado", "");
    const dato = document.getElementById("dato-regulado");
    dato.hidden = !editar;
    if (editar) {
      dato.replaceChildren(
        etiquetaRegulado(oficio.regulado),
        elemento("span", "ayuda", "Si necesita licencia de la SEC no se cambia desde aquí. Para cambiarlo, pídelo al equipo de desarrollo.")
      );
    }
    document.getElementById("campo-oficio-activo").hidden = !editar;
    marcarRadio(formOficio, "activo", editar ? (oficio.activo ? "si" : "no") : "");
    textoMotivo(formOficio, "oficio", editar);
    const guardar = document.getElementById("guardar-oficio");
    guardar.textContent = editar ? "Guardar el oficio" : "Crear el oficio";
    guardar.dataset.texto = guardar.textContent;
    pintar();
    document.getElementById("titulo-form-oficio").focus();
  }

  function abrirServicio({ accion, ref, oficio: codigoOficio }) {
    limpiar(avisoResultado);
    const editar = accion === "editar";
    const encontrado = editar ? buscarServicio(ref) : null;
    const oficio = editar ? encontrado.oficio : buscarOficio(ref);
    const servicio = encontrado ? encontrado.servicio : null;
    abierto = {
      tipo: "servicio",
      accion,
      ref,
      oficio: editar ? servicio.oficio : codigoOficio,
      version: servicio ? servicio.version : null,
    };
    formulario.limpiarErrores(formServicio);
    document.getElementById("titulo-form-servicio").textContent = editar
      ? `Editar el servicio «${servicio.nombre}»`
      : `Agregar un servicio a ${oficio.nombre}`;
    document.getElementById("dato-oficio-servicio").textContent = `Oficio: ${oficio.nombre}`;
    document.getElementById("servicio-nombre").value = editar ? servicio.nombre : "";
    for (const modalidad of MODALIDADES) {
      const actual = servicio ? servicio.modalidades.find((m) => m.modalidad === modalidad.codigo) : null;
      document.getElementById(`precio-${modalidad.codigo}`).value = actual ? String(actual.precio_referencia) : "";
    }
    document.getElementById("campo-servicio-activo").hidden = !editar;
    marcarRadio(formServicio, "activo", editar ? (servicio.activo ? "si" : "no") : "");
    textoMotivo(formServicio, "servicio", editar);
    const guardar = document.getElementById("guardar-servicio");
    guardar.textContent = editar ? "Guardar el servicio" : "Crear el servicio";
    guardar.dataset.texto = guardar.textContent;
    pintar();
    document.getElementById("titulo-form-servicio").focus();
  }

  document.getElementById("abrir-oficio").addEventListener("click", () => abrirOficio({ accion: "crear" }));
  document.getElementById("cancelar-oficio").addEventListener("click", () => cerrarFormulario());
  document.getElementById("cancelar-servicio").addEventListener("click", () => cerrarFormulario());

  // --- Envío ---

  function cuerpoOficio() {
    const editar = abierto.accion === "editar";
    const cuerpo = { nombre: document.getElementById("oficio-nombre").value };
    const motivo = document.getElementById("oficio-motivo").value;
    if (editar) {
      cuerpo.version = abierto.version;
      cuerpo.motivo = motivo;
      const activo = leerRadio(formOficio, "activo");
      if (activo !== undefined) {
        cuerpo.activo = activo;
      }
    } else {
      // Sin elección no se envía: el servidor responde en el campo (obligatorio, D-2).
      const regulado = leerRadio(formOficio, "regulado");
      if (regulado !== undefined) {
        cuerpo.regulado = regulado;
      }
      if (motivo.trim()) {
        cuerpo.motivo = motivo;
      }
    }
    return cuerpo;
  }

  function cuerpoServicio() {
    const editar = abierto.accion === "editar";
    const modalidades = [];
    for (const modalidad of MODALIDADES) {
      const valor = document.getElementById(`precio-${modalidad.codigo}`).value;
      if (valor.trim() !== "") {
        modalidades.push({ modalidad: modalidad.codigo, precio_referencia: formato.leerEntero(valor) });
      }
    }
    const cuerpo = { nombre: document.getElementById("servicio-nombre").value, modalidades };
    const motivo = document.getElementById("servicio-motivo").value;
    if (editar) {
      cuerpo.version = abierto.version;
      cuerpo.motivo = motivo;
      const activo = leerRadio(formServicio, "activo");
      if (activo !== undefined) {
        cuerpo.activo = activo;
      }
    } else {
      cuerpo.oficio = abierto.oficio;
      if (motivo.trim()) {
        cuerpo.motivo = motivo;
      }
    }
    return cuerpo;
  }

  // 409: se conserva lo escrito. "Volver a cargar" lee el catálogo, muestra el
  // registro actual en la lista y toma su versión nueva; el formulario sigue
  // abierto con lo escrito para decidir si guardarlo de nuevo.
  function avisar409(form) {
    const recargar = boton("Volver a cargar", "boton-secundario", "", async () => {
      const estado = abierto;
      const { estado: codigo, datos } = await leerCatalogo();
      if (codigo === 401) {
        avisarSesionTerminada();
        return;
      }
      if (codigo === 403) {
        avisarSinRol();
        return;
      }
      if (codigo !== 200) {
        formulario.avisar(form, datos.mensaje, "error");
        return;
      }
      if (estado && estado.accion === "editar") {
        const actual = estado.tipo === "oficio" ? buscarOficio(estado.ref) : (buscarServicio(estado.ref) || {}).servicio;
        if (actual) {
          estado.version = actual.version;
        }
      }
      pintar();
      formulario.limpiarErrores(form);
      formulario.avisar(
        form,
        "Cargamos los datos actuales: revísalos en la lista. Lo que escribiste sigue aquí; si todavía quieres tu cambio, guárdalo de nuevo.",
        "exito"
      );
      form.querySelector(".aviso").setAttribute("tabindex", "-1");
      form.querySelector(".aviso").focus();
    });
    formulario.avisar(form, TEXTO_409, "error");
    form.querySelector(".aviso").append(" ", recargar);
  }

  async function enviar(form, prefijo, ruta, cuerpo, textoExito) {
    formulario.limpiarErrores(form);
    formulario.ocupado(form, true);
    const editar = abierto.accion === "editar";
    const { estado, datos } = editar
      ? await api.modificar(`${ruta}/${encodeURIComponent(abierto.ref)}`, cuerpo)
      : await api.enviar(ruta, cuerpo);
    formulario.ocupado(form, false);
    if (estado === 200 || estado === 201) {
      const registro = datos.oficio || datos.servicio;
      cerrarFormulario(false);
      const lectura = await leerCatalogo();
      pintar();
      const texto = textoExito(registro);
      avisar(avisoResultado, "exito", lectura.estado === 200 ? texto : `${texto} Toca «Reintentar» para ver la lista al día.`);
      if (lectura.estado !== 200) {
        avisoResultado.append(" ", boton("Reintentar", "", "", cargar));
      }
      return;
    }
    if (estado === 401) {
      avisarSesionTerminada();
      return;
    }
    if (estado === 403) {
      avisarSinRol();
      return;
    }
    if (estado === 409) {
      avisar409(form);
      return;
    }
    if (estado === 400) {
      const campo = formulario.mostrarErrores(form, conPrefijo(datos, prefijo));
      if (campo) {
        (campo.tagName === "FIELDSET" ? campo.querySelector("input") || campo : campo).focus();
      }
      return;
    }
    if (estado === 404) {
      formulario.avisar(form, "No encontramos este registro. Toca «Volver a cargar» para ver el catálogo al día.", "error");
      form.querySelector(".aviso").append(" ", boton("Volver a cargar", "boton-secundario", "", cargar));
      return;
    }
    // Sin conexión u otro error: el aviso y lo escrito se conserva.
    formulario.avisar(form, datos.mensaje, "error");
  }

  formOficio.addEventListener("submit", (evento) => {
    evento.preventDefault();
    if (!abierto || abierto.tipo !== "oficio") {
      return;
    }
    const editar = abierto.accion === "editar";
    enviar(formOficio, "oficio-", `${RUTA}/oficios`, cuerpoOficio(), (oficio) =>
      editar
        ? oficio.activo
          ? `Listo: guardaste los cambios del oficio «${oficio.nombre}».`
          : `Listo: el oficio «${oficio.nombre}» quedó dado de baja.`
        : `Listo: creaste el oficio «${oficio.nombre}». Ya puedes agregarle servicios.`
    );
  });

  formServicio.addEventListener("submit", (evento) => {
    evento.preventDefault();
    if (!abierto || abierto.tipo !== "servicio") {
      return;
    }
    const editar = abierto.accion === "editar";
    enviar(formServicio, "servicio-", `${RUTA}/servicios`, cuerpoServicio(), (servicio) =>
      editar
        ? servicio.activo
          ? `Listo: guardaste los cambios del servicio «${servicio.nombre}». Maestros y clientes ya ven los precios nuevos.`
          : `Listo: el servicio «${servicio.nombre}» quedó dado de baja.`
        : `Listo: creaste el servicio «${servicio.nombre}». Los maestros ya pueden ofrecerlo.`
    );
  });

  cargar();
})();
