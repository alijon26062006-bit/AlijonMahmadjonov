import { esc } from './lib/format.js';

// Общие куски интерфейса: иконки, подсказки, окно с вопросом, пустой список, загрузка.

const svg = d => `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
export const ICON = {
  home: svg('<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>'),
  alert: svg('<path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h.01"/>'),
  orders: svg('<path d="M6 3h12l1 18H5z"/><path d="M9 7a3 3 0 0 0 6 0"/>'),
  people: svg('<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14.5a5 5 0 0 1 5.5 5.5"/>'),
  shop: svg('<path d="M4 10v10h16V10M3 10l2-6h14l2 6M9 20v-6h6v6"/>'),
  box: svg('<path d="M3 7l9-4 9 4v10l-9 4-9-4z"/><path d="M3 7l9 4 9-4M12 11v10"/>'),
  car: svg('<path d="M5 16l1.5-6h11L19 16"/><rect x="3" y="16" width="18" height="4" rx="1"/><circle cx="7.5" cy="20" r="1"/><circle cx="16.5" cy="20" r="1"/>'),
  map: svg('<path d="M9 4l6 2 6-2v16l-6 2-6-2-6 2V6z"/><path d="M9 4v16M15 6v16"/>'),
  star: svg('<path d="M12 3l2.8 5.8 6.2.9-4.5 4.4 1 6.3L12 17.5 6.5 20.4l1-6.3L3 9.7l6.2-.9z"/>'),
  log: svg('<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>'),
  roles: svg('<circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><circle cx="12" cy="18" r="3"/><path d="M8.5 7.5l2 8M15.5 7.5l-2 8M9 6h6"/>'),
  more: svg('<circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>'),
  search: svg('<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>'),
  back: svg('<path d="M15 5l-7 7 7 7"/>'),
  phone: svg('<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>'),
  refresh: svg('<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>'),
  out: svg('<path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 17l5-5-5-5M15 12H3"/>'),
  chevron: svg('<path d="M9 5l7 7-7 7"/>'),
  lock: svg('<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>'),
};

// ---------- подсказка внизу ----------
let toastTimer = 0;
export function toast(text, tone = '') {
  let el = document.getElementById('toast');
  if (!el) { el = document.createElement('div'); el.id = 'toast'; el.setAttribute('role', 'status'); el.setAttribute('aria-live', 'polite'); document.body.append(el); }
  el.className = `toast show ${tone}`; el.textContent = text;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.className = 'toast'; }, 4000);
}

// ---------- окно с вопросом ----------
/**
 * Спросить подтверждение (и, если нужно, причину). Возвращает текст причины ('' без поля) или null, если нажали «Отмена».
 * @param {{ title: string, text?: string, ok: string, danger?: boolean, field?: string, required?: boolean, value?: string }} o
 */
export function ask({ title, text = '', ok, danger = false, field = '', required = false, value = '' }) {
  return new Promise(done => {
    const wrap = document.createElement('div');
    wrap.className = 'modal-wrap';
    wrap.innerHTML = `<form class="modal" role="dialog" aria-modal="true" aria-labelledby="m-title" novalidate>
      <h2 id="m-title">${esc(title)}</h2>
      ${text ? `<p class="muted">${esc(text)}</p>` : ''}
      ${field ? `<label class="field"><span>${esc(field)}${required ? ' *' : ''}</span><textarea name="v" rows="3" maxlength="300">${esc(value)}</textarea><small class="err" hidden>Заполните поле — без этого нельзя</small></label>` : ''}
      <div class="modal-actions"><button type="button" class="btn" data-m="no">Отмена</button><button type="submit" class="btn ${danger ? 'danger' : 'primary'}">${esc(ok)}</button></div></form>`;
    const close = v => { wrap.remove(); removeEventListener('keydown', onKey); done(v); };
    const onKey = e => { if (e.key === 'Escape') close(null); };
    addEventListener('keydown', onKey);
    wrap.addEventListener('click', e => { if (e.target === wrap || /** @type {HTMLElement} */ (e.target).closest('[data-m="no"]')) close(null); });
    wrap.querySelector('form').addEventListener('submit', e => {
      e.preventDefault();
      const ta = wrap.querySelector('textarea'), v = ta ? ta.value.trim() : '';
      if (ta && required && !v) { wrap.querySelector('.err').hidden = false; ta.focus(); return; }
      close(v);
    });
    document.body.append(wrap);
    /** @type {HTMLElement} */ (wrap.querySelector('textarea') || wrap.querySelector('[type="submit"]')).focus();
  });
}

// ---------- куски экранов ----------
export const loading = () => '<div class="loading" role="status"><span class="spin"></span>Загрузка…</div>';
export const empty = (title, text = '') => `<div class="empty"><b>${esc(title)}</b>${text ? `<span>${esc(text)}</span>` : ''}</div>`;
export const errorBox = msg => `<div class="alert bad" role="alert"><div><b>Не загрузилось</b><br>${esc(msg)}</div><button class="btn sm" data-act="reload">${ICON.refresh} Ещё раз</button></div>`;
/** Плитка с цифрой. */
export const stat = (label, value, sub = '', href = '') => `<${href ? `a href="${href}"` : 'div'} class="stat"><span class="stat-l">${esc(label)}</span><b class="stat-v num">${value}</b>${sub ? `<span class="stat-s">${sub}</span>` : ''}</${href ? 'a' : 'div'}>`;
/** Строка «название — значение». */
export const kv = (k, v) => `<div class="kv"><span>${esc(k)}</span><b>${v}</b></div>`;
/** Заголовок экрана. */
export const head = (title, sub = '', right = '', back = '') => `<header class="page-head">
  ${back ? `<a class="icon-btn" href="${back}" aria-label="Назад">${ICON.back}</a>` : ''}
  <div class="page-t"><h1>${title}</h1>${sub ? `<p class="muted">${sub}</p>` : ''}</div>${right ? `<div class="page-r">${right}</div>` : ''}</header>`;
/** Поиск и фильтры: форма меняет адрес (#/…?q=…), поэтому кнопка «Назад» и ссылка работают. */
export const searchBar = (q, placeholder, filters = '') => `<form class="searchbar" data-search>
  <label class="search">${ICON.search}<input type="search" name="q" value="${esc(q)}" placeholder="${esc(placeholder)}" aria-label="${esc(placeholder)}"></label>${filters}</form>`;
/** Набор кнопок-фильтров: [значение, подпись, сколько]. */
export const tabs = (name, cur, list) => `<div class="tabs" role="tablist">${list.map(([v, l, n]) =>
  `<button type="button" class="tab" role="tab" aria-selected="${v === cur}" data-filter="${name}" data-value="${esc(v)}">${esc(l)}${n != null ? ` <span class="num">${n}</span>` : ''}</button>`).join('')}</div>`;
export const section = (title, body, right = '') => `<section class="card"><div class="card-h"><h2>${title}</h2>${right}</div>${body}</section>`;
