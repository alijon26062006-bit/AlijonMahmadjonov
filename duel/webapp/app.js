/* Клиент Mini App. Ответы не проверяет и правильных ответов не знает —
   всё решает сервер. Здесь только экран, нажатия и связь.

   Игр несколько, и у каждой свой экран, но пример, ответ и клавиатура
   общие: где именно они на экране, говорит таблица VIEWS. Новая игра —
   новая строка в ней, новый экран и свой модуль вроде sea.js. */

'use strict';

const tg = window.Telegram && window.Telegram.WebApp;
const $ = (id) => document.getElementById(id);

/* Длительность каната. Раньше её выбирали на экране, но выбор до игры только
   мешает: человек пришёл играть, а не настраивать. */
const MATCH_SECONDS = 60;

const DEFAULT_GAME = 'rope';

const S = {
  ws: null,
  strings: {},
  profile: null,
  games: [DEFAULT_GAME],
  // Игра, выбранная в меню, и игра идущего матча — не всегда одна и та же:
  // приглашение друга приводит в его игру.
  game: localStorage.getItem('duel.game') || DEFAULT_GAME,
  playing: '',
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
  topGame: '',
};

const say = (key, fallback) => S.strings[key] || fallback || key;

/* ── игры ───────────────────────────────────────────────── */

/* Где у каждой игры пример, ответ, клавиатура и часы. */
const VIEWS = {
  rope: {
    screen: 'game', question: 'g-question', answer: 'g-answer', pad: 'g-pad',
    flash: 'g-flash', countdown: 'g-countdown', clock: 'g-clock',
  },
  sea: {
    screen: 'sea', question: 'z-question', answer: 'z-answer', pad: 'z-pad',
    flash: 'z-flash', countdown: 'z-countdown', clock: 'z-clock',
  },
};

const view = () => VIEWS[S.playing] || VIEWS[S.game] || VIEWS.rope;

/* Значки игр на карточках меню. */
const GAME_ICONS = {
  rope:
    '<svg viewBox="0 0 64 36" aria-hidden="true">' +
    '<path class="i-rope" d="M4 22 Q 20 16 32 20 T 60 18"/>' +
    '<path class="i-flag" d="M31 4 L31 20 M31 4 L43 8.5 L31 13 z"/>' +
    '<path class="i-rope" d="M31 6 L31 21" style="stroke:#e0453e;stroke-width:2.5"/>' +
    '</svg>',
  sea:
    '<svg viewBox="0 0 64 36" aria-hidden="true">' +
    '<path class="i-deck" d="M22 8 h14 v9 h-14 z M28 3 h6 v6 h-6 z"/>' +
    '<path class="i-hull" d="M8 17 h48 l-8 11 h-32 z"/>' +
    '<path class="i-wave" d="M4 31 q5 -4 10 0 t10 0 t10 0 t10 0 t10 0 t6 0"/>' +
    '</svg>',
};

const gameName = (game) => say('game.' + game, game);

function pickGame(game) {
  if (!S.games.includes(game)) return;
  S.game = game;
  localStorage.setItem('duel.game', game);
  paint();
}

/* Что просим у сервера: игру, уровень и — для каната — длительность. */
function wanted(game) {
  const g = game || S.game;
  const out = { game: g, level: S.level };
  if (g === 'rope') out.duration = MATCH_SECONDS;
  return out;
}

/* Свои очки в игре: рейтинг, место, матчей. */
function standing(game) {
  const all = (S.profile && S.profile.standings) || {};
  return all[game] || { rating: 1000, games: 0, place: 0, wins: 0 };
}

/* ── экраны ─────────────────────────────────────────────── */

const SCREENS = {
  loading: 's-loading', menu: 's-menu', search: 's-search', room: 's-room',
  game: 's-game', sea: 's-sea', result: 's-result', top: 's-top',
  invite: 's-invite', players: 's-players',
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

const inMatch = () => S.screen === 'game' || S.screen === 'sea';

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
    if (inMatch()) toast(say('offline', 'Связь пропала…'));
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
    case 'start': $(view().countdown).classList.add('hidden'); Sound.startMusic(); break;
    case 'task': onTask(msg); break;
    case 'ans': onAnswer(msg); break;
    case 'state': onState(msg); break;
    case 'end': onEnd(msg); break;
    // морской бой
    case 'placed': Sea.placed(msg); break;
    case 'sea_layout': Sea.layout(msg); break;
    case 'shot': Sea.shot(msg); break;
    case 'incoming': Sea.incoming(msg); break;
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
  if (Array.isArray(msg.games) && msg.games.length) S.games = msg.games;
  if (!S.games.includes(S.game)) S.game = S.games[0];
  buildOptions(msg.levels);
  buildGames();
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
  $('q-game').textContent = gameName(msg.game || S.game);
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
  const game = gameName(msg.game || S.game);
  if (msg.group) {
    // Вызов уже в чате: остаётся только ждать, кто нажмёт первым.
    paintRoom({
      title: say('room.group.title', 'Вызов брошен в чат'),
      hint: `${game} · ${say('room.group.hint', 'Ждём соперника')}`,
      spinner: true,
    });
    return;
  }
  paintRoom({
    title: say('room.title', 'Комната для друга'),
    hint: `${game} · ${say('room.hint', '')}`,
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
    `<span>${escapeHtml(gameName(msg.game || DEFAULT_GAME))}</span>` +
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
  send({ t: 'players', offset: 0, game: S.game });
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
  send(Object.assign({ t: 'challenge', to: id }, wanted()));
  button.classList.add('done');
  button.textContent = say('called', 'Позвали');
}

/* Друг нажал «В бой», а хозяина в игре нет. Ждём его — он уже позван в чате. */
function onWaitingHost(msg) {
  show('search');
  $('q-offer').classList.add('hidden');
  document.querySelector('#s-search h2').textContent =
    `${say('waiting_host', 'Ждём, пока зайдёт')}: ${msg.name}`;
  $('q-game').textContent = '';
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

/* ── матч ───────────────────────────────────────────────── */

function onFound(msg) {
  S.playing = S.games.includes(msg.game) ? msg.game : DEFAULT_GAME;
  S.winSteps = msg.win_steps || 10;
  S.leftMs = msg.duration > 0 ? msg.duration * 1000 : null;
  S.leftAt = performance.now();
  resetBoard();
  Sound.match();

  if (S.playing === 'sea') {
    Sea.begin(msg);
    show('sea');
    // Отсчёт в море идёт после расстановки — его объявит состояние.
    return;
  }
  $('g-me-name').textContent = (S.profile && S.profile.name) || say('you', 'Ты');
  $('g-opp-name').textContent = msg.opp.name;
  show('game');
  startCountdown(msg.starts_in_ms || 0);
}

let countdownEnds = 0;
function startCountdown(ms) {
  const box = $(view().countdown);
  const label = box.querySelector('span');
  if (ms <= 0) { box.classList.add('hidden'); return; }
  if (!box.classList.contains('hidden') && countdownEnds > performance.now()) return;
  box.classList.remove('hidden');
  const endsAt = performance.now() + ms;
  countdownEnds = endsAt;
  (function step() {
    if (countdownEnds !== endsAt) return;
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
  const v = view();
  $(v.question).textContent = `${msg.q} = ?`;
  $(v.answer).textContent = '';
  $(v.answer).classList.remove('bad');
}

function onAnswer(msg) {
  const v = view();
  const flash = $(v.flash);
  flash.className = 'flash ' + (msg.correct ? 'ok' : 'bad');
  setTimeout(() => (flash.className = 'flash'), 360);

  if (msg.correct) {
    S.streak += 1;
    haptic('ok');
    Sound.correct(S.streak, msg.step);
    if (S.playing === 'rope') {
      pull('me');
      if (msg.step > 1) $('g-streak').classList.add('boom');
    }
  } else {
    S.streak = 0;
    haptic('bad');
    Sound.wrong();
    $(v.answer).classList.add('bad');
    S.input = '';
    $(v.answer).textContent = '';
    if (msg.freeze_ms) freeze(msg.freeze_ms);
  }
}

function freeze(ms) {
  S.frozenUntil = performance.now() + ms;
  const pad = $(view().pad);
  pad.classList.add('locked');
  $('g-scene').classList.add('frozen');
  setTimeout(() => {
    if (performance.now() < S.frozenUntil - 20) return;
    pad.classList.remove('locked');
    $('g-scene').classList.remove('frozen');
  }, ms);
}

function onState(msg) {
  if (msg.state === 'finished') return;
  const game = msg.game || S.playing || DEFAULT_GAME;
  if (game !== S.playing) S.playing = game;
  const v = view();
  if (S.screen !== v.screen) show(v.screen);

  S.streak = msg.me.streak;
  S.leftAt = performance.now();

  if (game === 'sea') {
    if (msg.state === 'placing') S.leftMs = msg.place_left_ms;
    else S.leftMs = msg.left_ms;
    if (msg.state === 'countdown') startCountdown(msg.starts_in_ms || 0);
    Sea.state(msg);
    return;
  }

  if (msg.opp.score > S.oppScore) {
    pull('opp');
    Sound.rival();
  }
  S.oppScore = msg.opp.score;
  $('g-me-score').textContent = msg.me.score;
  $('g-opp-score').textContent = msg.opp.score;
  S.leftMs = msg.left_ms;
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
  const game = msg.game || S.playing || DEFAULT_GAME;
  const verdict = $('e-verdict');
  verdict.className = 'verdict ' + msg.outcome;
  verdict.textContent = say(msg.outcome, msg.outcome);
  const reasonKey = game === 'sea'
    ? `sea.${msg.outcome}.${msg.reason}`
    : `${msg.outcome}.${msg.reason}`;
  $('e-reason').textContent = say(reasonKey, say(`${msg.outcome}.${msg.reason}`, ''));

  // В море главный счёт — попадания, в канате — верные ответы.
  const sea = game === 'sea';
  $('e-score').textContent = sea ? msg.hits : msg.score;
  $('e-opp-score').textContent = sea ? msg.opp_hits : msg.opp_score;

  if (msg.rated === false) {
    $('e-rating').innerHTML = `<span class="muted">${say('training', 'Тренировка')}</span>`;
  } else {
    const delta = msg.delta || 0;
    const sign = delta > 0 ? 'up' : delta < 0 ? 'down' : '';
    $('e-rating').innerHTML =
      `${escapeHtml(gameName(game))} · ${say('result.rating', 'Рейтинг')}: <b>${msg.rating}</b> ` +
      `<span class="${sign}">${delta > 0 ? '+' : ''}${delta}</span>`;
  }

  const rows = sea
    ? [
      [say('result.sunk', 'Потоплено кораблей'), `${msg.sunk} / ${Sea.FLEET.length}`],
      [say('result.shots', 'Выстрелов'), msg.shots],
      [say('result.correct', 'Верных ответов'), `${msg.score} : ${msg.opp_score}`],
      [say('result.accuracy', 'Точность'), `${msg.accuracy}%`],
      [say('rank', 'Место'), msg.place || '—'],
    ]
    : [
      [say('result.accuracy', 'Точность'), `${msg.accuracy}%`],
      [say('result.streak', 'Лучшая серия'), msg.best_streak],
      [say('result.speed', 'Среднее время'), msg.avg_ms ? `${(msg.avg_ms / 1000).toFixed(1)} c` : '—'],
      [say('result.fastest', 'Быстрее всего'), msg.fastest_ms ? `${(msg.fastest_ms / 1000).toFixed(1)} c` : '—'],
      [say('rank', 'Место'), msg.place || '—'],
    ];
  $('e-stats').innerHTML = rows
    .map(([k, v]) => `<li><span>${k}</span><b>${v}</b></li>`).join('');

  const reveal = $('e-reveal');
  reveal.classList.toggle('hidden', !sea);
  if (sea) Sea.reveal($('e-fleet'), msg);

  if (S.profile) {
    const mine = standing(game);
    S.profile.standings = S.profile.standings || {};
    S.profile.standings[game] = Object.assign({}, mine, {
      rating: msg.rating,
      place: msg.place,
      games: mine.games + (msg.rated === false ? 0 : 1),
      wins: mine.wins + (msg.rated !== false && msg.outcome === 'win' ? 1 : 0),
    });
  }
  S.playing = '';
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

function buildOptions(levels) {
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

/* Карточки игр в меню и переключатель над таблицей лидеров. */
function buildGames() {
  const box = $('m-games');
  box.innerHTML = S.games.map((game) =>
    `<button class="gcard" data-game="${game}">` +
      `<span class="gicon">${GAME_ICONS[game] || ''}</span>` +
      `<span class="gname"></span>` +
      `<span class="ghint"></span>` +
      `<span class="gscore"></span>` +
    `</button>`
  ).join('');
  box.querySelectorAll('.gcard').forEach((card) => {
    card.onclick = () => pickGame(card.dataset.game);
  });

  const tabs = $('t-tabs');
  tabs.innerHTML = S.games.map((game) =>
    `<button class="tab" data-game="${game}"></button>`
  ).join('');
  tabs.querySelectorAll('.tab').forEach((tab) => {
    tab.onclick = () => openTop(tab.dataset.game);
  });
  tabs.classList.toggle('hidden', S.games.length < 2);
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
  // На экране лидеров заголовок остаётся полным, а кнопка в меню — короткой.
  document.querySelector('#s-top h2').textContent = say('top', 'Таблица лидеров');
  $('m-title').textContent = say('app', 'Канат');
  $('m-sub').textContent = say('app.sub', 'математические дуэли');

  document.querySelectorAll('#m-levels .chip').forEach((chip) => {
    const name = chip.dataset.level;
    chip.innerHTML =
      `${say('level.' + name, name)}<small>${say('level.' + name + '.hint', '')}</small>`;
    chip.classList.toggle('on', name === S.level);
  });

  document.querySelectorAll('#m-games .gcard').forEach((card) => {
    const game = card.dataset.game;
    const mine = standing(game);
    card.classList.toggle('on', game === S.game);
    card.querySelector('.gname').textContent = gameName(game);
    card.querySelector('.ghint').textContent = say(`game.${game}.hint`, '');
    const score = card.querySelector('.gscore');
    score.classList.toggle('none', !mine.games);
    score.textContent = mine.games
      ? `${mine.rating} · ${say('rank', 'Место')} ${mine.place}`
      : say('top.newcomer', 'ещё не играл');
  });
  document.querySelectorAll('#t-tabs .tab').forEach((tab) => {
    tab.textContent = gameName(tab.dataset.game);
    tab.classList.toggle('on', tab.dataset.game === S.topGame);
  });

  // Под карточками — подсказка, что рейтинг у каждой игры свой: она
  // объясняет, почему в одной игре ты мастер, а в другой новичок.
  $('m-me').textContent = say('game.pick.hint', '');
  $('m-lang').title = say('lang', 'Язык');
  $('m-sound').title = say('sound', 'Звук');
  $('m-music').title = say('music', 'Музыка');
  paintOnline();
  $('m-sound').textContent = S.sound ? '🔊' : '🔇';
  $('m-music').textContent = S.music ? '🎵' : '🚫';
  $('m-music').classList.toggle('off', !S.music);
  $('m-sound').classList.toggle('off', !S.sound);
  Sea.paint();
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
  countdownEnds = 0;
  Sound.hurry(false);
  $('g-scene').classList.remove('frozen', 'pull-me', 'pull-opp');
  $('g-streak').classList.remove('boom');
  $('g-streak').classList.add('hidden');
  $('g-me-score').textContent = '0';
  $('g-opp-score').textContent = '0';
  Object.values(VIEWS).forEach((v) => {
    $(v.answer).textContent = '';
    $(v.answer).classList.remove('bad');
    $(v.question).textContent = '…';
    $(v.pad).classList.remove('locked');
    $(v.countdown).classList.add('hidden');
  });
  drawRope(0);
}

/* ── ввод ───────────────────────────────────────────────── */

function press(key) {
  if (!inMatch() || performance.now() < S.frozenUntil) return;
  if (key === 'del') {
    S.input = S.input.slice(0, -1);
  } else if (key === 'ok') {
    submit();
    return;
  } else if (S.input.length < 6) {
    S.input = (S.input === '0' ? '' : S.input) + key;
  }
  const answer = $(view().answer);
  answer.textContent = S.input;
  answer.classList.remove('bad');
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
  $(view().answer).textContent = '';
}

/* ── часы ───────────────────────────────────────────────── */

function tickClock() {
  if (inMatch()) {
    const clock = $(view().clock);
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
      // Спешка — только в бою: во время расстановки музыки ещё нет.
      const hurry = low && (S.playing !== 'sea' || Sea.mode() === 'battle');
      if (hurry !== S.hurrying) {
        S.hurrying = hurry;
        Sound.hurry(hurry);
      }
    }
  }
  requestAnimationFrame(tickClock);
}

/* ── запуск ─────────────────────────────────────────────── */

function bind() {
  document.querySelectorAll('.pad').forEach((pad) => {
    pad.addEventListener('click', (event) => {
      const key = event.target.closest('.key');
      if (key) press(key.dataset.key);
    });
  });

  document.addEventListener('keydown', (event) => {
    if (!inMatch()) return;
    if (/^[0-9]$/.test(event.key)) press(event.key);
    else if (event.key === 'Backspace') press('del');
    else if (event.key === 'Enter') press('ok');
  });

  $('m-play').onclick = () => {
    send(Object.assign({ t: 'find' }, wanted()));
    show('search');
  };
  $('m-friend').onclick = () => send(Object.assign({ t: 'room' }, wanted()));
  $('m-join').onclick = () => {
    const code = prompt(say('room.enter', 'Введи код комнаты'));
    if (code) send(Object.assign({ t: 'join', code: code.trim() }, wanted()));
  };
  $('q-cancel').onclick = () => { send({ t: 'cancel' }); show('menu'); };
  $('q-robot').onclick = () => {
    send(Object.assign({ t: 'play_bot' }, wanted()));
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
    // Игру и условия задаёт тот, кто позвал; своё сервер не спросит.
    send(Object.assign({ t: 'join', code: S.invite }, wanted()));
    show('search');
  };
  $('i-cancel').onclick = () => { S.invite = ''; show('menu'); };

  $('m-players').onclick = openPeople;
  $('p-back').onclick = () => show('menu');
  $('p-more').onclick = () => send({ t: 'players', offset: S.peopleOffset, game: S.game });
  $('m-top').onclick = () => openTop(S.game);
  $('t-back').onclick = () => show('menu');
  $('e-home').onclick = () => show('menu');
  $('e-again').onclick = () => {
    send(Object.assign({ t: 'find' }, wanted()));
    show('search');
  };

  Sea.init();

  if (tg && tg.BackButton) tg.BackButton.onClick(() => show('menu'));
}

async function openTop(game) {
  S.topGame = S.games.includes(game) ? game : S.game;
  show('top');
  paint();
  const podium = $('t-podium');
  const list = $('t-list');
  const you = $('t-you');
  podium.innerHTML = '';
  list.innerHTML = '';
  you.classList.add('hidden');

  try {
    const data = await (await fetch(`/api/top?limit=100&game=${S.topGame}`)).json();
    if ((data.game || S.topGame) !== S.topGame) return;   // уже переключили вкладку
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
    const own = standing(S.topGame);
    if (!mine && S.profile && own.games) {
      you.innerHTML = boardRow({
        place: own.place,
        name: S.profile.name,
        rating: own.rating,
        wins: own.wins,
        games: own.games,
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
