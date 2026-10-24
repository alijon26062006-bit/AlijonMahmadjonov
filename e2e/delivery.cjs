// Три телефона: продавец, покупатель, курьер — весь путь заказа через общую базу (мини-Supabase в браузере).
// Запуск: node e2e/delivery.cjs [ru|tg]. Снимки экранов — в e2e/report/. Код выхода 1, если что-то не так.
const fs = require('fs'); const { chromium } = require('playwright'); const server = require('./server.cjs');
const MOCK = fs.readFileSync(__dirname + '/mock-supabase.js', 'utf8'), LANG = process.argv[2] || 'ru', OUT = __dirname + '/report/delivery-' + LANG;
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const srv = await server.start(), R = srv.url;
  const b = await chromium.launch(); const errs = [];
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, colorScheme: process.env.DARK ? 'dark' : 'light', geolocation: { latitude: 43.2395, longitude: 76.8905 }, permissions: ['geolocation'] });
  await ctx.route(/supabase\.co|fonts\.g|unpkg|openstreetmap/, r => r.abort());
  await ctx.addInitScript(MOCK); await ctx.addInitScript(l => { if (!localStorage.getItem('zud-lang')) localStorage.setItem('zud-lang', l); }, LANG);
  const sp = await ctx.newPage(), cp = await ctx.newPage(), kp = await ctx.newPage();
  for (const [p, n] of [[sp, 'seller'], [cp, 'client'], [kp, 'courier']]) { p.on('pageerror', e => errs.push(n + ': ' + e.message)); p.on('console', m => m.type() === 'error' && !/ERR_|fonts|Failed to load/.test(m.text()) && errs.push(n + ' console: ' + m.text())); }
  const DB = () => sp.evaluate(() => JSON.parse(localStorage.getItem('__mockdb')));
  const RU = new Map();
  // русский текст узнаём по буквам, которых нет в таджикском алфавите: ы, щ, ь, ц
  const scan = async (p, n) => { if (LANG !== 'tg') return; for (const t of await p.evaluate(() => { const out = []; const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); for (let x = tw.nextNode(); x; x = tw.nextNode()) { if (x.parentElement.closest('[translate="no"],script,style')) continue; const v = x.nodeValue.trim(); if (/[ыщьц]/i.test(v)) out.push(v); } document.querySelectorAll('[placeholder],[aria-label]').forEach(e => { if (e.closest('[translate="no"]')) return; for (const a of ['placeholder', 'aria-label']) { const v = e.getAttribute(a); if (v && /[ыщьц]/i.test(v)) out.push('@' + v); } }); return out; })) RU.set(n + ': ' + t, 1); };
  const slide = async (p, label) => { const k = p.locator('.slide-knob'); if (LANG === 'ru' && label && !(await p.textContent('.slide-label')).includes(label)) errs.push(`slider label "${await p.textContent('.slide-label')}" not "${label}"`); await k.focus(); await k.press('Enter'); await p.waitForTimeout(700); };
  // ---- продавец ----
  await sp.goto(R + 'seller/index.html'); await sp.evaluate(() => localStorage.clear()); await sp.evaluate(() => localStorage.setItem('zud-lang', 'ru')); await sp.reload();
  await sp.click('[data-auth="skip"]'); await sp.check('#agIn'); await sp.fill('#phoneIn', '901234567'); await sp.click('#phoneForm button[type=submit]');
  await sp.fill('#codeIn', (await sp.textContent('.testnote b')).trim()); await sp.waitForTimeout(300);
  await sp.click('[data-reg-kind="grocery"]'); await sp.click('[data-reg="next"]');
  await sp.fill('#r_name', 'Бозори Сабз'); await sp.fill('#r_phone', '935551234'); await sp.click('[data-reg="next"]');
  await sp.waitForTimeout(1200); await sp.fill('#r_city', 'Алматы'); await sp.fill('#r_address', 'Абая, 1'); await sp.click('[data-reg="next"]'); await sp.click('[data-reg="next"]');
  await sp.click('[data-reg="create"]'); await sp.waitForTimeout(300);
  for (const [nm, pr] of [['Помидоры местные', '12'], ['Огурцы', '10']]) {
    await sp.click('[data-act="add"]:visible'); await sp.waitForTimeout(200); await sp.fill('#p_name', nm); await sp.click('[data-pnav="1"]'); await sp.click('[data-pnav="1"]');
    await sp.fill('#p_price', pr); await sp.fill('#p_stock', '30'); await sp.click('[data-pnav="1"]'); await sp.check('#p_ok'); await sp.click('[data-act="saveP"]'); await sp.waitForTimeout(300);
  }
  await sp.waitForTimeout(1500);
  // точка магазина на карте (в тесте карта не грузится — ставим как будто продавец отметил её): Алматы, проспект Абая
  await sp.evaluate(() => { const d = JSON.parse(localStorage.getItem('__mockdb')); Object.assign(d.t.shops[0], { lat: 43.2389, lng: 76.8897 }); localStorage.setItem('__mockdb', JSON.stringify(d)); });
  await sp.evaluate(l => localStorage.setItem('zud-lang', l), LANG);   // покупатель и курьер — на проверяемом языке
  // ---- курьер выходит на линию ----
  await kp.goto(R + 'courier/'); await kp.fill('#phone', '900000001'); await kp.click('[data-a="login"]'); await kp.waitForTimeout(500);
  await kp.fill('#r_name', 'Алишер'); await kp.fill('#r_car', 'Opel Astra, белый'); await kp.fill('#r_plate', '01 123 aa'); await kp.click('[data-a="saveMe"]'); await kp.waitForTimeout(500);
  await kp.click('.switch-big'); await kp.waitForTimeout(700);
  if (!(await kp.$('.radar-card'))) errs.push('courier: no radar while waiting');
  // ---- покупатель заказывает наличными ----
  await cp.goto(R + 'client/'); await cp.click('[data-a="introDone"]'); await cp.fill('#a_city', 'Алматы'); await cp.fill('#a_street', 'Абая'); await cp.fill('#a_house', '10'); await cp.click('[data-a="saveAddr"]');
  await cp.waitForTimeout(600); const sid = (await DB()).t.shops[0].id;
  await cp.click(`.big-pic[data-go="#/shop/${sid}"]`); await cp.waitForTimeout(300);
  for (let k = 0; k < 4; k++) await cp.click('.card:has-text("Помидоры местные") [data-a="plus"]');
  await cp.click('.card:has-text("Огурцы") [data-a="plus"]');
  await cp.goto(R + 'client/#/checkout'); await cp.waitForTimeout(300); await cp.click('[data-a="pay"][value="cash"]');
  await cp.click('[data-a="placeOrder"]'); await cp.fill('#lgName', 'Мадина'); await cp.fill('#lgPhone', '935550011'); await cp.click('[data-a="sendCode"]');
  await cp.fill('#lgCode', (await cp.textContent('.notice b')).trim()); await cp.waitForTimeout(900);
  // ---- курьер не видит заказ, пока магазин не принял ----
  await kp.waitForTimeout(4500); if (await kp.$('.offer')) errs.push('courier sees order before shop accepted');
  // ---- продавец принимает ----
  await sp.click('.tabs [data-nav="orders"]'); await sp.waitForTimeout(300);
  await sp.click('.order:has-text("Мадина") [data-oact="accept"]'); await sp.click('[data-accmin="20"]'); await sp.waitForTimeout(1500);
  // ---- курьеру приходит заказ ----
  await kp.waitForTimeout(5000);
  const offer = await kp.textContent('.offers').catch(() => ''); if (!offer.includes('Бозори Сабз')) errs.push('courier: offer not shown: ' + offer.slice(0, 80));
  await scan(kp, 'courier'); await kp.screenshot({ path: OUT + '/k1-offer.png', fullPage: true });
  await kp.evaluate(() => { window.__opened = []; addEventListener('zud:open', e => window.__opened.push(e.detail)); });
  await kp.click('[data-a="take"]'); await kp.waitForTimeout(700);
  // карта никогда не пустая молча: либо улицы загрузились, либо видна понятная надпись (источники перебираются сами)
  await kp.waitForTimeout(2500);
  const mapOk = await kp.evaluate(() => !!document.querySelector('#map-layer .leaflet-tile-loaded') || !!document.querySelector('#map-layer.nomap .nomap-note'));
  if (!mapOk) errs.push('courier: map is blank without explanation');
  // взял заказ — 2GIS сам строит путь до магазина
  const opened1 = await kp.evaluate(() => window.__opened); if (!opened1.includes('dgis://2gis.ru/routeSearch/rsType/car/to/76.8897,43.2389')) errs.push('courier: 2GIS route to shop not opened: ' + opened1);
  await scan(kp, 'courier'); await kp.screenshot({ path: OUT + '/k2-to-shop.png', fullPage: true });
  if (!(await kp.textContent('.order-no')).includes(String((await DB()).t.orders[0].no))) errs.push('courier: order number not shown');
  // ---- покупатель и продавец видят курьера ----
  await cp.waitForTimeout(5500);
  const ctext = await cp.textContent('main'); if (!ctext.includes('Алишер') || !ctext.includes('01 123 AA')) errs.push('client: no courier card');
  const code = (await cp.textContent('.code-card .code')).trim(); if (!/^\d{4}$/.test(code)) errs.push('client: no code ' + code);
  await scan(cp, 'client'); await cp.screenshot({ path: OUT + '/c1-courier-going.png', fullPage: true });
  await sp.waitForTimeout(1500); await sp.click('.tabs [data-nav="orders"]'); await sp.waitForTimeout(300); await sp.click('[data-otab="work"]').catch(() => {}); await sp.waitForTimeout(300);
  if (!/Курьер едет к вам|Курйер ба назди шумо меояд/.test(await sp.textContent('main'))) errs.push('seller: no courier line');
  await scan(sp, 'seller'); await sp.screenshot({ path: OUT + '/s1-courier-line.png', fullPage: false });
  // ---- курьер: в магазине → забрал (магазин ещё не нажал «Готов» → подтверждение) ----
  await slide(kp, 'Я в магазине');
  await kp.click('[data-a="tick"] >> nth=0'); await scan(kp, 'courier'); await kp.screenshot({ path: OUT + '/k3-at-shop.png', fullPage: true });
  await slide(kp, 'Забрал заказ'); await kp.waitForTimeout(200);
  if (!(await kp.$('[data-a="pickAnyway"]'))) errs.push('courier: no confirm when shop not ready'); else await kp.click('[data-a="pickAnyway"]');
  await kp.waitForTimeout(700); await scan(kp, 'courier'); await kp.screenshot({ path: OUT + '/k4-to-client.png', fullPage: true });
  // забрал — 2GIS сам строит путь до покупателя
  const opened2 = await kp.evaluate(() => window.__opened || []); console.log('2GIS:', opened2.join('  |  ')); if (opened2.length < 2) errs.push('courier: 2GIS route to client not opened: ' + opened2);
  if (!(await kp.textContent('.ir-v.cash')).includes('смн')) errs.push('courier: no cash box');
  await cp.waitForTimeout(5500); if (LANG === 'ru' && !(await cp.textContent('h1')).includes('Курьер в пути')) errs.push('client: not in transit: ' + await cp.textContent('h1'));
  // ---- у двери: неверный код, потом верный ----
  await slide(kp, 'Я у покупателя');
  await kp.fill('#code', '0000'); await slide(kp, 'Передал заказ');
  if (!(await kp.$('.done-screen'))) { /* ожидаемо: код не подошёл */ } else errs.push('courier: wrong code accepted');
  await kp.fill('#code', code); await scan(kp, 'courier'); await kp.screenshot({ path: OUT + '/k5-code.png', fullPage: true }); await slide(kp, 'Передал заказ');
  await kp.waitForTimeout(500);
  if (!(await kp.$('.done-screen'))) errs.push('courier: no done screen'); await scan(kp, 'courier'); await kp.screenshot({ path: OUT + '/k6-done.png', fullPage: true });
  // ---- покупатель: доставлен, оценивает курьера ----
  await cp.waitForTimeout(5500); if (LANG === 'ru' && !(await cp.textContent('h1')).includes('доставлен')) errs.push('client: not delivered: ' + await cp.textContent('h1'));
  await cp.click('[data-a="rateCourier"][data-v="5"]'); await cp.waitForTimeout(500); await scan(cp, 'client'); await cp.screenshot({ path: OUT + '/c2-delivered.png', fullPage: true });
  const db = await DB(); const o = db.t.orders[0];
  console.log('db order', o.no, o.status, o.courier_status, 'cash', o.cash_taken, 'fee', o.courier_fee, 'received', !!o.received_at, 'courier rating', db.t.couriers[0].rating, db.t.couriers[0].rating_count);
  if (o.courier_status !== 'delivered' || !o.received_at || o.cash_taken !== o.total) errs.push('db final state wrong');
  if (db.t.couriers[0].rating !== 5) errs.push('courier rating not saved');
  // ---- курьер: доход ----
  await kp.click('[data-a="doneOk"]'); await kp.waitForTimeout(300); await scan(kp, 'courier'); await kp.screenshot({ path: OUT + '/k7-shift-after.png', fullPage: true });
  await kp.click('.tab[data-go="#/money"]'); await kp.waitForTimeout(600); await scan(kp, 'courier'); await kp.screenshot({ path: OUT + '/k8-money.png', fullPage: true });
  if (!(await kp.textContent('.earn-hero')).includes('15')) errs.push('courier money: earn missing');
  for (const [p, n] of [[sp, 'seller'], [cp, 'client'], [kp, 'courier']]) { const ov = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth); if (ov > 0) errs.push(n + ' overflow ' + ov); }
  // перевод: русские фразы, которые остались на экране (кабинет продавца в этом тесте специально на русском, данные магазина не переводятся)
  const left = [...RU.keys()].filter(k => !k.startsWith('seller:') && !/×|Алматы|Помидоры|Огурцы/.test(k));
  if (left.length) errs.push('не переведено:\n  ' + left.join('\n  '));
  await b.close(); srv.close();
  console.log(errs.length ? 'FAIL delivery ' + LANG + '\n' + errs.join('\n') : 'OK delivery ' + LANG);
  process.exit(errs.length ? 1 : 0);
})().catch(e => { console.error('FAIL delivery', e); process.exit(1); });
