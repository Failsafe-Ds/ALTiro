// Olvidé mi contraseña (ADR-027, punto 3).
// - El servidor responde lo mismo exista o no la cuenta: la página solo muestra
//   ese mensaje y no dice si la cuenta existe.
// - El 429 (varios pedidos seguidos) llega con su mensaje en el formato común.
"use strict";

(() => {
  const form = document.getElementById("recuperar");
  formulario.prepararBoton(form);

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(form);
    const revision = formulario.revisar(form);
    if (revision) {
      const campo = formulario.mostrarErrores(form, revision);
      if (campo) {
        campo.focus();
      }
      return;
    }
    formulario.ocupado(form, true);
    const { estado, datos } = await api.enviar("/api/recuperacion", formulario.leer(form));
    formulario.ocupado(form, false);
    if (estado === 202) {
      formulario.avisar(form, datos.mensaje, "exito");
      form.querySelector(".aviso").focus();
      return;
    }
    const campo = formulario.mostrarErrores(form, datos);
    if (campo) {
      campo.focus();
    }
  });
})();
