// Encabezado en dos versiones (ADR-002 E-2 y E-3). Solo presentación: cada
// ruta de la API vuelve a exigir identidad, rol y propiedad (no es una barrera).
// - Sin sesión: solo la marca «AlTiro», que lleva a index.html (el HTML ya
//   viene así; Ingresar, Crear cuenta y Postular están en el cuerpo del inicio).
// - Con sesión (GET /api/cuenta, la única consulta): la marca lleva al inicio
//   del rol y se agrega el botón «Menú» con los enlaces de los roles.
// window.altiroInicio(roles): ÚNICO lugar del inicio por rol (E-3, punto 7);
// también lo usa ingresar.js como destino por defecto.
"use strict";

(() => {
  // Orden para cuentas con varios roles (E-3, punto 7, PROVISIONAL): el primero
  // que tenga la cuenta. comercial, moderación y control de gestión, PROVISIONAL.
  const INICIO_POR_ROL = [
    ["curatoria", "curatoria.html"],
    ["moderacion", "moderacion.html"],
    ["comercial", "comercial.html"],
    ["control_gestion", "indicadores.html"],
    ["maestro", "mis-trabajos.html"],
    ["cliente", "categorias.html"],
  ];

  window.altiroInicio = (roles) => {
    const lista = Array.isArray(roles) ? roles : [];
    const encontrado = INICIO_POR_ROL.find(([rol]) => lista.includes(rol));
    return encontrado ? encontrado[1] : "cuenta.html";
  };

  // Una sola consulta GET /api/cuenta por página, compartida con opciones.js
  // (menú lateral de las páginas de opciones): window.altiroCuenta es una
  // promesa con la cuenta o null (sin sesión, sin conexión u otro error).
  window.altiroCuenta =
    typeof api === "undefined"
      ? Promise.resolve(null)
      : api
          .obtener("/api/cuenta")
          .then(({ estado, datos }) => (estado === 200 && datos && datos.cuenta ? datos.cuenta : null))
          .catch(() => null);

  const encabezado = document.querySelector("header.encabezado");
  if (!encabezado || typeof api === "undefined") {
    return;
  }

  const enlaces = (cuenta) => {
    const lista = [["Buscar un maestro", "buscar.html"]];
    const roles = cuenta.roles || [];
    if (cuenta.perfil_cliente) {
      lista.push(["Categorías de oficios", "categorias.html"], ["Mis pedidos", "mis-pedidos.html"]);
    }
    if (cuenta.perfil_maestro) {
      lista.push(["Mis trabajos", "mis-trabajos.html"], ["Mi perfil", "mi-perfil.html"],
        ["Mi agenda", "mi-agenda.html"], ["Mis servicios", "mis-servicios.html"]);
    }
    if (roles.includes("curatoria")) lista.push(["Curatoría", "curatoria.html"]);
    if (roles.includes("comercial")) lista.push(["Catálogo", "comercial.html"]);
    if (roles.includes("moderacion")) lista.push(["Denuncias", "moderacion.html"]);
    if (roles.includes("control_gestion")) lista.push(["Indicadores", "indicadores.html"]);
    lista.push(["Mi cuenta", "cuenta.html"]);
    return lista;
  };

  const crear = (etiqueta, atributos, texto) => {
    const nodo = document.createElement(etiqueta);
    Object.assign(nodo, atributos);
    if (texto) nodo.textContent = texto;
    return nodo;
  };

  async function salir(boton) {
    boton.disabled = true;
    boton.textContent = "Saliendo…";
    const { estado } = await api.borrar("/api/sesion");
    if (estado === 204 || estado === 401) {
      if (window.formulario) window.formulario.olvidarTodo();
      location.replace("index.html?aviso=sesion-cerrada");
      return;
    }
    boton.disabled = false;
    boton.textContent = "No se pudo salir: reintentar";
  }

  (async () => {
    const cuenta = await window.altiroCuenta;
    if (!cuenta) {
      // Sin sesión: solo la marca hacia index.html (ya viene en el HTML).
      return;
    }
    const marca = encabezado.querySelector("a.marca");
    if (marca) {
      marca.href = window.altiroInicio(cuenta.roles);
    }
    const actual = location.pathname.split("/").pop() || "index.html";

    const nav = crear("nav", { className: "menu" });
    nav.setAttribute("aria-label", "Menú principal");
    const boton = crear("button", { type: "button", className: "menu-boton" }, "Menú");
    boton.setAttribute("aria-expanded", "false");
    boton.setAttribute("aria-controls", "menu-lista");
    const ul = crear("ul", { id: "menu-lista", className: "menu-lista", hidden: true });
    for (const [texto, destino] of enlaces(cuenta)) {
      const a = crear("a", { href: destino }, texto);
      if (destino === actual) a.setAttribute("aria-current", "page");
      const li = crear("li", {});
      li.append(a);
      ul.append(li);
    }
    const salirBoton = crear("button", { type: "button", className: "menu-salir" }, "Salir");
    salirBoton.addEventListener("click", () => salir(salirBoton));
    const li = crear("li", {});
    li.append(salirBoton);
    ul.append(li);

    const abrir = (si) => {
      ul.hidden = !si;
      boton.setAttribute("aria-expanded", String(si));
    };
    boton.addEventListener("click", () => abrir(ul.hidden));
    nav.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !ul.hidden) {
        abrir(false);
        boton.focus();
      }
    });
    document.addEventListener("click", (e) => {
      if (!nav.contains(e.target)) abrir(false);
    });
    nav.append(boton, ul);
    encabezado.append(nav);
  })();
})();
