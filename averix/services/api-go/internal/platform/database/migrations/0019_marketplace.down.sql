-- 0019 marketplace: revert to the developer-only taxonomy.
--
-- Everything that arrived is removed; everything that moved moves back; the
-- names return to English. Rows a user attached to the new professions or
-- categories block this rollback through their foreign keys, which is the
-- correct outcome: a rollback must not silently delete someone's profile.

-- Links first, then the rows they point at.
DELETE FROM category_skills cs USING categories c
WHERE cs.category_id = c.id AND (c.depth = 0 OR c.path !~ '^it/');
DELETE FROM category_specialisations cs USING categories c
WHERE cs.category_id = c.id AND (c.depth = 0 OR c.path !~ '^it/');
DELETE FROM category_specialisations cs USING specialisations sp
WHERE cs.specialisation_id = sp.id AND sp.sort_order >= 100;
DELETE FROM specialisation_skills ss USING specialisations sp
WHERE ss.specialisation_id = sp.id AND sp.sort_order >= 100;

DELETE FROM categories WHERE depth = 1 AND path !~ '^it/';
DELETE FROM specialisations WHERE sort_order >= 100;
DELETE FROM skills WHERE slug IN (
  'photoshop','adobe-illustrator','indesign','after-effects','premiere-pro','davinci-resolve','capcut',
  'blender','cinema-4d','lightroom','canva','sketch','procreate','audacity','ableton','fl-studio',
  'midjourney','stable-diffusion','chatgpt','tilda','wordpress','wix','bitrix24','amocrm','1c',
  'yandex-direct','google-ads','yandex-metrika','google-analytics','vk-ads','telegram-ads','meta-ads',
  'youtube','tiktok','vk','unisender','mailchimp','notion','google-sheets','excel','wildberries','ozon',
  'copywriting','editing','storytelling','english','german','chinese','turkish','uzbek','seo','ppc',
  'targeting','smm','content-planning','email-marketing','branding','typography','ux-research',
  'prototyping','illustration','3d-modelling','motion-graphics','video-editing','color-grading',
  'voice-over','sound-design','mixing-mastering','photo-retouching','photography','accounting','taxes',
  'contract-law','financial-modelling','market-research','data-entry','web-scraping','recruiting',
  'project-management','presentations','teaching','mentoring','transcription','subtitling');

-- Move the IT tree back to the top.
UPDATE categories SET parent_id = NULL WHERE depth = 1 AND path ~ '^it/';
DELETE FROM categories WHERE depth = 0;
UPDATE categories SET path = substr(path, 4), depth = depth - 1 WHERE path ~ '^it/';

UPDATE specialisations sp SET name = v.name, short_name = v.short_name, description = v.description
FROM (VALUES
  ('backend-developer',   'Backend Developer',        'Backend',   'Server-side systems, APIs, data modelling and reliability.'),
  ('frontend-developer',  'Frontend Developer',       'Frontend',  'Interfaces, state, performance and accessibility in the browser.'),
  ('fullstack-developer', 'Full Stack Developer',     'Full Stack','End-to-end product delivery across client and server.'),
  ('telegram-developer',  'Telegram Developer',       'Telegram',  'Bots, Mini Apps and payments on the Telegram platform.'),
  ('mobile-developer',    'Mobile Developer',         'Mobile',    'iOS, Android and cross-platform applications.'),
  ('ai-automation-developer','AI / Automation Developer','AI',     'Model integration, pipelines, agents and process automation.'),
  ('devops-engineer',     'DevOps Engineer',          'DevOps',    'Delivery pipelines, containers, observability and infrastructure.'),
  ('ui-ux-designer',      'UI/UX Designer',           'UI/UX',     'Product interface and interaction design for digital products.')
) AS v(slug, name, short_name, description)
WHERE sp.slug = v.slug;

UPDATE categories c SET name = v.name
FROM (VALUES
  ('backend-development','Backend Development'),('frontend-development','Frontend Development'),
  ('fullstack-development','Full Stack Development'),('telegram-bots','Telegram Bots'),
  ('telegram-mini-apps','Telegram Mini Apps'),('mobile-applications','Mobile Applications'),
  ('ai-automation','AI / Automation'),('api-development','API Development'),
  ('web-applications','Web Applications'),('saas','SaaS'),('ecommerce','E-commerce'),('devops','DevOps'),
  ('infrastructure','Infrastructure'),('ui-ux-digital','UI/UX for Digital Products'),('integrations','Integrations'),
  ('ai-llm-integration','LLM Integration'),('ai-agents','Agents & Tooling'),('ai-data-pipelines','Data Pipelines'),
  ('ai-computer-vision','Computer Vision'),('ai-workflow-automation','Workflow Automation'),
  ('telegram-commerce-bot','Commerce Bot'),('telegram-service-bot','Service Bot'),
  ('telegram-admin-bot','Admin & Moderation'),('devops-containers','Containers & Orchestration'),
  ('devops-observability','Observability'),('infra-cloud','Cloud Architecture'),('infra-databases','Databases'),
  ('infra-networking','Networking & Security'),('go-stdlib','Standard library')
) AS v(slug, name)
WHERE c.slug = v.slug;

UPDATE skills s SET name = v.name
FROM (VALUES
  ('testing','Automated testing'),('accessibility','Accessibility'),
  ('performance','Performance optimisation'),('security','Application security'),
  ('s3','S3-compatible storage')
) AS v(slug, name)
WHERE s.slug = v.slug;

CREATE OR REPLACE FUNCTION projects_refresh_search_doc() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.search_doc :=
      setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A')
   || setweight(to_tsvector('simple', coalesce(NEW.summary, '')), 'B')
   || setweight(to_tsvector('english', coalesce(NEW.description, '')), 'C');
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION services_refresh_search_doc() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.search_doc :=
      setweight(to_tsvector('simple',  coalesce(NEW.title, '')), 'A')
   || setweight(to_tsvector('simple',  coalesce(NEW.summary, '')), 'B')
   || setweight(to_tsvector('english', coalesce(NEW.description, '')), 'C');
  RETURN NEW;
END;
$$;

ALTER TABLE users ALTER COLUMN locale SET DEFAULT 'en';
