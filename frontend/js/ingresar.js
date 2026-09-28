// Inicio de sesión (RF-02). El identificador es el correo o el RUT (ADR-013).
"use strict";

(() => {
  const form = document.getElementById("ingresar");
  formulario.prepararBoton(form);

  const aviso = new URLSearchParams(location.search).get("aviso");
  if (aviso === "registrado") {
    formulario.avisar(form, "Tu cuenta quedó creada. Ahora ingresa con tus datos.", "exito");
  } else if (aviso === "sesion") {
    formulario.avisar(form, "Tu sesión terminó. Ingresa de nuevo para continuar.", "error");
  }

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(form);
    formulario.ocupado(form, true);
    const { estado, datos } = await api.enviar("/api/sesion", formulario.leer(form));
    formulario.ocupado(form, false);
    if (estado === 200) {
      location.assign("cuenta.html");
      return;
    }
    // Nunca se conserva la contraseña escrita tras un error.
    form.querySelector("#contrasena").value = "";
    const campo = formulario.mostrarErrores(form, datos);
    if (campo) {
      campo.focus();
    }
  });
})();
