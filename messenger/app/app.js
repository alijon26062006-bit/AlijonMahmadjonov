'use strict';
/* =========================================================
   Aloqa — messenger web app (front-end prototype).
   State lives in localStorage; replies are simulated.
   ========================================================= */

const KEY = 'aloqa.v1';
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
  alert: '<circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/>'
};
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
function load() { try { const s = JSON.parse(localStorage.getItem(KEY)); return s && s.v === 1 ? s : null; } catch (e) { return null; } }
function save() { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { /* storage unavailable: keep in memory */ } }

const UI = {
  route: {}, query: '', folder: 'all', callFilter: 'all', contactQuery: '',
  typing: {}, replyToken: {}, rendered: new Set(), reply: null, emoji: false,
  playing: null, rec: null, story: null, drafts: {}
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
  return m.kind === 'voice' ? 'Голосовое сообщение · ' + dur(m.dur) : m.kind === 'image' ? (m.caption || 'Фото') : m.kind === 'file' ? m.name : m.text;
}
function bodyPreview(m) {
  if (m.kind === 'voice') return `<span class="pv brand">${ic('mic', 14)}Голосовое · ${dur(m.dur)}</span>`;
  if (m.kind === 'image') return `<span class="pv">${ic('image', 14)}${esc(m.caption || 'Фото')}</span>`;
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
function waveHeights(id, n = 28) { let x = 0; for (const ch of id) x = (x * 31 + ch.charCodeAt(0)) >>> 0; const out = []; for (let i = 0; i < n; i++) { x = (x * 1103515245 + 12345) >>> 0; out.push(5 + (x % 23)); } return out; }

/* ---------- Theme ---------- */
const darkMQ = matchMedia('(prefers-color-scheme: dark)');
function applyTheme() {
  const t = S.settings.theme === 'system' ? (darkMQ.matches ? 'dark' : 'light') : S.settings.theme;
  document.documentElement.dataset.theme = t;
  const m = $('meta[name="theme-color"]'); if (m) m.content = t === 'dark' ? '#0E1016' : '#F4F5FA';
}
darkMQ.addEventListener('change', applyTheme);

/* ---------- Toast ---------- */
let toastTimer;
function toast(html, action, onAction, ms = 3500) {
  const el = $('#toast');
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
        <p class="lead">Быстрые сообщения, звонки и истории. Сквозное шифрование для каждого чата.</p>
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
      busy($('#phoneBtn'), () => { OB.step = 2; renderOnboarding(); });
    });
  } else if (OB.step === 2) {
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
  $('#main').innerHTML = `<div class="main-empty"><div>${LOGO}<b>Выберите чат</b><p>Сообщения защищены сквозным шифрованием</p></div></div>`;
}
function renderTabbar() {
  const n = totalUnread(), t = UI.route.tab;
  const tab = (id, icon, label, extra = '') => `<a class="tab" href="#/${id}" ${t === id && !UI.route.chat ? 'aria-current="page"' : t === id ? 'aria-current="page"' : ''}>${ic(icon)}${extra}${label}</a>`;
  $('#tabbar').innerHTML = tab('chats', 'chat', 'Чаты', n ? `<span class="badge" aria-label="${n} ${plural(n, 'непрочитанный чат', 'непрочитанных чата', 'непрочитанных чатов')}">${n}</span>` : '')
    + tab('calls', 'phone', 'Звонки') + tab('contacts', 'users', 'Контакты') + tab('settings', 'settings', 'Настройки');
}
function renderTab() {
  const v = $('#tabView'); v.scrollTop = 0;
  ({ chats: renderChatsTab, calls: renderCallsTab, contacts: renderContactsTab, settings: renderSettingsTab })[UI.route.tab]();
}

/* ---------- Chats tab ---------- */
function renderChatsTab() {
  $('#tabView').innerHTML = `
    <header class="lh"><h1>Чаты</h1><div class="btns">
      <button class="ib soft" type="button" data-act="new-story" aria-label="Новая история">${ic('camera', 22)}</button>
      <a class="ib brand" href="#/contacts" aria-label="Новый чат">${ic('edit', 20)}</a></div></header>
    <div class="search" role="search">${ic('search', 20)}<label class="sr-only" for="chatSearch">Поиск по чатам</label>
      <input id="chatSearch" type="search" placeholder="Поиск по чатам и людям" autocomplete="off" value="${esc(UI.query)}">
      <button class="ib" type="button" data-act="clear-search" aria-label="Очистить поиск" ${UI.query ? '' : 'hidden'}>${ic('x', 18)}</button></div>
    <div class="stories" id="stories" aria-label="Истории"></div>
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
  el.innerHTML = rows.map(c => {
    const m = lastMsg(c), title = chatTitle(c), mine = m && m.from === 'me';
    return `<a class="row${c.pinned ? ' pinned' : ''}" href="#/chat/${c.id}" ${UI.route.chat === c.id ? 'aria-current="page"' : ''}>
      ${chatAv(c)}
      <span class="rc"><span class="r1"><span class="nm"><span>${esc(title)}</span>${c.verified ? `<span class="verified" title="Подтверждённый канал">${ic('verified', 16)}</span>` : ''}${c.muted ? `<span class="mute-i" title="Без звука">${ic('mute', 14)}</span>` : ''}</span>
        ${mine && c.type !== 'channel' ? `<span class="ok" title="${m.status === 'read' ? 'Прочитано' : 'Отправлено'}">${ic(m.status === 'read' ? 'checks' : 'check', 16)}</span>` : ''}
        <span class="tm${c.unread ? ' new' : ''}">${m ? listTime(m.ts) : ''}</span></span>
      <span class="r2"><span class="msg">${preview(c)}</span>${c.pinned && !c.unread ? `<span class="pin-i" title="Закреплён">${ic('pin', 16)}</span>` : ''}${c.unread ? `<span class="badge${c.muted ? ' muted' : ''}"><span class="sr-only">Непрочитанных: </span>${c.unread}</span>` : ''}</span></span></a>`;
  }).join('');
}

/* ---------- Calls tab ---------- */
function renderCallsTab() {
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
      <input id="contactSearch" type="search" placeholder="Поиск по имени или @username" autocomplete="off" value="${esc(UI.contactQuery)}"></div>
    <div class="list" id="contactList"></div>`;
  const s = $('#contactSearch'); s.addEventListener('input', () => { UI.contactQuery = s.value; renderContactList(); });
  renderContactList();
}
function renderContactList() {
  const q = UI.contactQuery.trim().toLowerCase();
  const list = Object.entries(S.contacts).filter(([, p]) => !q || p.name.toLowerCase().includes(q) || (p.user && p.user.includes(q.replace('@', ''))))
    .sort((a, b) => (b[1].online - a[1].online) || a[1].name.localeCompare(b[1].name, 'ru'));
  $('#contactList').innerHTML = `<button type="button" class="row" data-act="invite" style="width:100%;text-align:left"><span class="av" style="--s:48px;background:var(--brand-soft);color:var(--brand)">${ic('link', 22)}</span><span class="rc"><span class="nm" style="color:var(--brand)"><span>Пригласить друзей</span></span><span class="msg">Отправьте ссылку на Aloqa</span></span></button>
    <p class="sect">${list.length} ${plural(list.length, 'контакт', 'контакта', 'контактов')}</p>`
    + (list.length ? list.map(([id, p]) => `<button type="button" class="row" data-act="open-contact" data-cid="${id}" style="width:100%;text-align:left">${av(p.ini, p.g, 48, p.online)}
      <span class="rc"><span class="nm"><span>${esc(p.name)}</span></span><span class="msg${p.online ? ' sub-online' : ''}">${seenText(p)}</span></span></button>`).join('') : '<div class="empty"><b>Никого не нашли</b>Проверьте написание имени</div>');
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
    <div class="card" style="margin-top:0">
      <div class="li"><span class="ico" style="background:#EF4444">${ic('bell', 16)}</span><span class="t"><b id="notifyLbl">Уведомления</b><small>Показывать новые сообщения</small></span>
        <button type="button" class="switch" role="switch" aria-checked="${S.settings.notify}" aria-labelledby="notifyLbl" data-act="toggle-notify"></button></div>
      <div class="li"><span class="ico" style="background:#2563EB">${ic('shield', 16)}</span><span class="t"><b>Шифрование</b><small>Сквозное для всех личных чатов</small></span><span class="v">Включено</span></div>
      <button type="button" class="li" data-act="reset-demo"><span class="ico" style="background:#0EA5A4">${ic('chat', 16)}</span><span class="t"><b>Сбросить демо-чаты</b><small>Вернуть исходные переписки</small></span><span class="v">${ic('chevron', 18)}</span></button>
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
  stopVoice(); stopRec(false); UI.reply = null; UI.emoji = false;
  UI.rendered = new Set(c.messages.map(m => m.id));
  const direct = c.type === 'direct';
  $('#main').innerHTML = `<div class="conv">
    <header class="ch">
      <a class="ib only-mobile" href="#/chats" aria-label="Назад к чатам">${ic('back', 26)}</a>
      <a class="who" href="#/chat/${c.id}/info" aria-label="Информация: ${esc(chatTitle(c))}">${chatAv(c, 40)}<div><b>${esc(chatTitle(c))}</b><span id="convStatus">${headerStatus(c)}</span></div></a>
      ${direct ? `<button class="ib" type="button" data-act="call" data-cid="${c.cid}" data-video="1" aria-label="Видеозвонок">${ic('video')}</button>
      <button class="ib" type="button" data-act="call" data-cid="${c.cid}" aria-label="Аудиозвонок">${ic('phone', 22)}</button>` : `<a class="ib" href="#/chat/${c.id}/info" aria-label="Информация">${ic('info', 22)}</a>`}
    </header>
    <div class="thread" id="thread"><div class="thread-in" role="log" aria-live="polite" aria-relevant="additions" id="threadIn"></div></div>
    <div id="composerWrap"></div></div>`;
  renderThread(c, true); renderComposer(c);
}
function msgHTML(m, c, prev, next) {
  const out = m.from === 'me';
  const same = (a, b) => a && b && a.from === b.from && dayStart(a.ts) === dayStart(b.ts) && Math.abs(a.ts - b.ts) < 5 * 60e3;
  const first = !same(prev, m), last = !same(m, next);
  const cls = ['b', out ? 'out' : 'in', first ? 'first' : '', last ? 'last' : '', m.kind === 'image' ? 'media' : '', UI.rendered.has(m.id) ? '' : 'enter'].join(' ');
  const author = c.type === 'group' && !out && first ? `<span class="author" style="color:${({ g2: '#E23E6B', g3: '#0E8F8E', g5: '#2563EB', g4: '#D9630B', g6: '#B21FC3', g7: '#15803D' })[person(m.from).g] || 'var(--brand)'}">${esc(person(m.from).name)}</span>` : '';
  const st = out && c.type !== 'channel' ? `<span class="sr-only">${m.status === 'read' ? 'Прочитано' : 'Отправлено'}</span>${ic(m.status === 'read' ? 'checks' : 'check', 15)}` : '';
  const meta = `<span class="mt">${hhmm(m.ts)}${st}</span>`;
  const q = m.reply ? `<span class="q"><b>${esc(m.reply.author)}</b><span>${esc(m.reply.text)}</span></span>` : '';
  let body;
  if (m.kind === 'image') body = `${author ? `<span style="padding:2px 8px 4px;display:block">${author}</span>` : ''}<span class="pic" role="img" aria-label="${esc(m.caption || 'Фото')}">${hueGrad(m.hue || 250)}</span>${m.caption ? `<span class="cap">${esc(m.caption)}${meta}</span>` : meta}`;
  else if (m.kind === 'voice') {
    const h = waveHeights(m.id);
    body = `${author}<span class="voice" data-voice="${m.id}"><button type="button" class="play" data-act="play" data-id="${m.id}" aria-label="Воспроизвести голосовое, ${dur(m.dur)}">${ic('play', 18)}</button><span style="flex:1"><span class="wave">${h.map(x => `<i style="height:${x}px"></i>`).join('')}</span><small>${dur(m.dur)}</small></span></span>${meta}`;
  } else if (m.kind === 'file') body = `${author}<span class="file"><span class="fi">${ic('file', 22)}</span><span><b>${esc(m.name)}</b><small>${esc(m.size)}</small></span></span>${meta}`;
  else body = `${author}${q}${esc(m.text).replace(/\n/g, '<br>')}${meta}`;
  return `<div class="${cls}" data-mid="${m.id}" tabindex="0" aria-label="${out ? 'Вы' : esc(c.type === 'channel' ? chatTitle(c) : person(m.from).name)}, ${hhmm(m.ts)}">${body}</div>`;
}
function renderThread(c, jump) {
  const inEl = $('#threadIn'), th = $('#thread'); if (!inEl) return;
  const nearBottom = th.scrollHeight - th.scrollTop - th.clientHeight < 120;
  let html = '', lastDay = null;
  c.messages.forEach((m, i) => {
    const d = dayStart(m.ts); if (d !== lastDay) { html += `<span class="date">${dayLabel(m.ts)}</span>`; lastDay = d; }
    html += msgHTML(m, c, c.messages[i - 1], c.messages[i + 1]);
  });
  if (!c.messages.length) html = `<p class="sys">${c.type === 'direct' ? 'Напишите первое сообщение — оно будет зашифровано' : 'Сообщений пока нет'}</p>`;
  if (c.blocked) html += `<p class="sys">Вы заблокировали этот контакт</p>`;
  if (UI.typing[c.id]) html += `<div class="typing" aria-label="${esc(firstName(UI.typing[c.id]))} печатает"><i></i><i></i><i></i></div>`;
  inEl.innerHTML = html;
  c.messages.forEach(m => UI.rendered.add(m.id));
  if (UI.playing) paintVoice();
  if (jump || nearBottom) th.scrollTop = th.scrollHeight;
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
    <div class="emoji-panel" id="emojiPanel" hidden aria-label="Эмодзи">${EMOJI.map(e => `<button type="button" data-act="emoji-pick" data-e="${e}" aria-label="${e}">${e}</button>`).join('')}</div>
    <div class="composer" id="composer">
      <button class="ib" type="button" data-act="attach" aria-label="Прикрепить файл или фото">${ic('attach', 22)}</button>
      <div class="field"><label class="sr-only" for="msgInput">Сообщение</label>
        <textarea id="msgInput" rows="1" placeholder="Сообщение" enterkeyhint="send">${esc(UI.drafts[c.id] || '')}</textarea>
        <button class="ib" type="button" data-act="emoji" aria-label="Эмодзи" aria-expanded="false" aria-controls="emojiPanel">${ic('smile', 22)}</button></div>
      <button class="ib brand send-btn" type="button" data-act="send" id="sendBtn" aria-label="Записать голосовое">${ic('mic', 22)}</button>
    </div>`;
  const ta = $('#msgInput');
  const grow = () => { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 132) + 'px'; };
  ta.addEventListener('input', () => { UI.drafts[c.id] = ta.value; grow(); syncSend(); });
  ta.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendText(); } if (e.key === 'Escape' && UI.reply) setReply(null); });
  grow(); syncSend();
}
function syncSend() {
  const b = $('#sendBtn'), ta = $('#msgInput'); if (!b || !ta) return;
  const has = ta.value.trim().length > 0, mode = has ? 'send' : 'mic';
  if (b.dataset.mode === mode) return;
  b.dataset.mode = mode; b.innerHTML = ic(mode, 22); b.setAttribute('aria-label', has ? 'Отправить' : 'Записать голосовое');
  b.classList.remove('pop'); void b.offsetWidth; b.classList.add('pop');
}
function setReply(m) {
  const bar = $('#replyBar'); if (!bar) return;
  const c = chatById(UI.route.chat);
  UI.reply = m ? { author: m.from === 'me' ? meName() : (c.type === 'channel' ? chatTitle(c) : person(m.from).name), text: bodyText(m) } : null;
  bar.hidden = !m;
  bar.innerHTML = m ? `${ic('reply', 20)}<div class="rb"><b>${esc(UI.reply.author)}</b><span>${esc(UI.reply.text)}</span></div><button class="ib" type="button" data-act="cancel-reply" aria-label="Отменить ответ">${ic('x', 20)}</button>` : '';
  if (m) $('#msgInput').focus();
}
function sendText() {
  const ta = $('#msgInput'); const text = ta.value.trim(); if (!text) return;
  const c = chatById(UI.route.chat);
  addMessage(c, { from: 'me', kind: 'text', text, reply: UI.reply || undefined });
  ta.value = ''; UI.drafts[c.id] = ''; ta.style.height = 'auto'; setReply(null); syncSend(); ta.focus();
}
function addMessage(c, m) {
  m.id = uid(); m.ts = Date.now(); if (m.from === 'me') m.status = 'sent';
  c.messages.push(m);
  const viewing = UI.route.chat === c.id && !UI.route.info && !document.hidden;
  if (m.from !== 'me' && !viewing) {
    c.unread = (c.unread || 0) + 1;
    if (S.settings.notify && !c.muted) toast(`${chatAv(c, 32, false)}<span><b>${esc(chatTitle(c))}</b><br><span style="font-weight:500;opacity:.85">${esc(bodyText(m)).slice(0, 60)}</span></span>`, 'Открыть', () => { location.hash = '#/chat/' + c.id; }, 4000);
  }
  save();
  if (UI.route.chat === c.id) refreshChat(c.id);
  renderChatList(); renderTabbar();
  if (m.from === 'me') scheduleReply(c);
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
  if (UI.playing && UI.playing.id === id) { const p = UI.playing; if (p.paused) { p.start = performance.now() - p.pos * 1000; p.paused = false; loopVoice(); } else { p.paused = true; cancelAnimationFrame(p.raf); } paintVoice(); return; }
  stopVoice();
  const [, m] = findMsg(id); if (!m) return;
  UI.playing = { id, dur: m.dur, pos: 0, start: performance.now(), paused: false }; loopVoice();
}
function loopVoice() {
  const p = UI.playing; if (!p) return;
  p.pos = (performance.now() - p.start) / 1000;
  if (p.pos >= p.dur) { stopVoice(); return; }
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
  const p = UI.playing; if (!p) return; cancelAnimationFrame(p.raf); UI.playing = null;
  const el = $(`[data-voice="${p.id}"]`); if (!el) return;
  $$('.wave i', el).forEach(b => b.classList.remove('on')); $('small', el).textContent = dur(p.dur);
  const btn = $('.play', el); btn.dataset.state = 'play'; btn.innerHTML = ic('play', 18); btn.setAttribute('aria-label', 'Воспроизвести голосовое, ' + dur(p.dur));
}

/* ---------- Voice recording (simulated) ---------- */
function startRec() {
  const comp = $('#composer'); if (!comp || UI.rec) return;
  UI.rec = { start: Date.now() };
  comp.dataset.html = comp.innerHTML;
  comp.innerHTML = `<div class="recbar"><span class="rdot" aria-hidden="true"></span><span id="recTime" aria-live="off">0:00</span><span class="lbl">Идёт запись…</span>
    <button type="button" class="cancel" data-act="rec-cancel">Отмена</button></div>
    <button class="ib brand" type="button" data-act="rec-send" aria-label="Отправить голосовое">${ic('send', 22)}</button>`;
  UI.rec.t = setInterval(() => { const e = $('#recTime'); if (e) e.textContent = dur((Date.now() - UI.rec.start) / 1000); }, 250);
  $('[data-act="rec-send"]').focus();
}
function stopRec(send) {
  if (!UI.rec) return; clearInterval(UI.rec.t);
  const secs = Math.max(1, Math.round((Date.now() - UI.rec.start) / 1000)); UI.rec = null;
  const comp = $('#composer');
  if (comp && comp.dataset.html) {
    const c = chatById(UI.route.chat); renderComposer(c);
  }
  if (send) addMessage(chatById(UI.route.chat), { from: 'me', kind: 'voice', dur: secs });
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
        <div class="li"><span class="ico" style="background:#0E8F8E">${ic('image', 16)}</span><span class="t"><b>Медиа и файлы</b></span><span class="v">${media}</span></div>
        <div class="li"><span class="ico" style="background:#2563EB">${ic('lock', 16)}</span><span class="t"><b>Шифрование</b><small>Сообщения защищены</small></span></div>
      </div>
      <div class="card" style="margin-bottom:8px">
        <button type="button" class="li danger" data-act="clear-chat">Очистить историю</button>
        ${c.type === 'direct' ? `<button type="button" class="li danger" data-act="${c.blocked ? 'unblock' : 'block'}">${c.blocked ? 'Разблокировать' : 'Заблокировать'}</button>` : ''}
      </div></div></div>`;
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
function msgActions(mid) {
  const [c, m] = findMsg(mid); if (!m) return;
  const canReply = c.type !== 'channel' && !c.blocked;
  openSheet('Действия с сообщением', `
    ${canReply ? `<button type="button" class="opt" data-act="m-reply" data-id="${mid}"><span class="ico" style="background:#5B4BFF">${ic('reply', 20)}</span>Ответить</button>` : ''}
    ${m.kind === 'text' ? `<button type="button" class="opt" data-act="m-copy" data-id="${mid}"><span class="ico" style="background:#0E8F8E">${ic('copy', 20)}</span>Копировать</button>` : ''}
    <button type="button" class="opt danger" data-act="m-delete" data-id="${mid}"><span class="ico" style="background:#DC2626">${ic('trash', 20)}</span>Удалить у меня</button>`);
}
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
function attachSheet() {
  openSheet('Прикрепить', `<h3>Прикрепить</h3>
    <button type="button" class="opt" data-act="send-photo"><span class="ico" style="background:#5B4BFF">${ic('image', 20)}</span>Фото или видео</button>
    <button type="button" class="opt" data-act="send-file"><span class="ico" style="background:#EA580C">${ic('file', 20)}</span>Файл</button>`);
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
    <div class="enc">${ic('lock', 14)} Сквозное шифрование</div>
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
    case 'call': openCall(el.dataset.cid, !!el.dataset.video); break;
    case 'call-end': endCall(); break;
    case 'call-mute': case 'call-cam': case 'call-spk': el.setAttribute('aria-pressed', el.getAttribute('aria-pressed') !== 'true'); break;
    case 'call-filter': UI.callFilter = el.dataset.id; renderCallsTab(); $(`[data-act="call-filter"][data-id="${UI.callFilter}"]`).focus(); break;
    case 'call-new': location.hash = '#/contacts'; break;
    case 'open-contact': location.hash = '#/chat/' + ensureDirect(el.dataset.cid).id; break;
    case 'invite': copyText('https://aloqa.app/invite/' + uid(), 'Ссылка-приглашение скопирована'); break;
    case 'copy': copyText(el.dataset.text, 'Скопировано'); break;
    case 'theme': S.settings.theme = el.dataset.id; save(); applyTheme(); renderSettingsTab(); $(`[data-act="theme"][data-id="${el.dataset.id}"]`).focus(); break;
    case 'toggle-notify': S.settings.notify = !S.settings.notify; save(); el.setAttribute('aria-checked', S.settings.notify); break;
    case 'edit-name': editNameSheet(); break;
    case 'reset-demo': if (await confirmDialog({ title: 'Сбросить демо-чаты?', text: 'Все переписки вернутся к исходным. Ваше имя сохранится.', ok: 'Сбросить', danger: true })) { const u = S.user, st = S.settings; S = seed(); S.user = u; S.settings = st; save(); UI.route = {}; location.hash = '#/chats'; renderApp(); toast('Демо-чаты восстановлены'); } break;
    case 'logout': if (await confirmDialog({ title: 'Выйти из Aloqa?', text: 'Переписки на этом устройстве будут удалены.', ok: 'Выйти', danger: true })) { try { localStorage.removeItem(KEY); } catch (err) { /* ignore */ } S = seed(); OB.step = 1; OB.phone = ''; UI.route = {}; $('#app').innerHTML = ''; history.replaceState(null, '', location.pathname); renderApp(); } break;
    // conversation
    case 'send': if ($('#msgInput').value.trim()) sendText(); else startRec(); break;
    case 'rec-cancel': stopRec(false); toast('Запись удалена'); break;
    case 'rec-send': stopRec(true); break;
    case 'emoji': { UI.emoji = !UI.emoji; $('#emojiPanel').hidden = !UI.emoji; el.setAttribute('aria-expanded', UI.emoji); if (UI.emoji) $('#emojiPanel button').focus(); break; }
    case 'emoji-pick': { const ta = $('#msgInput'); const s = ta.selectionStart ?? ta.value.length; ta.value = ta.value.slice(0, s) + el.dataset.e + ta.value.slice(ta.selectionEnd ?? s); ta.dispatchEvent(new Event('input')); ta.focus(); ta.selectionStart = ta.selectionEnd = s + el.dataset.e.length; break; }
    case 'attach': attachSheet(); break;
    case 'send-photo': closeOverlay(); addMessage(c, { from: 'me', kind: 'image', hue: Math.floor(Math.random() * 360) }); break;
    case 'send-file': closeOverlay(); addMessage(c, { from: 'me', kind: 'file', name: 'Макет_Aloqa.fig', size: '2,4 МБ' }); break;
    case 'play': toggleVoice(el.dataset.id); break;
    case 'cancel-reply': setReply(null); $('#msgInput').focus(); break;
    case 'm-reply': closeOverlay(); setTimeout(() => setReply(findMsg(el.dataset.id)[1]), 180); break;
    case 'm-copy': closeOverlay(); copyText(findMsg(el.dataset.id)[1].text, 'Текст скопирован'); break;
    case 'm-delete': {
      closeOverlay(); const [ch, m] = findMsg(el.dataset.id); const idx = ch.messages.indexOf(m);
      ch.messages.splice(idx, 1); save(); refreshChat(ch.id); renderChatList();
      toast('Сообщение удалено', 'Отменить', () => { ch.messages.splice(idx, 0, m); save(); refreshChat(ch.id); renderChatList(); }, 5000);
      break;
    }
    case 'toggle-mute': c.muted = !c.muted; save(); renderChatList(); renderTabbar(); if (UI.route.info) renderInfo(c); else renderComposer(c); toast(c.muted ? 'Уведомления выключены' : 'Уведомления включены'); break;
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
    const go = () => { const v = inp.value.trim(); if (!v) { inp.setAttribute('aria-invalid', 'true'); return; } S.user.name = v; save(); closeOverlay(); renderSettingsTab(); toast('Имя обновлено'); };
    $('#nameSave', sh).onclick = go; inp.addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
  });
}

/* Long-press / right-click on a message opens actions */
let lp = null;
document.addEventListener('pointerdown', e => {
  const b = e.target.closest('.b'); if (!b || e.target.closest('button') || e.button !== 0) return;
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
    if (UI.emoji) { UI.emoji = false; $('#emojiPanel').hidden = true; $('[data-act="emoji"]').setAttribute('aria-expanded', 'false'); return; }
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

renderApp();
