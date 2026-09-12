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
