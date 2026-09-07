/* Клиент Mini App. Ответы не проверяет и правильных ответов не знает —
   всё решает сервер. Здесь только экран, нажатия и связь. */

'use strict';

const tg = window.Telegram && window.Telegram.WebApp;
const $ = (id) => document.getElementById(id);

const S = {
  ws: null,
  strings: {},
  profile: null,
  duration: 60,
  level: 'auto',
  winSteps: 10,
  sound: localStorage.getItem('duel.sound') !== 'off',
  lang: 'ru',
  bot: '',
  screen: 'loading',
  task: null,
  taskAt: 0,
  input: '',
  frozenUntil: 0,
  leftMs: null,
  leftAt: 0,
  retry: 0,
  oppScore: 0,
  pendingRoom: '',
};

const say = (key, fallback) => S.strings[key] || fallback || key;

/* ── экраны ─────────────────────────────────────────────── */

const SCREENS = {
  loading: 's-loading', menu: 's-menu', search: 's-search', room: 's-room',
  game: 's-game', result: 's-result', top: 's-top',
};

function show(name) {
  S.screen = name;
  hideToast();
  for (const [key, id] of Object.entries(SCREENS)) {
    $(id).classList.toggle('hidden', key !== name);
  }
  if (tg && tg.BackButton) {
    if (name === 'top' || name === 'room') tg.BackButton.show();
    else tg.BackButton.hide();
  }
}

let toastTimer = 0;
function hideToast() {
  clearTimeout(toastTimer);
  $('toast').classList.add('hidden');
}

function toast(text) {
  const el = $('toast');
  el.textContent = text;
  el.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), 2600);
}

/* ── звук ───────────────────────────────────────────────── */

let audio = null;
function beep(freq, ms, type) {
  if (!S.sound) return;
  try {
    audio = audio || new (window.AudioContext || window.webkitAudioContext)();
    const osc = audio.createOscillator();
    const gain = audio.createGain();
    osc.type = type || 'sine';
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.06, audio.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + ms / 1000);
    osc.connect(gain).connect(audio.destination);
    osc.start();
    osc.stop(audio.currentTime + ms / 1000);
  } catch (e) { /* звук не критичен */ }
}

const haptic = (kind) => {
  if (!tg || !tg.HapticFeedback) return;
  try {
    if (kind === 'ok') tg.HapticFeedback.impactOccurred('light');
    else if (kind === 'bad') tg.HapticFeedback.notificationOccurred('error');
    else if (kind === 'win') tg.HapticFeedback.notificationOccurred('success');
  } catch (e) { /* не на всех клиентах есть */ }
};

/* ── связь ──────────────────────────────────────────────── */

function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  S.ws = ws;

  ws.onopen = () => {
    S.retry = 0;
    send({ t: 'hello', initData: (tg && tg.initData) || '', devId: devId() });
  };
  ws.onmessage = (event) => {
    let msg;
    try { msg = JSON.parse(event.data); } catch (e) { return; }
    handle(msg);
  };
  ws.onclose = () => {
    if (S.screen === 'game') toast(say('offline', 'Связь пропала…'));
    S.retry = Math.min(S.retry + 1, 6);
    setTimeout(connect, Math.min(500 * 2 ** (S.retry - 1), 5000));
  };
  ws.onerror = () => ws.close();
}

function send(payload) {
  if (S.ws && S.ws.readyState === WebSocket.OPEN) {
    S.ws.send(JSON.stringify(payload));
  }
}

/* Локальная отладка без Telegram: стабильный id на браузер. */
function devId() {
  let id = localStorage.getItem('duel.devid');
  if (!id) {
    id = String(100000 + Math.floor(Math.random() * 900000));
    localStorage.setItem('duel.devid', id);
  }
  return Number(id);
}

/* ── сообщения сервера ──────────────────────────────────── */

function handle(msg) {
  switch (msg.t) {
    case 'ready': onReady(msg); break;
    case 'strings': S.strings = msg.strings; S.lang = msg.lang; paint(); break;
    case 'queued': onQueued(msg); break;
    case 'idle': show('menu'); break;
    case 'room': onRoom(msg); break;
    case 'room_error': toast(say('room.bad', 'Комнаты нет')); show('menu'); break;
    case 'found': onFound(msg); break;
    case 'start': $('g-countdown').classList.add('hidden'); break;
    case 'task': onTask(msg); break;
    case 'ans': onAnswer(msg); break;
    case 'state': onState(msg); break;
    case 'end': onEnd(msg); break;
    case 'opp_offline': toast(say('opp_offline', 'У соперника пропала связь')); break;
    case 'error': onError(msg); break;
  }
}

function onReady(msg) {
  S.strings = msg.strings;
  S.lang = msg.lang;
  S.profile = msg.profile;
  S.winSteps = msg.win_steps || 10;
  S.bot = msg.bot || '';
  buildOptions(msg.durations, msg.levels);
  paint();
  if (S.screen === 'loading' || S.screen === 'search') show('menu');

  // Открыли по ссылке-приглашению — сразу входим в комнату друга.
  const code = S.pendingRoom || msg.start_param || '';
  if (code && /^[A-Z0-9]{4,10}$/i.test(code)) {
    S.pendingRoom = '';
    send({ t: 'join', code: code, duration: S.duration, level: S.level });
    show('search');
  }
}

function onQueued(msg) {
  show('search');
  const n = Math.max(0, (msg.waiting || 1) - 1);
  $('q-count').textContent = n > 0 ? `${say('waiting_players', 'в очереди')}: ${n}` : '';
}

function onRoom(msg) {
  show('room');
  $('r-code').textContent = msg.code;
  $('r-share').onclick = () => {
    const text = `${say('room.code', 'Код комнаты')}: ${msg.code}`;
    if (msg.link && tg && tg.openTelegramLink) {
      tg.openTelegramLink(
        `https://t.me/share/url?url=${encodeURIComponent(msg.link)}&text=${encodeURIComponent(text)}`
      );
    } else {
      navigator.clipboard && navigator.clipboard.writeText(msg.link || msg.code);
      toast(msg.code);
    }
  };
}

function onFound(msg) {
  S.winSteps = msg.win_steps || 10;
  S.leftMs = msg.duration > 0 ? msg.duration * 1000 : null;
  S.leftAt = performance.now();
  resetBoard();
  $('g-me-name').textContent = (S.profile && S.profile.name) || say('you', 'Ты');
  $('g-opp-name').textContent = msg.opp.name;
  show('game');
  startCountdown(msg.starts_in_ms || 0);
  beep(660, 120);
}

function startCountdown(ms) {
  const box = $('g-countdown');
  const label = box.querySelector('span');
  if (ms <= 0) { box.classList.add('hidden'); return; }
  box.classList.remove('hidden');
  const endsAt = performance.now() + ms;
  (function step() {
    const left = endsAt - performance.now();
    if (left <= 0) {
      label.textContent = say('go', 'Марш!');
      setTimeout(() => box.classList.add('hidden'), 400);
      return;
    }
    const digit = Math.ceil(left / 1000);
    if (label.textContent !== String(digit)) {
      label.textContent = String(digit);
      beep(440, 90);
    }
    requestAnimationFrame(step);
  })();
}

function onTask(msg) {
  S.task = msg;
  S.taskAt = performance.now();
  S.input = '';
  $('g-question').textContent = `${msg.q} = ?`;
  $('g-answer').textContent = '';
  $('g-answer').classList.remove('bad');
}

function onAnswer(msg) {
  const flash = $('g-flash');
  flash.className = 'flash ' + (msg.correct ? 'ok' : 'bad');
  setTimeout(() => (flash.className = 'flash'), 360);

  if (msg.correct) {
    haptic('ok');
    beep(msg.step > 1 ? 1046 : 784, 90);
    pull('me');
    if (msg.step > 1) $('g-streak').classList.add('boom');
  } else {
    haptic('bad');
    beep(180, 220, 'square');
    $('g-answer').classList.add('bad');
    S.input = '';
    $('g-answer').textContent = '';
    if (msg.freeze_ms) freeze(msg.freeze_ms);
  }
}

function freeze(ms) {
  S.frozenUntil = performance.now() + ms;
  $('g-pad').classList.add('locked');
  $('g-scene').classList.add('frozen');
  setTimeout(() => {
    if (performance.now() < S.frozenUntil - 20) return;
    $('g-pad').classList.remove('locked');
    $('g-scene').classList.remove('frozen');
  }, ms);
}

function onState(msg) {
  if (S.screen !== 'game' && msg.state !== 'finished') show('game');
  if (msg.opp.score > S.oppScore) pull('opp');
  S.oppScore = msg.opp.score;
  $('g-me-score').textContent = msg.me.score;
  $('g-opp-score').textContent = msg.opp.score;
  S.leftMs = msg.left_ms;
  S.leftAt = performance.now();
  drawRope(msg.rope);

  const streak = $('g-streak');
  if (msg.me.streak >= 3) {
    streak.textContent = `${say('streak', 'серия')} ×${msg.me.streak} · ${say('double', '×2')}`;
    streak.classList.remove('hidden');
  } else {
    streak.classList.add('hidden');
    streak.classList.remove('boom');
  }
}

/* Рывок: сцена дёргается в сторону того, кто только что ответил. */
let pullTimer = 0;
function pull(side) {
  const scene = $('g-scene');
  scene.classList.remove('pull-me', 'pull-opp');
  scene.getBoundingClientRect();       // перезапустить анимацию с начала
  scene.classList.add('pull-' + side);
  clearTimeout(pullTimer);
  pullTimer = setTimeout(() => scene.classList.remove('pull-' + side), 430);
}

/* Кто перетягивает — видно по флажку: он уходит от средней черты в сторону
   ведущего. Сами команды при этом только чуть подаются следом, иначе на
   узком экране они уехали бы за край. */
function drawRope(rope) {
  const step = Math.max(-S.winSteps, Math.min(S.winSteps, rope));
  const lean = `translate(${(-step * 16 / S.winSteps).toFixed(2)}, 0)`;
  const flag = `translate(${(-step * 34 / S.winSteps).toFixed(2)}, 0)`;
  $('rope-group').setAttribute('transform', lean);
  $('g-team-me').setAttribute('transform', lean);
  $('g-team-opp').setAttribute('transform', lean);
  $('g-knot').setAttribute('transform', flag);
}

function onEnd(msg) {
  const verdict = $('e-verdict');
  verdict.className = 'verdict ' + msg.outcome;
  verdict.textContent = say(msg.outcome, msg.outcome);
  $('e-reason').textContent = say(`${msg.outcome}.${msg.reason}`, '');
  $('e-score').textContent = msg.score;
  $('e-opp-score').textContent = msg.opp_score;

  const delta = msg.delta || 0;
  const sign = delta > 0 ? 'up' : delta < 0 ? 'down' : '';
  $('e-rating').innerHTML =
    `${say('result.rating', 'Рейтинг')}: <b>${msg.rating}</b> ` +
    `<span class="${sign}">${delta > 0 ? '+' : ''}${delta}</span>`;

  $('e-stats').innerHTML = [
    [say('result.accuracy', 'Точность'), `${msg.accuracy}%`],
    [say('result.streak', 'Лучшая серия'), msg.best_streak],
    [say('result.speed', 'Среднее время'), msg.avg_ms ? `${(msg.avg_ms / 1000).toFixed(1)} c` : '—'],
    [say('result.fastest', 'Быстрее всего'), msg.fastest_ms ? `${(msg.fastest_ms / 1000).toFixed(1)} c` : '—'],
    [say('rank', 'Место'), msg.place || '—'],
  ].map(([k, v]) => `<li><span>${k}</span><b>${v}</b></li>`).join('');

  if (S.profile) { S.profile.rating = msg.rating; S.profile.place = msg.place; }
  paint();
  show('result');
  haptic(msg.outcome === 'win' ? 'win' : 'bad');
  if (msg.outcome === 'win') { beep(784, 120); setTimeout(() => beep(1046, 200), 130); }
  else beep(300, 260, 'triangle');
}

function onError(msg) {
  if (msg.code === 'auth') {
    show('loading');
    $('s-loading').innerHTML =
      `<p class="muted">${say('auth_error', 'Открой игру из Telegram')}</p>`;
  } else if (msg.code === 'replaced') {
    if (S.ws) { S.ws.onclose = null; S.ws.close(); }
    show('loading');
    $('s-loading').innerHTML = '<p class="muted">Игра открыта в другом окне</p>';
  }
}

/* ── экран и настройки ──────────────────────────────────── */

function buildOptions(durations, levels) {
  const box = $('m-durations');
  if (!box.children.length) {
    (durations || [30, 60, 120, 300, 0]).forEach((sec) => {
      const chip = document.createElement('button');
      chip.className = 'chip';
      chip.dataset.duration = String(sec);
      chip.onclick = () => { S.duration = sec; paint(); };
      box.appendChild(chip);
    });
  }
  const lv = $('m-levels');
  if (!lv.children.length) {
    (levels || ['easy', 'normal', 'hard', 'auto']).forEach((name) => {
      const chip = document.createElement('button');
      chip.className = 'chip';
      chip.dataset.level = name;
      chip.onclick = () => { S.level = name; paint(); };
      lv.appendChild(chip);
    });
  }
}

function humanDuration(sec) {
  if (sec === 0) return say('endless', 'До победы');
  if (sec < 60) return `${sec} ${say('sec', 'сек')}`;
  return `${sec / 60} ${say('min', 'мин')}`;
}

function paint() {
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    const key = el.dataset.i18n;
    if (S.strings[key]) el.textContent = S.strings[key];
  });
  $('m-title').textContent = say('title', 'Перетягивание каната');

  document.querySelectorAll('#m-durations .chip').forEach((chip) => {
    const sec = Number(chip.dataset.duration);
    chip.textContent = humanDuration(sec);
    chip.classList.toggle('on', sec === S.duration);
  });
  document.querySelectorAll('#m-levels .chip').forEach((chip) => {
    const name = chip.dataset.level;
    chip.innerHTML =
      `${say('level.' + name, name)}<small>${say('level.' + name + '.hint', '')}</small>`;
    chip.classList.toggle('on', name === S.level);
  });

  if (S.profile) {
    const p = S.profile;
    $('m-me').textContent = p.games
      ? `${say('rating', 'Рейтинг')} ${p.rating} · ${say('rank', 'Место')} ${p.place} · ` +
        `${say('games', 'Матчей')} ${p.games}`
      : say('no_games', 'Ещё ни одного матча');
  }
  $('m-sound').textContent = S.sound ? '🔊' : '🔇';
}

function resetBoard() {
  S.input = '';
  S.task = null;
  S.frozenUntil = 0;
  S.oppScore = 0;
  $('g-scene').classList.remove('frozen', 'pull-me', 'pull-opp');
  $('g-streak').classList.remove('boom');
  $('g-answer').textContent = '';
  $('g-question').textContent = '…';
  $('g-me-score').textContent = '0';
  $('g-opp-score').textContent = '0';
  $('g-pad').classList.remove('locked');
  $('g-streak').classList.add('hidden');
  drawRope(0);
}

/* ── ввод ───────────────────────────────────────────────── */

function press(key) {
  if (S.screen !== 'game' || performance.now() < S.frozenUntil) return;
  if (key === 'del') {
    S.input = S.input.slice(0, -1);
  } else if (key === 'ok') {
    submit();
    return;
  } else if (S.input.length < 6) {
    S.input = (S.input === '0' ? '' : S.input) + key;
  }
  $('g-answer').textContent = S.input;
  $('g-answer').classList.remove('bad');
}

function submit() {
  if (!S.task || S.input === '') return;
  send({
    t: 'answer',
    id: S.task.id,
    v: Number(S.input),
    ms: Math.round(performance.now() - S.taskAt),
  });
  S.input = '';
  $('g-answer').textContent = '';
}

/* ── часы ───────────────────────────────────────────────── */

function tickClock() {
  const clock = $('g-clock');
  if (S.screen === 'game') {
    if (S.leftMs === null || S.leftMs === undefined) {
      clock.textContent = '∞';
      clock.classList.remove('low');
    } else {
      const left = Math.max(0, S.leftMs - (performance.now() - S.leftAt));
      const total = Math.ceil(left / 1000);
      const mm = Math.floor(total / 60);
      const ss = String(total % 60).padStart(2, '0');
      clock.textContent = mm > 0 ? `${mm}:${ss}` : `0:${ss}`;
      clock.classList.toggle('low', total <= 10);
    }
  }
  requestAnimationFrame(tickClock);
}

/* ── запуск ─────────────────────────────────────────────── */

function bind() {
  $('g-pad').addEventListener('click', (event) => {
    const key = event.target.closest('.key');
    if (key) press(key.dataset.key);
  });

  document.addEventListener('keydown', (event) => {
    if (S.screen !== 'game') return;
    if (/^[0-9]$/.test(event.key)) press(event.key);
    else if (event.key === 'Backspace') press('del');
    else if (event.key === 'Enter') press('ok');
  });

  $('m-play').onclick = () => {
    send({ t: 'find', duration: S.duration, level: S.level });
    show('search');
  };
  $('m-friend').onclick = () => send({ t: 'room', duration: S.duration, level: S.level });
  $('m-join').onclick = () => {
    const code = prompt(say('room.enter', 'Введи код комнаты'));
    if (code) send({ t: 'join', code: code.trim(), duration: S.duration, level: S.level });
  };
  $('q-cancel').onclick = () => { send({ t: 'cancel' }); show('menu'); };
  $('r-cancel').onclick = () => { send({ t: 'cancel' }); show('menu'); };

  $('m-lang').onclick = () => send({ t: 'lang', lang: S.lang === 'ru' ? 'tg' : 'ru' });
  $('m-sound').onclick = () => {
    S.sound = !S.sound;
    localStorage.setItem('duel.sound', S.sound ? 'on' : 'off');
    paint();
  };

  $('m-top').onclick = openTop;
  $('t-back').onclick = () => show('menu');
  $('e-home').onclick = () => show('menu');
  $('e-again').onclick = () => {
    send({ t: 'find', duration: S.duration, level: S.level });
    show('search');
  };

  if (tg && tg.BackButton) tg.BackButton.onClick(() => show('menu'));
}

async function openTop() {
  show('top');
  const list = $('t-list');
  list.innerHTML = '';
  try {
    const data = await (await fetch('/api/top?limit=100')).json();
    if (!data.top.length) {
      list.innerHTML = `<p class="muted">${say('top.empty', '')}</p>`;
      return;
    }
    const myId = S.profile && S.profile.id;
    list.innerHTML = data.top.map((row) =>
      `<li class="${row.id === myId ? 'self' : ''}">` +
      `<span class="place">${row.place}</span>` +
      `<span class="name">${escapeHtml(row.name)}</span>` +
      `<span class="score">${row.rating}</span></li>`
    ).join('');
  } catch (e) {
    list.innerHTML = `<p class="muted">${say('error', 'Ошибка')}</p>`;
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function boot() {
  if (tg) {
    tg.ready();
    tg.expand();
    if (tg.disableVerticalSwipes) tg.disableVerticalSwipes();
    S.pendingRoom = (tg.initDataUnsafe && tg.initDataUnsafe.start_param) || '';
  }
  bind();
  connect();
  tickClock();
}

boot();
