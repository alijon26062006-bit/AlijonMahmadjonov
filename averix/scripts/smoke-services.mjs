// Вторая половина сквозной проверки: услуги с фиксированной ценой и панель
// администратора.
//
// scripts/smoke.mjs проходит путь «заказ → отклик → сделка». Здесь — путь
// «услуга → покупка в один шаг», ради которого платформа и называется
// маркетплейсом, и проверка, что каждый экран администратора открывается и
// показывает данные, а не пустую рамку.
//
// Запуск:
//   AVERIX_SMOKE_URL=http://localhost:3000 node scripts/smoke-services.mjs
//
// Подтверждение почты, публикация анкеты и выдача роли администратора идут
// напрямую в базу: письма в разработке не уходят, а девять шагов анкеты уже
// проверены в scripts/smoke.mjs и повторять их здесь нечего.

import { chromium } from 'playwright';
import { execSync } from 'node:child_process';

const BASE = process.env.AVERIX_SMOKE_URL ?? 'http://localhost:3000';
const PSQL = process.env.AVERIX_SMOKE_PSQL ?? '-U postgres -h /var/run/postgresql -d averix_dev';
execSync(`redis-cli -n ${process.env.AVERIX_SMOKE_REDIS_DB ?? 3} FLUSHDB`, { stdio: 'ignore' });
const fail = [];
function step(name, ok, detail = '') {
  console.log(`${ok ? '✓' : '✗'} ${name}${detail ? ' — ' + detail : ''}`);
  if (!ok) fail.push(name);
}
function sql(q) { execSync(`psql ${PSQL} -c "${q}"`, { stdio: 'ignore' }); }

const browser = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
);
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, locale: 'ru-RU' });
const bad = [];
page.on('response', (r) => { if (r.status() >= 400 && r.url().includes('/api/v1/')) bad.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`); });

const stamp = Date.now();
const dev = { name: 'Олег Соколов', user: 'oleg' + (stamp % 100000), email: `s${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };
const buyer = { name: 'Анна Петрова', user: 'anna' + (stamp % 100000), email: `b${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };

async function register(who, role) {
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
  await page.waitForURL(/onboarding|dashboard/, { timeout: 15000 });
  sql(`UPDATE users SET email_verified_at = now() WHERE email = '${who.email}'`);
  if (role === 'developer') {
    // Услуги продаёт только проверенный исполнитель. Сама проверка — с
    // документами и сотрудником — это smoke-identity.mjs; здесь отметка
    // ставится напрямую, как и подтверждение почты строкой выше.
    sql(`UPDATE users SET identity_verified_at = now() WHERE email = '${who.email}'`);
  }
}
async function signOut() {
  await page.goto(`${BASE}/settings`, { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: 'Меню аккаунта' }).click();
  await page.getByRole('button', { name: 'Выйти' }).click();
  await page.waitForURL(/\/login/, { timeout: 15000 });
}
async function login(who) {
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
  await page.getByLabel('Электронная почта').fill(who.email);
  await page.getByLabel('Пароль').fill(who.pass);
  await page.getByRole('button', { name: 'Войти' }).click();
  await page.waitForURL(/feed|dashboard|admin/, { timeout: 15000 });
}

// Исполнитель публикует услугу. Каталог показывает услуги только от
// опубликованной анкеты, поэтому сначала анкета — как и в жизни.
await register(dev, 'developer');
sql(`UPDATE developer_profiles SET is_searchable = true, onboarding_completed_at = now() WHERE user_id = (SELECT id FROM users WHERE email = '${dev.email}')`);
await page.goto(`${BASE}/services/new`, { waitUntil: 'networkidle' });
await page.waitForSelector('text=Направление', { timeout: 15000 });
await page.getByRole('button', { name: 'Аудио и видео' }).first().click();
await page.waitForTimeout(1200);
const cat = page.getByRole('button', { name: 'Видеомонтаж' }).first();
step('категории услуги подгружаются', (await cat.count()) > 0);
await cat.click();
await page.getByLabel('Название услуги').fill('Смонтирую ролик для маркетплейса из ваших съёмок');
await page.getByLabel('Короткое описание').fill('Ролик до минуты: склейка, субтитры, музыка, экспорт под площадку.');
await page.getByLabel('Подробное описание').fill(
  'Работаю с исходниками, снятыми на телефон: чищу звук, выравниваю свет, ' +
  'собираю ритм под площадку. Отдаю вертикаль и горизонталь. Правки — по одному кругу ' +
  'на каждом пакете, дальше по договорённости.',
);
await page.getByLabel('Название пакета').first().fill('Базовый');
await page.getByRole('textbox', { name: 'Цена' }).first().fill('3000');
await page.getByRole('textbox', { name: 'Срок, дней' }).first().fill('3');
await page.getByLabel('Что входит').first().fill('Склейка до 60 секунд\nСубтитры\nМузыка из библиотеки');
await page.waitForTimeout(1200);
const skill = page.locator('button[aria-pressed]').filter({ hasText: /Premiere|After|Монтаж|DaVinci/ }).first();
if (await skill.count()) await skill.click();
else {
  await page.getByLabel('Найти навык').fill('Premiere');
  await page.waitForTimeout(1500);
  const found = page.locator('button[aria-pressed]').last();
  if (await found.count()) await found.click();
}
const [created] = await Promise.all([
  page.waitForResponse((r) => r.url().includes('/api/v1/services') && r.request().method() === 'POST', { timeout: 20000 }).catch(() => null),
  page.getByRole('button', { name: 'Опубликовать' }).click(),
]);
step('услуга создаётся', created?.status() === 201,
  created ? `${created.status()} ${(await created.text()).slice(0, 300)}` : 'нет ответа');
if (created?.status() !== 201) {
  console.log('ЭКРАН:', (await page.locator('body').innerText()).slice(0, 500).replace(/\n/g, ' | '));
  await browser.close();
  process.exit(1);
}
await page.waitForURL(/\/services\/[0-9a-f-]{36}/, { timeout: 20000 });
const svcURL = page.url();
await page.waitForSelector('text=Что входит', { timeout: 20000 });
const svcBody = await page.locator('body').innerText();
step('страница услуги на русском', /Что входит|Описание|Исполнитель/.test(svcBody), svcBody.slice(0, 140).replace(/\n/g, ' | '));

await page.goto(`${BASE}/services/mine`, { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
step('услуга видна в «Моих услугах»', /Смонтирую ролик/.test(await page.locator('body').innerText()));

// Заказчик находит услугу в каталоге и заказывает её
await signOut();
await register(buyer, 'client');
await page.goto(`${BASE}/services`, { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);
step('услуга появилась в каталоге', /Смонтирую ролик/.test(await page.locator('body').innerText()),
  (await page.locator('body').innerText()).slice(0, 160).replace(/\n/g, ' | '));
await page.goto(svcURL, { waitUntil: 'networkidle' });
await page.waitForSelector('text=Что входит', { timeout: 15000 });
await page.getByRole('button', { name: 'Заказать' }).click();
await page.waitForSelector('text=Что нужно сделать', { timeout: 15000 });
await page.getByLabel('Что нужно сделать').fill(
  'Есть двадцать минут съёмок с телефона: распаковка и примерка. Нужен ролик на 45 секунд ' +
  'для карточки товара, вертикальный, с субтитрами.',
);
const [ordered] = await Promise.all([
  page.waitForResponse((r) => /\/api\/v1\/services\/.*\/order/.test(r.url()), { timeout: 20000 }).catch(() => null),
  page.getByRole('button', { name: 'Оформить заказ' }).click(),
]);
step('услуга заказывается', ordered?.status() === 201, String(ordered?.status()));
await page.waitForURL(/\/contracts\//, { timeout: 20000 });
await page.waitForSelector('text=Этапы', { timeout: 20000 });
step('заказ услуги открывает сделку', /Этапы/.test(await page.locator('body').innerText()), page.url());

// Администратор: панель, модерация, настройки
await signOut();
sql(`INSERT INTO user_roles (user_id, role) SELECT id, 'admin' FROM users WHERE email = '${buyer.email}' ON CONFLICT DO NOTHING`);
await login(buyer);
await page.goto(`${BASE}/admin`, { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);
const admin = await page.locator('body').innerText();
step('панель администратора открывается', /Люди|Площадка|Требует внимания/.test(admin), admin.slice(0, 160).replace(/\n/g, ' | '));
for (const [path, marker] of [['/admin/users', /Пользователи|Найти/], ['/admin/moderation', /Очередь|Жалобы/], ['/admin/settings', /Параметры|Комиссия/], ['/admin/disputes', /спор/i], ['/admin/audit', /Журнал|записей/i], ['/admin/identity', /Раздел вам не открыт|Введите пароль|Ждут проверки/]]) {
  await page.goto(BASE + path, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  step(`${path} работает`, marker.test(await page.locator('body').innerText()));
}

console.log('\nОтветы 4xx/5xx: ' + (bad.length ? [...new Set(bad)].join(', ') : 'нет'));
console.log(fail.length ? `ПРОВАЛЕНО: ${fail.join(', ')}` : 'ВСЁ ПРОШЛО');
await browser.close();
process.exit(fail.length ? 1 : 0);
