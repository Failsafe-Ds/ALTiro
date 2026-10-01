// Cliente de la API JSON bajo /api/ (ADR-002).
// - Envía el token CSRF en X-CSRFToken en toda operación que cambia datos (ADR-006).
// - Nunca lanza excepciones: siempre devuelve { estado, datos } con datos en el
//   formato común { mensaje, errores } cuando hay error (RNF-15).
// - Sin conexión devuelve estado 0 y un mensaje accionable (RNF-20). Al leer
//   (GET) no hay nada escrito que conservar: el mensaje pide tocar «Reintentar»,
//   y cada página que muestra ese error ofrece ese botón (hallazgo UX E-2).
// - 429 (demasiadas solicitudes): el de la app (ADR-007) y el del proxy
//   (ADR-029) traen { mensaje, errores } en español. Si el cuerpo no se puede
//   leer, el mensaje se arma con Retry-After (segundos) para decir cuánto esperar.
"use strict";

const api = (() => {
  const SIN_CONEXION = {
    mensaje: "No pudimos conectarnos. Revisa tu señal o tu wifi e inténtalo de nuevo. Lo que escribiste sigue aquí.",
    errores: {},
  };
  const SIN_CONEXION_LECTURA = {
    mensaje: "No pudimos conectarnos. Revisa tu señal o tu wifi y toca «Reintentar».",
    errores: {},
  };
  const RESPUESTA_ILEGIBLE = {
    mensaje: "Tuvimos un problema al procesar tu solicitud. Inténtalo de nuevo en unos minutos.",
    errores: {},
  };

  function demasiadasSolicitudes(retryAfter) {
    const segundos = Number.parseInt(retryAfter || "", 10);
    let espera = "un momento";
    if (Number.isFinite(segundos) && segundos > 0) {
      const minutos = Math.ceil(segundos / 60);
      espera = segundos < 60 ? `${segundos} segundos` : minutos === 1 ? "1 minuto" : `${minutos} minutos`;
    }
    return {
      mensaje: `Recibimos demasiadas solicitudes seguidas. Espera ${espera} y vuelve a intentarlo. Lo que escribiste sigue aquí.`,
      errores: {},
    };
  }

  // Cuerpo de respuesta a entregar a la página cuando no trae { mensaje }.
  function cuerpoOFalla(cuerpo, estado, retryAfter) {
    if (cuerpo && typeof cuerpo.mensaje === "string") {
      return cuerpo;
    }
    if (estado === 429) {
      return demasiadasSolicitudes(retryAfter);
    }
    return cuerpo || RESPUESTA_ILEGIBLE;
  }

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
      return { estado: 0, datos: metodo === "GET" ? SIN_CONEXION_LECTURA : SIN_CONEXION };
    }
    // Señal interna (ADR-006, E-1): solo el rechazo CSRF lleva esta cabecera.
    const rechazoCsrf = respuesta.status === 403 && respuesta.headers.get("AlTiro-Rechazo") === "csrf";
    if (respuesta.status === 204) {
      return { estado: 204, datos: null, rechazoCsrf };
    }
    const cuerpo = await respuesta.json().catch(() => null);
    const cuerpoFinal = cuerpoOFalla(cuerpo, respuesta.status, respuesta.headers.get("Retry-After"));
    return { estado: respuesta.status, datos: cuerpoFinal, rechazoCsrf };
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

  // --- Envío de archivos (fotos de documentos, RF-04; ADR-015) ---
  // Se usa XMLHttpRequest porque fetch no informa el avance de la subida, y el
  // maestro con señal débil necesita ver que la foto avanza ("Enviando… 40 %").
  // Mismo formato de respuesta y mismas reglas que pedir(): CSRF en
  // X-CSRFToken, reintento único solo ante 403 con "AlTiro-Rechazo: csrf"
  // (ADR-006, E-1), estado 0 sin conexión (RNF-20) y el 413 del proxy, que
  // llega en JSON con el formato común.
  function subir(ruta, formData, alProgreso) {
    return new Promise((resolver) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", ruta);
      xhr.setRequestHeader("Accept", "application/json");
      xhr.setRequestHeader("X-CSRFToken", leerCookie("csrftoken"));
      // Content-Type lo pone el navegador (multipart con su separador).
      if (alProgreso) {
        xhr.upload.addEventListener("progress", (evento) => {
          if (evento.lengthComputable && evento.total > 0) {
            alProgreso(evento.loaded / evento.total);
          }
        });
      }
      xhr.addEventListener("load", () => {
        const rechazoCsrf = xhr.status === 403 && xhr.getResponseHeader("AlTiro-Rechazo") === "csrf";
        let cuerpo = null;
        try {
          cuerpo = JSON.parse(xhr.responseText);
        } catch (error) {
          cuerpo = null;
        }
        if (xhr.status === 0) {
          resolver({ estado: 0, datos: SIN_CONEXION });
          return;
        }
        const cuerpoFinal = cuerpoOFalla(cuerpo, xhr.status, xhr.getResponseHeader("Retry-After"));
        resolver({ estado: xhr.status, datos: cuerpoFinal, rechazoCsrf });
      });
      for (const falla of ["error", "abort", "timeout"]) {
        xhr.addEventListener(falla, () => resolver({ estado: 0, datos: SIN_CONEXION }));
      }
      xhr.send(formData);
    });
  }

  async function enviarArchivo(ruta, formData, alProgreso) {
    if (!leerCookie("csrftoken")) {
      await renovarCsrf();
    }
    let resultado = await subir(ruta, formData, alProgreso);
    // Misma regla que en pedir(): el rechazo CSRF ocurre antes de la vista, sin efectos.
    if (resultado.rechazoCsrf) {
      await renovarCsrf();
      resultado = await subir(ruta, formData, alProgreso);
    }
    return { estado: resultado.estado, datos: resultado.datos };
  }

  return {
    obtener: (ruta) => pedir("GET", ruta),
    enviar: (ruta, datos) => pedir("POST", ruta, datos),
    modificar: (ruta, datos) => pedir("PATCH", ruta, datos),
    // PUT: reemplaza el recurso completo (cobertura del maestro, ADR-019, punto 4).
    reemplazar: (ruta, datos) => pedir("PUT", ruta, datos),
    borrar: (ruta) => pedir("DELETE", ruta),
    enviarArchivo,
  };
})();
