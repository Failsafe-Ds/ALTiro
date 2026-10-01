// Crear una contraseña nueva con el enlace de recuperación (ADR-027, punto 3).
// - El token llega en el fragmento (#t=...): el navegador no lo manda al
//   servidor ni queda en los registros. Se lee una vez, se borra de la barra de
//   direcciones y del historial (history.replaceState) y solo se envía en el cuerpo.
// - Si el enlace venció o ya se usó, el servidor responde 400 en "token": se
//   muestra su mensaje con el acceso para pedir otro.
// - No inicia sesión: al terminar se ofrece "Ingresar".
"use strict";

(() => {
  const token = new URLSearchParams(location.hash.slice(1)).get("t") || "";
  history.replaceState(null, "", location.pathname);

  const form = document.getElementById("nueva-contrasena");
  if (!token) {
    const aviso = document.getElementById("sin-enlace");
    aviso.classList.remove("oculto");
    aviso.focus();
    return;
  }
  form.classList.remove("oculto");
  formulario.prepararBoton(form);

  function enlacePedirOtro() {
    const enlace = document.createElement("a");
    enlace.className = "boton";
    enlace.href = "recuperar.html";
    enlace.textContent = "Pedir un enlace nuevo";
    return enlace;
  }

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(form);
    formulario.ocupado(form, true);
    const campoContrasena = form.querySelector("#contrasena-nueva");
    const { estado, datos } = await api.enviar("/api/recuperacion/contrasena", {
      token,
      contrasena_nueva: campoContrasena.value,
    });
    formulario.ocupado(form, false);
    if (estado === 200) {
      campoContrasena.value = "";
      form.classList.add("oculto");
      const aviso = document.getElementById("aviso-listo");
      aviso.textContent = datos.mensaje;
      document.getElementById("listo").classList.remove("oculto");
      aviso.focus();
      return;
    }
    const errores = datos.errores || {};
    if (errores.token) {
      // El enlace ya no sirve: no tiene sentido seguir escribiendo aquí.
      campoContrasena.value = "";
      formulario.avisar(form, errores.token, "error");
      form.querySelector(".aviso").append(" ", enlacePedirOtro());
      return;
    }
    const campo = formulario.mostrarErrores(form, datos);
    if (campo) {
      campo.focus();
    }
  });
})();
