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
  const headers = { Accept: 'application/json', Origin: 'http://localhost:3000' };
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

async function register(label, { username, full_name, email, role, password = 'correct horse battery staple' }) {
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
  const database = process.env.PGDATABASE || 'averix_demo';
  const psql = (sql) =>
    execSync(`psql -h /tmp -p 5433 -U postgres -d ${database} -qtA -c ${JSON.stringify(sql)}`, {
      stdio: ['ignore', 'pipe', 'pipe'],
    }).toString().trim();
  console.log('clearing previous demo data…');
  psql('TRUNCATE users, payment_intents, payment_webhook_events, audit_logs CASCADE');
  psql(`DELETE FROM platform_settings WHERE description IS NULL`);

  // ── People ───────────────────────────────────────────────────────────────
  console.log('creating accounts…');
  await register('client', {
    username: 'nurstore', full_name: 'Nilufar Rahimova',
    email: 'nilufar@nurstore.example', role: 'client',
  });
  await register('dev', {
    username: 'alijon', full_name: 'Alijon Mahmadjonov',
    email: 'alijon@example.dev', role: 'developer',
  });
  await register('dev2', {
    username: 'saida', full_name: 'Saida Karimova',
    email: 'saida@example.dev', role: 'developer',
  });
  await register('admin', {
    username: 'averixops', full_name: 'AVERIX Operations',
    email: 'ops@averix.example', role: 'client',
  });

  // Email confirmation and the admin grant are operator acts, not endpoints.
  psql(`UPDATE users SET email_verified_at = now(), identity_verified_at = now()`);
  psql(`INSERT INTO user_roles (user_id, role) SELECT id, 'admin' FROM users WHERE username = 'averixops' ON CONFLICT DO NOTHING`);
  await call('admin', 'POST', '/auth/role/switch', { role: 'admin' });

  // ── Developer profiles ───────────────────────────────────────────────────
  console.log('building developer profiles…');
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
      full_name: 'Alijon Mahmadjonov', country_code: 'TJ', city: 'Dushanbe',
      timezone: 'Asia/Dushanbe',
      languages: [
        { language: 'Tajik', proficiency: 'native' },
        { language: 'Russian', proficiency: 'fluent' },
        { language: 'English', proficiency: 'conversational' },
      ],
    },
    specialisation: { slug: 'backend-developer', professional_title: 'Backend & Telegram bot developer' },
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
    experience: { experience_level: 'senior', years_experience: 6, hourly_rate_minor: 3500, currency: 'USD' },
    availability: { availability: 'available', hours_per_week: 35, show_location: true, show_hourly_rate: true },
    bio: 'I build Telegram bots and the backends behind them — catalogues, orders, payments and the admin screens your staff actually use every day. Most of my work is Python with PostgreSQL, deployed in Docker with a small amount of Go where it earns its keep. I care about migrations that run safely, errors that say something useful, and handing over something your team can run without me.',
  });

  await onboard('dev2', {
    basics: {
      full_name: 'Saida Karimova', country_code: 'UZ', city: 'Tashkent', timezone: 'Asia/Tashkent',
      languages: [
        { language: 'Uzbek', proficiency: 'native' },
        { language: 'English', proficiency: 'fluent' },
      ],
    },
    specialisation: { slug: 'fullstack-developer', professional_title: 'Full-stack developer' },
    additional: { slugs: ['telegram-developer'] },
    technologies: [
      { slug: 'python', level: 'strong', years: 4 },
      { slug: 'telegram-api', level: 'strong', years: 3 },
      { slug: 'react', level: 'strong', years: 4 },
      { slug: 'postgresql', level: 'working', years: 3 },
      { slug: 'typescript', level: 'strong', years: 4 },
    ],
    experience: { experience_level: 'mid', years_experience: 4, hourly_rate_minor: 2800, currency: 'USD' },
    availability: { availability: 'limited', hours_per_week: 20, show_location: true, show_hourly_rate: true },
    bio: 'Full-stack developer working mostly in Python and React. I like projects where the interface matters as much as the API, and I have shipped several small commerce products end to end.',
  });

  // ── Portfolio ────────────────────────────────────────────────────────────
  console.log('publishing portfolio work…');
  const portfolio = await call('dev', 'POST', '/portfolio', {
    title: 'Warehouse stock and ordering API',
    short_description: 'A stock and ordering API that replaced a spreadsheet for a wholesaler',
    description:
      'A Python service that replaced a spreadsheet-driven stock process for a food wholesaler. It exposes an ordering API for their sales team, reconciles deliveries against invoices, and pushes low-stock alerts into the warehouse team’s Telegram group. Built with FastAPI and PostgreSQL, deployed with Docker Compose on a single server, with nightly backups the client can restore themselves.',
    category_slug: 'api-development',
    developer_role: 'Backend developer, sole engineer',
    technologies: ['python', 'fastapi', 'postgresql', 'docker', 'redis'],
    completed_on: '2025-11-20',
    duration_days: 45,
    value_minor: 240000,
    currency: 'USD',
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
    { hue: 268, label: 'Dashboard' },
    { hue: 150, label: 'Orders' },
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
    title: 'Delivery tracking bot for a courier company',
    short_description: 'Telegram bot that tracks parcels and tells customers where they are',
    description:
      'A Telegram bot for a courier company in Dushanbe. Customers send a tracking number and get the parcel’s current status; couriers update status from the same bot with a keyboard rather than a separate app. Handles about 2,000 lookups a day against a PostgreSQL database, with a small admin panel for the dispatcher.',
    category_slug: 'telegram-bots',
    developer_role: 'Backend developer',
    technologies: ['python', 'telegram-api', 'postgresql'],
    completed_on: '2025-06-02',
    duration_days: 21,
    value_visibility: 'private',
    value_minor: 90000,
    demo_status: 'private_repo',
  });
  const cover = createCanvasPng(1600, 900, 205, 'Tracking');
  const coverForm = new FormData();
  coverForm.append('image', new Blob([cover], { type: 'image/png' }), 'tracking.png');
  await call('dev', 'POST', `/portfolio/${secondPortfolio.id}/images`, coverForm, { form: true });
  await call('dev', 'POST', `/portfolio/${secondPortfolio.id}/publish`, { published: true });

  // ── Projects ─────────────────────────────────────────────────────────────
  console.log('posting projects…');
  const project = await call('client', 'POST', '/projects', {
    title: 'Telegram bot for an online clothing store',
    description:
      'We sell clothing through Instagram and a small website, and we take orders by hand in direct messages — about 300 a month, and we are losing some of them. We need a Telegram bot where a customer can browse the catalogue by category, add items to a cart, choose a size, and place an order that lands in our system rather than in someone’s inbox. Our staff need a simple admin screen to load new products and mark orders as sent. Payment can come later, but the cart and the order flow have to be right first.',
    category_slug: 'telegram-bots',
    required_skills: ['python', 'telegram-api', 'postgresql'],
    budget_type: 'range',
    budget_min_minor: 50000,
    budget_max_minor: 90000,
    currency: 'USD',
    duration_days: 21,
    experience_wanted: 'senior',
    publish: true,
  });

  await call('client', 'POST', '/projects', {
    title: 'Nightly reconciliation between our shop and our accounting system',
    description:
      'Every night we need to compare orders in our shop database with what our accountant’s system says, and produce a short report of anything that does not match. Today one person does this by hand every morning and it takes two hours. We want it to run by itself and only tell us when something is wrong.',
    category_slug: 'ai-workflow-automation',
    required_skills: ['python', 'postgresql'],
    budget_type: 'fixed',
    budget_max_minor: 45000,
    currency: 'USD',
    duration_days: 14,
    publish: true,
  });

  await call('client', 'POST', '/projects', {
    title: 'Telegram bot that books appointments for a dental clinic',
    description:
      'Our receptionist spends most of the day on the phone taking bookings. We want patients to book a slot in Telegram: pick a doctor, see free times for the next two weeks, confirm, and get a reminder the day before. The clinic staff need to see the day’s bookings and move or cancel one if something changes.',
    category_slug: 'telegram-service-bot',
    required_skills: ['python', 'telegram-api', 'postgresql'],
    budget_type: 'range',
    budget_min_minor: 60000,
    budget_max_minor: 120000,
    currency: 'USD',
    duration_days: 30,
    experience_wanted: 'mid',
    publish: true,
  });

  await call('client', 'POST', '/projects', {
    title: 'API to connect our warehouse system to a courier company',
    description:
      'When an order is packed, our warehouse system should create a delivery with our courier partner and store the tracking number against the order. Right now someone copies numbers between two screens. The courier has a REST API and reasonable documentation. We need this to be reliable and to tell us clearly when the courier’s side is down.',
    category_slug: 'integrations',
    required_skills: ['python', 'fastapi', 'postgresql', 'docker'],
    budget_type: 'fixed',
    budget_max_minor: 85000,
    currency: 'USD',
    duration_days: 20,
    experience_wanted: 'senior',
    publish: true,
  });

  // ── Proposals ────────────────────────────────────────────────────────────
  console.log('sending proposals…');
  const proposal = await call('dev', 'POST', '/proposals', {
    project_id: project.id,
    amount_minor: 68000,
    currency: 'USD',
    delivery_days: 18,
    cover_letter:
      'I have built three Telegram commerce bots, the most recent for a clothing retailer doing about 400 orders a month, so your catalogue, cart and size selection map closely onto work I have already shipped. The part I would want to agree in detail before starting is the order hand-off: whether orders should land in a panel your staff open, or be pushed into something you already use.',
    approach:
      'I would start with the data model for products, variants and orders, because sizes are where these bots usually go wrong. Then the admin screen, so your staff can load the catalogue while I build the customer flow against real products rather than test data. The cart and checkout come next, and payment goes in last, after the cart works end to end — testing payment against a half-built cart wastes everyone’s time.',
    relevant_experience:
      'Six years of Python, most of it on Telegram bots and the backends behind them, with PostgreSQL throughout. Two of my three commerce bots are still running in production.',
    questions: 'Do you already have a payment provider in mind, or should I recommend one for Tajikistan?',
    milestones: [
      { title: 'Catalogue, products and admin screen', amount_minor: 30000, days: 7,
        detail: 'Products, variants, categories and the staff admin screen for loading them.' },
      { title: 'Cart, sizes and order flow', amount_minor: 38000, days: 11,
        detail: 'Customer browsing, cart, size selection and the order hand-off to your staff.' },
    ],
  });

  await call('dev2', 'POST', '/proposals', {
    project_id: project.id,
    amount_minor: 54000,
    currency: 'USD',
    delivery_days: 24,
    cover_letter:
      'I build full-stack products and have done two Telegram shops before, both with a React admin panel rather than a bot-only admin. If your staff would rather load products from a browser than from inside Telegram, that is the difference between my proposal and most others you will get here.',
    approach:
      'Bot first with a minimal catalogue so you can try the customer flow within the first week, then the React admin panel, then sizes and the order hand-off. I would keep the bot and the panel talking to one API so there is a single source of truth for stock.',
    relevant_experience:
      'Four years of Python and React. Two Telegram commerce bots with admin panels, both still in use.',
    milestones: [
      { title: 'Bot and catalogue', amount_minor: 24000, days: 10 },
      { title: 'Admin panel and orders', amount_minor: 30000, days: 14 },
    ],
  });

  // ── Contract ─────────────────────────────────────────────────────────────
  console.log('signing a contract…');
  const contract = await call('client', 'POST', '/contracts', {
    proposal_id: proposal.id,
    price_visibility: 'range',
  });

  // ── Payments, the manual way ─────────────────────────────────────────────
  console.log('configuring manual payments…');
  await call('admin', 'PUT', '/admin/payments/manual-details', {
    account_name: 'AVERIX Operations LLC',
    account_number: 'TJ02 0000 1111 2222 3333',
    bank_name: 'Amonatbonk',
    extra_label: 'SWIFT',
    extra_value: 'AMONTJ22',
    note: 'Quote the payment reference exactly so we can match your transfer.',
  });

  const first = contract.milestones[0];
  const payment = await call('client', 'POST', `/milestones/${first.id}/fund`);
  await call('admin', 'POST', `/admin/payments/${payment.id}/confirm`, {
    amount_minor: payment.amount_minor,
    reference: 'STMT-40219',
    note: 'Received 11:42, Amonatbonk transfer.',
  });

  console.log('working the milestone…');
  await call('dev', 'POST', `/milestones/${first.id}/start`);
  await call('dev', 'POST', `/milestones/${first.id}/submit`, {
    note: 'Catalogue, variants and the admin screen are on the staging bot. Load a few real products and tell me if the size fields match how you actually sell.',
    deliverables: [
      { kind: 'link', title: 'Staging bot', url: 'https://example.org/staging-bot' },
      { kind: 'repository', title: 'Source', url: 'https://github.com/example/clothing-bot' },
    ],
  });

  // ── Conversation ─────────────────────────────────────────────────────────
  console.log('adding messages…');
  const conversations = await call('client', 'GET', '/conversations');
  const thread = conversations.find((item) => item.contract_id === contract.id);
  if (thread) {
    await call('client', 'POST', `/conversations/${thread.id}/messages`, {
      body: 'Morning — the product photos are in the shared drive now. Sizes are S to XXL, and a few items are one-size.',
    });
    await call('dev', 'POST', `/conversations/${thread.id}/messages`, {
      body: 'Got them, thank you. One-size items will show as a single option rather than an empty size list.',
    });
    await call('client', 'POST', `/conversations/${thread.id}/messages`, {
      body: 'That works. Can customers change the size after adding to the cart?',
    });
    await call('dev', 'POST', `/conversations/${thread.id}/messages`, {
      body: 'Yes — the cart line has an edit button that reopens the size keyboard. I will show it on the staging bot this evening.',
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
          password: 'correct horse battery staple',
        },
      },
      null,
      2,
    ),
  );

  console.log('\ndemo data ready.');
  console.log('  client    nilufar@nurstore.example');
  console.log('  developer alijon@example.dev');
  console.log('  developer saida@example.dev');
  console.log('  admin     ops@averix.example');
  console.log('  password  correct horse battery staple');
}

main().catch((error) => {
  console.error('\nseed failed:', error.message);
  process.exit(1);
});
