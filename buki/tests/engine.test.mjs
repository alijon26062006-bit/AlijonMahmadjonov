// Запуск: node --test buki/tests
import test from 'node:test';
import assert from 'node:assert/strict';
import { UNITS, COURSES } from '../js/data.js';
import {
  buildCourse, newLearner, checkAnswer, normalize, translit, tokenize, lessonPlan,
  buildLessonQueue, Session, Placement, applyPlacement, currentNode, pickType, mulberry32,
  makeExercise, TYPES, checkStreak, registerActivity, levelInfo, markLessonDone, buildPracticeQueue,
} from '../js/engine.js';

const en = buildCourse(UNITS, COURSES.en_ru);
const tg = buildCourse(UNITS, COURSES.en_tg);
const ru = buildCourse(UNITS, COURSES.ru_en);

test('ids are unique across the course', () => {
  const ids = UNITS.flatMap((u) => [...u.words, ...u.sentences].map((x) => x.id));
  assert.equal(new Set(ids).size, ids.length);
});

test('normalize ignores case, punctuation, ё and contractions', () => {
  assert.equal(normalize('I’m fine, thanks!', 'en'), 'i am fine thanks');
  assert.equal(normalize('Всё хорошо!', 'ru'), 'все хорошо');
  assert.equal(normalize('Ты говоришь по-английски?', 'ru'), 'ты говоришь по-английски');
});

test('checkAnswer accepts alternatives, typos and latin input for Russian', () => {
  assert.ok(checkAnswer('Hi', ['hello', 'hi'], 'en').ok);
  const typo = checkAnswer('studnet', ['student'], 'en');
  assert.ok(typo.ok && typo.typo);
  assert.ok(!checkAnswer('no', ['yes'], 'en').ok);
  assert.ok(checkAnswer('privet', ['привет'], 'ru').ok);
  assert.ok(checkAnswer('spasibo', ['спасибо'], 'ru').ok);
  assert.ok(!checkAnswer('', ['спасибо'], 'ru').ok);
});

test('every item and tip has text for every course language', () => {
  for (const u of UNITS) {
    for (const lang of ['en', 'ru', 'tg']) assert.ok(u.title[lang], `${u.id} title ${lang}`);
    for (const c of Object.keys(COURSES)) assert.ok(u.tip[c], `${u.id} tip ${c}`);
    for (const x of [...u.words, ...u.sentences]) for (const lang of ['en', 'ru', 'tg']) assert.ok(x[lang], `${x.id} ${lang}`);
  }
});

test('Tajik answers accept Russian-keyboard letters', () => {
  assert.ok(checkAnswer('хуб, ташаккур', ['Хуб, ташаккур.'], 'tg').ok);
  assert.ok(checkAnswer('Ман об менушам', ['Ман об менӯшам.'], 'tg').ok);
});

test('translit and tokenize', () => {
  assert.equal(translit('Привет'), 'Privet');
  assert.deepEqual(tokenize('Hello, Anna!'), ['Hello', 'Anna']);
});

test('lesson plan covers every item of a unit', () => {
  for (let u = 0; u < UNITS.length; u++) {
    const plan = lessonPlan(en, u);
    const learned = new Set(plan.filter((l) => l.kind === 'learn').flatMap((l) => l.ids));
    assert.equal(learned.size, en.unitItems[u].length);
  }
});

test('new words start with recognition, never with typing', () => {
  const L = newLearner();
  const rng = mulberry32(1);
  for (let i = 0; i < 50; i++) {
    const t = pickType(L, en.items.apple, { exposure: 0, audio: true, combo: 0, wrongStreak: 0 }, rng);
    assert.ok(TYPES[t].recog, t);
  }
});

test('every exercise type builds and its correct answer passes', () => {
  const rng = mulberry32(7);
  for (const c of [en, tg, ru]) {
    for (const item of Object.values(c.items)) {
      for (const [type, def] of Object.entries(TYPES)) {
        if (def.for !== item.kind || (type === 'pick_image' && !item.e)) continue;
        const ex = makeExercise(c, item, type, rng);
        if (ex.options) {
          assert.equal(ex.options.filter((o) => o.correct).length, 1, `${c.id} ${type} ${item.id}`);
          assert.ok(ex.options.length >= 3);
        }
        if (ex.tiles) {
          // ответ можно собрать из плиток
          const pool = ex.tiles.map((t) => t.text);
          for (const w of tokenize(ex.accepted[0])) {
            const i = pool.indexOf(w);
            assert.ok(i >= 0, `${c.id} ${type} ${item.id}: no tile "${w}"`);
            pool.splice(i, 1);
          }
        }
        assert.ok(checkAnswer(ex.accepted[0], ex.accepted, ex.answerLang).ok);
      }
    }
  }
});

test('a perfect lesson raises ability and finishes with XP', () => {
  const L = newLearner();
  const rng = mulberry32(3);
  const s = new Session({ courseData: en, learner: L, queue: buildLessonQueue(en, L, 0, 0, { rng }), rng });
  let ex, steps = 0;
  while ((ex = s.next())) {
    steps++;
    if (ex.type === 'teach') s.submit();
    else if (ex.type === 'match') s.submit({ mistakes: [] });
    else if (ex.options) s.submit({ choice: ex.options.findIndex((o) => o.correct) });
    else s.submit({ text: ex.accepted[0] });
  }
  const r = s.finish();
  assert.ok(steps >= 8);
  assert.equal(r.accuracy, 1);
  assert.ok(L.theta > 0);
  assert.ok(r.xp >= 15);
  assert.ok(Object.values(L.items).every((st) => st.box >= 1));
});

test('mistakes are retried later and lower the box', () => {
  const L = newLearner();
  const rng = mulberry32(4);
  const s = new Session({ courseData: en, learner: L, queue: buildLessonQueue(en, L, 0, 0, { rng }), rng });
  let wrongOnce = false, ex;
  while ((ex = s.next())) {
    if (ex.type === 'teach') { s.submit(); continue; }
    if (ex.type !== 'match' && ex.itemId === 'hello' && !wrongOnce) {
      wrongOnce = true;
      const r = s.submit({ text: 'zzz', choice: ex.options ? ex.options.findIndex((o) => !o.correct) : undefined });
      assert.equal(r.correct, false);
      assert.ok(s.queue.some((q) => q.itemId === 'hello' && q.retry));
      continue;
    }
    if (ex.type === 'match') s.submit({ mistakes: [] });
    else if (ex.options) s.submit({ choice: ex.options.findIndex((o) => o.correct) });
    else s.submit({ text: ex.accepted[0] });
  }
  const r = s.finish();
  assert.ok(r.accuracy < 1);
  assert.ok(L.items.hello.box < L.items.thanks.box);
});

test('placement moves up for strong answers and down for weak ones', () => {
  for (const strong of [true, false]) {
    const L = newLearner();
    const p = new Placement({ courseData: en, learner: L, start: 3, rng: mulberry32(5) });
    let ex;
    while ((ex = p.next())) {
      if (ex.options) p.submit({ choice: ex.options.findIndex((o) => o.correct === strong) });
      else p.submit({ text: strong ? ex.accepted[0] : 'nope' });
    }
    const start = p.result();
    if (strong) assert.ok(start >= 7, `strong → ${start}`);
    else assert.equal(start, 0);
    applyPlacement(en, L, start);
    assert.equal(currentNode(en, L).u, start);
  }
});

test('practice queue picks the weakest seen items', () => {
  const L = newLearner();
  applyPlacement(en, L, 2);
  L.items.apple = { box: 0, due: 0, seen: 3, right: 1, wrong: 5, d: 0 };
  const q = buildPracticeQueue(en, L, { rng: mulberry32(2) });
  assert.ok(q.some((e) => e.itemId === 'apple'));
});

test('streak: continues, freezes one missed day, resets after more', () => {
  let s = registerActivity({ count: 0, freezes: 1 }, '2026-11-01');
  s = registerActivity(s, '2026-11-02');
  assert.equal(s.count, 2);
  const frozen = checkStreak(s, '2026-11-04');
  assert.equal(frozen.count, 2);
  assert.equal(frozen.freezes, 0);
  assert.equal(registerActivity(frozen, '2026-11-04').count, 3);
  assert.equal(checkStreak(s, '2026-11-06').count, 0);
});

test('level info grows with finished lessons', () => {
  const L = newLearner();
  assert.equal(levelInfo(en, L).code, 'A0');
  markLessonDone(L, 0, 0);
  const li = levelInfo(en, L);
  assert.equal(li.code, 'A1');
  assert.ok(li.courseProgress > 0);
});
