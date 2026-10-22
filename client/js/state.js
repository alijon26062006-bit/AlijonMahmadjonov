import { uid } from './lib/format.js';

// Всё, что покупатель хранит у себя: адрес, корзина, заказы, избранное
const KEY = 'zud-client-v1';
const fresh = () => ({ onboarded: false, user: null, addr: null, addresses: [], cart: { shopId: null, items: [], ifMissing: 'replace', comment: '', cutlery: false }, orders: [], favShops: [], favProducts: [], recent: [], theme: 'auto', nextNo: 5001, device: uid() });
export const C = (() => { try { return { ...fresh(), ...JSON.parse(localStorage.getItem(KEY)) }; } catch { return fresh(); } })();
export const save = () => { try { localStorage.setItem(KEY, JSON.stringify(C)); } catch { /* память браузера заполнена */ } };
export const ui = { q: '', kind: null, filter: 'all', shopCat: null };
