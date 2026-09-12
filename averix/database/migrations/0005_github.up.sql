-- 0005 GitHub: explicitly connected accounts, mirrored repositories, analysis runs.
--
-- A GitHub account is only ever linked through the OAuth callback, so the stored
-- github_user_id is proof of ownership. Nothing here is inferred from a name.

CREATE TABLE github_accounts (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  github_user_id     bigint NOT NULL,
  login              text NOT NULL,
  name               text,
  avatar_url         text,
  profile_url        text,
  company            text,
  blog               text,
  public_repos       int NOT NULL DEFAULT 0,
  followers          int NOT NULL DEFAULT 0,
  account_created_at timestamptz,
  -- Encrypted with the application data key; never returned by any endpoint.
  access_token_enc   bytea,
  token_expires_at   timestamptz,
  refresh_token_enc  bytea,
  -- Granted scopes. Public analysis needs none beyond the default; private
  -- repository access requires 'repo' and an explicit second consent.
  scopes             text[] NOT NULL DEFAULT '{}',
  private_access_granted_at timestamptz,
  verified_at        timestamptz NOT NULL DEFAULT now(),
  last_synced_at     timestamptz,
  sync_error         text,
  revoked_at         timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
-- One live link per user, and a GitHub identity cannot be claimed twice.
CREATE UNIQUE INDEX github_accounts_user_key   ON github_accounts (user_id) WHERE revoked_at IS NULL;
CREATE UNIQUE INDEX github_accounts_remote_key ON github_accounts (github_user_id) WHERE revoked_at IS NULL;
SELECT attach_touch_trigger('github_accounts');

CREATE TABLE github_repositories (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  github_account_id uuid NOT NULL REFERENCES github_accounts(id) ON DELETE CASCADE,
  repo_id           bigint NOT NULL,
  name              text NOT NULL,
  full_name         text NOT NULL,
  description       text,
  html_url          text NOT NULL,
  homepage          text,
  is_private        boolean NOT NULL DEFAULT false,
  is_fork           boolean NOT NULL DEFAULT false,
  is_archived       boolean NOT NULL DEFAULT false,
  primary_language  text,
  stars             int NOT NULL DEFAULT 0,
  forks             int NOT NULL DEFAULT 0,
  open_issues       int NOT NULL DEFAULT 0,
  size_kb           int NOT NULL DEFAULT 0,
  topics            text[] NOT NULL DEFAULT '{}',
  license           text,
  default_branch    text,
  pushed_at         timestamptz,
  repo_created_at   timestamptz,
  -- Set by the analysis service: this repository is a credible portfolio piece.
  portfolio_candidate boolean NOT NULL DEFAULT false,
  candidate_reason  text,
  readme_excerpt    text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX github_repositories_key ON github_repositories (github_account_id, repo_id);
CREATE INDEX github_repositories_pushed_idx ON github_repositories (github_account_id, pushed_at DESC);
CREATE INDEX github_repositories_candidate_idx ON github_repositories (github_account_id)
  WHERE portfolio_candidate;
SELECT attach_touch_trigger('github_repositories');

-- Byte counts straight from the GitHub languages endpoint. Reported as code
-- share only — this is never presented as a skill rating.
CREATE TABLE github_repository_languages (
  repository_id uuid NOT NULL REFERENCES github_repositories(id) ON DELETE CASCADE,
  language      text NOT NULL,
  bytes         bigint NOT NULL CHECK (bytes >= 0),
  PRIMARY KEY (repository_id, language)
);

-- Technologies detected from manifests, not from language bytes: a go.mod entry
-- is evidence, a .go file share is only a hint.
CREATE TABLE github_detected_technologies (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  repository_id uuid NOT NULL REFERENCES github_repositories(id) ON DELETE CASCADE,
  skill_id      uuid REFERENCES skills(id) ON DELETE SET NULL,
  raw_name      text NOT NULL,
  source        text NOT NULL CHECK (source IN
                  ('go.mod','requirements.txt','pyproject.toml','package.json','composer.json',
                   'Dockerfile','docker-compose.yml','Cargo.toml','pom.xml','build.gradle',
                   'Gemfile','csproj','language-stats','topics','readme')),
  confidence    numeric(3,2) NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
  version_spec  text,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX github_detected_tech_key ON github_detected_technologies (repository_id, raw_name, source);
CREATE INDEX github_detected_tech_skill_idx ON github_detected_technologies (skill_id);

-- One row per analysis run. Keeping history means a regression in the analyser
-- is visible, and the admin panel can show API errors per job.
CREATE TABLE github_analysis (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  github_account_id uuid NOT NULL REFERENCES github_accounts(id) ON DELETE CASCADE,
  status            text NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued','running','succeeded','failed','partial')),
  trigger           text NOT NULL DEFAULT 'connect'
                      CHECK (trigger IN ('connect','manual','scheduled','admin')),
  repos_seen        int NOT NULL DEFAULT 0,
  repos_analysed    int NOT NULL DEFAULT 0,
  -- [{"language":"Go","bytes":...,"share":0.39}] — share of code, nothing more.
  language_stats    jsonb NOT NULL DEFAULT '[]'::jsonb,
  technology_summary jsonb NOT NULL DEFAULT '[]'::jsonb,
  -- Prose summary produced by the AI service. Always surfaced with a label.
  ai_summary        text,
  ai_model          text,
  ai_generated_at   timestamptz,
  focus_areas       text[] NOT NULL DEFAULT '{}',
  error_code        text,
  error_detail      text,
  api_calls_used    int NOT NULL DEFAULT 0,
  rate_limit_remaining int,
  started_at        timestamptz,
  finished_at       timestamptz,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX github_analysis_account_idx ON github_analysis (github_account_id, created_at DESC);
CREATE INDEX github_analysis_status_idx  ON github_analysis (status) WHERE status IN ('queued','running');
SELECT attach_touch_trigger('github_analysis');
