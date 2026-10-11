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
  const controles = document.getElementById("carrusel-controles");
  const anterior = document.getElementById("carrusel-anterior");
  const siguiente = document.getElementById("carrusel-siguiente");
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
    lista.replaceChildren(...oficios.map(categoria));
    carrusel.hidden = false;
    actualizar();
  }

  // --- Carrusel (ADR-002 E-3.3) ---
  // En los extremos el botón queda con aria-disabled (sigue enfocable, para no
  // perder el foco) y el aviso lo dice. Con prefers-reduced-motion, sin animación.
  const sinMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)");
  let anunciar = false;

  function visibles() {
    const caja = lista.getBoundingClientRect();
    const items = Array.from(lista.children);
    const dentro = items
      .map((item, i) => [i, item.getBoundingClientRect()])
      .filter(([, r]) => r.left >= caja.left - 2 && r.right <= caja.right + 2)
      .map(([i]) => i);
    return { primero: dentro.length ? dentro[0] + 1 : 1, ultimo: dentro.length ? dentro[dentro.length - 1] + 1 : 1, total: items.length };
  }

  function actualizar() {
    const sobra = lista.scrollWidth - lista.clientWidth;
    controles.hidden = sobra <= 1;
    const alInicio = lista.scrollLeft <= 1;
    const alFinal = lista.scrollLeft >= sobra - 1;
    anterior.setAttribute("aria-disabled", String(alInicio));
    siguiente.setAttribute("aria-disabled", String(alFinal));
    if (anunciar) {
      anunciar = false;
      const { primero, ultimo, total } = visibles();
      const extremo = alInicio ? " Estás al inicio de la lista." : alFinal ? " Llegaste al final de la lista." : "";
      estadoCarrusel.textContent = `Oficios ${primero} a ${ultimo} de ${total}.${extremo}`;
    }
  }

  function mover(direccion) {
    const sobra = lista.scrollWidth - lista.clientWidth;
    const limite = direccion < 0 ? lista.scrollLeft <= 1 : lista.scrollLeft >= sobra - 1;
    anunciar = true;
    if (limite) {
      actualizar();
      return;
    }
    lista.scrollBy({ left: direccion * lista.clientWidth * 0.8, behavior: sinMovimiento.matches ? "auto" : "smooth" });
  }

  let espera = null;
  lista.addEventListener("scroll", () => {
    clearTimeout(espera);
    espera = setTimeout(actualizar, 120);
  });
  // Con Tab, la tarjeta enfocada se alinea a un punto de ajuste (inicio) para
  // que el scroll-snap no la deje cortada.
  lista.addEventListener("focusin", (evento) => {
    const item = evento.target.closest("li");
    if (item && lista.scrollWidth > lista.clientWidth + 1) {
      item.scrollIntoView({ block: "nearest", inline: "start", behavior: sinMovimiento.matches ? "auto" : "smooth" });
    }
  });
  anterior.addEventListener("click", () => mover(-1));
  siguiente.addEventListener("click", () => mover(1));
  window.addEventListener("resize", () => {
    clearTimeout(espera);
    espera = setTimeout(actualizar, 120);
  });

  cargar();
})();
