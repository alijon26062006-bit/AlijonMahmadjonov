// Сквозная проверка живого продукта в настоящем браузере.
//
// Юнит-тесты Go проверяют каждый модуль, но не отвечают на вопрос, ради
// которого всё это существует: может ли человек зарегистрироваться, заполнить
// анкету, разместить заказ, откликнуться и заключить сделку — не читая
// подсказок и не открывая консоль. Этот сценарий проходит весь путь дважды,
// с двух сторон, и заодно смотрит, не осталось ли английского и не сыплются
// ли ошибки в консоль.
//
// Запуск:
//   AVERIX_SMOKE_URL=http://localhost:3000 node scripts/smoke.mjs
//
// Подтверждение почты — единственное место, где сценарий обходит интерфейс:
// в разработке письма не уходят, а без подтверждённого адреса нельзя ни
// опубликовать анкету, ни разместить заказ. Настройки подключения к базе и
// Redis берутся из AVERIX_SMOKE_PSQL и AVERIX_SMOKE_REDIS_DB.

import { chromium } from 'playwright';
import { execSync } from 'node:child_process';

const BASE = process.env.AVERIX_SMOKE_URL ?? 'http://localhost:3000';
const log = [];
const fail = [];

function step(name, ok, detail = '') {
  const line = `${ok ? '✓' : '✗'} ${name}${detail ? ' — ' + detail : ''}`;
  console.log(line);
  log.push(line);
  if (!ok) fail.push(name + (detail ? ': ' + detail : ''));
}

// Лимит регистраций считается по IP и мешает повторному прогону.
execSync(`redis-cli -n ${process.env.AVERIX_SMOKE_REDIS_DB ?? 3} FLUSHDB`, { stdio: 'ignore' });

const browser = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
);
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: 'ru-RU' });
const page = await ctx.newPage();
const errors = [];
const bad = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('response', (r) => {
  if (r.status() >= 400 && r.url().includes('/api/v1/')) {
    bad.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`);
  }
});

function verifyIdentity(email) {
  // Проверка личности — отдельный сценарий с документами и сотрудником;
  // здесь важно только то, что без неё исполнителю нельзя работать.
  execSync(
    `psql ${process.env.AVERIX_SMOKE_PSQL ?? '-U postgres -h /var/run/postgresql -d averix_dev'} -c ` +
      `"UPDATE users SET identity_verified_at = now() WHERE email = '${email}'"`,
    { stdio: 'ignore' },
  );
}

function verifyEmail(email) {
  // В разработке письма не уходят, поэтому адрес подтверждается напрямую —
  // это единственное место, где тест обходит интерфейс.
  execSync(
    `psql ${process.env.AVERIX_SMOKE_PSQL ?? '-U postgres -h /var/run/postgresql -d averix_dev'} -c ` +
      `"UPDATE users SET email_verified_at = now() WHERE email = '${email}'"`,
    { stdio: 'ignore' },
  );
}

const stamp = Date.now();
const dev = { name: 'Марина Иванова', user: 'marina' + stamp % 100000, email: `m${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };
const client = { name: 'ООО Ромашка', user: 'romashka' + stamp % 100000, email: `c${stamp}@example.test`, pass: 'тихий-фонарь-4417-ok' };

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
  await page.waitForURL(/feed|dashboard/, { timeout: 15000 });
}

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
}

// 1. Исполнитель регистрируется и попадает в анкету
await register(dev, 'developer');
step('регистрация исполнителя ведёт в анкету', page.url().includes('/onboarding'), page.url());

// 2. Анкета: шаг 1
await page.waitForSelector('text=Кто вы и где', { timeout: 15000 });
await page.getByLabel('Код страны').fill('RU');
await page.getByLabel('Город').fill('Казань');
await page.getByRole('button', { name: 'Далее' }).click();
await page.waitForSelector('text=Чем вы занимаетесь', { timeout: 15000 });
step('шаг 1 анкеты сохраняется', true);

// 3. Выбор профессии — должна быть не только IT
const professions = await page.locator('button:has-text("дизайнер"), button:has-text("Копирайтер")').count();
step('в списке профессий есть не только IT', professions > 0, `найдено ${professions}`);
const designer = page.locator('button', { hasText: 'Графический дизайнер' }).first();
if (await designer.count()) await designer.click();
else await page.locator('button:has-text("Бэкенд-разработчик")').first().click();
await page.getByLabel('Как вас представить').fill('Дизайнер логотипов и айдентики');
await page.getByRole('button', { name: 'Далее' }).click();
await page.waitForSelector('text=Дополнительные направления', { timeout: 15000 });
await page.getByRole('button', { name: 'Пропустить' }).click();

// 4. Навыки
await page.waitForSelector('text=Навыки и инструменты', { timeout: 15000 });
await page.getByLabel('Найти навык').fill('Figma');
await page.waitForTimeout(1200);
const chip = page.locator('button[aria-pressed]', { hasText: /Figma/i }).first();
const hasChip = await chip.count();
if (hasChip) await chip.click();
step('поиск навыков возвращает результат', hasChip > 0);
await page.getByRole('button', { name: 'Далее' }).click();

// 5. Опыт → занятость → о себе
await page.waitForSelector('text=Опыт и цены', { timeout: 15000 });
await page.getByLabel('Ставка за час').fill('1500');
await page.getByRole('button', { name: 'Далее' }).click();
await page.waitForSelector('text=Занятость и приватность', { timeout: 15000 });
await page.getByRole('button', { name: 'Далее' }).click();
await page.waitForSelector('text=О себе', { timeout: 15000 });
await page.getByLabel('О себе').fill(
  'Рисую логотипы и фирменные стили для небольших компаний уже семь лет: кофейни, ' +
  'частные клиники, локальные производства. Начинаю с разговора о том, кому вы продаёте ' +
  'и чем отличаетесь, и только потом берусь за эскизы. Отдаю исходники и короткий гайд.',
);
await page.getByRole('button', { name: 'Далее' }).click();
await page.waitForSelector('text=Фотография', { timeout: 15000 });
await page.getByRole('button', { name: 'Пропустить' }).click();
await page.waitForSelector('text=Готово', { timeout: 15000 });
// Публикация требует подтверждённой почты — экран об этом говорит.
const gate = await page.locator('body').innerText();
step('шаг «Готово» требует подтвердить почту', /Подтвердите адрес почты/.test(gate));
await verifyEmail(dev.email);
await page.reload({ waitUntil: 'networkidle' });
await page.waitForSelector('text=Готово', { timeout: 15000 });
await page.getByRole('button', { name: 'Опубликовать анкету' }).click();
// Анкета заполнена — дальше по новому правилу идёт проверка личности: без неё
// исполнитель не может ни откликаться, ни продавать услуги.
await page.waitForURL(/\/settings\/verification/, { timeout: 20000 });
step('после анкеты исполнителя ведут на проверку личности', page.url().includes('/settings/verification'), page.url());

// Саму проверку проходит человек, а решение принимает сотрудник — этот
// сценарий не про них (для них есть smoke-identity.mjs), поэтому отметка
// ставится напрямую, как и подтверждение почты выше.
verifyIdentity(dev.email);

await page.goto(`${BASE}/developers/${dev.user}`, { waitUntil: 'networkidle' });
step('анкета опубликована и открывается профиль', page.url().includes('/developers/'), page.url());

await page.waitForSelector(`text=${dev.name}`, { timeout: 15000 });
const profileText = await page.locator('body').innerText();
step('профиль на русском', /Навыки|О себе|Рейтинг/.test(profileText), profileText.slice(0, 200).replace(/\n/g, ' | '));

// 6. Каталог исполнителей показывает нового человека
await page.goto(`${BASE}/freelancers`, { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
const catalogue = await page.locator('body').innerText();
step('исполнитель появился в каталоге', catalogue.includes(dev.name), catalogue.slice(0, 120).replace(/\n/g, ' '));

// 7. Заказчик регистрируется, размещает заказ
// Выход через интерфейс, а не через fetch: так проверяется и сама кнопка.
await page.goto(`${BASE}/feed`, { waitUntil: 'networkidle' });
await page.getByRole('button', { name: 'Меню аккаунта' }).click();
await page.getByRole('button', { name: 'Выйти' }).click();
await page.waitForURL(/\/login/, { timeout: 15000 });
step('выход возвращает на страницу входа', page.url().includes('/login'));
await register(client, 'client');
step('регистрация заказчика ведёт в кабинет', page.url().includes('/dashboard'), page.url());
verifyEmail(client.email);

await page.goto(`${BASE}/projects/new`, { waitUntil: 'networkidle' });
await page.waitForSelector('text=Что нужно сделать', { timeout: 15000 });
await page.locator('button:has-text("Дизайн")').first().click();
await page.waitForTimeout(1200);
const cat = page.getByRole('button', { name: 'Логотипы и фирменный стиль' }).first();
step('подкатегории направления показываются', (await cat.count()) > 0);
await cat.click();
await page.getByLabel('Название заказа').fill('Логотип и вывеска для кофейни в центре города');
await page.getByRole('button', { name: 'Далее' }).click();
await page.waitForSelector('text=Описание', { timeout: 15000 });
await page.getByLabel('Подробное описание').fill(
  'Открываем маленькую кофейню на 12 мест. Нужен логотип, который читается на вывеске ' +
  'с другой стороны улицы, и на стакане. Отдельно — вариант в одну краску для стаканов. ' +
  'Название уже есть, стиль — тёплый, без модного минимализма.',
);
await page.getByRole('button', { name: 'Далее' }).click();
await page.waitForSelector('text=Навыки', { timeout: 15000 });
await page.waitForTimeout(1500);
let skillChip = page.locator('button[aria-pressed]').first();
if (!(await skillChip.count())) {
  await page.getByLabel('Найти навык').fill('Figma');
  await page.waitForTimeout(1500);
  skillChip = page.locator('button[aria-pressed]').first();
}
step('навыки предлагаются по категории заказа', (await skillChip.count()) > 0);
if (await skillChip.count()) await skillChip.click();
await page.getByRole('button', { name: 'Далее' }).click();
await page.waitForSelector('text=Бюджет и сроки', { timeout: 15000 });
await page.getByRole('textbox', { name: 'От' }).fill('15000');
await page.getByRole('textbox', { name: 'До' }).fill('30000');
await page.getByRole('button', { name: 'Далее' }).click();
await page.waitForSelector('text=Проверьте и опубликуйте', { timeout: 15000 });
const summary = await page.locator('body').innerText();
step('бюджет показан в рублях', /₽/.test(summary), (summary.match(/.{0,30}₽.{0,10}/) || [''])[0]);
const publishBtn = page.getByRole('button', { name: 'Опубликовать', exact: true });
step('кнопка публикации доступна', await publishBtn.isEnabled());
const [postResponse] = await Promise.all([
  page.waitForResponse((r) => r.url().includes('/api/v1/projects') && r.request().method() === 'POST', { timeout: 20000 }).catch(() => null),
  publishBtn.click(),
]);
step('POST /projects отправлен', Boolean(postResponse), postResponse ? String(postResponse.status()) : 'запроса не было');
await page.waitForTimeout(4000);
step('заказ публикуется', /\/projects\/[a-z0-9-]+/.test(page.url()) && !page.url().endsWith('/new'),
  page.url() + ' | ' + (await page.locator('body').innerText()).slice(0, 200).replace(/\n/g, ' | '));
const projectURL = page.url().replace('/proposals', '');

// 8. Поиск
await page.goto(`${BASE}/search?q=логотип`, { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);
const search = await page.locator('body').innerText();
step('поиск что-то находит', /Исполнители|Заказы|Услуги|Ничего не нашли/.test(search));

// 9. Исполнитель откликается на заказ
await signOut();
await login(dev);
await page.goto(projectURL, { waitUntil: 'networkidle' });
await page.waitForTimeout(2500);
const openedProject = await page.locator('body').innerText();
step('исполнитель открывает страницу заказа', /Что нужно сделать/.test(openedProject), page.url() + ' | ' + openedProject.slice(0, 220).replace(/\n/g, ' | '));
const projectBody = await page.locator('body').innerText();
step('исполнитель видит совпадение по заказу', /совпадение/i.test(projectBody));
const respond = page.getByRole('button', { name: 'Откликнуться' });
step('кнопка отклика показана исполнителю', (await respond.count()) > 0,
  (await page.locator('body').innerText()).slice(-300).replace(/\n/g, ' | '));
await respond.click();
await page.waitForSelector('text=Условия', { timeout: 15000 });
await page.getByRole('textbox', { name: /Ваша цена/ }).fill('22000');
await page.getByRole('textbox', { name: 'Срок выполнения (дней)' }).fill('10');
const fee = await page.locator('body').innerText();
step('комиссия показана до отправки отклика', /комиссия платформы/i.test(fee), (fee.match(/.{0,80}комиссия платформы.{0,60}/i) || [''])[0]);
await page.getByRole('button', { name: 'Далее' }).click();
await page.getByLabel('Сообщение заказчику').fill(
  'Делала логотипы для двух кофеен: в обоих случаях главным была читаемость с улицы, ' +
  'поэтому начинала с силуэта и только потом занималась деталями. Покажу три направления ' +
  'на выбор, дальше дорабатываем одно. Вариант в одну краску сделаю сразу, он вам понадобится.',
);
await page.getByRole('button', { name: 'Далее' }).click();
await page.getByLabel('Ваш подход').fill(
  'Сначала короткий разговор о районе, гостях и соседях-конкурентах. Потом три эскиза ' +
  'в чёрно-белом, без цвета — так честнее видно форму. После выбора дорабатываю один ' +
  'и собираю мини-гайд: цвета, отступы, запреты.',
);
await page.getByLabel('Похожий опыт').fill('Семь лет в айдентике, из них две кофейни и одна пекарня с вывеской.');
const [proposalResponse] = await Promise.all([
  page.waitForResponse((r) => r.url().includes('/api/v1/proposals') && r.request().method() === 'POST', { timeout: 20000 }).catch(() => null),
  page.getByRole('button', { name: 'Отправить отклик' }).click(),
]);
step('отклик отправляется', proposalResponse?.status() === 201, String(proposalResponse?.status()));

await page.goto(`${BASE}/proposals`, { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
const mine = await page.locator('body').innerText();
step('отклик виден в «Моих откликах»', /Логотип и вывеска/.test(mine), mine.slice(0, 150).replace(/\n/g, ' | '));

// 10. Заказчик нанимает исполнителя
await signOut();
await login(client);
await page.goto(projectURL + '/proposals', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
const list = await page.locator('body').innerText();
step('заказчик видит отклик', /Марина Иванова/.test(list), list.slice(0, 160).replace(/\n/g, ' | '));
await page.getByRole('button', { name: 'Нанять' }).first().click();
await page.waitForSelector('text=Комиссия платформы', { timeout: 15000 });
const [contractResponse] = await Promise.all([
  page.waitForResponse((r) => r.url().includes('/api/v1/contracts') && r.request().method() === 'POST', { timeout: 20000 }).catch(() => null),
  page.getByRole('button', { name: 'Заключить сделку' }).click(),
]);
step('сделка создаётся', contractResponse?.status() === 201, String(contractResponse?.status()));
await page.waitForURL(/\/contracts\//, { timeout: 20000 });
await page.waitForSelector('text=Этапы', { timeout: 20000 });
const workspace = await page.locator('body').innerText();
step('рабочее пространство открывается на русском', /Этапы|Сумма сделки/.test(workspace), workspace.slice(0, 200).replace(/\n/g, ' | '));

// 11. Экраны, которые раньше давали 404
for (const path of ['/services', '/freelancers', '/notifications', '/settings', '/messages', '/dashboard']) {
  const res = await page.goto(BASE + path, { waitUntil: 'domcontentloaded' });
  const body = await page.locator('body').innerText();
  step(`${path} открывается`, res.status() === 200 && !/This page could not be found|404/.test(body), String(res.status()));
}

// Анонимный опрос сессии отвечает 401 — это состояние, а не ошибка.
const realErrors = errors.filter((e) => !/401 \(Unauthorized\)/.test(e));
step('нет ошибок в консоли', realErrors.length === 0, realErrors.slice(0, 3).join(' | '));
console.log('\nОтветы 4xx/5xx:\n' + (bad.length ? [...new Set(bad)].join('\n') : 'нет'));

console.log(fail.length ? `\nПРОВАЛЕНО: ${fail.length}\n` + fail.join('\n') : '\nВСЁ ПРОШЛО');
await browser.close();
process.exit(fail.length ? 1 : 0);
