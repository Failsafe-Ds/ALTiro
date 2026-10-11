// Mi perfil (RF-13 y RF-14 parciales, HU-12, HU-13; ADR-019, D-7; ADR-021).
// - GET /api/maestros/perfil: {"perfil": {ref, publicado, tiene_foto, pendientes}}.
//   Si el maestro está publicado y qué le falta lo decide el servidor; la
//   página solo muestra sus textos y un botón hacia la página que resuelve
//   cada pendiente.
// - POST /api/maestros/perfil/foto: multipart con la foto en "archivo"
//   (foto.js la achica en el teléfono; el servidor la valida y la recodifica).
//   Responde 201 con el perfil actualizado.
// - El maestro no recibe su propia foto antes de publicarse (propuesta S3,
//   §9, punto 5): solo "tiene_foto". Una vez publicado, se muestra la foto
//   pública (la misma que ven los clientes).
// RNF-14: botones grandes. RNF-15: errores junto al campo. RNF-16: estado con
// ícono y texto. RNF-17: lenguaje del oficio. RNF-20: la foto queda en memoria
// para reintentar si se corta la señal.
"use strict";

(() => {
  const RUTA = "/api/maestros/perfil";
  const RUTA_FOTO = "/api/maestros/perfil/foto";

  const MENSAJE_SIN_CONEXION = "No se pudo enviar tu foto. Revisa tu señal y toca «Reintentar». Tu foto sigue aquí.";
  const MENSAJE_PESADA = "La foto es muy pesada. Tómala de nuevo o elige otra.";

  // Respaldo por si el servidor no trae el texto de un pendiente (RNF-17).
  const TEXTOS_PENDIENTE = {
    postulacion_no_aprobada: "Tu postulación todavía no está aprobada.",
    sin_comuna_base: "Falta que elijas tu comuna principal.",
    sin_foto: "Falta que subas tu foto.",
    sin_servicio_visible: "Falta que ofrezcas al menos un servicio que los clientes puedan ver.",
  };
  // Página que resuelve cada pendiente; la foto se sube aquí mismo.
  const ACCIONES_PENDIENTE = {
    postulacion_no_aprobada: { texto: "Ir a mi postulación", href: "mi-postulacion.html" },
    sin_comuna_base: { texto: "Ir a mi cobertura", href: "mi-cobertura.html" },
    sin_servicio_visible: { texto: "Ir a mis servicios", href: "mis-servicios.html" },
    sin_foto: { texto: "Subir mi foto aquí", foto: true },
  };

  const cargando = document.getElementById("cargando");
  const avisoPagina = document.getElementById("aviso-pagina");
  const avisoResultado = document.getElementById("aviso-resultado");
  const contenido = document.getElementById("contenido");
  const formFoto = document.getElementById("form-foto");
  const botonFoto = document.getElementById("guardar-foto");
  const progresoFoto = document.getElementById("progreso-foto");
  const fotoActual = document.getElementById("foto-actual");

  let perfil = null;

  const selector = foto.crearSelector(document.getElementById("selector-foto"), {
    campo: "archivo",
    titulo: "Foto de tu cara",
    ayuda: "Una foto tuya, de frente y con buena luz. Los clientes la verán en tu perfil.",
    camara: "user",
    textoLista: "✓ Foto lista. Revisa que se vea bien tu cara y toca «Guardar mi foto».",
  });

  const elemento = dom.elemento;

  function icono(texto) {
    const nodo = elemento("span", "", texto);
    nodo.setAttribute("aria-hidden", "true");
    return nodo;
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

  function irAFoto() {
    const titulo = document.getElementById("titulo-foto");
    titulo.scrollIntoView();
    titulo.focus();
  }

  // --- Sesión y acceso ---

  function sesionTerminada() {
    contenido.hidden = true;
    limpiarResultado();
    selector.liberar();
    expediente.avisarSesionTerminada(avisoPagina, "perfil", "");
  }

  function sinAcceso() {
    contenido.hidden = true;
    selector.liberar();
    expediente.avisarNoMaestro(avisoPagina);
  }

  // --- Pintar ---

  function itemPendiente(pendiente) {
    const item = elemento("li", "aviso-vencimiento");
    const marca = elemento("span", "icono-aviso", "⚠");
    marca.setAttribute("aria-hidden", "true");
    const detalle = elemento("span", "detalle-aviso", pendiente.mensaje || TEXTOS_PENDIENTE[pendiente.codigo] || "");
    const accion = ACCIONES_PENDIENTE[pendiente.codigo];
    if (accion && accion.foto) {
      const boton = elemento("button", "boton boton-secundario", accion.texto);
      boton.type = "button";
      boton.addEventListener("click", irAFoto);
      detalle.append(boton);
    } else if (accion) {
      const enlace = elemento("a", "boton boton-secundario", accion.texto);
      enlace.href = accion.href;
      detalle.append(enlace);
    }
    item.append(marca, detalle);
    return item;
  }

  function pintar() {
    const seccion = document.getElementById("seccion-estado");
    const titulo = document.getElementById("titulo-estado");
    seccion.classList.toggle("avisos", !perfil.publicado);
    seccion.classList.toggle("estado-publicado", perfil.publicado);
    if (perfil.publicado) {
      titulo.replaceChildren(icono("✓ "), "Los clientes ya pueden ver tu perfil");
      document.getElementById("ver-publico").href = `perfil-maestro.html?m=${encodeURIComponent(perfil.ref)}`;
    } else {
      titulo.replaceChildren(icono("⚠ "), "Todavía no te ven los clientes");
    }
    document.getElementById("estado-publicado").hidden = !perfil.publicado;
    document.getElementById("estado-pendiente").hidden = perfil.publicado;
    document.getElementById("lista-pendientes").replaceChildren(...(perfil.pendientes || []).map(itemPendiente));

    // Foto: el maestro solo ve la foto pública cuando ya está publicado.
    const textoFoto = document.getElementById("foto-estado-texto");
    if (perfil.tiene_foto) {
      textoFoto.replaceChildren(
        elemento("span", "estado estado-aprobado", icono("✓"), " Ya subiste tu foto"),
        perfil.publicado ? "" : " Los clientes la verán cuando tu perfil esté completo."
      );
    } else {
      textoFoto.replaceChildren(
        elemento("span", "estado estado-rechazado", icono("✕"), " Falta tu foto"),
        " Sin foto los clientes no te ven."
      );
    }
    if (perfil.publicado && perfil.tiene_foto) {
      fotoActual.src = `/api/maestros/publicos/${encodeURIComponent(perfil.ref)}/foto?tam=160`;
      fotoActual.alt = "Tu foto de perfil, tal como la ven los clientes";
      fotoActual.hidden = false;
    } else {
      fotoActual.removeAttribute("src");
      fotoActual.alt = "";
      fotoActual.hidden = true;
    }
    const textoBoton = perfil.tiene_foto ? "Guardar mi foto nueva" : "Guardar mi foto";
    botonFoto.textContent = textoBoton;
    botonFoto.dataset.texto = textoBoton;
  }

  // --- Carga ---

  async function cargar() {
    expediente.limpiarAviso(avisoPagina);
    cargando.hidden = false;
    const { estado, datos } = await api.obtener(RUTA);
    cargando.hidden = true;
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 403) {
      sinAcceso();
      return;
    }
    if (estado !== 200) {
      contenido.hidden = true;
      expediente.avisarErrorCarga(avisoPagina, datos.mensaje, cargar);
      return;
    }
    perfil = datos.perfil;
    pintar();
    pintarDescripcion();
    contenido.hidden = false;
  }

  // --- «Sobre mí» (DA-30) ---
  // Borrador en sessionStorage mientras se escribe (se borra al guardar o al
  // cerrar sesión). El servidor recorta y valida el largo; aquí solo se ayuda.
  const MAXIMO = 500;
  const CLAVE_BORRADOR = "altiro.mi-perfil.descripcion";
  const formSobreMi = document.getElementById("form-sobre-mi");
  const campoDescripcion = document.getElementById("descripcion");
  const contador = document.getElementById("contador-descripcion");
  const anuncio = document.getElementById("anuncio-descripcion");
  // El contador se ve siempre; al lector de pantalla solo se le avisa en
  // algunos umbrales, para no anunciar cada tecla.
  const UMBRALES = [100, 50, 20, 0];
  let ultimoUmbral = null;

  function contar() {
    const quedan = MAXIMO - campoDescripcion.value.length;
    contador.textContent = quedan === 1 ? "Te queda 1 carácter." : `Te quedan ${quedan} caracteres.`;
    const umbral = [...UMBRALES].reverse().find((u) => quedan <= u);
    if (umbral !== undefined && umbral !== ultimoUmbral) {
      anuncio.textContent = contador.textContent;
    }
    ultimoUmbral = umbral === undefined ? null : umbral;
  }

  function pintarDescripcion() {
    const guardada = perfil.descripcion || "";
    const borrador = formulario.recuperar(CLAVE_BORRADOR);
    const texto = borrador && borrador.valores ? borrador.valores.descripcion : undefined;
    if (typeof texto === "string" && texto !== guardada) {
      campoDescripcion.value = texto;
      formulario.avisar(formSobreMi, "Recuperamos lo que estabas escribiendo. Todavía no está guardado: revísalo y toca «Guardar «Sobre mí»».", "exito");
    } else {
      campoDescripcion.value = guardada;
      formulario.olvidar(CLAVE_BORRADOR);
    }
    contar();
  }

  campoDescripcion.addEventListener("input", () => {
    contar();
    formulario.guardarDatos(CLAVE_BORRADOR, { valores: { descripcion: campoDescripcion.value } });
  });

  formulario.prepararBoton(formSobreMi);
  formSobreMi.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(formSobreMi);
    const texto = formulario.valor(campoDescripcion);
    campoDescripcion.value = texto;
    contar();
    formulario.ocupado(formSobreMi, true, "Guardando…");
    const { estado, datos } = await api.reemplazar(RUTA, { descripcion: texto });
    formulario.ocupado(formSobreMi, false);
    if (estado === 200) {
      perfil = datos.perfil;
      formulario.olvidar(CLAVE_BORRADOR);
      // El campo muestra lo guardado (no se vacía: es el texto vigente del perfil).
      campoDescripcion.value = perfil.descripcion || "";
      contar();
      formulario.avisar(
        formSobreMi,
        perfil.descripcion ? "Listo: guardamos tu «Sobre mí». Los clientes lo ven en tu perfil." : "Listo: borramos tu «Sobre mí».",
        "exito"
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
    if (estado === 0) {
      formulario.avisar(formSobreMi, "No pudimos conectarnos. Revisa tu señal o tu wifi y toca «Guardar «Sobre mí»» de nuevo. Lo que escribiste sigue aquí.", "error");
      return;
    }
    // Error del servidor: se conserva lo escrito y se marca el campo.
    const campo = formulario.mostrarErrores(formSobreMi, datos);
    if (campo) {
      campo.focus();
    }
  });

  // --- Subir o cambiar la foto (ADR-021) ---

  function textoEnvio(fraccion) {
    return fraccion >= 1 ? "Revisando la foto…" : `Enviando foto… ${Math.floor(fraccion * 10) * 10} %`;
  }

  formFoto.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(formFoto);
    limpiarResultado();
    progresoFoto.textContent = "";
    if (!(await selector.lista())) {
      formulario.mostrarErrores(formFoto, {
        mensaje: "Falta la foto.",
        errores: { archivo: "Toma una foto o elige una de la galería." },
      });
      selector.enfocar();
      return;
    }
    const envio = new FormData();
    envio.append("archivo", selector.blob(), "foto.jpg");
    formulario.ocupado(formFoto, true);
    progresoFoto.textContent = textoEnvio(0);
    let ultimo = "";
    const { estado, datos } = await api.enviarArchivo(RUTA_FOTO, envio, (fraccion) => {
      const texto = textoEnvio(fraccion);
      if (texto !== ultimo) {
        ultimo = texto;
        progresoFoto.textContent = texto;
      }
    });
    formulario.ocupado(formFoto, false);
    progresoFoto.textContent = "";

    if (estado === 201) {
      perfil = datos.perfil;
      selector.liberar();
      pintar();
      avisarResultado(
        "Listo: guardamos tu foto." + (perfil.publicado ? " Los clientes ya la ven." : " Revisa arriba lo que te falta para que te vean los clientes.")
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
    if (estado === 0) {
      // La foto sigue en memoria: se reintenta con el mismo botón.
      botonFoto.textContent = "Reintentar";
      formulario.avisar(formFoto, MENSAJE_SIN_CONEXION, "error");
      return;
    }
    if (estado === 413) {
      formulario.avisar(formFoto, datos.mensaje || MENSAJE_PESADA, "error");
      return;
    }
    if (estado === 400) {
      const campo = formulario.mostrarErrores(formFoto, datos);
      if (campo) {
        campo.focus();
      }
      return;
    }
    // 409 (postulación no aprobada) u otro error: el aviso del servidor; la foto sigue aquí.
    formulario.avisar(formFoto, datos.mensaje, "error");
    if (estado >= 500) {
      botonFoto.textContent = "Reintentar";
    }
  });

  cargar();
})();
