// Textos y piezas comunes de las páginas del expediente del maestro
// (mi-postulacion.html y mis-documentos.html; HU-11, HU-17, RF-08).
// - RNF-17: lenguaje del oficio. Los códigos de la API (en_revision,
//   licencia_sec…) nunca se muestran tal cual.
// - RNF-16: cada estado lleva ícono y texto, nunca solo color.
// Aquí no hay reglas de negocio: qué falta, qué vence y qué se aprueba lo
// decide el servidor (GET /api/maestros/expediente).
"use strict";

const expediente = (() => {
  const RUTA = "/api/maestros/expediente";

  // Estados del expediente (ADR-017, D-2).
  const ESTADOS_EXPEDIENTE = {
    en_revision: { texto: "En revisión", icono: "⏳", clase: "estado-revision" },
    observado: { texto: "Te pedimos corregir algo", icono: "⚠", clase: "estado-observado" },
    aprobado: { texto: "Aprobado", icono: "✓", clase: "estado-aprobado" },
    rechazado: { texto: "No aprobado", icono: "✕", clase: "estado-rechazado" },
    suspendido: { texto: "Suspendido", icono: "⏸", clase: "estado-suspendido" },
  };

  // Estados de un documento actual (ADR-017, D-2; "reemplazado" no se muestra al dueño).
  const ESTADOS_DOCUMENTO = {
    en_revision: ESTADOS_EXPEDIENTE.en_revision,
    observado: ESTADOS_EXPEDIENTE.observado,
    validado: ESTADOS_EXPEDIENTE.aprobado,
  };

  const DESCONOCIDO = { texto: "Sin información", icono: "•", clase: "estado-revision" };

  const ORDEN_TIPOS = ["cedula_identidad", "certificado_antecedentes", "licencia_sec"];

  const MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
  ];

  // Oficio regulado explicado sin siglas sueltas (RNF-17).
  const TEXTO_SEC = "licencia de la Superintendencia de Electricidad y Combustibles (SEC)";

  function nombreDocumento(tipo, oficio) {
    if (tipo === "cedula_identidad") {
      return "Cédula de identidad";
    }
    if (tipo === "certificado_antecedentes") {
      return "Certificado de antecedentes";
    }
    if (tipo === "licencia_sec") {
      return oficio ? `Licencia de ${oficio.nombre} (SEC)` : "Licencia (SEC)";
    }
    return "Documento";
  }

  // "2030-03-12" => "12 de marzo de 2030", sin pasar por la zona horaria.
  function formatearFecha(iso) {
    const partes = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
    if (!partes) {
      return "";
    }
    return `${Number(partes[3])} de ${MESES[Number(partes[2]) - 1]} de ${partes[1]}`;
  }

  // Fecha y hora de un instante ISO ("2026-09-28T17:05:00+00:00"), en la hora
  // de Chile (D-6): "28 de septiembre de 2026, 14:05".
  const FORMATO_FECHA_HORA = new Intl.DateTimeFormat("es-CL", {
    timeZone: "America/Santiago",
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });

  function formatearFechaHora(iso) {
    const instante = Date.parse(iso || "");
    return Number.isNaN(instante) ? "" : FORMATO_FECHA_HORA.format(instante);
  }

  // "12345678K" => "12.345.678-K".
  function formatearRut(rut) {
    if (!rut || rut.length < 2) {
      return rut || "";
    }
    const cuerpo = rut.slice(0, -1).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return cuerpo + "-" + rut.slice(-1);
  }

  // <span class="estado …"><span aria-hidden="true">⏳</span> En revisión</span>
  function etiquetaEstado(estado, tabla) {
    const datos = tabla[estado] || DESCONOCIDO;
    const etiqueta = document.createElement("span");
    etiqueta.className = "estado " + datos.clase;
    const icono = document.createElement("span");
    icono.setAttribute("aria-hidden", "true");
    icono.textContent = datos.icono;
    etiqueta.append(icono, " " + datos.texto);
    return etiqueta;
  }

  // Clave de un requisito o documento: tipo más oficio (solo las licencias).
  function clave(tipo, oficio) {
    return oficio ? `${tipo}:${oficio.codigo}` : tipo;
  }

  // Requisitos que ve el maestro, en orden: los documentos que ya entregó más
  // los que el servidor informa como faltantes (ADR-017, E-2). No se calculan
  // aquí: se toman de la respuesta.
  function requisitos(datos) {
    const vistos = new Map();
    for (const documento of datos.documentos) {
      vistos.set(clave(documento.tipo, documento.oficio), { tipo: documento.tipo, oficio: documento.oficio, documento });
    }
    for (const faltante of datos.faltantes) {
      const k = clave(faltante.tipo, faltante.oficio);
      if (!vistos.has(k)) {
        vistos.set(k, { tipo: faltante.tipo, oficio: faltante.oficio, documento: null });
      }
    }
    const posicionOficio = (oficio) => {
      const i = oficio ? datos.oficios.findIndex((o) => o.codigo === oficio.codigo) : -1;
      return i < 0 ? datos.oficios.length : i;
    };
    return Array.from(vistos.values()).sort(
      (a, b) =>
        ORDEN_TIPOS.indexOf(a.tipo) - ORDEN_TIPOS.indexOf(b.tipo) || posicionOficio(a.oficio) - posicionOficio(b.oficio)
    );
  }

  // Aviso de sesión terminada con enlace para volver a ingresar y seguir
  // en la misma página ("siguiente" es una clave de la lista cerrada de ingresar.js).
  function avisarSesionTerminada(aviso, siguiente, textoExtra) {
    const enlace = document.createElement("a");
    enlace.className = "boton";
    enlace.href = `ingresar.html?aviso=sesion&siguiente=${siguiente}`;
    enlace.textContent = "Ingresar de nuevo";
    aviso.className = "aviso aviso-error";
    aviso.replaceChildren(["Tu sesión terminó.", textoExtra, "Vuelve a ingresar para continuar."].filter(Boolean).join(" "), enlace);
    aviso.focus();
  }

  // La cuenta no es de maestro (403 de la API): se explica y se ofrece "Mi cuenta".
  function avisarNoMaestro(aviso) {
    const enlace = document.createElement("a");
    enlace.className = "boton";
    enlace.href = "cuenta.html";
    enlace.textContent = "Ir a mi cuenta";
    aviso.className = "aviso aviso-error";
    aviso.replaceChildren(
      "Esta página es para maestros. Si quieres trabajar como maestro, postula desde «Mi cuenta».",
      enlace
    );
    aviso.focus();
  }

  // Error al cargar (sin conexión o servidor sin responder): mensaje y "Reintentar".
  function avisarErrorCarga(aviso, mensaje, reintentar) {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.textContent = "Reintentar";
    boton.addEventListener("click", reintentar);
    aviso.className = "aviso aviso-error";
    aviso.replaceChildren(mensaje, boton);
    aviso.focus();
  }

  function limpiarAviso(aviso) {
    aviso.className = "aviso";
    aviso.replaceChildren();
  }

  return {
    RUTA,
    ESTADOS_EXPEDIENTE,
    ESTADOS_DOCUMENTO,
    TEXTO_SEC,
    nombreDocumento,
    formatearFecha,
    formatearFechaHora,
    formatearRut,
    etiquetaEstado,
    clave,
    requisitos,
    avisarSesionTerminada,
    avisarNoMaestro,
    avisarErrorCarga,
    limpiarAviso,
  };
})();
