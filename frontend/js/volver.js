// Enlace «← Volver»: vuelve a la página anterior de AlTiro; si no hay, sigue el
// enlace de respaldo (data-volver, un href real que funciona sin JavaScript).
(() => {
  const enlace = document.querySelector("a[data-volver]");
  if (!enlace) {
    return;
  }
  enlace.addEventListener("click", (evento) => {
    if (evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.button !== 0) {
      return;
    }
    // Pasos dentro de la página (buscar, formularios por pasos): retrocede un paso.
    const pasoInterno = history.state && history.state.altiroPaso;
    let mismoOrigen = false;
    try {
      const anterior = document.referrer ? new URL(document.referrer) : null;
      mismoOrigen = Boolean(anterior) && anterior.origin === location.origin && anterior.href !== location.href;
    } catch (error) {
      mismoOrigen = false;
    }
    if (pasoInterno || (mismoOrigen && history.length > 1)) {
      evento.preventDefault();
      history.back();
    }
  });
})();
