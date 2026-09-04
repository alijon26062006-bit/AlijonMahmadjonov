/* Панель кухни: сама обновляется, звенит на новый заказ, статус в одно касание. */

const $ = s => document.querySelector(s);
const board = $('#board');

let known = new Set();     // номера заказов, которые уже показывали
let muted = localStorage.getItem('kitchen_muted') === '1';
let first = true;

const STATUS = { new: 'Новый', confirmed: 'Принят', cooking: 'Готовится' };

/* Короткий сигнал — без файлов, чтобы панель работала и без интернета. */
function beep() {
  if (muted) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.connect(gain); gain.connect(ctx.destination);
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.5);
    osc.start(); osc.stop(ctx.currentTime + 0.5);
  } catch (e) { /* браузер не дал звук — панель всё равно работает */ }
}

const minutesSince = iso => {
  const started = new Date(iso.replace(' ', 'T') + 'Z');
  return Math.max(0, Math.floor((Date.now() - started.getTime()) / 60000));
};

function ticket(o) {
  const mins = minutesSince(o.created_at);
  const late = mins >= 20;

  return `
  <article class="ticket ticket--${o.status}${late ? ' ticket--late' : ''}" data-id="${o.id}">
    <header class="ticket__head">
      <span class="ticket__no">№${o.number}</span>
      <span class="ticket__mode ${o.mode === 'pickup' ? 'is-pickup' : ''}">
        ${o.mode === 'pickup' ? 'Самовывоз' : 'Доставка'}
      </span>
      <span class="ticket__time">${mins} мин</span>
    </header>

    <ul class="ticket__items">
      ${o.items.map(i => `
        <li>
          <span class="qty">${i.qty}</span>
          <span class="name">${i.name}${i.options ? `<span class="opts">${i.options}</span>` : ''}</span>
        </li>`).join('')}
    </ul>

    ${o.note ? `<p class="ticket__note">${o.note}</p>` : ''}

    <div class="ticket__act">
      ${o.status !== 'cooking'
        ? `<button class="act-cook" data-set="cooking" data-id="${o.id}">Взять в работу</button>` : ''}
      <button class="act-done" data-set="done" data-id="${o.id}">Готово</button>
    </div>
  </article>`;
}

async function refresh() {
  try {
    const res = await fetch('/api/kitchen', { cache: 'no-store' });
    if (res.status === 303 || res.redirected) { location.href = '/admin/login'; return; }
    if (!res.ok) return;

    const { orders } = await res.json();

    // звеним, только когда появился заказ, которого раньше не было
    const fresh = orders.filter(o => !known.has(o.number));
    if (!first && fresh.length) beep();
    known = new Set(orders.map(o => o.number));
    first = false;

    board.innerHTML = orders.map(ticket).join('');
    $('#empty').hidden = orders.length > 0;
    $('#count').textContent = `${orders.length} ${plural(orders.length)}`;
  } catch (e) {
    // связь пропала — оставляем на экране то, что было
  }
}

const plural = n => {
  const t = n % 100, u = n % 10;
  if (t > 10 && t < 20) return 'заказов';
  if (u === 1) return 'заказ';
  if (u >= 2 && u <= 4) return 'заказа';
  return 'заказов';
};

board.addEventListener('click', async e => {
  const btn = e.target.closest('[data-set]');
  if (!btn) return;

  btn.disabled = true;
  const body = new FormData();
  body.append('status', btn.dataset.set);

  try {
    await fetch(`/api/kitchen/${btn.dataset.id}/status`, { method: 'POST', body });
    await refresh();
  } catch (e) {
    btn.disabled = false;
  }
});

$('#mute').addEventListener('click', () => {
  muted = !muted;
  localStorage.setItem('kitchen_muted', muted ? '1' : '0');
  $('#mute').textContent = muted ? 'Звук выкл' : 'Звук вкл';
  $('#mute').setAttribute('aria-pressed', String(muted));
  if (!muted) beep();
});

if (muted) {
  $('#mute').textContent = 'Звук выкл';
  $('#mute').setAttribute('aria-pressed', 'true');
}

function tick() {
  const d = new Date();
  $('#clock').textContent = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

tick();
refresh();
setInterval(refresh, 7000);   // новые заказы
setInterval(tick, 20000);     // часы в шапке
