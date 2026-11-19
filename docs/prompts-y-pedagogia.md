# Prompts y fundamento pedagógico

Este documento recoge los prompts que usa el asistente tal como están en producción, explica por qué se redactaron así y en qué literatura se
apoyan esas decisiones. La fuente de verdad de los prompts es [`flujos-n8n/flujos/chatbot_academico.json`](../flujos-n8n/flujos/chatbot_academico.json):
si cambian allí, hay que actualizar este documento.

## Contenido

1. [Dónde actúa cada prompt](#1-dónde-actúa-cada-prompt) · 2. [Clasificador de intención](#2-clasificador-de-intención) ·
3. [Agente académico (MCP)](#3-agente-académico-mcp) · 4. [Agente institucional (RAG)](#4-agente-institucional-rag) ·
5. [Guardrails y respuestas fijas](#5-guardrails-y-respuestas-fijas) · 6. [Fundamento pedagógico](#6-fundamento-pedagógico) ·
7. [Cómo se validan](#7-cómo-se-validan) · 8. [Referencias](#8-referencias)

## 1. Dónde actúa cada prompt

```
mensaje → Guardrail de entrada → Clasificador de intención ─┬─ academico_personal → Agente académico  (MCP: 9 herramientas)  ─┐
         (jailbreak, claves)    (gpt-oss-120b, temp. 0)     ├─ institucional      → Agente institucional (RAG: pgvector, k=5) ─┼→ Guardrail de salida → respuesta
                                                            └─ fuera_de_tema      → respuesta fija                            ─┘   (tarjetas, IBAN, cripto, claves)
```

| Nodo | Modelo | Temperatura | Límite |
|---|---|---|---|
| Guardrail de entrada, clasificador y guardrail de salida | `openai/gpt-oss-120b` (Groq) | 0 | 1000 tokens |
| Agente académico y agente institucional | `openai/gpt-oss-20b` (Groq) | 0.1 | 4096 tokens, 5 iteraciones de herramientas |

Los filtros usan el modelo grande con temperatura 0 porque un error de clasificación manda la pregunta al agente equivocado; los agentes usan el
modelo pequeño porque cada pregunta los llama varias veces y el plan gratuito de Groq limita los tokens por minuto. La memoria guarda los 2 últimos
intercambios de cada conversación.

## 2. Clasificador de intención

Nodo *Text Classifier* de n8n. Recibe el mensaje ya revisado por el guardrail y elige una categoría; si el modelo no sabe, cae en `other`
(que se trata como fuera de tema). Las descripciones son el prompt: el nodo las pasa al modelo como definición de cada clase.

**`academico_personal`**

```text
La pregunta puede estar escrita en español o en inglés: clasifica por su significado, nunca por el idioma. Saludos (hola, hello, buenas tardes,
gracias, thanks), preguntas sobre qué puede hacer el asistente, mensajes que solo contienen un código estudiantil (la letra U seguida de 8 dígitos)
o que responden a la petición de identificarse, o preguntas sobre la situación del propio estudiante o datos académicos: estado de matrícula,
avance del plan, materias perdidas, proyección de semestres, qué cursos tomar, cursos de competencias digitales que ha tomado, recomendaciones,
planes y técnicas de estudio, orientación académica, calendario académico, fechas de inscripción o pruebas diagnósticas, noticias y convocatorias
de la universidad. Una pregunta sobre una norma o un trámite en general, que no use los datos del propio estudiante, NO va en esta categoría sino
en institucional. Las preguntas sobre FECHAS del calendario académico (cuándo es la inscripción o la matrícula, cuándo empiezan las clases, fechas
de cortes, exámenes finales, cancelación de materias, festivos, grados y convocatorias) son de esta categoría. Los cálculos de notas (qué nota
necesita para aprobar una materia, notas de cortes o del examen final, nota definitiva) también son de esta categoría. También son personales las
preguntas sobre SU promedio o SUS notas, si está en prueba académica, cuántos créditos puede inscribir o si cumple el promedio de una beca. Las
preguntas en primera persona sobre lo que EL PROPIO estudiante puede o debe hacer (¿cuántos créditos puedo inscribir?, ¿califico para una beca?,
¿estoy en prueba académica?, ¿cuánto me falta?) son personales aunque el tema también tenga una norma general.
```

**`institucional`**

```text
Preguntas generales sobre normas, reglamentos, trámites, políticas o documentos del programa y de la universidad, que no dependen de los datos
personales del estudiante: escala de notas y nota mínima para aprobar, asistencia, prueba académica, repetición de materias, carga máxima de
créditos, cómo inscribir, adicionar, cancelar o aplazar materias, estados de matrícula y pagos, becas y descuentos, bienestar y apoyo psicológico,
monitorías y tutorías, homologaciones, reintegros, traslados y doble programa, requisitos de grado, práctica profesional, estructura general del
plan de estudios (duración, créditos totales, cursos menor), y qué es o cómo funciona la insignia de competencias digitales. Si la pregunta es
sobre una norma o un trámite en general, es institucional aunque no mencione ningún documento. Las fechas concretas del calendario NO van aquí
sino en academico_personal; aquí solo va el cómo y el por qué de las normas y trámites. Las reglas generales (qué es la prueba académica, cómo
funcionan las becas) van aquí; los datos propios del estudiante, en academico_personal.
```

**`fuera_de_tema`**

```text
Temas que no tienen relación con la universidad, el programa o la vida académica del estudiante. Los saludos y las preguntas sobre el asistente
NO son fuera de tema. Escribir en inglés u otro idioma nunca hace que una pregunta sea fuera de tema.
```

**Por qué está escrito así**

- **La frontera se define por de quién es el dato, no por el tema.** «¿Qué es la prueba académica?» es institucional (la responde el reglamento);
  «¿Estoy en prueba académica?» es personal (la responde la base de datos). Si se clasificara por tema, la segunda iría al RAG, que contestaría
  con la norma pero sin el dato del estudiante. Las frases en mayúsculas (SU, EL PROPIO, FECHAS, NO) marcan esos casos frontera.
- **Las fechas van al agente académico** porque el calendario es una herramienta MCP (lee el Google Sheet), no un documento del RAG.
- **El idioma nunca decide la clase.** Una pregunta académica en inglés no debe terminar como fuera de tema; la batería lo comprueba.
- **Los saludos y el código solo son personales** para que el agente académico pueda identificar al estudiante y saludarlo por su nombre.

## 3. Agente académico (MCP)

Nodo *AI Agent* conectado al servidor MCP (9 herramientas, ver [README](../README.md#herramientas-del-mcp)). Las partes entre `{{ }}` son
expresiones de n8n que se evalúan en cada mensaje: la fecha de hoy y si la web ya envió el código del estudiante.

```text
Reasoning: low
Eres el asistente académico de Ingeniería de Sistemas. Nunca nombres la universidad ni su sigla: di "la universidad". Hoy es {{ fecha de hoy }}.
{{ identificación, una de las dos variantes de abajo }}

Datos:
- Toda pregunta sobre matrícula, avance, créditos, proyección, materias, promedio, notas, prueba académica, becas por promedio, insignia, plan,
  calendario o noticias exige llamar a la herramienta correspondiente en ese mismo turno, aunque ya hayas hablado del tema. Nunca inventes datos;
  si la herramienta falla, dilo. Pasa siempre el código exacto del estudiante y consulta solo ese código.
- Notas de una materia: usa calcular_nota solo con las notas que el estudiante te dio (0.0 a 5.0; primer corte 30 %, segundo corte 30 %, examen
  final 40 %; se aprueba con 3.0). Si dio al menos una nota, llama igual a calcular_nota con las que tiene (la herramienta calcula sola lo que
  falta, no le pidas las demás). Solo si no dio ninguna, pídelas; nunca calcules de memoria.
- Los datos son de demostración (base sintética). Respeta los prerrequisitos: recomienda solo materias habilitadas y, si pregunta por una
  bloqueada, di qué le falta aprobar antes. Al dar noticias incluye la fecha y la fuente (enlace) de cada una; si pide un tema (ingeniería de
  sistemas, tecnología, educación), filtra por él. No hay datos de pagos: que los consulte en el sistema académico de la universidad. Promedio,
  situación académica (prueba académica, carga máxima de créditos, becas) y notas de las materias aprobadas salen de promedio_y_estado (con
  con_detalle=true si pregunta por la nota de una materia concreta); no hay notas de materias reprobadas ni en curso.
- Solo atiendes Ingeniería de Sistemas; si preguntan por otra carrera, dilo con naturalidad. Adapta los consejos a su semestre y avance.

Formato: tono cercano y profesional, de tú, y siempre en español aunque la pregunta llegue en otro idioma. Sin emojis, exclamaciones, negritas,
cursivas, asteriscos, tablas ni encabezados. Nunca empieces con «Hola» ni con un saludo: empieza con la respuesta y luego el contexto, en párrafos
cortos (listas con guiones solo si hay varios elementos). Cuando aplique, cierra con el siguiente paso concreto como una oración normal, sin
etiquetas como «Próximo paso:». Escribe siempre una respuesta final.
```

Variante de identificación cuando **ya hay código** (la web lo manda en `metadata.codigo`):

```text
Identificación: el estudiante YA se identificó con el código {{ código }}; nunca se lo pidas. Llama a consultar_estudiante al inicio de la
conversación y cada vez que el código cambie; si no existe, pídele que lo revise. SOLO si su mensaje es únicamente el código o un saludo,
salúdalo por su primer nombre con su semestre y estado de matrícula y pregunta en qué le ayudas. Si su mensaje ya trae una pregunta, respóndela
directamente con las herramientas: sin saludar, sin repetir su semestre ni su matrícula y sin preguntar en qué más puedes ayudarle.
```

Variante cuando **no hay código**:

```text
Identificación: el estudiante NO se ha identificado. Tu ÚNICA respuesta es pedirle su código estudiantil (U y 8 dígitos, por ejemplo
U00100001). No uses herramientas.
```

**Por qué está escrito así**

| Instrucción | Problema que resuelve |
|---|---|
| «exige llamar a la herramienta … en ese mismo turno, aunque ya hayas hablado del tema» | Con memoria, el modelo puede repetir datos de turnos anteriores (o inventarlos) en vez de consultar. Los datos personales siempre salen de la base en el momento de la pregunta. |
| «Pasa siempre el código exacto … y consulta solo ese código» | Evita que el agente consulte a otro estudiante por un código mencionado de pasada. |
| La identificación como expresión, no como instrucción fija | Sin código, el agente ni siquiera intenta usar herramientas; con código, no lo vuelve a pedir. Es más barato que dejar que el modelo lo decida. |
| «nunca calcules de memoria» y los pesos explícitos | Los modelos pequeños se equivocan en aritmética; `calcular_nota` hace la cuenta y el modelo solo la explica. |
| «Respeta los prerrequisitos … di qué le falta aprobar antes» | `cursos_recomendados` ya filtra las materias bloqueadas; la instrucción evita que el modelo sugiera por su cuenta una materia del plan que el estudiante aún no puede inscribir. |
| «incluye la fecha y la fuente (enlace)» | Que el estudiante pueda comprobar cada noticia en la página original, en lugar de confiar en un resumen. |
| «Adapta los consejos a su semestre y avance» | El mismo consejo no sirve en primer semestre que en séptimo (ver sección 6). |
| Formato sin negritas, tablas ni encabezados | El chat muestra texto plano; el Markdown aparecía como asteriscos. El nodo *Respuesta* además borra cualquier `**` que se escape. |
| «Nunca empieces con Hola … empieza con la respuesta» | Evita que el modelo salude en cada mensaje y repita el semestre del estudiante antes de responder; la batería marca como falla una respuesta que empieza con saludo. |
| «cierra con el siguiente paso concreto» | Retroalimentación que dice qué hacer después (ver sección 6). |
| `Reasoning: low` | Los modelos `gpt-oss` aceptan esta directiva; razonar menos baja tokens y latencia sin perder aciertos en la batería. |
| «Nunca nombres la universidad ni su sigla» | Los datos son ficticios: el asistente no debe hablar en nombre de la institución real. |

## 4. Agente institucional (RAG)

Nodo *AI Agent* con la herramienta *Documentos institucionales* (PGVector en modo herramienta, 5 fragmentos, embeddings `gemini-embedding-001`).

```text
Reasoning: low
Eres el asistente institucional de Ingeniería de Sistemas. Nunca nombres la universidad ni su sigla: di "la universidad".
Responde SOLO con la herramienta de documentos institucionales y cita el documento: cada fragmento trae el campo «documento» en sus metadatos;
nómbralo tal cual en una frase corta (por ejemplo «según el documento reglamento estudiantil resumen») y nómbralos todos si usas varios. Busca
con términos en español aunque la pregunta venga en otro idioma. Si los documentos no contienen la respuesta, dilo y sugiere contactar a la
dirección del programa. Si la herramienta falla o no devuelve fragmentos, responde solo que no pudiste consultar los documentos ahora y sugiere
intentarlo más tarde o contactar a la dirección; nunca respondas de memoria ni inventes.

Formato: (el mismo bloque de formato del agente académico)
```

Descripción de la herramienta que ve el modelo:

```text
Busca en los documentos institucionales del programa y del CCD (reglamentos, insignia de competencias digitales, procesos). Úsala para cualquier
pregunta institucional.
```

**Por qué está escrito así**

- **«Responde SOLO con la herramienta» y «nunca respondas de memoria».** Es la idea central del RAG (Lewis et al., 2020; Gao et al., 2023): la
  respuesta se apoya en texto recuperado y no en lo que el modelo recuerde, que para normas de una universidad concreta sería inventado.
- **Citar el documento por su nombre.** El estudiante sabe de dónde sale la norma y puede ir a la fuente; la batería de pruebas comprueba que la
  cita aparezca.
- **Decir cuando no está.** La prueba «valor de la matrícula» verifica que el agente diga que no encontró el dato en lugar de inventar una cifra.
- **Buscar en español.** Los documentos están en español; la evaluación del RAG muestra que el embedding multilingüe acierta igual con preguntas en
  inglés, pero la búsqueda en español es la más segura.

## 5. Guardrails y respuestas fijas

| Nodo | Configuración | Qué pasa si se activa |
|---|---|---|
| Guardrail de entrada | Detección de *jailbreak* (umbral 0.7) y de claves secretas (permisividad equilibrada) | Responde «No puedo procesar ese mensaje. Reformula tu pregunta sobre temas académicos.» |
| Clasificador → `fuera_de_tema` | Ver sección 2 | Responde «Puedo ayudarte únicamente con temas académicos de Ingeniería de Sistemas: tu matrícula y avance, qué materias cursar, el plan de estudios, la insignia de competencias digitales, el calendario, los documentos institucionales y las novedades de la universidad.» |
| Guardrail de salida | Limpia tarjetas de crédito, IBAN, direcciones de criptomonedas y claves secretas | Sustituye el dato por un marcador antes de enviar la respuesta |
| Fallo del modelo (cupo de Groq) | Rama de error del guardrail de entrada | Responde «El asistente alcanzó su límite temporal de uso. Espera unos segundos e inténtalo de nuevo.» |

Las respuestas de rechazo son textos fijos, no generados: no gastan tokens, no se pueden manipular con el mensaje del usuario y la batería de
pruebas puede compararlas literalmente. La de fuera de tema enumera lo que sí se puede preguntar, para que el estudiante sepa cómo seguir.

## 6. Fundamento pedagógico

El asistente no enseña contenidos de las materias: apoya la **gestión de la propia trayectoria académica** (qué inscribir, cuánto falta, qué
norma aplica). Estas son las ideas que guiaron su diseño y dónde se ven en el sistema.

**Personalización con datos del estudiante (educación de precisión).** Luan y Tsai (2021) describen la educación de precisión como el uso de
datos del estudiante para ajustar la intervención a cada uno. Aquí la intervención es la orientación: las recomendaciones salen de las materias
que el estudiante ya aprobó, de sus prerrequisitos pendientes y de su promedio (que fija la carga máxima de créditos), no de un consejo genérico.
La instrucción «Adapta los consejos a su semestre y avance» y la herramienta `cursos_recomendados` son la forma concreta de hacerlo. Las revisiones
de chatbots educativos (Okonkwo y Ade-Ibijola, 2021; Wollny et al., 2021) recogen sus usos en educación, y Wollny et al. proponen como retos
abiertos explorar los chatbots para acompañar (mentoría) a los estudiantes y aprovechar su capacidad de adaptarse a cada uno.

**Autorregulación del aprendizaje.** En el modelo cíclico de Zimmerman (2002), el estudiante autorregulado planea (fija metas y estrategias),
ejecuta y se autoevalúa. Panadero (2017) compara seis modelos de aprendizaje autorregulado, que coinciden en una fase de preparación antes de la
tarea. El asistente
da insumos para planear: avance y proyección de semestres (incluida la cadena de prerrequisitos que limita la graduación), materias habilitadas,
fechas del calendario y la calculadora de notas, que responde «¿qué necesito en el final?» y ayuda a fijar una meta concreta para el siguiente
examen. El asistente informa; las decisiones las toma el estudiante.

**Retroalimentación que dice hacia dónde ir.** Hattie y Timperley (2007) distinguen tres preguntas que una buena retroalimentación responde:
hacia dónde voy, cómo voy y qué sigue. El asistente cubre las tres: la meta (los 134 créditos y los requisitos de grado), el estado actual
(créditos, porcentaje, promedio) y el siguiente paso, que el prompt pide cerrar como una acción concreta («Cuando aplique, cierra con el siguiente
paso concreto»).

**Información verificable y sin inventar.** Kasneci et al. (2023) analizan las oportunidades y los retos de los modelos de lenguaje en
educación; entre los retos están las respuestas incorrectas presentadas con seguridad y la necesidad de supervisión humana. Por eso los datos personales siempre salen de herramientas, las normas
salen de documentos citados por nombre (RAG, Lewis et al., 2020), las noticias traen fecha y enlace, y el asistente dice explícitamente cuando no
tiene un dato. Las respuestas aclaran que los datos son de demostración y remiten a la dirección del programa para decisiones importantes.

**Interacción acotada y predecible.** Kuhail et al. (2023) revisan el tipo y el estilo de interacción y los principios de diseño de los chatbots
educativos. En este proyecto la interacción es dirigida por el estudiante y de alcance cerrado: el asistente se limita a Ingeniería de Sistemas, responde siempre en español con el mismo
tono, sin formato recargado, y rechaza con un mensaje fijo que explica qué sí puede hacer.

## 7. Cómo se validan

- **Batería de extremo a extremo** ([`pruebas/probar_chatbot.py`](../pruebas/probar_chatbot.py)): 36 preguntas reales contra el webhook de
  producción. Cada caso verifica datos que deben aparecer, datos que no deben aparecer y las reglas de estilo del prompt (sin negritas, sin emojis,
  sin saludo inicial, cita del documento en las preguntas institucionales). Incluye intentos de *jailbreak*, claves pegadas, preguntas fuera de
  tema y en inglés, prerrequisitos y noticias por tema.
- **Evaluación del RAG** ([`docs/evaluacion-rag.md`](evaluacion-rag.md)): mide si el documento correcto llega al agente (Hit@k, MRR, precisión@5).
- **Evidencias** ([`docs/evidencias.md`](evidencias.md)): respuestas reales del chat con los datos de la base que las respaldan.

Cuando se cambia un prompt, se corre la batería completa antes de publicar el flujo (una vez al día como máximo, por el cupo de Groq).

## 8. Referencias

- Gao, Y., Xiong, Y., Gao, X., Jia, K., Pan, J., Bi, Y., Dai, Y., Sun, J., Guo, Q., Wang, M. y Wang, H. (2023). *Retrieval-augmented generation
  for large language models: A survey*. arXiv:2312.10997. <https://arxiv.org/abs/2312.10997>
- Hattie, J. y Timperley, H. (2007). The power of feedback. *Review of Educational Research, 77*(1), 81–112.
  <https://doi.org/10.3102/003465430298487>
- Kasneci, E., Sessler, K., Küchemann, S., Bannert, M., Dementieva, D., Fischer, F., … Kasneci, G. (2023). ChatGPT for good? On opportunities
  and challenges of large language models for education. *Learning and Individual Differences, 103*, 102274.
  <https://doi.org/10.1016/j.lindif.2023.102274>
- Kuhail, M. A., Alturki, N., Alramlawi, S. y Alhejori, K. (2023). Interacting with educational chatbots: A systematic review. *Education and
  Information Technologies, 28*, 973–1018. <https://doi.org/10.1007/s10639-022-11177-3>
- Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., … Kiela, D. (2020). Retrieval-augmented generation for
  knowledge-intensive NLP tasks. *Advances in Neural Information Processing Systems, 33* (NeurIPS 2020). <https://arxiv.org/abs/2005.11401>
- Luan, H. y Tsai, C.-C. (2021). A review of using machine learning approaches for precision education. *Educational Technology & Society,
  24*(1), 250–266. <https://doaj.org/article/3aab60e9caec44fab6fc950b99b4443d>
- Okonkwo, C. W. y Ade-Ibijola, A. (2021). Chatbots applications in education: A systematic review. *Computers and Education: Artificial
  Intelligence, 2*, 100033. <https://doi.org/10.1016/j.caeai.2021.100033>
- Panadero, E. (2017). A review of self-regulated learning: Six models and four directions for research. *Frontiers in Psychology, 8*, 422.
  <https://doi.org/10.3389/fpsyg.2017.00422>
- Wollny, S., Schneider, J., Di Mitri, D., Weidlich, J., Rittberger, M. y Drachsler, H. (2021). Are we there yet? A systematic literature
  review on chatbots in education. *Frontiers in Artificial Intelligence, 4*, 654924. <https://doi.org/10.3389/frai.2021.654924>
- Zimmerman, B. J. (2002). Becoming a self-regulated learner: An overview. *Theory Into Practice, 41*(2), 64–70.
  <https://doi.org/10.1207/s15430421tip4102_2>
