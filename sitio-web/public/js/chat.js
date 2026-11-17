// Chat: envía la pregunta a POST /chat (Laravel) y muestra la respuesta. El id de sesión llega por un atributo de la vista.
// El primer mensaje del estudiante es su código (U + 8 dígitos): se recuerda aquí y viaja con cada pregunta para que el asistente lo tenga siempre.
let codigo = null;
const hilo = document.getElementById('hilo');
const mensajes = document.getElementById('mensajes');
const formulario = document.getElementById('formulario');
const campo = document.getElementById('mensaje');
const boton = document.getElementById('enviar');
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const icono = document.getElementById('icono').innerHTML;

// el agente responde en markdown: escapamos HTML y convertimos solo negritas, cursivas, separadores y tablas
const celdas = (fila) => fila.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
const tabla = (bloque) => {
    const filas = bloque.trim().split('\n').filter((f) => !/^\s*\|?[\s:|-]+\|?\s*$/.test(f));
    const [cabecera, ...cuerpo] = filas.map(celdas);
    return '<div class="tabla"><table><thead><tr>' + cabecera.map((c) => '<th>' + c + '</th>').join('') + '</tr></thead><tbody>'
        + cuerpo.map((f) => '<tr>' + f.map((c) => '<td>' + c + '</td>').join('') + '</tr>').join('') + '</tbody></table></div>';
};
const formato = (t) => t.replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]))
    .replace(/(^\|.*\|[ \t]*\n?)+/gm, (b) => tabla(b))
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/(^|[\s(])\*(?!\s)(.+?)\*(?=[\s.,;:!?)]|$)/gm, '$1<em>$2</em>')
    .replace(/^#{1,6}\s+/gm, '').replace(/^\s*-{3,}\s*$/gm, '<hr>');

// ir al último mensaje: instantáneo al abrir el chat y suave cuando llega uno nuevo (salvo que el sistema pida menos movimiento)
const sinMovimiento = matchMedia('(prefers-reduced-motion: reduce)');
const alFinal = (suave = false) => mensajes.scrollTo({top: mensajes.scrollHeight, behavior: suave && !sinMovimiento.matches ? 'smooth' : 'auto'});
alFinal();
// Algunos navegadores (WebKit) aún no tienen la altura final de la lista al ejecutar el script: se repite al terminar de cargar
// y cuando las tipografías están listas, siempre que la persona no haya empezado a desplazarse ella misma.
let desplazada = false;
['wheel', 'touchstart', 'keydown'].forEach((tipo) => mensajes.addEventListener(tipo, () => { desplazada = true; }, {once: true, passive: true}));
const reajustar = () => { if (!desplazada) alFinal(); };
addEventListener('load', reajustar);
document.fonts?.ready.then(reajustar);

function agregar(quien, html) {
    const fila = document.createElement('div');
    fila.className = 'fila ' + quien;
    fila.innerHTML = (quien === 'bot' ? '<div class="avatar" aria-hidden="true">' + icono + '</div>' : '')
        + '<div class="burbuja"></div>';
    fila.lastElementChild.innerHTML = html;
    hilo.appendChild(fila);
    alFinal(true);
    return fila.lastElementChild;
}

// Efecto de escritura: la respuesta llega completa (y ya revisada por el guardrail de salida de n8n) y aquí se muestra palabra por palabra.
// Dura como máximo ~2 s sea cual sea el largo. Sin animación si la persona pidió menos movimiento, si el texto es corto o si trae una tabla
// (una tabla a medias no se puede dibujar). Mientras escribe, aria-busy evita que el lector de pantalla lea cada fragmento: lee el final.
function escribir(burbuja, texto) {
    if (sinMovimiento.matches || texto.length < 40 || /(^|\n)\s*\|/.test(texto)) { burbuja.innerHTML = formato(texto); return Promise.resolve(); }
    return new Promise((fin) => {
        const paso = Math.max(3, Math.ceil(texto.length / 70));
        const cerca = () => mensajes.scrollHeight - mensajes.scrollTop - mensajes.clientHeight < 140;   // no arrastrar si leyó hacia arriba
        let i = 0;
        mensajes.setAttribute('aria-busy', 'true');
        const tic = () => {
            i = Math.min(texto.length, i + paso);
            while (i < texto.length && !/\s/.test(texto[i])) i++;   // no cortar palabras
            burbuja.innerHTML = formato(texto.slice(0, i));
            if (cerca()) alFinal();
            if (i < texto.length) { setTimeout(tic, 28); return; }
            mensajes.removeAttribute('aria-busy');
            fin();
        };
        tic();
    });
}

// Mientras el asistente trabaja (8 a 10 s) se muestra un texto de progreso. Son mensajes genéricos por tiempo transcurrido: el navegador
// no sabe qué está haciendo n8n, así que no afirman nada concreto.
const estadosEspera = [[3000, 'Buscando la información…'], [9000, 'Preparando la respuesta…'], [22000, 'Esto está tardando más de lo normal…']];

async function enviar(texto) {
    if (boton.disabled) return;
    // sin validación en el navegador: el servidor (Laravel) decide si el mensaje es válido
    document.getElementById('bienvenida')?.remove();   // el saludo inicial deja espacio a la conversación
    campo.value = '';
    campo.style.height = '';
    boton.disabled = true;
    if (texto.trim()) agregar('yo', formato(texto.trim()));
    codigo = texto.match(/\bU\d{8}\b/i)?.[0].toUpperCase() ?? codigo;   // un código nuevo reemplaza al anterior
    const espera = agregar('bot', '<span class="puntos" aria-label="Escribiendo"><i></i><i></i><i></i></span><span class="estado"></span>');
    const temporizadores = estadosEspera.map(([ms, t]) => setTimeout(() => { const e = espera.querySelector('.estado'); if (e) e.textContent = t; }, ms));
    try {
        const r = await fetch(formulario.dataset.url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRF-TOKEN': csrf},
            body: JSON.stringify({mensaje: texto, sesion: formulario.dataset.sesion, codigo}),
        });
        if (r.status === 401 || r.status === 419) { location.reload(); return; }
        if (r.status === 429) throw new Error('Hiciste muchas preguntas seguidas. Espera un minuto y vuelve a intentarlo.');
        const datos = await r.json();
        if (r.status === 422) {  // error de validación de Laravel
            espera.classList.add('error-chat');
            espera.textContent = Object.values(datos.errors ?? {})[0]?.[0] ?? datos.message;
            return;
        }
        temporizadores.forEach(clearTimeout);
        await escribir(espera, datos.respuesta ?? 'No hubo respuesta.');
        const sugerencias = document.getElementById('sugerencias');
        if (codigo) sugerencias.hidden = !sugerencias.querySelector('button');   // ya se identificó: ofrecer las preguntas que aún no usó
    } catch (err) {
        espera.textContent = err.message.startsWith('Hiciste') ? err.message : 'No pude conectarme con el asistente. Intenta de nuevo.';
    } finally {
        temporizadores.forEach(clearTimeout);
        mensajes.removeAttribute('aria-busy');
        boton.disabled = false;
        campo.focus();
        alFinal(true);
    }
}

formulario.addEventListener('submit', (e) => { e.preventDefault(); enviar(campo.value); });
// botones con data-enviar (códigos de demostración y preguntas sugeridas): envían ese texto como si el estudiante lo hubiera escrito
document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-enviar]');
    if (!b || boton.disabled) return;
    enviar(b.dataset.enviar);
    if (b.closest('#sugerencias')) b.remove();   // una pregunta sugerida ya usada no se vuelve a ofrecer
});
// en pantallas táctiles Enter hace salto de línea (se envía con el botón); con teclado físico Enter envía y Mayús+Enter salta
const tactil = matchMedia('(pointer: coarse)');
campo.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !tactil.matches) { e.preventDefault(); enviar(campo.value); }
});
campo.addEventListener('input', () => { campo.style.height = ''; campo.style.height = campo.scrollHeight + 'px'; });
document.getElementById('nuevo').addEventListener('click', () => location.reload());   // la página nueva trae otra sesión y otra memoria
