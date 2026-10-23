import { calc, prodSales, range, trend, ZERO } from '../domain/analytics.js';
import { lines } from '../domain/orders.js';
import { addDays, ddmm, dkey, esc, money, parseKey, plural, r2 } from '../lib/format.js';
import { S, ui } from '../state.js';
import { copyText } from './catalog.js';

// Статистика
export function vStats() {
  const [a, b] = range(), { list, T, top } = calc(a, b);
  const avg = T.orders ? T.rev / T.orders : 0, margin = T.rev ? Math.round(T.profit / T.rev * 100) : 0;
  const per = (k, l) => `<button class="chip" data-period="${k}" aria-pressed="${ui.period === k}">${l}</button>`;
  const max = Math.max(1, ...list.map(d => d.rev));
  const step = list.length > 16 ? Math.ceil(list.length / 8) : 1;
  const pick = list.find(d => d.k === ui.pickDay);
  const byCat = {};
  for (const o of S.orders) { const k = dkey(o.ts); if (o.status !== 'done' || k < a || k > b) continue; for (const i of lines(o)) { const p = S.products.find(x => x.id === i.pid); const c = p ? p.cat : 'Удалённые товары'; byCat[c] = (byCat[c] || 0) + i.qty * i.price; } }
  const cats = Object.entries(byCat).sort((x, y) => y[1] - x[1]), catMax = Math.max(1, ...cats.map(c => c[1]));
  const dayRows = [...list].reverse().filter(d => d.orders || d.exp || d.cancelled);
  return `
    <div class="head"><div><div class="eyebrow">${ddmm(a)}${a !== b ? ' – ' + ddmm(b) : ''}</div><h1>Статистика</h1></div>
      <button class="btn" data-act="exportstats">Копировать для Excel</button></div>
    <div class="col" style="gap:10px">
      <div class="chips">${per('today', 'Сегодня')}${per('7', '7 дней')}${per('30', '30 дней')}${per('month', 'Этот месяц')}${per('custom', 'Свои даты')}</div>
      ${ui.period === 'custom' ? `<div class="row"><input class="input" type="date" id="fromD" value="${ui.from}" max="${today()}" style="width:auto" aria-label="С"><span class="muted">—</span><input class="input" type="date" id="toD" value="${ui.to}" max="${today()}" style="width:auto" aria-label="По"></div>` : ''}
    </div>
    <div class="kpis">
      <div class="kpi hero"><span>Выручка</span><b class="num">${money(T.rev)}</b></div>
      <div class="kpi ${T.profit < 0 ? 'neg' : ''}"><span>Чистая прибыль · ${margin}%</span><b class="num">${money(T.profit)}</b></div>
      <div class="kpi"><span>Заказов · продано ед.</span><b class="num">${T.orders} · ${T.qty}</b></div>
      <div class="kpi"><span>Средний чек</span><b class="num">${money(avg)}</b></div>
    </div>
    <section class="panel col">
      <div class="row between"><h2>Откуда прибыль</h2><span class="small muted">за выбранный период</span></div>
      <div class="tablewrap"><table><tbody>
        <tr><td>Выручка от продаж</td><td class="r">${money(T.rev)}</td></tr>
        <tr><td>− Закупочная стоимость проданного товара</td><td class="r">${money(T.cogs)}</td></tr>
        <tr><td>− Комиссия сервиса (заказы из приложения)</td><td class="r">${money(T.fee)}</td></tr>
        <tr><td>− Расходы (аренда, зарплата и др.)</td><td class="r">${money(T.exp)}</td></tr>
        <tr><td><b>= Чистая прибыль</b></td><td class="r"><b class="${T.profit < 0 ? 'neg' : ''}">${money(T.profit)}</b></td></tr>
      </tbody></table></div>
      ${T.cancelled ? `<span class="small muted">Отменено заказов: ${T.cancelled}. Они не входят в выручку.</span>` : ''}
    </section>
    ${list.length > 1 ? `<section class="panel chart">
      <div class="row between"><h2>Продажи по дням</h2><div class="legend"><span><i style="background:var(--bar2)"></i>Выручка</span><span><i style="background:var(--accent)"></i>Валовая прибыль</span></div></div>
      <div class="tip num">${pick ? `<b>${ddmm(pick.k)}</b>: выручка ${money(pick.rev)}, заказов ${pick.orders}, чистая прибыль ${money(pick.profit)}` : '<span class="muted">Нажмите на столбик, чтобы увидеть день</span>'}</div>
      <div class="bars">${list.map(d => `<button class="b" data-day="${d.k}" aria-pressed="${ui.pickDay === d.k}" aria-label="${ddmm(d.k)}: ${money(d.rev)}"><i style="height:${d.rev / max * 100}%"><em style="height:${d.rev ? Math.max(0, (d.rev - d.cogs - d.fee) / d.rev * 100) : 0}%"></em></i></button>`).join('')}</div>
      <div class="axis">${list.map((d, i) => `<span>${i % step === 0 ? ddmm(d.k).slice(0, 2) : ''}</span>`).join('')}</div>
      <span class="small muted">Валовая прибыль: выручка минус закупочная цена и комиссия сервиса. Высота столбика — выручка за день, самый высокий: ${money(max)}.</span>
    </section>` : ''}
    ${productTable(a, b)}
    <div class="split">
      <section class="panel col"><h2>Выручка по категориям</h2>
        ${cats.length ? cats.map(([c, v]) => `<div class="col" style="gap:4px"><div class="row between small"><span>${esc(c)}</span><b class="num">${money(v)}</b></div><div class="bar"><i style="width:${v / catMax * 100}%"></i></div></div>`).join('') : '<span class="muted">Нет продаж за этот период</span>'}
      </section>
    </div>
    <section class="panel tight"><div style="padding:16px 16px 6px"><h2>По дням</h2></div>
      ${dayRows.length ? `<div class="tablewrap"><table><thead><tr><th>Дата</th><th class="r">Заказов</th><th class="r">Продано</th><th class="r">Выручка</th><th class="r">Закупка</th><th class="r">Комиссия</th><th class="r">Расходы</th><th class="r">Прибыль</th></tr></thead><tbody>${dayRows.map(d => `<tr><td>${ddmm(d.k)}, ${parseKey(d.k).toLocaleDateString('ru-RU', { weekday: 'short' })}</td><td class="r">${d.orders}</td><td class="r">${d.qty}</td><td class="r">${money(d.rev)}</td><td class="r">${money(d.cogs)}</td><td class="r">${money(d.fee)}</td><td class="r">${d.exp ? money(d.exp) : '—'}</td><td class="r"><span class="${d.profit < 0 ? 'neg' : ''}">${money(d.profit)}</span></td></tr>`).join('')}</tbody></table></div>` : '<div class="empty">За этот период продаж и расходов нет</div>'}
    </section>`;
}
export function productTable(a, b) {
  const n = Math.round((parseKey(b) - parseKey(a)) / 864e5) + 1;
  const cur = prodSales(a, b), prev = prodSales(addDays(a, -n), addDays(a, -1));
  const rows = S.products.map(p => ({ p, ...(cur[p.id] || ZERO), prevQty: (prev[p.id] || ZERO).qty })).sort((x, y) => y.rev - x.rev || y.qty - x.qty);
  const total = rows.reduce((t, r) => t + r.rev, 0) || 1;
  const leaders = rows.filter(r => r.qty).slice(0, 3).map(r => r.p.id);
  const dead = rows.filter(r => !r.qty && r.p.active).length;
  return `<section class="panel tight"><div style="padding:16px 16px 6px;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:baseline"><h2>Продажи по товарам</h2><span class="small muted">изменение к предыдущим ${n} ${plural(n, 'дню', 'дням', 'дням')}</span></div>
    ${dead ? `<div class="alert" style="margin:6px 16px 10px"><span><b>${dead} ${plural(dead, 'товар не продавался', 'товара не продавались', 'товаров не продавались')}</b> за этот период. Проверьте фото, цену или сделайте скидку.</span></div>` : ''}
    <div class="tablewrap"><table><thead><tr><th>#</th><th>Товар</th><th class="r">Продано</th><th class="r">Заказов</th><th class="r">Выручка</th><th class="r">Доля</th><th class="r">Прибыль</th><th class="r">Динамика</th></tr></thead><tbody>
    ${rows.map((r, i) => `<tr><td class="num muted">${i + 1}</td><td style="white-space:normal;min-width:170px"><button class="linkrow" data-edit="${r.p.id}"><span translate="no">${esc(r.p.name)}</span></button>${leaders.includes(r.p.id) ? ' <span class="pill">Лидер</span>' : ''}${!r.qty && r.p.active ? ' <span class="pill warn">Не продаётся</span>' : ''}</td><td class="r">${r.qty} ${esc(r.p.unit)}</td><td class="r">${r.orders}</td><td class="r">${money(r.rev)}</td><td class="r">${Math.round(r.rev / total * 100)}%</td><td class="r">${money(r.profit)}</td><td class="r">${trend(r.qty, r.prevQty)}</td></tr>`).join('')}
    </tbody></table></div></section>`;
}
export function exportStats() {
  const [a, b] = range(), { list } = calc(a, b);
  const rows = [['Дата', 'Заказов', 'Продано', 'Выручка', 'Закупка', 'Комиссия', 'Расходы', 'Прибыль'], ...list.map(d => [d.k, d.orders, d.qty, r2(d.rev), r2(d.cogs), r2(d.fee), r2(d.exp), r2(d.profit)])];
  copyText(rows.map(r => r.join('\t')).join('\n'), 'Таблица скопирована. Вставьте её в Excel');
}
