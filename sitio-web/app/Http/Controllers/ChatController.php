<?php

namespace App\Http\Controllers;

use App\Http\Requests\MensajeChatRequest;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;

class ChatController extends Controller
{
    private const MAX_RESPUESTA = 8000;

    // Cada visita a /chat es un chat nuevo: el id de sesión es distinto y n8n guarda la memoria con ese id.
    public function index()
    {
        return view('chat.index', ['sesion' => (string) Str::uuid()]);
    }

    // La web solo reenvía a n8n Cloud (usuario y clave en el servidor); el navegador nunca ve esa URL ni esas claves.
    // El código estudiantil viaja tal cual lo escribió el estudiante: el agente lo valida con el servidor MCP.
    public function enviar(MensajeChatRequest $request)
    {
        $n8n = config('services.n8n');

        $texto = $this->consultarN8n($n8n, [
            'action' => 'sendMessage',
            'sessionId' => 'chat-'.$request->validated('sesion'),
            'chatInput' => $request->validated('mensaje'), // ya sin caracteres de control
            'metadata' => ['codigo' => $request->validated('codigo')],
        ]);

        $texto = is_string($texto) ? Str::limit($this->sinEmojis($texto), self::MAX_RESPUESTA) : '';

        return response()->json([
            'respuesta' => $texto !== '' ? $texto : 'El asistente no está disponible en este momento. Intenta de nuevo en un minuto.',
        ]);
    }

    // Devuelve el texto del asistente o null si n8n no respondió.
    private function consultarN8n(array $n8n, array $cuerpo): ?string
    {
        try {
            $respuesta = Http::withBasicAuth((string) $n8n['usuario'], (string) $n8n['clave'])->timeout(120)->post($n8n['chat_url'], $cuerpo);
            $texto = $respuesta->successful() ? $respuesta->json('output') : null;
        } catch (ConnectionException) {
            $texto = null;
        }

        return is_string($texto) && $texto !== '' ? $texto : null;
    }

    // Emojis, símbolos decorativos y sus modificadores (variación, unión y keycap)
    private const EMOJIS = '[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{20E3}\x{FE0F}\x{200D}]+';

    // El asistente responde con tono académico y sin emojis; esto lo garantiza aunque el modelo se desvíe.
    private function sinEmojis(string $texto): string
    {
        $emojis = self::EMOJIS;
        $texto = preg_replace("/ *{$emojis}(?=[.,;:!?)])/u", '', $texto) ?? $texto;   // "plan ✅." queda "plan."
        $texto = preg_replace("/{$emojis}/u", '', $texto) ?? $texto;
        $texto = preg_replace('/[ \t]+$/m', '', $texto);                                // espacios al final de línea

        return trim(preg_replace('/(?<=\S) {2,}/', ' ', $texto));                       // espacios dobles entre palabras
    }
}
