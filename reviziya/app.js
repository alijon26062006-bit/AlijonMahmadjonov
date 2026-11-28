// Ревизия: живой сканер ценников.
// Камера включена постоянно. Когда бирка в рамке перестаёт двигаться, один кадр
// уходит на чтение, и цена прибавляется к сумме. Фото нигде не сохраняются.
//
// Два режима:
//  - внутри Telegram: кадр идёт на наш сервер, счёт общий, ключ Anthropic только на сервере;
//  - в обычном браузере: режим проверки, ключ лежит в этом телефоне и идёт прямо в Anthropic.
import Anthropic from './vendor/anthropic-sdk.js';

const $ = (id) => document.getElementById(id);
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const fmt = (n) => Math.abs(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
const signed = (n) => (n < 0 ? '−' : '+') + fmt(n);
const secs = (s) => s.toFixed(1).replace('.', ',') + ' с';
const hhmm = (d) => d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
const plural = (n, f) => { const a = n % 10, b = n % 100; return a === 1 && b !== 11 ? f[0] : a >= 2 && a <= 4 && (b < 10 || b >= 20) ? f[1] : f[2]; };
const SCAN_WORDS = ['скан', 'скана', 'сканов'];
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

/* ---------- which mode ---------- */
function getInitData() { // Telegram puts the signed launch data into the address after "#"
  try {
    const m = location.hash.match(/tgWebAppData=([^&]+)/);
    if (m) { const v = decodeURIComponent(m[1]); sessionStorage.setItem('rev-init', v); return v; }
    const tg = window.Telegram && window.Telegram.WebApp;
    if (tg && tg.initData) return tg.initData;
    return sessionStorage.getItem('rev-init') || '';
  } catch { return ''; }
}
const initData = getInitData();
const SERVER = !!initData;

/* ---------- storage (this phone only) ---------- */
const LS = {
  get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage may be blocked */ } },
  del(k) { try { localStorage.removeItem(k); } catch { /* ignore */ } },
};
const EMPTY = { sum: 0, scans: 0, minuses: 0, voids: 0, avg: null, uid: 0, log: [] };
let st = SERVER ? { ...EMPTY, log: [] } : Object.assign({ ...EMPTY, log: [] }, LS.get('rev-state', {}));
const opts = Object.assign({ model: 'claude-haiku-5-5', speed: 'normal', sound: 'on', autozoom: 'on', zoom: 1 }, LS.get('rev-opts', {}));
let apiKey = SERVER ? '' : LS.get('rev-key', '');
let me = null; // server mode: { id, name, role, status }

/* ---------- reading the price ---------- */
const SYSTEM = [
  'Ты читаешь цену с ценника или бирки товара в магазине одежды. На фото кадр с камеры телефона.',
  'Цена: число на наклейке от этикет-пистолета, число рядом со словом «Цена», или число, написанное ручкой на бирке или листке бумаги.',
  'Не цена: год на логотипе бренда (1913, SINCE 1985, EST. 1990), размер, состав ткани в процентах, штрихкод, артикул, дата, телефон.',
  'Рукописные буквы «о» внутри числа считай нулями.',
  'Ответь одной строкой без других слов:',
  '- только число цифрами без пробелов, например 3000',
  '- число и знак вопроса, если сомневаешься хотя бы в одной цифре, например 3000?',
  '- минус (-), если ценника нет или цену нельзя прочитать',
].join('\n');

let client = null;
function makeClient() {
  // Test mode only: the key lives in this browser and goes straight to Anthropic.
  client = apiKey ? new Anthropic({ apiKey, dangerouslyAllowBrowser: true, maxRetries: 1, timeout: 20000 }) : null;
}
makeClient();

// Thinking is switched off for speed; each model spells that differently.
const thinkingOff = (model) => (model === 'claude-haiku-5-5' ? { type: 'disabled' } : { type: 'between_tools' });

async function readPrice(b64) {
  const res = await client.messages.create({
    model: opts.model,
    max_tokens: 32,
    thinking: thinkingOff(opts.model),
    output_config: { effort: 'low' },
    system: SYSTEM,
    messages: [{
      role: 'user',
      content: [
        { type: 'image', source: { type: 'base64', media_type: 'image/jpeg', data: b64 } },
        { type: 'text', text: 'Какая цена?' },
      ],
    }],
  });
  if (res.stop_reason === 'refusal') return { price: 0 };
  const block = res.content.find((b) => b.type === 'text');
  return parseAnswer(block ? block.text : '');
}

export function parseAnswer(text) {
  const t = String(text).trim();
  if (!t || t.startsWith('-') || t.startsWith('−')) return { price: 0 };
  const m = t.match(/\d[\d  ]*/);
  if (!m) return { price: 0 };
  const price = parseInt(m[0].replace(/\D/g, ''), 10);
  if (!(price > 0 && price < 100000000)) return { price: 0 };
  return { price, unsure: t.includes('?') };
}

/* ---------- the two stores: same actions, different place for the numbers ---------- */
class StoreError extends Error { constructor(code) { super(code); this.code = code; } }

async function api(path, body) {
  let res;
  try {
    res = await fetch('api/' + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Tg-Init-Data': initData },
      body: JSON.stringify(body || {}),
    });
  } catch { throw new StoreError('offline'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const map = { reader_auth: 'auth', reader_rate: 'rate', reader_network: 'upstream', reader_rejected: 'rejected', reader_other: 'upstream', too_fast: 'rate', pending: 'access', blocked: 'access', auth: 'session' };
    throw new StoreError(map[data.error] || data.error || 'other');
  }
  return data;
}
const fromServer = (e) => ({ id: e.id, amt: e.amt, sec: e.sec, void: e.voided, t: hhmm(new Date(e.at)) });
function applyTotals(t) { st.sum = t.sum; st.scans = t.scans; st.minuses = t.minuses; st.voids = t.voids; st.avg = t.avg; }
function localAverage() { const t = st.log.filter((e) => e.sec).map((e) => e.sec); return t.length ? t.reduce((a, b) => a + b, 0) / t.length : null; }
function localAdd(amt, sec) {
  const e = { id: ++st.uid, t: hhmm(new Date()), amt };
  if (sec) e.sec = Math.round(sec * 10) / 10;
  st.log.unshift(e); st.sum += amt;
  if (amt > 0) st.scans++; else st.minuses++;
  if (st.log.length > 20000) st.log.length = 20000;
  st.avg = localAverage(); LS.set('rev-state', st);
  return e;
}

const serverStore = {
  async scan(b64) {
    const r = await api('scan', { image: b64 });
    if (r.result !== 'ok') return { kind: r.result, price: r.price || 0 };
    const e = fromServer(r.entry); st.log.unshift(e); applyTotals(r.totals);
    return { kind: 'ok', price: r.price, entry: e };
  },
  async add(price, sec) { const r = await api('add', { price, sec }); const e = fromServer(r.entry); st.log.unshift(e); applyTotals(r.totals); return e; },
  async minus(amount) { const r = await api('minus', { amount }); const e = fromServer(r.entry); st.log.unshift(e); applyTotals(r.totals); return e; },
  async void(id) { const r = await api('void', { id }); const e = st.log.find((x) => x.id === id); if (e) e.void = true; applyTotals(r.totals); },
};
const localStore = {
  async scan(b64) {
    const t0 = performance.now();
    let r;
    try { r = await readPrice(b64); } catch (e) {
      if (e instanceof Anthropic.AuthenticationError || e instanceof Anthropic.PermissionDeniedError) throw new StoreError('auth');
      if (e instanceof Anthropic.RateLimitError) throw new StoreError('rate');
      if (e instanceof Anthropic.APIConnectionError) throw new StoreError('offline');
      if (e instanceof Anthropic.APIError && e.status === 400) throw new StoreError('rejected');
      throw new StoreError('other');
    }
    if (!r.price) return { kind: 'none', price: 0 };
    if (r.unsure) return { kind: 'unsure', price: r.price };
    return { kind: 'ok', price: r.price, entry: localAdd(r.price, (performance.now() - t0) / 1000) };
  },
  async add(price, sec) { return localAdd(price, sec); },
  async minus(amount) { return localAdd(-amount); },
  async void(id) {
    const e = st.log.find((x) => x.id === id); if (!e || e.void) return;
    e.void = true; st.sum -= e.amt; st.voids++;
    if (e.amt > 0) st.scans--; else st.minuses--;
    LS.set('rev-state', st);
  },
};
const store = SERVER ? serverStore : localStore;

const ERR = {
  auth: SERVER ? 'Ключ Anthropic на сервере не подошёл. Скажите админу' : 'Ключ не подошёл. Проверьте его в Настройках',
  rate: 'Слишком часто. Жду 5 секунд',
  offline: 'Нет интернета. Бирка не засчитана',
  upstream: 'Claude сейчас не отвечает. Бирка не засчитана',
  rejected: SERVER ? 'Сервер отклонил запрос. Скажите админу' : 'Запрос отклонён. Смените модель в Настройках',
  access: 'У вас нет допуска. Напишите админу',
  session: 'Закройте и откройте мини-апп заново',
};
const errText = (e) => ERR[e && e.code] || 'Не получилось. Попробуйте ещё раз';

/* ---------- sound and vibration ---------- */
let actx = null;
function beep(freqs, dur = 0.07, type = 'sine', vol = 0.12) {
  if (opts.sound !== 'on') return;
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    if (actx.state === 'suspended') actx.resume();
    let t = actx.currentTime;
    for (const f of freqs) {
      const o = actx.createOscillator(), g = actx.createGain();
      o.type = type; o.frequency.value = f;
      g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.001, t + dur);
      o.connect(g).connect(actx.destination); o.start(t); o.stop(t + dur);
      t += dur;
    }
  } catch { /* no audio */ }
}
const buzz = (p) => { try { navigator.vibrate && navigator.vibrate(p); } catch { /* ignore */ } };
const sndShot = () => beep([1500], 0.03, 'square', 0.05);
const sndOk = () => { beep([880, 1320], 0.08); buzz(40); };
const sndBad = () => { beep([220, 180], 0.12, 'sawtooth', 0.1); buzz([60, 60, 60]); };

/* ---------- render ---------- */
function tween(node, to) {
  const from = node._v === undefined ? to : node._v; node._v = to;
  if (reduce || from === to) { node.textContent = fmt(to); return; }
  cancelAnimationFrame(node._raf); const t0 = performance.now();
  (function step(t) {
    const k = Math.min(1, (t - t0) / 380), e = 1 - Math.pow(1 - k, 3);
    node.textContent = fmt(Math.round(from + (to - from) * e));
    if (k < 1) node._raf = requestAnimationFrame(step);
  })(t0);
}
function kick(node, cls) { node.classList.remove(cls); void node.offsetWidth; node.classList.add(cls); }

function renderMe() {
  tween($('mySum'), st.sum); tween($('mySum2'), st.sum);
  $('cScans').textContent = st.scans; $('cScansW').textContent = plural(st.scans, SCAN_WORDS);
  $('cMinus').textContent = st.minuses; $('cVoid').textContent = st.voids;
  const last = st.log.find((e) => e.sec);
  $('cAvg').textContent = st.avg ? secs(st.avg) : '–';
  const sp = $('speed');
  if (last && st.avg) {
    sp.textContent = '';
    sp.append(el('b', 'num', st.scans), ' ' + plural(st.scans, SCAN_WORDS) + ' · посл. ', el('b', 'num', secs(last.sec)), ' · средн. ', el('b', 'num', secs(st.avg)));
  } else if (st.scans) {
    sp.textContent = ''; sp.append(el('b', 'num', st.scans), ' ' + plural(st.scans, SCAN_WORDS));
  } else sp.textContent = 'Скорость появится после первого скана';
}
const ICON = {
  scan: '<path d="M3 12V5a2 2 0 012-2h7l9 9-9 9-9-9z"/><circle cx="8" cy="8" r="1.4"/>',
  minus: '<path d="M5 12h14"/>',
};
function renderLog(newId) { // every value here is a number or a clock time we formatted ourselves
  const has = st.log.length > 0; $('log').hidden = !has; $('logEmpty').hidden = has; $('reset').hidden = !has || SERVER;
  $('log').innerHTML = st.log.slice(0, 80).map((e) => {
    const m = e.amt < 0;
    return '<li class="row' + (m ? ' m' : '') + (e.void ? ' void' : '') + (e.id === newId ? ' new' : '') + '">' +
      '<span class="ic"><svg width="18" height="18" viewBox="0 0 24 24">' + ICON[m ? 'minus' : 'scan'] + '</svg></span>' +
      '<span class="t"><b>' + (m ? 'Минус вручную' : 'Ценник') + '</b><small>' + e.t + (e.sec ? ' · читал ' + secs(e.sec) : '') + (e.void ? ' · отменено' : '') + '</small></span>' +
      '<span class="a">' + signed(e.amt) + '</span>' +
      (e.void ? '<span></span>' : '<button class="u" type="button" data-undo="' + Number(e.id) + '">Отменить</button>') + '</li>';
  }).join('');
}
function refresh(newId, how) {
  renderMe(); renderLog(newId);
  if (how) { kick($('stickerScan'), how); kick($('stickerMine'), how); }
}
async function undo(id) {
  try { await store.void(id); refresh(null, 'shake'); return true; } catch (e) { showToast('Ошибка', errText(e), true, '', 3000); return false; }
}
$('log').addEventListener('click', (ev) => { const b = ev.target.closest('[data-undo]'); if (b) undo(+b.dataset.undo); });
let resetArmed = 0;
$('reset').addEventListener('click', () => {
  if (Date.now() - resetArmed < 4000) {
    st = { ...EMPTY, uid: st.uid, log: [] }; LS.set('rev-state', st); refresh();
    $('reset').textContent = 'Обнулить мой счёт'; resetArmed = 0;
  } else {
    resetArmed = Date.now(); $('reset').textContent = 'Нажмите ещё раз, чтобы стереть всё';
    setTimeout(() => { if (resetArmed) { $('reset').textContent = 'Обнулить мой счёт'; resetArmed = 0; } }, 4000);
  }
});

/* ---------- tabs ---------- */
let tab = 'scan';
document.querySelectorAll('.tabs button').forEach((b) => b.addEventListener('click', () => {
  tab = b.dataset.tab;
  document.querySelectorAll('.tabs button').forEach((x) => x.classList.toggle('on', x === b));
  document.querySelectorAll('.view').forEach((v) => v.classList.toggle('on', v.id === 'v-' + tab));
  if (tab === 'admin') loadAdmin();
}));
function openTab(name) { document.querySelector('.tabs [data-tab="' + name + '"]').click(); }

/* ---------- camera ---------- */
const cam = $('cam'), video = $('video'), ret = $('ret'), toast = $('toast');
let stream = null, running = false, userPaused = false, pending = null, lastScan = null, wake = null;
let inflight = 0, toastTimer = 0, blockedUntil = 0;

function setStatus(text) { $('statusText').textContent = text; }
function setMode(mode) { cam.classList.remove('idle', 'held', 'paused'); if (mode) cam.classList.add(mode); }
const canRead = () => SERVER || !!client;

async function startCamera() {
  if (!canRead()) { openTab('set'); showKeyMsg('Сначала вставьте ключ Anthropic', false); return; }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return startError('Здесь нет доступа к камере. Обновите Telegram или откройте ссылку в Chrome или Safari.');
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)(); actx.resume();
  } catch { /* no audio */ }
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      // Full HD: a far tag still has enough pixels to read after cropping
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } },
    });
  } catch (e) {
    const n = e && e.name;
    return startError(n === 'NotAllowedError' ? 'Нет доступа к камере. Разрешите камеру и нажмите ещё раз.'
      : n === 'NotFoundError' ? 'Камера не найдена.' : 'Камера не включилась. Закройте другие приложения с камерой и попробуйте ещё раз.');
  }
  video.srcObject = stream;
  try { await video.play(); } catch { /* autoplay may need the tap we already have */ }
  $('start').hidden = true; $('camctl').hidden = false; $('zoomctl').hidden = false;
  running = true; userPaused = false; resetDetector();
  setMode(''); setStatus('Ищу ценник…');
  const track = stream.getVideoTracks()[0];
  const caps = track.getCapabilities ? track.getCapabilities() : {};
  $('torch').hidden = !caps.torch;
  if (caps.focusMode && caps.focusMode.includes('continuous')) track.applyConstraints({ advanced: [{ focusMode: 'continuous' }] }).catch(() => {});
  zoomInit(caps);
  try { wake = await navigator.wakeLock.request('screen'); } catch { /* optional */ }
}
function startError(msg) {
  const p = $('startText'); p.textContent = msg; p.classList.add('err');
  $('start').hidden = false; $('camctl').hidden = true; $('zoomctl').hidden = true; setMode('idle'); setStatus('Камера выключена');
}
function stopCamera() {
  running = false;
  if (stream) stream.getTracks().forEach((t) => t.stop());
  stream = null; video.srcObject = null; eyeReset();
  try { wake && wake.release(); } catch { /* ignore */ } wake = null;
}
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { if (running) { stopCamera(); cam.dataset.resume = '1'; } }
  else if (cam.dataset.resume) { delete cam.dataset.resume; startCamera(); }
});
$('startBtn').addEventListener('click', startCamera);

let torchOn = false;
$('torch').addEventListener('click', async () => {
  try {
    torchOn = !torchOn;
    await stream.getVideoTracks()[0].applyConstraints({ advanced: [{ torch: torchOn }] });
    $('torch').classList.toggle('act', torchOn);
  } catch { torchOn = false; $('torch').hidden = true; }
});
$('pause').addEventListener('click', () => {
  userPaused = !userPaused; $('pause').textContent = userPaused ? 'Продолжить' : 'Пауза';
  $('pause').classList.toggle('act', userPaused);
  if (userPaused) { setMode('paused'); setStatus('Пауза'); } else { resetDetector(); setMode(''); setStatus('Ищу ценник…'); }
});
$('shot').addEventListener('click', () => { if (running && !pending) capture(); });

/* ---------- smart zoom ---------- */
// 1. findTag: looks for the tag itself (a light, colourless patch) inside the reticle.
// 2. The shot is cut tightly around it at full camera resolution, so a small or far tag
//    reaches Claude large and sharp instead of as a speck in a wide picture.
// 3. autoZoom: when the tag is small, the camera zooms in by itself; when the tag is gone, it zooms back.
const zoom = { native: false, min: 1, max: 4, base: 1, value: 1, settleUntil: 0, lastAuto: 0, lastSeen: 0 };
const clampZoom = (v) => Math.min(zoom.max, Math.max(zoom.min, v));
function zoomInit(caps) {
  const z = caps && caps.zoom;
  zoom.native = !!(z && z.max > z.min);
  zoom.min = zoom.native ? Math.max(1, z.min) : 1;
  zoom.max = zoom.native ? Math.min(z.max, 8) : 4;
  zoom.value = 1; zoom.base = clampZoom(opts.zoom || 1);
  eyeReset();
  applyZoom(zoom.base); paintZoom();
}
function applyZoom(v) {
  v = clampZoom(v);
  if (Math.abs(v - zoom.value) < 0.02) return;
  zoom.value = v; zoom.settleUntil = performance.now() + (zoom.native ? 450 : 160);
  det.prev = null; det.still = 0; det.calm = 0; det.ema = 99;
  if (det.state === 'held') det.rebase = true; // same tag, new picture: do not take it for a new tag
  if (zoom.native && stream) {
    stream.getVideoTracks()[0].applyConstraints({ advanced: [{ zoom: v }] }).catch(() => {
      zoom.native = false; zoom.max = 4; zoom.value = clampZoom(zoom.value);
    });
  }
  paintZoom();
}
function setBaseZoom(v) { zoom.base = clampZoom(v); opts.zoom = zoom.base; LS.set('rev-opts', opts); applyZoom(zoom.base); paintZoom(); }
function paintZoom() {
  document.querySelectorAll('#zoomctl [data-z]').forEach((b) => {
    const z = +b.dataset.z; b.hidden = z > zoom.max + 0.01; b.classList.toggle('on', Math.abs(z - zoom.base) < 0.05);
  });
}
$('zoomctl').addEventListener('click', (ev) => { const b = ev.target.closest('[data-z]'); if (b) setBaseZoom(+b.dataset.z); });
let pinch = null; // two fingers on the camera picture change the zoom
cam.addEventListener('touchstart', (ev) => { if (ev.touches.length === 2) pinch = { d: touchDist(ev), z: zoom.base }; }, { passive: true });
cam.addEventListener('touchmove', (ev) => { if (pinch && ev.touches.length === 2) setBaseZoom(pinch.z * touchDist(ev) / pinch.d); }, { passive: true });
cam.addEventListener('touchend', () => { pinch = null; }, { passive: true });
function touchDist(ev) { const a = ev.touches[0], b = ev.touches[1]; return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY) || 1; }

const B = 48;
const bcv = document.createElement('canvas'); bcv.width = bcv.height = B;
const bctx = bcv.getContext('2d', { willReadFrequently: true });
const bMask = new Uint8Array(B * B), bSeen = new Uint8Array(B * B), bStack = new Int32Array(B * B);
// Returns the tag as fractions of the reticle crop ({x, y, w, h}), or null when nothing tag-like is there.
// Paper is light and has almost no colour. A white floor or wall next to the tag is light too and can
// merge with it into one big patch, so the search is repeated with a stricter brightness bar until the
// tag stands apart: price tags are usually the brightest compact thing in the picture.
const bLum = new Float32Array(B * B), bSorted = new Float32Array(B * B);
function findTag() {
  const r = cropRect(); if (!r) return null;
  bctx.drawImage(video, r.x, r.y, r.w, r.h, 0, 0, B, B);
  const d = bctx.getImageData(0, 0, B, B).data, n = B * B;
  let sum = 0, sq = 0;
  for (let i = 0, j = 0; j < n; i += 4, j++) {
    const l = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
    const mx = Math.max(d[i], d[i + 1], d[i + 2]), mn = Math.min(d[i], d[i + 1], d[i + 2]);
    bLum[j] = (mx - mn) / (mx || 1) < 0.28 ? l : 0; // coloured pixels can never be paper
    sum += l; sq += l * l;
  }
  const mean = sum / n, sd = Math.sqrt(Math.max(0, sq / n - mean * mean));
  bSorted.set(bLum); bSorted.sort();
  const pct = (q) => bSorted[Math.min(n - 1, Math.floor(n * q))];
  const bars = [Math.max(120, mean + 0.45 * sd), pct(0.7), pct(0.8), pct(0.87), pct(0.92)].filter((v, i, a) => v >= 120 && (i === 0 || v > a[i - 1] + 3));
  let fallback = null;
  for (const bar of bars) {
    const tag = brightest(bar);
    if (!tag) break;
    if (tag.w * tag.h < 0.42 || tag.w < 0.75 || tag.h < 0.75) return tag; // stands apart from the background
    if (!fallback) fallback = tag;
  }
  return fallback;
}
function brightest(bar) { // the best light, solid patch above the brightness bar
  const n = B * B;
  for (let j = 0; j < n; j++) { bMask[j] = bLum[j] > bar ? 1 : 0; bSeen[j] = 0; }
  let best = null, bestScore = 0;
  for (let start = 0; start < n; start++) {
    if (!bMask[start] || bSeen[start]) continue;
    let top = 0, area = 0, x0 = B, x1 = 0, y0 = B, y1 = 0;
    bStack[top++] = start; bSeen[start] = 1;
    while (top) {
      const j = bStack[--top], x = j % B, y = (j - x) / B;
      area++; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
      if (x > 0 && bMask[j - 1] && !bSeen[j - 1]) { bSeen[j - 1] = 1; bStack[top++] = j - 1; }
      if (x < B - 1 && bMask[j + 1] && !bSeen[j + 1]) { bSeen[j + 1] = 1; bStack[top++] = j + 1; }
      if (y > 0 && bMask[j - B] && !bSeen[j - B]) { bSeen[j - B] = 1; bStack[top++] = j - B; }
      if (y < B - 1 && bMask[j + B] && !bSeen[j + B]) { bSeen[j + B] = 1; bStack[top++] = j + B; }
    }
    const bw = x1 - x0 + 1, bh = y1 - y0 + 1;
    if (area < n * 0.012) continue;                    // a speck
    if (bw > B * 0.92 && bh > B * 0.92) continue;      // the whole picture is light: a wall or a floor, not a tag
    if (area / (bw * bh) < 0.4) continue;              // tags are solid patches, not thin streaks
    const dist = Math.hypot((x0 + x1 + 1) / 2 / B - 0.5, (y0 + y1 + 1) / 2 / B - 0.5);
    const score = area * (1 - Math.min(0.9, dist * 1.4)); // prefer the big patch near the middle
    if (score > bestScore) { bestScore = score; best = { x: x0 / B, y: y0 / B, w: bw / B, h: bh / B }; }
  }
  return best;
}
function trackTag(tag) { // how many checks in a row the tag stayed in about the same place
  const prev = zoom.prevTag; zoom.prevTag = tag;
  const steady = tag && prev && Math.hypot(tag.x + tag.w / 2 - prev.x - prev.w / 2, tag.y + tag.h / 2 - prev.y - prev.h / 2) < 0.12
    && Math.abs(tag.w - prev.w) < 0.3 * tag.w;
  zoom.steady = steady ? (zoom.steady || 0) + 1 : 0;
}

/* ---------- the eye: the picture itself moves in on the tag, like eyes looking closer ---------- */
// Only what is shown on screen moves. Detection and the shot always use the full camera picture,
// so the eye can never cut the price off or confuse the double-count protection.
const EYE_MAX = 4;          // the closest the eye goes, relative to the normal view
const eye = { mode: 'base', cur: null, target: null, tag: null, lost: 0, raf: 0, last: 0 };
function geom() {
  const vw = video.videoWidth, vh = video.videoHeight; if (!vw || !vh) return null;
  const cr = cam.getBoundingClientRect(), rr = ret.getBoundingClientRect();
  const scale = Math.max(cr.width / vw, cr.height / vh);
  const pw = rr.width * (1 + 2 * PAD), ph = rr.height * (1 + 2 * PAD);
  return {
    W: cr.width, H: cr.height, scale, offX: (vw * scale - cr.width) / 2, offY: (vh * scale - cr.height) / 2,
    P: { x: rr.left - cr.left + rr.width / 2 - pw / 2, y: rr.top - cr.top + rr.height / 2 - ph / 2, w: pw, h: ph },
  };
}
function searchOnScreen(g) { // the area the scanner analyses, where it sits on the unmoved picture
  const r = cropRect(); if (!r) return null;
  return { x: r.x * g.scale - g.offX, y: r.y * g.scale - g.offY, w: r.w * g.scale, h: r.h * g.scale };
}
function viewFor(g, S, tagRect) { // the piece of the picture to stretch over the reticle
  const A = g.P.w / g.P.h;
  let cx = S.x + S.w / 2, cy = S.y + S.h / 2, w = S.w;
  if (tagRect) {
    const m = 0.14; // a margin round the tag so its edges stay in view
    let tw = tagRect.w * (1 + 2 * m), th = tagRect.h * (1 + 2 * m);
    if (tw / th < A) tw = th * A;
    cx = tagRect.x + tagRect.w / 2; cy = tagRect.y + tagRect.h / 2;
    w = Math.min(S.w, Math.max(S.w / EYE_MAX, tw));
    if (S.w / w < 1.3) { w = S.w; cx = S.x + S.w / 2; cy = S.y + S.h / 2; } // the tag is already big: no point moving
  }
  return { x: cx - w / 2, y: cy - w / A / 2, w };
}
function transformFor(g, V) {
  const s = g.P.w / V.w;
  let tx = g.P.x - V.x * s, ty = g.P.y - V.y * s;
  // never pull the picture away from the screen edge: no empty strips
  tx = Math.min(0, Math.max(g.W - g.W * s, tx)); ty = Math.min(0, Math.max(g.H - g.H * s, ty));
  return { s, tx, ty };
}
function eyeReset() {
  eye.mode = 'base'; eye.cur = null; eye.target = null; eye.tag = null; eye.lost = 0;
  video.style.transform = ''; $('tagbox').hidden = true; $('tagbox').classList.remove('lock');
}
function eyeSettled() {
  if (!eye.cur || !eye.target) return true;
  return Math.abs(eye.cur.x - eye.target.x) < 2 && Math.abs(eye.cur.y - eye.target.y) < 2 && Math.abs(eye.cur.w - eye.target.w) < 2;
}
function eyeUpdate(tag) { // called on every check with what the scanner sees now
  const g = geom(); if (!g) return;
  const S = searchOnScreen(g); if (!S) return;
  if (tag) {
    eye.lost = 0;
    eye.tag = { x: S.x + tag.x * S.w, y: S.y + tag.y * S.h, w: tag.w * S.w, h: tag.h * S.h };
  } else if (++eye.lost >= 4) eye.tag = null; // a few checks of grace: a blink of glare should not jerk the view
  const wantTag = opts.autozoom === 'on' && eye.tag && (zoom.steady >= 2 || (eye.mode === 'tag' && zoom.steady >= 1) || det.state === 'held');
  const next = viewFor(g, S, wantTag ? eye.tag : null);
  let switched = false;
  if (wantTag && eye.mode !== 'tag') {
    eye.mode = 'tag'; switched = true; kick($('tagbox'), 'lock');
    if (det.state === 'armed') setStatus('Вижу ценник…');
  } else if (!wantTag && eye.mode !== 'base') { eye.mode = 'base'; switched = true; }
  const t = eye.target;
  // follow the tag like eyes do, but ignore tiny trembling
  if (!t || switched || eye.mode === 'base' || Math.hypot(next.x + next.w / 2 - t.x - t.w / 2, next.y + next.w / 2 - t.y - t.w / 2) > t.w * 0.08 || Math.abs(next.w - t.w) > t.w * 0.18) eye.target = next;
  if (!eye.cur) eye.cur = { ...eye.target };
  if (!eye.raf) eye.raf = requestAnimationFrame(eyeFrame);
}
function eyeFrame(now) {
  eye.raf = 0;
  const g = geom(); if (!g || !eye.cur || !eye.target || !running) return;
  const dt = Math.min(80, now - (eye.last || now)); eye.last = now;
  const k = reduce ? 1 : 1 - Math.exp(-dt / 95);
  for (const key of ['x', 'y', 'w']) eye.cur[key] += (eye.target[key] - eye.cur[key]) * k;
  const { s, tx, ty } = transformFor(g, eye.cur);
  video.style.transform = s > 1.002 ? 'translate(' + tx.toFixed(1) + 'px,' + ty.toFixed(1) + 'px) scale(' + s.toFixed(4) + ')' : '';
  const box = $('tagbox');
  if (eye.tag) { // the green frame sits on the tag wherever the picture has moved to
    box.hidden = false; box.classList.toggle('held', det.state === 'held');
    box.style.left = (eye.tag.x * s + tx) + 'px'; box.style.top = (eye.tag.y * s + ty) + 'px';
    box.style.width = (eye.tag.w * s) + 'px'; box.style.height = (eye.tag.h * s) + 'px';
  } else box.hidden = true;
  $('zoomNow').hidden = s < 1.15 * (zoom.native ? 1 : zoom.base);
  $('zoomNow').textContent = 'смотрю ' + (s * (zoom.native ? zoom.value : 1)).toFixed(1).replace('.', ',') + '×';
  if (!eyeSettled() || eye.tag) eye.raf = requestAnimationFrame(eyeFrame);
  else eye.last = 0;
}

function autoZoom(tag, t) { // true when the zoom was changed on this check
  // Only the camera's own zoom adds real detail. Without it the tight cut around the tag
  // already does the magnifying, and enlarging the picture further would only risk cutting the price off.
  if (opts.autozoom !== 'on' || !zoom.native || t - zoom.lastAuto < 700) return false;
  const top = Math.min(zoom.max, zoom.base * 3);
  if (tag) {
    const size = Math.max(tag.w, tag.h * 0.8);
    const whole = tag.x > 0.03 && tag.y > 0.03 && tag.x + tag.w < 0.97 && tag.y + tag.h < 0.97; // the tag is fully in view
    if (zoom.steady >= 3 && whole && size < 0.36 && tag.w * tag.h > 0.02 && zoom.value < top - 0.05) { // small and far: come closer
      zoom.lastAuto = t; zoom.steady = 0; applyZoom(Math.min(top, zoom.value * Math.min(1.8, Math.max(1.2, 0.5 / size)))); setStatus('Приближаю ценник…'); return true;
    }
    if ((tag.w > 0.85 || tag.h > 0.9) && zoom.value > zoom.base + 0.05) { zoom.lastAuto = t; applyZoom(Math.max(zoom.base, zoom.value / 1.3)); return true; }
  } else if (zoom.value > zoom.base + 0.05 && t - zoom.lastSeen > 1800) { // the tag is gone: back to the wide view
    zoom.lastAuto = t; applyZoom(zoom.base); setStatus('Ищу ценник…'); return true;
  }
  return false;
}

// The frame that goes to Claude: cut around the tag, the sharpest of three taken 70 ms apart.
const scv = document.createElement('canvas'); scv.width = scv.height = 64;
const sctx = scv.getContext('2d', { willReadFrequently: true });
const keep = document.createElement('canvas'); const kctx = keep.getContext('2d');
function shotRect() {
  const r = cropRect(); if (!r) return null;
  const tag = findTag(); if (!tag) return r;
  const mx = tag.w * 0.18, my = tag.h * 0.18; // a margin, in case the edge of the tag was cut off
  const x = Math.max(0, tag.x - mx), y = Math.max(0, tag.y - my);
  const w = Math.min(1 - x, tag.w + 2 * mx), h = Math.min(1 - y, tag.h + 2 * my);
  return { x: r.x + x * r.w, y: r.y + y * r.h, w: w * r.w, h: h * r.h };
}
function sharpness(r) { // how much fine detail the piece has: blurred frames score low
  sctx.drawImage(video, r.x, r.y, r.w, r.h, 0, 0, 64, 64);
  const d = sctx.getImageData(0, 0, 64, 64).data; let s = 0;
  const g = (i) => d[i * 4] + d[i * 4 + 1] + d[i * 4 + 2];
  for (let y = 1; y < 63; y++) for (let x = 1; x < 63; x++) { const i = y * 64 + x; s += Math.abs(4 * g(i) - g(i - 1) - g(i + 1) - g(i - 64) - g(i + 64)); }
  return s;
}
async function sharpestShot() {
  let best = -1;
  for (let i = 0; i < 3; i++) {
    const r = shotRect();
    if (r) {
      const sharp = sharpness(r);
      if (sharp > best) {
        best = sharp;
        const long = Math.max(r.w, r.h);
        const k = long > 768 ? 768 / long : long < 384 ? 384 / long : 1; // shrink big pieces, enlarge tiny ones
        keep.width = Math.round(r.w * k); keep.height = Math.round(r.h * k);
        kctx.imageSmoothingQuality = 'high';
        kctx.drawImage(video, r.x, r.y, r.w, r.h, 0, 0, keep.width, keep.height);
      }
    }
    if (i < 2) await new Promise((res) => setTimeout(res, 70));
  }
  if (best < 0) throw new StoreError('other');
  const url = keep.toDataURL('image/jpeg', 0.78);
  const seen = $('sent'); seen.src = url; seen.hidden = false; clearTimeout(seen._t); seen._t = setTimeout(() => { seen.hidden = true; }, 2500);
  return url.split(',')[1];
}

/* ---------- auto-capture: shoot once when the tag holds still ---------- */
// The reticle area is shrunk to a tiny grey thumbnail a few times a second.
// "armed": wait until consecutive thumbnails barely differ, then shoot one frame.
// "held":  the same tag is still in the frame, so do nothing until the picture
//          changes a lot (the tag was taken away). This is what stops double counting.
const SPEED = {
  // still/need: how calm the picture must be, and for how many checks, before shooting.
  // move/gone: how different the picture must become before the next tag may be shot.
  // A shaky hand on the same tag measured about 15-20 here, a real swap 80+, so "move" sits between.
  fast: { still: 7, need: 2, move: 26, gone: 2 },
  normal: { still: 5, need: 3, move: 30, gone: 3 },
  careful: { still: 3.5, need: 5, move: 34, gone: 3 },
};
const T = 24, MAX_INFLIGHT = 3, MIN_GAP_MS = 600, PAD = 0.14;
const tcv = document.createElement('canvas'); tcv.width = tcv.height = T;
const tctx = tcv.getContext('2d', { willReadFrequently: true });
const ccv = document.createElement('canvas'); const cctx = ccv.getContext('2d');
let det = { state: 'armed', prev: null, ref: null, still: 0, calm: 0, ema: 99, moved: 0, lastShot: 0 };
function resetDetector() { det = { state: 'armed', prev: null, ref: null, still: 0, calm: 0, ema: 99, moved: 0, lastShot: det.lastShot || 0 }; }
function rearm() { det.state = 'armed'; det.still = 0; det.calm = 0; det.ema = 99; det.peak = 0; }

function cropRect() { // reticle (plus a margin) in video pixels; the video is drawn with object-fit: cover
  const vw = video.videoWidth, vh = video.videoHeight; if (!vw || !vh) return null;
  const cr = cam.getBoundingClientRect(), rr = ret.getBoundingClientRect();
  const scale = Math.max(cr.width / vw, cr.height / vh);
  const offX = (vw * scale - cr.width) / 2, offY = (vh * scale - cr.height) / 2;
  const dz = zoom.native ? 1 : zoom.value; // digital zoom: the same reticle covers a smaller piece of the picture
  const cx = (rr.left + rr.width / 2 - cr.left + offX) / scale, cy = (rr.top + rr.height / 2 - cr.top + offY) / scale;
  let w = rr.width * (1 + 2 * PAD) / scale / dz, h = rr.height * (1 + 2 * PAD) / scale / dz;
  let x = cx - w / 2, y = cy - h / 2;
  x = Math.max(0, x); y = Math.max(0, y); w = Math.min(vw - x, w); h = Math.min(vh - y, h);
  return w > 8 && h > 8 ? { x, y, w, h } : null;
}
function thumb() {
  const r = cropRect(); if (!r) return null;
  tctx.imageSmoothingQuality = 'high';
  tctx.drawImage(video, r.x, r.y, r.w, r.h, 0, 0, T, T);
  const d = tctx.getImageData(0, 0, T, T).data, g = new Float32Array(T * T);
  let sum = 0;
  for (let i = 0, j = 0; i < d.length; i += 4, j++) { g[j] = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]; sum += g[j]; }
  const mean = sum / g.length; let v = 0;
  for (let j = 0; j < g.length; j++) v += (g[j] - mean) * (g[j] - mean);
  return { g, sd: Math.sqrt(v / g.length) };
}
function diff(a, b) { let s = 0; for (let i = 0; i < a.length; i++) s += Math.abs(a[i] - b[i]); return s / a.length; }

// ?debug=1 shows the detector numbers on screen, for tuning on a real phone
const dbgEl = /[?&]debug/.test(location.search) ? Object.assign(document.createElement('div'), { style: 'position:absolute;left:8px;top:52px;font:11px monospace;color:#0f0;background:rgba(0,0,0,.6);padding:3px 6px;border-radius:6px;z-index:3' }) : null;
if (dbgEl) cam.appendChild(dbgEl);
function dbg(state, d, sd) { if (dbgEl) dbgEl.textContent = state + ' d=' + d.toFixed(1) + ' sd=' + sd.toFixed(0) + ' q=' + inflight; }

let sheetOpen = false, gated = false;
function tick() {
  if (!running || userPaused || pending || gated || tab !== 'scan' || sheetOpen || document.hidden) return;
  if (video.readyState < 2) return;
  const p = SPEED[opts.speed] || SPEED.normal, t = performance.now();
  if (t < zoom.settleUntil) { det.prev = null; return; } // the picture jumps while the zoom changes
  const th = thumb(); if (!th) return;
  if (det.rebase) { det.rebase = false; if (det.state === 'held') det.ref = th.g; }
  const tag = findTag(); trackTag(tag); eyeUpdate(tag);
  if (tag) zoom.lastSeen = t;
  if (det.state === 'armed' && autoZoom(tag, t)) { det.prev = null; return; }
  if (det.state === 'armed') {
    const d = det.prev ? diff(th.g, det.prev) : 99;
    det.still = d < p.still ? det.still + 1 : 0;
    // a shaky hand never gets fully still: also accept "mostly still" held a little longer
    det.ema = det.ema * 0.6 + d * 0.4;
    det.calm = det.ema < p.still * 1.7 ? det.calm + 1 : 0;
    dbg(det.state, d, th.sd);
    if ((det.still >= p.need || det.calm >= p.need + 4) && th.sd > 10 && (!tag || eyeSettled()) && inflight < MAX_INFLIGHT && t - det.lastShot > MIN_GAP_MS && t > blockedUntil) {
      det.ref = th.g; det.state = 'held'; det.moved = 0; capture();
    }
  } else {
    const dr = diff(th.g, det.ref);
    det.moved = dr > p.move ? det.moved + 1 : 0;
    det.peak = Math.max(det.peak || 0, dr);
    dbg(det.state, dr, th.sd);
    if (det.moved >= p.gone) { if (dbgEl) console.log('REARM peak=' + det.peak.toFixed(1) + ' at ' + (performance.now() / 1000).toFixed(1)); rearm(); eye.tag = null; eye.lost = 9; setMode(''); setStatus(inflight ? 'Читаю… Подносите следующую' : 'Ищу ценник…'); }
  }
  det.prev = th.g;
}
setInterval(tick, 90);

function updateQueue() { const q = $('queue'); q.hidden = inflight === 0; q.textContent = 'читаю: ' + inflight; }

function capture() {
  if (!cropRect() || !canRead()) return;
  const th = thumb(); if (th) det.ref = th.g;
  det.state = 'held'; det.moved = 0; det.peak = 0; det.lastShot = performance.now();
  kick($('flash'), 'go'); sndShot();
  setMode('held'); setStatus('Снято. Читаю цену…');
  inflight++; updateQueue();
  const t0 = performance.now();
  sharpestShot().then((b64) => store.scan(b64)).then((r2) => onRead(r2, (performance.now() - t0) / 1000), onReadError)
    .finally(() => { inflight--; updateQueue(); });
}

function showToast(amtText, sub, neg, mode, ms) { // mode: 'undo' | 'confirm' | ''
  $('toastAmt').textContent = amtText; $('toastSub').textContent = sub; toast.classList.toggle('neg', !!neg);
  $('toastUndo').hidden = mode !== 'undo'; $('toastYes').hidden = mode !== 'confirm'; $('toastNo').hidden = mode !== 'confirm';
  toast.classList.add('on'); clearTimeout(toastTimer);
  if (ms) toastTimer = setTimeout(() => toast.classList.remove('on'), ms);
}
function fly(price) {
  if (reduce) return;
  const a = ret.getBoundingClientRect(), b = $('mySum').getBoundingClientRect();
  const node = el('div', 'fly', '+' + fmt(price)); document.body.appendChild(node);
  const w = node.offsetWidth, h = node.offsetHeight, x0 = a.left + a.width / 2 - w / 2, y0 = a.top + a.height / 2 - h / 2;
  node.style.left = x0 + 'px'; node.style.top = y0 + 'px';
  const dx = b.left + b.width / 2 - w / 2 - x0, dy = b.top + b.height / 2 - h / 2 - y0;
  node.animate([{ transform: 'scale(.6)', opacity: 0 }, { transform: 'scale(1.25)', opacity: 1, offset: 0.2 },
    { transform: 'translate(' + dx + 'px,' + dy + 'px) scale(.7)', opacity: 0.9 }], { duration: 420, easing: 'cubic-bezier(.5,0,.2,1)' }).onfinish = () => node.remove();
}
function credited(entry, price, sec) {
  fly(price); sndOk(); lastScan = entry; refresh(entry.id, 'bump');
  showToast('+' + fmt(price), 'Засчитано за ' + secs(sec), false, 'undo', 4000);
}
function onRead(r, sec) {
  if (r.kind === 'ok') credited(r.entry, r.price, sec);
  else if (r.kind === 'unsure') { // stop and ask: a wrong digit costs more than a second
    pending = { price: r.price, sec }; sndBad(); setMode('paused'); setStatus('Проверьте цену');
    showToast(fmt(r.price) + '?', 'Не уверен в цифрах', true, 'confirm');
  } else { sndBad(); showToast('Не прочитал', 'Уберите и поднесите бирку ещё раз · ' + secs(sec), true, '', 2500); }
}
function onReadError(e) {
  sndBad();
  if (e.code === 'rate') blockedUntil = performance.now() + 5000;
  if (e.code === 'auth' || e.code === 'rejected' || e.code === 'access' || e.code === 'session') { if (!userPaused) $('pause').click(); }
  if (e.code === 'access') loadMe();
  showToast('Ошибка', errText(e), true, '', 4000);
}

$('toastUndo').addEventListener('click', async () => {
  if (!lastScan) return; const e = lastScan; lastScan = null;
  if (await undo(e.id)) showToast('−' + fmt(e.amt), 'Отменено', true, '', 2000);
});
function endConfirm() { // keep the tag "held" so the same one is not shot again right away
  pending = null; resetDetector();
  const th = thumb(); if (th) { det.ref = th.g; det.state = 'held'; setMode('held'); } else setMode('');
  setStatus('Берите следующую');
}
$('toastYes').addEventListener('click', async () => {
  if (!pending) return; const p = pending; endConfirm();
  try { credited(await store.add(p.price, p.sec), p.price, p.sec); } catch (e) { sndBad(); showToast('Ошибка', errText(e), true, '', 4000); }
});
$('toastNo').addEventListener('click', () => { if (!pending) return; endConfirm(); showToast('Не засчитано', 'Уберите и поднесите бирку ещё раз', true, '', 2000); });

/* ---------- minus sheet ---------- */
let val = 0;
const keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '00', '0', 'del'];
$('keys').innerHTML = keys.map((k) => '<button class="key" type="button" data-k="' + k + '"' + (k === 'del' ? ' aria-label="Стереть"' : '') + '>' +
  (k === 'del' ? '<svg width="24" height="24" viewBox="0 0 24 24" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6h11v12H9l-6-6z"/><path d="M12.5 9.5l5 5M17.5 9.5l-5 5"/></svg>' : k) + '</button>').join('');
function showVal() {
  $('disp').textContent = '−' + fmt(val); $('disp').classList.toggle('zero', !val);
  $('go').disabled = !val; $('go').textContent = val ? 'Вычесть ' + fmt(val) : 'Вычесть';
}
$('keys').addEventListener('click', (ev) => {
  const b = ev.target.closest('[data-k]'); if (!b) return; const k = b.dataset.k;
  if (k === 'del') val = Math.floor(val / 10); else { const s = String(val || '') + k; if (s.length <= 8) val = parseInt(s, 10) || 0; }
  showVal();
});
function openSheet(o) { sheetOpen = o; $('scrim').classList.toggle('on', o); if (o) { val = 0; showVal(); } else resetDetector(); }
$('openMinus').addEventListener('click', () => openSheet(true));
$('scrim').addEventListener('click', (ev) => { if (ev.target === $('scrim')) openSheet(false); });
$('go').addEventListener('click', async () => {
  if (!val) return; const v = val; $('go').disabled = true;
  try {
    const e = await store.minus(v); openSheet(false); lastScan = null; refresh(e.id, 'shake');
    showToast('−' + fmt(v), 'Вычтено', true, '', 2200);
  } catch (e) { openSheet(false); showToast('Ошибка', errText(e), true, '', 4000); }
});

/* ---------- settings ---------- */
function showKeyMsg(text, ok) { const m = $('keyMsg'); m.hidden = !text; m.textContent = text || ''; m.className = 'msg ' + (ok ? 'ok' : 'bad'); }
function renderKey() {
  $('keyState').textContent = apiKey ? 'Ключ сохранён: …' + apiKey.slice(-4) : 'Ключ не задан. Без него сканер не читает ценники.';
  $('keyDel').hidden = !apiKey;
}
$('keySave').addEventListener('click', async () => {
  const v = $('keyInput').value.trim();
  if (!v) return showKeyMsg('Вставьте ключ в поле', false);
  apiKey = v; makeClient(); showKeyMsg('Проверяю…', true);
  try {
    await client.models.retrieve(opts.model);
    LS.set('rev-key', apiKey); $('keyInput').value = ''; renderKey(); showKeyMsg('Ключ работает. Откройте вкладку «Сканер»', true);
  } catch (e) {
    const bad = e instanceof Anthropic.AuthenticationError || e instanceof Anthropic.PermissionDeniedError;
    if (bad) { apiKey = LS.get('rev-key', ''); makeClient(); showKeyMsg('Ключ не подошёл. Скопируйте его целиком с console.anthropic.com', false); }
    else { LS.set('rev-key', apiKey); $('keyInput').value = ''; renderKey(); showKeyMsg('Ключ сохранён, но проверить не удалось: нет связи', false); }
  }
});
$('keyDel').addEventListener('click', () => { apiKey = ''; LS.del('rev-key'); makeClient(); renderKey(); showKeyMsg('Ключ удалён с этого телефона', true); });
function seg(id, key) {
  const box = $(id);
  const paint = () => box.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b.dataset.v === opts[key]));
  box.addEventListener('click', (ev) => { const b = ev.target.closest('[data-v]'); if (!b) return; opts[key] = b.dataset.v; LS.set('rev-opts', opts); paint(); resetDetector(); });
  paint();
}
seg('segModel', 'model'); seg('segSpeed', 'speed'); seg('segSound', 'sound'); seg('segZoom', 'autozoom');

/* ---------- server mode: who am I, am I allowed in ---------- */
let gateTimer = 0;
function gate(title, text) { // covers the app while the person has no access
  gated = !!title; $('gate').hidden = !title;
  if (title) { $('gateTitle').textContent = title; $('gateText').textContent = text; if (running) stopCamera(); }
}
async function loadMe() {
  clearTimeout(gateTimer);
  let data;
  try { data = await api('me'); } catch (e) {
    gate('Нет связи с сервером', e.code === 'session' ? 'Закройте мини-апп и откройте его заново из бота.' : 'Проверьте интернет. Пробую ещё раз…');
    if (e.code !== 'session') gateTimer = setTimeout(loadMe, 4000);
    return;
  }
  me = data.user;
  $('who').textContent = me.name; $('rate').hidden = false; $('rate').textContent = data.revision.title;
  $('tabAdmin').hidden = me.role !== 'admin';
  if (me.status === 'active') {
    gate(null); st.log = data.log.map(fromServer); applyTotals(data.totals); refresh();
  } else if (me.status === 'pending') {
    gate('Заявка отправлена', 'Админ получил сообщение. Как только он вас допустит, сканер откроется сам.');
    gateTimer = setTimeout(loadMe, 5000);
  } else gate('Доступ закрыт', 'Админ закрыл вам доступ к ревизии.');
}

/* ---------- admin ---------- */
const rows = new Map();
let adminTimer = 0, newArmed = 0;
function adminMsg(text, ok) { const m = $('aMsg'); m.hidden = !text; m.textContent = text || ''; m.className = 'msg ' + (ok ? 'ok' : 'bad'); }
function renderAdmin(a) { // names come from Telegram profiles, so they only ever go in as text
  $('aTitle').textContent = a.revision.title;
  tween($('allSum'), a.sum); $('allScans').textContent = a.scans; $('allScansW').textContent = plural(a.scans, SCAN_WORDS);
  $('allMinus').textContent = fmt(a.minus_sum);

  $('pendingBox').hidden = a.pending.length === 0;
  $('pending').replaceChildren(...a.pending.map((p) => {
    const li = el('li', 'st ask');
    const yes = el('button', 'lnk', 'Допустить'); yes.type = 'button'; yes.dataset.user = p.id; yes.dataset.status = 'active';
    const no = el('button', 'lnk no', 'Отклонить'); no.type = 'button'; no.dataset.user = p.id; no.dataset.status = 'blocked';
    li.append(el('span', 'nm', p.name + (p.username ? ' @' + p.username : '')), yes, no);
    return li;
  }));

  const ul = $('staff'), first = new Map();
  rows.forEach((li, id) => first.set(id, li.getBoundingClientRect().top));
  const max = Math.max(1, ...a.users.map((u) => u.sum));
  const seen = new Set();
  a.users.forEach((u, i) => {
    seen.add(u.id);
    let li = rows.get(u.id);
    if (!li) {
      li = el('li', 'st');
      li.append(el('span', 'rk'), el('span', 'nm'), el('span', 'sm'), el('span', 'mn'), el('span', 'act'), el('span', 'bar'));
      li.lastChild.append(el('i')); rows.set(u.id, li);
    }
    ul.appendChild(li);
    const mine = me && u.id === me.id, off = u.status === 'blocked';
    li.className = 'st' + (mine ? ' me' : '') + (off ? ' off' : '');
    li.children[0].textContent = i + 1;
    li.children[1].replaceChildren(u.name + (mine ? ' (я)' : '') + (u.role === 'admin' && !mine ? ' · админ' : ''), el('small', '', u.scans + ' ' + plural(u.scans, SCAN_WORDS)));
    tween(li.children[2], u.sum);
    li.children[3].textContent = (u.minus_sum ? 'минусы −' + fmt(u.minus_sum) : '') + (off ? (u.minus_sum ? ' · ' : '') + 'доступ закрыт' : '');
    if (mine) li.children[4].replaceChildren();
    else {
      const b = el('button', 'lnk' + (off ? '' : ' no'), off ? 'Вернуть' : 'Закрыть доступ'); b.type = 'button';
      b.dataset.user = u.id; b.dataset.status = off ? 'active' : 'blocked'; li.children[4].replaceChildren(b);
    }
    li.querySelector('.bar i').style.width = (Math.max(0, u.sum) / max * 100).toFixed(1) + '%';
  });
  rows.forEach((li, id) => { if (!seen.has(id)) { li.remove(); rows.delete(id); } });
  if (!reduce && first.size) rows.forEach((li, id) => {
    const d = first.has(id) ? first.get(id) - li.getBoundingClientRect().top : 0;
    if (d) li.animate([{ transform: 'translateY(' + d + 'px)' }, { transform: 'none' }], { duration: 380, easing: 'cubic-bezier(.2,.8,.2,1)' });
  });
}
async function loadAdmin() {
  clearTimeout(adminTimer);
  if (!SERVER || tab !== 'admin' || document.hidden) return;
  try { renderAdmin(await api('admin')); } catch (e) { adminMsg(errText(e), false); }
  adminTimer = setTimeout(loadAdmin, 4000);
}
$('v-admin').addEventListener('click', async (ev) => {
  const b = ev.target.closest('[data-user]'); if (!b) return;
  try { renderAdmin(await api('admin/user', { id: +b.dataset.user, status: b.dataset.status })); adminMsg('', true); }
  catch (e) { adminMsg(errText(e), false); }
});
$('aReport').addEventListener('click', async () => {
  adminMsg('Готовлю отчёт…', true);
  try { await api('admin/report'); adminMsg('Отчёт отправлен вам в чат с ботом', true); }
  catch { adminMsg('Не удалось отправить отчёт. Напишите боту /start и попробуйте ещё раз', false); }
});
$('aNew').addEventListener('click', async () => {
  if (Date.now() - newArmed > 4000) {
    newArmed = Date.now(); $('aNew').textContent = 'Нажмите ещё раз: счёт у всех обнулится';
    setTimeout(() => { $('aNew').textContent = 'Новая ревизия'; newArmed = 0; }, 4000);
    return;
  }
  newArmed = 0; $('aNew').textContent = 'Новая ревизия';
  try { renderAdmin(await api('admin/new_revision', {})); adminMsg('Новая ревизия начата, счёт обнулён', true); loadMe(); }
  catch (e) { adminMsg(errText(e), false); }
});
document.addEventListener('visibilitychange', () => { if (!document.hidden && tab === 'admin') loadAdmin(); });

/* ---------- boot ---------- */
function telegram() { // inside Telegram: fill the screen
  try { const tg = window.Telegram && window.Telegram.WebApp; if (tg && tg.ready) { tg.ready(); tg.expand(); } } catch { /* not in Telegram */ }
}
telegram(); addEventListener('load', telegram);
[$('mySum'), $('mySum2')].forEach((node) => { node._v = st.sum; });
if (SERVER) {
  document.querySelectorAll('[data-local]').forEach((node) => { node.hidden = true; });
  refresh(); loadMe();
} else {
  st.avg = localAverage(); renderKey(); refresh();
  if (!apiKey) $('startText').textContent = 'Сначала вставьте ключ Anthropic в Настройках. Потом включите камеру и подносите бирки в рамку.';
}
