/* =========================================================
   НАСТРОЙКИ САЙТА — правь только этот файл
   =========================================================
   После правки просто перезалей config.js на хостинг.
   Ничего собирать не нужно.
   ========================================================= */

export const person = {
  name: 'Alijon',
  fullName: 'Alijon Mahmadjonov',
  nickname: 'Uways',
  hometown: 'Душанбе',
  basedIn: 'Казахстан',
  birthYear: 2006,
  birthMonth: 6,   // июнь
  birthDay: 26,
};

/* ---------- КОНТАКТЫ ----------
   icon — одно из: telegram | instagram | github | mail | phone
   primary: true — контакт показывается кнопкой на первом экране */
export const contacts = [
  {
    id: 'telegram',
    label: 'Telegram',
    display: '@rutsiyax',
    href: 'https://t.me/rutsiyax',
    icon: 'telegram',
    primary: true,
  },
  {
    id: 'instagram',
    label: 'Instagram',
    display: '@uways',
    href: 'https://instagram.com/uways',
    icon: 'instagram',
    primary: true,
  },
  {
    id: 'github',
    label: 'GitHub',
    display: 'alijon26062006-bit',
    href: 'https://github.com/alijon26062006-bit',
    icon: 'github',
  },
  {
    id: 'email',
    label: 'Email',
    display: 'alijon26.06.2006@gmail.com',
    href: 'mailto:alijon26.06.2006@gmail.com',
    icon: 'mail',
  },
  {
    id: 'phone',
    label: 'Телефон',
    display: '+992 000 00 00 00',      // ← ПОМЕНЯЙ НА СВОЙ
    href: 'tel:+992000000000',          // ← И ЗДЕСЬ ТОЖЕ
    icon: 'phone',
  },
];

/* ---------- КУДА УХОДИТ ЗАЯВКА ----------
   'telegram' — заявка копируется в буфер и открывается твой чат.
   'php'      — заявка уходит на php/order.php (см. инструкцию в README). */
export const orderTarget = {
  mode: 'telegram',
  telegramUser: 'rutsiyax',
  phpEndpoint: 'php/order.php',
};

/* ---------- НАВЫКИ ----------
   group: frontend | backend | tools
   tint  — цвет технологии, им подсвечивается карточка */
export const skills = [
  { name: 'JavaScript',       group: 'frontend', tint: '#F7DF1E' },
  { name: 'TypeScript',       group: 'frontend', tint: '#3178C6' },
  { name: 'React',            group: 'frontend', tint: '#61DAFB' },
  { name: 'Next.js',          group: 'frontend', tint: '#FFFFFF' },
  { name: 'HTML',             group: 'frontend', tint: '#E34F26' },
  { name: 'CSS',              group: 'frontend', tint: '#1572B6' },
  { name: 'Tailwind',         group: 'frontend', tint: '#38BDF8' },
  { name: 'PHP',              group: 'backend',  tint: '#777BB4' },
  { name: 'Node.js',          group: 'backend',  tint: '#5FA04E' },
  { name: 'Python',           group: 'backend',  tint: '#3776AB' },
  { name: 'MySQL',            group: 'backend',  tint: '#4479A1' },
  { name: 'REST API',         group: 'backend',  tint: '#5EA8FF' },
  { name: 'Telegram Bot API', group: 'backend',  tint: '#26A5E4' },
  { name: 'AI',               group: 'backend',  tint: '#C9D6E8' },
  { name: 'Git',              group: 'tools',    tint: '#F05032' },
  { name: 'GitHub',           group: 'tools',    tint: '#FFFFFF' },
  { name: 'Docker',           group: 'tools',    tint: '#2496ED' },
];

/* ---------- ПРОЕКТЫ ----------
   key   — по нему берутся название и описание из lang.js
   shape — рисунок на карточке: messenger | marketplace | bot | miniapp | ai | web
   href  — ссылка на проект. null, если показывать пока нечего */
export const projects = [
  {
    key: 'payom',
    year: '2025',
    stack: ['React', 'Node.js', 'WebSocket', 'MySQL'],
    href: null,
    shape: 'messenger',
    accent: '#2F7BFF',
  },
  {
    key: 'tajbozor',
    year: '2025',
    stack: ['Next.js', 'TypeScript', 'MySQL', 'REST API'],
    href: null,
    shape: 'marketplace',
    accent: '#38E0FF',
  },
  {
    key: 'cargo',
    year: '2025',
    stack: ['Python', 'aiogram', 'Telegram Bot API'],
    href: null,
    shape: 'bot',
    accent: '#26A5E4',
  },
  {
    key: 'miniapps',
    year: '2025 — сейчас',
    stack: ['React', 'TypeScript', 'Telegram Mini Apps'],
    href: null,
    shape: 'miniapp',
    accent: '#7C6BFF',
  },
  {
    key: 'ai',
    year: '2025 — сейчас',
    stack: ['Python', 'LLM API', 'Автоматизация'],
    href: null,
    shape: 'ai',
    accent: '#5EA8FF',
  },
  {
    key: 'websites',
    year: '2024 — сейчас',
    stack: ['JavaScript', 'Three.js', 'CSS'],
    href: null,
    shape: 'web',
    accent: '#9AB4E0',
  },
];

/* ---------- ФОНОВАЯ МУЗЫКА ----------
   Положи mp3 в папку audio/ и впиши путь, например 'audio/ambient.mp3'.
   Пустая строка — кнопка звука не показывается.
   Браузеры запрещают автозапуск, поэтому звук включается кнопкой. */
export const audio = {
  src: '',
  volume: 0.35,
};

/* ---------- ТЯЖЕСТЬ 3D-СЦЕНЫ ----------
   Если на слабом телефоне тормозит — уменьши числа. */
export const scene = {
  buildings: { desktop: 260, mobile: 90 },
  particles: { desktop: 2600, mobile: 900 },
  bloomOnDesktop: true,
};

/** Возраст считается сам — каждый год править не нужно. */
export function getAge() {
  const now = new Date();
  let age = now.getFullYear() - person.birthYear;
  const hadBirthday =
    now.getMonth() + 1 > person.birthMonth ||
    (now.getMonth() + 1 === person.birthMonth && now.getDate() >= person.birthDay);
  if (!hadBirthday) age -= 1;
  return age;
}
