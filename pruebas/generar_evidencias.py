"""Genera docs/evidencias.md con pruebas reales del sistema en producción.

Qué incluye (todo sale de llamadas reales en el momento de ejecutarlo, nada se escribe a mano):
  1. Servidor MCP: llamadas con curl (sin token, lista de herramientas y varias herramientas con datos de la base).
  2. Webhook de n8n: preguntas con curl y la respuesta del asistente (gasta cupo de Groq: 2 preguntas).
  3. Base de datos: versión del servidor, tablas con su número de filas y RLS, diagrama entidad-relación leído del catálogo y filas de ejemplo.
  4. Ejecuciones en n8n: nodos recorridos por una ejecución exitosa del chatbot, herramientas que llamó y ejecuciones automáticas de noticias.
  5. Recuperación del RAG: preguntas reales, la búsqueda que hizo el agente y los fragmentos que devolvió pgvector, con su documento.

Uso, desde la raíz del proyecto (lee el .env):
    pip install "psycopg[binary]"
    python pruebas/generar_evidencias.py
Requiere curl (incluido en Windows 10+, Linux y macOS). Nunca escribe claves: los comandos muestran $MCP_TOKEN, $N8N_CHAT_USER, etc.
"""
import json
import re
import subprocess
import sys
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

RAIZ = Path(__file__).resolve().parent.parent
ENV = dict(l.split("=", 1) for l in (RAIZ / ".env").read_text(encoding="utf8").splitlines() if re.match(r"^[A-Z][A-Z0-9_]*=", l))
ENV = {k: v.strip().strip('"') for k, v in ENV.items()}
SALIDA = RAIZ / "docs" / "evidencias.md"
FLUJO = json.loads((RAIZ / "flujos-n8n" / "flujos" / "chatbot_academico.json").read_text(encoding="utf8"))
MCP_URL = next(n["parameters"]["endpointUrl"] for n in FLUJO["nodes"] if n["name"] == "Servidor MCP UNAB")
N8N_BASE = re.match(r"https://[^/]+", ENV["N8N_CHAT_URL"]).group(0)
WF = {"chatbot": "kpRjKoGXyOIF39Zp", "ingesta": "K1LvWOoUvZmg2EXN", "noticias": "YWX5bEwEi67dhLDN"}
COLOMBIA = timezone(timedelta(hours=-5))
md = []


def linea(t=""):
    md.append(t)


def bloque(texto, lenguaje=""):
    md.append(f"```{lenguaje}\n{texto.rstrip()}\n```")


def corta(obj, lineas=28):
    t = json.dumps(obj, ensure_ascii=False, indent=2) if not isinstance(obj, str) else obj
    partes = t.splitlines()
    return "\n".join(partes[:lineas] + ([f"… ({len(partes) - lineas} líneas más)"] if len(partes) > lineas else []))


def hora(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(COLOMBIA).strftime("%Y-%m-%d %H:%M")


def curl(args, entrada=None):
    r = subprocess.run(["curl", "-s", "-A", "evidencias-chatbot", *args], input=entrada, capture_output=True)
    return r.stdout.decode("utf8", "replace")


# ---------------------------------------------------------------------------------------------------------------- 1. MCP
def mcp_jsonrpc(metodo, params, sesion=None, mostrar=None):
    cuerpo = json.dumps({"jsonrpc": "2.0", "id": 1, "method": metodo, "params": params}, ensure_ascii=False)
    cab = ["-H", f"Authorization: Bearer {ENV['MCP_TOKEN']}", "-H", "Content-Type: application/json",
           "-H", "Accept: application/json, text/event-stream"] + (["-H", f"mcp-session-id: {sesion}"] if sesion else [])
    salida = curl(["-i", "-X", "POST", MCP_URL, *cab, "--data-binary", "@-"], entrada=cuerpo.encode("utf8"))
    sid = re.search(r"(?im)^mcp-session-id:\s*(\S+)", salida)
    datos = re.search(r"(?m)^data: (\{.*\})", salida)
    if mostrar:
        bloque(f"curl -X POST {MCP_URL} \\\n  -H \"Authorization: Bearer $MCP_TOKEN\" \\\n  -H \"Content-Type: application/json\" -H \"Accept: application/json, text/event-stream\" \\"
               + ("\n  -H \"mcp-session-id: $SESION\" \\" if sesion else "") + f"\n  -d '{cuerpo}'", "bash")
    return (sid.group(1) if sid else None), (json.loads(datos.group(1)) if datos else {"respuesta_cruda": salida[-400:]})


def seccion_mcp():
    linea("## 1. Servidor MCP probado con curl")
    linea()
    linea(f"El servidor es público en `{MCP_URL}` a través del túnel de Cloudflare y exige un token Bearer.")
    linea()
    linea("**Sin token** (debe rechazar):")
    codigo = curl(["-o", "/dev/null" if sys.platform != "win32" else "NUL", "-w", "%{http_code}", "-X", "POST", MCP_URL])
    bloque(f"curl -s -o /dev/null -w \"%{{http_code}}\" -X POST {MCP_URL}\n{codigo}", "bash")
    linea()
    linea("**Inicio de sesión MCP y lista de herramientas:**")
    sid, r = mcp_jsonrpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "evidencias", "version": "1"}}, mostrar=True)
    info = r.get("result", {})
    bloque(corta({"serverInfo": info.get("serverInfo"), "protocolVersion": info.get("protocolVersion"),
                  "capabilities": sorted((info.get("capabilities") or {}).keys())}, 12), "json")
    linea("El servidor devuelve la cabecera `mcp-session-id`, que se envía en las llamadas siguientes como `$SESION`.")
    linea()
    mcp_jsonrpc("notifications/initialized", {}, sid)
    _, r = mcp_jsonrpc("tools/list", {}, sid, mostrar=True)
    herramientas = [(t["name"], re.split(r"\.(?:\s|$)", t.get("description", ""))[0]) for t in r.get("result", {}).get("tools", [])]
    linea()
    linea(f"Respuesta: **{len(herramientas)} herramientas**.")
    linea()
    linea("| Herramienta | Descripción (del propio servidor) |")
    linea("|---|---|")
    for n, d in herramientas:
        linea(f"| `{n}` | {d}. |")
    linea()
    for titulo, nombre, args in [
        ("Consulta a la base: datos del estudiante U00100005", "consultar_estudiante", {"codigo": "U00100005"}),
        ("Promedio y situación académica según el reglamento", "promedio_y_estado", {"codigo": "U00100005"}),
        ("Calculadora de notas (3.2 y 2.8 en los dos primeros cortes)", "calcular_nota", {"primer_corte": 3.2, "segundo_corte": 2.8}),
        ("Calendario: búsqueda de «inscripción»", "calendario_academico", {"buscar": "inscripción"}),
    ]:
        linea(f"**{titulo}:**")
        _, r = mcp_jsonrpc("tools/call", {"name": nombre, "arguments": args}, sid, mostrar=True)
        res = r.get("result", {})
        bloque(corta(res.get("structuredContent") or res.get("content") or r, 22), "json")
        linea()


# ------------------------------------------------------------------------------------------------------------ 2. Webhook
def seccion_webhook():
    linea("## 2. Webhook de n8n probado con curl")
    linea()
    linea("Es el mismo webhook que usa la web. Exige usuario y clave (Basic Auth). Las preguntas pasan por los guardrails, el clasificador y el agente.")
    linea()
    linea("**Sin credenciales** (debe rechazar):")
    codigo = curl(["-o", "NUL" if sys.platform == "win32" else "/dev/null", "-w", "%{http_code}", "-X", "POST", ENV["N8N_CHAT_URL"],
                   "-H", "Content-Type: application/json", "-d", "{}"])
    bloque(f"curl -s -o /dev/null -w \"%{{http_code}}\" -X POST \"$N8N_CHAT_URL\" -H \"Content-Type: application/json\" -d '{{}}'\n{codigo}", "bash")
    linea()
    sesion = "chat-" + str(uuid.uuid4())
    for pregunta in ["U00100005", "¿Cuál es mi promedio y cuántos créditos puedo inscribir?"]:
        cuerpo = json.dumps({"action": "sendMessage", "sessionId": sesion, "chatInput": pregunta, "metadata": {"codigo": "U00100005"}}, ensure_ascii=False)
        salida = curl(["-X", "POST", ENV["N8N_CHAT_URL"], "-u", f"{ENV['N8N_CHAT_USER']}:{ENV['N8N_CHAT_PASSWORD']}",
                       "-H", "Content-Type: application/json; charset=utf-8", "--data-binary", "@-"], entrada=cuerpo.encode("utf8"))
        if re.search(r"límite temporal|no está disponible", salida):
            print("AVISO: el asistente respondió «límite temporal» (cupo de Groq agotado); se anota y se sigue.")
            linea("> No se pudo completar esta prueba al generar el documento: el plan gratuito de Groq había agotado su cupo. "
                  "Vuelve a ejecutar el script más tarde.")
            linea()
            return
        bloque(f"curl -X POST \"$N8N_CHAT_URL\" -u \"$N8N_CHAT_USER:$N8N_CHAT_PASSWORD\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{cuerpo.replace(sesion, 'chat-<id-de-la-conversación>')}'", "bash")
        try:
            bloque(corta(json.loads(salida), 30), "json")
        except ValueError:
            bloque(salida[:1500])
        linea()


# ------------------------------------------------------------------------------------------------------- 3. Base de datos
def tabla_md(cols, filas):
    linea("| " + " | ".join(cols) + " |")
    linea("|" + "---|" * len(cols))
    for f in filas:
        linea("| " + " | ".join(str(x).replace("|", "/").replace("\n", " ")[:80] for x in f) + " |")


def seccion_base():
    linea("## 3. Base de datos PostgreSQL (Supabase)")
    linea()
    with psycopg.connect(ENV["DATABASE_URL"], prepare_threshold=None) as c:
        version = c.execute("SELECT split_part(version(), ' on ', 1)").fetchone()[0]
        pgvector = c.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()[0]
        linea(f"Conexión directa al servidor de Supabase (*Session pooler*): **{version}**, extensión `vector` {pgvector}.")
        linea()
        tablas = [r[0] for r in c.execute("""SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                                             WHERE n.nspname = 'public' AND c.relkind = 'r' ORDER BY relname""")]
        linea("**Tablas, filas y seguridad a nivel de fila (RLS):**")
        linea()
        filas = []
        for t in tablas:
            n = c.execute(f'SELECT count(*) FROM public."{t}"').fetchone()[0]
            rls = c.execute("SELECT relrowsecurity FROM pg_class WHERE relname = %s AND relnamespace = 'public'::regnamespace", (t,)).fetchone()[0]
            filas.append((f"`{t}`", n, "sí" if rls else "no"))
        tabla_md(["Tabla", "Filas", "RLS"], filas)
        linea()
        vistas = [r[0] for r in c.execute("SELECT viewname FROM pg_views WHERE schemaname = 'public' ORDER BY 1")]
        linea("Vistas: " + ", ".join(f"`{v}`" for v in vistas) + ".")
        linea()
        # diagrama entidad-relación leído del catálogo (columnas, claves primarias y foráneas reales)
        linea("**Modelo entidad-relación** (generado a partir del catálogo de la base, no dibujado a mano):")
        linea()
        cols = c.execute("""SELECT table_name, column_name, udt_name FROM information_schema.columns
                            WHERE table_schema = 'public' AND table_name = ANY(%s) ORDER BY table_name, ordinal_position""", (tablas,)).fetchall()
        pk = {(r[0], r[1]) for r in c.execute("""SELECT tc.table_name, kcu.column_name FROM information_schema.table_constraints tc
                 JOIN information_schema.key_column_usage kcu USING (constraint_schema, constraint_name)
                 WHERE tc.table_schema = 'public' AND tc.constraint_type = 'PRIMARY KEY'""")}
        fks = c.execute("""SELECT cl.relname, a.attname, cr.relname FROM pg_constraint co
                 JOIN pg_class cl ON cl.oid = co.conrelid JOIN pg_class cr ON cr.oid = co.confrelid
                 JOIN pg_attribute a ON a.attrelid = co.conrelid AND a.attnum = co.conkey[1]
                 WHERE co.contype = 'f' AND cl.relnamespace = 'public'::regnamespace ORDER BY 1, 2""").fetchall()
        fkset = {(t, col) for t, col, _ in fks}
        er = ["erDiagram"]
        for t in tablas:
            if t.startswith("n8n_"):
                continue
            er.append(f"    {t} {{")
            for tt, col, tipo in cols:
                if tt == t:
                    claves = [k for k, si in (("PK", (t, col) in pk), ("FK", (t, col) in fkset)) if si]
                    marca = (" " + ", ".join(claves)) if claves else ""
                    er.append(f"        {tipo} {col}{marca}")
            er.append("    }")
        for t, col, ref in fks:
            er.append(f'    {ref} ||--o{{ {t} : "{col}"')
        bloque("\n".join(er), "mermaid")
        linea()
        linea("Las tablas `n8n_chat_histories` (memoria del chat) y `n8n_vectors` (vectores del RAG) las usa n8n y no se relacionan con las académicas.")
        linea()
        linea("**Filas de ejemplo** (datos sintéticos):")
        linea()
        for titulo, sql, columnas in [
            ("Estudiantes", "SELECT codigo, nombre, semestre_actual, periodo_actual, estado_matricula FROM estudiante ORDER BY codigo LIMIT 4",
             ["Código", "Nombre", "Semestre", "Periodo", "Matrícula"]),
            ("Avance (vista `v_avance`)", "SELECT codigo, creditos_aprobados, creditos_pendientes, porcentaje_avance FROM v_avance WHERE codigo IN ('U00100005','U00100018') ORDER BY 1",
             ["Código", "Créditos aprobados", "Pendientes", "% avance"]),
            ("Materias aprobadas con nota", """SELECT a.codigo_estudiante, c.nombre, c.creditos, a.nota FROM materia_aprobada a JOIN curso c ON c.id = a.curso
                                               WHERE a.codigo_estudiante = 'U00100005' ORDER BY c.semestre, c.id LIMIT 4""",
             ["Código", "Materia", "Créditos", "Nota"]),
            ("Cursos de la insignia (vista `v_cd_estado`)", "SELECT codigo_estudiante, curso_cd, nombre, estado, nota FROM v_cd_estado WHERE codigo_estudiante = 'U00100005' ORDER BY 2",
             ["Código", "Curso", "Nombre", "Estado", "Nota"]),
            ("Calendario", "SELECT evento, fecha_inicio, fecha_fin, categoria FROM calendario ORDER BY fecha_inicio LIMIT 4",
             ["Evento", "Inicio", "Fin", "Categoría"]),
            ("Noticias (las escribe el scraper)", "SELECT fecha::date, titulo, url FROM noticia ORDER BY fecha DESC LIMIT 4", ["Fecha", "Título", "Fuente"]),
            ("Fragmentos del RAG por documento", "SELECT metadata->>'documento', count(*), max(vector_dims(embedding)) FROM n8n_vectors GROUP BY 1 ORDER BY 1",
             ["Documento", "Fragmentos", "Dimensiones"]),
        ]:
            linea(f"*{titulo}:*")
            linea()
            tabla_md(columnas, [tuple("" if v is None else v for v in f) for f in c.execute(sql).fetchall()])
            linea()


# ------------------------------------------------------------------------------------------------- 4 y 5. n8n (vía MCP)
def n8n(herramienta, args):
    cuerpo = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": herramienta, "arguments": args}}).encode()
    req = urllib.request.Request(N8N_BASE + "/mcp-server/http", cuerpo, {"Authorization": "Bearer " + ENV["N8N_CLOUD_API_KEY"],
                                 "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    texto = urllib.request.urlopen(req, timeout=120).read().decode()
    return json.loads(json.loads(re.search(r"data: (\{.*\})", texto).group(1))["result"]["content"][0]["text"])


def ejecuciones(wid, n):
    return n8n("search_workflow_executions", {"workflowId": wid, "limit": n})["data"]


def detalle(wid, eid):
    return n8n("get_workflow_execution", {"workflowId": wid, "executionId": str(eid), "includeData": True})["data"]["resultData"]["runData"]


def salida_de(rd, nodo):
    try:
        return rd[nodo][0]["data"]["main"][0][0]["json"]
    except (KeyError, IndexError, TypeError):
        return {}


def seccion_n8n(recientes):
    linea("## 4. Ejecuciones en n8n Cloud")
    linea()
    linea("Datos leídos del registro de ejecuciones de n8n Cloud.")
    linea()
    for clave, nombre in (("chatbot", "Chatbot UNAB"), ("noticias", "Noticias UNAB"), ("ingesta", "Ingesta de documentos")):
        ex = ejecuciones(WF[clave], 6)
        linea(f"**{nombre}**, últimas ejecuciones:")
        linea()
        tabla_md(["Ejecución", "Inicio (hora Colombia)", "Modo", "Estado"],
                 [(e["id"], hora(e["startedAt"]), {"webhook": "webhook", "trigger": "automático (cada 6 h)", "manual": "manual"}.get(e["mode"], e["mode"]),
                   "✔ éxito" if e["status"] == "success" else e["status"]) for e in ex])
        linea()
    # una ejecución completa del chatbot que pasó por el agente académico y llamó al MCP
    for eid, rd in recientes:
        if "Servidor MCP UNAB" in rd and salida_de(rd, "Respuesta").get("output") and "límite" not in salida_de(rd, "Respuesta")["output"]:
            break
    else:
        return
    pregunta = salida_de(rd, "Chat").get("chatInput")
    linea(f"**Recorrido de una ejecución exitosa del chatbot** (ejecución {eid}): pregunta *«{pregunta}»*.")
    linea()
    pasos = sorted(((r.get("startTime", 0), nodo, r.get("executionStatus"), r.get("executionTime", 0))
                    for nodo, runs in rd.items() for r in runs), key=lambda x: x[0])
    tabla_md(["#", "Nodo", "Estado", "Tiempo (ms)"], [(i + 1, n, "✔" if s == "success" else s, ms) for i, (_, n, s, ms) in enumerate(pasos)])
    linea()
    linea("Herramientas del MCP que llamó el agente:")
    linea()
    for r in rd["Servidor MCP UNAB"]:
        j = (r.get("inputOverride") or {}).get("ai_tool", [[{}]])[0][0].get("json", {})
        linea(f"- `{j.get('tool', {}).get('name', '?').replace('Servidor_MCP_UNAB_', '')}` con `{json.dumps(j.get('query'), ensure_ascii=False)}`")
    linea()
    linea("Respuesta final que recibió el estudiante:")
    linea()
    linea("> " + salida_de(rd, "Respuesta")["output"].replace("\n", "\n> "))
    linea()


PREGUNTAS_RAG = ["¿Cuál es la nota mínima para aprobar una materia y qué pasa si falto a clases?",
                 "¿Cuántos créditos puedo homologar de otra universidad?",
                 "¿Qué requisitos necesito para inscribir la práctica profesional?"]


def hacer_preguntas_rag():
    """Hace las preguntas institucionales fijas por el webhook; su recuperación se lee después del registro de n8n."""
    for pregunta in PREGUNTAS_RAG:
        cuerpo = json.dumps({"action": "sendMessage", "sessionId": "chat-" + str(uuid.uuid4()), "chatInput": pregunta,
                             "metadata": {"codigo": "U00100005"}}, ensure_ascii=False)
        salida = curl(["-X", "POST", ENV["N8N_CHAT_URL"], "-u", f"{ENV['N8N_CHAT_USER']}:{ENV['N8N_CHAT_PASSWORD']}",
                       "-H", "Content-Type: application/json; charset=utf-8", "--data-binary", "@-"], entrada=cuerpo.encode("utf8"))
        if re.search(r"límite temporal|no está disponible", salida):
            print("AVISO: cupo de Groq agotado en las preguntas del RAG.")


def seccion_rag(recientes):
    linea("## 5. Recuperación del RAG")
    linea()
    linea("Preguntas reales que el clasificador envió al agente institucional. Se ve la búsqueda que formuló el agente y los fragmentos que devolvió pgvector "
          "(los 5 más parecidos, `topK = 5`), cada uno con el documento del que sale.")
    linea()
    vistas = set()
    for eid, rd in recientes:
        runs = rd.get("Documentos institucionales") or []
        if not runs or runs[0].get("error") or not salida_de(rd, "Respuesta").get("output"):
            continue
        pregunta = salida_de(rd, "Chat").get("chatInput")
        if pregunta in vistas or pregunta not in PREGUNTAS_RAG:
            continue
        vistas.add(pregunta)
        consulta = (runs[0].get("inputOverride") or {}).get("ai_tool", [[{}]])[0][0].get("json", {}).get("query", {})
        frag = []
        for item in runs[0]["data"]["ai_tool"][0][0]["json"]["response"]:
            d = json.loads(item["text"])
            texto = re.sub(r"[#*]", "", d["pageContent"]).strip().replace("\n", " ")
            frag.append((d["metadata"].get("documento", "?"), texto[:110] + "…"))
        linea(f"### Pregunta: «{pregunta}» (ejecución {eid})")
        linea()
        linea(f"Búsqueda del agente: `{json.dumps(consulta, ensure_ascii=False)}`")
        linea()
        tabla_md(["#", "Documento", "Inicio del fragmento"], [(i + 1, d, t) for i, (d, t) in enumerate(frag)])
        linea()
        linea("Respuesta:")
        linea()
        linea("> " + salida_de(rd, "Respuesta")["output"].replace("\n", "\n> "))
        linea()
        if len(vistas) == len(PREGUNTAS_RAG):
            break
    if len(vistas) < len(PREGUNTAS_RAG):
        linea(f"> Solo se encontraron {len(vistas)} de {len(PREGUNTAS_RAG)} preguntas en el registro (¿cupo de Groq agotado?). Vuelve a ejecutar el script.")
        linea()


def main():
    ahora = datetime.now(COLOMBIA).strftime("%Y-%m-%d %H:%M")
    linea("# Evidencias del funcionamiento")
    linea()
    linea(f"Generado el {ahora} (hora de Colombia) con `python pruebas/generar_evidencias.py`. Todo lo que aparece aquí es la salida real de llamadas al sistema "
          "en producción; los datos de estudiantes son sintéticos y las claves se muestran como variables (`$MCP_TOKEN`, `$N8N_CHAT_USER`, …).")
    linea()
    linea("[1. Servidor MCP](#1-servidor-mcp-probado-con-curl) · [2. Webhook de n8n](#2-webhook-de-n8n-probado-con-curl) · "
          "[3. Base de datos](#3-base-de-datos-postgresql-supabase) · [4. Ejecuciones en n8n](#4-ejecuciones-en-n8n-cloud) · [5. Recuperación del RAG](#5-recuperación-del-rag)")
    linea()
    print("1/5 servidor MCP…"); seccion_mcp()
    print("2/5 webhook…"); seccion_webhook()
    print("3/5 base de datos…"); seccion_base()
    print("   preguntas del RAG…"); hacer_preguntas_rag()
    print("4/5 ejecuciones de n8n…")
    recientes = [(e["id"], detalle(WF["chatbot"], e["id"])) for e in ejecuciones(WF["chatbot"], 60) if e["status"] == "success"]
    seccion_n8n(recientes)
    print("5/5 RAG…"); seccion_rag(recientes)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text("\n".join(md) + "\n", encoding="utf8")
    print("escrito", SALIDA.relative_to(RAIZ))


if __name__ == "__main__":
    main()
