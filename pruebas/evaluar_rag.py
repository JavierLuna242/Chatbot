"""Evalúa la recuperación del RAG y genera docs/evaluacion-rag.md.

Método: 24 preguntas con su documento correcto conocido (3 por documento y 3 en inglés). Cada configuración de fragmentación
(tamaño y solapamiento en caracteres) se ingesta en una tabla de prueba con el mismo modelo de embeddings que producción
(gemini-embedding-001) y se mide la búsqueda por similitud (top 5, distancia coseno). También se mide la tabla real de
producción (n8n_vectors) como control.

Métricas (las estándar de recuperación de información):
  Hit@k        porcentaje de preguntas cuyo documento correcto aparece entre los k primeros fragmentos.
  MRR          promedio de 1 / posición del primer fragmento correcto (1 = siempre primero; 0 = nunca en el top 5).
  Precisión@5  porcentaje de los 5 fragmentos recuperados que vienen del documento correcto.

Usa el flujo «Evaluación RAG» de n8n (webhooks rag-eval-ingestar y rag-eval-buscar, con la misma clave básica que la web), así la
clave de Gemini nunca sale de n8n. Las tablas de prueba se crean con RLS y se borran al final; n8n_vectors no se modifica.
No gasta cupo de Groq (solo embeddings de Gemini).

Uso, desde la raíz del proyecto:   pip install "psycopg[binary]"   y   python pruebas/evaluar_rag.py
"""
import base64
import json
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

RAIZ = Path(__file__).resolve().parent.parent
E = {k: v.strip().strip('"') for k, v in (l.split("=", 1) for l in (RAIZ / ".env").read_text(encoding="utf8").splitlines()
                                          if re.match(r"^[A-Z][A-Z0-9_]*=", l))}
BASE = re.match(r"https://[^/]+", E["N8N_CHAT_URL"]).group(0)
AUTH = "Basic " + base64.b64encode(f"{E['N8N_CHAT_USER']}:{E['N8N_CHAT_PASSWORD']}".encode()).decode()
SALIDA = RAIZ / "docs" / "evaluacion-rag.md"
K = 5
CONFIGS = [(500, 75), (1000, 0), (1000, 150), (2000, 300)]   # (tamaño, solapamiento) en caracteres
PRODUCCION = (1000, 150)                                     # lo que usa el flujo «Ingesta de documentos»

# (pregunta, documentos que la responden). Redactadas con otras palabras que los documentos, como las haría un estudiante.
PREGUNTAS = [
    ("¿Con qué nota se aprueba una materia?", {"reglamento estudiantil resumen"}),
    ("¿Qué porcentaje de asistencia necesito para no perder una materia?", {"reglamento estudiantil resumen"}),
    ("¿Qué pasa si mi promedio acumulado queda por debajo de 3.0?", {"reglamento estudiantil resumen"}),
    ("¿Qué significa que mi matrícula esté pendiente de pago?", {"proceso inscripcion y matricula"}),
    ("¿Hasta qué semana puedo cancelar una materia?", {"proceso inscripcion y matricula"}),
    ("¿Cómo pido el aplazamiento del semestre?", {"proceso inscripcion y matricula"}),
    ("¿Cuántos créditos tiene la carrera y cuántos semestres dura?", {"plan de estudios ingenieria de sistemas"}),
    ("¿Qué son los cursos menor?", {"plan de estudios ingenieria de sistemas"}),
    ("¿A cuántas horas de trabajo equivale un crédito?", {"plan de estudios ingenieria de sistemas"}),
    ("¿Qué necesito para graduarme?", {"opciones de grado y practica profesional"}),
    ("¿Cuántos créditos debo tener aprobados para inscribir la práctica profesional?", {"opciones de grado y practica profesional"}),
    ("¿Puedo hacer la práctica en mi propio emprendimiento?", {"opciones de grado y practica profesional"}),
    ("¿Qué promedio piden para la beca de investigación?", {"bienestar becas y apoyos"}),
    ("¿La universidad ofrece atención psicológica gratuita?", {"bienestar becas y apoyos"}),
    ("¿Hay monitorías para materias de programación?", {"bienestar becas y apoyos"}),
    ("¿Cuántos créditos puedo homologar de otra universidad?", {"homologaciones reintegros y traslados"}),
    ("¿Puedo cambiarme a otro programa de la universidad?", {"homologaciones reintegros y traslados"}),
    ("¿Qué necesito para irme de intercambio?", {"homologaciones reintegros y traslados"}),
    ("¿Qué cursos componen la insignia de competencias digitales?", {"insignia competencias digitales"}),
    ("¿Qué pasa si repruebo un curso de la insignia?", {"insignia competencias digitales"}),
    ("¿La insignia es requisito para la práctica profesional?", {"insignia competencias digitales", "opciones de grado y practica profesional"}),
    ("What grade do I need to pass a course?", {"reglamento estudiantil resumen"}),
    ("How many credits can I transfer from another university?", {"homologaciones reintegros y traslados"}),
    ("Is there free psychological counseling?", {"bienestar becas y apoyos"}),
]


def post(ruta, cuerpo, intentos=3):
    req = urllib.request.Request(f"{BASE}/webhook/{ruta}", json.dumps(cuerpo, ensure_ascii=False).encode(),
                                 {"Content-Type": "application/json", "Authorization": AUTH})
    for i in range(intentos):
        try:
            return urllib.request.urlopen(req, timeout=180).read().decode()
        except Exception:   # límite de peticiones de Gemini u otro fallo pasajero: espera y repite
            if i == intentos - 1:
                raise
            time.sleep(20)


def tabla_de(c, o):
    return f"rag_eval_{c}_{o}"


def ingestar(con, chunk, overlap):
    tabla = tabla_de(chunk, overlap)
    con.execute(f"DROP TABLE IF EXISTS {tabla}")
    for doc in sorted((RAIZ / "documentos-rag").glob("*.md")):
        post("rag-eval-ingestar", {"tabla": tabla, "chunk": chunk, "overlap": overlap,
                                   "documento": doc.stem.replace("_", " "), "texto": doc.read_text(encoding="utf8")})
        time.sleep(1)
    con.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
    con.execute(f"REVOKE ALL ON {tabla} FROM anon, authenticated")
    return con.execute(f"SELECT count(*), round(avg(length(text))), max(length(text)) FROM {tabla}").fetchone()


def buscar(tabla, pregunta):
    r = json.loads(post("rag-eval-buscar", {"tabla": tabla, "pregunta": pregunta, "k": K}))
    return [(x["document"]["metadata"].get("documento", "?"), x.get("score"), x["document"]["pageContent"]) for x in r]


def fragmentos_por_documento(con, tabla):
    return dict(con.execute(f"SELECT metadata->>'documento', count(*) FROM {tabla} GROUP BY 1").fetchall())


def techo_precision(por_doc):
    """Precisión@5 máxima posible: el documento correcto no puede aportar más fragmentos de los que tiene."""
    return 100 * sum(min(sum(por_doc.get(d, 0) for d in esperados), K) / K for _, esperados in PREGUNTAS) / len(PREGUNTAS)


def medir(tabla):
    filas = []
    for pregunta, esperados in PREGUNTAS:
        res = buscar(tabla, pregunta)
        pos = next((i + 1 for i, (d, _, _) in enumerate(res) if d in esperados), None)
        filas.append({"pregunta": pregunta, "esperados": esperados, "pos": pos, "res": res,
                      "prec": sum(d in esperados for d, _, _ in res) / K})
        time.sleep(0.6)
    n = len(filas)
    m = {f"hit{k}": 100 * sum(1 for f in filas if f["pos"] and f["pos"] <= k) / n for k in (1, 3, 5)}
    m["mrr"] = sum(1 / f["pos"] for f in filas if f["pos"]) / n
    m["prec5"] = 100 * sum(f["prec"] for f in filas) / n
    return m, filas


def main():
    md = []
    linea = md.append
    with psycopg.connect(E["DATABASE_URL"], prepare_threshold=None, autocommit=True) as con:
        tam, techo = {}, {}
        resultados = {}
        for chunk, overlap in CONFIGS:
            print(f"ingestando {chunk}/{overlap}…")
            tam[(chunk, overlap)] = ingestar(con, chunk, overlap)
            techo[(chunk, overlap)] = techo_precision(fragmentos_por_documento(con, tabla_de(chunk, overlap)))
            print(f"  {tam[(chunk, overlap)][0]} fragmentos; midiendo…")
            resultados[(chunk, overlap)] = medir(tabla_de(chunk, overlap))
        print("midiendo la tabla de producción (n8n_vectors)…")
        tam["prod"] = con.execute("SELECT count(*), round(avg(length(text))), max(length(text)) FROM n8n_vectors").fetchone()
        resultados["prod"] = medir("n8n_vectors")
        techo["prod"] = techo_precision(fragmentos_por_documento(con, "n8n_vectors"))
        for chunk, overlap in CONFIGS:
            con.execute(f"DROP TABLE IF EXISTS {tabla_de(chunk, overlap)}")
        docs = {d.stem.replace("_", " "): len(d.read_text(encoding="utf8")) for d in sorted((RAIZ / "documentos-rag").glob("*.md"))}

    ahora = datetime.now(timezone(timedelta(hours=-5))).strftime("%Y-%m-%d %H:%M")
    linea("# Evaluación de la recuperación del RAG")
    linea("")
    linea(f"Generado el {ahora} (hora de Colombia) con `python pruebas/evaluar_rag.py`. Resultados medidos, no estimados.")
    linea("")
    linea("## Método")
    linea("")
    linea(f"- **Corpus:** los {len(docs)} documentos de `documentos-rag/` (de {min(docs.values())} a {max(docs.values())} caracteres cada uno).")
    linea(f"- **Preguntas:** {len(PREGUNTAS)}, con su documento correcto conocido: 3 por documento, redactadas con otras palabras, y 3 en inglés.")
    linea("- **Modelo de embeddings:** `gemini-embedding-001` (3072 dimensiones), el mismo de producción. Búsqueda por similitud coseno en pgvector, top 5.")
    linea("- **Configuraciones:** cada tamaño y solapamiento (en caracteres, con el divisor recursivo de n8n) se ingesta en una tabla de prueba; "
          "la última fila mide la tabla real de producción como control.")
    linea("- **Métricas:** Hit@k (el documento correcto aparece entre los k primeros fragmentos), MRR (promedio de 1 / posición del primer "
          "fragmento correcto) y Precisión@5 (porcentaje de los 5 fragmentos que vienen del documento correcto).")
    linea("")
    linea("## Resultados")
    linea("")
    linea("| Configuración | Fragmentos | Largo medio | Hit@1 | Hit@3 | Hit@5 | MRR | Precisión@5 | Precisión@5 máxima posible |")
    linea("|---|---|---|---|---|---|---|---|---|")
    for clave in CONFIGS + ["prod"]:
        m, _ = resultados[clave]
        n, medio, _ = tam[clave]
        nombre = "Producción (`n8n_vectors`, 1000 / 150)" if clave == "prod" else f"{clave[0]} / {clave[1]}" + (" ← producción" if clave == PRODUCCION else "")
        linea(f"| {nombre} | {n} | {int(medio)} | {m['hit1']:.0f} % | {m['hit3']:.0f} % | {m['hit5']:.0f} % | {m['mrr']:.2f} | {m['prec5']:.0f} % | {techo[clave]:.0f} % |")
    linea("")
    linea("La *precisión@5 máxima posible* es el techo de la precisión: si el documento correcto tiene menos de 5 fragmentos, el resto del top 5 "
          "viene obligatoriamente de otros documentos. Con fragmentos grandes hay menos fragmentos por documento y el techo baja.")
    linea("")
    _, filas = resultados["prod"]
    linea("## Detalle por pregunta (tabla de producción)")
    linea("")
    linea("Posición del primer fragmento del documento correcto, documentos que ocuparon el top 5 y distancia coseno del primer resultado "
          "(la puntuación que devuelve pgvector: menor = más parecido; una pregunta sin relación con los documentos queda cerca de 0.46).")
    linea("")
    linea("| # | Pregunta | Documento esperado | Posición | Top 5 (documento de cada fragmento) | Distancia del 1.º |")
    linea("|---|---|---|---|---|---|")
    abrev = {d: "".join(p[0] for p in d.split()[:3]).upper() for d in docs}
    for i, f in enumerate(filas, 1):
        top = " · ".join(abrev.get(d, "?") for d, _, _ in f["res"])
        sim = f"{f['res'][0][1]:.3f}" if f["res"] and f["res"][0][1] is not None else "—"
        linea(f"| {i} | {f['pregunta']} | {' o '.join(sorted(f['esperados']))} | {f['pos'] or 'no está'} | {top} | {sim} |")
    linea("")
    linea("Abreviaturas: " + " · ".join(f"`{a}` = {d}" for d, a in abrev.items()) + ".")
    linea("")
    fallos = [f for f in filas if f["pos"] != 1]
    if fallos:
        linea("## Preguntas donde el documento correcto no salió primero")
        linea("")
        for f in fallos:
            linea(f"- **{f['pregunta']}** (posición {f['pos'] or 'fuera del top 5'}): el primer fragmento vino de *{f['res'][0][0]}* "
                  f"y empieza «{re.sub(r'[#*]', '', f['res'][0][2]).strip()[:120]}…».")
        linea("")
    SALIDA.write_text("\n".join(md) + "\n", encoding="utf8")
    print("escrito", SALIDA.relative_to(RAIZ))
    for clave in CONFIGS + ["prod"]:
        m, _ = resultados[clave]
        print(clave, {k: round(v, 2) for k, v in m.items()}, "fragmentos:", tam[clave][0])


if __name__ == "__main__":
    main()
