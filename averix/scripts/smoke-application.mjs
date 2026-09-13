// Анкета исполнителя: три коротких шага, работа и заявка.
//
// Проверяется то, ради чего её переделывали: шагов немного и видно, где ты;
// переход назад ничего не теряет; без единой работы заявку отправить нельзя;
// после отправки анкеты нет в каталоге, зато она есть у администратора, а
// исполнитель видит «Заявка на рассмотрении».
//
//   AVERIX_SMOKE_URL=http://localhost:3100 node scripts/smoke-application.mjs

import { chromium } from 'playwright';
import { execSync } from 'node:child_process';

const BASE = process.env.AVERIX_SMOKE_URL ?? 'http://localhost:3100';
const PSQL = process.env.AVERIX_SMOKE_PSQL ?? '-d "postgres://postgres@/averix_smoke4?host=/var/run/postgresql&sslmode=disable"';
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
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: 'ru-RU' });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

const stamp = Date.now();
const dev = { name: 'Динара Юсупова', user: 'dinara' + (stamp % 100000), email: `a${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };

// ── Регистрация и выбор роли ────────────────────────────────────────────────

await page.goto(`${BASE}/register`, { waitUntil: 'networkidle' });
await page.getByLabel('Имя и фамилия').fill(dev.name);
await page.getByLabel('Имя пользователя').fill(dev.user);
await page.getByLabel('Электронная почта').fill(dev.email);
await page.getByLabel('Пароль').fill(dev.pass);
await page.locator('input[type=checkbox]').check();
await page.getByRole('button', { name: 'Создать аккаунт' }).click();
await page.waitForURL(/welcome/, { timeout: 20000 });
await page.getByRole('button', { name: /Я хочу работать и зарабатывать/ }).click();
await page.waitForURL(/onboarding/, { timeout: 20000 });
sql(`UPDATE users SET email_verified_at = now() WHERE email = '${dev.email}'`);

// ── Шаг 1 ───────────────────────────────────────────────────────────────────

await page.waitForSelector('text=Шаг 1 из 4', { timeout: 15000 });
step('анкета показывает четыре шага, а не девять', true);
step('на экране виден индикатор прогресса', (await page.locator('ol li').count()) >= 4);

await page.getByLabel('Код страны').fill('UZ');
await page.getByLabel('Город').fill('Ташкент');
const designer = page.locator('button', { hasText: 'Графический дизайнер' }).first();
if (await designer.count()) await designer.click();
else await page.locator('button:has-text("Бэкенд-разработчик")').first().click();
await page.getByLabel('Как вас представить').fill('Логотипы и фирменный стиль');
await page.getByRole('button', { name: 'Далее' }).click();

// ── Шаг 2 ───────────────────────────────────────────────────────────────────

await page.waitForSelector('text=Шаг 2 из 4', { timeout: 15000 });
step('второй шаг — про умения', (await page.locator('text=Навыки и инструменты').count()) > 0);

await page.getByLabel('Найти навык').fill('Figma');
await page.waitForTimeout(1200);
const chip = page.locator('button[aria-pressed]', { hasText: /Figma/i }).first();
if (await chip.count()) await chip.click();
await page.getByLabel('Ставка за час').fill('1500');
await page.getByLabel('О себе').fill(
  'Рисую логотипы и фирменные стили для небольших компаний уже семь лет: кофейни, ' +
  'частные клиники, локальные производства. Начинаю с разговора о том, кому вы продаёте ' +
  'и чем отличаетесь, и только потом берусь за эскизы. Отдаю исходники и короткий гайд.',
);

// Назад и снова вперёд — ничего не должно потеряться.
await page.getByRole('button', { name: 'Назад' }).click();
await page.waitForSelector('text=Шаг 1 из 4', { timeout: 15000 });
step('шаг назад возвращает сохранённые данные', (await page.getByLabel('Город').inputValue()) === 'Ташкент');
await page.getByRole('button', { name: 'Далее' }).click();
await page.waitForSelector('text=Шаг 2 из 4', { timeout: 15000 });
const bioKept = (await page.getByLabel('О себе').inputValue()).length > 100;
step('введённое на втором шаге тоже на месте', bioKept);

await page.getByRole('button', { name: 'Далее' }).click();

// ── Шаг 3: работы ───────────────────────────────────────────────────────────

await page.waitForSelector('text=Шаг 3 из 4', { timeout: 15000 });
step('третий шаг — работы', (await page.locator('text=Нужна хотя бы одна работа').count()) > 0);
step('без работы дальше не пускают', await page.getByRole('button', { name: 'Далее' }).isDisabled());

await page.getByRole('button', { name: 'Добавить работу' }).click();
await page.getByLabel('Что вы сделали').fill('Логотип и вывеска для кофейни «Зерно»');
await page.getByLabel('Направление').selectOption({ index: 1 });
await page.getByLabel('Коротко, одной строкой').fill('Логотип, вывеска и стаканы для кофейни в центре');
await page.getByLabel('Что именно вы делали').fill(
  'Сделала логотип, вывеску и оформление стаканов для кофейни на 20 посадочных мест. ' +
  'Начали с разговора о гостях и районе, потом три направления эскизов, дальше отрисовка.',
);
await page.getByLabel('Ссылка на работу').fill('https://example.org/zerno');
await page.getByRole('button', { name: 'Сохранить работу' }).click();
await page.waitForTimeout(2000);

const userID = sql(`SELECT id FROM users WHERE email = '${dev.email}'`);
step('работа сохранена и опубликована',
  sql(`SELECT count(*) FROM portfolio_projects WHERE developer_id = '${userID}' AND is_published`) === '1');
step('после работы кнопка «Далее» открылась', !(await page.getByRole('button', { name: 'Далее' }).isDisabled()));
await page.getByRole('button', { name: 'Далее' }).click();

// ── Шаг 4: сводка и заявка ──────────────────────────────────────────────────

await page.waitForSelector('text=Шаг 4 из 4', { timeout: 15000 });
const summary = await page.locator('body').innerText();
step('сводка показывает введённое', /Ташкент/.test(summary) && /Логотипы и фирменный стиль/.test(summary),
  summary.replace(/\n/g, ' | ').slice(0, 160));
step('на сводке есть кнопка отправки', (await page.getByRole('button', { name: 'Отправить заявку' }).count()) === 1);

await page.getByRole('button', { name: 'Отправить заявку' }).click();
await page.waitForSelector('text=Заявка на рассмотрении', { timeout: 20000 });
step('после отправки показан статус «Заявка на рассмотрении»', true);

step('анкета не опубликована до решения',
  sql(`SELECT is_searchable FROM developer_profiles WHERE user_id = '${userID}'`) === 'f');
step('состояние анкеты — на рассмотрении',
  sql(`SELECT moderation_state FROM developer_profiles WHERE user_id = '${userID}'`) === 'pending');
step('заявка попала в очередь администратора',
  sql(`SELECT count(*) FROM moderation_queue WHERE subject_type = 'developer_profile' AND subject_id = '${userID}' AND status IN ('pending','escalated')`) === '1');
step('исполнителю ушло уведомление об отправке',
  sql(`SELECT count(*) FROM notifications WHERE user_id = '${userID}' AND type = 'profile_submitted'`) === '1');

// В каталоге исполнителей его пока нет.
await page.goto(`${BASE}/freelancers`, { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
step('в каталоге его пока нет', !(await page.locator('body').innerText()).includes(dev.name));

// ── Решение администратора ──────────────────────────────────────────────────

const admin = { name: 'Админ Петров', user: 'admin' + (stamp % 100000), email: `adm${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };
const adminPage = await ctx.browser().newContext({ viewport: { width: 390, height: 844 }, locale: 'ru-RU' }).then((c) => c.newPage());
await adminPage.goto(`${BASE}/register`, { waitUntil: 'networkidle' });
await adminPage.getByLabel('Имя и фамилия').fill(admin.name);
await adminPage.getByLabel('Имя пользователя').fill(admin.user);
await adminPage.getByLabel('Электронная почта').fill(admin.email);
await adminPage.getByLabel('Пароль').fill(admin.pass);
await adminPage.locator('input[type=checkbox]').check();
await adminPage.getByRole('button', { name: 'Создать аккаунт' }).click();
await adminPage.waitForURL(/welcome/, { timeout: 20000 });
await adminPage.getByRole('button', { name: /Я хочу заказать услугу/ }).click();
await adminPage.waitForURL(/dashboard/, { timeout: 20000 });
sql(`INSERT INTO user_roles (user_id, role) SELECT id, 'admin' FROM users WHERE email = '${admin.email}' ON CONFLICT DO NOTHING`);
// Роль выдана в обход интерфейса, а сессия ещё «заказчик»: переключаемся так
// же, как это делает панель.
await adminPage.evaluate(async () => {
  const session = await (await fetch('/api/v1/auth/session', { credentials: 'include' })).json();
  await fetch('/api/v1/auth/role/switch', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session?.data?.csrf_token ?? '' },
    body: JSON.stringify({ role: 'admin' }),
  });
});

await adminPage.goto(`${BASE}/admin/moderation`, { waitUntil: 'networkidle' });
await adminPage.waitForTimeout(1500);
step('заявка видна администратору в модерации',
  (await adminPage.locator('body').innerText()).includes(dev.name),
  (await adminPage.locator('body').innerText()).replace(/\n/g, ' | ').slice(0, 140));

await browser.close();

console.log('');
if (fail.length) {
  console.log(`НЕ ПРОШЛО: ${fail.length}`);
  for (const f of fail) console.log('  · ' + f);
  process.exit(1);
}
console.log('Всё прошло.');
