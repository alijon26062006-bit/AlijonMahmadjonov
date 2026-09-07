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
  music: localStorage.getItem('duel.music') !== 'off',
  streak: 0,
  hurrying: false,
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
  invite: '',
  online: null,
  people: [],
  peopleOffset: 0,
};

const say = (key, fallback) => S.strings[key] || fallback || key;

/* ── экраны ─────────────────────────────────────────────── */

const SCREENS = {
  loading: 's-loading', menu: 's-menu', search: 's-search', room: 's-room',
  game: 's-game', result: 's-result', top: 's-top', invite: 's-invite',
  players: 's-players',
};

function show(name) {
  S.screen = name;
  hideToast();
  for (const [key, id] of Object.entries(SCREENS)) {
    $(id).classList.toggle('hidden', key !== name);
  }
  if (tg && tg.BackButton) {
    if (['top', 'room', 'invite', 'players'].includes(name)) tg.BackButton.show();
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
    case 'online': S.online = msg; paintOnline(); break;
    case 'strings': S.strings = msg.strings; S.lang = msg.lang; paint(); break;
    case 'queued': onQueued(msg); break;
    case 'idle': show('menu'); break;
    case 'room': onRoom(msg); break;
    case 'room_error': toast(say('room.bad', 'Комнаты нет')); show('menu'); break;
    case 'invite': onInvite(msg); break;
    case 'players': onPeople(msg); break;
    case 'offer_bot': onRobotOffer(msg); break;
    case 'waiting_host': onWaitingHost(msg); break;
    case 'host_gone':
      toast(say('host_gone', 'Так и не зашёл'));
      show('menu');
      break;
    case 'challenge_sent': onCalled(msg); break;
    case 'challenge_error':
      toast(say('called.error.' + msg.reason, say('error', 'Ошибка')));
      break;
    case 'found': onFound(msg); break;
    case 'start': $('g-countdown').classList.add('hidden'); Sound.startMusic(); break;
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
  S.online = msg;
  buildOptions(msg.durations, msg.levels);
  paint();
  if (S.screen === 'loading' || S.screen === 'search') show('menu');

  // Пришли по ссылке-приглашению: показываем, кто зовёт, и ждём нажатия.
  const code = S.pendingRoom || msg.start_param || '';
  if (code && /^[A-Z0-9]{4,10}$/i.test(code)) {
    S.pendingRoom = '';
    send({ t: 'peek', code: code });
  }
}

function onQueued(msg) {
  show('search');
  $('q-offer').classList.add('hidden');
  document.querySelector('#s-search h2').textContent = say('searching', 'Ищем соперника');
  $('q-hint').textContent = say('searching.hint', '');
  const n = Math.max(0, (msg.waiting || 1) - 1);
  $('q-count').textContent = n > 0 ? `${say('waiting_players', 'в очереди')}: ${n}` : '';
}

/* Полминуты в пустой очереди — и человек уходит. Предлагаем робота. */
function onRobotOffer(msg) {
  if (S.screen !== 'search') return;
  $('q-offer').classList.remove('hidden');
  $('q-count').textContent = msg.online > 1
    ? `${msg.online} ${say('online', 'в сети')}`
    : '';
}

/* Экран ожидания на три случая. Разница не косметическая: вызов, уже
   брошенный в чат, не надо предлагать «отправить другу» — он отправлен. */
function paintRoom({ title, hint, waiting, code, spinner }) {
  show('room');
  $('r-title').textContent = title;
  $('r-hint').textContent = hint;
  $('r-waiting').textContent = waiting || '';
  $('r-spinner').classList.toggle('hidden', !spinner);
  $('r-code').classList.toggle('hidden', !code);
  $('r-share').classList.toggle('hidden', !code);
  if (code) $('r-code').textContent = code;
}

function onRoom(msg) {
  if (msg.group) {
    // Вызов уже в чате: остаётся только ждать, кто нажмёт первым.
    paintRoom({
      title: say('room.group.title', 'Вызов брошен в чат'),
      hint: say('room.group.hint', 'Ждём соперника'),
      spinner: true,
    });
    return;
  }
  paintRoom({
    title: say('room.title', 'Комната для друга'),
    hint: say('room.hint', ''),
    waiting: say('room.waiting', ''),
    code: msg.code,
  });
  $('r-share').onclick = () => shareInvite(msg);
}

/* Гостя встречает имя того, кто позвал, и одна кнопка. Влетать в бой сразу,
   без предупреждения, — верный способ проиграть первые десять секунд. */
function onInvite(msg) {
  S.invite = msg.code;
  $('i-face').textContent = initial(msg.host.name);
  $('i-face').style.background = colorOf(msg.host.name);
  $('i-name').textContent = msg.host.name;
  $('i-rank').textContent = `${say('rating', 'Рейтинг')} ${msg.host.rating} · ${msg.host.title}`;
  document.querySelector('.invite-title').textContent = say('invite.title', 'зовёт тебя на дуэль');
  $('i-terms').innerHTML =
    `<span>${humanDuration(msg.duration)}</span>` +
    `<span>${say('level.' + msg.level, msg.level)}</span>`;
  show('invite');
  Sound.match();
}

/* Первая буква имени и постоянный для него цвет — вместо аватарки. */
function initial(name) {
  return (name || '?').trim().charAt(0).toUpperCase() || '?';
}

function colorOf(name) {
  let hash = 0;
  for (let i = 0; i < (name || '').length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) % 360;
  }
  return `hsl(${hash}, 58%, 48%)`;
}

/* ── все игроки ─────────────────────────────────────────── */

function openPeople() {
  S.people = [];
  S.peopleOffset = 0;
  $('p-list').innerHTML = '';
  $('p-more').classList.add('hidden');
  show('players');
  send({ t: 'players', offset: 0 });
}

function onPeople(msg) {
  S.people = S.people.concat(msg.list);
  S.peopleOffset = msg.offset + msg.list.length;

  const list = $('p-list');
  if (!S.people.length) {
    list.innerHTML = `<p class="muted">${say('players.empty', '')}</p>`;
    return;
  }
  list.innerHTML = S.people.map(personRow).join('');
  list.querySelectorAll('.call').forEach((button) => {
    button.onclick = () => callToBattle(button, Number(button.dataset.id));
  });
  $('p-more').classList.toggle('hidden', S.peopleOffset >= msg.total);
}

function personRow(person) {
  return `<li>` +
    `<span class="face" style="background:${colorOf(person.name)}">${initial(person.name)}</span>` +
    `<span class="who">` +
      `<div class="nick">${escapeHtml(person.name)}</div>` +
      `<div class="seen ${person.busy ? 'busy' : person.online ? 'now' : ''}">` +
        `${seenText(person)} · <span class="rank">${person.rating}</span></div>` +
    `</span>` +
    `<button class="call" data-id="${person.id}">${say('players.call', 'Позвать')}</button>` +
    `</li>`;
}

/* Точное время никому не нужно, а «вчера» и «давно» говорят главное:
   стоит ли ждать ответа прямо сейчас. */
function seenText(person) {
  if (person.busy) return say('seen.busy', 'играет');
  if (person.online) return say('seen.online', 'в сети');
  // Сроки берём по прошедшему времени, а не по календарю: сервер шлёт
  // секунды, а «сегодня» для того, кто был 18 часов назад, — уже неправда.
  const s = person.seen;
  if (s < 600) return say('seen.now', 'только что');
  if (s < 7200) return say('seen.recent', 'недавно');
  if (s < 86400) return say('seen.hours', 'несколько часов назад');
  if (s < 259200) return say('seen.days', 'на днях');
  if (s < 604800) return say('seen.week', 'на этой неделе');
  if (s < 2592000) return say('seen.month', 'в этом месяце');
  return say('seen.long', 'давно');
}

function callToBattle(button, id) {
  send({ t: 'challenge', to: id, duration: S.duration, level: S.level });
  button.classList.add('done');
  button.textContent = say('called', 'Позвали');
}

/* Друг нажал «В бой», а хозяина в игре нет. Ждём его — он уже позван в чате. */
function onWaitingHost(msg) {
  show('search');
  $('q-offer').classList.add('hidden');
  document.querySelector('#s-search h2').textContent =
    `${say('waiting_host', 'Ждём, пока зайдёт')}: ${msg.name}`;
  $('q-hint').textContent = say('waiting_host.hint', '');
  $('q-count').textContent = '';
}

function onCalled(msg) {
  paintRoom({
    title: `${say('called', 'Позвали')}: ${msg.to.name}`,
    hint: msg.to.online
      ? say('called.wait', 'Ждём ответа')
      : say('called.chat', 'Приглашение ушло ему в чат'),
    spinner: true,
  });
}

/* Отправить приглашение другу: открываем выбор чата прямо в Telegram.
   Комната переживёт наш уход из игры, поэтому закрытое окно ничего не сломает. */
function shareInvite(msg) {
  const text = say('invite.share.text', 'Сыграем в математическую дуэль?');
  if (msg.link && tg && tg.openTelegramLink) {
    tg.openTelegramLink(
      'https://t.me/share/url?url=' + encodeURIComponent(msg.link) +
      '&text=' + encodeURIComponent(text)
    );
    return;
  }
  if (navigator.clipboard && msg.link) {
    navigator.clipboard.writeText(msg.link);
    toast(say('room.share.copied', 'Ссылка скопирована'));
    return;
  }
  toast(msg.code);
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
  Sound.match();
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
      Sound.go();
      setTimeout(() => box.classList.add('hidden'), 400);
      return;
    }
    const digit = Math.ceil(left / 1000);
    if (label.textContent !== String(digit)) {
      label.textContent = String(digit);
      Sound.tick();
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
    S.streak += 1;
    haptic('ok');
    Sound.correct(S.streak, msg.step);
    pull('me');
    if (msg.step > 1) $('g-streak').classList.add('boom');
  } else {
    S.streak = 0;
    haptic('bad');
    Sound.wrong();
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
  if (msg.opp.score > S.oppScore) {
    pull('opp');
    Sound.rival();
  }
  S.oppScore = msg.opp.score;
  S.streak = msg.me.streak;
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

  if (msg.rated === false) {
    $('e-rating').innerHTML = `<span class="muted">${say('training', 'Тренировка')}</span>`;
  } else {
    const delta = msg.delta || 0;
    const sign = delta > 0 ? 'up' : delta < 0 ? 'down' : '';
    $('e-rating').innerHTML =
      `${say('result.rating', 'Рейтинг')}: <b>${msg.rating}</b> ` +
      `<span class="${sign}">${delta > 0 ? '+' : ''}${delta}</span>`;
  }

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
  Sound.stopMusic();
  Sound[msg.outcome === 'win' ? 'win' : msg.outcome === 'draw' ? 'draw' : 'lose']();
}

function onError(msg) {
  if (msg.code === 'auth') {
    show('loading');
    // Без подробностей такой экран нечем чинить: показываем, что именно не так.
    const seen = !(window.Telegram && window.Telegram.WebApp)
      ? say('auth.no_lib', 'Библиотека Telegram не загрузилась')
      : (tg && tg.initData)
        ? say('auth.bad_sign', 'Telegram передал данные, но сервер их не принял')
        : say('auth.no_data', 'Открой игру кнопкой в боте');
    $('s-loading').innerHTML =
      `<p>${say('auth_error', 'Открой игру из Telegram')}</p>` +
      `<p class="muted">${escapeHtml(seen)}</p>` +
      (msg.message ? `<p class="muted tiny">${escapeHtml(msg.message)}</p>` : '') +
      `<button class="btn" id="retry">${say('retry', 'Попробовать снова')}</button>`;
    const again = $('retry');
    if (again) again.onclick = () => location.reload();
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
  $('m-lang').title = say('lang', 'Язык');
  $('m-sound').title = say('sound', 'Звук');
  $('m-music').title = say('music', 'Музыка');
  paintOnline();
  $('m-sound').textContent = S.sound ? '🔊' : '🔇';
  $('m-music').textContent = S.music ? '🎵' : '🚫';
  $('m-music').classList.toggle('off', !S.music);
  $('m-sound').classList.toggle('off', !S.sound);
}

/* Сколько людей сейчас в игре. Когда один — вместо цифры зовём друга:
   «1 в сети» выглядит уныло и ничего не подсказывает. */
function paintOnline() {
  const box = $('m-online');
  if (!box || !S.online) return;
  const { online = 0, searching = 0, playing = 0 } = S.online;

  if (online <= 1) {
    box.textContent = say('online.alone', 'Пока ты один — позови друга');
    box.classList.add('alone');
    return;
  }
  box.classList.remove('alone');

  const parts = [`${online} ${say('online', 'в сети')}`];
  if (searching > 0) parts.push(`${searching} ${countWord('online.searching', searching)}`);
  else if (playing > 0) parts.push(`${playing} ${countWord('online.playing', playing)}`);
  box.textContent = parts.join(' · ');
}

/* «1 ищут соперника» режет глаз — берём форму слова по числу. */
function countWord(key, count) {
  return say(`${key}.${count === 1 ? 'one' : 'many'}`, key);
}

function resetBoard() {
  S.input = '';
  S.task = null;
  S.frozenUntil = 0;
  S.oppScore = 0;
  S.streak = 0;
  S.hurrying = false;
  Sound.hurry(false);
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
      const low = total <= 10;
      clock.classList.toggle('low', low);
      if (low !== S.hurrying) {
        S.hurrying = low;
        Sound.hurry(low);
      }
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
  $('q-robot').onclick = () => {
    send({ t: 'play_bot', duration: S.duration, level: S.level });
    $('q-offer').classList.add('hidden');
  };
  $('r-cancel').onclick = () => { send({ t: 'cancel' }); show('menu'); };

  $('m-lang').onclick = () => send({ t: 'lang', lang: S.lang === 'ru' ? 'tg' : 'ru' });
  $('m-sound').onclick = () => {
    S.sound = !S.sound;
    localStorage.setItem('duel.sound', S.sound ? 'on' : 'off');
    Sound.setSfx(S.sound);
    if (S.sound) Sound.tick();
    paint();
  };
  $('m-music').onclick = () => {
    S.music = !S.music;
    localStorage.setItem('duel.music', S.music ? 'on' : 'off');
    Sound.setMusic(S.music);
    paint();
  };

  $('i-go').onclick = () => {
    if (!S.invite) return show('menu');
    send({ t: 'join', code: S.invite, duration: S.duration, level: S.level });
    show('search');
  };
  $('i-cancel').onclick = () => { S.invite = ''; show('menu'); };

  $('m-players').onclick = openPeople;
  $('p-back').onclick = () => show('menu');
  $('p-more').onclick = () => send({ t: 'players', offset: S.peopleOffset });
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
  const podium = $('t-podium');
  const list = $('t-list');
  const you = $('t-you');
  podium.innerHTML = '';
  list.innerHTML = '';
  you.classList.add('hidden');

  try {
    const data = await (await fetch('/api/top?limit=100')).json();
    if (!data.top.length) {
      list.innerHTML = `<p class="muted">${say('top.empty', '')}</p>`;
      return;
    }
    const myId = S.profile && S.profile.id;

    // На пьедестал встают только те, кто действительно играл. Остальные —
    // списком ниже, включая новичков: пустой экран под пьедесталом выглядит
    // сломанным, даже когда всё правильно.
    const played = data.top.filter((row) => row.games > 0).slice(0, 3);
    const rest = data.top.filter((row) => !played.includes(row));

    const medals = ['🥇', '🥈', '🥉'];
    const order = [1, 0, 2];
    podium.innerHTML = order
      .filter((i) => played[i])
      .map((i) => {
        const row = played[i];
        return `<div class="pod pod-${i + 1}">` +
          `<div class="pod-medal">${medals[i]}</div>` +
          `<div class="face" style="background:${colorOf(row.name)}">${initial(row.name)}</div>` +
          `<div class="pod-name">${escapeHtml(row.name)}</div>` +
          `<div class="pod-rating">${row.rating}</div>` +
          `<div class="pod-base">${row.place}</div>` +
          `</div>`;
      })
      .join('');

    list.innerHTML = rest.map((row) => boardRow(row, row.id === myId)).join('');

    // Своё место далеко внизу — показываем отдельной строкой, чтобы не искать.
    const mine = data.top.find((row) => row.id === myId);
    if (!mine && S.profile && S.profile.games) {
      you.innerHTML = boardRow({
        place: S.profile.place,
        name: S.profile.name,
        rating: S.profile.rating,
        wins: S.profile.wins,
        games: S.profile.games,
      }, true, true);
      you.classList.remove('hidden');
    }
  } catch (e) {
    list.innerHTML = `<p class="muted">${say('error', 'Ошибка')}</p>`;
  }
}

function boardRow(row, self, bare) {
  const played = row.games > 0;
  const inner =
    `<span class="place">${played ? row.place : '—'}</span>` +
    `<span class="face" style="background:${colorOf(row.name)}">${initial(row.name)}</span>` +
    `<span class="name">${escapeHtml(row.name)}` +
    `<span class="games"> · ${played ? `${row.wins}/${row.games}` : say('top.newcomer', '')}` +
    `</span></span>` +
    `<span class="score">${played ? row.rating : ''}</span>`;
  return bare ? inner : `<li class="${self ? 'self' : ''}">${inner}</li>`;
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
  Sound.setSfx(S.sound);
  Sound.setMusic(S.music);
  // Телефоны не дают звучать, пока человек сам не коснётся экрана.
  const wake = () => Sound.unlock();
  document.addEventListener('pointerdown', wake, { passive: true });
  document.addEventListener('keydown', wake);
  document.addEventListener('visibilitychange', () => Sound.mute(document.hidden));

  bind();
  connect();
  tickClock();
}

boot();
