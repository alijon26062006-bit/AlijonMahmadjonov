// Без интернета и при испорченных данных приложения не падают:
//   * база недоступна — продавец, покупатель и курьер открываются, покупатель видит магазины-примеры;
//   * курьер без сети получает понятное «Нет связи», а не белый экран;
//   * если экран всё-таки сломался — вместо белого экрана «Что-то пошло не так» и «Обновить».
const { chromium } = require('playwright'); const server = require('./server.cjs');
(async () => {
  const srv = await server.start(), R = srv.url, b = await chromium.launch(), errs = [];
  const page = async (lang = 'ru') => {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 } });
    await ctx.route(/supabase\.co|fonts\.g|unpkg|openstreetmap|nominatim/, r => r.abort('internetdisconnected'));
    await ctx.addInitScript(l => localStorage.setItem('zud-lang', l), lang);
    const p = await ctx.newPage(); p.on('pageerror', e => errs.push(p.url() + ': ' + e.message)); return p;
  };
  for (const lang of ['ru', 'tg']) {
    // продавец
    let p = await page(lang); await p.goto(R + 'seller/'); await p.waitForTimeout(500);
    if (!(await p.$('[data-auth]'))) errs.push(`seller ${lang}: welcome not shown`);
    // покупатель: без базы — магазины-примеры
    p = await page(lang); await p.goto(R + 'client/'); await p.click('[data-a="introDone"]');
    await p.fill('#a_street', 'Айни'); await p.fill('#a_house', '7'); await p.click('[data-a="saveAddr"]'); await p.waitForTimeout(1500);
    if ((await p.$$('.big')).length < 2) errs.push(`client ${lang}: demo shops not shown offline`);
    // курьер: вход без сети — понятная ошибка
    p = await page(lang); await p.goto(R + 'courier/'); await p.fill('#phone', '900000001'); await p.click('[data-a="login"]'); await p.waitForTimeout(800);
    const msg = await p.textContent('#loginErr'); if (!msg.trim()) errs.push(`courier ${lang}: no offline message`);
  }
  // испорченные данные в памяти телефона → экран «Что-то пошло не так», а не белый
  const p = await page('ru');
  await p.goto(R + 'client/'); await p.evaluate(() => localStorage.setItem('zud-client-v1', JSON.stringify({ onboarded: true, orders: [{ id: 'broken' }], addresses: [], cart: { items: [] } })));
  await p.reload(); await p.waitForTimeout(900);
  if (!(await p.$('.crash'))) errs.push('client: crash screen not shown for broken data');
  if (!(await p.textContent('.crash')).includes('Обновить')) errs.push('client: crash screen has no reload');
  const saved = await p.evaluate(() => JSON.parse(localStorage.getItem('zud-errors') || '[]').length); if (!saved) errs.push('client: error not recorded');
  await b.close(); srv.close();
  console.log(errs.length ? 'FAIL offline\n' + errs.join('\n') : 'OK offline');
  process.exit(errs.length ? 1 : 0);
})().catch(e => { console.error('FAIL offline', e); process.exit(1); });
