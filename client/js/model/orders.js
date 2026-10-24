import { fmtPhone, r2, uid } from '../lib/format.js';
import { readSeller, updateSeller } from '../services/bridge.js';
import { act, placeCloud, rowOf } from '../services/market.js';
import { C, save } from '../state.js';
import { clear, totals } from './cart.js';
import { shopById } from './catalog.js';
import { route } from './delivery.js';

// Заказы покупателя. Заказ в магазин из базы уходит прямо в кабинет этого продавца (place_order),
// статус и сборку (вес, замены) магазин меняет в базе, а мы показываем. Без интернета: заказ в кабинет
// на этом же устройстве идёт через память браузера, а заказы в магазины-примеры проходят этапы сами.

export const STAGES = ['Магазин получил заказ', 'Собирают заказ', 'Передают курьеру', 'Курьер в пути', 'Доставлен'];
export const addrLine = a => a ? [a.city, a.street, a.house && 'д. ' + a.house, a.apt && 'кв. ' + a.apt].filter(Boolean).join(', ') : '';

export async function placeOrder({ pay, when }) {
  const { shop, rows, sum, fee, total, way } = totals();
  if (!way.ok) throw new Error(`Магазин не возит так далеко: ${way.km} км`);
  const a = C.addr, u = C.user;
  const items = rows.map(r => ({ pid: r.p.id, name: r.p.name, unit: r.p.unit, variant: r.variant, qty: r.qty, price: r.price, cost: null, opts: r.optNames.map(o => ({ name: o.name, price: o.price })) }));
  const comment = [C.cart.comment.trim(), shop.kind === 'food' && C.cart.cutlery ? 'Положите приборы' : ''].filter(Boolean).join('. ');
  const order = { id: uid(), shopId: shop.id, shopName: shop.name, kind: shop.kind, ts: Date.now(), items, sum, fee, total, km: way.km, pay, when, addr: { ...a }, ifMissing: C.cart.ifMissing, comment, phone: shop.phone || '' };
  if (shop.cloud) {
    const r = await placeCloud({
      p_shop: shop.id, p_items: rows.map(x => ({ pid: x.p.id, vid: x.vid || '', opts: x.opts || [], qty: x.qty })),
      p_addr: { city: a.city, street: a.street, house: a.house, entrance: a.entrance, floor: a.floor, apt: a.apt, intercom: a.intercom, landmark: a.landmark, lat: a.lat ?? null, lng: a.lng ?? null },
      p_name: u.name || '', p_phone: '+992 ' + fmtPhone(u.phone), p_pay: pay, p_comment: comment, p_if_missing: C.cart.ifMissing,
      p_when_at: when ? new Date(when.at).toISOString() : null, p_when_label: when?.label || null,
    });
    // цены, доставку и номер заказа считает база — берём её цифры
    const row = rowOf(r);
    Object.assign(order, { id: r.id, no: Number(r.no), cloud: true, ts: Date.parse(r.created_at) || order.ts, items: row.items, sum: Number(r.sum), fee: Number(r.fee), total: Number(r.total), km: Number(r.km), row });
  } else if (shop.local) {
    const r = updateSeller(S => {
      const no = S.nextNo++;
      const sellerItems = items.map(i => ({ ...i, cost: S.products.find(p => p.id === i.pid)?.cost ?? null }));
      S.orders.push({
        id: order.id, no, ts: order.ts, source: 'app', status: 'new', items: sellerItems, delivery: 'courier', pay: pay === 'cash' ? 'Наличные курьеру' : 'Онлайн',
        customer: { name: u.name || 'Покупатель', phone: '+992 ' + fmtPhone(u.phone), address: [addrLine(a), a.entrance && 'подъезд ' + a.entrance, a.floor && 'этаж ' + a.floor, a.intercom && 'домофон ' + a.intercom, a.landmark && 'ориентир: ' + a.landmark].filter(Boolean).join(', ') },
        comment: [comment, { call: 'Если чего-то нет — позвонить', replace: 'Если чего-то нет — заменить похожим', remove: 'Если чего-то нет — убрать' }[C.cart.ifMissing]].filter(Boolean).join('. '),
        cancelReason: '', client: true, ifMissing: C.cart.ifMissing, fee, km: way.km,
      });
      for (const i of items) { const p = S.products.find(x => x.id === i.pid); if (p) p.stock = Math.max(0, r2(p.stock - i.qty)); }
      return no;
    });
    if (r == null) throw new Error('Магазин сейчас недоступен. Попробуйте ещё раз');
    order.no = r; order.local = true;
  } else order.no = C.nextNo++;
  C.orders.unshift(order); clear(); save();
  return order;
}

/** Заказ с текущим состоянием: этап, строки после сборки, суммы. */
export function view(o) {
  let status = 'new', items = o.items, sel = null;
  if (o.cloud) {
    sel = o.row; if (sel) { status = sel.status; items = sel.items; }
  } else if (o.local) {
    sel = readSeller()?.orders.find(x => x.id === o.id);
    if (sel) { status = sel.status; items = sel.items; }
  } else {
    const s = (Date.now() - o.ts) / 1000;
    status = o.cancelled ? 'cancelled' : s < 12 ? 'new' : s < 35 ? 'accepted' : s < 50 ? 'ready' : 'done';
  }
  if (o.cancelled) status = 'cancelled';
  // курьер взял заказ: едет в магазин — этап «передают курьеру», забрал — «в пути», передал — доставлен
  const cs = o.row?.courierStatus;
  const stage = status === 'cancelled' ? -1 : o.receivedAt || o.row?.receivedAt || cs === 'delivered' ? 4
    : cs === 'picked' || cs === 'at_client' ? 3 : cs === 'going' || cs === 'at_shop' ? Math.max(2, { new: 0, accepted: 1, ready: 2, done: 3 }[status]) : { new: 0, accepted: 1, ready: 2, done: 3 }[status];
  const shop = shopById(o.shopId);
  const rows = [];
  for (const i of items) {
    if (!i.missing) rows.push({ ...i, q: i.actual ?? i.qty, changed: i.actual != null && i.actual !== i.qty });
    else rows.push({ ...i, q: 0, missing: true });
  }
  const subs = items.map((i, n) => ({ i, n })).filter(x => x.i.sub);
  const sum = r2(items.reduce((s, i) => s + (i.missing ? 0 : (i.actual ?? i.qty) * i.price) + (i.sub?.status === 'ok' ? i.sub.qty * i.sub.price : 0), 0));
  const fee = o.fee;
  return {
    o, status, stage, rows, subs, sum, fee, total: r2(sum + fee), diff: r2(o.sum - sum), shop,
    waiting: subs.some(x => x.i.sub.status === 'wait'), reason: sel?.cancelReason || o.cancelReason || '',
    courier: o.row?.courier || null, cstep: cs || null,
    eta: o.ts + ((shop?.prep || 30) + (shop ? route(shop, o.addr).min : 15)) * 60000,
  };
}

export async function answerSub(o, n, yes) {
  if (o.cloud) return act('buyer_answer_sub', { p_order: o.id, p_n: n, p_yes: yes });
  updateSeller(S => { const x = S.orders.find(q => q.id === o.id); const i = x?.items[n]; if (i?.sub?.status === 'wait') { i.sub.status = yes ? 'ok' : 'no'; i.picked = false; } });
}
export async function cancel(o) {
  if (o.cloud) await act('buyer_cancel', { p_order: o.id });
  else if (o.local) updateSeller(S => {
    const x = S.orders.find(q => q.id === o.id); if (!x || x.status !== 'new') return;
    x.status = 'cancelled'; x.cancelReason = 'Клиент попросил отменить';
    for (const i of x.items) { const p = S.products.find(q => q.id === i.pid); if (p) p.stock = r2(p.stock + i.qty); }
  });
  o.cancelled = true; o.cancelReason = 'Вы отменили заказ'; save();
}
export async function received(o) {
  if (o.cloud) await act('buyer_received', { p_order: o.id });
  o.receivedAt = Date.now();
  if (o.local) updateSeller(S => { const x = S.orders.find(q => q.id === o.id); if (x) x.receivedAt = o.receivedAt; });
  save();
}
export async function sendReview(o, { rating, tags, text, likes }) {
  if (o.cloud) await act('buyer_review', { p_order: o.id, p_rating: rating, p_tags: tags, p_text: text, p_likes: likes, p_name: C.user?.name || '' });
  o.review = { rating, tags, text, ts: Date.now() };
  if (o.local) updateSeller(S => {
    const x = S.orders.find(q => q.id === o.id); if (!x) return;
    S.reviews.push({ id: uid(), orderId: x.id, orderNo: x.no, ts: Date.now(), name: C.user?.name || 'Покупатель', rating, tags, text,
      items: x.items.map(i => ({ pid: i.pid, name: i.name, like: likes[i.pid] ?? null })) });
  });
  save();
}
export async function reportProblem(o, reason, text) {
  if (o.cloud) await act('buyer_problem', { p_order: o.id, p_reason: reason, p_text: text });
  o.problem = { reason, text, ts: Date.now() };
  if (o.local) updateSeller(S => { const x = S.orders.find(q => q.id === o.id); if (x) x.problem = o.problem; });
  save();
}

/** Оценка курьера — одна на заказ. */
export async function rateCourier(o, rating) {
  await act('buyer_rate_courier', { p_order: o.id, p_rating: rating });
  o.courierRated = rating; save();
}
