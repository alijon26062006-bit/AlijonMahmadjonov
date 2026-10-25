import * as api from './api.js';
import { crashScreen, guardGlobal, report } from './lib/guard.js';
import { esc } from './lib/format.js';
import { ask, errorBox, ICON, loading, toast } from './ui.js';
import { checks, overview } from './views/overview.js';
import { people, person } from './views/people.js';
import { products, shop, shops } from './views/shops.js';
import { order, orders } from './views/orders.js';
import { couriers, map } from './views/couriers.js';
import { log, reviews, roles } from './views/more.js';

// Админ-панель «Зуд». Адрес экрана — в ссылке (#/orders?status=active), поэтому «Назад», обновление страницы
// и пересланная ссылка открывают тот же экран. Данные — только через функции admin_* в базе.

const root = /** @type {HTMLElement} */ (document.getElementById('app'));
const VIEWS = { '': overview, checks, people, person, shops, shop, products, orders, order, couriers, map, reviews, log, roles };
// меню: [адрес, подпись, иконка]; первые четыре и «Ещё» — нижняя панель на телефоне
/** @type {[string, string, string][]} */
const NAV = [['', 'Обзор', 'home'], ['checks', 'Проверки', 'alert'], ['orders', 'Заказы', 'orders'], ['people', 'Люди', 'people'], ['shops', 'Магазины', 'shop'],
  ['products', 'Товары', 'box'], ['couriers', 'Курьеры', 'car'], ['map', 'Карта', 'map'], ['reviews', 'Отзывы', 'star'], ['log', 'Журнал', 'log'], ['roles', 'Роли', 'roles']];
const PARENT = { person: 'people', shop: 'shops', order: 'orders' };
const LIVE_EVERY = 20000;   // экраны, где важна свежесть, обновляются сами раз в 20 секунд

let me = null, cur = { key: '', name: '', id: '', q: {} }, data = null, err = '', seq = 0, liveTimer = 0, alerts = 0, menuOpen = false;

/** Разобрать адрес: #/order/abc?x=1 → { name: 'order', id: 'abc', q: { x: '1' } }. */
function parse() {
  const h = location.hash.replace(/^#\/?/, ''), [path, qs = ''] = h.split('?'), [name = '', id = ''] = path.split('/');
  return { key: h, name: name in VIEWS ? name : '', id: decodeURIComponent(id || ''), q: Object.fromEntries(new URLSearchParams(qs)) };
}
/** Поменять параметры текущего экрана (поиск, фильтр). */
function setQuery(patch) {
  const q = { ...cur.q, ...patch };
  for (const k of Object.keys(q)) if (q[k] === '' || q[k] == null) delete q[k];
  const qs = new URLSearchParams(q).toString();
  location.hash = `#/${cur.name}${cur.id ? '/' + encodeURIComponent(cur.id) : ''}${qs ? '?' + qs : ''}`;
}

// ---------- экран входа ----------
function vLogin(msg = '') {
  return `<main class="login"><form class="login-card" id="login" novalidate>
    <div class="brand"><span class="logo" aria-hidden="true">З</span><span><b>Зуд</b><span class="muted">Админ-панель</span></span></div>
    <h1>Вход для администратора</h1>
    ${msg ? `<div class="alert bad" role="alert">${esc(msg)}</div>` : ''}
    <label class="field"><span>Почта</span><input type="email" name="email" autocomplete="username" required inputmode="email"></label>
    <label class="field"><span>Пароль</span><span class="pass"><input type="password" name="password" autocomplete="current-password" required minlength="6">
      <button type="button" class="btn sm" data-act="showpass" aria-label="Показать пароль">Показать</button></span></label>
    <button class="btn primary big" type="submit">Войти</button>
    <p class="small muted">Вход по номеру телефона здесь не работает: доступ ко всем данным — только по почте и паролю администратора.</p>
  </form></main>`;
}
function vNotAdmin() {
  return `<main class="login"><div class="login-card">
    <div class="brand"><span class="logo" aria-hidden="true">З</span><span><b>Зуд</b><span class="muted">Админ-панель</span></span></div>
    <h1>Нет доступа</h1><p>Вы вошли как <b>${esc(me?.email || '')}</b>, но эта учётная запись не админ.</p>
    <p class="small muted">Админа добавляет владелец: в Supabase → SQL Editor или в панели «Люди» → «Сделать админом».</p>
    <button class="btn" data-act="logout">${ICON.out} Выйти</button></div></main>`;
}

// ---------- каркас ----------
function navLink([k, label, icon], extra = '') {
  const active = cur.name === k || PARENT[cur.name] === k;
  const badge = k === 'checks' && alerts ? `<span class="badge num" aria-label="срочных: ${alerts}">${alerts}</span>` : '';
  return `<a class="nav-a${extra}" href="#/${k}" ${active ? 'aria-current="page"' : ''}>${ICON[icon]}<span>${label}</span>${badge}</a>`;
}
function layout(body) {
  const moreActive = NAV.slice(4).some(([k]) => cur.name === k || PARENT[cur.name] === k);
  return `<div class="shell">
    <aside class="side" aria-label="Разделы">
      <div class="brand"><span class="logo" aria-hidden="true">З</span><span><b>Зуд</b><span class="muted">Админ-панель</span></span></div>
      <nav class="side-nav">${NAV.map(n => navLink(n)).join('')}</nav>
      <div class="side-foot"><span class="small muted" title="${esc(me.email)}">${esc(me.email)}</span><button class="btn sm" data-act="logout">${ICON.out} Выйти</button></div>
    </aside>
    <main class="main" id="main" tabindex="-1">${body}</main>
    <nav class="bottom" aria-label="Разделы">${NAV.slice(0, 4).map(n => navLink(n)).join('')}
      <button class="nav-a" data-act="menu" aria-expanded="${menuOpen}" ${moreActive ? 'aria-current="page"' : ''}>${ICON.more}<span>Ещё</span></button></nav>
    ${menuOpen ? `<div class="sheet-wrap" data-act="menu"><nav class="sheet" aria-label="Все разделы">${NAV.slice(4).map(n => navLink(n, ' row')).join('')}
      <div class="sheet-foot"><span class="small muted">${esc(me.email)}</span><button class="btn sm" data-act="logout">${ICON.out} Выйти</button></div></nav></div>` : ''}
  </div>`;
}

function render() {
  try {
    if (!me) { root.innerHTML = vLogin(); return; }
    if (!me.admin) { root.innerHTML = vNotAdmin(); return; }
    const v = VIEWS[cur.name];
    const body = err && !data ? errorBox(err) : data == null ? loading() : v.html(data, cur.q, cur.id);
    const y = scrollY, a = document.activeElement;
    // поиск перерисовывается вместе с экраном — курсор остаётся там, где был
    const caret = a instanceof HTMLInputElement && a.type === 'search' ? a.selectionStart : null;
    root.innerHTML = layout(body);
    scrollTo(0, y);
    if (caret != null) { const n = /** @type {HTMLInputElement|null} */ (root.querySelector('input[type="search"]')); n?.focus(); n?.setSelectionRange(caret, caret); }
    if (data != null && v.after) v.after(data);
  } catch (e) { crashScreen(root, e); }
}

/**
 * Загрузить данные экрана.
 * full — новый экран: «Загрузка…»; soft — тихое обновление тех же данных (карта обновляет точки на месте);
 * query — поменяли поиск или фильтр: старый список виден, пока не придёт новый.
 * @param {'full'|'soft'|'query'} mode
 */
async function load(mode = 'full') {
  const my = ++seq, v = VIEWS[cur.name], soft = mode !== 'full';
  if (!soft) { data = null; err = ''; render(); }
  try {
    const d = await v.load(cur.q, cur.id);
    if (my !== seq) return;          // пока грузили, ушли на другой экран
    const first = data == null;
    data = d; err = '';
    if (mode === 'soft' && !first && v.update) v.update(d); else render();
  } catch (e) {
    if (my !== seq) return;
    report(e, 'load:' + cur.name);
    err = e.message || String(e);
    if (soft && data != null) toast(err, 'bad'); else render();
  }
  refreshBadge();
}
async function refreshBadge() {
  try {
    const list = cur.name === 'checks' && Array.isArray(data) ? data : await api.checks();
    const n = list.filter(c => c.level === 'high').length;
    if (n !== alerts) { alerts = n; document.querySelectorAll('.nav-a[href="#/checks"]').forEach(a => { a.querySelector('.badge')?.remove(); if (n) a.insertAdjacentHTML('beforeend', `<span class="badge num">${n}</span>`); }); }
  } catch { /* значок — не главное */ }
}

function onRoute() {
  const next = parse();
  if (next.key === cur.key && data != null) return;
  const sameView = next.name === cur.name && next.id === cur.id;
  VIEWS[cur.name]?.leave?.();
  cur = next; menuOpen = false;
  if (!sameView) scrollTo(0, 0);
  load(sameView && data != null ? 'query' : 'full');
  if (!sameView) document.getElementById('main')?.focus({ preventScroll: true });
  document.title = `${VIEWS[cur.name].title} · Зуд Админ`;
}

// ---------- действия ----------
const ACTS = {
  'user-block': id => run(() => ask({ title: 'Заблокировать человека?', text: 'Не сможет заказывать, работать курьером и открыть магазин. Его магазин скроется от покупателей. Снять блокировку можно в любой момент.', ok: 'Заблокировать', danger: true, field: 'Причина (увидит человек)', required: true }), r => api.blockUser(id, true, r), 'Человек заблокирован'),
  'user-unblock': id => run(() => ask({ title: 'Разблокировать?', text: 'Магазин и анкета курьера вернутся в то состояние, что было до блокировки.', ok: 'Разблокировать' }), () => api.blockUser(id, false), 'Блокировка снята'),
  'courier-block': id => run(() => ask({ title: 'Заблокировать курьера?', text: 'Не увидит новые заказы и не сможет выйти на линию. Текущий заказ проверьте отдельно.', ok: 'Заблокировать', danger: true, field: 'Причина (увидит курьер)', required: true }), r => api.blockCourier(id, true, r), 'Курьер заблокирован'),
  'courier-unblock': id => run(() => ask({ title: 'Разблокировать курьера?', ok: 'Разблокировать' }), () => api.blockCourier(id, false), 'Курьер снова может работать'),
  'shop-block': id => run(() => ask({ title: 'Заблокировать магазин?', text: 'Покупатели перестанут его видеть, новые заказы не придут. Владелец увидит причину в кабинете.', ok: 'Заблокировать', danger: true, field: 'Причина (увидит владелец)', required: true }), r => api.blockShop(id, true, r), 'Магазин заблокирован'),
  'shop-unblock': id => run(() => ask({ title: 'Разблокировать магазин?', ok: 'Разблокировать' }), () => api.blockShop(id, false), 'Магазин снова виден покупателям'),
  'product-block': id => run(() => ask({ title: 'Скрыть товар?', text: 'Покупатели перестанут его видеть. Магазин увидит причину и не сможет вернуть товар сам.', ok: 'Скрыть', danger: true, field: 'Причина (увидит магазин)', required: true }), r => api.blockProduct(id, true, r), 'Товар скрыт'),
  'product-unblock': id => run(() => ask({ title: 'Вернуть товар в продажу?', ok: 'Вернуть' }), () => api.blockProduct(id, false), 'Товар снова виден'),
  'order-cancel': id => run(() => ask({ title: 'Отменить заказ?', text: 'Покупатель, магазин и курьер увидят отмену. Если товар ещё в магазине — остатки вернутся.', ok: 'Отменить заказ', danger: true, field: 'Причина', required: true }), r => api.cancelOrder(id, r), 'Заказ отменён'),
  'order-release': id => run(() => ask({ title: 'Снять курьера с заказа?', text: 'Заказ снова появится у всех курьеров рядом. Курьер ещё не забрал товар.', ok: 'Снять курьера', field: 'Почему (для журнала)' }), r => api.releaseOrder(id, r), 'Курьер снят, заказ снова в ленте'),
  'order-delivered': id => run(() => ask({ title: 'Закрыть как полученный?', text: 'Только если вы точно знаете, что покупатель получил заказ (позвонили ему).', ok: 'Закрыть заказ', field: 'Кто подтвердил получение', required: true }), r => api.deliveredOrder(id, r), 'Заказ закрыт'),
  'order-resolve': id => run(() => ask({ title: 'Проблема решена?', ok: 'Отметить решённой', field: 'Что сделали', required: true }), r => api.resolveOrder(id, r), 'Проблема отмечена решённой'),
  'review-hide': id => run(() => ask({ title: 'Скрыть отзыв?', text: 'Покупатели перестанут его видеть, рейтинг магазина пересчитается.', ok: 'Скрыть', danger: true, field: 'Почему (увидит магазин)' }), r => api.decideReview(id, true, r), 'Отзыв скрыт'),
  'review-keep': id => run(() => ask({ title: 'Оставить отзыв?', text: 'Жалоба магазина будет отклонена, отзыв останется виден.', ok: 'Оставить', field: 'Почему (увидит магазин)' }), r => api.decideReview(id, false, r), 'Жалоба отклонена'),
  'review-show': id => run(() => ask({ title: 'Вернуть отзыв?', ok: 'Вернуть' }), () => api.decideReview(id, false, 'Отзыв возвращён'), 'Отзыв снова виден'),
  'admin-add': id => run(() => ask({ title: 'Сделать админом?', text: 'Этот человек увидит всё и сможет блокировать и отменять. Давайте права только тому, кому доверяете.', ok: 'Дать права', field: 'Кто это (для журнала)', required: true }), r => api.setAdmin(id, true, r), 'Права админа выданы'),
  'admin-remove': id => run(() => ask({ title: 'Забрать права админа?', ok: 'Забрать', danger: true, field: 'Почему (для журнала)' }), r => api.setAdmin(id, false, r), 'Права админа забраны'),
};
let busy = false;
/** Спросить → выполнить → подсказка → обновить экран. Кнопки не срабатывают дважды. */
async function run(question, action, done) {
  if (busy) return;
  const answer = await question();
  if (answer == null) return;
  busy = true; document.body.classList.add('busy');
  try { await action(answer); toast(done, 'ok'); await load('query'); }
  catch (e) { report(e, 'action'); toast(e.message || String(e), 'bad'); }
  finally { busy = false; document.body.classList.remove('busy'); }
}

root.addEventListener('click', async e => {
  const t = /** @type {HTMLElement} */ (e.target).closest('[data-act],[data-filter]');
  if (!t) return;
  const ds = /** @type {HTMLElement} */ (t).dataset;
  if (ds.filter) { setQuery({ [ds.filter]: ds.value }); return; }
  if (t.classList.contains('sheet-wrap') && e.target !== t) return;   // нажали внутри меню — это ссылка
  switch (ds.act) {
    case 'menu': menuOpen = !menuOpen; render(); return;
    case 'reload': load('full'); return;
    case 'logout': await api.signOut(); me = null; data = null; render(); return;
    case 'showpass': { const i = /** @type {HTMLInputElement} */ (root.querySelector('[name="password"]')); i.type = i.type === 'password' ? 'text' : 'password'; t.textContent = i.type === 'password' ? 'Показать' : 'Скрыть'; return; }
    default: ACTS[ds.act]?.(ds.id);
  }
});
root.addEventListener('submit', async e => {
  const f = /** @type {HTMLFormElement} */ (e.target);
  e.preventDefault();
  if (f.id === 'login') {
    const fd = new FormData(f), btn = /** @type {HTMLButtonElement} */ (f.querySelector('[type="submit"]'));
    const email = String(fd.get('email') || ''), pass = String(fd.get('password') || '');
    if (!/^\S+@\S+\.\S+$/.test(email) || pass.length < 6) { root.innerHTML = vLogin('Введите почту и пароль (не короче 6 знаков)'); return; }
    btn.disabled = true; btn.textContent = 'Входим…';
    try { me = await api.signIn(email, pass); cur = { key: '\0', name: '', id: '', q: {} }; if (me?.admin) { onRoute(); tick(); } else render(); }
    catch (er) { root.innerHTML = vLogin(er.message || String(er)); }
    return;
  }
  if (f.hasAttribute('data-search')) {
    const fd = new FormData(f), patch = {};
    for (const [k, v] of fd.entries()) patch[k] = String(v).trim();
    setQuery(patch);
  }
});
// поиск по мере ввода — с паузой, чтобы не спрашивать базу на каждую букву
let typing = 0;
root.addEventListener('input', e => {
  const i = /** @type {HTMLInputElement} */ (e.target);
  if (i.type !== 'search') return;
  clearTimeout(typing);
  typing = setTimeout(() => setQuery({ q: i.value.trim() }), 450);
});
root.addEventListener('change', e => { const i = /** @type {HTMLInputElement} */ (e.target); if (i.type === 'date') setQuery({ [i.name]: i.value }); });

// ---------- запуск ----------
guardGlobal(text => toast(text, 'bad'));
addEventListener('hashchange', () => { if (me?.admin) onRoute(); });
document.addEventListener('visibilitychange', () => { if (!document.hidden && me?.admin && data != null) load('soft'); });
function tick() {
  clearTimeout(liveTimer);
  liveTimer = setTimeout(() => {
    if (me?.admin && !document.hidden && !busy && data != null && !document.querySelector('.modal-wrap')
        && (['', 'checks', 'orders', 'order', 'couriers', 'map'].includes(cur.name))) load('soft');
    tick();
  }, LIVE_EVERY);
}

(async () => {
  root.innerHTML = loading();
  try { me = await api.whoami(); }
  catch (e) { report(e, 'whoami'); me = null; root.innerHTML = vLogin(e.message || String(e)); return; }
  if (me?.admin) { cur = { key: '\0', name: '', id: '', q: {} }; onRoute(); tick(); } else render();
})();
