// Registro de cliente por pasos (RF-01, HU-01; RNF-14, RNF-20).
// Con sesión iniciada no se ofrece el formulario de cuenta nueva: el perfil de
// cliente se agrega desde "Mi cuenta" (ADR-013, punto 2; DEF-QA-001).
// El envío y los pasos se conectan antes de cualquier espera de red, y el
// formulario queda oculto ("Cargando…") hasta saber si hay sesión (hallazgo UX M-1).
"use strict";

(() => {
  const CLAVE = "altiro.registro-cliente";
  const CON_SESION = {
    perfil: "perfil_cliente",
    sinPerfil:
      "No necesitas crear otra cuenta: para pedir trabajos con la que ya usas, agrega tu comuna en «Mi cuenta».",
    conPerfil: "Tu cuenta ya puede pedir trabajos. No necesitas crear otra.",
  };
  // Respaldo si no se pudo consultar la sesión tras el error (por ejemplo, sin conexión).
  const NO_PERMITIDO = {
    mensaje:
      "Parece que se inició una sesión en este navegador mientras llenabas el formulario. Recarga la página para ver cómo continuar.",
    campo: "Recarga la página para continuar.",
  };
  const form = document.getElementById("registro-cliente");

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
  const previo = formulario.recuperar(CLAVE);
  const pasos = formulario.porPasos(form, { clave: CLAVE });

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(form);
    formulario.ocupado(form, true);
    const { estado, datos } = await api.enviar("/api/clientes", formulario.leer(form));
    if (estado === 201) {
      pasos.terminar();
      location.assign("ingresar.html?aviso=registrado");
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

  // --- Después: sesión y listas de territorio ---
  (async () => {
    if (await derivarSiHaySesion(false)) {
      return;
    }
    formulario.mostrarVisitante();
    // Región y comuna guardadas se aplican cuando llegan sus listas.
    await territorio.conectar(form.region, form.comuna, (previo && previo.valores) || {});
    // Vuelve a guardar el progreso ya con región y comuna (RNF-20): los pasos
    // se conectaron antes de que existieran sus opciones.
    form.comuna.dispatchEvent(new Event("change", { bubbles: true }));
  })();
})();
