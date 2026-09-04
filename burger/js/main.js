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

/* Кнопка «В заказ» превращается в счётчик, когда блюдо уже взято —
   так не нужно открывать корзину, чтобы добавить второй бургер. */
function pick(id, small = false) {
  return `
  <div class="pick${small ? ' pick--small' : ''}" data-id="${id}">
    <button class="add${small ? ' add--small' : ''}" type="button" data-id="${id}">${small ? '+' : 'В заказ'}</button>
    <div class="stepper">
      <button type="button" data-act="minus" aria-label="Убрать одну">−</button>
      <span data-count>1</span>
      <button type="button" data-act="plus" aria-label="Добавить ещё">+</button>
    </div>
  </div>`;
}

/* приводим счётчики на карточках в соответствие с заказом */
function syncPicks() {
  $$('.pick').forEach(box => {
    const qty = order[box.dataset.id] || 0;
    box.classList.toggle('is-picked', qty > 0);
    if (qty > 0) $('[data-count]', box).textContent = qty;
  });
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
      <img src="assets/dishes/${d.id}.jpg" alt="${d.name}" width="1216" height="896" loading="lazy">
      <div class="chip">
        <b>${som(d.price)}</b>
        ${d.oldPrice ? `<s>${som(d.oldPrice)}</s>` : ''}
      </div>
    </div>
    <div class="dish__body">
      <h4>${d.name}</h4>
      <p class="dish__about">${d.about}</p>
      <div class="dish__foot">
        <span class="dish__weight">${d.weight} г</span>
        ${pick(d.id)}
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
    ${pick(d.id, true)}
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

/* если фото баннера или зала нет — блок остаётся угольным, без пустой рамки */
function photoOrNothing(img, holder, cls) {
  if (!img) return;
  const off = () => { img.hidden = true; holder.classList.add(cls); };
  if (img.complete && !img.naturalWidth) off();
  else img.addEventListener('error', off, { once: true });
}
photoOrNothing($('#hero-photo'), $('.hero'), 'is-nophoto');
photoOrNothing($('#place-photo'), $('.place__card'), 'is-nophoto');

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
  const count = positions();

  $('#basket-sum').textContent = som(total());
  $('#basket-open').classList.toggle('is-full', count > 0);

  const bar = $('#bottombar');
  $('#bb-count').textContent = count;
  $('#bb-sum').textContent = som(total());

  if (count > 0) {
    bar.hidden = false;
    requestAnimationFrame(() => bar.classList.add('is-on'));
    document.body.classList.add('has-bar');
  } else {
    bar.classList.remove('is-on');
    document.body.classList.remove('has-bar');
    setTimeout(() => { if (!bar.classList.contains('is-on')) bar.hidden = true; }, 300);
  }

  syncPicks();

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

document.addEventListener('click', e => {
  const btn = e.target.closest('.pick .stepper button');
  if (!btn) return;
  const id = btn.closest('.pick').dataset.id;
  setQty(id, (order[id] || 0) + (btn.dataset.act === 'plus' ? 1 : -1));
});

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

let returnFocusTo = null;
const slowMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function open(sel) {
  const el = $(sel);
  returnFocusTo = document.activeElement;
  el.hidden = false;
  // класс ставим следующим кадром, иначе переход не запустится
  requestAnimationFrame(() => el.classList.add('is-open'));
  document.body.classList.add('is-fixed');
}

function closeAll() {
  let wasOpen = false;

  ['#basket', '#order'].forEach(sel => {
    const el = $(sel);
    if (el.hidden) return;
    wasOpen = true;
    el.classList.remove('is-open');
    if (slowMotion()) el.hidden = true;
    else setTimeout(() => { if (!el.classList.contains('is-open')) el.hidden = true; }, 420);
  });

  document.body.classList.remove('is-fixed');
  if (wasOpen && returnFocusTo) returnFocusTo.focus();
}

$('#basket-open').addEventListener('click', () => open('#basket'));
$('#bottombar').addEventListener('click', () => open('#basket'));

/* Корзину-шторку на телефоне можно смахнуть вниз. */
(function swipeToClose() {
  const panel = $('.basket__panel');
  let start = 0, shift = 0, active = false;

  panel.addEventListener('touchstart', e => {
    if ($('#receipt').scrollTop > 0) return;
    active = true;
    start = e.touches[0].clientY;
    panel.style.transition = 'none';
  }, { passive: true });

  panel.addEventListener('touchmove', e => {
    if (!active) return;
    shift = Math.max(0, e.touches[0].clientY - start);
    panel.style.transform = `translateY(${shift}px)`;
  }, { passive: true });

  panel.addEventListener('touchend', () => {
    if (!active) return;
    active = false;
    panel.style.transition = '';
    panel.style.transform = '';
    if (shift > 110) closeAll();
    shift = 0;
  });
})();
$$('[data-close]').forEach(el => el.addEventListener('click', closeAll));
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeAll(); });

$('#to-order').addEventListener('click', () => {
  const basket = $('#basket');
  basket.classList.remove('is-open');
  setTimeout(() => { basket.hidden = true; }, slowMotion() ? 0 : 420);

  open('#order');
  setTimeout(() => $('#order-form').elements.name.focus(), 120);
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

const phoneField = $('#order-form').elements.phone;
phoneField.addEventListener('blur', () => {
  const digits = phoneField.value.replace(/\D/g, '');
  const err = $('#order-err');
  if (phoneField.value && digits.length < 9) {
    err.textContent = 'В номере не хватает цифр — проверьте, пожалуйста.';
    err.hidden = false;
  } else if (!err.hidden && digits.length >= 9) {
    err.hidden = true;
  }
});

$('#order-call').href = `tel:${PHONE_MAIN}`;

/* Карточки появляются волной при прокрутке. Стартуют из видимого
   состояния, а не из нуля: если наблюдателя нет или включён режим
   уменьшенной анимации — меню просто на месте. */
function revealOnScroll() {
  if (slowMotion() || !('IntersectionObserver' in window)) return;

  const io = new IntersectionObserver((entries, obs) => {
    entries.filter(en => en.isIntersecting).forEach((en, i) => {
      en.target.style.setProperty('--delay', `${Math.min(i, 5) * 60}ms`);
      en.target.classList.add('is-in');
      obs.unobserve(en.target);
    });
  }, { rootMargin: '0px 0px -12% 0px', threshold: .15 });

  $$('.dish, .line, [data-rise]').forEach(el => {
    el.classList.add('will-rise');
    io.observe(el);
  });

  // страховка: если наблюдатель почему-то не сработал, всё видно через 3 с
  setTimeout(() => $$('.will-rise').forEach(el => el.classList.add('is-in')), 3000);
}

/* ── вкладки категорий ──────────────────────────────── */

function watchTabs() {
  const links = $$('#tabs-row a');
  const secs = SECTIONS.map(s => $(`#sec-${s.id}`)).filter(Boolean);

  const io = new IntersectionObserver(entries => {
    entries.forEach(en => {
      if (!en.isIntersecting) return;
      const id = en.target.id.replace('sec-', '');
      links.forEach(a => a.classList.toggle('is-active', a.dataset.sec === id));

      const active = links.find(a => a.dataset.sec === id);
      const row = $('#tabs-row');
      if (active && row.scrollWidth > row.clientWidth) {
        const shift = active.offsetLeft - (row.clientWidth - active.offsetWidth) / 2;
        row.scrollTo({ left: Math.max(shift, 0), behavior: slowMotion() ? 'auto' : 'smooth' });
      }
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
revealOnScroll();
watchTabs();
$$('#mode button').forEach(b => b.classList.toggle('is-active', b.dataset.mode === mode));
$('#addr-field').hidden = mode === 'pickup';
renderBasket();
