import * as api from '../api.js';
import { ACTIONS, count, esc, ROLES, STAFF_ROLES, when } from '../lib/format.js';
import { empty, head, ICON, section, tabs } from '../ui.js';
import { who } from './parts.js';

// Отзывы и жалобы, журнал действий админов, роли и как всё связано.

const stars = n => '★'.repeat(n) + '☆'.repeat(5 - n);
const COMPLAINT = { review: ['warn', 'Жалоба ждёт решения'], accepted: ['', 'Скрыт (жалоба принята)'], rejected: ['ok', 'Оставлен (жалоба отклонена)'] };

export const reviews = {
  title: 'Отзывы',
  load: q => api.reviews(q.f || ''),
  html(list, q) {
    return `${head('Отзывы', 'Отзывы покупателей о магазинах. Скрыть отзыв может только админ — магазин может лишь пожаловаться')}
      ${tabs('f', q.f || '', [['', 'Все'], ['complaints', 'Жалобы магазинов'], ['low', '1–2 звезды'], ['hidden', 'Скрытые']])}
      ${list.length ? `<div class="list">${list.map(r => {
        const c = r.complaint, cs = c ? COMPLAINT[c.decided_at ? c.status : 'review'] || COMPLAINT.review : null, hidden = !!c?.hidden;
        return `<div class="item"><span class="item-main"><b>${stars(r.rating)}</b> <a class="link" href="#/shop/${r.shop.id}">${esc(r.shop.name)}</a> · ${r.buyer ? `<a class="link" href="#/person/${r.buyer.id}">${who(r.buyer)}</a>` : esc(r.name)}
            ${cs ? ` <span class="chip ${cs[0]}">${cs[1]}</span>` : ''}
            <span class="item-sub">${esc(r.text || 'без текста')}${(r.tags || []).length ? ` · ${esc(r.tags.join(', '))}` : ''}</span>
            ${r.reply ? `<span class="item-sub">Ответ магазина: ${esc(r.reply)}</span>` : ''}
            ${c ? `<span class="item-sub">Жалоба магазина: <b>${esc(c.reason || '')}</b>${c.note ? ` · решение: ${esc(c.note)}` : ''}</span>` : ''}
            <span class="item-sub">заказ № ${r.order_no} · ${when(r.created_at)}</span></span>
          <span class="item-end">${hidden ? `<button class="btn sm" data-act="review-show" data-id="${r.id}">Вернуть</button>`
            : `<button class="btn sm danger" data-act="review-hide" data-id="${r.id}">Скрыть</button>`}
            ${c && !c.decided_at ? `<button class="btn sm" data-act="review-keep" data-id="${r.id}">Оставить</button>` : ''}</span></div>`;
      }).join('')}</div>` : empty('Отзывов нет')}`;
  },
};

const TARGET = { order: id => `#/order/${encodeURIComponent(id)}`, shop: id => `#/shop/${id}`, user: id => `#/person/${id}`, courier: id => `#/person/${id}`, admin: id => `#/person/${id}`,
  review: () => '#/reviews', product: (id, d) => d?.shop ? `#/shop/${d.shop}` : '#/products' };
export const log = {
  title: 'Журнал',
  load: () => api.log(500),
  html(list) {
    return `${head('Журнал', 'Каждое действие любого админа: кто, когда, что сделал и почему. Удалить запись нельзя')}
      ${list.length ? `<ul class="timeline big">${list.map(l => `<li><span class="t-at">${when(l.at)}</span><span>
        <b>${esc(ACTIONS[l.action] || l.action)}</b>${l.data?.no ? ` № ${l.data.no}` : ''} — <a class="link" href="${(TARGET[l.kind] || (() => '#/'))(l.target, l.data)}">открыть</a>
        ${l.note ? `<span class="item-sub">${esc(l.note)}</span>` : ''}<span class="item-sub">${esc(l.by || '')}</span></span></li>`).join('')}</ul>` : empty('Пока пусто', 'Здесь появятся блокировки, отмены и решения админов')}`;
  },
};

// ---------- роли и связи ----------
export const roles = {
  title: 'Роли',
  load: async () => { const [sys, o] = await Promise.all([api.system(), api.overview()]); return { sys, o }; },
  html({ sys, o }) {
    const n = { admin: o.admins, seller: o.shops, courier: o.couriers, buyer: o.buyers };
    return `${head('Роли и связи', 'Кто есть кто в «Зуд» и как они связаны друг с другом')}
      ${section('Как всё связано', `<div class="flow" aria-label="Путь заказа">
        <a class="flow-n green" href="#/people?role=buyer"><b>Покупатель</b><span>оформил заказ</span></a><span class="flow-a" aria-hidden="true">→</span>
        <a class="flow-n" href="#/orders"><b>Заказ</b><span>номер, состав, деньги, код</span></a><span class="flow-a" aria-hidden="true">→</span>
        <a class="flow-n blue" href="#/shops"><b>Магазин</b><span>владелец и сотрудники собирают</span></a><span class="flow-a" aria-hidden="true">→</span>
        <a class="flow-n amber" href="#/couriers"><b>Курьер</b><span>забирает и везёт</span></a><span class="flow-a" aria-hidden="true">→</span>
        <a class="flow-n green" href="#/people?role=buyer"><b>Покупатель</b><span>называет код, оценивает</span></a></div>
        <ul class="facts">
          <li>Один номер телефона — одна учётная запись. Один человек может быть сразу покупателем, продавцом и курьером: роли видны в карточке человека.</li>
          <li>Магазин принадлежит одному владельцу. Сотрудников владелец добавляет по номеру: ${Object.values(STAFF_ROLES).join(', ').toLowerCase()}.</li>
          <li>Заказ всегда связан с магазином; из приложения — ещё с покупателем, после «Беру» — с курьером. Деньги заказа считает база, а не телефон.</li>
          <li>Отзыв пишет покупатель после получения. Магазин может ответить и пожаловаться, скрыть — только админ.</li>
          <li>Админ видит всё, но меняет только через кнопки панели — и каждое действие попадает в журнал.</li>
        </ul>`)}
      ${section('Роли', `<div class="roles">${Object.entries(ROLES).map(([k, r]) => `<a class="role-card" href="#/people?role=${k}">
        <span class="chip ${r.tone}">${r.name}</span>${n[k] != null ? `<b class="num">${count(n[k])}</b>` : ''}<span class="small muted">${esc(r.hint)}</span></a>`).join('')}
        <div class="role-card"><span class="chip">Без роли</span><span class="small muted">Вошёл по номеру, но ещё ничего не заказал, не открыл магазин и не стал курьером</span></div></div>`)}
      ${section('Что может каждая роль', `<div class="table-wrap"><table class="matrix">
        <thead><tr><th>Действие</th><th>Покупатель</th><th>Продавец</th><th>Сотрудник</th><th>Курьер</th><th>Админ</th></tr></thead><tbody>
        ${[['Заказать в приложении', 1, 0, 0, 0, 0], ['Товары, цены, остатки своего магазина', 0, 1, '½', 0, 0], ['Принять и собрать заказ', 0, 1, 1, 0, 0],
          ['Деньги магазина и сотрудники', 0, 1, 0, 0, 0], ['Взять заказ и доставить', 0, 0, 0, 1, 0], ['Видеть адрес и телефон покупателя', 0, 1, 1, '½', 1],
          ['Видеть код получения', 1, 0, 0, 0, 1], ['Оценить магазин и курьера', 1, 0, 0, 0, 0], ['Ответить на отзыв, пожаловаться', 0, 1, '½', 0, 0],
          ['Скрыть отзыв, товар, магазин', 0, 0, 0, 0, 1], ['Заблокировать человека или курьера', 0, 0, 0, 0, 1], ['Отменить чужой заказ', 0, 0, 0, 0, 1], ['Видеть всё во всех магазинах', 0, 0, 0, 0, 1]]
          .map(([t, ...v]) => `<tr><td>${t}</td>${v.map(x => `<td class="c">${x === 1 ? '<span class="yes" aria-label="да">✓</span>' : x === '½' ? '<span class="part" title="Частично: управляющий и кассир — да, сборщик — нет; курьер — только после «Беру»">частично</span>' : '<span class="no" aria-label="нет">—</span>'}</td>`).join('')}</tr>`).join('')}
        </tbody></table></div>`)}
      ${section('Админы', `<div class="list">${sys.admins.map(a => `<a class="item" href="#/person/${a.id}">${ICON.roles}<span class="item-main"><b>${esc(a.email)}</b>${a.me ? ' <span class="chip">это вы</span>' : ''}
        <span class="item-sub">с ${when(a.added_at)}${a.note ? ' · ' + esc(a.note) : ''}</span></span>${ICON.chevron}</a>`).join('')}</div>
        <p class="small muted">Добавить админа: человек создаётся в Supabase (Authentication → Add user, почта и пароль), потом здесь — «Люди» → он → «Сделать админом». По номеру телефона админом стать нельзя.</p>`)}
      ${section('Настройки сервиса', `<div class="kvs">
        <div class="kv"><span>Зона доставки</span><b>${sys.zone_open ? 'открыта везде (тест)' : 'только свой район'}</b></div>
        <div class="kv"><span>Курьеру от платы за доставку</span><b>${Math.round(sys.courier_share * 100)}%</b></div>
        <div class="kv"><span>Курьер видит заказы в радиусе</span><b>${sys.courier_radius} км</b></div></div>
        <p class="small muted">Меняются в базе (миграцией), чтобы случайное нажатие не поменяло деньги всем сразу.</p>`)}`;
  },
};
