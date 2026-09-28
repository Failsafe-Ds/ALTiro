// Cliente de la API JSON bajo /api/ (ADR-002).
// - Envía el token CSRF en X-CSRFToken en toda operación que cambia datos (ADR-006).
// - Nunca lanza excepciones: siempre devuelve { estado, datos } con datos en el
//   formato común { mensaje, errores } cuando hay error (RNF-15).
// - Sin conexión devuelve estado 0 y un mensaje accionable (RNF-20).
"use strict";

const api = (() => {
  const SIN_CONEXION = {
    mensaje: "No pudimos conectarnos. Revisa tu señal o tu wifi e inténtalo de nuevo. Lo que escribiste sigue aquí.",
    errores: {},
  };
  const RESPUESTA_ILEGIBLE = {
    mensaje: "Tuvimos un problema al procesar tu solicitud. Inténtalo de nuevo en unos minutos.",
    errores: {},
  };

  function leerCookie(nombre) {
    const par = document.cookie.split("; ").find((c) => c.startsWith(nombre + "="));
    return par ? decodeURIComponent(par.split("=")[1]) : "";
  }

  async function renovarCsrf() {
    try {
      await fetch("/api/sesion/csrf", { credentials: "same-origin" });
    } catch (error) {
      // Sin conexión: la petición siguiente devolverá el aviso correspondiente.
    }
  }

  async function ejecutar(metodo, ruta, datos) {
    const cabeceras = { Accept: "application/json" };
    const opciones = { method: metodo, credentials: "same-origin", headers: cabeceras };
    if (metodo !== "GET") {
      cabeceras["X-CSRFToken"] = leerCookie("csrftoken");
    }
    if (datos !== undefined) {
      cabeceras["Content-Type"] = "application/json";
      opciones.body = JSON.stringify(datos);
    }
    let respuesta;
    try {
      respuesta = await fetch(ruta, opciones);
    } catch (error) {
      return { estado: 0, datos: SIN_CONEXION };
    }
    if (respuesta.status === 204) {
      return { estado: 204, datos: null };
    }
    const cuerpo = await respuesta.json().catch(() => null);
    return { estado: respuesta.status, datos: cuerpo || RESPUESTA_ILEGIBLE };
  }

  async function pedir(metodo, ruta, datos) {
    if (metodo !== "GET" && !leerCookie("csrftoken")) {
      await renovarCsrf();
    }
    let resultado = await ejecutar(metodo, ruta, datos);
    // Token CSRF vencido o rotado (por ejemplo, tras iniciar sesión): se pide
    // uno nuevo y se reintenta una sola vez.
    if (resultado.estado === 403 && metodo !== "GET") {
      await renovarCsrf();
      resultado = await ejecutar(metodo, ruta, datos);
    }
    return resultado;
  }

  return {
    obtener: (ruta) => pedir("GET", ruta),
    enviar: (ruta, datos) => pedir("POST", ruta, datos),
    borrar: (ruta) => pedir("DELETE", ruta),
  };
})();
