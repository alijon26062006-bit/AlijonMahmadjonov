import { BRAND } from './config.js';
import { add, bumpSimple, totals } from './data/cart.js';
import { productIn, shopById } from './data/catalog.js';
import { view } from './data/orders.js';
import { SELLER_KEY } from './services/bridge.js';
import { C, save, ui } from './state.js';
import { $, actions, app, closeSheet, ico, on, openSheet, sheetOpen, toast } from './ui/dom.js';
import { addressActions, loginActions, openAddress, openLogin } from './views/account.js';
import { cartActions, cartDock, vCart } from './views/cart.js';
import { checkoutActions, checkoutDock, vCheckout } from './views/checkout.js';
import { vHome, vKind } from './views/home.js';
import { orderActions, vOrder, vOrders } from './views/order.js';
import { applyTheme, introActions, profileActions, vFavorites, vIntro, vProfile } from './views/profile.js';
import { refreshResults, remember, vSearch } from './views/search.js';
import { askReplace, openProduct, productActions, vShop } from './views/shop.js';

// Экраны: адрес → функция, вкладка снизу, нужна ли полоска корзины, закреплённая кнопка
const ROUTES = [
  [/^#\/?$/, () => ({ html: vHome(), tab: 'home', cartbar: true })],
  [/^#\/search$/, () => ({ html: vSearch(), tab: 'search', cartbar: true, after: () => { const i = $('#q'); i.focus(); i.setSelectionRange(i.value.length, i.value.length); } })],
  [/^#\/kind\/(\w+)$/, k => ({ html: vKind(k), tab: 'home', cartbar: true })],
  [/^#\/shop\/([\w-]+)$/, id => ({ html: vShop(id), tab: 'home', cartbar: true })],
  [/^#\/cart$/, () => ({ html: vCart(), tab: 'cart', dock: cartDock() })],
  [/^#\/checkout$/, () => ({ html: vCheckout(), flow: true, dock: checkoutDock() })],
  [/^#\/orders$/, () => ({ html: vOrders(), tab: 'orders' })],
  [/^#\/order\/([\w-]+)$/, id => ({ html: vOrder(id), tab: 'orders' })],
  [/^#\/profile$/, () => ({ html: vProfile(), tab: 'profile' })],
  [/^#\/favorites$/, () => ({ html: vFavorites(), tab: 'profile', cartbar: true })],
];
const TABS = [['home', '#/', 'Главная', 'home'], ['search', '#/search', 'Поиск', 'search'], ['cart', '#/cart', 'Корзина', 'cart'], ['orders', '#/orders', 'Заказы', 'orders'], ['profile', '#/profile', 'Профиль', 'user']];

export function render() {
  applyTheme();
  if (!C.onboarded) { app.innerHTML = vIntro(); return; }
  const h = location.hash || '#/';
  let r = null;
  for (const [re, fn] of ROUTES) { const m = h.match(re); if (m) { r = fn(m[1]); break; } }
  if (!r) { location.replace('#/'); return; }
  const T = totals(), active = C.orders.some(o => { const v = view(o); return v.stage >= 0 && v.stage < 4; });
  const bar = r.cartbar && T.rows.length ? `<button class="cartbar" data-go="#/cart">${ico('cart')}<span class="grow" style="text-align:left">Корзина<small>${T.shop.name}</small></span><span class="num">${T.total.toLocaleString('ru-RU')} смн</span></button>` : '';
  const dock = r.dock || bar;
  app.innerHTML = `<main class="page ${r.flow ? 'flow' : dock ? 'has-bar' : ''}" id="main">${r.html}</main>
    ${dock ? `<div class="dock ${r.flow ? '' : 'over-tabs'}">${dock}</div>` : ''}
    ${r.flow ? '' : `<nav class="tabs" aria-label="Разделы"><div class="tabs-in">${TABS.map(([k, to, t, i]) => `<button class="tab" data-go="${to}" ${r.tab === k ? 'aria-current="page"' : ''}>${ico(i)}<span>${t}</span>${k === 'cart' && T.rows.length ? `<span class="badge">${T.rows.length}</span>` : k === 'orders' && active ? '<span class="badge">•</span>' : ''}</button>`).join('')}</div></nav>`}`;
  r.after?.();
}
let depth = 0;   // сколько шагов сделали внутри приложения — «назад» не уводит с сайта
export function go(to) { if (location.hash === to) render(); else { depth++; location.hash = to; } }
let lastHash = location.hash;
window.addEventListener('hashchange', () => { closeSheet(); const deeper = location.hash.length > lastHash.length; lastHash = location.hash; render(); if (deeper || !location.hash.startsWith('#/shop')) window.scrollTo(0, 0); });

// ----- действия -----
Object.entries({ ...productActions, ...cartActions, ...checkoutActions, ...orderActions, ...profileActions, ...introActions, ...addressActions, ...loginActions }).forEach(([k, fn]) => on(k, fn));
on('closeSheet', () => { closeSheet(); return false; });
on('back', el => { if (depth > 0) { depth--; history.back(); } else location.replace(el.dataset.to || '#/'); return false; });
on('address', () => { openAddress(render); return false; });
on('login', () => { openLogin(render); return false; });
on('filter', el => { ui.filter = el.dataset.v; });
on('jump', el => { $('#' + el.dataset.to)?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); return false; });
on('product', el => { openProduct(el.dataset.shop, el.dataset.pid); return false; });
on('plus', el => {
  const s = shopById(el.dataset.shop), p = productIn(s, el.dataset.pid);
  if (bumpSimple(s, p, 1) === 'other') { askReplace(() => { add(s, p, {}, true); render(); }); return false; }
});
on('minus', el => { const s = shopById(el.dataset.shop); bumpSimple(s, productIn(s, el.dataset.pid), -1); });
on('ifMissing', el => { C.cart.ifMissing = el.value; save(); return false; });
on('cutlery', el => { C.cart.cutlery = el.checked; save(); return false; });
on('cartComment', el => { C.cart.comment = el.value; save(); return false; });
on('searchFor', el => { ui.q = el.dataset.q; remember(ui.q); render(); return false; });
on('clearRecent', () => { C.recent = []; save(); refreshResults(); return false; });
on('about', () => {
  openSheet(`<h2>Как работает ${BRAND}</h2>
    <ol class="col" style="padding-left:20px;gap:10px;margin:0"><li>Вы выбираете товары в магазинах рядом. Цены и наличие — прямо из магазина.</li><li>Магазин собирает заказ. Весовой товар взвешивают, если чего-то нет — предложат замену.</li><li>Курьер привозит заказ. Вы нажимаете «Заказ получил» — только тогда магазин получает деньги.</li></ol>
    <p class="muted small">Доставка 10 смн, бесплатно от 200 смн. Если сумма после сборки меньше — разницу вернём.</p>`, { label: 'О сервисе' });
  return false;
});
on('install', () => { install(); return false; });

let searchTimer;
on('qInput', el => { ui.q = el.value; clearTimeout(searchTimer); searchTimer = setTimeout(refreshResults, 120); return false; });

document.addEventListener('click', async e => {
  const g = e.target.closest('[data-go]');
  if (g && !g.disabled) { e.preventDefault(); return go(g.dataset.go); }
  const el = e.target.closest('[data-a]'); if (!el || el.disabled) return;
  const fn = actions[el.dataset.a]; if (!fn) return;
  const res = await fn(el, go);
  if (res === 'address') { render(); openAddress(render); return; }
  if (res !== false && !sheetOpen()) render();
});
document.addEventListener('input', e => {
  const el = e.target;
  if (el.id === 'q') return actions.qInput(el);
  const name = el.dataset.input; if (name) actions[name]?.(el, go);
});
document.addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.id === 'q') { remember(e.target.value); e.target.blur(); } });

// кабинет продавца на этом устройстве поменял заказ или товары — показываем сразу
window.addEventListener('storage', e => { if (e.key === SELLER_KEY && !sheetOpen() && !(document.activeElement?.matches('input,textarea'))) render(); });
// заказы в магазины-примеры идут по этапам сами — обновляем экран заказа
setInterval(() => { if (/^#\/(order|orders$)/.test(location.hash) && !sheetOpen()) render(); else if ((location.hash === '' || location.hash === '#/') && !sheetOpen() && C.orders.length) render(); }, 5000);

// ----- установка на телефон -----
let deferred = null;
window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); deferred = e; });
async function install() {
  if (matchMedia('(display-mode: standalone)').matches || navigator.standalone) return toast('Приложение уже установлено');
  if (deferred) { deferred.prompt(); await deferred.userChoice; deferred = null; return; }
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  openSheet(`<h2>Установить ${BRAND}</h2><ol class="col" style="padding-left:20px;gap:8px;margin:0">${(ios ? ['Откройте сайт в Safari', 'Нажмите «Поделиться» внизу экрана', 'Выберите «На экран Домой»'] : ['Откройте сайт в Chrome', 'Нажмите ⋮ в правом верхнем углу', 'Выберите «Установить приложение»']).map(s => `<li>${s}</li>`).join('')}</ol>`, { label: 'Установка' });
}
if ('serviceWorker' in navigator && (location.protocol === 'https:' || ['localhost', '127.0.0.1'].includes(location.hostname))) navigator.serviceWorker.register('sw.js').catch(() => {});

document.title = BRAND + ' — доставка из магазинов рядом';
render();
