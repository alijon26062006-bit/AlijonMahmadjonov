import * as api from '../api.js';
import { count, esc, money, when } from '../lib/format.js';
import { empty, head, ICON, section, stat, tabs } from '../ui.js';

// Главный экран: цифры за сегодня и неделю, график заказов, срочное. И экран «Проверки» — всё, что требует внимания.

const TARGET = { order: id => `#/order/${encodeURIComponent(id)}`, shop: id => `#/shop/${id}`, user: id => `#/person/${id}`, review: () => '#/reviews?f=complaints' };
const LEVEL = { high: ['bad', 'Срочно'], mid: ['warn', 'Сегодня'], low: ['', 'Когда будет время'] };

function checkList(list) {
  if (!list.length) return empty('Всё в порядке', 'Проверки ничего не нашли — магазины отвечают, курьеры на связи, проблем нет');
  return `<div class="list">${list.map(c => {
    const [tone, label] = LEVEL[c.level] || LEVEL.low, href = TARGET[c.target?.kind]?.(c.target.id) || '#/checks';
    return `<a class="item check ${tone}" href="${href}"><span class="dot ${tone}" aria-hidden="true"></span>
      <span class="item-main"><b>${esc(c.title)}</b><span class="item-sub">${esc(c.text)}</span></span>
      <span class="item-end"><span class="chip ${tone}">${label}</span>${c.at ? `<span class="item-sub">${when(c.at)}</span>` : ''}</span>${ICON.chevron}</a>`;
  }).join('')}</div>`;
}

/** Столбики за 14 дней: высота — число заказов, подпись — выручка. Без библиотек. */
function chart(days) {
  const max = Math.max(1, ...days.map(d => d.orders));
  return `<div class="bars" role="img" aria-label="Заказы за 14 дней">${days.map(d => {
    const dt = new Date(d.d), lbl = `${dt.getDate()}.${String(dt.getMonth() + 1).padStart(2, '0')}`;
    return `<div class="bar" title="${lbl}: ${d.orders} заказов, ${money(d.total)}, отмен ${d.cancelled}">
      <span class="bar-n num">${d.orders || ''}</span><span class="bar-t"><span class="bar-f" style="height:${Math.round(d.orders / max * 100)}%"><i style="height:${d.orders ? Math.round(d.cancelled / d.orders * 100) : 0}%"></i></span></span><span class="bar-d">${lbl}</span></div>`;
  }).join('')}</div><p class="small muted legend"><span class="sw"></span> заказы <span class="sw bad"></span> из них отменены</p>`;
}

export const overview = {
  title: 'Обзор',
  load: async () => { const [o, c] = await Promise.all([api.overview(), api.checks()]); return { o, c }; },
  html({ o, c }) {
    const high = c.filter(x => x.level === 'high');
    return `${head('Обзор', `Обновлено ${when(new Date().toISOString())}`)}
      ${high.length ? `<a class="alert bad" href="#/checks"><div><b>Срочно: ${high.length}</b><br>${esc(high.slice(0, 2).map(x => x.title).join(' · '))}${high.length > 2 ? '…' : ''}</div>${ICON.chevron}</a>` : ''}
      <div class="stats">
        ${stat('Заказов сегодня', count(o.orders_today), `${money(o.gmv_today)}`, '#/orders?from=today')}
        ${stat('В работе сейчас', count(o.active), 'новые, собирают, в пути', '#/orders?status=active')}
        ${stat('Проблемы', count(o.problems), 'от покупателей и курьеров', '#/orders?status=problem')}
        ${stat('Требует внимания', count(c.length), `срочно: ${high.length}`, '#/checks')}
      </div>
      ${section('Заказы за 14 дней', chart(o.days || []))}
      <div class="stats">
        ${stat('Оборот за 7 дней', money(o.gmv_7d), `заказов ${count(o.orders_7d)}, отмен ${count(o.cancelled_7d)}`)}
        ${stat('Доставка за 7 дней', money(o.fees_7d), `курьерам ${money(o.courier_pay_7d)}`)}
        ${stat('Жалобы на отзывы', count(o.complaints), 'ждут решения', '#/reviews?f=complaints')}
        ${stat('Заблокировано', count(o.blocked), 'люди, магазины, курьеры', '#/people?role=blocked')}
      </div>
      <div class="stats">
        ${stat('Люди', count(o.users), `новых сегодня ${count(o.users_today)}`, '#/people')}
        ${stat('Покупатели', count(o.buyers), 'делали заказы', '#/people?role=buyer')}
        ${stat('Магазины', count(o.shops), `открыто ${count(o.shops_open)}`, '#/shops')}
        ${stat('Курьеры', count(o.couriers), `на линии ${count(o.couriers_online)}`, '#/couriers')}
        ${stat('Товары', count(o.products), `в продаже ${count(o.products_live)}`, '#/products')}
        ${stat('Админы', count(o.admins), '', '#/roles')}
      </div>
      ${c.length ? section('Требует внимания', checkList(c.slice(0, 6)), `<a class="link" href="#/checks">Все ${c.length}</a>`) : ''}`;
  },
};

export const checks = {
  title: 'Проверки',
  load: () => api.checks(),
  html(list, q) {
    const f = q.f || '', shown = f ? list.filter(c => c.level === f) : list, n = l => list.filter(c => c.level === l).length;
    return `${head('Проверки', 'Система сама ищет, что пошло не так: магазин молчит, нет курьера, курьер без связи, проблемы, жалобы, пустые витрины')}
      ${tabs('f', f, [['', 'Все', list.length], ['high', 'Срочно', n('high')], ['mid', 'Сегодня', n('mid')], ['low', 'Позже', n('low')]])}
      ${checkList(shown)}`;
  },
};
