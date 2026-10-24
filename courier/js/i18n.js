import { TG } from './i18n/tg.js';

// Язык интерфейса. Основной — таджикский, в профиле можно включить русский.
// Экраны пишутся по-русски, а этот модуль переводит готовый текст на лету:
// при каждом изменении страницы переводятся только новые куски, это быстро и не держит лишнего в памяти.
// Названия магазинов, адреса и имена помечены translate="no" и не трогаются.

const KEY = 'zud-lang';
export let lang = (() => { try { return localStorage.getItem(KEY) || 'tg'; } catch { return 'tg'; } })();
export const LANGS = [['tg', 'Тоҷикӣ'], ['ru', 'Русский']];

const CYR = /[А-Яа-яЁё]/;
const B = '(^|[^А-Яа-яЁёӢӣҒғҚқҲҳҶҷӮӯ])';
const PHRASES = Object.keys(TG.dict).filter(k => /\s/.test(k)).sort((a, b) => b.length - a.length);
const WORDS = Object.entries(TG.words).map(([ru, tg]) => [new RegExp(B + ru + '(?=$|[^А-Яа-яЁёӢӣҒғҚқҲҳҶҷӮӯ])', 'g'), '$1' + tg]);

/** Перевод одной строки. На русском возвращает как есть. */
export function tr(s) {
  if (lang !== 'tg' || !s || !CYR.test(s)) return s;
  const lead = s.match(/^[\s·•→]*/)[0], trail = s.match(/\s*$/)[0], core = s.slice(lead.length, s.length - trail.length);
  const tail = core.match(/(\s\*|[.!?:…])+$/)?.[0] || '', body = tail ? core.slice(0, -tail.length) : core;
  let out = TG.dict[core] ?? (TG.dict[body] != null ? TG.dict[body] + tail : null);
  if (out == null) { const m = core.match(/^(.+?)(\s*\(\d+\)|\s+\d+)$/); if (m && TG.dict[m[1]] != null) out = TG.dict[m[1]] + m[2]; }
  if (out == null) {
    out = core;
    for (const [re, rep] of TG.patterns) out = out.replace(re, rep);
    for (const p of PHRASES) if (out.includes(p)) out = out.split(p).join(TG.dict[p]);
    for (const [re, rep] of WORDS) out = out.replace(re, rep);
  }
  return lead + out + trail;
}

const SKIP = 'script,style,textarea,[translate="no"]';
const ATTRS = ['placeholder', 'aria-label', 'title', 'alt'];
const done = new WeakMap();   // какой текст мы сами поставили — чтобы не переводить по кругу

function fixText(n) {
  if (done.get(n) === n.nodeValue) return;
  if (n.parentElement?.closest(SKIP)) return;
  const v = tr(n.nodeValue);
  if (v !== n.nodeValue) n.nodeValue = v;
  done.set(n, n.nodeValue);
}
function fixAttrs(el) {
  if (el.closest('[translate="no"]')) return; for (const a of ATTRS) { const v = el.getAttribute(a); if (v && CYR.test(v)) { const t = tr(v); if (t !== v) el.setAttribute(a, t); } } }

export function translate(root) {
  if (lang !== 'tg' || !root) return;
  if (root.nodeType === 3) return fixText(root);
  if (root.nodeType !== 1) return;
  if (root.closest(SKIP)) { if (root.matches('textarea')) fixAttrs(root); return; }
  const tw = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode: n => n.nodeType === 1 ? (n.matches(SKIP) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_SKIP) : NodeFilter.FILTER_ACCEPT,
  });
  fixAttrs(root);
  for (let n = tw.nextNode(); n; n = tw.nextNode()) fixText(n);
  root.querySelectorAll('[placeholder],[aria-label],[title],[alt]').forEach(fixAttrs);
}

const mo = new MutationObserver(list => {
  for (const m of list) {
    if (m.type === 'characterData') fixText(m.target);
    else m.addedNodes.forEach(translate);
  }
});
export function startTranslating() {
  document.documentElement.lang = lang === 'tg' ? 'tg' : 'ru';
  translate(document.body);
  mo.observe(document.body, { childList: true, subtree: true, characterData: true });
}
export function setLang(l) { lang = l; try { localStorage.setItem(KEY, l); } catch { /* память браузера недоступна */ } document.documentElement.lang = l === 'tg' ? 'tg' : 'ru'; }
