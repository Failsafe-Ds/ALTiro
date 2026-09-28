// Postulación de maestro, paso de identificación (RF-03, HU-11; RNF-14, RNF-20).
// Los documentos del expediente llegan en el Sprint 2 (RF-04).
"use strict";

(() => {
  const CLAVE = "altiro.postulacion-maestro";
  const form = document.getElementById("postulacion");
  formulario.prepararBoton(form);
  const pasos = formulario.porPasos(form, { clave: CLAVE });

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(form);
    formulario.ocupado(form, true);
    const { estado, datos } = await api.enviar("/api/maestros/postulaciones", formulario.leer(form));
    formulario.ocupado(form, false);
    if (estado === 201) {
      pasos.terminar();
      location.assign("ingresar.html?aviso=registrado");
      return;
    }
    const campo = formulario.mostrarErrores(form, datos);
    if (campo) {
      pasos.irAlCampo(campo);
    }
  });
})();
