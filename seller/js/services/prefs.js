// Тема оформления кабинета: как в телефоне, светлая или тёмная. Хранится на этом устройстве.
const KEY = 'seller-theme';
export let theme = (() => { try { return localStorage.getItem(KEY) || 'auto'; } catch { return 'auto'; } })();
export const isDark = () => theme === 'dark' || (theme === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches);
export function applyTheme() { if (theme === 'auto') delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = theme; }
export function setTheme(t) { theme = t; try { localStorage.setItem(KEY, t); } catch { /* память браузера недоступна */ } applyTheme(); }
