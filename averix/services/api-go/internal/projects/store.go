package projects

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/money"
)

type Store struct{ db *database.DB }

func NewStore(db *database.DB) *Store { return &Store{db: db} }

var (
	ErrNotFound      = errors.New("project not found")
	ErrBadTransition = errors.New("that status change is not allowed")
)

// NewProject is a validated brief ready to be written.
type NewProject struct {
	ClientID         uuid.UUID
	Title            string
	Summary          string
	Description      string
	CategoryID       uuid.UUID
	BudgetType       string
	BudgetMinMinor   *int64
	BudgetMaxMinor   *int64
	Currency         string
	DurationDays     *int
	Deadline         *time.Time
	Starts           string
	ExperienceWanted string
	OverlapFromUTC   *int
	OverlapToUTC     *int
	Visibility       string
	Origin           string
	AssistantSession *uuid.UUID
	RequiredSkills   []uuid.UUID
	OptionalSkills   []uuid.UUID
	Features         []NewFeature
	IsDemo           bool
}

type NewFeature struct {
	Title    string
	Detail   string
	Required bool
	Origin   string
}

// Create writes the project, its skills, its features and its targeting in one
// transaction.
//
// Targeting is resolved from the category rather than supplied by the client:
// a brief reaches the right developers because of what it is, not because of
// who the client thought to name.
func (s *Store) Create(ctx context.Context, in NewProject) (uuid.UUID, error) {
	reference, err := newReference()
	if err != nil {
		return uuid.Nil, err
	}

	var id uuid.UUID
	err = s.db.InTx(ctx, func(q database.Querier) error {
		slug, err := s.uniqueSlug(ctx, q, in.Title)
		if err != nil {
			return err
		}

		err = q.QueryRow(ctx, `
			INSERT INTO projects
			  (reference, client_id, title, slug, summary, description, category_id,
			   status, visibility, budget_type, budget_min_minor, budget_max_minor,
			   currency, duration_days, deadline, starts, experience_wanted,
			   overlap_from_utc, overlap_to_utc, origin, assistant_session_id, is_demo)
			VALUES ($1,$2,$3,$4,$5,$6,$7,'draft',$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
			RETURNING id`,
			reference, in.ClientID, in.Title, slug, nullIfBlank(in.Summary), in.Description,
			in.CategoryID, in.Visibility, in.BudgetType, in.BudgetMinMinor, in.BudgetMaxMinor,
			in.Currency, in.DurationDays, in.Deadline, nullIfBlank(in.Starts),
			nullIfBlank(in.ExperienceWanted), in.OverlapFromUTC, in.OverlapToUTC,
			in.Origin, in.AssistantSession, in.IsDemo).Scan(&id)
		if err != nil {
			return fmt.Errorf("insert project: %w", err)
		}

		for _, skillID := range in.RequiredSkills {
			if _, err := q.Exec(ctx,
				`INSERT INTO project_skills (project_id, skill_id, is_required)
				 VALUES ($1, $2, true) ON CONFLICT DO NOTHING`, id, skillID); err != nil {
				return fmt.Errorf("insert required skill: %w", err)
			}
		}
		for _, skillID := range in.OptionalSkills {
			if _, err := q.Exec(ctx,
				`INSERT INTO project_skills (project_id, skill_id, is_required)
				 VALUES ($1, $2, false) ON CONFLICT DO NOTHING`, id, skillID); err != nil {
				return fmt.Errorf("insert optional skill: %w", err)
			}
		}

		for i, f := range in.Features {
			if _, err := q.Exec(ctx, `
				INSERT INTO project_features (project_id, title, detail, is_required, origin, sort_order)
				VALUES ($1, $2, $3, $4, $5, $6)`,
				id, f.Title, nullIfBlank(f.Detail), f.Required, f.Origin, i); err != nil {
				return fmt.Errorf("insert feature: %w", err)
			}
		}

		if err := resolveTargeting(ctx, q, id, in.CategoryID); err != nil {
			return err
		}

		if _, err := q.Exec(ctx,
			`UPDATE client_profiles SET projects_posted = projects_posted + 1, updated_at = now()
			 WHERE user_id = $1`, in.ClientID); err != nil {
			return fmt.Errorf("increment projects posted: %w", err)
		}
		return nil
	})
	return id, err
}

// resolveTargeting copies the category's specialisation relevance onto the
// project.
//
// It is denormalised deliberately: the feed query joins it on every read, and
// a later change to the taxonomy must not silently re-target briefs that
// developers have already seen and bid on.
func resolveTargeting(ctx context.Context, q database.Querier, projectID, categoryID uuid.UUID) error {
	tag, err := q.Exec(ctx, `
		INSERT INTO project_specialisations (project_id, specialisation_id, relevance)
		SELECT $1, cs.specialisation_id, cs.relevance
		FROM category_specialisations cs
		WHERE cs.category_id = $2
		ON CONFLICT (project_id, specialisation_id) DO UPDATE
		  SET relevance = excluded.relevance`, projectID, categoryID)
	if err != nil {
		return fmt.Errorf("resolve targeting: %w", err)
	}
	if tag.RowsAffected() == 0 {
		// A category with no mapping targets nobody, which would make the
		// project invisible. Falling back to the parent category's mapping
		// keeps a leaf category usable before someone maps it.
		if _, err := q.Exec(ctx, `
			INSERT INTO project_specialisations (project_id, specialisation_id, relevance)
			SELECT $1, cs.specialisation_id, cs.relevance * 0.9
			FROM categories child
			JOIN category_specialisations cs ON cs.category_id = child.parent_id
			WHERE child.id = $2
			ON CONFLICT DO NOTHING`, projectID, categoryID); err != nil {
			return fmt.Errorf("resolve targeting from parent category: %w", err)
		}
	}
	return nil
}

func (s *Store) uniqueSlug(ctx context.Context, q database.Querier, title string) (string, error) {
	base := slugify(title)
	if base == "" {
		base = "project"
	}
	if len(base) > 60 {
		base = strings.Trim(base[:60], "-")
	}
	// A short random suffix rather than a counter: a counter would need a
	// select-then-insert race to resolve, and the suffix also keeps a client's
	// project titles from being enumerable from the slug.
	suffix, err := cryptox.RandomHex(3)
	if err != nil {
		return "", err
	}
	return base + "-" + suffix, nil
}

func newReference() (string, error) {
	// Human-quotable: AVX-7F3K2A. Used in support threads and in the workspace
	// header, where a uuid would be unusable.
	raw, err := cryptox.RandomHex(3)
	if err != nil {
		return "", err
	}
	return "AVX-" + strings.ToUpper(raw), nil
}

// ── Reads ───────────────────────────────────────────────────────────────────

const projectSelect = `
	SELECT p.id, p.reference, p.slug, p.title, coalesce(p.summary, ''), p.description,
	       c.slug, c.name, c.path,
	       p.status, p.visibility, p.budget_type, p.budget_min_minor, p.budget_max_minor,
	       p.currency, p.duration_days, p.deadline, coalesce(p.starts, ''),
	       coalesce(p.experience_wanted, ''), p.overlap_from_utc, p.overlap_to_utc,
	       p.proposals_count, p.invitations_count, p.views_count, p.shortlisted_count,
	       p.origin, p.moderation_state, coalesce(p.moderation_note, ''),
	       p.published_at, p.expires_at, p.completed_at, p.created_at, p.updated_at,
	       u.id, u.username, coalesce(cp.company_name, u.full_name),
	       coalesce(u.country_code, ''), cp.hires_made, cp.rating_avg, cp.rating_count,
	       cp.payment_verified_at IS NOT NULL, u.created_at
	FROM projects p
	JOIN categories c ON c.id = p.category_id
	JOIN users u ON u.id = p.client_id
	JOIN client_profiles cp ON cp.user_id = u.id`

func (s *Store) scanProject(row interface{ Scan(...any) error }) (*Project, error) {
	var p Project
	err := row.Scan(
		&p.ID, &p.Reference, &p.Slug, &p.Title, &p.Summary, &p.Description,
		&p.Category.Slug, &p.Category.Name, &p.Category.Path,
		&p.Status, &p.Visibility, &p.Budget.Type, &p.Budget.MinMinor, &p.Budget.MaxMinor,
		&p.Budget.Currency, &p.DurationDays, &p.Deadline, &p.Starts,
		&p.ExperienceWanted, &p.OverlapFromUTC, &p.OverlapToUTC,
		&p.ProposalsCount, &p.InvitationsCount, &p.ViewsCount, &p.ShortlistedCount,
		&p.Origin, &p.ModerationState, &p.ModerationNote,
		&p.PublishedAt, &p.ExpiresAt, &p.CompletedAt, &p.CreatedAt, &p.UpdatedAt,
		&p.Client.UserID, &p.Client.Username, &p.Client.DisplayName,
		&p.Client.CountryCode, &p.Client.HiresMade, &p.Client.RatingAvg,
		&p.Client.RatingCount, &p.Client.Verified, &p.Client.MemberSince,
	)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("scan project: %w", err)
	}
	p.Budget.Display = formatBudget(p.Budget)
	return &p, nil
}

func (s *Store) ByID(ctx context.Context, id uuid.UUID) (*Project, error) {
	p, err := s.scanProject(s.db.QueryRow(ctx, projectSelect+" WHERE p.id = $1", id))
	if err != nil {
		return nil, err
	}
	return s.hydrate(ctx, p)
}

func (s *Store) BySlug(ctx context.Context, slug string) (*Project, error) {
	p, err := s.scanProject(s.db.QueryRow(ctx, projectSelect+" WHERE p.slug = $1", slug))
	if err != nil {
		return nil, err
	}
	return s.hydrate(ctx, p)
}

// hydrate loads the collections a single project needs.
func (s *Store) hydrate(ctx context.Context, p *Project) (*Project, error) {
	skills, err := s.skillsFor(ctx, p.ID)
	if err != nil {
		return nil, err
	}
	p.Skills = skills

	rows, err := s.db.Query(ctx, `
		SELECT id, title, coalesce(detail, ''), is_required, origin
		FROM project_features WHERE project_id = $1 ORDER BY sort_order`, p.ID)
	if err != nil {
		return nil, fmt.Errorf("query features: %w", err)
	}
	for rows.Next() {
		var f Feature
		if err := rows.Scan(&f.ID, &f.Title, &f.Detail, &f.Required, &f.Origin); err != nil {
			rows.Close()
			return nil, err
		}
		p.Features = append(p.Features, f)
	}
	rows.Close()

	rows, err = s.db.Query(ctx, `
		SELECT sp.slug, sp.name, ps.relevance
		FROM project_specialisations ps
		JOIN specialisations sp ON sp.id = ps.specialisation_id
		WHERE ps.project_id = $1
		ORDER BY ps.relevance DESC`, p.ID)
	if err != nil {
		return nil, fmt.Errorf("query targeting: %w", err)
	}
	defer rows.Close()
	for rows.Next() {
		var t TargetRef
		if err := rows.Scan(&t.Slug, &t.Name, &t.Relevance); err != nil {
			return nil, err
		}
		p.Targeting = append(p.Targeting, t)
	}
	return p, rows.Err()
}

func (s *Store) skillsFor(ctx context.Context, projectID uuid.UUID) ([]SkillRef, error) {
	rows, err := s.db.Query(ctx, `
		SELECT sk.slug, sk.name, coalesce(sk.colour, ''), ps.is_required
		FROM project_skills ps JOIN skills sk ON sk.id = ps.skill_id
		WHERE ps.project_id = $1
		ORDER BY ps.is_required DESC, sk.name`, projectID)
	if err != nil {
		return nil, fmt.Errorf("query project skills: %w", err)
	}
	defer rows.Close()

	out := []SkillRef{}
	for rows.Next() {
		var sk SkillRef
		if err := rows.Scan(&sk.Slug, &sk.Name, &sk.Colour, &sk.Required); err != nil {
			return nil, err
		}
		out = append(out, sk)
	}
	return out, rows.Err()
}

// ── Updates ─────────────────────────────────────────────────────────────────

type UpdateInput struct {
	Title            *string
	Summary          *string
	Description      *string
	CategoryID       *uuid.UUID
	BudgetType       *string
	BudgetMinMinor   *int64
	BudgetMaxMinor   *int64
	Currency         *string
	DurationDays     *int
	Deadline         *time.Time
	Starts           *string
	ExperienceWanted *string
	OverlapFromUTC   *int
	OverlapToUTC     *int
	Visibility       *string
	RequiredSkills   []uuid.UUID
	OptionalSkills   []uuid.UUID
	ReplaceSkills    bool
	Features         []NewFeature
	ReplaceFeatures  bool
}

// Update applies a partial change. COALESCE on every column means an absent
// field is left alone rather than nulled, which is what a PATCH should do.
func (s *Store) Update(ctx context.Context, projectID uuid.UUID, in UpdateInput) error {
	return s.db.InTx(ctx, func(q database.Querier) error {
		_, err := q.Exec(ctx, `
			UPDATE projects SET
			  title            = coalesce($2, title),
			  summary          = coalesce($3, summary),
			  description      = coalesce($4, description),
			  category_id      = coalesce($5, category_id),
			  budget_type      = coalesce($6, budget_type),
			  budget_min_minor = coalesce($7, budget_min_minor),
			  budget_max_minor = coalesce($8, budget_max_minor),
			  currency         = coalesce($9, currency),
			  duration_days    = coalesce($10, duration_days),
			  deadline         = coalesce($11, deadline),
			  starts           = coalesce($12, starts),
			  experience_wanted = coalesce($13, experience_wanted),
			  overlap_from_utc = coalesce($14, overlap_from_utc),
			  overlap_to_utc   = coalesce($15, overlap_to_utc),
			  visibility       = coalesce($16, visibility),
			  updated_at       = now()
			WHERE id = $1`,
			projectID, in.Title, in.Summary, in.Description, in.CategoryID,
			in.BudgetType, in.BudgetMinMinor, in.BudgetMaxMinor, in.Currency,
			in.DurationDays, in.Deadline, in.Starts, in.ExperienceWanted,
			in.OverlapFromUTC, in.OverlapToUTC, in.Visibility)
		if err != nil {
			return fmt.Errorf("update project: %w", err)
		}

		if in.ReplaceSkills {
			if _, err := q.Exec(ctx, `DELETE FROM project_skills WHERE project_id = $1`, projectID); err != nil {
				return fmt.Errorf("clear project skills: %w", err)
			}
			for _, skillID := range in.RequiredSkills {
				if _, err := q.Exec(ctx,
					`INSERT INTO project_skills (project_id, skill_id, is_required)
					 VALUES ($1, $2, true) ON CONFLICT DO NOTHING`, projectID, skillID); err != nil {
					return fmt.Errorf("insert required skill: %w", err)
				}
			}
			for _, skillID := range in.OptionalSkills {
				if _, err := q.Exec(ctx,
					`INSERT INTO project_skills (project_id, skill_id, is_required)
					 VALUES ($1, $2, false) ON CONFLICT DO NOTHING`, projectID, skillID); err != nil {
					return fmt.Errorf("insert optional skill: %w", err)
				}
			}
		}

		if in.ReplaceFeatures {
			if _, err := q.Exec(ctx, `DELETE FROM project_features WHERE project_id = $1`, projectID); err != nil {
				return fmt.Errorf("clear features: %w", err)
			}
			for i, f := range in.Features {
				if _, err := q.Exec(ctx, `
					INSERT INTO project_features (project_id, title, detail, is_required, origin, sort_order)
					VALUES ($1, $2, $3, $4, $5, $6)`,
					projectID, f.Title, nullIfBlank(f.Detail), f.Required, f.Origin, i); err != nil {
					return fmt.Errorf("insert feature: %w", err)
				}
			}
		}

		// Changing the category re-targets the brief, which is the point of
		// changing it.
		if in.CategoryID != nil {
			if _, err := q.Exec(ctx,
				`DELETE FROM project_specialisations WHERE project_id = $1`, projectID); err != nil {
				return fmt.Errorf("clear targeting: %w", err)
			}
			if err := resolveTargeting(ctx, q, projectID, *in.CategoryID); err != nil {
				return err
			}
		}
		return nil
	})
}

// Transition changes the status, refusing anything the lifecycle disallows.
//
// The current status is read and checked inside the same statement, so two
// concurrent requests cannot both see "open" and both transition it.
func (s *Store) Transition(ctx context.Context, projectID uuid.UUID, to string) (string, error) {
	var from string
	err := s.db.QueryRow(ctx, `SELECT status FROM projects WHERE id = $1`, projectID).Scan(&from)
	if database.IsNoRows(err) {
		return "", ErrNotFound
	}
	if err != nil {
		return "", fmt.Errorf("read project status: %w", err)
	}
	if from == to {
		return from, nil
	}
	if !CanTransition(from, to) {
		return from, fmt.Errorf("%w: %s -> %s", ErrBadTransition, from, to)
	}

	var timestamps string
	switch to {
	case StatusOpen:
		timestamps = ", published_at = coalesce(published_at, now()), expires_at = now() + interval '45 days'"
	case StatusCompleted:
		timestamps = ", completed_at = now()"
	case StatusCancelled:
		timestamps = ", cancelled_at = now()"
	}

	tag, err := s.db.Exec(ctx,
		`UPDATE projects SET status = $2, updated_at = now()`+timestamps+
			` WHERE id = $1 AND status = $3`, projectID, to, from)
	if err != nil {
		return from, fmt.Errorf("transition project: %w", err)
	}
	if tag.RowsAffected() == 0 {
		// Someone else changed it between the read and the write.
		return from, fmt.Errorf("%w: the project changed while the request was in flight", ErrBadTransition)
	}
	return to, nil
}

// IsInvolved reports whether a developer has already proposed on a project or
// been hired for it.
//
// Used by the visibility rule: a brief that has closed is nobody else's
// business, but the people who worked on it keep their access to it.
func (s *Store) IsInvolved(ctx context.Context, projectID, developerID uuid.UUID) (bool, error) {
	var involved bool
	err := s.db.QueryRow(ctx, `
		SELECT EXISTS (
		  SELECT 1 FROM proposals
		   WHERE project_id = $1 AND developer_id = $2
		     AND status NOT IN ('draft','withdrawn')
		) OR EXISTS (
		  SELECT 1 FROM contracts
		   WHERE project_id = $1 AND developer_id = $2
		)`, projectID, developerID).Scan(&involved)
	return involved, err
}

func (s *Store) OwnerOf(ctx context.Context, projectID uuid.UUID) (uuid.UUID, string, error) {
	var owner uuid.UUID
	var status string
	err := s.db.QueryRow(ctx,
		`SELECT client_id, status FROM projects WHERE id = $1`, projectID).Scan(&owner, &status)
	if database.IsNoRows(err) {
		return uuid.Nil, "", ErrNotFound
	}
	return owner, status, err
}

func (s *Store) RecordView(ctx context.Context, projectID uuid.UUID, viewerID *uuid.UUID, source string) {
	// Views are analytics: a failure here must never fail the page load.
	bg := context.WithoutCancel(ctx)
	_, _ = s.db.Exec(bg,
		`INSERT INTO project_views (project_id, viewer_id, source) VALUES ($1, $2, $3)`,
		projectID, viewerID, nullIfBlank(source))
	_, _ = s.db.Exec(bg,
		`UPDATE projects SET views_count = views_count + 1 WHERE id = $1`, projectID)
}

func (s *Store) OpenProjectCount(ctx context.Context, clientID uuid.UUID) (int, error) {
	var n int
	err := s.db.QueryRow(ctx,
		`SELECT count(*) FROM projects
		 WHERE client_id = $1 AND status IN ('open','pending_review','draft')`, clientID).Scan(&n)
	return n, err
}

func nullIfBlank(s string) any {
	if strings.TrimSpace(s) == "" {
		return nil
	}
	return s
}

// slugify mirrors the database's slugify() so a slug generated here matches one
// generated there.
func slugify(input string) string {
	var b strings.Builder
	lastDash := true
	for _, r := range strings.ToLower(input) {
		switch {
		case r >= 'a' && r <= 'z', r >= '0' && r <= '9':
			b.WriteRune(r)
			lastDash = false
		default:
			if !lastDash {
				b.WriteByte('-')
				lastDash = true
			}
		}
	}
	return strings.Trim(b.String(), "-")
}

func formatBudget(b Budget) string {
	switch {
	case b.MinMinor != nil && b.MaxMinor != nil && *b.MinMinor != *b.MaxMinor:
		return money.Round(*b.MinMinor, b.Currency) + " – " + money.Round(*b.MaxMinor, b.Currency)
	case b.MaxMinor != nil:
		if b.Type == "hourly" {
			return money.Round(*b.MaxMinor, b.Currency) + " в час"
		}
		return money.Round(*b.MaxMinor, b.Currency)
	case b.MinMinor != nil:
		return "от " + money.Round(*b.MinMinor, b.Currency)
	}
	return "Бюджет не указан"
}
