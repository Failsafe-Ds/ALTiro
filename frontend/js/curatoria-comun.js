// Textos y piezas comunes de las páginas de curatoría (HU-19, HU-25; propuesta
// del S2, §5): cola (curatoria.html) y detalle (curatoria-expediente.html).
// - RNF-15: ningún código de la API (en_revision, licencia_sec…) se muestra tal cual.
// - RNF-16: cada estado lleva ícono y texto, nunca solo color.
// - Sin reglas de negocio: qué transiciones hay, qué falta y qué está
//   habilitado lo informa el servidor.
"use strict";

const curatoria = (() => {
  const RUTA = "/api/curatoria";

  // Estados del expediente con el nombre administrativo (ADR-017, D-2).
  const ESTADOS_EXPEDIENTE = {
    en_revision: { texto: "En revisión", icono: "⏳", clase: "estado-revision" },
    observado: { texto: "Observado", icono: "⚠", clase: "estado-observado" },
    aprobado: { texto: "Aprobado", icono: "✓", clase: "estado-aprobado" },
    rechazado: { texto: "Rechazado", icono: "✕", clase: "estado-rechazado" },
    suspendido: { texto: "Suspendido", icono: "⏸", clase: "estado-suspendido" },
  };

  // Estados de un documento, incluido "reemplazado", que solo ve curatoría (ADR-017, E-3).
  const ESTADOS_DOCUMENTO = {
    en_revision: ESTADOS_EXPEDIENTE.en_revision,
    observado: ESTADOS_EXPEDIENTE.observado,
    validado: { texto: "Validado", icono: "✓", clase: "estado-aprobado" },
    reemplazado: { texto: "Reemplazado", icono: "↺", clase: "estado-suspendido" },
  };

  // Filtros de la cola: valores que acepta ?estado= (vistas_curatoria.cola).
  const FILTROS = [
    { valor: "en_revision", texto: "En revisión" },
    { valor: "observado", texto: "Observados" },
    { valor: "aprobado", texto: "Aprobados" },
    { valor: "suspendido", texto: "Suspendidos" },
    { valor: "rechazado", texto: "Rechazados" },
    { valor: "", texto: "Todos" },
  ];

  // Formato de la referencia pública (UUID; ADR-011). Solo evita pedir a la API
  // una dirección mal copiada: la validez real la decide el servidor.
  const FORMATO_REF = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

  function nombreOficios(oficios) {
    return oficios.map((o) => o.nombre).join(", ");
  }

  function enlaceBoton(texto, href, secundario) {
    const enlace = document.createElement("a");
    enlace.className = secundario ? "boton boton-secundario" : "boton";
    enlace.href = href;
    enlace.textContent = texto;
    return enlace;
  }

  // Aviso con texto y acciones; recibe el foco para que el lector de pantalla lo lea.
  function avisar(aviso, tipo, texto, ...acciones) {
    aviso.className = "aviso aviso-" + tipo;
    aviso.replaceChildren(texto, ...acciones);
    aviso.focus();
  }

  function avisarSesionTerminada(aviso) {
    avisar(
      aviso,
      "error",
      "Tu sesión terminó. Vuelve a ingresar para seguir revisando expedientes.",
      enlaceBoton("Ingresar de nuevo", "ingresar.html?aviso=sesion&siguiente=curatoria")
    );
  }

  // 403 por falta del rol (el texto del servidor es genérico; aquí se nombra la sección).
  function avisarSinRol(aviso) {
    avisar(
      aviso,
      "error",
      "Esta sección es para curatoría. Tu cuenta no tiene acceso a ella.",
      enlaceBoton("Ir a mi cuenta", "cuenta.html")
    );
  }

  function avisarErrorCarga(aviso, mensaje, reintentar) {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.textContent = "Reintentar";
    boton.addEventListener("click", reintentar);
    avisar(aviso, "error", mensaje, boton);
  }

  function limpiar(aviso) {
    aviso.className = "aviso";
    aviso.replaceChildren();
  }

  return {
    RUTA,
    ESTADOS_EXPEDIENTE,
    ESTADOS_DOCUMENTO,
    FILTROS,
    FORMATO_REF,
    nombreOficios,
    enlaceBoton,
    avisar,
    avisarSesionTerminada,
    avisarSinRol,
    avisarErrorCarga,
    limpiar,
  };
})();
