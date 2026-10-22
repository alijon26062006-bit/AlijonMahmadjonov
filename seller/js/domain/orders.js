import { FEE } from '../config.js';
import { r2 } from '../lib/format.js';
import { S } from '../state.js';

export const orderTotal = o => o.items.reduce((s, i) => s + i.qty * i.price, 0);
export const orderCost = o => o.items.reduce((s, i) => s + i.qty * (i.cost || 0), 0);
// комиссия сервиса берётся только с заказов из приложения, продажи в магазине без комиссии
export const orderFee = o => o.source === 'app' ? r2(orderTotal(o) * FEE) : 0;
export function changeStockForOrder(o, sign) {
  for (const i of o.items) { const p = S.products.find(x => x.id === i.pid); if (p) p.stock = Math.max(0, p.stock + sign * i.qty); }
}
