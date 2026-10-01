// Ayudas para crear nodos, compartidas por las páginas (antes había una copia
// idéntica en cada script).
// - elemento(etiqueta, clase, ...hijos): nodo con clase opcional y sus hijos
//   (texto o nodos). Nunca usa innerHTML: el texto del servidor se agrega como texto.
// - opcion(valor, texto): <option> de un <select>.
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

  return { elemento, opcion };
})();
