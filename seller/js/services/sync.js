import { kindOf } from '../config.js';
import { uid } from '../lib/format.js';
import { S, setS } from '../state.js';
import { store } from './storage.js';
import { db, explain, isNetErr, signInPhone, signOut } from './cloud.js';

// Синхронизация кабинета с базой.
// Кабинет работает как раньше со своим состоянием S; после каждого сохранения сюда приходит сигнал,
// и через долю секунды в базу уходит только то, что изменилось (сравниваем со снимком последней отправки).
// Новые заказы, ответы покупателей и отзывы приходят из базы сразу (живые обновления) и раз в 20 секунд на всякий случай.
// Без интернета кабинет работает дальше, а изменения уйдут, когда связь вернётся.

const SNAP_KEY = 'seller-sync-v1';
let snap = (() => { try { return JSON.parse(localStorage.getItem(SNAP_KEY)) || {}; } catch { return {}; } })();
const keepSnap = () => { try { localStorage.setItem(SNAP_KEY, JSON.stringify(snap)); } catch { /* память переполнена — отправим всё заново */ } };

export const cloud = { user: null, status: 'off', error: '' };   // off | connecting | ok | offline
/** @type {() => void} */
let onChange = () => {};
/** @type {(n: number) => void} */
let onNewOrder = () => {};
let timer = null, busy = false, again = false, channel = null, poll = null, lastPoll = 0;
/** Кабинет передаёт, как перерисовать экран и что делать с новым заказом. */
export function hooks(h) { onChange = h.render || onChange; onNewOrder = h.newOrder || onNewOrder; }

const iso = ts => ts ? new Date(ts).toISOString() : null;
const ms = s => s ? Date.parse(s) : null;
const n = v => v == null ? null : Number(v);
const IF_MISSING = { call: 'Если чего-то нет — позвонить', replace: 'Если чего-то нет — заменить похожим', remove: 'Если чего-то нет — убрать' };

// ---------- из кабинета в строки базы ----------
const shopId = () => S?.shop?.cloudId;
const shopRow = () => {
  const sh = S.shop;
  return { name: sh.name, kind: sh.kind || kindOf(sh).id, phone: sh.phone || '', city: sh.city || '', address: sh.address || '', landmark: sh.landmark || '',
    lat: sh.lat ?? null, lng: sh.lng ?? null, about: (sh.about || '').slice(0, 300), logo: sh.logo || '', cover: sh.cover || '', banner: sh.banner || '',
    paused: !!sh.paused, min_order: sh.minOrder || 0, prep_min: sh.prep || 30, delivery: sh.delivery !== false, pickup: sh.pickup !== false,
    schedule: sh.schedule || [], cats: S.cats || [] };
};
const shopPriv = () => {
  const { alif, melody, sound, awake, autoAccept, owner, type } = S.shop;
  return { shop_id: shopId(), data: { alif, melody, sound, awake, autoAccept, owner, type, staff: S.staff || [] } };
};
const productRow = p => ({
  id: p.id, shop_id: shopId(), name: p.name, cat: p.cat || '', price: p.price, old_price: p.oldPrice || null, unit: p.unit || 'шт', stock: Math.max(0, p.stock || 0),
  active: p.active !== false, stop_until: iso(p.stopUntil), expiry: p.expiry || null,
  data: { desc: p.desc || '', imgs: p.imgs || [], labels: p.labels || [], prep: p.prep ?? null, attrs: p.attrs || {}, minStep: p.minStep ?? null, options: p.options || [],
    variants: (p.variants || []).map(({ cost, ...v }) => v), created: p.created || null },
});
const productPriv = p => ({ product_id: p.id, shop_id: shopId(), cost: p.cost ?? null,
  variant_costs: Object.fromEntries((p.variants || []).filter(v => v.cost != null).map(v => [v.id, v.cost])) });
const cleanItems = items => items.map(({ cost, ...i }) => i);
// продажа в магазине: заводит сам магазин целиком
const saleRow = o => ({ id: o.id, shop_id: shopId(), source: 'shop', status: o.status, delivery: 'shop', items: cleanItems(o.items),
  sum: o.items.reduce((s, i) => s + i.qty * i.price, 0), total: o.items.reduce((s, i) => s + i.qty * i.price, 0), pay: o.pay || 'Наличные', created_at: iso(o.ts) });
// заказ из приложения: магазин меняет только ход сборки
const appPatch = o => ({ status: o.status, items: cleanItems(o.items), ready_in: o.readyIn ?? null, cancel_reason: o.cancelReason || '', accepted_at: iso(o.acceptedAt) });
const expenseRow = e => ({ id: e.id, shop_id: shopId(), spent_on: e.date, cat: e.cat, amount: e.amount, note: e.note || '', stock_purchase: !!e.stockPurchase });
const reviewPatch = r => ({ reply: r.reply || null, reply_at: iso(r.replyTs), complaint: r.complaint || null });

// ---------- из базы в кабинет ----------
const fromProduct = (r, pp) => ({
  id: r.id, sku: n(r.sku), name: r.name, cat: r.cat, price: n(r.price), oldPrice: n(r.old_price), cost: pp ? n(pp.cost) : null, stock: n(r.stock), unit: r.unit,
  desc: r.data?.desc || '', imgs: r.data?.imgs || [], active: r.active, labels: r.data?.labels || [], prep: r.data?.prep ?? null, attrs: r.data?.attrs || {},
  variants: (r.data?.variants || []).map(v => ({ ...v, cost: pp?.variant_costs?.[v.id] ?? null })), options: r.data?.options || [],
  expiry: r.expiry || '', minStep: r.data?.minStep ?? undefined, stopUntil: ms(r.stop_until), created: r.data?.created || ms(r.created_at),
  // скрыт администратором: только показываем, в базу магазин это поле не пишет
  blocked: !!r.blocked, blockReason: r.block_reason || '',
});
const fromOrder = (r, op) => {
  const app = r.source === 'app', c = r.customer || {};
  return {
    id: r.id, no: n(r.no), ts: ms(r.created_at), source: r.source, status: r.status, cloud: true,
    items: (r.items || []).map((i, k) => ({ ...i, qty: n(i.qty), price: n(i.price), cost: op?.costs?.[k] ?? null })),
    customer: app ? { name: c.name || 'Покупатель', phone: c.phone || '', address: c.address || '' } : null,
    delivery: r.delivery, comment: app ? [r.comment, IF_MISSING[r.if_missing]].filter(Boolean).join('. ') : r.comment, cancelReason: r.cancel_reason || '',
    pay: app ? (r.pay === 'card' ? 'Онлайн' : 'Наличные курьеру') : r.pay, readyIn: r.ready_in, acceptedAt: ms(r.accepted_at), receivedAt: ms(r.received_at),
    client: app, ifMissing: r.if_missing, fee: n(r.fee), km: n(r.km), problem: r.problem || undefined, paid: n(r.total),
    whenLabel: r.when_label || '',
    courier: r.courier || null, courierStatus: r.courier_status || null,
  };
};
const fromReview = r => ({ id: r.id, cloud: true, orderId: r.order_id, orderNo: n(r.order_no), ts: ms(r.created_at), name: r.name, rating: r.rating, tags: r.tags || [],
  text: r.text || '', items: r.items || [], reply: r.reply || undefined, replyTs: ms(r.reply_at) || undefined, complaint: r.complaint || undefined });
const fromExpense = e => ({ id: e.id, date: e.spent_on, cat: e.cat, amount: n(e.amount), note: e.note, stockPurchase: e.stock_purchase });

// ---------- снимок: что уже лежит в базе ----------
const J = x => JSON.stringify(x);
function rows() {
  const out = { shop: J(shopRow()), shopp: J(shopPriv()) };
  for (const p of S.products) { out['p:' + p.id] = J(productRow(p)); out['pp:' + p.id] = J(productPriv(p)); }
  for (const o of S.orders) if (!o.test && !(o.source === 'app' && !o.cloud)) out['o:' + o.id] = J(o.source === 'shop' ? saleRow(o) : appPatch(o));
  for (const e of S.expenses || []) out['e:' + e.id] = J(expenseRow(e));
  for (const r of S.reviews || []) if (r.cloud) out['r:' + r.id] = J(reviewPatch(r));
  return out;
}

// ---------- вход и загрузка ----------
/** Войти по номеру и подтянуть магазин из базы. Без связи кабинет работает с тем, что есть на телефоне. */
export async function connect(phone) {
  if (!db()) { cloud.status = 'off'; return; }
  cloud.status = 'connecting';
  try {
    cloud.user = await signInPhone(phone);
    await pushNow();                      // сначала то, что успели изменить без связи
    await pull(phone);
    cloud.status = 'ok'; cloud.error = '';
    listen();
  } catch (e) {
    cloud.status = isNetErr(e) ? 'offline' : 'error'; cloud.error = explain(e);
    console.warn('sync', e);
  }
  onChange();
}

async function pull(phone) {
  const c = db();
  const { data: shop, error } = await c.from('shops').select('*').eq('owner_id', cloud.user.id).maybeSingle();
  if (error) throw error;
  if (!shop) {
    // магазина в базе ещё нет: если на телефоне есть свой магазин этого номера — выгружаем его
    if (S && !S.demo && S.shop && !S.shop.cloudId && (S.shop.owner || phone) === phone) { snap = {}; await pushNow(); }
    else if (S?.shop?.cloudId) { setS(null); store.fresh(); snap = {}; keepSnap(); }   // магазин удалили в базе
    return;
  }
  const id = shop.id;
  const [priv, prods, pprivs, ords, oprivs, revs, exps] = await Promise.all([
    c.from('shop_private').select('*').eq('shop_id', id).maybeSingle(),
    c.from('products').select('*').eq('shop_id', id),
    c.from('product_private').select('*').eq('shop_id', id),
    c.from('orders').select('*').eq('shop_id', id).gte('created_at', iso(Date.now() - 120 * 864e5)).order('created_at'),
    c.from('order_private').select('*').eq('shop_id', id),
    c.from('reviews').select('*').eq('shop_id', id).order('created_at'),
    c.from('expenses').select('*').eq('shop_id', id),
  ]);
  for (const r of [priv, prods, pprivs, ords, oprivs, revs, exps]) if (r.error) throw r.error;
  const pp = Object.fromEntries((pprivs.data || []).map(x => [x.product_id, x]));
  const op = Object.fromEntries((oprivs.data || []).map(x => [x.order_id, x]));
  const d = priv.data?.data || {};
  const orders = (ords.data || []).map(r => fromOrder(r, op[r.id]));
  // тестовые заказы и продажи, которые ещё не дошли до базы, не теряем
  const localOnly = (S?.shop?.cloudId === id ? S.orders : []).filter(o => o.test || (!o.cloud && !orders.some(x => x.id === o.id)));
  setS({
    v: 2, demo: false, cats: shop.cats || [], staff: d.staff || [],
    shop: { cloudId: id, name: shop.name, kind: shop.kind, type: d.type || kindOf({ kind: shop.kind }).name, phone: shop.phone, city: shop.city, address: shop.address,
      landmark: shop.landmark, lat: shop.lat, lng: shop.lng, about: shop.about, logo: shop.logo, cover: shop.cover, banner: shop.banner, paused: shop.paused,
      minOrder: n(shop.min_order), prep: shop.prep_min, delivery: shop.delivery, pickup: shop.pickup, schedule: shop.schedule,
      alif: d.alif || { terminal: '', status: 'none', holder: '', tin: '' }, melody: d.melody, sound: d.sound, awake: d.awake, autoAccept: d.autoAccept, owner: d.owner || phone,
      blocked: !!shop.blocked, blockReason: shop.block_reason || '' },
    products: (prods.data || []).map(r => fromProduct(r, pp[r.id])).sort((a, b) => (b.created || 0) - (a.created || 0)),
    orders: [...orders, ...localOnly],
    reviews: (revs.data || []).map(fromReview),
    expenses: (exps.data || []).map(fromExpense),
    nextNo: Math.max(1000, ...orders.map(o => o.no)) + 1,
  });
  store.save(S);
  snap = rows(); for (const o of localOnly) delete snap['o:' + o.id];
  keepSnap(); lastPoll = Date.now();
}

// ---------- отправка изменений ----------
/** Вызывается после каждого сохранения кабинета. */
export function schedule() {
  if (!cloud.user || !S || S.demo) return;
  clearTimeout(timer); timer = setTimeout(pushNow, 700);
}
async function pushNow() {
  if (!cloud.user || !S || S.demo || !S.shop) return;
  if (busy) { again = true; return; }
  busy = true;
  try {
    const c = db();
    if (!shopId()) {
      const { data, error } = await c.from('shops').insert(shopRow()).select('id').single();
      if (error) throw error;
      S.shop.cloudId = data.id; store.save(S); snap = {};
      listen();
    }
    await uploadPhotos();
    const now = rows(), changed = k => now[k] !== snap[k];
    const pick = (pre, map) => Object.keys(now).filter(k => k.startsWith(pre) && changed(k)).map(k => map(k.slice(pre.length)));
    const byId = (list, id) => list.find(x => x.id === id);
    if (changed('shop')) { const { error } = await c.from('shops').update(shopRow()).eq('id', shopId()); if (error) throw error; }
    if (changed('shopp')) { const { error } = await c.from('shop_private').upsert(shopPriv()); if (error) throw error; }
    const prods = pick('p:', id => productRow(byId(S.products, id)));
    if (prods.length) {
      const { data, error } = await c.from('products').upsert(prods).select('id,sku'); if (error) throw error;
      let fresh = false;
      for (const r of data || []) { const p = byId(S.products, r.id); if (p && !p.sku) { p.sku = n(r.sku); fresh = true; } }
      if (fresh) setTimeout(onChange);   // показать новые артикулы
    }
    const privs = pick('pp:', id => productPriv(byId(S.products, id)));
    if (privs.length) { const { error } = await c.from('product_private').upsert(privs); if (error) throw error; }
    const gone = Object.keys(snap).filter(k => k.startsWith('p:') && !(k in now)).map(k => k.slice(2));
    if (gone.length) { const { error } = await c.from('products').delete().in('id', gone); if (error) throw error; }
    // заказы: продажи в магазине заводим, у заказов из приложения меняем только ход сборки
    for (const id of Object.keys(now).filter(k => k.startsWith('o:') && changed(k)).map(k => k.slice(2))) {
      const o = byId(S.orders, id);
      if (o.source === 'shop') {
        if (!snap['o:' + id]) {
          const { data, error } = await c.from('orders').insert(saleRow(o)).select('no').single(); if (error) throw error;
          o.no = n(data.no); o.cloud = true; now['o:' + id] = J(saleRow(o));
          const pr = await c.from('order_private').upsert({ order_id: o.id, shop_id: shopId(), costs: o.items.map(i => i.cost ?? null) }); if (pr.error) throw pr.error;
        } else { const { error } = await c.from('orders').update({ status: o.status, items: cleanItems(o.items) }).eq('id', id); if (error) throw error; }
      } else { const { error } = await c.from('orders').update(appPatch(o)).eq('id', id); if (error) throw error; }
    }
    const exps = pick('e:', id => expenseRow(byId(S.expenses, id)));
    if (exps.length) { const { error } = await c.from('expenses').upsert(exps); if (error) throw error; }
    const goneExp = Object.keys(snap).filter(k => k.startsWith('e:') && !(k in now)).map(k => k.slice(2));
    if (goneExp.length) { const { error } = await c.from('expenses').delete().in('id', goneExp); if (error) throw error; }
    for (const id of Object.keys(now).filter(k => k.startsWith('r:') && changed(k)).map(k => k.slice(2))) {
      const { error } = await c.from('reviews').update(reviewPatch(byId(S.reviews, id))).eq('id', id); if (error) throw error;
    }
    snap = rows(); keepSnap(); store.save(S);
    if (cloud.status !== 'ok') { cloud.status = 'ok'; cloud.error = ''; onChange(); }
  } catch (e) {
    const was = cloud.status;
    cloud.status = isNetErr(e) ? 'offline' : 'error'; cloud.error = explain(e);
    console.warn('sync push', e);
    if (was !== cloud.status) onChange();
    clearTimeout(timer); timer = setTimeout(pushNow, 15000);   // повторим позже
  } finally {
    busy = false;
    if (again) { again = false; schedule(); }
  }
}

// фото из телефона (data:) кладём в хранилище базы, в карточке остаётся ссылка
async function uploadPhotos() {
  const c = db(), up = async src => {
    if (!src?.startsWith('data:')) return src;
    const blob = await (await fetch(src)).blob();
    const path = `${shopId()}/${uid()}.${blob.type === 'image/png' ? 'png' : blob.type === 'image/webp' ? 'webp' : 'jpg'}`;
    const { error } = await c.storage.from('media').upload(path, blob, { contentType: blob.type, upsert: false });
    if (error) throw error;
    return c.storage.from('media').getPublicUrl(path).data.publicUrl;
  };
  for (const k of ['logo', 'cover', 'banner']) S.shop[k] = await up(S.shop[k]);
  for (const p of S.products) if (p.imgs?.some(s => s.startsWith('data:'))) p.imgs = await Promise.all(p.imgs.map(up));
}

// ---------- живые обновления ----------
function mergeOrder(row, op) {
  const o = fromOrder(row, op), i = S.orders.findIndex(x => x.id === o.id), fresh = i < 0;
  if (fresh) S.orders.push(o); else S.orders[i] = { ...S.orders[i], ...o };
  snap['o:' + o.id] = J(o.source === 'shop' ? saleRow(o) : appPatch(o));
  return fresh && o.source === 'app' && o.status === 'new';
}
async function fetchOrders(ids) {
  const c = db();
  const [{ data: ords }, { data: ops }] = await Promise.all([c.from('orders').select('*').in('id', ids), c.from('order_private').select('*').in('order_id', ids)]);
  const op = Object.fromEntries((ops || []).map(x => [x.order_id, x]));
  let fresh = 0;
  for (const r of ords || []) if (mergeOrder(r, op[r.id])) fresh++;
  return fresh;
}
function applied(fresh) { keepSnap(); store.save(S); onChange(); if (fresh) onNewOrder(fresh); }

// блокировку магазина ставит и снимает администратор — показываем её сразу, без перезахода
function shopBlock(row) {
  if (!S?.shop || (!!row.blocked === !!S.shop.blocked && (row.block_reason || '') === (S.shop.blockReason || ''))) return;
  S.shop.blocked = !!row.blocked; S.shop.blockReason = row.block_reason || ''; store.save(S); onChange();
}

function listen() {
  const c = db(); if (!c || !shopId() || channel) return;
  const id = shopId();
  channel = c.channel('shop-' + id)
    .on('postgres_changes', { event: '*', schema: 'public', table: 'orders', filter: `shop_id=eq.${id}` }, async ev => {
      try { const fresh = await fetchOrders([ev.new?.id || ev.old?.id]); applied(fresh); } catch (e) { console.warn('sync order', e); }
    })
    .on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'products', filter: `shop_id=eq.${id}` }, ev => {
      const p = S.products.find(x => x.id === ev.new.id); if (!p) return;
      const pending = snap['p:' + p.id] !== J(productRow(p));
      p.stock = n(ev.new.stock); p.blocked = !!ev.new.blocked; p.blockReason = ev.new.block_reason || '';
      if (!pending) snap['p:' + p.id] = J(productRow(p));
      applied(0);
    })
    .on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'shops', filter: `id=eq.${id}` }, ev => { shopBlock(ev.new); })
    .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'reviews', filter: `shop_id=eq.${id}` }, ev => {
      if (S.reviews.some(r => r.id === ev.new.id)) return;
      const r = fromReview(ev.new); S.reviews.push(r); snap['r:' + r.id] = J(reviewPatch(r)); applied(0);
    })
    .subscribe();
  // запасной путь: раз в 20 секунд спрашиваем, что поменялось
  clearInterval(poll);
  poll = setInterval(async () => {
    if (!cloud.user || !shopId() || document.visibilityState === 'hidden') return;
    try {
      const since = iso(lastPoll - 10000); lastPoll = Date.now();
      const { data, error } = await c.from('orders').select('id').eq('shop_id', shopId()).gte('updated_at', since);
      if (error) throw error;
      if (data?.length) applied(await fetchOrders(data.map(x => x.id)));
      const sh = await c.from('shops').select('blocked,block_reason').eq('id', shopId()).maybeSingle();
      if (sh.data) shopBlock(sh.data);
      if (cloud.status !== 'ok') { cloud.status = 'ok'; cloud.error = ''; schedule(); onChange(); }
    } catch (e) { if (cloud.status === 'ok') { cloud.status = isNetErr(e) ? 'offline' : 'error'; cloud.error = explain(e); onChange(); } }
  }, 20000);
}

/** Выход: сначала отправляем несохранённое, потом забываем магазин на этом телефоне. */
export async function disconnect() {
  try { await pushNow(); } catch { /* без связи — что успели, то успели */ }
  try { if (channel) await db()?.removeChannel(channel); } catch { /* канал уже закрыт */ }
  channel = null; clearInterval(poll); cloud.user = null; cloud.status = 'off';
  snap = {}; keepSnap();
  await signOut();
}
/** Удалить магазин целиком из базы (товары, заказы, отзывы удаляются вместе с ним). */
export async function deleteShop() {
  const id = shopId(); if (!id || !cloud.user) return;
  const { error } = await db().from('shops').delete().eq('id', id);
  if (error) throw error;
  snap = {}; keepSnap();
}
window.addEventListener('online', () => { if (cloud.user) schedule(); });
