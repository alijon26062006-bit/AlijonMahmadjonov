import { RATING_DAYS, RATING_MIN } from '../config.js';
import { S } from '../state.js';

// Рейтинг магазина: оценки за последние 3 месяца, свежий месяц весит вдвое больше
export function rating() {
  const now = Date.now(), recent = S.reviews.filter(r => now - r.ts < RATING_DAYS * 864e5);
  let sum = 0, w = 0;
  for (const r of recent) { const k = now - r.ts < 30 * 864e5 ? 2 : 1; sum += r.rating * k; w += k; }
  return { value: w ? Math.round(sum / w * 10) / 10 : 0, count: recent.length, isNew: recent.length < RATING_MIN };
}
export const isBad = r => r.rating <= 3;
export const needsReply = r => isBad(r) && !r.reply;
export const unansweredBad = () => S.reviews.filter(needsReply).length;

export function tagStats(list) {
  const m = {};
  for (const r of list) for (const t of r.tags || []) m[t] = (m[t] || 0) + 1;
  return Object.entries(m).sort((a, b) => b[1] - a[1]);
}
// лайки товаров из отзывов: { pid: { up, down } }
export function productLikes() {
  const m = {};
  for (const r of S.reviews) for (const i of r.items || []) if (i.like != null) { const x = m[i.pid] || (m[i.pid] = { up: 0, down: 0 }); i.like ? x.up++ : x.down++; }
  return m;
}
export const stars = n => '★★★★★'.slice(0, Math.round(n)) + '☆☆☆☆☆'.slice(0, 5 - Math.round(n));
