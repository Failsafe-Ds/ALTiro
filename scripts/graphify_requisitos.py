"""Extrae los identificadores del informe como nodos de graphify, sin LLM (ADR-025).

Cada fila de tabla de `docs/informe-altiro.md` cuya primera celda sea un
identificador (HU, RF, RNF, NTI, CA, OBJ) produce un nodo. Cada identificador
citado en la misma fila produce una arista `references` EXTRACTED. Los rangos
"CA-06.1 a CA-06.4" se expanden.

Uso (con el intérprete de graphify):
    python scripts/graphify_requisitos.py graphify-out/.graphify_chunk_01.json

Si el archivo de salida ya existe, se fusionan sus nodos con los nuevos. Los
nodos de requisitos del script reemplazan a los que tengan el mismo id; las
aristas previas se conservan (el armado del grafo resuelve las que apuntan a
otros fragmentos).
"""
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INFORME = RAIZ / "docs" / "informe-altiro.md"
FUENTE = str(INFORME)
ID = re.compile(r"\b(HU|RF|RNF|NTI|OBJ|CA)-(\d{2})(?:\.(\d+))?\b")
RANGO = re.compile(r"\bCA-(\d{2})\.(\d+) a CA-\1\.(\d+)\b")


def nodo_id(texto):
    return "docs_informe_altiro_" + re.sub(r"[^a-z0-9]", "_", texto.lower())


def ids_en(texto):
    encontrados = {m.group(0) for m in ID.finditer(texto)}
    for m in RANGO.finditer(texto):
        for i in range(int(m.group(2)), int(m.group(3)) + 1):
            encontrados.add(f"CA-{m.group(1)}.{i}")
    return encontrados


def main(salida):
    nodos, aristas, seccion = {}, [], None
    for n, linea in enumerate(INFORME.read_text(encoding="utf-8").splitlines(), 1):
        if linea.startswith("#"):
            seccion = linea.lstrip("# ").split(" ")[0].rstrip(".")
            continue
        if not linea.startswith("|"):
            continue
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        m = ID.fullmatch(celdas[0]) if celdas else None
        if not m:
            continue
        propio = celdas[0]
        resto = " | ".join(celdas[1:])
        corto = celdas[1] if len(celdas) > 1 else ""
        # En la tabla de RNF la segunda celda es la categoría ISO; la descripción es la tercera.
        if propio.startswith("RNF") and len(celdas) > 2:
            corto = celdas[2]
        nid = nodo_id(propio)
        nodos[nid] = {
            "id": nid, "label": f"{propio} — {corto[:80]}", "file_type": "document",
            "source_file": FUENTE, "source_location": f"§{seccion} L{n}",
            "rationale": resto[:600], "source_url": None, "captured_at": None,
            "author": None, "contributor": None,
        }
        for otro in sorted(ids_en(resto) - {propio}):
            aristas.append({
                "source": nid, "target": nodo_id(otro), "relation": "references",
                "confidence": "EXTRACTED", "confidence_score": 1.0,
                "source_file": FUENTE, "source_location": f"§{seccion} L{n}", "weight": 1.0,
            })
    # Nodo mínimo para cada id citado que no tenga fila propia, para no dejar aristas colgando.
    for a in aristas:
        if a["target"] not in nodos:
            etiqueta = a["target"].removeprefix("docs_informe_altiro_").upper().replace("_", "-", 1).replace("_", ".")
            nodos[a["target"]] = {
                "id": a["target"], "label": etiqueta, "file_type": "document", "source_file": FUENTE,
                "source_location": None, "source_url": None, "captured_at": None,
                "author": None, "contributor": None,
            }

    ruta = Path(salida)
    previo = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {"nodes": [], "edges": [], "hyperedges": []}
    finales = {n["id"]: n for n in previo["nodes"]}
    finales.update(nodos)
    todas = previo["edges"] + aristas
    ruta.write_text(json.dumps({
        "nodes": list(finales.values()), "edges": todas, "hyperedges": previo.get("hyperedges", []),
        "input_tokens": previo.get("input_tokens", 0), "output_tokens": previo.get("output_tokens", 0),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"requisitos: {len(nodos)} nodos, {len(aristas)} aristas; total {len(finales)} nodos, {len(todas)} aristas")


if __name__ == "__main__":
    main(sys.argv[1])
