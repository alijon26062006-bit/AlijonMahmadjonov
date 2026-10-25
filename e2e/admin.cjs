// Админ-панель в браузере: вход, каждый экран открывается без ошибок, связи между карточками, действия спрашивают причину.
// База подменена: функции admin_* отвечают готовыми данными, действия записываются — проверяем, что ушло в базу.
//   node e2e/admin.cjs            — телефон и компьютер
//   node e2e/admin.cjs shots      — ещё и снимки экранов в e2e/report/
const { chromium } = require('playwright'); const server = require('./server.cjs'); const fs = require('fs'); const path = require('path');

const SHOTS = process.argv.includes('shots');
const OUT = path.join(__dirname, 'report');

// ---------- данные «базы» ----------
function mock() {
  const iso = m => new Date(Date.now() - m * 60e3).toISOString();
  const shop = { id: 's1', name: 'Бозори Сабз', kind: 'grocery', city: 'Шахритус', address: 'Айни 7', phone: '900000010', logo: '', paused: false, blocked: false, block_reason: '',
    rating: 4.6, rating_count: 12, has_pin: true, created_at: iso(9000), owner: { id: 'u1', phone: '900000010', name: '' }, staff: 1, products: 3, products_live: 2, orders_30d: 14, revenue_30d: 2450, active: 2 };
  const order = { id: 'o1', no: 1042, status: 'ready', step: null, source: 'app', delivery: 'courier', shop: { id: 's1', name: shop.name }, buyer_id: 'u2',
    customer: { name: 'Мадина', phone: '+992 935550011', address: 'Шахритус, Айни, д. 10' }, courier_id: null, courier: null, sum: 120, fee: 15, total: 135, courier_fee: null,
    pay: 'cash', items: 2, created_at: iso(35), accepted_at: iso(30), problem: null, cancel_reason: '' };
  const DATA = {
    admin_me: { id: 'a1', email: 'owner@example.com', admin: true },
    admin_overview: { users: 7, users_today: 1, buyers: 3, shops: 2, shops_open: 1, products: 5, products_live: 3, couriers: 2, couriers_online: 1, admins: 1, blocked: 1,
      orders_today: 4, orders_7d: 20, gmv_today: 540, gmv_7d: 3100, fees_7d: 300, courier_pay_7d: 300, cancelled_7d: 2, active: 2, problems: 1, complaints: 1,
      by_status: { new: 1, ready: 1, done: 15, cancelled: 2 }, days: Array.from({ length: 14 }, (_, i) => ({ d: new Date(Date.now() - (13 - i) * 864e5).toISOString().slice(0, 10), orders: i % 4, total: i * 50, cancelled: i % 5 === 0 ? 1 : 0 })) },
    admin_checks: [
      { level: 'high', kind: 'no_courier', title: 'Нет курьера: заказ № 1042', text: 'Магазин принял заказ 30 мин назад, ни один курьер его не взял. Курьеров на линии: 1', target: { kind: 'order', id: 'o1' }, at: iso(35) },
      { level: 'mid', kind: 'courier_lost', title: 'Курьер без связи: Алишер', text: 'Место не обновлялось 22 мин', target: { kind: 'user', id: 'u3' }, at: iso(22) },
      { level: 'low', kind: 'no_phone', title: 'Магазин без телефона: Сафо', text: 'Курьер и покупатель не смогут позвонить в магазин', target: { kind: 'shop', id: 's2' }, at: iso(9000) }],
    admin_users: [
      { id: 'u1', phone: '900000010', email: '992900000010@zud.tj', name: 'Фируза', created_at: iso(9000), last_at: iso(5), roles: ['seller', 'buyer'], blocked: false, shop: { id: 's1', name: shop.name, blocked: false }, courier: null, orders: 2 },
      { id: 'u2', phone: '935550011', email: '992935550011@zud.tj', name: 'Мадина', created_at: iso(5000), last_at: iso(40), roles: ['buyer'], blocked: false, shop: null, courier: null, orders: 6 },
      { id: 'u3', phone: '900000001', email: '992900000001@zud.tj', name: 'Алишер', created_at: iso(3000), last_at: iso(22), roles: ['courier'], blocked: false, shop: null, courier: { status: 'active', online: true }, orders: 0 },
      { id: 'u4', phone: '900000099', email: '992900000099@zud.tj', name: 'Фарход', created_at: iso(2000), last_at: iso(100), roles: ['staff'], blocked: false, shop: null, courier: null, orders: 0 },
      { id: 'a1', phone: null, email: 'owner@example.com', name: '', created_at: iso(10000), last_at: iso(1), roles: ['admin'], blocked: false, shop: null, courier: null, orders: 0 }],
    admin_user: { id: 'u1', phone: '900000010', email: '992900000010@zud.tj', name: 'Фируза', created_at: iso(9000), last_at: iso(5), roles: ['seller', 'buyer'], block: null, admin: null,
      shop: { id: 's1', name: shop.name, kind: 'grocery', city: 'Шахритус', paused: false, blocked: false }, staff_in: [{ shop_id: 's2', shop: 'Сафо', role: 'manager', name: 'Фируза' }],
      courier: null, orders: [order], deliveries: [], reviews: [{ id: 'r9', shop: 'Сафо', shop_id: 's2', order_no: 1003, rating: 5, text: 'Быстро', created_at: iso(3000) }],
      stats: { orders: 2, spent: 270, cancelled: 0, problems: 0, deliveries: 0, earned: 0 }, log: [{ at: iso(60), action: 'shop_unblock', note: '', by: 'owner@example.com' }] },
    admin_shops: [shop, { ...shop, id: 's2', name: 'Сафо', phone: '', blocked: true, block_reason: 'Продаёт без документов', has_pin: false, active: 0 }],
    admin_shop: { shop: { ...shop, lat: 37.267, lng: 68.133, landmark: 'у рынка', min_order: 10, prep_min: 25, delivery: true, pickup: true }, owner: shop.owner,
      staff: [{ id: 'st1', name: 'Фарход', phone: '900000099', role: 'picker', user: { id: 'u4', phone: '900000099', name: 'Фарход' } }, { id: 'st2', name: 'Зарина', phone: '900000077', role: 'cashier', user: null }],
      alif: { status: 'none' },
      products: [{ id: 'p1', sku: 100001, name: 'Помидоры', cat: 'Овощи', price: 12, unit: 'кг', stock: 38, active: true, blocked: false, block_reason: '', img: null, expiry: null },
        { id: 'p2', sku: 100002, name: 'Сыр', cat: 'Молочное', price: 60, unit: 'кг', stock: 0, active: true, blocked: true, block_reason: 'Нет сертификата', img: null, expiry: '2026-01-01' }],
      orders: [order], reviews: [{ id: 'r1', name: 'Мадина', rating: 2, text: 'Помидоры мятые', order_no: 1040, created_at: iso(800), complaint: { reason: 'Неправда', status: 'review' } }],
      stats: { orders: 30, app_orders: 22, shop_sales: 8, revenue: 4100, cancelled: 2, expenses_30d: 300, avg_accept_min: 3.4 }, log: [] },
    admin_products: [{ id: 'p1', sku: 100001, name: 'Помидоры', cat: 'Овощи', price: 12, unit: 'кг', stock: 38, active: true, blocked: false, block_reason: '', img: null, shop: { id: 's1', name: shop.name } }],
    admin_orders: [order, { ...order, id: 'o2', no: 1041, status: 'done', step: 'delivered', courier: 'Алишер', courier_id: 'u3', received_at: iso(100), created_at: iso(160) },
      { ...order, id: 'o3', no: 1039, status: 'cancelled', cancel_reason: 'Покупатель отменил заказ', created_at: iso(300) }],
    admin_order: { order: { ...order, courier_status: null, customer: { ...order.customer, addr: {} }, items: [{ pid: 'p1', sku: 100001, name: 'Помидоры', unit: 'кг', qty: 2, price: 12, opts: [] },
        { pid: 'p3', sku: 100003, name: 'Хлеб', unit: 'шт', qty: 4, price: 24, opts: [], missing: true }], comment: 'Позвоните у подъезда', if_missing: 'replace', km: 1.8, updated_at: iso(30) },
      buyer: { id: 'u2', phone: '935550011', name: 'Мадина' }, courier_user: null, shop: { id: 's1', name: shop.name, phone: '900000010', address: 'Айни 7', owner: { id: 'u1', phone: '900000010', name: 'Фируза' } },
      code: null, costs: [8, null], review: null, log: [] },
    admin_couriers: [{ id: 'u3', name: 'Алишер', phone: '+992 900000001', car: 'Opel Astra, белый', plate: '01 123 AA', status: 'active', block_reason: '', online: true, lat: 37.27, lng: 68.14, loc_at: iso(22),
      rating: 4.9, rating_count: 31, created_at: iso(3000), account: { id: 'u3' }, job: null, done_7d: 12, earned_7d: 210, cash_today: 135, returned: 0 }],
    admin_map: { couriers: [{ id: 'u3', name: 'Алишер', lat: 37.27, lng: 68.14, loc_at: iso(1), busy: false }], shops: [{ id: 's1', name: shop.name, lat: 37.267, lng: 68.133, paused: false, blocked: false }],
      orders: [{ id: 'o1', no: 1042, status: 'ready', step: null, courier_id: null, shop_lat: 37.267, shop_lng: 68.133, to_lat: 37.26, to_lng: 68.12 }] },
    admin_reviews: [{ id: 'r1', name: 'Мадина', rating: 2, text: 'Помидоры мятые', tags: [], order_no: 1040, created_at: iso(800), complaint: { reason: 'Неправда', status: 'review' },
      shop: { id: 's1', name: shop.name }, buyer: { id: 'u2', phone: '935550011', name: 'Мадина' } }],
    admin_log: [{ id: 1, at: iso(60), by: 'owner@example.com', action: 'shop_block', kind: 'shop', target: 's2', note: 'Продаёт без документов', data: {} }],
    admin_system: { admins: [{ id: 'a1', email: 'owner@example.com', note: 'владелец', added_at: iso(10000), me: true }], zone_open: true, courier_share: 1, courier_radius: 15 },
  };
  const calls = []; window.__calls = calls;
  let session = JSON.parse(localStorage.getItem('mock-session') || 'null');
  window.__SUPABASE_MOCK__ = {
    createClient: () => ({
      auth: {
        getSession: async () => ({ data: { session } }),
        signInWithPassword: async ({ email, password }) => {
          if (password !== 'correct-horse') return { error: { message: 'Invalid login credentials' } };
          session = { user: { email } }; localStorage.setItem('mock-session', JSON.stringify(session)); return { data: { session } };
        },
        signOut: async () => { session = null; localStorage.removeItem('mock-session'); return {}; },
      },
      rpc: async (fn, args) => {
        calls.push({ fn, args });
        if (fn === 'admin_me') return { data: { ...DATA.admin_me, email: session?.user?.email, admin: session?.user?.email === 'owner@example.com' } };
        if (fn in DATA) return { data: DATA[fn] };
        if (fn.startsWith('admin_')) return { data: null };   // действие
        return { error: { message: 'unknown ' + fn } };
      },
    }),
  };
}

(async () => {
  const srv = await server.start(), R = srv.url + 'admin/', b = await chromium.launch(), errs = [];
  if (SHOTS) fs.mkdirSync(OUT, { recursive: true });
  const fail = m => errs.push(m);
  for (const [label, viewport] of [['phone', { width: 390, height: 844 }], ['desktop', { width: 1366, height: 860 }]]) {
    const ctx = await b.newContext({ viewport });
    await ctx.route(/supabase\.co|fonts\.g|openstreetmap|unpkg/, r => r.abort('internetdisconnected'));
    await ctx.addInitScript(mock);
    const p = await ctx.newPage();
    p.on('pageerror', e => fail(`${label}: ${e.message}`));
    p.on('console', m => { if (m.type() === 'error' && !/Failed to load resource|ERR_INTERNET_DISCONNECTED/.test(m.text())) fail(`${label} console: ${m.text()}`); });
    const shot = async name => { if (SHOTS) await p.screenshot({ path: path.join(OUT, `admin-${label}-${name}.png`), fullPage: name !== 'map' }); };

    // вход: неверный пароль — понятная ошибка
    await p.goto(R); await p.waitForSelector('#login');
    await shot('login');
    await p.fill('[name="email"]', 'owner@example.com'); await p.fill('[name="password"]', 'wrong-pass'); await p.click('[type="submit"]');
    await p.waitForSelector('.alert.bad'); if (!(await p.textContent('.alert.bad')).includes('Неверная почта или пароль')) fail(`${label}: wrong password message`);
    // не админ — «Нет доступа»
    await p.fill('[name="email"]', 'someone@example.com'); await p.fill('[name="password"]', 'correct-horse'); await p.click('[type="submit"]');
    await p.waitForSelector('h1'); if (!(await p.textContent('h1')).includes('Нет доступа')) fail(`${label}: non-admin got in`);
    await p.click('[data-act="logout"]'); await p.waitForSelector('#login');
    // админ
    await p.fill('[name="email"]', 'owner@example.com'); await p.fill('[name="password"]', 'correct-horse'); await p.click('[type="submit"]');
    await p.waitForSelector('.stats'); await p.waitForTimeout(200);
    if (!(await p.textContent('.main')).includes('Срочно: 1')) fail(`${label}: urgent banner missing`);
    if (!(await p.$('.nav-a[href="#/checks"] .badge'))) fail(`${label}: checks badge missing`);
    await shot('overview');

    // каждый экран
    const routes = [['checks', 'Проверки'], ['people', 'Люди'], ['person/u1', 'Фируза'], ['shops', 'Магазины'], ['shop/s1', 'Бозори Сабз'], ['products', 'Товары'],
      ['orders', 'Заказы'], ['order/o1', 'Заказ № 1042'], ['couriers', 'Курьеры'], ['map', 'Карта'], ['reviews', 'Отзывы'], ['log', 'Журнал'], ['roles', 'Роли и связи']];
    for (const [r, title] of routes) {
      await p.goto(R + '#/' + r); await p.waitForFunction(t => document.querySelector('.page-head h1')?.textContent.includes(t), title, { timeout: 4000 }).catch(() => fail(`${label}: #/${r} title «${title}» not shown`));
      if (await p.$('.crash')) fail(`${label}: #/${r} crashed`);
      const overflow = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
      if (overflow > 1) fail(`${label}: #/${r} scrolls sideways by ${overflow}px`);
      await shot(r.replace('/', '-'));
    }

    // связи: человек → его магазин → сотрудник → карточка сотрудника
    await p.goto(R + '#/person/u1'); await p.waitForSelector('a[href="#/shop/s1"]');
    if (!(await p.textContent('.main')).includes('Управляющий в магазине «Сафо»')) fail(`${label}: staff link missing on person`);
    await p.click('a.item[href="#/shop/s1"]'); await p.waitForSelector('a[href="#/person/u4"]');
    if (!(await p.textContent('.main')).includes('ещё ни разу не входил')) fail(`${label}: staff without account not marked`);

    // фильтр меняет адрес — ссылкой можно поделиться
    await p.goto(R + '#/orders'); await p.waitForSelector('.tab'); await p.click('.tab[data-value="cancelled"]');
    await p.waitForFunction(() => window.__calls.filter(c => c.fn === 'admin_orders').pop()?.args?.p_status === 'cancelled', null, { timeout: 3000 })
      .catch(() => fail(`${label}: status filter not sent to base`));
    if (!(await p.evaluate(() => location.hash.includes('status=cancelled')))) fail(`${label}: filter not in address`);
    // поиск с паузой
    await p.fill('input[type="search"]', '1042'); await p.waitForFunction(() => location.hash.includes('q=1042'), null, { timeout: 3000 }).catch(() => fail(`${label}: search not applied`));
    if (!(await p.evaluate(() => document.activeElement?.getAttribute('type') === 'search'))) fail(`${label}: search lost focus after results`);

    // действие: блокировка магазина без причины — не уходит; с причиной — уходит с причиной
    await p.goto(R + '#/shop/s1'); await p.waitForSelector('[data-act="shop-block"]'); await p.click('[data-act="shop-block"]');
    await p.waitForSelector('.modal'); await shot('modal');
    await p.click('.modal [type="submit"]'); if (await p.$('.modal .err[hidden]')) fail(`${label}: empty reason accepted`);
    if (await p.evaluate(() => window.__calls.some(c => c.fn === 'admin_shop_block'))) fail(`${label}: blocked without reason`);
    await p.fill('.modal textarea', 'Продаёт запрещённое'); await p.click('.modal [type="submit"]');
    await p.waitForSelector('.toast.show'); const sent = await p.evaluate(() => window.__calls.find(c => c.fn === 'admin_shop_block')?.args);
    if (sent?.p_reason !== 'Продаёт запрещённое' || sent?.p_on !== true || sent?.p_shop !== 's1') fail(`${label}: block args wrong ${JSON.stringify(sent)}`);
    // «Отмена» ничего не делает
    await p.goto(R + '#/order/o1'); await p.waitForSelector('[data-act="order-cancel"]'); await p.click('[data-act="order-cancel"]');
    await p.waitForSelector('.modal'); await p.click('[data-m="no"]');
    if (await p.evaluate(() => window.__calls.some(c => c.fn === 'admin_order_cancel'))) fail(`${label}: cancel sent after «Отмена»`);
    if (!(await p.textContent('.main')).includes('Закупка / прибыль магазина')) fail(`${label}: order money block incomplete`);

    // телефон: «Ещё» открывает остальные разделы
    if (label === 'phone') {
      await p.click('[data-act="menu"]'); await p.waitForSelector('.sheet'); await shot('menu');
      await p.click('.sheet a[href="#/log"]'); await p.waitForFunction(() => document.querySelector('.page-head h1')?.textContent === 'Журнал');
      if (await p.$('.sheet')) fail('phone: menu stayed open');
    }
    await ctx.close();
  }
  await b.close(); srv.close();
  console.log(errs.length ? 'FAIL admin\n' + errs.join('\n') : 'OK admin');
  process.exit(errs.length ? 1 : 0);
})().catch(e => { console.error('FAIL admin', e); process.exit(1); });
