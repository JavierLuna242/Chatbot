"""Convierte base-de-datos/planes_pregrados.csv en base-de-datos/plan_estudios.sql (carreras + materias).

Uso: python base-de-datos/generar_plan_estudios.py
El id de cada materia es su posición en el CSV: los estudiantes guardan esos ids como "aprobadas",
así que al actualizar el plan agrega filas AL FINAL del CSV y no reordenes las existentes.
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

AQUI = Path(__file__).parent
ORDINALES = ["primer", "segundo", "tercer", "cuarto", "quinto", "sexto", "septimo", "octavo", "noveno",
             "decimo", "undecimo", "duodecimo"]


def sql(texto):
    return "'" + texto.replace("'", "''") + "'"


def tipo(nombre):
    return "electivo" if re.match(r"(ELECTIVA|CURSOS? (CICLO )?MENOR|MENOR|CURSOS MENORES)", nombre.upper()) else "obligatorio"


filas = list(csv.DictReader(open(AQUI / "planes_pregrados.csv", encoding="utf-8-sig")))
carreras, por_semestre, total = {}, defaultdict(int), defaultdict(int)
materias = []
for i, f in enumerate(filas, start=1):
    sem = ORDINALES.index(f["semestre"].split()[0].lower()) + 1
    cred = int(f["creditos_materia"])
    carreras[f["carrera"]] = (int(f["duracion"].split()[0]), int(f["creditos_totales"]))
    por_semestre[(f["carrera"], sem, int(f["creditos_semestre"]))] += cred
    total[f["carrera"]] += cred
    materias.append((i, f["carrera"], sem, f["materia"].strip(), cred, tipo(f["materia"])))

# el CSV debe ser coherente: créditos por semestre y por carrera
errores = [f"{c} sem {s}: suma {v} != {esperado}" for (c, s, esperado), v in por_semestre.items() if v != esperado]
errores += [f"{c}: suma {total[c]} != {carreras[c][1]}" for c in carreras if total[c] != carreras[c][1]]
if errores:
    print("INCOHERENCIAS EN EL CSV:", *errores, sep="\n  ")

salida = ["-- GENERADO por base-de-datos/generar_plan_estudios.py desde planes_pregrados.csv. No editar a mano.",
          "INSERT INTO carrera (nombre, semestres, creditos_totales) VALUES"]
salida.append(",\n".join(f"({sql(c)},{s},{cr})" for c, (s, cr) in sorted(carreras.items())) + ";")
salida.append("INSERT INTO curso (id, carrera, semestre, nombre, creditos, tipo) VALUES")
salida.append(",\n".join(f"({i},{sql(c)},{s},{sql(n)},{cr},{sql(t)})" for i, c, s, n, cr, t in materias) + ";")
(AQUI / "plan_estudios.sql").write_text("\n".join(salida) + "\n", encoding="utf-8")
print(f"{len(carreras)} carreras, {len(materias)} materias -> plan_estudios.sql")
