// The API's shapes, mirrored.
//
// Hand-written rather than generated: the surface the web app uses is a subset
// of what the API returns, and writing it out makes the coupling visible.

export type SkillRef = { slug: string; name: string; colour?: string };
export type CategoryRef = { slug: string; name: string; path?: string };

export type Budget = {
  type: string;
  min_minor?: number;
  max_minor?: number;
  currency: string;
  display: string;
};

export type MatchReason = { label: string; met: boolean; detail?: string };

export type MatchDimension = {
  key: string;
  label: string;
  weight: number;
  raw: number;
  points: number;
  reasons: MatchReason[];
};

export type MatchScore = {
  total: number;
  weights_version: number;
  dimensions: MatchDimension[];
  highlights: MatchReason[];
  excluded?: boolean;
  exclusion_reason?: string;
};

export type FeedCard = {
  id: string;
  slug: string;
  reference: string;
  title: string;
  excerpt?: string;
  category: CategoryRef;
  skills: SkillRef[];
  budget: Budget;
  proposals_count: number;
  published_at?: string;
  match_score?: number;
  match_highlights?: MatchReason[];
  client_country?: string;
  client_hires: number;
  client_verified: boolean;
  has_proposed?: boolean;
  is_saved?: boolean;
  is_invited?: boolean;
};

export type ClientRef = {
  user_id?: string;
  username?: string;
  /** What the client chose to be known as: a company name, or their own. */
  display_name?: string;
  country_code?: string;
  photo_url?: string;
  hires_made?: number;
  rating_avg?: number;
  rating_count?: number;
  verified?: boolean;
  member_since?: string;
};

export type Project = {
  id: string;
  reference: string;
  slug: string;
  title: string;
  summary?: string;
  description: string;
  category: CategoryRef;
  skills: SkillRef[];
  features?: { title: string; detail?: string }[];
  targeting?: { slug: string; name: string; relevance?: number }[];
  status: string;
  budget: Budget;
  duration_days?: number;
  deadline?: string;
  experience_wanted?: string;
  client: ClientRef;
  proposals_count: number;
  views_count: number;
  shortlisted_count: number;
  published_at?: string;
  match?: MatchScore;
  has_proposed?: boolean;
  is_saved?: boolean;
  is_owner?: boolean;
};

export type ProposalCard = {
  id: string;
  project_id: string;
  amount_minor: number;
  amount_display: string;
  currency: string;
  delivery_days: number;
  /** The first lines of the cover letter, for triage without opening each one. */
  preview?: string;
  match_score?: number;
  match_highlights?: MatchReason[];
  developer: {
    user_id: string;
    username: string;
    full_name: string;
    professional_title?: string;
    photo_url?: string;
    rating_avg?: number;
    rating_count?: number;
    projects_completed?: number;
    success_rate?: number;
    skills?: string[];
    availability?: string;
    country_code?: string;
    identity_verified?: boolean;
    github_connected?: boolean;
  };
  /** The single most relevant piece of past work. */
  top_evidence?: {
    kind: 'averix_verified' | 'portfolio';
    id: string;
    title: string;
    note?: string;
    technologies?: string[];
    completed_at?: string;
    client_rating?: number;
    value_display?: string;
    cover_url?: string;
    slug?: string;
  };
  status: string;
  milestone_count?: number;
  shortlisted_at?: string;
  created_at: string;
};

export type ContractCard = {
  id: string;
  reference: string;
  title: string;
  status: string;
  counterparty: { id: string; username: string; full_name: string; title?: string; photo_url?: string };
  progress_percent: number;
  amount_minor?: number;
  currency?: string;
  next_milestone?: Milestone;
  due_on?: string;
  needs_my_action: boolean;
  unread_count: number;
  updated_at: string;
  my_role: string;
};

export type Milestone = {
  id: string;
  contract_id: string;
  position: number;
  title: string;
  detail?: string;
  amount_minor?: number;
  currency?: string;
  status: string;
  due_on?: string;
  revision_count: number;
  revision_limit: number;
  submitted_at?: string;
  submission_note?: string;
  approved_at?: string;
  released_at?: string;
  revision_note?: string;
  deliverables?: Deliverable[];
  events?: MilestoneEvent[];
};

export type MilestoneEvent = {
  id: string;
  from_status?: string;
  to_status: string;
  actor?: { id: string; username: string; full_name: string };
  note?: string;
  created_at: string;
};

export type Deliverable = {
  id: string;
  milestone_id?: string;
  kind: string;
  title: string;
  detail?: string;
  file_id?: string;
  file_url?: string;
  file_name?: string;
  file_byte_size?: number;
  url?: string;
  host?: string;
  submitted_by?: { id: string; username: string; full_name: string };
  accepted_at?: string;
  created_at: string;
};

export type Contract = {
  id: string;
  reference: string;
  title: string;
  project: { id: string; slug: string; title: string; category?: string };
  client: PartyRef;
  developer: PartyRef;
  status: string;
  progress_percent: number;
  amount_minor?: number;
  fee_minor?: number;
  payout_minor?: number;
  released_minor?: number;
  funded_minor?: number;
  currency?: string;
  fee_percent?: string;
  due_on?: string;
  price_visibility: string;
  milestones: Milestone[];
  deliverables?: Deliverable[];
  participants?: PartyRef[];
  completed_at?: string;
  cancellation_reason?: string;
  my_role: string;
  can: Record<string, boolean>;
};

export type PartyRef = {
  id: string;
  username: string;
  full_name: string;
  title?: string;
  photo_url?: string;
  role?: string;
  can_message?: boolean;
  can_upload?: boolean;
};

export type PhotoSet = {
  placeholder?: string;
  crop_shape?: string;
  sources?: Record<string, Record<string, string>>;
  width?: number;
};

export type Reputation = {
  rating_avg?: number;
  rating_count: number;
  rating_quality?: number;
  rating_communication?: number;
  rating_technical?: number;
  rating_deadline?: number;
  projects_completed: number;
  success_rate?: number;
  on_time_rate?: number;
  repeat_clients: number;
  response_time_seconds?: number;
};

export type ProfileBadge = { kind: string; label: string };

export type GitHubSummary = {
  login: string;
  profile_url: string;
  public_repos: number;
  language_share?: { name: string; share: number; bytes?: number }[];
  ai_summary?: string;
  focus_areas?: string[];
  analysis_state?: string;
  last_analysed_at?: string;
};

export type PublicProfile = {
  user_id: string;
  username: string;
  full_name: string;
  primary_specialisation?: { slug: string; name: string; short_name?: string };
  additional_specialisations?: { slug: string; name: string; short_name?: string }[];
  professional_title?: string;
  bio?: string;
  skills: {
    slug: string;
    name: string;
    kind?: string;
    level?: string;
    years?: number;
    evidence?: string[];
    is_primary?: boolean;
  }[];
  experience_level?: string;
  years_experience?: number;
  hourly_rate_minor?: number;
  rate_currency?: string;
  availability: string;
  hours_per_week?: number;
  location?: string;
  languages?: { language: string; proficiency: string }[];
  photo?: PhotoSet;
  reputation: Reputation;
  badges: ProfileBadge[];
  github?: GitHubSummary;
  member_since: string;
  is_owner?: boolean;
  is_saved?: boolean;
};

export type DeveloperProfile = {
  user_id: string;
  username: string;
  full_name: string;
  professional_title?: string;
  bio?: string;
  photo?: { url?: string; sources?: Record<string, Record<string, string>> };
  photo_url?: string;
  country_code?: string;
  city?: string;
  location?: string;
  specialisation?: { slug: string; name: string };
  additional_specialisations?: { slug: string; name: string }[];
  skills?: { slug: string; name: string; level?: string; years?: number; evidence?: string[] }[];
  experience_level?: string;
  years_experience?: number;
  hourly_rate_minor?: number;
  currency?: string;
  availability?: string;
  hours_per_week?: number;
  rating?: number;
  reviews_count?: number;
  completed_projects?: number;
  success_rate?: number;
  response_time?: string;
  identity_verified?: boolean;
  github_verified?: boolean;
  github?: { login?: string; languages?: { name: string; share: number }[]; repositories?: number };
  languages?: { language: string; proficiency: string }[];
  is_owner?: boolean;
  member_since?: string;
};

export type PortfolioCard = {
  id: string;
  slug: string;
  title: string;
  excerpt?: string;
  skills: SkillRef[];
  cover?: { url: string; placeholder?: string; variants?: { format: string; width: number; url: string }[] };
  project_host?: string;
  can_preview: boolean;
  demo_status: string;
  completed_on?: string;
  value_display?: string;
  kind: string;
  is_featured: boolean;
};

export type PortfolioProject = PortfolioCard & {
  description?: string;
  developer_role?: string;
  images: {
    id: string;
    url: string;
    caption?: string;
    alt_text?: string;
    placeholder?: string;
    variants?: { format: string; width: number; url: string }[];
  }[];
  links: { id: string; label: string; url: string; host: string; kind: string }[];
  project_url?: string;
  repository_url?: string;
  embeddable: string;
  category?: CategoryRef;
  is_owner?: boolean;
};

export type PreviewResponse = {
  project: { id: string; slug: string; title: string; developer: PartyRef };
  frame: {
    url: string;
    host: string;
    verdict: 'allowed' | 'blocked' | 'unreachable' | 'unknown';
    title?: string;
    reason?: string;
    sandbox?: string;
    referrer_policy?: string;
    permissions_policy?: string;
    csp?: string;
    devices?: { key: string; label: string; width: number; height?: number }[];
  };
  fallback?: { url: string; placeholder?: string };
};

export type ConversationCard = {
  id: string;
  counterparty: { id: string; username: string; full_name: string; photo_url?: string };
  subject?: string;
  contract_id?: string;
  project_id?: string;
  project_title?: string;
  preview?: string;
  unread_count: number;
  last_message_at?: string;
};

export type Message = {
  id: string;
  conversation_id: string;
  sender?: { id: string; username: string; full_name: string; photo_url?: string };
  kind: string;
  body?: string;
  code_language?: string;
  reply_to_id?: string;
  system_event?: string;
  system_payload?: Record<string, unknown>;
  attachments?: {
    id: string;
    file_id: string;
    name: string;
    byte_size: number;
    mime: string;
    url?: string;
    is_image: boolean;
  }[];
  is_mine: boolean;
  is_deleted?: boolean;
  created_at: string;
};

export type Payment = {
  id: string;
  reference: string;
  contract_id?: string;
  milestone_id?: string;
  direction: string;
  amount_minor: number;
  fee_minor: number;
  currency: string;
  status: string;
  status_label: string;
  provider: string;
  instructions?: { label: string; value: string; critical?: boolean }[];
  redirect_url?: string;
  refunded_minor?: number;
  failure_reason?: string;
  created_at: string;
};

export type Balance = {
  currency: string;
  available_minor: number;
  pending_minor: number;
  lifetime_minor: number;
  fees_minor: number;
  entries?: {
    id: string;
    kind: string;
    amount_minor: number;
    currency: string;
    balance_after_minor: number;
    description?: string;
    created_at: string;
  }[];
};

export type PendingPayment = {
  id: string;
  reference: string;
  direction: string;
  amount_minor: number;
  fee_minor: number;
  currency: string;
  status: string;
  status_label: string;
  contract_reference?: string;
  contract_title?: string;
  milestone_title?: string;
  payer_username: string;
  payer_name: string;
  payee_username?: string;
  payee_name?: string;
  created_at: string;
};

// ── Уведомления ─────────────────────────────────────────────────────────────

export type Notification = {
  id: string;
  type: string;
  title: string;
  body?: string;
  href?: string;
  priority: string;
  read_at?: string;
  created_at: string;
  actor?: { user_id: string; username: string; full_name: string; photo_url?: string };
};

export type NotificationPage = { items: Notification[]; next_before?: string; unread: number };

export type NotificationPreference = {
  type: string;
  label: string;
  in_app_locked: boolean;
  in_app: boolean;
  email: boolean;
  push: boolean;
};

export type NotificationPreferenceGroup = {
  key: string;
  label: string;
  preferences: NotificationPreference[];
};

// ── Отзывы и история ────────────────────────────────────────────────────────

export type ReviewCategory = { key: string; label: string; hint?: string };

export type Review = {
  id: string;
  contract_id: string;
  direction: string;
  author: { user_id: string; username: string; full_name: string; photo_url?: string };
  subject: { user_id: string; username: string; full_name: string; photo_url?: string };
  overall: number;
  scores: Record<string, number>;
  comment?: string;
  would_work_again?: boolean;
  response?: string;
  response_at?: string;
  published_at?: string;
  created_at: string;
  contract_title?: string;
  is_mine?: boolean;
  is_about_me?: boolean;
  can_respond?: boolean;
};

export type ReviewSide = {
  direction: string;
  submitted: boolean;
  published: boolean;
  review?: Review;
  categories: ReviewCategory[];
};

export type ContractReviews = {
  contract_id: string;
  can_review: boolean;
  reason?: string;
  my_direction?: string;
  window_closes_at?: string;
  of_developer: ReviewSide;
  of_client: ReviewSide;
};

export type HistoryEntry = {
  id: string;
  contract_id: string;
  title: string;
  summary?: string;
  category?: string;
  client_rating?: number;
  review_id?: string;
  value_display?: string;
  duration_days?: number;
  completed_at: string;
  is_visible: boolean;
};

// ── Услуги ──────────────────────────────────────────────────────────────────

export type ServiceTier = {
  id?: string;
  position?: number;
  name: string;
  price_minor: number;
  price_display?: string;
  delivery_days: number;
  revisions: number;
  includes: string[];
};

export type ServiceSeller = {
  user_id: string;
  username: string;
  full_name: string;
  photo_url?: string;
  professional_title?: string;
  rating_avg?: number;
  rating_count: number;
  projects_completed: number;
  availability: string;
};

export type ServiceCard = {
  id: string;
  slug: string;
  title: string;
  summary?: string;
  category: CategoryRef;
  cover_url?: string;
  from_minor: number;
  from_display: string;
  currency: string;
  delivery_days: number;
  orders_count: number;
  rating_avg?: number;
  rating_count: number;
  status: string;
  seller: ServiceSeller;
  created_at: string;
};

export type Service = ServiceCard & {
  description: string;
  revisions: number;
  skills: SkillRef[];
  tiers: ServiceTier[];
  portfolio_ids: string[];
  view_count: number;
  moderation_state?: string;
  updated_at: string;
  is_owner?: boolean;
  can_order: boolean;
};

// ── Поиск и каталог ─────────────────────────────────────────────────────────

export type FreelancerCard = {
  user_id: string;
  username: string;
  full_name: string;
  photo_url?: string;
  professional_title?: string;
  specialisation?: { slug: string; name: string; short_name: string };
  sector_slug?: string;
  skills: (SkillRef & { verified?: boolean })[];
  rating_avg?: number;
  rating_count: number;
  projects_completed: number;
  hourly_rate_minor?: number;
  rate_currency?: string;
  rate_display?: string;
  availability: string;
  location?: string;
  identity_verified: boolean;
  github_verified: boolean;
  is_featured?: boolean;
  last_seen_at?: string;
  is_saved?: boolean;
  note?: string;
  saved_at?: string;
};

export type ProjectHit = {
  id: string;
  slug: string;
  title: string;
  excerpt?: string;
  category_name: string;
  category_slug: string;
  budget_display: string;
  proposals_count: number;
  published_at?: string;
};

export type SearchResults = {
  query: string;
  freelancers: FreelancerCard[];
  services: ServiceCard[] | null;
  projects: ProjectHit[];
  totals: Record<string, number>;
};

// ── Справочники ─────────────────────────────────────────────────────────────

export type Specialisation = {
  id: string;
  slug: string;
  name: string;
  short_name: string;
  description?: string;
  sort_order: number;
};

export type Category = {
  id: string;
  parent_id?: string;
  slug: string;
  name: string;
  description?: string;
  path: string;
  depth: number;
  sort_order: number;
  children?: Category[];
};

export type Skill = {
  id: string;
  slug: string;
  name: string;
  kind: string;
  colour?: string;
  is_core?: boolean;
};

// ── Аккаунт ─────────────────────────────────────────────────────────────────

export type AccountSettings = {
  user_id: string;
  email: string;
  email_verified: boolean;
  pending_email?: string;
  username: string;
  full_name: string;
  headline?: string;
  timezone: string;
  locale: string;
  country_code?: string;
  city?: string;
  roles: string[];
  identity_verified: boolean;
  status: string;
  active_sessions: number;
  member_since: string;
  has_password: boolean;
  github_connected: boolean;
  last_seen_at?: string;
};

export type AuthSession = {
  id: string;
  current: boolean;
  role: string;
  user_agent?: string;
  ip?: string;
  last_used_at: string;
  created_at: string;
  expires_at: string;
};

export type ClientProfile = {
  user_id: string;
  username: string;
  full_name: string;
  email?: string;
  company_name?: string;
  company_website?: string;
  company_size?: string;
  industry?: string;
  about?: string;
  country_code?: string;
  city?: string;
  timezone?: string;
  projects_posted: number;
  hires_made: number;
  rating_avg?: number;
  rating_count: number;
  payment_verified: boolean;
  identity_verified: boolean;
  /** Видно только владельцу: сколько заказчик потратил — не дело исполнителей. */
  spent?: { currency: string; minor: number; display: string }[];
  member_since: string;
  last_seen_at?: string;
};

// ── Анкета исполнителя (свой профиль) ───────────────────────────────────────

export type Onboarding = {
  step: number;
  total_steps: number;
  completed: boolean;
  completed_at?: string;
  completeness: number;
  missing?: { key: string; label: string; weight?: number }[];
};

export type OwnProfile = {
  user_id: string;
  username: string;
  full_name: string;
  email?: string;
  primary_specialisation?: { slug: string; name: string; short_name: string };
  additional_specialisations: { slug: string; name: string; short_name: string }[];
  professional_title?: string;
  bio?: string;
  skills: { slug: string; name: string; kind?: string; level?: string; years?: number; is_primary?: boolean }[];
  experience_level?: string;
  years_experience?: number;
  hourly_rate_minor?: number;
  min_project_minor?: number;
  rate_currency: string;
  availability: string;
  hours_per_week?: number;
  available_from?: string;
  overlap_from_utc?: number;
  overlap_to_utc?: number;
  country_code?: string;
  city?: string;
  timezone?: string;
  languages: { language: string; proficiency: string }[];
  show_location: boolean;
  show_hourly_rate: boolean;
  open_to_invitations: boolean;
  photo?: PhotoSet;
  reputation: Reputation;
  onboarding: Onboarding;
  github?: GitHubSummary;
  identity_verified: boolean;
  email_verified: boolean;
  is_searchable: boolean;
  member_since: string;
};

export type StepResult = { step: number; next_step: number; onboarding: Onboarding; profile?: OwnProfile };

export type GitHubStatus = {
  configured: boolean;
  connected: boolean;
  account?: { id: string; login: string; name?: string; avatar_url?: string; profile_url: string; company?: string };
  analysis?: {
    id: string;
    status: string;
    trigger: string;
    repos_seen: number;
    repos_analysed: number;
    language_stats: { name: string; share: number; bytes?: number }[];
    technology_summary: { name: string; repos?: number; share?: number }[];
    ai_summary?: string;
    focus_areas?: string[];
    error_code?: string;
    ai_generated_at?: string;
  };
  can_grant_private: boolean;
  private_granted: boolean;
  analysis_degraded?: string;
};

// ── Админка и модерация ─────────────────────────────────────────────────────

export type AdminOverview = {
  users: { total: number; clients: number; freelancers: number; listed_freelancers: number; new_this_week: number; suspended: number };
  marketplace: {
    open_projects: number;
    active_services: number;
    active_contracts: number;
    completed_this_month: number;
    proposals_this_week: number;
    open_disputes: number;
    published_reviews: number;
  };
  money: { currency: string; gross_minor: number; fee_minor: number; contracts: number }[];
  attention: { moderation_pending: number; moderation_escalated: number; open_reports: number; pending_payments: number };
  integrations: Record<string, boolean>;
  version: string;
};

export type AdminUser = {
  id: string;
  username: string;
  full_name: string;
  email: string;
  status: string;
  roles: string[];
  email_verified: boolean;
  identity_verified: boolean;
  suspended_reason?: string;
  suspended_until?: string;
  created_at: string;
  last_seen_at?: string;
  country_code?: string;
  city?: string;
  projects_posted?: number;
  contracts_total?: number;
  contracts_active?: number;
  reports_against?: number;
  reports_filed?: number;
  warnings?: number;
  active_sessions?: number;
  github_connected?: boolean;
  freelancer_listed?: boolean;
  reference?: string;
  phone?: string;
  photo_url?: string;
  identity_status?: string;
  projects_open?: number;
  contracts_completed?: number;
  disputes?: number;
  two_factor?: string;
  last_login_at?: string;
  password_changed_at?: string;
  timezone?: string;
  locale?: string;
  professional_status?: string;
  grants?: AdminGrant[];
};

/** Извлекается отдельным запросом: вкладки страницы пользователя. */
export type AdminGrant = {
  permission: string;
  label: string;
  granted_by?: string;
  granted_by_name?: string;
  granted_at: string;
  note?: string;
};

export type AdminGrantable = { permission: string; label: string };

export type AdminUserProjects = {
  posted: {
    id: string;
    slug: string;
    reference: string;
    title: string;
    status: string;
    budget_display?: string;
    proposals_count: number;
    created_at: string;
    published_at?: string;
  }[];
  contracts: {
    id: string;
    reference: string;
    title: string;
    status: string;
    role: string;
    counterparty: string;
    amount_minor?: number;
    currency?: string;
    created_at: string;
    completed_at?: string;
  }[];
};

export type AdminPayment = {
  id: string;
  reference: string;
  direction: string;
  amount_minor: number;
  fee_minor: number;
  currency: string;
  status: string;
  provider: string;
  contract_reference?: string;
  /** Уже замаскировано на сервере: «•••• 4242». Полного номера здесь не бывает. */
  destination?: string;
  refunded_minor: number;
  created_at: string;
  captured_at?: string;
};

export type AdminSecurity = {
  two_factor: string;
  sessions: {
    id: string;
    role: string;
    user_agent?: string;
    ip?: string;
    last_used_at: string;
    created_at: string;
    expires_at: string;
  }[];
  events: { action: string; outcome: string; ip?: string; detail?: string; created_at: string }[];
  github_connected: boolean;
  github_login?: string;
  password_changed_at?: string;
  failed_logins: number;
  locked_until?: string;
};

/** Проверка личности. Ни один из этих типов не несёт ссылок на изображения. */
export type IdentityDocument = {
  id: string;
  kind: string;
  kind_label: string;
  mime: string;
  byte_size: number;
  width?: number;
  height?: number;
  status: string;
  created_at: string;
  deleted_at?: string;
};

export type IdentityCase = {
  id: string;
  user_id: string;
  status: string;
  status_label: string;
  document_type?: string;
  document_label?: string;
  country_code?: string;
  submitted_at?: string;
  reviewed_at?: string;
  reviewed_by?: string;
  reviewer_name?: string;
  decision_reason?: string;
  resubmit?: { key: string; label: string }[];
  required: string[];
  missing: string[];
  documents: IdentityDocument[];
  retention_expires_at?: string;
  created_at: string;
  updated_at: string;
};

export type IdentityOptions = {
  document_types: { key: string; label: string; needs_back: boolean }[];
  selfie_with_document: boolean;
  max_bytes: number;
};

export type IdentityQueueItem = {
  id: string;
  user_id: string;
  username: string;
  full_name: string;
  status: string;
  status_label: string;
  document_type?: string;
  document_label?: string;
  country_code?: string;
  submitted_at?: string;
  waiting_hours: number;
  documents: number;
};

export type IdentityAccessEntry = {
  id: number;
  actor_id?: string;
  actor_name?: string;
  subject_user_id?: string;
  resource_type: string;
  resource_id?: string;
  action: string;
  reason?: string;
  ip?: string;
  created_at: string;
};

export type IdentityReviewAction = {
  id: number;
  actor_id?: string;
  actor_name?: string;
  action: string;
  reason?: string;
  detail?: string;
  created_at: string;
};

export type IdentityViewToken = { token: string; url: string; expires_at: string };

export type ResubmitReason = { key: string; label: string; kinds: string[] | null };

export type AdminSetting = {
  key: string;
  label: string;
  description?: string;
  type: 'int' | 'bool' | 'string';
  value: unknown;
  scope: string;
  min?: number;
  max?: number;
  updated_at: string;
  group: string;
};

export type FeatureFlag = { key: string; enabled: boolean; rollout_percent: number; description?: string; updated_at?: string };

export type MatchingWeights = {
  version?: number;
  technical: number;
  track_record: number;
  github: number;
  availability: number;
  platform_history: number;
  budget_fit: number;
  feed_threshold: number;
  note?: string;
  created_at?: string;
};

export type AuditRow = {
  id: number;
  actor_id?: string;
  actor_name?: string;
  actor_role?: string;
  action: string;
  subject_type?: string;
  subject_id?: string;
  outcome: string;
  detail?: string;
  ip?: string;
  before?: Record<string, unknown>;
  after?: Record<string, unknown>;
  created_at: string;
};

export type DisputedMilestone = {
  milestone_id: string;
  contract_id: string;
  contract_title: string;
  title: string;
  amount_minor: number;
  currency: string;
  client: PartyRef;
  developer: PartyRef;
  disputed_at: string;
  note?: string;
};

export type ModerationPreview = { title?: string; excerpt?: string; owner_id?: string; owner_username?: string; moderation_state?: string };

export type ModerationItem = {
  id: string;
  subject_type: string;
  subject_id: string;
  reason: string;
  origin: string;
  priority: number;
  status: string;
  created_at: string;
  preview: ModerationPreview;
  decision?: { by: string; by_name?: string; note?: string; outcome: string; at: string };
  reports: number;
  href?: string;
};

export type ModerationReport = {
  id: string;
  subject_type: string;
  subject_id: string;
  reason: string;
  reason_label: string;
  detail?: string;
  status: string;
  /** На странице одного человека: жалоба на него («against») или его («filed»). */
  direction?: 'against' | 'filed';
  reporter?: { user_id: string; username: string; full_name: string };
  resolution?: string;
  resolved_at?: string;
  created_at: string;
  preview: ModerationPreview;
};

export type OwnProposal = {
  id: string;
  project_id: string;
  project_title?: string;
  project_slug?: string;
  project_status?: string;
  amount_minor: number;
  currency: string;
  fee_minor: number;
  payout_minor: number;
  amount_display: string;
  delivery_days: number;
  cover_letter: string;
  approach: string;
  relevant_experience: string;
  questions?: string;
  status: string;
  client_note?: string;
  decline_reason?: string;
  match_score?: number;
  viewed_at?: string;
  shortlisted_at?: string;
  responded_at?: string;
  withdrawn_at?: string;
  created_at: string;
};
