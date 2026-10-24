import { BRAND, KINDS, kindSrc } from '../config.js';
import { feeFor, route } from '../model/delivery.js';
import { eta, loadingShops, openState, ratingText, shopById, shops } from '../model/catalog.js';
import { STAGES, view } from '../model/orders.js';
import { esc, money } from '../lib/format.js';
import { C, ui } from '../state.js';
import { ico } from '../ui/dom.js';
import { backBar, productCard } from './parts.js';

// Главная: адрес, поиск, разделы, акции, магазины рядом, все магазины с фильтрами, рестораны.
// Порядок как в больших приложениях доставки: на первом экране уже видно, где заказать.

export function addrShort() {
  const a = C.addr; if (!a) return '';
  return [a.street, a.house].filter(Boolean).join(', ') || a.city;
}
export const head = (title, more) => `<div class="sec-head"><h2>${title}</h2>${more ? `<button class="all" data-go="${more}">Все ${ico('right', 'sm')}</button>` : ''}</div>`;
const off = s => Math.max(0, ...s.products.filter(p => p.oldPrice > p.price).map(p => Math.round((1 - p.price / p.oldPrice) * 100)));
const initials = name => name.split(/\s+/).filter(w => /^[\p{L}\d]/u.test(w)).slice(0, 2).map(w => w[0]).join('').toUpperCase();

/** Знак магазина: загруженный логотип или буквы на фирменном цвете. */
export const shopMark = (s, cls = '') => `<span class="mark ${cls}" style="background:${s.tile?.bg || s.color};color:${s.tile?.fg || '#21201f'}" aria-hidden="true">${s.logo ? `<img src="${s.logo}" alt="">` : `<b translate="no">${esc(initials(s.name))}</b>`}</span>`;

// магазин в ленте «рядом»: круглый знак, название, время
export const shopTile = s => `<button class="near" data-go="#/shop/${s.id}">${shopMark(s)}<b translate="no">${esc(s.name)}</b><small>${eta(s)}</small></button>`;

/** Строка «★ 4,8 · 35–45 мин · 2,1 км · 9 смн» — всё, по чему выбирают магазин. Цена доставки — по расстоянию до вашего адреса. */
export function shopMeta(s) {
  const r = route(s);
  return `<span class="meta-line"><span class="rate">${ico('starFill', 'xs')}${ratingText(s)}</span>${r.ok ? `<span>${eta(s)}</span><span>${ico('bike', 'xs')}${money(feeFor(s))}</span>` : `<span class="far">Не доставляет на ваш адрес</span>`}</span>`;
}

// большая карточка магазина: обложка магазина или фирменный цвет с картинкой раздела
export function bigCard(s) {
  const st = openState(s), d = off(s), fav = C.favShops.includes(s.id);
  const cover = s.cover ? `<img class="cover" src="${s.cover}" alt="" width="1200" height="600" loading="lazy">`
    : `<span class="poster" style="background:${s.tile?.bg || s.color};color:${s.tile?.fg || '#21201f'}"><b translate="no">${esc(s.about || s.name)}</b><img src="${kindSrc(s.kind)}" alt="" width="200" height="200" loading="lazy"></span>`;
  return `<article class="big ${st.open ? '' : 'closed'}">
    <button class="big-pic" data-go="#/shop/${s.id}" aria-label="${esc(s.name)}">${cover}
      ${d ? `<span class="badge-off">−${d}%</span>` : ''}${st.open ? '' : `<span class="badge-closed">${esc(st.text)}</span>`}</button>
    <button class="big-fav" data-a="fav" data-kind="shop" data-id="${s.id}" aria-pressed="${fav}" aria-label="${fav ? 'Убрать из избранного' : 'В избранное'}">${ico('heart')}</button>
    <button class="big-info" data-go="#/shop/${s.id}">${shopMark(s, 'sm')}<span class="grow"><b translate="no">${esc(s.name)}</b>${shopMeta(s)}</span></button>
  </article>`;
}

// акции: без выдуманных промокодов — только то, что правда работает
const BANNERS = [
  { go: '#/shop/sabz', t: 'Скидки до 18% на фрукты', s: 'Дехкон Маркет', img: 'img/kind-grocery.webp', bg: '#fdf1dc' },
  { go: '#/kind/food', t: 'Доставка до двери — от 15 смн', s: 'По всему Шахритусу', img: 'img/intro-bag.webp', bg: '#e6f4ea' },
  { go: '#/shop/atir', t: 'Ароматы — только оригиналы', s: 'Парфюм-хаус Атир', img: 'img/kind-perfume.webp', bg: '#f2ece4' },
];
const FILTERS = [['open', 'Открыто сейчас'], ['sale', 'Со скидкой'], ['fast', 'До 40 минут']];
const pass = { open: s => openState(s).open, sale: s => off(s) > 0, fast: s => s.prep <= 20 };

const banner = b => b.src ? `<button class="banner photo" data-go="#/shop/${b.id}" aria-label="${esc(b.t)}"><img src="${b.src}" alt="" width="1200" height="520"></button>`
  : `<button class="banner" style="background:${b.bg}" data-go="${b.go}"><span class="bt"><b>${esc(b.t)}</b><small>${esc(b.s)}</small></span><img src="${b.img}" alt="" width="200" height="200" loading="lazy"></button>`;

/** Разделы: четыре равные плитки — компактно, чтобы магазины были видны сразу. */
export const kindTiles = () => `<nav class="kinds" aria-label="Разделы">${KINDS.map(k => `<button class="kind" data-go="#/kind/${k.id}"><span class="kind-img"><img src="${kindSrc(k.id)}" alt="" width="120" height="120"></span><b>${k.name}</b></button>`).join('')}</nav>`;

export function vHome() {
  const all = shops(), live = C.orders.map(view).find(v => v.stage >= 0 && v.stage < 4);
  const past = [...new Set(C.orders.filter(o => o.receivedAt).map(o => o.shopId))].map(shopById).filter(Boolean);
  let list = all.filter(s => s.kind !== 'food').filter(s => Object.entries(ui.f || {}).every(([k, on]) => !on || pass[k](s)));
  if (ui.sort === 'rating') list = [...list].sort((a, b) => (b.isNew ? 0 : b.rating) - (a.isNew ? 0 : a.rating));
  const food = all.filter(s => s.kind === 'food');
  return `
    <header class="home-head">
      <button class="where" data-a="address"><small>Доставка</small><b>${addrShort() ? `<span translate="no">${esc(addrShort())}</span>` : '<span>Укажите адрес</span>'}${ico('down', 'sm')}</b></button>
      <button class="round" data-go="#/favorites" aria-label="Избранное">${ico('heart')}</button>
    </header>
    <button class="search-pill" data-go="#/search">${ico('search')}<span>Найти товар или магазин</span></button>
    ${live ? `<button class="live" data-go="#/order/${live.o.id}"><span class="pulse"></span><span class="grow"><b>${STAGES[live.stage]}</b><small>Заказ № ${live.o.no} · ${esc(live.o.shopName)}${live.waiting ? ' · нужен ваш ответ' : ''}</small></span>${ico('right', 'sm')}</button>` : ''}
    ${kindTiles()}
    <div class="banners">${[...all.filter(s => s.banner).map(s => ({ id: s.id, src: s.banner, t: s.name })), ...BANNERS.filter(b => !b.go.startsWith('#/shop/') || shopById(b.go.slice(7)))].map(banner).join('')}</div>
    ${past.length ? `<section class="section">${head('Вы заказывали', '#/orders')}<div class="hscroll">${past.map(bigCard).join('')}</div></section>` : ''}
    ${loadingShops() ? '<section class="section" aria-busy="true"><span class="sk card"></span><span class="sk line w60"></span><span class="sk card"></span></section>'
      : !all.length ? `<section class="section"><div class="empty"><p><b>Магазины скоро появятся</b></p><p class="muted">Продавцы Шахритуса подключаются к ${BRAND}. Загляните чуть позже.</p></div></section>` : `
    <section class="section">${head('Магазины рядом')}<div class="near-row">${all.map(shopTile).join('')}</div></section>
    <section class="section">${head('Все магазины')}
      <div class="filters">
        <button class="fbtn ${ui.sort === 'rating' ? 'on' : ''}" data-a="sortRating" aria-pressed="${ui.sort === 'rating'}">${ico('starFill', 'xs')} Высокий рейтинг</button>
        ${FILTERS.map(([k, t]) => `<button class="fbtn ${ui.f?.[k] ? 'on' : ''}" data-a="filterToggle" data-v="${k}" aria-pressed="${!!ui.f?.[k]}">${t}</button>`).join('')}
      </div>
      <div class="cards">${list.map(bigCard).join('') || '<div class="empty"><p>Под эти фильтры ничего не нашлось.</p></div>'}</div>
    </section>`}
    ${food.length ? `<section class="section">${head('Рестораны и кафе', '#/kind/food')}<div class="cards">${food.map(bigCard).join('')}</div></section>` : ''}`;
}

export function vKind(id) {
  const k = KINDS.find(x => x.id === id); if (!k) return vHome();
  const list = shops().filter(s => s.kind === id);
  const hits = list.flatMap(s => s.products.filter(p => p.labels.includes('Хит') || p.oldPrice).map(p => [s, p])).slice(0, 10);
  return `${backBar(k.name)}
    ${list.length > 1 ? `<div class="near-row">${list.map(shopTile).join('')}</div>` : ''}
    <div class="cards">${list.map(bigCard).join('') || '<div class="empty"><p>В вашем городе пока нет таких магазинов.</p></div>'}</div>
    ${hits.length ? `<section class="section">${head('Популярное')}<div class="grid">${hits.map(([s, p]) => productCard(s, p)).join('')}</div></section>` : ''}`;
}

// скелет главной, пока грузятся шрифты: без прыжков вёрстки
export const skeleton = () => `<main class="page"><span class="sk line w40"></span><span class="sk pill"></span>
  <div class="sk-row">${'<span class="sk sq"></span>'.repeat(4)}</div>
  ${'<span class="sk card"></span><span class="sk line w60"></span>'.repeat(2)}</main>`;
