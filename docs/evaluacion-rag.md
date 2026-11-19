# Evaluación de la recuperación del RAG

Generado el 2026-11-19 17:25 (hora de Colombia) con `python pruebas/evaluar_rag.py`. Resultados medidos, no estimados.

## Método

- **Corpus:** los 7 documentos de `documentos-rag/` (de 1718 a 3903 caracteres cada uno).
- **Preguntas:** 24, con su documento correcto conocido: 3 por documento, redactadas con otras palabras, y 3 en inglés.
- **Modelo de embeddings:** `gemini-embedding-001` (3072 dimensiones), el mismo de producción. Búsqueda por similitud coseno en pgvector, top 5.
- **Configuraciones:** cada tamaño y solapamiento (en caracteres, con el divisor recursivo de n8n) se ingesta en una tabla de prueba; la última fila mide la tabla real de producción como control.
- **Métricas:** Hit@k (el documento correcto aparece entre los k primeros fragmentos), MRR (promedio de 1 / posición del primer fragmento correcto) y Precisión@5 (porcentaje de los 5 fragmentos que vienen del documento correcto).

## Resultados

| Configuración | Fragmentos | Largo medio | Hit@1 | Hit@3 | Hit@5 | MRR | Precisión@5 | Precisión@5 máxima posible |
|---|---|---|---|---|---|---|---|---|
| 500 / 75 | 53 | 335 | 92 % | 100 % | 100 % | 0.96 | 65 % | 100 % |
| 1000 / 0 | 26 | 684 | 100 % | 100 % | 100 % | 1.00 | 52 % | 71 % |
| 1000 / 150 ← producción | 26 | 684 | 100 % | 100 % | 100 % | 1.00 | 52 % | 71 % |
| 2000 / 300 | 14 | 1338 | 88 % | 100 % | 100 % | 0.93 | 38 % | 42 % |
| Producción (`n8n_vectors`, 1000 / 150) | 24 | 744 | 96 % | 100 % | 100 % | 0.98 | 53 % | 71 % |

La *precisión@5 máxima posible* es el techo de la precisión: si el documento correcto tiene menos de 5 fragmentos, el resto del top 5 viene obligatoriamente de otros documentos. Con fragmentos grandes hay menos fragmentos por documento y el techo baja.

## Detalle por pregunta (tabla de producción)

Posición del primer fragmento del documento correcto, documentos que ocuparon el top 5 y distancia coseno del primer resultado (la puntuación que devuelve pgvector: menor = más parecido; una pregunta sin relación con los documentos queda cerca de 0.46).

| # | Pregunta | Documento esperado | Posición | Top 5 (documento de cada fragmento) | Distancia del 1.º |
|---|---|---|---|---|---|
| 1 | ¿Con qué nota se aprueba una materia? | reglamento estudiantil resumen | 1 | RER · RER · RER · ICD · ODG | 0.263 |
| 2 | ¿Qué porcentaje de asistencia necesito para no perder una materia? | reglamento estudiantil resumen | 1 | RER · RER · PIY · HRY · RER | 0.188 |
| 3 | ¿Qué pasa si mi promedio acumulado queda por debajo de 3.0? | reglamento estudiantil resumen | 1 | RER · RER · RER · RER · ICD | 0.254 |
| 4 | ¿Qué significa que mi matrícula esté pendiente de pago? | proceso inscripcion y matricula | 1 | PIY · PIY · PIY · PIY · RER | 0.241 |
| 5 | ¿Hasta qué semana puedo cancelar una materia? | proceso inscripcion y matricula | 1 | PIY · PIY · RER · PIY · HRY | 0.182 |
| 6 | ¿Cómo pido el aplazamiento del semestre? | proceso inscripcion y matricula | 1 | PIY · PIY · HRY · PIY · HRY | 0.229 |
| 7 | ¿Cuántos créditos tiene la carrera y cuántos semestres dura? | plan de estudios ingenieria de sistemas | 1 | PDE · PDE · PDE · PDE · RER | 0.247 |
| 8 | ¿Qué son los cursos menor? | plan de estudios ingenieria de sistemas | 1 | PDE · PDE · PDE · ICD · HRY | 0.312 |
| 9 | ¿A cuántas horas de trabajo equivale un crédito? | plan de estudios ingenieria de sistemas | 2 | RER · PDE · PDE · ODG · ODG | 0.330 |
| 10 | ¿Qué necesito para graduarme? | opciones de grado y practica profesional | 1 | ODG · ICD · PDE · ICD · PDE | 0.264 |
| 11 | ¿Cuántos créditos debo tener aprobados para inscribir la práctica profesional? | opciones de grado y practica profesional | 1 | ODG · ODG · PDE · PDE · ICD | 0.194 |
| 12 | ¿Puedo hacer la práctica en mi propio emprendimiento? | opciones de grado y practica profesional | 1 | ODG · ODG · ICD · PDE · ODG | 0.240 |
| 13 | ¿Qué promedio piden para la beca de investigación? | bienestar becas y apoyos | 1 | BBY · RER · HRY · RER · RER | 0.255 |
| 14 | ¿La universidad ofrece atención psicológica gratuita? | bienestar becas y apoyos | 1 | BBY · BBY · ODG · HRY · BBY | 0.252 |
| 15 | ¿Hay monitorías para materias de programación? | bienestar becas y apoyos | 1 | BBY · PDE · BBY · PIY · HRY | 0.276 |
| 16 | ¿Cuántos créditos puedo homologar de otra universidad? | homologaciones reintegros y traslados | 1 | HRY · RER · HRY · HRY · PDE | 0.249 |
| 17 | ¿Puedo cambiarme a otro programa de la universidad? | homologaciones reintegros y traslados | 1 | HRY · HRY · PIY · PIY · RER | 0.221 |
| 18 | ¿Qué necesito para irme de intercambio? | homologaciones reintegros y traslados | 1 | HRY · PIY · PDE · ODG · PIY | 0.279 |
| 19 | ¿Qué cursos componen la insignia de competencias digitales? | insignia competencias digitales | 1 | ICD · ICD · PDE · ODG · PDE | 0.192 |
| 20 | ¿Qué pasa si repruebo un curso de la insignia? | insignia competencias digitales | 1 | ICD · RER · ICD · PDE · PDE | 0.206 |
| 21 | ¿La insignia es requisito para la práctica profesional? | insignia competencias digitales o opciones de grado y practica profesional | 1 | ICD · ODG · ICD · ODG · ODG | 0.271 |
| 22 | What grade do I need to pass a course? | reglamento estudiantil resumen | 1 | RER · RER · ICD · ODG · RER | 0.382 |
| 23 | How many credits can I transfer from another university? | homologaciones reintegros y traslados | 1 | HRY · RER · PDE · HRY · HRY | 0.364 |
| 24 | Is there free psychological counseling? | bienestar becas y apoyos | 1 | BBY · BBY · PIY · ODG · HRY | 0.352 |

Abreviaturas: `BBY` = bienestar becas y apoyos · `HRY` = homologaciones reintegros y traslados · `ICD` = insignia competencias digitales · `ODG` = opciones de grado y practica profesional · `PDE` = plan de estudios ingenieria de sistemas · `PIY` = proceso inscripcion y matricula · `RER` = reglamento estudiantil resumen.

## Preguntas donde el documento correcto no salió primero

- **¿A cuántas horas de trabajo equivale un crédito?** (posición 2): el primer fragmento vino de *reglamento estudiantil resumen* y empieza «Repetición de materias
- Una materia reprobada debe repetirse la próxima vez que se ofrezca. Si la materia es obligatori…».

