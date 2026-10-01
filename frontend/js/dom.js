// Ayudas para crear nodos, compartidas por las páginas (antes había una copia
// idéntica en cada script).
// - elemento(etiqueta, clase, ...hijos): nodo con clase opcional y sus hijos
//   (texto o nodos). Nunca usa innerHTML: el texto del servidor se agrega como texto.
// - opcion(valor, texto): <option> de un <select>.
// - enlaceInterno(valor, rutas): devuelve "ruta?consulta#fragmento" solo si
//   "valor" es del mismo origen y su ruta exacta está en la lista cerrada
//   "rutas"; si no, null. Para enlaces que llegan del servidor (avisos,
//   hallazgo B-4): evita "javascript:", "//otro-sitio" y rutas parecidas.
"use strict";

const dom = (() => {
  function elemento(etiqueta, clase, ...hijos) {
    const nodo = document.createElement(etiqueta);
    if (clase) {
      nodo.className = clase;
    }
    nodo.append(...hijos);
    return nodo;
  }

  function opcion(valor, texto) {
    const nodo = document.createElement("option");
    nodo.value = valor;
    nodo.textContent = texto;
    return nodo;
  }

  function enlaceInterno(valor, rutas) {
    if (typeof valor !== "string" || !valor) {
      return null;
    }
    let url;
    try {
      url = new URL(valor, window.location.origin);
    } catch (error) {
      return null;
    }
    if (url.origin !== window.location.origin || !rutas.includes(url.pathname)) {
      return null;
    }
    return url.pathname + url.search + url.hash;
  }

  return { elemento, opcion, enlaceInterno };
})();
