<?php

// Solo las reglas que usa el chat (ver app/Http/Requests/MensajeChatRequest.php). Laravel no trae español por defecto.
return [
    'max' => ['string' => 'Revisa :attribute: máximo :max caracteres.'],
    'min' => ['string' => 'Revisa :attribute: mínimo :min caracteres.'],
    'regex' => 'Revisa el formato de :attribute.',
    'required' => 'Completa :attribute.',
    'string' => 'Revisa :attribute: debe ser texto.',
    'uuid' => 'Revisa :attribute: no es válido.',

    'attributes' => [
        'codigo' => 'el código estudiantil', 'mensaje' => 'el mensaje', 'sesion' => 'la sesión',
    ],
];
