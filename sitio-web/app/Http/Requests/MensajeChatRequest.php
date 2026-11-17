<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class MensajeChatRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true; // chat público: el control de abuso es el límite por IP de la ruta
    }

    public function rules(): array
    {
        // sesion: id del chat (lo genera el servidor al abrir /chat); codigo: el código estudiantil que el estudiante escribió, si ya lo dio
        return [
            'mensaje' => ['required', 'string', 'min:2', 'max:1000'],
            'sesion' => ['required', 'uuid'],
            'codigo' => ['nullable', 'regex:/^U\d{8}$/'],
        ];
    }

    public function messages(): array
    {
        return ['mensaje.min' => 'Escribe una pregunta de al menos 2 caracteres.'];
    }

    // quita caracteres de control (salvo saltos de línea) antes de validar y de mandarlo al modelo
    protected function prepareForValidation(): void
    {
        $this->merge([
            'mensaje' => trim(preg_replace('/[^\P{C}\n]+/u', '', (string) $this->input('mensaje')) ?? ''),
            'codigo' => $this->filled('codigo') ? strtoupper(trim((string) $this->input('codigo'))) : null,
        ]);
    }
}
