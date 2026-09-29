// Listas de región y comuna (RF-01, CA-01.1, CA-01.2).
// Al elegir la región, solo se cargan las comunas de esa región.
// Hallazgo UX E-6: si una lista no carga (sin señal o servidor sin responder),
// se muestra un aviso junto al campo con el botón "Reintentar"; lo ya elegido
// se conserva.
"use strict";

const territorio = (() => {
  const SIN_SENAL = "Revisa tu señal o tu wifi y toca «Reintentar».";

  function opcion(valor, texto) {
    const elemento = document.createElement("option");
    elemento.value = valor;
    elemento.textContent = texto;
    return elemento;
  }

  // Aviso de error junto al campo (debajo de su bloque .campo), con "Reintentar".
  function avisarFalla(select, texto, reintentar) {
    quitarFalla(select);
    const aviso = document.createElement("div");
    aviso.className = "aviso aviso-error aviso-territorio";
    aviso.setAttribute("role", "alert");
    aviso.dataset.territorio = select.id;
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "boton-secundario";
    boton.textContent = "Reintentar";
    boton.addEventListener("click", () => {
      quitarFalla(select);
      reintentar();
    });
    aviso.append(texto, " ", boton);
    (select.closest(".campo") || select).after(aviso);
  }

  function quitarFalla(select) {
    const previo = document.querySelector(`[data-territorio="${select.id}"]`);
    if (previo) {
      previo.remove();
    }
  }

  async function cargarComunas(selectComuna, region, seleccionada) {
    quitarFalla(selectComuna);
    selectComuna.replaceChildren(opcion("", region ? "Cargando comunas…" : "Primero elige tu región"));
    selectComuna.disabled = true;
    if (!region) {
      return;
    }
    const { estado, datos } = await api.obtener(`/api/territorio/regiones/${encodeURIComponent(region)}/comunas`);
    if (estado !== 200) {
      selectComuna.replaceChildren(opcion("", "No pudimos cargar las comunas"));
      avisarFalla(selectComuna, `No pudimos cargar las comunas. ${estado === 0 ? SIN_SENAL : "Toca «Reintentar»."}`, () =>
        cargarComunas(selectComuna, region, seleccionada)
      );
      return;
    }
    selectComuna.replaceChildren(
      opcion("", "Elige tu comuna"),
      ...datos.comunas.map((c) => opcion(String(c.codigo), c.nombre))
    );
    selectComuna.disabled = false;
    if (seleccionada) {
      selectComuna.value = seleccionada;
      // Avisa al formulario (progreso guardado, RNF-20) de la comuna repuesta.
      selectComuna.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  // Carga la lista de regiones; si falla, ofrece "Reintentar" y la promesa
  // termina igual (el formulario sigue usable y conserva lo escrito).
  async function cargarRegiones(selectRegion, selectComuna, guardados) {
    quitarFalla(selectRegion);
    selectRegion.replaceChildren(opcion("", "Cargando regiones…"));
    const { estado, datos } = await api.obtener("/api/territorio/regiones");
    if (estado !== 200) {
      selectRegion.replaceChildren(opcion("", "No pudimos cargar las regiones"));
      avisarFalla(selectRegion, `No pudimos cargar las regiones. ${estado === 0 ? SIN_SENAL : "Toca «Reintentar»."}`, () =>
        cargarRegiones(selectRegion, selectComuna, guardados)
      );
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

  // Conecta los dos select. Devuelve una promesa que termina cuando la lista
  // de regiones (y, si corresponde, la de comunas guardadas) está cargada, o
  // cuando falló y quedó el aviso con "Reintentar".
  async function conectar(selectRegion, selectComuna, guardados = {}) {
    selectRegion.addEventListener("change", () => cargarComunas(selectComuna, selectRegion.value, ""));
    await cargarRegiones(selectRegion, selectComuna, guardados);
  }

  return { conectar };
})();
