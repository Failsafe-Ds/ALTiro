// Mi cobertura (HU-13, RF-06, CA-13.1; ADR-019, punto 4).
// - GET y PUT /api/maestros/cobertura: {"comunas": [{"comuna": "8101", "es_base": true}, ...]}.
//   El PUT reemplaza la lista completa; el servidor exige exactamente una
//   comuna principal (CA-13.1) y responde el error en "comunas", que aquí se
//   muestra junto al campo del paso que se estaba guardando (RNF-15).
// - Paso 1: región y comuna principal. Paso 2: otras comunas, de cualquier
//   región. Cada cambio se guarda de inmediato en el servidor (RNF-20): si se
//   corta la señal, lo ya guardado se conserva.
// - RNF-17: en pantalla se dice "comuna principal" por la "comuna base" del informe.
// Sin reglas de negocio: qué lista es válida lo decide el servidor.
"use strict";

(() => {
  const RUTA = "/api/maestros/cobertura";

  const cargando = document.getElementById("cargando");
  const avisoPagina = document.getElementById("aviso-pagina");
  const avisoResultado = document.getElementById("aviso-resultado");
  const contenido = document.getElementById("contenido");

  const formPrincipal = document.getElementById("form-principal");
  const principalGuardada = document.getElementById("principal-guardada");
  const selectPrincipalRegion = document.getElementById("principal-region");
  const selectPrincipal = document.getElementById("principal-comuna");
  const botonCancelarPrincipal = document.getElementById("cancelar-principal");

  const formOtra = document.getElementById("form-otra");
  const selectOtraRegion = document.getElementById("otra-region");
  const selectOtra = document.getElementById("otra-comuna");
  const listaOtras = document.getElementById("lista-otras");

  let comunas = []; // [{codigo, nombre, es_base}] tal como las guardó el servidor
  let ocupado = false;

  // Guarda el texto de cada botón para devolverlo después de "Enviando…".
  formulario.prepararBoton(formPrincipal);
  formulario.prepararBoton(formOtra);

  function elemento(etiqueta, clase, ...hijos) {
    const nodo = document.createElement(etiqueta);
    if (clase) {
      nodo.className = clase;
    }
    nodo.append(...hijos);
    return nodo;
  }

  function principal() {
    return comunas.find((c) => c.es_base) || null;
  }

  function otras() {
    return comunas.filter((c) => !c.es_base);
  }

  function nombreElegido(select) {
    const opcion = select.selectedOptions[0];
    return opcion && opcion.value ? opcion.textContent : "";
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

  // --- Sesión y acceso ---

  function sesionTerminada() {
    contenido.hidden = true;
    limpiarResultado();
    expediente.avisarSesionTerminada(avisoPagina, "cobertura", "Las comunas que ya guardaste siguen guardadas.");
  }

  function sinAcceso() {
    contenido.hidden = true;
    expediente.avisarNoMaestro(avisoPagina);
  }

  // --- Pintar ---

  function mostrarFormPrincipal(visible) {
    formPrincipal.hidden = !visible;
    principalGuardada.hidden = visible || !principal();
    // "Cancelar" solo tiene sentido si ya hay una comuna principal guardada.
    botonCancelarPrincipal.hidden = !principal();
  }

  function itemOtra(comuna) {
    const item = elemento("li", "linea-comuna");
    item.dataset.codigo = comuna.codigo;
    const quitar = elemento("button", "boton-secundario boton-quitar", "Quitar");
    quitar.type = "button";
    quitar.setAttribute("aria-label", `Quitar ${comuna.nombre}`);
    quitar.addEventListener("click", () => quitarOtra(comuna));
    item.append(elemento("span", "nombre-comuna", comuna.nombre), quitar);
    return item;
  }

  function pintar() {
    const base = principal();
    document.getElementById("nombre-principal").textContent = base ? base.nombre : "";
    mostrarFormPrincipal(!base);
    // El paso 2 se habilita cuando hay una comuna principal guardada (CA-13.1).
    document.getElementById("otras-bloqueado").hidden = Boolean(base);
    document.getElementById("otras-contenido").hidden = !base;
    const lista = otras();
    listaOtras.replaceChildren(...lista.map(itemOtra));
    document.getElementById("sin-otras").hidden = lista.length > 0;
  }

  // --- Guardar (PUT con la lista completa) ---

  // Devuelve true si se guardó. "form" y "campo" indican dónde mostrar el
  // error; sin form, el aviso va arriba de la página.
  async function guardar(lista, form, campo) {
    if (ocupado) {
      return false;
    }
    ocupado = true;
    limpiarResultado();
    expediente.limpiarAviso(avisoPagina);
    if (form) {
      formulario.limpiarErrores(form);
      formulario.ocupado(form, true);
    }
    const { estado, datos } = await api.reemplazar(RUTA, { comunas: lista });
    ocupado = false;
    if (form) {
      formulario.ocupado(form, false);
    }
    if (estado === 200) {
      comunas = datos.comunas || [];
      pintar();
      return true;
    }
    if (estado === 401) {
      sesionTerminada();
      return false;
    }
    if (estado === 403) {
      sinAcceso();
      return false;
    }
    if (estado === 400 && form) {
      // El servidor responde en "comunas" (CA-13.1): se muestra junto al campo del paso.
      const errores = {};
      for (const [clave, texto] of Object.entries(datos.errores || {})) {
        errores[clave === "comunas" ? campo : clave] = texto;
      }
      const marcado = formulario.mostrarErrores(form, { mensaje: datos.mensaje, errores });
      if (marcado) {
        // Si la comuna todavía no se puede elegir (falta la región), el foco va a la región.
        (marcado.disabled ? form.querySelector("select") : marcado).focus();
      }
      return false;
    }
    // 409 (postulación no aprobada), sin conexión u otro error: lo guardado
    // antes sigue igual y lo elegido queda en pantalla.
    const texto = (datos.errores && datos.errores.comunas) || datos.mensaje;
    if (form) {
      formulario.avisar(form, texto, "error");
    } else {
      avisarPagina(texto);
    }
    return false;
  }

  function lineaDe(comuna, esBase) {
    return { comuna: comuna.codigo, es_base: esBase };
  }

  // --- Paso 1: comuna principal ---

  document.getElementById("abrir-principal").addEventListener("click", () => {
    limpiarResultado();
    formulario.limpiarErrores(formPrincipal);
    mostrarFormPrincipal(true);
    selectPrincipalRegion.focus();
  });

  botonCancelarPrincipal.addEventListener("click", () => {
    formulario.limpiarErrores(formPrincipal);
    mostrarFormPrincipal(false);
    document.getElementById("abrir-principal").focus();
  });

  formPrincipal.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const elegida = selectPrincipal.value;
    const nombre = nombreElegido(selectPrincipal);
    const anterior = principal();
    // La comuna principal anterior no se pierde: queda entre las otras comunas
    // (decisión conservadora de la pantalla; el maestro puede quitarla después).
    const resto = comunas
      .filter((c) => c.codigo !== elegida)
      .map((c) => lineaDe(c, false));
    // Sin comuna elegida se envía igual: el servidor responde el error de
    // CA-13.1 ("marca cuál es tu comuna principal") y no guarda nada.
    const lista = elegida ? [{ comuna: elegida, es_base: true }, ...resto] : resto;
    const listo = await guardar(lista, formPrincipal, "principal");
    if (!listo) {
      return;
    }
    let texto = `Listo: guardamos ${nombre} como tu comuna principal.`;
    if (anterior && anterior.codigo !== elegida) {
      texto += ` ${anterior.nombre} quedó entre tus otras comunas; si ya no trabajas ahí, quítala en el paso 2.`;
    }
    if (!otras().length) {
      texto += " Si trabajas en otras comunas, agrégalas en el paso 2.";
    }
    avisarResultado(texto);
  });

  // --- Paso 2: otras comunas ---

  formOtra.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(formOtra);
    const elegida = selectOtra.value;
    const nombre = nombreElegido(selectOtra);
    // Solo experiencia de uso: el servidor vuelve a revisar la lista completa.
    if (!elegida) {
      formulario.mostrarErrores(formOtra, {
        mensaje: "Elige una comuna para agregarla.",
        errores: { otra: selectOtraRegion.value ? "Elige la comuna de la lista." : "Primero elige la región y después la comuna." },
      });
      (selectOtraRegion.value ? selectOtra : selectOtraRegion).focus();
      return;
    }
    if (comunas.some((c) => c.codigo === elegida)) {
      const esBase = comunas.some((c) => c.codigo === elegida && c.es_base);
      formulario.mostrarErrores(formOtra, {
        mensaje: "Esa comuna ya está en tu lista.",
        errores: { otra: esBase ? `${nombre} ya es tu comuna principal.` : `${nombre} ya está entre tus comunas.` },
      });
      selectOtra.focus();
      return;
    }
    const lista = [...comunas.map((c) => lineaDe(c, c.es_base)), { comuna: elegida, es_base: false }];
    if (await guardar(lista, formOtra, "otra")) {
      selectOtra.value = "";
      avisarResultado(`Listo: agregaste ${nombre} a tus comunas.`);
    }
  });

  async function quitarOtra(comuna) {
    const lista = comunas.filter((c) => c.codigo !== comuna.codigo).map((c) => lineaDe(c, c.es_base));
    if (await guardar(lista, null, null)) {
      avisarResultado(`Quitaste ${comuna.nombre} de tus comunas. Si fue un error, agrégala de nuevo.`);
    }
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
    comunas = datos.comunas || [];
    pintar();
    contenido.hidden = false;
    return true;
  }

  // Las listas de región y comuna se conectan una sola vez, tras la primera carga correcta.
  let conectado = false;
  async function iniciar() {
    if (!(await cargar()) || conectado) {
      return;
    }
    conectado = true;
    await Promise.all([
      territorio.conectar(selectPrincipalRegion, selectPrincipal),
      territorio.conectar(selectOtraRegion, selectOtra),
    ]);
  }

  iniciar();
})();
