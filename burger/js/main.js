/* The Burger — меню, корзина, оформление заказа.
   Заказ уходит текстом в Telegram: сервер не нужен, ничего не теряется. */

/* Адрес бэкенда. Пусто — сайт работает сам по себе на встроенном меню
   и отправляет заказ текстом в Telegram. Заполнено — меню приходит с сервера,
   заведение правит его в админке, а заказ уходит прямо в базу. */
const API = '';

const TG_CHAT = 'theburgertj';
const PHONE_MAIN = '+992939171997';
const FIRST_ORDER_NO = 124;

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const som = n => `${n.toLocaleString('ru-RU').replace(/,/g, ' ')} сомони`;
const dish = id => MENU.find(d => d.id === id);
const photoUrl = d => (API && d.photo) ? `${API}/uploads/${d.photo}` : `assets/dishes/${d.id}.jpg`;
const slow = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

const plural = (n, one, few, many) => {
  const t = n % 100, u = n % 10;
  if (t > 10 && t < 20) return many;
  if (u === 1) return one;
  if (u >= 2 && u <= 4) return few;
  return many;
};

/* ── состояние ──────────────────────────────────────── */

/* Позиция корзины — блюдо плюс выбранные изменения:
   { id, qty, add: [id добавки], remove: [название] } */
let cart = load();
let mode = localStorage.getItem('tb_mode') || 'delivery';
let zone = localStorage.getItem('tb_zone') || ZONES[0].id;

function load() {
  const raw = JSON.parse(localStorage.getItem('tb_cart') || '{}');
  const out = {};

  for (const [key, val] of Object.entries(raw)) {
    // старый формат корзины хранил просто количество — переносим его
    if (typeof val === 'number') {
      if (dish(key)) out[lineKey(key, [], [])] = { id: key, qty: val, add: [], remove: [] };
    } else if (val && dish(val.id)) {
      out[key] = { id: val.id, qty: val.qty, add: val.add || [], remove: val.remove || [] };
    }
  }
  return out;
}

function save() {
  localStorage.setItem('tb_cart', JSON.stringify(cart));
  localStorage.setItem('tb_mode', mode);
  localStorage.setItem('tb_zone', zone);
}

const lineKey = (id, add, remove) =>
  `${id}|${[...add].sort().join('+')}|${[...remove].sort().join('+')}`;

const linePrice = line =>
  dish(line.id).price + line.add.reduce((s, a) => s + (ADDON(a)?.price || 0), 0);

const goods = () => Object.values(cart).reduce((s, l) => s + linePrice(l) * l.qty, 0);
const positions = () => Object.values(cart).reduce((s, l) => s + l.qty, 0);
const dishQty = id => Object.values(cart).filter(l => l.id === id).reduce((s, l) => s + l.qty, 0);

const currentZone = () => ZONES.find(z => z.id === zone) || ZONES[0];

/* Доставка: цена по району. По городу бесплатно от 100 сомони,
   за городом — по договорённости, поэтому в сумму не попадает. */
function deliveryCost() {
  if (mode === 'pickup' || !positions()) return 0;
  const z = currentZone();
  if (z.price === null) return 0;
  return goods() >= DELIVERY.freeFrom ? 0 : z.price;
}
const total = () => goods() + deliveryCost();

/* ── корзина: изменения ─────────────────────────────── */

function addLine(id, add = [], remove = [], qty = 1) {
  const key = lineKey(id, add, remove);
  if (cart[key]) cart[key].qty += qty;
  else cart[key] = { id, qty, add: [...add], remove: [...remove] };
  save();
  paint();
}

function setLineQty(key, qty) {
  if (!cart[key]) return;
  if (qty <= 0) delete cart[key];
  else cart[key].qty = qty;
  save();
  paint();
}

/* Счётчик на карточке меняет позицию без изменений.
   Если такой нет, а количество уменьшают — трогаем последнюю позицию блюда. */
function bumpDish(id, delta) {
  const plain = lineKey(id, [], []);
  if (cart[plain] || delta > 0) {
    setLineQty(plain, (cart[plain]?.qty || 0) + delta);
    return;
  }
  const keys = Object.keys(cart).filter(k => cart[k].id === id);
  if (keys.length) setLineQty(keys[keys.length - 1], cart[keys[keys.length - 1]].qty - 1);
}

/* ── меню ───────────────────────────────────────────── */

const camera = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3 7.2 5H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-3.2L15 3H9Zm3 5.5a5.5 5.5 0 1 1 0 11 5.5 5.5 0 0 1 0-11Zm0 2a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z"/></svg>`;

/* Фото может не быть — тогда остаётся аккуратное место под него. */
function watchPhoto(img) {
  const fail = () => {
    const box = img.parentElement;
    img.remove();
    box.classList.add('shot--empty');
    box.insertAdjacentHTML('beforeend', camera);
  };
  if (img.complete && !img.naturalWidth) fail();
  else img.addEventListener('error', fail, { once: true });
}

const badge = tag => tag && TAGS[tag]
  ? `<span class="badge badge--${tag}">${TAGS[tag].label}</span>` : '';

const pickControl = id => `
  <div class="pick" data-pick="${id}">
    <button class="add" type="button" data-add="${id}">Добавить <span aria-hidden="true">+</span></button>
    <div class="stepper">
      <button type="button" data-bump="-1" data-id="${id}" aria-label="Убрать одну порцию">−</button>
      <span data-count="${id}">1</span>
      <button type="button" data-bump="1" data-id="${id}" aria-label="Добавить ещё порцию">+</button>
    </div>
  </div>`;

const priceHtml = d => `<span class="price">${som(d.price)}${d.oldPrice ? `<s>${som(d.oldPrice)}</s>` : ''}</span>`;

function dishCard(d) {
  return `
  <article class="dish" data-open="${d.id}">
    <div class="shot">
      <img src="${photoUrl(d)}" alt="${d.name}" width="1216" height="760" loading="lazy">
      <div class="badges">${badge(d.tag)}</div>
    </div>
    <div class="dish__body">
      <h4 class="dish__name">${d.name}</h4>
      ${d.about ? `<p class="dish__about">${d.about}</p>` : ''}
      ${d.weight ? `<span class="dish__weight">${d.weight} г</span>` : ''}
      <div class="dish__foot">
        ${priceHtml(d)}
        ${pickControl(d.id)}
      </div>
    </div>
  </article>`;
}

function rowCard(d) {
  return `
  <article class="row-item" data-open="${d.id}">
    <div class="row-item__name">
      <b>${d.name} ${badge(d.tag)}</b>
      ${d.about ? `<small>${d.about}</small>` : ''}
    </div>
    ${priceHtml(d)}
    <div class="pick" data-pick="${d.id}">
      <button class="add add--icon" type="button" data-add="${d.id}" aria-label="Добавить ${d.name}">+</button>
      <div class="stepper">
        <button type="button" data-bump="-1" data-id="${d.id}" aria-label="Убрать одну">−</button>
        <span data-count="${d.id}">1</span>
        <button type="button" data-bump="1" data-id="${d.id}" aria-label="Добавить ещё">+</button>
      </div>
    </div>
  </article>`;
}

function renderMenu() {
  $('#tabs-row').innerHTML = SECTIONS
    .map(s => `<a href="#sec-${s.id}" data-tab="${s.id}">${s.title}</a>`).join('');

  $('#menu-body').innerHTML = SECTIONS.map(s => {
    const items = MENU.filter(d => d.section === s.id);
    const big = (s.layout || 'cards') === 'cards';
    return `
    <section class="sec" id="sec-${s.id}" aria-labelledby="h-${s.id}">
      <div class="sec__head">
        <h3 id="h-${s.id}">${s.title}</h3>
        ${s.note ? `<span>${s.note}</span>` : ''}
      </div>
      <div class="${big ? 'dishes' : 'rows-menu'}">
        ${items.map(big ? dishCard : rowCard).join('')}
      </div>
    </section>`;
  }).join('');

  $$('.shot img').forEach(watchPhoto);
}

/* ── карточка блюда ─────────────────────────────────── */

let sheetDish = null;   // { id, qty, add, remove }

function openDish(id) {
  const d = dish(id);
  if (!d) return;
  sheetDish = { id, qty: 1, add: [], remove: [] };

  const mods = MODIFIERS[d.section];
  const facts = [
    d.weight && `<div><dt>${d.weight} г</dt><dd>вес</dd></div>`,
    d.kcal && `<div><dt>${d.kcal}</dt><dd>ккал</dd></div>`,
    d.cook && `<div><dt>${d.cook}</dt><dd>готовим</dd></div>`
  ].filter(Boolean).join('');

  $('#dish-body').innerHTML = `
    <div class="ds-shot shot">
      <img src="${photoUrl(d)}" alt="${d.name}" width="1216" height="760">
    </div>
    <h2 class="ds-name" id="dish-name">${d.name}</h2>
    ${d.about ? `<p class="ds-about">${d.about}</p>` : ''}
    <dl class="ds-facts">${facts}</dl>

    ${d.parts?.length ? `
      <h3 class="ds-title">Состав</h3>
      <ul class="ds-parts">${d.parts.map(p => `<li>${p}</li>`).join('')}</ul>` : ''}

    ${mods?.remove?.length ? `
      <h3 class="ds-title">Убрать</h3>
      <div class="opts">${mods.remove.map(name => `
        <label class="opt">
          <input type="checkbox" data-remove="${name}">
          <span>${name}</span>
        </label>`).join('')}</div>` : ''}

    ${mods?.add?.length ? `
      <h3 class="ds-title">Добавить</h3>
      <div class="opts">${mods.add.map(a => `
        <label class="opt">
          <input type="checkbox" data-addon="${a.id}">
          <span>${a.name}</span>
          <b>+${som(a.price)}</b>
        </label>`).join('')}</div>` : ''}
  `;

  $('#dish-foot').innerHTML = `
    <div class="ds-qty">
      <span>Количество</span>
      <div class="stepper">
        <button type="button" id="ds-minus" aria-label="Меньше">−</button>
        <span id="ds-qty">1</span>
        <button type="button" id="ds-plus" aria-label="Больше">+</button>
      </div>
    </div>
    <button class="btn btn--accent btn--full" id="ds-add" type="button"></button>`;

  watchPhoto($('#dish-body img'));
  paintDishSheet();
  openSheet('#dish-sheet');
}

function dishSheetPrice() {
  const d = dish(sheetDish.id);
  const extra = sheetDish.add.reduce((s, a) => s + (ADDON(a)?.price || 0), 0);
  return (d.price + extra) * sheetDish.qty;
}

function paintDishSheet() {
  $('#ds-qty').textContent = sheetDish.qty;
  $('#ds-add').textContent = `Добавить в корзину · ${som(dishSheetPrice())}`;
}

document.addEventListener('change', e => {
  if (!sheetDish || !e.target.matches('[data-addon], [data-remove]')) return;

  const { addon, remove } = e.target.dataset;
  const list = addon ? sheetDish.add : sheetDish.remove;
  const val = addon || remove;
  const at = list.indexOf(val);

  if (e.target.checked && at === -1) list.push(val);
  if (!e.target.checked && at > -1) list.splice(at, 1);

  paintDishSheet();
});

/* ── корзина: экран ─────────────────────────────────── */

function lineTitle(line) {
  const bits = [
    ...line.add.map(a => `+ ${ADDON(a)?.name || a}`),
    ...line.remove.map(r => `без ${REMOVE_GEN[r] || r.toLowerCase()}`)
  ];
  return bits.join(', ');
}

function renderCart() {
  const keys = Object.keys(cart);
  const shown = $$('#cart-lines .cart-line').map(el => el.dataset.key);
  const sameSet = keys.length > 0 && shown.length === keys.length && shown.every((k, i) => k === keys[i]);

  // Меняется только количество — правим цифры на месте.
  // Полная перерисовка сбрасывала прокрутку списка наверх.
  if (sameSet) {
    keys.forEach(key => {
      const el = $(`.cart-line[data-key="${key}"]`);
      $('.stepper span', el).textContent = cart[key].qty;
      $('.cart-line__price', el).textContent = `${som(linePrice(cart[key]))} × ${cart[key].qty}`;
    });
    paintCartFoot();
    return;
  }

  $('#cart-lines').innerHTML = keys.length ? keys.map(key => {
    const line = cart[key];
    const d = dish(line.id);
    const opts = lineTitle(line);
    return `
    <div class="cart-line" data-key="${key}">
      <div class="cart-line__shot shot">
        <img src="${photoUrl(d)}" alt="" width="128" height="128" loading="lazy">
      </div>
      <div class="cart-line__name">
        <b>${d.name}</b>
        ${opts ? `<span class="cart-line__opts">${opts}</span>` : ''}
        <span class="cart-line__price">${som(linePrice(line))} × ${line.qty}</span>
      </div>
      <div class="cart-line__side">
        <div class="stepper">
          <button type="button" data-line="${key}" data-delta="-1" aria-label="Меньше">−</button>
          <span>${line.qty}</span>
          <button type="button" data-line="${key}" data-delta="1" aria-label="Больше">+</button>
        </div>
        <button class="cart-line__del" type="button" data-drop="${key}">Удалить</button>
      </div>
    </div>`;
  }).join('') : `
    <div class="empty">
      <b>Корзина пуста</b>
      <span>Начните с бургера — остальное соберётся само.</span>
    </div>`;

  $$('#cart-lines img').forEach(watchPhoto);
  paintCartFoot();
}

function paintCartFoot() {
  const keys = Object.keys(cart);
  const short = DELIVERY.minOrder - goods();
  const needMore = mode === 'delivery' && positions() > 0 && short > 0;

  $('#cart-sums').innerHTML = sumsHtml();
  $('#cart-hint').textContent = needMore
    ? `Минимальный заказ на доставку — ${som(DELIVERY.minOrder)}. Добавьте ещё на ${som(short)}.`
    : (mode === 'delivery' && deliveryCost() > 0
        ? `До бесплатной доставки — ${som(DELIVERY.freeFrom - goods())}.`
        : '');
  $('#cart-hint').hidden = !$('#cart-hint').textContent;
  $('#cart-foot').hidden = !keys.length;
  $('#to-checkout').disabled = !keys.length;
}

function sumsHtml() {
  const z = currentZone();
  const cost = deliveryCost();

  const delivery = mode === 'pickup'
    ? 'самовывоз'
    : z.price === null ? 'по договорённости' : (cost ? som(cost) : 'бесплатно');

  return `
    <div><dt>Товары</dt><dd>${som(goods())}</dd></div>
    <div><dt>Доставка</dt><dd>${delivery}</dd></div>
    <div class="total"><dt>Итого</dt><dd>${som(total())}</dd></div>`;
}

/* ── общая перерисовка ──────────────────────────────── */

function paint() {
  const count = positions();

  $$('.pick').forEach(box => {
    const qty = dishQty(box.dataset.pick);
    box.classList.toggle('is-on', qty > 0);
    if (qty > 0) $(`[data-count="${box.dataset.pick}"]`, box).textContent = qty;
  });

  $('#cart-count').textContent = count;
  $('#cart-count').hidden = !count;
  $('#cartbar-count').textContent = `${count} ${plural(count, 'товар', 'товара', 'товаров')}`;
  $('#cartbar-sum').textContent = som(total());

  const bar = $('#cartbar');
  if (count) {
    bar.hidden = false;
    requestAnimationFrame(() => bar.classList.add('is-up'));
  } else {
    bar.classList.remove('is-up');
    setTimeout(() => { if (!bar.classList.contains('is-up')) bar.hidden = true; }, 260);
  }

  renderCart();
  if (!$('#checkout-sheet').hidden) paintCheckout();
}

/* ── шторки и окна ──────────────────────────────────── */

const SHEETS = ['#cart-sheet', '#dish-sheet', '#checkout-sheet', '#done-sheet'];
let lastFocus = null;

function openSheet(sel) {
  const el = $(sel);
  lastFocus = document.activeElement;
  SHEETS.filter(s => s !== sel).forEach(hideSheet);

  el.hidden = false;
  requestAnimationFrame(() => el.classList.add('is-open'));
  document.body.classList.add('is-locked');

  const first = $('.btn, button, input, select, [href]', el);
  setTimeout(() => first?.focus({ preventScroll: true }), 120);
}

function hideSheet(sel) {
  const el = $(sel);
  if (el.hidden) return;
  el.classList.remove('is-open');
  if (slow()) el.hidden = true;
  else setTimeout(() => { if (!el.classList.contains('is-open')) el.hidden = true; }, 280);
}

function closeSheets() {
  const wasOpen = SHEETS.some(s => !$(s).hidden);
  SHEETS.forEach(hideSheet);
  document.body.classList.remove('is-locked');
  if (wasOpen) lastFocus?.focus?.({ preventScroll: true });
}

document.addEventListener('keydown', e => {
  const open = SHEETS.map(sel => $(sel)).find(el => !el.hidden);
  if (!open) return;

  if (e.key === 'Escape') { closeSheets(); return; }

  // фокус не должен уходить из открытого окна
  if (e.key !== 'Tab') return;
  const items = $$('button, [href], input, select, textarea', open).filter(el => el.offsetParent !== null);
  if (!items.length) return;

  const first = items[0], last = items[items.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
});

/* смахивание шторки вниз на телефоне */
SHEETS.forEach(sel => {
  const box = $(`${sel} .sheet__box`);
  let start = 0, shift = 0, live = false;

  box.addEventListener('touchstart', e => {
    const scroll = $('.sheet__scroll', box);
    if (scroll && scroll.scrollTop > 0) return;
    live = true; start = e.touches[0].clientY;
    box.style.transition = 'none';
  }, { passive: true });

  box.addEventListener('touchmove', e => {
    if (!live) return;
    const delta = e.touches[0].clientY - start;
    if (delta < 0) { live = false; box.style.transition = ''; box.style.transform = ''; return; }
    shift = delta;
    box.style.transform = `translateY(${shift}px)`;
  }, { passive: true });

  box.addEventListener('touchend', () => {
    if (!live) return;
    live = false;
    box.style.transition = '';
    box.style.transform = '';
    if (shift > 110) closeSheets();
    shift = 0;
  });
});

/* ── оформление заказа ──────────────────────────────── */

function setMode(next) {
  mode = next;
  $$('.switch button').forEach(b => b.setAttribute('aria-checked', String(b.dataset.mode === mode)));
  $$('.only-delivery').forEach(el => { el.hidden = mode !== 'delivery'; });
  save();
  paint();
}

function paintCheckout() {
  const short = DELIVERY.minOrder - goods();
  const needMore = mode === 'delivery' && short > 0;

  $('#checkout-sums').innerHTML = sumsHtml();
  $('#checkout-hint').textContent = needMore
    ? `Доставка — от ${som(DELIVERY.minOrder)}. Добавьте ещё на ${som(short)} или выберите самовывоз.`
    : '';
  $('#checkout-hint').hidden = !needMore;
  $('#submit-order').textContent = `Подтвердить заказ · ${som(total())}`;
}

function orderText(f, no) {
  const rows = Object.values(cart).map(l => {
    const opts = lineTitle(l);
    return `• ${dish(l.id).name}${opts ? ` (${opts})` : ''} × ${l.qty} — ${som(linePrice(l) * l.qty)}`;
  });

  const lines = [`Заказ №${no} с сайта The Burger`, '', ...rows, '', `Товары: ${som(goods())}`];

  if (mode === 'delivery') {
    const z = currentZone();
    lines.push(`Доставка: ${z.name} — ${z.price === null ? 'по договорённости' : (deliveryCost() ? som(deliveryCost()) : 'бесплатно')}`);
    lines.push(`Адрес: ${f.address.value.trim()}${f.flat.value.trim() ? `, ${f.flat.value.trim()}` : ''}`);
    if (f.landmark.value.trim()) lines.push(`Ориентир: ${f.landmark.value.trim()}`);
  } else {
    lines.push(`Самовывоз: ${DELIVERY.pickup}`);
  }

  lines.push(`Итого: ${som(total())}`, '', `Имя: ${f.name.value.trim()}`, `Телефон: ${f.phone.value.trim()}`);
  if (f.note.value.trim()) lines.push(`Комментарий: ${f.note.value.trim()}`);

  return lines.join('\n');
}

function nextOrderNo() {
  const no = Number(localStorage.getItem('tb_order_no') || FIRST_ORDER_NO);
  localStorage.setItem('tb_order_no', String(no + 1));
  return no;
}

$('#order-form').addEventListener('submit', e => {
  e.preventDefault();
  const f = e.target.elements;
  const err = $('#form-err');

  const fail = (msg, field) => {
    err.textContent = msg;
    err.hidden = false;
    field?.setAttribute('aria-invalid', 'true');
    field?.focus();
  };

  $$('#order-form input').forEach(i => i.removeAttribute('aria-invalid'));

  if (!f.name.value.trim()) return fail('Напишите, как вас зовут.', f.name);
  if (f.phone.value.replace(/\D/g, '').length < 9) return fail('Проверьте номер — по нему подтверждаем заказ.', f.phone);
  if (mode === 'delivery' && goods() < DELIVERY.minOrder)
    return fail(`Доставка — от ${som(DELIVERY.minOrder)}. Добавьте ещё на ${som(DELIVERY.minOrder - goods())} или выберите самовывоз.`);
  if (mode === 'delivery' && !f.address.value.trim()) return fail('Укажите улицу и дом, иначе курьер не доедет.', f.address);

  err.hidden = true;
  finish(f, err);
});

async function finish(f, err) {
  const btn = $('#submit-order');
  btn.disabled = true;

  try {
    if (API) {
      const done = await sendOrder(f);
      $('#done-number').textContent = `№${done.number}`;
      $('#done-text').textContent = mode === 'delivery'
        ? `Мы получили заказ и скоро позвоним. Доставим за ${done.time || DELIVERY.time}.`
        : `Мы получили заказ и скоро позвоним. Заберёте на ${DELIVERY.pickup}.`;
    } else {
      // без сервера: собираем текст и отдаём его в Telegram
      const no = nextOrderNo();
      const text = orderText(f, no);
      navigator.clipboard?.writeText(text).catch(() => {});
      window.open(`https://t.me/${TG_CHAT}?text=${encodeURIComponent(text)}`, '_blank', 'noopener');

      $('#done-number').textContent = `№${no}`;
      $('#done-text').textContent = mode === 'delivery'
        ? `Отправьте сообщение в Telegram — мы подтвердим заказ и привезём за ${DELIVERY.time}.`
        : `Отправьте сообщение в Telegram — заказ будет готов через 15 минут на ${DELIVERY.pickup}.`;
    }

    cart = {};
    save();
    paint();
    openSheet('#done-sheet');
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  } finally {
    btn.disabled = false;
  }
}

/* телефон в местном формате: +992 XX XXX XX XX */
$('#order-form').elements.phone.addEventListener('input', e => {
  let d = e.target.value.replace(/\D/g, '');
  if (d.startsWith('992')) d = d.slice(3);
  d = d.slice(0, 9);

  const parts = [d.slice(0, 2), d.slice(2, 5), d.slice(5, 7), d.slice(7, 9)].filter(Boolean);
  e.target.value = d ? `+992 ${parts.join(' ')}` : '';
});

/* ── связь с сервером ───────────────────────────────── */

/* Меню с сервера. Не получилось — работаем на встроенном:
   лучше показать вчерашние цены, чем пустую страницу. */
async function loadMenu() {
  if (!API) return false;

  try {
    const res = await fetch(`${API}/api/menu`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`сервер ответил ${res.status}`);
    const d = await res.json();
    if (!d.dishes?.length) throw new Error('сервер прислал пустое меню');

    SECTIONS = d.sections;
    MENU = d.dishes;
    ZONES = d.zones;
    DELIVERY = { ...DELIVERY, ...d.delivery };

    MODIFIERS = {};
    (d.addons || []).forEach(a => {
      MODIFIERS[a.section] ??= { remove: [], add: [] };
      MODIFIERS[a.section].add.push({ id: a.id, name: a.name, price: a.price });
    });
    REMOVE_GEN = {};
    (d.removals || []).forEach(r => {
      MODIFIERS[r.section] ??= { remove: [], add: [] };
      MODIFIERS[r.section].remove.push(r.name);
      REMOVE_GEN[r.name] = r.gen || r.name.toLowerCase();
    });

    return true;
  } catch (e) {
    console.warn('Меню с сервера не загрузилось, показываем встроенное:', e.message);
    return false;
  }
}

/* Заказ на сервер. Сервер сам пересчитывает цены и присылает номер. */
async function sendOrder(f) {
  const items = Object.values(cart).map(l => ({
    id: l.id, qty: l.qty, add: l.add,
    remove: l.remove.map(r => REMOVE_GEN[r] || r.toLowerCase()),
  }));

  const res = await fetch(`${API}/api/orders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      items, mode, zone,
      name: f.name.value.trim(), phone: f.phone.value.trim(),
      address: f.address.value.trim(), flat: f.flat.value.trim(),
      landmark: f.landmark.value.trim(), note: f.note.value.trim(),
    }),
  });

  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || 'Заказ не прошёл. Позвоните нам, пожалуйста.');
  return body;
}

/* ── вкладки разделов ───────────────────────────────── */

function watchTabs() {
  const tabs = $$('#tabs-row a');
  const row = $('#tabs-row');

  tabs.forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    $(`#sec-${a.dataset.tab}`).scrollIntoView({ behavior: slow() ? 'auto' : 'smooth', block: 'start' });
  }));

  if (!('IntersectionObserver' in window)) return;

  const io = new IntersectionObserver(entries => {
    const shown = entries.filter(en => en.isIntersecting)
      .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
    if (!shown) return;

    const id = shown.target.id.replace('sec-', '');
    tabs.forEach(a => a.classList.toggle('is-on', a.dataset.tab === id));

    // активная вкладка всегда должна быть видна целиком
    const on = tabs.find(a => a.dataset.tab === id);
    if (on && row.scrollWidth > row.clientWidth) {
      const to = on.offsetLeft - (row.clientWidth - on.offsetWidth) / 2;
      row.scrollTo({ left: Math.max(0, to), behavior: slow() ? 'auto' : 'smooth' });
    }
  }, { rootMargin: '-45% 0px -50% 0px' });

  $$('.sec').forEach(s => io.observe(s));
  tabs[0]?.classList.add('is-on');
}

/* ── мелочи ─────────────────────────────────────────── */

let snackTimer;
function snack(text) {
  const box = $('#snack');
  box.textContent = text;
  box.hidden = false;
  clearTimeout(snackTimer);
  snackTimer = setTimeout(() => { box.hidden = true; }, 2200);
}

document.addEventListener('click', e => {
  const t = e.target;

  if (t.closest('[data-shut]')) { closeSheets(); return; }

  const add = t.closest('[data-add]');
  if (add) {
    addLine(add.dataset.add);
    if ($('#dish-sheet').hidden) snack(`${dish(add.dataset.add).name} — в корзине`);
    return;
  }

  const bump = t.closest('[data-bump]');
  if (bump) { bumpDish(bump.dataset.id, Number(bump.dataset.bump)); return; }

  const line = t.closest('[data-line]');
  if (line) { setLineQty(line.dataset.line, cart[line.dataset.line].qty + Number(line.dataset.delta)); return; }

  const drop = t.closest('[data-drop]');
  if (drop) { setLineQty(drop.dataset.drop, 0); return; }

  if (t.closest('#ds-minus')) { sheetDish.qty = Math.max(1, sheetDish.qty - 1); paintDishSheet(); return; }
  if (t.closest('#ds-plus'))  { sheetDish.qty += 1; paintDishSheet(); return; }

  if (t.closest('#ds-add')) {
    addLine(sheetDish.id, sheetDish.add, sheetDish.remove, sheetDish.qty);
    closeSheets();
    snack(`${dish(sheetDish.id).name} — в корзине`);
    return;
  }

  const openCart = t.closest('#cartbar, #cart-open');
  if (openCart) { openSheet('#cart-sheet'); return; }

  if (t.closest('#to-checkout')) { paintCheckout(); openSheet('#checkout-sheet'); return; }

  const modeBtn = t.closest('.switch button');
  if (modeBtn) { setMode(modeBtn.dataset.mode); paintCheckout(); return; }

  // карточка блюда открывается по нажатию, но не по кнопкам внутри
  const card = t.closest('[data-open]');
  if (card && !t.closest('.pick')) openDish(card.dataset.open);
});

$('#nav-toggle').addEventListener('click', () => {
  const panel = $('#nav-panel');
  const open = panel.hidden;
  panel.hidden = !open;
  $('#nav-toggle').setAttribute('aria-expanded', String(open));
});
$$('#nav-panel a').forEach(a => a.addEventListener('click', () => {
  $('#nav-panel').hidden = true;
  $('#nav-toggle').setAttribute('aria-expanded', 'false');
}));

$('#zone-select').addEventListener('change', e => {
  zone = e.target.value;
  save();
  paint();
});

/* ── запуск ─────────────────────────────────────────── */

$('#year').textContent = new Date().getFullYear();
$$('.hero__media img, .shot-frame img').forEach(img => {
  if (img.closest('.hero__media')) {
    const off = () => { img.hidden = true; $('.hero').classList.add('is-bare'); };
    if (img.complete && !img.naturalWidth) off();
    else img.addEventListener('error', off, { once: true });
  } else {
    watchPhoto(img);
  }
});

async function start() {
  await loadMenu();

  $('#zone-select').innerHTML = ZONES
    .map(z => `<option value="${z.id}"${z.id === zone ? ' selected' : ''}>${z.name}</option>`).join('');

  $('#zones').innerHTML = ZONES.map(z => `
    <div class="zone${z.price === null ? ' zone--soft' : ''}">
      <span>${z.name}</span>
      <b>${z.price === null ? 'по договорённости' : som(z.price)}</b>
    </div>`).join('');

  renderMenu();
  watchTabs();
  setMode(mode);
  paint();
}

start();
