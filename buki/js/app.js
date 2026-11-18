// «Буки» — интерфейс приложения. Логика обучения — в engine.js, тексты — в i18n.js.
import { UNITS, COURSES } from './data.js';
import {
  buildCourse, newLearner, lessonPlan, currentNode, isLessonDone, markLessonDone,
  buildLessonQueue, buildPracticeQueue, Session, Placement, applyPlacement,
  levelInfo, wordsStats, weakness, normalize, translit, dateKey, checkStreak, registerActivity,
} from './engine.js';
import { t, setLang, pick, WELCOME } from './i18n.js';
import { speak, canSpeak, sfx } from './audio.js';
import { mascot } from './mascot.js';

// ---------- состояние ----------

const KEY = 'buki-v1';
const AUDIO = canSpeak();
const $app = document.getElementById('app');

const defaults = () => ({
  v: 1,
  profile: { name: '', why: null, goal: 20, theme: 'sunny', sound: true, translit: true },
  active: null,
  courses: {},
  onboarded: {},
  streak: { count: 0, last: null, best: 0, freezes: 1 },
  history: {},
});

function load() {
  try {
    const s = JSON.parse(localStorage.getItem(KEY));
    if (s && s.v === 1) return { ...defaults(), ...s, profile: { ...defaults().profile, ...s.profile } };
  } catch { /* приватный режим или повреждённые данные — начнём заново */ }
  return defaults();
}
let state = load();
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* нет места — не страшно */ } };

const built = {};
const course = () => built[state.active] || (built[state.active] = buildCourse(UNITS, COURSES[state.active]));
const learner = () => state.courses[state.active] || (state.courses[state.active] = newLearner());
const native = () => COURSES[state.active]?.native || 'tg';
const today = () => dateKey();
const todayXp = () => state.history[today()]?.xp || 0;

let view = { name: 'welcome' };
let run = null;
const ui = { tipOpen: null };

// ---------- утилиты ----------

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const ICON = {
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  back: '<path d="M15 18l-6-6 6-6"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  trophy: '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0zM7 6H4a3 3 0 0 0 3 4M17 6h3a3 3 0 0 1-3 4"/>',
  book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5zM4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/>',
  home: '<path d="M3 10.5L12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  practice: '<path d="M6 6v12M18 6v12M3 9v6M21 9v6M6 12h12"/>',
  stats: '<path d="M5 20V11M12 20V4M19 20v-6"/>',
  profile: '<path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c0-4 3.6-6 8-6s8 2 8 6"/>',
  ear: '<path d="M7 10a5 5 0 0 1 10 0c0 3-3 4-3 7a3 3 0 0 1-5 2"/><path d="M10 10a2 2 0 0 1 4 0"/>',
};
const icon = (name, size = 26, sw = 2.4) =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">${ICON[name]}</svg>`;
const STAR = '<svg width="38" height="38" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2.8l2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 16.6l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8z"/></svg>';
const FLAME = (s = 24) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" aria-hidden="true"><path fill="var(--streak)" d="M12 2c1 3.5 5 6 5 11a5 5 0 0 1-10 0c0-2.4 1.2-4 2.4-5.2.3 1.6 1.2 2.6 2.1 3 .2-3.2-.6-6.3.5-8.8z"/><path fill="var(--accent)" d="M12 13c.6 1.5 2.4 2.4 2.4 4.4a2.4 2.4 0 0 1-4.8 0c0-1.3.9-2.2 2.4-4.4z"/></svg>`;
const SPEAKER = '<svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path fill="currentColor" d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a7.5 7.5 0 0 1 0 11"/></svg>';
const SLOW = '<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 15c0-4 3.5-7 8-7s8 3 8 7z"/><path d="M20 15h1.5a1.5 1.5 0 0 0 0-3H20M7 15v3M17 15v3"/></svg>';

function goalRing(xp, goal, size = 32) {
  const c = 2 * Math.PI * 14, f = Math.min(1, xp / goal) * c;
  return `<svg width="${size}" height="${size}" viewBox="0 0 36 36" aria-hidden="true">
    <circle cx="18" cy="18" r="14" fill="none" stroke="var(--locked)" stroke-width="5"/>
    <circle cx="18" cy="18" r="14" fill="none" stroke="var(--accent)" stroke-width="5" stroke-linecap="round" stroke-dasharray="${f} ${c}" transform="rotate(-90 18 18)"/>
    <path d="M19.5 10l-6 9h4.5l-1.5 7 6-9h-4.5z" fill="var(--accent-shade)"/></svg>`;
}

function toast(text) {
  document.querySelector('.toast')?.remove();
  const el = document.createElement('div');
  el.className = 'toast';
  el.setAttribute('role', 'status');
  el.textContent = text;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 1900);
}

const say = (text) => AUDIO && speak(text, COURSES[state.active].speech);
const fmtTime = (ms) => { const s = Math.round(ms / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
const unitTitle = (u) => course().units[u].title[native()];

// ---------- отрисовка ----------

function render() {
  document.documentElement.dataset.theme = state.profile.theme;
  document.documentElement.lang = state.active ? native() : 'tg';
  $app.innerHTML = SCREENS[view.name]();
  const w = document.getElementById('write');
  if (w) w.focus();
  if (view.name === 'home' && ui.scroll) {
    ui.scroll = false;
    document.getElementById('current')?.scrollIntoView({ block: 'center' });
  }
}

const tabbar = (on) => `<nav class="tabbar" aria-label="menu">${[
  ['home', 'learn', 'home'], ['practice', 'practice', 'practice'], ['stats', 'stats', 'stats'], ['profile', 'profile', 'profile'],
].map(([to, label, ic]) => `<button class="tab ${on === to ? 'on' : ''}" data-act="go" data-to="${to}" ${on === to ? 'aria-current="page"' : ''}>${icon(ic, 28, 2.2)}${t()[label]}</button>`).join('')}</nav>`;

const SCREENS = {
  welcome() {
    return `<div class="screen">
      <div class="say" style="margin-top:24px">${mascot('happy', 112)}
        <div class="bubble">${esc(WELCOME.title)}<div class="soft" style="font-size:14px;margin-top:4px">${esc(WELCOME.subtitle)}</div></div></div>
      <div class="options">${WELCOME.options.map((o) => `
        <button class="choice" data-act="pickCourse" data-id="${o.course}">
          <span class="big">${COURSES[o.course].flag}</span><span>${esc(o.title)}<small>${esc(o.sub)}</small></span>
        </button>`).join('')}</div>
    </div>`;
  },

  onboard() {
    const T = t(), step = view.step, steps = ['name', 'why', 'goal', 'level'];
    const i = steps.indexOf(step);
    const head = `<div class="topline">
      <button class="icon-btn" data-act="obBack" aria-label="${T.back}">${icon('back')}</button>
      <div class="bar"><i style="width:${((i + 1) / steps.length) * 100}%"></i></div></div>`;
    let body = '';
    if (step === 'name') {
      body = `<div class="say">${mascot('happy', 104)}<div class="bubble">${esc(T.mascot.hello(''))}</div></div>
        <label class="card" style="display:flex;flex-direction:column;gap:8px">
          <span>${T.obNameQ}</span>
          <input id="nameInput" type="text" maxlength="30" autocomplete="given-name" placeholder="${esc(T.obNamePh)}" value="${esc(state.profile.name)}"
            style="padding:12px 14px;border-radius:14px;border:2px solid var(--border);background:var(--surface-2);font-size:18px;font-weight:800">
        </label>
        <div class="grow"></div>
        <button class="btn" data-act="obNext">${T.continue}</button>`;
    } else if (step === 'why') {
      body = `<h1>${T.obWhyQ}</h1><div class="options">${Object.entries(T.why).map(([k, v]) => `
        <button class="choice ${state.profile.why === k ? 'on' : ''}" data-act="obWhy" data-k="${k}">${esc(v)}</button>`).join('')}</div>`;
    } else if (step === 'goal') {
      body = `<h1>${T.obGoalQ}</h1>
        <div class="options">${Object.entries(T.goals).map(([xp, [a, b]]) => `
          <button class="choice ${state.profile.goal === +xp ? 'on' : ''}" data-act="obGoal" data-xp="${xp}">
            <span style="flex:1">${esc(a)}</span><small>${esc(b)}</small></button>`).join('')}</div>
        <p class="soft">${T.obGoalHint}</p>`;
    } else {
      body = `<h1>${T.obLevelQ}</h1>
        <div class="options">${Object.entries(T.lvl).map(([k, [a, b]]) => `
          <button class="choice" data-act="obLevel" data-k="${k}"><span>${esc(a)}<small>${esc(b)}</small></span></button>`).join('')}</div>`;
    }
    return `<div class="screen">${head}${body}</div>`;
  },

  placementIntro() {
    const T = t();
    return `<div class="screen">
      <div class="topline"><button class="icon-btn" data-act="obBack" aria-label="${T.back}">${icon('back')}</button></div>
      <div class="say">${mascot('think', 104)}<div class="bubble">${T.placementIntro}</div></div>
      <h1>${T.placementTitle}</h1>
      <div class="grow"></div>
      <button class="btn" data-act="startPlacement">${T.start}</button>
    </div>`;
  },

  placementDone() {
    const T = t();
    const msg = view.u > 0 ? T.placementDone(unitTitle(view.u)) : T.placementZero;
    return `<div class="screen" style="align-items:center;text-align:center;justify-content:center">
      ${mascot('cheer', 160)}
      <h1>${T.placementTitle}</h1>
      <p style="font-size:17px;line-height:1.45">${esc(msg)}</p>
      <div class="grow"></div>
      <button class="btn" data-act="go" data-to="home">${T.continue}</button>
    </div>`;
  },

  quiz: () => quizHTML(),

  result() {
    const T = t(), s = view.summary;
    const praise = s.accuracy === 1 ? T.praise.perfect : s.accuracy >= 0.85 ? T.praise.great : s.accuracy >= 0.6 ? T.praise.good : T.praise.ok;
    const h = state.history[today()];
    return `<div class="screen">
      <div class="confetti">${confetti()}${mascot('cheer', 150)}</div>
      <div style="text-align:center;display:flex;flex-direction:column;gap:6px">
        <h1 style="font-size:30px;color:var(--primary-ink)">${view.kind === 'lesson' ? T.lessonDone : T.practiceDone}</h1>
        <p class="soft" style="font-size:16px">${esc(praise)}${s.newItems ? ' ' + esc(T.newWords(s.newItems)) + '.' : ''}</p>
      </div>
      <div class="stat3">
        <div style="--c:var(--accent);--cc:var(--accent-ink)"><span>${T.xpEarned}</span><b>+${s.xp}</b></div>
        <div style="--c:var(--primary)"><span>${T.accuracy}</span><b>${Math.round(s.accuracy * 100)}%</b></div>
        <div style="--c:var(--blue)"><span>${T.time}</span><b>${fmtTime(s.ms)}</b></div>
      </div>
      <div class="card" style="display:flex;flex-direction:column;gap:10px">
        <div class="between"><span>${view.goalJust ? T.goalReached : T.dailyGoal}</span><span class="soft">${h.xp}/${state.profile.goal}</span></div>
        <div class="bar thin"><i style="width:${Math.min(100, (h.xp / state.profile.goal) * 100)}%;background:var(--accent)"></i></div>
        <div class="row">${FLAME(20)}<span>${esc(T.streakDays(state.streak.count))}</span></div>
      </div>
      <div class="grow"></div>
      <button class="btn" data-act="go" data-to="home">${T.continue}</button>
    </div>`;
  },

  home() {
    const T = t(), c = course(), L = learner(), cur = currentNode(c, L);
    const names = T.mascot.home(state.profile.name);
    const tip = state.profile.why && todayXp() === 0 ? T.mascot.why[state.profile.why] : names[new Date().getDate() % names.length];
    const goalLeft = todayXp() >= state.profile.goal ? T.goalReached : tip;
    let html = `<header class="appbar">
      <button class="chip" data-act="go" data-to="profile" aria-label="${esc(T.courseNames[state.active])}">${COURSES[state.active].flag} EN</button>
      <div class="chip plain">${FLAME()}<span>${state.streak.count}</span></div>
      <div class="chip" style="padding-left:6px">${goalRing(todayXp(), state.profile.goal)}<span>${todayXp()}<span class="soft">/${state.profile.goal}</span></span></div>
    </header>
    <div class="path">
      <div class="say">${mascot(todayXp() >= state.profile.goal ? 'cheer' : 'happy', 68)}<div class="bubble" style="margin-bottom:10px">${esc(goalLeft)}</div></div>`;
    c.units.forEach((unit, u) => {
      const plan = lessonPlan(c, u);
      const reached = !cur || u <= cur.u;
      html += `<section class="u${u % 5}" style="display:flex;flex-direction:column;gap:14px">
        <div class="unit-banner ${reached ? '' : 'locked'}">
          <div><div class="kicker">${T.unit.toUpperCase()} ${u + 1} · ${unit.cefr}</div><h2>${esc(unit.title[native()])}</h2></div>
          <button class="tipbtn" data-act="tip" data-u="${u}" aria-label="${T.tipTitle}" aria-expanded="${ui.tipOpen === u}">${icon('book', 24, 2.2)}</button>
        </div>
        ${ui.tipOpen === u ? `<div class="tip">💡 ${esc(unit.tip[state.active])}</div>` : ''}
        <div class="nodes">`;
      plan.forEach((lesson, l) => {
        const done = isLessonDone(L, u, l);
        const isCur = cur && cur.u === u && cur.l === l;
        const off = [0, -56, -16, 44][l % 4];
        const isRev = lesson.kind === 'review';
        const label = isRev ? T.review : T.lessonN(l + 1);
        if (isCur) {
          html += `<div class="node-wrap" id="current" style="transform:translateX(${off}px)">
            <button class="node-label" data-act="startLesson" data-u="${u}" data-l="${l}"><small>${esc(label.toUpperCase())} · ~4 ${T.minutesShort}</small><b>${T.startLesson}</b></button>
            <div class="ring"><button class="node current ${isRev ? 'review' : ''}" data-act="startLesson" data-u="${u}" data-l="${l}" aria-label="${esc(label)}">${isRev ? icon('trophy', 34, 2.2) : STAR}</button></div>
          </div>`;
        } else if (done) {
          html += `<button class="node done ${isRev ? 'review' : ''}" style="transform:translateX(${off}px)" data-act="startLesson" data-u="${u}" data-l="${l}" aria-label="${esc(label)} — ${T.redo}">${icon(isRev ? 'trophy' : 'check', 34, 3)}</button>`;
        } else {
          html += `<button class="node ${isRev ? 'review' : ''}" style="transform:translateX(${off}px)" data-act="locked" aria-label="${esc(label)}">${icon(isRev ? 'trophy' : 'lock', 30, 2.4)}</button>`;
        }
      });
      html += '</div></section>';
    });
    if (!cur) html += `<div class="card" style="text-align:center">${esc(T.courseDone)}</div>`;
    return `${html}</div>${tabbar('home')}`;
  },

  practice() {
    const T = t(), L = learner(), now = Date.now();
    const seen = Object.values(L.items).filter((s) => s.seen > 0);
    const due = seen.filter((s) => s.due <= now).length;
    if (!seen.length) {
      return `<div class="screen with-tabs"><h1>${T.practiceTitle}</h1>
        <div class="say">${mascot('think', 96)}<div class="bubble">${T.practiceEmpty}</div></div></div>${tabbar('practice')}`;
    }
    return `<div class="screen with-tabs"><h1>${T.practiceTitle}</h1>
      <div class="say">${mascot('happy', 88)}<div class="bubble">${esc(T.dueNow(Math.max(due, Math.min(seen.length, 10))))}</div></div>
      <button class="choice" data-act="practice" data-mode="smart"><span class="big">🧠</span><span>${T.practiceSmart}<small>${T.practiceSmartD}</small></span></button>
      ${AUDIO ? `<button class="choice" data-act="practice" data-mode="listen"><span class="big">🎧</span><span>${T.practiceListen}<small>${T.practiceListenD}</small></span></button>` : ''}
    </div>${tabbar('practice')}`;
  },

  stats() {
    const T = t(), c = course(), L = learner(), li = levelInfo(c, L), ws = wordsStats(c, L);
    let lessonsDone = 0, lessonsTotal = 0;
    c.units.forEach((_, u) => { const n = lessonPlan(c, u).length; lessonsTotal += n; lessonsDone += Math.min(n, (L.done[u] || []).length); });
    const now = new Date();
    const monday = new Date(now); monday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
    const week = T.days.map((d, i) => { const x = new Date(monday); x.setDate(monday.getDate() + i); return { d, on: (state.history[dateKey(x)]?.xp || 0) > 0 }; });
    const last7 = Array.from({ length: 7 }, (_, i) => { const x = new Date(now); x.setDate(now.getDate() - 6 + i); return { d: T.days[(x.getDay() + 6) % 7], xp: state.history[dateKey(x)]?.xp || 0 }; });
    const max = Math.max(state.profile.goal * 1.5, ...last7.map((x) => x.xp));
    const px = (v) => Math.round((v / max) * 120);
    const totalXp = Object.values(state.history).reduce((a, h) => a + (h.xp || 0), 0);
    const weak = Object.entries(L.items)
      .filter(([id, s]) => s.wrong > 0 && c.items[id])
      .sort((a, b) => weakness(b[1], Date.now()) - weakness(a[1], Date.now()))
      .slice(0, 6).map(([id]) => c.items[id].t[0]);
    const skillColors = { vocab: 'var(--primary)', sentence: 'var(--blue)', listen: 'var(--purple)', write: 'var(--accent)' };
    return `<div class="screen with-tabs"><h1>${T.statsTitle}</h1>
      <section class="card row">
        <div class="level-badge">${li.code}</div>
        <div style="flex:1;display:flex;flex-direction:column;gap:6px">
          <div class="between"><span>${T.level} ${li.code}</span><span class="soft" style="font-size:14px">${li.next ? `${Math.round(li.bandProgress * 100)}% ${T.toNext(li.next)}` : ''}</span></div>
          <div class="bar thin"><i style="width:${li.bandProgress * 100}%;background:var(--purple)"></i></div>
          <span class="soft" style="font-size:13px">${T.courseProgress}: ${lessonsDone}/${lessonsTotal}</span>
        </div>
      </section>
      <section class="card" style="display:flex;flex-direction:column;gap:12px">
        <div class="between">
          <div class="row">${FLAME(40)}<div><b style="font-size:22px">${esc(T.streakDays(state.streak.count))}</b><div class="soft" style="font-size:13px">${T.bestStreak}: ${state.streak.best || 0}</div></div></div>
          <div class="soft" style="font-size:13px;text-align:right" title="${esc(T.freezesD)}">🛡️ ${T.freezes}: ${state.streak.freezes || 0}</div>
        </div>
        <div class="week">${week.map((w) => `<div>${w.d}<i class="${w.on ? 'on' : ''}">${w.on ? '✓' : ''}</i></div>`).join('')}</div>
      </section>
      <section class="card" style="display:flex;flex-direction:column;gap:10px">
        <div class="between"><h2>${T.week}</h2><span class="soft">${last7.reduce((a, x) => a + x.xp, 0)} XP</span></div>
        <div class="chart"><div class="goal" style="bottom:${px(state.profile.goal)}px"></div>
          ${last7.map((x) => `<div class="col"><span>${x.xp || ''}</span><i class="${x.xp >= state.profile.goal ? 'met' : ''}" style="height:${Math.max(4, px(x.xp))}px"></i></div>`).join('')}</div>
        <div class="chart-days">${last7.map((x) => `<span>${x.d}</span>`).join('')}</div>
      </section>
      <div class="grid2">
        <div class="mini"><b>${totalXp}</b><span>${T.totalXp}</span></div>
        <div class="mini"><b>${lessonsDone}</b><span>${T.lessons}</span></div>
        <div class="mini"><b>${ws.learned}</b><span>${T.wordsLearned}</span></div>
        <div class="mini"><b>${ws.mastered}</b><span>${T.mastered}</span></div>
      </div>
      <section class="card" style="display:flex;flex-direction:column;gap:12px"><h2>${T.skills}</h2>
        ${Object.entries(L.skills).map(([k, s]) => { const p = s.t ? Math.round((s.r / s.t) * 100) : 0; return `
          <div><div class="between" style="font-size:15px"><span>${T.skillNames[k]}</span><span class="soft">${s.t ? p + '%' : '—'}</span></div>
          <div class="bar thin" style="margin-top:5px"><i style="width:${p}%;background:${skillColors[k]}"></i></div></div>`; }).join('')}
      </section>
      <section class="card" style="display:flex;flex-direction:column;gap:12px"><h2>${T.weak}</h2>
        ${weak.length ? `<div class="chips">${weak.map((w) => `<span class="wchip" lang="${c.target}">${esc(w)}</span>`).join('')}</div>
          <button class="btn blue small" data-act="practice" data-mode="smart">${T.reviewWeak}</button>` : `<p class="soft">${T.noWeak}</p>`}
      </section>
    </div>${tabbar('stats')}`;
  },

  profile() {
    const T = t(), p = state.profile;
    const totalXp = Object.values(state.history).reduce((a, h) => a + (h.xp || 0), 0);
    const seg = (act, items, cur) => `<div class="seg" style="--n:${items.length}">${items.map(([v, label]) => `<button class="${String(cur) === String(v) ? 'on' : ''}" data-act="${act}" data-v="${v}">${esc(label)}</button>`).join('')}</div>`;
    return `<div class="screen with-tabs">
      <section class="row">
        <div class="level-badge" style="border-radius:36px;width:72px;height:72px">${esc((p.name || '🙂').slice(0, 1).toUpperCase())}</div>
        <div><h1>${esc(p.name || T.profileTitle)}</h1><div class="soft" style="font-size:14px">${esc(T.courseNames[state.active])} · ${totalXp} XP</div></div>
      </section>
      <section class="card settings" style="padding:0;overflow:hidden">
        <label class="set"><span>${T.name}</span><input id="nameInput" type="text" maxlength="30" value="${esc(p.name)}" placeholder="${esc(T.obNamePh)}"></label>
        <div><div class="set" style="min-height:44px;padding-bottom:6px"><span>${T.goal}</span></div>
          ${seg('setGoal', Object.entries(T.goals).map(([xp, [a]]) => [xp, a]), p.goal)}</div>
        <div><div class="set" style="min-height:44px;padding-bottom:6px"><span>${T.theme}</span></div>
          ${seg('setTheme', [['sunny', '☀️ ' + T.themes.sunny], ['night', '🌙 ' + T.themes.night]], p.theme)}</div>
        <div class="set"><span>${T.sound}</span><button class="switch" role="switch" aria-checked="${p.sound}" aria-label="${T.sound}" data-act="toggle" data-k="sound"></button></div>
        ${COURSES[state.active].target === 'ru' ? `<div class="set"><span>${T.translit}</span><button class="switch" role="switch" aria-checked="${p.translit}" aria-label="${T.translit}" data-act="toggle" data-k="translit"></button></div>` : ''}
        <div><div class="set" style="min-height:44px;padding-bottom:6px"><span>${T.course}</span></div>
          ${seg('setCourse', Object.keys(COURSES).map((id) => [id, `${COURSES[id].flag} ${T.courseNames[id]}`]), state.active)}</div>
      </section>
      <section class="card"><h2 style="margin-bottom:6px">${T.about}</h2><p class="soft" style="font-size:15px;line-height:1.45">${esc(T.aboutText)}</p></section>
      <button class="link-danger" data-act="reset">${T.reset}</button>
    </div>${tabbar('profile')}`;
  },
};

function confetti() {
  const dots = [[40, 40, 'accent'], [262, 56, 'blue'], [70, 140, 'primary'], [236, 150, 'purple'], [210, 24, 'primary'], [92, 18, 'purple'], [30, 96, 'blue'], [256, 104, 'accent']];
  return `<svg width="300" height="170" viewBox="0 0 300 170" aria-hidden="true" style="position:absolute;top:0">${dots.map(([x, y, c]) => `<circle cx="${x}" cy="${y}" r="5" fill="var(--${c})"/>`).join('')}</svg>`;
}

// ---------- урок ----------

function hintable(text, lang) {
  const dict = course().dict;
  return text.split(/(\s+)/).map((tok) => {
    if (!tok.trim()) return tok;
    const tr = dict[normalize(tok, lang)];
    return tr ? `<span class="hint-w" data-act="hint" data-tr="${esc(tr)}">${esc(tok)}</span>` : esc(tok);
  }).join('');
}

const showTranslit = (lang) => lang === 'ru' && state.profile.translit;
const trLine = (text, lang) => (showTranslit(lang) ? `<span class="tr">${esc(translit(text))}</span>` : '');

function promptHTML(ex) {
  const p = ex.prompt;
  if (p.text == null) {
    return `<div class="listen-row">
      <button class="speak" data-act="speak" data-text="${esc(p.audio)}" aria-label="▶">${SPEAKER}</button>
      <button class="speak slow" data-act="speak" data-slow="1" data-text="${esc(p.audio)}" aria-label="${t().listenSlow}">${SLOW}</button></div>`;
  }
  const audio = p.audio ? `<button class="speak" data-act="speak" data-text="${esc(p.audio)}" aria-label="▶">${SPEAKER}</button>` : '';
  return `<div class="say">${mascot('happy', 80)}
    <div class="prompt" style="flex:1;margin-bottom:12px">${audio}<div lang="${p.lang}">${hintable(p.text, p.lang)}${trLine(p.text, p.lang)}</div></div></div>`;
}

function canCheck() {
  const ex = run?.ex;
  if (!ex || run.phase !== 'answer') return false;
  if (ex.options) return run.sel != null;
  if (ex.tiles) return run.built.length > 0;
  if ('accepted' in ex) return run.typed.trim().length > 0;
  return false;
}

function quizHTML() {
  const T = t(), ex = run.ex, s = run.session;
  const fb = run.phase === 'feedback';
  const head = `<div class="topline" style="padding:16px 20px 0">
    <button class="icon-btn" data-act="quit" aria-label="${T.close}">${icon('close', 26, 2.8)}</button>
    <div class="bar" role="progressbar" aria-valuenow="${Math.round(s.progress * 100)}" aria-valuemin="0" aria-valuemax="100"><i style="width:${s.progress * 100}%"></i></div>
    <div class="combo">${s.combo >= 2 ? `${FLAME(22)}${s.combo}` : ''}</div></div>`;
  let body = '';
  let foot = '';

  if (ex.type === 'teach') {
    const it = ex.item;
    body = `<span class="badge-new">★ ${T.newWord}</span><h1>${T.q.teach()}</h1>
      <div class="card teach">
        ${it.e ? `<div class="emoji" aria-hidden="true">${it.e}</div>` : ''}
        <div class="word" lang="${course().target}">${esc(it.t[0])}</div>${trLine(it.t[0], course().target)}
        <div class="tr" lang="${native()}">${esc(it.n[0])}</div>
        <button class="speak" data-act="speak" data-text="${esc(it.t[0])}" aria-label="▶">${SPEAKER}</button>
      </div>`;
    foot = `<div class="q-foot"><button class="btn" data-act="teachNext">${T.continue}</button></div>`;
  } else if (ex.type === 'match') {
    const m = run.match;
    const cell = (side, it) => {
      const cls = m.done.includes(it.id) ? 'done' : m.bad?.includes(`${side}:${it.id}`) ? 'bad' : m[side] === it.id ? 'on' : '';
      const lang = side === 'left' ? course().target : native();
      return `<button class="mt ${cls}" data-act="match" data-side="${side}" data-id="${it.id}" lang="${lang}">${esc(it.text)}</button>`;
    };
    body = `<h1>${T.q.match()}</h1>
      <div class="match"><div class="col">${ex.left.map((it) => cell('left', it)).join('')}</div>
      <div class="col">${ex.right.map((it) => cell('right', it)).join('')}</div></div>`;
  } else {
    const title = T.q[ex.type](ex.prompt.text);
    const showPrompt = !['pick_image', 'choose_n2t'].includes(ex.type);
    body = `${ex.isNew ? `<span class="badge-new">★ ${T.newWord}</span>` : ''}<h1>${esc(title)}</h1>${showPrompt ? promptHTML(ex) : ''}`;
    if (ex.options) {
      const grid = ex.type === 'pick_image';
      body += `<div class="options ${grid ? 'grid' : ''}" role="group">${ex.options.map((o, i) => {
        let cls = run.sel === i ? 'on' : '';
        if (fb) cls = o.correct ? 'right' : run.sel === i ? 'wrong' : '';
        return `<button class="opt ${grid ? 'pic' : ''} ${cls}" data-act="opt" data-i="${i}" ${fb ? 'disabled' : ''} lang="${o.lang}">
          ${grid ? `<span class="emoji" aria-hidden="true">${o.emoji}</span>` : `<span class="key">${i + 1}</span>`}
          <span>${esc(o.text)}${trLine(o.text, o.lang)}</span></button>`;
      }).join('')}</div>`;
    } else if (ex.tiles) {
      body += `<div class="answer-line" lang="${ex.answerLang}">${run.built.map((ti, pos) => `<button class="tile" data-act="unbuild" data-pos="${pos}" ${fb ? 'disabled' : ''}>${esc(ex.tiles[ti].text)}</button>`).join('')}</div>
        <div class="bank" lang="${ex.answerLang}">${ex.tiles.map((tl, i) => `<button class="tile ${run.built.includes(i) ? 'used' : ''}" data-act="build" data-i="${i}" ${fb ? 'disabled' : ''}>${esc(tl.text)}</button>`).join('')}</div>`;
    } else {
      body += `<textarea id="write" class="write" lang="${ex.answerLang}" rows="3" autocapitalize="off" autocomplete="off" spellcheck="false"
        placeholder="${esc(T.typePh)}" ${fb ? 'readonly' : ''}>${esc(run.typed)}</textarea>
        ${ex.answerLang === 'ru' && T.typePhRu ? `<p class="note">${esc(T.typePhRu)}</p>` : ''}`;
    }
  }

  if (ex.type !== 'teach') {
    if (fb) {
      const r = run.fb;
      if (r.correct) {
        foot = `<div class="q-foot ok" role="status">
          <div class="fb-title">${icon('check', 30, 3)}${esc(run.fbTitle)}</div>
          ${r.typo ? `<div class="fb-text">${T.typo} <b>${esc(r.solution)}</b></div>` : ''}
          <button class="btn" data-act="next">${T.continue}</button></div>`;
      } else {
        foot = `<div class="q-foot bad" role="status">
          <div class="fb-title">${esc(T.almost)}</div>
          ${r.solution ? `<div class="fb-text">${T.wrong}</div><div class="fb-answer" lang="${ex.answerLang || ''}">${esc(r.solution)}</div>` : ''}
          <div class="row">${mascot('care', 54)}<span class="fb-text" style="color:var(--ink)">${esc(run.fbSoft)}</span></div>
          <button class="btn danger" data-act="next">${T.gotIt}</button></div>`;
      }
    } else if (ex.type !== 'match') {
      const dontKnow = run.kind === 'placement' ? `<button class="btn ghost small" data-act="dontKnow">${T.dontKnow}</button>` : '';
      foot = `<div class="q-foot">${dontKnow}<button id="checkBtn" class="btn" data-act="check" ${canCheck() ? '' : 'disabled'}>${T.check}</button></div>`;
    }
  }
  return `<div class="quiz">${head}<div class="q-body">${body}</div>${foot}</div>`;
}

function startRun(kind, session, extra = {}) {
  run = { kind, session, ...extra };
  nextEx();
}

function nextEx() {
  run.ex = run.session.next();
  Object.assign(run, { sel: null, built: [], typed: '', phase: 'answer', fb: null, match: { left: null, right: null, done: [], mistakes: [], bad: null } });
  if (!run.ex) return finishRun();
  view = { name: 'quiz' };
  render();
  const ex = run.ex;
  if (ex.type === 'teach') say(ex.item.t[0]);
  else if (ex.prompt?.audio && ['listen_choose', 'listen_bank', 'choose_t2n', 'bank_t2n'].includes(ex.type)) say(ex.prompt.audio);
}

function submitAnswer(resp) {
  const ex = run.ex;
  const r = run.session.submit(resp);
  if (run.kind === 'placement') return nextEx(); // в тесте на уровень — без оценок, чтобы не было стресса
  run.phase = 'feedback';
  run.fb = r;
  run.fbTitle = pick(t().right);
  const ev = run.session.takeEvent();
  run.fbSoft = ev?.kind === 'support' ? t().support(state.profile.name) : pick(t().wrongSoft);
  sfx(r.correct ? 'right' : 'wrong', state.profile.sound);
  if (!r.correct) navigator.vibrate?.(60);
  if (ex.answerLang === course().target && r.solution) say(r.solution);
  if (ev?.kind === 'combo') toast(t().combo(ev.n));
  render();
}

function check() {
  if (!canCheck()) return;
  const ex = run.ex;
  if (ex.options) submitAnswer({ choice: run.sel });
  else if (ex.tiles) submitAnswer({ text: run.built.map((i) => ex.tiles[i].text).join(' ') });
  else submitAnswer({ text: run.typed });
}

function matchTap(side, id) {
  const m = run.match;
  m[side] = id;
  if (side === 'left') say(run.ex.left.find((x) => x.id === id).text);
  if (m.left && m.right) {
    if (m.left === m.right) {
      m.done.push(m.left);
      sfx('tap', state.profile.sound);
    } else {
      for (const x of [m.left, m.right]) if (!m.mistakes.includes(x)) m.mistakes.push(x);
      m.bad = [`left:${m.left}`, `right:${m.right}`];
      sfx('wrong', state.profile.sound);
      setTimeout(() => { if (run?.match === m) { m.bad = null; render(); } }, 450);
    }
    m.left = m.right = null;
  }
  if (m.done.length === run.ex.left.length) submitAnswer({ mistakes: m.mistakes });
  else render();
}

function finishRun() {
  if (run.kind === 'placement') {
    const u = run.session.result();
    applyPlacement(course(), learner(), u);
    state.onboarded[state.active] = true;
    save();
    view = { name: 'placementDone', u };
    run = null;
    ui.scroll = true;
    return render();
  }
  const summary = run.session.finish();
  if (run.kind === 'lesson') markLessonDone(learner(), run.u, run.l);
  const h = state.history[today()] || (state.history[today()] = { xp: 0, lessons: 0, ms: 0 });
  const before = h.xp;
  h.xp += summary.xp;
  h.lessons++;
  h.ms += summary.ms;
  state.streak = registerActivity(state.streak, today());
  save();
  sfx('done', state.profile.sound);
  view = { name: 'result', kind: run.kind, summary, goalJust: before < state.profile.goal && h.xp >= state.profile.goal };
  run = null;
  ui.scroll = true;
  render();
}

// ---------- действия ----------

function finishOnboarding() {
  state.onboarded[state.active] = true;
  save();
  ui.scroll = true;
  view = { name: 'home' };
  render();
}

const ACT = {
  pickCourse(el) {
    state.active = el.dataset.id;
    setLang(native());
    save();
    if (state.onboarded[state.active]) { view = { name: 'home' }; ui.scroll = true; }
    else view = { name: 'onboard', step: state.profile.why ? 'level' : 'name' };
    render();
  },
  obBack() {
    const order = ['name', 'why', 'goal', 'level'];
    if (view.name === 'placementIntro') view = { name: 'onboard', step: 'level' };
    else {
      const i = order.indexOf(view.step);
      view = i > 0 ? { name: 'onboard', step: order[i - 1] } : { name: 'welcome' };
    }
    render();
  },
  obNext() { view = { name: 'onboard', step: 'why' }; save(); render(); },
  obWhy(el) { state.profile.why = el.dataset.k; save(); view = { name: 'onboard', step: 'goal' }; render(); },
  obGoal(el) { state.profile.goal = +el.dataset.xp; save(); view = { name: 'onboard', step: 'level' }; render(); },
  obLevel(el) {
    const k = el.dataset.k;
    if (k === 'zero') return finishOnboarding();
    view = { name: 'placementIntro', start: k === 'good' ? 5 : 2 };
    render();
  },
  startPlacement() {
    startRun('placement', new Placement({ courseData: course(), learner: learner(), start: view.start ?? 2 }));
  },
  go(el) { view = { name: el.dataset.to }; if (el.dataset.to === 'home') ui.scroll = true; render(); window.scrollTo(0, 0); },
  tip(el) { const u = +el.dataset.u; ui.tipOpen = ui.tipOpen === u ? null : u; render(); },
  locked() { toast(t().locked); },
  startLesson(el) {
    const u = +el.dataset.u, l = +el.dataset.l;
    const queue = buildLessonQueue(course(), learner(), u, l);
    startRun('lesson', new Session({ courseData: course(), learner: learner(), queue, audio: AUDIO }), { u, l });
  },
  practice(el) {
    const mode = el.dataset.mode;
    const queue = buildPracticeQueue(course(), learner(), { mode });
    if (!queue.length) return toast(t().practiceEmpty);
    startRun('practice', new Session({ courseData: course(), learner: learner(), queue, audio: AUDIO, target: 0.72 }));
  },
  quit() { run = null; view = { name: 'home' }; ui.scroll = true; save(); render(); },
  speak(el) { AUDIO ? speak(el.dataset.text, COURSES[state.active].speech, !!el.dataset.slow) : toast(t().noAudio); },
  hint(el) {
    document.querySelector('.hint-pop')?.remove();
    const r = el.getBoundingClientRect();
    const pop = document.createElement('div');
    pop.className = 'hint-pop';
    pop.textContent = el.dataset.tr;
    pop.style.left = `${r.left + window.scrollX}px`;
    pop.style.top = `${r.bottom + window.scrollY + 6}px`;
    document.body.appendChild(pop);
    setTimeout(() => pop.remove(), 1800);
  },
  opt(el) {
    if (run.phase !== 'answer') return;
    run.sel = +el.dataset.i;
    const o = run.ex.options[run.sel];
    if (o.lang === course().target) say(o.text);
    render();
  },
  build(el) {
    if (run.phase !== 'answer') return;
    const i = +el.dataset.i;
    run.built.push(i);
    if (run.ex.answerLang === course().target) say(run.ex.tiles[i].text);
    render();
  },
  unbuild(el) { if (run.phase === 'answer') { run.built.splice(+el.dataset.pos, 1); render(); } },
  match(el) { if (run.phase === 'answer') matchTap(el.dataset.side, el.dataset.id); },
  check,
  dontKnow() { submitAnswer({ text: '' }); },
  next() { nextEx(); },
  teachNext() { run.session.submit(); nextEx(); },
  setGoal(el) { state.profile.goal = +el.dataset.v; save(); render(); },
  setTheme(el) { state.profile.theme = el.dataset.v; save(); render(); },
  toggle(el) { const k = el.dataset.k; state.profile[k] = !state.profile[k]; save(); render(); },
  setCourse(el) {
    state.active = el.dataset.v;
    setLang(native());
    save();
    view = state.onboarded[state.active] ? { name: 'profile' } : { name: 'onboard', step: 'level' };
    render();
  },
  reset() {
    if (!confirm(t().resetConfirm)) return;
    delete state.courses[state.active];
    state.onboarded[state.active] = false;
    save();
    view = { name: 'onboard', step: 'level' };
    render();
  },
};

$app.addEventListener('click', (e) => {
  const el = e.target.closest('[data-act]');
  if (el && ACT[el.dataset.act]) ACT[el.dataset.act](el, e);
});

$app.addEventListener('input', (e) => {
  if (e.target.id === 'nameInput') { state.profile.name = e.target.value.trim(); save(); }
  if (e.target.id === 'write' && run) {
    run.typed = e.target.value;
    const b = document.getElementById('checkBtn');
    if (b) b.disabled = !canCheck();
  }
});

document.addEventListener('keydown', (e) => {
  if (view.name !== 'quiz' || !run) return;
  if (e.key === 'Enter') {
    e.preventDefault();
    if (run.phase === 'feedback') nextEx();
    else if (run.ex.type === 'teach') ACT.teachNext();
    else check();
  } else if (/^[1-9]$/.test(e.key) && run.ex.options && run.phase === 'answer' && e.target.tagName !== 'TEXTAREA') {
    const i = +e.key - 1;
    if (run.ex.options[i]) { run.sel = i; render(); }
  }
});

// ---------- старт ----------

state.streak = checkStreak(state.streak, today());
if (state.active && COURSES[state.active]) {
  setLang(native());
  view = state.onboarded[state.active] ? { name: 'home' } : { name: 'onboard', step: state.profile.why ? 'level' : 'name' };
  ui.scroll = true;
} else {
  state.active = null;
}
save();
render();

// Для автотестов: при открытии с ?debug виден текущий урок (window.buki.run).
if (new URLSearchParams(location.search).has('debug')) window.buki = { get run() { return run; } };

if ('serviceWorker' in navigator && location.protocol === 'https:') {
  navigator.serviceWorker.register('./sw.js').catch(() => {});
}
