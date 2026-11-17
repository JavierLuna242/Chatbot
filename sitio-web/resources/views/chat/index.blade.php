<x-aplicacion clase="pantalla-ventana">
    <x-ventana>
        <section class="panel chat" aria-label="Conversación con el asistente">
            <header class="cabecera">
                <div class="avatar" aria-hidden="true"><x-icono-asistente /></div>
                <div>
                    <strong>Asistente Académico</strong>
                    <small>Matrícula, avance y recomendaciones con tu código estudiantil</small>
                </div>
                {{-- recargar la página abre un chat nuevo (sesión y memoria nuevas); hay que volver a dar el código --}}
                <div class="nuevo-chat">
                    <button type="button" class="secundario" id="nuevo"><x-icono nombre="mas" /><span>Nuevo chat</span></button>
                </div>
            </header>

            <main id="mensajes" aria-live="polite">
                <div class="hilo" id="hilo">
                    <div class="bienvenida" id="bienvenida">
                        <h2>Hola<span>¿Cuál es tu código estudiantil?</span></h2>
                        <p>Escríbelo en el cuadro de abajo (la letra U y 8 dígitos, por ejemplo U00100001) y te muestro tu matrícula, tu avance en el plan de estudios y qué materias te conviene cursar. Si prefieres, también puedes preguntar por el plan, el calendario o la insignia de competencias digitales.</p>
                        {{-- datos de demostración: el sistema no está conectado a Banner. Quitar este bloque cuando haya datos reales. --}}
                        <p class="etiqueta-demo">Modo demostración: no tengo conexión con la universidad, así que usa uno de estos códigos de prueba</p>
                        <div class="sugerencias" aria-label="Códigos de demostración">
                            <button type="button" data-enviar="U00100001">U00100001 · 1.er semestre</button>
                            <button type="button" data-enviar="U00100005">U00100005 · 5.º semestre</button>
                            <button type="button" data-enviar="U00100008">U00100008 · 8.º semestre</button>
                        </div>
                    </div>
                </div>
            </main>

            <div class="compositor">
                {{-- preguntas sugeridas: aparecen cuando el estudiante ya se identificó (texto del botón => pregunta que se envía) --}}
                @php($sugeridas = [
                    'Mi avance' => '¿Cuánto me falta para graduarme?',
                    'Mi promedio' => '¿Cuál es mi promedio y cómo voy académicamente?',
                    'Qué materias cursar' => '¿Qué materias debería cursar el próximo semestre?',
                    'Mi insignia digital' => '¿Qué cursos de competencias digitales he tomado?',
                    'Fechas de inscripción' => '¿Cuándo es la inscripción de materias?',
                    'Calcular mi nota' => 'Quiero calcular qué nota necesito para aprobar una materia.',
                    'Cancelar una materia' => '¿Hasta cuándo puedo cancelar una materia?',
                    'Requisitos de grado' => '¿Cuáles son los requisitos para graduarme?',
                    'Becas' => '¿Cómo funcionan las becas?',
                    'Noticias' => '¿Qué noticias hay de la universidad?',
                ])
                <div class="sugerencias barra" id="sugerencias" aria-label="Preguntas sugeridas" hidden>
                    @foreach ($sugeridas as $texto => $pregunta)
                        <button type="button" data-enviar="{{ $pregunta }}">{{ $texto }}</button>
                    @endforeach
                </div>
                <form id="formulario" data-url="{{ route('chat.enviar') }}" data-sesion="{{ $sesion }}" novalidate>
                    <label for="mensaje" hidden>Mensaje</label>
                    <textarea id="mensaje" rows="1" placeholder="Escribe tu código estudiantil (ej. U00100001)…"></textarea>
                    <button class="primario" id="enviar">Enviar</button>
                </form>
                <p class="nota">Las respuestas se generan con IA a partir de datos de demostración; verifica la información importante con tu programa.</p>
            </div>
        </section>
    </x-ventana>

    {{-- el icono del asistente se clona desde aquí para las respuestas que llegan por fetch --}}
    <template id="icono"><x-icono-asistente /></template>
    <script src="{{ asset('js/chat.js') }}?v={{ filemtime(public_path('js/chat.js')) }}" defer></script>
</x-aplicacion>
