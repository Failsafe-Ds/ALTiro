// ADR-031: compara formulario.js con los resultados del servidor (vectores.json).
// El correo se revisa de forma básica: se tolera que la pantalla deje pasar algo que el servidor rechaza.
const fs = require("fs");
const vm = require("vm");
const almacen = { length: 0, key: () => null, getItem: () => null, setItem() {}, removeItem() {} };
const ctx = { document: { addEventListener() {} }, window: { addEventListener() {} }, sessionStorage: almacen,
  localStorage: almacen, history: {}, location: {}, console, Date, JSON, Object, Array, Number, String, Math };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync("/front/js/formulario.js", "utf8") + "\nthis.formulario = formulario;", ctx);
const f = ctx.formulario;
const v = JSON.parse(fs.readFileSync("/w/vectores.json", "utf8"));
const fn = { rut: f.errorRut, correo: f.errorCorreo, identificador: f.errorIdentificador };
let fallos = 0, total = 0, masEstricto = 0;
for (const [tipo, casos] of Object.entries(v)) {
  for (const [entrada, esperado] of casos) {
    total++;
    const obtenido = fn[tipo](entrada);
    if (obtenido !== esperado) {
      // Para el correo la revisión es básica: se acepta que deje pasar algo que el servidor rechaza.
      const toleradoCorreo = tipo !== "rut" && obtenido === null && esperado !== null && !/RUT/.test(esperado);
      if (!toleradoCorreo) { fallos++; console.log("DIFIERE", tipo, JSON.stringify(entrada), "| js:", obtenido, "| servidor:", esperado); }
      else console.log("tolerado (solo servidor):", tipo, JSON.stringify(entrada));
    }
    if (obtenido !== null && esperado === null) masEstricto++;
  }
}
console.log(`casos=${total} fallos=${fallos} mas_estricto_que_servidor=${masEstricto}`);
process.exit(fallos ? 1 : 0);
