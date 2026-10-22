import { FREE_FROM, IF_MISSING, WEIGHT_UNITS } from '../config.js';
import { bump, clear, totals } from '../data/cart.js';
import { eta, openState } from '../data/catalog.js';
import { esc, money, qtyLabel } from '../lib/format.js';
import { C } from '../state.js';
import { pic } from '../ui/art.js';
import { ico, toast } from '../ui/dom.js';
import { backBar, logo } from './parts.js';

// Корзина
export function vCart() {
  const T = totals(), { shop, rows } = T;
  if (!rows.length) return `${backBar('Корзина')}
    <div class="empty"><img src="img/kind-grocery.webp" alt="" width="120" height="120"><h2>Корзина пустая</h2><p>Загляните в магазины рядом — добавьте то, что нужно, и мы привезём.</p><button class="btn primary" data-go="#/">Выбрать магазин</button></div>`;
  const toFree = Math.max(0, FREE_FROM - T.sum);
  const st = openState(shop);
  return `${backBar('Корзина', `<button class="round" data-a="clearCart" aria-label="Очистить корзину">${ico('trash')}</button>`)}
    <button class="li list" data-go="#/shop/${shop.id}" style="border-radius:var(--r)">${logo(shop)}<span class="grow"><b>${esc(shop.name)}</b><small>${st.open ? 'Доставка ' + eta(shop) : esc(st.text)}</small></span>${ico('right', 'chev')}</button>
    <div class="col" style="gap:14px">${rows.map(r => {
      const w = WEIGHT_UNITS.includes(r.p.unit);
      return `<div class="cart-row"><span class="thumb">${pic(r.p)}</span>
        <div style="min-width:0"><div class="small" style="font-weight:600">${esc(r.p.name)}${r.variant ? ', ' + esc(r.variant) : ''}</div>
          ${r.optNames.length ? `<div class="tiny muted">${r.optNames.map(o => esc(o.name)).join(', ')}</div>` : ''}
          <div class="tiny muted num">${money(r.price)}${w || r.p.unit !== 'шт' ? ` за 1 ${esc(r.p.unit)}` : ''}</div>
          <b class="num small">${money(r.sum)}</b></div>
        <div class="stepper light"><button data-a="bump" data-key="${esc(r.key)}" data-d="-1" aria-label="Меньше">${ico('minus', 'sm')}</button><span class="num small">${w ? qtyLabel(r.qty, r.p.unit) : r.qty}</span><button data-a="bump" data-key="${esc(r.key)}" data-d="1" aria-label="Больше" ${r.qty >= r.p.stock ? 'disabled' : ''}>${ico('plus', 'sm')}</button></div></div>`;
    }).join('')}</div>
    ${T.left ? `<div class="col" style="gap:8px"><span class="small">До минимального заказа <b>${money(T.left)}</b></span><div class="progress"><i style="width:${T.sum / shop.minOrder * 100}%"></i></div></div>`
      : toFree ? `<div class="col" style="gap:8px"><span class="small">До бесплатной доставки <b>${money(toFree)}</b></span><div class="progress"><i style="width:${T.sum / FREE_FROM * 100}%"></i></div></div>`
      : `<div class="notice ok">${ico('check', 'sm')}<span>Доставка бесплатная</span></div>`}
    <section class="section"><h3>Если товара не окажется</h3>
      <div class="col" style="gap:8px">${IF_MISSING.map(([k, t]) => `<label class="opt"><input type="radio" name="miss" value="${k}" ${C.cart.ifMissing === k ? 'checked' : ''} data-a="ifMissing"><span class="grow">${t}</span></label>`).join('')}</div>
      ${shop.kind === 'grocery' ? '<span class="small muted">Весовой товар взвешивают при сборке: сумма может немного измениться, разницу вернём.</span>' : ''}</section>
    ${shop.kind === 'food' ? `<label class="opt"><input type="checkbox" ${C.cart.cutlery ? 'checked' : ''} data-a="cutlery"><span class="grow">Положить приборы</span></label>` : ''}
    <div class="field"><label for="cmt">Комментарий магазину</label><textarea class="input" id="cmt" maxlength="300" placeholder="Например: помидоры покрепче" data-input="cartComment">${esc(C.cart.comment)}</textarea></div>
    <div class="sum-table num"><div><span>Товары</span><span>${money(T.sum)}</span></div><div><span>Доставка</span><span>${T.fee ? money(T.fee) : 'бесплатно'}</span></div><div class="total"><span>Итого</span><span>${money(T.total)}</span></div></div>`;
}
export function cartDock() {
  const T = totals(); if (!T.rows.length) return '';
  return `<button class="btn primary block" data-go="#/checkout" ${T.left ? 'disabled' : ''}>${T.left ? `Добавьте ещё на ${money(T.left)}` : 'Перейти к оформлению'}<span class="sum">${money(T.total)}</span></button>`;
}
export const cartActions = {
  bump: el => bump(el.dataset.key, +el.dataset.d),
  clearCart: el => { if (el.dataset.armed) { clear(); return; } confirmClear(el); toast('Нажмите ещё раз, чтобы очистить корзину'); return false; },
};
function confirmClear(el) { el.dataset.armed = '1'; el.style.background = 'var(--bad-soft)'; el.style.color = 'var(--bad)'; setTimeout(() => { if (el.isConnected) { delete el.dataset.armed; el.style.cssText = ''; } }, 3000); }
