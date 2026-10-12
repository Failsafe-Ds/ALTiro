// Categorías (oficios): inicio del cliente al estilo Fiverr (ADR-002 E-3,
// punto 7; MASTER, «Categorías»). Es la entrada a la búsqueda (HU-02, RF-09),
// no una funcionalidad nueva.
// - GET /api/oficios (pública): { oficios: [{ codigo, nombre, regulado }] }.
// - Cada oficio enlaza a buscar.html?oficio=<código>; buscar.js lo deja
//   elegido solo si está en la lista del catálogo y pide la comuna.
// Estados: cargando (texto con aria-live), error con «Reintentar» (sin señal o
// falla del servidor) y sin datos.
"use strict";

(() => {
  const SIN_SENAL = "Revisa tu señal o tu wifi y toca «Reintentar».";
  const cargando = document.getElementById("cargando-categorias");
  const aviso = document.getElementById("aviso-categorias");
  const lista = document.getElementById("lista-categorias");
  const carrusel = document.getElementById("carrusel-categorias");
  const controles = carrusel.querySelector(".carrusel-controles");
  const puntos = document.getElementById("carrusel-indicadores");
  const estadoCarrusel = document.getElementById("carrusel-estado");
  const elemento = dom.elemento;

  function avisarError(estado) {
    const boton = elemento("button", "boton-secundario", "Reintentar");
    boton.type = "button";
    boton.addEventListener("click", cargar);
    aviso.className = "aviso aviso-error angosto";
    aviso.replaceChildren(
      `No pudimos cargar los oficios. ${estado === 0 ? SIN_SENAL : "Toca «Reintentar» en un momento."}`,
      " ",
      boton
    );
    aviso.focus();
  }

  function categoria(oficio) {
    const enlace = elemento(
      "a",
      "enlace-categoria",
      elemento("span", "icono-categoria", iconos.crear(iconos.deOficio(oficio.codigo))),
      elemento("span", "nombre-categoria", oficio.nombre)
    );
    enlace.href = `buscar.html?oficio=${encodeURIComponent(oficio.codigo)}`;
    enlace.append(" ", elemento("span", "ver-maestros", "Ver maestros"));
    return elemento("li", "", enlace);
  }

  async function cargar() {
    aviso.className = "aviso angosto";
    aviso.replaceChildren();
    cargando.textContent = "Cargando oficios…";
    cargando.hidden = false;
    const { estado, datos } = await api.obtener("/api/oficios");
    cargando.textContent = "";
    cargando.hidden = true;
    if (estado !== 200) {
      carrusel.hidden = true;
      avisarError(estado);
      return;
    }
    const oficios = Array.isArray(datos.oficios) ? datos.oficios : [];
    if (!oficios.length) {
      carrusel.hidden = true;
      aviso.className = "aviso sin-resultados angosto";
      aviso.textContent = "Por ahora no hay oficios disponibles. Vuelve a intentarlo más tarde.";
      return;
    }
    const total = armar(oficios.map(categoria));
    carrusel.hidden = false;
    const instancia = bootstrap.Carousel.getOrCreateInstance(carrusel, { interval: false, ride: false, touch: true, wrap: true, keyboard: true });
    instancia.to(0);
    carrusel.addEventListener("slid.bs.carousel", (evento) => anunciar(evento.to, total));
  }

  // --- Carrusel (ADR-002 E-3.3 y E-4) ---
  // Carrusel de Bootstrap: diapositivas de a POR_DIAPOSITIVA oficios (3: los 9
  // del catálogo quedan en 3 diapositivas parejas, en celular y en PC). Sin
  // avance automático (interval: false); con el dedo (touch) y dando la vuelta
  // al final (wrap). Bootstrap oculta las diapositivas inactivas, así que Tab
  // solo recorre los oficios a la vista. El aviso para lectores dice cuáles son.
  const POR_DIAPOSITIVA = 3;

  function armar(items) {
    const diapositivas = [];
    for (let i = 0; i < items.length; i += POR_DIAPOSITIVA) {
      const grupo = items.slice(i, i + POR_DIAPOSITIVA);
      const ul = elemento("ul", "lista-categorias", ...grupo);
      const diapositiva = elemento("div", i === 0 ? "carousel-item active" : "carousel-item", ul);
      diapositiva.setAttribute("role", "group");
      diapositiva.setAttribute("aria-roledescription", "diapositiva");
      diapositiva.setAttribute("aria-label", `${diapositivas.length + 1} de ${Math.ceil(items.length / POR_DIAPOSITIVA)}`);
      diapositivas.push(diapositiva);
    }
    lista.replaceChildren(...diapositivas);
    puntos.replaceChildren(
      ...diapositivas.map((_, i) => {
        const punto = elemento("button", i === 0 ? "active" : "");
        punto.type = "button";
        punto.dataset.bsTarget = "#carrusel-categorias";
        punto.dataset.bsSlideTo = String(i);
        punto.setAttribute("aria-label", `Ver oficios, parte ${i + 1} de ${diapositivas.length}`);
        if (i === 0) punto.setAttribute("aria-current", "true");
        return punto;
      })
    );
    // Con una sola diapositiva no hay nada que pasar: se ocultan los controles.
    controles.hidden = diapositivas.length < 2;
    return items.length;
  }

  function anunciar(indice, total) {
    const primero = indice * POR_DIAPOSITIVA + 1;
    const ultimo = Math.min(total, primero + POR_DIAPOSITIVA - 1);
    estadoCarrusel.textContent = `Oficios ${primero} a ${ultimo} de ${total}.`;
  }

  cargar();
})();
