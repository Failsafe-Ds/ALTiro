# ADR-031: casos de prueba evaluados con los validadores reales del servidor (datos ficticios).
# Se ejecuta dentro del contenedor app (ver verificar.sh); imprime JSON.
import json, random
import django, os
django.setup()
from identidad.validadores import normalizar_rut, normalizar_correo, calcular_digito_verificador
from identidad.autenticacion import interpretar_identificador
from identidad.errores import ErrorValidacion
random.seed(7)
def fmt(c, dv):
    r = random.random()
    if r < .3: return f"{int(c):,}".replace(",", ".") + "-" + dv
    if r < .6: return c + "-" + dv
    return c + dv
ruts = []
for _ in range(1500):
    c = str(random.randint(1, 99999999))
    dv = calcular_digito_verificador(c)
    if random.random() < .5:
        dv = random.choice("0123456789Kk")
    ruts.append(fmt(c, dv.lower() if random.random() < .2 else dv))
ruts += ["", "0", "0K", "01-9", "1-9", "12.345.678-5", "12345678-k", "123456789-0", " 12345678-5", "12345678-5 ",
         "abc", "11.111.111-1", "1K", "--", "..", "12.345.678", "7-K", "99999999-9", "1.000.005-K", "１２３-4"]
correos = ["a@b.cl", "nombre@dominio.cl", "  Nombre@Dominio.CL ", "a@b", "a@b.c", "@b.cl", "a@.cl", "a@b..cl",
           "a b@c.cl", "a@b.cl.", ".a@b.cl", "a.@b.cl", "a..b@c.cl", "a@@b.cl", "a@b@c.cl", "x" * 250 + "@b.cl",
           "juan.perez+demo@sub.dominio.cl", "a@b-c.cl", "a@xn--b.cl", "ñandú@dominio.cl", "a@dominio.c0m", "abc", "a@b.co"]
salida = {"rut": [], "correo": [], "identificador": []}
def probar(f, v):
    try:
        f(v); return None
    except ErrorValidacion as e:
        return e.mensaje
for v in ruts: salida["rut"].append([v, probar(normalizar_rut, v)])
for v in correos:
    if v.strip(): salida["correo"].append([v, probar(normalizar_correo, v)])
for v in ruts + correos:
    if v.strip(): salida["identificador"].append([v, probar(interpretar_identificador, v)])
print(json.dumps(salida, ensure_ascii=False))
