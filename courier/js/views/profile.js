import { BRAND, NAVS } from '../config.js';
import { lang, LANGS, setLang } from '../i18n.js';
import { esc } from '../lib/format.js';
import { play } from '../lib/sound.js';
import { vibrate } from '../platform.js';
import { K, save } from '../state.js';
import { closeSheet, ico, openSheet, toast, twice } from '../ui/dom.js';
import { avatar } from './shift.js';

// Профиль и настройки: анкета, навигатор, звук, экран, язык, тема, выход.

const sw = (act, on, title, sub) => `<button class="li" data-a="${act}" role="switch" aria-checked="${on}"><span class="grow"><b>${title}</b>${sub ? `<small>${sub}</small>` : ''}</span><span class="tgl ${on ? 'on' : ''}" aria-hidden="true"></span></button>`;

export function applyTheme() {
  const r = document.documentElement;
  if (K.theme === 'auto') r.removeAttribute('data-theme'); else r.dataset.theme = K.theme;
  const dark = K.theme === 'dark' || (K.theme === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? '#121212' : '#ffffff');
}

export function vProfile() {
  const m = K.me || {};
  return `<h1>Профиль</h1>
    <section class="me-card">${avatar(m.name, 'lg')}<span class="grow"><b translate="no">${esc(m.name || '')}</b>
      <small><span translate="no">${esc(m.car || '')}</span>${m.plate ? ` · <span translate="no">${esc(m.plate)}</span>` : ''}</small>
      <small>${m.rating_count ? `${ico('starFill', 'xs')} ${Number(m.rating).toLocaleString('ru-RU', { minimumFractionDigits: 1 })} · оценок: ${m.rating_count}` : 'Оценок пока нет'}</small></span>
      <button class="btn sm" data-go="#/register">Изменить</button></section>
    <section class="section"><h3>Работа</h3><div class="list">
      <button class="li" data-a="chooseNav">${ico('nav')}<span class="grow"><b>Навигатор</b><small>${esc(NAVS.find(n => n[0] === K.nav)?.[1] || '')}</small></span>${ico('right', 'chev')}</button>
      ${sw('toggleSound', K.sound, 'Звук нового заказа', 'Громкая мелодия и вибрация')}
      <button class="li" data-a="testSound">${ico('bike')}<span class="grow"><b>Проверить звук</b></span></button>
      ${sw('toggleAwake', K.awake, 'Не гасить экран на линии', 'Заказы видно сразу, даже если телефон лежит на панели')}
    </div></section>
    <section class="section"><h3>Приложение</h3><div class="list">
      <div class="li"><span class="grow"><b>Язык</b></span><span class="chips">${LANGS.map(([k, t]) => `<button class="chip" data-a="lang" data-v="${k}" aria-pressed="${lang === k}" translate="no">${t}</button>`).join('')}</span></div>
      <div class="li"><span class="grow"><b>Тема</b></span><span class="chips">${[['auto', 'Авто'], ['light', 'Светлая'], ['dark', 'Тёмная']].map(([k, t]) => `<button class="chip" data-a="theme" data-v="${k}" aria-pressed="${K.theme === k}">${t}</button>`).join('')}</span></div>
      <button class="li" data-a="install">${ico('install')}<span class="grow"><b>Установить на телефон</b><small>Иконка на экране, как приложение</small></span></button>
    </div></section>
    <button class="btn block danger-text" data-a="logout">${ico('logout')} Выйти</button>
    <p class="tiny muted center">${BRAND} Курьер · тестовая версия</p>`;
}

export const profileActions = {
  chooseNav: () => {
    openSheet(`<h2>Навигатор</h2><p class="muted">Кнопка «Маршрут» будет открывать его</p><div class="list">${NAVS.map(([k, t]) => `<button class="li" data-a="setNav" data-v="${k}" aria-pressed="${K.nav === k}"><span class="grow"><b>${t}</b></span>${K.nav === k ? ico('check') : ''}</button>`).join('')}</div>`, { label: 'Навигатор' });
    return false;
  },
  setNav: el => { K.nav = el.dataset.v; save(); closeSheet(); toast('Навигатор выбран'); },
  toggleSound: () => { K.sound = !K.sound; save(); },
  testSound: () => { if (!play('offer')) toast('Звук недоступен в этом браузере'); vibrate([300, 120, 300]); toast('Если не слышно — уберите беззвучный режим и прибавьте громкость'); return false; },
  toggleAwake: () => { K.awake = !K.awake; save(); },
  lang: el => { setLang(el.dataset.v); location.reload(); return false; },
  theme: el => { K.theme = el.dataset.v; save(); applyTheme(); },
  logout: el => twice(el, 'Нажмите ещё раз, чтобы выйти') ? 'logout' : false,
};
