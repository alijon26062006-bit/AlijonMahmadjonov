import { render } from '../app.js';
import { newCount, S, save } from '../state.js';
import { toast } from '../ui/dom.js';

// Сигнал о новых заказах: звук каждые 3 секунды, вибрация и мигающий заголовок,
// пока продавец не ответит. Браузер разрешает звук только после первого касания страницы.

const EVERY_MS = 3000;
const TITLE = document.title;
let audio = null;
let flip = false;

const unlock = () => {
  if (audio) return;
  try { audio = new (window.AudioContext || window.webkitAudioContext)(); } catch { /* звук недоступен */ }
};
document.addEventListener('pointerdown', unlock);
document.addEventListener('keydown', unlock);

function ring() {
  if (!audio) return;
  if (audio.state === 'suspended') audio.resume();
  const t0 = audio.currentTime;
  [880, 660, 880].forEach((hz, i) => {
    const t = t0 + i * 0.18;
    const osc = audio.createOscillator();
    const gain = audio.createGain();
    osc.type = 'square';
    osc.frequency.value = hz;
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(0.25, t + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
    osc.connect(gain).connect(audio.destination);
    osc.start(t);
    osc.stop(t + 0.17);
  });
}

function autoAccept() {
  const fresh = S.orders.filter(o => o.status === 'new');
  if (!fresh.length) return;
  for (const o of fresh) Object.assign(o, { status: 'accepted', readyIn: S.shop.prep, acceptedAt: Date.now(), autoAccepted: true });
  save();
  render();
  toast(fresh.length === 1 ? `Заказ № ${fresh[0].no} принят автоматически` : `Принято автоматически: ${fresh.length} заказа`);
}

function tick() {
  if (!S) { document.title = TITLE; return; }
  if (S.shop.autoAccept) autoAccept();
  const n = newCount();
  flip = !flip;
  document.title = n && flip ? `(${n}) Новый заказ` : TITLE;
  if (!n) return;
  if (S.shop.sound !== false) ring();
  navigator.vibrate?.([200, 100, 200]);
}

setInterval(tick, EVERY_MS);
