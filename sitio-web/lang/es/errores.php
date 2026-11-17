<?php

// Textos de las páginas de error (resources/views/errors/4xx y 5xx). La clave es el código HTTP; "otro" cubre los demás.
return [
    403 => ['titulo' => 'Acceso no permitido', 'texto' => 'No tienes permiso para ver esta página.'],
    404 => ['titulo' => 'Página no encontrada', 'texto' => 'La página que buscas no existe.'],
    419 => ['titulo' => 'La sesión expiró', 'texto' => 'Pasó mucho tiempo sin actividad. Recarga la página e intenta de nuevo.'],
    429 => ['titulo' => 'Demasiados intentos', 'texto' => 'Hiciste muchas solicitudes seguidas. Espera un minuto e inténtalo de nuevo.'],
    500 => ['titulo' => 'Algo salió mal', 'texto' => 'Ocurrió un error inesperado. Intenta de nuevo en unos minutos.'],
    503 => ['titulo' => 'Estamos en mantenimiento', 'texto' => 'Volvemos en unos minutos.'],
    'otro' => ['titulo' => 'No pudimos completar la solicitud', 'texto' => 'Intenta de nuevo o vuelve al inicio.'],
];
