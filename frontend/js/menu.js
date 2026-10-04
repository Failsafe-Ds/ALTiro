// Menú principal del encabezado. Solo presentación: muestra los enlaces que
// corresponden a la sesión y a los roles de GET /api/cuenta; cada ruta de la API
// vuelve a exigir identidad, rol y propiedad (el menú no es una barrera).
"use strict";

(() => {
  const encabezado = document.querySelector("header.encabezado");
  if (!encabezado || typeof api === "undefined") {
    return;
  }

  const enlaces = (cuenta) => {
    const lista = [["Buscar un maestro", "buscar.html"]];
    if (!cuenta) {
      lista.push(["Ingresar", "ingresar.html"], ["Crear mi cuenta", "registro-cliente.html"],
        ["Soy maestro: quiero postular", "postulacion-maestro.html"]);
      return lista;
    }
    const roles = cuenta.roles || [];
    if (cuenta.perfil_cliente) {
      lista.push(["Mis pedidos", "mis-pedidos.html"]);
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
    const { estado, datos } = await api.obtener("/api/cuenta");
    const cuenta = estado === 200 && datos && datos.cuenta ? datos.cuenta : null;
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
    if (cuenta) {
      const salirBoton = crear("button", { type: "button", className: "menu-salir" }, "Salir");
      salirBoton.addEventListener("click", () => salir(salirBoton));
      const li = crear("li", {});
      li.append(salirBoton);
      ul.append(li);
    }

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
