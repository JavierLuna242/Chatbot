@props(['sub' => 'Tu guía académica personalizada'])
<a class="marca" href="{{ route('inicio') }}">
    <div class="logo"><x-icono-asistente /></div>
    <div><h1>Asistente Académico</h1><p class="sub">{{ $sub }}</p></div>
</a>
