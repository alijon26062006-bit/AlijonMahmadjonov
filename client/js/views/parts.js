import { WEIGHT_UNITS } from '../config.js';
import { qtyInCart, stepOf, totals } from '../model/cart.js';
import { esc, money, qtyLabel } from '../lib/format.js';
import { C } from '../state.js';
import { pic } from '../ui/art.js';
import { ico } from '../ui/dom.js';

// Общие куски: карточка товара, полоса корзины, шапка с кнопкой «назад»

export const logo = s => `<span class="logo">${s.logo ? `<img src="${s.logo}" alt="">` : esc(s.name.charAt(0))}</span>`;
export const attrLine = p => {
  const a = p.attrs || {};
  return [a.brand, a.volume && `${a.volume} мл`, a.pack, a.portion && `${a.portion} г`, a.origin === 'Тестер' || a.origin === 'Разлив' ? a.origin.toLowerCase() : ''].filter(Boolean).join(' · ');
};
export function priceFrom(p) { return p.variants.length ? Math.min(...p.variants.map(v => v.price)) : p.price; }

// цена со скидкой зелёным, старая — зачёркнута; скидка на картинке суммой, как в приложениях доставки
export const unitLine = p => attrLine(p) || (WEIGHT_UNITS.includes(p.unit) ? `за 1 ${p.unit}` : `1 ${p.unit}`);
export const likesLine = p => p.likes ? `<span class="likes">${ico('thumb', 'sm')}${p.likes}%${p.likesN ? ` (${p.likesN})` : ''}</span>` : '';

export function productCard(shop, p, small = false) {
  const q = qtyInCart(p.id), weight = WEIGHT_UNITS.includes(p.unit), complex = p.variants.length || p.options.length;
  const save = p.oldPrice && p.oldPrice > p.price ? p.oldPrice - p.price : 0;
  const ids = `data-shop="${shop.id}" data-pid="${p.id}"`;
  const qty = weight ? qtyLabel(q, p.unit) : q;
  const ctl = complex
    ? `<button class="fab ${q ? 'on' : ''}" data-a="product" ${ids} aria-label="${q ? `В корзине: ${qty}. Изменить` : 'Выбрать и добавить'}">${q ? `<span class="num">${qty}</span>` : ico('plus')}</button>`
    : q ? `<div class="fab-step"><button data-a="minus" ${ids} aria-label="Убрать">${ico('minus', 'sm')}</button><span class="num">${qty}</span><button data-a="plus" ${ids} aria-label="Добавить" ${q + stepOf(p) > p.stock ? 'disabled' : ''}>${ico('plus', 'sm')}</button></div>`
      : `<button class="fab" data-a="plus" ${ids} aria-label="Добавить ${esc(p.name)}">${ico('plus')}</button>`;
  return `<article class="card ${small ? 'small' : ''}">
    <div class="pic-wrap"><button class="pic" data-a="product" ${ids} aria-label="${esc(p.name)}" translate="no">${pic(p)}</button>
      ${save ? `<span class="off">−${money(save)}</span>` : p.labels[0] ? `<span class="lbl-tag">${esc(p.labels[0])}</span>` : ''}${ctl}</div>
    <div class="price num">${p.variants.length ? '<span class="from">от</span>' : ''}<b class="${save ? 'sale' : ''}">${money(priceFrom(p))}</b>${save ? `<s>${money(p.oldPrice)}</s>` : ''}</div>
    <button class="name" data-a="product" ${ids} translate="no">${esc(p.name)}</button>
    <span class="meta">${esc(unitLine(p))}</span>
    ${small ? '' : likesLine(p)}
  </article>`;
}

/** Одна полоса корзины внизу: сколько товаров, сумма с доставкой и сколько ехать. */
export function cartBar() {
  const T = totals(); if (!T.rows.length) return '';
  const n = T.rows.reduce((s, r) => s + (WEIGHT_UNITS.includes(r.p.unit) ? 1 : r.qty), 0);
  return `<button class="cartbar" data-go="#/cart"><span class="cb-n num">${n}</span><span class="grow"><b>Корзина</b><small>Доставка до двери ${money(T.fee)}</small></span><b class="num">${money(T.total)}</b></button>`;
}

export const backBar = (title, right = '', to = '') => `<div class="back"><button class="round" data-a="back" ${to ? `data-to="${to}"` : ''} aria-label="Назад">${ico('back')}</button><h3 class="grow">${esc(title)}</h3>${right}</div>`;
export const favBtn = (kind, id) => {
  const on = (kind === 'shop' ? C.favShops : C.favProducts).includes(id);
  return `<button class="round" data-a="fav" data-kind="${kind}" data-id="${id}" aria-pressed="${on}" aria-label="${on ? 'Убрать из избранного' : 'В избранное'}" style="${on ? 'color:var(--bad)' : ''}">${on ? ico('heart').replace('class="ico ', 'style="fill:currentColor" class="ico ') : ico('heart')}</button>`;
};
