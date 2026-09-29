// Formatos de pantalla compartidos (propuesta del S3, §5).
// - monto(n): pesos chilenos con Intl.NumberFormat("es-CL"): 85000 => "$85.000".
// - hora(minutos): hora de 24 h "HH:MM" desde los minutos después de la
//   medianoche (ADR-020, D-10): 480 => "08:00"; 1440 => "24:00".
// - leerMonto(texto): quita puntos, espacios y el signo "$" que la persona
//   escriba ("$ 85.000" => "85000"). No valida: si lo escrito no es un número,
//   se devuelve tal cual para que el servidor responda con su mensaje (RNF-15).
// - fechaLarga, fechaConReferencia, hoyEnChile, sumarDias: días de calendario
//   "AAAA-MM-DD" en español (búsqueda y ficha del maestro, S4).
// Sin reglas de negocio: los topes y mínimos los decide el servidor.
"use strict";

const formato = (() => {
  const PESOS = new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });

  function monto(valor) {
    return typeof valor === "number" && Number.isFinite(valor) ? PESOS.format(valor) : "";
  }

  function dosDigitos(numero) {
    return String(numero).padStart(2, "0");
  }

  function hora(minutos) {
    if (!Number.isInteger(minutos) || minutos < 0 || minutos > 1440) {
      return "";
    }
    return `${dosDigitos(Math.floor(minutos / 60))}:${dosDigitos(minutos % 60)}`;
  }

  // Devuelve "" si no se escribió nada, una cadena de solo dígitos si lo
  // escrito es un número, o el texto original (recortado) si no lo es.
  function leerMonto(texto) {
    const limpio = String(texto || "").trim();
    const digitos = limpio.replace(/[\s.$]/g, "");
    return /^\d+$/.test(digitos) ? digitos : limpio;
  }

  // Igual que leerMonto, pero como número (para campos que el servidor exige
  // enteros, como el precio de referencia). Lo que no es número se devuelve tal cual.
  function leerEntero(texto) {
    const valor = leerMonto(texto);
    return /^\d{1,15}$/.test(valor) ? Number(valor) : valor;
  }

  // --- Fechas de calendario "AAAA-MM-DD" (búsqueda y ficha del maestro, S4) ---
  // Se tratan como días de calendario, sin hora: se arman en UTC y se
  // muestran en UTC para que la zona del teléfono no corra el día.
  const FECHA_ISO = /^(\d{4})-(\d{2})-(\d{2})$/;
  const LARGA = new Intl.DateTimeFormat("es-CL", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
  // "en-CA" da el día como "AAAA-MM-DD".
  const DIA_CHILE = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Santiago",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });

  function aFecha(iso) {
    const partes = FECHA_ISO.exec(iso || "");
    return partes ? new Date(Date.UTC(Number(partes[1]), Number(partes[2]) - 1, Number(partes[3]))) : null;
  }

  // "martes 6 de octubre"; "" si no es una fecha. Se arma por partes para no
  // depender de la coma que algunos navegadores ponen después del día.
  function fechaLarga(iso) {
    const fecha = aFecha(iso);
    if (!fecha) {
      return "";
    }
    const partes = Object.fromEntries(LARGA.formatToParts(fecha).map((p) => [p.type, p.value]));
    return `${partes.weekday} ${partes.day} de ${partes.month}`;
  }

  // Día de hoy en Chile continental ("AAAA-MM-DD"). Solo para armar la lista
  // de días que se ofrecen; el servidor decide qué días valen.
  function hoyEnChile() {
    return DIA_CHILE.format(new Date());
  }

  // "AAAA-MM-DD" de iso + dias.
  function sumarDias(iso, dias) {
    const fecha = aFecha(iso);
    if (!fecha) {
      return "";
    }
    fecha.setUTCDate(fecha.getUTCDate() + dias);
    return fecha.toISOString().slice(0, 10);
  }

  // "Hoy, martes 29 de septiembre", "Mañana, …" o "Jueves 1 de octubre".
  function fechaConReferencia(iso, hoy = hoyEnChile()) {
    const larga = fechaLarga(iso);
    if (!larga) {
      return "";
    }
    if (iso === hoy) {
      return `Hoy, ${larga}`;
    }
    if (iso === sumarDias(hoy, 1)) {
      return `Mañana, ${larga}`;
    }
    return larga.charAt(0).toUpperCase() + larga.slice(1);
  }

  return { monto, hora, leerMonto, leerEntero, fechaLarga, hoyEnChile, sumarDias, fechaConReferencia };
})();
