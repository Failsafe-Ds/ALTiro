// Inicio de sesión (RF-02). El identificador es el correo o el RUT (ADR-013).
// Parámetro "siguiente": a dónde seguir tras ingresar. Se valida contra una
// lista cerrada de claves (nunca se usa como dirección), para que nadie
// arme un enlace que lleve a otro sitio. Solo aplica a cuentas de maestro:
// el servidor decide igual qué puede ver cada cuenta.
"use strict";

(() => {
  const DESTINOS_MAESTRO = {
    postulacion: "mi-postulacion.html",
    documentos: "mis-documentos.html",
  };
  const form = document.getElementById("ingresar");
  formulario.prepararBoton(form);

  const parametros = new URLSearchParams(location.search);
  const aviso = parametros.get("aviso");
  const siguiente = parametros.get("siguiente");
  const destino = Object.prototype.hasOwnProperty.call(DESTINOS_MAESTRO, siguiente || "")
    ? DESTINOS_MAESTRO[siguiente]
    : null;

  if (aviso === "registrado") {
    formulario.avisar(
      form,
      siguiente === "postulacion"
        ? "Tu postulación quedó registrada. Ahora ingresa con tu RUT y tu contraseña para enviar las fotos de tus documentos."
        : "Tu cuenta quedó creada. Ahora ingresa con tus datos.",
      "exito"
    );
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
      const esMaestro = Boolean(datos.cuenta && Array.isArray(datos.cuenta.roles) && datos.cuenta.roles.includes("maestro"));
      location.assign(destino && esMaestro ? destino : "cuenta.html");
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
