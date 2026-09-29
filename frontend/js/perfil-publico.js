// Perfil público del maestro, sin sesión (RF-14 y RF-13 parciales, HU-05 parcial; ADR-019, D-12 y D-14; ADR-021).
// - GET /api/maestros/publicos/<ref>: nombre, foto (160 y 480 px), servicios
//   visibles (oficio, servicio, forma de cobro y monto), comunas (sin indicar
//   cuál es la principal) y horarios semanales en "HH:MM" de 24 horas.
// - Un maestro no publicado o una referencia inexistente responden el mismo
//   404: la página dice lo mismo en ambos casos, sin motivos.
// - Sin datos de contacto: la API no los entrega. Sin calificaciones (S5) ni
//   bloques ocupados (S4).
// El parámetro "m" se valida como UUID antes de consultar; si no lo es, se
// muestra el mismo aviso que un 404 (no se arma ninguna ruta con él).
"use strict";

(() => {
  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const NO_ENCONTRADO = "No encontramos este perfil. Puede que el maestro ya no esté disponible.";
  const DIAS = { 1: "lunes", 2: "martes", 3: "miércoles", 4: "jueves", 5: "viernes", 6: "sábado", 7: "domingo" };
  const MODALIDADES = { por_trabajo: "por trabajo", por_hora: "por hora" };

  const cargando = document.getElementById("cargando");
  const aviso = document.getElementById("aviso-pagina");
  const perfil = document.getElementById("perfil");

  function elemento(etiqueta, clase, ...hijos) {
    const nodo = document.createElement(etiqueta);
    if (clase) {
      nodo.className = clase;
    }
    nodo.append(...hijos);
    return nodo;
  }

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
    cargando.hidden = true;
    perfil.hidden = false;
  }

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
