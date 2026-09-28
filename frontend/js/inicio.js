// Página de inicio: si hay sesión, ofrece ir a la cuenta.
// Tras cerrar sesión (cuenta.js, solo con 204 o 401 del servidor) avisa que quedó cerrada.
"use strict";

(async () => {
  const cerrada = new URLSearchParams(location.search).get("aviso") === "sesion-cerrada";
  if (cerrada) {
    // El aviso no se repite al recargar.
    history.replaceState(null, "", location.pathname);
  }
  const { estado } = await api.obtener("/api/cuenta");
  if (estado === 200) {
    document.getElementById("con-sesion").classList.remove("oculto");
    document.getElementById("sin-sesion").classList.add("oculto");
    return;
  }
  if (cerrada) {
    const aviso = document.getElementById("aviso-inicio");
    aviso.className = "aviso aviso-exito";
    aviso.textContent = "Cerraste tu sesión. Para volver a entrar, pulsa «Ingresar».";
    aviso.focus();
  }
})();
