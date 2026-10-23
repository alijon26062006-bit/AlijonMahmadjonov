import { BRAND, FREE_FROM, KINDS, kindSrc } from '../config.js';
import { eta, openState, ratingText, shopById, shops } from '../model/catalog.js';
import { STAGES, view } from '../model/orders.js';
import { esc } from '../lib/format.js';
import { C, ui } from '../state.js';
import { art } from '../ui/art.js';
import { ico } from '../ui/dom.js';
import { backBar, productCard } from './parts.js';

// Главная в духе приложений доставки: шапка с адресом, поиск, баннеры, плитки разделов,
// логотипы магазинов, большие карточки, «что заказать», фильтры и тёмный блок ресторанов.

export function addrShort() {
  const a = C.addr; if (!a) return '';
  return [a.street, a.house].filter(Boolean).join(', ') || a.city;
}
export const brandMark = `<span class="brand-mark" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 8h14l-1 12H6zM9 8V7a3 3 0 0 1 6 0v1"/></svg></span>`;
export const head = (title, more) => `<div class="sec-head"><h2>${title}</h2>${more ? `<button class="all" data-go="${more}">Все ${ico('right', 'sm')}</button>` : ''}</div>`;
const off = s => Math.max(0, ...s.products.filter(p => p.oldPrice > p.price).map(p => Math.round((1 - p.price / p.oldPrice) * 100)));

// логотип магазина плиткой: фирменный цвет и название
export const shopTile = s => `<button class="logo-tile" data-go="#/shop/${s.id}"><span class="lt" style="background:${s.tile?.bg || s.color};color:${s.tile?.fg || '#21201f'}">${s.logo ? `<img src="${s.logo}" alt="">` : `<b>${esc(s.name)}</b>`}</span><span class="small">${eta(s)}</span></button>`;

// большая карточка магазина: картинка, название и рейтинг, время, плашка доставки
export function bigCard(s) {
  const st = openState(s), d = off(s), fav = C.favShops.includes(s.id);
  return `<article class="big ${st.open ? '' : 'closed'}">
    <button class="big-pic" data-go="#/shop/${s.id}" style="background:${s.color}" aria-label="${esc(s.name)}">
      <img src="${kindSrc(s.kind)}" alt="" width="220" height="220" loading="lazy">
      ${d ? `<span class="badge-off">−${d}%</span>` : ''}${st.open ? '' : `<span class="badge-closed">${esc(st.text)}</span>`}</button>
    <button class="big-fav" data-a="fav" data-kind="shop" data-id="${s.id}" aria-pressed="${fav}" aria-label="${fav ? 'Убрать из избранного' : 'В избранное'}">${ico('heart')}</button>
    <button class="big-info" data-go="#/shop/${s.id}"><span class="row between"><b>${esc(s.name)}</b><span class="rate">★ ${ratingText(s)}</span></span>
      <span class="eta">${ico('bike', 'sm')} ${eta(s)}</span>
      <span class="free">Бесплатная доставка от ${FREE_FROM}</span></button>
  </article>`;
}

const BANNERS = [
  { id: 'sabz', t: 'Скидки до 18% на фрукты', code: 'СВЕЖЕЕ', img: 'img/kind-grocery.webp', bg: '#fbefd9' },
  { go: '#/kind/food', t: 'Бесплатная доставка от 200 смн', code: 'ДОСТАВКА 0', img: 'img/intro-bag.webp', bg: '#fce000' },
  { id: 'atir', t: 'Ароматы — только оригиналы', code: 'АТИР', img: 'img/kind-perfume.webp', bg: '#f1e7da' },
];
const WHAT = [['Плов', 'Горячее'], ['Бургеры', 'Бургеры'], ['Наушники', 'наушники'], ['Чехлы', 'Чехлы'], ['Овощи', 'Овощи и зелень'], ['Фрукты', 'Фрукты и ягоды'], ['Сладкое', 'Десерты'], ['Ароматы', 'Мужская парфюмерия'], ['Напитки', 'Напитки']];
const FILTERS = [['open', 'Открыто сейчас'], ['sale', 'Акции'], ['fast', 'До 40 минут']];
const pass = { open: s => openState(s).open, sale: s => off(s) > 0, fast: s => s.prep <= 20 };

const banner = b => `<button class="banner" style="background:${b.bg}" data-go="${b.go || '#/shop/' + b.id}"><span class="bt"><b>${esc(b.t)}</b><span class="code">${esc(b.code)}</span></span><img src="${b.img}" alt="" width="200" height="200" loading="lazy"></button>`;

export function vHome() {
  const all = shops(), live = C.orders.map(view).find(v => v.stage >= 0 && v.stage < 4);
  const past = [...new Set(C.orders.filter(o => o.receivedAt).map(o => o.shopId))].map(shopById).filter(Boolean);
  let list = all.filter(s => s.kind !== 'food').filter(s => Object.entries(ui.f || {}).every(([k, on]) => !on || pass[k](s)));
  if (ui.sort === 'rating') list = [...list].sort((a, b) => (b.isNew ? 0 : b.rating) - (a.isNew ? 0 : a.rating));
  const food = all.filter(s => s.kind === 'food');
  const promo = all.find(s => s.local) || all[0];
  return `
    <header class="home-head">
      ${brandMark}
      <button class="where" data-a="address"><b>${BRAND}</b><span>${esc(addrShort()) || 'Укажите адрес'} <i>${ico('right', 'sm')}</i></span></button>
      <button class="round ghost" data-go="#/favorites" aria-label="Избранное">${ico('heart')}</button>
    </header>
    <button class="search-pill" data-go="#/search">${ico('search')}<span>Поиск</span></button>
    ${live ? `<button class="live" data-go="#/order/${live.o.id}"><span class="pulse"></span><span class="grow"><b>${STAGES[live.stage]}</b><small>Заказ № ${live.o.no} · ${esc(live.o.shopName)}${live.waiting ? ' · нужен ваш ответ' : ''}</small></span>${ico('right', 'sm')}</button>` : ''}
    <div class="banners">${BANNERS.map(banner).join('')}</div>
    <div class="bento">
      <button class="tile tall" data-go="#/kind/food"><img src="img/kind-food.webp" alt="" width="200" height="200"><b>Рестораны</b></button>
      <button class="tile" data-go="#/kind/grocery"><img src="img/kind-grocery.webp" alt="" width="120" height="120"><b>Продукты</b></button>
      <button class="tile" data-go="#/kind/perfume"><img src="img/kind-perfume.webp" alt="" width="120" height="120"><b>Парфюмерия</b></button>
      <button class="tile wide" data-go="#/kind/tech"><img src="${kindSrc('tech')}" alt="" width="120" height="120"><span><b>Аксессуары</b><small>Наушники, чехлы, зарядки, кабели</small></span></button>
    </div>
    <div class="minis">
      <button class="mini" data-a="filterSale"><span class="m" style="background:#ff5a36;color:#fff">%</span><b>Акции</b></button>
      ${all.slice(0, 3).map(s => `<button class="mini" data-go="#/shop/${s.id}"><span class="m" style="background:${s.tile?.bg || s.color};color:${s.tile?.fg || '#21201f'}">${esc(s.name.charAt(0))}</span><b>${esc(s.name.split(' ')[0])}</b></button>`).join('')}
    </div>
    <section class="section">${head('Скидки и не только')}${banner({ id: promo.id, t: `Всё для дома в «${promo.name}»`, code: 'ЗАКАЗАТЬ', img: kindSrc(promo.kind), bg: '#fbefd9' })}</section>
    <section class="section">${head('Магазины', '#/kind/grocery')}<div class="logo-row">${all.filter(s => s.kind !== 'food').map(shopTile).join('')}</div></section>
    ${past.length ? `<section class="section">${head('Вы заказывали', '#/orders')}<div class="hscroll">${past.map(bigCard).join('')}</div></section>` : ''}
    <section class="section">${head('Что заказать')}
      <div class="what">${WHAT.map(([t, q]) => `<button class="what-i" data-a="searchFor" data-q="${q}" data-goto="search"><span class="w">${art({ cat: q, name: t })}</span><span>${t}</span></button>`).join('')}</div>
      <div class="filters">
        <button class="fbtn ${ui.sort === 'rating' ? 'on' : ''}" data-a="sortRating" aria-pressed="${ui.sort === 'rating'}">${ico('star', 'sm')} Рейтинг ${ico('down', 'sm')}</button>
        ${FILTERS.map(([k, t]) => `<button class="fbtn ${ui.f?.[k] ? 'on' : ''}" data-a="filterToggle" data-v="${k}" aria-pressed="${!!ui.f?.[k]}">${t}</button>`).join('')}
      </div>
      <div class="cards">${list.map(bigCard).join('') || '<div class="empty"><p>Под эти фильтры ничего не нашлось.</p></div>'}</div>
    </section>
    ${food.length ? `<section class="dark-block">
      <button class="dark-head" data-go="#/kind/food"><span><b>Горячее рядом ${ico('right', 'sm')}</b><span>Плов, шашлык, бургеры — привезём горячим</span></span><img src="img/kind-food.webp" alt="" width="150" height="150"></button>
      <div class="cards">${food.map(bigCard).join('')}</div>
    </section>` : ''}`;
}

export function vKind(id) {
  const k = KINDS.find(x => x.id === id); if (!k) return vHome();
  const list = shops().filter(s => s.kind === id);
  const hits = list.flatMap(s => s.products.filter(p => p.labels.includes('Хит') || p.oldPrice).map(p => [s, p])).slice(0, 10);
  return `${backBar(k.name)}
    ${list.length > 1 ? `<div class="logo-row">${list.map(shopTile).join('')}</div>` : ''}
    <div class="cards">${list.map(bigCard).join('') || '<div class="empty"><p>В вашем городе пока нет таких магазинов.</p></div>'}</div>
    ${hits.length ? `<section class="section">${head('Популярное')}<div class="grid">${hits.map(([s, p]) => productCard(s, p)).join('')}</div></section>` : ''}`;
}

// скелет главной, пока грузятся шрифты: без прыжков вёрстки
export const skeleton = () => `<main class="page"><div class="home-head">${brandMark}</div>
  <div class="sk-row">${'<span class="sk sq"></span>'.repeat(5)}</div>
  ${'<span class="sk card"></span><span class="sk line w60"></span><span class="sk line w40"></span>'.repeat(2)}</main>`;
