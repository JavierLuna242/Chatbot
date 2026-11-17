{{-- Página de error de cualquier código HTTP. La elige bootstrap/app.php y los textos salen de lang/es/errores.php. --}}
@php($mensaje = trans()->has("errores.{$codigo}") ? trans("errores.{$codigo}") : trans('errores.otro'))
<x-aplicacion :titulo="$mensaje['titulo']">
    <x-tarjeta class="centro">
        <h2>{{ $mensaje['titulo'] }}</h2>
        <p>{{ $mensaje['texto'] }}</p>
        <a class="primario boton-enlace" href="{{ route('inicio') }}">Ir al inicio</a>
    </x-tarjeta>
</x-aplicacion>
