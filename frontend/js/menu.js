// Encabezado en dos versiones (ADR-002 E-2 y E-3). Solo presentación: cada
// ruta de la API vuelve a exigir identidad, rol y propiedad (no es una barrera).
// - Sin sesión: solo la marca «AlTiro», que lleva a index.html (el HTML ya
//   viene así; Ingresar, Crear cuenta y Postular están en el cuerpo del inicio).
// - Con sesión (GET /api/cuenta, la única consulta): la marca lleva al inicio
//   del rol y se agrega el botón «Menú» con los enlaces de los roles.
// window.altiroInicio(roles): ÚNICO lugar del inicio por rol (E-3, punto 7, y
// E-3.2: dos flujos); también lo usan ingresar.js e inicio.js.
// window.altiroFlujo(flujo): conversacion y evaluar lo llaman cuando saben si
// la persona es el cliente o el maestro del pedido (E-3.2).
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

  // Dos flujos (ADR-002 E-3.2): la marca lleva al inicio del flujo en que está
  // la persona. Las páginas que no están aquí son neutras: usan el último flujo
  // visitado (sessionStorage «altiro.flujo», solo «cliente» o «maestro», sin
  // datos personales) o, si no hay, el orden de E-3.
  const INICIO_FLUJO = { cliente: "categorias.html", maestro: "mis-trabajos.html" };
  const FLUJO_POR_PAGINA = {
    "categorias.html": "cliente",
    "buscar.html": "cliente",
    "perfil-maestro.html": "cliente",
    "pedir-trabajo.html": "cliente",
    "mis-pedidos.html": "cliente",
    "mis-trabajos.html": "maestro",
    "mi-perfil.html": "maestro",
    "mis-servicios.html": "maestro",
    "mi-cobertura.html": "maestro",
    "mi-agenda.html": "maestro",
    "mis-documentos.html": "maestro",
    "mi-postulacion.html": "maestro",
  };
  const CLAVE_FLUJO = "altiro.flujo";

  function leerFlujo() {
    try {
      const valor = sessionStorage.getItem(CLAVE_FLUJO);
      return INICIO_FLUJO[valor] ? valor : null;
    } catch (_) {
      return null;
    }
  }

  function guardarFlujo(flujo) {
    try {
      sessionStorage.setItem(CLAVE_FLUJO, flujo);
    } catch (_) {
      // Sin almacenamiento (modo privado): la marca usa el flujo de la página.
    }
  }

  const paginaActual = location.pathname.split("/").pop() || "index.html";
  let flujoActual = FLUJO_POR_PAGINA[paginaActual] || null;
  if (flujoActual) {
    guardarFlujo(flujoActual);
  }

  window.altiroInicio = (roles) => {
    const lista = Array.isArray(roles) ? roles : [];
    // El flujo solo cuenta si la cuenta tiene ese rol (otra cuenta en la misma pestaña).
    const flujo = flujoActual || leerFlujo();
    if (flujo && lista.includes(flujo)) {
      return INICIO_FLUJO[flujo];
    }
    const encontrado = INICIO_POR_ROL.find(([rol]) => lista.includes(rol));
    return encontrado ? encontrado[1] : "cuenta.html";
  };

  let alCambiarFlujo = () => {};
  window.altiroFlujo = (flujo) => {
    if (!INICIO_FLUJO[flujo]) {
      return;
    }
    flujoActual = flujo;
    guardarFlujo(flujo);
    alCambiarFlujo();
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
    // E-3.2: «Buscar maestros» y «Mi trabajo como maestro» cambian de flujo.
    const lista = [["Buscar maestros", "categorias.html"]];
    const roles = cuenta.roles || [];
    if (cuenta.perfil_cliente) {
      lista.push(["Mis pedidos", "mis-pedidos.html"]);
    }
    if (cuenta.perfil_maestro) {
      lista.push(["Mi trabajo como maestro", "mis-trabajos.html"], ["Mi perfil", "mi-perfil.html"],
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
    boton.textContent = "Cerrando sesión…";
    const { estado } = await api.borrar("/api/sesion");
    if (estado === 204 || estado === 401) {
      formulario.olvidarTodo();
      // olvidarTodo también borra «altiro.flujo» (prefijo «altiro.»).
      location.replace("index.html?aviso=sesion-cerrada");
      return;
    }
    boton.disabled = false;
    boton.textContent = "No se pudo cerrar la sesión: reintentar";
  }

  (async () => {
    const cuenta = await window.altiroCuenta;
    if (!cuenta) {
      // Sin sesión: solo la marca hacia index.html (ya viene en el HTML).
      return;
    }
    const marca = encabezado.querySelector("a.marca");
    alCambiarFlujo = () => {
      if (marca) marca.href = window.altiroInicio(cuenta.roles);
    };
    alCambiarFlujo();
    const actual = paginaActual;

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
    const salirBoton = crear("button", { type: "button", className: "menu-salir" }, "Cerrar sesión en este dispositivo");
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
