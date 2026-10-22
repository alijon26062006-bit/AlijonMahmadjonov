import { COURIER_MIN, DELIVERY_FEE, FREE_FROM, KINDS } from '../config.js';
import { today } from '../lib/format.js';
import { readSeller } from '../services/bridge.js';
import { DEMO_SHOPS } from './demo.js';

// Каталог: магазины-примеры и магазин из кабинета продавца на этом устройстве
const FRESH = ['Овощи и зелень', 'Фрукты и ягоды'];

export function shops() {
  const local = localShop();
  return local ? [local, ...DEMO_SHOPS] : DEMO_SHOPS;
}
export const shopById = id => shops().find(s => s.id === id);
export const productIn = (shop, pid) => shop?.products.find(p => p.id === pid);
export const kindName = id => KINDS.find(k => k.id === id)?.name || '';

function localShop() {
  const S = readSeller(); if (!S) return null;
  const sh = S.shop, kind = ['grocery', 'perfume', 'food'].includes(sh.kind) ? sh.kind : 'grocery';
  const likes = {};
  for (const r of S.reviews || []) for (const i of r.items || []) if (i.like != null) { const x = likes[i.pid] ||= { up: 0, all: 0 }; x.all++; if (i.like) x.up++; }
  const products = (S.products || []).filter(p => onSale(p, kind)).map(p => ({
    id: p.id, cat: p.cat, name: p.name, price: p.price, oldPrice: p.oldPrice, unit: p.unit, minStep: p.minStep || 1, stock: p.stock,
    imgs: p.imgs || [], desc: p.desc || '', attrs: p.attrs || {}, variants: p.variants || [], options: p.options || [], labels: p.labels || [], expiry: p.expiry || '',
    likes: likes[p.id]?.all >= 3 ? Math.round(likes[p.id].up / likes[p.id].all * 100) : null,
  }));
  const R = rating(S.reviews || []);
  return {
    id: 'local', local: true, name: sh.name, kind, about: sh.about || '', logo: sh.logo || '', rating: R.value, count: R.count, isNew: R.count < 10,
    prep: sh.prep || 30, minOrder: sh.minOrder || 0, address: sh.address || '', schedule: sh.schedule || [], paused: !!sh.paused, delivery: sh.delivery !== false,
    phone: sh.phone || '', color: '#fff6c2', cats: (S.cats || []).filter(c => products.some(p => p.cat === c)).concat([...new Set(products.map(p => p.cat))].filter(c => !(S.cats || []).includes(c))), products,
  };
}
// те же правила, что в кабинете: товар на стопе, без остатка или с истёкшим сроком покупатель не видит
function onSale(p, kind) {
  if (!p.active || p.stock <= 0 || (p.stopUntil && p.stopUntil > Date.now())) return false;
  if (p.expiry) return p.expiry >= today();
  return !(kind === 'grocery' && !FRESH.includes(p.cat));
}
function rating(reviews) {
  const now = Date.now(), recent = reviews.filter(r => now - r.ts < 90 * 864e5);
  let sum = 0, w = 0;
  for (const r of recent) { const k = now - r.ts < 30 * 864e5 ? 2 : 1; sum += r.rating * k; w += k; }
  return { value: w ? Math.round(sum / w * 10) / 10 : 0, count: recent.length };
}

const mins = t => { const [h, m] = t.split(':').map(Number); return h * 60 + m; };
/** Открыт ли магазин сейчас и что написать покупателю. */
export function openState(shop, at = new Date()) {
  if (shop.paused) return { open: false, text: 'Временно не принимает заказы' };
  const day = (at.getDay() + 6) % 7, now = at.getHours() * 60 + at.getMinutes();
  const d = shop.schedule[day], prev = shop.schedule[(day + 6) % 7];
  // ночная смена вчерашнего дня (например 11:00–02:00)
  if (prev?.open && mins(prev.to) < mins(prev.from) && now < mins(prev.to)) return { open: true, text: `Открыто до ${prev.to}` };
  if (d?.open) {
    const f = mins(d.from), t = mins(d.to) < f ? mins(d.to) + 1440 : mins(d.to);
    if (t - f >= 1439) return { open: true, text: 'Круглосуточно' };
    if (now >= f && now < t) return { open: true, text: `Открыто до ${d.to}` };
    if (now < f) return { open: false, text: `Откроется в ${d.from}` };
  }
  for (let i = 1; i <= 7; i++) { const n = shop.schedule[(day + i) % 7]; if (n?.open) return { open: false, text: i === 1 ? `Откроется завтра в ${n.from}` : 'Сегодня не работает' }; }
  return { open: false, text: 'Закрыто' };
}
export const eta = shop => `${shop.prep + COURIER_MIN}–${shop.prep + COURIER_MIN + 10} мин`;
export const deliveryFee = sum => sum >= FREE_FROM ? 0 : DELIVERY_FEE;
export const ratingText = s => s.isNew || !s.count ? 'Новый' : s.rating.toLocaleString('ru-RU', { minimumFractionDigits: 1 });
