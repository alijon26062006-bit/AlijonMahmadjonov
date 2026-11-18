// Адаптивный движок «Буки». Чистая логика без DOM — покрыта тестами (tests/engine.test.mjs).
//
// Три идеи, на которых держится обучение:
// 1. Модель ученика по Эло: у ученика есть «сила» θ, у каждого типа задания и слова — сложность.
//    Вероятность правильного ответа p = σ(θ + знание_слова − сложность).
// 2. «Зона ближайшего развития»: задание выбирается так, чтобы p ≈ 0.78 — не скучно и не больно.
//    После ошибок цель смещается к лёгкому (0.9), на серии правильных — к трудному (0.68).
// 3. Интервальные повторения (коробки Лейтнера): слово, которое помнишь, возвращается
//    через 1, 2, 4, 7, 14, 30 дней; ошибка опускает его вниз.

// ---------- Утилиты ----------

export const vals = (v) => (Array.isArray(v) ? v : [v]);
export const canon = (v) => vals(v)[0];

export function mulberry32(seed) {
  let a = seed >>> 0;
  return function rng() {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function shuffle(arr, rng = Math.random) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

const sigmoid = (x) => 1 / (1 + Math.exp(-x));

// ---------- Текст: нормализация, проверка, транслит ----------

const EN_CONTRACTIONS = [
  [/\bi'm\b/g, 'i am'], [/\byou're\b/g, 'you are'], [/\bwe're\b/g, 'we are'],
  [/\bthey're\b/g, 'they are'], [/\bhe's\b/g, 'he is'], [/\bshe's\b/g, 'she is'],
  [/\bit's\b/g, 'it is'], [/\bwhat's\b/g, 'what is'], [/\bwhere's\b/g, 'where is'],
  [/\bdon't\b/g, 'do not'], [/\bdoesn't\b/g, 'does not'], [/\bcan't\b/g, 'cannot'],
  [/\bisn't\b/g, 'is not'], [/\baren't\b/g, 'are not'], [/\bthat's\b/g, 'that is'],
];

// Таджикские буквы → русские: многие пишут без таджикской раскладки (ҳ→х, ӯ→у…).
const TG_FOLD = { 'ҳ': 'х', 'қ': 'к', 'ғ': 'г', 'ҷ': 'ч', 'ӣ': 'и', 'ӯ': 'у' };

export function normalize(s, lang) {
  let t = String(s).toLowerCase().replace(/[’`]/g, "'").replace(/ё/g, 'е');
  if (lang === 'en') for (const [re, rep] of EN_CONTRACTIONS) t = t.replace(re, rep);
  if (lang === 'tg') t = t.replace(/[ҳқғҷӣӯ]/g, (c) => TG_FOLD[c]);
  t = t
    .replace(/[.,!?;:«»"“”()…]/g, ' ')
    .replace(/(^|\s)[-–—]+|[-–—]+(\s|$)/g, ' ') // тире как знак препинания, но не дефис внутри слова
    .replace(/\s+/g, ' ')
    .trim();
  return t;
}

// Слова для плиток «собери предложение» (сохраняем регистр, убираем пунктуацию).
export function tokenize(s) {
  return String(s)
    .replace(/[.,!?;:«»"“”()…]/g, ' ')
    .split(/\s+/)
    .map((w) => w.replace(/^[-–—]+|[-–—]+$/g, ''))
    .filter(Boolean);
}

const TR = {
  а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'yo', ж: 'zh', з: 'z', и: 'i', й: 'y',
  к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u', ф: 'f',
  х: 'kh', ц: 'ts', ч: 'ch', ш: 'sh', щ: 'shch', ъ: '', ы: 'y', ь: "'", э: 'e', ю: 'yu', я: 'ya',
};

export function translit(s) {
  return String(s).replace(/[а-яё]/gi, (ch) => {
    const low = ch.toLowerCase();
    const r = TR[low] ?? ch;
    return ch === low ? r : r.charAt(0).toUpperCase() + r.slice(1);
  });
}

// Грубое сравнение латиницей — для тех, у кого нет русской раскладки.
const latinKey = (s) => normalize(translit(s), 'ru').replace(/'/g, '').replace(/kh/g, 'h').replace(/[jy]/g, 'i');

// Расстояние редактирования; перестановка соседних букв («studnet») — одна опечатка.
export function levenshtein(a, b) {
  if (a === b) return 0;
  const m = a.length, n = b.length;
  if (!m) return n;
  if (!n) return m;
  const d = Array.from({ length: m + 1 }, (_, i) => [i, ...Array(n).fill(0)]);
  for (let j = 0; j <= n; j++) d[0][j] = j;
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
    }
  }
  return d[m][n];
}

// Проверка ответа. Мягкая: регистр, пунктуация, ё/е, сокращения не важны;
// одна опечатка в длинном слове засчитывается (с пометкой «опечатка»).
export function checkAnswer(answer, accepted, lang, { lenient = true } = {}) {
  const a = normalize(answer, lang);
  const list = vals(accepted);
  if (!a) return { ok: false, typo: false, solution: list[0] };
  for (const acc of list) if (normalize(acc, lang) === a) return { ok: true, typo: false, solution: acc };
  if (lang === 'ru' && /^[a-z0-9' -]+$/.test(a)) {
    for (const acc of list) if (latinKey(acc) === latinKey(a)) return { ok: true, typo: false, solution: acc, latin: true };
  }
  if (lenient) {
    for (const acc of list) {
      const n = normalize(acc, lang);
      const budget = n.length >= 12 ? 2 : n.length >= 5 ? 1 : 0;
      if (budget && levenshtein(a, n) <= budget) return { ok: true, typo: true, solution: acc };
    }
  }
  return { ok: false, typo: false, solution: list[0] };
}

// ---------- Курс ----------

export function buildCourse(units, course) {
  const items = {};
  const unitItems = [];
  units.forEach((u, ui) => {
    const ids = [];
    for (const w of u.words) {
      items[w.id] = { id: w.id, kind: 'word', unit: ui, t: vals(w[course.target]), n: vals(w[course.native]), e: w.e || null };
      ids.push(w.id);
    }
    for (const s of u.sentences) {
      const t = vals(s[course.target]);
      items[s.id] = { id: s.id, kind: 'sentence', unit: ui, t, n: vals(s[course.native]), len: tokenize(t[0]).length };
      ids.push(s.id);
    }
    unitItems.push(ids);
  });
  // Словарик для подсказок по нажатию на слово.
  const dict = {};
  for (const it of Object.values(items)) {
    if (it.kind !== 'word') continue;
    for (const t of it.t) dict[normalize(t, course.target)] = it.n[0];
    for (const n of it.n) dict[normalize(n, course.native)] = it.t[0];
  }
  return { ...course, units, items, unitItems, dict };
}

// План юнита: 3 урока с новым материалом + «закрепление».
export function lessonPlan(courseData, unitIdx) {
  const u = courseData.units[unitIdx];
  const words = u.words.map((w) => w.id);
  const sents = u.sentences.map((s) => s.id);
  const half = Math.ceil(words.length / 2);
  const s3 = Math.ceil(sents.length / 3);
  return [
    { kind: 'learn', ids: [...words.slice(0, half), ...sents.slice(0, s3)] },
    { kind: 'learn', ids: [...words.slice(half), ...sents.slice(s3, s3 * 2)] },
    { kind: 'learn', ids: sents.slice(s3 * 2) },
    { kind: 'review', ids: [...words, ...sents] },
  ];
}

// ---------- Модель ученика ----------

export const INTERVAL_DAYS = [0, 1, 2, 4, 7, 14, 30];
export const MAX_BOX = INTERVAL_DAYS.length - 1;
const DAY = 86400000;

export function newLearner() {
  return {
    theta: 0,
    answers: 0,
    items: {},
    done: {}, // unitIdx -> [lessonIdx, ...]
    skills: { vocab: { r: 0, t: 0 }, listen: { r: 0, t: 0 }, write: { r: 0, t: 0 }, sentence: { r: 0, t: 0 } },
    placed: false,
  };
}

export function itemState(learner, id) {
  if (!learner.items[id]) learner.items[id] = { box: 0, due: 0, seen: 0, right: 0, wrong: 0, d: 0 };
  return learner.items[id];
}

export function isLessonDone(learner, u, l) {
  return (learner.done[u] || []).includes(l);
}

// Текущая позиция на тропе: первый непройденный урок.
export function currentNode(courseData, learner) {
  for (let u = 0; u < courseData.units.length; u++) {
    const plan = lessonPlan(courseData, u);
    for (let l = 0; l < plan.length; l++) if (!isLessonDone(learner, u, l)) return { u, l };
  }
  return null; // курс пройден
}

export function markLessonDone(learner, u, l) {
  const arr = learner.done[u] || (learner.done[u] = []);
  if (!arr.includes(l)) arr.push(l);
}

// Слабость слова: чем выше — тем нужнее повторить.
export function weakness(st, now) {
  const overdue = st.due ? Math.max(0, (now - st.due) / DAY) : 0;
  const errRate = (st.wrong + 1) / (st.right + st.wrong + 2);
  return (MAX_BOX - st.box) + errRate * 3 + Math.min(overdue, 10) * 0.3;
}

export function pickReview(courseData, learner, { exclude = [], max = 3, maxUnit = Infinity, now = Date.now(), dueOnly = false } = {}) {
  const ex = new Set(exclude);
  const cands = Object.entries(learner.items)
    .filter(([id, st]) => st.seen > 0 && !ex.has(id) && courseData.items[id] && courseData.items[id].unit <= maxUnit)
    .filter(([, st]) => !dueOnly || st.due <= now)
    .map(([id, st]) => ({ id, w: weakness(st, now) }))
    .sort((a, b) => b.w - a.w);
  return cands.slice(0, max).map((c) => c.id);
}

// ---------- Типы заданий ----------

export const TYPES = {
  pick_image:    { base: -1.6, skill: 'vocab',    for: 'word',     recog: true },
  choose_t2n:    { base: -1.3, skill: 'vocab',    for: 'word',     recog: true },
  choose_n2t:    { base: -1.0, skill: 'vocab',    for: 'word',     recog: true },
  listen_choose: { base: -0.3, skill: 'listen',   for: 'word',     audio: true },
  type_n2t:      { base: 1.0,  skill: 'write',    for: 'word' },
  bank_t2n:      { base: -0.4, skill: 'sentence', for: 'sentence', recog: true },
  bank_n2t:      { base: 0.2,  skill: 'sentence', for: 'sentence' },
  listen_bank:   { base: 0.8,  skill: 'listen',   for: 'sentence', audio: true },
  type_sent:     { base: 1.8,  skill: 'write',    for: 'sentence' },
  match:         { base: -0.9, skill: 'vocab',    for: 'group' },
};

export function pCorrect(learner, item, type) {
  const st = learner.items[item.id] || { box: 0, d: 0 };
  const lenD = item.kind === 'sentence' ? Math.max(0, item.len - 3) * 0.15 : 0;
  return sigmoid(learner.theta + 0.35 * st.box - TYPES[type].base - (st.d || 0) - lenD);
}

// Выбор типа задания под текущее состояние ученика.
export function pickType(learner, item, ctx, rng = Math.random) {
  const st = learner.items[item.id];
  const firstTime = !st || st.seen === 0;
  let cands = Object.keys(TYPES).filter((k) => TYPES[k].for === item.kind);
  if (!ctx.audio) cands = cands.filter((k) => !TYPES[k].audio);
  if (!item.e) cands = cands.filter((k) => k !== 'pick_image');
  // Сначала узнавание, потом воспроизведение: новое слово не просим писать по памяти.
  if (ctx.exposure === 0 && firstTime) cands = cands.filter((k) => TYPES[k].recog);
  if (ctx.forceEasy) cands = cands.filter((k) => TYPES[k].base <= -0.3);
  if (ctx.allowed) cands = cands.filter((k) => ctx.allowed.includes(k));
  if (!cands.length) cands = item.kind === 'word' ? ['choose_n2t'] : ['bank_t2n'];

  let target = ctx.target ?? 0.78;
  if (ctx.wrongStreak >= 1) target = 0.9;
  else if (ctx.combo >= 3) target = Math.max(0.6, target - 0.1);

  let best = null, bestScore = -Infinity;
  for (const k of cands) {
    const p = pCorrect(learner, item, k);
    let score = -Math.abs(p - target) + rng() * 0.12;
    if (k === ctx.lastType) score -= 0.15; // разнообразие
    if (score > bestScore) { bestScore = score; best = k; }
  }
  return best;
}

// ---------- Сборка задания ----------

function distractorItems(courseData, item, kind, count, rng) {
  const all = Object.values(courseData.items).filter((it) => it.kind === kind && it.id !== item.id);
  const same = all.filter((it) => it.unit === item.unit);
  const near = all.filter((it) => it.unit !== item.unit && Math.abs(it.unit - item.unit) <= 2);
  const pool = [...shuffle(same, rng), ...shuffle(near, rng), ...shuffle(all, rng)];
  const out = [];
  const usedT = new Set(item.t.map((x) => x.toLowerCase()));
  const usedN = new Set(item.n.map((x) => x.toLowerCase()));
  for (const it of pool) {
    if (out.length >= count) break;
    if (out.includes(it)) continue;
    if (it.t.some((x) => usedT.has(x.toLowerCase())) || it.n.some((x) => usedN.has(x.toLowerCase()))) continue;
    out.push(it);
    it.t.forEach((x) => usedT.add(x.toLowerCase()));
    it.n.forEach((x) => usedN.add(x.toLowerCase()));
  }
  return out;
}

function bankTiles(courseData, answer, lang, rng, extra = 3) {
  const words = tokenize(answer);
  const have = new Set(words.map((w) => normalize(w, lang)));
  const pool = [];
  for (const it of Object.values(courseData.items)) {
    const src = lang === courseData.target ? it.t[0] : it.n[0];
    for (const w of tokenize(src)) {
      const k = normalize(w, lang);
      if (!have.has(k) && !/^[A-ZА-Я]/.test(w.slice(0, 1)) ) { pool.push(w); have.add(k); }
    }
  }
  const distract = shuffle(pool, rng).slice(0, extra);
  return shuffle([...words, ...distract], rng).map((text, i) => ({ id: i, text }));
}

export function makeExercise(courseData, item, type, rng = Math.random) {
  const T = courseData.target, N = courseData.native;
  const base = { type, itemId: item.id, skill: TYPES[type].skill };
  switch (type) {
    case 'pick_image':
    case 'choose_n2t':
    case 'listen_choose': {
      const ds = distractorItems(courseData, item, 'word', type === 'pick_image' ? 3 : 3, rng)
        .filter((d) => type !== 'pick_image' || d.e);
      const options = shuffle([item, ...ds], rng).map((it) => ({ text: it.t[0], lang: T, emoji: type === 'pick_image' ? it.e : null, correct: it.id === item.id }));
      const prompt = type === 'listen_choose'
        ? { audio: item.t[0], lang: T }
        : { text: item.n[0], lang: N };
      return { ...base, prompt, options, answerLang: T, accepted: item.t };
    }
    case 'choose_t2n': {
      const ds = distractorItems(courseData, item, 'word', 3, rng);
      const options = shuffle([item, ...ds], rng).map((it) => ({ text: it.n[0], lang: N, correct: it.id === item.id }));
      return { ...base, prompt: { text: item.t[0], lang: T, audio: item.t[0] }, options, answerLang: N, accepted: item.n };
    }
    case 'type_n2t':
      return { ...base, prompt: { text: item.n[0], lang: N }, answerLang: T, accepted: item.t };
    case 'bank_t2n':
      return { ...base, prompt: { text: item.t[0], lang: T, audio: item.t[0] }, tiles: bankTiles(courseData, item.n[0], N, rng), answerLang: N, accepted: item.n };
    case 'bank_n2t':
      return { ...base, prompt: { text: item.n[0], lang: N }, tiles: bankTiles(courseData, item.t[0], T, rng), answerLang: T, accepted: item.t };
    case 'listen_bank':
      return { ...base, prompt: { audio: item.t[0], lang: T }, tiles: bankTiles(courseData, item.t[0], T, rng), answerLang: T, accepted: item.t };
    case 'type_sent':
      return { ...base, prompt: { text: item.n[0], lang: N }, answerLang: T, accepted: item.t };
    default:
      throw new Error('unknown type ' + type);
  }
}

export function makeMatch(courseData, ids, rng = Math.random) {
  const pairs = ids.map((id) => courseData.items[id]).map((it) => ({ id: it.id, t: it.t[0], n: it.n[0] }));
  return { type: 'match', skill: 'vocab', itemIds: ids, left: shuffle(pairs, rng).map((p) => ({ id: p.id, text: p.t })), right: shuffle(pairs, rng).map((p) => ({ id: p.id, text: p.n })) };
}

// ---------- Урок ----------

// Очередь урока: элементы { kind: 'teach'|'ex'|'match', itemId|itemIds, exposure }.
export function buildLessonQueue(courseData, learner, unitIdx, lessonIdx, { rng = Math.random, now = Date.now() } = {}) {
  const plan = lessonPlan(courseData, unitIdx)[lessonIdx];
  const q = [];
  if (plan.kind === 'learn') {
    const fresh = plan.ids.filter((id) => !(learner.items[id]?.seen > 0));
    const known = plan.ids.filter((id) => !fresh.includes(id));
    const freshWords = fresh.filter((id) => courseData.items[id].kind === 'word');
    const freshSents = fresh.filter((id) => courseData.items[id].kind === 'sentence');
    for (const id of freshWords) q.push({ kind: 'teach', itemId: id }, { kind: 'ex', itemId: id, exposure: 0 });
    if (freshWords.length >= 3) q.push({ kind: 'match', itemIds: freshWords.slice(0, 5) });
    for (const id of freshSents) q.push({ kind: 'ex', itemId: id, exposure: 0 });
    const second = shuffle([...fresh, ...known], rng).map((id) => ({ kind: 'ex', itemId: id, exposure: 1 }));
    q.push(...second);
    const rev = pickReview(courseData, learner, { exclude: plan.ids, max: 3, maxUnit: unitIdx, now });
    q.push(...rev.map((id) => ({ kind: 'ex', itemId: id, exposure: 2 })));
  } else {
    // Закрепление: самые слабые элементы юнита + сопоставление.
    const ranked = plan.ids
      .map((id) => ({ id, w: weakness(itemState(learner, id), now) }))
      .sort((a, b) => b.w - a.w)
      .map((x) => x.id);
    const words = ranked.filter((id) => courseData.items[id].kind === 'word');
    q.push({ kind: 'match', itemIds: shuffle(words, rng).slice(0, 5) });
    q.push(...ranked.slice(0, 10).map((id) => ({ kind: 'ex', itemId: id, exposure: 2 })));
  }
  return spreadOut(q);
}

// Тренировка: самые слабые / просроченные элементы всего пройденного.
export function buildPracticeQueue(courseData, learner, { mode = 'smart', now = Date.now(), rng = Math.random } = {}) {
  let ids = pickReview(courseData, learner, { max: 12, now });
  if (mode === 'listen') ids = ids.filter(Boolean);
  const words = ids.filter((id) => courseData.items[id].kind === 'word');
  const q = [];
  if (mode === 'smart' && words.length >= 4) q.push({ kind: 'match', itemIds: shuffle(words, rng).slice(0, 5) });
  q.push(...ids.map((id) => ({ kind: 'ex', itemId: id, exposure: 2, allowed: mode === 'listen' ? ['listen_choose', 'listen_bank'] : undefined })));
  return spreadOut(q);
}

// Не ставим одно и то же слово два раза подряд (кроме «знакомство → первое задание»).
function spreadOut(q) {
  for (let i = 1; i < q.length; i++) {
    const a = q[i - 1], b = q[i];
    if (a.kind === 'ex' && b.kind === 'ex' && a.itemId === b.itemId) {
      const j = q.findIndex((x, k) => k > i && x.itemId !== b.itemId && x.kind !== 'teach');
      if (j > 0) [q[i], q[j]] = [q[j], q[i]];
    }
  }
  return q;
}

export class Session {
  constructor({ courseData, learner, queue, audio = true, rng = Math.random, now = () => Date.now(), target = 0.78, mode = 'lesson' }) {
    Object.assign(this, { courseData, learner, queue: queue.slice(), audio, rng, now, target, mode });
    this.doneCount = 0;
    this.combo = 0;
    this.maxCombo = 0;
    this.wrongStreak = 0;
    this.firstTry = { right: 0, total: 0 };
    this.results = {}; // itemId -> { right, wrong }
    this.lastType = null;
    this.current = null;
    this.startedAt = now();
    this.events = [];
  }

  get progress() {
    const total = this.doneCount + this.queue.length + (this.current ? 1 : 0);
    return total ? this.doneCount / total : 1;
  }

  next() {
    const entry = this.queue.shift();
    if (!entry) { this.current = null; return null; }
    let ex;
    if (entry.kind === 'teach') {
      ex = { type: 'teach', item: this.courseData.items[entry.itemId] };
    } else if (entry.kind === 'match') {
      ex = makeMatch(this.courseData, entry.itemIds, this.rng);
    } else {
      const item = this.courseData.items[entry.itemId];
      const type = pickType(this.learner, item, {
        exposure: entry.exposure, audio: this.audio, combo: this.combo, wrongStreak: this.wrongStreak,
        lastType: this.lastType, forceEasy: entry.retry, target: this.target, allowed: entry.allowed,
      }, this.rng);
      ex = makeExercise(this.courseData, item, type, this.rng);
      ex.isNew = entry.exposure === 0;
      ex.p = pCorrect(this.learner, item, type);
      this.lastType = type;
    }
    this.current = { entry, ex };
    return ex;
  }

  // Ответ ученика. Для match передаётся { mistakes: [itemId, ...] }, для teach — ничего.
  submit(response) {
    const { entry, ex } = this.current;
    this.current = null;
    this.doneCount++;
    if (ex.type === 'teach') return { correct: true, ungraded: true };

    let correct, typo = false, solution, ids;
    if (ex.type === 'match') {
      ids = ex.itemIds;
      const wrongSet = new Set(response?.mistakes || []);
      correct = wrongSet.size === 0;
      for (const id of ids) this._record(id, !wrongSet.has(id));
    } else {
      if ('choice' in (response || {})) {
        correct = !!ex.options[response.choice]?.correct;
        solution = ex.options.find((o) => o.correct).text;
      } else {
        const r = checkAnswer(response?.text ?? '', ex.accepted, ex.answerLang);
        correct = r.ok; typo = r.typo; solution = r.solution;
      }
      ids = [ex.itemId];
      this._record(ex.itemId, correct);
      if (!entry.retry) this._elo(ex, correct);
    }

    // Навыки (статистика по видам заданий).
    const sk = this.learner.skills[ex.skill];
    if (sk) { sk.t++; if (correct) sk.r++; }

    if (!entry.retry) { this.firstTry.total++; if (correct) this.firstTry.right++; }

    if (correct) {
      this.combo++; this.wrongStreak = 0;
      this.maxCombo = Math.max(this.maxCombo, this.combo);
      if ([3, 5, 8, 12].includes(this.combo)) this.events.push({ kind: 'combo', n: this.combo });
    } else {
      this.combo = 0; this.wrongStreak++;
      if (this.wrongStreak >= 2) this.events.push({ kind: 'support' });
      // Ошибку не наказываем — возвращаем это же слово чуть позже, в более лёгкой форме.
      const retry = ex.type === 'match'
        ? { kind: 'match', itemIds: ex.itemIds, retry: true }
        : { kind: 'ex', itemId: ex.itemId, exposure: 1, retry: true };
      this.queue.splice(Math.min(2, this.queue.length), 0, retry);
    }
    return { correct, typo, solution: solution ?? null, ids };
  }

  takeEvent() { return this.events.shift() || null; }

  _record(id, ok) {
    const r = this.results[id] || (this.results[id] = { right: 0, wrong: 0 });
    if (ok) r.right++; else r.wrong++;
  }

  _elo(ex, correct) {
    const item = this.courseData.items[ex.itemId];
    const p = pCorrect(this.learner, item, ex.type);
    const L = this.learner;
    const k = Math.max(0.08, 0.5 / (1 + L.answers / 40));
    L.theta += k * ((correct ? 1 : 0) - p);
    L.answers++;
    const st = itemState(L, item.id);
    st.d = (st.d || 0) - 0.3 * ((correct ? 1 : 0) - p);
  }

  // Завершение: обновить интервальные повторения и вернуть итоги.
  finish() {
    const now = this.now();
    for (const [id, r] of Object.entries(this.results)) {
      const st = itemState(this.learner, id);
      st.seen++;
      st.right += r.right;
      st.wrong += r.wrong;
      if (r.wrong === 0) st.box = Math.min(MAX_BOX, st.box + 1);
      else st.box = Math.max(st.seen > 1 ? 1 : 0, st.box - 1);
      st.due = now + INTERVAL_DAYS[st.box] * DAY;
    }
    const acc = this.firstTry.total ? this.firstTry.right / this.firstTry.total : 1;
    const xp = 10 + this.firstTry.right + (acc === 1 && this.firstTry.total >= 5 ? 5 : 0) + Math.floor(this.maxCombo / 5) * 2;
    return {
      xp,
      accuracy: acc,
      right: this.firstTry.right,
      total: this.firstTry.total,
      maxCombo: this.maxCombo,
      ms: now - this.startedAt,
      newItems: Object.keys(this.results).filter((id) => this.learner.items[id].seen === 1).length,
    };
  }
}

// ---------- Тест на уровень (адаптивная «лестница») ----------

export class Placement {
  constructor({ courseData, learner, start = 2, questions = 8, audio = false, rng = Math.random }) {
    Object.assign(this, { courseData, learner, questions, audio, rng });
    this.level = Math.min(start, courseData.units.length - 1);
    this.step = 2;
    this.asked = 0;
    this.lastCorrect = null;
    this.used = new Set();
    this.current = null;
  }

  get progress() { return this.asked / this.questions; }

  next() {
    if (this.asked >= this.questions) return null;
    const u = Math.min(this.level, this.courseData.units.length - 1);
    const ids = this.courseData.unitItems[u].filter((id) => !this.used.has(id));
    const wantSentence = this.asked % 2 === 1;
    const pool = ids.filter((id) => (this.courseData.items[id].kind === 'sentence') === wantSentence);
    const id = shuffle(pool.length ? pool : ids, this.rng)[0];
    this.used.add(id);
    const item = this.courseData.items[id];
    const type = item.kind === 'word' ? 'choose_n2t' : 'bank_n2t';
    const ex = makeExercise(this.courseData, item, type, this.rng);
    this.current = ex;
    return ex;
  }

  submit(response) {
    const ex = this.current;
    let correct;
    if ('choice' in (response || {})) correct = !!ex.options[response.choice]?.correct;
    else correct = checkAnswer(response?.text ?? '', ex.accepted, ex.answerLang, { lenient: true }).ok;
    if (this.lastCorrect !== null && this.lastCorrect !== correct) this.step = 1; // разворот — шаг меньше
    this.lastCorrect = correct;
    const U = this.courseData.units.length;
    this.level = correct ? Math.min(U, this.level + this.step) : Math.max(0, this.level - this.step);
    this.asked++;
    return { correct, solution: canon(ex.accepted) };
  }

  // Результат: с какого юнита начинать (всё, что раньше, считается знакомым).
  result() {
    return Math.min(this.level, this.courseData.units.length - 1);
  }
}

export function applyPlacement(courseData, learner, startUnit, now = Date.now()) {
  for (let u = 0; u < startUnit; u++) {
    lessonPlan(courseData, u).forEach((_, l) => markLessonDone(learner, u, l));
    courseData.unitItems[u].forEach((id, i) => {
      const st = itemState(learner, id);
      st.seen = Math.max(st.seen, 1);
      st.box = Math.max(st.box, 2);
      st.due = now + (1 + (i % 3)) * DAY; // разнесём повторения по дням
    });
  }
  learner.theta = -0.5 + startUnit * 0.25;
  learner.placed = true;
}

// ---------- Уровень (CEFR) ----------

export function levelInfo(courseData, learner) {
  const U = courseData.units.length;
  let lessons = 0, total = 0;
  for (let u = 0; u < U; u++) {
    const n = lessonPlan(courseData, u).length;
    total += n;
    lessons += Math.min(n, (learner.done[u] || []).length);
  }
  const frac = total ? lessons / total : 0;
  const node = currentNode(courseData, learner);
  const unit = node ? courseData.units[node.u] : courseData.units[U - 1];
  const bands = ['A1', 'A2'];
  const code = lessons === 0 ? 'A0' : unit.cefr;
  // прогресс внутри полосы CEFR
  const inBand = courseData.units.map((x, i) => [x, i]).filter(([x]) => x.cefr === unit.cefr).map(([, i]) => i);
  let bDone = 0, bTotal = 0;
  for (const u of inBand) { const n = lessonPlan(courseData, u).length; bTotal += n; bDone += Math.min(n, (learner.done[u] || []).length); }
  return { code, bandProgress: bTotal ? bDone / bTotal : 0, courseProgress: frac, next: bands[bands.indexOf(code) + 1] || null };
}

export function wordsStats(courseData, learner) {
  let learned = 0, mastered = 0;
  for (const [id, st] of Object.entries(learner.items)) {
    if (!courseData.items[id] || courseData.items[id].kind !== 'word') continue;
    if (st.seen > 0) learned++;
    if (st.box >= 4) mastered++;
  }
  return { learned, mastered };
}

// ---------- Серия дней (streak) ----------

export function dateKey(d = new Date()) {
  const x = new Date(d);
  return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`;
}

export function daysBetween(a, b) {
  const pa = new Date(a + 'T00:00:00'), pb = new Date(b + 'T00:00:00');
  return Math.round((pb - pa) / DAY);
}

// При открытии приложения: если пропущен ровно один день и есть «заморозка» — серия сохраняется.
export function checkStreak(streak, today) {
  const s = { ...streak };
  if (!s.last) return s;
  const gap = daysBetween(s.last, today);
  if (gap <= 1) return s;
  if (gap === 2 && s.freezes > 0) {
    s.freezes--;
    s.last = dateKey(new Date(new Date(today + 'T00:00:00').getTime() - DAY));
    s.frozeOn = s.last;
    return s;
  }
  s.count = 0;
  return s;
}

export function registerActivity(streak, today) {
  const s = { ...streak };
  if (s.last === today) return s;
  s.count = s.last && daysBetween(s.last, today) === 1 ? (s.count || 0) + 1 : 1;
  s.last = today;
  s.best = Math.max(s.best || 0, s.count);
  if (s.count % 7 === 0) s.freezes = Math.min(2, (s.freezes || 0) + 1); // награда за неделю
  return s;
}
