/* RealPhone — каталог, корзина, оформление заказа. */

const BOT_USERNAME = 'RealPhoneShopBot';   // <— username бота-админки, без @
const FREE_DELIVERY_FROM = 1000;           // бесплатная доставка по Душанбе, сомони

let lang = localStorage.getItem('rp_lang') || 'ru';
let cart = JSON.parse(localStorage.getItem('rp_cart') || '{}');
let activeCat = 'all';
let query = '';
let sortBy = 'popular';

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const t = (ru, tj) => (lang === 'ru' ? ru : tj);
const price = n => n.toLocaleString('ru-RU').replace(/,/g, ' ') + ' с.';
const monthly = n => Math.ceil(n / 12 / 10) * 10;   // платёж на 12 месяцев, округляем вверх

/* ── язык ───────────────────────────────────────────── */

function applyLang() {
  document.documentElement.lang = lang === 'ru' ? 'ru' : 'tg';

  $$('[data-ru]').forEach(el => {
    el.textContent = el.dataset[lang];
  });
  $$('[data-ru-placeholder]').forEach(el => {
    el.placeholder = el.dataset[lang + 'Placeholder'];
  });
  $$('.lang__btn').forEach(b => b.classList.toggle('is-active', b.dataset.lang === lang));

  localStorage.setItem('rp_lang', lang);
}

$$('.lang__btn').forEach(btn => {
  btn.addEventListener('click', () => {
    lang = btn.dataset.lang;
    applyLang();
    renderCats();
    renderFilters();
    renderGrid();
    renderCart();
    calc();
  });
});

/* ── категории и фильтры ────────────────────────────── */

const CAT_ICONS = {
  phones: 'M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm0 3v13h10V5H7Zm4 14h2v1h-2v-1Z',
  audio: 'M12 3a9 9 0 0 0-9 9v6a3 3 0 0 0 3 3h2v-8H5v-1a7 7 0 1 1 14 0v1h-3v8h2a3 3 0 0 0 3-3v-6a9 9 0 0 0-9-9Z',
  watch: 'M9 1h6l.6 3.1A8 8 0 0 1 15.6 20L15 23H9l-.6-3.1A8 8 0 0 1 8.4 4.1L9 1Zm3 5a6 6 0 1 0 0 12 6 6 0 0 0 0-12Zm-1 2h2v4h3v2h-5V8Z',
  accessories: 'M4 6h13a3 3 0 0 1 3 3v1h1v4h-1v1a3 3 0 0 1-3 3H4a3 3 0 0 1-3-3V9a3 3 0 0 1 3-3Zm0 2a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h13a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1H4Z'
};

function renderCats() {
  $('#cats').innerHTML = CATEGORIES.map(c => `
    <button class="cat" type="button" data-cat="${c.id}">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="${CAT_ICONS[c.id]}"/></svg>
      <span>${c[lang]}</span>
      <small>${PRODUCTS.filter(p => p.category === c.id).length}</small>
    </button>`).join('');

  $$('.cat').forEach(btn => btn.addEventListener('click', () => {
    activeCat = btn.dataset.cat;
    renderFilters();
    renderGrid();
    $('#catalog').scrollIntoView({ behavior: 'smooth' });
  }));
}

function renderFilters() {
  const items = [{ id: 'all', label: t('Все товары', 'Ҳама молҳо') }]
    .concat(CATEGORIES.map(c => ({ id: c.id, label: c[lang] })));

  $('#filters').innerHTML = items.map(i => `
    <button class="chip${i.id === activeCat ? ' is-active' : ''}" type="button" data-cat="${i.id}">${i.label}</button>
  `).join('');

  $$('#filters .chip').forEach(btn => btn.addEventListener('click', () => {
    activeCat = btn.dataset.cat;
    renderFilters();
    renderGrid();
  }));
}

/* ── карточки товаров ───────────────────────────────── */

function visibleProducts() {
  let list = PRODUCTS.filter(p => activeCat === 'all' || p.category === activeCat);

  if (query) {
    const q = query.toLowerCase();
    list = list.filter(p => (p.name + ' ' + p.brand).toLowerCase().includes(q));
  }

  if (sortBy === 'cheap')     list = [...list].sort((a, b) => a.price - b.price);
  if (sortBy === 'expensive') list = [...list].sort((a, b) => b.price - a.price);
  if (sortBy === 'popular')   list = [...list].sort((a, b) => (b.hit ? 1 : 0) - (a.hit ? 1 : 0));

  return list;
}

function discount(p) {
  if (!p.oldPrice) return 0;
  return Math.round((1 - p.price / p.oldPrice) * 100);
}

function card(p) {
  const off = discount(p);
  return `
  <article class="card" data-id="${p.id}">
    <div class="card__media">
      ${off ? `<span class="card__badge">−${off}%</span>` : ''}
      ${p.hit ? `<span class="card__hit">${t('Хит', 'Хит')}</span>` : ''}
      <img src="assets/products/${p.id}.jpg" alt="${p.name}" loading="lazy"
           onerror="this.replaceWith(placeholder())">
    </div>
    <div class="card__body">
      <span class="card__brand">${p.brand}</span>
      <h3 class="card__name">${p.name}</h3>
      <p class="card__specs">${p.specs[lang]}</p>
      <div class="card__prices">
        <b>${price(p.price)}</b>
        ${p.oldPrice ? `<s>${price(p.oldPrice)}</s>` : ''}
      </div>
      <p class="card__nasiya">${t('в насия от', 'ба насия аз')} <b>${price(monthly(p.price))}</b>/${t('мес', 'моҳ')}</p>
      <button class="btn btn--primary btn--wide add" type="button" data-id="${p.id}">
        ${t('В корзину', 'Ба сабад')}
      </button>
    </div>
  </article>`;
}

/* заглушка вместо фото, пока его нет */
function placeholder() {
  const box = document.createElement('div');
  box.className = 'card__ph';
  box.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm0 3v13h10V5H7Z"/></svg>`;
  return box;
}

function renderGrid() {
  const list = visibleProducts();
  $('#grid').innerHTML = list.map(card).join('');
  $('#empty').hidden = list.length > 0;

  $$('.add').forEach(btn => btn.addEventListener('click', () => addToCart(btn.dataset.id)));
}

$('#search').addEventListener('input', e => {
  query = e.target.value.trim();
  renderGrid();
});

$('#sort').addEventListener('change', e => {
  sortBy = e.target.value;
  renderGrid();
});

/* ── корзина ────────────────────────────────────────── */

function saveCart() {
  localStorage.setItem('rp_cart', JSON.stringify(cart));
}

function cartCount() {
  return Object.values(cart).reduce((s, n) => s + n, 0);
}

function cartTotal() {
  return Object.entries(cart).reduce((sum, [id, qty]) => {
    const p = PRODUCTS.find(p => p.id === id);
    return p ? sum + p.price * qty : sum;
  }, 0);
}

function addToCart(id) {
  cart[id] = (cart[id] || 0) + 1;
  saveCart();
  renderCart();
  toast(t('Товар добавлен в корзину', 'Мол ба сабад илова шуд'));
}

function setQty(id, qty) {
  if (qty <= 0) delete cart[id];
  else cart[id] = qty;
  saveCart();
  renderCart();
}

function renderCart() {
  const count = cartCount();
  const badge = $('#cart-count');
  badge.textContent = count;
  badge.hidden = count === 0;

  const entries = Object.entries(cart);

  if (!entries.length) {
    $('#cart-items').innerHTML = `<p class="drawer__empty">${t('Корзина пока пустая', 'Сабад ҳоло холӣ аст')}</p>`;
  } else {
    $('#cart-items').innerHTML = entries.map(([id, qty]) => {
      const p = PRODUCTS.find(p => p.id === id);
      if (!p) return '';
      return `
      <div class="line" data-id="${id}">
        <div class="line__info">
          <b>${p.name}</b>
          <span>${price(p.price)}</span>
        </div>
        <div class="qty">
          <button type="button" data-act="minus">−</button>
          <span>${qty}</span>
          <button type="button" data-act="plus">+</button>
        </div>
        <button class="line__del" type="button" data-act="del" aria-label="Удалить">&times;</button>
      </div>`;
    }).join('');
  }

  const total = cartTotal();
  const left = FREE_DELIVERY_FROM - total;

  $('#delivery-hint').textContent = total && left > 0
    ? t(`До бесплатной доставки ещё ${price(left)}`, `То расонидани ройгон боз ${price(left)}`)
    : t('Доставка по Душанбе бесплатно', 'Расонидан дар Душанбе ройгон');

  $('#cart-total').textContent = price(total);
  $('#modal-total').textContent = price(total);
  $('#checkout').disabled = total === 0;
}

$('#cart-items').addEventListener('click', e => {
  const btn = e.target.closest('button[data-act]');
  if (!btn) return;

  const id = btn.closest('.line').dataset.id;
  const act = btn.dataset.act;

  if (act === 'plus')  setQty(id, cart[id] + 1);
  if (act === 'minus') setQty(id, cart[id] - 1);
  if (act === 'del')   setQty(id, 0);
});

/* ── панель корзины и модалка ───────────────────────── */

function openDrawer()  { $('#drawer').hidden = false;  document.body.classList.add('is-locked'); }
function closeDrawer() { $('#drawer').hidden = true;   document.body.classList.remove('is-locked'); }

$('#cart-open').addEventListener('click', openDrawer);

$$('[data-close]').forEach(el => el.addEventListener('click', () => {
  closeDrawer();
  $('#checkout-modal').hidden = true;
  document.body.classList.remove('is-locked');
}));

document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  closeDrawer();
  $('#checkout-modal').hidden = true;
});

$('#checkout').addEventListener('click', () => {
  if (!cartCount()) return;
  closeDrawer();
  $('#checkout-modal').hidden = false;
  document.body.classList.add('is-locked');
  $('#send-order').href = orderLink();
});

/* Ссылка на бота: корзина в компактном виде, например 3q1-7q2
   (номер товара в каталоге, q, количество). Бот разбирает её сам. */
function orderCode() {
  return Object.entries(cart).map(([id, qty]) => {
    const idx = PRODUCTS.findIndex(p => p.id === id);
    return idx.toString(36) + 'q' + qty;
  }).join('-');
}

function orderLink() {
  return `https://t.me/${BOT_USERNAME}?start=${orderCode()}`;
}

function orderText() {
  const lines = Object.entries(cart).map(([id, qty]) => {
    const p = PRODUCTS.find(p => p.id === id);
    return `${p.name} × ${qty} — ${price(p.price * qty)}`;
  });
  lines.push(`${t('Итого', 'Ҳамагӣ')}: ${price(cartTotal())}`);
  return lines.join('\n');
}

/* заодно кладём заказ в буфер — если бот недоступен, клиент вставит текст в чат */
$('#send-order').addEventListener('click', () => {
  navigator.clipboard?.writeText(orderText()).catch(() => {});
});

/* номера карт копируются по клику */
$$('.pay__num').forEach(el => el.addEventListener('click', () => {
  navigator.clipboard?.writeText(el.dataset.copy)
    .then(() => toast(t('Номер карты скопирован', 'Рақами корт нусхабардорӣ шуд')))
    .catch(() => {});
}));

/* ── калькулятор насия ──────────────────────────────── */

let term = 3;

function calc() {
  const total = Number($('#calc-price').value) || 0;
  const downPct = Number($('#calc-down').value);
  const down = total * downPct / 100;
  const rest = total - down;

  // 3 месяца без переплаты, дальше 3% в месяц на остаток
  const rate = term === 3 ? 0 : 0.03;
  const withRate = rest * (1 + rate * term);

  $('#calc-down-out').textContent = downPct + '%';
  $('#calc-month').textContent = price(Math.ceil(withRate / term));
  $('#calc-over').textContent = price(Math.round(withRate - rest));
}

$('#calc-price').addEventListener('input', calc);
$('#calc-down').addEventListener('input', calc);

$$('#calc-terms button').forEach(btn => btn.addEventListener('click', () => {
  term = Number(btn.dataset.term);
  $$('#calc-terms button').forEach(b => b.classList.toggle('is-active', b === btn));
  calc();
}));

/* ── мелочи ─────────────────────────────────────────── */

let toastTimer;
function toast(text) {
  const box = $('#toast');
  box.textContent = text;
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { box.hidden = true; }, 2500);
}

$('#burger').addEventListener('click', () => {
  $('.header__nav').classList.toggle('is-open');
});

$$('.header__nav a').forEach(a => a.addEventListener('click', () => {
  $('.header__nav').classList.remove('is-open');
}));

window.addEventListener('scroll', () => {
  $('#header').classList.toggle('is-stuck', window.scrollY > 10);
});

$('#year').textContent = new Date().getFullYear();

applyLang();
renderCats();
renderFilters();
renderGrid();
renderCart();
calc();
