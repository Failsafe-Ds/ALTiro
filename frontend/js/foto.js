// Selector de fotos de documentos (RF-04, HU-11; ADR-015; RNF-14, RNF-17, NTI-11).
// - Dos botones grandes: "Tomar foto" (abre la cámara trasera) y "Elegir de la
//   galería". Un solo <input type="file"> por foto: el atributo capture se pone
//   o se quita justo antes de abrirlo.
// - La foto se achica en el teléfono antes de enviarla (lado mayor de unos
//   2000 px, JPEG de calidad 0,8; ADR-015, D-5): pesa menos con señal débil.
//   El servidor vuelve a validar y recodificar todo: esto es solo comodidad.
// - Vista previa como data: (la CSP permite img-src 'self' data:, no blob:),
//   en tamaño reducido para no gastar memoria.
// - La foto queda en memoria (nunca en el almacenamiento del navegador) hasta
//   enviarla, para poder reintentar si falla la conexión. liberar() la suelta.
"use strict";

const foto = (() => {
  const LADO_MAYOR = 2000;
  const CALIDAD = 0.8;
  const LADO_VISTA = 480;

  const MENSAJE_ILEGIBLE = "No pudimos abrir esa foto. Toma la foto de nuevo o elige otra de la galería.";

  // Decodifica la imagen aplicando la orientación de la cámara.
  async function decodificar(archivo) {
    if (typeof createImageBitmap === "function") {
      try {
        return await createImageBitmap(archivo, { imageOrientation: "from-image" });
      } catch (error) {
        // Se intenta con <img> más abajo.
      }
    }
    const url = await new Promise((resolver, rechazar) => {
      const lector = new FileReader();
      lector.onload = () => resolver(lector.result);
      lector.onerror = () => rechazar(lector.error);
      lector.readAsDataURL(archivo);
    });
    return new Promise((resolver, rechazar) => {
      const imagen = new Image();
      imagen.onload = () => resolver(imagen);
      imagen.onerror = () => rechazar(new Error("imagen ilegible"));
      imagen.src = url;
    });
  }

  function dibujar(fuente, ancho, alto, ladoMaximo) {
    const escala = Math.min(1, ladoMaximo / Math.max(ancho, alto));
    const lienzo = document.createElement("canvas");
    lienzo.width = Math.max(1, Math.round(ancho * escala));
    lienzo.height = Math.max(1, Math.round(alto * escala));
    const contexto = lienzo.getContext("2d");
    // Fondo blanco: una foto con transparencia no queda negra en JPEG.
    contexto.fillStyle = "#ffffff";
    contexto.fillRect(0, 0, lienzo.width, lienzo.height);
    contexto.drawImage(fuente, 0, 0, lienzo.width, lienzo.height);
    return lienzo;
  }

  function vaciarLienzo(lienzo) {
    lienzo.width = 0;
    lienzo.height = 0;
  }

  // Devuelve { blob, vista } o lanza un Error si la foto no se pudo leer.
  async function comprimir(archivo) {
    const imagen = await decodificar(archivo);
    const ancho = imagen.width || imagen.naturalWidth;
    const alto = imagen.height || imagen.naturalHeight;
    if (!ancho || !alto) {
      throw new Error("imagen vacía");
    }
    const grande = dibujar(imagen, ancho, alto, LADO_MAYOR);
    const blob = await new Promise((resolver) => grande.toBlob(resolver, "image/jpeg", CALIDAD));
    vaciarLienzo(grande);
    const chica = dibujar(imagen, ancho, alto, LADO_VISTA);
    const vista = chica.toDataURL("image/jpeg", 0.7);
    vaciarLienzo(chica);
    if (typeof imagen.close === "function") {
      imagen.close();
    } else {
      imagen.removeAttribute("src");
    }
    if (!blob) {
      throw new Error("no se pudo generar la foto");
    }
    return { blob, vista };
  }

  function crearElemento(etiqueta, atributos = {}, texto = "") {
    const elemento = document.createElement(etiqueta);
    for (const [nombre, valor] of Object.entries(atributos)) {
      elemento.setAttribute(nombre, valor);
    }
    if (texto) {
      elemento.textContent = texto;
    }
    return elemento;
  }

  // Crea un selector dentro de "contenedor".
  // opciones: { campo, titulo, ayuda }. "campo" es el nombre que usa la API
  // ("archivo" o "archivo_reverso"): el error del servidor se muestra en
  // #error-<campo>, junto a los botones (formulario.mostrarErrores).
  function crearSelector(contenedor, { campo, titulo, ayuda }) {
    const idTitulo = `titulo-${campo}`;
    const idError = `error-${campo}`;
    const idAyuda = `ayuda-${campo}`;
    const grupo = crearElemento("div", { class: "campo foto", role: "group", "aria-labelledby": idTitulo });
    const etiqueta = crearElemento("p", { class: "etiqueta", id: idTitulo }, titulo);
    const textoAyuda = crearElemento("span", { class: "ayuda", id: idAyuda }, ayuda);
    const vista = crearElemento("img", { class: "vista-previa", alt: "", hidden: "" });
    const estado = crearElemento("p", { class: "foto-estado", role: "status" });
    const botones = crearElemento("div", { class: "foto-botones" });
    const camara = crearElemento("button", {
      type: "button",
      class: "boton-secundario",
      "aria-describedby": `${idAyuda} ${idError}`,
    });
    const galeria = crearElemento("button", { type: "button", class: "boton-secundario" });
    const entrada = crearElemento("input", { type: "file", accept: "image/*", hidden: "", id: `entrada-${campo}` });
    const error = crearElemento("span", { class: "error-campo", id: idError });
    botones.append(camara, galeria);
    grupo.append(etiqueta, textoAyuda, vista, estado, botones, entrada, error);
    contenedor.append(grupo);

    let blob = null;
    let preparando = null;

    // El ícono es decorativo: el lector de pantalla lee solo el texto.
    function rotular(boton, icono, texto) {
      boton.replaceChildren(crearElemento("span", { "aria-hidden": "true", class: "icono" }, icono), texto);
    }

    function pintar() {
      const hay = Boolean(blob);
      vista.hidden = !hay;
      rotular(camara, "📷", hay ? "Tomar otra foto" : "Tomar foto");
      rotular(galeria, "🖼", hay ? "Elegir otra de la galería" : "Elegir de la galería");
    }

    function abrir(conCamara) {
      if (conCamara) {
        entrada.setAttribute("capture", "environment");
      } else {
        entrada.removeAttribute("capture");
      }
      entrada.value = "";
      entrada.click();
    }

    camara.addEventListener("click", () => abrir(true));
    galeria.addEventListener("click", () => abrir(false));

    entrada.addEventListener("change", () => {
      const archivo = entrada.files && entrada.files[0];
      if (!archivo) {
        return;
      }
      error.textContent = "";
      grupo.classList.remove("foto-con-error");
      estado.textContent = "Preparando la foto…";
      preparando = comprimir(archivo)
        .then((resultado) => {
          blob = resultado.blob;
          vista.src = resultado.vista;
          vista.alt = `Vista previa: ${titulo.toLowerCase()}`;
          estado.textContent = "✓ Foto lista. Revisa que se lean todas las letras.";
          grupo.dispatchEvent(new CustomEvent("foto-lista", { bubbles: true }));
        })
        .catch(() => {
          estado.textContent = "";
          error.textContent = MENSAJE_ILEGIBLE;
          grupo.classList.add("foto-con-error");
        })
        .finally(() => {
          // El archivo original no se conserva: solo la versión achicada.
          entrada.value = "";
          preparando = null;
          pintar();
        });
    });

    pintar();

    return {
      campo,
      // Espera a que termine de prepararse una foto recién elegida.
      async lista() {
        if (preparando) {
          await preparando;
        }
        return Boolean(blob);
      },
      blob: () => blob,
      enfocar: () => camara.focus(),
      mostrarError(texto) {
        error.textContent = texto;
        grupo.classList.add("foto-con-error");
      },
      // Suelta la foto de la memoria (al enviarla con éxito o al salir).
      liberar() {
        blob = null;
        vista.removeAttribute("src");
        vista.alt = "";
        estado.textContent = "";
        error.textContent = "";
        grupo.classList.remove("foto-con-error");
        pintar();
      },
      quitar() {
        this.liberar();
        grupo.remove();
      },
    };
  }

  return { crearSelector, comprimir };
})();
