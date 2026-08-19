/* ===========================================================
   Работа с GitHub. Всё, что касается токена и коммитов, — здесь.

   Токен хранится в браузере (localStorage). Поэтому он должен быть
   fine-grained и выдан ТОЛЬКО на этот репозиторий с правом
   Contents: read and write. Тогда в худшем случае злоумышленник
   меняет один сайт, а не трогает аккаунт.
   =========================================================== */

const GH = (() => {
  const API = 'https://api.github.com';
  const TOKEN_KEY = 'alijon.gh.token';
  const CFG_KEY = 'alijon.gh.cfg';

  const DEFAULTS = {
    owner: 'alijon26062006-bit',
    repo: 'alijonmahmadjonov',
    branch: 'main'
  };

  /* --- хранилище ---------------------------------------------- */

  function cfg() {
    try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(CFG_KEY) || '{}') }; }
    catch (_) { return { ...DEFAULTS }; }
  }
  function saveCfg(next) {
    try { localStorage.setItem(CFG_KEY, JSON.stringify({ ...cfg(), ...next })); } catch (_) {}
  }
  function token() {
    try { return localStorage.getItem(TOKEN_KEY) || ''; } catch (_) { return ''; }
  }
  function saveToken(value) {
    try { localStorage.setItem(TOKEN_KEY, String(value).trim()); } catch (_) {}
  }
  function clearToken() {
    try { localStorage.removeItem(TOKEN_KEY); } catch (_) {}
  }

  /* --- base64 с поддержкой кириллицы --------------------------- */

  function encode(text) {
    const bytes = new TextEncoder().encode(text);
    let bin = '';
    for (const byte of bytes) bin += String.fromCharCode(byte);
    return btoa(bin);
  }
  function decode(base64) {
    const bin = atob(String(base64).replace(/\s/g, ''));
    return new TextDecoder().decode(Uint8Array.from(bin, ch => ch.charCodeAt(0)));
  }

  /* --- запросы -------------------------------------------------- */

  /** Ошибка GitHub, переведённая на человеческий язык. */
  class GHError extends Error {
    constructor(status, path) {
      super(GHError.explain(status, path));
      this.status = status;
      this.path = path;
    }
    static explain(status, path) {
      switch (status) {
        case 401: return 'Токен не подошёл. Проверь, что скопировал его целиком и что срок ещё не истёк.';
        case 403: return 'GitHub отказал. Скорее всего у токена нет права Contents: read and write на этот репозиторий.';
        case 404: return `Не найдено: ${path}. Проверь владельца, название репозитория и ветку в Настройках.`;
        case 409:
        case 422: return 'Файл на GitHub успел измениться. Нажми «Обновить» и попробуй ещё раз — так правки не затрут друг друга.';
        case 429: return 'Слишком много запросов подряд. Подожди минуту.';
        default:  return `GitHub ответил ошибкой ${status}.`;
      }
    }
  }

  async function api(path, options = {}) {
    if (!token()) throw new GHError(401, path);
    const res = await fetch(API + path, {
      ...options,
      headers: {
        Accept: 'application/vnd.github+json',
        Authorization: 'Bearer ' + token(),
        'X-GitHub-Api-Version': '2022-11-28',
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers || {})
      }
    });
    if (!res.ok) throw new GHError(res.status, path);
    return res.status === 204 ? null : res.json();
  }

  const base = () => `/repos/${cfg().owner}/${cfg().repo}`;

  /* --- операции ------------------------------------------------- */

  /** Проверяет токен и права. Возвращает {name, canWrite}. */
  async function verify() {
    const repo = await api(base());
    return {
      name: repo.full_name,
      branch: cfg().branch,
      canWrite: Boolean(repo.permissions && repo.permissions.push)
    };
  }

  /** Читает файл. Возвращает {text, sha} либо null, если файла нет. */
  async function getFile(path) {
    try {
      const data = await api(`${base()}/contents/${encodeURIComponent(path).replace(/%2F/g, '/')}?ref=${cfg().branch}`);
      return { text: decode(data.content), sha: data.sha };
    } catch (err) {
      if (err.status === 404) return null;
      throw err;
    }
  }

  /** Пишет файл. sha обязателен, если файл уже существует. Возвращает новый sha. */
  async function putFile(path, text, sha, message) {
    const body = {
      message,
      content: encode(text),
      branch: cfg().branch,
      ...(sha ? { sha } : {})
    };
    const res = await api(`${base()}/contents/${encodeURIComponent(path).replace(/%2F/g, '/')}`, {
      method: 'PUT',
      body: JSON.stringify(body)
    });
    return res.content.sha;
  }

  /** Пишет уже закодированный в base64 файл — для картинок. */
  async function putBinary(path, base64, sha, message) {
    const body = { message, content: base64, branch: cfg().branch, ...(sha ? { sha } : {}) };
    const res = await api(`${base()}/contents/${encodeURIComponent(path).replace(/%2F/g, '/')}`, {
      method: 'PUT',
      body: JSON.stringify(body)
    });
    return res.content.sha;
  }

  /** Список файлов в папке. */
  async function listDir(path) {
    try {
      const items = await api(`${base()}/contents/${path}?ref=${cfg().branch}`);
      return Array.isArray(items) ? items : [];
    } catch (err) {
      if (err.status === 404) return [];
      throw err;
    }
  }

  /** Адрес живого сайта на GitHub Pages. */
  function siteUrl() {
    const { owner, repo } = cfg();
    return `https://${owner}.github.io/${repo}/`;
  }

  return {
    cfg, saveCfg, token, saveToken, clearToken,
    verify, getFile, putFile, putBinary, listDir, siteUrl,
    encode, decode, GHError
  };
})();
