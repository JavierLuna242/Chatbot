{{-- Plantilla base de todas las páginas. Uso: <x-aplicacion titulo="Mi título" clase="pantalla-ventana"> ... </x-aplicacion> --}}
@props(['titulo' => null, 'clase' => ''])
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <meta name="theme-color" content="#0b3b5c">
    <meta name="robots" content="noindex, nofollow">
    {{-- favicon: SVG para navegadores modernos, ICO (16/32/48 px) de respaldo e icono de pantalla de inicio para iPhone --}}
    <link rel="icon" href="{{ asset('favicon.svg') }}?v={{ filemtime(public_path('favicon.svg')) }}" type="image/svg+xml">
    <link rel="icon" href="{{ asset('favicon.ico') }}?v={{ filemtime(public_path('favicon.ico')) }}" sizes="48x48">
    <link rel="apple-touch-icon" href="{{ asset('apple-touch-icon.png') }}?v={{ filemtime(public_path('apple-touch-icon.png')) }}">
    <title>{{ $titulo ? $titulo.' · ' : '' }}Asistente Académico</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&display=swap" rel="stylesheet">
    {{-- ?v= cambia solo cuando cambia el archivo, así el navegador nunca usa una versión vieja --}}
    <link rel="stylesheet" href="{{ asset('css/estilos.css') }}?v={{ filemtime(public_path('css/estilos.css')) }}">
    <script src="{{ asset('js/compartido.js') }}?v={{ filemtime(public_path('js/compartido.js')) }}" defer></script>
</head>
<body class="{{ $clase }}">
{{ $slot }}
</body>
</html>
