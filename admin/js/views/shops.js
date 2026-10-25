import * as api from '../api.js';
import { count, esc, KINDS, money, phone, STAFF_ROLES, tel, when } from '../lib/format.js';
import { empty, head, ICON, kv, searchBar, section, stat, tabs } from '../ui.js';
import { logList, orderList, who } from './parts.js';

// Магазины и товары всех продавцов. Карточка магазина — владелец, сотрудники, товары, заказы, отзывы, расходы, журнал.

const img = src => src ? `<img class="thumb" src="${esc(src)}" alt="" loading="lazy">` : `<span class="thumb ph" aria-hidden="true">${ICON.box}</span>`;

export const shops = {
  title: 'Магазины',
  load: q => api.shops(q.q || ''),
  html(list, q) {
    const f = q.f || '';
    const shown = list.filter(s => !f || (f === 'blocked' && s.blocked) || (f === 'paused' && s.paused && !s.blocked) || (f === 'open' && !s.paused && !s.blocked) || (f === 'nopin' && !s.has_pin));
    return `${head('Магазины', 'Все продавцы: кто владелец, сколько товаров и заказов, что не так')}
      ${searchBar(q.q || '', 'Название, город или телефон')}
      ${tabs('f', f, [['', 'Все', list.length], ['open', 'Открыты', list.filter(s => !s.paused && !s.blocked).length], ['paused', 'На паузе', list.filter(s => s.paused && !s.blocked).length],
        ['blocked', 'Заблокированы', list.filter(s => s.blocked).length], ['nopin', 'Без точки на карте', list.filter(s => !s.has_pin).length]])}
      ${shown.length ? `<div class="list">${shown.map(s => `<a class="item" href="#/shop/${s.id}">${img(s.logo)}
        <span class="item-main"><b>${esc(s.name)}</b> ${s.blocked ? '<span class="chip bad">Заблокирован</span>' : s.paused ? '<span class="chip warn">Пауза</span>' : '<span class="chip ok">Открыт</span>'}
          <span class="item-sub">${esc(KINDS[s.kind] || s.kind)} · ${esc(s.city)} · владелец ${s.owner?.phone ? phone(s.owner.phone) : '—'}${s.staff ? ` · сотрудников ${s.staff}` : ''}</span>
          <span class="item-sub">товаров ${s.products_live}/${s.products} · заказов за 30 дн ${s.orders_30d} · ${s.rating_count ? `${s.rating} ★` : 'без оценок'}${s.active ? ` · <b>в работе ${s.active}</b>` : ''}</span></span>
        <span class="item-end"><b class="num">${money(s.revenue_30d)}</b><span class="item-sub">за 30 дней</span></span>${ICON.chevron}</a>`).join('')}</div>` : empty('Магазинов нет')}`;
  },
};

export const shop = {
  title: 'Магазин',
  load: (q, id) => api.shop(id),
  html(d) {
    const s = d.shop, st = d.stats, live = d.products.filter(p => p.active && !p.blocked && p.stock > 0).length;
    const alif = d.alif?.status === 'connected' ? 'подключён' : d.alif?.status === 'pending' ? 'на проверке' : 'не подключён';
    return `${head(esc(s.name), `${esc(KINDS[s.kind] || s.kind)} · ${esc(s.city)} · с ${when(s.created_at)}`, '', '#/shops')}
      ${s.blocked ? `<div class="alert bad" role="alert"><div><b>Магазин заблокирован</b><br>${esc(s.block_reason)}<br><span class="small">Покупатели его не видят, заказы не принимаются. Владелец видит причину у себя в кабинете</span></div></div>` : ''}
      <div class="actions">
        ${s.phone ? `<a class="btn" href="${tel(s.phone)}">${ICON.phone} Позвонить в магазин</a>` : ''}
        ${s.blocked ? `<button class="btn" data-act="shop-unblock" data-id="${s.id}">Разблокировать</button>` : `<button class="btn danger" data-act="shop-block" data-id="${s.id}">${ICON.lock} Заблокировать магазин</button>`}
        <a class="btn" href="#/orders?shop=${s.id}">Все заказы магазина</a>
      </div>
      <div class="stats">
        ${stat('Выручка', money(st.revenue), `заказов ${count(st.orders)}`)}
        ${stat('Из приложения', count(st.app_orders), `продаж в магазине ${count(st.shop_sales)}`)}
        ${stat('Отменено', count(st.cancelled), st.orders ? `${Math.round(st.cancelled / st.orders * 100)}%` : '')}
        ${stat('Принимает заказ', st.avg_accept_min != null ? `${st.avg_accept_min} мин` : '—', 'в среднем за 30 дней')}
        ${stat('Рейтинг', s.rating_count ? `${s.rating} ★` : '—', `оценок ${s.rating_count}`)}
        ${stat('Расходы', money(st.expenses_30d), 'за 30 дней')}
      </div>
      ${section('Люди магазина', `<div class="list">
        <a class="item" href="#/person/${d.owner?.id}">${ICON.shop}<span class="item-main"><b>Владелец: ${who(d.owner)}</b><span class="item-sub">${d.owner?.phone ? phone(d.owner.phone) : ''} · видит всё, включая деньги</span></span>${ICON.chevron}</a>
        ${d.staff.map(x => x.user ? `<a class="item" href="#/person/${x.user.id}">${ICON.people}<span class="item-main"><b>${esc(x.name)} — ${esc(STAFF_ROLES[x.role] || x.role)}</b><span class="item-sub">${phone(x.phone)}</span></span>${ICON.chevron}</a>`
          : `<div class="item">${ICON.people}<span class="item-main"><b>${esc(x.name)} — ${esc(STAFF_ROLES[x.role] || x.role)}</b><span class="item-sub">${phone(x.phone)} · ещё ни разу не входил</span></span></div>`).join('')}
        </div>`)}
      ${section('Данные магазина', `<div class="kvs">${kv('Телефон', s.phone ? phone(s.phone) : '<span class="bad-t">нет</span>')}${kv('Адрес', esc([s.address, s.landmark].filter(Boolean).join(', ') || '—'))}
        ${kv('Точка на карте', s.lat != null ? `${s.lat.toFixed(5)}, ${s.lng.toFixed(5)}` : '<span class="bad-t">нет — курьер не построит маршрут</span>')}
        ${kv('Сейчас', s.paused ? 'на паузе (поставил сам магазин)' : 'принимает заказы')}${kv('Доставка / самовывоз', `${s.delivery ? 'да' : 'нет'} / ${s.pickup ? 'да' : 'нет'}`)}
        ${kv('Минимальный заказ', money(s.min_order))}${kv('Сборка', `${s.prep_min} мин`)}${kv('Оплата картой (Alif)', alif)}</div>`)}
      ${section(`Товары · ${live} в продаже из ${d.products.length}`, d.products.length ? `<div class="list">${d.products.map(productItem).join('')}</div>` : empty('Товаров нет'))}
      ${section(`Заказы · последние ${d.orders.length}`, orderList(d.orders, { showShop: false }))}
      ${section(`Отзывы · ${d.reviews.length}`, reviewMini(d.reviews))}
      ${section('Что меняли админы', logList(d.log))}`;
  },
};

function productItem(p) {
  const tone = p.blocked ? ['bad', 'Скрыт админом'] : !p.active ? ['', 'Снят с продажи'] : p.stock <= 0 ? ['warn', 'Нет в наличии'] : ['ok', 'В продаже'];
  return `<div class="item">${img(p.img)}<span class="item-main"><b>${esc(p.name)}</b> <span class="chip ${tone[0]}">${tone[1]}</span>
      <span class="item-sub">арт. ${p.sku} · ${esc(p.cat || 'без категории')} · ${money(p.price)} за ${esc(p.unit)} · остаток ${p.stock}${p.expiry ? ` · годен до ${esc(p.expiry)}` : ''}</span>
      ${p.blocked ? `<span class="item-sub bad-t">${esc(p.block_reason)}</span>` : ''}${p.shop ? `<a class="item-sub link" href="#/shop/${p.shop.id}">${esc(p.shop.name)}</a>` : ''}</span>
    <span class="item-end">${p.blocked ? `<button class="btn sm" data-act="product-unblock" data-id="${esc(p.id)}">Вернуть</button>`
      : `<button class="btn sm danger" data-act="product-block" data-id="${esc(p.id)}">Скрыть</button>`}</span></div>`;
}

const stars = n => '★'.repeat(n) + '☆'.repeat(5 - n);
function reviewMini(list) {
  if (!list.length) return empty('Отзывов нет');
  return `<div class="list">${list.slice(0, 30).map(r => `<div class="item"><span class="item-main"><b>${stars(r.rating)} ${esc(r.name)}</b>
    ${r.complaint?.hidden ? ' <span class="chip">Скрыт</span>' : r.complaint && !r.complaint.decided_at ? ' <span class="chip warn">Жалоба</span>' : ''}
    <span class="item-sub">${esc(r.text || 'без текста')} · заказ № ${r.order_no}</span>${r.reply ? `<span class="item-sub">Ответ магазина: ${esc(r.reply)}</span>` : ''}</span>
    <span class="item-end item-sub">${when(r.created_at)}</span></div>`).join('')}</div>${list.length > 30 ? '<a class="link" href="#/reviews">Все отзывы</a>' : ''}`;
}

export const products = {
  title: 'Товары',
  load: q => api.products(q.q || '', q.f || ''),
  html(list, q) {
    return `${head('Товары', 'Все товары всех магазинов. Скрыть товар — он пропадёт у покупателей, магазин увидит причину')}
      ${searchBar(q.q || '', 'Название, артикул или категория')}
      ${tabs('f', q.f || '', [['', 'Все'], ['blocked', 'Скрытые админом'], ['off', 'Сняты магазином'], ['empty', 'Нет в наличии'], ['expired', 'Просрочены']])}
      <p class="small muted">Найдено: ${list.length}</p>
      ${list.length ? `<div class="list">${list.map(productItem).join('')}</div>` : empty('Товаров не нашли')}`;
  },
};
