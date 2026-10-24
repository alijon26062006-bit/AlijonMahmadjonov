import { dkey, esc, hhmm, money, plural } from '../lib/format.js';
import { kmText } from '../lib/nav.js';
import { rt } from '../state.js';
import { ico } from '../ui/dom.js';

// Доход: сколько заработал за день, неделю, месяц; график по дням; наличные на руках; список поездок.

const PERIODS = [['day', 'Сегодня'], ['week', '7 дней'], ['month', '30 дней']];
const DAYS = { day: 1, week: 7, month: 30 };
const startOf = p => { const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - DAYS[p] + 1); return +d; };
const dayName = k => { const d = new Date(k + 'T00:00:00'); return d.toLocaleDateString('ru-RU', { weekday: 'short' }).replace('.', ''); };

export function vMoney() {
  if (!rt.history) return `<h1>Доход</h1><div class="sk card"></div><div class="sk card"></div>`;
  const from = startOf(rt.period), list = rt.history.filter(j => j.step === 'delivered' && j.delivered >= from).sort((a, b) => b.delivered - a.delivered);
  const earn = list.reduce((s, j) => s + j.earn, 0), cash = list.reduce((s, j) => s + (j.cash_taken || 0), 0), km = list.reduce((s, j) => s + (j.km || 0), 0);
  // график: заработок по дням за 7 дней
  const days = Array.from({ length: 7 }, (_, i) => dkey(Date.now() - (6 - i) * 864e5));
  const byDay = Object.fromEntries(days.map(k => [k, 0]));
  for (const j of rt.history) if (j.step === 'delivered' && byDay[dkey(j.delivered)] != null) byDay[dkey(j.delivered)] += j.earn;
  const top = Math.max(1, ...Object.values(byDay));
  const groups = {};
  for (const j of list) (groups[dkey(j.delivered)] ||= []).push(j);
  return `<h1>Доход</h1>
    <div class="seg" role="tablist">${PERIODS.map(([k, t]) => `<button role="tab" aria-selected="${rt.period === k}" data-a="period" data-v="${k}">${t}</button>`).join('')}</div>
    <section class="earn-hero"><small>Заработано</small><b class="num">${money(earn)}</b>
      <div class="kpis"><span><b class="num">${list.length}</b> ${plural(list.length, 'поездка', 'поездки', 'поездок')}</span><span><b class="num">${kmText(km) || '0 км'}</b> в пути с заказом</span>
        <span><b class="num">${list.length ? money(Math.round(earn / list.length)) : '—'}</b> в среднем за заказ</span></div></section>
    <section class="chart" aria-label="Заработок по дням за неделю">${days.map(k => `<div class="bar-col ${k === dkey(Date.now()) ? 'today' : ''}"><span class="v num">${byDay[k] ? Math.round(byDay[k]) : ''}</span><span class="b" style="height:${Math.round(byDay[k] / top * 100)}%"></span><small>${dayName(k)}</small></div>`).join('')}</section>
    <section class="cash-card">${ico('cash')}<span class="grow"><b>Наличные за период: <span class="num">${money(cash)}</span></b><small>Это деньги покупателей за товары и доставку. Сдайте их в сервис — сумму сверим по этому списку</small></span></section>
    ${list.length ? Object.entries(groups).map(([k, js]) => `<section class="section"><div class="sec-head"><h3>${k === dkey(Date.now()) ? 'Сегодня' : new Date(k + 'T00:00:00').toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}</h3>
        <span class="muted num">${money(js.reduce((s, j) => s + j.earn, 0))}</span></div>
        <div class="list">${js.map(j => `<div class="li"><span class="time num">${hhmm(j.delivered)}</span><span class="grow"><b translate="no">${esc(j.shop.name)}</b><small>№ ${j.no}${j.km ? ` · ${kmText(j.km)}` : ''}${j.cash_taken ? ` · наличные ${money(j.cash_taken)}` : ' · онлайн'}${j.rating ? ` · ${'★'.repeat(j.rating)}` : ''}</small></span><b class="num plus">+${money(j.earn)}</b></div>`).join('')}</div></section>`).join('')
    : `<div class="empty"><p>За этот период доставок нет.</p><button class="btn primary" data-go="#/">К заказам</button></div>`}`;
}

export const moneyActions = { period: el => { rt.period = el.dataset.v; } };
