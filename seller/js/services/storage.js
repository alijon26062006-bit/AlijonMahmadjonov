// хранилище (сейчас — браузер; позже заменим на сервер)
export const KEY = 'seller-panel-v2';
export const store = {
  load() { try { const raw = localStorage.getItem(KEY) ?? localStorage.getItem('seller-panel-v1'); return raw ? JSON.parse(raw) : null; } catch { return null; } },
  save(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); return true; } catch { return false; } },
  fresh() { try { localStorage.setItem(KEY, '"fresh"'); } catch { /* память браузера недоступна */ } },
};
export const AKEY = 'seller-auth-v1';
export const auth = (() => { try { return JSON.parse(localStorage.getItem(AKEY)) || {}; } catch { return {}; } })();
export const saveAuth = () => { try { localStorage.setItem(AKEY, JSON.stringify(auth)); } catch { /* память браузера недоступна — вход живёт до закрытия вкладки */ } };
