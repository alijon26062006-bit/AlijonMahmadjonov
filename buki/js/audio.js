// Озвучка (Web Speech API) и короткие звуки интерфейса (Web Audio, без файлов).

const synth = typeof window !== 'undefined' ? window.speechSynthesis : null;
let voices = [];
if (synth) {
  const load = () => { voices = synth.getVoices(); };
  load();
  synth.addEventListener?.('voiceschanged', load);
}

export const canSpeak = () => !!synth;

export function speak(text, langTag, slow = false) {
  if (!synth || !text) return;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = langTag;
  const prefix = langTag.slice(0, 2);
  const v = voices.find((x) => x.lang === langTag) || voices.find((x) => x.lang?.startsWith(prefix));
  if (v) u.voice = v;
  u.rate = slow ? 0.6 : 0.95;
  synth.speak(u);
}

let ctx = null;
function tone(freq, start, dur, type = 'sine', gain = 0.12) {
  ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.type = type;
  o.frequency.value = freq;
  const t0 = ctx.currentTime + start;
  g.gain.setValueAtTime(0, t0);
  g.gain.linearRampToValueAtTime(gain, t0 + 0.02);
  g.gain.exponentialRampToValueAtTime(0.001, t0 + dur);
  o.connect(g).connect(ctx.destination);
  o.start(t0);
  o.stop(t0 + dur + 0.05);
}

export function sfx(kind, enabled = true) {
  if (!enabled) return;
  try {
    if (kind === 'right') { tone(660, 0, 0.12); tone(990, 0.09, 0.2); }
    else if (kind === 'wrong') { tone(220, 0, 0.18, 'triangle'); tone(180, 0.12, 0.22, 'triangle'); }
    else if (kind === 'done') { [523, 659, 784, 1047].forEach((f, i) => tone(f, i * 0.1, 0.25)); }
    else if (kind === 'tap') tone(440, 0, 0.05, 'sine', 0.05);
  } catch { /* звук недоступен — не страшно */ }
}
