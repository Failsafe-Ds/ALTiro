// Cliente mínimo de la API JSON bajo /api/ (ADR-002).
// El envío del token CSRF (ADR-006) y el manejo de errores para el usuario se
// agregarán junto con las primeras operaciones que cambien datos.
"use strict";

const api = (() => {
  async function obtener(ruta) {
    const respuesta = await fetch(ruta, {
      method: "GET",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    const datos = await respuesta.json().catch(() => null);
    return { estado: respuesta.status, datos };
  }

  return { obtener };
})();
