/* ===========================================================
   Рендер сайта из data/*.json.
   В HTML нет ни одного текста о человеке — всё приходит отсюда.
   =========================================================== */

const DATA = { profile: null, timeline: null, projects: null, diary: null };
let lang = 'tj';

/* --- маленькие помощники ------------------------------------- */

/** Создаёт элемент. Текст ставится через textContent — разметка из данных не исполняется. */
function el(tag, opts = {}, children = []) {
  const node = document.createElement(tag);
  if (opts.id) node.id = opts.id;
  if (opts.class) node.className = opts.class;
  if (opts.text != null) node.textContent = opts.text;
  for (const [k, v] of Object.entries(opts.attrs || {})) {
    if (v != null && v !== false) node.setAttribute(k, v === true ? '' : v);
  }
  for (const [k, v] of Object.entries(opts.style || {})) node.style.setProperty(k, v);
  for (const child of [].concat(children)) if (child) node.appendChild(child);
  return node;
}

function icon(name, cls = 'icon') {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', cls);
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', '#i-' + name);
  svg.appendChild(use);
  return svg;
}

function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

/** Заголовок, где одно слово залито градиентом: {before, accent, after}. */
function gradHeadline(node, parts) {
  clear(node);
  if (!parts) return;
  if (parts.before) node.append(parts.before + ' ');
  if (parts.accent) node.appendChild(el('span', { class: 'grad-text', text: parts.accent }));
  if (parts.after) node.append(' ' + parts.after);
}

/** Иконки лежат одним файлом; браузеры надёжно видят их только внутри документа. */
async function injectSprite() {
  try {
    const res = await fetch('icons/sprite.svg', { cache: 'force-cache' });
    if (!res.ok) return;
    const holder = el('div', { attrs: { 'aria-hidden': 'true' } });
    holder.innerHTML = await res.text();   // собственный файл, не пользовательские данные
    holder.style.display = 'none';
    document.body.prepend(holder);
  } catch (_) { /* без иконок сайт остаётся читаемым */ }
}

async function loadJSON(path) {
  const res = await fetch(path, { cache: 'no-cache' });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

/* --- Первый экран ---------------------------------------------- */

function renderHero(p) {
  const media = document.getElementById('heroMedia');
  clear(media);

  const poster = p.meta.videoPoster || p.meta.photo;
  const wantsMotion = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  // На узких экранах и при выключенном движении показываем кадр вместо видео —
  // мобильный интернет не должен тянуть мегабайты ради фона.
  const bigScreen = window.matchMedia('(min-width: 760px)').matches;

  if (p.meta.video && wantsMotion && bigScreen) {
    const video = el('video', { attrs: {
      autoplay: true, muted: true, loop: true, playsinline: true, preload: 'none', poster
    }});
    video.muted = true;
    video.appendChild(el('source', { attrs: { src: p.meta.video, type: 'video/mp4' } }));
    media.appendChild(video);
    video.play().catch(() => {});
  } else if (poster) {
    media.appendChild(el('img', { attrs: { src: poster, alt: '', decoding: 'async', fetchpriority: 'high' } }));
  }

  gradHeadline(document.getElementById('heroTitle'), t(p.hero.headline, lang));

  const stats = document.getElementById('stats');
  clear(stats);
  for (const s of p.hero.stats || []) {
    stats.appendChild(el('li', {}, [
      el('span', { class: 'v grad-text', text: s.v }),
      el('span', { class: 'k', text: t(s.k, lang) })
    ]));
  }

  // Лента дублируется, чтобы прокрутка на -50% выглядела бесшовной
  const ticker = document.getElementById('ticker');
  clear(ticker);
  const words = p.hero.ticker || [];
  for (const word of [...words, ...words]) ticker.appendChild(el('span', { text: word }));

  const tg = p.contacts.items.find(c => c.icon === 'telegram');
  if (tg) document.getElementById('heroCta1').href = tg.url;
}

/* --- Кто я ------------------------------------------------------ */

function renderAbout(p) {
  const portrait = document.getElementById('portrait');
  clear(portrait);
  if (p.meta.photo) {
    portrait.append(
      el('img', { attrs: { src: p.meta.photo, alt: p.meta.name, loading: 'lazy', decoding: 'async' } }),
      el('figcaption', { class: 'badge badge-dot', text: t(p.about.statusBadge, lang) })
    );
  }

  gradHeadline(document.getElementById('greeting'), t(p.about.greeting, lang));

  const body = document.getElementById('aboutBody');
  clear(body);
  for (const par of p.about.paragraphs) body.appendChild(el('p', { text: t(par, lang) }));

  const stack = document.getElementById('stack');
  clear(stack);
  for (const item of p.about.stack || []) {
    stack.appendChild(el('li', {}, [
      el('span', { class: 'dot', style: { background: item.color || 'var(--c-ice)' } }),
      el('span', { text: item.name })
    ]));
  }

  const work = document.getElementById('workBody');
  clear(work);
  for (const par of p.work.paragraphs) work.appendChild(el('p', { text: t(par, lang) }));
}

/* --- Путь, навыки, карточки -------------------------------------- */

function renderTimeline(items) {
  const list = document.getElementById('timeline');
  clear(list);
  for (const item of items) {
    list.appendChild(el('li', {
      class: 'tl-item reveal',
      attrs: { 'data-highlight': item.highlight || null, 'data-future': item.future || null }
    }, [
      el('span', { class: 'tl-year', text: item.year }),
      el('h3', { text: t(item.t, lang) }),
      el('p', { text: t(item.d, lang) })
    ]));
  }
}

function renderSkills(p) {
  const list = document.getElementById('skillsList');
  clear(list);
  for (const s of p.skills.items) {
    list.appendChild(el('li', { class: 'skill' }, [
      el('span', { text: s.name }),
      el('span', { class: 'level', text: t(p.skills.levels[s.level], lang), attrs: { 'data-level': s.level } })
    ]));
  }

  const langs = document.getElementById('langs');
  clear(langs);
  for (const l of p.languages.items) {
    langs.appendChild(el('li', {}, [
      el('span', { text: t(l.name, lang) + ' — ' }),
      el('span', { class: 'lvl', text: t(l.level, lang) })
    ]));
  }
}

function renderCards(containerId, items, build) {
  const box = document.getElementById(containerId);
  if (!box) return;
  clear(box);
  for (const item of items) box.appendChild(build(item));
}

/* --- Проекты и дневник -------------------------------------------- */

function renderProjects(p, projects) {
  const box = document.getElementById('projectsWrap');
  clear(box);

  const visible = projects.filter(x => x.visible !== false);
  if (!visible.length) {
    box.appendChild(el('div', { class: 'empty reveal' }, [
      icon('folder'), el('p', { text: t(p.sections.projectsEmpty, lang) })
    ]));
    return;
  }

  const grid = el('div', { class: 'projects' });
  for (const pr of visible) {
    const tags = el('div', { class: 'project-tags' });
    if (pr.status) {
      tags.appendChild(el('span', {
        class: 'status', text: t(p.sections.status[pr.status], lang), attrs: { 'data-status': pr.status }
      }));
    }
    for (const tag of pr.tags || []) tags.appendChild(el('span', { class: 'tag', text: tag }));

    grid.appendChild(el('a', {
      class: 'project reveal', attrs: { href: 'project.html?slug=' + encodeURIComponent(pr.slug) }
    }, [
      pr.cover ? el('div', { class: 'project-cover' }, [
        el('img', { attrs: { src: pr.cover, alt: '', loading: 'lazy', decoding: 'async' } })
      ]) : null,
      el('div', { class: 'project-body' }, [
        el('h3', { text: t(pr.title, lang) }),
        el('p', { text: t(pr.summary, lang) }),
        tags
      ])
    ]));
  }
  box.appendChild(grid);
}

// Локали tg-TJ в браузерах нет — таджикские месяцы пишем сами.
const TJ_MONTHS = ['январи', 'феврали', 'марти', 'апрели', 'майи', 'июни',
                   'июли', 'августи', 'сентябри', 'октябри', 'ноябри', 'декабри'];

function formatDate(iso, lang) {
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  if (lang === 'tj') return `${d.getDate()}-уми ${TJ_MONTHS[d.getMonth()]} ${d.getFullYear()}`;
  return d.toLocaleDateString('ru-RU', { year: 'numeric', month: 'long', day: 'numeric' });
}

function renderDiary(p, entries) {
  const list = document.getElementById('diaryList');
  clear(list);

  const sorted = [...entries].sort((a, b) => String(b.date).localeCompare(String(a.date)));
  if (!sorted.length) {
    list.appendChild(el('li', { class: 'diary-item' }, [el('p', { text: t(p.sections.diaryEmpty, lang) })]));
    return;
  }
  for (const e of sorted) {
    list.appendChild(el('li', { class: 'diary-item reveal' }, [
      el('time', { class: 'diary-date', attrs: { datetime: e.date } },
        [icon('calendar'), el('span', { text: formatDate(e.date, lang) })]),
      el('div', {}, [el('h3', { text: t(e.t, lang) }), el('p', { text: t(e.d, lang) })])
    ]));
  }
}

/* --- Контакты и форма заказа ---------------------------------------- */

function renderContacts(p) {
  const list = document.getElementById('contactsList');
  clear(list);
  for (const c of p.contacts.items) {
    list.appendChild(el('li', {}, [
      el('a', { attrs: { href: c.url, target: '_blank', rel: 'noopener' } }, [
        icon(c.icon),
        el('span', { class: 'contact-value', text: c.value })
      ])
    ]));
  }
  gradHeadline(document.getElementById('formTitle'), t(p.contacts.formTitle, lang));
}

/**
 * Сервера у сайта нет — GitHub Pages отдаёт только статику.
 * Поэтому форма не «отправляет письмо», а открывает Telegram с готовым текстом.
 */
function wireOrderForm(p) {
  const form = document.getElementById('orderForm');
  if (!form || form.dataset.wired) return;
  form.dataset.wired = '1';

  form.addEventListener('submit', event => {
    event.preventDefault();
    const tg = DATA.profile.contacts.items.find(c => c.icon === 'telegram');
    if (!tg) return;

    const greeting = t(DATA.profile.contacts.form.greeting, lang);
    const name = form.elements.name.value.trim();
    const task = form.elements.task.value.trim();
    const text = `${greeting} ${name}.\n\n${task}`;

    window.open(`${tg.url}?text=${encodeURIComponent(text)}`, '_blank', 'noopener');
  });
}

/* --- Сборка страницы -------------------------------------------------- */

/** Общее для всех страниц: подписи, навигация, год, кнопки языка. */
function renderCommon() {
  const p = DATA.profile;
  document.documentElement.lang = HTML_LANG[lang];

  for (const node of document.querySelectorAll('[data-bind]')) {
    node.textContent = t(pick(p, node.dataset.bind), lang);
  }
  for (const node of document.querySelectorAll('[data-nav]')) {
    node.textContent = t(p.nav[node.dataset.nav], lang);
  }

  const year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();

  for (const btn of document.querySelectorAll('.lang button')) {
    btn.setAttribute('aria-pressed', String(btn.dataset.lang === lang));
  }
}

function renderHome() {
  const p = DATA.profile;
  renderCommon();

  renderHero(p);
  renderAbout(p);
  renderTimeline(DATA.timeline.items);
  renderSkills(p);

  gradHeadline(document.getElementById('advTitle'), t(p.advantages.title, lang));
  renderCards('advantages', p.advantages.items, item =>
    el('div', { class: 'card reveal' }, [
      el('div', { class: 'card-icon' }, [icon(item.icon)]),
      el('h3', { text: t(item.t, lang) }),
      el('p', { text: t(item.d, lang) })
    ]));

  renderCards('goalsGrid', p.goals.items, item =>
    el('div', { class: 'card reveal' }, [
      el('span', { class: 'when', text: t(item.when, lang) }),
      el('h3', { text: t(item.t, lang) }),
      el('p', { text: t(item.d, lang) })
    ]));

  renderCards('servicesGrid', p.services.items, item =>
    el('div', { class: 'card reveal' }, [
      el('div', { class: 'card-icon' }, [icon(item.icon)]),
      el('h3', { text: t(item.t, lang) }),
      el('p', { text: t(item.d, lang) })
    ]));

  renderProjects(p, DATA.projects.items);
  renderDiary(p, DATA.diary.items);
  renderContacts(p);
  wireOrderForm(p);

  document.dispatchEvent(new CustomEvent('site:rendered'));
}

/** Главная знает себя по блоку с фоном; остальные страницы рисуют себя сами. */
function renderPage() {
  if (document.getElementById('heroMedia')) {
    renderHome();
  } else {
    renderCommon();
    document.dispatchEvent(new CustomEvent('site:data'));
  }
}

async function boot() {
  injectSprite();
  try {
    const [profile, timeline, projects, diary] = await Promise.all([
      loadJSON('data/profile.json'),
      loadJSON('data/timeline.json'),
      loadJSON('data/projects.json'),
      loadJSON('data/diary.json')
    ]);
    Object.assign(DATA, { profile, timeline, projects, diary });
  } catch (err) {
    const main = document.getElementById('main');
    if (main) {
      main.prepend(el('div', { class: 'wrap', style: { 'padding-top': '8rem' } },
        [el('p', { text: 'Не удалось загрузить данные сайта: ' + err.message })]));
    }
    return;
  }

  lang = readLang(DATA.profile.meta.defaultLang);
  renderPage();

  for (const btn of document.querySelectorAll('.lang button')) {
    btn.addEventListener('click', () => {
      lang = btn.dataset.lang;
      saveLang(lang);
      renderPage();
    });
  }
}

boot();
