// Dibuja los flujos de n8n del proyecto con el componente oficial n8n-demo y guarda su imagen en docs/capturas/n8n-*.png.
// Uso, desde la carpeta pruebas/:   npm install   y luego   node capturar_flujos_n8n.js
//   NAVEGADOR=<ruta>  ejecutable de Edge o Chrome (por defecto, el de Edge en Windows)
//
// Importante: NO es una captura de tu instancia de n8n Cloud (esa exige iniciar sesión). Es el mismo lienzo de n8n dibujado a partir de los
// archivos de flujos-n8n/flujos/. Para ello el JSON del flujo (sin el id del webhook; las credenciales son solo nombres de ejemplo) viaja al
// servicio de vista previa que n8n aloja para este componente (n8n-preview-service.internal.n8n.cloud). Requiere internet.
const { chromium } = require('playwright-core');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { pathToFileURL } = require('url');

const NAVEGADOR = process.env.NAVEGADOR || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const FLUJOS = path.join(__dirname, '..', 'flujos-n8n', 'flujos');
const SALIDA = path.join(__dirname, '..', 'docs', 'capturas');
const VISTAS = [   // archivo, imagen, ancho y alto de la vista
    ['chatbot_academico.json', 'n8n-01-chatbot.png', 1600, 900],
    ['ingesta_documentos.json', 'n8n-02-ingesta.png', 1400, 620],
    ['noticias_unab.json', 'n8n-03-noticias.png', 1400, 420],
    ['evaluacion_rag.json', 'n8n-04-evaluacion-rag.png', 1400, 760],
];
const PAGINA = `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#fff}n8n-demo{display:block}</style>
<script type="module" src="https://cdn.jsdelivr.net/npm/@n8n_io/n8n-demo-component@1.0.20/n8n-demo.bundled.js"></script></head>
<body><n8n-demo id="d" frame="false" clicktointeract="false" hidecanvaserrors="true" collapseformobile="false" theme="light"></n8n-demo></body></html>`;

(async () => {
    fs.mkdirSync(SALIDA, { recursive: true });
    const pagina = path.join(os.tmpdir(), 'vista_flujo_n8n.html');
    fs.writeFileSync(pagina, PAGINA);
    const nav = await chromium.launch({ executablePath: NAVEGADOR, headless: true });
    for (const [archivo, imagen, ancho, alto] of VISTAS) {
        const flujo = JSON.parse(fs.readFileSync(path.join(FLUJOS, archivo), 'utf8'));
        for (const n of flujo.nodes) delete n.webhookId;
        delete flujo.id; delete flujo.active;
        const p = await nav.newPage({ viewport: { width: ancho, height: alto }, deviceScaleFactor: 2 });
        await p.goto(pathToFileURL(pagina).href);
        await p.waitForSelector('n8n-demo');
        await p.evaluate((w) => document.getElementById('d').setAttribute('workflow', JSON.stringify(w)), flujo);
        await p.waitForTimeout(12000);
        // el lienzo vive en un iframe dentro del shadow DOM del componente: se agranda a toda la vista
        await p.evaluate((h) => {
            const f = document.getElementById('d').shadowRoot.querySelector('iframe');
            f.style.height = h + 'px'; f.style.width = '100%'; f.parentElement.style.height = h + 'px';
        }, alto);
        await p.waitForTimeout(2500);
        const marco = p.frames().find((f) => f !== p.mainFrame());
        await marco.addStyleTag({ content: '[data-test-id="node-issues"]{display:none!important}' });   // triángulos de «faltan credenciales»
        await marco.locator('[data-test-id="zoom-to-fit"]').click();
        await marco.evaluate(() => {   // panel de zoom: se oculta el contenedor de los botones de acercar, alejar y encuadrar
            document.querySelectorAll('[data-test-id^="zoom-"]').forEach((b) => { b.parentElement.parentElement.style.display = 'none'; });
        });
        await p.waitForTimeout(2500);
        await p.screenshot({ path: path.join(SALIDA, imagen) });
        console.log('captura', imagen);
        await p.close();
    }
    await nav.close();
    console.log('LISTO');
})().catch((e) => { console.error('ERROR:', e.message); process.exit(1); });
