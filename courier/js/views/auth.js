import { BRAND, PHONE_CODE } from '../config.js';
import { esc, fmtPhone } from '../lib/format.js';
import * as api from '../services/api.js';
import { K, save } from '../state.js';
import { $, ico } from '../ui/dom.js';

// Вход по номеру (тестовый, без SMS) и анкета курьера: имя, машина, госномер. Три поля — и можно работать.

const draft = { name: '', car: '', plate: '' };
const field = (id, label, value, attrs = '') => `<div class="field"><label for="${id}">${label}</label><input class="input" id="${id}" value="${esc(value)}" ${attrs}></div>`;

export function vWelcome() {
  return `<main class="page auth">
    <div class="hero">
      <span class="hero-mark">${ico('bike')}</span>
      <h1>${BRAND} Курьер</h1>
      <p class="muted">Возите заказы из магазинов рядом и зарабатывайте каждый день</p>
    </div>
    <ul class="perks">
      <li>${ico('wallet')}<span><b>Сразу видно, сколько заработаете</b><small>Сумма на каждом заказе до того, как вы его взяли</small></span></li>
      <li>${ico('route')}<span><b>Маршрут в один нажим</b><small>Яндекс, 2GIS или Google — какой удобнее</small></span></li>
      <li>${ico('clock')}<span><b>Работаете когда хотите</b><small>Вышли на линию — пошли заказы. Ушли — никто не звонит</small></span></li>
    </ul>
    <form class="col" id="loginForm" novalidate>
      <div class="field"><label for="phone">Номер телефона</label>
        <div class="phone"><span>${PHONE_CODE}</span><input id="phone" type="tel" inputmode="numeric" autocomplete="tel-national" placeholder="90 123 45 67" value="${fmtPhone(K.phone)}"></div>
        <span class="err" id="loginErr" role="alert"></span></div>
      <button class="btn primary block xl" type="submit" data-a="login">Войти</button>
      <p class="tiny muted center">Тестовый вход: без SMS. Перед запуском добавим код подтверждения.</p>
    </form>
  </main>`;
}

export function vRegister() {
  const m = K.me || {};
  if (!draft.name && m.name) Object.assign(draft, { name: m.name, car: m.car, plate: m.plate });
  return `<main class="page auth">
    <div class="col" style="gap:6px"><h1>${K.me ? 'Анкета курьера' : 'Расскажите о себе'}</h1>
      <p class="muted">Это увидят покупатель и магазин, чтобы узнать вас и машину</p></div>
    <form class="col" id="regForm" novalidate>
      ${field('r_name', 'Ваше имя', draft.name, 'maxlength="40" autocomplete="given-name" placeholder="Например, Алишер"')}
      ${field('r_car', 'Машина: марка и цвет', draft.car, 'maxlength="40" placeholder="Например, Opel Astra, белый"')}
      ${field('r_plate', 'Госномер', draft.plate, 'maxlength="15" autocapitalize="characters" placeholder="01 123 AA"')}
      <div class="field"><span class="lbl">Телефон для связи</span><div class="input readonly num">${PHONE_CODE} ${fmtPhone(K.phone)}</div></div>
      <span class="err" id="regErr" role="alert"></span>
      <button class="btn primary block xl" type="submit" data-a="saveMe">${K.me ? 'Сохранить' : 'Начать работу'}</button>
      ${K.me ? '<button class="btn block" type="button" data-go="#/profile">Отмена</button>' : ''}
    </form>
  </main>`;
}

export const authActions = {
  login: async el => {
    const d = $('#phone').value.replace(/\D/g, '').replace(/^992(?=\d{9})/, '');
    if (d.length !== 9) { $('#loginErr').textContent = 'Введите 9 цифр номера'; $('#phone').focus(); return false; }
    el.disabled = true; el.textContent = 'Входим…';
    try {
      await api.login(d);
      K.phone = d; K.me = await api.me(); save();
    } catch (e) { $('#loginErr').textContent = e.message; el.disabled = false; el.textContent = 'Войти'; return false; }
  },
  saveMe: async el => {
    Object.assign(draft, { name: $('#r_name').value.trim(), car: $('#r_car').value.trim(), plate: $('#r_plate').value.trim() });
    const err = !draft.name ? ['r_name', 'Напишите имя'] : !draft.car ? ['r_car', 'Напишите марку и цвет машины'] : !draft.plate ? ['r_plate', 'Напишите госномер'] : null;
    if (err) { $('#regErr').textContent = err[1]; $('#' + err[0]).focus(); return false; }
    el.disabled = true;
    try { K.me = await api.register({ ...draft, phone: `${PHONE_CODE} ${fmtPhone(K.phone)}` }); save(); location.hash = '#/'; }
    catch (e) { $('#regErr').textContent = e.message; el.disabled = false; return false; }
  },
};
