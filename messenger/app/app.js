'use strict';
/* =========================================================
   Aloqa — messenger web app (front-end prototype).
   State lives in localStorage; replies are simulated.
   ========================================================= */

const KEY = 'aloqa.v1';
const RM = matchMedia('(prefers-reduced-motion: reduce)');
const NET = window.NET || { on: false };
const isMobile = () => !matchMedia('(min-width: 900px)').matches;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const uid = () => Math.random().toString(36).slice(2, 10);
const pick = a => a[Math.floor(Math.random() * a.length)];

/* ---------- Icons (same set as Figma icon/* components) ---------- */
const I = {
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
  chat: '<path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.6 8.6 0 0 1-3.8-.9L3 21l1.9-5A8.4 8.4 0 0 1 12 3a8.5 8.5 0 0 1 9 8.5z"/>',
  phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  back: '<path d="m15 18-6-6 6-6"/>', chevron: '<path d="m9 18 6-6-6-6"/>',
  video: '<path d="m22 8-6 4 6 4V8z"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
  attach: '<path d="m21.4 11-9.2 9.2a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5"/>',
  mic: '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M19 10v1a7 7 0 0 1-14 0v-1"/><path d="M12 18v4"/>',
  micOff: '<path d="m2 2 20 20"/><path d="M18.9 13.5A7 7 0 0 0 19 12v-2"/><path d="M5 10v2a7 7 0 0 0 12 5"/><path d="M15 9.3V5a3 3 0 0 0-5.7-1.3"/><path d="M9 9v3a3 3 0 0 0 5.1 2.1"/><path d="M12 19v3"/>',
  send: '<path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/>',
  smile: '<circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><path d="M9 9h.01"/><path d="M15 9h.01"/>',
  checks: '<path d="M2 12.5 6.5 17 15 8"/><path d="m12 15.5 1.5 1.5L22 8"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  pin: '<path d="M12 17v5"/><path d="M9 10.8V4h6v6.8l3 3.2v3H6v-3z"/>',
  more: '<circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/>',
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/>',
  mute: '<path d="M6 8a6 6 0 0 1 9.3-5"/><path d="M18 8c0 7 3 9 3 9H9"/><path d="M6.3 11.5C6 15.6 3 17 3 17h3"/><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/><path d="m2 2 20 20"/>',
  lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
  at: '<circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-4 8"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  plus: '<path d="M12 5v14"/><path d="M5 12h14"/>',
  camera: '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3z"/><circle cx="12" cy="13" r="3"/>',
  play: '<path d="m7 4 13 8-13 8z" fill="currentColor"/>',
  pause: '<rect x="6" y="4" width="4" height="16" rx="1" fill="currentColor"/><rect x="14" y="4" width="4" height="16" rx="1" fill="currentColor"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
  reply: '<path d="m9 17-5-5 5-5"/><path d="M20 18v-2a4 4 0 0 0-4-4H4"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  monitor: '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  arrowIn: '<path d="M17 7 7 17"/><path d="M17 17H7V7"/>',
  arrowOut: '<path d="M7 17 17 7"/><path d="M7 7h10v10"/>',
  volume: '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/>',
  videoOff: '<path d="m2 2 20 20"/><path d="M16 16v1a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2"/><path d="M10 5h4a2 2 0 0 1 2 2v3.3l1 1L22 8v8"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
  megaphone: '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
  verified: '<path d="M12 2 14.4 4.3l3.3-.5.6 3.3 3 1.5-1.5 3 1.5 3-3 1.5-.6 3.3-3.3-.5L12 22l-2.4-2.3-3.3.5-.6-3.3-3-1.5 1.5-3-1.5-3 3-1.5.6-3.3 3.3.5z" fill="currentColor" stroke="none"/><path d="m8.5 12 2.5 2.5 4.5-5" stroke="#fff"/>',
  alert: '<circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
  keyboard: '<rect x="2" y="5" width="20" height="14" rx="3"/><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 12.5h.01M10 12.5h.01M14 12.5h.01M18 12.5h.01M8 16h8"/>',
  images: '<rect x="7" y="7" width="15" height="13" rx="2"/><path d="M3 16V5a2 2 0 0 1 2-2h11"/><circle cx="12" cy="11.5" r="1.5"/><path d="m22 16-3-3-6 6"/>',
  mapPin: '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z" fill="currentColor" fill-opacity=".18"/><circle cx="12" cy="10" r="3"/>',
  userCircle: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="10" r="3"/><path d="M6.7 19a6 6 0 0 1 10.6 0"/>',
  doc: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="currentColor" fill-opacity=".18"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h5"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  poll: '<path d="M4 6h10"/><path d="M4 12h16"/><path d="M4 18h7"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/><path d="M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/>'
};
const MAP = `<svg class="map" viewBox="0 0 260 130" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><rect width="260" height="130" fill="#E3EBDD"/><rect x="84" y="50" width="38" height="32" rx="4" fill="#CFDDC3"/><rect x="192" y="104" width="56" height="22" rx="4" fill="#BFD7EA"/><rect x="10" y="102" width="44" height="22" rx="4" fill="#CFDDC3"/><path d="M0 40h260M0 96h260M70 0v130M182 0v130" stroke="#fff" stroke-width="10"/><path d="M0 72 260 18M122 0l40 130" stroke="#fff" stroke-width="5"/><g transform="translate(130 66)"><ellipse cy="4" rx="14" ry="5" fill="#000" opacity=".12"/><path d="M0-30c-9 0-16 7-16 16 0 11 16 24 16 24s16-13 16-24c0-9-7-16-16-16z" fill="#10B981"/><circle cy="-14" r="6" fill="#fff"/></g></svg>`;
const MON_SHORT = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
const WD_FULL = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота'];
const ATT = [
  ['att-photo', 'images', 'Фото', '#3B82F6'], ['att-camera', 'camera', 'Камера', 'var(--text)'],
  ['att-location', 'mapPin', 'Геопозиция', '#10B981'], ['att-contact', 'userCircle', 'Контакт', '#8A90A6'],
  ['att-doc', 'doc', 'Документ', '#2563EB'], ['att-poll', 'poll', 'Опрос', '#F59E0B'], ['att-event', 'calendar', 'Мероприятие', '#EF4444']
];
const ic = (n, s = 24) => `<svg class="ic" width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${I[n]}</svg>`;
const av = (t, g, s = 52, online = false) => `<span class="av ${g}" style="--s:${s}px" aria-hidden="true">${esc(t)}${online ? '<span class="dot"></span>' : ''}</span>`;
const LOGO = `<div class="logo" aria-hidden="true"><svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">${I.chat}<path d="M8.5 13.5 12 7l3.5 6.5M9.6 11.5h4.8"/></svg></div>`;

/* ---------- Time helpers ---------- */
const pad = n => String(n).padStart(2, '0');
const hhmm = ts => { const d = new Date(ts); return pad(d.getHours()) + ':' + pad(d.getMinutes()); };
const dayStart = ts => { const d = new Date(ts); d.setHours(0, 0, 0, 0); return d.getTime(); };
const dayDiff = ts => Math.round((dayStart(Date.now()) - dayStart(ts)) / 864e5);
const WD = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
const MON = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
function listTime(ts) {
  const d = dayDiff(ts);
  if (d === 0) return hhmm(ts);
  if (d === 1) return 'Вчера';
  if (d < 7) return WD[new Date(ts).getDay()];
  const x = new Date(ts); return pad(x.getDate()) + '.' + pad(x.getMonth() + 1) + '.' + String(x.getFullYear()).slice(2);
}
function dayLabel(ts) {
  const d = dayDiff(ts);
  if (d === 0) return 'Сегодня';
  if (d === 1) return 'Вчера';
  const x = new Date(ts); return x.getDate() + ' ' + MON[x.getMonth()];
}
const dur = s => Math.floor(s / 60) + ':' + pad(Math.floor(s % 60));
function seenText(p) {
  if (p.online) return 'в сети';
  const m = Math.round((Date.now() - p.seen) / 60e3);
  if (m < 1) return 'был(а) только что';
  if (m < 60) return `был(а) ${m} мин назад`;
  if (dayDiff(p.seen) === 0) return 'был(а) в ' + hhmm(p.seen);
  if (dayDiff(p.seen) === 1) return 'был(а) вчера в ' + hhmm(p.seen);
  return 'был(а) ' + dayLabel(p.seen);
}
const plural = (n, one, few, many) => { const a = n % 10, b = n % 100; return a === 1 && b !== 11 ? one : a >= 2 && a <= 4 && (b < 10 || b >= 20) ? few : many; };

/* ---------- Seed data ---------- */
function seed() {
  const ago = m => Date.now() - m * 60e3;
  const M = (from, extra, minAgo) => ({ id: uid(), from, ts: ago(minAgo), kind: 'text', status: 'read', ...extra });
  const contacts = {
    madina: { name: 'Мадина Каримова', ini: 'МК', g: 'g2', phone: '+992 90 123 45 67', user: 'madina_k', bio: 'Дизайнер интерфейсов · Душанбе', online: true },
    dilshod: { name: 'Дилшод Рахимов', ini: 'ДР', g: 'g3', phone: '+992 93 555 12 40', user: 'dilshod_r', bio: 'Фронтенд-разработчик', online: true },
    mama: { name: 'Мама', ini: 'М', g: 'g6', phone: '+992 91 700 00 01', user: '', bio: '', online: false, seen: ago(35) },
    safina: { name: 'Сафина Назарова', ini: 'СН', g: 'g4', phone: '+992 98 210 33 77', user: 'safina_n', bio: 'Фотограф', online: false, seen: ago(180) },
    bakhrom: { name: 'Бахром Алиев', ini: 'БА', g: 'g7', phone: '+992 92 404 18 18', user: 'bakhrom', bio: 'Футбол и кофе', online: false, seen: ago(60 * 26) },
    farrukh: { name: 'Фаррух Ахмедов', ini: 'ФА', g: 'g5', phone: '+992 90 818 81 88', user: 'farrukh_dev', bio: 'Бэкенд · Go и Python', online: true },
    lola: { name: 'Лола Мирзоева', ini: 'ЛМ', g: 'g6', phone: '+992 93 101 20 30', user: 'lola_m', bio: 'Путешествия и горы', online: false, seen: ago(15) }
  };
  const chats = [
    { id: 'team', type: 'group', title: 'Команда проекта', ini: 'КП', g: 'g5', members: ['farrukh', 'dilshod', 'madina'], pinned: true, unread: 3, messages: [
      M('farrukh', { text: 'Всем привет! Сегодня в 15:00 показываем демо' }, 160),
      M('dilshod', { text: 'Я подготовлю экран чатов' }, 150),
      M('me', { text: 'Супер, жду 👌' }, 148),
      M('madina', { text: 'Обновила иконки в Figma' }, 40),
      M('dilshod', { text: 'Тёмная тема тоже готова' }, 22),
      M('farrukh', { text: 'Залил новую сборку 🚀' }, 8)
    ] },
    { id: 'madina', type: 'direct', cid: 'madina', unread: 2, messages: [
      M('madina', { text: 'Привет! Ты уже посмотрел макет мессенджера? 👀' }, 30),
      M('me', { text: 'Да, только что! Выглядит очень круто 🔥' }, 29),
      M('me', { text: 'Особенно тёмная тема' }, 29),
      M('madina', { kind: 'image', hue: 250, caption: 'Вот ещё вариант обложки' }, 26),
      M('madina', { kind: 'voice', dur: 42 }, 18)
    ] },
    { id: 'mama', type: 'direct', cid: 'mama', unread: 0, messages: [
      M('mama', { text: 'Как дела? Как учёба?' }, 160),
      M('me', { text: 'Всё хорошо! Позвоню вечером, обнимаю' }, 110)
    ] },
    { id: 'dilshod', type: 'direct', cid: 'dilshod', unread: 0, messages: [
      M('me', { text: 'Скинь, пожалуйста, фото с презентации' }, 200),
      M('dilshod', { kind: 'image', hue: 170 }, 190)
    ] },
    { id: 'news', type: 'channel', title: 'Aloqa News', ini: 'A', g: 'g1', verified: true, muted: true, unread: 12, subs: 12480, about: 'Официальный канал Aloqa: новости и обновления.', messages: [
      M('news', { text: 'Добро пожаловать в Aloqa! Здесь мы рассказываем о новых функциях.' }, 60 * 50),
      M('news', { text: 'Вышло обновление 2.0: темы и папки' }, 60 * 22)
    ] },
    { id: 'safina', type: 'direct', cid: 'safina', unread: 0, messages: [
      M('safina', { text: 'Пойдём в субботу в горы?' }, 60 * 27),
      M('me', { text: 'Ок, увидимся в субботу 👋' }, 60 * 26)
    ] },
    { id: 'bakhrom', type: 'direct', cid: 'bakhrom', unread: 0, messages: [
      M('bakhrom', { kind: 'file', name: 'Расписание_матчей.pdf', size: '1,2 МБ' }, 60 * 74),
      M('bakhrom', { text: 'Ха-ха, это лучшее 😂' }, 60 * 73)
    ] }
  ];
  const calls = [
    { id: uid(), cid: 'madina', dir: 'in', video: true, ts: ago(90), dur: 754 },
    { id: uid(), cid: 'mama', dir: 'out', ts: ago(60 * 20), dur: 312 },
    { id: uid(), cid: 'farrukh', dir: 'missed', ts: ago(60 * 28) },
    { id: uid(), cid: 'safina', dir: 'out', video: true, ts: ago(60 * 50), dur: 1260 },
    { id: uid(), cid: 'bakhrom', dir: 'missed', ts: ago(60 * 75) }
  ];
  const stories = [
    { cid: 'madina', seen: false, ts: ago(50), slides: [{ text: 'Новый макет Aloqa почти готов ✨', g: 'g2' }, { text: 'Скоро покажу тёмную тему', g: 'g1' }] },
    { cid: 'dilshod', seen: false, ts: ago(120), slides: [{ text: 'Код ревью до полуночи ☕', g: 'g3' }] },
    { cid: 'safina', seen: false, ts: ago(300), slides: [{ text: 'Закат в Варзобе 🌄', g: 'g4' }] },
    { cid: 'farrukh', seen: true, ts: ago(600), slides: [{ text: 'Go 1.24 — огонь', g: 'g5' }] },
    { cid: 'lola', seen: true, ts: ago(900), slides: [{ text: 'Искандеркуль 💙', g: 'g6' }] }
  ];
  return { v: 1, user: null, contacts, chats, calls, stories, myStory: null, settings: { theme: 'system', notify: true } };
}

/* ---------- State ---------- */
let S = load() || seed();
function load() { try { const s = JSON.parse(localStorage.getItem(KEY)); return s && s.v === 1 && Array.isArray(s.chats) ? s : null; } catch (e) { return null; } }
function save() {
  if (NET.on) { try { localStorage.setItem(KEY, JSON.stringify({ v: 1, settings: S.settings })); } catch (e) { /* ignore */ } return; }
  try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { /* storage unavailable: keep in memory */ } }

const UI = {
  route: {}, query: '', folder: 'all', callFilter: 'all', contactQuery: '',
  typing: {}, replyToken: {}, rendered: new Set(), reply: null, emoji: false,
  playing: null, rec: null, story: null, drafts: {}, prevUnread: {}, prevTotal: 0, fabNew: 0
};
const REPLIES = ['Звучит отлично!', 'Ха-ха, точно 😄', 'Давай обсудим вечером', 'Хорошо, договорились 👍', 'Сейчас посмотрю', 'Супер! Спасибо 🙌', 'Согласен(на) на все 100', 'Уже бегу 🏃'];
const EMOJI = ['😀', '😂', '😍', '🥰', '😎', '🤔', '😭', '😅', '👍', '👏', '🙏', '🔥', '🎉', '❤️', '💜', '✨', '🤝', '🙌', '👋', '✅', '🚀', '☕', '🌙', '😴'];

/* ---------- Chat helpers ---------- */
const chatById = id => S.chats.find(c => c.id === id);
const person = id => S.contacts[id];
const chatTitle = c => c.type === 'direct' ? person(c.cid).name : c.title;
const chatAv = (c, s = 52, dot = true) => c.type === 'direct' ? av(person(c.cid).ini, person(c.cid).g, s, dot && person(c.cid).online) : av(c.ini, c.g, s);
const lastMsg = c => c.messages[c.messages.length - 1];
const firstName = id => id === 'me' ? 'Вы' : (person(id) ? person(id).name.split(' ')[0] : id);
const meName = () => S.user ? S.user.name : 'Вы';
const meIni = () => S.user ? S.user.name.split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase() : 'Я';
function sortedChats() {
  return [...S.chats].sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0) || ((lastMsg(b) || {}).ts || 0) - ((lastMsg(a) || {}).ts || 0));
}
function bodyText(m) {
  switch (m.kind) {
    case 'voice': return 'Голосовое сообщение · ' + dur(m.dur);
    case 'image': return m.caption || 'Фото';
    case 'video': return m.caption || 'Видео';
    case 'file': return m.name;
    case 'location': return 'Геопозиция: ' + m.addr;
    case 'contact': return 'Контакт: ' + ((person(m.cid) || m.card || {}).name || '');
    case 'poll': return 'Опрос: ' + m.poll.q;
    case 'event': return 'Мероприятие: ' + m.event.title;
    default: return m.text;
  }
}
function bodyPreview(m) {
  const K = { location: 'mapPin', contact: 'userCircle', poll: 'poll', event: 'calendar' };
  if (K[m.kind]) return `<span class="pv">${ic(K[m.kind], 14)}${esc(bodyText(m))}</span>`;
  if (m.kind === 'voice') return `<span class="pv brand">${ic('mic', 14)}Голосовое · ${dur(m.dur)}</span>`;
  if (m.kind === 'image' || m.kind === 'video') return `<span class="pv">${ic(m.kind === 'video' ? 'video' : 'image', 14)}${esc(bodyText(m))}</span>`;
  if (m.kind === 'file') return `<span class="pv">${ic('file', 14)}${esc(m.name)}</span>`;
  return esc(m.text);
}
function preview(c) {
  if (UI.typing[c.id]) return `<span class="typing-t">${c.type === 'group' ? esc(firstName(UI.typing[c.id])) + ' печатает…' : 'печатает…'}</span>`;
  const m = lastMsg(c); if (!m) return 'Нет сообщений';
  let who = '';
  if (c.type === 'group') who = `<em>${esc(firstName(m.from))}:</em> `;
  return who + bodyPreview(m);
}
const totalUnread = () => S.chats.filter(c => c.unread > 0 && !c.muted).length;
function hueGrad(h) { return `<svg viewBox="0 0 260 182" preserveAspectRatio="xMidYMid slice"><defs><linearGradient id="gr${h}" x1="0" y1="0" x2=".6" y2="1"><stop offset="0" stop-color="hsl(${h} 90% 64%)"/><stop offset=".55" stop-color="hsl(${h + 20} 85% 72%)"/><stop offset="1" stop-color="hsl(${h + 120} 95% 80%)"/></linearGradient></defs><rect width="260" height="182" fill="url(#gr${h})"/><circle cx="196" cy="52" r="20" fill="#FFF3DC" opacity=".9"/><path d="M0 182 76 90l44 48 36-32 104 76z" fill="hsl(${h} 60% 25%)" opacity=".55"/><path d="M0 182 56 126l42 32 60-60 102 84z" fill="hsl(${h} 60% 16%)" opacity=".7"/></svg>`; }
function resample(arr, n) { if (arr.length === n) return arr; return Array.from({ length: n }, (_, i) => arr[Math.min(arr.length - 1, Math.floor(i * arr.length / n))]); }
const linkify = t => t.replace(/\b(https?:\/\/[^\s<]+[^\s<.,;:!?)\]'"])/g, '<a class="lnk" href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
function reactsHTML(m) {
  const r = m.reacts; if (!r) return '';
  const list = Object.entries(r).filter(([, ids]) => ids.length);
  if (!list.length) return '';
  return `<span class="rxs">${list.map(([e, ids]) => `<button type="button" class="rx${ids.includes('me') ? ' mine' : ''}" data-act="react" data-id="${m.id}" data-e="${e}" aria-label="Реакция ${e}: ${ids.length}${ids.includes('me') ? ', ваша' : ''}" aria-pressed="${ids.includes('me')}">${e}${ids.length > 1 ? `<span>${ids.length}</span>` : ''}</button>`).join('')}</span>`;
}
function waveHeights(id, n = 28) { let x = 0; for (const ch of id) x = (x * 31 + ch.charCodeAt(0)) >>> 0; const out = []; for (let i = 0; i < n; i++) { x = (x * 1103515245 + 12345) >>> 0; out.push(5 + (x % 23)); } return out; }

/* ---------- Theme ---------- */
const darkMQ = matchMedia('(prefers-color-scheme: dark)');
function applyTheme() {
  const t = S.settings.theme === 'system' ? (darkMQ.matches ? 'dark' : 'light') : S.settings.theme;
  document.documentElement.dataset.theme = t;
  const m = $('meta[name="theme-color"]'); if (m) m.content = t === 'dark' ? '#0E1016' : '#F4F5FA';
  if (window.applyChatLook) applyChatLook();
}
darkMQ.addEventListener('change', applyTheme);

/* ---------- Toast ---------- */
let toastTimer;
function toast(html, action, onAction, ms = 3500, top = false) {
  const el = $('#toast'); el.classList.toggle('top', top || !!$('#callLayer').innerHTML); el.dataset.chat = '';
  el.innerHTML = `<div class="tt">${html}${action ? `<button type="button">${esc(action)}</button>` : ''}</div>`;
  if (action) $('button', el).onclick = () => { el.innerHTML = ''; onAction(); };
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.innerHTML = ''; }, ms);
}

/* =========================================================
   Onboarding: phone → code → name
   ========================================================= */
const OB = { step: 1, cc: '+992', phone: '' };
const CC = [['+992', 'TJ', 9], ['+998', 'UZ', 9], ['+7', 'RU', 10]];
function fmtPhone(d, cc) {
  if (cc === '+7') return [d.slice(0, 3), d.slice(3, 6), d.slice(6, 8), d.slice(8, 10)].filter(Boolean).join(' ');
  return [d.slice(0, 2), d.slice(2, 5), d.slice(5, 7), d.slice(7, 9)].filter(Boolean).join(' ');
}
function renderOnboarding() {
  const app = $('#app'); app.className = 'app';
  const steps = `<div class="steps" aria-label="Шаг ${OB.step} из 3">${[1, 2, 3].map(i => `<i class="${i === OB.step ? 'on' : ''}"></i>`).join('')}</div>`;
  if (OB.step === 1) {
    app.innerHTML = `<div class="ob"><div class="ob-in" id="main">
      <div class="art" aria-hidden="true">
        <span class="fa" style="left:38px;top:76px">${av('МК', 'g2', 56, true)}</span>
        <span class="fa" style="right:44px;top:52px">${av('ДР', 'g3', 48)}</span>
        <span class="fa" style="right:70px;top:300px">${av('СН', 'g4', 44)}</span>
        <span class="fa" style="left:56px;top:300px">${av('ФА', 'g5', 40)}</span>
        <div class="fb w" style="left:104px;top:66px">Привет! 👋</div>
        <div class="fb p" style="right:24px;top:112px">Созвонимся?</div>
        <div class="fb w" style="left:24px;top:240px">${ic('mic', 16)}0:42</div>
        <div class="fb p" style="right:28px;top:250px">${ic('image', 16)}Фото</div>
        ${LOGO}
      </div>
      <form class="body" id="phoneForm" novalidate>
        <h1>Общайтесь<br>без <span>границ</span></h1>
        <p class="lead">Быстрые сообщения, голосовые, фото и видео — через ваш собственный сервер.</p>
        <label class="lbl" for="phone">Номер телефона</label>
        <div class="phone-in">
          <label class="sr-only" for="cc">Код страны</label>
          <select class="inp" id="cc" autocomplete="tel-country-code">${CC.map(([c, n]) => `<option value="${c}" ${c === OB.cc ? 'selected' : ''}>${n} ${c}</option>`).join('')}</select>
          <input class="inp" id="phone" type="tel" inputmode="numeric" autocomplete="tel-national" placeholder="90 123 45 67" value="${esc(fmtPhone(OB.phone, OB.cc))}" aria-describedby="phoneErr">
        </div>
        <div id="phoneErr" aria-live="polite"></div>
        <button class="btn primary block" type="submit" id="phoneBtn">Продолжить</button>
        <p class="terms">Продолжая, вы принимаете <a href="#" onclick="return false">Условия</a><br>и <a href="#" onclick="return false">Политику конфиденциальности</a></p>
      </form></div></div>`;
    const inp = $('#phone'), cc = $('#cc');
    const need = () => CC.find(x => x[0] === OB.cc)[2];
    inp.addEventListener('input', () => {
      OB.phone = inp.value.replace(/\D/g, '').slice(0, need()); inp.value = fmtPhone(OB.phone, OB.cc);
      if (inp.getAttribute('aria-invalid')) { inp.removeAttribute('aria-invalid'); $('#phoneErr').innerHTML = ''; }
    });
    cc.addEventListener('change', () => { OB.cc = cc.value; OB.phone = OB.phone.slice(0, need()); inp.value = fmtPhone(OB.phone, OB.cc); });
    $('#phoneForm').addEventListener('submit', e => {
      e.preventDefault();
      if (OB.phone.length !== need()) {
        inp.setAttribute('aria-invalid', 'true');
        $('#phoneErr').innerHTML = `<p class="err">${ic('alert', 16)}Введите ${need()} цифр номера — без кода страны</p>`;
        inp.focus(); return;
      }
      if (NET.on) return NET.phoneSubmit($('#phoneBtn'));
      busy($('#phoneBtn'), () => { OB.step = 2; renderOnboarding(); });
    });
  } else if (OB.step === 2) {
    if (NET.on) return NET.renderPassStep();
    app.innerHTML = `<div class="ob"><div class="ob-in" id="main">
      <div class="top-nav"><button class="ib accent" type="button" id="obBack" aria-label="Назад">${ic('back', 26)}</button>${steps}</div>
      <form class="step-body" id="codeForm" novalidate>
        <div class="step-ill">${ic('lock', 32)}</div>
        <h1>Введите код</h1>
        <p class="lead">Мы отправили SMS на <b style="color:var(--text)">${esc(OB.cc + ' ' + fmtPhone(OB.phone, OB.cc))}</b></p>
        <span class="lbl" id="codeLbl">Код из SMS</span>
        <div class="code" role="group" aria-labelledby="codeLbl">${[0, 1, 2, 3].map(i => `<input class="inp" inputmode="numeric" maxlength="1" ${i === 0 ? 'autocomplete="one-time-code"' : ''} aria-label="Цифра ${i + 1}">`).join('')}</div>
        <p class="hint">Демо-режим: подойдёт любой код</p>
        <div class="resend" id="resend"></div>
        <button class="btn primary block" type="submit" id="codeBtn" disabled>Подтвердить</button>
      </form></div></div>`;
    $('#obBack').onclick = () => { OB.step = 1; renderOnboarding(); };
    const boxes = $$('.code input'); boxes[0].focus();
    const check = () => { const full = boxes.every(b => b.value); $('#codeBtn').disabled = !full; if (full) $('#codeForm').requestSubmit(); };
    boxes.forEach((b, i) => {
      b.addEventListener('input', () => {
        const d = b.value.replace(/\D/g, '');
        if (d.length > 1) { d.split('').slice(0, 4 - i).forEach((x, k) => { boxes[i + k].value = x; }); boxes[Math.min(3, i + d.length - 1)].focus(); }
        else { b.value = d; if (d && i < 3) boxes[i + 1].focus(); }
        check();
      });
      b.addEventListener('keydown', e => { if (e.key === 'Backspace' && !b.value && i > 0) boxes[i - 1].focus(); });
    });
    let left = 30; const tick = () => {
      const r = $('#resend'); if (!r) return clearInterval(t);
      r.innerHTML = left > 0 ? `Отправить код повторно через 0:${pad(left)}` : `<button type="button" id="resendBtn">Отправить код ещё раз</button>`;
      if (left <= 0) { clearInterval(t); $('#resendBtn').onclick = () => { toast('Код отправлен повторно'); left = 30; t = setInterval(tick, 1000); tick(); }; }
      left--;
    }; let t = setInterval(tick, 1000); tick();
    $('#codeForm').addEventListener('submit', e => { e.preventDefault(); if (!$('#codeBtn').disabled) busy($('#codeBtn'), () => { OB.step = 3; renderOnboarding(); }); });
  } else {
    app.innerHTML = `<div class="ob"><div class="ob-in" id="main">
      <div class="top-nav"><button class="ib accent" type="button" id="obBack" aria-label="Назад">${ic('back', 26)}</button>${steps}</div>
      <form class="step-body" id="nameForm" novalidate>
        <div class="step-ill">${ic('smile', 32)}</div>
        <h1>Как вас зовут?</h1>
        <p class="lead">Имя увидят ваши контакты. Его можно изменить в настройках.</p>
        <label class="lbl" for="fname">Имя</label>
        <input class="inp" id="fname" autocomplete="given-name" aria-describedby="nameErr" required>
        <div id="nameErr" aria-live="polite"></div>
        <label class="lbl" for="lname">Фамилия <span style="font-weight:500">(необязательно)</span></label>
        <input class="inp" id="lname" autocomplete="family-name">
        <button class="btn primary block" type="submit" id="nameBtn" style="margin-top:24px">Начать общение</button>
      </form></div></div>`;
    $('#obBack').onclick = () => { OB.step = 2; renderOnboarding(); };
    $('#fname').focus();
    $('#nameForm').addEventListener('submit', e => {
      e.preventDefault();
      const f = $('#fname').value.trim(), l = $('#lname').value.trim();
      if (!f) { $('#fname').setAttribute('aria-invalid', 'true'); $('#nameErr').innerHTML = `<p class="err">${ic('alert', 16)}Укажите имя, чтобы контакты вас узнали</p>`; $('#fname').focus(); return; }
      busy($('#nameBtn'), () => {
        S.user = { name: (f + ' ' + l).trim(), phone: OB.cc + ' ' + fmtPhone(OB.phone, OB.cc), user: '' };
        save(); location.hash = '#/chats'; renderApp();
        toast(`Добро пожаловать, ${esc(f)}!`);
      });
    });
  }
}
function busy(btn, done) { const t = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<span class="spinner" aria-hidden="true"></span><span class="sr-only">Загрузка</span>'; setTimeout(() => { btn.innerHTML = t; done(); }, 650); }

/* =========================================================
   App shell & routing
   ========================================================= */
function renderApp() {
  applyTheme();
  if (!S.user) { renderOnboarding(); return; }
  const app = $('#app');
  if (!$('#shell')) {
    app.innerHTML = `<div class="shell" id="shell">
      <section class="pane-list" aria-label="Разделы">
        <div class="tab-view" id="tabView"></div>
        <nav class="tabbar" id="tabbar" aria-label="Основная навигация"></nav>
      </section>
      <main class="pane-main" id="main" tabindex="-1"></main>
    </div>`;
  }
  route();
}
function parseHash() {
  const p = location.hash.replace(/^#\/?/, '').split('/');
  if (p[0] === 'chat' && chatById(p[1])) return { tab: 'chats', chat: p[1], info: p[2] === 'info' };
  if (['calls', 'contacts', 'settings'].includes(p[0])) return { tab: p[0] };
  return { tab: 'chats' };
}
function route() {
  if (!S.user) return;
  if (!$('#shell')) { renderApp(); return; }
  const prev = UI.route; const r = parseHash(); UI.route = r;
  if (prev.tab !== r.tab || !$('#tabView').innerHTML) renderTab(); else if (r.tab === 'chats') renderChatList();
  renderTabbar();
  const shell = $('#shell');
  if (r.chat) {
    const c = chatById(r.chat);
    if (prev.chat !== r.chat) UI.pendingUnread = c.unread || 0;
    const tt = $('#toast'); if (tt.dataset.chat === c.id) { tt.innerHTML = ''; tt.dataset.chat = ''; }
    if (NET.on) NET.read(c.id);
    if (c.unread) { c.unread = 0; save(); renderChatList(); renderTabbar(); }
    if (r.info) renderInfo(c); else if (prev.chat !== r.chat || prev.info || !$('#thread')) renderConversation(c);
    shell.classList.add('show-main');
    if (prev.chat !== r.chat || prev.info !== r.info) setTimeout(() => { const f = r.info ? $('#main .ph .ib') : $('#msgInput'); if (f && matchMedia('(min-width: 900px)').matches) f.focus(); else $('#main').focus({ preventScroll: true }); }, 30);
  } else {
    shell.classList.remove('show-main');
    stopVoice(); stopRec(false);
    if (matchMedia('(min-width: 900px)').matches || !$('#main').innerHTML) renderEmptyMain();
  }
}
window.addEventListener('hashchange', route);
function renderEmptyMain() {
  $('#main').innerHTML = `<div class="main-empty"><div>${LOGO}<b>Выберите чат</b><p>Или найдите друга по номеру во вкладке «Контакты»</p></div></div>`;
}
function renderTabbar() {
  const n = totalUnread(), t = UI.route.tab;
  const tab = (id, icon, label, extra = '') => `<a class="tab" href="#/${id}" ${t === id && !UI.route.chat ? 'aria-current="page"' : t === id ? 'aria-current="page"' : ''}>${ic(icon)}${extra}${label}</a>`;
  $('#tabbar').innerHTML = tab('chats', 'chat', 'Чаты', n ? `<span class="badge${n > UI.prevTotal ? ' pop' : ''}" aria-label="${n} ${plural(n, 'непрочитанный чат', 'непрочитанных чата', 'непрочитанных чатов')}">${n}</span>` : '')
    + tab('calls', 'phone', 'Звонки') + tab('contacts', 'users', 'Контакты') + tab('settings', 'settings', 'Настройки');
  UI.prevTotal = n;
}
function renderTab() {
  const v = $('#tabView'); v.scrollTop = 0;
  v.classList.remove('tab-enter'); void v.offsetWidth; v.classList.add('tab-enter');
  ({ chats: renderChatsTab, calls: renderCallsTab, contacts: renderContactsTab, settings: renderSettingsTab })[UI.route.tab]();
}

/* ---------- Chats tab ---------- */
function renderChatsTab() {
  $('#tabView').innerHTML = `
    <header class="lh"><h1>${NET.on ? NET.title() : 'Чаты'}</h1><div class="btns">
      ${NET.on ? '' : `<button class="ib soft" type="button" data-act="new-story" aria-label="Новая история">${ic('camera', 22)}</button>`}
      <a class="ib brand" href="#/contacts" aria-label="Новый чат">${ic('edit', 20)}</a></div></header>
    <div class="search" role="search">${ic('search', 20)}<label class="sr-only" for="chatSearch">Поиск по чатам</label>
      <input id="chatSearch" type="search" placeholder="Поиск по чатам и людям" autocomplete="off" value="${esc(UI.query)}">
      <button class="ib" type="button" data-act="clear-search" aria-label="Очистить поиск" ${UI.query ? '' : 'hidden'}>${ic('x', 18)}</button></div>
    ${NET.on ? '' : '<div class="stories" id="stories" aria-label="Истории"></div>'}
    <div class="chips" role="tablist" aria-label="Папки" id="chips"></div>
    <div class="list" id="chatList"></div>`;
  const s = $('#chatSearch');
  s.addEventListener('input', () => { UI.query = s.value; $('[data-act="clear-search"]').hidden = !UI.query; renderChatList(); });
  renderStories(); renderChatList();
}
function renderStories() {
  const el = $('#stories'); if (!el) return;
  const list = [...S.stories].sort((a, b) => a.seen - b.seen);
  el.innerHTML = `<button type="button" class="story" data-act="${S.myStory ? 'open-story' : 'new-story'}" data-cid="me" aria-label="${S.myStory ? 'Ваша история' : 'Добавить историю'}">
      ${S.myStory ? `<span class="ring">${av(meIni(), 'g1', 55)}</span>` : `<span class="add">${ic('plus', 24)}</span>`}<span>Вы</span></button>`
    + list.map(st => `<button type="button" class="story" data-act="open-story" data-cid="${st.cid}" aria-label="История: ${esc(person(st.cid).name)}${st.seen ? ', просмотрена' : ''}"><span class="ring${st.seen ? ' seen' : ''}">${av(person(st.cid).ini, person(st.cid).g, 55)}</span><span>${esc(person(st.cid).name.split(' ')[0])}</span></button>`).join('');
}
function renderChatList() {
  const el = $('#chatList'); if (!el) return;
  const F = [['all', 'Все', () => true], ['direct', 'Личные', c => c.type === 'direct'], ['group', 'Группы', c => c.type === 'group'], ['channel', 'Каналы', c => c.type === 'channel']];
  $('#chips').innerHTML = F.map(([id, label, fn]) => { const n = S.chats.filter(c => fn(c) && c.unread > 0).length; return `<button type="button" class="chip" role="tab" aria-selected="${UI.folder === id}" data-act="folder" data-id="${id}">${label}${n ? ` <b>${n}</b>` : ''}</button>`; }).join('');
  const fn = F.find(f => f[0] === UI.folder)[2];
  const q = UI.query.trim().toLowerCase();
  const rows = sortedChats().filter(fn).filter(c => !q || chatTitle(c).toLowerCase().includes(q) || c.messages.some(m => bodyText(m).toLowerCase().includes(q)));
  if (!rows.length) { el.innerHTML = `<div class="empty"><b>${q ? 'Ничего не найдено' : 'Здесь пока пусто'}</b>${q ? 'Попробуйте другое имя или слово' : 'Начните новый чат из контактов'}</div>`; return; }
  const before = {}; if (!RM.matches) $$('.row', el).forEach(r => { before[r.getAttribute('href')] = r.getBoundingClientRect().top; });
  el.innerHTML = rows.map(c => {
    const m = lastMsg(c), title = chatTitle(c), mine = m && m.from === 'me';
    return `<a class="row${c.pinned ? ' pinned' : ''}" href="#/chat/${c.id}" ${UI.route.chat === c.id ? 'aria-current="page"' : ''}>
      ${chatAv(c)}
      <span class="rc"><span class="r1"><span class="nm"><span>${esc(title)}</span>${c.verified ? `<span class="verified" title="Подтверждённый канал">${ic('verified', 16)}</span>` : ''}${c.muted ? `<span class="mute-i" title="Без звука">${ic('mute', 14)}</span>` : ''}</span>
        ${mine && c.type !== 'channel' ? `<span class="ok" title="${m.status === 'read' ? 'Прочитано' : m.status === 'sending' ? 'Отправляется' : 'Отправлено'}">${m.status === 'sending' ? ic('clock', 14) : ic(m.status === 'read' ? 'checks' : 'check', 16)}</span>` : ''}
        <span class="tm${c.unread ? ' new' : ''}">${m ? listTime(m.ts) : ''}</span></span>
      <span class="r2"><span class="msg">${preview(c)}</span>${c.pinned && !c.unread ? `<span class="pin-i" title="Закреплён">${ic('pin', 16)}</span>` : ''}${c.unread ? `<span class="badge${c.muted ? ' muted' : ''}${c.unread > (UI.prevUnread[c.id] || 0) ? ' pop' : ''}"><span class="sr-only">Непрочитанных: </span>${c.unread}</span>` : ''}</span></span></a>`;
  }).join('');
  S.chats.forEach(c => { UI.prevUnread[c.id] = c.unread || 0; });
  $$('.row', el).forEach(r => {
    const b0 = before[r.getAttribute('href')]; if (b0 == null) return;
    const d = b0 - r.getBoundingClientRect().top; if (!d || Math.abs(d) > 1200) return;
    r.style.transition = 'none'; r.style.transform = `translateY(${d}px)`; r.style.zIndex = d > 0 ? 1 : 0;
    requestAnimationFrame(() => { r.style.transition = 'transform 360ms var(--ease-ios), background-color 150ms'; r.style.transform = ''; setTimeout(() => { r.style.zIndex = ''; }, 380); });
  });
}

/* ---------- Calls tab ---------- */
function renderCallsTab() {
  if (NET.on) return RTC.renderCallsTab();
  const list = S.calls.filter(c => UI.callFilter === 'all' || c.dir === 'missed');
  $('#tabView').innerHTML = `<header class="lh"><h1>Звонки</h1></header>
    <div class="seg" role="radiogroup" aria-label="Фильтр звонков" style="margin-top:0">
      <button type="button" role="radio" aria-checked="${UI.callFilter === 'all'}" data-act="call-filter" data-id="all">Все</button>
      <button type="button" role="radio" aria-checked="${UI.callFilter === 'missed'}" data-act="call-filter" data-id="missed">Пропущенные</button>
      <button type="button" role="radio" aria-checked="false" data-act="call-new">${ic('plus', 16)}Новый</button></div>
    <div class="list">${list.length ? list.map(c => {
      const p = person(c.cid), miss = c.dir === 'missed';
      const label = miss ? 'Пропущенный' : (c.dir === 'in' ? 'Входящий' : 'Исходящий') + (c.dur ? ' · ' + dur(c.dur) : '');
      return `<div class="row call-row">${av(p.ini, p.g, 48)}
        <span class="rc"><span class="nm${miss ? ' miss' : ''}"><span>${esc(p.name)}</span></span>
        <span class="msg dir${miss ? ' miss' : ''}">${ic(c.dir === 'in' || miss ? 'arrowIn' : 'arrowOut', 14)}${c.video ? 'Видео · ' : ''}${label}</span></span>
        <span class="tm">${listTime(c.ts)}</span>
        <button class="ib cb" type="button" data-act="call" data-cid="${c.cid}" data-video="${c.video ? 1 : ''}" aria-label="${c.video ? 'Видеозвонок' : 'Позвонить'}: ${esc(p.name)}">${ic(c.video ? 'video' : 'phone', 22)}</button></div>`;
    }).join('') : '<div class="empty"><b>Нет пропущенных</b>Все звонки приняты</div>'}</div>`;
}

/* ---------- Contacts tab ---------- */
function renderContactsTab() {
  $('#tabView').innerHTML = `<header class="lh"><h1>Контакты</h1></header>
    <div class="search" role="search">${ic('search', 20)}<label class="sr-only" for="contactSearch">Поиск контактов</label>
      <input id="contactSearch" type="search" placeholder="${NET.on ? 'Имя или номер: +992 90 123 45 67' : 'Поиск по имени или @username'}" autocomplete="off" value="${esc(UI.contactQuery)}"></div>
    <div class="list" id="contactList"></div>`;
  const s = $('#contactSearch'); s.addEventListener('input', () => { UI.contactQuery = s.value; renderContactList(); });
  renderContactList();
}
function renderContactList() {
  const q = UI.contactQuery.trim().toLowerCase();
  const list = Object.entries(S.contacts).filter(([, p]) => !q || p.name.toLowerCase().includes(q) || (p.user && p.user.includes(q.replace('@', ''))))
    .sort((a, b) => (b[1].online - a[1].online) || a[1].name.localeCompare(b[1].name, 'ru'));
  const digits = q.replace(/[^\d+]/g, ''), phoneQ = NET.on && /^\+?\d{9,15}$/.test(digits) ? (digits.startsWith('+') ? digits : '+' + digits) : '';
  $('#contactList').innerHTML = (phoneQ ? `<button type="button" class="row" data-act="find-phone" data-phone="${esc(phoneQ)}" style="width:100%;text-align:left"><span class="av" style="--s:48px;background:var(--brand);color:#fff">${ic('search', 22)}</span><span class="rc"><span class="nm"><span>Найти ${esc(phoneQ)}</span></span><span class="msg">Открыть чат по номеру телефона</span></span></button>` : '')
    + `<button type="button" class="row" data-act="invite" style="width:100%;text-align:left"><span class="av" style="--s:48px;background:var(--brand-soft);color:var(--brand)">${ic('link', 22)}</span><span class="rc"><span class="nm" style="color:var(--brand)"><span>Пригласить друзей</span></span><span class="msg">Отправьте ссылку на Aloqa</span></span></button>
    <p class="sect">${list.length} ${plural(list.length, 'контакт', 'контакта', 'контактов')}</p>`
    + (list.length ? list.map(([id, p]) => `<button type="button" class="row" data-act="open-contact" data-cid="${id}" style="width:100%;text-align:left">${av(p.ini, p.g, 48, p.online)}
      <span class="rc"><span class="nm"><span>${esc(p.name)}</span></span><span class="msg${p.online ? ' sub-online' : ''}">${seenText(p)}</span></span></button>`).join('') : (NET.on && !q ? '<div class="empty"><b>Пока нет контактов</b>Введите номер телефона друга в поиске выше, чтобы начать чат</div>' : '<div class="empty"><b>Никого не нашли</b>' + (NET.on ? 'Введите полный номер с кодом страны' : 'Проверьте написание имени') + '</div>'));
}

/* ---------- Settings tab ---------- */
function renderSettingsTab() {
  const th = S.settings.theme;
  $('#tabView').innerHTML = `<header class="lh"><h1>Настройки</h1></header>
    <div class="card" style="margin-top:0"><div class="me-card">${av(meIni(), 'g1', 64)}<div><b>${esc(meName())}</b><small>${esc(S.user.phone)}</small></div></div>
      <button type="button" class="li" data-act="edit-name"><span class="ico" style="background:#5B4BFF">${ic('edit', 16)}</span><span class="t"><b>Изменить имя</b></span><span class="v">${ic('chevron', 18)}</span></button></div>
    <p class="sect">Оформление</p>
    <div class="seg" role="radiogroup" aria-label="Тема оформления">
      ${[['system', 'monitor', 'Система'], ['light', 'sun', 'Светлая'], ['dark', 'moon', 'Тёмная']].map(([id, i, l]) => `<button type="button" role="radio" aria-checked="${th === id}" data-act="theme" data-id="${id}">${ic(i, 16)}${l}</button>`).join('')}
    </div>
    <div class="card" style="margin-top:0;margin-bottom:12px"><button type="button" class="li" data-act="look"><span class="ico" style="background:#C026D3">${ic('image', 16)}</span><span class="t"><b>Обои, цвет и стекло</b><small>Фон чата, эффект движения, размер текста</small></span><span class="v">${ic('chevron', 18)}</span></button></div>
    <div class="card" style="margin-top:0">
      <div class="li"><span class="ico" style="background:#EF4444">${ic('bell', 16)}</span><span class="t"><b id="notifyLbl">Уведомления</b><small>Показывать новые сообщения</small></span>
        <button type="button" class="switch" role="switch" aria-checked="${S.settings.notify}" aria-labelledby="notifyLbl" data-act="toggle-notify"></button></div>
      <div class="li"><span class="ico" style="background:#2563EB">${ic('shield', 16)}</span><span class="t"><b>Защищённое соединение</b><small>HTTPS между телефоном и сервером</small></span><span class="v">Включено</span></div>
      ${NET.on ? `<div class="li"><span class="ico" style="background:#0EA5A4">${ic('monitor', 16)}</span><span class="t"><b>Сервер</b><small>${esc(location.host)} · медиа хранятся ${NET.ttl} ч</small></span><span class="v">В сети</span></div>` : `<button type="button" class="li" data-act="reset-demo"><span class="ico" style="background:#0EA5A4">${ic('chat', 16)}</span><span class="t"><b>Сбросить демо-чаты</b><small>Вернуть исходные переписки</small></span><span class="v">${ic('chevron', 18)}</span></button>`}
    </div>
    <div class="card" style="margin-bottom:24px"><button type="button" class="li danger" data-act="logout">${ic('logout', 18)}Выйти</button></div>`;
}

/* =========================================================
   Conversation
   ========================================================= */
function headerStatus(c) {
  if (UI.typing[c.id]) return `<span class="typing-t">${c.type === 'group' ? esc(firstName(UI.typing[c.id])) + ' печатает…' : 'печатает…'}</span>`;
  if (c.type === 'direct') { const p = person(c.cid); return `<span class="${p.online ? 'on' : ''}">${c.blocked ? 'заблокирован(а)' : seenText(p)}</span>`; }
  if (c.type === 'group') { const on = c.members.filter(m => person(m).online).length; return `<span>${c.members.length + 1} ${plural(c.members.length + 1, 'участник', 'участника', 'участников')}${on ? `, ${on} в сети` : ''}</span>`; }
  return `<span>${c.subs.toLocaleString('ru')} ${plural(c.subs, 'подписчик', 'подписчика', 'подписчиков')}</span>`;
}
function renderConversation(c) {
  stopVoice(); stopRec(false); UI.reply = null; UI.emoji = false; UI.attach = false;
  UI.rendered = new Set(c.messages.map(m => m.id)); UI.edit = null;
  const nU = UI.pendingUnread || 0; UI.pendingUnread = 0;
  UI.unreadFrom = nU && nU < c.messages.length ? c.messages[c.messages.length - nU].id : null;
  const direct = c.type === 'direct';
  $('#main').innerHTML = `<div class="conv${lookClass()}">
    <header class="ch">
      <a class="ib only-mobile" href="#/chats" aria-label="Назад к чатам">${ic('back', 26)}</a>
      <a class="who" href="#/chat/${c.id}/info" aria-label="Информация: ${esc(chatTitle(c))}">${chatAv(c, 40)}<div><b>${esc(chatTitle(c))}</b><span id="convStatus">${headerStatus(c)}</span></div></a>
      ${direct ? `<button class="ib" type="button" data-act="call" data-cid="${c.cid}" data-video="1" aria-label="Видеозвонок">${ic('video')}</button>
      <button class="ib" type="button" data-act="call" data-cid="${c.cid}" aria-label="Аудиозвонок">${ic('phone', 22)}</button>` : `<a class="ib" href="#/chat/${c.id}/info" aria-label="Информация">${ic('info', 22)}</a>`}
    </header>
    <div class="thread-box"><div class="wall" id="wall" aria-hidden="true"></div><div class="thread" id="thread"><div class="thread-in" role="log" aria-live="polite" aria-relevant="additions" id="threadIn"></div></div>
    <button type="button" class="fab-down" id="fabDown" data-act="to-bottom" aria-label="Прокрутить к последним сообщениям" hidden>${ic('chevronDown', 24)}<span class="badge" id="fabCount" hidden></span></button></div>
    <div id="composerWrap"></div></div>`;
  UI.fabNew = 0;
  renderThread(c, true); renderComposer(c); afterConvRender();
  const th = $('#thread');
  th.addEventListener('scroll', () => { if (th.scrollHeight - th.scrollTop - th.clientHeight < 80) UI.fabNew = 0; updateFab(); }, { passive: true });
}
function updateFab() {
  const th = $('#thread'), f = $('#fabDown'); if (!th || !f) return;
  f.hidden = th.scrollHeight - th.scrollTop - th.clientHeight < 240;
  const cnt = $('#fabCount'); cnt.hidden = !UI.fabNew; cnt.textContent = UI.fabNew;
}
function msgHTML(m, c, prev, next) {
  const out = m.from === 'me';
  const same = (a, b) => a && b && a.from === b.from && dayStart(a.ts) === dayStart(b.ts) && Math.abs(a.ts - b.ts) < 5 * 60e3;
  const first = !same(prev, m), last = !same(m, next);
  const cls = ['b', out ? 'out' : 'in', first ? 'first' : '', last ? 'last' : '', m.kind === 'image' || m.kind === 'video' || m.kind === 'location' ? 'media' : '', UI.rendered.has(m.id) ? '' : 'enter'].join(' ');
  const author = c.type === 'group' && !out && first ? `<span class="author" style="color:${({ g2: '#E23E6B', g3: '#0E8F8E', g5: '#2563EB', g4: '#D9630B', g6: '#B21FC3', g7: '#15803D' })[person(m.from).g] || 'var(--brand)'}">${esc(person(m.from).name)}</span>` : '';
  const st = out && c.type !== 'channel' ? `<span class="sr-only">${m.status === 'read' ? 'Прочитано' : m.status === 'sending' ? 'Отправляется' : 'Отправлено'}</span>${m.status === 'sending' ? ic('clock', 13) : ic(m.status === 'read' ? 'checks' : 'check', 15)}` : '';
  const meta = `<span class="mt">${m.edited ? '<span class="ed">изм.</span>' : ''}${hhmm(m.ts)}${st}</span>`;
  const q = m.reply ? `<span class="q"${m.reply.id ? ` data-act="goto" data-id="${m.reply.id}" role="link"` : ''}><b>${esc(m.reply.author)}</b><span>${esc(m.reply.text)}</span></span>` : '';
  const fw = m.fwd ? `<span class="fwd">${ic('send', 12)}Переслано от <b>${esc(m.fwd)}</b></span>` : '';
  let body;
  if (m.kind === 'image' || m.kind === 'video') {
    const label = esc(bodyText(m)), M = m.media;
    const visual = !M ? `<span class="pic" role="img" aria-label="${label}" data-act="${m.kind === 'image' ? 'view' : ''}" data-id="${m.id}">${hueGrad(m.hue || 250)}</span>`
      : M.expired ? `<span class="pic expired">${ic(m.kind === 'video' ? 'video' : 'image', 28)}<small>${m.kind === 'video' ? 'Видео' : 'Фото'} удалено с сервера</small></span>`
      : m.kind === 'video' ? `<span class="pic"><video src="${esc(M.url)}" controls playsinline preload="metadata" aria-label="${label}"></video>${m.uploading ? '<span class="upl">0%</span>' : ''}</span>`
      : `<span class="pic" data-act="view" data-id="${m.id}"><img src="${esc(M.url)}" alt="${label}" loading="lazy">${m.uploading ? '<span class="upl">0%</span>' : ''}</span>`;
    body = `${author ? `<span style="padding:2px 8px 4px;display:block">${author}</span>` : ''}${visual}${m.caption ? `<span class="cap">${esc(m.caption)}${meta}</span>` : meta}`;
  }
  else if (m.kind === 'voice') {
    const n = Math.max(18, Math.min(44, Math.round(14 + m.dur * 1.1)));
    const h = resample(m.wave || waveHeights(m.id, n), n);
    if (m.media && m.media.expired) body = `${author}<span class="file"><span class="fi">${ic('mic', 22)}</span><span><b>Голосовое · ${dur(m.dur)}</b><small>Удалено с сервера</small></span></span>${meta}`;
    else body = `${author}<span class="voice" data-voice="${m.id}"><button type="button" class="play" data-act="play" data-id="${m.id}" aria-label="Воспроизвести голосовое, ${dur(m.dur)}">${ic('play', 18)}</button><span style="flex:1"><span class="wave">${h.map(x => `<i style="height:${x}px"></i>`).join('')}</span><small>${dur(m.dur)}</small></span></span>${meta}`;
  } else if (m.kind === 'file') {
    const M = m.media, inner = `<span class="fi">${ic('file', 22)}</span><span><b>${esc(m.name)}</b><small>${esc(m.size)}${M && M.expired ? ' · удалён с сервера' : m.uploading ? ' · загрузка <span class="upl-t upl">0%</span>' : ''}</small></span>`;
    body = `${author}${M && !M.expired && !m.uploading ? `<a class="file" href="${esc(M.url)}" download="${esc(m.name)}" target="_blank" rel="noopener">${inner}</a>` : `<span class="file">${inner}</span>`}${meta}`;
  }
  else if (m.kind === 'location') body = `${author ? `<span style="padding:2px 8px 4px;display:block">${author}</span>` : ''}<a class="loc" href="https://www.openstreetmap.org/?mlat=${m.lat}&amp;mlon=${m.lon}#map=16/${m.lat}/${m.lon}" target="_blank" rel="noopener" aria-label="Открыть на карте: ${esc(m.addr)}">${MAP}<span class="loc-t"><b>Геопозиция</b><small>${esc(m.addr)}</small></span></a>${meta}`;
  else if (m.kind === 'contact') {
    const card = m.card || {}, p = person(m.cid) || { name: card.name || 'Контакт', phone: card.phone || '', g: card.color || 'g1', ini: String(card.name || '?').split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase() };
    const go = m.cid ? `data-act="open-contact" data-cid="${m.cid}"` : `data-act="find-phone" data-phone="${esc(p.phone)}"`;
    body = `${author}<span class="cc">${av(p.ini, p.g, 44)}<span><b>${esc(p.name)}</b><small>${esc(p.phone)}</small></span></span><button type="button" class="cc-btn" ${go}>Написать</button>${meta}`;
  } else if (m.kind === 'poll') {
    const P = m.poll, total = P.opts.reduce((s, o) => s + o.v, 0), voted = P.my >= 0;
    body = `${author}<span class="poll"><b class="pq">${esc(P.q)}</b><small class="pk">${voted ? 'Вы проголосовали' : 'Опрос · выберите один вариант'}</small>${P.opts.map((o, i) => {
      const pct = total ? Math.round(o.v * 100 / total) : 0;
      return `<button type="button" class="po${voted ? ' done' : ''}${P.my === i ? ' mine' : ''}" data-act="vote" data-id="${m.id}" data-i="${i}" ${voted ? 'aria-disabled="true"' : ''}><span class="po-row"><span class="po-c">${P.my === i ? ic('check', 14) : ''}</span><span class="po-t">${esc(o.t)}</span>${voted ? `<span class="po-p">${pct}%</span>` : ''}</span>${voted ? `<span class="po-bar"><i style="width:${pct}%"></i></span>` : ''}</button>`;
    }).join('')}<small class="pk" style="margin:6px 0 0">${total} ${plural(total, 'голос', 'голоса', 'голосов')}</small></span>${meta}`;
  } else if (m.kind === 'event') {
    const E = m.event, d = new Date(E.at);
    body = `${author}<span class="ev"><span class="ev-cal" aria-hidden="true"><small>${MON_SHORT[d.getMonth()]}</small><b>${d.getDate()}</b></span><span class="ev-t"><b>${esc(E.title)}</b><small>${d.getDate()} ${MON[d.getMonth()]}, ${WD_FULL[d.getDay()]} · ${hhmm(E.at)}</small><small>${E.going} ${plural(E.going, 'идёт', 'идут', 'идут')}</small></span></span><button type="button" class="ev-btn${E.me ? ' on' : ''}" data-act="event-go" data-id="${m.id}" aria-pressed="${!!E.me}">${E.me ? ic('check', 16) + 'Вы идёте' : 'Пойду'}</button>${meta}`;
  }
  else if (m.kind === 'call') {
    const C = m.call || {}, missed = !C.dur && !out, icn = C.video ? 'video' : 'phone';
    const title = out ? (C.dur ? 'Исходящий' : C.status === 'declined' ? 'Звонок отклонён' : C.status === 'busy' ? 'Занято' : C.status === 'unavailable' ? 'Не в сети' : 'Нет ответа') + (C.dur ? (C.video ? ' видеозвонок' : ' звонок') : '')
      : C.dur ? (C.video ? 'Входящий видеозвонок' : 'Входящий звонок') : (C.video ? 'Пропущенный видеозвонок' : 'Пропущенный звонок');
    body = `<button type="button" class="callmsg${missed ? ' miss' : ''}" data-act="call" data-cid="${c.cid}" ${C.video ? 'data-video="1"' : ''} aria-label="${title}. Перезвонить"><span class="ci">${ic(icn, 20)}</span><span><b>${title}</b><small>${ic(out ? 'arrowOut' : 'arrowIn', 12)}${C.dur ? dur(C.dur) : hhmm(m.ts)}</small></span></button>${meta}`;
  }
  else body = `${author}${fw}${q}${linkify(esc(m.text)).replace(/\n/g, '<br>')}${meta}`;
  const rx = reactsHTML(m);
  if (rx) { const i = body.lastIndexOf(meta); body = body.slice(0, i) + rx + body.slice(i); }
  return `<div class="${cls}" data-mid="${m.id}" tabindex="0" aria-label="${out ? 'Вы' : esc(c.type === 'channel' ? chatTitle(c) : person(m.from).name)}, ${hhmm(m.ts)}">${body}</div>`;
}
function renderThread(c, jump) {
  const inEl = $('#threadIn'), th = $('#thread'); if (!inEl) return;
  const nearBottom = th.scrollHeight - th.scrollTop - th.clientHeight < 120;
  let anchor = null, anchorTop = 0;
  if (!jump && !RM.matches) { const all = $$('.b[data-mid]', inEl); const last = all[all.length - 1]; if (last) { anchor = last.dataset.mid; anchorTop = last.getBoundingClientRect().top; } }
  const fresh = c.messages.filter(m => !UI.rendered.has(m.id) && m.from !== 'me').length;
  let html = '', lastDay = null;
  c.messages.forEach((m, i) => {
    const d = dayStart(m.ts); if (d !== lastDay) { html += `<span class="date">${dayLabel(m.ts)}</span>`; lastDay = d; }
    if (UI.unreadFrom === m.id) html += '<div class="unread-div" id="unreadDiv"><span>Непрочитанные сообщения</span></div>';
    html += msgHTML(m, c, c.messages[i - 1], c.messages[i + 1]);
  });
  if (!c.messages.length) html = `<p class="sys">${c.type === 'direct' ? 'Напишите первое сообщение' : 'Сообщений пока нет'}</p>`;
  if (c.blocked) html += `<p class="sys">Вы заблокировали этот контакт</p>`;
  if (UI.typing[c.id]) html += `<div class="typing" aria-label="${esc(firstName(UI.typing[c.id]))} печатает"><i></i><i></i><i></i></div>`;
  inEl.innerHTML = html;
  c.messages.forEach(m => UI.rendered.add(m.id));
  if (UI.playing) paintVoice();
  const ud = jump && $('#unreadDiv');
  if (ud) th.scrollTop = Math.max(0, ud.offsetTop - 90);
  else if (jump || nearBottom) th.scrollTop = th.scrollHeight;
  else if (fresh) UI.fabNew += fresh;
  if (anchor) {
    const el = $(`.b[data-mid="${anchor}"]`, inEl);
    const d = el ? anchorTop - el.getBoundingClientRect().top : 0;
    if (d && Math.abs(d) < 700) {
      inEl.style.transition = 'none'; inEl.style.transform = `translateY(${d}px)`; void inEl.offsetHeight;
      inEl.style.transition = 'transform 320ms var(--ease-ios)'; inEl.style.transform = '';
    }
  }
  updateFab();
}
function refreshChat(id) {
  if (UI.route.chat !== id || UI.route.info) return;
  const c = chatById(id); renderThread(c); const st = $('#convStatus'); if (st) st.innerHTML = headerStatus(c);
}

/* ---------- Composer ---------- */
function renderComposer(c) {
  const w = $('#composerWrap'); if (!w) return;
  if (c.type === 'channel') { w.innerHTML = `<div class="composer-alt"><button class="btn" type="button" data-act="toggle-mute">${ic(c.muted ? 'bell' : 'mute', 20)}${c.muted ? 'Включить звук' : 'Без звука'}</button></div>`; return; }
  if (c.blocked) { w.innerHTML = `<div class="composer-alt"><button class="btn danger-t" type="button" data-act="unblock">Разблокировать</button></div>`; return; }
  w.innerHTML = `
    <div class="replybar" id="replyBar" hidden></div>
    <div class="composer" id="composer">
      <button class="ib round" type="button" data-act="attach" id="attachBtn" aria-label="Вложения" aria-expanded="false" aria-controls="attachPanel">${ic('attach', 22)}</button>
      <div class="field"><label class="sr-only" for="msgInput">Сообщение</label>
        <textarea id="msgInput" rows="1" placeholder="Сообщение" enterkeyhint="send">${esc(UI.drafts[c.id] || '')}</textarea>
        <button class="ib" type="button" data-act="emoji" aria-label="Эмодзи" aria-expanded="false" aria-controls="emojiPanel">${ic('smile', 22)}</button></div>
      <button class="ib round" type="button" data-act="att-camera" id="camBtn" aria-label="Сделать снимок">${ic('camera', 22)}</button>
      <button class="ib brand send-btn" type="button" data-act="send" id="sendBtn" aria-label="Записать голосовое">${ic('mic', 22)}</button>
    </div>
    <div class="attach-panel" id="attachPanel" hidden role="group" aria-label="Вложения">${ATT.map(([act, i, l, col]) => `<button type="button" class="att" data-act="${act}"><span class="c" style="color:${col}">${ic(i, 30)}</span>${l}</button>`).join('')}</div>
    <div class="emoji-panel" id="emojiPanel" hidden aria-label="Эмодзи">${EMOJI.map(e => `<button type="button" data-act="emoji-pick" data-e="${e}" aria-label="${e}">${e}</button>`).join('')}</div>`;
  const ta = $('#msgInput');
  const grow = () => { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 132) + 'px'; };
  ta.addEventListener('input', () => { UI.drafts[c.id] = ta.value; grow(); syncSend(); if (NET.on && ta.value) NET.typing(c.id); });
  ta.addEventListener('pointerdown', () => { if (UI.attach) closePanels(); });
  ta.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendText(); } if (e.key === 'Escape' && UI.reply) setReply(null); });
  grow(); syncSend();
}
function syncSend() {
  const b = $('#sendBtn'), ta = $('#msgInput'); if (!b || !ta) return;
  const has = ta.value.trim().length > 0, mode = has ? (UI.edit ? 'check' : 'send') : 'mic';
  const cam = $('#camBtn'); if (cam) cam.hidden = has;
  if (b.dataset.mode === mode) return;
  b.dataset.mode = mode; b.innerHTML = ic(mode, 22); b.setAttribute('aria-label', has ? (UI.edit ? 'Сохранить изменения' : 'Отправить') : 'Записать голосовое');
  b.classList.remove('pop'); void b.offsetWidth; b.classList.add('pop');
}
function setReply(m) {
  const bar = $('#replyBar'); if (!bar) return;
  const c = chatById(UI.route.chat);
  if (m) UI.edit = null;
  UI.reply = m ? { id: m.id, author: m.from === 'me' ? meName() : (c.type === 'channel' ? chatTitle(c) : person(m.from).name), text: bodyText(m) } : null;
  bar.hidden = !m;
  bar.innerHTML = m ? `${ic('reply', 20)}<div class="rb"><b>${esc(UI.reply.author)}</b><span>${esc(UI.reply.text)}</span></div><button class="ib" type="button" data-act="cancel-reply" aria-label="Отменить ответ">${ic('x', 20)}</button>` : '';
  if (m) $('#msgInput').focus();
}
function sendText() {
  if (UI.edit) return finishEdit();
  const ta = $('#msgInput'); const text = ta.value.trim(); if (!text) return;
  const c = chatById(UI.route.chat);
  addMessage(c, { from: 'me', kind: 'text', text, reply: UI.reply || undefined });
  ta.value = ''; UI.drafts[c.id] = ''; ta.style.height = 'auto'; setReply(null); syncSend(); ta.focus();
}
function addMessage(c, m) {
  if (NET.on && m.from === 'me') return NET.send(c, m);
  m.id = uid(); m.ts = Date.now(); if (m.from === 'me') m.status = 'sent';
  c.messages.push(m);
  const viewing = UI.route.chat === c.id && !UI.route.info && !document.hidden;
  if (m.from !== 'me' && !viewing) {
    c.unread = (c.unread || 0) + 1;
    if (S.settings.notify && !c.muted) { toast(`${chatAv(c, 32, false)}<span><b>${esc(chatTitle(c))}</b><br><span style="font-weight:500;opacity:.85">${esc(bodyText(m)).slice(0, 60)}</span></span>`, 'Открыть', () => { location.hash = '#/chat/' + c.id; }, 4000, true); $('#toast').dataset.chat = c.id; }
  }
  save();
  if (UI.route.chat === c.id) refreshChat(c.id);
  renderChatList(); renderTabbar();
  if (m.from === 'me') scheduleReply(c);
  if (m.from === 'me' && (m.kind === 'poll' || m.kind === 'event')) simulateReaction(c, m);
}
function scheduleReply(c) {
  if (c.type === 'channel' || c.blocked) return;
  const token = (UI.replyToken[c.id] || 0) + 1; UI.replyToken[c.id] = token;
  const who = c.type === 'direct' ? c.cid : pick(c.members);
  setTimeout(() => {
    if (UI.replyToken[c.id] !== token || c.blocked) return;
    c.messages.forEach(m => { if (m.from === 'me') m.status = 'read'; }); save();
    UI.typing[c.id] = who; refreshChat(c.id); renderChatList();
    setTimeout(() => {
      if (UI.replyToken[c.id] !== token) return;
      delete UI.typing[c.id];
      if (!c.blocked) addMessage(c, { from: who, kind: 'text', text: pick(REPLIES) }); else refreshChat(c.id);
    }, 1300 + Math.random() * 1300);
  }, 900);
}

/* ---------- Voice playback ---------- */
function findMsg(id) { for (const c of S.chats) { const m = c.messages.find(x => x.id === id); if (m) return [c, m]; } return []; }
function toggleVoice(id) {
  if (UI.playing && UI.playing.id === id) { const p = UI.playing; if (p.paused) { p.start = performance.now() - p.pos * 1000; p.paused = false; if (p.audio) p.audio.play(); loopVoice(); } else { p.paused = true; if (p.audio) p.audio.pause(); cancelAnimationFrame(p.raf); } paintVoice(); return; }
  stopVoice();
  const [, m] = findMsg(id); if (!m) return;
  UI.playing = { id, dur: m.dur, pos: 0, start: performance.now(), paused: false };
  if (m.media && m.media.url && !m.media.expired) {
    const a = new Audio(m.media.url); UI.playing.audio = a;
    a.play().catch(() => { stopVoice(); toast('Не удалось воспроизвести запись'); });
  }
  loopVoice();
}
function loopVoice() {
  const p = UI.playing; if (!p) return;
  p.pos = p.audio ? p.audio.currentTime : (performance.now() - p.start) / 1000;
  if (p.pos >= p.dur || (p.audio && p.audio.ended)) { stopVoice(); return; }
  paintVoice(); p.raf = requestAnimationFrame(loopVoice);
}
function paintVoice() {
  const p = UI.playing; if (!p) return;
  const el = $(`[data-voice="${p.id}"]`); if (!el) return;
  const bars = $$('.wave i', el), on = Math.round(bars.length * p.pos / p.dur);
  bars.forEach((b, i) => b.classList.toggle('on', i < on));
  $('small', el).textContent = dur(p.pos) + ' / ' + dur(p.dur);
  const btn = $('.play', el), want = p.paused ? 'play' : 'pause';
  if (btn.dataset.state !== want) { btn.dataset.state = want; btn.innerHTML = ic(want, 18); btn.setAttribute('aria-label', p.paused ? 'Продолжить' : 'Пауза'); }
}
function stopVoice() {
  const p = UI.playing; if (!p) return; cancelAnimationFrame(p.raf); if (p.audio) p.audio.pause(); UI.playing = null;
  const el = $(`[data-voice="${p.id}"]`); if (!el) return;
  $$('.wave i', el).forEach(b => b.classList.remove('on')); $('small', el).textContent = dur(p.dur);
  const btn = $('.play', el); btn.dataset.state = 'play'; btn.innerHTML = ic('play', 18); btn.setAttribute('aria-label', 'Воспроизвести голосовое, ' + dur(p.dur));
}

/* ---------- Voice recording (simulated) ---------- */
function startRec() {
  const wrap = $('#composerWrap'), comp = $('#composer'); if (!comp || UI.rec) return;
  closePanels();
  UI.rec = { elapsed: 0, paused: false, wave: [], lvl: .3 };
  comp.hidden = true;
  const r = document.createElement('div'); r.className = 'recwrap'; r.id = 'recWrap';
  r.innerHTML = `<div class="recpill"><span class="rdot" aria-hidden="true"></span><span class="rtime" id="recTime">0:00</span>
      <span class="livewave" id="liveWave" aria-hidden="true">${'<i class="d"></i>'.repeat(46)}</span></div>
    <div class="recrow">
      <button type="button" class="rbtn del" data-act="rec-delete" aria-label="Удалить запись">${ic('trash', 24)}</button>
      <button type="button" class="rbtn pause" data-act="rec-pause" aria-label="Пауза" aria-pressed="false">${ic('pause', 22)}</button>
      <button type="button" class="rbtn send" data-act="rec-send" aria-label="Отправить голосовое">${ic('send', 24)}</button></div>
    <p class="sr-only" aria-live="polite">Идёт запись голосового сообщения</p>`;
  wrap.appendChild(r);
  UI.rec.t = setInterval(recTick, 100);
  if (NET.on) NET.recStart(UI.rec);
  $('[data-act="rec-send"]', r).focus();
}
function recTick() {
  const R = UI.rec; if (!R || R.paused) return;
  R.elapsed += .1;
  const target = R.level ? R.level() : (Math.random() < .12 ? .04 : .2 + Math.random() * .8);
  R.lvl = R.lvl * .45 + target * .55; R.wave.push(R.lvl);
  const w = $('#liveWave');
  if (w) { const i = document.createElement('i'); i.style.height = Math.max(3, Math.round(R.lvl * 34)) + 'px'; w.appendChild(i); if (w.children.length > 70) w.firstElementChild.remove(); }
  const t = $('#recTime'); if (t) t.textContent = dur(R.elapsed);
}
function toggleRecPause(btn) {
  const R = UI.rec; if (!R) return; R.paused = !R.paused;
  if (R.mr && R.mr.state !== 'inactive') { if (R.paused) R.mr.pause(); else R.mr.resume(); }
  btn.innerHTML = ic(R.paused ? 'mic' : 'pause', 22);
  btn.setAttribute('aria-label', R.paused ? 'Продолжить запись' : 'Пауза'); btn.setAttribute('aria-pressed', R.paused);
  $('#recWrap').classList.toggle('paused', R.paused);
}
function stopRec(send) {
  const R = UI.rec; if (!R) return; clearInterval(R.t); UI.rec = null;
  const r = $('#recWrap'); if (r) r.remove();
  const comp = $('#composer'); if (comp) comp.hidden = false;
  const n = 28, L = R.wave.length, wave = [];
  for (let i = 0; i < n; i++) { const a = R.wave.slice(Math.floor(i * L / n), Math.floor((i + 1) * L / n)); const v = a.length ? a.reduce((s, x) => s + x, 0) / a.length : .08; wave.push(Math.round(5 + v * 23)); }
  const secs = Math.max(1, Math.round(R.elapsed));
  if (NET.on) NET.recStop(R, send, secs, wave);
  else if (send) addMessage(chatById(UI.route.chat), { from: 'me', kind: 'voice', dur: secs, wave });
  const sb = $('#sendBtn'); if (sb && UI.route.chat) sb.focus({ preventScroll: true });
}

/* ---------- Attach / emoji panels ---------- */
function closePanels() {
  const a = $('#attachPanel'), e = $('#emojiPanel'), ab = $('#attachBtn'), eb = $('[data-act="emoji"]');
  if (a) a.hidden = true; if (e) e.hidden = true; UI.emoji = false; UI.attach = false;
  if (ab) { ab.innerHTML = ic('attach', 22); ab.setAttribute('aria-expanded', 'false'); ab.setAttribute('aria-label', 'Вложения'); }
  if (eb) eb.setAttribute('aria-expanded', 'false');
  const comp = $('#composer'); if (comp) comp.classList.remove('has-panel');
}
function toggleAttach() {
  const open = !UI.attach; closePanels();
  if (!open) { $('#msgInput').focus(); return; }
  UI.attach = true; $('#attachPanel').hidden = false; $('#composer').classList.add('has-panel');
  const ab = $('#attachBtn'); ab.innerHTML = ic('keyboard', 22); ab.setAttribute('aria-expanded', 'true'); ab.setAttribute('aria-label', 'Скрыть вложения');
  $('#msgInput').blur();
  const th = $('#thread'); if (th) th.scrollTop = th.scrollHeight;
}
function toggleEmoji() {
  const open = !UI.emoji; closePanels();
  if (!open) { $('#msgInput').focus(); return; }
  UI.emoji = true; $('#emojiPanel').hidden = false; $('#composer').classList.add('has-panel');
  $('[data-act="emoji"]').setAttribute('aria-expanded', 'true');
  $('#emojiPanel button').focus();
}

/* ---------- Rich messages: contact, poll, event ---------- */
function contactSheet() {
  const list = Object.entries(S.contacts).sort((a, b) => a[1].name.localeCompare(b[1].name, 'ru'));
  openSheet('Отправить контакт', `<h3>Отправить контакт</h3>${list.map(([id, p]) => `<button type="button" class="opt" data-act="pick-contact" data-cid="${id}">${av(p.ini, p.g, 40)}<span><b style="display:block">${esc(p.name)}</b><small style="color:var(--text-2);font-weight:500">${esc(p.phone)}</small></span></button>`).join('')}`);
}
function pollSheet() {
  openSheet('Новый опрос', `<h3>Новый опрос</h3>
    <label class="lbl" for="pollQ" style="margin-top:0">Вопрос</label><input class="inp" id="pollQ" maxlength="120" placeholder="Куда пойдём в субботу?">
    <span class="lbl" id="pollOL">Варианты ответа</span>
    <div id="pollOpts" role="group" aria-labelledby="pollOL" style="display:flex;flex-direction:column;gap:8px">
      <input class="inp" maxlength="60" placeholder="Вариант 1" aria-label="Вариант 1"><input class="inp" maxlength="60" placeholder="Вариант 2" aria-label="Вариант 2"></div>
    <button type="button" class="btn ghost block" id="pollAdd" style="margin-top:8px;color:var(--brand)">${ic('plus', 18)}Добавить вариант</button>
    <button type="button" class="btn primary block" id="pollGo" style="margin-top:12px" disabled>Создать опрос</button>`, sh => {
    const q = $('#pollQ', sh), box = $('#pollOpts', sh), go = $('#pollGo', sh), add = $('#pollAdd', sh);
    q.focus();
    const opts = () => $$('input', box).map(i => i.value.trim()).filter(Boolean);
    const check = () => { go.disabled = !(q.value.trim() && opts().length >= 2); add.hidden = $$('input', box).length >= 6; };
    sh.addEventListener('input', check);
    add.onclick = () => { const n = $$('input', box).length + 1; box.insertAdjacentHTML('beforeend', `<input class="inp" maxlength="60" placeholder="Вариант ${n}" aria-label="Вариант ${n}">`); box.lastElementChild.focus(); check(); };
    go.onclick = () => {
      const c = chatById(UI.route.chat); closeOverlay();
      addMessage(c, { from: 'me', kind: 'poll', poll: { q: q.value.trim(), opts: opts().map(t => ({ t, v: 0 })), my: -1 } });
    };
  });
}
function eventSheet() {
  const d = new Date(Date.now() + 864e5); const iso = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  openSheet('Новое мероприятие', `<h3>Новое мероприятие</h3>
    <label class="lbl" for="evT" style="margin-top:0">Название</label><input class="inp" id="evT" maxlength="80" placeholder="Встреча команды">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div><label class="lbl" for="evD">Дата</label><input class="inp" id="evD" type="date" value="${iso}" min="${iso.slice(0, 8)}01"></div>
      <div><label class="lbl" for="evH">Время</label><input class="inp" id="evH" type="time" value="18:00"></div></div>
    <button type="button" class="btn primary block" id="evGo" style="margin-top:16px" disabled>Создать мероприятие</button>`, sh => {
    const t = $('#evT', sh), go = $('#evGo', sh); t.focus();
    sh.addEventListener('input', () => { go.disabled = !(t.value.trim() && $('#evD', sh).value && $('#evH', sh).value); });
    go.onclick = () => {
      const [y, mo, da] = $('#evD', sh).value.split('-').map(Number), [h, mi] = $('#evH', sh).value.split(':').map(Number);
      const c = chatById(UI.route.chat); closeOverlay();
      addMessage(c, { from: 'me', kind: 'event', event: { title: t.value.trim(), at: new Date(y, mo - 1, da, h, mi).getTime(), going: 1, me: true } });
    };
  });
}
/* Simulate the other side reacting to polls and events */
function simulateReaction(c, m) {
  const people = c.type === 'direct' ? [c.cid] : c.members.slice(0, 2);
  people.forEach((p, k) => setTimeout(() => {
    if (m.kind === 'poll') m.poll.opts[Math.floor(Math.random() * m.poll.opts.length)].v++;
    else if (m.kind === 'event') m.event.going++;
    save(); refreshChat(c.id);
  }, 2600 + k * 1500));
}

/* =========================================================
   Info (profile / group / channel)
   ========================================================= */
function renderInfo(c) {
  stopVoice(); stopRec(false);
  const media = c.messages.filter(m => m.kind === 'image' || m.kind === 'file').length;
  let body;
  if (c.type === 'direct') {
    const p = person(c.cid);
    body = `<div class="hero">${av(p.ini, p.g, 104, p.online)}<h2>${esc(p.name)}</h2><p class="${p.online ? 'on' : ''}">${seenText(p)}</p></div>
      <div class="acts"><a class="act" href="#/chat/${c.id}">${ic('chat', 22)}Чат</a>
        <button type="button" class="act" data-act="call" data-cid="${c.cid}">${ic('phone', 22)}Звонок</button>
        <button type="button" class="act" data-act="call" data-cid="${c.cid}" data-video="1">${ic('video', 22)}Видео</button>
        <button type="button" class="act" data-act="toggle-mute" aria-pressed="${!!c.muted}">${ic(c.muted ? 'mute' : 'bell', 22)}${c.muted ? 'Без звука' : 'Звук'}</button></div>
      <div class="card">
        <div class="li"><span class="ico" style="background:#16A34A">${ic('phone', 16)}</span><span class="t"><b>${esc(p.phone)}</b><small>Мобильный</small></span></div>
        ${p.user ? `<button type="button" class="li" data-act="copy" data-text="@${esc(p.user)}"><span class="ico" style="background:#5B4BFF">${ic('at', 16)}</span><span class="t"><b>@${esc(p.user)}</b><small>Имя пользователя · нажмите, чтобы скопировать</small></span></button>` : ''}
        ${p.bio ? `<div class="li"><span class="ico" style="background:#EA580C">${ic('info', 16)}</span><span class="t"><b>${esc(p.bio)}</b><small>О себе</small></span></div>` : ''}
      </div>`;
  } else if (c.type === 'group') {
    body = `<div class="hero">${av(c.ini, c.g, 104)}<h2>${esc(c.title)}</h2><p>${c.members.length + 1} ${plural(c.members.length + 1, 'участник', 'участника', 'участников')}</p></div>
      <div class="acts" style="grid-template-columns:repeat(2,1fr)"><a class="act" href="#/chat/${c.id}">${ic('chat', 22)}Чат</a>
        <button type="button" class="act" data-act="toggle-mute" aria-pressed="${!!c.muted}">${ic(c.muted ? 'mute' : 'bell', 22)}${c.muted ? 'Без звука' : 'Звук'}</button></div>
      <p class="sect" style="max-width:560px;margin:0 auto">Участники</p>
      <div class="card" style="margin-top:0">
        <div class="li">${av(meIni(), 'g1', 36)}<span class="t"><b>${esc(meName())}</b><small>владелец</small></span></div>
        ${c.members.map(id => `<button type="button" class="li" data-act="open-contact" data-cid="${id}">${av(person(id).ini, person(id).g, 36, person(id).online)}<span class="t"><b>${esc(person(id).name)}</b><small class="${person(id).online ? 'sub-online' : ''}">${seenText(person(id))}</small></span></button>`).join('')}
      </div>`;
  } else {
    body = `<div class="hero">${av(c.ini, c.g, 104)}<h2>${esc(c.title)} <span class="verified" style="display:inline-block;vertical-align:-3px">${ic('verified', 22)}</span></h2><p>${c.subs.toLocaleString('ru')} ${plural(c.subs, 'подписчик', 'подписчика', 'подписчиков')}</p></div>
      <div class="card"><div class="li"><span class="ico" style="background:#5B4BFF">${ic('megaphone', 16)}</span><span class="t"><b>${esc(c.about)}</b><small>Описание</small></span></div></div>`;
  }
  $('#main').innerHTML = `<div class="conv"><div class="ph"><a class="ib" href="#/chat/${c.id}" aria-label="Назад к чату">${ic('back', 26)}</a><button class="ib" type="button" data-act="info-more" aria-label="Ещё">${ic('more', 24)}</button></div>
    <div class="scroll">${body}
      <div class="card">
        <div class="li"><span class="ico" style="background:#DC2626">${ic('bell', 16)}</span><span class="t"><b id="nLbl">Уведомления</b></span><button type="button" class="switch" role="switch" aria-labelledby="nLbl" aria-checked="${!c.muted}" data-act="toggle-mute"></button></div>
        <button type="button" class="li" data-act="look"><span class="ico" style="background:#C026D3">${ic('image', 16)}</span><span class="t"><b>Обои и оформление</b></span><span class="v">${ic('chevron', 18)}</span></button>
        <div class="li"><span class="ico" style="background:#0E8F8E">${ic('file', 16)}</span><span class="t"><b>Медиа и файлы</b></span><span class="v">${media}</span></div>
        <div class="li"><span class="ico" style="background:#2563EB">${ic('lock', 16)}</span><span class="t"><b>Защищённое соединение</b><small>HTTPS между телефоном и сервером</small></span></div>
      </div>
      ${NET.on ? '' : `<div class="card" style="margin-bottom:8px">
        <button type="button" class="li danger" data-act="clear-chat">Очистить историю</button>
        ${c.type === 'direct' ? `<button type="button" class="li danger" data-act="${c.blocked ? 'unblock' : 'block'}">${c.blocked ? 'Разблокировать' : 'Заблокировать'}</button>` : ''}
      </div>`}</div></div>`;
}

/* =========================================================
   Sheets, dialogs
   ========================================================= */
let lastFocus = null;
function openSheet(title, html, onOpen) {
  lastFocus = document.activeElement;
  $('#overlay').innerHTML = `<div class="scrim" data-act="close-overlay"></div><div class="sheet" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="grab" aria-hidden="true"></div>${html}</div>`;
  const first = $('#overlay .sheet button, #overlay .sheet textarea'); if (first) first.focus();
  if (onOpen) onOpen($('#overlay .sheet'));
}
function closeOverlay() {
  if ($('#overlay .mm')) return closeMsgMenu();
  const o = $('#overlay'); if (!o.innerHTML) return;
  $$('.scrim, .sheet, .dialog', o).forEach(e => e.classList.add('closing'));
  setTimeout(() => { o.innerHTML = ''; if (lastFocus && document.contains(lastFocus)) lastFocus.focus(); }, 170);
}
function confirmDialog({ title, text, ok, danger }) {
  return new Promise(res => {
    lastFocus = document.activeElement;
    $('#overlay').innerHTML = `<div class="scrim"></div><div class="dialog" role="alertdialog" aria-modal="true" aria-labelledby="dlgT" aria-describedby="dlgD">
      <h3 id="dlgT">${esc(title)}</h3><p id="dlgD">${esc(text)}</p>
      <div class="row-btns"><button type="button" class="btn ghost" id="dlgNo">Отмена</button><button type="button" class="btn ${danger ? 'danger' : 'primary'}" id="dlgYes">${esc(ok)}</button></div></div>`;
    const done = v => { closeOverlay(); res(v); };
    $('#dlgNo').onclick = () => done(false); $('#dlgYes').onclick = () => done(true); $('#overlay .scrim').onclick = () => done(false);
    $('#dlgNo').focus();
  });
}
function msgActions(mid) { openMsgMenu(mid); }
const STORY_G = ['g1', 'g2', 'g3', 'g4', 'g5', 'g6'];
function newStorySheet() {
  let g = 'g1';
  openSheet('Новая история', `<h3>Новая история</h3>
    <label class="sr-only" for="storyText">Текст истории</label><textarea id="storyText" maxlength="120" placeholder="Что у вас нового?"></textarea>
    <div class="swatches" role="radiogroup" aria-label="Фон">${STORY_G.map((x, i) => `<button type="button" role="radio" class="${x}" aria-checked="${i === 0}" aria-label="Фон ${i + 1}" data-g="${x}"></button>`).join('')}</div>
    <button type="button" class="btn primary block" id="storyPub" disabled>Опубликовать</button>`, sh => {
    const ta = $('#storyText', sh), b = $('#storyPub', sh);
    ta.addEventListener('input', () => { b.disabled = !ta.value.trim(); });
    $$('.swatches button', sh).forEach(s => s.onclick = () => { g = s.dataset.g; $$('.swatches button', sh).forEach(x => x.setAttribute('aria-checked', x === s)); });
    b.onclick = () => { S.myStory = { ts: Date.now(), slides: [{ text: ta.value.trim(), g }] }; save(); closeOverlay(); renderStories(); toast('История опубликована на 24 часа'); };
  });
}
/* =========================================================
   Calls
   ========================================================= */
let CALL = null;
function openCall(cid, video) {
  if (CALL) return;
  const p = person(cid); lastFocus = document.activeElement;
  CALL = { cid, video, start: null, t: null, mute: false, cam: !!video, spk: false };
  const L = $('#callLayer');
  L.innerHTML = `<div class="call ringing" role="dialog" aria-modal="true" aria-label="Звонок: ${esc(p.name)}">
    <div class="enc">${ic('lock', 14)} Звонок Aloqa</div>
    <div class="pulse">${av(p.ini, p.g, 128)}</div>
    <h2>${esc(p.name)}</h2><div class="sub" id="callSub" aria-live="polite">${video ? 'Видеовызов…' : 'Вызов…'}</div>
    <div class="ctrls">
      <button type="button" class="ctrl" data-act="call-mute" aria-pressed="false"><span class="c">${ic('micOff', 24)}</span>Микрофон</button>
      <button type="button" class="ctrl" data-act="call-cam" aria-pressed="${!video}"><span class="c">${ic('videoOff', 24)}</span>Камера</button>
      <button type="button" class="ctrl" data-act="call-spk" aria-pressed="false"><span class="c">${ic('volume', 24)}</span>Динамик</button>
    </div>
    <button type="button" class="ctrl end" data-act="call-end" aria-label="Завершить звонок"><span class="c">${ic('phone', 30)}</span></button></div>`;
  $('[data-act="call-end"]').focus();
  CALL.connect = setTimeout(() => {
    if (!CALL) return; CALL.start = Date.now(); $('.call').classList.remove('ringing');
    const tick = () => { const s = $('#callSub'); if (s && CALL) s.textContent = dur((Date.now() - CALL.start) / 1000); };
    tick(); CALL.t = setInterval(tick, 1000);
  }, 2400);
}
function endCall() {
  if (!CALL) return; clearTimeout(CALL.connect); clearInterval(CALL.t);
  const d = CALL.start ? Math.round((Date.now() - CALL.start) / 1000) : 0;
  S.calls.unshift({ id: uid(), cid: CALL.cid, dir: 'out', video: CALL.video, ts: Date.now(), dur: d }); save();
  CALL = null;
  const el = $('#callLayer .call'); if (el) el.classList.add('closing');
  setTimeout(() => { $('#callLayer').innerHTML = ''; if (lastFocus && document.contains(lastFocus)) lastFocus.focus(); }, 190);
  if (UI.route.tab === 'calls') renderCallsTab();
  toast(d ? `Звонок завершён · ${dur(d)}` : 'Звонок отменён');
}

/* =========================================================
   Stories
   ========================================================= */
function storyList() { return (S.myStory ? [{ cid: 'me', ...S.myStory, seen: true }] : []).concat([...S.stories].sort((a, b) => a.seen - b.seen)); }
function openStory(cid) {
  const list = storyList(); const i = list.findIndex(s => s.cid === cid); if (i < 0) return;
  lastFocus = document.activeElement; UI.story = { list, i, s: 0 }; showStory();
}
function showStory() {
  const st = UI.story; clearTimeout(st.t);
  const cur = st.list[st.i], sl = cur.slides[st.s], me = cur.cid === 'me';
  const name = me ? 'Ваша история' : person(cur.cid).name;
  $('#storyLayer').innerHTML = `<div class="story-view" role="dialog" aria-modal="true" aria-label="История: ${esc(name)}"><div class="sv ${sl.g}">
    <div class="bars" aria-hidden="true">${cur.slides.map((_, k) => `<i class="${k < st.s ? 'done' : k === st.s ? 'cur' : ''}"><b></b></i>`).join('')}</div>
    <div class="top">${me ? av(meIni(), 'g1', 36) : av(person(cur.cid).ini, person(cur.cid).g, 36)}<b>${esc(name)}</b><small>${listTime(cur.ts)}</small>
      <button class="ib" type="button" data-act="story-close" aria-label="Закрыть историю">${ic('x', 24)}</button></div>
    <button type="button" class="zone l" data-act="story-prev" aria-label="Предыдущая"></button><button type="button" class="zone r" data-act="story-next" aria-label="Следующая"></button>
    <div class="txt">${esc(sl.text)}</div>
    ${me ? '' : `<form class="reply" id="storyReply"><label class="sr-only" for="storyIn">Ответить на историю</label><input id="storyIn" placeholder="Написать ответ…" autocomplete="off"><button class="ib" type="submit" aria-label="Отправить ответ">${ic('send', 20)}</button></form>`}
  </div></div>`;
  $('[data-act="story-close"]').focus({ preventScroll: true });
  const sv = $('.sv'); const inp = $('#storyIn');
  if (inp) {
    inp.addEventListener('focus', () => { sv.classList.add('paused'); clearTimeout(st.t); });
    inp.addEventListener('blur', () => { sv.classList.remove('paused'); st.t = setTimeout(nextStory, 2500); });
    $('#storyReply').addEventListener('submit', e => {
      e.preventDefault(); const v = inp.value.trim(); if (!v) return;
      const c = ensureDirect(cur.cid); addMessage(c, { from: 'me', kind: 'text', text: v, reply: { author: 'История', text: sl.text } });
      closeStory(); toast('Ответ отправлен', 'Открыть чат', () => { location.hash = '#/chat/' + c.id; });
    });
  }
  st.t = setTimeout(nextStory, 5000);
}
function nextStory() {
  const st = UI.story; if (!st) return; const cur = st.list[st.i];
  if (st.s < cur.slides.length - 1) { st.s++; return showStory(); }
  markSeen(cur.cid);
  if (st.i < st.list.length - 1) { st.i++; st.s = 0; return showStory(); }
  closeStory();
}
function prevStory() { const st = UI.story; if (st.s > 0) st.s--; else if (st.i > 0) { st.i--; st.s = 0; } showStory(); }
function markSeen(cid) { const s = S.stories.find(x => x.cid === cid); if (s && !s.seen) { s.seen = true; save(); } }
function closeStory() {
  const st = UI.story; if (!st) return; clearTimeout(st.t); markSeen(st.list[st.i].cid); UI.story = null;
  const el = $('#storyLayer .story-view'); if (el) el.classList.add('closing');
  setTimeout(() => { $('#storyLayer').innerHTML = ''; renderStories(); if (lastFocus && document.contains(lastFocus)) lastFocus.focus(); }, 170);
}
function ensureDirect(cid) {
  let c = S.chats.find(x => x.type === 'direct' && x.cid === cid);
  if (!c) { c = { id: cid, type: 'direct', cid, unread: 0, messages: [] }; S.chats.push(c); save(); }
  return c;
}

/* =========================================================
   Events
   ========================================================= */
document.addEventListener('click', async e => {
  const el = e.target.closest('[data-act]'); if (!el) return;
  const a = el.dataset.act, c = UI.route.chat ? chatById(UI.route.chat) : null;
  switch (a) {
    case 'folder': UI.folder = el.dataset.id; renderChatList(); $(`.chip[data-id="${UI.folder}"]`).focus(); break;
    case 'clear-search': UI.query = ''; $('#chatSearch').value = ''; el.hidden = true; renderChatList(); $('#chatSearch').focus(); break;
    case 'new-story': newStorySheet(); break;
    case 'open-story': openStory(el.dataset.cid); break;
    case 'story-close': closeStory(); break;
    case 'story-next': nextStory(); break;
    case 'story-prev': prevStory(); break;
    case 'close-overlay': closeOverlay(); break;
    case 'call': if (NET.on) { RTC.start(el.dataset.cid, !!el.dataset.video); break; } openCall(el.dataset.cid, !!el.dataset.video); break;
    case 'call-end': endCall(); break;
    case 'call-mute': case 'call-cam': case 'call-spk': el.setAttribute('aria-pressed', el.getAttribute('aria-pressed') !== 'true'); break;
    case 'call-filter': UI.callFilter = el.dataset.id; renderCallsTab(); $(`[data-act="call-filter"][data-id="${UI.callFilter}"]`).focus(); break;
    case 'call-new': location.hash = '#/contacts'; break;
    case 'open-contact': if (NET.on) NET.openDirect(el.dataset.cid); else location.hash = '#/chat/' + ensureDirect(el.dataset.cid).id; break;
    case 'find-phone': NET.startChat(el.dataset.phone); break;
    case 'invite': copyText(NET.on ? location.origin + location.pathname : 'https://aloqa.app/invite/' + uid(), 'Ссылка-приглашение скопирована'); break;
    case 'copy': copyText(el.dataset.text, 'Скопировано'); break;
    case 'theme': S.settings.theme = el.dataset.id; save(); applyTheme(); renderSettingsTab(); $(`[data-act="theme"][data-id="${el.dataset.id}"]`).focus(); break;
    case 'toggle-notify': S.settings.notify = !S.settings.notify; save(); el.setAttribute('aria-checked', S.settings.notify); break;
    case 'edit-name': editNameSheet(); break;
    case 'reset-demo': if (await confirmDialog({ title: 'Сбросить демо-чаты?', text: 'Все переписки вернутся к исходным. Ваше имя сохранится.', ok: 'Сбросить', danger: true })) { const u = S.user, st = S.settings; S = seed(); S.user = u; S.settings = st; save(); UI.route = {}; location.hash = '#/chats'; renderApp(); toast('Демо-чаты восстановлены'); } break;
    case 'logout': if (await confirmDialog({ title: 'Выйти из Aloqa?', text: 'Переписки на этом устройстве будут удалены.', ok: 'Выйти', danger: true })) { if (NET.on) { NET.logout(); break; } try { localStorage.removeItem(KEY); } catch (err) { /* ignore */ } S = seed(); OB.step = 1; OB.phone = ''; UI.route = {}; $('#app').innerHTML = ''; history.replaceState(null, '', location.pathname); renderApp(); } break;
    // conversation
    case 'send': if ($('#msgInput').value.trim()) sendText(); else startRec(); break;
    case 'rec-delete': stopRec(false); toast('Запись удалена'); break;
    case 'rec-send': stopRec(true); break;
    case 'emoji': toggleEmoji(); break;
    case 'emoji-pick': { const ta = $('#msgInput'); const s = ta.selectionStart ?? ta.value.length; ta.value = ta.value.slice(0, s) + el.dataset.e + ta.value.slice(ta.selectionEnd ?? s); ta.dispatchEvent(new Event('input')); ta.focus(); ta.selectionStart = ta.selectionEnd = s + el.dataset.e.length; break; }
    case 'to-bottom': { const th = $('#thread'); th.scrollTo({ top: th.scrollHeight, behavior: RM.matches ? 'auto' : 'smooth' }); UI.fabNew = 0; break; }
    case 'attach': toggleAttach(); break;
    case 'att-photo': closePanels(); if (NET.on) { NET.pickFile(c, 'photo'); break; } addMessage(c, { from: 'me', kind: 'image', hue: Math.floor(Math.random() * 360) }); break;
    case 'att-camera': closePanels(); if (NET.on) { NET.pickFile(c, 'camera'); break; } addMessage(c, { from: 'me', kind: 'image', hue: Math.floor(Math.random() * 360), caption: 'Снимок с камеры' }); break;
    case 'att-location': closePanels(); addMessage(c, { from: 'me', kind: 'location', lat: 38.5598, lon: 68.7870, addr: 'Душанбе, проспект Рудаки' }); break;
    case 'att-contact': closePanels(); contactSheet(); break;
    case 'att-doc': closePanels(); if (NET.on) { NET.pickFile(c, 'doc'); break; } addMessage(c, { from: 'me', kind: 'file', name: 'Макет_Aloqa.pdf', size: '2,4 МБ' }); break;
    case 'att-poll': closePanels(); pollSheet(); break;
    case 'att-event': closePanels(); eventSheet(); break;
    case 'pick-contact': closeOverlay(); addMessage(c, { from: 'me', kind: 'contact', cid: el.dataset.cid }); break;
    case 'vote': if (NET.on) { const [ch, m] = findMsg(el.dataset.id); if (m) NET.vote(ch, m, +el.dataset.i); break; } { const [ch, m] = findMsg(el.dataset.id); if (!m || m.poll.my >= 0) break; m.poll.my = +el.dataset.i; m.poll.opts[m.poll.my].v++; save(); refreshChat(ch.id); break; }
    case 'event-go': if (NET.on) { const [ch, m] = findMsg(el.dataset.id); if (m) NET.rsvp(ch, m); break; } { const [ch, m] = findMsg(el.dataset.id); if (!m) break; m.event.me = !m.event.me; m.event.going += m.event.me ? 1 : -1; save(); refreshChat(ch.id); toast(m.event.me ? 'Вы идёте на мероприятие' : 'Участие отменено'); break; }
    case 'rec-pause': toggleRecPause(el); break;
    case 'play': toggleVoice(el.dataset.id); break;
    case 'cancel-reply': setReply(null); $('#msgInput').focus(); break;
    case 'm-reply': closeOverlay(); setTimeout(() => setReply(findMsg(el.dataset.id)[1]), 180); break;
    case 'm-copy': closeOverlay(); copyText(findMsg(el.dataset.id)[1].text, 'Текст скопирован'); break;
    case 'm-delete': {
      closeOverlay();
      if (NET.on) { const [ch, m] = findMsg(el.dataset.id); if (m) NET.del(ch, m); break; } const [ch, m] = findMsg(el.dataset.id); const idx = ch.messages.indexOf(m);
      ch.messages.splice(idx, 1); save(); refreshChat(ch.id); renderChatList();
      toast('Сообщение удалено', 'Отменить', () => { ch.messages.splice(idx, 0, m); save(); refreshChat(ch.id); renderChatList(); }, 5000);
      break;
    }
    case 'toggle-mute': c.muted = !c.muted; save(); if (NET.on) NET.mute(c); renderChatList(); renderTabbar(); if (UI.route.info) renderInfo(c); else renderComposer(c); toast(c.muted ? 'Уведомления выключены' : 'Уведомления включены'); break;
    case 'block': if (await confirmDialog({ title: `Заблокировать ${person(c.cid).name}?`, text: 'Контакт не сможет писать вам и звонить.', ok: 'Заблокировать', danger: true })) { c.blocked = true; delete UI.typing[c.id]; UI.replyToken[c.id] = -1; save(); renderInfo(c); toast('Контакт заблокирован', 'Отменить', () => { c.blocked = false; save(); route(); }); } break;
    case 'unblock': c.blocked = false; save(); if (UI.route.info) renderInfo(c); else { renderComposer(c); refreshChat(c.id); } toast('Контакт разблокирован'); break;
    case 'clear-chat': if (await confirmDialog({ title: 'Очистить историю?', text: 'Сообщения будут удалены только на этом устройстве.', ok: 'Очистить', danger: true })) { c.messages = []; save(); renderChatList(); renderInfo(c); toast('История очищена'); } break;
    case 'info-more': copyText(location.href, 'Ссылка на чат скопирована'); break;
  }
});
function copyText(t, msg) {
  const ok = () => toast(msg);
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(ok, ok); else ok();
}
function editNameSheet() {
  openSheet('Изменить имя', `<h3>Изменить имя</h3><label class="lbl" for="nameEdit" style="margin-top:0">Имя и фамилия</label>
    <input class="inp" id="nameEdit" autocomplete="name" value="${esc(meName())}"><button type="button" class="btn primary block" id="nameSave" style="margin-top:14px">Сохранить</button>`, sh => {
    const inp = $('#nameEdit', sh); inp.focus(); inp.select();
    const go = () => { const v = inp.value.trim(); if (!v) { inp.setAttribute('aria-invalid', 'true'); return; } S.user.name = v; save(); if (NET.on) NET.profile(v, S.user.bio || ''); closeOverlay(); renderSettingsTab(); toast('Имя обновлено'); };
    $('#nameSave', sh).onclick = go; inp.addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
  });
}

/* Long-press / right-click on a message opens actions */
let lp = null;
document.addEventListener('pointerdown', e => {
  const b = e.target.closest('.b'); if (!b || e.target.closest('button, a, input') || e.button !== 0) return;
  const x = e.clientX, y = e.clientY;
  lp = { b, x, y, t: setTimeout(() => { b.classList.add('pressed'); if (navigator.vibrate) navigator.vibrate(10); msgActions(b.dataset.mid); setTimeout(() => b.classList.remove('pressed'), 200); lp = null; }, 450) };
});
['pointerup', 'pointercancel'].forEach(t => document.addEventListener(t, () => { if (lp) { clearTimeout(lp.t); lp = null; } }));
document.addEventListener('pointermove', e => { if (lp && Math.hypot(e.clientX - lp.x, e.clientY - lp.y) > 10) { clearTimeout(lp.t); lp = null; } });
document.addEventListener('contextmenu', e => { const b = e.target.closest('.b'); if (b) { e.preventDefault(); msgActions(b.dataset.mid); } });

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (UI.story) return closeStory();
    if ($('#overlay').innerHTML) return closeOverlay();
    if (UI.emoji || UI.attach) { closePanels(); const ta = $('#msgInput'); if (ta) ta.focus(); return; }
  }
  if (UI.story) { if (e.key === 'ArrowRight') nextStory(); if (e.key === 'ArrowLeft') prevStory(); }
  const b = document.activeElement && document.activeElement.classList.contains('b') ? document.activeElement : null;
  if (b && (e.key === 'Enter' || e.key === 'ContextMenu')) { e.preventDefault(); msgActions(b.dataset.mid); }
});
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && UI.route.chat && !UI.route.info) { const c = chatById(UI.route.chat); if (c && c.unread) { c.unread = 0; save(); renderChatList(); renderTabbar(); } }
});

/* Keep relative times fresh */
setInterval(() => { if (!S.user) return; renderChatList(); const c = UI.route.chat && chatById(UI.route.chat); if (c && !UI.route.info) { const st = $('#convStatus'); if (st) st.innerHTML = headerStatus(c); } }, 60e3);

/* =========================================================
   Native-like gestures
   - swipe right on a conversation: go back (mobile)
   - swipe left on a message: reply
   ========================================================= */
let G = null;
document.addEventListener('pointerdown', e => {
  if (e.pointerType === 'mouse' || !e.isPrimary) return;
  if (!$('#thread') || !e.target.closest('#main .conv') || e.target.closest('input, textarea, button, a, select, .composer, .recwrap, .attach-panel, .emoji-panel, .replybar')) return;
  G = { x0: e.clientX, y0: e.clientY, t0: performance.now(), id: e.pointerId, mode: null, b: e.target.closest('.b'), dx: 0 };
}, { passive: true });
document.addEventListener('pointermove', e => {
  if (!G || e.pointerId !== G.id) return;
  const dx = e.clientX - G.x0, dy = e.clientY - G.y0; G.dx = dx;
  if (!G.mode) {
    if (Math.hypot(dx, dy) < 10) return;
    if (Math.abs(dx) < Math.abs(dy) * 1.3) { G = null; return; }
    const c = UI.route.chat && chatById(UI.route.chat);
    if (dx > 0 && isMobile() && !UI.route.info) G.mode = 'back';
    else if (dx < 0 && G.b && c && c.type !== 'channel' && !c.blocked && $('#msgInput')) G.mode = 'reply';
    else { G = null; return; }
    if (lp) { clearTimeout(lp.t); lp = null; }
    if (G.mode === 'back') $('#shell').classList.add('dragging');
    else { G.b.classList.add('dragging'); G.b.classList.remove('spring'); }
  }
  if (G.mode === 'back') {
    const W = innerWidth, x = Math.max(0, dx);
    $('#main').style.transform = `translateX(${x}px)`;
    $('.pane-list').style.transform = `translateX(${-0.28 * W + 0.28 * x}px)`;
    $('#shell').style.setProperty('--dimv', (0.22 * (1 - x / W)).toFixed(3));
  } else {
    const raw = Math.min(0, dx), x = raw < -64 ? -64 + (raw + 64) * 0.25 : raw;
    G.b.style.transform = `translateX(${x}px)`;
    let si = $('.swipe-ic', G.b);
    if (!si) { si = document.createElement('span'); si.className = 'swipe-ic'; si.innerHTML = ic('reply', 18); G.b.appendChild(si); }
    const p = Math.min(1, -x / 60); si.style.setProperty('--p', p.toFixed(2));
    const hit = p >= 1; if (hit && !G.hit && navigator.vibrate) navigator.vibrate(10);
    G.hit = hit; si.classList.toggle('hit', hit);
  }
}, { passive: true });
function endGesture(e) {
  if (!G || (e && e.pointerId !== G.id)) return;
  const g = G; G = null; if (!g.mode) return;
  if (g.mode === 'back') {
    const shell = $('#shell'), main = $('#main'), list = $('.pane-list'), W = innerWidth;
    const v = g.dx / Math.max(1, performance.now() - g.t0);
    shell.classList.remove('dragging');
    if (g.dx > W * 0.33 || (v > 0.45 && g.dx > 40)) {
      const T = 'transform 260ms var(--ease-ios)';
      main.style.transition = T; list.style.transition = T + ', opacity 260ms';
      main.style.transform = 'translateX(100%)'; list.style.transform = 'translateX(0)'; shell.style.setProperty('--dimv', '0');
      setTimeout(() => {
        location.hash = '#/chats';
        requestAnimationFrame(() => { [main, list].forEach(n => { n.style.transform = ''; n.style.transition = ''; }); shell.style.removeProperty('--dimv'); });
      }, 250);
    } else {
      main.style.transform = ''; list.style.transform = ''; shell.style.removeProperty('--dimv');
    }
  } else {
    const b = g.b, si = $('.swipe-ic', b);
    b.classList.remove('dragging'); b.classList.add('spring'); b.style.transform = '';
    if (si) { si.style.setProperty('--p', 0); setTimeout(() => si.remove(), 300); }
    setTimeout(() => b.classList.remove('spring'), 480);
    if (g.hit) { const m = findMsg(b.dataset.mid)[1]; if (m) setReply(m); }
  }
}
document.addEventListener('pointerup', endGesture);
document.addEventListener('pointercancel', endGesture);

/* Material-style ripple on tappable surfaces */
const RIPPLE = '.row, .li, .opt, .act, .tab, .chip, .po:not(.done), .ev-btn, .cc-btn, .btn, .seg button, .ib, .rbtn';
document.addEventListener('pointerdown', e => {
  if (RM.matches) return;
  const att = e.target.closest('.att');
  const t = att ? $('.c', att) : e.target.closest(RIPPLE);
  if (!t || t.disabled || t.closest('.call, .sv')) return;
  const r = t.getBoundingClientRect(), size = Math.max(r.width, r.height) * 2.2;
  const s = document.createElement('span'); s.className = 'ripple';
  s.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX - r.left - size / 2}px;top:${e.clientY - r.top - size / 2}px`;
  t.classList.add('rp'); t.appendChild(s); setTimeout(() => s.remove(), 600);
}, { passive: true });

/* Drag a bottom sheet down to dismiss it */
document.addEventListener('pointerdown', e => {
  const sh = e.target.closest('.sheet'); if (!sh || !e.target.closest('.grab, h3')) return;
  const y0 = e.clientY, t0 = performance.now(); let dy = 0;
  const move = ev => { dy = Math.max(0, ev.clientY - y0); sh.style.transition = 'none'; sh.style.animation = 'none'; sh.style.transform = `translateY(${dy}px)`; };
  const up = () => {
    removeEventListener('pointermove', move); removeEventListener('pointerup', up); removeEventListener('pointercancel', up);
    const v = dy / Math.max(1, performance.now() - t0);
    if (dy > 110 || (v > 0.6 && dy > 30)) {
      sh.style.transition = 'transform 220ms var(--ease-in)'; sh.style.transform = 'translateY(110%)';
      const sc = $('#overlay .scrim'); if (sc) sc.classList.add('closing');
      setTimeout(() => { $('#overlay').innerHTML = ''; if (lastFocus && document.contains(lastFocus)) lastFocus.focus(); }, 220);
    } else { sh.style.transition = 'transform 420ms var(--ease-spring)'; sh.style.transform = ''; }
  };
  addEventListener('pointermove', move); addEventListener('pointerup', up); addEventListener('pointercancel', up);
});

/* Installable app (PWA) */
if ('serviceWorker' in navigator && location.protocol === 'https:') {
  try { navigator.serviceWorker.register('sw.js').catch(() => {}); } catch (e) { /* not allowed in this context */ }
}

function boot() { if (window.NETBOOT) window.NETBOOT(); else renderApp(); }
