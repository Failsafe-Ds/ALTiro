// Rellena la versión en el pie de página (el resto del pie ya viene en el HTML).
(() => {
  const lugar = document.getElementById("pie-version");
  if (lugar && window.ALTIRO_VERSION) {
    lugar.textContent = `v${window.ALTIRO_VERSION}`;
  }
})();
