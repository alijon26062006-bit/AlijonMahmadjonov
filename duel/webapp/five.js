/* «Пять в ряд» на клиенте: поле, свой знак и перечёркнутая линия победы.

   Правил тут нет вовсе — сервер говорит, чей ход и что стоит на поле,
   а этот файл только рисует и отправляет нажатие по клетке. */

'use strict';

const Five = (function () {
  const SIZE = 9;

  const V = {
    cells: [],        // клетки поля, по порядку
    grid: null,
    marks: {},        // что где стоит: ключ клетки → 'x' | 'o'
    mine: '',         // мой знак
    myTurn: false,
    last: null,
    win: [],
    opp: '',
    ready: false,
  };

  const key = (r, c) => r * SIZE + c;

  /* ── поле ───────────────────────────────────────────────── */

  function build() {
    const box = $('f-grid');
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
    if (!V.ready) return;
    if (!V.myTurn) {
      const bar = $('f-turn');
      bar.classList.remove('shake');
      bar.getBoundingClientRect();
      bar.classList.add('shake');
      toast(say('five.not_your_turn', 'Сейчас ходит соперник'));
      return;
    }
    if (V.marks[key(r, c)]) {
      toast(say('five.busy', 'Клетка занята'));
      return;
    }
    // Свой знак ставим сразу, не дожидаясь ответа: сервер всё равно
    // пришлёт состояние и поправит, если что-то не так.
    V.cells[key(r, c)].classList.add(V.mine, 'mine', 'fresh');
    send({ t: 'move', row: r, col: c });
    Sound.place();
  }

  /* Перечёркиваем выигрышные пять — как это делают на бумаге. */
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
    const length = Math.hypot(x2 - x1, y2 - y1) + a.width * 0.7;
    const angle = Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI;
    line.style.width = `${length}px`;
    line.style.left = `${x1 - a.width * 0.35}px`;
    line.style.top = `${y1}px`;
    line.style.transform = `rotate(${angle}deg)`;
    line.classList.remove('hidden');
  }

  function paintBoard(msg) {
    const fresh = {};
    (msg.cells || []).forEach(([r, c, mark]) => { fresh[key(r, c)] = mark; });
    const last = msg.last ? key(msg.last[0], msg.last[1]) : -1;

    V.cells.forEach((cell, i) => {
      const mark = fresh[i];
      const had = V.marks[i];
      if (mark !== had || !cell.className.includes(mark || 'нет')) {
        cell.className = 'cell';
        if (mark) {
          cell.classList.add(mark);
          if (mark === V.mine) cell.classList.add('mine');
          if (!had) cell.classList.add('fresh');
        }
      }
      cell.classList.toggle('last', i === last);
    });
    V.marks = fresh;
    drawWin(msg.win);
  }

  /* ── чей ход ────────────────────────────────────────────── */

  function paintTurn(mine, quiet) {
    const changed = mine !== V.myTurn;
    V.myTurn = mine;
    const bar = $('f-turn');
    bar.classList.toggle('mine', mine);
    bar.classList.toggle('theirs', !mine);
    $('f-turn-who').textContent = mine
      ? say('five.your_turn', 'Твой ход')
      : say('five.opp_turn', 'Ход соперника');
    if (changed && mine && !quiet) {
      Sound.turn();
      haptic('ok');
    }
  }

  function note(text, kind) {
    const el = $('f-note');
    el.textContent = text;
    el.className = 'turn-note ' + (kind || '');
  }

  function paintMarks() {
    const mine = V.mine === 'o' ? '◯' : '✕';
    const theirs = V.mine === 'o' ? '✕' : '◯';
    $('f-marks').innerHTML =
      `<span class="mark-you">${say('five.you', 'ты')} ${mine}</span>` +
      `<span class="mark-opp">${say('five.opp', 'он')} ${theirs}</span>`;
  }

  /* ── сообщения сервера ──────────────────────────────────── */

  function begin(found) {
    if (!V.cells.length) build();
    V.marks = {};
    V.mine = '';
    V.myTurn = false;
    V.last = null;
    V.win = [];
    V.ready = false;
    V.opp = found.opp.name;
    V.cells.forEach((cell) => { cell.className = 'cell'; });
    V.line.classList.add('hidden');
    $('f-opp-name').textContent = `${say('vs', 'против')} ${V.opp}`;
    note(say('five.hint', 'Пять своих подряд — победа'), 'calm');
    paintMarks();
  }

  function onState(msg) {
    if (!V.cells.length) build();
    const first = !V.ready;
    V.ready = msg.state === 'running';
    if (msg.mark && msg.mark !== V.mine) {
      V.mine = msg.mark;
      paintMarks();
    }
    $('f-opp-name').textContent = V.opp;

    // Чужой ход слышно: тихий щелчок, как будто соперник поставил знак рядом.
    const last = msg.last ? key(msg.last[0], msg.last[1]) : -1;
    const theirs = last >= 0 && V.marks[last] === undefined && !!msg.my_turn;
    if (theirs) Sound.rival();

    paintBoard(msg);
    paintTurn(!!msg.my_turn, first);
    if (msg.state === 'running' && first) {
      note(say('five.hint', 'Пять своих подряд — победа'), 'calm');
    }
  }

  function onError(msg) {
    if (msg.reason === 'busy') toast(say('five.busy', 'Клетка занята'));
    else if (msg.reason === 'not_your_turn') {
      toast(say('five.not_your_turn', 'Сейчас ходит соперник'));
    }
  }

  /* Итог: то же поле целиком, с перечёркнутой линией победы. */
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
    paintTurn(V.myTurn, true);
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
    clock: (msg) => msg.turn_ms,
    myTurn: () => V.myTurn,
  };
})();
