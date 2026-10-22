import { WEIGHT_UNITS } from '../config.js';
import { qtyInCart, stepOf } from '../model/cart.js';
import { eta, openState, ratingText } from '../model/catalog.js';
import { esc, money, qtyLabel } from '../lib/format.js';
import { C } from '../state.js';
import { pic } from '../ui/art.js';
import { ico } from '../ui/dom.js';

// Общие куски: карточка магазина, карточка товара, шапка с кнопкой «назад»

export const logo = s => `<span class="logo">${s.logo ? `<img src="${s.logo}" alt="">` : esc(s.name.charAt(0))}</span>`;
export const kindImg = (kind, cls = 'k') => `<img class="${cls}" src="img/kind-${kind}.webp" alt="" width="160" height="160" loading="lazy">`;

export function shopCard(s) {
  const st = openState(s);
  return `<button class="shop-card ${st.open ? '' : 'closed'}" data-go="#/shop/${s.id}">
    <span class="shop-cover" style="background:${s.color}">${kindImg(s.kind)}${logo(s)}
      ${st.open ? '' : `<span class="tag dark">${esc(st.text)}</span>`}</span>
    <span class="col" style="gap:4px"><h3>${esc(s.name)}</h3>
      <span class="shop-meta"><span class="rate"><span class="star">★</span>${ratingText(s)}</span>${s.count ? `<span>${s.count} оценок</span>` : ''}<span>${ico('clock', 'sm')} ${eta(s)}</span>${s.minOrder ? `<span>от ${money(s.minOrder)}</span>` : ''}</span></span>
  </button>`;
}

export const attrLine = p => {
  const a = p.attrs || {};
  return [a.brand, a.volume && `${a.volume} мл`, a.pack, a.portion && `${a.portion} г`, a.origin === 'Тестер' || a.origin === 'Разлив' ? a.origin.toLowerCase() : ''].filter(Boolean).join(' · ');
};
export function priceFrom(p) { return p.variants.length ? Math.min(...p.variants.map(v => v.price)) : p.price; }

export function productCard(shop, p) {
  const q = qtyInCart(p.id), weight = WEIGHT_UNITS.includes(p.unit), complex = p.variants.length || p.options.length;
  const off = p.oldPrice && p.oldPrice > p.price ? Math.round((1 - p.price / p.oldPrice) * 100) : 0;
  const meta = attrLine(p) || (weight ? `за 1 ${p.unit}` : p.unit !== 'шт' ? `за 1 ${p.unit}` : '');
  const ctl = complex
    ? `<button class="add" data-a="product" data-shop="${shop.id}" data-pid="${p.id}">${q ? `В корзине ${weight ? qtyLabel(q, p.unit) : q}` : `${ico('plus', 'sm')} Выбрать`}</button>`
    : q ? `<div class="stepper"><button data-a="minus" data-shop="${shop.id}" data-pid="${p.id}" aria-label="Убрать">${ico('minus', 'sm')}</button><span class="num">${weight ? qtyLabel(q, p.unit) : q}</span><button data-a="plus" data-shop="${shop.id}" data-pid="${p.id}" aria-label="Добавить" ${q + stepOf(p) > p.stock ? 'disabled' : ''}>${ico('plus', 'sm')}</button></div>`
      : `<button class="add" data-a="plus" data-shop="${shop.id}" data-pid="${p.id}" aria-label="Добавить ${esc(p.name)}">${ico('plus', 'sm')} ${weight ? qtyLabel(stepOf(p), p.unit) : 'В корзину'}</button>`;
  return `<article class="card">
    <button class="pic" data-a="product" data-shop="${shop.id}" data-pid="${p.id}" aria-label="${esc(p.name)}">${pic(p)}
      <span class="tags">${off ? `<span class="tag sale">−${off}%</span>` : ''}${p.labels.slice(0, 1).map(l => `<span class="tag">${esc(l)}</span>`).join('')}</span></button>
    <div class="price num">${p.variants.length ? '<span class="tiny muted">от</span>' : ''}<b class="${off ? 'sale' : ''}">${money(priceFrom(p))}</b>${off ? `<s>${money(p.oldPrice)}</s>` : ''}</div>
    <button class="name" data-a="product" data-shop="${shop.id}" data-pid="${p.id}">${esc(p.name)}</button>
    <span class="meta">${esc(meta) || '&nbsp;'}</span>
    ${ctl}
  </article>`;
}

export const backBar = (title, right = '', to = '') => `<div class="back"><button class="round" data-a="back" ${to ? `data-to="${to}"` : ''} aria-label="Назад">${ico('back')}</button><h3 class="grow">${esc(title)}</h3>${right}</div>`;
export const favBtn = (kind, id) => {
  const on = (kind === 'shop' ? C.favShops : C.favProducts).includes(id);
  return `<button class="round" data-a="fav" data-kind="${kind}" data-id="${id}" aria-pressed="${on}" aria-label="${on ? 'Убрать из избранного' : 'В избранное'}" style="${on ? 'color:var(--bad)' : ''}">${on ? ico('heart').replace('class="ico ', 'style="fill:currentColor" class="ico ') : ico('heart')}</button>`;
};
