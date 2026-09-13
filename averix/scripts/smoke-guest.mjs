// Открытый просмотр: площадку видно без аккаунта.
//
// Проверяется обещание, ради которого это сделано: гость без единой куки
// открывает каталог исполнителей, профиль с портфолио и отзывами, каталог
// услуг, каталог открытых заказов и сам заказ — и нигде его не выкидывает на
// вход. Регистрация встречает его ровно на действии: кнопка «Откликнуться»
// ведёт на вход с адресом возврата, и после входа человек оказывается на той
// же странице, а не на чужом рабочем столе.
//
//   AVERIX_SMOKE_URL=http://localhost:3000 node scripts/smoke-guest.mjs

import { chromium } from 'playwright';
import { execSync } from 'node:child_process';

const BASE = process.env.AVERIX_SMOKE_URL ?? 'http://localhost:3000';
const PSQL = process.env.AVERIX_SMOKE_PSQL ?? '-U postgres -h /var/run/postgresql -d averix_dev';
const fail = [];

function step(name, ok, detail = '') {
  console.log(`${ok ? '✓' : '✗'} ${name}${detail ? ' — ' + detail : ''}`);
  if (!ok) fail.push(name + (detail ? ': ' + detail : ''));
}

const sql = (q) => execSync(`psql ${PSQL} -At -c "${q.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim();

execSync(`redis-cli -n ${process.env.AVERIX_SMOKE_REDIS_DB ?? 3} FLUSHDB`, { stdio: 'ignore' });

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

async function register(page, who, role) {
  await page.goto(`${BASE}/register`, { waitUntil: 'networkidle' });
  await page.getByLabel('Имя и фамилия').fill(who.name);
  await page.getByLabel('Имя пользователя').fill(who.user);
  await page.getByLabel('Электронная почта').fill(who.email);
  await page.getByLabel('Пароль').fill(who.pass);
  await page.locator('input[type=checkbox]').check();
  await page.getByRole('button', { name: 'Создать аккаунт' }).click();
  await page.waitForURL(/welcome/, { timeout: 20000 });
  await page.getByRole('button', {
    name: role === 'client' ? /Я хочу заказать услугу/ : /Я хочу работать и зарабатывать/,
  }).click();
  await page.waitForURL(/onboarding|dashboard/, { timeout: 20000 });
  sql(`UPDATE users SET email_verified_at = now() WHERE email = '${who.email}'`);
}

const stamp = Date.now();
const dev = { name: 'Севара Рахимова', user: 'sevara' + (stamp % 100000), email: `g${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };
const client = { name: 'Пекарня «Корка»', user: 'korka' + (stamp % 100000), email: `k${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };

// ── Подготовка: один опубликованный исполнитель и один открытый заказ ───────
//
// Гостю нужно на что смотреть. Всё создаётся через интерфейс, кроме решения
// администратора и подтверждения личности: у них есть свои сценарии, а здесь
// это просто состояние, с которого начинается открытый каталог.

const maker = await open();
await register(maker, dev, 'developer');

await maker.waitForSelector('text=Шаг 1 из 4', { timeout: 20000 });
await maker.getByLabel('Код страны').fill('UZ');
await maker.getByLabel('Город').fill('Самарканд');
const designer = maker.locator('button', { hasText: 'Графический дизайнер' }).first();
if (await designer.count()) await designer.click();
else await maker.locator('button:has-text("Бэкенд-разработчик")').first().click();
await maker.getByLabel('Как вас представить').fill('Логотипы и упаковка');
await maker.getByRole('button', { name: 'Далее' }).click();

await maker.waitForSelector('text=Шаг 2 из 4', { timeout: 20000 });
await maker.getByLabel('Найти навык').fill('Figma');
await maker.waitForTimeout(1500);
const chip = maker.locator('button[aria-pressed]', { hasText: /Figma/i }).first();
if (await chip.count()) await chip.click();
await maker.getByLabel('Ставка за час').fill('1200');
await maker.getByLabel('О себе').fill(
  'Рисую логотипы и упаковку для небольших производств: пекарни, сыроварни, ' +
  'локальные чайные. Начинаю с полки и вывески — с того, как знак живёт в жизни, ' +
  'а не в презентации. Отдаю исходники и короткий гайд по применению.',
);
await maker.getByRole('button', { name: 'Далее' }).click();

await maker.waitForSelector('text=Шаг 3 из 4', { timeout: 20000 });
await maker.getByRole('button', { name: 'Добавить работу' }).click();
await maker.getByLabel('Что вы сделали').fill('Упаковка для пекарни «Корка»');
await maker.getByLabel('Направление').selectOption({ index: 1 });
await maker.getByLabel('Коротко, одной строкой').fill('Знак, пакет и наклейки для районной пекарни');
await maker.getByLabel('Что именно вы делали').fill(
  'Сделала знак, бумажный пакет и наклейки для пекарни у метро. Считали, сколько стоит ' +
  'печать в одну краску, и собрали всё вокруг этого ограничения.',
);
await maker.getByLabel('Ссылка на работу').fill('https://example.org/korka');
await maker.getByRole('button', { name: 'Сохранить работу' }).click();
await maker.waitForTimeout(2500);
await maker.getByRole('button', { name: 'Далее' }).click();

await maker.waitForSelector('text=Шаг 4 из 4', { timeout: 20000 });
await maker.getByRole('button', { name: 'Отправить заявку' }).click();
await maker.waitForSelector('text=Заявка на рассмотрении', { timeout: 25000 });

sql(`UPDATE developer_profiles SET moderation_state = 'approved', is_searchable = true ` +
    `WHERE user_id = (SELECT id FROM users WHERE email = '${dev.email}')`);
sql(`UPDATE users SET identity_verified_at = now() WHERE email = '${dev.email}'`);

const buyer = await open();
await register(buyer, client, 'client');
await buyer.goto(`${BASE}/projects/new`, { waitUntil: 'networkidle' });
await buyer.waitForSelector('text=Что нужно сделать', { timeout: 20000 });
await buyer.locator('button:has-text("Дизайн")').first().click();
await buyer.waitForTimeout(1500);
await buyer.getByRole('button', { name: 'Логотипы и фирменный стиль' }).first().click();
await buyer.getByLabel('Название заказа').fill('Упаковка для пекарни у вокзала');
await buyer.getByRole('button', { name: 'Далее' }).click();
await buyer.waitForSelector('text=Описание', { timeout: 20000 });
await buyer.getByLabel('Подробное описание').fill(
  'Открываем вторую точку и хотим свою упаковку: пакет, наклейка и коробка под торт. ' +
  'Печать в одну краску, крафт. Знак уже есть, нужен человек, который соберёт из него ' +
  'внятную упаковку и подготовит файлы к типографии.',
);
await buyer.getByRole('button', { name: 'Далее' }).click();
await buyer.waitForSelector('text=Навыки', { timeout: 20000 });
await buyer.waitForTimeout(1800);
const skill = buyer.locator('button[aria-pressed]').first();
if (await skill.count()) await skill.click();
await buyer.getByRole('button', { name: 'Далее' }).click();
await buyer.waitForSelector('text=Бюджет и сроки', { timeout: 20000 });
await buyer.getByRole('textbox', { name: 'От' }).fill('20000');
await buyer.getByRole('textbox', { name: 'До' }).fill('45000');
await buyer.getByRole('button', { name: 'Далее' }).click();
await buyer.waitForSelector('text=Проверьте и опубликуйте', { timeout: 20000 });
await buyer.getByRole('button', { name: 'Опубликовать', exact: true }).click();
await buyer.waitForTimeout(4500);
const projectURL = buyer.url().replace('/proposals', '');
step('подготовка: заказ опубликован', /\/projects\/[a-z0-9-]+/.test(projectURL), projectURL);
const slug = projectURL.split('/projects/')[1];

// ── Дальше — гость. Ни одной куки. ─────────────────────────────────────────

const guest = await open();

await guest.goto(BASE, { waitUntil: 'networkidle' });
const landing = await guest.locator('body').innerText();
step('с главной можно уйти смотреть, а не только регистрироваться',
  /Открытые заказы/.test(landing) && /без регистрации/i.test(landing));

// 1. Каталог заказов
await guest.goto(`${BASE}/projects`, { waitUntil: 'networkidle' });
await guest.waitForTimeout(2000);
step('каталог заказов открыт гостю', !guest.url().includes('/login'), guest.url());
const catalogue = await guest.locator('body').innerText();
step('в каталоге виден опубликованный заказ', /Упаковка для пекарни у вокзала/.test(catalogue),
  catalogue.replace(/\n/g, ' | ').slice(0, 160));
step('у карточки заказа есть бюджет', /₽/.test(catalogue));
step('гостю объясняют, зачем аккаунт', /Создайте аккаунт/.test(catalogue));

await guest.locator('button', { hasText: 'Дизайн' }).first().click();
await guest.waitForTimeout(2000);
step('фильтр по направлению работает гостю',
  (await guest.locator('body').innerText()).includes('Упаковка для пекарни у вокзала'));

// 2. Страница заказа
await guest.goto(`${BASE}/projects/${slug}`, { waitUntil: 'networkidle' });
await guest.waitForTimeout(2000);
step('страница заказа открыта гостю', !guest.url().includes('/login'), guest.url());
const brief = await guest.locator('body').innerText();
step('гость читает задачу целиком', /Что нужно сделать/.test(brief) && /коробка под торт/.test(brief));
step('гость видит, у кого заказ', /О заказчике/.test(brief));

const respond = guest.getByRole('link', { name: 'Откликнуться' });
step('вместо пустоты гостю показывают «Откликнуться»', (await respond.count()) === 1);
const href = await respond.getAttribute('href');
step('кнопка ведёт на вход с адресом возврата',
  href?.startsWith('/login?next=') && decodeURIComponent(href).includes(`/projects/${slug}`), String(href));

// 3. Каталог исполнителей и профиль
await guest.goto(`${BASE}/freelancers`, { waitUntil: 'networkidle' });
await guest.waitForTimeout(2000);
step('каталог исполнителей открыт гостю', !guest.url().includes('/login'), guest.url());
step('исполнитель в каталоге виден без аккаунта',
  (await guest.locator('body').innerText()).includes(dev.name));

await guest.goto(`${BASE}/developers/${dev.user}`, { waitUntil: 'networkidle' });
await guest.waitForTimeout(2500);
step('профиль исполнителя открыт гостю', !guest.url().includes('/login'), guest.url());
const profile = await guest.locator('body').innerText();
step('гость видит анкету и навыки', profile.includes(dev.name) && /Навыки/.test(profile));
step('на профиле есть кнопка действия, а не пустое место',
  (await guest.getByRole('link', { name: 'Войти и заказать' }).count()) === 1);

await guest.locator('button', { hasText: 'Портфолио' }).first().click();
await guest.waitForTimeout(1500);
step('портфолио видно без аккаунта',
  (await guest.locator('body').innerText()).includes('Упаковка для пекарни «Корка»'));
await guest.locator('button', { hasText: 'Отзывы' }).first().click();
await guest.waitForTimeout(1200);
step('раздел отзывов открывается гостю',
  /Отзыв/i.test(await guest.locator('body').innerText()));

// 4. Услуги, поиск, справочник
for (const path of ['/services', '/search?q=логотип', '/talent']) {
  const res = await guest.goto(BASE + path, { waitUntil: 'domcontentloaded' });
  await guest.waitForTimeout(1200);
  const body = await guest.locator('body').innerText();
  step(`${path} открыт гостю`,
    res.status() === 200 && !guest.url().includes('/login') && !/could not be found/.test(body),
    `${res.status()} ${guest.url()}`);
}

// 5. Нижняя панель у гостя
await guest.goto(`${BASE}/freelancers`, { waitUntil: 'networkidle' });
await guest.waitForTimeout(1200);
const nav = guest.locator('nav[aria-label="Главное меню"]');
step('у гостя есть нижняя навигация', (await nav.count()) === 1);
const navText = (await nav.count()) ? await nav.innerText() : '';
step('в ней каталоги и вход', /Исполнители/.test(navText) && /Заказы/.test(navText) && /Войти/.test(navText), navText.replace(/\n/g, ' '));

// 6. Личное по-прежнему закрыто
for (const path of ['/dashboard', '/feed', '/messages', '/settings', '/admin']) {
  await guest.goto(BASE + path, { waitUntil: 'networkidle' });
  await guest.waitForTimeout(1500);
  step(`${path} закрыт гостю`, guest.url().includes('/login'), guest.url());
}

// 7. Действие приводит на вход и возвращает обратно
await guest.goto(`${BASE}/projects/${slug}`, { waitUntil: 'networkidle' });
await guest.waitForTimeout(1500);
await guest.getByRole('link', { name: 'Откликнуться' }).click();
await guest.waitForURL(/\/login/, { timeout: 20000 });
step('с заказа гость попадает на вход', guest.url().includes('/login'), guest.url());
await guest.getByLabel('Электронная почта').fill(client.email);
await guest.getByLabel('Пароль').fill(client.pass);
await guest.getByRole('button', { name: 'Войти' }).click();
// Именно на страницу заказа, а не на /login?next=…: адрес возврата и сам
// содержит слаг, и проверка «в адресе есть слаг» прошла бы, не сходя с формы.
await guest.waitForURL((url) => url.pathname === `/projects/${slug}`, { timeout: 20000 });
step('после входа человек возвращается на тот же заказ',
  new URL(guest.url()).pathname === `/projects/${slug}`, guest.url());

const noise = guest.errors.filter((e) => !/401 \(Unauthorized\)/.test(e));
step('в консоли гостя нет ошибок', noise.length === 0, noise.slice(0, 3).join(' | '));

await browser.close();

console.log('');
if (fail.length) {
  console.log(`НЕ ПРОШЛО: ${fail.length}`);
  for (const f of fail) console.log('  · ' + f);
  process.exit(1);
}
console.log('Всё прошло.');
