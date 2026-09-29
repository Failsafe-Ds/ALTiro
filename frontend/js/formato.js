// Formatos de pantalla compartidos (propuesta del S3, §5).
// - monto(n): pesos chilenos con Intl.NumberFormat("es-CL"): 85000 => "$85.000".
// - hora(minutos): hora de 24 h "HH:MM" desde los minutos después de la
//   medianoche (ADR-020, D-10): 480 => "08:00"; 1440 => "24:00".
// - leerMonto(texto): quita puntos, espacios y el signo "$" que la persona
//   escriba ("$ 85.000" => "85000"). No valida: si lo escrito no es un número,
//   se devuelve tal cual para que el servidor responda con su mensaje (RNF-15).
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

  return { monto, hora, leerMonto, leerEntero };
})();
