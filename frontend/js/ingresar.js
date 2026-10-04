// Inicio de sesión (RF-02). El identificador es el correo o el RUT (ADR-013).
// Parámetro "siguiente": a dónde seguir tras ingresar. Se valida contra una
// lista cerrada de claves (nunca se usa como dirección), para que nadie
// arme un enlace que lleve a otro sitio. Cada destino se usa solo si la
// cuenta tiene el rol de esa página; es solo navegación: el servidor decide
// igual qué puede ver cada cuenta.
"use strict";

(() => {
  const DESTINOS = {
    postulacion: { pagina: "mi-postulacion.html", rol: "maestro" },
    documentos: { pagina: "mis-documentos.html", rol: "maestro" },
    curatoria: { pagina: "curatoria.html", rol: "curatoria" },
    servicios: { pagina: "mis-servicios.html", rol: "maestro" },
    comercial: { pagina: "comercial.html", rol: "comercial" },
    perfil: { pagina: "mi-perfil.html", rol: "maestro" },
    cobertura: { pagina: "mi-cobertura.html", rol: "maestro" },
    agenda: { pagina: "mi-agenda.html", rol: "maestro" },
    pedidos: { pagina: "mis-pedidos.html", rol: "cliente" },
    trabajos: { pagina: "mis-trabajos.html", rol: "maestro" },
    // Pantallas de un pedido: vuelven con ?ticket=<ref> (solo si es un UUID).
    conversacion: { pagina: "conversacion.html", rol: ["cliente", "maestro"], ticket: true },
    evaluar: { pagina: "evaluar.html", rol: ["cliente", "maestro"], ticket: true },
    moderacion: { pagina: "moderacion.html", rol: "moderacion" },
    indicadores: { pagina: "indicadores.html", rol: "control_gestion" },
  };
  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const form = document.getElementById("ingresar");
  formulario.prepararBoton(form);

  const parametros = new URLSearchParams(location.search);
  const aviso = parametros.get("aviso");
  const siguiente = parametros.get("siguiente");
  const destino = Object.prototype.hasOwnProperty.call(DESTINOS, siguiente || "") ? DESTINOS[siguiente] : null;
  const refTicket = parametros.get("ticket") || "";

  function paginaDestino(roles) {
    if (!destino) {
      return null;
    }
    const permitidos = [].concat(destino.rol);
    if (!permitidos.some((rol) => roles.includes(rol))) {
      return null;
    }
    if (!destino.ticket) {
      return destino.pagina;
    }
    return UUID.test(refTicket) ? `${destino.pagina}?ticket=${encodeURIComponent(refTicket)}` : null;
  }

  if (aviso === "registrado") {
    formulario.avisar(
      form,
      siguiente === "postulacion"
        ? // RNF-13: no debe parecer que la postulación terminó (término falso).
          "Primer paso listo. Ahora ingresa con tu RUT y tu contraseña para enviar las fotos de tus documentos."
        : "Tu cuenta quedó creada. Ahora ingresa con tus datos.",
      "exito"
    );
  } else if (aviso === "sesion") {
    formulario.avisar(form, "Tu sesión terminó. Ingresa de nuevo para continuar.", "error");
  }

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
    const { estado, datos } = await api.enviar("/api/sesion", formulario.leer(form));
    formulario.ocupado(form, false);
    if (estado === 200) {
      const roles = datos.cuenta && Array.isArray(datos.cuenta.roles) ? datos.cuenta.roles : [];
      location.assign(paginaDestino(roles) || "cuenta.html");
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
