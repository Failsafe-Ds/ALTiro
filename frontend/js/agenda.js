// Mi agenda (HU-14, RF-07, CA-14.1, CA-14.2, CA-14.4; ADR-020).
// - GET y POST /api/maestros/disponibilidad: {"dia_semana": 1, "inicio": "08:00", "fin": "12:00"}.
// - DELETE /api/maestros/disponibilidad/<ref>: quitar un horario (con confirmación en la página).
// - CA-14.1: horas en formato de 24 horas, con un selector propio (hora 00–24 y
//   minutos 00 o 30), nunca <input type="time">, que en algunos teléfonos
//   muestra AM/PM (ADR-020, punto 2). Se muestran con formato.hora(); el fin
//   del día es 24:00.
// - CA-14.2: el servidor rechaza un término que no sea posterior al inicio (y
//   el cruce de medianoche) y un horario que se cruce con otro; el mensaje se
//   muestra junto al campo ("inicio" o "fin").
// - CA-14.4: cada horario se guarda en su propia petición. Lo que se está
//   eligiendo y no se ha guardado se conserva en sessionStorage (con
//   vencimiento, formulario.guardarDatos) por si se corta la señal.
// Sin reglas de negocio: qué horario es válido lo decide el servidor.
"use strict";

(() => {
  const RUTA = "/api/maestros/disponibilidad";
  const CLAVE = "altiro.agenda.nuevo";
  const DIAS = { 1: "lunes", 2: "martes", 3: "miércoles", 4: "jueves", 5: "viernes", 6: "sábado", 7: "domingo" };

  const cargando = document.getElementById("cargando");
  const avisoPagina = document.getElementById("aviso-pagina");
  const avisoResultado = document.getElementById("aviso-resultado");
  const contenido = document.getElementById("contenido");
  const listaDias = document.getElementById("lista-dias");
  const main = document.querySelector("main");

  const seccionAgregar = document.getElementById("seccion-agregar");
  const abrirAgregar = document.getElementById("abrir-agregar");
  const form = document.getElementById("form-bloque");
  const selectDia = document.getElementById("dia");
  const inicioHora = document.getElementById("inicio-hora");
  const inicioMinutos = document.getElementById("inicio-minutos");
  const finHora = document.getElementById("fin-hora");
  const finMinutos = document.getElementById("fin-minutos");
  const resumen = document.getElementById("resumen-bloque");

  const confirmarQuitar = document.getElementById("confirmar-quitar");
  const avisoQuitar = document.getElementById("aviso-quitar");

  let bloques = [];
  let quitando = null;

  // Guarda el texto del botón para devolverlo después de "Enviando…".
  formulario.prepararBoton(form);

  const elemento = dom.elemento;

  function mayuscula(texto) {
    return texto ? texto.charAt(0).toUpperCase() + texto.slice(1) : "";
  }

  function nombreDia(bloque) {
    return bloque.dia || DIAS[bloque.dia_semana] || "";
  }

  // "de 08:00 a 12:00", siempre en 24 horas (CA-14.1).
  function rango(bloque) {
    return `de ${formato.hora(bloque.inicio_min)} a ${formato.hora(bloque.fin_min)}`;
  }

  function avisarResultado(texto) {
    avisoResultado.className = "aviso aviso-exito";
    avisoResultado.textContent = texto;
    avisoResultado.focus();
  }

  function limpiarResultado() {
    avisoResultado.className = "aviso";
    avisoResultado.textContent = "";
  }

  function avisarPagina(texto) {
    avisoPagina.className = "aviso aviso-error";
    avisoPagina.textContent = texto;
    avisoPagina.focus();
  }

  // --- Selector de 24 horas (ADR-020), compartido con la búsqueda (hora24.js) ---

  // La hora de inicio va de 00 a 23 (un horario no empieza a las 24:00); el
  // término, de 00 a 24. "24" solo admite ":00" (no existe 24:30).
  hora24.preparar(inicioHora, inicioMinutos);
  hora24.preparar(finHora, finMinutos, { esTermino: true });

  function ajustarFinDelDia() {
    hora24.ajustar(finHora, finMinutos);
  }

  function horaElegida(selectHora, selectMinutos) {
    return hora24.leer(selectHora, selectMinutos);
  }

  // Resumen en palabras de lo que se va a guardar (CA-14.1: siempre en 24 horas).
  function actualizarResumen() {
    const dia = DIAS[selectDia.value];
    const inicio = horaElegida(inicioHora, inicioMinutos);
    const fin = horaElegida(finHora, finMinutos);
    resumen.textContent = dia && inicio && fin ? `Vas a guardar: ${dia} de ${inicio} a ${fin}.` : "";
  }

  // --- Progreso sin guardar (CA-14.4, RNF-20) ---

  function guardarProgreso() {
    formulario.guardarDatos(CLAVE, {
      dia: selectDia.value,
      inicioHora: inicioHora.value,
      inicioMinutos: inicioMinutos.value,
      finHora: finHora.value,
      finMinutos: finMinutos.value,
    });
  }

  function restaurar(previo) {
    const valores = [
      [selectDia, previo.dia],
      [inicioHora, previo.inicioHora],
      [inicioMinutos, previo.inicioMinutos],
      [finHora, previo.finHora],
      [finMinutos, previo.finMinutos],
    ];
    for (const [select, valor] of valores) {
      if (typeof valor === "string" && Array.from(select.options).some((o) => o.value === valor)) {
        select.value = valor;
      }
    }
    ajustarFinDelDia();
    actualizarResumen();
  }

  form.addEventListener("change", (evento) => {
    if (evento.target === finHora) {
      ajustarFinDelDia();
    }
    actualizarResumen();
    guardarProgreso();
  });

  // --- Sesión y acceso ---

  function sesionTerminada() {
    guardarFormulariosFlotantes();
    contenido.hidden = true;
    limpiarResultado();
    expediente.avisarSesionTerminada(
      avisoPagina,
      "agenda",
      seccionAgregar.hidden
        ? "Los horarios que ya guardaste siguen guardados."
        : "Los horarios que ya guardaste siguen guardados, y lo que elegiste seguirá aquí cuando vuelvas."
    );
  }

  function sinAcceso() {
    guardarFormulariosFlotantes();
    contenido.hidden = true;
    expediente.avisarNoMaestro(avisoPagina);
  }

  // --- Lista por día ---

  function guardarFormulariosFlotantes() {
    confirmarQuitar.hidden = true;
    main.append(confirmarQuitar);
  }

  function itemBloque(bloque) {
    const item = elemento("li", "linea-bloque");
    item.dataset.ref = bloque.ref;
    const texto = elemento("span", "rango-bloque", `${formato.hora(bloque.inicio_min)} a ${formato.hora(bloque.fin_min)}`);
    const quitar = elemento("button", "boton-secundario boton-quitar", "Quitar");
    quitar.type = "button";
    quitar.setAttribute("aria-label", `Quitar el horario del ${nombreDia(bloque)} ${rango(bloque)}`);
    quitar.addEventListener("click", () => abrirQuitar(bloque, item));
    item.append(texto, quitar);
    return item;
  }

  function pintar() {
    guardarFormulariosFlotantes();
    quitando = null;
    const porDia = new Map();
    for (const bloque of bloques) {
      if (!porDia.has(bloque.dia_semana)) {
        porDia.set(bloque.dia_semana, []);
      }
      porDia.get(bloque.dia_semana).push(bloque);
    }
    const dias = Array.from(porDia.keys()).sort((a, b) => a - b);
    listaDias.replaceChildren(
      ...dias.map((dia) => {
        const lista = porDia.get(dia).sort((a, b) => a.inicio_min - b.inicio_min);
        const titulo = elemento("h3", "", mayuscula(nombreDia(lista[0])));
        return elemento("li", "tarjeta dia-agenda", titulo, elemento("ul", "lista-simple", ...lista.map(itemBloque)));
      })
    );
    document.getElementById("sin-horarios").hidden = bloques.length > 0;
  }

  // --- Carga ---

  async function cargar() {
    expediente.limpiarAviso(avisoPagina);
    cargando.hidden = false;
    const { estado, datos } = await api.obtener(RUTA);
    cargando.hidden = true;
    if (estado === 401) {
      sesionTerminada();
      return false;
    }
    if (estado === 403) {
      sinAcceso();
      return false;
    }
    if (estado !== 200) {
      contenido.hidden = true;
      expediente.avisarErrorCarga(avisoPagina, datos.mensaje, iniciar);
      return false;
    }
    bloques = datos.bloques || [];
    pintar();
    contenido.hidden = false;
    return true;
  }

  async function recargarLista() {
    const { estado, datos } = await api.obtener(RUTA);
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 200) {
      bloques = datos.bloques || [];
      pintar();
    }
  }

  // --- Agregar un horario (un horario por petición, CA-14.4) ---

  function abrirFormulario(previo) {
    limpiarResultado();
    guardarFormulariosFlotantes();
    seccionAgregar.hidden = false;
    document.getElementById("acciones-agregar").hidden = true;
    formulario.limpiarErrores(form);
    if (previo) {
      restaurar(previo);
    } else {
      actualizarResumen();
    }
  }

  function cerrarFormulario() {
    seccionAgregar.hidden = true;
    document.getElementById("acciones-agregar").hidden = false;
    formulario.limpiarErrores(form);
    formulario.olvidar(CLAVE);
  }

  abrirAgregar.addEventListener("click", () => {
    abrirFormulario(null);
    guardarProgreso();
    document.getElementById("titulo-agregar").focus();
  });

  document.getElementById("cancelar-agregar").addEventListener("click", () => {
    cerrarFormulario();
    abrirAgregar.focus();
  });

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(form);
    limpiarResultado();
    // Lo que falte lo dice el servidor junto a cada campo (RNF-15).
    const cuerpo = {
      dia_semana: selectDia.value ? Number(selectDia.value) : "",
      inicio: horaElegida(inicioHora, inicioMinutos),
      fin: horaElegida(finHora, finMinutos),
    };
    formulario.ocupado(form, true);
    const { estado, datos } = await api.enviar(RUTA, cuerpo);
    formulario.ocupado(form, false);
    if (estado === 201) {
      const nuevo = datos.bloque;
      bloques.push(nuevo);
      pintar();
      // Se deja el día elegido para agregar otro horario del mismo día.
      inicioHora.value = "";
      inicioMinutos.value = "00";
      finHora.value = "";
      finMinutos.value = "00";
      ajustarFinDelDia();
      actualizarResumen();
      guardarProgreso();
      avisarResultado(`Listo: guardaste el ${nombreDia(nuevo)} ${rango(nuevo)}. Puedes agregar otro horario o tocar «Cancelar».`);
      return;
    }
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 403) {
      sinAcceso();
      return;
    }
    if (estado === 400) {
      const campo = formulario.mostrarErrores(form, datos);
      if (campo) {
        campo.focus();
      }
      return;
    }
    // 409 (postulación no aprobada), sin conexión u otro error: lo elegido se conserva.
    formulario.avisar(form, datos.mensaje, "error");
  });

  // --- Quitar un horario, con confirmación en la página ---

  function abrirQuitar(bloque, item) {
    limpiarResultado();
    guardarFormulariosFlotantes();
    quitando = bloque;
    expediente.limpiarAviso(avisoQuitar);
    document.getElementById("titulo-quitar").textContent = `¿Quitar el horario del ${nombreDia(bloque)} ${rango(bloque)}?`;
    item.append(confirmarQuitar);
    confirmarQuitar.hidden = false;
    document.getElementById("titulo-quitar").focus();
  }

  document.getElementById("quitar-no").addEventListener("click", () => {
    const ref = quitando && quitando.ref;
    guardarFormulariosFlotantes();
    quitando = null;
    const item = ref && listaDias.querySelector(`[data-ref="${ref}"]`);
    const boton = item && item.querySelector("button");
    if (boton) {
      boton.focus();
    }
  });

  const botonQuitarSi = document.getElementById("quitar-si");
  const textoQuitarSi = botonQuitarSi.textContent;
  botonQuitarSi.addEventListener("click", async () => {
    if (!quitando) {
      return;
    }
    const bloque = quitando;
    expediente.limpiarAviso(avisoQuitar);
    botonQuitarSi.disabled = true;
    botonQuitarSi.textContent = "Quitando…";
    const { estado, datos } = await api.borrar(`${RUTA}/${encodeURIComponent(bloque.ref)}`);
    botonQuitarSi.disabled = false;
    botonQuitarSi.textContent = textoQuitarSi;
    if (estado === 204) {
      bloques = bloques.filter((b) => b.ref !== bloque.ref);
      pintar();
      avisarResultado(`Quitaste el horario del ${nombreDia(bloque)} ${rango(bloque)}.`);
      return;
    }
    if (estado === 401) {
      sesionTerminada();
      return;
    }
    if (estado === 403) {
      sinAcceso();
      return;
    }
    if (estado === 404 || estado === 409) {
      const mensaje =
        estado === 404 ? "No encontramos este horario. Puede que ya lo hayas quitado desde otro teléfono." : datos.mensaje;
      await recargarLista();
      avisarPagina(mensaje);
      return;
    }
    avisoQuitar.className = "aviso aviso-error";
    avisoQuitar.textContent = datos.mensaje;
    avisoQuitar.focus();
  });

  // --- Inicio ---

  async function iniciar() {
    if (!(await cargar())) {
      return;
    }
    // CA-14.4: si quedó un horario a medio elegir, se retoma.
    const previo = formulario.recuperar(CLAVE);
    if (previo && seccionAgregar.hidden) {
      abrirFormulario(previo);
      if (previo.dia || previo.inicioHora || previo.finHora) {
        formulario.avisar(form, "Recuperamos lo que habías elegido. Revísalo y toca «Guardar este horario».", "exito");
      }
    }
  }

  iniciar();
})();
