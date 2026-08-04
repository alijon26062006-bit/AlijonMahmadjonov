import fs from 'node:fs';
import path from 'node:path';

const SITE = '/home/user/AlijonMahmadjonov/site';
const read = (p) => fs.readFileSync(path.join(SITE, p), 'utf8');

/* ---------- 1. Three.js: ESM -> одна константа ---------- */
function bundleThree() {
  const src = read('js/three.module.min.js').replace(/\/\/# sourceMappingURL=.*$/gm, '');
  const m = src.match(/export\{([^}]*)\};?/);
  if (!m) throw new Error('three: export не найден');
  const pairs = m[1].split(',').map((s) => {
    const [local, exported] = s.split(' as ').map((x) => x.trim());
    return `${exported || local}:${local}`;
  });
  return `const THREE=(()=>{${src.slice(0, m.index)}\nreturn{${pairs.join(',')}};})();`;
}

/* ---------- 2. Lenis ---------- */
function bundleLenis() {
  const src = read('js/lenis.mjs').replace(/\/\/# sourceMappingURL=.*$/gm, '');
  const m = src.match(/export\s*\{\s*(\w+)\s+as\s+default\s*\}\s*;?/);
  if (!m) throw new Error('lenis: export не найден');
  return `const Lenis=(()=>{${src.slice(0, m.index)}\nreturn ${m[1]};})();`;
}

/* ---------- 3. Постобработка: каждый модуль в своей области ----------
   Отдельная IIFE на модуль нужна потому, что разные модули достают из
   THREE одни и те же имена — в общей области это была бы ошибка
   повторного объявления const. */
const PP_ORDER = [
  'js/postprocessing/Pass.js',
  'js/shaders/CopyShader.js',
  'js/shaders/LuminosityHighPassShader.js',
  'js/shaders/OutputShader.js',
  'js/postprocessing/ShaderPass.js',
  'js/postprocessing/MaskPass.js',
  'js/postprocessing/RenderPass.js',
  'js/postprocessing/UnrealBloomPass.js',
  'js/postprocessing/OutputPass.js',
  'js/postprocessing/EffectComposer.js',
];

function bundlePostprocessing() {
  const names = (block) =>
    block.split(',').map((s) => s.trim()).filter(Boolean)
      .map((s) => (s.includes(' as ') ? s.split(' as ')[1].trim() : s));

  const parts = PP_ORDER.map((file) => {
    let src = read(file);

    const threeImport = src.match(/import\s*\{([\s\S]*?)\}\s*from\s*['"]three['"];?/);
    const threeNames = threeImport ? names(threeImport[1]) : [];

    const relNames = [];
    src.replace(/import\s*\{([^}]*)\}\s*from\s*['"]\.[^'"]*['"];?/g, (_, block) => {
      relNames.push(...names(block));
      return '';
    });

    const exportMatch = src.match(/export\s*\{([^}]*)\}\s*;?/);
    const exportNames = exportMatch ? names(exportMatch[1]) : [];

    // вырезаем все import и export
    src = src
      .replace(/import\s*\{[\s\S]*?\}\s*from\s*['"][^'"]*['"];?/g, '')
      .replace(/export\s*\{[^}]*\}\s*;?/g, '');

    const head = [
      threeNames.length ? `const {${threeNames.join(',')}}=THREE;` : '',
      relNames.length ? `const {${[...new Set(relNames)].join(',')}}=PP;` : '',
    ].join('');

    return `(()=>{${head}${src}\nObject.assign(PP,{${exportNames.join(',')}});})();`;
  });

  return `const PP={};${parts.join('')}\nconst {EffectComposer,RenderPass,UnrealBloomPass,OutputPass}=PP;`;
}

/* ---------- 4. Свой код ---------- */
function bundleApp() {
  const strip = (src) =>
    src
      .replace(/^import[\s\S]*?from\s*['"][^'"]*['"];?\s*$/gm, '')
      .replace(/^import\s+\w+\s+from\s*['"][^'"]*['"];?\s*$/gm, '')
      .replace(/^export\s+(const|function|let|class)\s/gm, '$1 ');

  const config = strip(read('config.js'));
  const lang = strip(read('lang.js'));
  // scene.js обращается к настройкам качества под именем sceneConfig
  const scene = strip(read('js/scene.js'));
  const app = strip(read('js/app.js'));

  return [
    config,
    // в одном файле заявка уходит на этот же адрес, обрабатывает её PHP сверху
    `orderTarget.mode='php';orderTarget.phpEndpoint='';`,
    lang,
    `const sceneConfig=scene;`,
    scene,
    app,
    `initApp();initScene(document.getElementById('gl'));`,
  ].join('\n');
}

/* ---------- 5. Стили со встроенными шрифтами ---------- */
function bundleCss() {
  let css = read('style.css');
  let inlined = 0;
  css = css.replace(/url\('fonts\/([^']+)'\)/g, (_, name) => {
    const data = fs.readFileSync(path.join(SITE, 'fonts', name)).toString('base64');
    inlined++;
    return `url(data:font/woff2;base64,${data})`;
  });
  console.log('шрифтов встроено:', inlined);
  return css;
}

/* ---------- 6. Разметка ---------- */
function bundleMarkup() {
  const html = read('index.html');
  let body = html.slice(html.indexOf('<body>') + 6, html.indexOf('</body>'));
  // убираем подключение модулей — весь код будет встроен ниже
  body = body.replace(/<script type="module">[\s\S]*?<\/script>/g, '');
  return body.trim();
}

/* ---------- сборка ---------- */
const js = [bundleThree(), bundleLenis(), bundlePostprocessing(), bundleApp()].join('\n');
// строка </script> внутри кода закрыла бы тег раньше времени
const safeJs = js.replace(/<\/script>/g, '<\\/script>');

const php = `${fs.readFileSync('/home/user/AlijonMahmadjonov/site-php/_header.php', 'utf8')}
<style>
${bundleCss()}
</style>
</head>
<body>

${bundleMarkup()}

<script>
${safeJs}
</script>
</body>
</html>
`;

fs.mkdirSync('/home/user/AlijonMahmadjonov/site-php', { recursive: true });
fs.writeFileSync('/home/user/AlijonMahmadjonov/site-php/index.php', php);
console.log('index.php:', (php.length / 1024 / 1024).toFixed(2), 'MB');
