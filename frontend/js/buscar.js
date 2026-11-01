// Buscar un maestro, página pública (HU-02 a HU-04; RF-09 a RF-13; CA-02.x, CA-04.1 a CA-04.3; ADR-022).
// - GET /api/oficios: lista de oficios. Región y comuna con territorio.js.
// - GET /api/busqueda?oficio=<código>&comuna=<CUT>[&fecha=AAAA-MM-DD&inicio=HH:MM&fin=HH:MM][&pagina=N].
//   Respuesta: { resultados, total, pagina, paginas, mensaje, sugerencias }.
//   Cada tarjeta trae ref, nombre, foto (160 px), oficio, calificacion_texto,
//   atiende_en (hasta 3 comunas, sin marcar la base), atiende_en_mas y
//   precio {modalidad, modalidad_texto, monto, desde} (DA-29; ADR-022, E-2);
//   cada sugerencia, además, incumple e incumple_texto (el criterio que no cumple).
// - Los filtros van en la dirección de la página (buscar.html?oficio=…&region=…&comuna=…):
//   la búsqueda se puede recargar y compartir. "region" solo sirve para llenar
//   las listas; a la API se mandan solo sus parámetros.
// - Si hay sesión de cliente y la dirección no trae comuna, se precarga la
//   comuna de su perfil (ADR-022, punto 1).
// - El día y el horario son opcionales y van en un segundo paso (RNF-14), con
//   el selector propio de 24 horas (hora24.js; ADR-020, CA-14.1).
// Sin reglas de negocio: qué filtros valen, qué maestros cumplen y en qué orden
// van lo decide el servidor. Aquí no se calcula ni se muestra ningún puntaje.
"use strict";

(() => {
  const DIAS_OFRECIDOS = 14; // Hoy y los 13 días siguientes (ADR-022, punto 4; propuesta del S4, §11.2).
  const PARAMETROS_API = ["oficio", "comuna", "fecha", "inicio", "fin", "pagina"];
  const PARAMETROS_PAGINA = ["oficio", "region", "comuna", "fecha", "inicio", "fin", "pagina"];
  const CAMPOS_CUANDO = ["fecha", "inicio", "fin"];
  const SIN_SENAL = "Revisa tu señal o tu wifi y toca «Reintentar».";

  const titulo = document.getElementById("titulo-pagina");
  const avisoPagina = document.getElementById("aviso-pagina");
  const form = document.getElementById("form-busqueda");
  const pasoQue = document.getElementById("paso-que");
  const pasoCuando = document.getElementById("paso-cuando");
  const selectOficio = document.getElementById("oficio");
  const selectRegion = document.getElementById("region");
  const selectComuna = document.getElementById("comuna");
  const selectFecha = document.getElementById("fecha");
  const inicioHora = document.getElementById("inicio-hora");
  const inicioMinutos = document.getElementById("inicio-minutos");
  const finHora = document.getElementById("fin-hora");
  const finMinutos = document.getElementById("fin-minutos");
  const resumenCuando = document.getElementById("resumen-cuando");
  const irCuando = document.getElementById("ir-cuando");

  const resumen = document.getElementById("resumen-busqueda");
  const textoResumen = document.getElementById("texto-resumen");
  const buscando = document.getElementById("buscando");

  const seccionResultados = document.getElementById("resultados");
  const tituloResultados = document.getElementById("titulo-resultados");
  const mensajeResultados = document.getElementById("mensaje-resultados");
  const listaResultados = document.getElementById("lista-resultados");
  const paginacion = document.getElementById("paginacion");
  const textoPagina = document.getElementById("texto-pagina");
  const anterior = document.getElementById("pagina-anterior");
  const siguiente = document.getElementById("pagina-siguiente");

  const seccionSugerencias = document.getElementById("sugerencias");
  const listaSugerencias = document.getElementById("lista-sugerencias");

  let consulta = 0; // Solo se pinta la respuesta de la última búsqueda pedida.
  let actual = null; // Filtros de la última búsqueda que respondió 200.

  const elemento = dom.elemento;

  const opcion = dom.opcion;

  // --- Filtros <-> dirección de la página ---

  function vacio() {
    return Object.fromEntries(PARAMETROS_PAGINA.map((p) => [p, ""]));
  }

  function leerDireccion() {
    const parametros = new URLSearchParams(location.search);
    const filtros = vacio();
    for (const nombre of PARAMETROS_PAGINA) {
      filtros[nombre] = (parametros.get(nombre) || "").trim();
    }
    return filtros;
  }

  function consultaDe(filtros, nombres) {
    const parametros = new URLSearchParams();
    for (const nombre of nombres) {
      if (filtros[nombre] && !(nombre === "pagina" && filtros[nombre] === "1")) {
        parametros.set(nombre, filtros[nombre]);
      }
    }
    return parametros.toString();
  }

  function direccionDe(filtros) {
    const texto = consultaDe(filtros, PARAMETROS_PAGINA);
    return texto ? `buscar.html?${texto}` : "buscar.html";
  }

  // Solo el oficio (por ejemplo, desde categorias.html) no es una búsqueda:
  // lo deja elegido en el formulario y falta la comuna.
  function hayBusqueda(filtros) {
    return ["comuna", "fecha", "inicio", "fin"].some((nombre) => filtros[nombre]);
  }

  function leerFormulario() {
    return Object.assign(vacio(), {
      oficio: selectOficio.value,
      region: selectRegion.value,
      comuna: selectComuna.value,
      fecha: selectFecha.value,
      inicio: hora24.leer(inicioHora, inicioMinutos),
      fin: hora24.leer(finHora, finMinutos),
    });
  }

  function elegir(select, valor) {
    if (Array.from(select.options).some((o) => o.value === valor)) {
      select.value = valor;
    }
  }

  // Pone en el formulario lo que trae la dirección (al cargar o al volver
  // atrás). La región y la comuna las pone territorio.js al cargar; al volver
  // atrás dentro de la misma región basta elegir la comuna.
  function ponerEnFormulario(filtros) {
    elegir(selectOficio, filtros.oficio);
    ponerFecha(filtros.fecha);
    hora24.poner(inicioHora, inicioMinutos, filtros.inicio);
    hora24.poner(finHora, finMinutos, filtros.fin);
    if (filtros.region === selectRegion.value) {
      elegir(selectComuna, filtros.comuna);
    }
    actualizarResumenCuando();
  }

  // --- Día (lista de los próximos 14 días) y horario ---

  function llenarFechas() {
    const hoy = formato.hoyEnChile();
    const opciones = [opcion("", "Cualquier día")];
    for (let i = 0; i < DIAS_OFRECIDOS; i += 1) {
      const iso = formato.sumarDias(hoy, i);
      opciones.push(opcion(iso, formato.fechaConReferencia(iso, hoy)));
    }
    selectFecha.replaceChildren(...opciones);
  }

  // Un día que no está en la lista (por ejemplo, un enlace antiguo) se muestra
  // igual, para que el aviso del servidor quede junto a lo que se pidió.
  function ponerFecha(fecha) {
    if (fecha && !Array.from(selectFecha.options).some((o) => o.value === fecha)) {
      const texto = formato.fechaConReferencia(fecha);
      if (texto) {
        selectFecha.append(opcion(fecha, texto));
      }
    }
    selectFecha.value = Array.from(selectFecha.options).some((o) => o.value === fecha) ? fecha : "";
  }

  function textoCuando(filtros) {
    if (!filtros.fecha && !filtros.inicio && !filtros.fin) {
      return "";
    }
    const dia = formato.fechaLarga(filtros.fecha) || "día sin elegir";
    return `${dia}, de ${filtros.inicio || "--:--"} a ${filtros.fin || "--:--"}`;
  }

  function actualizarResumenCuando() {
    const texto = textoCuando(leerFormulario());
    resumenCuando.textContent = texto ? `Día y horario: ${texto}.` : "";
    irCuando.textContent = texto ? "Cambiar el día y el horario" : "Elegir día y horario (opcional)";
  }

  // --- Pasos del formulario (RNF-14: 5 campos o menos por paso) ---

  function mostrarPaso(paso, enfocar) {
    pasoQue.hidden = paso !== pasoQue;
    pasoCuando.hidden = paso !== pasoCuando;
    if (enfocar) {
      const leyenda = paso.querySelector("legend");
      leyenda.setAttribute("tabindex", "-1");
      leyenda.focus();
    }
  }

  // E-4.10: en escritorio (dos columnas) el formulario queda siempre a la
  // izquierda y «Buscaste…» a la derecha; solo en el celular se pliega.
  const dosColumnas = window.matchMedia("(min-width: 60rem)");

  function desplegarFormulario(paso, enfocar) {
    resumen.hidden = !(dosColumnas.matches && actual);
    form.hidden = false;
    mostrarPaso(paso || pasoQue, enfocar);
  }

  function plegarFormulario() {
    form.hidden = !dosColumnas.matches;
    resumen.hidden = false;
  }

  dosColumnas.addEventListener("change", () => {
    if (actual && !resumen.hidden) {
      plegarFormulario();
    } else if (dosColumnas.matches) {
      form.hidden = false;
    }
  });

  // Cada paso del formulario deja una entrada en el historial: el botón Atrás
  // del navegador o del teléfono retrocede un paso dentro de la página sin
  // perder lo elegido (RNF-20). La página no tiene botón «Volver» (ADR-002 E-3).
  function enPasoCuando() {
    return Boolean(history.state && history.state.altiroPaso === "cuando");
  }

  // Deja el paso del día y el horario: si tiene entrada propia, retrocede en el
  // historial (popstate muestra el primer paso); si no, lo muestra directamente.
  function volverAlPrimerPaso() {
    if (enPasoCuando()) {
      history.back();
      return;
    }
    actualizarResumenCuando();
    mostrarPaso(pasoQue, true);
  }

  irCuando.addEventListener("click", () => {
    history.pushState({ altiroPaso: "cuando" }, "", location.href);
    mostrarPaso(pasoCuando, true);
  });
  document.getElementById("quitar-cuando").addEventListener("click", () => {
    selectFecha.value = "";
    hora24.poner(inicioHora, inicioMinutos, "");
    hora24.poner(finHora, finMinutos, "");
    for (const nombre of CAMPOS_CUANDO) {
      document.getElementById(`error-${nombre}`).textContent = "";
    }
    for (const campo of pasoCuando.querySelectorAll("select")) {
      campo.removeAttribute("aria-invalid");
    }
    volverAlPrimerPaso();
  });
  document.getElementById("cambiar-busqueda").addEventListener("click", () => {
    history.pushState({ altiroPaso: "formulario" }, "", location.href);
    desplegarFormulario(pasoQue, true);
  });
  form.addEventListener("change", actualizarResumenCuando);

  // --- Listas: oficios, regiones y comunas ---

  function avisarFallaOficios(texto) {
    quitarFallaOficios();
    const aviso = elemento("div", "aviso aviso-error aviso-territorio", texto, " ");
    aviso.id = "falla-oficios";
    aviso.setAttribute("role", "alert");
    const boton = elemento("button", "boton-secundario", "Reintentar");
    boton.type = "button";
    boton.addEventListener("click", () => cargarOficios(selectOficio.value || leerDireccion().oficio));
    aviso.append(boton);
    selectOficio.closest(".campo").after(aviso);
  }

  function quitarFallaOficios() {
    const previo = document.getElementById("falla-oficios");
    if (previo) {
      previo.remove();
    }
  }

  async function cargarOficios(elegido) {
    quitarFallaOficios();
    selectOficio.replaceChildren(opcion("", "Cargando oficios…"));
    const { estado, datos } = await api.obtener("/api/oficios");
    if (estado !== 200) {
      selectOficio.replaceChildren(opcion("", "No pudimos cargar los oficios"));
      avisarFallaOficios(`No pudimos cargar los oficios. ${estado === 0 ? SIN_SENAL : "Toca «Reintentar»."}`);
      return;
    }
    selectOficio.replaceChildren(
      opcion("", "Elige el oficio"),
      ...(datos.oficios || []).map((o) => opcion(o.codigo, o.nombre))
    );
    elegir(selectOficio, elegido);
    if (actual) {
      pintarResumen(actual);
    }
  }

  // Comuna del perfil de cliente, si hay sesión con ese perfil. Sin sesión, nada.
  async function comunaDelCliente() {
    const { estado, datos } = await api.obtener("/api/cuenta");
    const perfil = estado === 200 && datos && datos.cuenta && datos.cuenta.perfil_cliente;
    return perfil ? { region: String(perfil.region.codigo), comuna: String(perfil.comuna.codigo) } : {};
  }

  // --- Resumen de lo buscado ---

  function nombreElegido(select, valor) {
    const elegida = Array.from(select.options).find((o) => o.value && o.value === valor);
    return elegida ? elegida.textContent : "";
  }

  function pintarResumen(filtros) {
    const oficio = nombreElegido(selectOficio, filtros.oficio) || "El oficio elegido";
    const comuna = nombreElegido(selectComuna, filtros.comuna);
    const cuando = textoCuando(filtros);
    textoResumen.textContent =
      `Buscaste: ${oficio} en ${comuna || "la comuna elegida"}` + (cuando ? `, el ${cuando}.` : ", cualquier día.");
  }

  // --- Tarjetas (RF-13) ---

  // Solo rutas de la propia API: la foto viene del servidor, pero no se arma
  // una imagen con otra dirección.
  function rutaFoto(foto) {
    return typeof foto === "string" && foto.startsWith("/api/maestros/publicos/") ? foto : "";
  }

  // ADR-022, E-1: "Atiende en: Concepción, Talcahuano y 2 comunas más".
  function textoAtiendeEn(maestro) {
    const comunas = Array.isArray(maestro.atiende_en) ? maestro.atiende_en : [];
    if (!comunas.length) {
      return "";
    }
    const mas = Number(maestro.atiende_en_mas) || 0;
    let lista = comunas.join(", ");
    if (mas) {
      lista += ` y ${mas} ${mas === 1 ? "comuna" : "comunas"} más`;
    } else if (comunas.length > 1) {
      lista = `${comunas.slice(0, -1).join(", ")} y ${comunas[comunas.length - 1]}`;
    }
    return `Atiende en: ${lista}`;
  }

  // DA-29, ADR-022 E-2: "Desde $25.000 por trabajo" o "$12.000 por hora".
  // Solo se muestra: el orden lo da el servidor y no depende del precio.
  function textoPrecio(maestro) {
    const precio = maestro.precio;
    const pesos = precio ? formato.monto(precio.monto) : "";
    if (!pesos) {
      return "";
    }
    const texto = `${pesos} ${String(precio.modalidad_texto || "").toLowerCase()}`.trim();
    return precio.desde ? `Desde ${texto}` : texto;
  }

  // RF-13: promedio y cantidad con estrella ("4,8 (23)"); el lector de
  // pantalla oye el texto completo del servidor. Sin evaluaciones, el texto
  // del servidor (CA-05.2). El promedio ya viene redondeado a un decimal.
  function calificacionTarjeta(maestro) {
    const p = elemento("p", "calificacion-tarjeta");
    const datos = maestro.calificacion;
    if (!datos) {
      p.append(elemento("span", "sin-evaluaciones", maestro.calificacion_texto || ""));
      return p;
    }
    const nota = Number(datos.promedio).toLocaleString("es-CL", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    const visible = [
      iconos.crear("estrella"),
      elemento("span", "nota-tarjeta", nota),
      elemento("span", "cantidad-tarjeta", `(${datos.cantidad})`),
    ];
    for (const nodo of visible.slice(1)) {
      nodo.setAttribute("aria-hidden", "true");
    }
    p.append(...visible, elemento("span", "solo-lector", `Calificación: ${maestro.calificacion_texto}`));
    return p;
  }

  // Estilo Fiverr (ADR-002 E-3, MASTER): foto arriba e información debajo, sin
  // recuadro; todo el bloque es un solo enlace al perfil. Solo presentación:
  // el orden y los datos son los del servidor.
  function tarjeta(maestro, conIncumple) {
    const item = elemento("li", "tarjeta-maestro");
    const enlace = elemento("a", "enlace-maestro");
    enlace.href = `perfil-maestro.html?m=${encodeURIComponent(maestro.ref)}`;
    const foto = document.createElement("img");
    foto.className = "foto-tarjeta";
    // Ancho y alto fijos (4:3): la página no se mueve mientras llegan las fotos (RNF-02).
    foto.width = 480;
    foto.height = 360;
    foto.loading = "lazy";
    foto.decoding = "async";
    // El nombre ya está en el enlace: la foto no repite texto.
    foto.alt = "";
    const ruta = rutaFoto(maestro.foto);
    if (ruta) {
      foto.src = ruta;
      // Variante de 480 px de la misma ruta pública (perfil/fotos.py, TAMANOS):
      // el navegador la pide solo si la foto se muestra más grande que 160 px.
      if (ruta.includes("tam=160")) {
        foto.srcset = `${ruta} 160w, ${ruta.replace("tam=160", "tam=480")} 480w`;
        foto.sizes = "(min-width: 75rem) 19rem, (min-width: 56.25rem) 31vw, (min-width: 35rem) 46vw, 92vw";
      }
    }
    // Todos los resultados y sugerencias son maestros publicados, es decir,
    // aprobados por curatoría (ADR-019): de ahí «Verificado» (ícono y texto).
    const verificado = elemento("span", "verificado", iconos.crear("verificado"), "Verificado");
    enlace.append(
      foto,
      elemento("div", "nombre-linea", elemento("h3", "nombre-tarjeta", maestro.nombre), verificado),
      elemento("p", "oficio-tarjeta", maestro.oficio ? maestro.oficio.nombre : ""),
      calificacionTarjeta(maestro),
      elemento("p", "comunas-tarjeta", textoAtiendeEn(maestro)),
      elemento("p", "precio-tarjeta", textoPrecio(maestro))
    );
    if (conIncumple) {
      // CA-04.3: el criterio que no cumple, con ícono y texto (no solo color).
      const incumple = elemento(
        "p",
        "incumple",
        elemento("span", "icono-incumple", "⚠︎"),
        elemento("span", "", `No cumple: ${maestro.incumple_texto || ""}`)
      );
      incumple.firstChild.setAttribute("aria-hidden", "true");
      enlace.append(incumple);
    }
    item.append(enlace);
    return item;
  }

  // --- Resultados ---

  function ocultarResultados() {
    seccionResultados.hidden = true;
    seccionSugerencias.hidden = true;
  }

  function enlacePagina(enlace, filtros, pagina, texto) {
    enlace.textContent = texto;
    enlace.href = direccionDe(Object.assign({}, filtros, { pagina: String(pagina) }));
    enlace.dataset.pagina = String(pagina);
    enlace.hidden = false;
  }

  function pintarPaginacion(filtros, datos, vacia) {
    anterior.hidden = true;
    siguiente.hidden = true;
    if (vacia) {
      // Página fuera de rango (por ejemplo, un enlace antiguo): se ofrece la primera.
      textoPagina.textContent = "";
      enlacePagina(anterior, filtros, 1, "Ir a la primera página");
      paginacion.hidden = false;
      return;
    }
    if (datos.paginas <= 1) {
      paginacion.hidden = true;
      return;
    }
    textoPagina.textContent = `Página ${datos.pagina} de ${datos.paginas}`;
    if (datos.pagina > 1) {
      enlacePagina(anterior, filtros, datos.pagina - 1, "Página anterior");
    }
    if (datos.pagina < datos.paginas) {
      enlacePagina(siguiente, filtros, datos.pagina + 1, "Página siguiente");
    }
    paginacion.hidden = false;
  }

  function pintarResultados(filtros, datos) {
    const resultados = datos.resultados || [];
    const sugerencias = datos.sugerencias || [];
    const total = Number(datos.total) || 0;
    const vacia = total > 0 && resultados.length === 0;
    if (total === 0) {
      tituloResultados.textContent = "Sin resultados";
    } else if (vacia) {
      tituloResultados.textContent = "Esta página ya no tiene resultados";
    } else {
      tituloResultados.textContent = `Encontramos ${total} ${total === 1 ? "maestro" : "maestros"}`;
    }
    // CA-04.1: mensaje explícito del servidor cuando nadie cumple los filtros.
    mensajeResultados.textContent = datos.mensaje || "";
    mensajeResultados.hidden = !datos.mensaje;
    listaResultados.replaceChildren(...resultados.map((m) => tarjeta(m, false)));
    listaResultados.hidden = resultados.length === 0;
    seccionResultados.querySelector(".nota-orden").hidden = resultados.length === 0;
    pintarPaginacion(filtros, datos, vacia);
    seccionResultados.hidden = false;

    // RF-12, CA-04.2: sección aparte y rotulada, solo si el servidor mandó sugerencias.
    listaSugerencias.replaceChildren(...sugerencias.map((m) => tarjeta(m, true)));
    seccionSugerencias.hidden = sugerencias.length === 0;
    pintarResumen(filtros);
  }

  // --- Búsqueda ---

  function avisarFalla(datos, filtros) {
    avisoPagina.className = "aviso aviso-error";
    const boton = elemento("button", "boton-secundario", "Reintentar");
    boton.type = "button";
    boton.addEventListener("click", () => buscar(filtros, "reintento"));
    avisoPagina.replaceChildren((datos && datos.mensaje) || "No pudimos buscar. Toca «Reintentar».", " ", boton);
    avisoPagina.focus();
  }

  function limpiarAvisoPagina() {
    avisoPagina.className = "aviso";
    avisoPagina.replaceChildren();
  }

  // 400: cada error junto a su campo (RNF-15), en el paso donde está el primero.
  function mostrarErroresDeCampo(datos) {
    const errores = datos.errores || {};
    const enCuando = CAMPOS_CUANDO.some((c) => errores[c]);
    const enQue = ["oficio", "comuna"].some((c) => errores[c]);
    desplegarFormulario(enQue || !enCuando ? pasoQue : pasoCuando, false);
    const primero = formulario.mostrarErrores(form, datos);
    // Un error de página (por ejemplo, un enlace antiguo) no tiene campo: la
    // próxima búsqueda vuelve a la primera página.
    if (primero && !primero.closest("[hidden]")) {
      primero.focus();
    } else if (!primero) {
      form.querySelector(".aviso").focus();
    }
  }

  // origen: "formulario" y "pagina" agregan la búsqueda al historial; "inicio",
  // "historial" y "reintento" no la agregan.
  async function buscar(filtros, origen) {
    const numero = ++consulta;
    limpiarAvisoPagina();
    buscando.textContent = "Buscando maestros…";
    seccionResultados.setAttribute("aria-busy", "true");
    const { estado, datos } = await api.obtener(`/api/busqueda?${consultaDe(filtros, PARAMETROS_API)}`);
    if (numero !== consulta) {
      return;
    }
    buscando.textContent = "";
    seccionResultados.removeAttribute("aria-busy");
    if (estado === 200) {
      actual = filtros;
      formulario.limpiarErrores(form);
      if (origen === "formulario" || origen === "pagina") {
        history.pushState({ altiroPaso: "resultados" }, "", direccionDe(filtros));
      } else if (origen === "categoria") {
        // Desde una categoría con la comuna del perfil: la dirección queda con
        // la búsqueda completa (se puede recargar y compartir).
        history.replaceState({ altiroPaso: "resultados" }, "", direccionDe(filtros));
      }
      pintarResultados(filtros, datos);
      plegarFormulario();
      // Marca de medición de RNF-02 (docs/testing/rnf-02-medicion.md): dos
      // cuadros después, las tarjetas ya se pintaron.
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          if (window.performance && performance.mark) {
            performance.mark("resultados-listos");
          }
        })
      );
      if (origen !== "inicio") {
        tituloResultados.focus();
      }
      return;
    }
    if (estado === 400) {
      ocultarResultados();
      mostrarErroresDeCampo(datos);
      return;
    }
    // Sin conexión o error del servidor: lo elegido se conserva.
    avisarFalla(datos, filtros);
  }

  form.addEventListener("submit", (evento) => {
    evento.preventDefault();
    formulario.limpiarErrores(form);
    // Lo que falte o no sirva lo dice el servidor junto a cada campo (RNF-15).
    buscar(leerFormulario(), "formulario");
  });

  for (const enlace of [anterior, siguiente]) {
    enlace.addEventListener("click", (evento) => {
      if (!actual || evento.ctrlKey || evento.metaKey || evento.shiftKey) {
        return;
      }
      evento.preventDefault();
      buscar(Object.assign({}, actual, { pagina: enlace.dataset.pagina }), "pagina");
    });
  }

  // Atrás y adelante del navegador: se repite la búsqueda de esa dirección.
  // Si la búsqueda anterior es de otra región, se vuelve a cargar la página
  // para llenar de nuevo la lista de comunas de esa región.
  window.addEventListener("popstate", (evento) => {
    const paso = evento.state && evento.state.altiroPaso;
    if (paso === "cuando") {
      desplegarFormulario(pasoCuando, true);
      return;
    }
    const filtros = leerDireccion();
    // Lo escrito se conserva (RNF-20): no se recarga el formulario desde la dirección.
    if (paso === "formulario" || (!actual && !hayBusqueda(filtros))) {
      actualizarResumenCuando();
      desplegarFormulario(pasoQue, true);
      return;
    }
    // Se vuelve a la misma búsqueda que ya está en pantalla: solo se pliega el formulario.
    if (actual && hayBusqueda(filtros) && consultaDe(filtros, PARAMETROS_API) === consultaDe(actual, PARAMETROS_API)) {
      plegarFormulario();
      tituloResultados.focus();
      return;
    }
    if (!hayBusqueda(filtros)) {
      // Sin búsqueda en la dirección: el formulario con lo ya elegido (RNF-20).
      actual = null;
      ocultarResultados();
      formulario.limpiarErrores(form);
      actualizarResumenCuando();
      desplegarFormulario(pasoQue, false);
      titulo.focus();
      return;
    }
    if (filtros.region !== selectRegion.value && selectRegion.options.length > 1) {
      location.reload();
      return;
    }
    ponerEnFormulario(filtros);
    buscar(filtros, "historial");
  });

  // --- Inicio ---

  async function iniciar() {
    hora24.preparar(inicioHora, inicioMinutos);
    hora24.preparar(finHora, finMinutos, { esTermino: true });
    llenarFechas();
    const filtros = leerDireccion();
    ponerEnFormulario(filtros);
    const busqueda = hayBusqueda(filtros);
    if (busqueda) {
      // Los resultados no esperan a las listas del formulario (RNF-02).
      plegarFormulario();
      pintarResumen(filtros);
      buscar(filtros, "inicio");
    }
    const listas = [cargarOficios(filtros.oficio)];
    const guardados = filtros.comuna ? { region: filtros.region, comuna: filtros.comuna } : await comunaDelCliente();
    listas.push(territorio.conectar(selectRegion, selectComuna, guardados));
    await Promise.all(listas);
    if (busqueda) {
      pintarResumen(actual || filtros);
      return;
    }
    // Llegó con un oficio del catálogo (categorías): si el cliente tiene su
    // comuna en el perfil, se busca de inmediato; si no, falta elegir la comuna.
    // El oficio solo queda elegido si está en la lista del catálogo (elegir()).
    if (filtros.oficio && selectOficio.value === filtros.oficio) {
      if (selectComuna.value) {
        buscar(leerFormulario(), "categoria");
      } else {
        selectRegion.focus();
      }
    }
  }

  iniciar();
})();
