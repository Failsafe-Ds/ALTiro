// Páginas de opciones al estilo de la configuración de Steam (ADR-002 E-3,
// punto 3; MASTER, «Página de opciones»). Un solo componente: la página marca
// su <main data-opciones> y este archivo arma el menú de secciones.
// - En 768 px o más: menú a la izquierda y contenido a la derecha.
// - En el celular: el menú va arriba, plegado en un <details> con la sección actual.
// - Ítem activo: aria-current="page" (y en CSS fondo --marca-suave y barra roja).
// - Secciones internas (cuenta.html): elementos [data-seccion] con id; se
//   muestra solo la del fragmento (#datos, #seguridad, #perfiles).
// Solo navegación: la API vuelve a exigir identidad, rol y propiedad. Usa la
// cuenta que ya consultó menu.js (window.altiroCuenta), sin una segunda consulta.
"use strict";

(() => {
  const main = document.querySelector("main[data-opciones]");
  if (!main) {
    return;
  }

  const CUENTA = [
    ["Mis datos", "cuenta.html#datos"],
    ["Seguridad", "cuenta.html#seguridad"],
    ["Mis perfiles", "cuenta.html#perfiles"],
  ];
  const MAESTRO = [
    ["Mi perfil", "mi-perfil.html"],
    ["Mis servicios", "mis-servicios.html"],
    ["Mi cobertura", "mi-cobertura.html"],
    ["Mi agenda", "mi-agenda.html"],
    ["Mis documentos", "mis-documentos.html"],
    ["Mi postulación", "mi-postulacion.html"],
  ];
  const pagina = location.pathname.split("/").pop() || "index.html";
  const esPaginaMaestro = MAESTRO.some(([, destino]) => destino === pagina);
  const ANCHO = window.matchMedia("(min-width: 48rem)");

  // Estructura: menú + contenido (el contenido original de <main> se mueve tal cual).
  const contenido = document.createElement("div");
  contenido.className = "opciones-contenido";
  contenido.append(...main.childNodes);
  const nav = document.createElement("nav");
  nav.className = "opciones-menu";
  nav.setAttribute("aria-label", "Opciones de mi cuenta");
  const plegable = document.createElement("details");
  plegable.className = "opciones-plegable";
  const resumen = document.createElement("summary");
  plegable.append(resumen);
  nav.append(plegable);
  main.classList.add("opciones");
  main.append(nav, contenido);

  const secciones = Array.from(contenido.querySelectorAll("[data-seccion][id]"));

  function seccionDelFragmento() {
    const id = decodeURIComponent(location.hash.slice(1));
    return secciones.find((s) => s.id === id) || secciones[0];
  }

  // Item activo: la página actual o, en cuenta.html, la sección mostrada.
  function destinoActivo() {
    const seccion = secciones.length ? seccionDelFragmento() : null;
    return seccion ? `${pagina}#${seccion.id}` : pagina;
  }

  function marcarActivo() {
    const activo = destinoActivo();
    let texto = "";
    for (const enlace of nav.querySelectorAll("a")) {
      const es = enlace.getAttribute("href") === activo;
      if (es) {
        enlace.setAttribute("aria-current", "page");
        texto = enlace.textContent;
      } else {
        enlace.removeAttribute("aria-current");
      }
    }
    resumen.textContent = texto ? `Sección: ${texto}` : "Secciones";
  }

  function grupo(titulo, enlaces) {
    const caja = document.createElement("div");
    caja.className = "opciones-grupo";
    const h = document.createElement("p");
    h.className = "opciones-titulo";
    h.textContent = titulo;
    const ul = document.createElement("ul");
    for (const [texto, destino] of enlaces) {
      const a = document.createElement("a");
      a.href = destino;
      a.textContent = texto;
      const li = document.createElement("li");
      li.append(a);
      ul.append(li);
    }
    caja.append(h, ul);
    return caja;
  }

  function armar(conMaestro) {
    for (const viejo of plegable.querySelectorAll(".opciones-grupo")) {
      viejo.remove();
    }
    plegable.append(grupo("Mi cuenta", CUENTA));
    if (conMaestro) {
      plegable.append(grupo("Mi trabajo como maestro", MAESTRO));
    }
    marcarActivo();
  }

  // Abierto siempre en pantalla ancha; plegado en el celular.
  function ajustarAncho() {
    plegable.open = ANCHO.matches;
    plegable.classList.toggle("fijo", ANCHO.matches);
  }

  // Muestra una sección interna (por su id o por un elemento que contiene).
  function mostrar(objetivo, enfocar) {
    if (!secciones.length) {
      return;
    }
    const seccion =
      typeof objetivo === "string"
        ? secciones.find((s) => s.id === objetivo)
        : secciones.find((s) => s.contains(objetivo));
    if (!seccion) {
      return;
    }
    for (const s of secciones) {
      s.hidden = s !== seccion;
    }
    if (location.hash.slice(1) !== seccion.id) {
      history.replaceState(history.state, "", `#${seccion.id}`);
    }
    marcarActivo();
    if (enfocar) {
      const titulo = seccion.querySelector("h2");
      if (titulo) {
        titulo.focus();
      }
    }
  }

  window.altiroOpciones = { mostrar: (elemento) => mostrar(elemento, false) };

  armar(esPaginaMaestro);
  ajustarAncho();
  ANCHO.addEventListener("change", ajustarAncho);
  if (secciones.length) {
    mostrar(seccionDelFragmento().id, false);
    window.addEventListener("hashchange", () => {
      mostrar(seccionDelFragmento().id, true);
      if (!ANCHO.matches) {
        plegable.open = false;
      }
    });
  }
  // En el celular, elegir un ítem cierra el menú plegado.
  nav.addEventListener("click", (evento) => {
    if (evento.target.closest("a") && !ANCHO.matches) {
      plegable.open = false;
    }
  });

  Promise.resolve(window.altiroCuenta).then((cuenta) => {
    if (cuenta && Boolean(cuenta.perfil_maestro) !== esPaginaMaestro) {
      armar(Boolean(cuenta.perfil_maestro));
    }
  });
})();
