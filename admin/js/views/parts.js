import { ACTIONS, esc, money, phone, roleChips, stage, when } from '../lib/format.js';
import { empty, ICON } from '../ui.js';

// Строки списков, которые повторяются на разных экранах: заказ, человек, ссылка на связанную карточку.

/** Человек одной строкой: имя или номер. @param {{ id?: string, name?: string, phone?: string|null, email?: string|null }|null} u */
export const who = u => !u ? '—' : esc(u.name || (u.phone ? phone(u.phone) : u.email || 'без имени'));
/** Ссылка на карточку человека. */
export const personLink = u => u?.id ? `<a class="link" href="#/person/${u.id}">${who(u)}</a>` : '—';

/** Список заказов. */
export function orderList(list, { showShop = true } = {}) {
  if (!list?.length) return empty('Заказов нет');
  return `<div class="list">${list.map(o => {
    const s = stage(o), alert = o.problem && !o.problem.resolved_at;
    return `<a class="item" href="#/order/${encodeURIComponent(o.id)}">
      <span class="item-main"><b class="num">№ ${o.no}</b> <span class="chip ${s.tone}">${s.text}</span>${alert ? ' <span class="chip bad">Проблема</span>' : ''}
        <span class="item-sub">${[showShop ? esc(o.shop?.name) : '', o.source === 'app' ? esc(o.customer?.name || '') : 'Продажа в магазине', o.courier ? `курьер ${esc(o.courier)}` : ''].filter(Boolean).join(' · ')}</span></span>
      <span class="item-end"><b class="num">${money(o.total)}</b><span class="item-sub">${when(o.created_at)}</span></span>${ICON.chevron}</a>`;
  }).join('')}</div>`;
}

/** Список людей. */
export function peopleList(list) {
  if (!list?.length) return empty('Никого не нашли', 'Попробуйте другой номер или уберите фильтр');
  return `<div class="list">${list.map(u => `<a class="item" href="#/person/${u.id}">
      <span class="avatar" aria-hidden="true">${esc((u.name || u.email || '#').charAt(0).toUpperCase())}</span>
      <span class="item-main"><b>${who(u)}</b>${u.blocked ? ' <span class="chip bad">Заблокирован</span>' : ''}
        <span class="item-sub"><span class="nowrap">${u.phone ? phone(u.phone) : esc(u.email || '')}</span>${u.shop ? ` · магазин «${esc(u.shop.name)}»` : ''}</span>
        <span class="item-sub">вход ${when(u.last_at)} · с ${when(u.created_at)}</span>
        <span class="chips">${roleChips(u.roles)}</span></span>${ICON.chevron}</a>`).join('')}</div>`;
}

/** Журнал по одной карточке. */
export function logList(list) {
  if (!list?.length) return '<p class="muted small">Админы здесь ничего не меняли</p>';
  return `<ul class="timeline">${list.map(l => `<li><span class="t-at">${when(l.at)}</span><span><b>${esc(ACTIONS[l.action] || l.action)}</b>${l.note ? ` — ${esc(l.note)}` : ''}<span class="item-sub">${esc(l.by || '')}</span></span></li>`).join('')}</ul>`;
}
