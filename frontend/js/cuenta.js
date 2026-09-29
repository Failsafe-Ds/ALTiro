// Mi cuenta (RF-02): datos propios, agregar un segundo perfil (ADR-013, punto 2) y cerrar sesión.
// - Si la sesión termina mientras se agrega un perfil, se avisa y se ofrece
//   volver a ingresar, conservando lo escrito (propuesta del S1, §6; RNF-09; DEF-QA-002).
// - "Cerrar sesión" solo da la sesión por cerrada si el servidor lo confirma (RF-02; DEF-QA-003).
// - Hallazgo UX M-2: tras cerrar sesión, "Volver" no debe mostrar los datos
//   desde la caché del navegador (location.replace, datos vaciados y nueva
//   consulta a /api/cuenta al volver a mostrar la página).
"use strict";

(async () => {
  const NOMBRES_ROL = {
    cliente: "Cliente",
    maestro: "Maestro",
    curatoria: "Curatoría",
    comercial: "Administración comercial",
    moderacion: "Moderación",
    control_gestion: "Control de gestión",
  };
  const NOMBRES_DATO = { telefono: "teléfono", correo: "correo" };
  // Lo escrito al terminar la sesión, para devolverlo al volver a esta página.
  // sessionStorage (se borra al cerrar la pestaña), sin contraseñas (ADR-002),
  // con vencimiento (formulario.guardarDatos; hallazgo UX M-4).
  const CLAVE_PENDIENTE = "altiro.cuenta.pendiente";
  const aviso = document.getElementById("aviso-cuenta");
  const avisoSesion = document.getElementById("sesion-terminada");
  let huella = "";
  // true cuando la página terminó de conectar sus formularios y botones.
  let lista = false;

  // replace: "Mi cuenta" no queda en el historial de esta pestaña (M-2).
  function irAIngresar() {
    location.replace("ingresar.html?aviso=sesion");
  }

  // Quita de la página los datos de la cuenta y lo escrito en los formularios,
  // para que no queden en la copia que el navegador guarda al salir (M-2).
  function vaciarDatos() {
    for (const elemento of document.querySelectorAll('[id^="dato-"]')) {
      elemento.textContent = "";
    }
    for (const form of document.querySelectorAll("form")) {
      form.reset();
    }
    huella = "";
  }

  // Hallazgo UX M-3: con la sesión terminada no quedan a la vista los datos de
  // la cuenta (teléfono compartido): se vacían y se ocultan las secciones.
  // Solo queda el aviso para volver a ingresar.
  function ocultarCuenta() {
    vaciarDatos();
    for (const bloque of document.querySelectorAll("main > section, main > nav, main > .acciones")) {
      bloque.classList.add("oculto");
    }
    document.body.dataset.vaciada = "si";
  }

  // Botón "Reintentar" para errores al leer la cuenta (hallazgos UX E-2 y T-11).
  function avisarErrorCarga(mensaje) {
    const boton = formulario.botonVolverACargar("Reintentar");
    aviso.className = "aviso aviso-error";
    aviso.replaceChildren(mensaje, " ", boton);
    aviso.focus();
  }

  function formatearRut(rut) {
    const cuerpo = rut.slice(0, -1).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return cuerpo + "-" + rut.slice(-1);
  }

  function formatearTelefono(telefono) {
    // "+56" + 9 dígitos (ADR-013, E-3) => "+56 9 1234 5678".
    return telefono.replace(/^\+56(\d)(\d{4})(\d{4})$/, "+56 $1 $2 $3");
  }

  function mostrar(elemento, visible) {
    elemento.classList.toggle("oculto", !visible);
  }

  function avisarCuenta(texto, tipo) {
    aviso.className = "aviso aviso-" + tipo;
    aviso.textContent = texto;
    aviso.focus();
  }

  // Identifica la cuenta sin guardar sus datos: lo escrito solo se devuelve a
  // la misma cuenta (teléfonos compartidos, ADR-002). Sin crypto.subtle no se guarda nada.
  async function calcularHuella(cuenta) {
    try {
      const texto = JSON.stringify([cuenta.nombre, cuenta.correo, cuenta.telefono]);
      const resumen = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(texto));
      return Array.from(new Uint8Array(resumen), (b) => b.toString(16).padStart(2, "0")).join("");
    } catch (error) {
      return "";
    }
  }

  function pintar(cuenta) {
    document.getElementById("dato-nombre").textContent = cuenta.nombre;
    document.getElementById("dato-telefono").textContent = cuenta.telefono ? formatearTelefono(cuenta.telefono) : "Sin teléfono";
    document.getElementById("dato-correo").textContent = cuenta.correo || "Sin correo";
    document.getElementById("dato-roles").textContent = cuenta.roles.map((r) => NOMBRES_ROL[r] || r).join(", ");

    const cliente = cuenta.perfil_cliente;
    mostrar(document.getElementById("titulo-comuna"), Boolean(cliente));
    mostrar(document.getElementById("dato-comuna"), Boolean(cliente));
    if (cliente) {
      document.getElementById("dato-comuna").textContent = cliente.comuna.nombre + ", " + cliente.region.nombre;
    }
    const maestro = cuenta.perfil_maestro;
    mostrar(document.getElementById("titulo-rut"), Boolean(maestro));
    mostrar(document.getElementById("dato-rut"), Boolean(maestro));
    if (maestro) {
      document.getElementById("dato-rut").textContent = formatearRut(maestro.rut);
    }
    // Accesos al expediente (HU-11, HU-17). Solo navegación: la API vuelve a
    // exigir el rol de maestro en cada consulta.
    mostrar(document.getElementById("accesos-maestro"), Boolean(maestro));
    // Acceso a curatoría (HU-19). Solo navegación: cada ruta de la API exige el rol.
    mostrar(document.getElementById("accesos-curatoria"), cuenta.roles.includes("curatoria"));

    // Agregar perfil: correo y teléfono solo se piden si la cuenta no los tiene (ADR-013, E-1 y E-2).
    mostrar(document.getElementById("seccion-cliente"), !cliente);
    mostrar(document.getElementById("campo-correo-cliente"), !cuenta.correo);
    mostrar(document.getElementById("campo-telefono-cliente"), !cuenta.telefono);
    mostrar(document.getElementById("seccion-maestro"), !maestro);
    mostrar(document.getElementById("campo-telefono-maestro"), !cuenta.telefono);
  }

  // --- Sesión terminada (DEF-QA-002) ---

  function guardarPendiente(form) {
    if (!huella) {
      return false;
    }
    const valores = {};
    for (const campo of form.querySelectorAll("input[name], select[name]")) {
      if (campo.type !== "password" && campo.value !== "" && !campo.closest(".oculto")) {
        valores[campo.name] = campo.value;
      }
    }
    return formulario.guardarDatos(CLAVE_PENDIENTE, { huella, form: form.id, valores });
  }

  // No se reinterpreta la operación como un registro ni se piden datos de
  // visitante: se explica qué pasó y se ofrece volver a ingresar.
  function sesionTerminada(form) {
    formulario.limpiarErrores(form);
    // Primero se guarda lo escrito (con la huella de la cuenta); después se vacía la página.
    const guardado = guardarPendiente(form);
    ocultarCuenta();
    const enlace = document.createElement("a");
    enlace.className = "boton";
    enlace.href = "ingresar.html";
    enlace.textContent = "Ingresar de nuevo";
    avisoSesion.className = "aviso aviso-error";
    avisoSesion.replaceChildren(
      "Tu sesión terminó. Vuelve a ingresar para continuar." +
        (guardado ? " Lo que escribiste seguirá aquí cuando vuelvas a ingresar." : ""),
      enlace
    );
    avisoSesion.focus();
  }

  // Devuelve lo guardado solo si es de esta misma cuenta, y lo borra siempre.
  function tomarPendiente() {
    const pendiente = formulario.recuperar(CLAVE_PENDIENTE);
    formulario.olvidar(CLAVE_PENDIENTE);
    return pendiente && huella && pendiente.huella === huella ? pendiente : null;
  }

  function restaurar(pendiente) {
    const form = pendiente && document.getElementById(pendiente.form);
    if (!form || form.closest(".oculto")) {
      return;
    }
    // Hallazgo UX M-6: el aviso solo aparece si de verdad se recuperó algo.
    // Región y comuna ya las aplicó territorio.conectar: cuentan si quedaron puestas.
    let recuperados = 0;
    for (const [nombre, valor] of Object.entries(pendiente.valores || {})) {
      const campo = form.querySelector(`[name="${nombre}"]`);
      if (!campo || campo.type === "password" || campo.closest(".oculto")) {
        continue;
      }
      if (nombre !== "region" && nombre !== "comuna") {
        campo.value = valor;
      }
      if (valor !== "" && campo.value === valor) {
        recuperados += 1;
      }
    }
    if (recuperados > 0) {
      avisarCuenta("Recuperamos lo que habías escrito. Revísalo y vuelve a enviarlo.", "exito");
    }
  }

  // --- Errores de los formularios ---

  function campoDe(form, id) {
    return form.querySelector(`[aria-describedby~="error-${id}"]`) || form.querySelector(`[name="${id}"]`);
  }

  // Un error sobre algo que la persona no ve (un campo oculto o ausente, o el
  // perfil completo) indica que la cuenta cambió o que la sesión terminó.
  function hayQueRevisarCuenta(form, errores) {
    return Object.keys(errores).some((id) => {
      const campo = campoDe(form, id);
      return id.startsWith("perfil") || !campo || Boolean(campo.closest(".oculto"));
    });
  }

  // En esta página hay dos formularios: algunos errores se muestran en
  // elementos con otro id (por ejemplo, error-telefono-maestro).
  function conectarFormulario(form, ruta, textoExito, idsDeError = {}) {
    formulario.prepararBoton(form);
    const seccion = form.closest("section");
    const textoBoton = form.querySelector('button[type="submit"]').textContent;
    form.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      formulario.limpiarErrores(form);
      avisoSesion.replaceChildren();
      avisoSesion.className = "aviso";
      formulario.ocupado(form, true);
      const { estado, datos } = await api.enviar(ruta, formulario.leer(form));
      if (estado === 201) {
        formulario.ocupado(form, false);
        pintar(datos.cuenta);
        avisarCuenta(textoExito, "exito");
        return;
      }
      if (estado === 401) {
        formulario.ocupado(form, false);
        sesionTerminada(form);
        return;
      }
      const errores = {};
      for (const [campo, texto] of Object.entries(datos.errores || {})) {
        errores[idsDeError[campo] || campo] = texto;
      }
      let mensaje = datos.mensaje;
      if (estado === 400 && hayQueRevisarCuenta(form, errores)) {
        // Los endpoints de perfil también atienden a visitantes: sin sesión, el
        // servidor responde como a un registro nuevo. Se consulta la cuenta
        // para saber si la sesión terminó o si la cuenta cambió.
        const revision = await api.obtener("/api/cuenta");
        if (revision.estado === 401) {
          formulario.ocupado(form, false);
          sesionTerminada(form);
          return;
        }
        if (revision.estado !== 200) {
          // Hallazgo UX O-1: sin conexión (estado 0) o con el servidor sin
          // responder no se sabe si la sesión sigue abierta, así que no se
          // muestran los errores de visitante: se avisa y se conserva lo escrito.
          formulario.ocupado(form, false);
          formulario.limpiarErrores(form);
          formulario.avisar(
            form,
            revision.estado === 0
              ? `No pudimos conectarnos. Revisa tu señal o tu wifi y pulsa «${textoBoton}» de nuevo. Lo que escribiste sigue aquí.`
              : revision.datos.mensaje,
            "error"
          );
          return;
        }
        if (revision.estado === 200) {
          pintar(revision.datos.cuenta);
          if (seccion.classList.contains("oculto")) {
            // El perfil ya estaba agregado (por ejemplo, desde otra pestaña).
            formulario.ocupado(form, false);
            avisarCuenta(datos.errores.perfil || "Tu cuenta ya tiene este perfil.", "exito");
            return;
          }
          // Datos de contacto que la cuenta ya tiene: el campo ya no se muestra
          // ni se envía, así que basta con volver a enviar.
          const yaTiene = [];
          for (const [campo, nombre] of Object.entries(NOMBRES_DATO)) {
            const id = idsDeError[campo] || campo;
            const elemento = campoDe(form, id);
            if (errores[id] && elemento && elemento.closest(".oculto")) {
              delete errores[id];
              yaTiene.push(nombre);
            }
          }
          if (yaTiene.length) {
            mensaje =
              `Tu cuenta ya tiene ${yaTiene.join(" y ")}, así que no necesitas escribirlo. ` +
              `Revisa los datos y pulsa «${textoBoton}» de nuevo.`;
          }
        }
      }
      formulario.ocupado(form, false);
      const campo = formulario.mostrarErrores(form, { mensaje, errores });
      if (campo) {
        campo.focus();
      }
    });
  }

  // --- Cerrar sesión (RF-02; DEF-QA-003) ---
  // Solo se muestra la sesión como cerrada si el servidor lo confirma (204) o
  // si ya no había sesión (401). Si no, la página se mantiene y se puede reintentar.
  function conectarCierre() {
    const boton = document.getElementById("cerrar-sesion");
    const avisoCerrar = document.getElementById("aviso-cerrar");
    const texto = boton.textContent;
    boton.addEventListener("click", async () => {
      avisoCerrar.textContent = "";
      avisoCerrar.className = "aviso";
      boton.disabled = true;
      boton.textContent = "Cerrando sesión…";
      const { estado } = await api.borrar("/api/sesion");
      if (estado === 204 || estado === 401) {
        // M-4: no queda nada escrito en este teléfono. M-2: la página se vacía
        // antes de salir y "Mi cuenta" no queda en el historial.
        formulario.olvidarTodo();
        vaciarDatos();
        location.replace("index.html?aviso=sesion-cerrada");
        return;
      }
      boton.disabled = false;
      boton.textContent = texto;
      avisoCerrar.className = "aviso aviso-error";
      if (estado === 0) {
        avisoCerrar.textContent =
          "No pudimos cerrar tu sesión porque no hay conexión: tu sesión sigue abierta en este teléfono. Revisa tu señal o tu wifi y pulsa «Cerrar sesión» de nuevo.";
      } else {
        // T-11: en vez de "recarga la página", el botón que lo hace.
        avisoCerrar.replaceChildren(
          "No pudimos cerrar tu sesión: sigue abierta en este teléfono. Pulsa «Cerrar sesión» de nuevo; si no funciona, toca «Volver a cargar» e inténtalo otra vez.",
          " ",
          formulario.botonVolverACargar()
        );
      }
      avisoCerrar.focus();
    });
  }

  // M-2: si el navegador vuelve a mostrar esta página desde su caché ("Volver"),
  // se consulta de nuevo la cuenta. Si la sesión ya terminó (por ejemplo, se
  // cerró en otra pestaña), se vacían los datos y se va a "Ingresar".
  window.addEventListener("pageshow", async (evento) => {
    if (!evento.persisted) {
      return;
    }
    const revision = await api.obtener("/api/cuenta");
    if (revision.estado === 200) {
      if (!lista || document.body.dataset.vaciada) {
        // La primera carga no terminó (por ejemplo, sin conexión): se carga de nuevo.
        location.reload();
        return;
      }
      pintar(revision.datos.cuenta);
      huella = await calcularHuella(revision.datos.cuenta);
      return;
    }
    vaciarDatos();
    if (revision.estado === 401) {
      irAIngresar();
      return;
    }
    // Sin conexión u otro error: no se muestran datos que no se pudieron comprobar.
    avisarErrorCarga(revision.datos.mensaje);
  });

  const { estado, datos } = await api.obtener("/api/cuenta");
  if (estado === 401) {
    irAIngresar();
    return;
  }
  if (estado !== 200) {
    avisarErrorCarga(datos.mensaje);
    return;
  }
  pintar(datos.cuenta);
  conectarCierre();
  huella = await calcularHuella(datos.cuenta);
  const pendiente = tomarPendiente();

  const formCliente = document.getElementById("agregar-cliente");
  await territorio.conectar(
    formCliente.region,
    formCliente.comuna,
    pendiente && pendiente.form === formCliente.id ? pendiente.valores : {}
  );
  conectarFormulario(formCliente, "/api/clientes", "Listo: ya puedes pedir trabajos con tu cuenta.");
  conectarFormulario(
    document.getElementById("agregar-maestro"),
    "/api/maestros/postulaciones",
    "Primer paso listo. Ahora envía las fotos de tus documentos desde «Mi postulación».",
    { telefono: "telefono-maestro", perfil: "perfil-maestro" }
  );
  restaurar(pendiente);
  lista = true;
})();
