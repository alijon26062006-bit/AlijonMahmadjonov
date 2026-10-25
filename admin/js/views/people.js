import * as api from '../api.js';
import { esc, money, phone, ROLES, roleChips, STAFF_ROLES, tel, when, ago } from '../lib/format.js';
import { empty, head, ICON, kv, searchBar, section, tabs } from '../ui.js';
import { logList, orderList, peopleList } from './parts.js';

// Люди: все учётные записи с ролями. Карточка человека — все его связи: магазин, где он сотрудник, анкета курьера, заказы, доставки, отзывы.

export const people = {
  title: 'Люди',
  load: q => api.users(q.q || '', q.role || ''),
  html(list, q) {
    const role = q.role || '';
    return `${head('Люди', 'Каждый номер телефона — одна учётная запись. У одного человека может быть несколько ролей сразу')}
      ${searchBar(q.q || '', 'Номер, имя или почта')}
      ${tabs('role', role, [['', 'Все'], ...Object.entries(ROLES).map(([k, r]) => [k, r.name]), ['none', 'Без роли'], ['blocked', 'Заблокированы']])}
      <p class="small muted">Найдено: ${list.length}</p>
      ${peopleList(list)}`;
  },
};

export const person = {
  title: 'Человек',
  load: (q, id) => api.user(id),
  html(u) {
    const name = u.name || (u.phone ? phone(u.phone) : u.email);
    const b = u.block?.active ? u.block : null, c = u.courier, st = u.stats || {};
    const isPhone = !!u.phone;
    const actions = [
      isPhone ? `<a class="btn" href="${tel(u.phone)}">${ICON.phone} Позвонить</a>` : '',
      b ? `<button class="btn" data-act="user-unblock" data-id="${u.id}">Разблокировать</button>`
        : `<button class="btn danger" data-act="user-block" data-id="${u.id}">${ICON.lock} Заблокировать</button>`,
      !isPhone && !u.admin ? `<button class="btn" data-act="admin-add" data-id="${u.id}">Сделать админом</button>` : '',
      u.admin ? `<button class="btn" data-act="admin-remove" data-id="${u.id}">Забрать права админа</button>` : '',
    ].join('');
    const links = [];
    if (u.shop) links.push(`<a class="item" href="#/shop/${u.shop.id}">${ICON.shop}<span class="item-main"><b>Владелец магазина «${esc(u.shop.name)}»</b>
      <span class="item-sub">${esc(u.shop.city || '')}${u.shop.paused ? ' · на паузе' : ''}</span></span>${u.shop.blocked ? '<span class="chip bad">Заблокирован</span>' : ''}${ICON.chevron}</a>`);
    for (const s of u.staff_in || []) links.push(`<a class="item" href="#/shop/${s.shop_id}">${ICON.people}<span class="item-main"><b>${esc(STAFF_ROLES[s.role] || s.role)} в магазине «${esc(s.shop)}»</b>
      <span class="item-sub">в списке сотрудников как «${esc(s.name)}»</span></span>${ICON.chevron}</a>`);
    if (c) links.push(`<a class="item" href="#/couriers">${ICON.car}<span class="item-main"><b>Курьер: ${esc(c.name)}</b>
      <span class="item-sub">${esc([c.car, c.plate].filter(Boolean).join(' · '))} · ${c.online ? 'на линии' : 'не на линии'} · место ${ago(c.loc_at)}</span></span>
      <span class="chip ${c.status === 'active' ? 'ok' : 'bad'}">${c.status === 'active' ? 'Работает' : 'Заблокирован'}</span>${ICON.chevron}</a>`);
    if (st.orders) links.push(`<div class="item">${ICON.orders}<span class="item-main"><b>Покупатель: ${st.orders} заказов на ${money(st.spent)}</b>
      <span class="item-sub">отменено ${st.cancelled}, с проблемой ${st.problems}</span></span></div>`);
    if (u.admin) links.push(`<div class="item">${ICON.roles}<span class="item-main"><b>Админ</b><span class="item-sub">с ${when(u.admin.added_at)}${u.admin.note ? ' · ' + esc(u.admin.note) : ''}</span></span></div>`);

    return `${head(esc(name), `${isPhone ? phone(u.phone) : esc(u.email || '')} · с ${when(u.created_at)} · последний вход ${when(u.last_at)}`, '', '#/people')}
      ${b ? `<div class="alert bad" role="alert"><div><b>Заблокирован ${when(b.at)}</b><br>${esc(b.reason)}<br><span class="small">Не может заказывать, работать курьером и открыть магазин; его магазин скрыт от покупателей</span></div></div>` : ''}
      <div class="chips">${roleChips(u.roles)}</div>
      <div class="actions">${actions}</div>
      ${section('Роли и связи', links.length ? `<div class="list">${links.join('')}</div>` : empty('Пока без роли', 'Вошёл в одно из приложений, но ещё ничего не сделал'))}
      ${c ? section('Анкета курьера', `<div class="kvs">${kv('Имя', esc(c.name))}${kv('Телефон', `<a class="link" href="${tel(c.phone)}">${phone(c.phone)}</a>`)}
        ${kv('Машина', esc(c.car || '—'))}${kv('Номер', esc(c.plate || '—'))}${kv('Рейтинг', `${c.rating || '—'} ★ (${c.rating_count} оценок)`)}
        ${kv('Доставлено', `${st.deliveries} · заработал ${money(st.earned)}`)}${kv('Место', c.has_pos ? `пришло ${ago(c.loc_at)}` : 'ни разу не приходило')}
        ${c.block_reason ? kv('Причина блокировки', esc(c.block_reason)) : ''}</div>
        <div class="actions">${c.status === 'active' ? `<button class="btn danger" data-act="courier-block" data-id="${u.id}">Заблокировать курьера</button>`
          : `<button class="btn" data-act="courier-unblock" data-id="${u.id}">Разблокировать курьера</button>`}</div>`) : ''}
      ${u.orders?.length ? section(`Заказы как покупатель · ${u.orders.length}`, orderList(u.orders)) : ''}
      ${u.deliveries?.length ? section(`Доставки как курьер · ${u.deliveries.length}`, orderList(u.deliveries)) : ''}
      ${u.reviews?.length ? section(`Отзывы, которые написал · ${u.reviews.length}`, `<div class="list">${u.reviews.map(r => `<a class="item" href="#/shop/${r.shop_id}">
        <span class="item-main"><b>${'★'.repeat(r.rating)}${'☆'.repeat(5 - r.rating)} «${esc(r.shop)}»</b><span class="item-sub">${esc(r.text || 'без текста')} · заказ № ${r.order_no}</span></span>
        <span class="item-end item-sub">${when(r.created_at)}</span></a>`).join('')}</div>`) : ''}
      ${section('Что меняли админы', logList(u.log))}`;
  },
};
