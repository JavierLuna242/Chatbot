{{-- Iconos de línea de la interfaz. Uso: <x-icono nombre="chat" /> (chat, avance, perfil, salir, mas) --}}
@props(['nombre'])
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    @switch($nombre)
        @case('chat')
            <path d="M21 11.5a8.4 8.4 0 0 1-12.2 7.5L3 20.5l1.6-5A8.4 8.4 0 1 1 21 11.5z"/>
            @break
        @case('avance')
            <path d="M4 4v16h16"/><path d="M8 15l3.5-4 3 2.5L20 7"/>
            @break
        @case('perfil')
            <circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>
            @break
        @case('mas')
            <path d="M12 5v14M5 12h14"/>
            @break
        @case('salir')
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>
            @break
    @endswitch
</svg>
