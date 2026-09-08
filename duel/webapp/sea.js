/* Морской бой на клиенте: расстановка кораблей и поле боя.

   Правила здесь только для удобства — чтобы не дать поставить корабль
   впритык и сразу это показать. Решает всё равно сервер: он проверяет
   расстановку, он же говорит, чей ход и попал ты или нет.

   Скрипт подключается раньше app.js и берёт его глобальные функции
   (send, say, toast, $) уже во время игры, когда они давно определены. */

'use strict';

const Sea = (function () {
  const SIZE = 7;
  const FLEET = [3, 2, 2, 1, 1];
  const LETTERS = 'АБВГДЕЖ';

  // Расстановка: корабли по местам флота, выбранный и его поворот.
  const P = {
    ships: [],
    selected: -1,
    horizontal: true,
    locked: false,
    sent: false,
  };

  // Бой: последнее состояние с сервера и собранные поля.
  const V = {
    mode: '',
    myTurn: false,
    enemy: null,
    board: null,
    grids: {},
    pending: null,
    opp: '',
  };

  /* ── геометрия ─────────────────────────────────────────── */

  function cellsOf(ship) {
    const out = [];
    for (let i = 0; i < ship.size; i++) {
      out.push(ship.horizontal ? [ship.row, ship.col + i] : [ship.row + i, ship.col]);
    }
    return out;
  }

  const key = (r, c) => r * SIZE + c;
  const inside = (r, c) => r >= 0 && c >= 0 && r < SIZE && c < SIZE;

  /* Клетки корабля вместе с ободком вокруг: туда другому нельзя. */
  function halo(cells) {
    const out = new Set();
    cells.forEach(([r, c]) => {
      for (let dr = -1; dr <= 1; dr++) {
        for (let dc = -1; dc <= 1; dc++) {
          if (inside(r + dr, c + dc)) out.add(key(r + dr, c + dc));
        }
      }
    });
    return out;
  }

  /* Корабль, который вылез за край, задвигаем обратно: человек нажал
     на клетку у борта, а не просил невозможного. */
  function clamp(ship) {
    const s = Object.assign({}, ship);
    if (s.horizontal) s.col = Math.max(0, Math.min(SIZE - s.size, s.col));
    else s.row = Math.max(0, Math.min(SIZE - s.size, s.row));
    return s;
  }

  function fits(ship, skip) {
    const mine = cellsOf(ship);
    if (!mine.every(([r, c]) => inside(r, c))) return false;
    for (let i = 0; i < P.ships.length; i++) {
      if (i === skip || !P.ships[i]) continue;
      const taken = halo(cellsOf(P.ships[i]));
      if (mine.some(([r, c]) => taken.has(key(r, c)))) return false;
    }
    return true;
  }

  function shipAt(r, c) {
    for (let i = 0; i < P.ships.length; i++) {
      const ship = P.ships[i];
      if (ship && cellsOf(ship).some(([rr, cc]) => rr === r && cc === c)) return i;
    }
    return -1;
  }

  /* Прямоугольник по списку клеток — так корабли приходят с сервера. */
  function box(cells) {
    const rows = cells.map((c) => c[0]);
    const cols = cells.map((c) => c[1]);
    const row = Math.min(...rows);
    const col = Math.min(...cols);
    return { row, col, w: Math.max(...cols) - col + 1, h: Math.max(...rows) - row + 1 };
  }

  /* ── поле ───────────────────────────────────────────────── */

  function makeGrid(container, onTap, coords) {
    container.innerHTML = '';
    container.classList.toggle('nocoords', !coords);

    const cols = document.createElement('div');
    cols.className = 'coords cols';
    for (let c = 0; c < SIZE; c++) cols.innerHTML += `<i>${c + 1}</i>`;
    const rows = document.createElement('div');
    rows.className = 'coords rows';
    for (let r = 0; r < SIZE; r++) rows.innerHTML += `<i>${LETTERS[r]}</i>`;

    const cells = document.createElement('div');
    cells.className = 'cells';
    const list = [];
    for (let r = 0; r < SIZE; r++) {
      for (let c = 0; c < SIZE; c++) {
        const cell = document.createElement('div');
        cell.className = 'cell';
        cell.dataset.r = r;
        cell.dataset.c = c;
        cells.appendChild(cell);
        list.push(cell);
      }
    }
    const ships = document.createElement('div');
    ships.className = 'ships';
    cells.appendChild(ships);

    if (onTap) {
      cells.addEventListener('click', (event) => {
        const cell = event.target.closest('.cell');
        if (cell) onTap(Number(cell.dataset.r), Number(cell.dataset.c));
      });
    }

    container.appendChild(cols);
    container.appendChild(rows);
    container.appendChild(cells);
    return { cells: list, ships, box: cells };
  }

  /* Перерисовать поле целиком. Всё, что на нём есть, — в аргументах:
     корабли (списки клеток), попадания, промахи, последний выстрел. */
  function paintGrid(grid, view) {
    const hits = new Set((view.hits || []).map(([r, c]) => key(r, c)));
    const misses = new Set((view.misses || []).map(([r, c]) => key(r, c)));
    const last = view.last ? key(view.last[0], view.last[1]) : -1;
    const pending = view.pending ? key(view.pending[0], view.pending[1]) : -1;

    grid.cells.forEach((cell, i) => {
      cell.className = 'cell';
      cell.innerHTML = '';
      if (hits.has(i)) cell.classList.add('hit');
      else if (misses.has(i)) cell.classList.add('miss');
      if (i === last) {
        cell.classList.add('last');
        cell.innerHTML = '<div class="aim"></div>';
      }
      if (i === pending && !hits.has(i) && !misses.has(i)) cell.classList.add('pending');
    });

    grid.ships.innerHTML = (view.ships || []).map((ship) => {
      const b = box(ship.cells);
      const cls = ['ship'].concat(ship.classes || []).join(' ');
      return `<div class="${cls}" style="--row:${b.row};--col:${b.col};--w:${b.w};--h:${b.h}"></div>`;
    }).join('');
    grid.box.classList.toggle('locked', !!view.locked);
  }

  /* ── расстановка ────────────────────────────────────────── */

  function resetPlacement() {
    P.ships = FLEET.map(() => null);
    P.selected = 0;
    P.horizontal = true;
    P.locked = false;
    P.sent = false;
  }

  function allPlaced() {
    return P.ships.every(Boolean);
  }

  function selectNext() {
    const next = P.ships.findIndex((s, i) => !s && i > P.selected);
    P.selected = next >= 0 ? next : P.ships.findIndex((s) => !s);
  }

  function tapPlacement(r, c) {
    if (P.locked) return;
    const at = shipAt(r, c);
    if (at >= 0) {
      rotate(at);
      return;
    }
    if (P.selected < 0) {
      toast(say('sea.all_set', 'Все корабли на месте'));
      return;
    }
    const ship = clamp({ row: r, col: c, size: FLEET[P.selected], horizontal: P.horizontal });
    if (!fits(ship, P.selected)) {
      showBad(ship);
      toast(say('sea.place.bad', 'Так нельзя: корабли не должны касаться'));
      return;
    }
    P.ships[P.selected] = ship;
    Sound.place();
    selectNext();
    renderPlacement();
  }

  function rotate(i) {
    const turned = clamp(Object.assign({}, P.ships[i], { horizontal: !P.ships[i].horizontal }));
    if (!fits(turned, i)) {
      showBad(turned);
      toast(say('sea.cant_rotate', 'Так не повернуть — рядом другой корабль'));
      return;
    }
    P.ships[i] = turned;
    Sound.place();
    renderPlacement();
  }

  /* Неудачное место мигает красным пунктиром там, куда пытались поставить. */
  function showBad(ship) {
    renderPlacement({ bad: ship });
    setTimeout(() => renderPlacement(), 350);
  }

  function tapDock(i) {
    if (P.locked) return;
    if (P.ships[i]) {
      // Снять с поля, чтобы переставить.
      P.ships[i] = null;
      P.selected = i;
    } else if (P.selected === i) {
      P.horizontal = !P.horizontal;
    } else {
      P.selected = i;
    }
    renderPlacement();
  }

  function applyLayout(layout) {
    // Сервер отдаёт корабли по убыванию размера, как и во флоте — раздаём по местам.
    const pool = layout.slice();
    P.ships = FLEET.map((size) => {
      const idx = pool.findIndex((s) => s.size === size);
      if (idx < 0) return null;
      const s = pool.splice(idx, 1)[0];
      return { row: s.row, col: s.col, size: size, horizontal: s.horizontal !== false };
    });
    P.selected = P.ships.findIndex((s) => !s);
    renderPlacement();
  }

  function renderPlacement(extra) {
    const grid = V.grids.ownBig;
    const ships = P.ships.filter(Boolean).map((s) => ({
      cells: cellsOf(s),
      classes: P.ships.indexOf(s) === P.selected ? ['sel'] : [],
    }));
    if (extra && extra.bad) ships.push({ cells: cellsOf(extra.bad), classes: ['ghost', 'bad'] });
    paintGrid(grid, { ships, locked: P.locked });

    const dock = $('z-dock');
    dock.innerHTML = FLEET.map((size, i) => {
      const cls = ['dock-ship'];
      if (P.ships[i]) cls.push('placed');
      if (i === P.selected) cls.push('on');
      if (i === P.selected && !P.horizontal) cls.push('vertical');
      return `<button class="${cls.join(' ')}" data-i="${i}">${'<i></i>'.repeat(size)}</button>`;
    }).join('');
    dock.querySelectorAll('.dock-ship').forEach((chip) => {
      chip.onclick = () => tapDock(Number(chip.dataset.i));
    });

    const done = allPlaced();
    $('z-ready').disabled = !done || P.locked;
    $('z-rotate').disabled = P.locked;
    $('z-random').disabled = P.locked;
    $('z-clear').disabled = P.locked;
    $('z-place-hint').textContent = P.locked
      ? ''
      : done
        ? say('sea.all_set', 'Все корабли на месте')
        : say('sea.place.hint', '');
  }

  function ready() {
    if (!allPlaced() || P.locked) return;
    P.locked = true;
    P.sent = true;
    renderPlacement();
    send({ t: 'place', layout: P.ships.map((s) => ({
      row: s.row, col: s.col, size: s.size, horizontal: s.horizontal,
    })) });
  }

  function onPlaced(msg) {
    if (msg.ok) {
      showWaiting(say('sea.waiting_opp', 'Соперник ещё расставляет…'));
      return;
    }
    P.locked = false;
    P.sent = false;
    renderPlacement();
    toast(say('sea.place.bad', msg.error || 'Так нельзя'));
  }

  function showWaiting(text) {
    $('z-wait').classList.remove('hidden');
    $('z-wait-text').textContent = text;
    $('z-ready').classList.add('hidden');
    $('z-actions').classList.add('hidden');
    $('z-dock').classList.add('hidden');
  }

  /* ── режимы экрана ──────────────────────────────────────── */

  function setMode(mode) {
    if (V.mode === mode) return;
    V.mode = mode;
    const placing = mode === 'placing';
    $('z-place').classList.toggle('hidden', !placing);
    $('z-own-big').classList.toggle('hidden', !placing);
    $('z-dock').classList.toggle('hidden', !placing);
    $('z-actions').classList.toggle('hidden', !placing);
    $('z-ready').classList.toggle('hidden', !placing);
    $('z-wait').classList.add('hidden');
    $('z-enemy').classList.toggle('hidden', placing);
    $('z-turn').classList.toggle('hidden', placing);
    $('z-mid').classList.toggle('hidden', placing);
    $('z-enemy-fleet').classList.toggle('hidden', placing);
    paintLabels();
  }

  function paintLabels() {
    const placing = V.mode === 'placing';
    $('z-enemy-label').textContent = placing
      ? say('sea.you', 'ТЫ')
      : say('sea.enemy', 'СОПЕРНИК');
    // Пока расставляем, наверху своё поле — и подпись «против такого-то».
    $('z-opp-name').textContent = placing
      ? `${say('vs', 'против')} ${V.opp}`
      : V.opp;
    $('z-you-label').textContent = say('sea.you', 'ТЫ');
  }

  /* ── бой ────────────────────────────────────────────────── */

  function tapEnemy(r, c) {
    if (V.mode !== 'battle' || !V.enemy) return;
    if (!V.myTurn) {
      const bar = $('z-turn');
      bar.classList.remove('shake');
      bar.getBoundingClientRect();
      bar.classList.add('shake');
      toast(say('sea.not_your_turn', 'Сейчас ходит соперник'));
      return;
    }
    const known = V.enemy.hits.concat(V.enemy.misses);
    if (known.some(([rr, cc]) => rr === r && cc === c)) {
      toast(say('sea.repeat', 'Сюда уже стреляли'));
      return;
    }
    V.pending = [r, c];
    send({ t: 'fire', row: r, col: c });
    Sound.fire();
    paintEnemy();
  }

  function paintEnemy() {
    const e = V.enemy || { hits: [], misses: [], sunk: [], alive: FLEET.length };
    paintGrid(V.grids.enemy, {
      hits: e.hits,
      misses: e.misses,
      last: e.last,
      pending: V.pending,
      ships: (e.sunk || []).map((cells) => ({ cells, classes: ['sunk'] })),
    });
    $('z-enemy').classList.toggle('waiting', !V.myTurn);
  }

  function paintOwn(board, last) {
    if (!board) return;
    const hits = new Set(board.hits.map(([r, c]) => key(r, c)));
    paintGrid(V.grids.own, {
      hits: board.hits,
      misses: board.misses,
      last,
      ships: board.ships.map((cells) => ({
        cells,
        classes: cells.every(([r, c]) => hits.has(key(r, c))) ? ['sunk'] : [],
      })),
    });
  }

  function paintFleet(sunk) {
    // Потопленные вычёркиваем по размерам: два двухпалубных — два штриха.
    const gone = (sunk || []).map((cells) => cells.length);
    $('z-enemy-fleet').innerHTML = FLEET.map((size) => {
      const idx = gone.indexOf(size);
      const isSunk = idx >= 0;
      if (isSunk) gone.splice(idx, 1);
      return `<i class="fd ${isSunk ? 'sunk' : ''}">${'<b></b>'.repeat(size)}</i>`;
    }).join('');
  }

  /* Чей ход — главная строка экрана. Когда ход переходит к тебе, она
     подпрыгивает и звенит: пропустить свой ход обидно. */
  function paintTurn(mine, quiet) {
    const changed = mine !== V.myTurn;
    V.myTurn = mine;
    const bar = $('z-turn');
    bar.classList.toggle('mine', mine);
    bar.classList.toggle('theirs', !mine);
    $('z-turn-who').textContent = mine
      ? say('sea.your_turn', 'Твой ход')
      : say('sea.opp_turn', 'Ход соперника');
    if (changed && mine && !quiet) {
      Sound.turn();
      haptic('ok');
    }
  }

  function note(text, kind) {
    const el = $('z-note');
    el.textContent = text;
    el.className = 'turn-note ' + (kind || '');
    el.getBoundingClientRect();
    el.classList.add('boom');
  }

  /* ── сообщения сервера ──────────────────────────────────── */

  function begin(found) {
    resetPlacement();
    V.mode = '';
    V.myTurn = false;
    V.enemy = null;
    V.board = null;
    V.pending = null;
    V.opp = found.opp.name;
    $('z-note').textContent = '';
    $('z-note').className = 'turn-note';
    setMode('placing');
    $('z-wait').classList.add('hidden');
    paintFleet([]);
    renderPlacement();
  }

  function onState(msg) {
    if (msg.state === 'placing') {
      setMode('placing');
      if (msg.me.placed && !P.sent) {
        // Время вышло — сервер расставил сам. Показываем его расстановку.
        P.ships = msg.me.board.ships.map((cells) => {
          const b = box(cells);
          return { row: b.row, col: b.col, size: cells.length, horizontal: b.w >= b.h };
        });
        P.locked = true;
        P.sent = true;
        renderPlacement();
        showWaiting(say('sea.auto', 'Время вышло — корабли расставлены за тебя'));
      } else if (msg.me.placed && P.locked) {
        showWaiting(msg.opp.placed
          ? say('sea.opp_ready', 'Соперник готов')
          : say('sea.waiting_opp', 'Соперник ещё расставляет…'));
      } else if (msg.opp.placed) {
        $('z-place-hint').textContent = say('sea.opp_ready', 'Соперник готов');
      }
      return;
    }

    const first = V.mode !== 'battle';
    setMode('battle');
    V.enemy = msg.enemy;
    V.board = msg.me.board;
    if (V.pending && msg.enemy.last &&
        V.pending[0] === msg.enemy.last[0] && V.pending[1] === msg.enemy.last[1]) {
      V.pending = null;
    }
    paintTurn(!!msg.my_turn, first);
    paintEnemy();
    paintOwn(msg.me.board, msg.opp.last);
    paintFleet(msg.enemy.sunk);
    if (first) {
      note(msg.my_turn
        ? say('sea.aim', 'Стреляй по полю соперника')
        : say('sea.wait_shot', 'Соперник целится…'), 'calm');
    }
  }

  function onShot(msg) {
    V.pending = null;
    if (msg.result === 'not_your_turn') {
      toast(say('sea.not_your_turn', 'Сейчас ходит соперник'));
      return;
    }
    if (msg.result === 'repeat') {
      toast(say('sea.repeat', 'Сюда уже стреляли'));
      return;
    }
    if (msg.result === 'miss') {
      Sound.miss();
      note(say('sea.miss', 'Мимо — ход соперника'), 'calm');
    } else if (msg.result === 'hit') {
      Sound.hit();
      haptic('ok');
      note(say('sea.hit', 'Ранил! Стреляй ещё'), 'ok');
    } else if (msg.result === 'sunk') {
      Sound.sunk();
      haptic('win');
      note(say('sea.sunk', 'Убил! Стреляй ещё'), 'ok');
    }
  }

  function onIncoming(msg) {
    if (msg.result === 'miss') {
      note(say('sea.incoming.miss', 'Соперник промахнулся'), 'calm');
      return;
    }
    Sound.incoming(msg.result === 'sunk');
    haptic('bad');
    note(msg.result === 'sunk'
      ? say('sea.incoming.sunk', 'Твой корабль потоплен')
      : say('sea.incoming.hit', 'В тебя попали'));
    const own = $('z-mid');
    own.classList.remove('quake');
    own.getBoundingClientRect();
    own.classList.add('quake');
  }

  /* На экране итога — поле соперника целиком: где стоял флот и куда ты бил. */
  function reveal(container, end) {
    const grid = makeGrid(container, null, true);
    // Сервер присылает поле соперника целиком: с последним выстрелом,
    // после которого состояния уже не было.
    const e = end.enemy_view || V.enemy || { hits: [], misses: [] };
    const hits = new Set(e.hits.map(([r, c]) => key(r, c)));
    paintGrid(grid, {
      hits: e.hits,
      misses: e.misses,
      ships: (end.enemy_fleet || []).map((cells) => ({
        cells,
        classes: cells.every(([r, c]) => hits.has(key(r, c))) ? ['sunk'] : [],
      })),
      locked: true,
    });
  }

  function paint() {
    paintLabels();
    $('e-reveal-label').textContent = say('result.enemy_fleet', 'Флот соперника');
    if (V.mode === 'placing') renderPlacement();
    else if (V.mode === 'battle') paintTurn(V.myTurn, true);
  }

  function init() {
    V.grids.ownBig = makeGrid($('z-own-big'), tapPlacement, true);
    V.grids.enemy = makeGrid($('z-enemy'), tapEnemy, true);
    V.grids.own = makeGrid($('z-own'), null, true);
    $('z-rotate').onclick = () => {
      if (P.locked) return;
      if (P.selected >= 0 && !P.ships[P.selected]) P.horizontal = !P.horizontal;
      renderPlacement();
    };
    $('z-random').onclick = () => { if (!P.locked) send({ t: 'sea_random' }); };
    $('z-clear').onclick = () => {
      if (P.locked) return;
      resetPlacement();
      renderPlacement();
    };
    $('z-ready').onclick = ready;
    resetPlacement();
    renderPlacement();
  }

  return {
    FLEET,
    init,
    begin,
    paint,
    state: onState,
    shot: onShot,
    incoming: onIncoming,
    placed: onPlaced,
    layout: (msg) => { if (!P.locked) applyLayout(msg.layout || []); },
    reveal,
    mode: () => V.mode,
    myTurn: () => V.myTurn,
  };
})();
