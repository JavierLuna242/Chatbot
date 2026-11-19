-- Esquema para Supabase (PostgreSQL + pgvector). Pégalo en Supabase > SQL Editor y ejecútalo; después plan_estudios.sql
-- y estudiantes_sinteticos.sql, en ese orden. Se puede volver a ejecutar: reemplaza las tablas académicas
-- (la memoria del chat y los vectores del RAG no se tocan).
--
-- Solo Ingeniería de Sistemas. El estudiante se identifica en el chat con su código (U + 8 dígitos) y el servidor MCP
-- responde con estos datos SINTÉTICOS (no hay conexión a Banner). Nada de esto se expone por la API REST de Supabase:
-- todas las tablas tienen RLS activo sin políticas y se revoca el acceso a anon/authenticated; solo entran n8n Cloud
-- y el servidor MCP, que usan la conexión directa a Postgres (rol postgres, que ignora RLS).
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

DROP VIEW  IF EXISTS v_cd_estado, v_pendientes, v_avance, v_aprobados CASCADE;
DROP TABLE IF EXISTS prerrequisito, cd_cursado, curso_cd, materia_aprobada, estudiante, curso, carrera, calendario CASCADE;

CREATE TABLE carrera (
  nombre           text PRIMARY KEY,
  semestres        int  NOT NULL,   -- duración del plan
  creditos_totales int  NOT NULL
);

-- id = posición en el CSV (ver generar_plan_estudios.py). Los nombres se repiten (ELECTIVA, MENOR...), por eso no son clave.
CREATE TABLE curso (
  id       int  PRIMARY KEY,
  carrera  text NOT NULL REFERENCES carrera,
  semestre int  NOT NULL,           -- semestre del plan en que se ubica
  nombre   text NOT NULL,
  creditos int  NOT NULL,           -- 0 en laboratorios y talleres
  tipo     text NOT NULL            -- obligatorio | electivo
);
CREATE INDEX ON curso (carrera, semestre);

-- Prerrequisitos entre materias del plan (prerrequisitos.csv -> plan_estudios.sql). De demostración: coherentes con el plan,
-- pero no son los oficiales. Siempre apuntan a una materia de un semestre anterior.
CREATE TABLE prerrequisito (
  curso    int REFERENCES curso ON DELETE CASCADE,   -- la materia
  requiere int REFERENCES curso ON DELETE CASCADE,   -- la que hay que tener aprobada antes
  PRIMARY KEY (curso, requiere),
  CHECK (curso <> requiere)
);

-- Estudiantes sintéticos (estudiantes_sinteticos.sql). El código es lo único que el estudiante escribe en el chat.
CREATE TABLE estudiante (
  codigo            text PRIMARY KEY CHECK (codigo ~ '^U[0-9]{8}$'),
  nombre            text NOT NULL,
  carrera           text NOT NULL REFERENCES carrera,
  semestre_actual   int  NOT NULL,
  periodo_actual    text NOT NULL,                 -- ej. 2026-2
  estado_matricula  text NOT NULL                  -- Matriculado | Pendiente de pago | Aplazado
);

CREATE TABLE materia_aprobada (
  codigo_estudiante text REFERENCES estudiante ON DELETE CASCADE,
  curso             int  REFERENCES curso,
  nota              numeric(2,1) NOT NULL CHECK (nota BETWEEN 3.0 AND 5.0),   -- solo se guardan las aprobadas (nota mínima 3.0)
  PRIMARY KEY (codigo_estudiante, curso)
);

-- Insignia de competencias digitales: 4 cursos de 1 crédito (nota mínima 3.0). Ver documentos-rag/.
CREATE TABLE curso_cd (
  codigo   text PRIMARY KEY,
  nombre   text NOT NULL,
  creditos int  NOT NULL,
  semestre int  NOT NULL            -- semestre en que se recomienda cursarlo
);
INSERT INTO curso_cd VALUES
  ('CD01', 'Alfabetización Digital', 1, 1),
  ('CD02', 'Herramientas Digitales para la Productividad', 1, 2),
  ('CD03', 'Ciudadanía Digital y Seguridad de la Información', 1, 3),
  ('CD04', 'Inteligencia Artificial Generativa para el Aprendizaje', 1, 4);

CREATE TABLE cd_cursado (
  codigo_estudiante text REFERENCES estudiante ON DELETE CASCADE,
  curso_cd          text REFERENCES curso_cd,
  periodo           text NOT NULL,
  estado            text NOT NULL,   -- aprobado | reprobado | en curso
  nota              numeric(2,1),    -- null mientras está en curso
  PRIMARY KEY (codigo_estudiante, curso_cd, periodo)
);

-- Respaldo local del calendario (el servidor MCP usa Google Sheets si CALENDARIO_CSV_URL está definido).
CREATE TABLE calendario (
  evento       text NOT NULL,
  fecha_inicio date NOT NULL,
  fecha_fin    date,
  categoria    text NOT NULL
);

-- Tema de una noticia según palabras clave de su TÍTULO (sin tildes ni mayúsculas): el resumen trae texto genérico que confunde
-- (por ejemplo, las convocatorias laborales repiten «institución de educación superior»). La usa el flujo "Noticias UNAB" al guardar.
-- Orden de prioridad: ingeniería de sistemas > tecnología > educación > otros.
CREATE OR REPLACE FUNCTION clasificar_tema(texto text) RETURNS text
LANGUAGE sql IMMUTABLE SET search_path = pg_catalog AS $$
  SELECT CASE
    WHEN t ~ '(ingenieria de sistemas|software|programacion|ciberseguridad|ciencia de datos|bases? de datos|algoritm|data intelligence|desarrollo web)'
      THEN 'ingeniería de sistemas'
    WHEN t ~ '(inteligencia artificial|\mia\M|tecnolog|digital|moodle|biometric|face id|plataforma|innovacion|robot)'
      THEN 'tecnología'
    WHEN t ~ '(\mcursos?\M|estudiante|pregrado|posgrado|maestria|aprendizaje|academic|docente|profesor|matricula|beca|formacion|investigacion|ciencia|gradu|semestre)'
      THEN 'educación'
    ELSE 'otros' END
  FROM (SELECT translate(lower(coalesce(texto, '')), 'áéíóúüñ', 'aeiouun') AS t) x
$$;

-- Llenada por el workflow de n8n "Noticias UNAB" (scraping periódico)
CREATE TABLE IF NOT EXISTS noticia (
  url     text PRIMARY KEY,
  titulo  text NOT NULL,
  resumen text,
  fecha   timestamptz,
  tema    text                      -- clasificar_tema(titulo)
);

-- Memoria del chat (nodo "Postgres Chat Memory" de n8n) y vectores del RAG (nodo PGVector, embeddings de Gemini).
-- Se crean aquí para poder activar RLS; n8n usa las columnas que ya existen. La columna vector no fija las dimensiones
-- (sin índice, la búsqueda es exacta): sirve para Gemini (3072 por defecto) o cualquier otro modelo; no mezcles modelos en la misma tabla.
CREATE TABLE IF NOT EXISTS n8n_chat_histories (
  id         serial PRIMARY KEY,
  session_id varchar(255) NOT NULL,
  message    jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS n8n_chat_histories_sesion ON n8n_chat_histories (session_id);
CREATE TABLE IF NOT EXISTS n8n_vectors (
  id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  text      text,
  metadata  jsonb,
  embedding extensions.vector
);

-- ---------------------------------------------------------------- Vistas para el agente
-- security_invoker: respetan los permisos de quien consulta (la API REST no las puede usar).
CREATE VIEW v_aprobados WITH (security_invoker = true) AS
SELECT a.codigo_estudiante, c.id AS curso, c.nombre, c.creditos, c.semestre, a.nota
FROM materia_aprobada a
JOIN estudiante e ON e.codigo = a.codigo_estudiante
JOIN curso c ON c.id = a.curso AND c.carrera = e.carrera;

CREATE VIEW v_avance WITH (security_invoker = true) AS
SELECT e.codigo, e.nombre, e.carrera, e.semestre_actual, e.periodo_actual, e.estado_matricula,
       k.semestres AS semestres_plan,
       k.creditos_totales AS creditos_plan,
       coalesce(sum(a.creditos), 0)::int AS creditos_aprobados,
       k.creditos_totales - coalesce(sum(a.creditos), 0)::int AS creditos_pendientes,
       round(100.0 * coalesce(sum(a.creditos), 0) / k.creditos_totales, 1)::float AS porcentaje_avance,
       round(k.creditos_totales::numeric / k.semestres)::int AS creditos_por_semestre_plan
FROM estudiante e
JOIN carrera k ON k.nombre = e.carrera
LEFT JOIN v_aprobados a ON a.codigo_estudiante = e.codigo
GROUP BY e.codigo, k.nombre;

-- Materias del plan sin aprobar, ordenadas por semestre. «falta» = prerrequisitos que el estudiante aún no aprobó
-- (vacío = la puede inscribir ya).
CREATE VIEW v_pendientes WITH (security_invoker = true) AS
SELECT e.codigo AS codigo_estudiante, c.id AS curso, c.nombre, c.creditos, c.semestre, c.tipo,
       coalesce((SELECT array_agg(r.nombre ORDER BY r.semestre, r.id)
                 FROM prerrequisito p JOIN curso r ON r.id = p.requiere
                 WHERE p.curso = c.id
                   AND NOT EXISTS (SELECT 1 FROM materia_aprobada a WHERE a.codigo_estudiante = e.codigo AND a.curso = p.requiere)),
                '{}') AS falta
FROM estudiante e
JOIN curso c ON c.carrera = e.carrera
WHERE NOT EXISTS (SELECT 1 FROM materia_aprobada a WHERE a.codigo_estudiante = e.codigo AND a.curso = c.id);

-- Insignia: estado de cada curso CD por estudiante (aprobado | en curso | reprobado | pendiente)
CREATE VIEW v_cd_estado WITH (security_invoker = true) AS
SELECT e.codigo AS codigo_estudiante, d.codigo AS curso_cd, d.nombre, d.semestre AS semestre_recomendado,
       CASE WHEN bool_or(h.estado = 'aprobado') THEN 'aprobado'
            WHEN bool_or(h.estado = 'en curso')  THEN 'en curso'
            WHEN bool_or(h.estado = 'reprobado') THEN 'reprobado: debe repetirlo'
            ELSE 'pendiente' END AS estado,
       max(h.nota) FILTER (WHERE h.estado = 'aprobado') AS nota
FROM estudiante e
CROSS JOIN curso_cd d
LEFT JOIN cd_cursado h ON h.codigo_estudiante = e.codigo AND h.curso_cd = d.codigo
GROUP BY e.codigo, d.codigo, d.nombre, d.semestre;

-- ---------------------------------------------------------------- Seguridad
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['carrera','curso','prerrequisito','estudiante','materia_aprobada','curso_cd','cd_cursado',
                           'calendario','noticia','n8n_chat_histories','n8n_vectors'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);   -- sin políticas: la API REST (anon/authenticated) no ve nada
  END LOOP;
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
