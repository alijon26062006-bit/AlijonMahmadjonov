/* Панель курьера: сама обновляется, заказ забирается в одно касание.
   Если заказ увели — он просто пропадёт при следующем обновлении. */

const $ = s => document.querySelector(s);
const REFRESH = 7000;

let busy = false;          // пока идёт запрос, не даём нажать второй раз
let knownFree = new Set();

const plural = (n, one, few, many) => {
  const t = n % 100, d = n % 10;
  if (t > 10 && t < 20) return many;
  if (d === 1) return one;
  if (d >= 2 && d <= 4) return few;
  return many;
};

function ago(iso) {
  const t = Date.parse(iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z');
  if (Number.isNaN(t)) return '';
  const min = Math.max(0, Math.round((Date.now() - t) / 60000));
  if (min < 1) return 'только что';
  if (min < 60) return `${min} ${plural(min, 'минуту', 'минуты', 'минут')} назад`;
  const h = Math.round(min / 60);
  return `${h} ${plural(h, 'час', 'часа', 'часов')} назад`;
}

const esc = s => String(s ?? '').replace(/[&<>"]/g, c => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function snack(text) {
  const el = $('#snack');
  el.textContent = text;
  el.hidden = false;
  clearTimeout(snack.timer);
  snack.timer = setTimeout(() => { el.hidden = true; }, 3000);
}

/* короткий сигнал, когда появился новый свободный заказ */
let audio = null;
function beep() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    audio = audio || new Ctx();
    if (audio.state === 'suspended') audio.resume();
    const at = audio.currentTime;
    const gain = audio.createGain();
    gain.connect(audio.destination);
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.exponentialRampToValueAtTime(0.6, at + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.45);
    const osc = audio.createOscillator();
    osc.type = 'square';
    osc.frequency.value = 990;
    osc.connect(gain);
    osc.start(at);
    osc.stop(at + 0.45);
  } catch (e) { /* без звука тоже работает */ }
}

function goods(o) {
  if (!o.items || !o.items.length) return '';
  return `<ul class="goods">${o.items
    .map(i => `<li>${esc(i.name)} × ${i.qty}</li>`).join('')}</ul>`;
}

function card(o, mine) {
  const sub = [];
  if (o.landmark) sub.push(`Ориентир: ${esc(o.landmark)}`);
  if (o.note) sub.push(`Комментарий: ${esc(o.note)}`);
  if (mine && o.name) sub.push(`${esc(o.name)}, ${esc(o.phone)}`);

  const acts = mine
    ? `<div class="acts">
         <a class="btn ghost" href="tel:${esc(o.phone)}">Позвонить</a>
         <button class="btn" data-done="${o.id}" type="button">Доставил</button>
       </div>
       <button class="drop" data-drop="${o.id}" type="button">Не смогу — вернуть заказ</button>`
    : `<div class="acts">
         <button class="btn" data-take="${o.id}" type="button">Беру заказ</button>
       </div>`;

  return `<article class="card ${mine ? 'mine' : ''}">
    <div class="card__top"><span class="num">№${o.number}</span>
      <span class="ago">${ago(o.created_at)}</span></div>
    <p class="addr">${esc(o.address)}</p>
    ${sub.length ? `<p class="sub">${sub.join(' · ')}</p>` : ''}
    ${goods(o)}
    <p class="sum">К оплате: <b>${o.total} сомони</b></p>
    ${acts}
  </article>`;
}

function draw(data) {
  $('#mine').innerHTML = data.mine.map(o => card(o, true)).join('');
  $('#free').innerHTML = data.free.map(o => card(o, false)).join('');
  $('#mine-empty').hidden = data.mine.length > 0;
  $('#free-empty').hidden = data.free.length > 0;
  $('#mine-count').textContent = data.mine.length || '';
  $('#free-count').textContent = data.free.length || '';

  const ids = new Set(data.free.map(o => o.id));
  const fresh = [...ids].some(id => !knownFree.has(id));
  if (fresh && knownFree.size) beep();
  knownFree = ids;
}

async function load() {
  try {
    const r = await fetch('/api/courier/orders', { credentials: 'same-origin' });
    if (r.status === 403) { location.href = '/courier'; return; }
    if (!r.ok) throw new Error(r.status);
    draw(await r.json());
    $('#live').classList.add('on');
  } catch (e) {
    $('#live').classList.remove('on');
  }
}

async function act(id, what) {
  if (busy) return;
  busy = true;
  document.querySelectorAll('.btn').forEach(b => { b.disabled = true; });
  try {
    const r = await fetch(`/api/courier/orders/${id}/${what}`,
      { method: 'POST', credentials: 'same-origin' });
    const data = await r.json();
    snack(data.message || (data.ok ? 'Готово' : 'Не получилось'));
  } catch (e) {
    snack('Нет связи. Попробуйте ещё раз');
  } finally {
    busy = false;
    await load();
  }
}

document.addEventListener('click', e => {
  const take = e.target.closest('[data-take]');
  if (take) return act(take.dataset.take, 'take');

  const done = e.target.closest('[data-done]');
  if (done) return act(done.dataset.done, 'delivered');

  const drop = e.target.closest('[data-drop]');
  if (drop && confirm('Вернуть заказ в общий список?')) return act(drop.dataset.drop, 'release');
});

function clock() {
  $('#clock').textContent = new Date().toLocaleTimeString('ru-RU',
    { hour: '2-digit', minute: '2-digit' });
}

/* Оболочка панели живёт в кэше: в подъезде и в лифте экран всё равно откроется,
   а заказы всегда берутся с сервера. */
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js')
    .catch(e => console.warn('кэш панели не включился:', e.message));
}

clock();
setInterval(clock, 20000);
load();
setInterval(load, REFRESH);
document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
