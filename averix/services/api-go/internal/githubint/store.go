package githubint

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/database"
)

type Store struct {
	db     *database.DB
	sealer *cryptox.Sealer
}

func NewStore(db *database.DB, sealer *cryptox.Sealer) *Store {
	return &Store{db: db, sealer: sealer}
}

var (
	ErrNoAccount      = errors.New("no GitHub account is connected")
	ErrAlreadyClaimed = errors.New("this GitHub account is already connected to another AVERIX account")
)

// Account is a linked GitHub identity. The token is deliberately absent from
// this struct: it is only ever read by the sync path, through AccessToken.
type Account struct {
	ID                     uuid.UUID  `json:"id"`
	UserID                 uuid.UUID  `json:"-"`
	GitHubUserID           int64      `json:"github_user_id"`
	Login                  string     `json:"login"`
	Name                   string     `json:"name,omitempty"`
	AvatarURL              string     `json:"avatar_url,omitempty"`
	ProfileURL             string     `json:"profile_url"`
	Company                string     `json:"company,omitempty"`
	PublicRepos            int        `json:"public_repos"`
	Followers              int        `json:"followers"`
	AccountCreatedAt       *time.Time `json:"account_created_at,omitempty"`
	Scopes                 []string   `json:"scopes"`
	PrivateAccessGrantedAt *time.Time `json:"private_access_granted_at,omitempty"`
	VerifiedAt             time.Time  `json:"verified_at"`
	LastSyncedAt           *time.Time `json:"last_synced_at,omitempty"`
	SyncError              string     `json:"sync_error,omitempty"`
}

// HasPrivateAccess reports whether the developer granted the second consent.
func (a *Account) HasPrivateAccess() bool {
	if a.PrivateAccessGrantedAt == nil {
		return false
	}
	for _, scope := range a.Scopes {
		if scope == "repo" {
			return true
		}
	}
	return false
}

// LinkInput is a verified GitHub identity ready to be stored.
type LinkInput struct {
	UserID       uuid.UUID
	User         *User
	AccessToken  string
	RefreshToken string
	TokenExpires *time.Time
	Scopes       []string
}

// Link stores or refreshes the connection.
//
// The unique index on github_user_id is what stops two AVERIX accounts
// claiming one GitHub identity, which would make the verification badge
// meaningless.
func (s *Store) Link(ctx context.Context, in LinkInput) (*Account, error) {
	sealedAccess, err := s.sealer.SealString(in.AccessToken)
	if err != nil {
		return nil, fmt.Errorf("encrypt access token: %w", err)
	}
	var sealedRefresh []byte
	if in.RefreshToken != "" {
		if sealedRefresh, err = s.sealer.SealString(in.RefreshToken); err != nil {
			return nil, fmt.Errorf("encrypt refresh token: %w", err)
		}
	}

	privateGranted := any(nil)
	for _, scope := range in.Scopes {
		if scope == "repo" {
			privateGranted = time.Now()
		}
	}

	var accountID uuid.UUID
	err = s.db.InTx(ctx, func(q database.Querier) error {
		// A GitHub identity already linked to a different AVERIX account is
		// refused rather than silently moved.
		var existingOwner uuid.UUID
		err := q.QueryRow(ctx,
			`SELECT user_id FROM github_accounts
			 WHERE github_user_id = $1 AND revoked_at IS NULL`,
			in.User.ID).Scan(&existingOwner)
		if err == nil && existingOwner != in.UserID {
			return ErrAlreadyClaimed
		}
		if err != nil && !database.IsNoRows(err) {
			return fmt.Errorf("check existing link: %w", err)
		}

		// Re-connecting replaces the previous link for this user.
		if _, err := q.Exec(ctx,
			`UPDATE github_accounts SET revoked_at = now()
			 WHERE user_id = $1 AND revoked_at IS NULL AND github_user_id <> $2`,
			in.UserID, in.User.ID); err != nil {
			return fmt.Errorf("revoke previous link: %w", err)
		}

		err = q.QueryRow(ctx, `
			INSERT INTO github_accounts
			  (user_id, github_user_id, login, name, avatar_url, profile_url,
			   company, blog, public_repos, followers, account_created_at,
			   access_token_enc, refresh_token_enc, token_expires_at, scopes,
			   private_access_granted_at, verified_at)
			VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,now())
			ON CONFLICT (github_user_id) WHERE revoked_at IS NULL DO UPDATE SET
			  login = excluded.login,
			  name = excluded.name,
			  avatar_url = excluded.avatar_url,
			  company = excluded.company,
			  blog = excluded.blog,
			  public_repos = excluded.public_repos,
			  followers = excluded.followers,
			  access_token_enc = excluded.access_token_enc,
			  refresh_token_enc = excluded.refresh_token_enc,
			  token_expires_at = excluded.token_expires_at,
			  scopes = excluded.scopes,
			  private_access_granted_at = coalesce(excluded.private_access_granted_at,
			                                       github_accounts.private_access_granted_at),
			  sync_error = NULL,
			  updated_at = now()
			RETURNING id`,
			in.UserID, in.User.ID, in.User.Login, nullIfBlank(in.User.Name),
			nullIfBlank(in.User.AvatarURL), in.User.HTMLURL, nullIfBlank(in.User.Company),
			nullIfBlank(in.User.Blog), in.User.PublicRepos, in.User.Followers,
			nullTime(in.User.CreatedAt), sealedAccess, sealedRefresh, in.TokenExpires,
			database.Array(in.Scopes), privateGranted).Scan(&accountID)
		if err != nil {
			return fmt.Errorf("store github link: %w", err)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return s.ByID(ctx, accountID)
}

const accountSelect = `
	SELECT id, user_id, github_user_id, login, coalesce(name, ''),
	       coalesce(avatar_url, ''), profile_url, coalesce(company, ''),
	       public_repos, followers, account_created_at, scopes,
	       private_access_granted_at, verified_at, last_synced_at,
	       coalesce(sync_error, '')
	FROM github_accounts`

func (s *Store) scan(row interface{ Scan(...any) error }) (*Account, error) {
	var a Account
	err := row.Scan(&a.ID, &a.UserID, &a.GitHubUserID, &a.Login, &a.Name,
		&a.AvatarURL, &a.ProfileURL, &a.Company, &a.PublicRepos, &a.Followers,
		&a.AccountCreatedAt, &a.Scopes, &a.PrivateAccessGrantedAt,
		&a.VerifiedAt, &a.LastSyncedAt, &a.SyncError)
	if database.IsNoRows(err) {
		return nil, ErrNoAccount
	}
	if err != nil {
		return nil, fmt.Errorf("scan github account: %w", err)
	}
	return &a, nil
}

func (s *Store) ByID(ctx context.Context, id uuid.UUID) (*Account, error) {
	return s.scan(s.db.QueryRow(ctx, accountSelect+" WHERE id = $1", id))
}

func (s *Store) ByUser(ctx context.Context, userID uuid.UUID) (*Account, error) {
	return s.scan(s.db.QueryRow(ctx,
		accountSelect+" WHERE user_id = $1 AND revoked_at IS NULL", userID))
}

// UserForGitHubID resolves the AVERIX account a GitHub identity belongs to,
// which is how OAuth sign-in finds an existing user.
func (s *Store) UserForGitHubID(ctx context.Context, githubUserID int64) (uuid.UUID, error) {
	var userID uuid.UUID
	err := s.db.QueryRow(ctx,
		`SELECT user_id FROM github_accounts
		 WHERE github_user_id = $1 AND revoked_at IS NULL`, githubUserID).Scan(&userID)
	if database.IsNoRows(err) {
		return uuid.Nil, ErrNoAccount
	}
	return userID, err
}

// AccessToken decrypts the stored token.
//
// The only caller is the sync path. No HTTP handler reaches this, which is why
// the token cannot be exfiltrated through the API even by an admin.
func (s *Store) AccessToken(ctx context.Context, accountID uuid.UUID) (string, error) {
	var sealed []byte
	err := s.db.QueryRow(ctx,
		`SELECT access_token_enc FROM github_accounts
		 WHERE id = $1 AND revoked_at IS NULL`, accountID).Scan(&sealed)
	if database.IsNoRows(err) {
		return "", ErrNoAccount
	}
	if err != nil {
		return "", fmt.Errorf("read access token: %w", err)
	}
	if len(sealed) == 0 {
		return "", ErrNoAccount
	}
	token, err := s.sealer.OpenString(sealed)
	if err != nil {
		// A token that cannot be decrypted means the data key changed. The
		// developer has to reconnect; saying so is better than a 500.
		return "", fmt.Errorf("%w: stored token could not be decrypted", ErrNoAccount)
	}
	return token, nil
}

// Revoke disconnects the account and destroys the stored tokens.
func (s *Store) Revoke(ctx context.Context, userID uuid.UUID) error {
	_, err := s.db.Exec(ctx, `
		UPDATE github_accounts
		   SET revoked_at = now(),
		       access_token_enc = NULL,
		       refresh_token_enc = NULL,
		       updated_at = now()
		 WHERE user_id = $1 AND revoked_at IS NULL`, userID)
	return err
}

// GrantPrivateAccess records the second consent.
func (s *Store) GrantPrivateAccess(ctx context.Context, userID uuid.UUID, scopes []string) error {
	_, err := s.db.Exec(ctx, `
		UPDATE github_accounts
		   SET scopes = $2, private_access_granted_at = now(), updated_at = now()
		 WHERE user_id = $1 AND revoked_at IS NULL`, userID, database.Array(scopes))
	return err
}

// ── Repository mirror ───────────────────────────────────────────────────────

// SaveRepositories replaces the mirrored repository list.
//
// Repositories that disappeared from GitHub are removed rather than left
// behind, so a profile does not keep advertising a deleted project.
func (s *Store) SaveRepositories(ctx context.Context, accountID uuid.UUID, repos []Repository) error {
	return s.db.InTx(ctx, func(q database.Querier) error {
		seen := make([]int64, 0, len(repos))
		for _, r := range repos {
			seen = append(seen, r.ID)
			if _, err := q.Exec(ctx, `
				INSERT INTO github_repositories
				  (github_account_id, repo_id, name, full_name, description, html_url,
				   homepage, is_private, is_fork, is_archived, primary_language,
				   stars, forks, open_issues, size_kb, topics, license,
				   default_branch, pushed_at, repo_created_at)
				VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
				ON CONFLICT (github_account_id, repo_id) DO UPDATE SET
				  name = excluded.name, full_name = excluded.full_name,
				  description = excluded.description, html_url = excluded.html_url,
				  homepage = excluded.homepage, is_private = excluded.is_private,
				  is_fork = excluded.is_fork, is_archived = excluded.is_archived,
				  primary_language = excluded.primary_language,
				  stars = excluded.stars, forks = excluded.forks,
				  open_issues = excluded.open_issues, size_kb = excluded.size_kb,
				  topics = excluded.topics, license = excluded.license,
				  default_branch = excluded.default_branch,
				  pushed_at = excluded.pushed_at, updated_at = now()`,
				accountID, r.ID, r.Name, r.FullName, nullIfBlank(r.Description),
				r.HTMLURL, nullIfBlank(r.Homepage), r.Private, r.Fork, r.Archived,
				nullIfBlank(r.Language), r.Stars, r.Forks, r.OpenIssues, r.Size,
				database.Array(r.Topics), nullIfBlank(r.LicenseID()), nullIfBlank(r.DefaultBranch),
				r.PushedAt, r.CreatedAt); err != nil {
				return fmt.Errorf("upsert repository %s: %w", r.FullName, err)
			}
		}
		if len(seen) > 0 {
			if _, err := q.Exec(ctx,
				`DELETE FROM github_repositories
				 WHERE github_account_id = $1 AND repo_id <> ALL($2)`,
				accountID, seen); err != nil {
				return fmt.Errorf("prune removed repositories: %w", err)
			}
		}
		return nil
	})
}

// RepositoryIDs maps GitHub repository ids onto the mirrored rows.
func (s *Store) RepositoryIDs(ctx context.Context, accountID uuid.UUID) (map[int64]uuid.UUID, error) {
	rows, err := s.db.Query(ctx,
		`SELECT repo_id, id FROM github_repositories WHERE github_account_id = $1`, accountID)
	if err != nil {
		return nil, fmt.Errorf("map repository ids: %w", err)
	}
	defer rows.Close()

	out := map[int64]uuid.UUID{}
	for rows.Next() {
		var repoID int64
		var id uuid.UUID
		if err := rows.Scan(&repoID, &id); err != nil {
			return nil, err
		}
		out[repoID] = id
	}
	return out, rows.Err()
}

func (s *Store) SaveLanguages(ctx context.Context, repositoryID uuid.UUID, languages map[string]int64) error {
	return s.db.InTx(ctx, func(q database.Querier) error {
		if _, err := q.Exec(ctx,
			`DELETE FROM github_repository_languages WHERE repository_id = $1`, repositoryID); err != nil {
			return err
		}
		for language, bytes := range languages {
			if bytes <= 0 {
				continue
			}
			if _, err := q.Exec(ctx, `
				INSERT INTO github_repository_languages (repository_id, language, bytes)
				VALUES ($1, $2, $3)`, repositoryID, language, bytes); err != nil {
				return fmt.Errorf("insert language %s: %w", language, err)
			}
		}
		return nil
	})
}

// DetectedTechnology is one technology the analyser found, with where it found
// it and how confident that makes it.
type DetectedTechnology struct {
	RepositoryID uuid.UUID
	SkillSlug    string
	RawName      string
	Source       string
	Confidence   float64
	VersionSpec  string
}

// SaveDetectedTechnologies records the analyser's findings, resolving skill
// slugs against the taxonomy so an unknown dependency name is stored without a
// skill link rather than inventing one.
func (s *Store) SaveDetectedTechnologies(ctx context.Context, repositoryID uuid.UUID,
	detected []DetectedTechnology) error {

	return s.db.InTx(ctx, func(q database.Querier) error {
		if _, err := q.Exec(ctx,
			`DELETE FROM github_detected_technologies WHERE repository_id = $1`,
			repositoryID); err != nil {
			return err
		}
		for _, d := range detected {
			if _, err := q.Exec(ctx, `
				INSERT INTO github_detected_technologies
				  (repository_id, skill_id, raw_name, source, confidence, version_spec)
				VALUES ($1, (SELECT id FROM skills WHERE slug = $2 AND is_active), $3, $4, $5, $6)
				ON CONFLICT (repository_id, raw_name, source) DO UPDATE SET
				  confidence = greatest(github_detected_technologies.confidence, excluded.confidence),
				  skill_id = coalesce(excluded.skill_id, github_detected_technologies.skill_id)`,
				repositoryID, nullIfBlank(d.SkillSlug), d.RawName, d.Source,
				d.Confidence, nullIfBlank(d.VersionSpec)); err != nil {
				return fmt.Errorf("insert detected technology %s: %w", d.RawName, err)
			}
		}
		return nil
	})
}

// MarkPortfolioCandidate flags a repository the analyser judged worth offering
// as portfolio work.
func (s *Store) MarkPortfolioCandidate(ctx context.Context, repositoryID uuid.UUID,
	candidate bool, reason, readmeExcerpt string) error {

	_, err := s.db.Exec(ctx, `
		UPDATE github_repositories
		   SET portfolio_candidate = $2, candidate_reason = $3,
		       readme_excerpt = coalesce(nullif($4, ''), readme_excerpt),
		       updated_at = now()
		 WHERE id = $1`, repositoryID, candidate, nullIfBlank(reason), readmeExcerpt)
	return err
}

// ── Analysis runs ───────────────────────────────────────────────────────────

type Analysis struct {
	ID                uuid.UUID           `json:"id"`
	Status            string              `json:"status"`
	Trigger           string              `json:"trigger"`
	ReposSeen         int                 `json:"repos_seen"`
	ReposAnalysed     int                 `json:"repos_analysed"`
	LanguageStats     []LanguageStat      `json:"language_stats"`
	TechnologySummary []TechnologySummary `json:"technology_summary"`
	AISummary         string              `json:"ai_summary,omitempty"`
	AIModel           string              `json:"ai_model,omitempty"`
	AIGeneratedAt     *time.Time          `json:"ai_generated_at,omitempty"`
	FocusAreas        []string            `json:"focus_areas,omitempty"`
	ErrorCode         string              `json:"error_code,omitempty"`
	ErrorDetail       string              `json:"error_detail,omitempty"`
	APICallsUsed      int                 `json:"api_calls_used"`
	StartedAt         *time.Time          `json:"started_at,omitempty"`
	FinishedAt        *time.Time          `json:"finished_at,omitempty"`
	CreatedAt         time.Time           `json:"created_at"`
}

// LanguageStat is code share, and is labelled as such everywhere it appears.
type LanguageStat struct {
	Language string  `json:"language"`
	Bytes    int64   `json:"bytes"`
	Share    float64 `json:"share"`
}

type TechnologySummary struct {
	Slug         string  `json:"slug"`
	Name         string  `json:"name"`
	Repositories int     `json:"repositories"`
	Confidence   float64 `json:"confidence"`
	// Which manifests it was found in, so the evidence is inspectable.
	Sources []string `json:"sources,omitempty"`
}

func (s *Store) StartAnalysis(ctx context.Context, accountID uuid.UUID, trigger string) (uuid.UUID, error) {
	var id uuid.UUID
	err := s.db.QueryRow(ctx, `
		INSERT INTO github_analysis (github_account_id, status, trigger, started_at)
		VALUES ($1, 'running', $2, now())
		RETURNING id`, accountID, trigger).Scan(&id)
	if err != nil {
		return uuid.Nil, fmt.Errorf("start analysis: %w", err)
	}
	return id, nil
}

type AnalysisResult struct {
	Status             string
	ReposSeen          int
	ReposAnalysed      int
	LanguageStats      []LanguageStat
	TechnologySummary  []TechnologySummary
	AISummary          string
	AIModel            string
	FocusAreas         []string
	ErrorCode          string
	ErrorDetail        string
	APICallsUsed       int
	RateLimitRemaining int
}

func (s *Store) FinishAnalysis(ctx context.Context, analysisID uuid.UUID, result AnalysisResult) error {
	languages, err := json.Marshal(result.LanguageStats)
	if err != nil {
		return fmt.Errorf("encode language stats: %w", err)
	}
	technologies, err := json.Marshal(result.TechnologySummary)
	if err != nil {
		return fmt.Errorf("encode technology summary: %w", err)
	}

	var aiGenerated any
	if result.AISummary != "" {
		aiGenerated = time.Now()
	}
	var rateRemaining any
	if result.RateLimitRemaining >= 0 {
		rateRemaining = result.RateLimitRemaining
	}

	_, err = s.db.Exec(ctx, `
		UPDATE github_analysis SET
		  status = $2, repos_seen = $3, repos_analysed = $4,
		  language_stats = $5, technology_summary = $6,
		  ai_summary = $7, ai_model = $8, ai_generated_at = $9, focus_areas = $10,
		  error_code = $11, error_detail = $12,
		  api_calls_used = $13, rate_limit_remaining = $14,
		  finished_at = now(), updated_at = now()
		WHERE id = $1`,
		analysisID, result.Status, result.ReposSeen, result.ReposAnalysed,
		languages, technologies, nullIfBlank(result.AISummary),
		nullIfBlank(result.AIModel), aiGenerated, database.Array(result.FocusAreas),
		nullIfBlank(result.ErrorCode), nullIfBlank(result.ErrorDetail),
		result.APICallsUsed, rateRemaining)
	if err != nil {
		return fmt.Errorf("finish analysis: %w", err)
	}
	return nil
}

func (s *Store) MarkSynced(ctx context.Context, accountID uuid.UUID, syncErr string) error {
	_, err := s.db.Exec(ctx, `
		UPDATE github_accounts SET last_synced_at = now(), sync_error = $2, updated_at = now()
		WHERE id = $1`, accountID, nullIfBlank(syncErr))
	return err
}

// LatestAnalysis returns the most recent run for a developer's account.
func (s *Store) LatestAnalysis(ctx context.Context, userID uuid.UUID) (*Analysis, error) {
	var a Analysis
	var languages, technologies []byte
	err := s.db.QueryRow(ctx, `
		SELECT a.id, a.status, a.trigger, a.repos_seen, a.repos_analysed,
		       a.language_stats, a.technology_summary,
		       coalesce(a.ai_summary, ''), coalesce(a.ai_model, ''), a.ai_generated_at,
		       a.focus_areas, coalesce(a.error_code, ''), coalesce(a.error_detail, ''),
		       a.api_calls_used, a.started_at, a.finished_at, a.created_at
		FROM github_analysis a
		JOIN github_accounts ga ON ga.id = a.github_account_id
		WHERE ga.user_id = $1 AND ga.revoked_at IS NULL
		ORDER BY a.created_at DESC LIMIT 1`, userID).
		Scan(&a.ID, &a.Status, &a.Trigger, &a.ReposSeen, &a.ReposAnalysed,
			&languages, &technologies, &a.AISummary, &a.AIModel, &a.AIGeneratedAt,
			&a.FocusAreas, &a.ErrorCode, &a.ErrorDetail, &a.APICallsUsed,
			&a.StartedAt, &a.FinishedAt, &a.CreatedAt)
	if database.IsNoRows(err) {
		return nil, ErrNoAccount
	}
	if err != nil {
		return nil, fmt.Errorf("load latest analysis: %w", err)
	}
	_ = json.Unmarshal(languages, &a.LanguageStats)
	_ = json.Unmarshal(technologies, &a.TechnologySummary)
	// The internal detail of a failure is not the developer's problem; the
	// error code is enough for the UI to say something useful.
	a.ErrorDetail = ""
	return &a, nil
}

// AttachEvidenceToSkills records that GitHub corroborated a declared skill.
//
// This only ever adds evidence to a technology the developer already claimed:
// the analysis never adds a skill to someone's profile on their behalf.
func (s *Store) AttachEvidenceToSkills(ctx context.Context, userID uuid.UUID, slugs []string) error {
	if len(slugs) == 0 {
		return nil
	}
	_, err := s.db.Exec(ctx, `
		UPDATE developer_skills ds SET
		  evidence = CASE WHEN 'github' = ANY(ds.evidence) THEN ds.evidence
		                  ELSE array_append(ds.evidence, 'github') END
		FROM skills sk
		WHERE sk.id = ds.skill_id AND ds.user_id = $1 AND sk.slug = ANY($2)`,
		userID, slugs)
	return err
}

// PortfolioCandidates lists the repositories the analyser suggested, for the
// onboarding step that offers to turn them into portfolio entries.
func (s *Store) PortfolioCandidates(ctx context.Context, userID uuid.UUID, limit int) ([]map[string]any, error) {
	if limit <= 0 || limit > 50 {
		limit = 12
	}
	rows, err := s.db.Query(ctx, `
		SELECT r.id, r.name, r.full_name, coalesce(r.description, ''), r.html_url,
		       coalesce(r.homepage, ''), coalesce(r.primary_language, ''),
		       r.stars, r.pushed_at, coalesce(r.candidate_reason, ''),
		       coalesce(r.readme_excerpt, ''), r.topics
		FROM github_repositories r
		JOIN github_accounts ga ON ga.id = r.github_account_id
		WHERE ga.user_id = $1 AND ga.revoked_at IS NULL
		  AND r.portfolio_candidate AND NOT r.is_private
		ORDER BY r.stars DESC, r.pushed_at DESC
		LIMIT $2`, userID, limit)
	if err != nil {
		return nil, fmt.Errorf("query portfolio candidates: %w", err)
	}
	defer rows.Close()

	out := []map[string]any{}
	for rows.Next() {
		var (
			id                                   uuid.UUID
			name, fullName, description, htmlURL string
			homepage, language, reason, readme   string
			stars                                int
			pushedAt                             *time.Time
			topics                               []string
		)
		if err := rows.Scan(&id, &name, &fullName, &description, &htmlURL,
			&homepage, &language, &stars, &pushedAt, &reason, &readme, &topics); err != nil {
			return nil, err
		}
		out = append(out, map[string]any{
			"repository_id": id,
			"name":          name,
			"full_name":     fullName,
			"description":   description,
			"url":           htmlURL,
			"homepage":      homepage,
			"language":      language,
			"stars":         stars,
			"pushed_at":     pushedAt,
			"reason":        reason,
			"readme":        readme,
			"topics":        topics,
		})
	}
	return out, rows.Err()
}

func nullIfBlank(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func nullTime(t time.Time) any {
	if t.IsZero() {
		return nil
	}
	return t
}
