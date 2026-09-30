// Indicadores base y exportación agregada (HU-22, RF-38, CA-22.1, CA-22.2; ADR-026, E-6).
// - GET /api/gestion/indicadores?desde=&hasta=: los tres indicadores con su definición.
// - GET /api/gestion/exportacion?desde=&hasta=: archivo CSV agregado (se descarga).
// El servidor exige el rol control_gestion y valida el período (31 a 366 días);
// sus errores por campo se muestran junto a cada fecha.
"use strict";

(() => {
  const DIAS_POR_DEFECTO = 90;
  const form = document.getElementById("formulario-periodo");
  const desde = document.getElementById("desde");
  const hasta = document.getElementById("hasta");
  const exportar = document.getElementById("exportar");
  const cargando = document.getElementById("cargando");
  const resultados = document.getElementById("resultados");
  formulario.prepararBoton(form);

  function fechaIso(fecha) {
    // Fecha local del teléfono o computador, en AAAA-MM-DD.
    const mes = String(fecha.getMonth() + 1).padStart(2, "0");
    const dia = String(fecha.getDate()).padStart(2, "0");
    return `${fecha.getFullYear()}-${mes}-${dia}`;
  }

  const hoy = new Date();
  const inicio = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - (DIAS_POR_DEFECTO - 1));
  hasta.value = fechaIso(hoy);
  desde.value = fechaIso(inicio);

  function consulta() {
    return new URLSearchParams({ desde: desde.value, hasta: hasta.value }).toString();
  }

  function numero(valor, decimales = 0) {
    return valor.toLocaleString("es-CL", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
  }

  function duracion(minutos) {
    if (minutos < 60) {
      return `${minutos} min`;
    }
    const horas = Math.floor(minutos / 60);
    const resto = minutos % 60;
    return resto ? `${horas} h ${resto} min` : `${horas} h`;
  }

  function escribir(id, texto) {
    document.getElementById(id).textContent = texto;
  }

  function tratarError(estado, datos) {
    if (estado === 401) {
      const enlace = document.createElement("a");
      enlace.className = "boton";
      enlace.href = "ingresar.html?aviso=sesion&siguiente=indicadores";
      enlace.textContent = "Ingresar de nuevo";
      formulario.mostrarErrores(form, { mensaje: "Tu sesión terminó. Vuelve a ingresar para seguir.", errores: {} });
      form.querySelector(".aviso").append(" ", enlace);
      return;
    }
    formulario.mostrarErrores(form, datos || { mensaje: "No pudimos completar la acción. Inténtalo de nuevo.", errores: {} });
  }

  function pintar(datos) {
    const c = datos.concrecion;
    escribir("valor-concrecion", c.porcentaje === null ? "Sin pedidos en el período" : `${numero(c.porcentaje, 1)} %`);
    escribir("detalle-concrecion", `${numero(c.concretados)} de ${numero(c.enviados)} pedidos enviados.`);
    escribir("definicion-concrecion", c.definicion);

    const r = datos.primera_respuesta;
    escribir("valor-primera-respuesta", r.mediana_minutos === null ? "Sin respuestas en el período" : duracion(r.mediana_minutos));
    escribir("detalle-primera-respuesta", `Mediana de ${numero(r.cantidad)} pedidos respondidos: la mitad se respondió en menos tiempo que este y la otra mitad en más.`);
    escribir("definicion-primera-respuesta", r.definicion);

    const v = datos.vigencia_documental;
    escribir("valor-vigencia", v.porcentaje === null ? "Sin maestros aprobados" : `${numero(v.porcentaje, 1)} %`);
    escribir("detalle-vigencia", `${numero(v.vigentes)} de ${numero(v.aprobados)} maestros aprobados, a la fecha de hoy.`);
    escribir("definicion-vigencia", v.definicion);

    resultados.hidden = false;
    document.getElementById("titulo-resultados").focus();
  }

  async function consultar() {
    formulario.limpiarErrores(form);
    cargando.hidden = false;
    const { estado, datos } = await api.obtener(`/api/gestion/indicadores?${consulta()}`);
    cargando.hidden = true;
    if (estado !== 200) {
      resultados.hidden = true;
      tratarError(estado, datos);
      return;
    }
    pintar(datos);
  }

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const boton = form.querySelector('button[type="submit"]');
    boton.disabled = true;
    await consultar();
    boton.disabled = false;
  });

  // El CSV se pide con fetch para mostrar los errores del período junto a cada
  // fecha; si llega bien, se descarga con el nombre que indica el servidor.
  exportar.addEventListener("click", async () => {
    formulario.limpiarErrores(form);
    exportar.disabled = true;
    exportar.textContent = "Preparando archivo…";
    let respuesta = null;
    try {
      respuesta = await fetch(`/api/gestion/exportacion?${consulta()}`, { credentials: "same-origin" });
    } catch (error) {
      respuesta = null;
    }
    exportar.disabled = false;
    exportar.textContent = "Exportar CSV";
    if (!respuesta) {
      tratarError(0, { mensaje: "No pudimos conectarnos. Revisa tu señal o tu wifi e inténtalo de nuevo.", errores: {} });
      return;
    }
    if (respuesta.status !== 200) {
      tratarError(respuesta.status, await respuesta.json().catch(() => null));
      return;
    }
    const disposicion = respuesta.headers.get("Content-Disposition") || "";
    const nombre = (disposicion.match(/filename="([^"]+)"/) || [])[1] || "altiro-agregado.csv";
    const url = URL.createObjectURL(await respuesta.blob());
    const enlace = document.createElement("a");
    enlace.href = url;
    enlace.download = nombre;
    document.body.append(enlace);
    enlace.click();
    enlace.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    const aviso = form.querySelector(".aviso");
    aviso.className = "aviso aviso-exito";
    aviso.textContent = `Listo: se descargó ${nombre}.`;
    aviso.focus();
  });

  consultar();
})();
