// Registro de cliente por pasos (RF-01, HU-01; RNF-14, RNF-20).
"use strict";

(async () => {
  const CLAVE = "altiro.registro-cliente";
  const form = document.getElementById("registro-cliente");
  formulario.prepararBoton(form);

  const previo = formulario.recuperar(CLAVE);
  await territorio.conectar(form.region, form.comuna, (previo && previo.valores) || {});
  const pasos = formulario.porPasos(form, { clave: CLAVE });

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(form);
    formulario.ocupado(form, true);
    const { estado, datos } = await api.enviar("/api/clientes", formulario.leer(form));
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
