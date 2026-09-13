// Регистрация: одна дверь для всех, вопрос о роли — следующим экраном.
//
// Проверяется то, ради чего это переделано: форма не спрашивает роль, аккаунт
// создаётся сразу, роль выбирается двумя карточками, и до этого выбора ни один
// интерфейс не открывается. Плюс обратная сторона: человек, закрывший вкладку
// на карточках, возвращается к тому же вопросу, а не к пустому кабинету.
//
//   AVERIX_SMOKE_URL=http://localhost:3100 node scripts/smoke-signup.mjs

import { chromium } from 'playwright';
import { execSync } from 'node:child_process';

const BASE = process.env.AVERIX_SMOKE_URL ?? 'http://localhost:3100';
const PSQL = process.env.AVERIX_SMOKE_PSQL ?? '-d "postgres://postgres@/averix_smoke2?host=/var/run/postgresql&sslmode=disable"';
const fail = [];

function step(name, ok, detail = '') {
  console.log(`${ok ? '✓' : '✗'} ${name}${detail ? ' — ' + detail : ''}`);
  if (!ok) fail.push(name + (detail ? ': ' + detail : ''));
}

const sql = (q) => execSync(`psql ${PSQL} -At -c "${q.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim();

execSync(`redis-cli -n ${process.env.AVERIX_SMOKE_REDIS_DB ?? 5} FLUSHDB`, { stdio: 'ignore' });

const browser = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
);

async function open() {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: 'ru-RU' });
  const page = await ctx.newPage();
  page.errors = [];
  page.on('pageerror', (e) => page.errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') page.errors.push(m.text()); });
  return page;
}

async function register(page, who) {
  await page.goto(`${BASE}/register`, { waitUntil: 'networkidle' });
  await page.getByLabel('Имя и фамилия').fill(who.name);
  await page.getByLabel('Имя пользователя').fill(who.user);
  await page.getByLabel('Электронная почта').fill(who.email);
  await page.getByLabel('Пароль').fill(who.pass);
  await page.locator('input[type=checkbox]').check();
  await page.getByRole('button', { name: 'Создать аккаунт' }).click();
  await page.waitForURL(/welcome/, { timeout: 20000 });
}

const stamp = Date.now();
const worker = { name: 'Азиза Каримова', user: 'aziza' + (stamp % 100000), email: `w${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };
const buyer = { name: 'Руслан Ким', user: 'ruslan' + (stamp % 100000), email: `b${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };

// ── 1. Главная: одна дверь ──────────────────────────────────────────────────

const page = await open();
await page.goto(BASE, { waitUntil: 'networkidle' });
step('на главной одна кнопка регистрации, а не две по ролям',
  (await page.getByRole('link', { name: 'Создать аккаунт' }).count()) === 1 &&
  (await page.getByRole('link', { name: 'Стать исполнителем' }).count()) === 0);

// ── 2. Форма регистрации ────────────────────────────────────────────────────

await page.goto(`${BASE}/register`, { waitUntil: 'networkidle' });
const body = await page.locator('form').innerText();
step('форма не спрашивает роль', !/Выполнять заказы|Заказать работу/.test(body));
step('форма не спрашивает документы и телефон', !/паспорт|документ|телефон/i.test(body), body.replace(/\n/g, ' ').slice(0, 90));
step('кнопки Google нет, пока она не настроена', (await page.getByRole('link', { name: /Google/ }).count()) === 0);

// ── 3. Аккаунт создаётся и сразу спрашивают, кто он ─────────────────────────

await register(page, worker);
step('после регистрации — экран выбора', page.url().includes('/welcome'), page.url());
await page.waitForSelector('text=Что вас сюда привело', { timeout: 15000 });

const cards = await page.locator('button', { hasText: 'Я хочу' }).count();
step('на экране ровно две карточки', cards === 2, `найдено ${cards}`);
step('на карточках нарисованы иконки', (await page.locator('button svg').count()) >= 2);

const workerID = sql(`SELECT id FROM users WHERE email = '${worker.email}'`);
step('аккаунт уже существует', workerID.length === 36);
step('роли у него пока нет', sql(`SELECT count(*) FROM user_roles WHERE user_id = '${workerID}'`) === '0');
step('и профиля тоже нет', sql(`SELECT count(*) FROM developer_profiles WHERE user_id = '${workerID}'`) === '0');

// Попытка пройти мимо вопроса возвращает к нему же.
await page.goto(`${BASE}/feed`, { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
step('мимо выбора пройти нельзя', page.url().includes('/welcome'), page.url());

// ── 4. «Я хочу работать и зарабатывать» ─────────────────────────────────────

await page.getByRole('button', { name: /Я хочу работать и зарабатывать/ }).click();
await page.waitForURL(/onboarding/, { timeout: 20000 });
step('исполнитель попадает в анкету', page.url().includes('/onboarding'), page.url());
step('роль исполнителя выдана', sql(`SELECT role FROM user_roles WHERE user_id = '${workerID}'`) === 'developer');
step('анкета исполнителя создана', sql(`SELECT onboarding_step FROM developer_profiles WHERE user_id = '${workerID}'`) === '1');

// ── 5. «Я хочу заказать услугу» ─────────────────────────────────────────────

const second = await open();
await register(second, buyer);
await second.getByRole('button', { name: /Я хочу заказать услугу/ }).click();
await second.waitForURL(/dashboard/, { timeout: 20000 });
step('заказчик попадает в кабинет', second.url().includes('/dashboard'), second.url());
const buyerID = sql(`SELECT id FROM users WHERE email = '${buyer.email}'`);
step('роль заказчика выдана', sql(`SELECT role FROM user_roles WHERE user_id = '${buyerID}'`) === 'client');

// ── 6. Закрыл вкладку на вопросе — вернулся к нему ──────────────────────────

const third = await open();
const late = { name: 'Пока Думает', user: 'later' + (stamp % 100000), email: `l${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };
await register(third, late);
await third.context().clearCookies();
await third.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
await third.getByLabel('Электронная почта').fill(late.email);
await third.getByLabel('Пароль').fill(late.pass);
await third.getByRole('button', { name: 'Войти' }).click();
await third.waitForURL(/welcome/, { timeout: 20000 });
step('кто не ответил — при входе получает тот же вопрос', third.url().includes('/welcome'), third.url());

// ── 7. Ошибок в консоли нет ─────────────────────────────────────────────────

const errors = [...page.errors, ...second.errors, ...third.errors]
  .filter((e) => !e.includes('401') && !e.includes('Failed to load resource'));
step('в консоли чисто', errors.length === 0, errors.slice(0, 2).join(' | '));

await browser.close();

console.log('');
if (fail.length) {
  console.log(`НЕ ПРОШЛО: ${fail.length}`);
  for (const f of fail) console.log('  · ' + f);
  process.exit(1);
}
console.log('Всё прошло.');
