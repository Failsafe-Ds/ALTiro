// Listas de región y comuna (RF-01, CA-01.1, CA-01.2).
// Al elegir la región, solo se cargan las comunas de esa región.
"use strict";

const territorio = (() => {
  function opcion(valor, texto) {
    const elemento = document.createElement("option");
    elemento.value = valor;
    elemento.textContent = texto;
    return elemento;
  }

  async function cargarComunas(selectComuna, region, seleccionada) {
    selectComuna.replaceChildren(opcion("", region ? "Cargando comunas…" : "Primero elige tu región"));
    selectComuna.disabled = true;
    if (!region) {
      return;
    }
    const { estado, datos } = await api.obtener(`/api/territorio/regiones/${encodeURIComponent(region)}/comunas`);
    if (estado !== 200) {
      selectComuna.replaceChildren(opcion("", "No pudimos cargar las comunas. Vuelve a elegir la región."));
      return;
    }
    selectComuna.replaceChildren(
      opcion("", "Elige tu comuna"),
      ...datos.comunas.map((c) => opcion(String(c.codigo), c.nombre))
    );
    selectComuna.disabled = false;
    if (seleccionada) {
      selectComuna.value = seleccionada;
    }
  }

  // Conecta los dos select. Devuelve una promesa que termina cuando la lista
  // de regiones (y, si corresponde, la de comunas guardadas) está cargada.
  async function conectar(selectRegion, selectComuna, guardados = {}) {
    selectRegion.addEventListener("change", () => cargarComunas(selectComuna, selectRegion.value, ""));
    const { estado, datos } = await api.obtener("/api/territorio/regiones");
    if (estado !== 200) {
      selectRegion.replaceChildren(opcion("", "No pudimos cargar las regiones. Recarga la página."));
      return;
    }
    selectRegion.replaceChildren(
      opcion("", "Elige tu región"),
      ...datos.regiones.map((r) => opcion(String(r.codigo), r.nombre))
    );
    if (guardados.region) {
      selectRegion.value = guardados.region;
    }
    await cargarComunas(selectComuna, selectRegion.value, guardados.comuna);
  }

  return { conectar };
})();
