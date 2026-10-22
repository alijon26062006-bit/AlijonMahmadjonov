import { FEE } from '../config.js';
import { addDays, dkey, parseKey, today } from '../lib/format.js';
import { S, ui } from '../state.js';
import { orderFee } from './orders.js';

// статистика: расчёт
export function range() {
  const t = today();
  if (ui.period === 'today') return [t, t];
  if (ui.period === '7') return [addDays(t, -6), t];
  if (ui.period === '30') return [addDays(t, -29), t];
  if (ui.period === 'month') return [t.slice(0, 8) + '01', t];
  let a = ui.from, b = ui.to; if (a > b) [a, b] = [b, a];
  if ((parseKey(b) - parseKey(a)) / 864e5 > 366) a = addDays(b, -366);
  return [a, b];
}
export function calc(a, b) {
  const days = []; for (let k = a; k <= b; k = addDays(k, 1)) days.push(k);
  const D = Object.fromEntries(days.map(k => [k, { k, rev: 0, cogs: 0, fee: 0, exp: 0, orders: 0, qty: 0, cancelled: 0 }]));
  const prod = {};
  for (const o of S.orders) {
    const k = dkey(o.ts); const d = D[k]; if (!d) continue;
    if (o.status === 'cancelled') { d.cancelled++; continue; }
    if (o.status !== 'done') continue;
    d.orders++; d.fee += orderFee(o);
    const feeK = o.source === 'app' ? FEE : 0;
    for (const i of o.items) {
      d.rev += i.qty * i.price; d.cogs += i.qty * (i.cost || 0); d.qty += i.qty;
      const key = i.name + (i.variant ? ' · ' + i.variant : '');
      const p = prod[key] || (prod[key] = { name: key, qty: 0, rev: 0, profit: 0 });
      p.qty += i.qty; p.rev += i.qty * i.price; p.profit += i.qty * (i.price * (1 - feeK) - (i.cost || 0));
    }
  }
  // закупка товара уже учтена через закупочную цену — её не вычитаем второй раз
  for (const e of S.expenses) { const d = D[e.date]; if (d && !e.stockPurchase) d.exp += e.amount; }
  const list = days.map(k => ({ ...D[k], profit: D[k].rev - D[k].cogs - D[k].fee - D[k].exp }));
  const T = list.reduce((t, d) => { for (const f of ['rev', 'cogs', 'fee', 'exp', 'orders', 'qty', 'cancelled', 'profit']) t[f] += d[f]; return t; }, { rev: 0, cogs: 0, fee: 0, exp: 0, orders: 0, qty: 0, cancelled: 0, profit: 0 });
  return { list, T, top: Object.values(prod).sort((x, y) => y.rev - x.rev) };
}

// продажи каждого товара за период (только выполненные заказы)
export function prodSales(a, b) {
  const m = {};
  for (const o of S.orders) {
    if (o.status !== 'done') continue; const k = dkey(o.ts); if (k < a || k > b) continue;
    const feeK = o.source === 'app' ? FEE : 0;
    for (const i of o.items) { const r = m[i.pid] || (m[i.pid] = { qty: 0, rev: 0, profit: 0, orders: 0 }); r.qty += i.qty; r.rev += i.qty * i.price; r.profit += i.qty * (i.price * (1 - feeK) - (i.cost || 0)); r.orders++; }
  }
  return m;
}
export const ZERO = { qty: 0, rev: 0, profit: 0, orders: 0 };
export function trend(cur, prev) {
  if (!prev && !cur) return '<span class="muted">—</span>';
  if (!prev) return '<span class="pill">новый</span>';
  const d = Math.round((cur - prev) / prev * 100);
  return d >= 0 ? `<b style="color:var(--ok)">▲ ${d}%</b>` : `<b style="color:var(--bad)">▼ ${-d}%</b>`;
}

export function readiness() {
  const ps = S.products, sh = S.shop;
  const withPhoto = ps.filter(p => p.imgs.length).length, withCost = ps.filter(p => p.cost != null).length;
  const checks = [
    [!!(sh.name && sh.phone && sh.address), 'Магазин: название, телефон, адрес', 'shop'],
    [!!sh.logo, 'Загружен логотип', 'shop'],
    [sh.schedule.some(d => d.open), 'Указан график работы', 'shop'],
    [sh.alif.status === 'connected', 'Магазин подключён к Alif для приёма оплаты', 'finance'],
    [ps.length >= 5, `Не меньше 5 товаров (сейчас ${ps.length})`, 'catalog'],
    [ps.length > 0 && withPhoto === ps.length, `Фото у каждого товара (${withPhoto} из ${ps.length})`, 'catalog'],
    [ps.length > 0 && withCost === ps.length, `Закупочная цена у каждого товара (${withCost} из ${ps.length})`, 'catalog'],
  ];
  return { checks, pct: Math.round(checks.filter(c => c[0]).length / checks.length * 100) };
}
