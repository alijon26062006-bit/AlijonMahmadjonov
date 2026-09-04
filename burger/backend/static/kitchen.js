/* Панель кухни: сама обновляется, звенит на новый заказ, статус в одно касание. */

const $ = s => document.querySelector(s);
const board = $('#board');

let known = new Set();     // номера заказов, которые уже показывали
let muted = localStorage.getItem('kitchen_muted') === '1';
let first = true;

const STATUS = { new: 'Новый', confirmed: 'Принят', cooking: 'Готовится' };

/* Сигнал для шумной кухни: три громких гудка в две ноты, квадратная волна —
   она пробивается сквозь шум вытяжки лучше чистого тона.
   Пока есть непринятый заказ, сигнал повторяется каждые 15 секунд. */

let audio = null;
let alarmTimer = null;

function ensureAudio() {
  if (!audio) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    audio = new Ctx();
  }
  if (audio.state === 'suspended') audio.resume();
  return audio;
}

function pulse(at, seconds = 0.32) {
  const ctx = audio;
  const gain = ctx.createGain();
  gain.connect(ctx.destination);
  gain.gain.setValueAtTime(0.0001, at);
  gain.gain.exponentialRampToValueAtTime(0.9, at + 0.015);
  gain.gain.setValueAtTime(0.9, at + seconds - 0.05);
  gain.gain.exponentialRampToValueAtTime(0.0001, at + seconds);

  [880, 1320].forEach(freq => {
    const osc = ctx.createOscillator();
    osc.type = 'square';
    osc.frequency.value = freq;
    osc.connect(gain);
    osc.start(at);
    osc.stop(at + seconds);
  });
}

function alarm() {
  if (muted) return;
  const ctx = ensureAudio();
  if (!ctx) return;

  const t = ctx.currentTime;
  pulse(t);
  pulse(t + 0.45);
  pulse(t + 0.9, 0.5);
}

/* Пока заказ не взяли в работу, кухня продолжает слышать сигнал. */
function keepAlarm(orders) {
  const waiting = orders.some(o => o.status === 'new');

  if (!waiting || muted) {
    clearInterval(alarmTimer);
    alarmTimer = null;
    return;
  }
  if (!alarmTimer) alarmTimer = setInterval(alarm, 15000);
}

/* Браузер не даёт звук, пока по экрану не нажали. Говорим об этом прямо. */
function checkSound() {
  const ctx = ensureAudio();
  const blocked = !ctx || ctx.state === 'suspended';
  $('#unlock').hidden = !blocked || muted;
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
    if (!first && fresh.length) alarm();
    known = new Set(orders.map(o => o.number));
    first = false;

    keepAlarm(orders);
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
  if (!muted) alarm();
  checkSound();
});

if (muted) {
  $('#mute').textContent = 'Звук выкл';
  $('#mute').setAttribute('aria-pressed', 'true');
}

function tick() {
  const d = new Date();
  $('#clock').textContent = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

$('#unlock').addEventListener('click', () => {
  ensureAudio();
  alarm();
  checkSound();
});

document.addEventListener('pointerdown', checkSound, { once: true });

tick();
checkSound();
refresh();
setInterval(refresh, 5000);   // новые заказы
setInterval(tick, 20000);     // часы в шапке
