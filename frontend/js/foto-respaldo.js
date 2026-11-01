// Foto decorativa de la portada y del ingreso (ADR-002 E-4.9): si no carga, se
// oculta para que no quede el ícono de imagen rota; debajo queda el fondo
// oscuro de respaldo (--foto-respaldo), que mantiene legible el texto blanco.
(() => {
  document.querySelectorAll("img[data-foto-decorativa]").forEach((img) => {
    const ocultar = () => {
      img.hidden = true;
    };
    if (img.complete && img.naturalWidth === 0) {
      ocultar();
    } else {
      img.addEventListener("error", ocultar, { once: true });
    }
  });
})();
