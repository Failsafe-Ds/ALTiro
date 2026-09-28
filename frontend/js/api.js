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
    // Señal interna (ADR-006, E-1): solo el rechazo CSRF lleva esta cabecera.
    const rechazoCsrf = respuesta.status === 403 && respuesta.headers.get("AlTiro-Rechazo") === "csrf";
    if (respuesta.status === 204) {
      return { estado: 204, datos: null, rechazoCsrf };
    }
    const cuerpo = await respuesta.json().catch(() => null);
    return { estado: respuesta.status, datos: cuerpo || RESPUESTA_ILEGIBLE, rechazoCsrf };
  }

  async function pedir(metodo, ruta, datos) {
    if (metodo !== "GET" && !leerCookie("csrftoken")) {
      await renovarCsrf();
    }
    let resultado = await ejecutar(metodo, ruta, datos);
    // ADR-006, Enmienda E-1 (y ADR-011, E-1): se reintenta una sola vez, tras
    // pedir un token nuevo, solo si el método cambia datos, la respuesta es 403
    // y trae "AlTiro-Rechazo: csrf" (token vencido o rotado tras iniciar sesión).
    // Ese rechazo ocurre antes de ejecutar la vista, así que no tuvo efectos.
    // Cualquier otro 403 (por ejemplo, falta de rol) no se reintenta: repetirlo
    // duplicaría el registro en acceso_denegado. El resultado del reintento se
    // devuelve tal cual, aunque sea otro 403.
    if (metodo !== "GET" && resultado.rechazoCsrf) {
      await renovarCsrf();
      resultado = await ejecutar(metodo, ruta, datos);
    }
    // La señal no sale de este módulo: las páginas reciben { estado, datos }.
    return { estado: resultado.estado, datos: resultado.datos };
  }

  return {
    obtener: (ruta) => pedir("GET", ruta),
    enviar: (ruta, datos) => pedir("POST", ruta, datos),
    borrar: (ruta) => pedir("DELETE", ruta),
  };
})();
