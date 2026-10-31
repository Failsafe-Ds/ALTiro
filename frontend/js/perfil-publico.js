// Perfil público del maestro, sin sesión (RF-14 y RF-13 parciales, HU-05 parcial; ADR-019, D-12 y D-14; ADR-021).
// - GET /api/maestros/publicos/<ref>: nombre, foto (160 y 480 px), servicios
//   visibles (oficio, servicio, forma de cobro y monto), comunas (sin indicar
//   cuál es la principal) y horarios semanales en "HH:MM" de 24 horas.
// - Un maestro no publicado o una referencia inexistente responden el mismo
//   404: la página dice lo mismo en ambos casos, sin motivos.
// - Sin datos de contacto: la API no los entrega. Calificación por dimensión y últimos
//   comentarios sin autor; sin evaluaciones, "Todavía no tiene evaluaciones" (CA-05.1, CA-05.2).
// - Bloques de los próximos 14 días agrupados por fecha, libres u ocupados con
//   ícono y texto además del color (RF-14, CA-05.1; ADR-022, punto 4). Cada
//   bloque libre lleva «Pedir este horario» a
//   pedir-trabajo.html?m=<maestro>&b=<bloque>&f=<fecha>&s=<servicio> (S4,
//   incremento 4). El servicio se elige en la ficha con un radio; si el
//   maestro tiene uno solo, ya va elegido. Qué bloque se puede pedir lo
//   vuelve a decidir el servidor al crear el pedido.
// El parámetro "m" se valida como UUID antes de consultar; si no lo es, se
// muestra el mismo aviso que un 404 (no se arma ninguna ruta con él).
"use strict";

(() => {
  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const NO_ENCONTRADO = "No encontramos este perfil. Puede que el maestro ya no esté disponible.";
  const DIAS = { 1: "lunes", 2: "martes", 3: "miércoles", 4: "jueves", 5: "viernes", 6: "sábado", 7: "domingo" };
  const MODALIDADES = { por_trabajo: "por trabajo", por_hora: "por hora" };
  const SIN_EVALUACIONES = "Todavía no tiene evaluaciones";

  const cargando = document.getElementById("cargando");
  const aviso = document.getElementById("aviso-pagina");
  const perfil = document.getElementById("perfil");

  const elemento = dom.elemento;

  function mayuscula(texto) {
    return texto ? texto.charAt(0).toUpperCase() + texto.slice(1) : "";
  }

  function noEncontrado() {
    cargando.hidden = true;
    perfil.hidden = true;
    const enlace = elemento("a", "boton", "Ir al inicio");
    enlace.href = "index.html";
    aviso.className = "aviso aviso-error";
    aviso.replaceChildren(NO_ENCONTRADO, enlace);
    aviso.focus();
  }

  function errorCarga(mensaje) {
    cargando.hidden = true;
    perfil.hidden = true;
    const boton = elemento("button", "", "Reintentar");
    boton.type = "button";
    boton.addEventListener("click", cargar);
    aviso.className = "aviso aviso-error";
    aviso.replaceChildren(mensaje, boton);
    aviso.focus();
  }

  // Servicios agrupados por oficio, en el orden en que llegan.
  function pintarServicios(servicios) {
    const grupos = new Map();
    for (const s of servicios) {
      const clave = s.oficio.codigo;
      if (!grupos.has(clave)) {
        grupos.set(clave, { nombre: s.oficio.nombre, servicios: [] });
      }
      grupos.get(clave).servicios.push(s);
    }
    document.getElementById("lista-servicios").replaceChildren(
      ...Array.from(grupos.values()).map((grupo) =>
        elemento(
          "section",
          "tarjeta oficio-publico",
          elemento("h3", "", grupo.nombre),
          elemento(
            "ul",
            "lista-simple precios-publicos",
            ...grupo.servicios.map((s) => {
              const modalidad = (s.modalidad_texto || "").toLowerCase() || MODALIDADES[s.modalidad] || "";
              return elemento(
                "li",
                "",
                elemento("span", "nombre-servicio", s.servicio),
                elemento("strong", "precio-servicio", `${formato.monto(s.monto)} ${modalidad}`.trim())
              );
            })
          )
        )
      )
    );
  }

  // Horarios por día, en 24 horas (CA-14.1): "Lunes: 08:00 a 12:00, 14:00 a 18:00".
  function pintarHorarios(agenda) {
    const porDia = new Map();
    for (const b of agenda) {
      if (!porDia.has(b.dia_semana)) {
        porDia.set(b.dia_semana, { dia: b.dia || DIAS[b.dia_semana] || "", rangos: [] });
      }
      porDia.get(b.dia_semana).rangos.push(`${b.inicio} a ${b.fin}`);
    }
    const dias = Array.from(porDia.keys()).sort((a, b) => a - b);
    const lista = document.getElementById("lista-horarios");
    lista.replaceChildren(
      ...dias.flatMap((d) => [
        elemento("dt", "", mayuscula(porDia.get(d).dia)),
        elemento("dd", "", porDia.get(d).rangos.join(", ")),
      ])
    );
    lista.hidden = dias.length === 0;
    document.getElementById("sin-horarios").hidden = dias.length > 0;
  }

  function pintar(maestro) {
    document.title = `${maestro.nombre} — AlTiro`;
    document.getElementById("nombre-maestro").textContent = maestro.nombre;
    // DA-30: nunca innerHTML; el texto del maestro se muestra tal cual.
    const descripcion = typeof maestro.descripcion === "string" ? maestro.descripcion.trim() : "";
    document.getElementById("descripcion-maestro").textContent = descripcion;
    document.getElementById("seccion-sobre-mi").hidden = descripcion === "";
    const imagen = document.getElementById("foto-maestro");
    const fotos = maestro.foto || {};
    // 160 px en pantallas chicas y 480 px donde hace falta más detalle
    // (pantallas de alta densidad o anchas); el navegador elige (RNF-02).
    if (fotos["160"] && fotos["480"]) {
      imagen.srcset = `${fotos["160"]} 160w, ${fotos["480"]} 480w`;
      imagen.sizes = "(min-width: 40rem) 12rem, 8rem";
    }
    const url = fotos["160"] || fotos["480"] || "";
    if (url) {
      // Estado de carga (M-09): marcador gris con brillo suave hasta que llega la foto;
      // si falla, se oculta y quedan el nombre y el resto de la ficha.
      imagen.classList.add("cargando-foto");
      imagen.addEventListener("load", () => imagen.classList.remove("cargando-foto"), { once: true });
      imagen.addEventListener("error", () => { imagen.classList.remove("cargando-foto"); imagen.hidden = true; }, { once: true });
      imagen.src = url;
      imagen.alt = `Foto de ${maestro.nombre}`;
    }
    imagen.hidden = !url;

    pintarServicios(maestro.servicios || []);
    // Por nombre y sin indicar cuál es la principal (D-14).
    document.getElementById("lista-comunas").replaceChildren(
      ...(maestro.comunas || []).map((c) => elemento("li", "", c.nombre))
    );
    pintarHorarios(maestro.agenda || []);
    pintarCalificacion(maestro);
    pintarServiciosAPedir(maestro.servicios || []);
    pintarBloques(maestro.ref, maestro.bloques || []);
    cargando.hidden = true;
    perfil.hidden = false;
  }

  // --- Calificación (RF-14, RF-30, CA-05.1, CA-05.2; ADR-026, E-3) ---

  const DIMENSIONES = [
    ["puntualidad", "Puntualidad"],
    ["trabajo", "Calidad del trabajo"],
    ["cordialidad", "Trato"],
  ];

  function nota(valor) {
    return `${Number(valor).toFixed(1).replace(".", ",")} de 5`;
  }

  function pintarCalificacion(maestro) {
    const calificacion = maestro.calificacion || null;
    // CA-05.2: sin evaluaciones, el texto y nunca un promedio en cero.
    document.getElementById("calificacion-maestro").textContent = calificacion
      ? `Calificación: ${maestro.calificacion_texto}`
      : maestro.calificacion_texto || SIN_EVALUACIONES;
    const seccion = document.getElementById("seccion-evaluaciones");
    seccion.hidden = !calificacion;
    if (!calificacion) {
      return;
    }
    document.getElementById("dimensiones").replaceChildren(
      ...DIMENSIONES.flatMap(([clave, nombre]) => [elemento("dt", "", nombre), elemento("dd", "", nota(calificacion[clave]))])
    );
    const comentarios = maestro.comentarios || [];
    document.getElementById("lista-comentarios").replaceChildren(
      ...comentarios.map((c) =>
        elemento("li", "comentario", elemento("p", "", c.texto), elemento("p", "ayuda", c.fecha_texto))
      )
    );
    document.getElementById("sin-comentarios").hidden = comentarios.length > 0;
  }

  // --- Bloques de los próximos 14 días (RF-14, CA-05.1; ADR-022, punto 4) ---

  // Servicio elegido para pedir: radio en la ficha (si hay uno solo, ya va elegido).
  function servicioElegido() {
    const marcado = document.querySelector('input[name="servicio-pedido"]:checked');
    return marcado ? marcado.value : "";
  }

  function pintarServiciosAPedir(servicios) {
    const opciones = servicios.map((s) => {
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "servicio-pedido";
      radio.value = s.ref;
      radio.checked = servicios.length === 1;
      const modalidad = (s.modalidad_texto || "").toLowerCase() || MODALIDADES[s.modalidad] || "";
      const etiqueta = elemento(
        "label",
        "casilla casilla-grande",
        radio,
        elemento(
          "span",
          "casilla-texto",
          s.servicio,
          elemento("span", "nota-precio", `${s.oficio.nombre} · ${formato.monto(s.monto)} ${modalidad}`.trim())
        )
      );
      return etiqueta;
    });
    document.getElementById("opciones-servicio").replaceChildren(...opciones);
    document.getElementById("elegir-servicio").hidden = servicios.length === 0;
  }

  function direccionPedido(refMaestro, bloque) {
    const parametros = new URLSearchParams({ m: refMaestro, b: bloque.ref, f: bloque.fecha });
    const servicio = servicioElegido();
    if (servicio) {
      parametros.set("s", servicio);
    }
    return `pedir-trabajo.html?${parametros.toString()}`;
  }

  function actualizarEnlacesPedido(refMaestro) {
    for (const enlace of document.querySelectorAll("#lista-bloques a[data-bloque]")) {
      enlace.href = direccionPedido(refMaestro, JSON.parse(enlace.dataset.bloque));
    }
  }

  function lineaBloque(refMaestro, bloque, hayServicios) {
    const libre = bloque.estado === "libre";
    const item = elemento("li", `linea-bloque ${libre ? "bloque-libre" : "bloque-ocupado"}`);
    const icono = elemento("span", "", libre ? "✓" : "✕");
    icono.setAttribute("aria-hidden", "true");
    item.append(
      elemento("span", "rango-bloque", `${bloque.inicio} a ${bloque.fin}`),
      elemento("span", `estado ${libre ? "estado-libre" : "estado-ocupado"}`, icono, libre ? "Libre" : "Ocupado")
    );
    if (libre && hayServicios) {
      const cuando = `${formato.fechaLarga(bloque.fecha)} de ${bloque.inicio} a ${bloque.fin}`;
      // «Pedir» en la misma fila del horario (E-4.3); el nombre accesible lleva la fecha y la hora.
      const enlace = elemento("a", "boton boton-pedir", "Pedir", elemento("span", "solo-lector", ` este horario: ${cuando}`));
      enlace.dataset.bloque = JSON.stringify({ ref: bloque.ref, fecha: bloque.fecha });
      enlace.href = direccionPedido(refMaestro, bloque);
      item.append(enlace);
    }
    return item;
  }

  function pintarBloques(refMaestro, bloques) {
    const hoy = formato.hoyEnChile();
    const porFecha = new Map();
    const ordenados = bloques.slice().sort((a, b) => (a.fecha + a.inicio).localeCompare(b.fecha + b.inicio));
    for (const bloque of ordenados) {
      if (!porFecha.has(bloque.fecha)) {
        porFecha.set(bloque.fecha, []);
      }
      porFecha.get(bloque.fecha).push(bloque);
    }
    const hayServicios = document.querySelectorAll('input[name="servicio-pedido"]').length > 0;
    const dias = Array.from(porFecha.entries()).map(([fecha, lista], i) => {
      const dia = elemento(
        "li",
        "dia-ficha",
        elemento("h3", "", formato.fechaConReferencia(fecha, hoy) || fecha),
        elemento("ul", "lista-simple", ...lista.map((b) => lineaBloque(refMaestro, b, hayServicios)))
      );
      // E-4.3: se muestran los primeros DIAS_VISIBLES días; el resto con «Ver más días».
      dia.hidden = i >= DIAS_VISIBLES;
      return dia;
    });
    document.getElementById("lista-bloques").replaceChildren(...dias);
    const mas = document.getElementById("mas-dias");
    const ocultos = dias.length - DIAS_VISIBLES;
    mas.hidden = ocultos <= 0;
    mas.textContent = `Ver ${ocultos} ${ocultos === 1 ? "día más" : "días más"}`;
    document.getElementById("sin-bloques").hidden = bloques.length > 0;
    document.getElementById("con-bloques").hidden = bloques.length === 0;
  }

  const DIAS_VISIBLES = 7;

  // Muestra los días que faltaban y lleva el foco al primero de ellos.
  document.getElementById("mas-dias").addEventListener("click", (evento) => {
    const ocultos = Array.from(document.querySelectorAll("#lista-bloques > li[hidden]"));
    ocultos.forEach((dia) => {
      dia.hidden = false;
    });
    evento.currentTarget.hidden = true;
    if (ocultos.length) {
      const titulo = ocultos[0].querySelector("h3");
      titulo.tabIndex = -1;
      titulo.focus();
    }
  });

  // Al elegir un servicio se actualizan los enlaces y se quita el aviso.
  document.getElementById("opciones-servicio").addEventListener("change", () => {
    const ref = new URLSearchParams(location.search).get("m") || "";
    actualizarEnlacesPedido(ref);
    document.getElementById("error-servicio").textContent = "";
    document.getElementById("elegir-servicio").classList.remove("con-error");
  });

  // Sin servicio elegido no se sale de la ficha: el aviso queda junto a la lista (RNF-15).
  document.getElementById("lista-bloques").addEventListener("click", (evento) => {
    const enlace = evento.target.closest("a[data-bloque]");
    if (!enlace || servicioElegido()) {
      return;
    }
    evento.preventDefault();
    const error = document.getElementById("error-servicio");
    error.textContent = "Primero elige el servicio que necesitas, arriba de los horarios.";
    document.getElementById("elegir-servicio").classList.add("con-error");
    const primero = document.querySelector('input[name="servicio-pedido"]');
    if (primero) {
      primero.focus();
    }
  });

  async function cargar() {
    const ref = new URLSearchParams(location.search).get("m") || "";
    if (!UUID.test(ref)) {
      noEncontrado();
      return;
    }
    aviso.className = "aviso";
    aviso.replaceChildren();
    cargando.hidden = false;
    const { estado, datos } = await api.obtener(`/api/maestros/publicos/${encodeURIComponent(ref)}`);
    if (estado === 200) {
      pintar(datos.maestro);
      return;
    }
    if (estado === 404) {
      noEncontrado();
      return;
    }
    errorCarga(datos.mensaje);
  }

  cargar();
})();
