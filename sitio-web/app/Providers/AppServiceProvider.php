<?php

namespace App\Providers;

use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\Facades\URL;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        //
    }

    public function boot(): void
    {
        // en el dominio público todos los enlaces salen con https
        if ($this->app->isProduction() && ! in_array(request()->getHost(), ['localhost', '127.0.0.1', '::1'], true)) {
            URL::forceScheme('https');
        }

        // el chat gasta cuota de Groq y es público: límite por IP (limitación: una IP compartida, como la de la universidad, comparte el cupo)
        RateLimiter::for('chat', fn (Request $r) => [
            Limit::perMinute(10)->by('min:'.$r->ip()),
            Limit::perDay(300)->by('dia:'.$r->ip()),
        ]);
    }
}
