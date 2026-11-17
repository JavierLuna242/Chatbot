"""Genera base-de-datos/estudiantes_sinteticos.sql: 30 estudiantes ficticios de Ingeniería de Sistemas.

Uso: python base-de-datos/generar_estudiantes.py   (después de generar_plan_estudios.py)
Semilla fija: siempre salen los mismos estudiantes. Códigos U00100001 a U00100030 (el 1.º está en 1.er semestre y así hasta el 8.º).
Cada estudiante aprobó las materias de los semestres anteriores al actual, salvo 0-2 materias perdidas;
los cursos CD (insignia de competencias digitales) siguen el mismo patrón, con algún reprobado.
Cada materia aprobada trae una nota entre 3.0 y 5.0 (solo se guardan las aprobadas). Las notas salen de un generador aparte (rng_notas)
para que agregarlas no cambie nada de lo demás: cada estudiante tiene un nivel propio (3.3 a 4.6) y sus notas varían alrededor de él.
"""
import csv
import random
from pathlib import Path

AQUI = Path(__file__).parent
ORDINALES = ["primer", "segundo", "tercer", "cuarto", "quinto", "sexto", "septimo", "octavo"]
NOMBRES = ["Camila", "Juan", "Valentina", "Santiago", "Daniela", "Andrés", "Laura", "Sebastián", "Mariana", "Felipe",
           "Isabela", "Mateo", "Sara", "Nicolás", "Luisa"]
APELLIDOS = ["Gómez", "Rodríguez", "Martínez", "Hernández", "López", "Pérez", "Ramírez", "Torres", "Díaz", "Vargas",
             "Castro", "Rojas", "Moreno", "Ortiz", "Jiménez"]
CD = ["CD01", "CD02", "CD03", "CD04"]  # el CDn se recomienda en el semestre n

rng = random.Random(7)
rng_notas = random.Random(11)
cursos = []  # (id, semestre, creditos)
for i, f in enumerate(csv.DictReader(open(AQUI / "planes_pregrados.csv", encoding="utf-8-sig")), start=1):
    cursos.append((i, ORDINALES.index(f["semestre"].split()[0].lower()) + 1, int(f["creditos_materia"])))


def periodo(atras):
    """Periodo académico 'atras' semestres antes de 2026-2."""
    n = 2026 * 2 + 1 - atras
    return f"{n // 2}-{n % 2 + 1}"


def sql(t):
    return "'" + t.replace("'", "''") + "'"


est, aprobadas, cds = [], [], []
for n in range(1, 31):
    codigo = f"U{100000 + n:08d}"
    actual = (n - 1) % 8 + 1
    a1, a2 = (n * 4) % 15, (n * 4 + 5) % 15   # el 2.º apellido está 5 lugares después: nunca repite el 1.º
    nombre = f"{NOMBRES[(n * 7) % 15]} {APELLIDOS[a1]} {APELLIDOS[a2]}"
    estado = rng.choices(["Matriculado", "Pendiente de pago", "Aplazado"], [8, 2, 1])[0]
    est.append(f"({sql(codigo)},{sql(nombre)},'Ingeniería de Sistemas',{actual},'2026-2',{sql(estado)})")

    previas = [c for c in cursos if c[1] < actual]
    perdidas = {c[0] for c in rng.sample([c for c in previas if c[2] > 0], min(rng.choice([0, 0, 1, 2]), len(previas)))}
    nivel = rng_notas.uniform(3.3, 4.6)
    aprobadas += [f"({sql(codigo)},{c[0]},{min(5.0, max(3.0, round(rng_notas.gauss(nivel, 0.35), 1)))})" for c in previas if c[0] not in perdidas]

    for k, cd in enumerate(CD, start=1):
        if k < actual:  # ya le tocaba: casi siempre aprobado, a veces reprobó el primer intento
            if rng.random() < 0.12:
                cds.append(f"({sql(codigo)},{sql(cd)},{sql(periodo(actual - k + 1))},'reprobado',{rng.choice([2.0, 2.5, 2.8])})")
            else:
                cds.append(f"({sql(codigo)},{sql(cd)},{sql(periodo(actual - k))},'aprobado',{round(rng.uniform(3.0, 4.9), 1)})")
        elif k == actual:  # el del semestre en curso
            cds.append(f"({sql(codigo)},{sql(cd)},'2026-2','en curso',NULL)")

salida = ["-- GENERADO por base-de-datos/generar_estudiantes.py. Datos ficticios; no editar a mano.",
          "INSERT INTO estudiante (codigo, nombre, carrera, semestre_actual, periodo_actual, estado_matricula) VALUES",
          ",\n".join(est) + ";",
          "INSERT INTO materia_aprobada (codigo_estudiante, curso, nota) VALUES",
          ",\n".join(aprobadas) + ";",
          "INSERT INTO cd_cursado (codigo_estudiante, curso_cd, periodo, estado, nota) VALUES",
          ",\n".join(cds) + ";"]
(AQUI / "estudiantes_sinteticos.sql").write_text("\n".join(salida) + "\n", encoding="utf-8")
print(f"{len(est)} estudiantes, {len(aprobadas)} materias aprobadas, {len(cds)} registros CD -> estudiantes_sinteticos.sql")
