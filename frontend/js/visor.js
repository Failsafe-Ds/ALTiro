// Visor de fotos de documentos, compartido por "Mis documentos" (maestro) y
// la revisión de curatoría (RNF-06; ADR-015; ADR-017, E-3).
// - Cada foto se abre con un enlace temporal de 10 minutos que entrega el
//   servidor. El enlace se guarda solo en memoria y, si caducó o la imagen no
//   carga, se pide otro una vez.
// - Usa el <dialog id="visor"> de la página, con los ids titulo-visor,
//   estado-visor, imagen-visor, visor-otra-cara y visor-cerrar.
// - Quién puede abrir cada foto lo decide el servidor; aquí no hay reglas.
"use strict";

const visorFotos = (() => {
  // Margen para no usar un enlace a punto de caducar.
  const MARGEN_MS = 20 * 1000;

  function textoCara(cara) {
    return cara === "anverso" ? "frente" : "parte de atrás";
  }

  // La API de curatoría informa si hay foto de atrás; la del maestro no, y ahí
  // solo la cédula tiene dos fotos.
  function tieneReverso(documento) {
    return typeof documento.tiene_reverso === "boolean"
      ? documento.tiene_reverso
      : documento.tipo === "cedula_identidad";
  }

  // opciones.rutaEnlace(ref, cara): ruta de la API que entrega { url, caduca_en }.
  // opciones.alSesionTerminada(): la sesión terminó (401).
  function crear(opciones) {
    const visor = document.getElementById("visor");
    const tituloVisor = document.getElementById("titulo-visor");
    const estadoVisor = document.getElementById("estado-visor");
    const imagenVisor = document.getElementById("imagen-visor");
    const otraCara = document.getElementById("visor-otra-cara");
    const botonCerrar = document.getElementById("visor-cerrar");

    // Hallazgo UX T-11: si la foto no carga, el visor ofrece la acción en un
    // botón ("Reintentar" o "Volver a cargar") en vez de pedir "recarga la página".
    const reintentar = document.createElement("button");
    reintentar.type = "button";
    reintentar.className = "boton-secundario";
    reintentar.hidden = true;
    botonCerrar.parentElement.prepend(reintentar);
    let accionReintentar = null;

    function ofrecer(texto, accion) {
      reintentar.textContent = texto;
      reintentar.hidden = false;
      accionReintentar = accion;
    }

    function ocultarReintentar() {
      reintentar.hidden = true;
      accionReintentar = null;
    }

    reintentar.addEventListener("click", () => {
      const accion = accionReintentar;
      ocultarReintentar();
      if (accion) {
        accion();
      }
    });

    // "ref:cara" => { url, caduca }. Solo en memoria.
    const enlaces = new Map();
    let fotoAbierta = null; // { documento, nombre, cara, reintentado }
    let origenFoco = null;

    async function pedirEnlace(ref, cara) {
      const clave = `${ref}:${cara}`;
      const guardado = enlaces.get(clave);
      if (guardado && Date.now() < guardado.caduca - MARGEN_MS) {
        return { estado: 200, url: guardado.url };
      }
      enlaces.delete(clave);
      const { estado, datos } = await api.obtener(opciones.rutaEnlace(ref, cara));
      if (estado !== 200) {
        return { estado, mensaje: datos.mensaje };
      }
      const caduca = Date.parse(datos.caduca_en);
      enlaces.set(clave, { url: datos.url, caduca: Number.isNaN(caduca) ? 0 : caduca });
      return { estado, url: datos.url };
    }

    async function mostrarFoto() {
      const { documento, nombre, cara } = fotoAbierta;
      const dosCaras = tieneReverso(documento);
      tituloVisor.textContent = dosCaras ? `${nombre}: ${textoCara(cara)}` : nombre;
      imagenVisor.hidden = true;
      imagenVisor.removeAttribute("src");
      ocultarReintentar();
      estadoVisor.textContent = "Cargando la foto…";
      otraCara.classList.toggle("oculto", !dosCaras);
      otraCara.textContent = cara === "anverso" ? "Ver la parte de atrás" : "Ver el frente";

      const resultado = await pedirEnlace(documento.ref, cara);
      if (!fotoAbierta || fotoAbierta.cara !== cara || fotoAbierta.documento !== documento) {
        return; // Se cerró o se cambió de foto mientras cargaba.
      }
      if (resultado.estado === 401) {
        cerrar();
        opciones.alSesionTerminada();
        return;
      }
      if (resultado.estado === 404) {
        // El documento cambió (por ejemplo, se subió otro): se vuelve a cargar la página.
        estadoVisor.textContent =
          "No encontramos esta foto. Puede que el documento haya cambiado. Toca «Volver a cargar» para ver los documentos actualizados.";
        ofrecer("Volver a cargar", () => location.reload());
        return;
      }
      if (resultado.estado !== 200) {
        estadoVisor.textContent = resultado.mensaje;
        ofrecer("Reintentar", () => {
          fotoAbierta.reintentado = false;
          mostrarFoto();
        });
        return;
      }
      imagenVisor.alt = `Foto de ${nombre}${dosCaras ? `, ${textoCara(cara)}` : ""}`;
      imagenVisor.src = resultado.url;
    }

    imagenVisor.addEventListener("load", () => {
      estadoVisor.textContent = "";
      imagenVisor.hidden = false;
    });

    // Documento eliminado o archivo ilegible (OBS-S5-06): el servidor responde
    // 409 con un mensaje accionable que <img> no puede leer. Se consulta el
    // mismo enlace para mostrarlo; cualquier otra respuesta devuelve null.
    async function mensajeConflicto(url) {
      try {
        const respuesta = await fetch(url, { credentials: "same-origin", cache: "no-store" });
        if (respuesta.status !== 409) {
          return null;
        }
        const datos = await respuesta.json();
        return typeof datos.mensaje === "string" ? datos.mensaje : null;
      } catch {
        return null;
      }
    }

    // Enlace caducado o conexión cortada: se pide un enlace nuevo una sola vez.
    imagenVisor.addEventListener("error", async () => {
      const url = imagenVisor.getAttribute("src");
      if (!fotoAbierta || !url) {
        return;
      }
      const abierta = fotoAbierta;
      const mensaje = await mensajeConflicto(url);
      if (fotoAbierta !== abierta || imagenVisor.getAttribute("src") !== url) {
        return; // Se cerró o se cambió de foto mientras se consultaba.
      }
      if (mensaje) {
        // Reintentar no sirve: hay que volver a cargar el documento.
        imagenVisor.removeAttribute("src");
        estadoVisor.textContent = mensaje;
        return;
      }
      enlaces.delete(`${fotoAbierta.documento.ref}:${fotoAbierta.cara}`);
      if (!fotoAbierta.reintentado) {
        fotoAbierta.reintentado = true;
        mostrarFoto();
        return;
      }
      imagenVisor.removeAttribute("src");
      estadoVisor.textContent = "No pudimos mostrar la foto. Revisa tu señal o tu wifi y toca «Reintentar».";
      ofrecer("Reintentar", () => {
        fotoAbierta.reintentado = false;
        mostrarFoto();
      });
    });

    function abrir(documento, nombre, cara, boton) {
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
      botonCerrar.focus();
    }

    function cerrar() {
      fotoAbierta = null;
      ocultarReintentar();
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
    botonCerrar.addEventListener("click", cerrar);
    // Tecla Escape: el navegador cierra el diálogo; se limpia igual.
    visor.addEventListener("close", () => {
      if (fotoAbierta) {
        cerrar();
      }
    });

    return { abrir, cerrar };
  }

  return { crear, tieneReverso };
})();
