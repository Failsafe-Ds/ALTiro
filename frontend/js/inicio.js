// Página de inicio: si hay sesión, ofrece ir al inicio de su rol.
// Los oficios los muestra el carrusel compartido (carrusel-oficios.js).
// Tras cerrar sesión (cuenta.js, solo con 204 o 401 del servidor) avisa que quedó cerrada.
"use strict";

(async () => {
  const cerrada = new URLSearchParams(location.search).get("aviso") === "sesion-cerrada";
  if (cerrada) {
    // El aviso no se repite al recargar.
    history.replaceState(null, "", location.pathname);
  }
  const { estado, datos } = await api.obtener("/api/cuenta");
  if (estado === 200) {
    // Inicio del rol (menu.js, ADR-002 E-3); respaldo: la cuenta.
    const roles = datos && datos.cuenta ? datos.cuenta.roles : [];
    if (typeof window.altiroInicio === "function") {
      document.getElementById("con-sesion").href = window.altiroInicio(roles);
    }
    document.getElementById("con-sesion").classList.remove("oculto");
    document.getElementById("sin-sesion").classList.add("oculto");
    document.getElementById("para-maestros").classList.add("oculto");
    document.getElementById("encabezado-ingresar").classList.add("oculto");
    return;
  }
  if (cerrada) {
    const aviso = document.getElementById("aviso-inicio");
    aviso.className = "aviso aviso-exito";
    aviso.textContent = "Cerraste tu sesión. Para volver a entrar, pulsa «Ingresar».";
    aviso.focus();
  }
})();
