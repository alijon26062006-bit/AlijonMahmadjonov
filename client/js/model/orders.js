import { fmtPhone, r2, uid } from '../lib/format.js';
import { readSeller, updateSeller } from '../services/bridge.js';
import { C, save } from '../state.js';
import { clear, totals } from './cart.js';
import { shopById } from './catalog.js';
import { route } from './delivery.js';

// Заказы покупателя. Заказ в магазин из кабинета на этом устройстве уходит прямо в кабинет продавца,
// статус и сборку (вес, замены) берём оттуда. Заказы в магазины-примеры проходят этапы сами.

export const STAGES = ['Магазин получил заказ', 'Собирают заказ', 'Передают курьеру', 'Курьер в пути', 'Доставлен'];
export const addrLine = a => a ? [a.city, a.street, a.house && 'д. ' + a.house, a.apt && 'кв. ' + a.apt].filter(Boolean).join(', ') : '';

export function placeOrder({ pay, when }) {
  const { shop, rows, sum, fee, total, way } = totals();
  if (!way.ok) throw new Error(`Магазин не возит так далеко: ${way.km} км`);
  const a = C.addr, u = C.user;
  const items = rows.map(r => ({ pid: r.p.id, name: r.p.name, unit: r.p.unit, variant: r.variant, qty: r.qty, price: r.price, cost: null, opts: r.optNames.map(o => ({ name: o.name, price: o.price })) }));
  const comment = [C.cart.comment.trim(), shop.kind === 'food' && C.cart.cutlery ? 'Положите приборы' : ''].filter(Boolean).join('. ');
  const order = { id: uid(), shopId: shop.id, shopName: shop.name, kind: shop.kind, ts: Date.now(), items, sum, fee, total, km: way.km, pay, when, addr: { ...a }, ifMissing: C.cart.ifMissing, comment, phone: shop.phone || '' };
  if (shop.local) {
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
  if (o.local) {
    sel = readSeller()?.orders.find(x => x.id === o.id);
    if (sel) { status = sel.status; items = sel.items; }
  } else {
    const s = (Date.now() - o.ts) / 1000;
    status = o.cancelled ? 'cancelled' : s < 12 ? 'new' : s < 35 ? 'accepted' : s < 50 ? 'ready' : 'done';
  }
  if (o.cancelled) status = 'cancelled';
  const stage = status === 'cancelled' ? -1 : o.receivedAt ? 4 : { new: 0, accepted: 1, ready: 2, done: 3 }[status];
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
    eta: o.ts + ((shop?.prep || 30) + (shop ? route(shop, o.addr).min : 15)) * 60000,
  };
}

export function answerSub(o, n, yes) {
  updateSeller(S => { const x = S.orders.find(q => q.id === o.id); const i = x?.items[n]; if (i?.sub?.status === 'wait') { i.sub.status = yes ? 'ok' : 'no'; i.picked = false; } });
}
export function cancel(o) {
  if (o.local) updateSeller(S => {
    const x = S.orders.find(q => q.id === o.id); if (!x || x.status !== 'new') return;
    x.status = 'cancelled'; x.cancelReason = 'Клиент попросил отменить';
    for (const i of x.items) { const p = S.products.find(q => q.id === i.pid); if (p) p.stock = r2(p.stock + i.qty); }
  });
  o.cancelled = true; o.cancelReason = 'Вы отменили заказ'; save();
}
export function received(o) {
  o.receivedAt = Date.now();
  if (o.local) updateSeller(S => { const x = S.orders.find(q => q.id === o.id); if (x) x.receivedAt = o.receivedAt; });
  save();
}
export function sendReview(o, { rating, tags, text, likes }) {
  o.review = { rating, tags, text, ts: Date.now() };
  if (o.local) updateSeller(S => {
    const x = S.orders.find(q => q.id === o.id); if (!x) return;
    S.reviews.push({ id: uid(), orderId: x.id, orderNo: x.no, ts: Date.now(), name: C.user?.name || 'Покупатель', rating, tags, text,
      items: x.items.map(i => ({ pid: i.pid, name: i.name, like: likes[i.pid] ?? null })) });
  });
  save();
}
export function reportProblem(o, reason, text) {
  o.problem = { reason, text, ts: Date.now() };
  if (o.local) updateSeller(S => { const x = S.orders.find(q => q.id === o.id); if (x) x.problem = o.problem; });
  save();
}
