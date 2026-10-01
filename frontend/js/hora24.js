// Selector propio de hora de 24 horas (ADR-020, punto 2; CA-14.1).
// Nunca <input type="time">, que en algunos teléfonos muestra AM/PM. Cada hora
// se elige con dos <select>: la hora (00 a 23 para un inicio, 00 a 24 para un
// término) y los minutos (00 o 30). "24" solo admite ":00" (fin del día).
// Lo usan «Mi agenda» (agenda.js) y la búsqueda (buscar.js).
// Sin reglas de negocio: qué horario es válido lo decide el servidor.
"use strict";

const hora24 = (() => {
  const MINUTOS = ["00", "30"];

  const opcion = dom.opcion;

  // Si la hora elegida es 24, los minutos quedan en 00 y "30" se desactiva.
  function ajustar(selectHora, selectMinutos) {
    const esFinDelDia = selectHora.value === "24";
    const media = selectMinutos.querySelector('option[value="30"]');
    if (media) {
      media.disabled = esFinDelDia;
    }
    if (esFinDelDia) {
      selectMinutos.value = "00";
    }
  }

  // Llena las listas. esTermino: la hora llega hasta 24 (un término);
  // si no, hasta 23 (un horario no empieza a las 24:00).
  function preparar(selectHora, selectMinutos, { esTermino = false, textoVacio = "Elige" } = {}) {
    const hasta = esTermino ? 24 : 23;
    const horas = [opcion("", textoVacio)];
    for (let hora = 0; hora <= hasta; hora += 1) {
      const texto = String(hora).padStart(2, "0");
      horas.push(opcion(texto, texto));
    }
    selectHora.replaceChildren(...horas);
    selectMinutos.replaceChildren(...MINUTOS.map((m) => opcion(m, m)));
    if (esTermino) {
      selectHora.addEventListener("change", () => ajustar(selectHora, selectMinutos));
    }
  }

  // "HH:MM" elegido, o "" si no se eligió la hora.
  function leer(selectHora, selectMinutos) {
    return selectHora.value ? `${selectHora.value}:${selectMinutos.value || "00"}` : "";
  }

  // Pone "HH:MM" en las listas si existe entre las opciones; si no, las deja en blanco.
  function poner(selectHora, selectMinutos, valor) {
    const partes = /^(\d{2}):(\d{2})$/.exec(valor || "");
    const existe = (select, v) => Array.from(select.options).some((o) => o.value === v);
    if (partes && existe(selectHora, partes[1]) && existe(selectMinutos, partes[2])) {
      selectHora.value = partes[1];
      selectMinutos.value = partes[2];
    } else {
      selectHora.value = "";
      selectMinutos.value = "00";
    }
    ajustar(selectHora, selectMinutos);
  }

  return { preparar, ajustar, leer, poner };
})();
