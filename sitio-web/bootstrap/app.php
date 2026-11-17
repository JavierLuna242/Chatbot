<?php

use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware): void {
        // detrás del túnel de Cloudflare: solo cloudflared (local) puede informar https y la IP real del visitante
        $middleware->trustProxies(at: ['127.0.0.1', '::1']);
        $middleware->append(\App\Http\Middleware\SeguridadHttp::class);
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        $exceptions->shouldRenderJsonWhen(
            fn (Request $request) => $request->is('api/*') || $request->expectsJson(),
        );

        // una sola página para todos los errores HTTP (textos en lang/es/errores.php). Quedan igual: el JSON del chat y el modo debug.
        $exceptions->respond(function (Response $respuesta, Throwable $error, Request $peticion) {
            $codigo = $respuesta->getStatusCode();
            if ($codigo < 400 || $peticion->expectsJson() || config('app.debug')) {
                return $respuesta;
            }

            return response()->view('errors.pagina', ['codigo' => $codigo], $codigo,
                array_filter(['Retry-After' => $respuesta->headers->get('Retry-After')]));
        });
    })->create();
