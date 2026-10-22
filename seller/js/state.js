import { migrate } from './demo.js';
import { addDays, today } from './lib/format.js';
import { auth, store } from './services/storage.js';
import { toast } from './ui/dom.js';

export let S = migrate(store.load());
if (S === 'fresh') S = null;

/** Заменяет всё состояние магазина (пример, новый магазин, выход). */
export function setS(next) { S = next; }
if (S && S.shop && !S.shop.alif) S.shop.alif = { terminal: '', status: 'none', holder: S.shop.payout?.holder || '', tin: S.shop.tin || '' };

// вход: соглашение → три шага → номер телефона → SMS-код (сейчас тестовый режим, SMS не отправляется)
export const flow = { step: auth.agreed ? (auth.onboarded ? 'phone' : 'intro') : 'terms', slide: 0, phone: '', code: '', sent: 0, err: '' };
export const save = () => { if (S && !store.save(S)) toast('Не удалось сохранить: хранилище браузера переполнено или недоступно. Уменьшите число фото.'); };
export const ui = { q: '', oq: '', psort: 'sales', cat: 'Все', stock: 'all', ordTab: 'new', period: '30', from: addDays(today(), -13), to: today(), pickDay: null, expMonth: today().slice(0, 7) };
export const newCount = () => S.orders.filter(o => o.status === 'new').length;
