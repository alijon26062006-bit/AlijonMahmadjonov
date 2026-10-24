import { WEIGHT_UNITS } from '../config.js';
import { r2 } from '../lib/format.js';
import { C, save } from '../state.js';
import { productIn, shopById } from './catalog.js';
import { feeFor, route } from './delivery.js';

// Корзина: товары одного магазина. Строка = товар + вариант + добавки.
export const stepOf = p => WEIGHT_UNITS.includes(p.unit) ? (p.minStep || 0.5) : 1;
export const keyOf = (pid, vid = '', opts = []) => [pid, vid, [...opts].sort().join('+')].join('|');
export const unitPrice = (p, vid, opts = []) => (p.variants.find(v => v.id === vid)?.price ?? p.price) + p.options.filter(o => opts.includes(o.id)).reduce((s, o) => s + o.price, 0);

export function qtyInCart(pid) { return C.cart.items.filter(i => i.pid === pid).reduce((s, i) => s + i.qty, 0); }

/** Добавить товар. Если в корзине другой магазин — вернёт 'other', чтобы спросить покупателя. */
export function add(shop, p, { vid = '', opts = [], qty } = {}, force = false) {
  if (C.cart.items.length && C.cart.shopId !== shop.id) { if (!force) return 'other'; clear(); }
  C.cart.shopId = shop.id;
  const key = keyOf(p.id, vid, opts), step = stepOf(p), q = qty ?? step;
  const line = C.cart.items.find(i => i.key === key);
  if (line) line.qty = r2(line.qty + q); else C.cart.items.push({ key, pid: p.id, vid, opts, qty: q });
  save(); return 'ok';
}
/** Изменить количество строки на шаг товара (+1 / −1). */
export function bump(key, dir) {
  const line = C.cart.items.find(i => i.key === key); if (!line) return;
  const p = productIn(shopById(C.cart.shopId), line.pid); const step = p ? stepOf(p) : 1;
  line.qty = r2(line.qty + dir * step);
  if (line.qty <= 0) C.cart.items = C.cart.items.filter(i => i !== line);
  if (!C.cart.items.length) C.cart.shopId = null;
  save();
}
/** −/+ на карточке товара без вариантов: работает с простой строкой. */
export function bumpSimple(shop, p, dir) {
  const key = keyOf(p.id);
  if (dir > 0 && !C.cart.items.some(i => i.key === key)) return add(shop, p);
  bump(key, dir); return 'ok';
}
export function clear() { C.cart.items = []; C.cart.shopId = null; C.cart.comment = ''; save(); }

/** Строки корзины с ценами; товары, которые магазин убрал, отмечаем отдельно. */
export function lines() {
  const shop = shopById(C.cart.shopId); if (!shop) return { shop: null, rows: [], gone: C.cart.items.length };
  const rows = [], goneKeys = [];
  for (const i of C.cart.items) {
    const p = productIn(shop, i.pid);
    if (!p || (i.vid && !p.variants.some(v => v.id === i.vid))) { goneKeys.push(i.key); continue; }
    const price = unitPrice(p, i.vid, i.opts);
    const qty = Math.min(i.qty, p.stock ?? Infinity);
    rows.push({ ...i, qty, p, price, sum: r2(price * qty), variant: p.variants.find(v => v.id === i.vid)?.name || '', optNames: p.options.filter(o => i.opts.includes(o.id)) });
  }
  if (goneKeys.length) { C.cart.items = C.cart.items.filter(i => !goneKeys.includes(i.key)); save(); }
  return { shop, rows, gone: goneKeys.length };
}
export function totals() {
  const { shop, rows } = lines();
  const sum = r2(rows.reduce((s, r) => s + r.sum, 0)), fee = rows.length ? feeFor(shop) : 0, way = shop ? route(shop) : null;
  const count = rows.reduce((s, r) => s + (r.p.unit === 'кг' || r.p.unit === 'л' ? 1 : r.qty), 0);
  return { shop, rows, sum, fee, way, total: r2(sum + fee), count, left: shop ? Math.max(0, r2(shop.minOrder - sum)) : 0 };
}
