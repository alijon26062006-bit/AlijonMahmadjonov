import { render } from '../app.js';
import { ROLES } from '../config.js';
import { esc, fmtPhone, uid } from '../lib/format.js';
import { S, save } from '../state.js';
import { closeSheet, ICON, openSheet, plusI, showErrors, toast } from '../ui/dom.js';

// Сотрудники
export function vStaff() {
  const rows = S.staff.map(x => `<div class="staff-row"><span class="avatar">${esc(x.name.charAt(0).toUpperCase())}</span>
    <div style="min-width:0"><b translate="no">${esc(x.name)}</b><div class="small muted num">+992 ${fmtPhone(x.phone)} · ${ROLES[x.role].name}</div></div>
    <button class="btn sm" data-staffedit="${x.id}">Изменить</button></div>`).join('');
  return `
    <div class="head"><div><div class="eyebrow"><span translate="no">${esc(S.shop.name)}</span></div><h1>Сотрудники</h1></div>
      <div class="row"><button class="btn primary" data-act="addstaff">${plusI} Добавить сотрудника</button></div></div>
    <p class="muted" style="margin:0">Сотрудник входит в кабинет по своему номеру телефона и видит только свои разделы. Деньги и список сотрудников видит только владелец.</p>
    <div class="panel tight staff-list">
      <div class="staff-row"><span class="avatar own">${ICON.check}</span><div><b>Вы — владелец</b><div class="small muted num">+992 ${fmtPhone(S.shop.owner || '')} · все разделы</div></div></div>
      ${rows}
    </div>
    <section class="col" style="gap:10px"><h2>Что может каждая роль</h2>
      <div class="grid3">${Object.values(ROLES).map(r => `<div class="panel col" style="gap:4px"><b>${r.name}</b><span class="small muted">${r.hint}</span></div>`).join('')}</div></section>`;
}
export function sheetStaff(id) {
  const x = S.staff.find(s => s.id === id) || { id: uid(), name: '', phone: '', role: 'cashier', isNew: true };
  openSheet(x.isNew ? 'Новый сотрудник' : 'Сотрудник', `
    <form id="staffForm" class="col" novalidate style="gap:14px" data-id="${x.id}">
      <div class="field"><label for="st_name">Имя *</label><input class="input" id="st_name" name="name" value="${esc(x.name)}" maxlength="40" placeholder="Например, Фарход"></div>
      <div class="field"><label for="st_phone">Номер телефона *</label><div class="phone"><span>+992</span><input id="st_phone" name="phone" type="tel" inputmode="numeric" value="${fmtPhone(x.phone)}" placeholder="90 123 45 67"></div></div>
      <div class="field"><span class="lbl">Роль</span><div class="col" style="gap:8px">${Object.entries(ROLES).map(([k, r]) => `<label class="check role-opt"><input type="radio" name="role" value="${k}" ${k === x.role ? 'checked' : ''}><span><b>${r.name}</b><br><span class="small muted">${r.hint}</span></span></label>`).join('')}</div></div>
      <button type="submit" hidden></button>
    </form>`,
    `<div class="row">${x.isNew ? '' : `<button class="btn danger" data-staffdel="${x.id}">Удалить</button>`}</div><div class="row"><button class="btn" data-act="close">Отмена</button><button class="btn primary" data-act="savestaff">${x.isNew ? 'Добавить' : 'Сохранить'}</button></div>`);
}
export function saveStaff() {
  const f = document.querySelector('#staffForm'), fd = new FormData(f), id = f.dataset.id;
  const name = String(fd.get('name') ?? '').trim(), phone = String(fd.get('phone') ?? '').replace(/\D/g, '').replace(/^992(?=\d{9})/, ''), errs = {};
  if (!name) errs.name = 'Введите имя';
  if (phone.length !== 9) errs.phone = 'Нужно 9 цифр после +992';
  else if (phone === S.shop.owner) errs.phone = 'Это номер владельца';
  else if (S.staff.some(s => s.phone === phone && s.id !== id)) errs.phone = 'Этот номер уже добавлен';
  if (!showErrors(f, errs)) return;
  const i = S.staff.findIndex(s => s.id === id), x = { id, name, phone, role: fd.get('role') };
  if (i < 0) S.staff.push(x); else S.staff[i] = x;
  save(); closeSheet(); render(); toast(i < 0 ? `${name} добавлен. Пусть войдёт по своему номеру` : 'Сохранено');
}
export function deleteStaff(id) { S.staff = S.staff.filter(s => s.id !== id); save(); closeSheet(); render(); toast('Сотрудник удалён'); }
