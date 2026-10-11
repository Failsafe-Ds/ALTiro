// Íconos SVG propios (MASTER: SVG en línea, nunca emoji ni archivos de otros
// dominios). Se crean con createElementNS, sin innerHTML. Siempre acompañan a
// un texto, así que van con aria-hidden="true" y focusable="false".
// - iconos.crear(nombre, clase): <svg> de 24 x 24 que toma el color del texto.
// - iconos.deOficio(codigo): nombre del ícono de un oficio del catálogo, o el
//   genérico si el oficio no tiene uno propio (un oficio nuevo no rompe nada).
"use strict";

const iconos = (() => {
  const SVG = "http://www.w3.org/2000/svg";
  const TRAZOS = {
    estrella: "M12 2.5l2.9 6 6.6.8-4.9 4.5 1.3 6.5L12 17.1l-5.9 3.2 1.3-6.5L2.5 9.3l6.6-.8z",
    verificado: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm-1.2 14.2-4.3-4.3 1.4-1.4 2.9 2.9 5.7-5.7 1.4 1.4z",
    rayo: "M13.5 2 4 14h6.5l-1 8L19 10h-6.5z",
    llama: "M12 2c1 3.5 5.5 6 5.5 11.5a5.5 5.5 0 0 1-11 0c0-2.4 1.1-4.1 2.4-5.4.1 1.7.9 3 2.1 3.6C10.4 8.9 10.9 5.5 12 2z",
    gota: "M12 2.5S5 10.2 5 15a7 7 0 0 0 14 0c0-4.8-7-12.5-7-12.5zm-3 12h2a1.5 1.5 0 0 0 1.5 1.5v2A3.5 3.5 0 0 1 9 14.5z",
    martillo: "M13.5 2.5 21 6.2l-1 2-3-1.5-1.6 1.6 1.4 1.4-1.4 1.4-1.4-1.4-8.6 8.6a2 2 0 0 1-2.8-2.8l8.6-8.6-1.4-1.4L11.2 4z",
    rodillo: "M4 3h13a1 1 0 0 1 1 1v1h2.5v6.5h-8V14h1v7.5h-4V14h1v-4.5h8V7H18v1a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z",
    ladrillos: "M2 4h9v4.5H2zm11 0h9v4.5h-9zM2 10.5h4.5V15H2zm6.5 0h7V15h-7zm9 0H22V15h-4.5zM2 17h9v4.5H2zm11 0h9v4.5h-9z",
    llave: "M7.5 6a6 6 0 1 0 5.6 8H15v2.5h2.5V14H19v3h2.5v-5h-8.4A6 6 0 0 0 7.5 6zm0 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5z",
    hoja: "M20.5 3C11 3 4.5 7.5 4.5 15c0 1.6.4 3 1 4.1L3 21.6 4.4 23l2.5-2.5c1.1.6 2.5 1 4.1 1C18 21.5 21 13 20.5 3zM8.2 18.6C10 14.5 13 11 17 8.5c-3 3.2-5.5 6.6-7.3 10.6z",
    casa: "M12 3 2 11.5h3V21h5.5v-6h3v6H19v-9.5h3z",
    herramienta: "M21 7.5a5.5 5.5 0 0 1-7.4 5.2L6 20.3a2.1 2.1 0 0 1-3-3l7.6-7.6A5.5 5.5 0 0 1 17.5 2l-3.3 3.3.9 3.6 3.6.9z",
  };
  // Códigos del catálogo público (GET /api/oficios). Solo presentación.
  const POR_OFICIO = {
    gas: "llama",
    electricidad: "rayo",
    gasfiteria: "gota",
    carpinteria: "martillo",
    pintura: "rodillo",
    albanileria: "ladrillos",
    cerrajeria: "llave",
    jardineria: "hoja",
    otros: "casa",
  };

  function crear(nombre, clase) {
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("class", clase ? `icono-svg ${clase}` : "icono-svg");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    const trazo = document.createElementNS(SVG, "path");
    trazo.setAttribute("d", TRAZOS[nombre] || TRAZOS.herramienta);
    trazo.setAttribute("fill-rule", "evenodd");
    svg.append(trazo);
    return svg;
  }

  function deOficio(codigo) {
    return Object.prototype.hasOwnProperty.call(POR_OFICIO, codigo) ? POR_OFICIO[codigo] : "herramienta";
  }

  return { crear, deOficio };
})();
