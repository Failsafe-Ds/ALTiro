// Pedir un trabajo a un maestro (RF-15 a RF-18, HU-06, CA-06.1 a CA-06.4; ADR-023).
// - El servicio y el horario ya se eligieron en la ficha: llegan por la
//   dirección (m, b, f, s) y se resuelven contra GET /api/maestros/publicos/<m>
//   (misma respuesta pública que usa la ficha; sin inventar otra consulta).
// - Formulario en 4 pasos de 5 campos o menos (RNF-14): resumen (sin campos),
//   comuna, dirección y descripción, materiales y confirmar.
// - El progreso se conserva con formulario.porPasos (sessionStorage, vence a
//   las 2 horas; ADR-002: nunca RUT ni contraseña) para no perder lo escrito
//   si se corta la señal o se recarga la página (RNF-20).
// - POST /api/tickets: 201 o 200 (pedido repetido, D-10) van a mis-pedidos.html;
//   400 por campo (CA-06.4); 409 con "bloques" ofrece los horarios libres
//   vigentes (CA-06.2); otro 409 es un mensaje accionable del servidor.
"use strict";

(() => {
  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const FECHA = /^\d{4}-\d{2}-\d{2}$/;
  // Un borrador por pedido (maestro, horario, fecha y servicio): elegir otro
  // horario u otro maestro no arrastra lo escrito para el anterior (RNF-20).
  const PREFIJO_CLAVE = "altiro.pedir-trabajo.";
  const MODALIDADES = { por_trabajo: "por trabajo", por_hora: "por hora" };
  const NO_ENCONTRADO = "No encontramos este pedido. Vuelve a elegir el maestro y el horario.";
  const YA_NO_OFRECE = "Este maestro ya no ofrece este servicio. Vuelve a su ficha para elegir otro.";
  const YA_NO_LIBRE = "Ese horario ya no está disponible. Vuelve a la ficha para elegir otro.";

  const cargando = document.getElementById("cargando");
  const avisoPagina = document.getElementById("aviso-pagina");
  const avisoSesion = document.getElementById("aviso-sesion");
  const form = document.getElementById("form-pedido");
  const seccionBloques = document.getElementById("seccion-bloques");
  const selectComuna = document.getElementById("comuna");
  const selectMateriales = document.getElementById("materiales");

  const elemento = dom.elemento;

  function parametros() {
    const p = new URLSearchParams(location.search);
    return { m: p.get("m") || "", b: p.get("b") || "", f: p.get("f") || "", s: p.get("s") || "" };
  }

  function parametrosValidos(p) {
    return UUID.test(p.m) && UUID.test(p.b) && UUID.test(p.s) && FECHA.test(p.f);
  }

  function errorFatal(mensaje, enlaceFicha) {
    cargando.hidden = true;
    form.hidden = true;
    const enlace = elemento("a", "boton", "Buscar un maestro");
    enlace.href = enlaceFicha || "buscar.html";
    avisoPagina.className = "aviso aviso-error";
    avisoPagina.replaceChildren(mensaje, enlace);
    avisoPagina.focus();
  }

  function errorCarga(mensaje, reintentar) {
    cargando.hidden = true;
    form.hidden = true;
    const boton = elemento("button", "", "Reintentar");
    boton.type = "button";
    boton.addEventListener("click", reintentar);
    avisoPagina.className = "aviso aviso-error";
    avisoPagina.replaceChildren(mensaje, boton);
    avisoPagina.focus();
  }

  // --- Sesión: la creación exige rol cliente (RF-15). Solo aviso: el servidor decide. ---

  function avisarSinSesion() {
    const enlace = elemento("a", "boton", "Ingresar");
    enlace.href = "ingresar.html";
    avisoSesion.className = "aviso";
    avisoSesion.hidden = false;
    avisoSesion.replaceChildren(
      "Para enviar este pedido necesitas ingresar con tu cuenta de cliente. Puedes seguir llenando el formulario: lo que escribas se conserva.",
      " ",
      enlace
    );
  }

  function avisarSinRolCliente() {
    const enlace = elemento("a", "boton", "Ir a mi cuenta");
    enlace.href = "cuenta.html";
    avisoSesion.className = "aviso";
    avisoSesion.hidden = false;
    avisoSesion.replaceChildren(
      "Tu cuenta todavía no puede pedir trabajos. Para pedir trabajos con esta misma cuenta, entra a «Mi cuenta» y completa «Quiero pedir trabajos». Lo que escribiste sigue aquí.",
      " ",
      enlace
    );
  }

  async function revisarSesion() {
    const { estado, datos } = await api.obtener("/api/cuenta");
    if (estado === 200 && datos.cuenta && datos.cuenta.perfil_cliente) {
      avisoSesion.hidden = true;
      return;
    }
    if (estado === 200) {
      avisarSinRolCliente();
      return;
    }
    avisarSinSesion();
  }

  // --- Carga de la ficha pública y resolución del servicio y el horario elegidos ---

  let maestro = null;
  let servicio = null;
  let bloque = null;
  let pasos = null;

  function pintarResumen() {
    document.getElementById("resumen-maestro").textContent = maestro.nombre;
    document.getElementById("resumen-servicio").textContent = `${servicio.servicio} (${servicio.oficio.nombre})`;
    const modalidad = (servicio.modalidad_texto || MODALIDADES[servicio.modalidad] || "").toLowerCase();
    document.getElementById("resumen-precio").textContent = `${formato.monto(servicio.monto)} ${modalidad}`.trim();
    document.getElementById("resumen-horario").textContent =
      `${formato.fechaConReferencia(bloque.fecha)}, de ${bloque.inicio} a ${bloque.fin}`;
    document.getElementById("enlace-volver-ficha").href = `perfil-maestro.html?m=${encodeURIComponent(maestro.ref)}`;
  }

  function poblarComunas() {
    selectComuna.replaceChildren(
      elemento("option", "", "Elige una comuna"),
      ...(maestro.comunas || []).map((c) => {
        const opcion = document.createElement("option");
        opcion.value = c.codigo;
        opcion.textContent = c.nombre;
        return opcion;
      })
    );
  }

  function actualizarResumenFinal() {
    const datos = formulario.leer(form);
    const materialesTexto = { si: "Sí, tienes los materiales", no: "No, el maestro debe llevarlos" };
    const comunaTexto = selectComuna.selectedOptions[0] ? selectComuna.selectedOptions[0].textContent : "";
    document.getElementById("resumen-final").replaceChildren(
      elemento("dt", "", "Comuna"), elemento("dd", "", datos.comuna ? comunaTexto : "—"),
      elemento("dt", "", "Dirección"), elemento("dd", "", datos.direccion || "—"),
      elemento("dt", "", "Descripción"), elemento("dd", "", datos.descripcion || "—"),
      elemento("dt", "", "Materiales"), elemento("dd", "", materialesTexto[datos.materiales] || "—")
    );
  }

  // --- Horarios alternativos (CA-06.2): solo fecha, inicio y fin (sin ref de patrón). ---

  function pintarBloquesAlternativos(bloques) {
    document.getElementById("lista-bloques-alternativos").replaceChildren(
      ...(bloques || []).map((b) =>
        elemento("li", "tarjeta", `${formato.fechaConReferencia(b.fecha)}, de ${b.inicio} a ${b.fin}`)
      )
    );
    document.getElementById("enlace-ficha-alternativos").href = `perfil-maestro.html?m=${encodeURIComponent(maestro.ref)}`;
    if (!bloques || bloques.length === 0) {
      document.getElementById("lista-bloques-alternativos").replaceChildren(
        elemento("li", "", "Este maestro no tiene otros horarios libres por ahora.")
      );
    }
    form.hidden = true;
    seccionBloques.hidden = false;
    seccionBloques.querySelector("h2").focus();
  }

  // --- Envío ---

  async function enviar(evento) {
    evento.preventDefault();
    formulario.limpiarErrores(form);
    const datos = formulario.leer(form);
    if (datos.materiales !== "si" && datos.materiales !== "no") {
      const campo = formulario.mostrarErrores(form, {
        mensaje: "Responde si tienes los materiales para continuar.",
        errores: { materiales: "Elige una opción." },
      });
      if (campo) {
        pasos.irAlCampo(campo);
      }
      return;
    }
    formulario.ocupado(form, true);
    const p = parametros();
    const cuerpo = {
      maestro: p.m, servicio: p.s, comuna: datos.comuna, fecha: p.f, inicio: bloque.inicio, fin: bloque.fin,
      direccion: datos.direccion, descripcion: datos.descripcion, materiales: datos.materiales === "si",
    };
    const { estado, datos: respuesta } = await api.enviar("/api/tickets", cuerpo);
    formulario.ocupado(form, false);
    if (estado === 201 || estado === 200) {
      pasos.terminar();
      location.assign("mis-pedidos.html?enviado=1");
      return;
    }
    if (estado === 401) {
      avisarSinSesion();
      formulario.avisar(form, "Tu sesión terminó o no has iniciado sesión. Ingresa y vuelve a esta página: lo que escribiste sigue aquí.", "error");
      return;
    }
    if (estado === 403) {
      avisarSinRolCliente();
      formulario.avisar(form, "Tu cuenta todavía no puede pedir trabajos.", "error");
      return;
    }
    if (estado === 409 && Array.isArray(respuesta.bloques)) {
      pintarBloquesAlternativos(respuesta.bloques);
      return;
    }
    const campo = formulario.mostrarErrores(form, respuesta);
    if (campo) {
      pasos.irAlCampo(campo);
    }
  }

  async function cargar() {
    const p = parametros();
    if (!parametrosValidos(p)) {
      errorFatal(NO_ENCONTRADO);
      return;
    }
    cargando.hidden = false;
    const { estado, datos } = await api.obtener(`/api/maestros/publicos/${encodeURIComponent(p.m)}`);
    cargando.hidden = true;
    if (estado === 404) {
      errorFatal(NO_ENCONTRADO);
      return;
    }
    if (estado !== 200) {
      errorCarga(datos.mensaje, cargar);
      return;
    }
    maestro = datos.maestro;
    servicio = (maestro.servicios || []).find((s) => s.ref === p.s) || null;
    if (!servicio) {
      errorFatal(YA_NO_OFRECE, `perfil-maestro.html?m=${encodeURIComponent(p.m)}`);
      return;
    }
    bloque = (maestro.bloques || []).find((b) => b.ref === p.b && b.fecha === p.f) || null;
    if (!bloque || bloque.estado !== "libre") {
      errorFatal(YA_NO_LIBRE, `perfil-maestro.html?m=${encodeURIComponent(p.m)}`);
      return;
    }
    pintarResumen();
    poblarComunas();
    form.hidden = false;
    formulario.prepararBoton(form);
    pasos = formulario.porPasos(form, { clave: `${PREFIJO_CLAVE}${p.m}.${p.b}.${p.f}.${p.s}`, alRestaurar: () => actualizarResumenFinal() });
    form.addEventListener("input", actualizarResumenFinal);
    form.addEventListener("change", actualizarResumenFinal);
    actualizarResumenFinal();
    form.addEventListener("submit", enviar);
    revisarSesion();
  }

  cargar();
})();
