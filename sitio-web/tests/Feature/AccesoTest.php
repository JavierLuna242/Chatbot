<?php

namespace Tests\Feature;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use Tests\TestCase;

class AccesoTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        config(['services.n8n' => ['chat_url' => 'https://n8n.test/webhook/x/chat', 'usuario' => 'web', 'clave' => 'secreta']]);
    }

    public function test_la_entrada_lleva_al_chat_y_pide_el_codigo(): void
    {
        $this->get('/')->assertRedirect('/chat');
        $this->get('/chat')->assertOk()->assertSee('código estudiantil');
    }

    public function test_las_paginas_declaran_el_favicon(): void
    {
        $this->get('/chat')->assertOk()->assertSee(['favicon.svg', 'favicon.ico', 'apple-touch-icon.png'], false);
        foreach (['favicon.svg', 'favicon.ico', 'apple-touch-icon.png'] as $archivo) {
            $this->assertGreaterThan(0, filesize(public_path($archivo)), "public/$archivo está vacío");
        }
    }

    public function test_el_mensaje_llega_a_n8n_con_el_codigo_en_mayusculas_y_la_clave_basica(): void
    {
        Http::fake(['*' => Http::response(['output' => 'Hola, Camila.'])]);
        $sesion = (string) Str::uuid();

        $this->postJson('/chat', ['mensaje' => 'u00100001', 'sesion' => $sesion, 'codigo' => 'u00100001'])
            ->assertOk()->assertExactJson(['respuesta' => 'Hola, Camila.']);

        Http::assertSent(fn ($r) => $r->url() === 'https://n8n.test/webhook/x/chat'
            && $r['sessionId'] === 'chat-'.$sesion
            && $r['metadata']['codigo'] === 'U00100001'
            && $r->hasHeader('Authorization', 'Basic '.base64_encode('web:secreta')));
    }

    public function test_sin_respuesta_de_n8n_el_estudiante_ve_un_aviso(): void
    {
        Http::fake(['*' => Http::response('', 500)]);

        $this->postJson('/chat', ['mensaje' => 'hola', 'sesion' => (string) Str::uuid()])
            ->assertOk()->assertJsonPath('respuesta', 'El asistente no está disponible en este momento. Intenta de nuevo en un minuto.');
    }

    public function test_se_rechazan_sesion_o_codigo_mal_formados(): void
    {
        Http::fake();
        $this->postJson('/chat', ['mensaje' => 'hola', 'sesion' => 'no-es-uuid'])->assertUnprocessable();
        $this->postJson('/chat', ['mensaje' => 'hola', 'sesion' => (string) Str::uuid(), 'codigo' => 'X123'])->assertUnprocessable();
        Http::assertNothingSent();
    }

    public function test_una_ruta_inexistente_muestra_la_pagina_de_error_en_espanol(): void
    {
        $this->get('/no-existe')->assertNotFound()->assertSee('Página no encontrada')->assertSee('Ir al inicio');
    }

    public function test_los_errores_de_validacion_salen_en_espanol(): void
    {
        Http::fake();
        $this->postJson('/chat', ['mensaje' => 'hola', 'sesion' => 'no-es-uuid'])
            ->assertUnprocessable()->assertJsonPath('errors.sesion.0', 'Revisa la sesión: no es válido.');
        $this->postJson('/chat', ['mensaje' => '', 'sesion' => (string) Str::uuid()])
            ->assertUnprocessable()->assertJsonPath('errors.mensaje.0', 'Completa el mensaje.');
    }

    public function test_las_respuestas_llevan_cabeceras_de_seguridad(): void
    {
        $r = $this->get('/chat');
        $r->assertHeader('X-Frame-Options', 'DENY')->assertHeader('X-Content-Type-Options', 'nosniff')
            ->assertHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
        $this->assertStringContainsString("default-src 'self'", (string) $r->headers->get('Content-Security-Policy'));
        $this->assertStringNotContainsString('unsafe-inline', (string) $r->headers->get('Content-Security-Policy'), 'la CSP no debe permitir scripts en línea');
    }
}
