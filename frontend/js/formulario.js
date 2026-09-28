// Formularios por pasos, errores por campo y progreso guardado.
// - RNF-14: pasos de máximo 5 campos.
// - RNF-15: cada error se muestra junto a su campo, con texto (no solo color).
// - RNF-20: los pasos completados se conservan si se pierde la conexión o se
//   recarga la página. Se usa sessionStorage (se borra al cerrar la pestaña,
//   pensando en teléfonos compartidos) y nunca se guarda la contraseña (ADR-002).
"use strict";

const formulario = (() => {
  function campos(form) {
    return Array.from(form.querySelectorAll("input[name], select[name]"));
  }

  // Lee todos los campos, incluidos los de pasos ya completados (ocultos).
  // Se omiten los marcados con data-no-enviar (por ejemplo, la región, que
  // solo filtra la lista de comunas) y los de secciones .oculto.
  function leer(form) {
    const datos = {};
    for (const campo of campos(form)) {
      if (campo.dataset.noEnviar !== undefined || campo.closest(".oculto")) {
        continue;
      }
      if (campo.value !== "") {
        datos[campo.name] = campo.value;
      }
    }
    return datos;
  }

  function limpiarErrores(form) {
    for (const campo of campos(form)) {
      campo.removeAttribute("aria-invalid");
    }
    for (const error of form.querySelectorAll(".error-campo")) {
      error.textContent = "";
    }
    const aviso = form.querySelector(".aviso");
    if (aviso) {
      aviso.textContent = "";
      aviso.className = "aviso";
    }
  }

  function avisar(form, texto, tipo) {
    const aviso = form.querySelector(".aviso");
    aviso.className = "aviso aviso-" + tipo;
    aviso.textContent = texto;
    if (tipo === "error") {
      aviso.focus();
    }
  }

  // Muestra { mensaje, errores } del servidor. Devuelve el primer campo con error.
  function mostrarErrores(form, datos) {
    limpiarErrores(form);
    let primero = null;
    const sinCampo = [];
    for (const [nombre, texto] of Object.entries(datos.errores || {})) {
      const destino = form.querySelector(`#error-${nombre}`);
      const campo =
        form.querySelector(`[aria-describedby~="error-${nombre}"]`) || form.querySelector(`[name="${nombre}"]`);
      if (campo && destino) {
        campo.setAttribute("aria-invalid", "true");
        destino.textContent = texto;
        primero = primero || campo;
      } else {
        sinCampo.push(texto);
      }
    }
    avisar(form, [datos.mensaje, ...sinCampo].filter(Boolean).join(" "), "error");
    return primero;
  }

  // --- Progreso guardado (RNF-20) ---

  function guardar(form, clave, paso) {
    const valores = {};
    for (const campo of campos(form)) {
      if (campo.type !== "password" && campo.value !== "") {
        valores[campo.name] = campo.value;
      }
    }
    try {
      sessionStorage.setItem(clave, JSON.stringify({ paso, valores }));
    } catch (error) {
      // Almacenamiento no disponible: el formulario sigue funcionando.
    }
  }

  function recuperar(clave) {
    try {
      return JSON.parse(sessionStorage.getItem(clave)) || null;
    } catch (error) {
      return null;
    }
  }

  function olvidar(clave) {
    try {
      sessionStorage.removeItem(clave);
    } catch (error) {
      // Nada que hacer.
    }
  }

  // --- Pasos ---
  // Cada paso es un <fieldset class="paso">. "Continuar" solo exige los campos
  // marcados como required de ese paso; la validación real la hace el servidor.
  function porPasos(form, { clave, alRestaurar }) {
    const pasos = Array.from(form.querySelectorAll(".paso"));
    const progreso = form.querySelector(".progreso");
    let actual = 0;

    function mostrar(indice, enfocar = true) {
      actual = indice;
      pasos.forEach((paso, i) => {
        paso.hidden = i !== indice;
      });
      if (progreso) {
        progreso.textContent = `Paso ${indice + 1} de ${pasos.length}`;
      }
      guardar(form, clave, actual);
      if (enfocar) {
        const titulo = pasos[indice].querySelector("legend");
        if (titulo) {
          titulo.setAttribute("tabindex", "-1");
          titulo.focus();
        }
      }
    }

    function pasoDe(campo) {
      return pasos.findIndex((paso) => paso.contains(campo));
    }

    form.addEventListener("click", (evento) => {
      const boton = evento.target.closest("[data-paso]");
      if (!boton) {
        return;
      }
      evento.preventDefault();
      if (boton.dataset.paso === "siguiente") {
        const faltantes = Array.from(pasos[actual].querySelectorAll("[required]")).filter((c) => !c.value.trim());
        if (faltantes.length) {
          mostrarErrores(form, {
            mensaje: "Completa los datos marcados para continuar.",
            errores: Object.fromEntries(faltantes.map((c) => [c.name, "Completa este dato."])),
          });
          faltantes[0].focus();
          return;
        }
        limpiarErrores(form);
        mostrar(actual + 1);
      } else {
        limpiarErrores(form);
        mostrar(actual - 1);
      }
    });

    form.addEventListener("input", () => guardar(form, clave, actual));
    form.addEventListener("change", () => guardar(form, clave, actual));

    const previo = recuperar(clave);
    if (previo) {
      for (const [nombre, valor] of Object.entries(previo.valores || {})) {
        const campo = form.querySelector(`[name="${nombre}"]`);
        if (campo && campo.type !== "password") {
          campo.value = valor;
        }
      }
      Promise.resolve(alRestaurar ? alRestaurar(previo.valores || {}) : null).then(() => {
        mostrar(Math.min(previo.paso || 0, pasos.length - 1), false);
      });
    } else {
      mostrar(0, false);
    }

    return {
      irAlCampo(campo) {
        const indice = pasoDe(campo);
        if (indice >= 0 && indice !== actual) {
          mostrar(indice, false);
        }
        campo.focus();
      },
      terminar() {
        olvidar(clave);
      },
    };
  }

  function ocupado(form, sí) {
    const boton = form.querySelector('button[type="submit"]');
    if (boton) {
      boton.disabled = sí;
      boton.textContent = sí ? "Enviando…" : boton.dataset.texto || boton.textContent;
    }
  }

  function prepararBoton(form) {
    const boton = form.querySelector('button[type="submit"]');
    if (boton) {
      boton.dataset.texto = boton.textContent;
    }
  }

  // Casillas "Mostrar contraseña": <input type="checkbox" data-mostrar="id-del-campo">.
  document.addEventListener("change", (evento) => {
    const casilla = evento.target.closest("[data-mostrar]");
    if (casilla) {
      document.getElementById(casilla.dataset.mostrar).type = casilla.checked ? "text" : "password";
    }
  });

  return { leer, limpiarErrores, mostrarErrores, avisar, porPasos, ocupado, prepararBoton, recuperar, olvidar };
})();
