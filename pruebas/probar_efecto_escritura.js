// Prueba del efecto de escritura de sitio-web/public/js/chat.js: extrae formato() y escribir() y las ejecuta con un DOM mínimo simulado.
// Uso (desde la raíz del proyecto): node pruebas/probar_efecto_escritura.js   (necesita Node, sin dependencias)
const fs = require('fs');
const src = fs.readFileSync(process.argv[2] || require('path').join(__dirname, '../sitio-web/public/js/chat.js'), 'utf8');
const toma = (ini, fin) => src.slice(src.indexOf(ini), src.indexOf(fin));
const codigo = toma('const celdas', '// ir al último') + toma('function escribir', 'const estadosEspera');
const mensajes = { scrollHeight: 1000, scrollTop: 900, clientHeight: 100, setAttribute() { this.busy = true; }, removeAttribute() { this.busy = false; } };
const sinMovimiento = { matches: false };
const alFinal = () => {};
const f = new Function('mensajes', 'sinMovimiento', 'alFinal', 'setTimeout', codigo + '; return {formato, escribir};');
let reloj = 0; const rapido = (fn) => { fn(); };
const { formato, escribir } = f(mensajes, sinMovimiento, alFinal, rapido);
const textos = [
  'Andrés, llevas 61 de los 134 créditos del plan, es decir un 45.5 por ciento de avance. Te faltan 73 créditos.\n\nSi mantienes la carga típica, la proyección es de 5 semestres más.',
  'Lista:\n- **CD01** Alfabetización Digital: reprobado\n- CD02 Herramientas: aprobado con *3.3*\n\nSiguiente paso: inscribirte.',
  'Texto con <script>alert(1)</script> y "comillas" & símbolos, suficientemente largo para animarse.',
  '| Semestre | Créditos |\n|---|---|\n| 1 | 16 |\n| 2 | 17 |',
  'Corto',
];
(async () => {
  for (const t of textos) {
    const b = { innerHTML: '', pasos: 0 };
    Object.defineProperty(b, 'innerHTML', { set(v) { this._h = v; this.pasos++; }, get() { return this._h; } });
    await escribir(b, t);
    const esperado = formato(t);
    const ok = b.innerHTML === esperado && !b.innerHTML.includes('<script');
    console.log(ok ? 'OK ' : 'MAL', 'pasos:', String(b.pasos).padStart(3), '| aria-busy final:', mensajes.busy ?? '-', '|', JSON.stringify(t.slice(0, 40)));
    if (!ok) { console.log('   obtenido:', b.innerHTML); console.log('   esperado:', esperado); process.exitCode = 1; }
  }
  // todos los prefijos posibles de cada texto deben renderizar sin lanzar error
  let n = 0;
  for (const t of textos.slice(0, 3)) for (let i = 0; i <= t.length; i++) { formato(t.slice(0, i)); n++; }
  console.log('prefijos renderizados sin error:', n);
})();
