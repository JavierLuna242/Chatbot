{{-- Tarjeta centrada con la marca. Con "accion" es un formulario POST (con @csrf); sin ella, un contenedor simple. --}}
@props(['accion' => null, 'ancha' => false])
<div class="contenedor">
    @if ($accion)
        <form method="POST" action="{{ $accion }}" novalidate {{ $attributes->class(['tarjeta', 'vidrio', 'ancha' => $ancha]) }}>
            @csrf
            <x-marca />
            {{ $slot }}
        </form>
    @else
        <div {{ $attributes->class(['tarjeta', 'vidrio', 'ancha' => $ancha]) }}>
            <x-marca />
            {{ $slot }}
        </div>
    @endif
</div>
