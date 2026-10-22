import { FEE } from '../config.js';
import { r2 } from '../lib/format.js';
import { S } from '../state.js';

// Что реально уходит покупателю после сборки: фактический вес, без отсутствующих, с принятыми заменами
export function lines(o) {
  const out = [];
  for (const i of o.items) {
    if (!i.missing) out.push({ ...i, qty: i.actual ?? i.qty });
    if (i.sub && i.sub.status === 'ok') out.push({ ...i.sub, variant: '' });
  }
  return out;
}
export const orderTotal = o => lines(o).reduce((s, i) => s + i.qty * i.price, 0);
export const orderedTotal = o => o.items.reduce((s, i) => s + i.qty * i.price, 0);
export const orderCost = o => lines(o).reduce((s, i) => s + i.qty * (i.cost || 0), 0);
// комиссия сервиса берётся только с заказов из приложения, продажи в магазине без комиссии
export const orderFee = o => o.source === 'app' ? r2(orderTotal(o) * FEE) : 0;
export function changeStockForOrder(o, sign) {
  for (const i of o.items) { const p = S.products.find(x => x.id === i.pid); if (p) p.stock = Math.max(0, p.stock + sign * i.qty); }
}
