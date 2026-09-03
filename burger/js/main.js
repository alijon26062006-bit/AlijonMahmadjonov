/* The Burger — меню, корзина-чек, оформление заказа. */

const TG_CHAT = 'theburgertj';          // куда уходит заказ
const PHONE_MAIN = '+992939171997';

let order = JSON.parse(localStorage.getItem('tb_order') || '{}');
let mode = localStorage.getItem('tb_mode') || 'delivery';

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const som = n => n.toLocaleString('ru-RU').replace(/,/g, ' ') + ' с.';
const dish = id => MENU.find(d => d.id === id);

/* ── меню ───────────────────────────────────────────── */

/* знак заведения вместо фото, пока фото нет */
function mark() {
  const box = document.createElement('div');
  box.className = 'shot__mark';
  box.innerHTML = `<svg viewBox="0 0 64 52" aria-hidden="true">
    <path d="M14 17 10 3l7 5 5-8 5 8 7-5-4 14Z" transform="translate(10 0)" />
    <rect x="6" y="24" width="52" height="10" rx="5" />
    <rect x="9" y="36" width="46" height="5" rx="2.5" />
    <rect x="6" y="43" width="52" height="8" rx="4" />
  </svg>`;
  return box;
}

function tagHtml(key) {
  if (!key || !TAGS[key]) return '';
  return `<span class="tag ${TAGS[key].cls}">${TAGS[key].label}</span>`;
}

/* бургеры и сеты — крупными карточками с фото */
function bigCard(d) {
  return `
  <article class="dish">
    <div class="shot">
      ${tagHtml(d.tag)}
      <img src="assets/dishes/${d.id}.jpg" alt="${d.name}" loading="lazy">
    </div>
    <div class="dish__body">
      <h3>${d.name}</h3>
      <p class="dish__about">${d.about}</p>
      <div class="dish__foot">
        <div class="dish__price">
          <b>${som(d.price)}</b>
          ${d.oldPrice ? `<s>${som(d.oldPrice)}</s>` : ''}
          <span class="dish__weight">${d.weight} г</span>
        </div>
        <button class="add" type="button" data-id="${d.id}">В заказ</button>
      </div>
    </div>
  </article>`;
}

/* снэки, соусы, напитки — компактными строками, как в бумажном меню */
function row(d) {
  return `
  <div class="line">
    <div class="line__name">
      <b>${d.name}</b>${tagHtml(d.tag)}
      ${d.about ? `<span class="line__note">${d.about}</span>` : ''}
    </div>
    <span class="line__weight">${d.weight} г</span>
    <b class="line__price">${som(d.price)}</b>
    <button class="add add--small" type="button" data-id="${d.id}">+</button>
  </div>`;
}

function renderMenu() {
  $('#tabs-row').innerHTML = SECTIONS
    .map(s => `<a href="#sec-${s.id}" data-sec="${s.id}">${s.title}</a>`).join('');

  $('#menu-body').innerHTML = SECTIONS.map(s => {
    const items = MENU.filter(d => d.section === s.id);
    const big = s.id === 'burgers' || s.id === 'sets';

    return `
    <section class="sec" id="sec-${s.id}">
      <div class="sec__head">
        <h3 class="h-display">${s.title}</h3>
        ${s.note ? `<span>${s.note}</span>` : ''}
      </div>
      <div class="${big ? 'dishes' : 'lines'}">
        ${items.map(big ? bigCard : row).join('')}
      </div>
    </section>`;
  }).join('');

  $$('.add').forEach(b => b.addEventListener('click', () => addDish(b.dataset.id)));

  $$('.shot img').forEach(img => {
    if (img.complete && !img.naturalWidth) img.replaceWith(mark());
    else img.addEventListener('error', () => img.replaceWith(mark()), { once: true });
  });
}

/* фото в баннере тоже может отсутствовать */
const heroPhoto = $('#hero-photo');
if (heroPhoto) {
  const heroFallback = () => {
    heroPhoto.hidden = true;
    $('#hero-mark').hidden = false;
  };
  $('#hero-mark').hidden = true;
  if (heroPhoto.complete && !heroPhoto.naturalWidth) heroFallback();
  else heroPhoto.addEventListener('error', heroFallback, { once: true });
}

/* ── корзина ────────────────────────────────────────── */

function save() {
  localStorage.setItem('tb_order', JSON.stringify(order));
  localStorage.setItem('tb_mode', mode);
}

function goods() {
  return Object.entries(order).reduce((sum, [id, qty]) => {
    const d = dish(id);
    return d ? sum + d.price * qty : sum;
  }, 0);
}

function deliveryCost() {
  if (mode === 'pickup') return 0;
  const g = goods();
  return g === 0 || g >= DELIVERY.freeFrom ? 0 : DELIVERY.price;
}

function total() {
  return goods() + deliveryCost();
}

function positions() {
  return Object.values(order).reduce((s, n) => s + n, 0);
}

function addDish(id) {
  order[id] = (order[id] || 0) + 1;
  save();
  renderBasket();
  snack(`${dish(id).name} — в заказе`);
}

function setQty(id, qty) {
  if (qty <= 0) delete order[id];
  else order[id] = qty;
  save();
  renderBasket();
}

function renderBasket() {
  $('#basket-sum').textContent = som(total());
  $('#basket-open').classList.toggle('is-full', positions() > 0);

  const list = Object.entries(order);

  $('#receipt').innerHTML = list.length
    ? list.map(([id, qty]) => {
        const d = dish(id);
        return `
        <div class="pos" data-id="${id}">
          <div class="pos__name">
            <b>${d.name}</b>
            <span>${som(d.price)} × ${qty}</span>
          </div>
          <div class="counter">
            <button type="button" data-act="minus" aria-label="Меньше">−</button>
            <span>${qty}</span>
            <button type="button" data-act="plus" aria-label="Больше">+</button>
          </div>
          <b class="pos__sum">${som(d.price * qty)}</b>
        </div>`;
      }).join('')
    : `<p class="receipt__empty">Пока пусто. Начните с бургера — остальное само добавится.</p>`;

  const dc = deliveryCost();
  $('#totals').innerHTML = `
    <div><span>Блюда</span><b>${som(goods())}</b></div>
    <div><span>${mode === 'pickup' ? 'Самовывоз' : 'Доставка'}</span>
         <b>${mode === 'pickup' ? 'бесплатно' : (dc ? som(dc) : 'бесплатно')}</b></div>
    <div class="totals__big"><span>Итого к оплате</span><b>${som(total())}</b></div>`;

  const short = DELIVERY.minOrder - goods();
  const needMore = mode === 'delivery' && goods() > 0 && short > 0;

  $('#min-note').textContent = needMore
    ? `Минимальный заказ на доставку — ${som(DELIVERY.minOrder)} Добавьте ещё на ${som(short)}`
    : (mode === 'delivery' && goods() > 0 && dc
        ? `До бесплатной доставки — ${som(DELIVERY.freeFrom - goods())}`
        : '');

  $('#to-order').disabled = positions() === 0 || needMore;
  $('#order-total').textContent = som(total());
}

$('#receipt').addEventListener('click', e => {
  const btn = e.target.closest('button[data-act]');
  if (!btn) return;
  const id = btn.closest('.pos').dataset.id;
  setQty(id, order[id] + (btn.dataset.act === 'plus' ? 1 : -1));
});

$$('#mode button').forEach(btn => btn.addEventListener('click', () => {
  mode = btn.dataset.mode;
  $$('#mode button').forEach(b => b.classList.toggle('is-active', b === btn));
  $('#addr-field').hidden = mode === 'pickup';
  save();
  renderBasket();
}));

/* ── окна ───────────────────────────────────────────── */

function open(sel) {
  $(sel).hidden = false;
  document.body.classList.add('is-fixed');
}
function closeAll() {
  $('#basket').hidden = true;
  $('#order').hidden = true;
  document.body.classList.remove('is-fixed');
}

$('#basket-open').addEventListener('click', () => open('#basket'));
$$('[data-close]').forEach(el => el.addEventListener('click', closeAll));
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeAll(); });

$('#to-order').addEventListener('click', () => {
  $('#basket').hidden = true;
  open('#order');
  $('#order-form').elements.name.focus();
});

/* ── отправка заказа ────────────────────────────────── */

function orderText(f) {
  const rows = Object.entries(order).map(([id, qty]) => {
    const d = dish(id);
    return `• ${d.name} × ${qty} — ${som(d.price * qty)}`;
  });

  const lines = ['Заказ с сайта The Burger', '', ...rows, ''];

  if (mode === 'delivery') {
    lines.push(`Доставка: ${deliveryCost() ? som(deliveryCost()) : 'бесплатно'}`);
    lines.push(`Адрес: ${f.address.value.trim() || '—'}`);
  } else {
    lines.push('Самовывоз: ул. Айни 49');
  }

  lines.push(`Итого: ${som(total())}`, '', `Имя: ${f.name.value.trim()}`, `Телефон: ${f.phone.value.trim()}`);
  if (f.note.value.trim()) lines.push(`Комментарий: ${f.note.value.trim()}`);

  return lines.join('\n');
}

$('#order-form').addEventListener('submit', e => {
  e.preventDefault();
  const f = e.target.elements;          // у формы своё свойство name, поля берём через elements
  const err = $('#order-err');

  const digits = f.phone.value.replace(/\D/g, '');
  if (!f.name.value.trim()) return fail('Напишите, как вас зовут.');
  if (digits.length < 9) return fail('Проверьте номер телефона — по нему подтверждаем заказ.');
  if (mode === 'delivery' && !f.address.value.trim()) return fail('Нужен адрес, иначе курьер не доедет.');

  err.hidden = true;

  const text = orderText(f);
  navigator.clipboard?.writeText(text).catch(() => {});
  window.open(`https://t.me/${TG_CHAT}?text=${encodeURIComponent(text)}`, '_blank', 'noopener');

  closeAll();
  snack('Заказ собран — отправьте сообщение в Telegram');

  function fail(msg) {
    err.textContent = msg;
    err.hidden = false;
  }
});

$('#order-call').href = `tel:${PHONE_MAIN}`;

/* ── вкладки категорий ──────────────────────────────── */

function watchTabs() {
  const links = $$('#tabs-row a');
  const secs = SECTIONS.map(s => $(`#sec-${s.id}`)).filter(Boolean);

  const io = new IntersectionObserver(entries => {
    entries.forEach(en => {
      if (!en.isIntersecting) return;
      const id = en.target.id.replace('sec-', '');
      links.forEach(a => a.classList.toggle('is-active', a.dataset.sec === id));
    });
  }, { rootMargin: '-140px 0px -70% 0px' });

  secs.forEach(s => io.observe(s));
  links[0]?.classList.add('is-active');
}

/* ── мелочи ─────────────────────────────────────────── */

let snackTimer;
function snack(text) {
  const box = $('#snack');
  box.textContent = text;
  box.hidden = false;
  clearTimeout(snackTimer);
  snackTimer = setTimeout(() => { box.hidden = true; }, 2400);
}

$('#nav-toggle').addEventListener('click', () => $('.head__nav').classList.toggle('is-open'));
$$('.head__nav a').forEach(a => a.addEventListener('click', () => $('.head__nav').classList.remove('is-open')));

window.addEventListener('scroll', () => {
  $('#head').classList.toggle('is-down', window.scrollY > 8);
});

$('#year').textContent = new Date().getFullYear();

renderMenu();
watchTabs();
$$('#mode button').forEach(b => b.classList.toggle('is-active', b.dataset.mode === mode));
$('#addr-field').hidden = mode === 'pickup';
renderBasket();
