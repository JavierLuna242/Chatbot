"""Prueba rápida contra Supabase ya cargado con esquema.sql, plan_estudios.sql y estudiantes_sinteticos.sql.

Uso: DATABASE_URL=postgresql://... python probar_servidor_mcp.py   (solo lee; no modifica nada)
"""
import asyncio
import json
import os

os.environ.setdefault("DATABASE_URL", "postgresql://unab:unab@localhost:5432/unab")  # antes de importar el servidor

from fastmcp import Client  # noqa: E402

from servidor_mcp import mcp  # noqa: E402


async def main():
    async with Client(mcp) as c:
        call = lambda name, **kw: c.call_tool(name, kw, raise_on_error=False)

        e = (await call("consultar_estudiante", codigo="u00100005")).data  # minúsculas: se normaliza
        assert e["codigo"] == "U00100005" and e["semestre_actual"] == 5 and e["carrera"] == "Ingeniería de Sistemas", e

        nuevo = (await call("avance_y_proyeccion", codigo="U00100001")).data  # 1.er semestre: nada aprobado
        assert nuevo["creditos_plan"] == 134 and nuevo["creditos_aprobados"] == 0 and nuevo["semestres_restantes_estimados"] >= 8, nuevo

        a = (await call("avance_y_proyeccion", codigo="U00100005")).data  # 5.º: semestres 1 a 4 (67 créditos) menos las perdidas
        assert 50 <= a["creditos_aprobados"] <= 67 and a["creditos_pendientes"] == 134 - a["creditos_aprobados"], a

        r = (await call("cursos_recomendados", codigo="U00100005")).data
        assert 0 < r["creditos"] <= 17 and r["sugeridos"], r

        cd = (await call("competencias_digitales", codigo="U00100004")).data  # 4.º: CD01-CD03 hechos (o por repetir) y CD04 en curso: aún sin insignia
        assert [x["curso_cd"] for x in cd["cursos"]] == ["CD01", "CD02", "CD03", "CD04"] and not cd["insignia_obtenida"], cd

        plan = (await call("plan_de_estudios", semestre=1)).data
        assert sum(m["creditos"] for m in plan) == 16 and len(plan) == 6, plan

        (await call("calendario_academico", buscar="inscrip"))  # puede estar vacío, no debe fallar

        # promedio y estado (notas sintéticas de materias aprobadas, 3.0 a 5.0)
        pr = (await call("promedio_y_estado", codigo="U00100005")).data
        assert 3.0 <= pr["promedio_acumulado"] <= 5.0 and pr["creditos_con_nota"] > 40, pr
        assert pr["estado"] == "buen estado académico" and pr["puede_inscribir_hasta_creditos"] in (18, 21), pr
        assert (pr["puede_inscribir_hasta_creditos"] == 21) == (pr["promedio_acumulado"] >= 4.0), pr   # coherente con el reglamento
        det = (await call("promedio_y_estado", codigo="U00100005", con_detalle=True)).data["notas_por_materia"]
        assert len(det) == 24 and all(3.0 <= x["nota"] <= 5.0 for x in det) and det[0]["semestre"] == 1, det     # 22 con créditos + 2 laboratorios
        assert "notas_por_materia" not in pr                                                                       # sin pedirlo no se envían (gasta tokens)
        assert (await call("promedio_y_estado", codigo="U00100001")).data["promedio_acumulado"] is None   # 1.er semestre: sin notas
        pos = [int((await call("promedio_y_estado", codigo=f"U{100000 + n:08d}")).data.get("puesto_en_el_programa", "0 de 0").split()[0]) for n in range(2, 31)]
        con_nota = [x for x in pos if x]                            # los de 1.er semestre (U...09, 17, 25) no tienen puesto
        assert len(con_nota) == 26 and len(set(con_nota)) == 26 and min(con_nota) == 1, pos   # ranking real: 26 puestos distintos
        assert (await c.call_tool("promedio_y_estado", {"codigo": "U99999999"}, raise_on_error=False)).is_error

        # calculadora de notas (30 % + 30 % + 40 %, se aprueba con 3.0): casos con resultado conocido
        n = (await call("calcular_nota", primer_corte=3.2, segundo_corte=2.8)).data  # 1.80 acumulado: necesita exactamente 3.0 en el final
        assert n["puede_aprobar"] and n["nota_necesaria"] == 3.0 and n["puntos_acumulados"] == 1.8 and n["falta"] == ["examen final"], n
        n = (await call("calcular_nota", primer_corte=1.0, segundo_corte=1.0)).data  # 0.60 acumulado: ni con 5.0 llega
        assert n["puede_aprobar"] is False and n["maxima_nota_final_posible"] == 2.6, n
        n = (await call("calcular_nota", primer_corte=4.0, segundo_corte=4.0)).data  # 2.40 acumulado: le bastan 1.5
        assert n["puede_aprobar"] and n["nota_necesaria"] == 1.5, n
        n = (await call("calcular_nota", primer_corte=5.0, segundo_corte=5.0)).data  # 3.00 acumulado: ya aprobó
        assert n["ya_aprobo"] is True, n
        n = (await call("calcular_nota", primer_corte=4.0, examen_final=3.5)).data  # falta el segundo corte (30 %): necesita 1.33 -> 1.4
        assert n["falta"] == ["segundo corte"] and n["nota_necesaria"] == 1.4, n
        n = (await call("calcular_nota", primer_corte=3.0, segundo_corte=3.0, examen_final=3.0)).data  # justo en el límite: aprueba
        assert n["nota_definitiva"] == 3.0 and n["aprobada"] is True, n
        n = (await call("calcular_nota", primer_corte=2.0, segundo_corte=2.0, examen_final=4.0)).data  # 2.80: reprueba
        assert n["nota_definitiva"] == 2.8 and n["aprobada"] is False, n
        n = (await call("calcular_nota")).data  # sin ninguna nota: necesita 3.0 en todo
        assert n["nota_necesaria"] == 3.0 and len(n["falta"]) == 3, n

        # seguridad: inyección, códigos inexistentes o mal formados y rangos fuera de límite deben rechazarse
        for herramienta, args in [
            ("consultar_estudiante", {"codigo": "x' OR 1=1"}),
            ("consultar_estudiante", {"codigo": "U99999999"}),
            ("avance_y_proyeccion", {"codigo": "U00100005", "creditos_por_semestre": 0}),
            ("cursos_recomendados", {"codigo": "U00100005", "max_creditos": 999}),
            ("plan_de_estudios", {"semestre": 99}),
            ("calcular_nota", {"primer_corte": 5.5}),
            ("calcular_nota", {"segundo_corte": -1}),
            ("calcular_nota", {"examen_final": "abc"}),
        ]:
            assert (await c.call_tool(herramienta, args, raise_on_error=False)).is_error, f"debió rechazarse: {herramienta} {args}"

        print("promedio", json.dumps(pr, ensure_ascii=False))
        print("estudiante", json.dumps(e, ensure_ascii=False))
        print("avance", json.dumps(a, ensure_ascii=False)[:300])
        print("recomendados", json.dumps(r, ensure_ascii=False)[:300])
    print("OK")


asyncio.run(main())
