// Звук нового заказа: короткая яркая мелодия, слышно в машине. Синтезируем сами — файлов не нужно.
// Браузер разрешает звук только после первого касания экрана, поэтому включаем его на первом касании.

let ctx = null, out = null;
function unlock() {
  if (ctx) return;
  try {
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -18; comp.knee.value = 6; comp.ratio.value = 6;
    out = ctx.createGain(); out.gain.value = 1.7;
    out.connect(comp).connect(ctx.destination);
  } catch { /* звук недоступен */ }
}
document.addEventListener('pointerdown', unlock);
document.addEventListener('keydown', unlock);

function note(hz, t, len, type, vol) {
  const g = ctx.createGain(), o = ctx.createOscillator();
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(vol, t + 0.01);
  g.gain.exponentialRampToValueAtTime(0.0001, t + len);
  o.type = type; o.frequency.value = hz;
  o.connect(g).connect(out); o.start(t); o.stop(t + len + 0.05);
}
const TUNES = {
  // новый заказ: три восходящие ноты дважды — не спутать ни с чем
  offer: t => [0, 0.55].forEach(d => [880, 1174.7, 1568].forEach((hz, i) => note(hz, t + d + i * 0.11, 0.32, 'triangle', 0.7))),
  // доставлен: мягкий аккорд
  done: t => [523.3, 659.3, 784].forEach((hz, i) => note(hz, t + i * 0.07, 0.9, 'sine', 0.45)),
  // ошибка / отмена: два низких
  bad: t => [392, 311.1].forEach((hz, i) => note(hz, t + i * 0.22, 0.3, 'square', 0.25)),
};

/** Сыграть мелодию. false — звук пока недоступен (не было касания экрана). */
export function play(name = 'offer') {
  unlock();
  if (!ctx) return false;
  if (ctx.state === 'suspended') ctx.resume();
  (TUNES[name] || TUNES.offer)(ctx.currentTime + 0.02);
  return true;
}
