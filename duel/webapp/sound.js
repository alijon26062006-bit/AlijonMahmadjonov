/* Звук игры. Всё синтезируется прямо в браузере: ни одного скачанного файла,
   поэтому игра открывается мгновенно и звучит одинаково на любом телефоне.

   Ноты берутся из пентатоники — в ней любые две ноты сочетаются, поэтому
   длинная серия верных ответов складывается в мелодию и никогда не фальшивит. */

'use strict';

const Sound = (function () {
  // До-мажорная пентатоника, две октавы: чем длиннее серия, тем выше нота.
  const SCALE = [
    523.25, 587.33, 659.25, 783.99,
    880.0, 1046.5, 1174.66, 1318.51,
  ];

  // Фоновая музыка: Am – F – C – G. Спокойный круг, под него хорошо считается.
  const CHORDS = [
    [220.0, 261.63, 329.63],
    [174.61, 220.0, 261.63],
    [130.81, 196.0, 261.63],
    [196.0, 246.94, 293.66],
  ];
  const STEPS_PER_CHORD = 8;
  const CALM_STEP = 0.3;
  const HURRY_STEP = 0.22;

  let ctx = null;
  let master = null;
  let sfxBus = null;
  let musicBus = null;

  let sfxOn = true;
  let musicOn = true;
  let playing = false;
  let hurried = false;
  let step = 0;
  let nextAt = 0;
  let timer = 0;

  function ensure() {
    if (ctx) return ctx;
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return null;
    try {
      ctx = new Ctor();
    } catch (e) {
      return null;
    }
    master = ctx.createGain();
    master.gain.value = 0.9;
    master.connect(ctx.destination);

    sfxBus = ctx.createGain();
    sfxBus.gain.value = 1;
    sfxBus.connect(master);

    // Музыка заметно тише звуков: она фон, а не главное.
    musicBus = ctx.createGain();
    musicBus.gain.value = 0;
    musicBus.connect(master);
    return ctx;
  }

  /* Один голос: осциллятор через фильтр и огибающую. Из таких кирпичиков
     собраны все звуки — от щелчка до победного перебора. */
  function voice(options) {
    if (!ctx) return;
    const o = options || {};
    const at = o.time || ctx.currentTime;
    const dur = o.dur || 0.3;
    const peak = o.gain || 0.12;

    const osc = ctx.createOscillator();
    osc.type = o.type || 'triangle';
    osc.frequency.setValueAtTime(o.freq, at);
    if (o.glide) {
      osc.frequency.exponentialRampToValueAtTime(
        Math.max(30, o.freq * o.glide), at + dur
      );
    }

    const filter = ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.setValueAtTime(o.cutoff || 4200, at);

    const env = ctx.createGain();
    env.gain.setValueAtTime(0.0001, at);
    env.gain.exponentialRampToValueAtTime(peak, at + (o.attack || 0.012));
    env.gain.exponentialRampToValueAtTime(0.0001, at + dur);

    osc.connect(filter).connect(env).connect(o.bus || sfxBus);
    osc.start(at);
    osc.stop(at + dur + 0.05);
  }

  function sfx(options) {
    if (!sfxOn || !ensure()) return;
    voice(options);
  }

  /* Шум через фильтр: взрывы, всплески, выстрелы. Осциллятором такого
     не получить — там нет случайности, а взрыв ею и звучит. */
  let noiseBuffer = null;
  function burst(options) {
    if (!sfxOn || !ensure()) return;
    const o = options || {};
    const at = o.time || ctx.currentTime;
    const dur = o.dur || 0.3;
    if (!noiseBuffer) {
      noiseBuffer = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
      const data = noiseBuffer.getChannelData(0);
      for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
    }
    const src = ctx.createBufferSource();
    src.buffer = noiseBuffer;
    src.loop = true;

    const filter = ctx.createBiquadFilter();
    filter.type = o.filter || 'lowpass';
    filter.frequency.setValueAtTime(o.cutoff || 1200, at);
    if (o.sweep) {
      filter.frequency.exponentialRampToValueAtTime(
        Math.max(40, (o.cutoff || 1200) * o.sweep), at + dur
      );
    }
    filter.Q.value = o.q || 0.7;

    const env = ctx.createGain();
    env.gain.setValueAtTime(0.0001, at);
    env.gain.exponentialRampToValueAtTime(o.gain || 0.2, at + (o.attack || 0.008));
    env.gain.exponentialRampToValueAtTime(0.0001, at + dur);

    src.connect(filter).connect(env).connect(sfxBus);
    src.start(at);
    src.stop(at + dur + 0.05);
  }

  /* Небольшой перебор нот: победа, поражение, старт. */
  function phrase(freqs, gap, options) {
    if (!sfxOn || !ensure()) return;
    const start = ctx.currentTime;
    freqs.forEach(function (freq, i) {
      voice(Object.assign({ freq: freq, time: start + i * gap }, options));
    });
  }

  // ── фоновая музыка ────────────────────────────────────────

  function stepDur() {
    return hurried ? HURRY_STEP : CALM_STEP;
  }

  function playStep(index, at) {
    const chord = CHORDS[Math.floor(index / STEPS_PER_CHORD) % CHORDS.length];
    const inChord = index % STEPS_PER_CHORD;
    const note = chord[inChord % chord.length] * (inChord >= 4 ? 2 : 1);

    voice({
      freq: note,
      time: at,
      type: 'triangle',
      dur: stepDur() * 2.2,
      gain: 0.1,
      cutoff: 1600,
      attack: 0.05,
      bus: musicBus,
    });

    // Бас на смене аккорда — держит круг вместе.
    if (inChord === 0) {
      voice({
        freq: chord[0] / 2,
        time: at,
        type: 'sine',
        dur: stepDur() * 6,
        gain: 0.16,
        cutoff: 420,
        attack: 0.08,
        bus: musicBus,
      });
    }

    // Последние секунды: тихий пульс, чтобы чувствовалось время.
    if (hurried && inChord % 2 === 0) {
      voice({
        freq: 90,
        time: at,
        type: 'sine',
        dur: 0.16,
        gain: 0.22,
        glide: 0.6,
        cutoff: 300,
        bus: musicBus,
      });
    }
  }

  /* Ноты ставятся в очередь заранее: если считать их по таймеру страницы,
     ритм поплывёт, как только браузер отвлечётся на отрисовку. */
  function schedule() {
    if (!playing || !ctx) return;
    while (nextAt < ctx.currentTime + 0.25) {
      if (nextAt < ctx.currentTime) nextAt = ctx.currentTime + 0.02;
      playStep(step, nextAt);
      nextAt += stepDur();
      step += 1;
    }
  }

  function fadeMusic(to, seconds) {
    if (!ctx || !musicBus) return;
    const now = ctx.currentTime;
    musicBus.gain.cancelScheduledValues(now);
    musicBus.gain.setValueAtTime(musicBus.gain.value, now);
    musicBus.gain.linearRampToValueAtTime(to, now + seconds);
  }

  const api = {
    /* iOS и Android не дают звучать, пока человек сам чего-нибудь не коснётся,
       поэтому звук просыпается на первом же касании экрана. */
    unlock: function () {
      const c = ensure();
      if (c && c.state === 'suspended') c.resume();
    },

    setSfx: function (on) {
      sfxOn = !!on;
    },

    setMusic: function (on) {
      musicOn = !!on;
      if (!musicOn) api.stopMusic();
      else if (playing) fadeMusic(0.35, 0.6);
    },

    // ── звуки игры ──────────────────────────────────────────

    tick: function () {
      sfx({ freq: 660, type: 'sine', dur: 0.12, gain: 0.14, cutoff: 2600 });
    },

    go: function () {
      phrase([523.25, 659.25, 783.99], 0.06, {
        type: 'triangle', dur: 0.4, gain: 0.16, cutoff: 5000,
      });
    },

    match: function () {
      phrase([440, 659.25], 0.11, {
        type: 'triangle', dur: 0.32, gain: 0.15, cutoff: 4000,
      });
    },

    /* Верный ответ. Нота растёт вместе с серией — получается лесенка вверх,
       и слышно, что идёшь в гору. */
    correct: function (streak, step) {
      const index = Math.min(SCALE.length - 1, Math.max(0, (streak || 1) - 1));
      const freq = SCALE[index];
      sfx({ freq: freq, type: 'triangle', dur: 0.26, gain: 0.2, cutoff: 5400 });
      sfx({ freq: freq * 2, type: 'sine', dur: 0.16, gain: 0.06, cutoff: 6000 });
      if (step > 1) {
        // Двойной рывок — добавляем квинту сверху, звучит вдвое весомее.
        sfx({
          freq: freq * 1.5, type: 'triangle', dur: 0.3,
          gain: 0.12, cutoff: 5400, attack: 0.05,
        });
      }
    },

    /* Ошибка: глухой мягкий толчок, а не резкий писк — ругаться незачем. */
    wrong: function () {
      sfx({ freq: 190, type: 'sine', dur: 0.3, gain: 0.13, glide: 0.45, cutoff: 700 });
      sfx({ freq: 126, type: 'triangle', dur: 0.24, gain: 0.075, glide: 0.5, cutoff: 480 });
    },

    /* Соперник ответил: тихий далёкий щелчок, чтобы чувствовать его темп. */
    rival: function () {
      sfx({ freq: 300, type: 'sine', dur: 0.13, gain: 0.05, cutoff: 1100 });
    },

    win: function () {
      phrase([523.25, 659.25, 783.99, 1046.5], 0.1, {
        type: 'triangle', dur: 0.55, gain: 0.18, cutoff: 5200,
      });
    },

    lose: function () {
      phrase([440, 349.23, 261.63], 0.13, {
        type: 'triangle', dur: 0.5, gain: 0.15, cutoff: 2200,
      });
    },

    draw: function () {
      phrase([523.25, 523.25], 0.16, {
        type: 'triangle', dur: 0.4, gain: 0.14, cutoff: 3000,
      });
    },

    // ── морской бой ─────────────────────────────────────────

    /* Выстрел: короткий глухой хлопок. */
    fire: function () {
      burst({ dur: 0.14, gain: 0.2, cutoff: 900, sweep: 0.3 });
      sfx({ freq: 140, type: 'sine', dur: 0.12, gain: 0.12, glide: 0.5, cutoff: 500 });
    },

    /* Мимо: всплеск — шипящий шум с быстрым спадом. */
    miss: function () {
      burst({ dur: 0.35, gain: 0.1, cutoff: 3200, sweep: 0.25, filter: 'bandpass', q: 0.9 });
      sfx({ freq: 420, type: 'sine', dur: 0.14, gain: 0.05, glide: 1.6, cutoff: 2200 });
    },

    /* Попадание: взрыв — низкий шум и удар. */
    hit: function () {
      burst({ dur: 0.45, gain: 0.32, cutoff: 700, sweep: 0.15 });
      sfx({ freq: 110, type: 'triangle', dur: 0.32, gain: 0.18, glide: 0.35, cutoff: 600 });
    },

    /* Потопил: взрыв побольше и короткий победный ход вверх. */
    sunk: function () {
      burst({ dur: 0.7, gain: 0.38, cutoff: 900, sweep: 0.1 });
      sfx({ freq: 90, type: 'triangle', dur: 0.5, gain: 0.2, glide: 0.3, cutoff: 500 });
      phrase([659.25, 783.99, 1046.5], 0.09, {
        type: 'triangle', dur: 0.3, gain: 0.12, cutoff: 5000,
      });
    },

    /* В тебя попали: тот же взрыв, но приглушённый и без радости. */
    incoming: function (sunk) {
      burst({ dur: sunk ? 0.6 : 0.4, gain: sunk ? 0.3 : 0.2, cutoff: 500, sweep: 0.2 });
      sfx({ freq: 160, type: 'sine', dur: 0.35, gain: 0.12, glide: 0.4, cutoff: 500 });
      if (sunk) {
        phrase([392, 329.63, 261.63], 0.12, {
          type: 'triangle', dur: 0.35, gain: 0.1, cutoff: 2000,
        });
      }
    },

    /* Корабль поставлен: тихий карандашный щелчок. */
    place: function () {
      sfx({ freq: 880, type: 'sine', dur: 0.07, gain: 0.08, cutoff: 3000 });
    },

    // ── музыка ──────────────────────────────────────────────

    startMusic: function () {
      if (!musicOn || !ensure() || playing) return;
      playing = true;
      hurried = false;
      step = 0;
      nextAt = ctx.currentTime + 0.1;
      fadeMusic(0.35, 1.2);
      clearInterval(timer);
      timer = setInterval(schedule, 40);
      schedule();
    },

    stopMusic: function () {
      if (!playing) return;
      playing = false;
      clearInterval(timer);
      timer = 0;
      fadeMusic(0, 0.5);
    },

    /* Последние секунды матча: музыка ускоряется и добавляется пульс. */
    hurry: function (on) {
      hurried = !!on;
    },

    /* Вкладку свернули — музыка замолкает, чтобы не играть в кармане. */
    mute: function (on) {
      if (!ctx || !master) return;
      master.gain.setTargetAtTime(on ? 0 : 0.9, ctx.currentTime, 0.05);
    },
  };

  return api;
})();
