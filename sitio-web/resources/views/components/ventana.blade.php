{{-- Ventana principal de la app: barra lateral con la marca y el panel del chat a la derecha ($slot). --}}
<div class="ventana">
    <aside class="lateral" aria-label="Menú principal">
        <x-marca sub="Ingeniería de Sistemas" />
        <nav class="menu">
            <a href="{{ route('chat') }}" aria-current="page">
                <span class="icono-menu"><x-icono nombre="chat" /></span>
                <span><strong>Chat</strong><small>Pregúntale al asistente</small></span>
            </a>
        </nav>
    </aside>

    {{ $slot }}
</div>
