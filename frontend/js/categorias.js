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
      lista.hidden = true;
      avisarError(estado);
      return;
    }
    const oficios = Array.isArray(datos.oficios) ? datos.oficios : [];
    if (!oficios.length) {
      lista.hidden = true;
      aviso.className = "aviso sin-resultados angosto";
      aviso.textContent = "Por ahora no hay oficios disponibles. Vuelve a intentarlo más tarde.";
      return;
    }
    lista.replaceChildren(...oficios.map(categoria));
    lista.hidden = false;
  }

  cargar();
})();
