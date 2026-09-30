// Moderación de denuncias (HU-21, RF-31, RF-37, CA-21.1, CA-21.2; ADR-026, E-4; M-04).
// - GET /api/moderacion/denuncias?estado=abierta|resuelta: la lista.
// - GET /api/moderacion/denuncias/<ref>: detalle (sin dirección ni teléfono).
// - GET /api/moderacion/denuncias/<ref>/conversacion: solo al pulsar el botón,
//   con la advertencia de que el acceso queda registrado y avisa a las partes.
// - POST /api/moderacion/denuncias/<ref>/resolucion {decision, motivo}.
// El servidor exige el rol, revisa el conflicto de interés y el estado.
"use strict";

(() => {
  const QUIEN = { cliente: "Cliente", maestro: "Maestro" };
  const NOMBRES = { puntualidad: "Puntualidad", trabajo: "Trabajo", cordialidad: "Trato" };

  const avisoPagina = document.getElementById("aviso-pagina");
  const cargando = document.getElementById("cargando");
  const lista = document.getElementById("lista-denuncias");
  const sinDenuncias = document.getElementById("sin-denuncias");
  const filtro = document.getElementById("filtro-estado");
  const detalle = document.getElementById("detalle");
  const detalleDatos = document.getElementById("detalle-datos");
  const bloqueConversacion = document.getElementById("bloque-conversacion");
  const listaMensajes = document.getElementById("lista-mensajes");
  const sinMensajes = document.getElementById("sin-mensajes");
  const form = document.getElementById("formulario-resolucion");
  let actual = null;

  function elemento(etiqueta, clase, ...hijos) {
    const nodo = document.createElement(etiqueta);
    if (clase) {
      nodo.className = clase;
    }
    nodo.append(...hijos);
    return nodo;
  }

  function fechaHora(iso) {
    const fecha = new Date(iso);
    return fecha.toLocaleString("es-CL", { timeZone: "America/Santiago", dateStyle: "medium", timeStyle: "short", hour12: false });
  }

  function avisar(texto, accion) {
    avisoPagina.className = "aviso aviso-error";
    avisoPagina.replaceChildren(texto, ...(accion ? [" ", accion] : []));
    avisoPagina.focus();
  }

  // 401: sesión vencida. 403: sin rol o conflicto de interés (mensaje del servidor). 404: no existe o no disponible.
  function tratarError(estado, datos) {
    if (estado === 401) {
      const enlace = elemento("a", "boton", "Ingresar de nuevo");
      enlace.href = "ingresar.html?aviso=sesion&siguiente=moderacion";
      avisar("Tu sesión terminó. Vuelve a ingresar para seguir.", enlace);
      return;
    }
    if (estado === 404) {
      avisar("Esta denuncia ya no está disponible para esa acción. Vuelve a la lista y elige otra.");
      return;
    }
    avisar((datos && datos.mensaje) || "No pudimos completar la acción. Revisa tu señal o tu wifi e inténtalo de nuevo.");
  }

  // --- Lista ---

  async function cargarLista() {
    cargando.hidden = false;
    const { estado, datos } = await api.obtener(`/api/moderacion/denuncias?estado=${encodeURIComponent(filtro.value)}`);
    cargando.hidden = true;
    if (estado !== 200) {
      tratarError(estado, datos);
      return;
    }
    const denuncias = datos.denuncias || [];
    sinDenuncias.hidden = denuncias.length > 0;
    lista.replaceChildren(
      ...denuncias.map((d) => {
        const boton = elemento("button", "boton-secundario", "Revisar");
        boton.type = "button";
        boton.setAttribute("aria-label", `Revisar la denuncia de ${d.servicio} en ${d.comuna}`);
        boton.addEventListener("click", () => abrir(d.ref));
        return elemento(
          "li",
          "tarjeta",
          elemento("p", "", `${d.servicio}, ${d.comuna}`),
          elemento("p", "ayuda", `Denunció: ${QUIEN[d.denunciante]}. Recibida el ${fechaHora(d.creada_en)}. Estado: ${d.estado_texto}.`),
          elemento("div", "acciones", boton)
        );
      })
    );
  }

  // --- Detalle ---

  function dato(nombre, valor) {
    return [elemento("dt", "", nombre), elemento("dd", "", valor)];
  }

  function pintarDetalle(d) {
    const ev = d.evaluacion;
    const t = d.ticket;
    const datos = elemento(
      "dl",
      "datos",
      ...dato("Estado", d.estado_texto),
      ...dato("Denunció", QUIEN[d.denunciante]),
      ...dato("Motivo de la denuncia", d.motivo),
      ...dato("Trabajo", `${t.servicio} (${t.oficio}), ${t.comuna}`),
      ...dato("Horario", `${formato.fechaLarga(t.fecha)}, de ${t.inicio} a ${t.fin}`),
      ...dato("Precio", `${t.modalidad_texto}: publicado ${formato.monto(t.monto_publicado)}` +
        (t.monto_final ? `, final ${formato.monto(t.monto_final)}` : "")),
      ...dato("Evaluación hecha por", QUIEN[ev.parte]),
      ...Object.keys(NOMBRES).flatMap((clave) => dato(NOMBRES[clave], `${ev[clave]} de 5`)),
      ...dato("Comentario", ev.comentario || "(sin comentario)"),
      ...dato("Estado de la evaluación", ev.estado_texto)
    );
    const partes = [datos];
    if (d.decision_texto) {
      partes.push(elemento("p", "estado", `Decisión: ${d.decision_texto}. Motivo: ${d.motivo_resolucion}`));
    }
    detalleDatos.replaceChildren(...partes);
    bloqueConversacion.hidden = !d.puede_ver_conversacion;
    listaMensajes.hidden = true;
    sinMensajes.hidden = true;
    form.hidden = d.estado !== "abierta";
    form.reset();
    formulario.limpiarErrores(form);
  }

  async function abrir(ref) {
    avisoPagina.className = "aviso";
    avisoPagina.replaceChildren();
    const { estado, datos } = await api.obtener(`/api/moderacion/denuncias/${encodeURIComponent(ref)}`);
    if (estado !== 200) {
      detalle.hidden = true;
      tratarError(estado, datos);
      return;
    }
    actual = datos.denuncia;
    pintarDetalle(actual);
    detalle.hidden = false;
    detalle.focus();
  }

  document.getElementById("ver-conversacion").addEventListener("click", async () => {
    if (!actual) {
      return;
    }
    const { estado, datos } = await api.obtener(`/api/moderacion/denuncias/${encodeURIComponent(actual.ref)}/conversacion`);
    if (estado !== 200) {
      tratarError(estado, datos);
      return;
    }
    const mensajes = datos.mensajes || [];
    listaMensajes.replaceChildren(
      ...mensajes.map((m) =>
        elemento(
          "li",
          "mensaje",
          elemento("p", "mensaje-cabeza", `${QUIEN[m.autor] || m.autor}, ${fechaHora(m.enviado_en)}`),
          elemento("p", "mensaje-texto", m.texto)
        )
      )
    );
    listaMensajes.hidden = mensajes.length === 0;
    sinMensajes.hidden = mensajes.length > 0;
  });

  // --- Resolución ---

  formulario.prepararBoton(form);
  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (!actual) {
      return;
    }
    formulario.limpiarErrores(form);
    const marcada = form.querySelector('input[name="decision"]:checked');
    formulario.ocupado(form, true);
    const { estado, datos } = await api.enviar(`/api/moderacion/denuncias/${encodeURIComponent(actual.ref)}/resolucion`, {
      decision: marcada ? marcada.value : "",
      motivo: document.getElementById("motivo").value,
    });
    formulario.ocupado(form, false);
    if (estado === 200) {
      actual = datos.denuncia;
      pintarDetalle(actual);
      cargarLista();
      detalleDatos.prepend(elemento("p", "aviso aviso-exito", "Decisión registrada."));
      detalle.focus();
      return;
    }
    if (estado === 400) {
      const campo = formulario.mostrarErrores(form, datos);
      if (campo) {
        campo.focus();
      }
      return;
    }
    if (estado === 409) {
      formulario.avisar(form, datos.mensaje, "error");
      return;
    }
    tratarError(estado, datos);
  });

  filtro.addEventListener("change", () => {
    detalle.hidden = true;
    cargarLista();
  });
  cargarLista();
})();
