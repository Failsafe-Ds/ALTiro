// Etiquetas de estado y de motivo de cierre del pedido, en lenguaje de oficio
// (RNF-16, RNF-17; espejo de tickets/avisos.py, MOTIVOS_PARA_CLIENTE y
// MOTIVOS_PARA_MAESTRO). "pedido" por ticket y "horario" por bloque.
// Ningún estado depende solo del color: cada etiqueta lleva ícono y texto.
// Sin reglas de negocio: qué estado y qué motivo tiene un pedido lo decide el servidor.
"use strict";

const estadoPedido = (() => {
  const ESTADOS = {
    pendiente: { texto: "Pendiente de respuesta", icono: "⏳", clase: "estado-revision" },
    aceptado: { texto: "Aceptado", icono: "✓", clase: "estado-aprobado" },
    finalizado: { texto: "Trabajo terminado", icono: "★", clase: "estado-aprobado" },
    cerrado: { texto: "Cerrado", icono: "✕", clase: "estado-rechazado" },
  };
  const DESCONOCIDO = { texto: "Sin información", icono: "•", clase: "estado-revision" };

  // Motivo de cierre, en el lenguaje de quien lo lee (CA-08.2, CA-23.7).
  const MOTIVOS_CLIENTE = {
    vencido_plazo: "el maestro no respondió en 24 horas",
    vencido_proximidad: "faltaban 4 horas o menos para el horario y el maestro no respondió",
    cancelado_cliente: "lo cancelaste",
    rechazado_maestro: "el maestro no pudo tomarlo",
    bloque_tomado: "el maestro tomó otro trabajo en ese horario",
  };
  const MOTIVOS_MAESTRO = {
    vencido_plazo: "pasaron 24 horas sin tu respuesta",
    vencido_proximidad: "faltaban 4 horas o menos para el horario y no respondiste",
    cancelado_cliente: "el cliente lo canceló",
    rechazado_maestro: "lo rechazaste",
    bloque_tomado: "aceptaste otro trabajo en ese horario",
  };

  // <span class="estado …"><span aria-hidden="true">✓</span> Aceptado</span>
  function etiqueta(estado) {
    const datos = ESTADOS[estado] || DESCONOCIDO;
    const nodo = document.createElement("span");
    nodo.className = "estado " + datos.clase;
    const icono = document.createElement("span");
    icono.setAttribute("aria-hidden", "true");
    icono.textContent = datos.icono;
    nodo.append(icono, " " + datos.texto);
    return nodo;
  }

  function textoEstado(estado) {
    return (ESTADOS[estado] || DESCONOCIDO).texto;
  }

  // "el maestro no respondió en 24 horas" (sin punto ni mayúscula: se arma en la frase que lo use).
  function motivo(motivoCierre, esMaestro) {
    const tabla = esMaestro ? MOTIVOS_MAESTRO : MOTIVOS_CLIENTE;
    return tabla[motivoCierre] || "";
  }

  return { etiqueta, textoEstado, motivo, ESTADOS };
})();
