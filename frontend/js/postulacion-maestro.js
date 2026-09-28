// Postulación de maestro, paso de identificación (RF-03, HU-11; RNF-14, RNF-20).
// Los documentos del expediente llegan en el Sprint 2 (RF-04).
// Con sesión iniciada no se ofrece el formulario de cuenta nueva: el perfil de
// maestro se agrega desde "Mi cuenta" (ADR-013, punto 2; DEF-QA-001).
// El envío y los pasos se conectan antes de cualquier espera de red, y el
// formulario queda oculto ("Cargando…") hasta saber si hay sesión (hallazgo UX M-1).
"use strict";

(() => {
  const CLAVE = "altiro.postulacion-maestro";
  const CON_SESION = {
    perfil: "perfil_maestro",
    sinPerfil:
      "No necesitas crear otra cuenta: para postular como maestro con la que ya usas, escribe tu RUT en «Mi cuenta».",
    conPerfil: "Tu cuenta ya tiene una postulación como maestro. No necesitas postular de nuevo.",
  };
  // Respaldo si no se pudo consultar la sesión tras el error (por ejemplo, sin conexión).
  const NO_PERMITIDO = {
    mensaje:
      "Parece que se inició una sesión en este navegador mientras llenabas el formulario. Recarga la página para ver cómo continuar.",
    campo: "Recarga la página para continuar.",
  };
  const form = document.getElementById("postulacion");

  // Devuelve true si hay sesión y la página pasó a mostrar el aviso.
  async function derivarSiHaySesion(enfocar) {
    const { estado, datos } = await api.obtener("/api/cuenta");
    if (estado !== 200) {
      return false;
    }
    formulario.derivarACuenta(datos.cuenta, CON_SESION, enfocar);
    return true;
  }

  // --- Conexión síncrona: nunca hay un envío nativo del formulario ---
  formulario.prepararBoton(form);
  const pasos = formulario.porPasos(form, { clave: CLAVE });

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(form);
    formulario.ocupado(form, true);
    const { estado, datos } = await api.enviar("/api/maestros/postulaciones", formulario.leer(form));
    if (estado === 201) {
      pasos.terminar();
      // D-13 / ADR-013 E-8: la postulación no inicia sesión. Se va a ingresar
      // sin el RUT en la dirección, y tras ingresar se sigue con los documentos.
      location.assign("ingresar.html?aviso=registrado&siguiente=postulacion");
      return;
    }
    // Un 400 puede deberse a una sesión iniciada en otra pestaña: el servidor
    // aplicó las reglas de una cuenta existente (ADR-013, E-2).
    const derivado = estado === 400 && (await derivarSiHaySesion(true));
    formulario.ocupado(form, false);
    if (derivado) {
      return;
    }
    const campo = formulario.mostrarErrores(form, formulario.traducirNoPermitido(datos, NO_PERMITIDO));
    if (campo) {
      pasos.irAlCampo(campo);
    }
  });

  // --- Después: sesión ---
  (async () => {
    if (!(await derivarSiHaySesion(false))) {
      formulario.mostrarVisitante();
    }
  })();
})();
