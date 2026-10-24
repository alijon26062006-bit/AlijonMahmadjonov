import { go, render } from '../app.js';
import { CITIES, DAYS, inZone, kindOf, SERVICE_AREA, SHOP_KINDS } from '../config.js';
import { blankShop } from '../demo.js';
import { esc, fmtPhone } from '../lib/format.js';
import { findPlace, locate, mountPicker, placeAt } from '../lib/map.js';
import { auth } from '../services/storage.js';
import { S, save, setS } from '../state.js';
import { $, app, closeSheet, ICON, onSheetClose, openSheet, toast } from '../ui/dom.js';
import { readImage } from './catalog.js';

// Регистрация магазина: пять экранов, черновик хранится в браузере между шагами.

const STEPS = ['Что продаёте', 'Магазин', 'Где находится', 'Как работаете', 'Проверка'];
const DRAFT_KEY = 'seller-register-draft';
const PREP_OPTIONS = [15, 30, 45, 60];
const PRESETS = { daily: 'Каждый день', weekdays: 'Будни', custom: 'Свой' };

const fresh = () => ({
  step: 0, kind: '', name: '', phone: auth.phone || '', logo: '', about: '',
  city: SERVICE_AREA.open ? '' : CITIES[0].name, lat: null, lng: null, address: '', addrAuto: true, landmark: '',
  preset: 'daily', from: '09:00', to: '21:00', days: DAYS.map(() => true),
  delivery: true, pickup: true, prep: 30,
});
let R = (() => { try { return { ...fresh(), ...JSON.parse(localStorage.getItem(DRAFT_KEY)) }; } catch { return fresh(); } })();
const keep = () => { try { localStorage.setItem(DRAFT_KEY, JSON.stringify(R)); } catch { /* черновик не сохранится — анкета всё равно работает */ } };
const forget = () => { try { localStorage.removeItem(DRAFT_KEY); } catch { /* нечего убирать */ } };

let picker = null;
const dropPicker = () => { picker?.destroy(); picker = null; };
const cityOf = name => CITIES.find(c => c.name === name) || CITIES[0];
// город: в тестовом режиме — любой, вписывают сами (карта переходит туда); потом — выбор из городов сервиса
const cityField = st => SERVICE_AREA.open
  ? `<div class="field"><label for="r_city">Город</label><input class="input" id="r_city" value="${esc(st.city)}" maxlength="60" placeholder="Например, Алматы" autocomplete="address-level2"><span class="tiny muted">Тестовый режим: работаем в любом городе. Впишите город — карта перейдёт туда</span></div>`
  : `<div class="field"><label for="r_city">Город</label><select class="input" id="r_city">${CITIES.map(c => `<option ${c.name === st.city ? 'selected' : ''}>${c.name}</option>`).join('')}</select></div>`;

// ---------- экраны ----------

export function renderRegister() {
  dropPicker();
  const step = R.step;
  const body = [stepKind, stepShop, stepPlace, stepHours, stepReview][step]();
  app.innerHTML = `
  <div class="wizard">
    <header class="wiz-head">
      <div class="brand"><span class="brand-mark">${ICON.shop}</span>Регистрация магазина</div>
      <div class="wiz-prog" aria-hidden="true">${STEPS.map((_, i) => `<i class="${i <= step ? 'on' : ''}"></i>`).join('')}</div>
      <div class="eyebrow">Шаг ${step + 1} из ${STEPS.length} · ${STEPS[step]}</div>
    </header>
    <main class="wiz-body">${body}</main>
    <footer class="wiz-foot">
      ${step ? '<button class="btn" data-reg="back">Назад</button>' : '<button class="btn ghost" data-act="demo">Посмотреть пример</button>'}
      <button class="btn primary" data-reg="${step === STEPS.length - 1 ? 'create' : 'next'}">${step === STEPS.length - 1 ? 'Создать магазин' : 'Далее'}</button>
    </footer>
  </div>`;
  if (step === 2) startMap($('#r_map'));
}

function stepKind() {
  return `<h1>Что вы продаёте?</h1>
    <p class="muted">От этого зависят единицы товаров и готовые категории. Поменять можно позже в настройках.</p>
    <div class="kinds" role="radiogroup" aria-label="Тип магазина">
      ${SHOP_KINDS.map(k => `<button class="kind" role="radio" aria-checked="${R.kind === k.id}" data-reg-kind="${k.id}">
        <img class="kind-img" src="img/kind-${k.id}.webp" alt="" width="72" height="72" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><span class="kind-img kind-ph" hidden><svg viewBox="0 0 24 24">${k.icon}</svg></span><span><b>${k.name}</b><small>${k.hint}</small><small class="units">${k.units.join(' · ')}</small></span></button>`).join('')}
    </div>
    <span class="err" id="r_err"></span>`;
}

function stepShop() {
  return `<h1>Ваш магазин</h1>
    <div class="logo-row">
      <label class="logo-pick" for="r_logo">${R.logo ? `<img src="${R.logo}" alt="Логотип">` : `${ICON.image}<span>Логотип</span>`}</label>
      <input type="file" id="r_logo" accept="image/*" hidden>
      <span class="small muted">Квадратная картинка. Можно сфотографировать вывеску магазина.${R.logo ? ' <button class="linkbtn" data-reg="nologo">Убрать</button>' : ''}</span>
    </div>
    <div class="field"><label for="r_name">Название *</label><input class="input" id="r_name" value="${esc(R.name)}" maxlength="60" placeholder="Например, Бозори Сабз" autocomplete="organization"></div>
    <div class="field"><label for="r_phone">Телефон магазина *</label><div class="phone"><span>+992</span><input id="r_phone" type="tel" inputmode="numeric" value="${fmtPhone(R.phone)}" placeholder="90 123 45 67" autocomplete="tel-national"></div></div>
    <div class="field"><label for="r_about">Коротко о магазине</label><textarea class="input" id="r_about" maxlength="200" placeholder="Например, свежие овощи и фрукты каждый день">${esc(R.about)}</textarea></div>`;
}

function stepPlace() {
  return `<h1>Где находится магазин</h1>
    ${cityField(R)}
    <div class="map-box"><div id="r_map" class="map" role="application" aria-label="Карта: перетащите метку на место магазина"></div>
      <button class="btn sm gps" data-reg="locate"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>Определить моё место</button></div>
    <span class="small muted" id="r_maphint">Нажмите на карту или перетащите метку туда, где вход в магазин.</span>
    <div class="field"><label for="r_address">Улица и дом *</label><input class="input" id="r_address" value="${esc(R.address)}" placeholder="Заполнится сам, когда поставите метку" autocomplete="street-address"></div>
    <div class="field"><label for="r_landmark">Ориентир для курьера</label><input class="input" id="r_landmark" value="${esc(R.landmark)}" maxlength="100" placeholder="Например, напротив ЦУМа, вход со двора"></div>`;
}

function stepHours() {
  const custom = R.preset === 'custom';
  return `<h1>Когда и как работаете</h1>
    <div class="field"><span class="lbl">График</span><div class="chips wrap">${Object.entries(PRESETS).map(([k, l]) => `<button class="chip" data-reg-preset="${k}" aria-pressed="${R.preset === k}">${l}</button>`).join('')}</div></div>
    ${custom ? `<div class="daypick">${DAYS.map((d, i) => `<label class="day"><input type="checkbox" id="r_day${i}" ${R.days[i] ? 'checked' : ''}><span>${d.slice(0, 2)}</span></label>`).join('')}</div>` : ''}
    <div class="grid2"><div class="field"><label for="r_from">Открываемся</label><input class="input" type="time" id="r_from" value="${R.from}"></div>
      <div class="field"><label for="r_to">Закрываемся</label><input class="input" type="time" id="r_to" value="${R.to}"></div></div>
    <div class="panel col" style="gap:0;padding:4px 16px">
      <label class="switch-row" for="r_delivery"><span>Доставка курьером</span><input type="checkbox" id="r_delivery" ${R.delivery ? 'checked' : ''}></label>
      <label class="switch-row" for="r_pickup"><span>Самовывоз из магазина</span><input type="checkbox" id="r_pickup" ${R.pickup ? 'checked' : ''}></label>
    </div>
    <div class="field"><span class="lbl">Сколько обычно собирается заказ</span><div class="chips wrap">${PREP_OPTIONS.map(m => `<button class="chip" data-reg-prep="${m}" aria-pressed="${R.prep === m}">${m === 60 ? '1 час' : m + ' мин'}</button>`).join('')}</div></div>
    <span class="err" id="r_err"></span>`;
}

function stepReview() {
  const k = kindOf({ kind: R.kind });
  const row = (text, step) => `<div class="rev-row"><span>${text}</span><button class="linkbtn" data-reg-go="${step}">Изменить</button></div>`;
  return `<h1>Проверьте данные</h1>
    <div class="rev-head">${R.logo ? `<img class="store-logo" src="${R.logo}" alt="">` : `<span class="store-logo">${esc(R.name.charAt(0).toUpperCase())}</span>`}
      <div><b>${esc(R.name)}</b><br><span class="small muted">${k.name} · ${esc(R.city)}</span></div></div>
    <div class="panel col" style="gap:0;padding:4px 16px">
      ${row(`Тип: ${k.name}. Единицы: ${k.units.join(', ')}`, 0)}
      ${row(`+992 ${fmtPhone(R.phone)}`, 1)}
      ${row(`${esc([R.city, R.address].filter(Boolean).join(', '))}${R.landmark ? `<br><span class="small muted">${esc(R.landmark)}</span>` : ''}${R.lat ? '' : '<br><span class="small" style="color:var(--warn)">Метка на карте не поставлена</span>'}`, 2)}
      ${row(`${scheduleText()} · ${[R.delivery && 'доставка', R.pickup && 'самовывоз'].filter(Boolean).join(' и ')} · сборка ${R.prep} мин`, 3)}
    </div>
    <p class="small muted" style="margin:0">Создадим ${k.cats.length} готовых категорий: ${k.cats.slice(0, 4).join(', ')} и другие. Лишние можно не использовать, свои — добавить.</p>`;
}

const scheduleText = () => {
  const days = R.preset === 'daily' ? 'Каждый день' : R.preset === 'weekdays' ? 'Пн–Пт' : DAYS.filter((_, i) => R.days[i]).map(d => d.slice(0, 2)).join(', ');
  return `${days} ${R.from}–${R.to}`;
};

// ---------- карта ----------

async function startMap(el, state = R, onChange = () => keep()) {
  const c = cityOf(state.city);
  const hint = $('#r_maphint');
  try {
    picker = await mountPicker(el, { lat: state.lat ?? c.lat, lng: state.lng ?? c.lng, zoom: state.lat ? 17 : 13 }, async p => {
      Object.assign(state, p);
      onChange();
      if (!state.addrAuto && state.address && (state.city || !SERVICE_AREA.open)) return;
      const { street: a, city } = await placeAt(p);
      if (SERVICE_AREA.open && city && !state.city) { state.city = city; const ci = $('#r_city'); if (ci) ci.value = city; onChange(); }
      if (a && (state.addrAuto || !state.address)) { state.address = a; state.addrAuto = true; const inp = $('#r_address'); if (inp) inp.value = a; onChange(); }
    });
    // тест в любом городе: метки ещё нет — показываем карту там, где продавец, или вписанный город
    if (SERVICE_AREA.open && state.lat == null) {
      const p = await locate().catch(() => null) || (state.city ? await findPlace(state.city) : null);
      if (p && state.lat == null) picker?.moveTo(p.lat, p.lng, 16);
    }
  } catch (err) {
    el.innerHTML = `<div class="map-fail">${esc(err.message)}<br>Адрес можно ввести вручную.</div>`;
    if (hint) hint.hidden = true;
  }
}

async function locateMe(btn) {
  btn.disabled = true; const label = btn.innerHTML; btn.textContent = 'Определяю…';
  try { const p = await locate(); picker?.moveTo(p.lat, p.lng, 17); toast('Метка поставлена'); }
  catch (err) { toast(err.message); }
  finally { btn.disabled = false; btn.innerHTML = label; }
}

// ---------- переходы и проверка ----------

function check() {
  const err = msg => { const e = $('#r_err'); if (e) e.textContent = msg; else toast(msg); return false; };
  const field = (id, msg) => { const el = $(id); el.classList.add('invalid'); el.insertAdjacentHTML('afterend', `<span class="err">${msg}</span>`); el.focus(); return false; };
  document.querySelectorAll('.wiz-body .err').forEach(e => { e.textContent = ''; if (!e.id) e.remove(); });
  document.querySelectorAll('.wiz-body .invalid').forEach(e => e.classList.remove('invalid'));
  if (R.step === 0 && !R.kind) return err('Выберите, что вы продаёте');
  if (R.step === 1) {
    if (!R.name.trim()) return field('#r_name', 'Введите название магазина');
    if (R.phone.length !== 9) return field('#r_phone', 'Номер из 9 цифр после +992');
  }
  if (R.step === 2 && !R.address.trim()) return field('#r_address', 'Укажите улицу и дом, или поставьте метку на карте');
  if (R.step === 2 && !inZone(R)) return err(`Пока работаем только в Шахритусском районе — до ${SERVICE_AREA.radiusKm} км от центра посёлка. Поставьте метку там, где магазин`);
  if (R.step === 3) {
    if (!R.delivery && !R.pickup) return err('Включите доставку или самовывоз');
    if (R.from >= R.to) return err('Время закрытия должно быть позже открытия');
    if (R.preset === 'custom' && !R.days.some(Boolean)) return err('Отметьте хотя бы один рабочий день');
  }
  return true;
}

function schedule() {
  const open = i => R.preset === 'daily' || (R.preset === 'weekdays' ? i < 5 : R.days[i]);
  return DAYS.map((_, i) => ({ open: open(i), from: R.from, to: R.to }));
}

function create() {
  const k = kindOf({ kind: R.kind });
  const shop = {
    ...blankShop({ name: R.name.trim(), type: k.name, phone: '+992 ' + fmtPhone(R.phone), address: [R.city, R.address.trim()].filter(Boolean).join(', '), about: R.about.trim() }),
    kind: k.id, city: R.city, lat: R.lat, lng: R.lng, landmark: R.landmark.trim(), logo: R.logo,
    schedule: schedule(), delivery: R.delivery, pickup: R.pickup, prep: R.prep,
  };
  setS({ v: 2, demo: false, shop, cats: [...k.cats], products: [], orders: [], expenses: [], reviews: [], staff: [], nextNo: 1001 });
  save(); forget(); R = fresh();
  go('catalog');
  toast('Магазин создан. Добавьте первый товар');
}

// ---------- события ----------

document.addEventListener('click', e => {
  const t = e.target.closest('[data-reg],[data-reg-kind],[data-reg-go],[data-reg-preset],[data-reg-prep]');
  if (!t || !t.closest('.wizard, .place-sheet')) return;
  const d = t.dataset;
  if (d.regKind) { R.kind = d.regKind; keep(); return renderRegister(); }
  if (d.regGo) { R.step = +d.regGo; keep(); return renderRegister(); }
  if (d.regPreset) { R.preset = d.regPreset; keep(); return renderRegister(); }
  if (d.regPrep) { R.prep = +d.regPrep; keep(); return renderRegister(); }
  switch (d.reg) {
    case 'next': if (check()) { R.step++; keep(); renderRegister(); window.scrollTo(0, 0); } return;
    case 'back': R.step--; keep(); renderRegister(); window.scrollTo(0, 0); return;
    case 'create': return create();
    case 'locate': return locateMe(t);
    case 'nologo': R.logo = ''; keep(); return renderRegister();
    case 'saveplace': return savePlace();
  }
});

document.addEventListener('input', e => {
  const t = e.target;
  if (!t.closest('.wizard, .place-sheet')) return;
  const state = t.closest('.place-sheet') ? P : R;
  switch (t.id) {
    case 'r_name': R.name = t.value; break;
    case 'r_about': R.about = t.value; break;
    case 'r_phone': { const dgt = t.value.replace(/\D/g, '').replace(/^992(?=\d{9})/, '').slice(0, 9); R.phone = dgt; t.value = fmtPhone(dgt); break; }
    case 'r_address': state.address = t.value; state.addrAuto = !t.value; break;
    case 'r_landmark': state.landmark = t.value; break;
    case 'r_from': R.from = t.value; break;
    case 'r_to': R.to = t.value; break;
    default: return;
  }
  if (state === R) keep();
});

document.addEventListener('change', async e => {
  const t = e.target;
  if (!t.closest('.wizard, .place-sheet')) return;
  const state = t.closest('.place-sheet') ? P : R;
  if (t.id === 'r_city' && SERVICE_AREA.open) { state.city = t.value.trim(); const p = state.city && await findPlace(state.city); if (p) picker?.moveTo(p.lat, p.lng, 13); }
  else if (t.id === 'r_city') { state.city = t.value; const c = cityOf(t.value); picker?.moveTo(c.lat, c.lng, 13); }
  if (/^r_day\d$/.test(t.id)) R.days[+t.id.slice(5)] = t.checked;
  if (t.id === 'r_delivery') R.delivery = t.checked;
  if (t.id === 'r_pickup') R.pickup = t.checked;
  if (t.id === 'r_logo' && t.files[0]) {
    try { R.logo = await readImage(t.files[0], 400); keep(); renderRegister(); } catch (err) { toast(err.message); }
    return;
  }
  if (state === R) keep();
});

// ---------- изменение адреса из настроек магазина ----------

let P = null;
onSheetClose(() => { if (P) { dropPicker(); P = null; } });

export function sheetPlace() {
  const sh = S.shop;
  P = { city: sh.city || (SERVICE_AREA.open ? '' : CITIES[0].name), lat: sh.lat ?? null, lng: sh.lng ?? null,
        address: sh.city && sh.address.startsWith(sh.city + ', ') ? sh.address.slice(sh.city.length + 2) : sh.address,
        addrAuto: false, landmark: sh.landmark || '' };
  openSheet('Адрес магазина', `<div class="place-sheet col">
    ${cityField(P)}
    <div class="map-box"><div id="r_map" class="map" role="application" aria-label="Карта: перетащите метку на место магазина"></div>
      <button class="btn sm gps" data-reg="locate"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>Определить моё место</button></div>
    <span class="small muted" id="r_maphint">Нажмите на карту или перетащите метку туда, где вход в магазин.</span>
    <div class="field"><label for="r_address">Улица и дом *</label><input class="input" id="r_address" value="${esc(P.address)}"></div>
    <div class="field"><label for="r_landmark">Ориентир для курьера</label><input class="input" id="r_landmark" value="${esc(P.landmark)}" maxlength="100"></div>
  </div>`, `<span></span><div class="row"><button class="btn" data-act="close">Отмена</button><button class="btn primary place-sheet" data-reg="saveplace">Сохранить</button></div>`);
  dropPicker();
  startMap($('#r_map'), P, () => {});
}

function savePlace() {
  if (!P.address.trim()) { toast('Укажите улицу и дом'); return $('#r_address').focus(); }
  if (!inZone(P)) return toast('Пока работаем только в Шахритусском районе. Поставьте метку там, где магазин');
  Object.assign(S.shop, { city: P.city, lat: P.lat, lng: P.lng, landmark: P.landmark.trim(), address: [P.city, P.address.trim()].filter(Boolean).join(', ') });
  save(); closeSheet(); render(); toast('Адрес сохранён');
}
