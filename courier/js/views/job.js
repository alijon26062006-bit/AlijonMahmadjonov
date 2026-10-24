import { NAVS, WAIT_CLIENT_MIN } from '../config.js';
import { esc, money, pad, qtyLabel } from '../lib/format.js';
import { kmText, roadKm, routeUrl, waUrl } from '../lib/nav.js';
import { play } from '../lib/sound.js';
import { call, copy, openExternal, vibrate } from '../platform.js';
import * as api from '../services/api.js';
import { K, rt, save } from '../state.js';
import { $, closeSheet, ico, openSheet, toast, twice } from '../ui/dom.js';
import { slider } from '../ui/slide.js';
import { route } from '../lib/jobmap.js';
import { dayStats } from './shift.js';

// Доставка по шагам. На экране только то, что нужно сейчас: куда ехать, кому звонить, что сказать, что взять.
// Главный шаг — ползунок внизу: его не нажать случайно.

const STEPS = [['В магазин', ['going', 'at_shop']], ['Забрал', ['picked']], ['У покупателя', ['at_client']], ['Передал', ['delivered']]];
const NEXT = {
  going: ['at_shop', 'Я в магазине'],
  at_shop: ['picked', 'Забрал заказ'],
  picked: ['at_client', 'Я у покупателя'],
  at_client: ['delivered', 'Передал заказ'],
};
const TITLE = { going: 'Едете в магазин', at_shop: 'Вы в магазине', picked: 'Везёте покупателю', at_client: 'Вы у покупателя' };
const toShop = j => ['going', 'at_shop'].includes(j.step);
const target = j => toShop(j)
  ? { kind: 'Магазин', name: j.shop.name, address: j.shop.address, note: j.shop.landmark, phone: j.shop.phone, lat: j.shop.lat, lng: j.shop.lng }
  : { kind: 'Покупатель', name: j.client.name, address: j.client.address, note: '', phone: j.client.phone, lat: j.client.lat, lng: j.client.lng };

const waitLeft = j => K.waitFrom[j.id] ? Math.max(0, WAIT_CLIENT_MIN * 60000 - (Date.now() - K.waitFrom[j.id])) : null;
export const mmss = ms => `${pad(Math.floor(ms / 60000))}:${pad(Math.floor(ms / 1000) % 60)}`;

function readyRow(j) {
  if (j.status === 'ready' || j.status === 'done') return `<div class="ir"><span class="ir-l">Готовность</span><b class="ir-v ok">${ico('check', 'xs')} Собран</b></div>`;
  const min = j.readyAt ? Math.round((j.readyAt - Date.now()) / 60000) : null;
  return `<div class="ir"><span class="ir-l">Готовность</span><b class="ir-v num">${min > 0 ? `через ${min} мин` : 'скоро'}</b></div>`;
}

function itemsList(j) {
  const ticked = K.checked[j.id] || [];
  const left = j.items.filter((i, n) => !i.missing && !ticked.includes(n)).length;
  return `<div class="group-t"><span>Проверьте пакет</span><span class="muted">${left ? `осталось ${left}` : 'всё на месте'}</span></div>
    <div class="group">${j.items.map((i, n) => {
      const q = i.missing ? 0 : i.actual ?? i.qty, on = ticked.includes(n);
      return `<button class="check-row ${on ? 'on' : ''} ${i.missing ? 'gone' : ''}" data-a="tick" data-n="${n}" aria-pressed="${on}">
        <span class="box">${on ? ico('check', 'sm') : ''}</span>
        <span class="grow"><b translate="no">${esc(i.name)}${i.variant ? ', ' + esc(i.variant) : ''}</b>${i.missing ? '<small>нет в наличии — убрали</small>' : ''}
          ${i.sub?.status === 'ok' ? `<small>замена: <span translate="no">${esc(i.sub.name)}</span> × ${qtyLabel(+i.sub.qty, i.sub.unit || i.unit)}</small>` : ''}</span>
        <span class="qty num">${i.missing ? '—' : qtyLabel(q, i.unit)}</span></button>`;
    }).join('')}</div>`;
}

function payRow(j) {
  return j.pay === 'cash'
    ? `<div class="ir"><span class="ir-l">Возьмите наличными</span><b class="ir-v cash num">${money(j.total)}</b></div>
       <div class="ir sub"><span class="ir-l">товары ${money(j.sum)} + доставка ${money(j.fee)}</span></div>`
    : `<div class="ir"><span class="ir-l">Оплата</span><b class="ir-v ok">${ico('check', 'xs')} Онлайн, деньги не брать</b></div>`;
}

/** Экран доставки: карта на весь экран (слой #map-layer), снизу карточка с одним главным действием — ползунком. */
export function vJob(j) {
  const t = target(j), shop = toShop(j), idx = STEPS.findIndex(s => s[1].includes(j.step)), [next, label] = NEXT[j.step], left = waitLeft(j);
  const km = route.km ?? roadKm(rt.pos, t);
  return `
    <div class="map-top">
      <button class="fab" data-a="jobMenu" aria-label="Действия с заказом">${ico('dots')}</button>
      <span class="map-pill"><b class="num">№ ${j.no}</b><i aria-hidden="true"></i><b class="num plus">+${money(j.earn)}</b></span>
      <button class="fab" data-a="recenter" aria-label="Показать маршрут целиком">${ico('locate')}</button>
    </div>
    <section class="job-sheet ${j.step === 'at_client' ? 'door' : ''}" aria-label="Заказ № ${j.no}">
      <span class="grab" aria-hidden="true"></span>
      <div class="prog" role="progressbar" aria-valuemin="1" aria-valuemax="4" aria-valuenow="${idx + 1}" aria-label="Этап ${idx + 1} из 4">${STEPS.map((_, i) => `<i class="${i < idx ? 'done' : i === idx ? 'now' : ''}"></i>`).join('')}</div>
      <div class="lead"><small class="eyebrow">${TITLE[j.step]}</small>
        <span class="eta-line"><b class="eta num">${route.min != null ? `${route.min} мин` : km != null ? kmText(km) : STEPS[idx][0]}</b>${route.min != null && km != null ? `<span class="eta-km num">${kmText(km)}</span>` : ''}</span></div>
      <div class="who">
        <span class="who-ico ${shop ? 'shop' : 'client'}">${ico(shop ? 'store' : 'home')}</span>
        <span class="grow"><small>${t.kind}</small><b translate="no">${esc(t.name || '')}</b><span class="addr" translate="no">${esc(t.address || 'Адрес не указан')}</span>${t.note ? `<span class="note-l" translate="no">${esc(t.note)}</span>` : ''}</span>
      </div>
      <div class="quick">
        <button class="q primary" data-a="route"><span class="qi">${ico('nav')}</span><span>Маршрут</span></button>
        ${t.phone ? `<button class="q" data-a="callTarget"><span class="qi">${ico('phone')}</span><span>Позвонить</span></button>` : ''}
        ${!shop && t.phone ? `<button class="q" data-a="waTarget"><span class="qi">${ico('chat')}</span><span>WhatsApp</span></button>` : ''}
        <button class="q" data-a="copyAddr"><span class="qi">${ico('copy')}</span><span>Адрес</span></button>
      </div>
      ${shop ? `
        <div class="group">
          <div class="ir"><span class="ir-l">Назовите в магазине</span><b class="ir-v order-no num">№ ${j.no}</b></div>
          ${readyRow(j)}
        </div>
        ${itemsList(j)}
        <button class="link-btn" data-a="routeFull">${ico('route', 'sm')} Весь путь до покупателя${j.km ? ` · ${kmText(j.km)}` : ''}</button>`
      : `${j.step === 'at_client' ? `<div class="code-box"><label for="code">Код от покупателя</label>
          <input id="code" class="code-in num" inputmode="numeric" pattern="[0-9]*" maxlength="4" autocomplete="one-time-code" value="${esc(rt.code)}" placeholder="····">
          <small class="muted">4 цифры в приложении покупателя. Без кода заказ не закрыть</small></div>` : ''}
        <div class="group">${payRow(j)}</div>
        ${left != null ? `<div class="wait ${left ? '' : 'over'}">${ico('timer')}<span class="grow"><b>${left ? 'Ждём покупателя' : 'Покупатель не ответил'}</b>
            <small>${left ? 'Звоните ему. Через 10 минут можно вернуть заказ' : 'Можно вернуть заказ в магазин'}</small></span>
            ${left ? `<b class="num" id="waitT">${mmss(left)}</b>` : `<button class="btn sm" data-a="giveBack">Вернуть</button>`}</div>` : ''}`}
      ${j.comment ? `<div class="note">${ico('chat', 'sm')}<span translate="no">${esc(j.comment)}</span></div>` : ''}
      <div class="sheet-cta">${slider(label, 'step', { id: j.id, to: next }, next === 'delivered' ? 'go' : '')}</div>
    </section>`;
}

/** Точки для карты доставки. */
export const mapState = j => ({
  me: rt.pos, kind: /** @type {'shop'|'client'} */ (toShop(j) ? 'shop' : 'client'), target: target(j),
  shop: j.shop?.lat != null ? { lat: j.shop.lat, lng: j.shop.lng } : null,
  client: j.client?.lat != null ? { lat: j.client.lat, lng: j.client.lng } : null,
});

/** Экран «Доставлено»: сколько заработал сейчас и за день. */
export function vDone(j, list) {
  const s = dayStats(list);
  return `<section class="done-screen">
    <span class="done-check">${ico('check')}</span>
    <h1>Доставлено!</h1>
    <b class="huge num">+${money(j.earn)}</b>
    <p class="muted">Сегодня: <b class="num">${money(s.earn)}</b> · ${s.trips} ${s.trips === 1 ? 'поездка' : s.trips < 5 ? 'поездки' : 'поездок'}</p>
    ${j.cash_taken ? `<p class="pill cash">${ico('cash', 'sm')} У вас наличные за заказ: ${money(j.cash_taken)}</p>` : ''}
    <button class="btn primary block xl" data-a="doneOk">К новым заказам</button></section>`;
}

/** Заказ отменили, пока курьер его вёз. */
export const vCancelled = j => `<section class="done-screen bad">
    <span class="done-check">${ico('close')}</span>
    <h1>Заказ № ${j.no} отменён</h1>
    <p class="muted">${esc(j.cancel_reason || 'Магазин или покупатель отменили заказ')}</p>
    ${j.picked ? '<p class="pill">Если пакет уже у вас — верните его в магазин</p>' : ''}
    <button class="btn primary block xl" data-a="seenCancel" data-id="${j.id}">Понятно</button></section>`;

function replace(j) { K.jobs = [j, ...K.jobs.filter(x => x.id !== j.id)].slice(0, 30); save(); }
const job = id => K.jobs.find(j => j.id === id);

/** Шаг доставки (вызывает ползунок). */
export async function doStep(el, sure = false) {
  const j = job(el.dataset.id), to = el.dataset.to; if (!j || rt.busy) return;
  if (to === 'picked' && !sure && !['ready', 'done'].includes(j.status)) {
    openSheet(`<h2>Магазин ещё не нажал «Готов»</h2><p class="muted">Если пакет уже у вас в руках — подтвердите. Если нет — подождите, пока соберут.</p>`,
      { label: 'Забрали заказ?', foot: `<button class="btn" data-a="closeSheet">Подожду</button><button class="btn primary" data-a="pickAnyway" data-id="${j.id}">Да, забрал</button>` });
    return;
  }
  if (to === 'delivered' && !/^\d{4}$/.test(rt.code)) { toast('Введите 4 цифры кода от покупателя'); vibrate([60, 60, 60]); $('#code')?.focus(); return; }
  rt.busy = true;
  try {
    const r = await api.step(j.id, to, to === 'delivered' ? rt.code : null);
    replace(r);
    // забрал заказ — навигатор сам строит путь до покупателя
    if (to === 'picked' && K.autoRoute) openRoute(r);
    if (to === 'delivered') { rt.code = ''; delete K.waitFrom[j.id]; delete K.checked[j.id]; K.seenDone.push(j.id); save(); rt.done = r; if (K.sound) play('done'); vibrate([80, 60, 160]); }
    else vibrate(30);
  } catch (e) { toast(e.message); if (K.sound) play('bad'); }
  finally { rt.busy = false; }
}

/**
 * Открыть маршрут в навигаторе (по умолчанию 2GIS).
 * leg: 'now' — от курьера до текущей цели (магазин или покупатель); 'full' — весь путь магазин → покупатель.
 * @param {any} j заказ
 * @param {'now'|'full'} [leg]
 */
export function openRoute(j, leg = 'now') {
  const full = leg === 'full', t = full ? target({ ...j, step: 'picked' }) : target(j);
  const { url, fallback } = routeUrl(K.nav, t, full ? { lat: j.shop.lat, lng: j.shop.lng } : null);
  openExternal(url);
  // навигатора нет на телефоне — через полторы секунды открываем его сайт
  if (fallback) setTimeout(() => { if (document.visibilityState === 'visible') openExternal(fallback); }, 1500);
}

export const jobActions = {
  route: () => { const j = cur(); if (j) openRoute(j); return false; },
  routeFull: () => { const j = cur(); if (j) openRoute(j, 'full'); return false; },
  callTarget: () => { const j = cur(); if (j) call(target(j).phone); return false; },
  waTarget: () => { const j = cur(); if (j) openExternal(waUrl(target(j).phone)); return false; },
  copyAddr: async () => { const j = cur(); if (j) toast(await copy(target(j).address || '') ? 'Адрес скопирован' : 'Не удалось скопировать'); return false; },
  tick: el => { const j = cur(), n = +el.dataset.n, t = K.checked[j.id] ||= []; K.checked[j.id] = t.includes(n) ? t.filter(x => x !== n) : [...t, n]; save(); vibrate(15); },
  pickAnyway: async el => { closeSheet(); await doStep({ dataset: { id: el.dataset.id, to: 'picked' } }, true); },
  jobMenu: () => {
    const j = cur(); if (!j) return false;
    const before = toShop(j);
    openSheet(`<h2>Заказ № ${j.no}</h2><div class="list menu">
      ${j.shop.phone ? `<button class="li" data-a="callShop">${ico('store')}<span class="grow"><b>Позвонить в магазин</b><small translate="no">${esc(j.shop.name)}</small></span></button>` : ''}
      ${j.client.phone ? `<button class="li" data-a="callClient">${ico('user')}<span class="grow"><b>Позвонить покупателю</b><small translate="no">${esc(j.client.name || '')}</small></span></button>` : ''}
      ${!before && !K.waitFrom[j.id] ? `<button class="li" data-a="waitStart">${ico('timer')}<span class="grow"><b>Покупатель не отвечает</b><small>Подождём ${WAIT_CLIENT_MIN} минут, потом можно вернуть заказ</small></span></button>` : ''}
      ${before ? `<button class="li danger" data-a="release">${ico('close')}<span class="grow"><b>Отказаться от заказа</b><small>Заказ уйдёт другому курьеру</small></span></button>` : ''}
      <button class="li" data-a="chooseNav">${ico('nav')}<span class="grow"><b>Навигатор</b><small>${esc(NAVS.find(n => n[0] === K.nav)?.[1] || '')}</small></span></button>
    </div>`, { label: 'Действия с заказом' });
    return false;
  },
  callShop: () => { call(cur()?.shop.phone); return false; },
  callClient: () => { call(cur()?.client.phone); return false; },
  waitStart: () => { const j = cur(); K.waitFrom[j.id] = Date.now(); save(); closeSheet(); toast(`Ждём ${WAIT_CLIENT_MIN} минут. Звоните покупателю`); },
  release: async el => {
    if (!twice(el, 'Нажмите ещё раз, чтобы отказаться')) return false;
    const j = cur(); rt.busy = true;
    try { await api.release(j.id); K.jobs = K.jobs.filter(x => x.id !== j.id); delete K.checked[j.id]; save(); closeSheet(); toast('Вы отказались от заказа'); }
    catch (e) { toast(e.message); } finally { rt.busy = false; }
  },
  giveBack: async () => {
    const j = cur(); rt.busy = true;
    try { replace(await api.giveBack(j.id, `Покупатель не отвечал ${WAIT_CLIENT_MIN} минут`)); delete K.waitFrom[j.id]; save(); toast('Отвезите заказ обратно в магазин. Поддержка уже знает'); }
    catch (e) { toast(e.message); } finally { rt.busy = false; }
  },
  doneOk: () => { rt.done = null; },
  seenCancel: el => { K.seenDone.push(el.dataset.id); save(); },
};
let cur = () => null;
/** app.js сообщает, какой заказ сейчас на экране. */
export const setCurrent = fn => { cur = fn; };
