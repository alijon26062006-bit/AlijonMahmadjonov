import { CITIES, SERVICE_AREA } from '../config.js';
import { inZone } from '../model/delivery.js';
import { esc, fmtPhone } from '../lib/format.js';
import { addressAt, locate, mountPicker } from '../lib/map.js';
import { C, save } from '../state.js';
import { $, closeSheet, ico, openSheet, toast } from '../ui/dom.js';

// Адрес доставки и вход по номеру телефона — обе формы в шторке

// ----- адрес -----
let A = null, map = null, after = null;
const LABELS = ['Дом', 'Работа', 'Другое'];
export function openAddress(then = null) {
  after = then;
  A = { city: CITIES[0].name, street: '', house: '', entrance: '', floor: '', apt: '', intercom: '', landmark: '', label: 'Дом', lat: null, lng: null, ...(C.addr || {}) };
  drawAddress();
}
function drawAddress(keep) {
  try { map?.destroy(); } catch { /* карта уже убрана */ } map = null;
  const saved = C.addresses.filter(a => a.street);
  const f = (k, label, ph, attrs = '') => `<div class="field"><label for="a_${k}">${label}</label><input class="input" id="a_${k}" data-addr="${k}" value="${esc(A[k])}" placeholder="${ph}" ${attrs}></div>`;
  openSheet(`
    <h2>Куда доставить?</h2>
    ${saved.length ? `<div class="list">${saved.map((a, i) => `<button class="li" data-a="pickAddr" data-i="${C.addresses.indexOf(a)}">${ico('pin')}<span class="grow"><b>${esc(a.label || 'Адрес')}</b><small>${esc([a.street, a.house].filter(Boolean).join(', '))}, ${esc(a.city)}</small></span>${ico('right', 'chev')}</button>`).join('')}</div><span class="lbl">Или новый адрес</span>` : ''}
    <button class="btn block" data-a="locate">${ico('locate')} Определить, где я</button>
    ${CITIES.length > 1 ? `<div class="field"><span class="lbl">Город</span><div class="chips">${CITIES.map(c => `<button class="chip" data-a="addrCity" data-v="${c.name}" aria-pressed="${A.city === c.name}">${c.name}</button>`).join('')}</div></div>`
      : `<div class="notice info small">${ico('pin', 'sm')}<span>Пока возим только по Шахритусскому району — до ${SERVICE_AREA.radiusKm} км от центра посёлка.</span></div>`}
    <div class="grid2" style="grid-template-columns:2fr 1fr">${f('street', 'Улица *', 'Например, Айни', 'autocomplete="address-line1"')}${f('house', 'Дом *', '12')}</div>
    <div class="grid3">${f('entrance', 'Подъезд', '2', 'inputmode="numeric"')}${f('floor', 'Этаж', '5', 'inputmode="numeric"')}${f('apt', 'Квартира', '24')}</div>
    ${f('intercom', 'Домофон', 'Код или номер')}
    <div class="field"><label for="a_landmark">Ориентир</label><input class="input" id="a_landmark" data-addr="landmark" value="${esc(A.landmark)}" placeholder="Напротив школы №5, синие ворота"><span class="tiny muted">Курьеру так проще найти дом</span></div>
    <button class="btn block" data-a="showMap">${ico('pin')} ${A.lat ? 'Метка на карте стоит — изменить' : 'Отметить дом на карте'}</button>
    <div class="map" id="addrMap" hidden></div>
    <div class="field"><span class="lbl">Как назвать адрес</span><div class="chips wrap">${LABELS.map(l => `<button class="chip" data-a="addrLabel" data-v="${l}" aria-pressed="${A.label === l}">${l}</button>`).join('')}</div></div>
    <span class="err" id="addrErr"></span>`,
  { label: 'Адрес доставки', keepScroll: keep, foot: `<button class="btn primary" data-a="saveAddr">Сохранить адрес</button>`, onClose: () => { map?.destroy(); map = null; A = null; } });
}
const syncAddr = () => document.querySelectorAll('[data-addr]').forEach(el => { A[el.dataset.addr] = el.value.trim(); });
export const addressActions = {
  addrCity: el => { syncAddr(); A.city = el.dataset.v; const c = CITIES.find(x => x.name === A.city); if (map) map.moveTo(c.lat, c.lng, 13); drawAddress(true); return false; },
  addrLabel: el => { syncAddr(); A.label = el.dataset.v; drawAddress(true); return false; },
  pickAddr: el => { C.addr = { ...C.addresses[+el.dataset.i] }; save(); closeSheet(); toast('Адрес выбран'); after?.(); },
  showMap: async el => {
    syncAddr(); const box = $('#addrMap'); box.hidden = false; el.hidden = true;
    const c = CITIES.find(x => x.name === A.city) || CITIES[0];
    try { map = await mountPicker(box, { lat: A.lat || c.lat, lng: A.lng || c.lng, zoom: A.lat ? 17 : 13 }, async pt => { Object.assign(A, pt); const s = await addressAt(pt); if (s && !$('#a_street').value) fillStreet(s); }); }
    catch (e) { box.innerHTML = `<div class="notice info" style="height:100%">${esc(e.message)}</div>`; }
    return false;
  },
  locate: async el => {
    syncAddr(); el.disabled = true; el.textContent = 'Определяем…';
    try {
      const pt = await locate(); if (!inZone(pt)) throw new Error('Вы сейчас вне Шахритусского района — сюда пока не возим. Укажите адрес в районе'); Object.assign(A, pt);
      const near = CITIES.map(c => ({ c, d: (c.lat - pt.lat) ** 2 + (c.lng - pt.lng) ** 2 })).sort((a, b) => a.d - b.d)[0].c; A.city = near.name;
      const s = await addressAt(pt); drawAddress(true); if (s) fillStreet(s); toast(s ? 'Нашли ваш адрес — проверьте номер дома' : 'Место определили. Впишите улицу и дом');
    } catch (e) { toast(e.message); drawAddress(true); }
    return false;
  },
  saveAddr: () => {
    syncAddr();
    if (!A.street || !A.house) { $('#addrErr').textContent = 'Укажите улицу и номер дома'; (A.street ? $('#a_house') : $('#a_street')).focus(); return false; }
    if (!inZone(A)) { $('#addrErr').textContent = 'Этот адрес вне зоны доставки. Пока возим только по Шахритусскому району'; return false; }
    C.addr = { ...A }; C.addresses = [C.addr, ...C.addresses.filter(a => !(a.street === A.street && a.house === A.house && a.city === A.city))].slice(0, 5);
    save(); closeSheet(); toast('Адрес сохранён'); after?.();
  },
};
function fillStreet(s) { const [street, house] = s.split(', '); if (street) $('#a_street').value = street; if (house && !$('#a_house').value) $('#a_house').value = house; syncAddr(); }

// ----- вход по номеру -----
let L = null;
export function openLogin(then = null) {
  L = { step: 'phone', phone: C.user?.phone || '', name: C.user?.name || '', code: '', sent: 0, then };
  drawLogin();
}
function drawLogin() {
  if (L.step === 'phone') openSheet(`
    <h2>Вход по номеру телефона</h2>
    <p class="muted">Нужен, чтобы магазин и курьер могли связаться с вами. Пришлём SMS с кодом.</p>
    <div class="field"><label for="lgName">Как к вам обращаться</label><input class="input" id="lgName" value="${esc(L.name)}" placeholder="Имя" autocomplete="given-name" maxlength="40"></div>
    <div class="field"><label for="lgPhone">Номер телефона</label><div class="phone"><span>+992</span><input id="lgPhone" type="tel" inputmode="numeric" autocomplete="tel-national" placeholder="90 123 45 67" value="${fmtPhone(L.phone)}" data-input="phoneMask"></div><span class="err" id="lgErr"></span></div>
    <p class="tiny muted">Продолжая, вы соглашаетесь с условиями сервиса и обработкой персональных данных.</p>`,
  { label: 'Вход', foot: `<button class="btn primary" data-a="sendCode">Получить код</button>`, onClose: () => { L = null; } });
  else openSheet(`
    <h2>Код из SMS</h2>
    <p class="muted">Отправили на +992 ${fmtPhone(L.phone)}. <button class="link" data-a="loginBack" style="color:var(--ink)">Изменить</button></p>
    <input class="input code" id="lgCode" inputmode="numeric" autocomplete="one-time-code" maxlength="4" placeholder="····" aria-label="Код из SMS" data-input="codeTyped">
    <span class="err" id="lgErr"></span>
    <div class="notice info small">Тестовый режим: SMS не отправляется. Ваш код: <b class="num">${L.code}</b></div>`,
  { label: 'Код из SMS', foot: `<button class="btn primary" data-a="checkCode">Войти</button>`, onClose: () => { L = null; } });
  setTimeout(() => $(L?.step === 'code' ? '#lgCode' : '#lgPhone')?.focus(), 60);
}
export const loginActions = {
  phoneMask: el => { const d = el.value.replace(/\D/g, '').replace(/^992(?=\d{9})/, '').slice(0, 9); L.phone = d; el.value = fmtPhone(d); return false; },
  sendCode: () => {
    L.name = $('#lgName').value.trim();
    if (L.phone.length !== 9) { $('#lgErr').textContent = 'Введите 9 цифр номера после +992'; $('#lgPhone').focus(); return false; }
    L.code = String(Math.floor(1000 + Math.random() * 9000)); L.step = 'code'; drawLogin(); return false;
  },
  loginBack: () => { L.step = 'phone'; drawLogin(); return false; },
  codeTyped: el => { el.value = el.value.replace(/\D/g, '').slice(0, 4); if (el.value.length === 4) loginActions.checkCode(); return false; },
  checkCode: () => {
    const v = $('#lgCode').value;
    if (v !== L.code) { $('#lgErr').textContent = 'Неверный код. Проверьте и введите ещё раз'; $('#lgCode').value = ''; $('#lgCode').focus(); return false; }
    C.user = { phone: L.phone, name: L.name }; save(); const then = L.then; closeSheet(); toast('Вы вошли'); then?.();
  },
};
