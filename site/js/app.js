/* =========================================================
   ИНТЕРФЕЙС САЙТА
   =========================================================
   Языки, меню, карточки навыков и проектов, форма заявки,
   инерционный скролл и появление блоков при прокрутке.
   ========================================================= */

import Lenis from './lenis.mjs';
import { dicts, LANGS, LANG_LABELS } from '../lang.js';
import { person, contacts, skills, projects, orderTarget, audio, getAge } from '../config.js';

const STORAGE_KEY = 'alijon.lang';
const DEFAULT_LANG = 'ru';           // язык, на котором написан index.html
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

let lang = DEFAULT_LANG;

/* ---------------------------------------------------------
   ИКОНКИ — рисуем сами, чтобы не тянуть библиотеку
   --------------------------------------------------------- */
const ICONS = {
  telegram: '<path d="M21.5 4.3 2.9 11.5c-.9.3-.9 1.6 0 1.9l4.6 1.5 1.8 5.4c.2.7 1.1.9 1.6.3l2.5-2.7 4.7 3.5c.6.4 1.4.1 1.6-.6l3.4-15c.2-.8-.6-1.5-1.6-1.5Z"/><path d="m7.5 14.9 10.6-7.4-8.3 8.7-.4 4"/>',
  instagram: '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.4" cy="6.6" r="1.1" fill="currentColor" stroke="none"/>',
  github: '<path d="M9 19c-4.3 1.4-4.3-2.2-6-2.6m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.7 4.7 0 0 0-1.3-3.2 4.3 4.3 0 0 0-.1-3.3s-1.1-.3-3.6 1.3a12.3 12.3 0 0 0-6.4 0C6.1 3.1 5 3.4 5 3.4a4.3 4.3 0 0 0-.1 3.3A4.7 4.7 0 0 0 3.5 10c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21"/>',
  mail: '<rect x="2.5" y="4.5" width="19" height="15" rx="3"/><path d="m3 7 8.2 5.6a1.5 1.5 0 0 0 1.6 0L21 7"/>',
  phone: '<path d="M21 16.5v2.6a2 2 0 0 1-2.2 2 19.6 19.6 0 0 1-8.5-3 19.3 19.3 0 0 1-6-6 19.6 19.6 0 0 1-3-8.6A2 2 0 0 1 3.3 1.5H6a2 2 0 0 1 2 1.7c.1 1 .3 1.9.7 2.8a2 2 0 0 1-.5 2.1L7.1 9.3a16 16 0 0 0 6 6l1.2-1.1a2 2 0 0 1 2.1-.5c.9.4 1.8.6 2.8.7a2 2 0 0 1 1.8 2.1Z"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  arrowDown: '<path d="M12 4v16M6 14l6 6 6-6"/>',
  arrowUpRight: '<path d="M7 17 17 7M9 7h8v8"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2.5"/><path d="M6 15H4.5A1.5 1.5 0 0 1 3 13.5v-9A1.5 1.5 0 0 1 4.5 3h9A1.5 1.5 0 0 1 15 4.5V6"/>',
  check: '<path d="m5 12.5 5 5 9-11"/>',
  send: '<path d="M21 3 10.5 13.5M21 3l-6.8 18-3.7-7.5L3 9.8 21 3Z"/>',
  sound: '<path d="M11 5 6.5 9H3v6h3.5L11 19V5Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>',
  mute: '<path d="M11 5 6.5 9H3v6h3.5L11 19V5Z"/><path d="m16 9.5 5 5m0-5-5 5"/>',
};

function icon(name, extra = '') {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="${extra}">${ICONS[name] || ''}</svg>`;
}

/* Знаки проектов — линейная графика вместо скриншотов */
const GLYPHS = {
  messenger: '<rect class="g-a" x="14" y="20" width="50" height="34" rx="10"/><path class="g-a" d="M26 62l-6 12 16-9"/><rect class="g-b" x="38" y="40" width="44" height="30" rx="9"/><circle class="g-c" cx="30" cy="36" r="2.4"/><circle class="g-c" cx="39" cy="36" r="2.4"/><circle class="g-c" cx="48" cy="36" r="2.4"/>',
  marketplace: '<path class="g-a" d="M18 34h60l-5 44H23z"/><path class="g-b" d="M34 34V24a14 14 0 0128 0v10"/><path class="g-c" d="M32 52h32M32 63h20"/>',
  bot: '<rect class="g-a" x="20" y="30" width="56" height="42" rx="12"/><path class="g-b" d="M48 30V16M48 12a4 4 0 100 8 4 4 0 000-8z"/><circle class="g-c" cx="36" cy="48" r="4.5"/><circle class="g-c" cx="60" cy="48" r="4.5"/><path class="g-b" d="M38 61h20M12 44v14M84 44v14"/>',
  miniapp: '<rect class="g-a" x="30" y="12" width="36" height="72" rx="9"/><path class="g-b" d="M30 26h36M30 70h36"/><rect class="g-c" x="38" y="34" width="9" height="9" rx="2.5"/><rect class="g-c" x="51" y="34" width="9" height="9" rx="2.5"/><rect class="g-c" x="38" y="49" width="9" height="9" rx="2.5"/><rect class="g-c" x="51" y="49" width="9" height="9" rx="2.5"/>',
  ai: '<circle class="g-a" cx="48" cy="48" r="13"/><circle class="g-b" cx="48" cy="16" r="5"/><circle class="g-b" cx="48" cy="80" r="5"/><circle class="g-b" cx="19" cy="32" r="5"/><circle class="g-b" cx="77" cy="32" r="5"/><circle class="g-b" cx="19" cy="64" r="5"/><circle class="g-b" cx="77" cy="64" r="5"/><path class="g-c" d="M48 21v14M48 61v14M24 35l12 7M72 35L60 42M24 61l12-7M72 61L60 54"/>',
  web: '<rect class="g-a" x="12" y="20" width="72" height="56" rx="9"/><path class="g-b" d="M12 36h72"/><circle class="g-c" cx="23" cy="28" r="2.2"/><circle class="g-c" cx="31" cy="28" r="2.2"/><circle class="g-c" cx="39" cy="28" r="2.2"/><path class="g-c" d="M26 50h30M26 61h44"/>',
};

/* ---------------------------------------------------------
   ЯЗЫКИ
   --------------------------------------------------------- */
/** Достаёт значение из словаря по пути вида "hero.tagline" */
function t(path) {
  return path.split('.').reduce((value, key) => (value == null ? null : value[key]), dicts[lang]);
}

/** Подставляет {age} и подобные плейсхолдеры */
function fill(template, vars) {
  return String(template).replace(/\{(\w+)\}/g, (match, key) => (key in vars ? vars[key] : match));
}

function detectLang() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved && LANGS.includes(saved)) return saved;

  const list = navigator.languages?.length ? navigator.languages : [navigator.language];
  for (const raw of list) {
    const code = String(raw).toLowerCase().split('-')[0];
    if (LANGS.includes(code)) return code;
  }
  return DEFAULT_LANG;
}

function applyLang(next) {
  lang = next;
  document.documentElement.lang = next;
  try { localStorage.setItem(STORAGE_KEY, next); } catch { /* приватный режим */ }

  // Простые подписи: <span data-t="nav.about">
  document.querySelectorAll('[data-t]').forEach((node) => {
    const value = t(node.dataset.t);
    if (typeof value === 'string') node.textContent = value;
  });

  // Подсказки внутри полей формы
  document.querySelectorAll('[data-t-ph]').forEach((node) => {
    const value = t(node.dataset.tPh);
    if (typeof value === 'string') node.placeholder = value;
  });

  document.title = t('meta.title');
  document.querySelector('meta[name="description"]')?.setAttribute('content', t('meta.description'));

  // Списки собираются заново: у них меняется не только текст
  renderRoles();
  renderAbout();
  renderSkills();
  renderProjects();
  renderProcess();
  renderContacts();

  document.querySelectorAll('.lang button').forEach((button) => {
    const active = button.dataset.lang === next;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', String(active));
  });
}

/* ---------------------------------------------------------
   СБОРКА БЛОКОВ
   --------------------------------------------------------- */
function renderRoles() {
  const list = document.getElementById('hero-roles');
  if (list) list.innerHTML = t('hero.roles').map((role) => `<li>${role}</li>`).join('');
}

function renderAbout() {
  const age = getAge();

  const text = document.getElementById('about-text');
  if (text) {
    text.innerHTML = ['p1', 'p2', 'p3']
      .map((key) => `<p>${fill(t(`about.${key}`), { age })}</p>`)
      .join('');
  }

  const facts = document.getElementById('about-facts');
  if (facts) {
    const rows = [
      [t('about.factAge'), fill(t('about.factYears'), { age })],
      [t('about.factCity'), person.hometown || 'Душанбе'],
      [t('about.factBased'), person.basedIn || 'Казахстан'],
      [t('about.factLangs'), t('about.langsValue')],
      [t('about.factFocus'), t('about.focusValue')],
    ];
    facts.innerHTML = rows
      .map(([k, v]) => `<li><span class="facts-k">${k}</span><span class="facts-v">${v}</span></li>`)
      .join('');
  }
}

function renderSkills() {
  const root = document.getElementById('skills-groups');
  if (!root) return;

  root.innerHTML = ['frontend', 'backend', 'tools'].map((group) => {
    const items = skills.filter((skill) => skill.group === group);
    const cards = items.map((skill, index) => `
      <li class="skill reveal" style="--tint:${skill.tint};--delay:${Math.min(index * 45, 400)}ms">
        <span class="skill-dot"></span>
        <span class="skill-name">${skill.name}</span>
      </li>`).join('');

    return `
      <div class="skills-group">
        <h3 class="skills-group-title">${t(`skills.${group}`)}</h3>
        <ul class="skills-grid">${cards}</ul>
      </div>`;
  }).join('');

  observeReveals(root);
}

function renderProjects() {
  const root = document.getElementById('projects-grid');
  if (!root) return;

  root.innerHTML = projects.map((project, index) => {
    const copy = t(`projects.${project.key}`) || { title: project.key, tagline: '', description: '' };
    const tag = project.href ? 'a' : 'div';
    const attrs = project.href
      ? ` href="${project.href}" target="_blank" rel="noopener noreferrer"`
      : '';
    const action = project.href
      ? `${t('projects.view')}${icon('arrowUpRight')}`
      : t('projects.soon');

    return `
      <li class="reveal" style="--delay:${Math.min(index * 60, 320)}ms">
        <div class="tilt" data-accent="${project.accent}">
          <span class="tilt-glow" aria-hidden="true"></span>
          <${tag} class="project-inner"${attrs}>
            <div class="project-visual" style="--accent:${project.accent}">
              <svg viewBox="0 0 96 96" fill="none" stroke="currentColor" stroke-width="1.6"
                   stroke-linecap="round" stroke-linejoin="round" class="glyph" aria-hidden="true">
                ${GLYPHS[project.shape] || GLYPHS.web}
              </svg>
            </div>
            <div class="project-head">
              <span class="project-tagline">${copy.tagline}</span>
              <span class="project-year">${project.year}</span>
            </div>
            <h3 class="project-title">${copy.title}</h3>
            <p class="project-desc">${copy.description}</p>
            <ul class="project-stack">${project.stack.map((s) => `<li>${s}</li>`).join('')}</ul>
            <span class="project-action">${action}</span>
          </${tag}>
        </div>
      </li>`;
  }).join('');

  bindTilt(root);
  observeReveals(root);
}

function renderProcess() {
  const root = document.getElementById('process-list');
  if (!root) return;

  root.innerHTML = t('process.steps').map((step, index) => `
    <li class="reveal" style="--delay:${Math.min(index * 70, 400)}ms">
      <span class="process-num">${String(index + 1).padStart(2, '0')}</span>
      <div class="process-body">
        <h3>${step.title}</h3>
        <p>${step.text}</p>
      </div>
    </li>`).join('');

  observeReveals(root);
}

function renderContacts() {
  const root = document.getElementById('contacts-list');
  if (!root) return;

  root.innerHTML = contacts.map((contact, index) => {
    const external = contact.href.startsWith('http');
    return `
      <li class="contact u-glass reveal" style="--delay:${Math.min(index * 50, 300)}ms">
        <a class="contact-main" href="${contact.href}"
           ${external ? 'target="_blank" rel="noopener noreferrer"' : ''}>
          <span class="contact-icon">${icon(contact.icon)}</span>
          <span class="contact-text">
            <span class="contact-label">${contact.label}</span>
            <span class="contact-value">${contact.display}</span>
          </span>
        </a>
        <button type="button" class="contact-copy" data-copy="${contact.display}"
                aria-label="${t('contact.copy')}: ${contact.display}">
          ${icon('copy')}<span>${t('contact.copy')}</span>
        </button>
      </li>`;
  }).join('');

  root.querySelectorAll('.contact-copy').forEach((button) => {
    button.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(button.dataset.copy);
        button.innerHTML = `${icon('check')}<span>${t('contact.copied')}</span>`;
        setTimeout(() => {
          button.innerHTML = `${icon('copy')}<span>${t('contact.copy')}</span>`;
        }, 2000);
      } catch {
        // Буфер недоступен (нет https) — ссылка рядом всё равно рабочая
      }
    });
  });

  observeReveals(root);
}

function renderHeroSocials() {
  const root = document.getElementById('hero-socials');
  if (!root) return;
  root.innerHTML = contacts.filter((c) => c.primary).map((contact) => `
    <li>
      <a class="social" href="${contact.href}" target="_blank" rel="noopener noreferrer">
        ${icon(contact.icon)}<span>${contact.label}</span>
      </a>
    </li>`).join('');
}

/* ---------------------------------------------------------
   ПОЯВЛЕНИЕ БЛОКОВ ПРИ ПРОКРУТКЕ
   --------------------------------------------------------- */
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add('is-visible');
      revealObserver.unobserve(entry.target);   // одного раза достаточно
    }
  });
}, { threshold: 0.15, rootMargin: '-40px' });

function observeReveals(root = document) {
  root.querySelectorAll('.reveal:not(.is-visible)').forEach((node) => revealObserver.observe(node));
}

/* ---------------------------------------------------------
   НАКЛОН КАРТОЧЕК ЗА КУРСОРОМ
   Делается CSS-трансформацией: отдельная 3D-сцена на каждую
   карточку означала бы шесть контекстов WebGL и просевшие кадры.
   --------------------------------------------------------- */
function bindTilt(root) {
  if (reducedMotion) return;
  const MAX = 9;   // градусов; больше — карточка выглядит кривой

  root.querySelectorAll('.tilt').forEach((card) => {
    const glow = card.querySelector('.tilt-glow');

    card.addEventListener('pointermove', (event) => {
      const rect = card.getBoundingClientRect();
      const px = (event.clientX - rect.left) / rect.width - 0.5;
      const py = (event.clientY - rect.top) / rect.height - 0.5;

      card.style.transform = `perspective(1000px) rotateX(${-py * MAX}deg) rotateY(${px * MAX}deg)`;
      if (glow) {
        glow.style.left = `${(px + 0.5) * 100}%`;
        glow.style.top = `${(py + 0.5) * 100}%`;
        glow.style.background =
          `radial-gradient(circle, ${card.dataset.accent}55 0%, transparent 68%)`;
      }
    });

    card.addEventListener('pointerleave', () => {
      card.style.transform = '';
    });
  });
}

/* ---------------------------------------------------------
   МЕНЮ
   --------------------------------------------------------- */
function initNav() {
  const nav = document.querySelector('.nav');
  const burger = document.getElementById('burger');
  const links = document.getElementById('nav-links');

  window.addEventListener('scroll', () => {
    nav.classList.toggle('is-scrolled', window.scrollY > 40);
  }, { passive: true });

  burger.innerHTML = icon('menu');
  burger.addEventListener('click', () => {
    const open = links.classList.toggle('is-open');
    burger.innerHTML = icon(open ? 'close' : 'menu');
    burger.setAttribute('aria-expanded', String(open));
    // Пока открыто меню, фон скроллиться не должен
    document.body.style.overflow = open ? 'hidden' : '';
  });

  links.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      links.classList.remove('is-open');
      burger.innerHTML = icon('menu');
      burger.setAttribute('aria-expanded', 'false');
      document.body.style.overflow = '';
    });
  });

  const langBox = document.getElementById('lang');
  langBox.innerHTML = LANGS.map((code) =>
    `<button type="button" data-lang="${code}">${LANG_LABELS[code]}</button>`).join('');
  langBox.querySelectorAll('button').forEach((button) => {
    button.addEventListener('click', () => applyLang(button.dataset.lang));
  });
}

/* ---------------------------------------------------------
   ФОРМА ЗАЯВКИ
   --------------------------------------------------------- */
function initOrderForm() {
  const form = document.getElementById('order-form');
  if (!form) return;

  const status = document.getElementById('order-status');

  const rules = {
    name: (value) => (value.trim().length >= 2 ? '' : t('order.errors.nameShort')),
    telegram: (value) => (value.trim().length >= 2 ? '' : t('order.errors.telegramShort')),
    project: (value) => (value.trim().length >= 10 ? '' : t('order.errors.projectShort')),
  };

  function validateField(field) {
    const rule = rules[field.name];
    if (!rule) return true;

    const message = rule(field.value);
    const wrap = field.closest('.field');
    const errorNode = wrap.querySelector('.field-error');

    wrap.classList.toggle('has-error', !!message);
    field.setAttribute('aria-invalid', String(!!message));
    errorNode.textContent = message;
    return !message;
  }

  // Проверяем на blur, а не на каждую букву: иначе ошибка появляется,
  // когда человек ещё не дописал
  form.querySelectorAll('input, textarea').forEach((field) => {
    field.addEventListener('blur', () => validateField(field));
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const fields = [...form.querySelectorAll('input, textarea')];
    const valid = fields.map(validateField).every(Boolean);
    if (!valid) {
      // Ставим фокус на первое поле с ошибкой
      form.querySelector('.field.has-error input, .field.has-error textarea')?.focus();
      return;
    }

    const data = Object.fromEntries(new FormData(form).entries());
    const message = [
      'Заявка с сайта',
      `Имя: ${data.name}`,
      `Telegram: ${data.telegram}`,
      `Проект: ${data.project}`,
      data.budget ? `Бюджет: ${data.budget}` : null,
      data.deadline ? `Срок: ${data.deadline}` : null,
    ].filter(Boolean).join('\n');

    if (orderTarget.mode === 'php') {
      try {
        await fetch(orderTarget.phpEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        });
      } catch {
        // Сеть отвалилась — ниже всё равно откроем Telegram
      }
    }

    // Telegram не умеет подставлять текст в личный чат по ссылке,
    // поэтому кладём заявку в буфер: останется вставить одним движением
    try { await navigator.clipboard.writeText(message); } catch { /* нет буфера */ }

    status.textContent = t('order.success');
    window.open(`https://t.me/${orderTarget.telegramUser}`, '_blank', 'noopener');
    setTimeout(() => { status.textContent = ''; }, 5000);
  });
}

/* ---------------------------------------------------------
   ЗВУК
   Автозапуск браузеры запрещают — только по кнопке
   --------------------------------------------------------- */
function initSound() {
  const button = document.getElementById('sound');
  if (!button) return;

  if (!audio.src) { button.remove(); return; }

  const player = new Audio(audio.src);
  player.loop = true;
  player.volume = audio.volume;

  let playing = false;
  const paint = () => {
    button.innerHTML = icon(playing ? 'sound' : 'mute');
    button.setAttribute('aria-label', playing ? t('sound.off') : t('sound.on'));
  };
  paint();

  button.addEventListener('click', () => {
    if (playing) { player.pause(); playing = false; }
    else { player.play().then(() => { playing = true; paint(); }).catch(() => {}); }
    paint();
  });
}

/* ---------------------------------------------------------
   ПЛАВНЫЙ СКРОЛЛ
   --------------------------------------------------------- */
function initSmoothScroll() {
  if (reducedMotion) return;

  const lenis = new Lenis({ lerp: 0.09, wheelMultiplier: 1, touchMultiplier: 1.6, smoothWheel: true });
  const raf = (time) => { lenis.raf(time); requestAnimationFrame(raf); };
  requestAnimationFrame(raf);

  // Якорные ссылки должны ехать через Lenis, иначе прыгают рывком
  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener('click', (event) => {
      const target = document.querySelector(link.getAttribute('href'));
      if (!target) return;
      event.preventDefault();
      lenis.scrollTo(target, { offset: -72 });
    });
  });
}

/* ---------------------------------------------------------
   СТАРТ
   --------------------------------------------------------- */
export function initApp() {
  document.getElementById('year').textContent = String(new Date().getFullYear());
  document.getElementById('footer-name').textContent = person.fullName;

  initNav();
  renderHeroSocials();
  initOrderForm();
  initSound();
  initSmoothScroll();

  // Язык определяем после отрисовки: index.html уже написан по-русски,
  // поэтому первый кадр показывается без задержки
  applyLang(detectLang());

  observeReveals(document);
  document.body.classList.add('is-ready');
}
