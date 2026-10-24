import { CUR } from '../config.js';
import { dkey, esc, hhmm, money, plural, today } from '../lib/format.js';
import { kmText, roadKm } from '../lib/nav.js';
import { K, rt } from '../state.js';
import { ico } from '../ui/dom.js';

// Смена: на линии ли курьер, сколько заработал сегодня и свободные заказы рядом.
// На карточке заказа — всё, чтобы решить за секунду: сколько заплатят, куда ехать, наличные или нет.

export const initials = name => String(name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase();
export const avatar = (name, cls = '') => `<span class="ava ${cls}" aria-hidden="true">${esc(initials(name))}</span>`;

/** Доставки за день: заработок, поездки, наличные. */
export function dayStats(list, key = today()) {
  const done = list.filter(j => j.step === 'delivered' && j.delivered && dkey(j.delivered) === key);
  return { earn: done.reduce((s, j) => s + j.earn, 0), trips: done.length, cash: done.reduce((s, j) => s + (j.cash_taken || 0), 0), km: done.reduce((s, j) => s + (j.km || 0), 0) };
}
const allJobs = () => { const m = new Map(); for (const j of [...(rt.history || []), ...K.jobs]) m.set(j.id, j); return [...m.values()]; };

function readyText(o) {
  if (o.status === 'ready' || !o.readyAt) return { t: 'Заказ уже собран', ok: true };
  const min = Math.round((o.readyAt - Date.now()) / 60000);
  return min <= 0 ? { t: 'Скоро будет готов', ok: true } : { t: `Будет готов через ${min} мин`, ok: false };
}

/** Карточка свободного заказа. */
export function offerCard(o) {
  const r = readyText(o), toShop = o.to_shop ?? roadKm(rt.pos, { lat: o.shop_lat, lng: o.shop_lng });
  return `<article class="offer ${rt.fresh.has(o.id) ? 'new' : ''}" aria-label="Заказ на ${money(o.earn)}">
    <div class="offer-top">
      <b class="earn num">+${money(o.earn)}</b>
      ${o.pay === 'cash' ? `<span class="pill cash">${ico('cash', 'sm')} Наличные · возьмите ${money(o.cash)}</span>` : `<span class="pill paid">${ico('card', 'sm')} Оплачен онлайн</span>`}
    </div>
    <ol class="route">
      <li><span class="dot a"></span><span class="grow"><b translate="no">${esc(o.shop)}</b><small><span translate="no">${esc(o.shop_address || '')}</span>${toShop != null ? ` · ${kmText(toShop)} от вас` : ''}</small></span></li>
      <li><span class="dot b"></span><span class="grow"><b translate="no">${esc(o.area || 'Покупатель')}</b><small>${o.km != null ? `${kmText(o.km)} от магазина` : 'Адрес покажем после «Беру»'}</small></span></li>
    </ol>
    <div class="offer-meta"><span class="${r.ok ? 'ok' : ''}">${ico(r.ok ? 'check' : 'clock', 'xs')} ${r.t}</span><span>${ico('bag', 'xs')} ${o.items} ${plural(o.items, 'товар', 'товара', 'товаров')}</span><span class="num">№ ${o.no}</span></div>
    <button class="btn primary block xl" data-a="take" data-id="${o.id}" ${rt.busy ? 'disabled' : ''}>Беру заказ</button>
  </article>`;
}

export function vShift() {
  const m = K.me || {}, s = dayStats(allJobs());
  const status = !K.online ? '' : rt.net === 'off' ? `<div class="bar warn">${ico('alert', 'sm')} Нет связи с сервером. Как только появится — заказы снова пойдут</div>`
    : rt.geoErr ? `<div class="bar warn">${ico('pin', 'sm')} ${esc(rt.geoErr)}</div>` : '';
  return `
    <header class="shift-head">
      <button class="me" data-go="#/profile" aria-label="Профиль">${avatar(m.name)}<span class="grow"><b translate="no">${esc(m.name || '')}</b>
        <small>${m.rating_count ? `${ico('starFill', 'xs')} ${Number(m.rating).toLocaleString('ru-RU', { minimumFractionDigits: 1 })}` : 'Новый курьер'}${m.plate ? ` · <span translate="no">${esc(m.plate)}</span>` : ''}</small></span></button>
      <button class="switch-big ${K.online ? 'on' : ''}" data-a="toggleOnline" role="switch" aria-checked="${K.online}" ${rt.busy ? 'disabled' : ''}>
        <span class="knob">${ico('power', 'sm')}</span><span class="sw-t">${K.online ? "На линии" : "Не на линии"}</span></button>
    </header>
    <section class="today" aria-label="Сегодня">
      <div><small>Сегодня</small><b class="num">${money(s.earn)}</b></div>
      <div><small>Поездок</small><b class="num">${s.trips}</b></div>
      <div><small>Наличные</small><b class="num">${money(s.cash)}</b></div>
    </section>
    ${status}
    ${!K.online ? `<section class="offline-card">
        <span class="big-ico">${ico('power')}</span>
        <h2>Вы не на линии</h2>
        <p class="muted">Выйдите на линию — и заказы из магазинов рядом начнут приходить со звуком</p>
        <button class="btn primary block xl" data-a="toggleOnline" ${rt.busy ? 'disabled' : ''}>Выйти на линию</button>
      </section>`
    : rt.feed.length ? `<section class="section"><div class="sec-head"><h2>Заказы рядом</h2><span class="count num">${rt.feed.length}</span></div>
        <div class="offers">${rt.feed.map(offerCard).join('')}</div></section>`
    : `<section class="radar-card"><span class="radar" aria-hidden="true"><i></i><i></i><i></i>${ico('bike')}</span>
        <h2>Ищем заказы рядом</h2><p class="muted">Как только магазин примет заказ — он появится здесь со звуком. Экран можно не трогать</p></section>`}
    ${lastTrips()}`;
}

function lastTrips() {
  const list = allJobs().filter(j => j.step === 'delivered' && j.delivered && dkey(j.delivered) === today()).sort((a, b) => b.delivered - a.delivered).slice(0, 5);
  if (!list.length) return '';
  return `<section class="section"><div class="sec-head"><h2>Сегодня доставили</h2><button class="all" data-go="#/money">Весь доход ${ico('right', 'sm')}</button></div>
    <div class="list">${list.map(j => `<div class="li"><span class="time num">${hhmm(j.delivered)}</span><span class="grow"><b translate="no">${esc(j.shop.name)}</b><small>№ ${j.no}${j.cash_taken ? ` · наличные ${money(j.cash_taken)}` : ''}</small></span><b class="num plus">+${j.earn.toLocaleString('ru-RU')} ${CUR}</b></div>`).join('')}</div></section>`;
}
