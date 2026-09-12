-- 0016 reference data: the closed software taxonomy AVERIX is built around.
--
-- This is reference data, not seed data: the product cannot function without it
-- and it ships to production. Demo accounts and demo projects live in
-- scripts/seed-dev.sql and are marked is_demo.

INSERT INTO specialisations (slug, name, short_name, description, sort_order) VALUES
  ('backend-developer',   'Backend Developer',        'Backend',   'Server-side systems, APIs, data modelling and reliability.', 10),
  ('frontend-developer',  'Frontend Developer',       'Frontend',  'Interfaces, state, performance and accessibility in the browser.', 20),
  ('fullstack-developer', 'Full Stack Developer',     'Full Stack','End-to-end product delivery across client and server.', 30),
  ('telegram-developer',  'Telegram Developer',       'Telegram',  'Bots, Mini Apps and payments on the Telegram platform.', 40),
  ('mobile-developer',    'Mobile Developer',         'Mobile',    'iOS, Android and cross-platform applications.', 50),
  ('ai-automation-developer','AI / Automation Developer','AI',     'Model integration, pipelines, agents and process automation.', 60),
  ('devops-engineer',     'DevOps Engineer',          'DevOps',    'Delivery pipelines, containers, observability and infrastructure.', 70),
  ('ui-ux-designer',      'UI/UX Designer',           'UI/UX',     'Product interface and interaction design for digital products.', 80);

-- ── Categories ───────────────────────────────────────────────────────────────
INSERT INTO categories (slug, name, description, path, depth, sort_order) VALUES
  ('backend-development',  'Backend Development',  'APIs, services, data layers and server-side business logic.', 'backend-development', 0, 10),
  ('frontend-development', 'Frontend Development', 'Browser interfaces built on modern component frameworks.',    'frontend-development', 0, 20),
  ('fullstack-development','Full Stack Development','Whole-product builds spanning interface and backend.',        'fullstack-development', 0, 30),
  ('telegram-bots',        'Telegram Bots',        'Conversational bots, commerce flows and Telegram automation.', 'telegram-bots', 0, 40),
  ('telegram-mini-apps',   'Telegram Mini Apps',   'Web applications running inside the Telegram client.',         'telegram-mini-apps', 0, 50),
  ('mobile-applications',  'Mobile Applications',  'Native and cross-platform applications for phones and tablets.','mobile-applications', 0, 60),
  ('ai-automation',        'AI / Automation',      'Model integration, agents, data pipelines and workflow automation.','ai-automation', 0, 70),
  ('api-development',      'API Development',      'Public and internal APIs, SDKs and contract design.',          'api-development', 0, 80),
  ('web-applications',     'Web Applications',     'Dashboards, portals and internal tools on the web.',           'web-applications', 0, 90),
  ('saas',                 'SaaS',                 'Multi-tenant subscription products, billing and onboarding.',  'saas', 0, 100),
  ('ecommerce',            'E-commerce',           'Storefronts, carts, checkout, catalogue and fulfilment.',      'ecommerce', 0, 110),
  ('devops',               'DevOps',               'CI/CD, containers, deployment automation and observability.',  'devops', 0, 120),
  ('infrastructure',       'Infrastructure',       'Servers, networking, databases and cloud architecture.',       'infrastructure', 0, 130),
  ('ui-ux-digital',        'UI/UX for Digital Products','Interface and interaction design for software products.', 'ui-ux-digital', 0, 140),
  ('integrations',         'Integrations',         'Third-party APIs, payment gateways, CRMs and data sync.',      'integrations', 0, 150);

-- Second level: the language or platform the work is done in.
INSERT INTO categories (parent_id, slug, name, path, depth, sort_order)
SELECT p.id, v.slug, v.name, p.path || '/' || v.leaf, 1, v.sort_order
FROM (VALUES
  ('backend-development',  'backend-go',         'Go',          'go',          10),
  ('backend-development',  'backend-python',     'Python',      'python',      20),
  ('backend-development',  'backend-php',        'PHP',         'php',         30),
  ('backend-development',  'backend-nodejs',     'Node.js',     'nodejs',      40),
  ('backend-development',  'backend-java',       'Java',        'java',        50),
  ('backend-development',  'backend-dotnet',     '.NET',        'dotnet',      60),
  ('backend-development',  'backend-rust',       'Rust',        'rust',        70),
  ('backend-development',  'backend-ruby',       'Ruby',        'ruby',        80),
  ('frontend-development', 'frontend-react',     'React',       'react',       10),
  ('frontend-development', 'frontend-nextjs',    'Next.js',     'nextjs',      20),
  ('frontend-development', 'frontend-vue',       'Vue',         'vue',         30),
  ('frontend-development', 'frontend-svelte',    'Svelte',      'svelte',      40),
  ('frontend-development', 'frontend-angular',   'Angular',     'angular',     50),
  ('mobile-applications',  'mobile-ios',         'iOS',         'ios',         10),
  ('mobile-applications',  'mobile-android',     'Android',     'android',     20),
  ('mobile-applications',  'mobile-react-native','React Native','react-native',30),
  ('mobile-applications',  'mobile-flutter',     'Flutter',     'flutter',     40),
  ('ai-automation',        'ai-llm-integration', 'LLM Integration','llm-integration', 10),
  ('ai-automation',        'ai-agents',          'Agents & Tooling','agents',  20),
  ('ai-automation',        'ai-data-pipelines',  'Data Pipelines','data-pipelines', 30),
  ('ai-automation',        'ai-computer-vision', 'Computer Vision','computer-vision', 40),
  ('ai-automation',        'ai-workflow-automation','Workflow Automation','workflow-automation', 50),
  ('telegram-bots',        'telegram-commerce-bot','Commerce Bot','commerce-bot', 10),
  ('telegram-bots',        'telegram-service-bot', 'Service Bot','service-bot',  20),
  ('telegram-bots',        'telegram-admin-bot',   'Admin & Moderation','admin-bot', 30),
  ('devops',               'devops-ci-cd',       'CI/CD',       'ci-cd',       10),
  ('devops',               'devops-containers',  'Containers & Orchestration','containers', 20),
  ('devops',               'devops-observability','Observability','observability', 30),
  ('infrastructure',       'infra-cloud',        'Cloud Architecture','cloud', 10),
  ('infrastructure',       'infra-databases',    'Databases',   'databases',   20),
  ('infrastructure',       'infra-networking',   'Networking & Security','networking', 30)
) AS v(parent_slug, slug, name, leaf, sort_order)
JOIN categories p ON p.slug = v.parent_slug;

-- Third level: frameworks, where the choice genuinely changes who can do the work.
INSERT INTO categories (parent_id, slug, name, path, depth, sort_order)
SELECT p.id, v.slug, v.name, p.path || '/' || v.leaf, 2, v.sort_order
FROM (VALUES
  ('backend-go',      'go-gin',        'Gin',       'gin',        10),
  ('backend-go',      'go-fiber',      'Fiber',     'fiber',      20),
  ('backend-go',      'go-echo',       'Echo',      'echo',       30),
  ('backend-go',      'go-stdlib',     'Standard library','stdlib',40),
  ('backend-python',  'python-fastapi','FastAPI',   'fastapi',    10),
  ('backend-python',  'python-django', 'Django',    'django',     20),
  ('backend-python',  'python-flask',  'Flask',     'flask',      30),
  ('backend-php',     'php-laravel',   'Laravel',   'laravel',    10),
  ('backend-php',     'php-symfony',   'Symfony',   'symfony',    20),
  ('backend-nodejs',  'node-nestjs',   'NestJS',    'nestjs',     10),
  ('backend-nodejs',  'node-express',  'Express',   'express',    20),
  ('backend-java',    'java-spring',   'Spring Boot','spring',    10),
  ('backend-dotnet',  'dotnet-aspnet', 'ASP.NET Core','aspnet',   10)
) AS v(parent_slug, slug, name, leaf, sort_order)
JOIN categories p ON p.slug = v.parent_slug;

-- ── Technologies ─────────────────────────────────────────────────────────────
-- github_aliases match what the GitHub languages endpoint reports;
-- manifest_hints are the files that prove the technology is actually used.
INSERT INTO skills (slug, name, kind, github_aliases, manifest_hints, colour) VALUES
  ('go',          'Go',          'language', '{Go}',            '{go.mod,go.sum}',        '#00ADD8'),
  ('python',      'Python',      'language', '{Python}',        '{requirements.txt,pyproject.toml,Pipfile,setup.py}', '#3776AB'),
  ('typescript',  'TypeScript',  'language', '{TypeScript}',    '{tsconfig.json}',        '#3178C6'),
  ('javascript',  'JavaScript',  'language', '{JavaScript}',    '{package.json}',         '#F7DF1E'),
  ('php',         'PHP',         'language', '{PHP,Hack}',      '{composer.json}',        '#777BB4'),
  ('java',        'Java',        'language', '{Java}',          '{pom.xml,build.gradle}', '#E76F00'),
  ('kotlin',      'Kotlin',      'language', '{Kotlin}',        '{build.gradle.kts}',     '#7F52FF'),
  ('swift',       'Swift',       'language', '{Swift}',         '{Package.swift}',        '#F05138'),
  ('rust',        'Rust',        'language', '{Rust}',          '{Cargo.toml}',           '#DEA584'),
  ('csharp',      'C#',          'language', '{"C#"}',          '{csproj,sln}',           '#178600'),
  ('ruby',        'Ruby',        'language', '{Ruby}',          '{Gemfile}',              '#CC342D'),
  ('dart',        'Dart',        'language', '{Dart}',          '{pubspec.yaml}',         '#00B4AB'),
  ('sql',         'SQL',         'language', '{PLpgSQL,TSQL,SQL}', '{}',                  '#336791'),
  ('bash',        'Bash',        'language', '{Shell,"Shell Script"}', '{}',              '#4EAA25'),

  ('gin',         'Gin',         'framework', '{}', '{go.mod}',                '#00ADD8'),
  ('fiber',       'Fiber',       'framework', '{}', '{go.mod}',                '#00ADD8'),
  ('echo',        'Echo',        'framework', '{}', '{go.mod}',                '#00ADD8'),
  ('fastapi',     'FastAPI',     'framework', '{}', '{requirements.txt,pyproject.toml}', '#009688'),
  ('django',      'Django',      'framework', '{}', '{requirements.txt,manage.py}',      '#092E20'),
  ('flask',       'Flask',       'framework', '{}', '{requirements.txt}',      '#000000'),
  ('celery',      'Celery',      'framework', '{}', '{requirements.txt}',      '#37814A'),
  ('laravel',     'Laravel',     'framework', '{}', '{composer.json,artisan}', '#FF2D20'),
  ('symfony',     'Symfony',     'framework', '{}', '{composer.json}',         '#000000'),
  ('react',       'React',       'framework', '{}', '{package.json}',          '#61DAFB'),
  ('nextjs',      'Next.js',     'framework', '{}', '{package.json,next.config.js}', '#000000'),
  ('vue',         'Vue',         'framework', '{}', '{package.json}',          '#42B883'),
  ('nuxt',        'Nuxt',        'framework', '{}', '{package.json,nuxt.config.ts}', '#00DC82'),
  ('svelte',      'Svelte',      'framework', '{Svelte}', '{package.json}',    '#FF3E00'),
  ('angular',     'Angular',     'framework', '{}', '{package.json,angular.json}', '#DD0031'),
  ('nestjs',      'NestJS',      'framework', '{}', '{package.json,nest-cli.json}', '#E0234E'),
  ('express',     'Express',     'framework', '{}', '{package.json}',          '#000000'),
  ('spring-boot', 'Spring Boot', 'framework', '{}', '{pom.xml,build.gradle}',  '#6DB33F'),
  ('aspnet-core', 'ASP.NET Core','framework', '{}', '{csproj}',                '#512BD4'),
  ('react-native','React Native','framework', '{}', '{package.json,app.json}', '#61DAFB'),
  ('flutter',     'Flutter',     'framework', '{}', '{pubspec.yaml}',          '#02569B'),
  ('tailwind',    'Tailwind CSS','framework', '{}', '{package.json,tailwind.config.js}', '#06B6D4'),

  ('postgresql',  'PostgreSQL',  'database', '{}', '{docker-compose.yml,requirements.txt,go.mod}', '#336791'),
  ('mysql',       'MySQL',       'database', '{}', '{docker-compose.yml}',     '#4479A1'),
  ('sqlite',      'SQLite',      'database', '{}', '{}',                       '#003B57'),
  ('mongodb',     'MongoDB',     'database', '{}', '{docker-compose.yml}',     '#47A248'),
  ('redis',       'Redis',       'database', '{}', '{docker-compose.yml}',     '#DC382D'),
  ('clickhouse',  'ClickHouse',  'database', '{}', '{docker-compose.yml}',     '#FFCC01'),
  ('elasticsearch','Elasticsearch','database','{}', '{docker-compose.yml}',    '#005571'),

  ('docker',      'Docker',      'tool',  '{Dockerfile}', '{Dockerfile,docker-compose.yml}', '#2496ED'),
  ('kubernetes',  'Kubernetes',  'tool',  '{}', '{k8s,helm,Chart.yaml}',       '#326CE5'),
  ('terraform',   'Terraform',   'tool',  '{HCL}', '{main.tf}',               '#7B42BC'),
  ('ansible',     'Ansible',     'tool',  '{}', '{playbook.yml}',              '#EE0000'),
  ('nginx',       'Nginx',       'tool',  '{}', '{nginx.conf}',                '#009639'),
  ('github-actions','GitHub Actions','tool','{}', '{.github/workflows}',       '#2088FF'),
  ('gitlab-ci',   'GitLab CI',   'tool',  '{}', '{.gitlab-ci.yml}',            '#FC6D26'),
  ('prometheus',  'Prometheus',  'tool',  '{}', '{prometheus.yml}',            '#E6522C'),
  ('grafana',     'Grafana',     'tool',  '{}', '{}',                          '#F46800'),
  ('figma',       'Figma',       'tool',  '{}', '{}',                          '#F24E1E'),

  ('aws',         'AWS',         'cloud', '{}', '{}',                          '#FF9900'),
  ('gcp',         'Google Cloud','cloud', '{}', '{}',                          '#4285F4'),
  ('azure',       'Azure',       'cloud', '{}', '{}',                          '#0078D4'),
  ('cloudflare',  'Cloudflare',  'cloud', '{}', '{wrangler.toml}',             '#F38020'),
  ('vercel',      'Vercel',      'cloud', '{}', '{vercel.json}',               '#000000'),
  ('hetzner',     'Hetzner',     'cloud', '{}', '{}',                          '#D50C2D'),
  ('s3',          'S3-compatible storage','cloud','{}', '{}',                  '#569A31'),

  ('telegram-api','Telegram Bot API','platform','{}', '{}',                    '#26A5E4'),
  ('telegram-mini-apps','Telegram Mini Apps','platform','{}', '{}',            '#26A5E4'),
  ('aiogram',     'aiogram',     'framework','{}', '{requirements.txt}',       '#26A5E4'),
  ('telebot',     'pyTelegramBotAPI','framework','{}','{requirements.txt}',    '#26A5E4'),
  ('telegraf',    'Telegraf',    'framework','{}', '{package.json}',           '#26A5E4'),
  ('stripe',      'Stripe',      'platform','{}', '{}',                        '#635BFF'),
  ('shopify',     'Shopify',     'platform','{}', '{}',                        '#7AB55C'),
  ('woocommerce', 'WooCommerce', 'platform','{}', '{}',                        '#96588A'),
  ('supabase',    'Supabase',    'platform','{}', '{}',                        '#3ECF8E'),
  ('firebase',    'Firebase',    'platform','{}', '{}',                        '#FFCA28'),

  ('rest',        'REST',        'protocol','{}', '{openapi.yaml,swagger.json}','#6B7280'),
  ('graphql',     'GraphQL',     'protocol','{GraphQL}', '{schema.graphql}',   '#E10098'),
  ('grpc',        'gRPC',        'protocol','{"Protocol Buffer"}', '{proto}',  '#4A90E2'),
  ('websocket',   'WebSocket',   'protocol','{}', '{}',                        '#6B7280'),
  ('webhooks',    'Webhooks',    'protocol','{}', '{}',                        '#6B7280'),
  ('oauth2',      'OAuth 2.0',   'protocol','{}', '{}',                        '#6B7280'),

  ('openai-api',  'OpenAI API',  'platform','{}', '{requirements.txt,package.json}', '#412991'),
  ('anthropic-api','Anthropic API','platform','{}','{requirements.txt,package.json}','#D4A27F'),
  ('langchain',   'LangChain',   'framework','{}', '{requirements.txt}',       '#1C3C3C'),
  ('pytorch',     'PyTorch',     'framework','{}', '{requirements.txt}',       '#EE4C2C'),
  ('pandas',      'pandas',      'framework','{}', '{requirements.txt}',       '#150458'),
  ('opencv',      'OpenCV',      'framework','{}', '{requirements.txt}',       '#5C3EE8'),

  ('testing',     'Automated testing','practice','{}', '{}',                   '#6B7280'),
  ('ci-cd',       'CI/CD',       'practice','{}', '{}',                        '#6B7280'),
  ('accessibility','Accessibility','practice','{}', '{}',                      '#6B7280'),
  ('performance', 'Performance optimisation','practice','{}', '{}',            '#6B7280'),
  ('security',    'Application security','practice','{}', '{}',                '#6B7280');

-- Framework -> language parentage, so the picker can group "Python: FastAPI, Django, Flask".
UPDATE skills f SET parent_id = l.id
FROM (VALUES
  ('gin','go'), ('fiber','go'), ('echo','go'),
  ('fastapi','python'), ('django','python'), ('flask','python'), ('celery','python'),
  ('aiogram','python'), ('telebot','python'), ('langchain','python'), ('pytorch','python'),
  ('pandas','python'), ('opencv','python'),
  ('laravel','php'), ('symfony','php'),
  ('react','javascript'), ('nextjs','typescript'), ('vue','javascript'), ('nuxt','typescript'),
  ('svelte','javascript'), ('angular','typescript'), ('nestjs','typescript'),
  ('express','javascript'), ('telegraf','typescript'), ('react-native','typescript'),
  ('spring-boot','java'), ('aspnet-core','csharp'), ('flutter','dart')
) AS m(child, parent)
JOIN skills l ON l.slug = m.parent
WHERE f.slug = m.child;

-- ── Specialisation -> technology relevance ───────────────────────────────────
INSERT INTO specialisation_skills (specialisation_id, skill_id, is_core)
SELECT sp.id, sk.id, v.core
FROM (VALUES
  ('backend-developer','go',true),('backend-developer','python',true),('backend-developer','php',true),
  ('backend-developer','java',true),('backend-developer','csharp',true),('backend-developer','rust',true),
  ('backend-developer','typescript',false),('backend-developer','postgresql',true),
  ('backend-developer','mysql',true),('backend-developer','redis',true),('backend-developer','mongodb',false),
  ('backend-developer','docker',true),('backend-developer','rest',true),('backend-developer','graphql',false),
  ('backend-developer','grpc',false),('backend-developer','gin',false),('backend-developer','fiber',false),
  ('backend-developer','fastapi',false),('backend-developer','django',false),('backend-developer','laravel',false),
  ('backend-developer','spring-boot',false),('backend-developer','nestjs',false),('backend-developer','sql',true),
  ('backend-developer','websocket',false),('backend-developer','oauth2',false),('backend-developer','testing',false),

  ('frontend-developer','typescript',true),('frontend-developer','javascript',true),
  ('frontend-developer','react',true),('frontend-developer','nextjs',true),('frontend-developer','vue',true),
  ('frontend-developer','svelte',false),('frontend-developer','angular',false),('frontend-developer','nuxt',false),
  ('frontend-developer','tailwind',true),('frontend-developer','accessibility',false),
  ('frontend-developer','performance',false),('frontend-developer','rest',false),
  ('frontend-developer','graphql',false),('frontend-developer','figma',false),('frontend-developer','testing',false),

  ('fullstack-developer','typescript',true),('fullstack-developer','nextjs',true),('fullstack-developer','react',true),
  ('fullstack-developer','go',false),('fullstack-developer','python',false),('fullstack-developer','php',false),
  ('fullstack-developer','postgresql',true),('fullstack-developer','redis',false),('fullstack-developer','docker',true),
  ('fullstack-developer','rest',true),('fullstack-developer','supabase',false),('fullstack-developer','firebase',false),
  ('fullstack-developer','stripe',false),('fullstack-developer','tailwind',false),('fullstack-developer','nestjs',false),

  ('telegram-developer','telegram-api',true),('telegram-developer','telegram-mini-apps',true),
  ('telegram-developer','python',true),('telegram-developer','aiogram',true),('telegram-developer','telebot',false),
  ('telegram-developer','typescript',false),('telegram-developer','telegraf',false),('telegram-developer','go',false),
  ('telegram-developer','postgresql',true),('telegram-developer','redis',false),('telegram-developer','webhooks',true),
  ('telegram-developer','react',false),('telegram-developer','stripe',false),('telegram-developer','docker',false),

  ('mobile-developer','swift',true),('mobile-developer','kotlin',true),('mobile-developer','dart',true),
  ('mobile-developer','flutter',true),('mobile-developer','react-native',true),('mobile-developer','typescript',false),
  ('mobile-developer','firebase',false),('mobile-developer','rest',true),('mobile-developer','graphql',false),

  ('ai-automation-developer','python',true),('ai-automation-developer','openai-api',true),
  ('ai-automation-developer','anthropic-api',true),('ai-automation-developer','langchain',false),
  ('ai-automation-developer','fastapi',true),('ai-automation-developer','pytorch',false),
  ('ai-automation-developer','pandas',false),('ai-automation-developer','opencv',false),
  ('ai-automation-developer','postgresql',false),('ai-automation-developer','redis',false),
  ('ai-automation-developer','celery',false),('ai-automation-developer','docker',true),
  ('ai-automation-developer','webhooks',false),('ai-automation-developer','rest',false),

  ('devops-engineer','docker',true),('devops-engineer','kubernetes',true),('devops-engineer','terraform',true),
  ('devops-engineer','ansible',false),('devops-engineer','nginx',true),('devops-engineer','github-actions',true),
  ('devops-engineer','gitlab-ci',false),('devops-engineer','prometheus',true),('devops-engineer','grafana',false),
  ('devops-engineer','aws',true),('devops-engineer','gcp',false),('devops-engineer','azure',false),
  ('devops-engineer','hetzner',false),('devops-engineer','cloudflare',false),('devops-engineer','bash',true),
  ('devops-engineer','postgresql',false),('devops-engineer','redis',false),('devops-engineer','ci-cd',true),
  ('devops-engineer','security',false),

  ('ui-ux-designer','figma',true),('ui-ux-designer','accessibility',true),('ui-ux-designer','tailwind',false),
  ('ui-ux-designer','react',false),('ui-ux-designer','performance',false)
) AS v(spec_slug, skill_slug, core)
JOIN specialisations sp ON sp.slug = v.spec_slug
JOIN skills sk ON sk.slug = v.skill_slug;

-- ── Category -> specialisation targeting ─────────────────────────────────────
-- This is the table that decides whose feed a project reaches. A Telegram bot
-- project scores 1.0 for a Telegram developer, 0.7 for a Python backend
-- developer, 0.5 for a full stack developer — and does not appear at all for an
-- iOS or UI/UX specialist, because there is no row for them.
INSERT INTO category_specialisations (category_id, specialisation_id, relevance)
SELECT c.id, sp.id, v.relevance
FROM (VALUES
  ('backend-development',  'backend-developer',      1.00),
  ('backend-development',  'fullstack-developer',    0.70),
  ('backend-development',  'devops-engineer',        0.30),
  ('frontend-development', 'frontend-developer',     1.00),
  ('frontend-development', 'fullstack-developer',    0.75),
  ('frontend-development', 'ui-ux-designer',         0.30),
  ('fullstack-development','fullstack-developer',    1.00),
  ('fullstack-development','backend-developer',      0.60),
  ('fullstack-development','frontend-developer',     0.55),
  ('telegram-bots',        'telegram-developer',     1.00),
  ('telegram-bots',        'backend-developer',      0.65),
  ('telegram-bots',        'fullstack-developer',    0.50),
  ('telegram-bots',        'ai-automation-developer',0.35),
  ('telegram-mini-apps',   'telegram-developer',     1.00),
  ('telegram-mini-apps',   'fullstack-developer',    0.70),
  ('telegram-mini-apps',   'frontend-developer',     0.60),
  ('mobile-applications',  'mobile-developer',       1.00),
  ('mobile-applications',  'fullstack-developer',    0.40),
  ('ai-automation',        'ai-automation-developer',1.00),
  ('ai-automation',        'backend-developer',      0.55),
  ('ai-automation',        'fullstack-developer',    0.35),
  ('api-development',      'backend-developer',      1.00),
  ('api-development',      'fullstack-developer',    0.65),
  ('api-development',      'devops-engineer',        0.25),
  ('web-applications',     'fullstack-developer',    1.00),
  ('web-applications',     'frontend-developer',     0.75),
  ('web-applications',     'backend-developer',      0.65),
  ('saas',                 'fullstack-developer',    1.00),
  ('saas',                 'backend-developer',      0.75),
  ('saas',                 'frontend-developer',     0.60),
  ('saas',                 'devops-engineer',        0.35),
  ('ecommerce',            'fullstack-developer',    1.00),
  ('ecommerce',            'backend-developer',      0.70),
  ('ecommerce',            'frontend-developer',     0.65),
  ('devops',               'devops-engineer',        1.00),
  ('devops',               'backend-developer',      0.40),
  ('infrastructure',       'devops-engineer',        1.00),
  ('infrastructure',       'backend-developer',      0.35),
  ('ui-ux-digital',        'ui-ux-designer',         1.00),
  ('ui-ux-digital',        'frontend-developer',     0.45),
  ('integrations',         'backend-developer',      1.00),
  ('integrations',         'fullstack-developer',    0.70),
  ('integrations',         'ai-automation-developer',0.40),
  ('integrations',         'telegram-developer',     0.30)
) AS v(cat_slug, spec_slug, relevance)
JOIN categories c ON c.slug = v.cat_slug
JOIN specialisations sp ON sp.slug = v.spec_slug;

-- Child categories inherit their parent's targeting, then override where the
-- language changes who is relevant (a Go backend project is not a PHP job).
INSERT INTO category_specialisations (category_id, specialisation_id, relevance)
SELECT child.id, cs.specialisation_id, cs.relevance
FROM categories child
JOIN categories parent ON parent.id = child.parent_id
JOIN category_specialisations cs ON cs.category_id = parent.id
ON CONFLICT DO NOTHING;

-- ── Category -> technology hints ─────────────────────────────────────────────
INSERT INTO category_skills (category_id, skill_id, weight)
SELECT c.id, sk.id, v.weight
FROM (VALUES
  ('backend-go','go',1.00),('backend-go','postgresql',0.60),('backend-go','docker',0.50),
  ('backend-python','python',1.00),('backend-python','postgresql',0.60),('backend-python','fastapi',0.55),
  ('backend-php','php',1.00),('backend-php','laravel',0.60),('backend-php','mysql',0.55),
  ('backend-nodejs','typescript',0.80),('backend-nodejs','javascript',0.70),('backend-nodejs','nestjs',0.45),
  ('backend-java','java',1.00),('backend-java','spring-boot',0.70),
  ('backend-dotnet','csharp',1.00),('backend-dotnet','aspnet-core',0.75),
  ('backend-rust','rust',1.00),
  ('frontend-react','react',1.00),('frontend-react','typescript',0.80),('frontend-react','tailwind',0.40),
  ('frontend-nextjs','nextjs',1.00),('frontend-nextjs','react',0.85),('frontend-nextjs','typescript',0.80),
  ('frontend-vue','vue',1.00),('frontend-svelte','svelte',1.00),('frontend-angular','angular',1.00),
  ('telegram-bots','telegram-api',1.00),('telegram-bots','python',0.65),('telegram-bots','aiogram',0.50),
  ('telegram-bots','postgresql',0.45),('telegram-bots','webhooks',0.40),
  ('telegram-mini-apps','telegram-mini-apps',1.00),('telegram-mini-apps','react',0.55),
  ('telegram-mini-apps','typescript',0.55),('telegram-mini-apps','go',0.25),
  ('mobile-ios','swift',1.00),('mobile-android','kotlin',1.00),
  ('mobile-flutter','flutter',1.00),('mobile-flutter','dart',0.90),
  ('mobile-react-native','react-native',1.00),('mobile-react-native','typescript',0.75),
  ('ai-llm-integration','openai-api',0.80),('ai-llm-integration','anthropic-api',0.80),
  ('ai-llm-integration','python',0.85),('ai-llm-integration','fastapi',0.45),
  ('ai-agents','langchain',0.60),('ai-agents','python',0.85),
  ('ai-data-pipelines','python',0.90),('ai-data-pipelines','pandas',0.55),('ai-data-pipelines','celery',0.40),
  ('ai-computer-vision','opencv',0.80),('ai-computer-vision','pytorch',0.60),('ai-computer-vision','python',0.90),
  ('api-development','rest',0.90),('api-development','graphql',0.40),('api-development','grpc',0.30),
  ('api-development','oauth2',0.40),
  ('saas','stripe',0.55),('saas','postgresql',0.65),('saas','nextjs',0.45),
  ('ecommerce','stripe',0.60),('ecommerce','shopify',0.35),('ecommerce','woocommerce',0.30),
  ('devops-ci-cd','github-actions',0.70),('devops-ci-cd','gitlab-ci',0.45),('devops-ci-cd','ci-cd',0.90),
  ('devops-containers','docker',1.00),('devops-containers','kubernetes',0.80),
  ('devops-observability','prometheus',0.75),('devops-observability','grafana',0.60),
  ('infra-cloud','aws',0.65),('infra-cloud','terraform',0.60),('infra-cloud','hetzner',0.30),
  ('infra-databases','postgresql',0.85),('infra-databases','redis',0.55),('infra-databases','mysql',0.50),
  ('infra-networking','nginx',0.70),('infra-networking','cloudflare',0.45),('infra-networking','security',0.60),
  ('ui-ux-digital','figma',0.90),('ui-ux-digital','accessibility',0.55),
  ('integrations','rest',0.80),('integrations','webhooks',0.70),('integrations','oauth2',0.50),
  ('go-gin','gin',1.00),('go-fiber','fiber',1.00),('go-echo','echo',1.00),
  ('python-fastapi','fastapi',1.00),('python-django','django',1.00),('python-flask','flask',1.00),
  ('php-laravel','laravel',1.00),('php-symfony','symfony',1.00),
  ('node-nestjs','nestjs',1.00),('node-express','express',1.00),
  ('java-spring','spring-boot',1.00),('dotnet-aspnet','aspnet-core',1.00)
) AS v(cat_slug, skill_slug, weight)
JOIN categories c ON c.slug = v.cat_slug
JOIN skills sk ON sk.slug = v.skill_slug
ON CONFLICT DO NOTHING;
