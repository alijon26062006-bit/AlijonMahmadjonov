import { render } from '../app.js';
import { CUR, EXP_CATS } from '../config.js';
import { ddmm, esc, money, num, today, uid } from '../lib/format.js';
import { S, save, ui } from '../state.js';
import { $, closeSheet, ICON, openSheet, plusI, showErrors, toast } from '../ui/dom.js';

// Расходы
export function vExpenses() {
  const m = ui.expMonth;
  const list = S.expenses.filter(e => e.date.startsWith(m)).sort((x, y) => y.date.localeCompare(x.date));
  const total = list.reduce((s, e) => s + e.amount, 0);
  const by = {}; list.forEach(e => { by[e.cat] = (by[e.cat] || 0) + e.amount; });
  const cats = Object.entries(by).sort((x, y) => y[1] - x[1]), mx = Math.max(1, ...cats.map(c => c[1]));
  const months = [...new Set([today().slice(0, 7), ...S.expenses.map(e => e.date.slice(0, 7))])].sort().reverse();
  const mName = k => { const [y, mm] = k.split('-').map(Number); return new Date(y, mm - 1, 1).toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' }); };
  return `
    <div class="head"><div><div class="eyebrow">${esc(S.shop.name)}</div><h1>Расходы</h1></div><button class="btn primary" data-act="addexp">${plusI} Добавить расход</button></div>
    <div class="row"><select class="input" id="expMonth" style="width:auto" aria-label="Месяц">${months.map(k => `<option value="${k}" ${k === m ? 'selected' : ''}>${mName(k)}</option>`).join('')}</select><b class="num" style="font-size:18px">${money(total)}</b></div>
    <div class="alert info"><span>Закупку товара отмечайте галочкой «Закупка для продажи». Её стоимость уже входит в прибыль через закупочную цену товаров, поэтому мы не вычитаем её второй раз.</span></div>
    <div class="split">
      <section class="panel tight">${list.length ? `<div class="tablewrap"><table><thead><tr><th>Дата</th><th>Статья</th><th class="r">Сумма</th><th></th></tr></thead><tbody>${list.map(e => `<tr><td>${ddmm(e.date)}</td><td style="white-space:normal">${esc(e.cat)}${e.stockPurchase ? ' <span class="pill off">закупка</span>' : ''}${e.note ? `<br><span class="small muted">${esc(e.note)}</span>` : ''}</td><td class="r">${money(e.amount)}</td><td class="r"><button class="btn ghost sm" data-delexp="${e.id}" aria-label="Удалить расход">${ICON.close}</button></td></tr>`).join('')}</tbody></table></div>` : '<div class="empty"><b>Расходов за этот месяц нет</b><span>Добавляйте аренду, зарплату и другие траты, чтобы видеть настоящую прибыль.</span></div>'}</section>
      <section class="panel col"><h2>По статьям</h2>${cats.length ? cats.map(([c, v]) => `<div class="col" style="gap:4px"><div class="row between small"><span>${esc(c)}</span><b class="num">${money(v)}</b></div><div class="bar"><i style="width:${v / mx * 100}%"></i></div></div>`).join('') : '<span class="muted">Пока пусто</span>'}</section>
    </div>`;
}
export function sheetExpense() {
  openSheet('Новый расход', `<form id="expForm" class="col" novalidate style="gap:16px">
    <div class="grid2"><div class="field"><label for="e_date">Дата</label><input class="input" type="date" id="e_date" name="date" value="${today()}" max="${today()}"></div>
    <div class="field"><label for="e_amount">Сумма *</label><div class="suffix"><input class="input num" id="e_amount" name="amount" inputmode="decimal" placeholder="0"><span>${CUR}</span></div></div></div>
    <div class="field"><label for="e_cat">Статья</label><select class="input" id="e_cat" name="cat">${EXP_CATS.map(c => `<option>${c}</option>`).join('')}</select></div>
    <label class="check" id="stockPurchWrap" hidden><input type="checkbox" name="stockPurchase" id="e_sp" checked> Закупка для продажи (уже учтена в закупочной цене)</label>
    <div class="field"><label for="e_note">Комментарий</label><input class="input" id="e_note" name="note" maxlength="100" placeholder="Например, аренда за октябрь"></div>
    <button type="submit" hidden></button></form>`,
    `<span></span><div class="row"><button class="btn" data-act="close">Отмена</button><button class="btn primary" data-act="saveexp">Добавить</button></div>`);
  setTimeout(() => $('#e_amount')?.focus(), 50);
}
export function saveExpense() {
  const f = $('#expForm'), fd = new FormData(f), amount = num(fd.get('amount'));
  if (!showErrors(f, amount == null || amount <= 0 ? { amount: 'Введите сумму' } : {})) return;
  const cat = fd.get('cat');
  S.expenses.push({ id: uid(), date: fd.get('date') || today(), cat, amount, note: fd.get('note').trim(), stockPurchase: cat === 'Закупка товара' && !!fd.get('stockPurchase') });
  ui.expMonth = (fd.get('date') || today()).slice(0, 7); save(); closeSheet(); render(); toast('Расход добавлен');
}
