// Сквозная проверка проверки личности — в браузере, на живом стеке.
//
// Здесь важно не «страница открылась», а «закрытое осталось закрытым»:
// администратор без именного разрешения не видит документов, с разрешением —
// видит только после повторного ввода пароля, ссылка на изображение живёт
// две минуты и не работает у другого сотрудника, а решение без объяснения не
// принимается. Всё это проверяется тем же путём, которым ходит человек.
//
// Запуск:
//   AVERIX_SMOKE_URL=http://localhost:3100 node scripts/smoke-identity.mjs

import { chromium } from 'playwright';
import { execSync } from 'node:child_process';
import { PNG } from './lib/png.mjs';

const BASE = process.env.AVERIX_SMOKE_URL ?? 'http://localhost:3100';
const PSQL = process.env.AVERIX_SMOKE_PSQL ?? '-d "postgres://postgres@/averix_smoke?host=/var/run/postgresql&sslmode=disable"';
const fail = [];

function step(name, ok, detail = '') {
  console.log(`${ok ? '✓' : '✗'} ${name}${detail ? ' — ' + detail : ''}`);
  if (!ok) fail.push(name + (detail ? ': ' + detail : ''));
}

function sql(query) {
  return execSync(`psql ${PSQL} -At -c "${query.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim();
}

// Лимит регистраций считается по адресу и мешает повторному прогону.
execSync(`redis-cli -n ${process.env.AVERIX_SMOKE_REDIS_DB ?? 5} FLUSHDB`, { stdio: 'ignore' });

const browser = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
);

const stamp = Date.now();
// Документы подаёт исполнитель: заказчика о них не спрашивают вовсе.
const person = { name: 'Алия Рахимова', user: 'aliya' + (stamp % 100000), email: `p${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };
const buyer = { name: 'Руслан Ким', user: 'buyer' + (stamp % 100000), email: `q${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };
const reviewer = { name: 'Сергей Волков', user: 'reviewer' + (stamp % 100000), email: `r${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };
const other = { name: 'Олег Петров', user: 'other' + (stamp % 100000), email: `o${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };

async function open() {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: 'ru-RU' });
  const page = await ctx.newPage();
  page.errors = [];
  page.on('pageerror', (e) => page.errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') page.errors.push(m.text()); });
  return page;
}

async function register(page, who, role) {
  await page.goto(`${BASE}/register`, { waitUntil: 'networkidle' });
  await page.getByLabel('Имя и фамилия').fill(who.name);
  await page.getByLabel('Имя пользователя').fill(who.user);
  await page.getByLabel('Электронная почта').fill(who.email);
  await page.getByLabel('Пароль').fill(who.pass);
  await page.locator('input[type=checkbox]').check();
  await page.getByRole('button', { name: 'Создать аккаунт' }).click();
  await page.waitForURL(/welcome/, { timeout: 20000 });
  // Выбор роли — отдельный экран: две карточки, одна из них наша.
  await page.getByRole('button', { name: role === 'client' ? /Я хочу заказать услугу/ : /Я хочу работать и зарабатывать/ }).click();
  await page.waitForURL(/onboarding|dashboard|feed/, { timeout: 20000 });
}

async function login(page, who) {
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
  await page.getByLabel('Электронная почта').fill(who.email);
  await page.getByLabel('Пароль').fill(who.pass);
  await page.getByRole('button', { name: 'Войти' }).click();
  await page.waitForURL(/feed|dashboard|admin/, { timeout: 20000 });
}

// ── 0. Заказчику проверка не положена ───────────────────────────────────────

const buyerPage = await open();
await register(buyerPage, buyer, 'client');
await buyerPage.goto(`${BASE}/settings`, { waitUntil: 'networkidle' });
await buyerPage.waitForTimeout(1200);
step(
  'в настройках заказчика нет раздела «Личность»',
  (await buyerPage.locator('text=Личность').count()) === 0,
);
await buyerPage.goto(`${BASE}/settings/verification`, { waitUntil: 'networkidle' });
await buyerPage.waitForTimeout(1200);
step(
  'экран проверки заказчику объясняет, что она ему не нужна',
  (await buyerPage.locator('text=Вам это не нужно').count()) > 0,
);
const buyerRefused = await buyerPage.evaluate(async () => {
  const response = await fetch('/api/v1/account/identity', { credentials: 'include' });
  return response.status;
});
step('и мимо интерфейса — тоже отказ', buyerRefused === 403, `статус ${buyerRefused}`);

// ── 1. Исполнитель подаёт документы ─────────────────────────────────────────

const personPage = await open();
await register(personPage, person, 'developer');
const personID = sql(`SELECT id FROM users WHERE email = '${person.email}'`);
step('исполнитель зарегистрирован', personID.length === 36, personID);

await personPage.goto(`${BASE}/settings/verification`, { waitUntil: 'networkidle' });
await personPage.waitForSelector('text=Зачем это нужно', { timeout: 15000 });
step('экран проверки открывается из кабинета', true);
step(
  'экран говорит, что без проверки нельзя откликаться',
  (await personPage.locator('text=нельзя откликаться').count()) > 0,
);
step(
  'экран объясняет, что снимки удаляются после решения',
  (await personPage.locator('text=удаляются').count()) > 0,
);

await personPage.getByLabel('Что вы покажете').selectOption('passport');
await personPage.waitForTimeout(600);
await personPage.getByLabel('Страна выдачи').selectOption('RU');
await personPage.waitForSelector('text=Снимки', { timeout: 15000 });

const front = PNG(900, 600);
const selfie = PNG(800, 800);
// У паспорта нет оборотной стороны, поэтому мест ровно два: лицевая и селфи.
const slots = personPage.locator('input[type=file]');
step('мест под снимки ровно столько, сколько нужно паспорту', (await slots.count()) === 2, String(await slots.count()));
for (const [index, bytes] of [[0, front], [1, selfie]]) {
  await slots.nth(index).setInputFiles({ name: 'document.png', mimeType: 'image/png', buffer: bytes });
  await personPage.waitForTimeout(1500);
}
const uploaded = Number(sql(`SELECT count(*) FROM identity_documents d JOIN identity_verifications v ON v.id = d.verification_id WHERE v.user_id = '${personID}'`));
step('оба снимка приняты', uploaded === 2, `загружено ${uploaded}`);

await personPage.getByRole('button', { name: 'Отправить' }).click();
await personPage.waitForTimeout(1500);
const status = sql(`SELECT status FROM identity_verifications WHERE user_id = '${personID}'`);
step('дело отправлено на проверку', status === 'submitted', status);

// Ключи в хранилище не выдают, чей это документ, и не лежат рядом с аватарами.
const keys = sql(`SELECT storage_key FROM identity_documents d JOIN identity_verifications v ON v.id = d.verification_id WHERE v.user_id = '${personID}'`);
step('снимки лежат в своём разделе хранилища', keys.split('\n').every((k) => k.startsWith('identity/')), keys.replace(/\n/g, ' '));
step('в имени файла нет идентификатора человека', !keys.includes(personID));

// Страница профиля ничего не говорит о документах.
const html = await (await fetch(`${BASE}/api/v1/developers/${person.user}`)).text().catch(() => '');
step('публичный профиль молчит о документах', !html.includes('identity_doc') && !html.includes('storage_key'));

// ── 2. Администратор без разрешения ─────────────────────────────────────────

const reviewerPage = await open();
await register(reviewerPage, reviewer, 'client');
execSync(`/tmp/averix-smoke-ctl create-admin --email ${reviewer.email}`, { stdio: 'ignore', env: process.env });
await login(reviewerPage, reviewer);

await reviewerPage.goto(`${BASE}/admin/users/${personID}`, { waitUntil: 'networkidle' });
await reviewerPage.getByRole('tab', { name: 'Личность' }).click();
await reviewerPage.waitForTimeout(1500);
const refused = await reviewerPage.locator('text=Документы вам не открыты').count();
step('администратор без именного разрешения не видит документов', refused > 0);

const leaked = await reviewerPage.content();
step('на странице нет ни одной ссылки на изображение', !leaked.includes('/identity/documents/'));

// ── 3. Выдаём разрешение через саму панель ──────────────────────────────────

const reviewerID = sql(`SELECT id FROM users WHERE email = '${reviewer.email}'`);
await reviewerPage.goto(`${BASE}/admin/users/${reviewerID}`, { waitUntil: 'networkidle' });
await reviewerPage.waitForSelector('text=Именные разрешения', { timeout: 15000 });
for (const permission of ['Смотреть документы, удостоверяющие личность', 'Принимать решения по проверке личности']) {
  await reviewerPage.getByLabel('Выдать разрешение').selectOption({ label: permission });
  await reviewerPage.getByLabel('Зачем').fill('смена в поддержке');
  await reviewerPage.getByRole('button', { name: 'Выдать', exact: true }).click();
  await reviewerPage.waitForTimeout(1200);
}
const grants = Number(sql(`SELECT count(*) FROM admin_permission_grants WHERE user_id = '${reviewerID}' AND revoked_at IS NULL`));
step('разрешения выданы из панели', grants === 2, `выдано ${grants}`);

// ── 4. Пароль ещё раз, потом документы ──────────────────────────────────────

await reviewerPage.goto(`${BASE}/admin/users/${personID}`, { waitUntil: 'networkidle' });
await reviewerPage.getByRole('tab', { name: 'Личность' }).click();
await reviewerPage.waitForTimeout(1200);
step('одного разрешения мало — просят пароль', (await reviewerPage.locator('text=Введите пароль ещё раз').count()) > 0);

await reviewerPage.getByLabel('Ваш пароль').fill(reviewer.pass);
await reviewerPage.getByRole('button', { name: 'Открыть доступ' }).click();
await reviewerPage.waitForSelector('text=Дело о проверке', { timeout: 15000 });
step('после пароля дело открывается', true);
// Номер документа и дата рождения хранятся для сверки, но наружу не выходят:
// проверяющий сверяет имя на снимке с именем в профиле.
const casePayload = await reviewerPage.evaluate(async () => {
  const response = await fetch(window.location.pathname.replace(/.*\/users\//, '/api/v1/admin/identity/users/'), {
    credentials: 'include',
  });
  return response.text();
});
step(
  'в деле нет ни номера документа, ни даты рождения, ни ссылки на файл',
  !/document_number|date_of_birth|storage_key|"url"/.test(casePayload),
  casePayload.slice(0, 160),
);

// Изображение — только после причины.
await reviewerPage.getByRole('button', { name: 'Открыть' }).first().click();
await reviewerPage.waitForSelector('text=Укажите, зачем вы открываете документ', { timeout: 15000 });
step('просмотрщик сначала спрашивает причину', true);
await reviewerPage.getByLabel('Причина').fill('сверка имени с профилем');
await reviewerPage.getByRole('button', { name: 'Показать изображение' }).click();
await reviewerPage.waitForTimeout(2000);
const shown = await reviewerPage.locator('img[alt="Лицевая сторона"], img[alt="Селфи"]').count();
step('изображение показано', shown > 0);

const logged = sql(`SELECT reason FROM admin_access_logs WHERE action LIKE 'view:%' ORDER BY created_at DESC LIMIT 1`);
step('причина записана в журнал доступа', logged === 'сверка имени с профилем', logged);

// Ссылка на изображение не работает у другого сотрудника.
const url = await reviewerPage.locator('img[alt="Лицевая сторона"], img[alt="Селфи"]').first().getAttribute('src');
const otherPage = await open();
await register(otherPage, other, 'client');
execSync(`/tmp/averix-smoke-ctl create-admin --email ${other.email}`, { stdio: 'ignore', env: process.env });
await login(otherPage, other);
const stolen = await otherPage.request.get(`${BASE}${url}`);
step('украденная ссылка не работает у другого администратора', stolen.status() === 403, `статус ${stolen.status()}`);

// ── 5. Решение ──────────────────────────────────────────────────────────────

await reviewerPage.getByRole('button', { name: 'Закрыть' }).click();
await reviewerPage.waitForTimeout(500);
step(
  'без объяснения решение не принимается',
  await reviewerPage.getByRole('button', { name: 'Подтвердить личность' }).isDisabled(),
);
// И это не только защита в интерфейсе: тот же запрос мимо неё — тоже отказ.
const caseID = sql(`SELECT id FROM identity_verifications WHERE user_id = '${personID}'`);
const bare = await reviewerPage.evaluate(async (id) => {
  const session = await (await fetch('/api/v1/auth/session', { credentials: 'include' })).json();
  const response = await fetch(`/api/v1/admin/identity/cases/${id}/decide`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session?.data?.csrf_token ?? '' },
    body: JSON.stringify({ action: 'approve' }),
  });
  return response.status;
}, caseID);
step('тот же запрос без объяснения мимо интерфейса — отказ', bare === 422, String(bare));

await reviewerPage.getByLabel('Что вы проверили').fill('Имя и дата рождения совпадают с профилем, снимок читается целиком.');
await reviewerPage.getByRole('button', { name: 'Подтвердить личность' }).click();
await reviewerPage.waitForTimeout(2000);
const decided = sql(`SELECT status FROM identity_verifications WHERE user_id = '${personID}'`);
step('личность подтверждена', decided === 'approved', decided);
step('аккаунт отмечен проверенным', sql(`SELECT identity_verified_at IS NOT NULL FROM users WHERE id = '${personID}'`) === 't');
const retention = sql(`SELECT count(*) FROM identity_documents d JOIN identity_verifications v ON v.id = d.verification_id WHERE v.user_id = '${personID}' AND d.retention_expires_at IS NOT NULL`);
step('у снимков появился срок хранения', retention === '2', retention);

const notified = sql(`SELECT count(*) FROM notifications WHERE user_id = '${personID}' AND type = 'identity_approved'`);
step('человек получил уведомление о решении', notified === '1', notified);

// ── 6. Отзыв разрешения действует сразу ─────────────────────────────────────

await reviewerPage.goto(`${BASE}/admin/users/${reviewerID}`, { waitUntil: 'networkidle' });
await reviewerPage.waitForSelector('text=Именные разрешения', { timeout: 15000 });
await reviewerPage.getByRole('button', { name: 'Отозвать' }).first().click();
await reviewerPage.waitForTimeout(1200);
await reviewerPage.goto(`${BASE}/admin/users/${personID}`, { waitUntil: 'networkidle' });
await reviewerPage.getByRole('tab', { name: 'Личность' }).click();
await reviewerPage.waitForTimeout(1500);
step(
  'отзыв разрешения закрывает доступ немедленно',
  (await reviewerPage.locator('text=Документы вам не открыты').count()) > 0,
);

// ── 7. Человек видит, чем всё кончилось ─────────────────────────────────────

await personPage.goto(`${BASE}/settings/verification`, { waitUntil: 'networkidle' });
await personPage.waitForTimeout(1200);
step('человеку видно, что личность подтверждена', (await personPage.locator('text=Личность подтверждена').count()) > 0);

const errors = [...personPage.errors, ...buyerPage.errors, ...reviewerPage.errors].filter((e) => !e.includes('403') && !e.includes('Failed to load resource'));
step('в консоли нет ошибок страниц', errors.length === 0, errors.slice(0, 3).join(' | '));

await browser.close();

console.log('');
if (fail.length) {
  console.log(`НЕ ПРОШЛО: ${fail.length}`);
  for (const f of fail) console.log('  · ' + f);
  process.exit(1);
}
console.log('Всё прошло.');
