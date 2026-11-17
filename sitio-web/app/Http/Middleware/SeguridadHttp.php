<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\View;
use Symfony\Component\HttpFoundation\Response;

class SeguridadHttp
{
    private const LOCALES = ['localhost', '127.0.0.1', '::1'];

    public function handle(Request $request, Closure $next): Response
    {
        // HTTPS obligatorio en el dominio público (el túnel avisa el esquema con X-Forwarded-Proto)
        if (app()->isProduction() && ! $request->secure() && ! in_array($request->getHost(), self::LOCALES, true)) {
            return redirect()->secure($request->getRequestUri(), 301);
        }

        // nonce por petición: solo los <script> con este valor pueden ejecutarse (CSP)
        $nonce = base64_encode(random_bytes(18));
        View::share('cspNonce', $nonce);

        $respuesta = $next($request);
        header_remove('X-Powered-By');

        $cabeceras = [
            'Content-Security-Policy' => implode('; ', [
                "default-src 'self'",
                "script-src 'self' 'nonce-{$nonce}'",
                "style-src 'self' https://fonts.googleapis.com",
                'font-src https://fonts.gstatic.com',
                "img-src 'self' data:",
                "connect-src 'self'",
                "form-action 'self'",
                "base-uri 'none'",
                "frame-ancestors 'none'",
                "object-src 'none'",
            ]),
            'X-Frame-Options' => 'DENY',
            'X-Content-Type-Options' => 'nosniff',
            'Referrer-Policy' => 'strict-origin-when-cross-origin',
            'Permissions-Policy' => 'camera=(), microphone=(), geolocation=(), payment=(), usb=()',
            'Cross-Origin-Opener-Policy' => 'same-origin',
            'Cross-Origin-Resource-Policy' => 'same-origin',
        ];
        if ($request->secure()) {
            $cabeceras['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains';
        }

        // páginas HTML: nunca en caché, así "atrás" no muestra un chat anterior
        if (str_contains((string) $respuesta->headers->get('Content-Type'), 'text/html') || $respuesta->isRedirection()) {
            $cabeceras['Cache-Control'] = 'no-store, no-cache, must-revalidate, private';
            $cabeceras['Pragma'] = 'no-cache';
        }

        foreach ($cabeceras as $nombre => $valor) {
            $respuesta->headers->set($nombre, $valor);
        }

        return $respuesta;
    }
}
