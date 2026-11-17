# Asistente Académico · Ingeniería de Sistemas (UNAB)

Chatbot de apoyo académico para estudiantes de Ingeniería de Sistemas. El estudiante escribe su código estudiantil en el chat y el asistente le
responde con su matrícula, su avance en el plan de estudios, su promedio, qué materias cursar, las fechas del calendario, las noticias de la
universidad y las normas del programa (con cita del documento). Combina **RAG** sobre documentos institucionales con **agentes que consultan
herramientas MCP**, y todo corre sobre servicios gratuitos o de estudiante.

> **Los datos son de demostración.** Los 30 estudiantes, sus notas, el calendario y los 7 documentos institucionales son ficticios: no hay conexión
> con Banner ni con ningún sistema real de la universidad.

**Demo en producción:** <https://chatbot.javier.life> · códigos de prueba: `U00100001` a `U00100030`

## Contenido

[Capturas](#capturas) · [Qué hace](#qué-hace) · [Requisitos](#requisitos-del-proyecto-y-dónde-se-cumplen) · [Arquitectura](#arquitectura) · [Flujos en n8n](#flujos-en-n8n) · [Herramientas del MCP](#herramientas-del-mcp) ·
[Datos de demostración](#datos-de-demostración) · [Estructura](#estructura-del-repositorio) · [Instalación](#instalación-y-despliegue) ·
[Configuración](#configuración) · [Pruebas](#pruebas) · [Identidad](#cómo-funciona-la-identidad) · [Seguridad](#seguridad) · [Decisiones y límites](#decisiones-de-diseño-y-límites) · [Hoja de ruta](#hoja-de-ruta)

## Capturas

Capturas reales del sitio en producción, con estudiantes sintéticos.

<p align="center">
  <img src="docs/capturas/01-bienvenida.png" alt="Pantalla de bienvenida del chat" width="820"><br>
  <em><strong>Bienvenida.</strong> Pide el código estudiantil y ofrece códigos de prueba.</em>
</p>

<p align="center">
  <img src="docs/capturas/02-identificacion.png" alt="El asistente reconoce al estudiante" width="820"><br>
  <em><strong>Identificación.</strong> El asistente reconoce al estudiante por su código y aparece la barra de preguntas sugeridas.</em>
</p>

## Qué hace

- **Identificación sin cuentas:** el estudiante escribe su código (`U` + 8 dígitos) y el asistente lo valida contra la base de datos.
- **Su información académica:** estado de matrícula, avance y proyección de semestres, materias recomendadas, cursos de la insignia de competencias
  digitales, promedio acumulado, carga máxima de créditos y becas, y la nota de cada materia aprobada.
- **Calculadora de notas:** con los cortes que ya tiene (30 % + 30 % + 40 %), dice qué necesita en lo que falta para llegar a 3.0.
- **Información institucional con RAG:** reglamento, matrícula, plan de estudios, grado y práctica, bienestar, homologaciones e insignia. Cada
  respuesta nombra el documento del que sale.
- **Calendario y noticias:** fechas del calendario académico y noticias publicadas por la universidad, actualizadas cada 6 horas.
- **Preguntas sugeridas** y respuesta con efecto de escritura en la web.
- **Seguridad y control del alcance:** *guardrails* de entrada y salida, ruteo por intención y rechazo de temas ajenos a lo académico.

## Requisitos del proyecto y dónde se cumplen

| Requisito (diapositivas) | Dónde se cumple |
|---|---|
| Estado de matrícula, avance, proyección y recomendaciones | Herramientas `consultar_estudiante`, `avance_y_proyeccion`, `cursos_recomendados` y `plan_de_estudios` de `servidor-mcp/servidor_mcp.py`, más las vistas de `base-de-datos/esquema.sql` |
| Historial personalizado (cursos de competencias digitales, base sintética) | `competencias_digitales` y las tablas `curso_cd` y `cd_cursado` |
| Promedio, notas y situación académica | `promedio_y_estado`, `calcular_nota` y la columna `materia_aprobada.nota` |
| Insignia de competencias digitales y RAG institucional (CCD) | Flujo *Ingesta de documentos* + nodo PGVector del agente institucional; documentos en `documentos-rag/` |
| Calendario académico (Google Sheets) | `calendario_academico` lee el Sheet publicado como CSV si `CALENDARIO_CSV_URL` está definida; si no, la tabla `calendario` |
| Noticias (scraping periódico) | Flujo *Noticias UNAB*: API pública de unab.edu.co → tabla `noticia`, cada 6 horas |
| Guardrails | Nodos *Guardrails* de n8n: jailbreak y claves secretas a la entrada; tarjetas, IBAN, cripto y claves a la salida |
| Memoria persistente | *Postgres Chat Memory* en Supabase, una por conversación (id de sesión que genera la web) |
| Ruteo por intención | *Text Classifier* de n8n → agente académico, agente institucional o respuesta de fuera de tema |
| Cliente MCP | Agente de n8n con Groq conectado al servidor MCP por HTTP, con token Bearer |
| Docker | `docker-compose.yml` y `servidor-mcp/Dockerfile` para correr el MCP (alternativa al instalador; no probada en este entorno) |

## Arquitectura

```mermaid
flowchart TB
    E([Estudiante]) -->|"HTTPS"| WEB["Web Laravel<br/>solo el chat"]
    WEB -->|"HTTPS + usuario y clave"| FLUJO["Flujo Chatbot UNAB<br/>guardrails · clasificador · agentes"]
    FLUJO -->|"HTTPS + token Bearer"| MCP["Servidor MCP · FastMCP<br/>9 herramientas"]
    FLUJO -->|"modelos gpt-oss"| GROQ[("Groq")]
    ING["Flujo Ingesta de documentos"] -->|"embeddings"| GEM[("Gemini")]
    NOT["Flujo Noticias UNAB<br/>cada 6 horas"]
    FLUJO --> SB
    MCP --> SB
    ING --> SB
    NOT --> SB
    SB[("Supabase<br/>PostgreSQL + pgvector")]

    classDef azure fill:#dbeafe,stroke:#1d4ed8,color:#0f172a
    classDef n8n fill:#ffedd5,stroke:#c2410c,color:#0f172a
    classDef externo fill:#e5e7eb,stroke:#4b5563,color:#0f172a
    classDef datos fill:#dcfce7,stroke:#15803d,color:#0f172a
    class WEB,MCP azure
    class FLUJO,ING,NOT n8n
    class GROQ,GEM externo
    class SB datos
```

<sub>Azul: VM Debian en Azure, publicada con Cloudflare Tunnel y sin puertos abiertos · Naranja: n8n Cloud · Verde: base de datos · Gris: modelos externos.</sub>

### Recorrido de una pregunta dentro de n8n

```mermaid
flowchart TD
    A[Chat Trigger] --> B["Guardrail de entrada<br/>jailbreak y claves secretas"]
    B -->|bloqueado| X[Mensaje bloqueado]
    B -->|permitido| C[Clasificador de intención]
    C -->|"datos propios del estudiante"| D["Agente académico<br/>+ herramientas del MCP"]
    C -->|"normas y trámites"| R["Agente institucional<br/>+ búsqueda en documentos (RAG)"]
    C -->|"otro tema"| F[Fuera de tema]
    D --> G["Guardrail de salida<br/>tarjetas, IBAN, cripto y claves"]
    R --> G
    G --> H[Respuesta]
    D -.->|"fallo o límite de Groq"| S[Servicio ocupado]
    R -.-> S
    M[(Memoria en Supabase<br/>una por chat)] -.-> D
    M -.-> R
```

| Pieza | Tecnología | Función |
|---|---|---|
| Web | Laravel 13 (PHP 8.4) | Solo el chat: sin cuentas ni base de datos. Reenvía a n8n con usuario y clave, que el navegador nunca ve. |
| Orquestación | n8n Cloud | Guardrails, clasificador, dos agentes, memoria de conversación y los flujos de ingesta y noticias. |
| Modelos | Groq: `gpt-oss-20b` (agentes) y `gpt-oss-120b` (filtros) | Razonamiento y llamadas a herramientas. |
| Herramientas | FastMCP 4 (Python) | Servidor MCP con 9 herramientas y token Bearer. |
| Datos y RAG | Supabase (PostgreSQL + pgvector) | Datos académicos sintéticos, memoria del chat y vectores de los documentos. |
| Embeddings | Gemini (`gemini-embedding-001`) | Vectores de 3072 dimensiones para el RAG. |
| Red | Cloudflare Tunnel | Publica la web y el MCP con HTTPS sin abrir puertos en Azure. |

## Flujos en n8n

Los tres flujos están en [`flujos-n8n/flujos/`](flujos-n8n/flujos/) y se importan en n8n Cloud. Las imágenes son el lienzo de n8n dibujado con su componente
oficial a partir de esos archivos (no una captura de la cuenta de n8n Cloud, que exige iniciar sesión); se regeneran con `node pruebas/capturar_flujos_n8n.js`.

**Chatbot UNAB** (17 nodos): guardrails, clasificador de intención, agente académico con las herramientas del MCP, agente institucional con RAG, memoria y respuestas de error.

![Flujo Chatbot UNAB en n8n](docs/capturas/n8n-01-chatbot.png)

**Ingesta de documentos** (6 nodos): un formulario recibe los archivos, los separa, los fragmenta, calcula los embeddings con Gemini y los guarda en pgvector con el nombre del documento.

![Flujo de ingesta de documentos en n8n](docs/capturas/n8n-02-ingesta.png)

**Noticias UNAB** (4 nodos): cada 6 horas (o con el botón «Ejecutar ahora») lee las noticias de unab.edu.co y las guarda en la tabla `noticia`.

![Flujo de noticias en n8n](docs/capturas/n8n-03-noticias.png)

## Herramientas del MCP

El agente académico elige entre estas herramientas del servidor [`servidor-mcp/servidor_mcp.py`](servidor-mcp/servidor_mcp.py):

| Herramienta | Qué devuelve |
|---|---|
| `consultar_estudiante` | Nombre, carrera, semestre actual y estado de matrícula; valida el código. |
| `avance_y_proyeccion` | Créditos aprobados y pendientes, porcentaje de avance y semestres restantes estimados. |
| `cursos_recomendados` | Materias pendientes sugeridas para el próximo periodo, sin pasar de la carga máxima. |
| `competencias_digitales` | Estado de los cursos CD01 a CD04 de la insignia y si ya la obtuvo. |
| `promedio_y_estado` | Promedio acumulado ponderado por créditos, estado frente al reglamento, carga máxima, beca y puesto en el programa; con `con_detalle=true`, la nota de cada materia. |
| `calcular_nota` | Nota definitiva o nota necesaria en lo que falta (cortes de 30 %, 30 % y 40 %; aprueba con 3.0). Usa `Decimal`, sin errores de coma flotante. |
| `plan_de_estudios` | Materias y créditos del plan, completo o de un semestre. |
| `calendario_academico` | Fechas del calendario; búsqueda tolerante a tildes y a la forma de la palabra. |
| `noticias_recientes` | Últimas noticias y convocatorias de la universidad. |

## Datos de demostración

| Dato | Detalle |
|---|---|
| Estudiantes | 30, de `U00100001` a `U00100030`, repartidos en ciclo del 1.º al 8.º semestre. Los de 1.er semestre aún no tienen notas. |
| Plan de estudios | Ingeniería de Sistemas: 8 semestres, 134 créditos, 47 materias (`base-de-datos/planes_pregrados.csv`). |
| Notas | 611 notas de materias aprobadas, de 3.0 a 5.0 (media 3.93). No hay materias reprobadas ni del semestre en curso. |
| Calendario | 30 eventos de los periodos 2026-2 y 2027-1 (`base-de-datos/calendario_ejemplo.csv`). |
| Documentos del RAG | 7 documentos ficticios en `documentos-rag/` (23 fragmentos). |
| Noticias | Reales: se leen de la API pública de unab.edu.co. |

Códigos útiles para probar:

| Código | Promedio | Qué muestra |
|---|---|---|
| `U00100018` | 4.68 (puesto 1 de 26) | Puede inscribir 21 créditos y cumple el promedio de beca. |
| `U00100005` | 3.74 | Caso intermedio: avance del 45.5 %, 18 créditos máximos. |
| `U00100004` | 3.38 (puesto 26) | El promedio más bajo. |
| `U00100001` | sin notas | Primer semestre. |

## Estructura del repositorio

```
.
├── sitio-web/            Web Laravel 13: solo el chat (controlador, vistas, CSS/JS y tests)
├── servidor-mcp/         Servidor MCP (FastMCP), su prueba y su Dockerfile
├── flujos-n8n/flujos/    Los 3 workflows de n8n listos para importar (JSON)
├── base-de-datos/        Esquema SQL, plan de estudios, estudiantes sintéticos, calendario y sus generadores
├── documentos-rag/       Documentos ficticios que se suben al RAG
├── instalacion-debian/   instalar_debian.sh: instala MCP + web como servicios systemd
├── pruebas/              Batería de extremo a extremo, prueba del efecto de escritura y scripts de capturas
├── docs/capturas/        Capturas de pantalla usadas en este README
├── docker-compose.yml    Alternativa para correr solo el MCP con Docker (no probada en este entorno)
├── .env.example          Plantilla de variables de entorno
└── README.md
```

## Instalación y despliegue

**Requisitos:** cuenta de Supabase, n8n Cloud, clave de Groq y clave de Gemini (gratuitas), una VM Debian 12 y un dominio gestionado en Cloudflare.

1. **Supabase.** En *SQL Editor* ejecuta, en este orden, `base-de-datos/esquema.sql`, `plan_estudios.sql` y `estudiantes_sinteticos.sql`
   (y carga `calendario_ejemplo.csv` en la tabla `calendario`). Copia *Connect → Session pooler* (IPv4) para `DATABASE_URL`. Todas las tablas
   quedan con RLS activo y sin acceso desde la API REST. Para regenerar los datos: `python base-de-datos/generar_plan_estudios.py` y
   `python base-de-datos/generar_estudiantes.py`.
2. **VM Debian.** Copia el proyecto, `cp .env.example .env`, completa las variables (ver [Configuración](#configuración)) y ejecuta
   `sudo bash instalacion-debian/instalar_debian.sh`. El script instala PHP 8.4, crea el entorno de Python, genera los servicios `unab-mcp` y
   `unab-web` y comprueba que el MCP responda `401` sin token. Se puede volver a ejecutar para actualizar.
3. **Cloudflare Tunnel.** En *Zero Trust → Networks → Tunnels → Public hostnames* (servicio HTTP): `chatbot.TU-DOMINIO → localhost:8000` y
   `mcp.TU-DOMINIO → localhost:9000`.
4. **n8n Cloud.** Crea las credenciales de la tabla siguiente, importa los tres archivos de `flujos-n8n/flujos/` (*Workflows → Import from file*),
   asigna cada credencial a sus nodos, cambia la URL del nodo *Servidor MCP UNAB* por la tuya y publica *Chatbot UNAB*. Copia la *Production URL*
   del nodo **Chat** a `N8N_CHAT_URL`.
5. **Datos.** Sube los 7 archivos de `documentos-rag/` con el formulario del flujo *Ingesta de documentos* y ejecuta una vez *Noticias UNAB*.

Logs en la VM: `journalctl -u unab-mcp -u unab-web -f`.

Notas útiles:

- Si el nodo *Servidor MCP UNAB* no ofrece autenticación Bearer, usa *Header Auth* con nombre `Authorization` y valor `Bearer <MCP_TOKEN>`.
- `esquema.sql` reemplaza las tablas académicas (incluido `calendario`); la memoria del chat y los vectores no se tocan. No lo ejecutes de nuevo sin
  volver a cargar los datos.
- Si cambias el modelo de embeddings o reemplazas los documentos del RAG, vacía los vectores (`truncate n8n_vectors`) y vuelve a ingestar: la columna
  no fija dimensiones, pero no se pueden mezclar modelos.
- **Calendario con un Google Sheet:** crea una hoja con las columnas `evento, fecha_inicio, fecha_fin, categoria`, publícala (*Archivo → Compartir →
  Publicar en la web → CSV*) y pon la URL en `CALENDARIO_CSV_URL`; en la VM, vuelve a ejecutar el instalador.
- **Alternativa con Docker, solo para el MCP:** `docker compose up -d --build` (lee `DATABASE_URL`, `MCP_TOKEN` y `CALENDARIO_CSV_URL` del `.env`).

## Configuración

Variables de entorno (`.env`, que no se sube a git):

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Cadena del *Session pooler* de Supabase (puerto 5432). |
| `MCP_TOKEN` | Token del servidor MCP, mínimo 32 caracteres (`openssl rand -hex 32`). |
| `N8N_CHAT_URL` | *Production URL* del nodo Chat de n8n. |
| `N8N_CHAT_USER`, `N8N_CHAT_PASSWORD` | Usuario y clave del webhook del chat (los usa la web). |
| `CALENDARIO_CSV_URL` | Opcional: Google Sheet publicado como CSV. Si falta, se usa la tabla `calendario`. |

Credenciales de n8n Cloud (se crean en la interfaz: n8n Cloud no lee variables de entorno):

| Nombre | Tipo | Datos |
|---|---|---|
| `Groq` | Groq API | Clave de console.groq.com |
| `Supabase Postgres` | Postgres | Host, usuario y clave del *Session pooler*; puerto 5432, base `postgres`, SSL |
| `Gemini` | Google Gemini (PaLM) API | Clave de aistudio.google.com/apikey (los *Gateway credits* de n8n no cubren embeddings) |
| `Chat web` | Basic Auth | `N8N_CHAT_USER` y `N8N_CHAT_PASSWORD` |
| `MCP UNAB` | Bearer Auth | El mismo valor de `MCP_TOKEN` |

## Pruebas

| Nivel | Comando | Qué cubre |
|---|---|---|
| Servidor MCP | `cd servidor-mcp && pip install -r requirements.txt && DATABASE_URL=... python probar_servidor_mcp.py` | Las 9 herramientas contra Supabase: valores esperados, promedio y ranking, calculadora y rechazo de entradas inválidas. Solo lee. |
| Web (Laravel) | `cd sitio-web && php artisan test` | 8 pruebas: redirección y favicons, reenvío a n8n con código en mayúsculas y clave básica, aviso si n8n falla, validación y mensajes en español, página de error y cabeceras de seguridad. |
| Efecto de escritura | `node pruebas/probar_efecto_escritura.js` | La animación produce exactamente el mismo HTML que el render completo, escapa HTML y no rompe tablas. |
| Capturas del README | `cd pruebas && npm install && node tomar_capturas.js` | Toma capturas del chat real en `docs/capturas/` (bienvenida, identificación y varias funciones; hace unas 10 preguntas, así que gasta cupo de Groq). El README usa las dos primeras. Necesita Edge o Chrome. |
| Vistas de los flujos de n8n | `cd pruebas && npm install && node capturar_flujos_n8n.js` | Regenera `docs/capturas/n8n-*.png` desde los JSON de `flujos-n8n/` (necesita internet: usa el servicio de vista previa de n8n). |
| Extremo a extremo | `python pruebas/probar_chatbot.py [filtro] [--pausa 14]` | 34 casos contra el chat real: identificación, avance, promedio, calculadora, calendario, RAG con cita, fuera de tema, *jailbreak*, clave pegada e inglés. |

**Prueba rápida a mano:** abre <https://chatbot.javier.life>, escribe `U00100005` y pregunta *«¿Cuánto me falta para graduarme?»*,
*«¿Qué materias debería cursar?»*, *«¿Cuál es mi promedio?»*, *«¿Cuándo es la inscripción de materias?»*, *«¿Qué es la insignia de competencias
digitales?»* y *«¿Qué noticias hay?»*.

La batería de extremo a extremo gasta cerca de la mitad del cupo diario gratuito de Groq para el modelo de los agentes: conviene correrla una vez al día
o filtrarla por nombre de caso.

## Cómo funciona la identidad

No hay cuentas. La primera respuesta del asistente es pedir el código estudiantil. [`sitio-web/public/js/chat.js`](sitio-web/public/js/chat.js) lo detecta en
lo que escribe el estudiante (`U` + 8 dígitos) y lo envía con cada pregunta (`metadata.codigo`); el agente lo valida con `consultar_estudiante` y usa ese
código en las demás herramientas. El botón *Nuevo chat* (o recargar la página) abre otra sesión con memoria nueva. **El código es lo único que identifica al
estudiante**: por eso los datos son sintéticos. Con datos reales habría que validar contra Banner o contra el inicio de sesión institucional (Microsoft 365).

## Seguridad

| Capa | Medida |
|---|---|
| Red | La web y el MCP escuchan solo en `127.0.0.1`; el túnel de Cloudflare los publica con HTTPS. Sin puertos abiertos en Azure. |
| MCP | Toda petición exige `Authorization: Bearer <MCP_TOKEN>` (comparación en tiempo constante); sin token válido el servicio no arranca. |
| Web | CSP estricta con *nonce* y sin scripts en línea, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, COOP y CORP, HSTS y redirección 301 de HTTP a HTTPS; sin `X-Powered-By`. Validación en servidor y límite por IP (10 por minuto y 300 por día). |
| n8n | El webhook del chat exige usuario y clave. *Guardrails* de entrada (jailbreak, claves secretas) y de salida (tarjetas, IBAN, cripto, claves). |
| Supabase | RLS activo y sin políticas en todas las tablas, acceso revocado a `anon` y `authenticated`, vistas con `security_invoker`. Solo entran n8n y el MCP, por conexión directa a Postgres. |
| Secretos | `.env` fuera de git; en la VM viven en `/etc/unab` (modo 700, solo root) y cada servicio recibe solo sus variables; las claves de n8n quedan cifradas en n8n Cloud. |
| Dependencias | `composer audit` en cada despliegue; `pip-audit -r servidor-mcp/requirements.txt` para el MCP. |

## Decisiones de diseño y límites

- **El código estudiantil es la única credencial.** Es el diseño acordado (sin registro ni inicio de sesión) y por eso los datos son sintéticos: quien
  conozca un código ve los datos de ese estudiante. Con datos reales habría que validar contra el sistema académico o el inicio de sesión institucional.
- **Modelos.** Los agentes usan `gpt-oss-20b` y los filtros `gpt-oss-120b`. Se probó `qwen3.8-27b` para los agentes y se descartó: a partir del segundo
  mensaje respondía sin llamar a las herramientas e inventaba datos.
- **Plan gratuito de Groq.** Cada modelo permite 8 000 tokens por minuto y 200 000 por día. Una pregunta gasta unos 3 000 a 6 000 tokens, así que alcanza
  para unas decenas de preguntas al día; para demos largas conviene el plan de pago. Los prompts y las descripciones de herramientas son cortos a propósito.
- **Respuesta con efecto de escritura, no streaming real.** El streaming nativo de n8n impide que el *guardrail* de salida revise el texto antes de
  que lo vea el estudiante y deja sin respuesta las rutas sin agente (fuera de tema, mensaje bloqueado, servicio ocupado). Además, con Groq el texto llegó de golpe en la prueba (123 fragmentos en 10 ms), así que no mejoraba la espera. La web muestra la respuesta, ya revisada, palabra por palabra.
- **Latencia.** Una pregunta tarda de 8 a 12 segundos: dos llamadas al modelo, la consulta a las herramientas y la memoria. El MCP usa un pool de
  conexiones a Supabase para no abrir una conexión por consulta.
- **Alcance de los datos.** El plan no trae prerrequisitos, no hay materias reprobadas ni notas del semestre en curso (por eso nadie queda en prueba
  académica en la demo) y las notas, el calendario y los documentos son ficticios.
- **Docker.** `docker-compose.yml` y `servidor-mcp/Dockerfile` son una alternativa al instalador para correr el MCP; no se han ejecutado en este entorno.

## Hoja de ruta

- Segundo factor de identificación (por ejemplo un PIN) o inicio de sesión institucional.
- Conexión a datos reales (prerrequisitos y notas reales requieren un export o acceso a Banner), calendario oficial y documentos oficiales del programa.
  Para reemplazar los documentos de demostración: `truncate n8n_vectors` y subir los oficiales por el formulario de ingesta.
- Registro de conversaciones y valoración de respuestas para medir calidad.
- Alerta automática si la web o el MCP dejan de responder.
- Plan de pago de Groq para quitar el límite de tokens.

## Créditos

Proyecto académico de la asignatura Ciencia de Datos, Ingeniería de Sistemas (UNAB).
Tecnologías de terceros: [n8n](https://n8n.io), [Groq](https://groq.com) con los modelos `gpt-oss`, [FastMCP](https://gofastmcp.com),
[Supabase](https://supabase.com), [Laravel](https://laravel.com), [Cloudflare](https://www.cloudflare.com) y Gemini para los embeddings.
