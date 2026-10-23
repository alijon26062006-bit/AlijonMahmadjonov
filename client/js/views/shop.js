import { FREE_FROM, WEIGHT_UNITS } from '../config.js';
import { add, stepOf, totals, unitPrice } from '../model/cart.js';
import { DELIVERY_FEE } from '../config.js';
import { eta, kindName, openState, productIn, ratingText, shopById } from '../model/catalog.js';
import { esc, money, qtyLabel, r2 } from '../lib/format.js';
import { C, save, ui } from '../state.js';
import { art } from '../ui/art.js';
import { closeSheet, ico, openSheet, toast } from '../ui/dom.js';
import { backBar, likesLine, productCard, unitLine } from './parts.js';

const slug = c => 'c-' + [...c].reduce((s, ch) => (s * 31 + ch.charCodeAt(0)) >>> 0, 7).toString(36);

export function vShop(id) {
  const s = shopById(id);
  if (!s) return `${backBar('Магазин')}<div class="empty"><p>Магазин не найден или больше не работает.</p><button class="btn primary" data-go="#/">На главную</button></div>`;
  const st = openState(s), on = C.favShops.includes(s.id);
  const deals = s.products.filter(p => p.oldPrice > p.price).sort((x, y) => (y.oldPrice - y.price) - (x.oldPrice - x.price)).slice(0, 4);
  return `<div class="shop-top">
      <button class="icon-btn" data-a="back" aria-label="Назад">${ico('arrowL')}</button><b class="t" translate="no">${esc(s.name)}</b>
      <button class="icon-btn" data-go="#/search" aria-label="Поиск">${ico('search')}</button>
      <button class="icon-btn ${on ? 'faved' : ''}" data-a="fav" data-kind="shop" data-id="${s.id}" aria-pressed="${on}" aria-label="${on ? 'Убрать из избранного' : 'В избранное'}">${ico('heart')}</button></div>
    ${s.cover ? `<img class="shop-cover-img" src="${s.cover}" alt="" width="1200" height="600">` : ''}
    <h1 class="shop-name" translate="no">${esc(s.name)}</h1>
    <div class="shop-info">
      <button class="si" data-a="shopInfo" data-id="${s.id}"><span class="si-ico">${ico('starFill')}</span><span><b>${ratingText(s)}${s.count ? ` (${s.count})` : ''}</b><small>Подробнее ${ico('right', 'xs')}</small></span></button>
      <i class="sep"></i>
      <div class="si"><span class="si-ico">${ico('bike')}</span><span><b>${eta(s).replace('мин', 'минут')}</b><small>Доставка</small></span></div>
      <i class="sep"></i>
      <button class="si dots" data-a="shopInfo" data-id="${s.id}" aria-label="О магазине">${ico('dots')}</button>
    </div>
    ${st.open ? (s.minOrder ? `<p class="small muted" style="margin-top:-14px">${esc(st.text)} · заказ от ${money(s.minOrder)}</p>` : `<p class="small muted" style="margin-top:-14px">${esc(st.text)}</p>`)
      : `<div class="notice">${ico('clock', 'sm')}<span><b>${esc(st.text)}.</b> Соберите корзину сейчас — оформим заказ к открытию.</span></div>`}
    ${deals.length ? `<div class="deals">${deals.map(p => `<button class="deal" data-a="product" data-shop="${s.id}" data-pid="${p.id}"><span class="deal-ico">${ico('tag')}</span><b>−${money(p.oldPrice - p.price)}</b><small>${esc(p.name)}</small>${ico('right', 'sm')}</button>`).join('')}</div>` : ''}
    ${s.cats.length > 1 ? `<nav class="utabs" aria-label="Разделы меню">${s.cats.map((c, i) => `<button class="ut ${i ? '' : 'on'}" data-a="jump" data-to="${slug(c)}">${esc(c)}</button>`).join('')}</nav>` : ''}
    ${s.products.length ? s.cats.map(c => `<section class="section menu-sec" id="${slug(c)}"><h2>${esc(c)}</h2><div class="grid">${s.products.filter(p => p.cat === c).map(p => productCard(s, p)).join('')}</div></section>`).join('')
      : '<div class="empty"><p>Магазин ещё не добавил товары.</p></div>'}`;
}
/** Полоса бесплатной доставки внизу магазина, как в приложениях доставки. */
export function shopDock(id) {
  const T = totals(), sum = T.shop?.id === id ? T.sum : 0, left = Math.max(0, FREE_FROM - sum);
  const bar = `<div class="deliv"><span class="d-ico">${ico('bike')}</span><b class="num">${left ? money(DELIVERY_FEE) : 'Бесплатно'}</b><span class="d-track"><i style="width:${Math.min(100, sum / FREE_FROM * 100)}%"></i></span><span class="d-free num">0 смн</span></div>
    <span class="d-cap">${left ? (sum ? `Ещё ${money(left)} — и доставка бесплатная` : `Бесплатно на заказ от ${money(FREE_FROM)}`) : 'Доставка бесплатная'}</span>`;
  return T.rows.length ? `<div class="col" style="gap:8px">${bar}<button class="cartbar" data-go="#/cart">${ico('basket')}<span class="grow" style="text-align:left">Корзина<small>${esc(T.shop.name)}</small></span><span class="num">${money(T.total)}</span></button></div>` : `<div class="col" style="gap:4px">${bar}</div>`;
}
/** Подсветка раздела меню при прокрутке. */
export function spyTabs() {
  const tabs = [...document.querySelectorAll('.ut')]; if (!tabs.length) return;
  const io = new IntersectionObserver(es => {
    const vis = es.filter(e => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]; if (!vis) return;
    tabs.forEach(t => t.classList.toggle('on', t.dataset.to === vis.target.id));
    const on = tabs.find(t => t.classList.contains('on')); on?.scrollIntoView({ inline: 'center', block: 'nearest' });
  }, { rootMargin: '-140px 0px -60% 0px' });
  document.querySelectorAll('.menu-sec').forEach(sec => io.observe(sec));
}
export function shopInfo(id) {
  const s = shopById(id), st = openState(s);
  openSheet(`<h2>${esc(s.name)}</h2><p class="muted">${esc(s.about || kindName(s.kind))}</p>
    <div class="list">
      <div class="li">${ico('starFill')}<span class="grow"><b>Рейтинг ${ratingText(s)}</b><small>${s.count ? `${s.count} оценок за 3 месяца` : 'Пока мало оценок'}</small></span></div>
      <div class="li">${ico('clock')}<span class="grow"><b>${esc(st.text)}</b><small>Сборка заказа ~${s.prep} мин</small></span></div>
      <div class="li">${ico('bike')}<span class="grow"><b>Доставка ${money(DELIVERY_FEE)}</b><small>Бесплатно от ${money(FREE_FROM)}${s.minOrder ? ` · заказ от ${money(s.minOrder)}` : ''}</small></span></div>
      <div class="li">${ico('pin')}<span class="grow"><b>Адрес магазина</b><small>${esc(s.address || '—')}</small></span></div>
    </div>`, { label: s.name });
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
  const price = unitPrice(p, vid, opts), total = r2(price * qty), old = p.oldPrice > p.price && !p.variants.length ? r2(p.oldPrice * qty) : 0;
  const imgs = p.imgs?.length ? p.imgs.map(src => `<img src="${src}" alt="${esc(p.name)}">`).join('') : art(p);
  const specs = [['Бренд', a.brand], ['Для устройств', a.compat], ['Для кого', a.gender], ['Тип', a.ptype], ['Объём', a.volume && a.volume + ' мл'], ['Мощность, ёмкость', a.power], ['Цвет', a.color],
    [s.kind === 'tech' ? 'Оригинальность' : 'Состояние', a.origin], ['Гарантия', a.warranty && (a.warranty === '0' ? 'без гарантии' : a.warranty + ' мес.')], ['Упаковка', a.pack], ['Вес порции', a.portion && a.portion + ' г'],
    ['Острота', a.spicy], ['Страна', a.country], ['Годен до', p.expiry && new Date(p.expiry).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })]].filter(x => x[1]);
  const base = p.variants.length ? Math.min(...p.variants.map(v => v.price)) : p.price;
  const more = s.products.filter(x => x.id !== p.id).sort((x, y) => (y.cat === p.cat) - (x.cat === p.cat)).slice(0, 6);
  const fav = C.favProducts.includes(s.id + '::' + p.id);
  openSheet(`
    <div class="p-gallery" translate="no">${imgs}</div>
    <div class="p-head">
      <div class="row" style="gap:8px;flex-wrap:wrap">${p.oldPrice > p.price ? `<span class="off static">−${money(p.oldPrice - p.price)}</span>` : ''}${likesLine(p)}</div>
      <div class="row" style="align-items:flex-start"><h2 class="grow p-title" translate="no">${esc(p.name)}</h2><button class="icon-btn ${fav ? 'faved' : ''}" data-a="pfav" data-id="${s.id}::${p.id}" aria-pressed="${fav}" aria-label="${fav ? 'Убрать из избранного' : 'В избранное'}">${ico('heart')}</button></div>
      <span class="muted">${esc(unitLine(p))}</span>
      ${p.desc ? `<p class="p-desc" translate="no">${esc(p.desc)}</p>` : ''}
    </div>
    ${p.variants.length ? `<div class="grp"><span class="grp-t">Выберите вариант</span>${p.variants.map(v => `<label class="ropt"><input type="radio" name="pv" value="${v.id}" ${v.id === vid ? 'checked' : ''} data-a="pv"><span class="circle"></span><span class="grow" translate="no">${esc(v.name)}</span><span class="muted num">${v.price === base ? money(v.price) : '+' + money(v.price - base)}</span></label>`).join('')}</div>` : ''}
    ${p.options.length ? `<div class="grp"><span class="grp-t">Добавки и пожелания</span>${p.options.map(o => `<label class="ropt"><input type="checkbox" value="${o.id}" ${opts.includes(o.id) ? 'checked' : ''} data-a="po"><span class="circle sq"></span><span class="grow" translate="no">${esc(o.name)}</span><span class="muted num">+${money(o.price)}</span></label>`).join('')}</div>` : ''}
    ${specs.length ? `<div class="grp"><span class="grp-t">Характеристики</span><dl class="specs">${specs.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join('')}</dl></div>` : ''}
    ${more.length ? `<div class="grp"><h2>Вам может понравиться</h2><div class="grid three">${more.map(x => productCard(s, x, true)).join('')}</div></div>` : ''}`,
  { label: p.name, keepScroll: keep, foot: `<div class="pfoot"><div class="row between" style="gap:12px"><span class="pf-name" translate="no">${esc(p.name)}</span><span class="pf-price num">${old ? `<s>${money(old)}</s>` : ''}<b class="${old ? 'sale' : ''}">${money(total)}</b></span></div>
      <div class="row" style="gap:10px"><div class="stepper light pf-step"><button data-a="pq" data-d="-1" aria-label="Меньше" ${qty <= stepOf(p) ? 'disabled' : ''}>${ico('minus', 'sm')}</button><span class="num">${weight ? qtyLabel(qty, p.unit) : qty}</span><button data-a="pq" data-d="1" aria-label="Больше" ${qty + stepOf(p) > p.stock ? 'disabled' : ''}>${ico('plus', 'sm')}</button></div>
      <button class="btn primary grow" data-a="padd">Добавить</button></div></div>`, onClose: () => { pick = null; } });
}
/** Корзина поменялась из «Вам может понравиться» — перерисовать открытую карточку. */
export function refreshProduct() { if (pick) drawProduct(true); }
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
