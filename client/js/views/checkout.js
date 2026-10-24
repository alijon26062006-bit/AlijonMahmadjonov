import { totals } from '../model/cart.js';
import { eta, openState } from '../model/catalog.js';
import { addrLine, placeOrder } from '../model/orders.js';
import { esc, fmtPhone, money, pad } from '../lib/format.js';
import { C } from '../state.js';
import { ico, toast } from '../ui/dom.js';
import { openAddress, openLogin } from './account.js';
import { backBar } from './parts.js';
import { SERVICE_AREA } from '../config.js';
import { TARIFF } from '../model/delivery.js';

// Оформление заказа: адрес, время, получатель, оплата
const chk = { when: 'asap', pay: 'card' };

function slots(shop) {
  const st = openState(shop), now = new Date(), out = [];
  if (st.open) out.push(['asap', `Как можно скорее · ${eta(shop)}`]);
  const t = new Date(now); t.setMinutes(now.getMinutes() < 30 ? 30 : 60, 0, 0); t.setTime(t.getTime() + 3600e3);
  for (let i = 0; i < 48 && out.length < 9; i++, t.setTime(t.getTime() + 1800e3)) if (openState(shop, t).open) out.push([`${pad(t.getHours())}:${pad(t.getMinutes())}|${t.getTime()}`, `${t.getDate() === now.getDate() ? 'Сегодня' : 'Завтра'} к ${pad(t.getHours())}:${pad(t.getMinutes())}`]);
  return out;
}

export function vCheckout() {
  const T = totals(), { shop } = T;
  if (!T.rows.length) return `${backBar('Оформление')}<div class="empty"><p>Корзина пустая.</p><button class="btn primary" data-go="#/">К магазинам</button></div>`;
  const sl = slots(shop); if (!sl.some(s => s[0] === chk.when)) chk.when = sl[0]?.[0] || 'asap';
  const a = C.addr, u = C.user;
  return `${backBar('Оформление заказа')}
    <section class="section"><h3>Адрес</h3>
      ${a ? `<button class="li list" data-a="address" style="border-radius:var(--r)">${ico('pin')}<span class="grow"><b>${esc(addrLine(a))}</b><small>${esc([a.entrance && 'подъезд ' + a.entrance, a.floor && 'этаж ' + a.floor, a.intercom && 'домофон ' + a.intercom].filter(Boolean).join(', ') || 'Подъезд и этаж не указаны')}${a.landmark ? ' · ' + esc(a.landmark) : ''}</small></span><span class="link">Изменить</span></button>`
        : `<button class="btn primary block" data-a="address">${ico('pin')} Укажите адрес доставки</button>`}
      ${a ? (T.way.ok ? `<span class="small muted route">${ico('bike', 'xs')} Доставка до двери — ${money(T.fee)}${T.way.exact ? '' : ' · поставьте метку на карте — цена станет точной'}</span>`
        : `<div class="notice bad">${ico('alert', 'sm')}<span>${SERVICE_AREA.open ? `Магазин дальше ${TARIFF.maxKm} км от этого адреса — так далеко не возим.` : `Этот адрес вне зоны доставки. Пока возим только по Шахритусскому району — до ${SERVICE_AREA.radiusKm} км от центра посёлка.`}</span></div>`) : ''}</section>
    <section class="section"><h3>Когда доставить</h3>
      ${sl.length ? `<div class="chips">${sl.map(([k, t]) => `<button class="chip" data-a="when" data-v="${k}" aria-pressed="${chk.when === k}">${t}</button>`).join('')}</div>` : '<div class="notice bad">Магазин не работает ближайшие сутки. Выберите другой магазин.</div>'}
      ${!openState(shop).open && sl.length ? `<span class="small muted">Магазин сейчас закрыт — соберёт заказ к выбранному времени.</span>` : ''}</section>
    <section class="section"><h3>Получатель</h3>
      ${u ? `<button class="li list" data-a="login" style="border-radius:var(--r)">${ico('user')}<span class="grow"><b>${esc(u.name || 'Без имени')}</b><small>+992 ${fmtPhone(u.phone)}</small></span><span class="link">Изменить</span></button>`
        : `<button class="btn block" data-a="login">${ico('phone')} Войти по номеру телефона</button>`}</section>
    <section class="section"><h3>Оплата</h3>
      <div class="col" style="gap:8px">
        <label class="opt"><input type="radio" name="pay" value="card" ${chk.pay === 'card' ? 'checked' : ''} data-a="pay">${ico('card')}<span class="grow">Картой онлайн<small>Деньги заморозятся и уйдут магазину, только когда вы получите заказ</small></span></label>
        <label class="opt"><input type="radio" name="pay" value="cash" ${chk.pay === 'cash' ? 'checked' : ''} data-a="pay">${ico('cash')}<span class="grow">Наличными курьеру<small>Подготовьте сумму без сдачи, если можете</small></span></label>
      </div>
      ${chk.pay === 'card' ? `<div class="notice info small">${ico('shield', 'sm')}<span>Оплата картой пока в тестовом режиме — деньги не списываются.</span></div>` : ''}</section>
    <section class="section"><h3>${esc(shop.name)} · ${T.rows.length} ${T.rows.length === 1 ? 'позиция' : T.rows.length < 5 ? 'позиции' : 'позиций'}</h3>
      <div class="sum-table num"><div><span>Товары</span><span>${money(T.sum)}</span></div><div><span>Доставка</span><span>${T.fee ? money(T.fee) : 'бесплатно'}</span></div><div class="total"><span>К оплате</span><span>${money(T.total)}</span></div></div>
      ${shop.kind === 'grocery' ? '<span class="small muted">Если весовой товар окажется легче, разницу вернём.</span>' : ''}</section>`;
}
export function checkoutDock() {
  const T = totals(); if (!T.rows.length) return '';
  return `<button class="btn primary block" data-a="placeOrder" ${slots(T.shop).length && T.way.ok ? '' : 'disabled'}>${chk.pay === 'cash' ? 'Заказать' : 'Оплатить'}<span class="sum">${money(T.total)}</span></button>`;
}
export const checkoutActions = {
  when: el => { chk.when = el.dataset.v; },
  pay: el => { chk.pay = el.value; },
  placeOrder: async (el, go) => {
    if (!C.addr) return openAddress(() => checkoutActions.placeOrder(el, go)), false;
    if (!C.user) return openLogin(() => checkoutActions.placeOrder(el, go)), false;
    const T = totals(); if (T.left) return toast(`Минимальный заказ — ${money(T.shop.minOrder)}`), false;
    if (el.classList.contains('busy')) return false;   // второе нажатие, пока база думает, не создаст второй заказ
    el.classList.add('busy'); el.disabled = true;
    try {
      const [label, at] = chk.when.split('|');
      const o = await placeOrder({ pay: chk.pay, when: chk.when === 'asap' ? null : { label, at: +at } });
      toast(o.local || o.cloud ? 'Заказ отправлен в магазин' : 'Заказ оформлен'); go(`#/order/${o.id}`);
    } catch (e) { toast(e.message); el.classList.remove('busy'); el.disabled = false; }
    return false;
  },
};
