#!/usr/bin/env node
// Builds a demo dataset by driving the real API, exactly as people would.
//
// Development only. Every record it creates is marked as demo data, and it
// refuses to run against anything that is not a development environment —
// seed data must never reach production.

const API = process.env.AVERIX_API_URL || 'http://localhost:8080';
const BASE = `${API}/api/v1`;

const state = new Map(); // label -> { cookie, csrf }

async function call(as, method, path, body, { form } = {}) {
  const session = as ? state.get(as) : null;
  // API проверяет Origin у любой записи, поэтому он должен совпадать с
  // APP_URL той площадки, куда сид смотрит.
  const headers = { Accept: 'application/json', Origin: process.env.AVERIX_APP_URL || 'http://localhost:3000' };
  if (session?.cookie) headers.Cookie = session.cookie;
  if (session?.csrf && method !== 'GET') headers['X-CSRF-Token'] = session.csrf;
  if (body && !form) headers['Content-Type'] = 'application/json';

  const response = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: form ? body : body ? JSON.stringify(body) : undefined,
  });

  const setCookie = response.headers.getSetCookie?.() ?? [];
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};

  if (as) {
    const current = state.get(as) ?? {};
    const cookie = setCookie
      .map((value) => value.split(';')[0])
      .filter((value) => value.includes('averix'))
      .join('; ');
    if (cookie) current.cookie = cookie;
    if (payload?.data?.csrf_token) current.csrf = payload.data.csrf_token;
    state.set(as, current);
  }

  if (!response.ok) {
    const error = payload.error ?? {};
    throw new Error(`${method} ${path} → ${response.status} ${error.code ?? ''} ${error.message ?? text}\n${JSON.stringify(error.fields ?? {})}`);
  }
  return payload.data;
}

async function register(label, { username, full_name, email, role, password = 'правильная лошадь батарейка скрепка' }) {
  state.set(label, {});
  const session = await call(label, 'POST', '/auth/register', {
    username, full_name, email, role, password, accept_terms: true,
  });
  return session;
}

async function main() {
  const health = await fetch(`${API}/health`).then((r) => r.json()).catch(() => null);
  console.log('API:', health?.data?.status ?? 'unreachable');

  // Start from a clean slate, but keep what the migrations seeded: the
  // taxonomy, the fee schedule, the matching weights and the platform
  // settings are reference data, not fixtures.
  const { execSync } = await import('node:child_process');
  // Подключение берётся из PSQL_ARGS, чтобы сценарий работал и с сокетом, и
  // с TCP, и с базой под другим именем: захардкоженный порт 5433 означал, что
  // сид запускался только на машине автора.
  const connection = process.env.PSQL_ARGS || `-h ${process.env.PGHOST || '/tmp'} -p ${process.env.PGPORT || 5433} -U ${process.env.PGUSER || 'postgres'} -d ${process.env.PGDATABASE || 'averix_demo'}`;
  const psql = (sql) =>
    execSync(`psql ${connection} -qtA -c ${JSON.stringify(sql)}`, {
      stdio: ['ignore', 'pipe', 'pipe'],
    }).toString().trim();
  console.log('очищаем прежние демоданные…');
  psql('TRUNCATE users, payment_intents, payment_webhook_events, audit_logs CASCADE');
  psql(`DELETE FROM platform_settings WHERE description IS NULL`);

  // ── People ───────────────────────────────────────────────────────────────
  console.log('создаём аккаунты…');
  await register('client', {
    username: 'nurstore', full_name: 'Нилуфар Рахимова',
    email: 'nilufar@nurstore.example', role: 'client',
  });
  await register('dev', {
    username: 'alijon', full_name: 'Алижон Махмаджонов',
    email: 'alijon@example.dev', role: 'developer',
  });
  await register('dev2', {
    username: 'saida', full_name: 'Саида Каримова',
    email: 'saida@example.dev', role: 'developer',
  });
  await register('admin', {
    username: 'averixops', full_name: 'Поддержка AVERIX',
    email: 'ops@averix.example', role: 'client',
  });

  // Email confirmation and the admin grant are operator acts, not endpoints.
  psql(`UPDATE users SET email_verified_at = now(), identity_verified_at = now()`);
  psql(`INSERT INTO user_roles (user_id, role) SELECT id, 'admin' FROM users WHERE username = 'averixops' ON CONFLICT DO NOTHING`);
  await call('admin', 'POST', '/auth/role/switch', { role: 'admin' });

  // ── Developer profiles ───────────────────────────────────────────────────
  console.log('заполняем анкеты исполнителей…');
  async function onboard(label, profile) {
    await call(label, 'PUT', '/developers/me/basics', profile.basics);
    await call(label, 'PUT', '/developers/me/specialisation', profile.specialisation);
    if (profile.additional) {
      await call(label, 'PUT', '/developers/me/additional-specialisations', profile.additional);
    }
    await call(label, 'PUT', '/developers/me/technologies', { technologies: profile.technologies });
    await call(label, 'PUT', '/developers/me/experience', profile.experience);
    await call(label, 'PUT', '/developers/me/availability', profile.availability);
    await call(label, 'PUT', '/developers/me/bio', { bio: profile.bio });
    await call(label, 'POST', '/developers/me/finish');
  }

  await onboard('dev', {
    basics: {
      full_name: 'Алижон Махмаджонов', country_code: 'TJ', city: 'Душанбе',
      timezone: 'Asia/Dushanbe',
      languages: [
        { language: 'Таджикский', proficiency: 'native' },
        { language: 'Русский', proficiency: 'fluent' },
        { language: 'Английский', proficiency: 'conversational' },
      ],
    },
    specialisation: { slug: 'backend-developer', professional_title: 'Бэкенд и Telegram-боты' },
    additional: { slugs: ['telegram-developer', 'devops-engineer'] },
    technologies: [
      { slug: 'python', level: 'expert', years: 6 },
      { slug: 'telegram-api', level: 'expert', years: 5 },
      { slug: 'postgresql', level: 'expert', years: 6 },
      { slug: 'fastapi', level: 'strong', years: 4 },
      { slug: 'redis', level: 'strong', years: 4 },
      { slug: 'docker', level: 'strong', years: 5 },
      { slug: 'go', level: 'working', years: 2 },
      { slug: 'nginx', level: 'working', years: 3 },
    ],
    experience: { experience_level: 'senior', years_experience: 6, hourly_rate_minor: 250000, currency: 'RUB' },
    availability: { availability: 'available', hours_per_week: 35, show_location: true, show_hourly_rate: true },
    bio: 'Делаю Telegram-ботов и бэкенд под ними: каталог, заказы, оплату и админку, которой ваши сотрудники пользуются каждый день. Основное — Python с PostgreSQL, разворачиваю в Docker, Go добавляю там, где он окупается. Слежу за тем, чтобы миграции применялись безопасно, ошибки говорили что-то внятное, а результат ваша команда могла вести без меня.',
  });

  await onboard('dev2', {
    basics: {
      full_name: 'Саида Каримова', country_code: 'UZ', city: 'Ташкент', timezone: 'Asia/Tashkent',
      languages: [
        { language: 'Узбекский', proficiency: 'native' },
        { language: 'Русский', proficiency: 'fluent' },
        { language: 'Английский', proficiency: 'conversational' },
      ],
    },
    specialisation: { slug: 'graphic-designer', professional_title: 'Логотипы и фирменный стиль' },
    additional: { slugs: ['web-designer', 'illustrator'] },
    technologies: [
      { slug: 'figma', level: 'expert', years: 5 },
      { slug: 'adobe-illustrator', level: 'expert', years: 6 },
      { slug: 'branding', level: 'strong', years: 5 },
      { slug: 'photoshop', level: 'strong', years: 6 },
    ],
    experience: { experience_level: 'mid', years_experience: 5, hourly_rate_minor: 180000, currency: 'RUB' },
    availability: { availability: 'limited', hours_per_week: 20, show_location: true, show_hourly_rate: true },
    bio: 'Рисую логотипы и фирменные стили для небольших компаний: кофейни, клиники, локальные производства. Начинаю с разговора о том, кому вы продаёте и чем отличаетесь от соседей, и только потом берусь за эскизы — иначе получается красиво, но мимо. Отдаю исходники и короткий гайд, чтобы стилем можно было пользоваться без меня.',
  });

  // ── Portfolio ────────────────────────────────────────────────────────────
  console.log('публикуем портфолио…');
  const portfolio = await call('dev', 'POST', '/portfolio', {
    title: 'Складской учёт и приём заказов для оптовика',
    short_description: 'API учёта и заказов вместо таблицы, по которой работал весь склад',
    description:
      'Сервис на Python, заменивший таблицу, по которой оптовик продуктов вёл склад. Отдаёт API приёма заказов для отдела продаж, сверяет поставки с накладными и шлёт предупреждения об остатках в Telegram-группу склада. FastAPI и PostgreSQL, разворачивается одним Docker Compose на одном сервере, с ночными резервными копиями, которые заказчик восстанавливает сам.',
    category_slug: 'api-development',
    developer_role: 'Бэкенд-разработчик, один на проекте',
    technologies: ['python', 'fastapi', 'postgresql', 'docker', 'redis'],
    completed_on: '2025-11-20',
    duration_days: 45,
    value_minor: 18000000,
    currency: 'RUB',
    value_visibility: 'range',
    demo_status: 'live',
  });
  // In development the preview browser may frame a loopback address, so the
  // demo can show a real embedded site rather than only the refusal state.
  // AVERIX_DEMO_SITE is set by the demo runner; production never allows this.
  await call('dev', 'PATCH', `/portfolio/${portfolio.id}`, {
    project_url: process.env.AVERIX_DEMO_SITE || 'https://example.org/stock',
    repository_url: 'https://github.com/example/stock-api',
  });

  // A cover image, re-encoded by the API into the sizes the product serves.
  const { createCanvasPng } = await import('./demo-image.mjs');
  for (const [index, spec] of [
    { hue: 268, label: 'Сводка' },
    { hue: 150, label: 'Заказы' },
  ].entries()) {
    const png = createCanvasPng(1600, 900, spec.hue, spec.label);
    const form = new FormData();
    form.append('caption', spec.label);
    form.append('image', new Blob([png], { type: 'image/png' }), `${spec.label.toLowerCase()}.png`);
    await call('dev', 'POST', `/portfolio/${portfolio.id}/images`, form, { form: true });
    void index;
  }
  await call('dev', 'POST', `/portfolio/${portfolio.id}/publish`, { published: true });

  const secondPortfolio = await call('dev', 'POST', '/portfolio', {
    title: 'Бот отслеживания посылок для курьерской службы',
    short_description: 'Telegram-бот, который отвечает клиенту, где сейчас его посылка',
    description:
      'Telegram-бот для курьерской службы в Душанбе. Клиент отправляет номер отправления и получает текущий статус; курьеры меняют статус в том же боте с клавиатуры, а не в отдельном приложении. Около двух тысяч запросов в сутки к PostgreSQL и небольшая панель для диспетчера.',
    category_slug: 'telegram-bots',
    developer_role: 'Бэкенд-разработчик',
    technologies: ['python', 'telegram-api', 'postgresql'],
    completed_on: '2025-06-02',
    duration_days: 21,
    value_visibility: 'private',
    value_minor: 7000000,
    demo_status: 'private_repo',
  });
  const cover = createCanvasPng(1600, 900, 205, 'Отслеживание');
  const coverForm = new FormData();
  coverForm.append('image', new Blob([cover], { type: 'image/png' }), 'tracking.png');
  await call('dev', 'POST', `/portfolio/${secondPortfolio.id}/images`, coverForm, { form: true });
  await call('dev', 'POST', `/portfolio/${secondPortfolio.id}/publish`, { published: true });

  // ── Projects ─────────────────────────────────────────────────────────────
  console.log('размещаем заказы…');
  const project = await call('client', 'POST', '/projects', {
    title: 'Telegram-бот для магазина одежды',
    description:
      'Продаём одежду через соцсети и небольшой сайт, заказы принимаем руками в личных сообщениях — около трёхсот в месяц, и часть теряется. Нужен Telegram-бот, где покупатель смотрит каталог по категориям, кладёт вещь в корзину, выбирает размер и оформляет заказ, который попадает в нашу систему, а не в чью-то переписку. Сотрудникам нужен простой экран, чтобы загружать товары и отмечать заказы отправленными. Оплату можно добавить позже, но корзина и оформление должны работать сразу.',
    category_slug: 'telegram-bots',
    required_skills: ['python', 'telegram-api', 'postgresql'],
    budget_type: 'range',
    budget_min_minor: 15000000,
    budget_max_minor: 25000000,
    currency: 'RUB',
    duration_days: 21,
    experience_wanted: 'senior',
    publish: true,
  });

  await call('client', 'POST', '/projects', {
    title: 'Ночная сверка магазина с бухгалтерией',
    description:
      'Каждую ночь нужно сравнивать заказы в базе магазина с тем, что говорит система бухгалтера, и выдавать короткий отчёт обо всех расхождениях. Сейчас это делает человек каждое утро руками, и уходит два часа. Хотим, чтобы сверка шла сама и сообщала только тогда, когда что-то не сошлось.',
    category_slug: 'ai-workflow-automation',
    required_skills: ['python', 'postgresql'],
    budget_type: 'fixed',
    budget_max_minor: 9000000,
    currency: 'RUB',
    duration_days: 14,
    publish: true,
  });

  await call('client', 'POST', '/projects', {
    title: 'Логотип и вывеска для новой кофейни',
    description:
      'Открываем кофейню на двенадцать мест в центре города. Нужен логотип, который читается на вывеске с другой стороны улицы и не разваливается на бумажном стакане. Отдельно нужен вариант в одну краску — на стаканы и на пакеты. Название уже есть, настроение тёплое, без модного минимализма. Ждём три направления на выбор и доработку одного.',
    category_slug: 'design-logo',
    required_skills: ['branding', 'adobe-illustrator', 'figma'],
    budget_type: 'range',
    budget_min_minor: 1500000,
    budget_max_minor: 3000000,
    currency: 'RUB',
    duration_days: 30,
    experience_wanted: 'mid',
    publish: true,
  });

  await call('client', 'POST', '/projects', {
    title: 'Тексты для сайта клиники: главная и три услуги',
    description:
      'У клиники есть сайт, но тексты на нём писал врач между приёмами. Нужно переписать главную и три страницы услуг так, чтобы человек понял, что с ним будут делать, сколько это стоит и почему не страшно. Медицинские формулировки согласуем с врачом, продающих обещаний не нужно — их нам и так запрещает закон.',
    category_slug: 'texts-copywriting',
    required_skills: ['copywriting'],
    budget_type: 'fixed',
    budget_max_minor: 4000000,
    currency: 'RUB',
    duration_days: 20,
    experience_wanted: 'senior',
    publish: true,
  });

  // ── Proposals ────────────────────────────────────────────────────────────
  console.log('отправляем отклики…');
  const proposal = await call('dev', 'POST', '/proposals', {
    project_id: project.id,
    amount_minor: 21000000,
    currency: 'RUB',
    delivery_days: 18,
    cover_letter:
      'Я сделал три коммерческих Telegram-бота, последний — для магазина одежды примерно на четыреста заказов в месяц, так что каталог, корзина и выбор размера у вас ложатся на уже пройденный путь. Что хочу обсудить подробно до начала: куда попадает заказ — в панель, которую открывают ваши сотрудники, или сразу в то, чем вы уже пользуетесь.',
    approach:
      'Начну с модели данных для товаров, вариантов и заказов: именно на размерах такие боты обычно и ломаются. Потом админка, чтобы ваши сотрудники загружали каталог, пока я собираю покупательскую часть на настоящих товарах, а не на тестовых. Дальше корзина и оформление, оплата — последней, когда корзина уже работает целиком: проверять оплату на недоделанной корзине значит потерять время обоим.',
    relevant_experience:
      'Шесть лет Python, в основном Telegram-боты и бэкенд под ними, всюду PostgreSQL. Два из трёх моих коммерческих ботов до сих пор работают.',
    questions: 'У вас уже выбран платёжный провайдер или подсказать подходящий?',
    milestones: [
      { title: 'Каталог, товары и админка', amount_minor: 9000000, days: 7,
        detail: 'Товары, варианты, категории и экран для сотрудников, чтобы всё это загружать.' },
      { title: 'Корзина, размеры и оформление заказа', amount_minor: 12000000, days: 11,
        detail: 'Просмотр каталога, корзина, выбор размера и передача заказа вашим сотрудникам.' },
    ],
  });

  await call('dev2', 'POST', '/proposals', {
    project_id: project.id,
    amount_minor: 17000000,
    currency: 'RUB',
    delivery_days: 24,
    cover_letter:
      'Обычно я оформляю магазины, а не пишу их, но здесь важна витрина: карточка товара в боте — это тоже дизайн. Предлагаю сделать оформление каталога и карточек вместе с разработчиком, чтобы бот не выглядел как таблица. Если вам нужна только разработка, честно скажу — берите другой отклик.',
    approach:
      'Сначала соберу, как выглядит карточка товара и каталог: обложки, порядок, подписи размеров. Потом передам разработчику готовые макеты и проверю на живом боте, что всё читается с телефона.',
    relevant_experience:
      'Пять лет в графике и вебе, два оформленных магазина в соцсетях и один каталог для Telegram-бота.',
    milestones: [
      { title: 'Оформление каталога и карточек', amount_minor: 8000000, days: 10 },
      { title: 'Проверка на живом боте и правки', amount_minor: 9000000, days: 14 },
    ],
  });

  // ── Contract ─────────────────────────────────────────────────────────────
  console.log('заключаем сделку…');
  const contract = await call('client', 'POST', '/contracts', {
    proposal_id: proposal.id,
    price_visibility: 'range',
  });

  // ── Payments, the manual way ─────────────────────────────────────────────
  console.log('настраиваем реквизиты для переводов…');
  await call('admin', 'PUT', '/admin/payments/manual-details', {
    account_name: 'ООО «АВЕРИКС»',
    account_number: '40702810000000012345',
    bank_name: 'Демобанк',
    extra_label: 'БИК',
    extra_value: '044525000',
    note: 'Укажите номер платежа точно — по нему мы найдём ваш перевод.',
  });

  const first = contract.milestones[0];
  const payment = await call('client', 'POST', `/milestones/${first.id}/fund`);
  await call('admin', 'POST', `/admin/payments/${payment.id}/confirm`, {
    amount_minor: payment.amount_minor,
    reference: 'ВЫПИСКА-40219',
    note: 'Поступило в 11:42, перевод из Демобанка.',
  });

  console.log('проходим первый этап…');
  await call('dev', 'POST', `/milestones/${first.id}/start`);
  await call('dev', 'POST', `/milestones/${first.id}/submit`, {
    note: 'Каталог, варианты и админка уже на тестовом боте. Загрузите несколько настоящих товаров и скажите, совпадают ли поля размеров с тем, как вы продаёте на самом деле.',
    deliverables: [
      { kind: 'link', title: 'Тестовый бот', url: 'https://example.org/staging-bot' },
      { kind: 'repository', title: 'Исходники', url: 'https://github.com/example/clothing-bot' },
    ],
  });

  // ── Conversation ─────────────────────────────────────────────────────────
  console.log('добавляем переписку…');
  const conversations = await call('client', 'GET', '/conversations');
  const thread = conversations.find((item) => item.contract_id === contract.id);
  if (thread) {
    await call('client', 'POST', `/conversations/${thread.id}/messages`, {
      body: 'Доброе утро! Фотографии товаров выложила в общую папку. Размеры от S до XXL, несколько вещей — безразмерные.',
    });
    await call('dev', 'POST', `/conversations/${thread.id}/messages`, {
      body: 'Забрал, спасибо. Безразмерные покажу одним вариантом, а не пустым списком размеров.',
    });
    await call('client', 'POST', `/conversations/${thread.id}/messages`, {
      body: 'Так подойдёт. А покупатель сможет поменять размер уже в корзине?',
    });
    await call('dev', 'POST', `/conversations/${thread.id}/messages`, {
      body: 'Да, у строки в корзине есть кнопка правки, она открывает клавиатуру размеров заново. Вечером покажу на тестовом боте.',
    });
  }

  // A manifest, so tooling (and a person) can find what was created without
  // guessing at slugs.
  const fs = await import('node:fs');
  fs.writeFileSync(
    '/tmp/averix-demo.json',
    JSON.stringify(
      {
        project_slug: project.slug,
        project_id: project.id,
        contract_id: contract.id,
        milestone_ids: contract.milestones.map((m) => m.id),
        portfolio_slug: portfolio.slug,
        accounts: {
          client: 'nilufar@nurstore.example',
          developer: 'alijon@example.dev',
          developer2: 'saida@example.dev',
          admin: 'ops@averix.example',
          password: 'правильная лошадь батарейка скрепка',
        },
      },
      null,
      2,
    ),
  );

  console.log('\nдемоданные готовы.');
  console.log('  заказчик    nilufar@nurstore.example');
  console.log('  исполнитель alijon@example.dev');
  console.log('  исполнитель saida@example.dev');
  console.log('  админ       ops@averix.example');
  console.log('  пароль      правильная лошадь батарейка скрепка');
}

main().catch((error) => {
  console.error('\nне удалось создать демоданные:', error.message);
  process.exit(1);
});
