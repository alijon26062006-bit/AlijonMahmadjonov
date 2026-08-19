/* ===========================================================
   Язык сайта. Ключи в данных — tj и ru.
   В атрибут <html lang> уходит стандартный код: tg / ru.
   =========================================================== */

const LANGS = ['tj', 'ru'];
const HTML_LANG = { tj: 'tg', ru: 'ru' };
const LANG_KEY = 'alijon.lang';

/** Язык, выбранный раньше; иначе — из profile.meta.defaultLang. */
function readLang(fallback = 'tj') {
  try {
    const saved = localStorage.getItem(LANG_KEY);
    if (LANGS.includes(saved)) return saved;
  } catch (_) { /* приватный режим — просто берём язык по умолчанию */ }
  return LANGS.includes(fallback) ? fallback : 'tj';
}

function saveLang(lang) {
  try { localStorage.setItem(LANG_KEY, lang); } catch (_) {}
}

/**
 * Достаёт строку из значения вида {tj, ru}.
 * Если перевода нет — отдаёт другой язык, чтобы место не пустовало.
 */
function t(value, lang) {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (value[lang]) return value[lang];
  for (const l of LANGS) if (value[l]) return value[l];
  return '';
}

/** Достаёт вложенное значение по пути 'about.title'. */
function pick(obj, path) {
  return path.split('.').reduce((acc, key) => (acc == null ? acc : acc[key]), obj);
}
