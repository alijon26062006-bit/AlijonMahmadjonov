// Ревизия: живой сканер ценников.
// Камера включена постоянно. Когда бирка в рамке перестаёт двигаться, один кадр
// уходит в Claude, и цена прибавляется к сумме. Фото нигде не сохраняются.
import Anthropic from './vendor/anthropic-sdk.js';

const $ = (id) => document.getElementById(id);
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const fmt = (n) => Math.abs(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
const signed = (n) => (n < 0 ? '−' : '+') + fmt(n);
const secs = (s) => s.toFixed(1).replace('.', ',') + ' с';
const now = () => new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
const plural = (n, f) => { const a = n % 10, b = n % 100; return a === 1 && b !== 11 ? f[0] : a >= 2 && a <= 4 && (b < 10 || b >= 20) ? f[1] : f[2]; };
const SCAN_WORDS = ['скан', 'скана', 'сканов'];

/* ---------- storage (this phone only) ---------- */
const LS = {
  get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage may be blocked */ } },
  del(k) { try { localStorage.removeItem(k); } catch { /* ignore */ } },
};
let st = Object.assign({ sum: 0, scans: 0, minuses: 0, voids: 0, uid: 0, log: [] }, LS.get('rev-state', {}));
const opts = Object.assign({ model: 'claude-haiku-5-5', speed: 'normal', sound: 'on' }, LS.get('rev-opts', {}));
let apiKey = LS.get('rev-key', '');
const save = () => LS.set('rev-state', st);

/* ---------- Claude ---------- */
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
  // The key lives in this browser and goes straight to Anthropic. Test mode only:
  // for staff the key must move to a server.
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
function tween(el, to) {
  const from = el._v === undefined ? to : el._v; el._v = to;
  if (reduce || from === to) { el.textContent = fmt(to); return; }
  cancelAnimationFrame(el._raf); const t0 = performance.now();
  (function step(t) {
    const k = Math.min(1, (t - t0) / 380), e = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(Math.round(from + (to - from) * e));
    if (k < 1) el._raf = requestAnimationFrame(step);
  })(t0);
}
function kick(el, cls) { el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); }

function average() {
  const t = st.log.filter((e) => e.sec).map((e) => e.sec);
  return t.length ? t.reduce((a, b) => a + b, 0) / t.length : null;
}
function renderMe() {
  tween($('mySum'), st.sum); tween($('mySum2'), st.sum);
  $('cScans').textContent = st.scans; $('cScansW').textContent = plural(st.scans, SCAN_WORDS);
  $('cMinus').textContent = st.minuses; $('cVoid').textContent = st.voids;
  const avg = average(), last = st.log.find((e) => e.sec);
  $('cAvg').textContent = avg ? secs(avg) : '–';
  const sp = $('speed');
  if (last) {
    sp.textContent = '';
    const b1 = document.createElement('b'); b1.className = 'num'; b1.textContent = st.scans;
    const b2 = document.createElement('b'); b2.className = 'num'; b2.textContent = secs(last.sec);
    const b3 = document.createElement('b'); b3.className = 'num'; b3.textContent = secs(avg);
    sp.append(b1, ' ' + plural(st.scans, SCAN_WORDS) + ' · посл. ', b2, ' · средн. ', b3);
  } else sp.textContent = 'Скорость появится после первого скана';
}
const ICON = {
  scan: '<path d="M3 12V5a2 2 0 012-2h7l9 9-9 9-9-9z"/><circle cx="8" cy="8" r="1.4"/>',
  minus: '<path d="M5 12h14"/>',
};
function renderLog(newId) {
  const has = st.log.length > 0; $('log').hidden = !has; $('logEmpty').hidden = has; $('reset').hidden = !has;
  $('log').innerHTML = st.log.slice(0, 80).map((e) => {
    const m = e.amt < 0;
    return '<li class="row' + (m ? ' m' : '') + (e.void ? ' void' : '') + (e.id === newId ? ' new' : '') + '">' +
      '<span class="ic"><svg width="18" height="18" viewBox="0 0 24 24">' + ICON[m ? 'minus' : 'scan'] + '</svg></span>' +
      '<span class="t"><b>' + (m ? 'Минус вручную' : 'Ценник') + '</b><small>' + e.t + (e.sec ? ' · читал ' + secs(e.sec) : '') + (e.void ? ' · отменено' : '') + '</small></span>' +
      '<span class="a">' + signed(e.amt) + '</span>' +
      (e.void ? '<span></span>' : '<button class="u" type="button" data-undo="' + e.id + '">Отменить</button>') + '</li>';
  }).join('');
}

/* ---------- money ---------- */
function addEntry(amt, sec) {
  const e = { id: ++st.uid, t: now(), amt };
  if (sec) e.sec = Math.round(sec * 10) / 10;
  st.log.unshift(e); st.sum += amt;
  if (amt > 0) st.scans++; else st.minuses++;
  if (st.log.length > 20000) st.log.length = 20000;
  save(); renderMe(); renderLog(e.id);
  kick($('stickerScan'), amt > 0 ? 'bump' : 'shake'); kick($('stickerMine'), amt > 0 ? 'bump' : 'shake');
  return e;
}
function voidEntry(id) {
  const e = st.log.find((x) => x.id === id); if (!e || e.void) return;
  e.void = true; st.sum -= e.amt; st.voids++;
  if (e.amt > 0) st.scans--; else st.minuses--;
  save(); renderMe(); renderLog(); kick($('stickerScan'), 'shake'); kick($('stickerMine'), 'shake');
}
$('log').addEventListener('click', (ev) => { const b = ev.target.closest('[data-undo]'); if (b) voidEntry(+b.dataset.undo); });
let resetArmed = 0;
$('reset').addEventListener('click', () => {
  if (Date.now() - resetArmed < 4000) {
    st = { sum: 0, scans: 0, minuses: 0, voids: 0, uid: st.uid, log: [] }; save(); renderMe(); renderLog();
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
}));
function openTab(name) { document.querySelector('.tabs [data-tab="' + name + '"]').click(); }

/* ---------- camera ---------- */
const cam = $('cam'), video = $('video'), ret = $('ret'), toast = $('toast');
let stream = null, running = false, userPaused = false, pending = null, lastScan = null, wake = null;
let inflight = 0, toastTimer = 0, blockedUntil = 0;

function setStatus(text) { $('statusText').textContent = text; }
function setMode(mode) { cam.classList.remove('idle', 'held', 'paused'); if (mode) cam.classList.add(mode); }

async function startCamera() {
  if (!client) { openTab('set'); showKeyMsg('Сначала вставьте ключ Anthropic', false); return; }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return startError('Этот браузер не даёт доступ к камере. Откройте ссылку в Chrome или Safari.');
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)(); actx.resume();
  } catch { /* no audio */ }
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
    });
  } catch (e) {
    const n = e && e.name;
    return startError(n === 'NotAllowedError' ? 'Нет доступа к камере. Разрешите камеру для этого сайта и нажмите ещё раз.'
      : n === 'NotFoundError' ? 'Камера не найдена.' : 'Камера не включилась. Закройте другие приложения с камерой и попробуйте ещё раз.');
  }
  video.srcObject = stream;
  try { await video.play(); } catch { /* autoplay may need the tap we already have */ }
  $('start').hidden = true; $('camctl').hidden = false;
  running = true; userPaused = false; resetDetector();
  setMode(''); setStatus('Ищу ценник…');
  const track = stream.getVideoTracks()[0];
  const caps = track.getCapabilities ? track.getCapabilities() : {};
  $('torch').hidden = !caps.torch;
  try { wake = await navigator.wakeLock.request('screen'); } catch { /* optional */ }
}
function startError(msg) {
  const p = $('startText'); p.textContent = msg; p.classList.add('err');
  $('start').hidden = false; $('camctl').hidden = true; setMode('idle'); setStatus('Камера выключена');
}
function stopCamera() {
  running = false;
  if (stream) stream.getTracks().forEach((t) => t.stop());
  stream = null; video.srcObject = null;
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
const T = 24, MAX_INFLIGHT = 3, MIN_GAP_MS = 600;
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
  const offX = (vw * scale - cr.width) / 2, offY = (vh * scale - cr.height) / 2, pad = 0.14;
  let x = (rr.left - cr.left - rr.width * pad + offX) / scale, y = (rr.top - cr.top - rr.height * pad + offY) / scale;
  let w = rr.width * (1 + 2 * pad) / scale, h = rr.height * (1 + 2 * pad) / scale;
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

function tick() {
  if (!running || userPaused || pending || tab !== 'scan' || sheetOpen || document.hidden) return;
  if (video.readyState < 2) return;
  const th = thumb(); if (!th) return;
  const p = SPEED[opts.speed] || SPEED.normal, t = performance.now();
  if (det.state === 'armed') {
    const d = det.prev ? diff(th.g, det.prev) : 99;
    det.still = d < p.still ? det.still + 1 : 0;
    // a shaky hand never gets fully still: also accept "mostly still" held a little longer
    det.ema = det.ema * 0.6 + d * 0.4;
    det.calm = det.ema < p.still * 1.7 ? det.calm + 1 : 0;
    dbg(det.state, d, th.sd);
    if ((det.still >= p.need || det.calm >= p.need + 4) && th.sd > 10 && inflight < MAX_INFLIGHT && t - det.lastShot > MIN_GAP_MS && t > blockedUntil) {
      det.ref = th.g; det.state = 'held'; det.moved = 0; capture();
    }
  } else {
    const dr = diff(th.g, det.ref);
    det.moved = dr > p.move ? det.moved + 1 : 0;
    det.peak = Math.max(det.peak || 0, dr);
    dbg(det.state, dr, th.sd);
    if (det.moved >= p.gone) { if (dbgEl) console.log('REARM peak=' + det.peak.toFixed(1) + ' at ' + (performance.now() / 1000).toFixed(1)); rearm(); setMode(''); setStatus(inflight ? 'Читаю… Подносите следующую' : 'Ищу ценник…'); }
  }
  det.prev = th.g;
}
setInterval(tick, 90);
// ?debug=1 shows the detector numbers on screen, for tuning on a real phone
const dbgEl = /[?&]debug/.test(location.search) ? Object.assign(document.createElement('div'), { style: 'position:absolute;left:8px;top:52px;font:11px monospace;color:#0f0;background:rgba(0,0,0,.6);padding:3px 6px;border-radius:6px;z-index:3' }) : null;
if (dbgEl) cam.appendChild(dbgEl);
function dbg(state, d, sd) { if (dbgEl) dbgEl.textContent = state + ' d=' + d.toFixed(1) + ' sd=' + sd.toFixed(0) + ' q=' + inflight; }

function updateQueue() { const q = $('queue'); q.hidden = inflight === 0; q.textContent = 'читаю: ' + inflight; }

function capture() {
  const r = cropRect(); if (!r || !client) return;
  const k = Math.min(1, 640 / Math.max(r.w, r.h));
  ccv.width = Math.round(r.w * k); ccv.height = Math.round(r.h * k);
  cctx.drawImage(video, r.x, r.y, r.w, r.h, 0, 0, ccv.width, ccv.height);
  const b64 = ccv.toDataURL('image/jpeg', 0.72).split(',')[1];
  const th = thumb(); if (th) det.ref = th.g;
  det.state = 'held'; det.moved = 0; det.peak = 0; det.lastShot = performance.now();
  kick($('flash'), 'go'); sndShot();
  setMode('held'); setStatus('Снято. Берите следующую');
  inflight++; updateQueue();
  const t0 = performance.now();
  readPrice(b64).then((r2) => onRead(r2, (performance.now() - t0) / 1000), onReadError)
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
  const el = document.createElement('div'); el.className = 'fly'; el.textContent = '+' + fmt(price); document.body.appendChild(el);
  const w = el.offsetWidth, h = el.offsetHeight, x0 = a.left + a.width / 2 - w / 2, y0 = a.top + a.height / 2 - h / 2;
  el.style.left = x0 + 'px'; el.style.top = y0 + 'px';
  const dx = b.left + b.width / 2 - w / 2 - x0, dy = b.top + b.height / 2 - h / 2 - y0;
  el.animate([{ transform: 'scale(.6)', opacity: 0 }, { transform: 'scale(1.25)', opacity: 1, offset: 0.2 },
    { transform: 'translate(' + dx + 'px,' + dy + 'px) scale(.7)', opacity: 0.9 }], { duration: 420, easing: 'cubic-bezier(.5,0,.2,1)' }).onfinish = () => el.remove();
}
function credit(price, sec) {
  fly(price); sndOk();
  lastScan = addEntry(price, sec);
  showToast('+' + fmt(price), 'Засчитано за ' + secs(sec), false, 'undo', 4000);
}
function onRead(r, sec) {
  if (r.price && r.unsure) { // stop and ask: a wrong digit costs more than a second
    pending = { price: r.price, sec }; sndBad(); setMode('paused'); setStatus('Проверьте цену');
    showToast(fmt(r.price) + '?', 'Не уверен в цифрах', true, 'confirm');
  } else if (r.price) credit(r.price, sec);
  else { sndBad(); showToast('Не прочитал', 'Уберите и поднесите бирку ещё раз · ' + secs(sec), true, '', 2500); }
}
function onReadError(e) {
  sndBad();
  let msg = 'Сбой связи. Попробуйте ещё раз';
  if (e instanceof Anthropic.AuthenticationError || e instanceof Anthropic.PermissionDeniedError) { msg = 'Ключ не подошёл. Проверьте его в Настройках'; pauseForError(); }
  else if (e instanceof Anthropic.RateLimitError) { msg = 'Слишком часто. Жду 5 секунд'; blockedUntil = performance.now() + 5000; }
  else if (e instanceof Anthropic.APIConnectionError) msg = 'Нет интернета. Бирка не засчитана';
  else if (e instanceof Anthropic.APIError && e.status === 400) { msg = 'Запрос отклонён. Смените модель в Настройках'; pauseForError(); }
  showToast('Ошибка', msg, true, '', 4000);
}
function pauseForError() { if (!userPaused) $('pause').click(); }

$('toastUndo').addEventListener('click', () => {
  if (!lastScan) return; voidEntry(lastScan.id);
  showToast('−' + fmt(lastScan.amt), 'Отменено', true, '', 2000); lastScan = null;
});
function endConfirm() { pending = null; resetDetector(); det.state = 'held'; det.ref = (thumb() || {}).g || null; if (!det.ref) det.state = 'armed'; setMode(det.state === 'held' ? 'held' : ''); setStatus('Берите следующую'); }
$('toastYes').addEventListener('click', () => { if (!pending) return; const p = pending; endConfirm(); credit(p.price, p.sec); });
$('toastNo').addEventListener('click', () => { if (!pending) return; endConfirm(); showToast('Не засчитано', 'Уберите и поднесите бирку ещё раз', true, '', 2000); });

/* ---------- minus sheet ---------- */
let val = 0, sheetOpen = false;
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
$('go').addEventListener('click', () => {
  if (!val) return; const v = val; addEntry(-v); openSheet(false);
  lastScan = null; showToast('−' + fmt(v), 'Вычтено', true, '', 2200);
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
seg('segModel', 'model'); seg('segSpeed', 'speed'); seg('segSound', 'sound');

/* ---------- boot ---------- */
function telegram() { // inside Telegram: fill the screen and greet the person by name
  try {
    const tg = window.Telegram && window.Telegram.WebApp;
    if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) { tg.ready(); tg.expand(); $('who').textContent = tg.initDataUnsafe.user.first_name || 'Сканер ценников'; }
  } catch { /* not in Telegram */ }
}
telegram(); addEventListener('load', telegram);
[$('mySum'), $('mySum2')].forEach((el) => { el._v = st.sum; });
renderKey(); renderLog(); renderMe();
if (!apiKey) { $('startText').textContent = 'Сначала вставьте ключ Anthropic в Настройках. Потом включите камеру и подносите бирки в рамку.'; }
