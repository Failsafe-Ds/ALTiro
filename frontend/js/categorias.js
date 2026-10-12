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
  const anterior = document.getElementById("carrusel-anterior");
  const siguiente = document.getElementById("carrusel-siguiente");
  const pausa = document.getElementById("carrusel-pausa");
  const escena = document.getElementById("abanico-escena");
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
    return elemento("li", "abanico-item", enlace);
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
    carrusel.hidden = false;
    armar(oficios.map(categoria));
  }

  // --- Carrusel en abanico (ADR-002 E-4.1) ---
  // Cada oficio recibe data-pos = su distancia (circular) a la tarjeta actual:
  // 0 al centro, ±1 y ±2 a los lados (el CSS las achica e inclina) y "fuera"
  // las demás. Solo la del centro es enfocable y la leen los lectores de
  // pantalla. Avanza solo cada ESPERA ms (WCAG 2.2.2: se puede pausar, y se
  // detiene mientras la persona lo usa); con prefers-reduced-motion empieza
  // pausado y sin animación.
  const ESPERA = 4000;
  const sinMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)");
  let actual = 0;
  let total = 0;
  let reloj = null;
  let pausadoPorPersona = sinMovimiento.matches;
  let detenidoPorUso = false;

  function mostrar(indice, anunciar) {
    actual = (indice + total) % total;
    Array.from(lista.children).forEach((item, i) => {
      let d = i - actual;
      if (d > total / 2) d -= total;
      if (d < -total / 2) d += total;
      item.dataset.pos = Math.abs(d) <= 2 ? String(d) : "fuera";
      const centro = d === 0;
      item.setAttribute("aria-hidden", String(!centro));
      item.querySelector("a").tabIndex = centro ? 0 : -1;
    });
    Array.from(puntos.children).forEach((punto, i) => {
      punto.classList.toggle("activo", i === actual);
      if (i === actual) {
        punto.setAttribute("aria-current", "true");
      } else {
        punto.removeAttribute("aria-current");
      }
    });
    // El avance automático no se anuncia (sería ruido cada 4 s); el cambio a mano sí.
    if (anunciar) {
      const nombre = lista.children[actual].querySelector(".nombre-categoria").textContent;
      estadoCarrusel.textContent = `Oficio ${actual + 1} de ${total}: ${nombre}.`;
    }
  }

  // Al cambiar a mano: se anuncia y, si el foco estaba en la tarjeta, pasa a la nueva.
  function mover(paso) {
    const conFoco = lista.contains(document.activeElement);
    mostrar(actual + paso, true);
    if (conFoco) {
      lista.children[actual].querySelector("a").focus({ preventScroll: true });
    }
    programar();
  }

  function programar() {
    clearTimeout(reloj);
    reloj = null;
    if (pausadoPorPersona || detenidoPorUso || total < 2 || carrusel.hidden || document.hidden) {
      return;
    }
    reloj = setTimeout(() => {
      mostrar(actual + 1, false);
      programar();
    }, ESPERA);
  }

  function marcarPausa() {
    pausa.setAttribute("aria-pressed", String(pausadoPorPersona));
    pausa.querySelector(".pausa-texto").textContent = pausadoPorPersona ? "Reanudar" : "Pausar";
    pausa.querySelector(".pausa-icono").textContent = pausadoPorPersona ? "▶" : "❚❚";
  }

  function armar(items) {
    total = items.length;
    lista.replaceChildren(...items);
    puntos.replaceChildren(
      ...items.map((item, i) => {
        const punto = elemento("button", "punto");
        punto.type = "button";
        punto.setAttribute("aria-label", `Ver ${item.querySelector(".nombre-categoria").textContent}`);
        punto.addEventListener("click", () => {
          mostrar(i, true);
          programar();
        });
        return punto;
      })
    );
    controles.hidden = total < 2;
    marcarPausa();
    mostrar(0, false);
    programar();
  }

  anterior.addEventListener("click", () => mover(-1));
  siguiente.addEventListener("click", () => mover(1));
  pausa.addEventListener("click", () => {
    pausadoPorPersona = !pausadoPorPersona;
    marcarPausa();
    programar();
  });

  // Tocar una tarjeta lateral la trae al centro (no abre el enlace).
  lista.addEventListener("click", (evento) => {
    const item = evento.target.closest("li");
    if (item && item.dataset.pos !== "0") {
      evento.preventDefault();
      mostrar(Array.from(lista.children).indexOf(item), true);
      programar();
    }
  });

  // Se detiene mientras la persona lo usa (mouse encima o foco dentro) y sigue al salir.
  function detener(valor) {
    detenidoPorUso = valor;
    programar();
  }
  carrusel.addEventListener("mouseenter", () => detener(true));
  carrusel.addEventListener("mouseleave", () => detener(carrusel.contains(document.activeElement)));
  carrusel.addEventListener("focusin", () => detener(true));
  carrusel.addEventListener("focusout", (evento) => {
    if (!carrusel.contains(evento.relatedTarget)) {
      detener(carrusel.matches(":hover"));
    }
  });

  carrusel.addEventListener("keydown", (evento) => {
    if (evento.key === "ArrowLeft") {
      mover(-1);
    } else if (evento.key === "ArrowRight") {
      mover(1);
    } else {
      return;
    }
    evento.preventDefault();
  });

  // Deslizar con el dedo: más de 40 px en horizontal cambia de tarjeta. Tocarlo
  // con el dedo lo deja en pausa (en el celular no hay «mouse encima»); se
  // reanuda con «Reanudar».
  let inicioX = null;
  escena.addEventListener("pointerdown", (evento) => {
    inicioX = evento.clientX;
    if (evento.pointerType !== "mouse" && !pausadoPorPersona) {
      pausadoPorPersona = true;
      marcarPausa();
      programar();
    }
  });
  escena.addEventListener("pointerup", (evento) => {
    if (inicioX === null) {
      return;
    }
    const dx = evento.clientX - inicioX;
    inicioX = null;
    if (Math.abs(dx) > 40) {
      mover(dx < 0 ? 1 : -1);
    }
  });
  escena.addEventListener("pointercancel", () => {
    inicioX = null;
  });

  // Con la pestaña oculta no avanza.
  document.addEventListener("visibilitychange", programar);

  cargar();
})();
