import * as api from '../api.js';
import { esc, money, PAY, phone, span, stage, tel, when } from '../lib/format.js';
import { head, ICON, kv, searchBar, section, tabs } from '../ui.js';
import { logList, orderList, personLink } from './parts.js';

// Заказы: все, с фильтрами. Карточка заказа — кто, что, сколько, все этапы со временем, и что админ может сделать.

const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const dateArg = v => v === 'today' ? today() : /^\d{4}-\d{2}-\d{2}$/.test(v || '') ? v : null;

export const orders = {
  title: 'Заказы',
  load: q => api.orders({ status: q.status || '', q: q.q || '', shop: q.shop || null, person: q.person || null, from: dateArg(q.from), to: dateArg(q.to) }),
  html(list, q) {
    const scope = [q.shop ? 'одного магазина' : '', q.person ? 'одного человека' : '', q.from === 'today' ? 'за сегодня' : ''].filter(Boolean).join(', ');
    const sum = list.filter(o => o.status !== 'cancelled').reduce((s, o) => s + Number(o.total || 0), 0);
    return `${head('Заказы', scope ? `Показаны заказы ${scope} · <a class="link" href="#/orders">все заказы</a>` : 'Все заказы из приложения и продажи в магазинах')}
      ${searchBar(q.q || '', 'Номер заказа, телефон или имя', `<label class="date"><span>с</span><input type="date" name="from" value="${esc(dateArg(q.from) || '')}"></label>
        <label class="date"><span>по</span><input type="date" name="to" value="${esc(dateArg(q.to) || '')}"></label>`)}
      ${tabs('status', q.status || '', [['', 'Все'], ['active', 'В работе'], ['new', 'Новые'], ['accepted', 'Собирают'], ['ready', 'Собраны'], ['delivering', 'В пути'],
        ['done', 'Выданы'], ['cancelled', 'Отменены'], ['problem', 'Проблемы']])}
      <p class="small muted">Найдено: ${list.length}${list.length ? ` · на сумму ${money(sum)} без отмен` : ''}${list.length >= 500 ? ' · показаны последние 500, сузьте поиск' : ''}</p>
      ${orderList(list)}`;
  },
};

const STEPS = [['created_at', 'Заказ оформлен'], ['accepted_at', 'Магазин принял'], ['courier_at', 'Курьер взял'], ['picked_at', 'Курьер забрал в магазине'],
  ['delivered_at', 'Курьер доставил'], ['received_at', 'Покупатель получил']];

export const order = {
  title: 'Заказ',
  load: (q, id) => api.order(id),
  html(d) {
    const o = d.order, s = stage({ ...o, step: o.courier_status }), c = o.customer || {}, app = o.source === 'app';
    const costs = Array.isArray(d.costs) ? d.costs : [], known = costs.some(x => x != null);
    const cost = (o.items || []).reduce((t, i, k) => t + (costs[k] != null ? Number(costs[k]) * Number(i.actual ?? i.qty) : 0), 0);
    const active = o.status !== 'cancelled' && !o.received_at && o.courier_status !== 'delivered';
    const canRelease = o.courier_id && ['going', 'at_shop'].includes(o.courier_status) && o.status !== 'cancelled';
    const problem = o.problem;
    const timeline = STEPS.filter(([k]) => o[k]).map(([k, l], i, arr) => `<li><span class="t-at">${when(o[k])}</span><span><b>${l}</b>${i ? `<span class="item-sub">через ${span(o[arr[i - 1][0]], o[k])}</span>` : ''}</span></li>`);
    if (o.status === 'cancelled') timeline.push(`<li class="bad"><span class="t-at">${when(o.updated_at)}</span><span><b>Отменён</b><span class="item-sub">${esc(o.cancel_reason || 'без причины')}</span></span></li>`);
    if (o.courier_status === 'returned') timeline.push(`<li class="bad"><span class="t-at">${when(o.updated_at)}</span><span><b>Курьер вернул заказ в магазин</b></span></li>`);
    return `${head(`Заказ № ${o.no}`, `${app ? 'Из приложения' : 'Продажа в магазине'} · ${when(o.created_at)}`, `<span class="chip ${s.tone}">${s.text}</span>`, '#/orders')}
      ${problem ? `<div class="alert ${problem.resolved_at ? '' : 'bad'}" role="alert"><div><b>${problem.resolved_at ? 'Проблема решена' : 'Проблема'}: ${esc(problem.reason || '')}</b>
        ${problem.text ? `<br>${esc(problem.text)}` : ''}<br><span class="small">${problem.by === 'courier' ? 'сообщил курьер' : 'сообщил покупатель'} ${when(problem.ts)}</span>
        ${problem.resolved_at ? `<br><span class="small">Решение ${when(problem.resolved_at)}: ${esc(problem.resolved_note)}</span>` : ''}</div>
        ${problem.resolved_at ? '' : `<button class="btn sm" data-act="order-resolve" data-id="${esc(o.id)}">Отметить решённой</button>`}</div>` : ''}
      ${app ? `<div class="actions">
        ${active ? `<button class="btn danger" data-act="order-cancel" data-id="${esc(o.id)}">Отменить заказ</button>` : ''}
        ${canRelease ? `<button class="btn" data-act="order-release" data-id="${esc(o.id)}">Снять курьера</button>` : ''}
        ${active && o.status !== 'new' ? `<button class="btn" data-act="order-delivered" data-id="${esc(o.id)}">Закрыть как полученный</button>` : ''}
        ${!problem && o.courier_status === 'returned' ? `<button class="btn" data-act="order-resolve" data-id="${esc(o.id)}">Отметить решённым</button>` : ''}
      </div>` : ''}
      <div class="grid2">
        ${section('Кто участвует', `<div class="list">
          ${app ? `<div class="item">${ICON.people}<span class="item-main"><b>Покупатель: ${personLink(d.buyer)}</b><span class="item-sub">${esc(c.name || '')} · <a class="link" href="${tel(c.phone)}">${phone(c.phone)}</a></span>
            <span class="item-sub">${esc(c.address || 'адрес без деталей')}</span></span></div>` : ''}
          <div class="item">${ICON.shop}<span class="item-main"><b>Магазин: <a class="link" href="#/shop/${d.shop.id}">${esc(d.shop.name)}</a></b>
            <span class="item-sub">${d.shop.phone ? `<a class="link" href="${tel(d.shop.phone)}">${phone(d.shop.phone)}</a> · ` : ''}${esc(d.shop.address || '')}</span>
            <span class="item-sub">владелец ${personLink(d.shop.owner)}</span></span></div>
          ${o.courier ? `<div class="item">${ICON.car}<span class="item-main"><b>Курьер: ${personLink(d.courier_user)}</b>
            <span class="item-sub">${esc(o.courier.name)} · <a class="link" href="${tel(o.courier.phone)}">${phone(o.courier.phone)}</a> · ${esc([o.courier.car, o.courier.plate].filter(Boolean).join(' · '))}</span></span></div>`
            : app && o.delivery === 'courier' ? `<div class="item">${ICON.car}<span class="item-main"><b>Курьера пока нет</b><span class="item-sub">заказ появится у курьеров, когда магазин примет его</span></span></div>` : ''}
        </div>`)}
        ${section('Деньги', `<div class="kvs">${kv('Товары', money(o.sum))}${app ? kv('Доставка', `${money(o.fee)}${o.km ? ` · ${o.km} км` : ''}`) : ''}${kv('Итого', `<b>${money(o.total)}</b>`)}
          ${kv('Оплата', esc(PAY[o.pay] || o.pay))}${o.courier_fee != null ? kv('Курьеру', money(o.courier_fee)) : ''}${o.cash_taken != null ? kv('Курьер взял наличными', money(o.cash_taken)) : ''}
          ${known ? kv('Закупка / прибыль магазина', `${money(cost)} / ${money(Number(o.sum) - cost)}`) : ''}
          ${d.code ? kv('Код получения', `<span class="num code">${esc(d.code)}</span>`) : ''}</div>`)}
      </div>
      ${section(`Состав · ${(o.items || []).length}`, `<div class="list">${(o.items || []).map(i => `<div class="item"><span class="item-main"><b>${esc(i.name)}${i.variant ? ` (${esc(i.variant)})` : ''}</b>
        ${i.missing ? ' <span class="chip bad">Не было</span>' : ''}${i.sub ? ` <span class="chip warn">Замена: ${esc(i.sub.name || '')} — ${i.sub.status === 'ok' ? 'согласился' : i.sub.status === 'no' ? 'отказался' : 'ждёт ответа'}</span>` : ''}
        <span class="item-sub">арт. ${esc(i.sku || '—')} · ${i.qty} ${esc(i.unit || 'шт')}${i.actual != null && i.actual !== i.qty ? ` (взвесили ${i.actual})` : ''} × ${money(i.price)}${(i.opts || []).length ? ` · ${esc(i.opts.map(x => x.name).join(', '))}` : ''}</span></span>
        <span class="item-end num">${money(Number(i.price) * Number(i.actual ?? i.qty))}</span></div>`).join('')}</div>
        ${o.comment || app ? `<div class="kvs">${o.comment ? kv('Комментарий', esc(o.comment)) : ''}${app ? kv('Если чего-то нет', { call: 'позвонить', replace: 'заменить похожим', remove: 'убрать' }[o.if_missing] || '—') : ''}${o.when_label ? kv('Когда', esc(o.when_label)) : ''}</div>` : ''}`)}
      ${section('Этапы', `<ul class="timeline">${timeline.join('')}</ul>`)}
      ${d.review ? section('Отзыв покупателя', `<p><b>${'★'.repeat(d.review.rating)}${'☆'.repeat(5 - d.review.rating)}</b> ${esc(d.review.text || 'без текста')}</p>${d.review.reply ? `<p class="muted">Ответ магазина: ${esc(d.review.reply)}</p>` : ''}`) : ''}
      ${o.courier_rating ? section('Оценка курьеру', `<p><b>${'★'.repeat(o.courier_rating)}${'☆'.repeat(5 - o.courier_rating)}</b></p>`) : ''}
      ${section('Что меняли админы', logList(d.log))}`;
  },
};
