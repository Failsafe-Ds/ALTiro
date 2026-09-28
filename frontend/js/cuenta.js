// Mi cuenta (RF-02): datos propios, agregar un segundo perfil (ADR-013, punto 2) y cerrar sesión.
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
  const aviso = document.getElementById("aviso-cuenta");

  function irAIngresar() {
    location.assign("ingresar.html?aviso=sesion");
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

    // Agregar perfil: correo y teléfono solo se piden si la cuenta no los tiene (ADR-013, E-1 y E-2).
    mostrar(document.getElementById("seccion-cliente"), !cliente);
    mostrar(document.getElementById("campo-correo-cliente"), !cuenta.correo);
    mostrar(document.getElementById("campo-telefono-cliente"), !cuenta.telefono);
    mostrar(document.getElementById("seccion-maestro"), !maestro);
    mostrar(document.getElementById("campo-telefono-maestro"), !cuenta.telefono);
  }

  // En esta página hay dos formularios: algunos errores se muestran en
  // elementos con otro id (por ejemplo, error-telefono-maestro).
  function conectarFormulario(form, ruta, textoExito, idsDeError = {}) {
    formulario.prepararBoton(form);
    form.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      formulario.limpiarErrores(form);
      formulario.ocupado(form, true);
      const { estado, datos } = await api.enviar(ruta, formulario.leer(form));
      formulario.ocupado(form, false);
      if (estado === 401) {
        irAIngresar();
        return;
      }
      if (estado === 201) {
        pintar(datos.cuenta);
        aviso.className = "aviso aviso-exito";
        aviso.textContent = textoExito;
        aviso.focus();
        return;
      }
      const errores = {};
      for (const [campo, texto] of Object.entries(datos.errores || {})) {
        errores[idsDeError[campo] || campo] = texto;
      }
      const campo = formulario.mostrarErrores(form, { mensaje: datos.mensaje, errores });
      if (campo) {
        campo.focus();
      }
    });
  }

  const { estado, datos } = await api.obtener("/api/cuenta");
  if (estado === 401) {
    irAIngresar();
    return;
  }
  if (estado !== 200) {
    aviso.className = "aviso aviso-error";
    aviso.textContent = datos.mensaje;
    return;
  }
  pintar(datos.cuenta);

  const formCliente = document.getElementById("agregar-cliente");
  await territorio.conectar(formCliente.region, formCliente.comuna);
  conectarFormulario(formCliente, "/api/clientes", "Listo: ya puedes pedir trabajos con tu cuenta.");
  conectarFormulario(
    document.getElementById("agregar-maestro"),
    "/api/maestros/postulaciones",
    "Listo: tu postulación como maestro quedó registrada.",
    { telefono: "telefono-maestro", perfil: "perfil-maestro" }
  );

  document.getElementById("cerrar-sesion").addEventListener("click", async () => {
    await api.borrar("/api/sesion");
    location.assign("index.html");
  });
})();
