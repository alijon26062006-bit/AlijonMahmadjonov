// Заказ услуги целиком: опции, подтверждение исполнителем, срок приёмки.
//
// Четыре правила, которых раньше не было, и все четыре видны человеку на
// экране: к пакету можно докупить опции и цена меняется до нажатия «Заказать»;
// заказ ждёт ответа исполнителя, и обе стороны знают, до какого момента;
// сданная работа принимается сама, и срок написан до того, как истечёт;
// комиссия сейчас нулевая, и исполнителю сказано, что он получит всё.
//
//   AVERIX_SMOKE_URL=http://localhost:3000 node scripts/smoke-orders.mjs

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
const dev = { name: 'Гуля Сафарова', user: 'gulya' + (stamp % 100000), email: `o${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };
const buyer = { name: 'Пекарня «Корка»', user: 'korka' + (stamp % 100000), email: `p${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };

// ── Исполнитель: анкета и услуга с опциями ──────────────────────────────────

const seller = await open();
await register(seller, dev, 'developer');

await seller.waitForSelector('text=Шаг 1 из 4', { timeout: 20000 });
await seller.getByLabel('Код страны').fill('UZ');
await seller.getByLabel('Город').fill('Самарканд');
const designer = seller.locator('button', { hasText: 'Графический дизайнер' }).first();
if (await designer.count()) await designer.click();
else await seller.locator('button:has-text("Бэкенд-разработчик")').first().click();
await seller.getByLabel('Как вас представить').fill('Логотипы и упаковка');
await seller.getByRole('button', { name: 'Далее' }).click();

await seller.waitForSelector('text=Шаг 2 из 4', { timeout: 20000 });
await seller.getByLabel('Найти навык').fill('Figma');
await seller.waitForTimeout(1500);
const chip = seller.locator('button[aria-pressed]', { hasText: /Figma/i }).first();
if (await chip.count()) await chip.click();
await seller.getByLabel('Ставка за час').fill('1200');
await seller.getByLabel('О себе').fill(
  'Рисую логотипы и упаковку для небольших производств: пекарни, сыроварни, локальные ' +
  'чайные. Начинаю с полки и вывески — с того, как знак живёт в жизни, а не в презентации.',
);
await seller.getByRole('button', { name: 'Далее' }).click();

await seller.waitForSelector('text=Шаг 3 из 4', { timeout: 20000 });
await seller.getByRole('button', { name: 'Добавить работу' }).click();
await seller.getByLabel('Что вы сделали').fill('Упаковка для пекарни «Корка»');
await seller.getByLabel('Направление').selectOption({ index: 1 });
await seller.getByLabel('Коротко, одной строкой').fill('Знак, пакет и наклейки для районной пекарни');
await seller.getByLabel('Что именно вы делали').fill(
  'Сделала знак, бумажный пакет и наклейки для пекарни у метро. Считали стоимость печати ' +
  'в одну краску и собрали всё вокруг этого ограничения.',
);
await seller.getByLabel('Ссылка на работу').fill('https://example.org/korka');
await seller.getByRole('button', { name: 'Сохранить работу' }).click();
await seller.waitForTimeout(2500);
await seller.getByRole('button', { name: 'Далее' }).click();
await seller.waitForSelector('text=Шаг 4 из 4', { timeout: 20000 });
await seller.getByRole('button', { name: 'Отправить заявку' }).click();
await seller.waitForSelector('text=Заявка на рассмотрении', { timeout: 25000 });

sql(`UPDATE developer_profiles SET moderation_state = 'approved', is_searchable = true ` +
    `WHERE user_id = (SELECT id FROM users WHERE email = '${dev.email}')`);
sql(`UPDATE users SET identity_verified_at = now() WHERE email = '${dev.email}'`);

// Услуга с пакетом и двумя опциями.
await seller.goto(`${BASE}/services/new`, { waitUntil: 'networkidle' });
await seller.waitForTimeout(1500);
await seller.locator('button:has-text("Дизайн")').first().click();
await seller.waitForTimeout(1200);
await seller.getByRole('button', { name: 'Логотипы и фирменный стиль' }).first().click();
await seller.getByLabel('Название услуги').fill('Упаковка для небольшого производства');
await seller.getByLabel('Короткое описание').fill('Пакет, наклейка и коробка — с файлами для типографии');
await seller.getByLabel('Подробное описание').fill(
  'Соберу упаковку вокруг вашего знака: бумажный пакет, наклейка и коробка. Считаю ' +
  'стоимость печати заранее и подгоняю макет под неё, отдаю файлы, готовые к типографии.',
);
await seller.getByLabel('Название пакета').fill('Базовый');
await seller.getByLabel('Цена').fill('30000');
await seller.getByLabel('Срок, дней').fill('10');

// Публикация требует навыков, как и любая другая услуга.
await seller.getByLabel('Найти навык').fill('Figma');
await seller.waitForTimeout(1500);
const serviceSkill = seller.locator('button[aria-pressed]', { hasText: /Figma/i }).first();
if (await serviceSkill.count()) await serviceSkill.click();

step('в редакторе услуги есть опции', (await seller.getByRole('button', { name: 'Добавить опцию' }).count()) === 1);
await seller.getByRole('button', { name: 'Добавить опцию' }).click();
await seller.getByLabel('Что именно').nth(0).fill('Сделаю за три дня вместо десяти');
await seller.getByLabel('Доплата').nth(0).fill('15000');
await seller.getByLabel('+ дней к сроку').nth(0).fill('0');
await seller.getByRole('button', { name: 'Добавить опцию' }).click();
await seller.getByLabel('Что именно').nth(1).fill('Отдам исходники и инструкцию');
await seller.getByLabel('Доплата').nth(1).fill('5000');
await seller.getByLabel('+ дней к сроку').nth(1).fill('1');

await seller.getByRole('button', { name: 'Опубликовать' }).click();
await seller.waitForURL(/\/services\/[0-9a-f-]{36}/, { timeout: 25000 });
const serviceURL = seller.url();
step('услуга с опциями опубликована', serviceURL.includes('/services/'), serviceURL);

// ── Заказчик: выбирает опции и видит, как меняется цена ─────────────────────

const client = await open();
await register(client, buyer, 'client');
await client.goto(serviceURL, { waitUntil: 'networkidle' });
await client.waitForTimeout(2000);

const page = await client.locator('body').innerText();
step('опции видны заказчику', /Можно добавить/.test(page) && /Сделаю за три дня/.test(page),
  page.replace(/\n/g, ' | ').slice(0, 140));

// Нижняя панель заказа: до выбора опций там цена пакета, после — с опциями.
const orderBar = client.locator('button', { hasText: 'Заказать' }).locator('xpath=..');
// Цены печатаются с неразрывным пробелом, а подписи — заглавными через CSS:
// сравнивать надо нормализованный текст, иначе проверка ловит вёрстку.
const plain = (text) => text.replace(/\u00a0/g, ' ').replace(/\s+/g, ' ');
const before = plain(await orderBar.innerText());
step('до выбора опций в панели цена пакета', /30 000/.test(before), before);

await client.locator('label', { hasText: 'Сделаю за три дня' }).locator('input[type=checkbox]').check();
await client.locator('label', { hasText: 'Отдам исходники' }).locator('input[type=checkbox]').check();
await client.waitForTimeout(800);
const after = plain(await orderBar.innerText());
step('цена пересчиталась с опциями', /50 000/.test(after), after);

await client.getByRole('button', { name: 'Заказать' }).click();
await client.waitForSelector('text=Что нужно сделать', { timeout: 20000 });
// Читаем именно окно заказа: то же самое на странице под ним ничего не доказывает.
const sheetBox = client.locator('[role=dialog]').first();
const sheet = await sheetBox.innerText();
step('в окне заказа перечислены опции и итог', /Итого/.test(sheet) && /Отдам исходники/.test(sheet),
  sheet.replace(/\n/g, ' | ').slice(0, 140));
step('срок в окне учитывает опцию', /11 дн/.test(sheet), (sheet.match(/Срок.{0,20}/) || [''])[0]);

await client.getByLabel('Что нужно сделать').fill(
  'Пекарня у вокзала: пакет, наклейка и коробка под торт. Печать в одну краску, крафт.',
);
await client.getByRole('button', { name: 'Оформить заказ' }).click();
await client.waitForURL(/\/contracts\//, { timeout: 25000 });
const contractURL = client.url();
await client.waitForSelector('text=Этапы', { timeout: 25000 });
await client.waitForTimeout(1000);

const waiting = await client.locator('body').innerText();
step('заказчик видит, что заказ ждёт ответа исполнителя', /ждёт ответа исполнителя/.test(waiting),
  waiting.replace(/\n/g, ' | ').slice(0, 160));
step('заказчику видно, что докупили', /Что докупили к пакету/.test(waiting));
const money = plain(waiting);
step('комиссии сейчас нет', /комиссия нет/i.test(money),
  (money.match(/комиссия.{0,20}/i) || [''])[0]);

// ── Исполнитель принимает заказ ─────────────────────────────────────────────

await seller.goto(contractURL, { waitUntil: 'networkidle' });
await seller.waitForSelector('text=Этапы', { timeout: 25000 });
await seller.waitForTimeout(1000);
const ask = await seller.locator('body').innerText();
step('исполнителю показывают заказ и срок ответа', /ждёт вашего ответа/.test(ask),
  ask.replace(/\n/g, ' | ').slice(0, 160));
step('есть кнопки принять и отказаться',
  (await seller.getByRole('button', { name: 'Принять заказ' }).count()) === 1 &&
  (await seller.getByRole('button', { name: 'Отказаться' }).count()) === 1);

await seller.getByRole('button', { name: 'Принять заказ' }).click();
await seller.waitForTimeout(2500);
const accepted = await seller.locator('body').innerText();
step('после принятия ожидание исчезает', !/ждёт вашего ответа/.test(accepted));

const contractID = contractURL.split('/contracts/')[1];
step('подтверждение записано', sql(`SELECT developer_confirmed_at IS NOT NULL FROM contracts WHERE id = '${contractID}'`) === 't');
step('заказчику ушло уведомление о принятии',
  sql(`SELECT count(*) FROM notifications WHERE type = 'order_confirmed'`) !== '0');

// ── Сдача работы и срок автоприёмки ─────────────────────────────────────────

const milestoneID = sql(`SELECT id FROM milestones WHERE contract_id = '${contractID}' LIMIT 1`);
sql(`UPDATE milestones SET status = 'funded' WHERE id = '${milestoneID}'`);
sql(`UPDATE contracts SET status = 'active' WHERE id = '${contractID}'`);

await seller.reload({ waitUntil: 'networkidle' });
await seller.waitForTimeout(1500);
await seller.getByRole('button', { name: 'Начать работу' }).click();
await seller.waitForTimeout(1500);
await seller.getByRole('button', { name: 'Сдать работу' }).click();
await seller.waitForSelector('text=Сдать этап', { timeout: 20000 });
await seller.getByLabel('Что вы передаёте?').fill(
  'Пакет, наклейка и коробка собраны, файлы для типографии в архиве.',
);
await seller.getByRole('button', { name: 'Сдать на проверку' }).click();
await seller.waitForTimeout(3500);

const delivered = await seller.locator('body').innerText();
step('исполнителю видно, до какого дня отвечает заказчик', /будет принята автоматически/.test(delivered),
  (delivered.match(/.{0,80}автоматически.{0,20}/) || [''])[0]);
step('срок приёмки записан',
  sql(`SELECT auto_approve_at IS NOT NULL FROM milestones WHERE id = '${milestoneID}'`) === 't');

await client.goto(contractURL, { waitUntil: 'networkidle' });
await client.waitForTimeout(2000);
const clientView = await client.locator('body').innerText();
step('заказчика предупредили о сроке', /будет принята автоматически/.test(clientView));

const noise = [...seller.errors, ...client.errors].filter((e) => !/401 \(Unauthorized\)/.test(e));
step('в консоли чисто', noise.length === 0, noise.slice(0, 3).join(' | '));

await browser.close();

console.log('');
if (fail.length) {
  console.log(`НЕ ПРОШЛО: ${fail.length}`);
  for (const f of fail) console.log('  · ' + f);
  process.exit(1);
}
console.log('Всё прошло.');
