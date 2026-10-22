import { LOW } from '../config.js';
import { calc, prodSales, readiness, trend, ZERO } from '../domain/analytics.js';
import { addDays, esc, money, plural, today } from '../lib/format.js';
import { newCount, S } from '../state.js';
import { ICON, plusI, stockPill, thumb } from '../ui/dom.js';
import { rating, stars, unansweredBad } from '../domain/reviews.js';
import { can } from '../domain/staff.js';

// Главная
export function vHome() {
  const t = today(), { T } = calc(t, t), y = calc(addDays(t, -1), addDays(t, -1)).T;
  const nc = newCount(), active = S.orders.filter(o => o.status === 'accepted' || o.status === 'ready').length;
  const low = S.products.filter(p => p.active && p.stock <= LOW);
  const delta = y.rev ? Math.round((T.rev - y.rev) / y.rev * 100) : null;
  const ready = readiness(), rb = unansweredBad(), R = rating();
  return `
    <div class="head"><div><div class="eyebrow">${new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}</div><h1>${esc(S.shop.name)}</h1></div>
      <div class="row"><button class="btn" data-act="sale">${plusI} Продажа в магазине</button><button class="btn primary" data-act="add">${plusI} Товар</button></div></div>
    ${S.shop.paused ? `<div class="alert bad"><span><b>Приём заказов на паузе.</b> Покупатели видят магазин закрытым.</span><button class="btn sm" data-act="pause">Снова принимать заказы</button></div>` : ''}
    ${nc ? `<div class="alert bad"><span><b>${nc} ${plural(nc, 'новый заказ', 'новых заказа', 'новых заказов')}</b> ждёт ответа. Покупатель ждёт: примите или отклоните заказ как можно быстрее.</span><button class="btn sm primary" data-nav="orders">Открыть заказы</button></div>` : ''}
    ${rb ? `<div class="alert"><span><b>${rb} ${plural(rb, 'плохой отзыв', 'плохих отзыва', 'плохих отзывов')} без ответа.</b> Ответьте покупателю — другие видят, как магазин решает проблемы.</span><button class="btn sm" data-nav="reviews">Ответить</button></div>` : ''}
    <div class="kpis">
      <div class="kpi hero"><span>Выручка сегодня</span><b class="num">${money(T.rev)}</b><span>${delta == null ? 'вчера продаж не было' : (delta >= 0 ? '+' : '') + delta + '% к вчера'}</span></div>
      ${can('stats') ? `<div class="kpi ${T.profit < 0 ? 'neg' : ''}"><span>Чистая прибыль сегодня</span><b class="num">${money(T.profit)}</b></div>` : ''}
      <div class="kpi"><span>Выполнено заказов</span><b class="num">${T.orders}</b></div>
      <div class="kpi"><span>Заказы в работе</span><b class="num">${active}</b></div>
      <button class="kpi link" data-nav="reviews"><span>Рейтинг магазина</span><b class="num">${R.isNew ? 'Новый' : R.value.toLocaleString('ru-RU', { minimumFractionDigits: 1 })}</b><span>${R.isNew ? `оценок ${R.count} из 10` : `<span class="stars">${stars(R.value)}</span> · ${R.count} ${plural(R.count, 'оценка', 'оценки', 'оценок')}`}</span></button>
    </div>
    ${hitsBlock()}
    <div class="split">
      <section class="panel col">
        <div class="row between"><h2>Готовность к запуску</h2><b class="num" style="color:var(--ink)">${ready.pct}%</b></div>
        <div class="bar"><i style="width:${ready.pct}%"></i></div>
        <ul class="checklist">${ready.checks.map(([ok, t, nav]) => `<li><span class="dot ${ok ? 'ok' : ''}">${ok ? ICON.check : ''}</span><span style="flex:1">${t}</span>${!ok && nav ? `<button class="btn sm" data-nav="${nav}">Исправить</button>` : ''}</li>`).join('')}</ul>
      </section>
      <section class="col">
        <div class="row between"><h2>Нужно пополнить</h2>${low.length ? `<span class="pill warn">${low.length}</span>` : ''}</div>
        ${low.length ? `<div class="plist">${low.slice(0, 6).map(p => `<div class="prow compact"><button class="open" data-edit="${p.id}">${thumb(p)}<div style="min-width:0"><div class="pname">${esc(p.name)}</div><div class="pmeta">${stockPill(p)}</div></div></button><div class="stepper"><button class="iconbtn" data-stock="${p.id}" data-d="10" aria-label="Добавить 10">+10</button></div></div>`).join('')}</div>` : '<div class="panel muted">Все товары в наличии.</div>'}
      </section>
    </div>`;
}
export function hitsBlock() {
  const t = today(), m = prodSales(addDays(t, -6), t), pm = prodSales(addDays(t, -13), addDays(t, -7));
  const list = S.products.map(p => ({ p, ...(m[p.id] || ZERO) })).filter(x => x.qty).sort((x, y) => y.qty - x.qty).slice(0, 5);
  if (!list.length) return '';
  const mx = list[0].qty;
  return `<section class="panel col"><div class="row between"><h2>Хиты недели</h2><button class="btn sm" data-nav="stats">Все товары</button></div>
    ${list.map((x, i) => `<button class="hitrow" data-edit="${x.p.id}"><span class="rank num">${i + 1}</span>${thumb(x.p)}<span style="min-width:0"><span class="pname" style="display:block">${esc(x.p.name)}</span><span class="bar" style="display:block;margin-top:6px"><i style="width:${x.qty / mx * 100}%"></i></span></span><span style="text-align:right"><b class="num">${x.qty} ${esc(x.p.unit)}</b><br><span class="small num">${trend(x.qty, (pm[x.p.id] || ZERO).qty)}</span></span></button>`).join('')}
    <span class="small muted">Продано за последние 7 дней, в сравнении с неделей до этого.</span></section>`;
}
