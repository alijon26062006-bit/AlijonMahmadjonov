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
  if (opts.class) node.className = opts.class;
  if (opts.text != null) node.textContent = opts.text;
  if (opts.html != null) node.innerHTML = opts.html;   // только для собственных иконок
  for (const [k, v] of Object.entries(opts.attrs || {})) {
    if (v != null && v !== false) node.setAttribute(k, v);
  }
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

/** Иконки лежат одним файлом; браузеры надёжно видят их только внутри документа. */
async function injectSprite() {
  try {
    const res = await fetch('icons/sprite.svg', { cache: 'force-cache' });
    if (!res.ok) return;
    const holder = el('div', { attrs: { 'aria-hidden': 'true' }, html: await res.text() });
    holder.style.display = 'none';
    document.body.prepend(holder);
  } catch (_) { /* без иконок сайт остаётся читаемым */ }
}

async function loadJSON(path) {
  const res = await fetch(path, { cache: 'no-cache' });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

/* --- секции --------------------------------------------------- */

function renderHero(p) {
  const media = document.getElementById('heroMedia');
  clear(media);

  const poster = p.meta.videoPoster || p.meta.photo;
  if (p.meta.video) {
    // Видео тяжёлое: постер показывается сразу, файл подтягивается следом.
    const video = el('video', { attrs: {
      autoplay: '', muted: '', loop: '', playsinline: '',
      preload: 'none', poster
    }});
    video.muted = true;
    video.appendChild(el('source', { attrs: { src: p.meta.video, type: 'video/mp4' } }));
    media.appendChild(video);
    video.play().catch(() => {});
  } else if (p.meta.photo) {
    media.appendChild(el('img', { attrs: {
      src: p.meta.photo, alt: '', decoding: 'async', fetchpriority: 'high'
    }}));
  }

  const tg = p.contacts.items.find(c => c.icon === 'telegram');
  if (tg) {
    document.getElementById('heroCta1').href = tg.url;
    document.getElementById('servicesCta').href = tg.url;
  }
}

function renderAbout(p) {
  const facts = document.getElementById('facts');
  clear(facts);
  for (const f of p.about.facts) {
    facts.appendChild(el('li', {}, [
      el('span', { class: 'k', text: t(f.k, lang) }),
      el('span', { class: 'v', text: t(f.v, lang) })
    ]));
  }

  const body = document.getElementById('aboutBody');
  clear(body);
  for (const par of p.about.paragraphs) body.appendChild(el('p', { text: t(par, lang) }));

  const work = document.getElementById('workBody');
  clear(work);
  for (const par of p.work.paragraphs) work.appendChild(el('p', { text: t(par, lang) }));
}

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
      el('span', { class: 'skill-name', text: s.name }),
      el('span', {
        class: 'level', text: t(p.skills.levels[s.level], lang),
        attrs: { 'data-level': s.level }
      })
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
  clear(box);
  for (const item of items) box.appendChild(build(item));
}

function renderProjects(p, projects) {
  const box = document.getElementById('projectsWrap');
  clear(box);

  const visible = projects.filter(x => x.visible !== false);
  if (!visible.length) {
    box.appendChild(el('div', { class: 'empty reveal' }, [
      icon('folder'),
      el('p', { text: t(p.sections.projectsEmpty, lang) })
    ]));
    return;
  }

  const grid = el('div', { class: 'projects' });
  for (const pr of visible) {
    const cover = pr.cover
      ? el('div', { class: 'project-cover' }, [
          el('img', { attrs: { src: pr.cover, alt: '', loading: 'lazy', decoding: 'async' } })
        ])
      : null;

    const tags = el('div', { class: 'project-tags' });
    if (pr.status) {
      tags.appendChild(el('span', {
        class: 'status', text: t(p.sections.status[pr.status], lang),
        attrs: { 'data-status': pr.status }
      }));
    }
    for (const tag of pr.tags || []) tags.appendChild(el('span', { class: 'tag', text: tag }));

    grid.appendChild(el('a', {
      class: 'project reveal',
      attrs: { href: 'project.html?slug=' + encodeURIComponent(pr.slug) }
    }, [
      cover,
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
    list.appendChild(el('li', { class: 'diary-item' }, [
      el('p', { text: t(p.sections.diaryEmpty, lang) })
    ]));
    return;
  }

  for (const e of sorted) {
    list.appendChild(el('li', { class: 'diary-item reveal' }, [
      el('time', { class: 'diary-date', attrs: { datetime: e.date } }, [
        icon('calendar'), el('span', { text: formatDate(e.date, lang) })
      ]),
      el('div', {}, [
        el('h3', { text: t(e.t, lang) }),
        el('p', { text: t(e.d, lang) })
      ])
    ]));
  }
}

function renderContacts(p) {
  const list = document.getElementById('contactsList');
  clear(list);
  for (const c of p.contacts.items) {
    list.appendChild(el('li', {}, [
      el('a', { attrs: { href: c.url, target: '_blank', rel: 'noopener' } }, [
        icon(c.icon),
        el('span', { class: 'contact-label', text: c.label }),
        el('span', { class: 'contact-value', text: c.value }),
        icon('arrow-right', 'icon go')
      ])
    ]));
  }
}

/* --- сборка страницы ------------------------------------------- */

/** Общее для всех страниц: подписи, навигация, год, кнопки языка. */
function renderCommon() {
  const p = DATA.profile;
  document.documentElement.lang = HTML_LANG[lang];

  // Простые подписи: элементы с data-bind="путь.в.профиле"
  for (const node of document.querySelectorAll('[data-bind]')) {
    node.textContent = t(pick(p, node.dataset.bind), lang);
  }
  for (const node of document.querySelectorAll('[data-nav]')) {
    node.textContent = t(p.nav[node.dataset.nav], lang);
  }
  const skip = document.querySelector('.skip-link');
  if (skip) skip.textContent = t(p.a11y.skip, lang);

  const year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();

  for (const btn of document.querySelectorAll('.lang button')) {
    btn.setAttribute('aria-pressed', String(btn.dataset.lang === lang));
  }
}

/** Главная страница целиком. */
function renderHome() {
  const p = DATA.profile;
  renderCommon();

  renderHero(p);
  renderAbout(p);
  renderTimeline(DATA.timeline.items);
  renderSkills(p);
  renderCards('principlesGrid', p.principles.items, item =>
    el('div', { class: 'card reveal' }, [
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

  document.dispatchEvent(new CustomEvent('site:rendered'));
}

/** Главная знает себя по блоку с фото; остальные страницы рисуют себя сами. */
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
      main.prepend(el('div', { class: 'wrap', attrs: { style: 'padding-top:6rem' } }, [
        el('p', { text: 'Не удалось загрузить данные сайта: ' + err.message })
      ]));
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
