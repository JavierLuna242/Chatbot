<?php

use App\Http\Controllers\ChatController;
use Illuminate\Support\Facades\Route;

// Sin cuentas: el estudiante se identifica escribiendo su código en el chat.
Route::redirect('/', '/chat')->name('inicio');
Route::get('/chat', [ChatController::class, 'index'])->name('chat');
Route::post('/chat', [ChatController::class, 'enviar'])->middleware('throttle:chat')->name('chat.enviar'); // 10/min y 300/día por IP
