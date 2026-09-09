/* Крестики-нолики на клиенте: поле три на три и счёт партий.

   Правил тут нет вовсе — сервер говорит, чей ход, что стоит на поле и чем
   кончилась партия, а этот файл только рисует и отправляет нажатие. */

'use strict';

const Tic = (function () {
  const SIZE = 3;

  const V = {
    cells: [],        // клетки поля, по порядку
    grid: null,
    line: null,
    marks: {},        // что где стоит: ключ клетки → 'x' | 'o'
    mine: '',         // мой знак
    myTurn: false,
    round: 0,
    pause: false,     // между партиями поле не трогаем
    opp: '',
    started: false,
  };

  const key = (r, c) => r * SIZE + c;

  /* ── поле ───────────────────────────────────────────────── */

  function build() {
    const box = $('x-grid');
    box.innerHTML = '';
    const cells = document.createElement('div');
    cells.className = 'cells';
    V.cells = [];
    for (let r = 0; r < SIZE; r++) {
      for (let c = 0; c < SIZE; c++) {
        const cell = document.createElement('div');
        cell.className = 'cell';
        cell.dataset.r = r;
        cell.dataset.c = c;
        cells.appendChild(cell);
        V.cells.push(cell);
      }
    }
    const line = document.createElement('div');
    line.className = 'winline hidden';
    cells.appendChild(line);
    V.line = line;
    cells.addEventListener('click', (event) => {
      const cell = event.target.closest('.cell');
      if (cell) tap(Number(cell.dataset.r), Number(cell.dataset.c));
    });
    box.appendChild(cells);
    V.grid = cells;
  }

  function tap(r, c) {
    if (!V.started || V.pause) return;
    if (!V.myTurn) {
      const bar = $('x-turn');
      bar.classList.remove('shake');
      bar.getBoundingClientRect();
      bar.classList.add('shake');
      toast(say('tic.not_your_turn', 'Сейчас ходит соперник'));
      return;
    }
    if (V.marks[key(r, c)]) {
      toast(say('tic.busy', 'Клетка занята'));
      return;
    }
    // Свой знак ставим сразу, не дожидаясь ответа: сервер всё равно
    // пришлёт состояние и поправит, если что-то не так.
    V.cells[key(r, c)].classList.add(V.mine, 'mine', 'fresh');
    send({ t: 'move', row: r, col: c });
    Sound.place();
  }

  /* Выигрышную тройку перечёркиваем — как это делают на бумаге. */
  function drawWin(cells) {
    const line = V.line;
    if (!cells || cells.length < 2) {
      line.classList.add('hidden');
      return;
    }
    const first = V.cells[key(cells[0][0], cells[0][1])];
    const last = V.cells[key(cells[cells.length - 1][0], cells[cells.length - 1][1])];
    const box = V.grid.getBoundingClientRect();
    const a = first.getBoundingClientRect();
    const b = last.getBoundingClientRect();
    const x1 = a.left + a.width / 2 - box.left;
    const y1 = a.top + a.height / 2 - box.top;
    const x2 = b.left + b.width / 2 - box.left;
    const y2 = b.top + b.height / 2 - box.top;
    const length = Math.hypot(x2 - x1, y2 - y1) + a.width * 0.5;
    const angle = Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI;
    line.style.width = `${length}px`;
    line.style.left = `${x1 - a.width * 0.25}px`;
    line.style.top = `${y1}px`;
    line.style.transform = `rotate(${angle}deg)`;
    line.classList.remove('hidden');
  }

  function paintBoard(msg) {
    const fresh = {};
    (msg.cells || []).forEach(([r, c, mark]) => { fresh[key(r, c)] = mark; });
    const last = msg.last ? key(msg.last[0], msg.last[1]) : -1;
    const won = new Set((msg.win || []).map(([r, c]) => key(r, c)));

    V.cells.forEach((cell, i) => {
      const mark = fresh[i];
      cell.className = 'cell';
      if (mark) {
        cell.classList.add(mark);
        if (mark === V.mine) cell.classList.add('mine');
        if (V.marks[i] === undefined) cell.classList.add('fresh');
        if (won.has(i)) cell.classList.add('won');
      }
      if (i === last && mark) cell.classList.add('last');
    });
    V.marks = fresh;
    drawWin(msg.win);
  }

  /* ── счёт и ход ─────────────────────────────────────────── */

  function paintScore(msg) {
    const me = (msg.me && msg.me.score) || 0;
    const opp = (msg.opp && msg.opp.score) || 0;
    $('x-score').innerHTML =
      `<b class="mine">${me}</b><i>:</i><b class="theirs">${opp}</b>`;
    $('x-round').textContent =
      `${say('tic.round', 'партия')} ${msg.round || 1} ${say('tic.of', 'из')} ${msg.rounds || 3}`;
  }

  function paintMarks() {
    const mine = V.mine === 'o' ? '◯' : '✕';
    const theirs = V.mine === 'o' ? '✕' : '◯';
    $('x-marks').innerHTML =
      `<span class="mark-you">${say('tic.you', 'ты')} ${mine}</span>` +
      `<span class="mark-opp">${say('tic.opp', 'он')} ${theirs}</span>`;
  }

  function paintTurn(mine, quiet) {
    const changed = mine !== V.myTurn;
    V.myTurn = mine;
    const bar = $('x-turn');
    bar.classList.toggle('mine', mine);
    bar.classList.toggle('theirs', !mine);
    $('x-turn-who').textContent = mine
      ? say('tic.your_turn', 'Твой ход')
      : say('tic.opp_turn', 'Ход соперника');
    if (changed && mine && !quiet) {
      Sound.turn();
      haptic('ok');
    }
  }

  /* Между партиями вместо «чей ход» — чем кончилась предыдущая. */
  function paintPause(msg) {
    const bar = $('x-turn');
    const end = msg.round_end;
    bar.classList.toggle('mine', end === 'win');
    bar.classList.toggle('theirs', end !== 'win');
    $('x-turn-who').textContent = end === 'win'
      ? say('tic.round.win', 'Партия за тобой!')
      : end === 'loss'
        ? say('tic.round.loss', 'Партию взял соперник')
        : say('tic.round.draw', 'Ничья в этой партии');
    note(say('tic.round.next', 'Начинаем следующую…'), 'calm');
  }

  function note(text, kind) {
    const el = $('x-note');
    el.textContent = text;
    el.className = 'turn-note ' + (kind || '');
  }

  /* ── сообщения сервера ──────────────────────────────────── */

  function begin(found) {
    if (!V.cells.length) build();
    V.marks = {};
    V.mine = '';
    V.myTurn = false;
    V.round = 0;
    V.pause = false;
    V.started = false;
    V.opp = found.opp.name;
    V.cells.forEach((cell) => { cell.className = 'cell'; });
    V.line.classList.add('hidden');
    $('x-round').textContent = `${say('vs', 'против')} ${V.opp}`;
    $('x-score').innerHTML = '';
    note(say('tic.hint', 'Три своих подряд — партия твоя'), 'calm');
    paintMarks();
  }

  function onState(msg) {
    if (!V.cells.length) build();
    const first = !V.started;
    V.started = msg.state === 'running';
    if (msg.mark && msg.mark !== V.mine) {
      V.mine = msg.mark;
      paintMarks();
    }

    // Новая партия — поле очищаем сразу, чтобы старые знаки не мигали.
    if (msg.round !== V.round) {
      V.round = msg.round;
      V.marks = {};
      if (!msg.cells.length) {
        V.cells.forEach((cell) => { cell.className = 'cell'; });
        V.line.classList.add('hidden');
      }
    }

    // Чужой ход слышно: тихий щелчок, как будто соперник поставил знак рядом.
    const last = msg.last ? key(msg.last[0], msg.last[1]) : -1;
    if (last >= 0 && V.marks[last] === undefined && msg.my_turn) Sound.rival();

    paintBoard(msg);
    paintScore(msg);

    V.pause = !!msg.pause_ms;
    if (V.pause) {
      paintPause(msg);
      V.myTurn = false;
    } else {
      paintTurn(!!msg.my_turn, first);
      if (first || !$('x-note').textContent) {
        note(say('tic.hint', 'Три своих подряд — партия твоя'), 'calm');
      }
    }
  }

  function onError(msg) {
    if (msg.reason === 'busy') toast(say('tic.busy', 'Клетка занята'));
    else if (msg.reason === 'not_your_turn') {
      toast(say('tic.not_your_turn', 'Сейчас ходит соперник'));
    }
  }

  /* Итог: последняя партия целиком, с перечёркнутой тройкой. */
  function reveal(container, end) {
    container.innerHTML = '';
    const cells = document.createElement('div');
    cells.className = 'cells';
    const marks = {};
    (end.cells || []).forEach(([r, c, mark]) => { marks[key(r, c)] = mark; });
    const win = new Set((end.win || []).map(([r, c]) => key(r, c)));
    for (let r = 0; r < SIZE; r++) {
      for (let c = 0; c < SIZE; c++) {
        const cell = document.createElement('div');
        const mark = marks[key(r, c)];
        cell.className = 'cell' + (mark ? ` ${mark}` : '') +
          (mark === end.mark ? ' mine' : '') +
          (win.has(key(r, c)) ? ' won' : '');
        cells.appendChild(cell);
      }
    }
    container.appendChild(cells);
  }

  function paint() {
    if (!V.cells.length) return;
    paintMarks();
    if (!V.pause) paintTurn(V.myTurn, true);
  }

  function init() {
    build();
  }

  return {
    SIZE,
    init,
    begin,
    paint,
    reveal,
    state: onState,
    error: onError,
    // Часы отсчитывают время хода, а между партиями — сколько до следующей.
    clock: (msg) => (msg.pause_ms ? msg.pause_ms : msg.turn_ms),
    myTurn: () => V.myTurn,
  };
})();
