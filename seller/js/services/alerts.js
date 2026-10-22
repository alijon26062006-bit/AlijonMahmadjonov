import { render } from '../app.js';
import { newCount, S, save } from '../state.js';
import { toast } from '../ui/dom.js';

// Сигнал о новых заказах: мелодия каждые 4 секунды, вибрация и мигающий заголовок,
// пока продавец не ответит. Браузер разрешает звук только после первого касания страницы.

const EVERY_MS = 4000;
const TITLE = document.title;
let ctx = null, out = null, flip = false, lock = null;

export const MELODIES = [['bell', 'Колокольчик'], ['chime', 'Мелодия'], ['loud', 'Громкий сигнал']];

const unlock = () => {
  if (ctx) return;
  try {
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    // компрессор поднимает громкость, не давая звуку хрипеть
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -18; comp.knee.value = 6; comp.ratio.value = 6;
    out = ctx.createGain(); out.gain.value = 1.6;
    out.connect(comp).connect(ctx.destination);
  } catch { /* звук недоступен */ }
};
document.addEventListener('pointerdown', unlock);
document.addEventListener('keydown', unlock);

// одна нота: основной тон и обертон, мягкая атака и затухание
function note(hz, t, len, type = 'sine', vol = 0.5, partial = 0) {
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(vol, t + 0.012);
  g.gain.exponentialRampToValueAtTime(0.0001, t + len);
  g.connect(out);
  for (const [f, k] of partial ? [[hz, 1], [hz * partial, 0.35]] : [[hz, 1]]) {
    const o = ctx.createOscillator(), og = ctx.createGain();
    o.type = type; o.frequency.value = f; og.gain.value = k;
    o.connect(og).connect(g); o.start(t); o.stop(t + len + 0.05);
  }
}

const TUNES = {
  bell: t => [1046.5, 1318.5, 1568].forEach((hz, i) => note(hz, t + i * 0.16, 1.3, 'sine', 0.55, 2.76)),
  chime: t => [659.3, 784, 987.8, 1318.5, 987.8].forEach((hz, i) => note(hz, t + i * 0.13, 0.55, 'triangle', 0.6)),
  loud: t => [0, 1, 2, 3].forEach(i => note(i % 2 ? 784 : 1046.5, t + i * 0.2, 0.18, 'square', 0.35)),
};

export function ring(id = S?.shop.melody || 'bell') {
  if (!ctx) return false;
  if (ctx.state === 'suspended') ctx.resume();
  (TUNES[id] || TUNES.bell)(ctx.currentTime + 0.02);
  return true;
}
export function testSound(id) {
  unlock();
  if (!ring(id)) return toast('Звук недоступен в этом браузере');
  navigator.vibrate?.([200, 100, 200]);
  toast('Если не слышно — проверьте, что телефон не на беззвучном и громкость включена');
}

// экран не гаснет, пока открыт кабинет: продавец не пропустит заказ
async function keepAwake() {
  const want = S && S.shop.awake !== false && document.visibilityState === 'visible';
  try {
    if (want && !lock && navigator.wakeLock) { lock = await navigator.wakeLock.request('screen'); lock.addEventListener('release', () => { lock = null; }); }
    if (!want && lock) { await lock.release(); lock = null; }
  } catch { lock = null; }
}
document.addEventListener('visibilitychange', keepAwake);

function autoAccept() {
  const fresh = S.orders.filter(o => o.status === 'new');
  if (!fresh.length) return;
  for (const o of fresh) Object.assign(o, { status: 'accepted', readyIn: S.shop.prep, acceptedAt: Date.now(), autoAccepted: true });
  save();
  render();
  toast(fresh.length === 1 ? `Заказ № ${fresh[0].no} принят автоматически` : `Принято автоматически: ${fresh.length} заказа`);
}

function tick() {
  keepAwake();
  if (!S) { document.title = TITLE; return; }
  if (S.shop.autoAccept) autoAccept();
  const n = newCount();
  flip = !flip;
  document.title = n && flip ? `(${n}) Новый заказ` : TITLE;
  if (!n) return;
  if (S.shop.sound !== false) ring();
  navigator.vibrate?.([300, 120, 300, 120, 300]);
}

setInterval(tick, EVERY_MS);
