// Página de inicio: si hay sesión, ofrece ir a la cuenta.
"use strict";

(async () => {
  const { estado } = await api.obtener("/api/cuenta");
  if (estado === 200) {
    document.getElementById("con-sesion").classList.remove("oculto");
    document.getElementById("sin-sesion").classList.add("oculto");
  }
})();
