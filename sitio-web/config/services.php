<?php

// Credenciales de servicios externos que usa la web. Todo sale del .env.
return [

    // Flujo de chat en n8n Cloud: el webhook exige autenticación básica, así que solo este servidor puede llamarlo
    'n8n' => [
        'chat_url' => env('N8N_CHAT_URL'),
        'usuario' => env('N8N_CHAT_USER'),
        'clave' => env('N8N_CHAT_PASSWORD'),
    ],

];
