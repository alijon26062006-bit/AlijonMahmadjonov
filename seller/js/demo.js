import { DAYS, REPLY_TEMPLATES, REVIEW_BAD, REVIEW_GOOD, SHOP_KINDS } from './config.js';
import { addDays, pad, parseKey, today, uid } from './lib/format.js';

// пример магазина
export function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
export function demo() {
  const R = rng(26062006);
  const P = (name, cat, price, cost, stock, unit, desc, extra = {}) => ({ id: uid(), name, cat, price, oldPrice: null, cost, stock, unit, desc, imgs: [], active: true, labels: [], prep: null, variants: [], attrs: {}, expiry: '', created: Date.now() - Math.floor(R() * 9e8), ...extra });
  const products = [
    P('Помидоры местные', 'Овощи и зелень', 12, 8, 40, 'кг', 'Грунтовые, сладкие. Собраны вчера.', { labels: ['Хит'], minStep: 0.5 }),
    P('Огурцы', 'Овощи и зелень', 10, 6, 25, 'кг', 'Хрустящие, тепличные.', { minStep: 0.5 }),
    P('Картофель', 'Овощи и зелень', 6, 4, 120, 'кг', 'Молодой картофель.', { minStep: 1 }),
    P('Яблоки', 'Фрукты и ягоды', 14, 9, 30, 'кг', 'Сорт «Семеренко».', { minStep: 0.5 }),
    P('Гранат', 'Фрукты и ягоды', 18, 12, 4, 'кг', 'Кандибадам, крупный.', { oldPrice: 22, minStep: 0.5, labels: ['Новинка'] }),
    P('Курага исфаринская', 'Орехи и сухофрукты', 35, 24, 8, 'кг', 'Без косточки.', { minStep: 0.25, expiry: addDays(today(), 90) }),
    P('Чакка домашняя', 'Молочное и яйца', 11, 7, 18, 'шт', 'Банка 500 г.', { expiry: addDays(today(), 5), attrs: { pack: '500 г', country: 'Таджикистан' } }),
    P('Молоко', 'Молочное и яйца', 9, 6, 0, 'л', 'Деревенское, 3,5%.', { minStep: 1, expiry: addDays(today(), 2) }),
    P('Нон тандыри', 'Хлеб и выпечка', 4, 2.5, 60, 'шт', 'Горячий, из тандыра.', { labels: ['Хит'], expiry: addDays(today(), 1) }),
    P('Яйца деревенские', 'Молочное и яйца', 13, 9, 3, 'упак', 'Упаковка 10 шт.', { expiry: addDays(today(), 14), variants: [{ id: uid(), name: '10 шт', price: 13, cost: 9 }, { id: uid(), name: '30 шт', price: 36, cost: 26 }] }),
  ];
  const names = ['Фарзона', 'Шерали', 'Мадина', 'Рустам', 'Нигина', 'Бахром', 'Зарина', 'Далер', 'Манижа', 'Сухроб'];
  const streets = ['ул. Айни 12', 'пр. Рудаки 98', 'ул. Шотемур 5', 'ул. Бохтар 31', 'мкр. Сино, д. 14', 'ул. Карамова 7'];
  const pickItems = () => {
    const n = 1 + Math.floor(R() * 2), items = [];
    for (let i = 0; i < n; i++) {
      const p = products[Math.floor(R() * products.length)];
      const v = p.variants.length ? p.variants[Math.floor(R() * p.variants.length)] : null;
      const qty = p.unit === 'кг' || p.unit === 'л' ? (1 + Math.floor(R() * 5)) * 0.5 : p.price < 6 ? 2 + Math.floor(R() * 6) : 1 + Math.floor(R() * 2);
      items.push({ pid: p.id, name: p.name, unit: p.unit, variant: v ? v.name : '', qty, price: v ? v.price : p.price, cost: v ? v.cost : p.cost });
    }
    return items;
  };
  const orders = []; let no = 1000;
  for (let back = 34; back >= 0; back--) {
    const day = parseKey(addDays(today(), -back));
    const weekend = day.getDay() === 0 || day.getDay() === 6;
    const n = 3 + Math.floor(R() * (weekend ? 9 : 6)) + (back < 10 ? 2 : 0);
    for (let i = 0; i < n; i++) {
      const ts = new Date(day); ts.setHours(9 + Math.floor(R() * 12), Math.floor(R() * 60));
      if (ts.getTime() > Date.now() - 60 * 60000) continue; // сегодня — только уже прошедшие часы
      const app = R() < .6, cancel = R() < .06;
      orders.push({ id: uid(), no: ++no, ts: ts.getTime(), source: app ? 'app' : 'shop', status: cancel ? 'cancelled' : 'done', items: pickItems(), customer: app ? { name: names[Math.floor(R() * names.length)], phone: '+992 9' + Math.floor(R() * 1e8).toString().padStart(8, '0'), address: 'Душанбе, ' + streets[Math.floor(R() * streets.length)] } : null, delivery: app ? (R() < .8 ? 'courier' : 'pickup') : 'shop', comment: '', cancelReason: cancel ? 'Нет товара' : '', pay: R() < .5 ? 'Наличные' : 'Карта' });
    }
  }
  const now = Date.now();
  const live = (st, ago, comment) => ({ id: uid(), no: ++no, ts: now - ago * 60000, source: 'app', status: st, items: pickItems(), customer: { name: names[Math.floor(R() * names.length)], phone: '+992 93 555 12 ' + pad(Math.floor(R() * 99)), address: 'Душанбе, ' + streets[Math.floor(R() * streets.length)] }, delivery: 'courier', comment, cancelReason: '', pay: 'Наличные', readyIn: st === 'accepted' ? 25 : null });
  orders.push(live('ready', 41, ''), live('accepted', 18, 'Позвоните за 10 минут'), live('new', 3, 'Помидоры выберите покрепче, пожалуйста'), live('new', 1, ''));
  // отзывы примерно к каждому третьему заказу из приложения
  const texts = { 5: ['Всё свежее, спасибо!', 'Помидоры как с грядки, буду заказывать ещё', '', 'Быстро и аккуратно'], 4: ['Хорошо, но пакет порвался', '', 'Всё пришло, спасибо'], 3: ['Яблоки были мелковаты'], 2: ['Не положили курагу, пришлось звонить'], 1: ['Молоко оказалось кислым'] };
  const reviews = [];
  for (const o of orders) {
    if (o.source !== 'app' || o.status !== 'done' || R() > 0.33) continue;
    const x = R(), rate = x < 0.62 ? 5 : x < 0.86 ? 4 : x < 0.93 ? 3 : x < 0.97 ? 2 : 1, bad = rate <= 3;
    const pool = bad ? REVIEW_BAD : REVIEW_GOOD, list = texts[rate];
    const r = { id: uid(), orderId: o.id, orderNo: o.no, ts: o.ts + 3 * 36e5, name: o.customer.name, rating: rate, tags: pool.filter(() => R() < 0.3).slice(0, 2),
      text: list[Math.floor(R() * list.length)], items: o.items.map(i => ({ pid: i.pid, name: i.name, like: bad ? R() < 0.4 : R() < 0.95 })) };
    if (r.ts > Date.now()) continue;
    if (!bad && R() < 0.5) Object.assign(r, { reply: REPLY_TEMPLATES[0], replyTs: r.ts + 36e5 });
    if (bad && Date.now() - r.ts > 5 * 864e5) Object.assign(r, { reply: REPLY_TEMPLATES[2], replyTs: r.ts + 36e5 });
    reviews.push(r);
  }
  // в примере всегда есть свежий плохой отзыв без ответа — чтобы было видно, как на него отвечать
  const last = orders.filter(o => o.source === 'app' && o.status === 'done' && o.ts + 3 * 36e5 < Date.now()).sort((x, y) => y.ts - x.ts)[0];
  if (last && !reviews.some(r => r.rating <= 3 && !r.reply)) reviews.push({ id: uid(), orderId: last.id, orderNo: last.no, ts: last.ts + 3 * 36e5, name: last.customer.name, rating: 2,
    tags: [REVIEW_BAD[4]], text: 'Ждал почти час, помидоры помялись', items: last.items.map(i => ({ pid: i.pid, name: i.name, like: false })) });
  const expenses = [];
  const E = (back, cat, amount, note) => expenses.push({ id: uid(), date: addDays(today(), -back), cat, amount, note });
  E(30, 'Аренда', 2500, 'Аренда магазина'); E(28, 'Закупка товара', 3200, 'Овощи с базы'); E(21, 'Закупка товара', 2800, 'Фрукты, молочное');
  E(16, 'Зарплата', 1800, 'Продавец, половина месяца'); E(14, 'Закупка товара', 3100, ''); E(12, 'Упаковка', 260, 'Пакеты');
  E(9, 'Реклама', 400, 'Instagram'); E(7, 'Закупка товара', 2950, ''); E(5, 'Коммунальные', 380, 'Свет, вода'); E(2, 'Доставка товара', 150, 'Такси с базы'); E(1, 'Зарплата', 1800, 'Продавец');
  // в примере закупка товара считается и через закупочную цену, поэтому помечаем такие расходы, чтобы не учитывать дважды
  expenses.forEach(e => { if (e.cat === 'Закупка товара') e.stockPurchase = true; });
  return {
    v: 2, demo: true,
    shop: { name: 'Бозори Сабз', type: 'Продукты', kind: 'grocery', city: 'Шахритус', lat: 37.2655, lng: 68.1345, landmark: 'Рядом с рынком', phone: '+992 93 555 12 34', address: 'Шахритус, центр', about: 'Свежие овощи и фрукты каждый день.', logo: '', paused: false, minOrder: 50, delivery: true, pickup: true, prep: 30, schedule: DAYS.map((_, i) => ({ open: true, from: i === 6 ? '09:00' : '08:00', to: '21:00' })), alif: { terminal: '200001', status: 'connected', holder: 'ИП Каримов Шерали', tin: '510012345' } },
    cats: [...SHOP_KINDS[0].cats],
    products, orders, expenses, reviews, staff: [], nextNo: no + 1,
  };
}
export function blankShop(d) {
  return { name: d.name, type: d.type, phone: d.phone, address: d.address, about: d.about || '', logo: '', paused: false, minOrder: 0, delivery: true, pickup: true, prep: 30, schedule: DAYS.map(() => ({ open: true, from: '09:00', to: '21:00' })), alif: { terminal: '', status: 'none', holder: '', tin: '' } };
}
// перевод данных из первой версии
export function migrate(s) {
  if (!s || s === 'fresh' || s.v === 2) return s;
  const shop = { ...blankShop(s.shop), ...s.shop };
  return { v: 2, demo: s.demo, shop, cats: s.cats || [], orders: [], expenses: [], nextNo: 1001,
    products: (s.products || []).map(p => ({ oldPrice: null, labels: [], prep: null, variants: [], attrs: {}, expiry: '', ...p, imgs: p.imgs || (p.img ? [p.img] : []) })) };
}
