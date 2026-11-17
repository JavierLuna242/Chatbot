// Captura el chat real (escritorio y móvil) para las imágenes de docs/capturas/ del README. Usa estudiantes sintéticos.
// Uso, desde la carpeta pruebas/:   npm install   y luego   node tomar_capturas.js [url] [carpeta-salida]
//   url por defecto:      https://chatbot.javier.life/chat
//   carpeta por defecto:  ../docs/capturas
//   NAVEGADOR=<ruta>      ejecutable de Edge o Chrome (por defecto, el de Edge en Windows)
// Hace unas 10 preguntas reales, así que gasta cupo de Groq. Si el asistente responde "límite temporal" (cupo agotado) se detiene.
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const url = process.argv[2] || 'https://chatbot.javier.life/chat';
const dir = process.argv[3] || path.join(__dirname, '..', 'docs', 'capturas');
const NAVEGADOR = process.env.NAVEGADOR || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PAUSA = 22000;   // Groq gratis: 8000 tokens por minuto y por modelo

async function esperarRespuesta(p, paso) {
    await p.waitForFunction(() => !document.getElementById('enviar').disabled && !document.querySelector('.fila.bot:last-child .puntos'), null, { timeout: 150000 });
    await p.waitForTimeout(600);
    const texto = await p.locator('.fila.bot .burbuja').last().innerText();
    if (/límite temporal|no está disponible|No pude conectarme/i.test(texto)) throw new Error(`${paso}: el asistente no pudo responder -> ${texto.slice(0, 90)}`);
    return texto;
}

async function foto(p, nombre) {
    await p.evaluate(() => { const m = document.getElementById('mensajes'); m.scrollTo({ top: m.scrollHeight }); });
    await p.waitForTimeout(300);
    await p.screenshot({ path: path.join(dir, `${nombre}.png`) });
    console.log('captura', nombre);
}

async function chip(p, texto, nombre) {
    await p.locator('#sugerencias button', { hasText: texto }).click();
    const r = await esperarRespuesta(p, nombre);
    await foto(p, nombre);
    console.log('   ->', r.replace(/\s+/g, ' ').slice(0, 130));
    await p.waitForTimeout(PAUSA);
}

async function abrir(nav, opciones) {
    const ctx = await nav.newContext({ deviceScaleFactor: 1, reducedMotion: 'reduce', locale: 'es-CO', ...opciones });
    const p = await ctx.newPage();
    await p.goto(url, { waitUntil: 'networkidle' });
    await p.evaluate(() => document.fonts.ready);
    await p.waitForTimeout(500);
    return [ctx, p];
}

(async () => {
    fs.mkdirSync(dir, { recursive: true });
    const nav = await chromium.launch({ executablePath: NAVEGADOR, headless: true });

    // ---- escritorio
    let [ctx, p] = await abrir(nav, { viewport: { width: 1100, height: 720 } });
    await foto(p, '01-bienvenida');
    await p.locator('.bienvenida button', { hasText: 'U00100005' }).click();
    console.log('   ->', (await esperarRespuesta(p, '02-identificacion')).replace(/\s+/g, ' ').slice(0, 130));
    await foto(p, '02-identificacion');
    await p.waitForTimeout(PAUSA);
    await chip(p, 'Mi avance', '03-avance');
    await chip(p, 'Mi promedio', '04-promedio');
    await chip(p, 'Qué materias cursar', '05-materias');
    await p.fill('#mensaje', 'Saqué 3.2 en el primer corte y 2.8 en el segundo. ¿Qué nota necesito en el examen final para aprobar?');
    await p.click('#enviar');
    await esperarRespuesta(p, '06-calculadora');
    await foto(p, '06-calculadora');
    await p.waitForTimeout(PAUSA);
    await chip(p, 'Becas', '07-documentos');
    await chip(p, 'Fechas de inscripción', '08-calendario');
    await p.fill('#mensaje', '¿Cuál es la capital de Francia?');
    await p.click('#enviar');
    await esperarRespuesta(p, '09-fuera-de-tema');
    await foto(p, '09-fuera-de-tema');
    await ctx.close();

    // ---- móvil (otro estudiante)
    await new Promise((r) => setTimeout(r, PAUSA));
    [ctx, p] = await abrir(nav, { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    await p.fill('#mensaje', 'U00100018');
    await p.click('#enviar');
    await esperarRespuesta(p, '10-movil (identificación)');
    await p.waitForTimeout(PAUSA);
    await chip(p, 'Mi promedio', '10-movil');
    await ctx.close();
    await nav.close();
    console.log('LISTO');
})().catch((e) => { console.error('ABORTADO:', e.message); process.exit(1); });
