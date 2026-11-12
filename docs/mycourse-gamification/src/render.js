// node render.js [out.pdf] [shotsDir] [pages,csv] — рендер PDF и скриншотов страниц
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  const src = 'file://' + path.join(__dirname, 'presentation.html');
  const out = process.argv[2] || path.join(__dirname, '..', 'PyDoston-mycourse-gamification.pdf');
  const shots = process.argv[3];
  const only = process.argv[4] ? process.argv[4].split(',').map(Number) : null;
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
  p.on('pageerror', e => console.log('PAGEERR', e.message)); p.on('console', m => m.type()==='error' && console.log('CONSOLE', m.text()));
  await p.goto(src);
  await p.waitForSelector('body[data-ready="1"]', { state: 'attached', timeout: 15000 });
  await p.evaluate(() => document.fonts.ready);
  if (shots) {
    fs.mkdirSync(shots, { recursive: true });
    const els = await p.$$('.page');
    for (let i = 0; i < els.length; i++) {
      if (only && !only.includes(i + 1)) continue;
      await els[i].screenshot({ path: path.join(shots, `p${String(i + 1).padStart(2, '0')}.png`) });
    }
  }
  await p.pdf({ path: out, printBackground: true, preferCSSPageSize: true });
  // Проверка: элементы, вылезающие за нижнее поле страницы
  const over = await p.$$eval('.page', ps => ps.map((pg, i) => {
    const r = pg.getBoundingClientRect(); const bad = [];
    pg.querySelectorAll('*').forEach(e => {
      if (e.closest('.foot') || e.closest('svg')) return;
      const q = e.getBoundingClientRect();
      if (q.height && (q.bottom > r.bottom - 36 || q.right > r.right - 20)) bad.push((e.className || e.tagName) + ':' + Math.round(q.bottom - r.bottom) + '/' + Math.round(q.right - r.right));
    });
    return bad.length ? `p${i + 1}: ${bad.slice(0, 5).join(' | ')}` : null;
  }).filter(Boolean));
  if (over.length) console.log('OVERFLOW?\n' + over.join('\n'));
  console.log('PDF ->', out);
  await b.close();
})();
