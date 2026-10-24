import { C, save } from '../state.js';
import { db, explain, isNetErr, signInPhone } from './cloud.js';

// Общая база: витрины всех магазинов и заказы покупателя.
// Любой продавец добавил товар в кабинете — он появляется здесь. Заказ уходит прямо в кабинет того магазина.
// Без связи показываем то, что загрузили в прошлый раз; если база ни разу не ответила — магазины-примеры.

const CACHE = 'zud-market-v1';
// status: off — библиотека базы не загрузилась, loading, ok, offline — нет интернета, error — база ответила ошибкой
export const market = { status: 'off', shops: [], at: 0, error: '' };
try { const c = JSON.parse(localStorage.getItem(CACHE)); if (Array.isArray(c?.shops)) Object.assign(market, { shops: c.shops, at: c.at || 0 }); } catch { /* кэша нет */ }
/** Показываем магазины из базы: она ответила сейчас или раньше. */
export const live = () => market.status === 'ok' || market.at > 0;

let onChange = () => {};
const n = v => v == null ? null : Number(v);
const ms = v => v ? Date.parse(v) : null;
// база не ответила за это время — считаем, что связи нет
const withTimeout = (p, sec = 12) => Promise.race([p, new Promise((_, no) => setTimeout(() => no(new Error('timeout')), sec * 1000))]);

// ---------- витрины ----------
const TILES = [['#fce000', '#21201f'], ['#2e8b57', '#ffffff'], ['#e53935', '#ffffff'], ['#3f51b5', '#ffffff'], ['#ff8a00', '#21201f'], ['#7b4fd6', '#ffffff'], ['#00897b', '#ffffff'], ['#21201f', '#ffffff']];
const tileOf = id => { let h = 0; for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0; const [bg, fg] = TILES[h % TILES.length]; return { bg, fg }; };

function fromProduct(r, likes) {
  const d = r.data || {}, l = likes[r.id];
  return {
    id: r.id, sku: n(r.sku), cat: r.cat || '', name: r.name, price: n(r.price), oldPrice: n(r.old_price), unit: r.unit || 'шт', minStep: d.minStep || 1, stock: n(r.stock),
    active: r.active, stopUntil: ms(r.stop_until), imgs: d.imgs || [], desc: d.desc || '', attrs: d.attrs || {}, variants: d.variants || [], options: d.options || [], labels: d.labels || [],
    expiry: r.expiry || '', prep: d.prep ?? null, likes: l?.all >= 3 ? Math.round(l.up / l.all * 100) : null, likesN: l?.all || 0,
  };
}
function fromShop(r, products) {
  const cats = (r.cats || []).filter(c => products.some(p => p.cat === c));
  return {
    id: r.id, cloud: true, name: r.name, kind: r.kind, about: r.about || '', logo: r.logo || '', cover: r.cover || '', banner: r.banner || '',
    rating: n(r.rating) || 0, count: r.rating_count || 0, isNew: (r.rating_count || 0) < 10, prep: r.prep_min || 30, city: r.city || '', lat: r.lat, lng: r.lng,
    minOrder: n(r.min_order) || 0, address: r.address || '', schedule: r.schedule || [], paused: !!r.paused, delivery: r.delivery !== false, phone: r.phone || '',
    color: '#fff6c2', tile: tileOf(r.id), cats: cats.concat([...new Set(products.map(p => p.cat))].filter(c => !cats.includes(c))), products,
  };
}

/** Загрузить витрины всех магазинов. onSale — те же правила продажи, что в кабинете продавца. */
export async function loadCatalog(onSale) {
  const c = db(); if (!c) { market.status = 'off'; return onChange(); }
  if (market.status !== 'ok') market.status = 'loading';
  try {
    const since = new Date(Date.now() - 90 * 864e5).toISOString();
    const [sh, pr, rv] = await withTimeout(Promise.all([
      // без повторов: нет связи — сразу показываем запасной вариант, витрины всё равно обновляются раз в минуту
      c.from('shops').select('*').retry(false),
      c.from('products').select('*').eq('active', true).limit(5000).retry(false),
      c.from('reviews').select('shop_id,items').gte('created_at', since).limit(3000).retry(false),
    ]));
    const err = sh.error || pr.error || rv.error; if (err) throw err;
    const likes = {};
    for (const r of rv.data || []) for (const i of r.items || []) if (i.like != null) { const x = likes[i.pid] ||= { up: 0, all: 0 }; x.all++; if (i.like) x.up++; }
    const by = {};
    for (const r of pr.data || []) (by[r.shop_id] ||= []).push(r);
    market.shops = (sh.data || []).map(s => fromShop(s, (by[s.id] || []).map(r => fromProduct(r, likes)).filter(p => onSale(p, s.kind))))
      .filter(s => s.products.length);   // магазин без товаров покупателю не показываем
    market.at = Date.now(); market.status = 'ok'; market.error = '';
    listenCatalog?.();
    try { localStorage.setItem(CACHE, JSON.stringify({ at: market.at, shops: market.shops })); } catch { /* память заполнена — обойдёмся без кэша */ }
  } catch (e) {
    market.status = isNetErr(e) ? 'offline' : 'error'; market.error = explain(e);
    console.warn('market', e);
  }
  onChange();
}

// ---------- вход ----------
let uid = null;
/** Тестовый вход по номеру (без SMS): тот же номер — те же заказы на любом телефоне. */
export async function auth() {
  if (!C.user) throw new Error('Войдите по номеру телефона');
  const u = await withTimeout(signInPhone(C.user.phone));
  if (uid !== u.id) { uid = u.id; listenOrders(); }
  return u;
}
export async function login() { try { await auth(); await refreshOrders(); } catch (e) { console.warn('login', e); } }
export async function logout() { uid = null; ordersChan?.unsubscribe(); ordersChan = null; try { await db()?.auth.signOut(); } catch { /* уже вышли */ } }

// ---------- заказы ----------
/** Что меняет магазин в заказе: этап, сборка, причина отмены. */
export const rowOf = r => ({ status: r.status, items: (r.items || []).map(i => ({ ...i, qty: n(i.qty), price: n(i.price) })), cancelReason: r.cancel_reason || '',
  receivedAt: ms(r.received_at), acceptedAt: ms(r.accepted_at), readyIn: r.ready_in, problem: r.problem || null,
  courier: r.courier || null, courierStatus: r.courier_status || null, courierRating: r.courier_rating ?? null });

/** Оформить заказ: цены, остатки и доставку база проверяет сама. */
export async function placeCloud(args) {
  await auth();
  const { data, error } = await withTimeout(db().rpc('place_order', args), 20);
  if (error) throw new Error(explain(error));
  await refreshOrders();
  return data;
}
/** Действие покупателя с заказом: ответ на замену, отмена, получение, отзыв, проблема. */
export async function act(fn, args) {
  await auth();
  const { error } = await withTimeout(db().rpc(fn, args));
  if (error) throw new Error(explain(error));
  await refreshOrders();
}

const recent = () => C.orders.filter(o => o.cloud && Date.now() - o.ts < 7 * 864e5);
export async function refreshOrders() {
  const c = db(), ids = recent().map(o => o.id); if (!c || !ids.length || !C.user) return;
  try {
    await auth();
    const { data, error } = await withTimeout(c.from('orders').select('*').in('id', ids)); if (error) throw error;
    apply(data || []);
  } catch (e) { console.warn('orders', e); }
}
function apply(list) {
  let changed = false;
  for (const r of list) {
    const o = C.orders.find(x => x.id === r.id); if (!o) continue;
    const row = rowOf(r);
    if (JSON.stringify(o.row) !== JSON.stringify(row)) { o.row = row; if (row.receivedAt) o.receivedAt ||= row.receivedAt; changed = true; }
  }
  if (changed) { save(); onChange(); }
}
let ordersChan = null;
function listenOrders() {
  const c = db(); if (!c || !uid) return;
  ordersChan?.unsubscribe();
  ordersChan = c.channel('buyer-' + uid)
    .on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'orders', filter: `buyer_id=eq.${uid}` }, p => apply([p.new]))
    .subscribe();
}

// ---------- запуск ----------
let t = 0, listenCatalog = null;
/** Подключиться: витрины сейчас и при каждом изменении в базе, заказы — живьём и раз в 15 секунд на всякий случай. */
export function startMarket({ render, onSale }) {
  onChange = render;
  const c = db();
  if (!c) { market.status = 'off'; return; }
  const reload = () => loadCatalog(onSale);
  const soon = () => { clearTimeout(t); t = setTimeout(reload, 1500); };
  // живые изменения включаем, когда база ответила: без интернета не стучимся в неё каждую секунду
  listenCatalog = () => {
    listenCatalog = null;
    c.channel('market')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'products' }, soon)
      .on('postgres_changes', { event: '*', schema: 'public', table: 'shops' }, soon)
      .subscribe();
  };
  reload();
  if (C.user) login();
  setInterval(() => { if (!document.hidden) reload(); }, 60000);
  setInterval(() => { if (!document.hidden && recent().some(o => !o.row?.receivedAt && o.row?.status !== 'cancelled')) refreshOrders(); }, 15000);
  addEventListener('online', () => { reload(); refreshOrders(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { soon(); refreshOrders(); } });
}

// ---------- курьер заказа: код получения и где он сейчас ----------
const codes = {}, where = {}, asked = {};
/** Код получения (4 цифры) — покупатель называет его курьеру. Пока не загрузился — null, загрузка идёт сама. */
export function courierCode(id) {
  if (codes[id] || asked['c' + id] > Date.now() - 10000) return codes[id] || null;
  asked['c' + id] = Date.now();
  auth().then(() => db().rpc('buyer_code', { p_order: id })).then(r => { if (r?.data) { codes[id] = r.data; onChange(); } }).catch(() => {});
  return null;
}
/** Где курьер: { lat, lng, at } или null. Обновляется не чаще раза в 8 секунд, пока экран заказа открыт. */
export function courierWhere(id) {
  if (!(asked['w' + id] > Date.now() - 8000)) {
    asked['w' + id] = Date.now();
    auth().then(() => db().rpc('order_courier_where', { p_order: id })).then(r => {
      const p = r?.data, old = where[id];
      where[id] = p ? { lat: Number(p.lat), lng: Number(p.lng), at: ms(p.at) } : null;
      if (JSON.stringify(old) !== JSON.stringify(where[id])) onChange();
    }).catch(() => {});
  }
  return where[id] || null;
}
