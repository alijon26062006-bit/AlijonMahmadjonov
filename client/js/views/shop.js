import { FREE_FROM, WEIGHT_UNITS } from '../config.js';
import { add, qtyInCart, stepOf, unitPrice } from '../data/cart.js';
import { DELIVERY_FEE } from '../config.js';
import { eta, kindName, openState, productIn, ratingText, shopById } from '../data/catalog.js';
import { esc, money, qtyLabel, r2 } from '../lib/format.js';
import { C, save, ui } from '../state.js';
import { art } from '../ui/art.js';
import { closeSheet, ico, openSheet, toast } from '../ui/dom.js';
import { attrLine, backBar, favBtn, logo, productCard } from './parts.js';

const slug = c => 'c-' + [...c].reduce((s, ch) => (s * 31 + ch.charCodeAt(0)) >>> 0, 7).toString(36);

export function vShop(id) {
  const s = shopById(id);
  if (!s) return `${backBar('Магазин')}<div class="empty"><p>Магазин не найден или больше не работает.</p><button class="btn primary" data-go="#/">На главную</button></div>`;
  const st = openState(s);
  return `${backBar(s.name, favBtn('shop', s.id))}
    <section class="shop-hero" style="background:${s.color}"><div class="col" style="gap:6px"><h1 style="font-size:26px">${esc(s.name)}</h1><p>${esc(s.about || kindName(s.kind))}</p></div>${logo(s)}</section>
    <div class="facts">
      <div class="fact"><b><span class="star">★</span> ${ratingText(s)}</b><span>${s.count ? `${s.count} оценок` : 'мало оценок'}</span></div>
      <div class="fact"><b>${eta(s)}</b><span>доставка</span></div>
      <div class="fact"><b>${money(DELIVERY_FEE)}</b><span>бесплатно от ${FREE_FROM}</span></div>
    </div>
    ${st.open ? (s.minOrder ? `<div class="notice info">${ico('clock', 'sm')}<span>${esc(st.text)} · минимальный заказ ${money(s.minOrder)}</span></div>` : '')
      : `<div class="notice">${ico('clock', 'sm')}<span><b>${esc(st.text)}.</b> Соберите корзину сейчас — оформим заказ к открытию.</span></div>`}
    ${s.cats.length > 1 ? `<div class="cat-tabs"><div class="chips">${s.cats.map(c => `<button class="chip" data-a="jump" data-to="${slug(c)}" aria-pressed="${ui.shopCat === c}">${esc(c)}</button>`).join('')}</div></div>` : ''}
    ${s.products.length ? s.cats.map(c => `<section class="section" id="${slug(c)}" style="scroll-margin-top:120px"><h2>${esc(c)}</h2><div class="grid">${s.products.filter(p => p.cat === c).map(p => productCard(s, p)).join('')}</div></section>`).join('')
      : '<div class="empty"><p>Магазин ещё не добавил товары.</p></div>'}`;
}

// ----- карточка товара в шторке -----
let pick = null;   // выбор в открытой карточке: вариант, добавки, количество
export function openProduct(shopId, pid) {
  const s = shopById(shopId), p = productIn(s, pid); if (!p) return toast('Товар закончился');
  pick = { s, p, vid: p.variants[0]?.id || '', opts: [], qty: stepOf(p) };
  drawProduct();
}
function drawProduct(keep) {
  const { s, p, vid, opts, qty } = pick, a = p.attrs || {}, weight = WEIGHT_UNITS.includes(p.unit);
  const price = unitPrice(p, vid, opts), total = r2(price * qty);
  const imgs = p.imgs?.length ? p.imgs.map(src => `<img src="${src}" alt="${esc(p.name)}">`).join('') : art(p);
  const specs = [['Бренд', a.brand], ['Для кого', a.gender], ['Тип', a.ptype], ['Объём', a.volume && a.volume + ' мл'], ['Состояние', a.origin], ['Упаковка', a.pack], ['Вес порции', a.portion && a.portion + ' г'], ['Острота', a.spicy], ['Страна', a.country],
    ['Годен до', p.expiry && new Date(p.expiry).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })]].filter(x => x[1]);
  const inCart = qtyInCart(p.id);
  openSheet(`
    <div class="gallery">${imgs}</div>
    <div class="col" style="gap:6px">
      <div class="row" style="align-items:flex-start"><h2 class="grow">${esc(p.name)}</h2>${favBtn('product', s.id + '::' + p.id).replace('data-a="fav"', 'data-a="pfav"')}</div>
      ${attrLine(p) ? `<span class="muted">${esc(attrLine(p))}</span>` : ''}
      <div class="row" style="flex-wrap:wrap"><b class="num" style="font-size:22px">${money(price)}</b>${weight || p.unit !== 'шт' ? `<span class="muted">за 1 ${esc(p.unit)}</span>` : ''}${p.oldPrice > p.price && !p.variants.length ? `<s class="muted">${money(p.oldPrice)}</s>` : ''}
        ${p.likes ? `<span class="tag ok">${ico('up', 'sm')} Нравится ${p.likes}%</span>` : ''}</div>
    </div>
    ${p.variants.length ? `<div class="field"><span class="lbl">Вариант</span><div class="chips wrap">${p.variants.map(v => `<label class="chip"><input type="radio" name="pv" value="${v.id}" ${v.id === vid ? 'checked' : ''} data-a="pv">${esc(v.name)} · ${money(v.price)}</label>`).join('')}</div></div>` : ''}
    ${p.options.length ? `<div class="field"><span class="lbl">Добавки и пожелания</span><div class="col" style="gap:8px">${p.options.map(o => `<label class="opt"><input type="checkbox" value="${o.id}" ${opts.includes(o.id) ? 'checked' : ''} data-a="po"><span class="grow">${esc(o.name)}</span><b class="num">${o.price ? '+' + money(o.price) : 'бесплатно'}</b></label>`).join('')}</div></div>` : ''}
    ${p.desc ? `<p>${esc(p.desc)}</p>` : ''}
    ${specs.length ? `<dl class="specs">${specs.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join('')}</dl>` : ''}
    <div class="row muted small">${ico('store', 'sm')} ${esc(s.name)}${inCart ? ` · уже в корзине ${weight ? qtyLabel(inCart, p.unit) : inCart + ' шт'}` : ''}</div>`,
  { label: p.name, keepScroll: keep, foot: `<div class="stepper light" style="flex:none;width:150px"><button data-a="pq" data-d="-1" aria-label="Меньше" ${qty <= stepOf(p) ? 'disabled' : ''}>${ico('minus', 'sm')}</button><span class="num">${weight ? qtyLabel(qty, p.unit) : qty}</span><button data-a="pq" data-d="1" aria-label="Больше" ${qty + stepOf(p) > p.stock ? 'disabled' : ''}>${ico('plus', 'sm')}</button></div>
      <button class="btn primary" data-a="padd">Добавить<span class="sum">${money(total)}</span></button>`, onClose: () => { pick = null; } });
}
export const productActions = {
  pfav: el => { const l = C.favProducts, id = el.dataset.id; if (l.includes(id)) l.splice(l.indexOf(id), 1); else l.push(id); save(); drawProduct(true); toast(l.includes(id) ? 'Добавили в избранное' : 'Убрали из избранного'); return false; },
  pv: el => { pick.vid = el.value; drawProduct(true); },
  po: el => { pick.opts = el.checked ? [...pick.opts, el.value] : pick.opts.filter(x => x !== el.value); drawProduct(true); },
  pq: el => { const st = stepOf(pick.p); pick.qty = Math.max(st, r2(pick.qty + +el.dataset.d * st)); drawProduct(true); },
  padd: async (el, force) => {
    const { s, p, vid, opts, qty } = pick;
    const r = add(s, p, { vid, opts, qty }, force === true);
    if (r === 'other') return askReplace(() => productActions.padd(el, true));
    closeSheet(); toast(`${p.name} — в корзине`);
  },
};
/** В корзине товары другого магазина: спросить, начать ли новую. */
export function askReplace(yes) {
  openSheet(`<h2>Начать новую корзину?</h2><p class="muted">В корзине уже есть товары из другого магазина. Один заказ — из одного магазина, так курьер привезёт всё сразу.</p>`,
    { label: 'Новая корзина', foot: `<button class="btn" data-a="closeSheet">Оставить</button><button class="btn primary" data-a="replaceYes">Очистить и добавить</button>` });
  productActions.replaceYes = () => { closeSheet(); yes(); };
}
