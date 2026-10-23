import { lang, LANGS, setLang } from '../i18n.js';
import { BRAND } from '../config.js';
import { productIn, shopById } from '../model/catalog.js';
import { esc, fmtPhone } from '../lib/format.js';
import { C, save } from '../state.js';
import { ico, toast, twice } from '../ui/dom.js';
import { backBar, productCard } from './parts.js';
import { bigCard } from './home.js';

// Профиль, избранное, первый запуск

export function vProfile() {
  const u = C.user;
  return `<h1>Профиль</h1>
    ${u ? `<div class="li list" style="border-radius:var(--r)"><span class="logo" style="background:var(--accent)">${esc((u.name || '?').charAt(0).toUpperCase())}</span><span class="grow"><b>${esc(u.name || 'Без имени')}</b><small>+992 ${fmtPhone(u.phone)}</small></span><button class="link" data-a="login">Изменить</button></div>`
      : `<div class="status-hero"><h3>Войдите, чтобы заказывать</h3><p class="muted small">Сохраним адреса и историю заказов</p><button class="btn primary" data-a="login">${ico('phone')} Войти по номеру</button></div>`}
    <div class="list">
      <button class="li" data-go="#/orders">${ico('orders')}<span class="grow">Мои заказы<small>${C.orders.length ? `${C.orders.length} всего` : 'Пока нет'}</small></span>${ico('right', 'chev')}</button>
      <button class="li" data-a="address">${ico('pin')}<span class="grow">Адреса доставки<small>${C.addresses.length ? esc(C.addresses.map(a => a.label || a.street).join(', ')) : 'Не добавлены'}</small></span>${ico('right', 'chev')}</button>
      <button class="li" data-go="#/favorites">${ico('heart')}<span class="grow">Избранное<small>${C.favShops.length + C.favProducts.length || 'Пока пусто'}</small></span>${ico('right', 'chev')}</button>
    </div>
    <section class="section settings"><h2>Настройки</h2>
      <div class="set-row"><span class="set-ico">${ico('globe')}</span><span class="grow"><b>Язык</b></span>
        <div class="seg2" role="radiogroup" aria-label="Язык">${LANGS.map(([k, t]) => `<button role="radio" aria-checked="${lang === k}" data-a="lang" data-v="${k}" translate="no">${t}</button>`).join('')}</div></div>
      <div class="set-row"><span class="set-ico">${ico('moon')}</span><span class="grow"><b>Тёмная тема</b><small>${C.theme === 'auto' ? 'Как в телефоне' : C.theme === 'dark' ? 'Включена' : 'Выключена'}</small></span>
        <button class="switch-btn" role="switch" aria-checked="${isDark()}" data-a="themeToggle" aria-label="Тёмная тема"><i></i></button></div>
      ${C.theme === 'auto' ? '' : '<button class="link" data-a="theme" data-v="auto">Вернуть как в телефоне</button>'}
    </section>
    <div class="list">
      <button class="li" data-a="install">${ico('install')}<span class="grow">Установить на телефон<small>Иконка «${BRAND}» на экране</small></span>${ico('right', 'chev')}</button>
      <a class="li" href="../" style="color:inherit;text-decoration:none">${ico('store')}<span class="grow">Стать продавцом<small>Откройте свой магазин в ${BRAND}</small></span>${ico('right', 'chev')}</a>
      <button class="li" data-a="about">${ico('help')}<span class="grow">О сервисе<small>Как работает оплата и доставка</small></span>${ico('right', 'chev')}</button>
    </div>
    ${u ? `<button class="btn danger block" data-a="logout">${ico('logout')} Выйти</button>` : ''}`;
}

export function vFavorites() {
  const shops = C.favShops.map(shopById).filter(Boolean);
  const prods = C.favProducts.map(k => { const [sid, ...rest] = k.split('::'); const s = shopById(sid); const p = productIn(s, rest.join('::')); return p && [s, p]; }).filter(Boolean);
  return `${backBar('Избранное')}
    ${!shops.length && !prods.length ? '<div class="empty"><p>Нажмите на сердечко у магазина или товара — они появятся здесь.</p></div>' : ''}
    ${shops.length ? `<section class="section"><h2>Магазины</h2><div class="cards">${shops.map(bigCard).join('')}</div></section>` : ''}
    ${prods.length ? `<section class="section"><h2>Товары</h2><div class="grid">${prods.map(([s, p]) => productCard(s, p)).join('')}</div></section>` : ''}`;
}

export const profileActions = {
  theme: el => { C.theme = el.dataset.v; save(); applyTheme(); },
  themeToggle: () => { C.theme = isDark() ? 'light' : 'dark'; save(); applyTheme(); },
  lang: el => { setLang(el.dataset.v); },
  logout: el => { if (!twice(el, 'Нажмите ещё раз, чтобы выйти')) return false; C.user = null; save(); toast('Вы вышли'); },
  fav: el => {
    const list = el.dataset.kind === 'shop' ? C.favShops : C.favProducts, id = el.dataset.id, has = list.includes(id);
    if (has) list.splice(list.indexOf(id), 1); else list.push(id);
    save(); toast(has ? 'Убрали из избранного' : 'Добавили в избранное');
  },
};
export const isDark = () => C.theme === 'dark' || (C.theme === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches);
export function applyTheme() { if (C.theme === 'auto') delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = C.theme; }

// ----- первый запуск -----
const SLIDES = [
  { img: 'img/kind-grocery.webp', t: 'Всё рядом в одном приложении', d: 'Продукты, парфюмерия и рестораны вашего города. Цены и наличие — прямо из магазина.' },
  { img: 'img/intro-bag.webp', t: 'Соберут и привезут за 30 минут', d: 'Если чего-то не окажется, магазин предложит замену — вы решаете, соглашаться или нет.' },
  { img: 'img/intro-wallet.webp', t: 'Платите спокойно', d: 'Деньги заморозятся и уйдут магазину, только когда вы получите заказ. Или платите курьеру наличными.' },
];
let slide = 0;
export function vIntro() {
  const s = SLIDES[slide], last = slide === SLIDES.length - 1;
  return `<div class="screen">
    <div class="row between" style="min-height:44px">${slide ? `<button class="round" data-a="introPrev" aria-label="Назад">${ico('back')}</button>` : `<div class="seg2" role="radiogroup" aria-label="Язык">${LANGS.map(([k, t]) => `<button role="radio" aria-checked="${lang === k}" data-a="lang" data-v="${k}" translate="no">${t}</button>`).join('')}</div>`}${last ? '' : '<button class="link" data-a="introDone">Пропустить</button>'}</div>
    <div class="art-big"><img src="${s.img}" alt="" width="360" height="360"></div>
    <div class="col" style="gap:10px"><h1>${s.t}</h1><p class="muted">${s.d}</p></div>
    <div class="foot"><div class="dots">${SLIDES.map((_, i) => `<i class="${i === slide ? 'on' : ''}"></i>`).join('')}</div>
      <button class="btn primary block" data-a="${last ? 'introDone' : 'introNext'}">${last ? 'Указать адрес' : 'Далее'}</button>
      ${last ? '<button class="btn block" data-a="introSkipAddr">Сначала посмотреть магазины</button>' : ''}</div></div>`;
}
export const introActions = {
  introNext: () => { slide++; },
  introPrev: () => { slide--; },
  introDone: () => { C.onboarded = true; save(); return 'address'; },
  introSkipAddr: () => { C.onboarded = true; save(); },
};
