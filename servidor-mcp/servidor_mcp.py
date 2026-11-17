"""Servidor MCP (FastMCP) con herramientas académicas sobre Supabase (PostgreSQL) para Ingeniería de Sistemas.

Lo consume el agente de n8n Cloud (Groq) por HTTP streamable. Como n8n Cloud lo llama por internet, TODAS las
peticiones exigen `Authorization: Bearer <MCP_TOKEN>` (el mismo valor va en la credencial "Header Auth" de n8n).
El estudiante se identifica con su código (U + 8 dígitos); los datos son sintéticos (ver base-de-datos/).
"""
import csv
import hmac
import io
import math
import os
import re
import unicodedata
import urllib.request
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

import uvicorn
from fastmcp import FastMCP
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DB = os.environ["DATABASE_URL"]  # cadena del Session pooler de Supabase (IPv4)
MCP_TOKEN = os.environ.get("MCP_TOKEN", "")
CALENDARIO_CSV_URL = os.environ.get("CALENDARIO_CSV_URL")  # Google Sheet publicado como CSV
CARRERA = "Ingeniería de Sistemas"
CODIGO = re.compile(r"^U\d{8}$")

mcp = FastMCP("Asistente académico")


# Pool de conexiones a Supabase: abrir una conexión nueva (TLS + autenticación) en cada consulta costaba ~1 s y cada herramienta
# hace 2 o 3 consultas; con el pool se reutilizan. Solo se hacen lecturas, por eso autocommit. check= descarta conexiones que el
# pooler de Supabase cerró por inactividad. prepare_threshold=None: compatible con el pooler en modo transacción.
pool = ConnectionPool(DB, min_size=1, max_size=4, open=False, check=ConnectionPool.check_connection,
                      kwargs={"row_factory": dict_row, "prepare_threshold": None, "autocommit": True})


def q(sql, *params):
    pool.open()  # no hace nada si ya está abierto
    with pool.connection(timeout=15) as conn:
        return conn.execute(sql, params).fetchall()


def validar(codigo: str) -> str:
    codigo = str(codigo).strip().upper()
    if not CODIGO.match(codigo):
        raise ValueError("Código estudiantil inválido. Formato esperado: U seguido de 8 dígitos (ej. U00100001).")
    if not q("SELECT 1 FROM estudiante WHERE codigo = %s", codigo):
        raise ValueError(f"No encontré el código {codigo}. Pídele al estudiante que lo revise y lo escriba de nuevo.")
    return codigo


def sin_tildes(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def entre(valor: int, minimo: int, maximo: int, nombre: str) -> int:
    if not isinstance(valor, int) or not minimo <= valor <= maximo:
        raise ValueError(f"{nombre} debe ser un entero entre {minimo} y {maximo}.")
    return valor


def avance(codigo: str) -> dict:
    return q("SELECT * FROM v_avance WHERE codigo = %s", codigo)[0]


@mcp.tool
def consultar_estudiante(codigo: str) -> dict:
    """Identifica al estudiante por su código: nombre, carrera, semestre y estado de matrícula. Llámala primero."""
    codigo = validar(codigo)
    a = avance(codigo)
    return {k: a[k] for k in ("codigo", "nombre", "carrera", "semestre_actual", "periodo_actual", "estado_matricula")} | {
        "aviso": "Datos de demostración (base sintética), no del sistema académico oficial."}


@mcp.tool
def avance_y_proyeccion(codigo: str, creditos_por_semestre: int | None = None) -> dict:
    """Créditos aprobados y pendientes, porcentaje de avance y semestres restantes estimados (por defecto con la carga típica de la carrera)."""
    codigo = validar(codigo)
    av = avance(codigo)
    por_semestre = entre(av["creditos_por_semestre_plan"] if creditos_por_semestre is None else creditos_por_semestre, 1, 40, "creditos_por_semestre")
    av["creditos_por_semestre_supuestos"] = por_semestre
    # Limitación: proyección solo por créditos; el plan oficial no trae prerrequisitos para calcular la cadena más larga
    av["semestres_restantes_estimados"] = math.ceil(av["creditos_pendientes"] / por_semestre)
    av["aviso"] = "Datos de demostración (base sintética)."
    return av


@mcp.tool
def cursos_recomendados(codigo: str, max_creditos: int | None = None) -> dict:
    """Materias pendientes sugeridas para el próximo periodo (semestres bajos primero, sin pasar de max_creditos; por defecto la carga típica). El plan no trae prerrequisitos: que el estudiante los confirme."""
    codigo = validar(codigo)
    max_creditos = entre(avance(codigo)["creditos_por_semestre_plan"] if max_creditos is None else max_creditos, 1, 40, "max_creditos")
    candidatos = q("""SELECT nombre, creditos, semestre, tipo FROM v_pendientes
                      WHERE codigo_estudiante = %s ORDER BY semestre, curso""", codigo)
    elegidos, total = [], 0
    for c in candidatos:
        if total + c["creditos"] <= max_creditos:
            elegidos.append(c)
            total += c["creditos"]
    return {"sugeridos": elegidos, "creditos": total, "otras_pendientes": len(candidatos) - len(elegidos),
            "aviso": "Sin prerrequisitos en el plan: confirmar con el programa antes de inscribir."}


@mcp.tool
def competencias_digitales(codigo: str) -> dict:
    """Estado de los cursos CD01 a CD04 de la insignia (aprobado con nota, en curso, reprobado, pendiente) y si ya la obtuvo."""
    codigo = validar(codigo)
    cursos = q("""SELECT curso_cd, nombre, semestre_recomendado, estado, nota::float AS nota
                  FROM v_cd_estado WHERE codigo_estudiante = %s ORDER BY curso_cd""", codigo)
    return {"cursos": cursos, "insignia_obtenida": all(c["estado"] == "aprobado" for c in cursos),
            "regla": "La insignia se obtiene al aprobar los 4 cursos con nota mínima de 3.0.",
            "aviso": "Datos de demostración (base sintética)."}


@mcp.tool
def plan_de_estudios(semestre: int | None = None) -> list[dict]:
    """Materias y créditos del plan, opcionalmente de un semestre (1 a 8). Información pública."""
    if semestre is not None:
        entre(semestre, 1, 8, "semestre")
    return q("""SELECT semestre, nombre, creditos, tipo FROM curso
                WHERE carrera = %s AND (%s::int IS NULL OR semestre = %s) ORDER BY semestre, id""",
             CARRERA, semestre, semestre)


@mcp.tool
def calendario_academico(buscar: str | None = None) -> list[dict]:
    """Fechas del calendario académico (inscripciones, cortes, exámenes, festivos, grados). 'buscar' filtra por texto."""
    if CALENDARIO_CSV_URL:
        with urllib.request.urlopen(CALENDARIO_CSV_URL, timeout=10) as r:
            filas = list(csv.DictReader(io.StringIO(r.read().decode("utf-8"))))
    else:
        filas = q("""SELECT evento, fecha_inicio::text, fecha_fin::text, categoria
                     FROM calendario ORDER BY fecha_inicio""")
    if buscar:
        # búsqueda tolerante: sin tildes y por raíz de 5 letras de cada palabra ("cancelación" encuentra "cancelar"); basta una coincidencia
        raices = [sin_tildes(w)[:5] for w in str(buscar)[:100].split() if len(w) >= 4]
        if raices:
            filas = [f for f in filas if any(r in sin_tildes(f["evento"] + " " + f["categoria"]) for r in raices)]
    return filas


@mcp.tool
def noticias_recientes(limite: int = 4) -> list[dict]:
    """Últimas noticias y convocatorias de la universidad."""
    # resumen recortado: la salida entra completa al contexto del modelo y gasta tokens (Groq gratis: 8000 por minuto)
    return q("SELECT titulo, url, left(resumen, 180) AS resumen, fecha::text FROM noticia ORDER BY fecha DESC LIMIT %s",
             min(max(limite, 1), 10))


PRUEBA_ACADEMICA = Decimal("3.0")      # reglamento: promedio acumulado inferior a 3.0 = prueba académica
CARGA_MAX, CARGA_MAX_ALTO, PROMEDIO_ALTO = 18, 21, Decimal("4.0")   # 15-18 créditos; hasta 21 con promedio de 4.0 o más
BECA_INVESTIGACION = Decimal("3.8")    # promedio mínimo de la beca de investigación
BECA_EXCELENCIA = 0.05                 # el 5 % de mejor promedio del programa


@mcp.tool
def promedio_y_estado(codigo: str, con_detalle: bool = False) -> dict:
    """Promedio acumulado (ponderado por créditos) y situación según el reglamento: prueba académica, carga máxima de créditos y becas. Con con_detalle=true lista la nota de cada materia aprobada."""
    codigo = validar(codigo)
    todos = {f["c"]: f["p"] for f in q("""SELECT codigo_estudiante AS c, sum(nota * creditos) / sum(creditos) AS p, sum(creditos)::int AS cr
                                          FROM v_aprobados WHERE creditos > 0 GROUP BY 1""")}
    if codigo not in todos:
        return {"promedio_acumulado": None, "mensaje": "Aún no tiene materias aprobadas con nota (por ejemplo, está en primer semestre)."}
    p = Decimal(todos[codigo])
    ref = q("SELECT count(*)::int AS n, sum(creditos)::int AS cr FROM v_aprobados WHERE codigo_estudiante = %s AND creditos > 0", codigo)[0]
    puesto = 1 + sum(1 for v in todos.values() if Decimal(v) > p)   # 1 = mejor promedio del programa
    detalle = {"notas_por_materia": q("""SELECT semestre, nombre, creditos, nota::float AS nota FROM v_aprobados
                                         WHERE codigo_estudiante = %s ORDER BY semestre, curso""", codigo)} if con_detalle is True else {}
    return detalle | {"promedio_acumulado": float(p.quantize(Decimal("0.01"), ROUND_HALF_UP)), "materias_con_nota": ref["n"], "creditos_con_nota": ref["cr"],
            "estado": "prueba académica" if p < PRUEBA_ACADEMICA else "buen estado académico",
            "puede_inscribir_hasta_creditos": CARGA_MAX_ALTO if p >= PROMEDIO_ALTO else CARGA_MAX,
            "cumple_promedio_beca_investigacion": p >= BECA_INVESTIGACION,
            "puesto_en_el_programa": f"{puesto} de {len(todos)}",
            "dentro_del_5_por_ciento_mejor_promedio": puesto <= max(1, math.ceil(BECA_EXCELENCIA * len(todos))),
            "aviso": "Solo cuenta materias aprobadas (la base no guarda reprobadas). Datos de demostración."}


PESOS = {"primer corte": Decimal("0.30"), "segundo corte": Decimal("0.30"), "examen final": Decimal("0.40")}  # reglamento: 30 + 30 + 40 %
NOTA_MINIMA = Decimal("3.0")


def como_nota(valor, nombre: str) -> Decimal | None:
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not 0 <= valor <= 5:
        raise ValueError(f"{nombre} debe ser un número entre 0.0 y 5.0.")
    return Decimal(str(valor))  # Decimal(str(...)): 1.2 / 0.4 da 3.0 exacto, no 2.9999999999999996


def calcular_nota_de(primer_corte, segundo_corte, examen_final) -> dict:
    notas = dict(zip(PESOS, (como_nota(primer_corte, "primer_corte"), como_nota(segundo_corte, "segundo_corte"),
                             como_nota(examen_final, "examen_final"))))
    acumulado = sum((PESOS[k] * v for k, v in notas.items() if v is not None), Decimal(0))
    pendiente = sum((p for k, p in PESOS.items() if notas[k] is None), Decimal(0))
    base = {"pesos": "primer corte 30 %, segundo corte 30 %, examen final 40 %", "nota_minima_para_aprobar": 3.0,
            "puntos_acumulados": float(acumulado.quantize(Decimal("0.01")))}
    if not pendiente:  # las tres notas: nota definitiva
        return base | {"nota_definitiva": float(acumulado.quantize(Decimal("0.01"))), "aprobada": acumulado >= NOTA_MINIMA}
    faltan = [k for k in PESOS if notas[k] is None]
    necesaria = (NOTA_MINIMA - acumulado) / pendiente  # promedio que debe sacar en lo que falta
    base |= {"falta": faltan, "peso_de_lo_que_falta": f"{int(pendiente * 100)} %"}
    if necesaria <= 0:
        return base | {"ya_aprobo": True, "mensaje": "Ya tiene la nota para aprobar, aunque saque 0.0 en lo que falta."}
    if necesaria > 5:
        return base | {"puede_aprobar": False, "maxima_nota_final_posible": float((acumulado + pendiente * 5).quantize(Decimal("0.01"))),
                       "mensaje": "Aunque saque 5.0 en lo que falta no llega a 3.0."}
    return base | {"puede_aprobar": True, "nota_necesaria": float((necesaria * 10).to_integral_value(ROUND_CEILING) / 10),
                   "mensaje": "Es la nota mínima (con un decimal) que necesita en " + (" y en ".join(faltan)) + " para llegar a 3.0."}


@mcp.tool
def calcular_nota(primer_corte: float | None = None, segundo_corte: float | None = None, examen_final: float | None = None) -> dict:
    """Nota de UNA materia (0.0 a 5.0, se aprueba con 3.0; cortes 30 %, 30 % y examen final 40 %). Pasa solo las notas que el estudiante ya tiene: devuelve la definitiva o la que necesita en lo que falta. Si faltan datos, pídelos."""
    return calcular_nota_de(primer_corte, segundo_corte, examen_final)


class ExigirToken:
    """Middleware ASGI: sin el token Bearer correcto responde 401 (el servidor es público a través del túnel)."""

    def __init__(self, app, token: str):
        self.app, self.token = app, token.encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            enviado = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(enviado, b"Bearer " + self.token):
                await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"text/plain")]})
                await send({"type": "http.response.body", "body": "No autorizado".encode()})
                return
        await self.app(scope, receive, send)


if __name__ == "__main__":
    if len(MCP_TOKEN) < 32:
        raise SystemExit("Define MCP_TOKEN (mínimo 32 caracteres): el servidor es público y no arranca sin token.")
    # Detrás del túnel el Host es el dominio público: se acepta cualquier Host porque el control de acceso es el token.
    app = mcp.http_app(path="/mcp", host_origin_protection=False)
    uvicorn.run(ExigirToken(app, MCP_TOKEN), host=os.environ.get("MCP_HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 9000)))
