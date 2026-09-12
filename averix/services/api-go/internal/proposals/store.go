package proposals

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"github.com/google/uuid"

	"github.com/averix/api/internal/matching"
	"github.com/averix/api/internal/platform/database"
)

type Store struct {
	db *database.DB
	// publicURL turns an avatar storage key into a servable URL.
	publicURL func(string) string
}

func NewStore(db *database.DB, publicURL func(string) string) *Store {
	if publicURL == nil {
		publicURL = func(key string) string { return key }
	}
	return &Store{db: db, publicURL: publicURL}
}

var (
	ErrNotFound        = errors.New("proposal not found")
	ErrAlreadyProposed = errors.New("a live proposal already exists for this project")
	ErrProjectClosed   = errors.New("this project is not accepting proposals")
)

// New is a validated proposal ready to be written.
type New struct {
	ProjectID          uuid.UUID
	DeveloperID        uuid.UUID
	AmountMinor        int64
	Currency           string
	FeeMinor           int64
	DeliveryDays       int
	CoverLetter        string
	Approach           string
	RelevantExperience string
	Questions          string
	Milestones         []Milestone
	PortfolioIDs       []uuid.UUID
	HistoryIDs         []uuid.UUID
	MatchScore         *matching.Score
	IsDemo             bool
}

// Create writes the proposal and everything attached to it.
//
// The project's status is re-checked inside the transaction: a client closing
// a brief while a developer is writing a proposal must not end with a bid on a
// closed project.
func (s *Store) Create(ctx context.Context, in New) (uuid.UUID, error) {
	var id uuid.UUID

	err := s.db.InTx(ctx, func(q database.Querier) error {
		var status, visibility string
		var clientID uuid.UUID
		err := q.QueryRow(ctx,
			`SELECT status, visibility, client_id FROM projects WHERE id = $1 FOR SHARE`,
			in.ProjectID).Scan(&status, &visibility, &clientID)
		if database.IsNoRows(err) {
			return ErrNotFound
		}
		if err != nil {
			return fmt.Errorf("lock project: %w", err)
		}
		if status != "open" {
			return ErrProjectClosed
		}
		if clientID == in.DeveloperID {
			return fmt.Errorf("a client cannot bid on their own project")
		}
		if visibility != "public" {
			var invited bool
			if err := q.QueryRow(ctx,
				`SELECT EXISTS (SELECT 1 FROM project_invitations
				                WHERE project_id = $1 AND developer_id = $2)`,
				in.ProjectID, in.DeveloperID).Scan(&invited); err != nil {
				return fmt.Errorf("check invitation: %w", err)
			}
			if !invited {
				return ErrProjectClosed
			}
		}

		var breakdown any
		var score *int
		if in.MatchScore != nil {
			raw, err := json.Marshal(in.MatchScore)
			if err != nil {
				return fmt.Errorf("encode match snapshot: %w", err)
			}
			breakdown = raw
			total := in.MatchScore.Total
			score = &total
		}

		err = q.QueryRow(ctx, `
			INSERT INTO proposals
			  (project_id, developer_id, amount_minor, currency, fee_minor, delivery_days,
			   cover_letter, approach, relevant_experience, questions,
			   status, match_score, match_breakdown, is_demo)
			VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'submitted',$11,$12,$13)
			RETURNING id`,
			in.ProjectID, in.DeveloperID, in.AmountMinor, in.Currency, in.FeeMinor,
			in.DeliveryDays, in.CoverLetter, in.Approach, in.RelevantExperience,
			nullIfBlank(in.Questions), score, breakdown, in.IsDemo).Scan(&id)
		if err != nil {
			if database.IsUniqueViolation(err, "proposals_live_key") {
				return ErrAlreadyProposed
			}
			return fmt.Errorf("insert proposal: %w", err)
		}

		for i, m := range in.Milestones {
			if _, err := q.Exec(ctx, `
				INSERT INTO proposal_milestones (proposal_id, position, title, detail, amount_minor, days)
				VALUES ($1, $2, $3, $4, $5, $6)`,
				id, i+1, m.Title, nullIfBlank(m.Detail), m.AmountMinor, m.Days); err != nil {
				return fmt.Errorf("insert proposal milestone: %w", err)
			}
		}

		// Evidence is validated for ownership by the caller; the foreign keys
		// here are the final guard.
		for i, portfolioID := range in.PortfolioIDs {
			if _, err := q.Exec(ctx, `
				INSERT INTO proposal_portfolio_links (proposal_id, portfolio_project_id, sort_order)
				VALUES ($1, $2, $3)`, id, portfolioID, i); err != nil {
				return fmt.Errorf("attach portfolio evidence: %w", err)
			}
		}
		for i, historyID := range in.HistoryIDs {
			if _, err := q.Exec(ctx, `
				INSERT INTO proposal_portfolio_links (proposal_id, completed_history_id, sort_order)
				VALUES ($1, $2, $3)`, id, historyID, 100+i); err != nil {
				return fmt.Errorf("attach verified evidence: %w", err)
			}
		}

		if _, err := q.Exec(ctx,
			`UPDATE projects SET proposals_count = proposals_count + 1, updated_at = now()
			 WHERE id = $1`, in.ProjectID); err != nil {
			return fmt.Errorf("increment proposal count: %w", err)
		}
		return nil
	})
	return id, err
}

// ── Reads ───────────────────────────────────────────────────────────────────

const proposalSelect = `
	SELECT pr.id, pr.project_id, pr.amount_minor, pr.currency, pr.fee_minor,
	       pr.delivery_days, pr.cover_letter, pr.approach, pr.relevant_experience,
	       coalesce(pr.questions, ''), pr.status, coalesce(pr.client_note, ''),
	       coalesce(pr.decline_reason, ''), pr.match_score, pr.match_breakdown,
	       pr.viewed_at, pr.shortlisted_at, pr.responded_at, pr.withdrawn_at,
	       pr.created_at, pr.updated_at,
	       u.id, u.username, u.full_name, coalesce(d.professional_title, ''),
	       coalesce(u.country_code, ''),
	       d.rating_avg, d.rating_count, d.projects_completed, d.success_rate,
	       d.response_time_seconds, d.availability,
	       u.identity_verified_at IS NOT NULL,
	       EXISTS (SELECT 1 FROM github_accounts ga
	               WHERE ga.user_id = u.id AND ga.revoked_at IS NULL),
	       ph.derivatives, ph.placeholder
	FROM proposals pr
	JOIN users u ON u.id = pr.developer_id
	JOIN developer_profiles d ON d.user_id = u.id
	LEFT JOIN developer_photos ph ON ph.user_id = u.id AND ph.is_current`

func (s *Store) scanProposal(row interface{ Scan(...any) error }) (*Proposal, error) {
	var p Proposal
	var breakdown []byte
	var derivatives map[string]map[string]string
	var placeholder *string

	err := row.Scan(
		&p.ID, &p.ProjectID, &p.AmountMinor, &p.Currency, &p.FeeMinor,
		&p.DeliveryDays, &p.CoverLetter, &p.Approach, &p.RelevantExperience,
		&p.Questions, &p.Status, &p.ClientNote, &p.DeclineReason,
		&p.MatchScore, &breakdown,
		&p.ViewedAt, &p.ShortlistedAt, &p.RespondedAt, &p.WithdrawnAt,
		&p.CreatedAt, &p.UpdatedAt,
		&p.Developer.UserID, &p.Developer.Username, &p.Developer.FullName,
		&p.Developer.ProfessionalTitle, &p.Developer.CountryCode,
		&p.Developer.RatingAvg, &p.Developer.RatingCount,
		&p.Developer.ProjectsCompleted, &p.Developer.SuccessRate,
		&p.Developer.ResponseTimeSeconds, &p.Developer.Availability,
		&p.Developer.IdentityVerified, &p.Developer.GitHubConnected,
		&derivatives, &placeholder,
	)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("scan proposal: %w", err)
	}

	p.PayoutMinor = p.AmountMinor - p.FeeMinor
	p.AmountDisplay = FormatMoney(p.AmountMinor, p.Currency)
	p.Developer.PhotoURL = s.avatarURL(derivatives, "128")
	if placeholder != nil {
		p.Developer.Placeholder = *placeholder
	}
	if len(breakdown) > 0 {
		var score matching.Score
		if json.Unmarshal(breakdown, &score) == nil {
			p.MatchBreakdown = &score
		}
	}
	return &p, nil
}

// avatarURL picks a size out of the stored derivative keys, preferring WebP.
func (s *Store) avatarURL(derivatives map[string]map[string]string, size string) string {
	for _, format := range []string{"webp", "jpeg"} {
		sizes, ok := derivatives[format]
		if !ok {
			continue
		}
		if key, ok := sizes[size]; ok {
			return s.publicURL(key)
		}
		// Fall back to whatever size exists rather than showing nothing.
		for _, key := range sizes {
			return s.publicURL(key)
		}
	}
	return ""
}

func (s *Store) ByID(ctx context.Context, id uuid.UUID) (*Proposal, error) {
	p, err := s.scanProposal(s.db.QueryRow(ctx, proposalSelect+" WHERE pr.id = $1", id))
	if err != nil {
		return nil, err
	}
	return s.hydrate(ctx, p)
}

// hydrate loads a single proposal's milestones, evidence and relevant skills.
func (s *Store) hydrate(ctx context.Context, p *Proposal) (*Proposal, error) {
	rows, err := s.db.Query(ctx, `
		SELECT id, position, title, coalesce(detail, ''), amount_minor, days
		FROM proposal_milestones WHERE proposal_id = $1 ORDER BY position`, p.ID)
	if err != nil {
		return nil, fmt.Errorf("query proposal milestones: %w", err)
	}
	for rows.Next() {
		var m Milestone
		if err := rows.Scan(&m.ID, &m.Position, &m.Title, &m.Detail, &m.AmountMinor, &m.Days); err != nil {
			rows.Close()
			return nil, err
		}
		m.AmountDisplay = FormatMoney(m.AmountMinor, p.Currency)
		p.Milestones = append(p.Milestones, m)
	}
	rows.Close()

	evidence, err := s.evidenceFor(ctx, p.ID)
	if err != nil {
		return nil, err
	}
	p.Evidence = evidence

	skills, err := s.developerSkills(ctx, p.Developer.UserID, p.ProjectID)
	if err != nil {
		return nil, err
	}
	p.Developer.Skills = skills
	return p, nil
}

// evidenceFor loads attached past work, honouring the price visibility rules.
//
// The value of a verified contract is shown only when both parties agreed it
// could be. A private contract reads "Private contract" rather than being
// omitted, because its existence is the point.
func (s *Store) evidenceFor(ctx context.Context, proposalID uuid.UUID) ([]EvidenceItem, error) {
	out := []EvidenceItem{}

	rows, err := s.db.Query(ctx, `
		SELECT h.id, h.title, coalesce(l.note, ''), h.client_rating, h.completed_at,
		       h.value_minor, h.currency, h.value_visibility,
		       coalesce(array_agg(sk.name) FILTER (WHERE sk.name IS NOT NULL), '{}')
		FROM proposal_portfolio_links l
		JOIN completed_project_history h ON h.id = l.completed_history_id
		LEFT JOIN completed_project_skills cps ON cps.history_id = h.id
		LEFT JOIN skills sk ON sk.id = cps.skill_id
		WHERE l.proposal_id = $1 AND h.is_visible
		GROUP BY h.id, l.note, l.sort_order
		ORDER BY l.sort_order`, proposalID)
	if err != nil {
		return nil, fmt.Errorf("query verified evidence: %w", err)
	}
	for rows.Next() {
		var item EvidenceItem
		var valueMinor int64
		var currency, visibility string
		if err := rows.Scan(&item.ID, &item.Title, &item.Note, &item.ClientRating,
			&item.CompletedAt, &valueMinor, &currency, &visibility,
			&item.Technologies); err != nil {
			rows.Close()
			return nil, err
		}
		item.Kind = "averix_verified"
		item.ValueDisplay = FormatVisibleValue(valueMinor, currency, visibility)
		out = append(out, item)
	}
	rows.Close()

	rows, err = s.db.Query(ctx, `
		SELECT pp.id, pp.title, coalesce(l.note, ''), pp.completed_on,
		       pp.value_minor, pp.currency, pp.value_visibility,
		       coalesce(pp.project_url, ''), pp.slug,
		       coalesce(array_agg(sk.name) FILTER (WHERE sk.name IS NOT NULL), '{}')
		FROM proposal_portfolio_links l
		JOIN portfolio_projects pp ON pp.id = l.portfolio_project_id
		LEFT JOIN portfolio_skills ps ON ps.portfolio_project_id = pp.id
		LEFT JOIN skills sk ON sk.id = ps.skill_id
		WHERE l.proposal_id = $1 AND pp.is_published AND pp.moderation_state = 'approved'
		GROUP BY pp.id, l.note, l.sort_order
		ORDER BY l.sort_order`, proposalID)
	if err != nil {
		return nil, fmt.Errorf("query portfolio evidence: %w", err)
	}
	defer rows.Close()
	for rows.Next() {
		var item EvidenceItem
		var valueMinor *int64
		var currency, visibility string
		if err := rows.Scan(&item.ID, &item.Title, &item.Note, &item.CompletedAt,
			&valueMinor, &currency, &visibility, &item.URL, &item.Slug,
			&item.Technologies); err != nil {
			return nil, err
		}
		item.Kind = "portfolio"
		if valueMinor != nil {
			item.ValueDisplay = FormatVisibleValue(*valueMinor, currency, visibility)
		}
		out = append(out, item)
	}
	return out, rows.Err()
}

// developerSkills lists the developer's technologies with the ones this project
// requires first, so a client scanning proposals sees the relevant ones.
func (s *Store) developerSkills(ctx context.Context, developerID, projectID uuid.UUID) ([]string, error) {
	rows, err := s.db.Query(ctx, `
		SELECT sk.name
		FROM developer_skills ds
		JOIN skills sk ON sk.id = ds.skill_id
		WHERE ds.user_id = $1
		ORDER BY EXISTS (SELECT 1 FROM project_skills ps
		                 WHERE ps.project_id = $2 AND ps.skill_id = ds.skill_id) DESC,
		         ds.is_primary DESC, ds.sort_order
		LIMIT 8`, developerID, projectID)
	if err != nil {
		return nil, fmt.Errorf("query developer skills: %w", err)
	}
	defer rows.Close()

	out := []string{}
	for rows.Next() {
		var name string
		if err := rows.Scan(&name); err != nil {
			return nil, err
		}
		out = append(out, name)
	}
	return out, rows.Err()
}

// ForProject lists the proposals on a project, ordered as the client asked.
func (s *Store) ForProject(ctx context.Context, projectID uuid.UUID, sort SortOrder, limit int) ([]Card, error) {
	if limit <= 0 || limit > 200 {
		limit = 50
	}

	order := "pr.created_at DESC"
	where := "pr.status NOT IN ('withdrawn','expired','draft')"
	switch sort {
	case SortBestMatch:
		order = "pr.match_score DESC NULLS LAST, pr.created_at DESC"
	case SortNewest:
		order = "pr.created_at DESC"
	case SortPriceLow:
		order = "pr.amount_minor ASC, pr.created_at DESC"
	case SortFastest:
		order = "pr.delivery_days ASC, pr.created_at DESC"
	case SortHighestRated:
		order = "d.rating_avg DESC NULLS LAST, d.rating_count DESC, pr.created_at DESC"
	case SortShortlisted:
		where += " AND pr.shortlisted_at IS NOT NULL"
		order = "pr.shortlisted_at DESC"
	case SortRecommended, "":
		// A blend: fit first, then a demonstrated track record, then price.
		// Shortlisted proposals float to the top because the client already
		// said they were interested.
		order = `(pr.shortlisted_at IS NOT NULL) DESC,
		         coalesce(pr.match_score, 0) * 0.6
		           + least(coalesce(d.rating_avg, 0) * 20, 100) * 0.25
		           + least(d.projects_completed, 20) * 0.75 DESC,
		         pr.created_at DESC`
	}

	rows, err := s.db.Query(ctx, `
		SELECT pr.id, pr.project_id, pr.amount_minor, pr.currency, pr.delivery_days,
		       pr.cover_letter, pr.match_score, pr.match_breakdown, pr.status,
		       pr.viewed_at, pr.shortlisted_at, pr.created_at,
		       (SELECT count(*) FROM proposal_milestones pm WHERE pm.proposal_id = pr.id),
		       u.id, u.username, u.full_name, coalesce(d.professional_title, ''),
		       coalesce(u.country_code, ''),
		       d.rating_avg, d.rating_count, d.projects_completed, d.success_rate,
		       d.response_time_seconds, d.availability,
		       u.identity_verified_at IS NOT NULL,
		       EXISTS (SELECT 1 FROM github_accounts ga
		               WHERE ga.user_id = u.id AND ga.revoked_at IS NULL),
		       ph.derivatives, ph.placeholder
		FROM proposals pr
		JOIN users u ON u.id = pr.developer_id
		JOIN developer_profiles d ON d.user_id = u.id
		LEFT JOIN developer_photos ph ON ph.user_id = u.id AND ph.is_current
		WHERE pr.project_id = $1 AND `+where+`
		ORDER BY `+order+`
		LIMIT $2`, projectID, limit)
	if err != nil {
		return nil, fmt.Errorf("query proposals: %w", err)
	}
	defer rows.Close()

	cards := []Card{}
	for rows.Next() {
		var c Card
		var coverLetter string
		var breakdown []byte
		var derivatives map[string]map[string]string
		var placeholder *string

		if err := rows.Scan(&c.ID, &c.ProjectID, &c.AmountMinor, &c.Currency,
			&c.DeliveryDays, &coverLetter, &c.MatchScore, &breakdown, &c.Status,
			&c.ViewedAt, &c.ShortlistedAt, &c.CreatedAt, &c.MilestoneCount,
			&c.Developer.UserID, &c.Developer.Username, &c.Developer.FullName,
			&c.Developer.ProfessionalTitle, &c.Developer.CountryCode,
			&c.Developer.RatingAvg, &c.Developer.RatingCount,
			&c.Developer.ProjectsCompleted, &c.Developer.SuccessRate,
			&c.Developer.ResponseTimeSeconds, &c.Developer.Availability,
			&c.Developer.IdentityVerified, &c.Developer.GitHubConnected,
			&derivatives, &placeholder); err != nil {
			return nil, fmt.Errorf("scan proposal card: %w", err)
		}

		c.AmountDisplay = FormatMoney(c.AmountMinor, c.Currency)
		c.Preview = previewOf(coverLetter, 180)
		c.Developer.PhotoURL = s.avatarURL(derivatives, "128")
		if placeholder != nil {
			c.Developer.Placeholder = *placeholder
		}
		if len(breakdown) > 0 {
			var score matching.Score
			if json.Unmarshal(breakdown, &score) == nil {
				c.MatchHighlights = score.Highlights
			}
		}
		cards = append(cards, c)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	// The relevant skills and the single best piece of evidence are loaded per
	// card. The lists are short (a project rarely has more than a few dozen
	// proposals) and the queries are indexed.
	for i := range cards {
		skills, err := s.developerSkills(ctx, cards[i].Developer.UserID, projectID)
		if err != nil {
			return nil, err
		}
		if len(skills) > 5 {
			skills = skills[:5]
		}
		cards[i].Developer.Skills = skills

		evidence, err := s.evidenceFor(ctx, cards[i].ID)
		if err != nil {
			return nil, err
		}
		if len(evidence) > 0 {
			cards[i].TopEvidence = &evidence[0]
		}
	}
	return cards, nil
}

// ForDeveloper lists a developer's own proposals.
func (s *Store) ForDeveloper(ctx context.Context, developerID uuid.UUID, status string, limit int) ([]Proposal, error) {
	if limit <= 0 || limit > 100 {
		limit = 50
	}
	condition := ""
	args := []any{developerID, limit}
	if status != "" {
		condition = " AND pr.status = $3"
		args = append(args, status)
	}

	rows, err := s.db.Query(ctx,
		proposalSelect+" WHERE pr.developer_id = $1"+condition+
			" ORDER BY pr.created_at DESC LIMIT $2", args...)
	if err != nil {
		return nil, fmt.Errorf("query developer proposals: %w", err)
	}
	defer rows.Close()

	out := []Proposal{}
	for rows.Next() {
		p, err := s.scanProposal(rows)
		if err != nil {
			return nil, err
		}
		p.IsAuthor = true
		out = append(out, *p)
	}
	return out, rows.Err()
}

// ── State changes ───────────────────────────────────────────────────────────

// Parties resolves who is involved in a proposal, for authorisation.
type Parties struct {
	ProposalID    uuid.UUID
	ProjectID     uuid.UUID
	DeveloperID   uuid.UUID
	ClientID      uuid.UUID
	Status        string
	ProjectStatus string
	AmountMinor   int64
	Currency      string
	DeliveryDays  int
}

func (s *Store) PartiesOf(ctx context.Context, proposalID uuid.UUID) (Parties, error) {
	var p Parties
	p.ProposalID = proposalID
	err := s.db.QueryRow(ctx, `
		SELECT pr.project_id, pr.developer_id, pj.client_id, pr.status, pj.status,
		       pr.amount_minor, pr.currency, pr.delivery_days
		FROM proposals pr JOIN projects pj ON pj.id = pr.project_id
		WHERE pr.id = $1`, proposalID).
		Scan(&p.ProjectID, &p.DeveloperID, &p.ClientID, &p.Status, &p.ProjectStatus,
			&p.AmountMinor, &p.Currency, &p.DeliveryDays)
	if database.IsNoRows(err) {
		return p, ErrNotFound
	}
	return p, err
}

// MarkViewed records that the client opened it, without downgrading a
// shortlisted proposal back to merely viewed.
func (s *Store) MarkViewed(ctx context.Context, proposalID uuid.UUID) error {
	_, err := s.db.Exec(ctx, `
		UPDATE proposals SET
		  viewed_at = coalesce(viewed_at, now()),
		  status = CASE WHEN status = 'submitted' THEN 'viewed' ELSE status END,
		  updated_at = now()
		WHERE id = $1`, proposalID)
	return err
}

// SetShortlisted toggles the client's shortlist.
func (s *Store) SetShortlisted(ctx context.Context, proposalID uuid.UUID, shortlisted bool, note string) error {
	return s.db.InTx(ctx, func(q database.Querier) error {
		var projectID uuid.UUID
		var wasShortlisted bool
		if err := q.QueryRow(ctx,
			`SELECT project_id, shortlisted_at IS NOT NULL FROM proposals WHERE id = $1`,
			proposalID).Scan(&projectID, &wasShortlisted); err != nil {
			if database.IsNoRows(err) {
				return ErrNotFound
			}
			return err
		}

		if shortlisted {
			if _, err := q.Exec(ctx, `
				UPDATE proposals SET
				  shortlisted_at = coalesce(shortlisted_at, now()),
				  status = CASE WHEN status IN ('submitted','viewed') THEN 'shortlisted' ELSE status END,
				  client_note = coalesce(nullif($2, ''), client_note),
				  updated_at = now()
				WHERE id = $1`, proposalID, note); err != nil {
				return err
			}
			if !wasShortlisted {
				if _, err := q.Exec(ctx,
					`UPDATE projects SET shortlisted_count = shortlisted_count + 1 WHERE id = $1`,
					projectID); err != nil {
					return err
				}
			}
			return nil
		}

		if _, err := q.Exec(ctx, `
			UPDATE proposals SET
			  shortlisted_at = NULL,
			  status = CASE WHEN status = 'shortlisted' THEN 'viewed' ELSE status END,
			  updated_at = now()
			WHERE id = $1`, proposalID); err != nil {
			return err
		}
		if wasShortlisted {
			if _, err := q.Exec(ctx,
				`UPDATE projects SET shortlisted_count = greatest(shortlisted_count - 1, 0)
				 WHERE id = $1`, projectID); err != nil {
				return err
			}
		}
		return nil
	})
}

func (s *Store) Decline(ctx context.Context, proposalID uuid.UUID, reason string) error {
	tag, err := s.db.Exec(ctx, `
		UPDATE proposals SET status = 'declined', decline_reason = $2,
		                     responded_at = now(), updated_at = now()
		WHERE id = $1 AND status IN ('submitted','viewed','shortlisted')`,
		proposalID, nullIfBlank(reason))
	if err != nil {
		return fmt.Errorf("decline proposal: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return fmt.Errorf("proposal is not in a state that can be declined")
	}
	return nil
}

func (s *Store) Withdraw(ctx context.Context, proposalID, developerID uuid.UUID) error {
	return s.db.InTx(ctx, func(q database.Querier) error {
		var projectID uuid.UUID
		err := q.QueryRow(ctx, `
			UPDATE proposals SET status = 'withdrawn', withdrawn_at = now(), updated_at = now()
			WHERE id = $1 AND developer_id = $2 AND status IN ('submitted','viewed','shortlisted')
			RETURNING project_id`, proposalID, developerID).Scan(&projectID)
		if database.IsNoRows(err) {
			return fmt.Errorf("proposal is not in a state that can be withdrawn")
		}
		if err != nil {
			return fmt.Errorf("withdraw proposal: %w", err)
		}
		if _, err := q.Exec(ctx,
			`UPDATE projects SET proposals_count = greatest(proposals_count - 1, 0)
			 WHERE id = $1`, projectID); err != nil {
			return err
		}
		return nil
	})
}

// CountToday counts a developer's submissions in the last rolling day, for the
// anti-spam limit.
func (s *Store) CountToday(ctx context.Context, developerID uuid.UUID) (int, error) {
	var n int
	err := s.db.QueryRow(ctx, `
		SELECT count(*) FROM proposals
		WHERE developer_id = $1 AND created_at > now() - interval '24 hours'
		  AND status <> 'draft'`, developerID).Scan(&n)
	return n, err
}

// OwnedEvidence filters the supplied ids down to the ones this developer
// actually owns.
//
// Returning the filtered set rather than an error keeps the endpoint from
// telling a caller which ids exist, while the count difference is enough for
// the service to refuse the request.
func (s *Store) OwnedEvidence(ctx context.Context, developerID uuid.UUID,
	portfolioIDs, historyIDs []uuid.UUID) ([]uuid.UUID, []uuid.UUID, error) {

	ownedPortfolio := []uuid.UUID{}
	if len(portfolioIDs) > 0 {
		rows, err := s.db.Query(ctx, `
			SELECT id FROM portfolio_projects
			WHERE id = ANY($1) AND developer_id = $2 AND is_published`,
			portfolioIDs, developerID)
		if err != nil {
			return nil, nil, fmt.Errorf("check portfolio ownership: %w", err)
		}
		for rows.Next() {
			var id uuid.UUID
			if err := rows.Scan(&id); err != nil {
				rows.Close()
				return nil, nil, err
			}
			ownedPortfolio = append(ownedPortfolio, id)
		}
		rows.Close()
	}

	ownedHistory := []uuid.UUID{}
	if len(historyIDs) > 0 {
		rows, err := s.db.Query(ctx, `
			SELECT id FROM completed_project_history
			WHERE id = ANY($1) AND developer_id = $2 AND is_visible`,
			historyIDs, developerID)
		if err != nil {
			return nil, nil, fmt.Errorf("check verified history ownership: %w", err)
		}
		defer rows.Close()
		for rows.Next() {
			var id uuid.UUID
			if err := rows.Scan(&id); err != nil {
				return nil, nil, err
			}
			ownedHistory = append(ownedHistory, id)
		}
	}
	return ownedPortfolio, ownedHistory, nil
}

// ── Formatting ──────────────────────────────────────────────────────────────

// FormatMoney renders an amount for display.
func FormatMoney(minor int64, currency string) string {
	symbol := map[string]string{"USD": "$", "EUR": "€", "GBP": "£"}[currency]
	if symbol == "" {
		symbol = currency + " "
	}
	whole := minor / 100
	if minor%100 == 0 {
		return symbol + thousands(whole)
	}
	return fmt.Sprintf("%s%s.%02d", symbol, thousands(whole), minor%100)
}

// FormatVisibleValue applies the price visibility ladder from the
// specification.
//
// "private" is rendered as "Private contract" rather than omitted: the work
// happened, and hiding its existence would misrepresent the developer's
// history. Only the figure is withheld.
func FormatVisibleValue(minor int64, currency, visibility string) string {
	switch visibility {
	case "public":
		return FormatMoney(minor, currency)
	case "range":
		return formatRange(minor, currency)
	case "hidden":
		return ""
	case "private":
		return "Private contract"
	}
	return ""
}

// formatRange buckets a figure so the scale is visible without the exact
// amount.
func formatRange(minor int64, currency string) string {
	bands := []struct {
		upto  int64
		label string
	}{
		{25000, "under %s250"},
		{50000, "%s250–%s500"},
		{100000, "%s500–%s1,000"},
		{250000, "%s1,000–%s2,500"},
		{500000, "%s2,500–%s5,000"},
		{1000000, "%s5,000–%s10,000"},
		{2500000, "%s10,000–%s25,000"},
	}
	symbol := map[string]string{"USD": "$", "EUR": "€", "GBP": "£"}[currency]
	if symbol == "" {
		symbol = currency + " "
	}
	for _, band := range bands {
		if minor < band.upto {
			return fillSymbol(band.label, symbol)
		}
	}
	return fillSymbol("%s25,000+", symbol)
}

func fillSymbol(template, symbol string) string {
	out := template
	for strings.Contains(out, "%s") {
		out = strings.Replace(out, "%s", symbol, 1)
	}
	return out
}

func thousands(v int64) string {
	s := fmt.Sprintf("%d", v)
	if len(s) <= 3 {
		return s
	}
	var out []byte
	for i, digit := range []byte(s) {
		if i > 0 && (len(s)-i)%3 == 0 {
			out = append(out, ',')
		}
		out = append(out, digit)
	}
	return string(out)
}

// previewOf takes the opening of a cover letter for the list view.
func previewOf(text string, limit int) string {
	text = strings.TrimSpace(strings.ReplaceAll(text, "\n", " "))
	for strings.Contains(text, "  ") {
		text = strings.ReplaceAll(text, "  ", " ")
	}
	if len(text) <= limit {
		return text
	}
	window := text[:limit]
	if idx := strings.LastIndex(window, " "); idx > limit/2 {
		return window[:idx] + "…"
	}
	return window + "…"
}

func nullIfBlank(s string) any {
	if strings.TrimSpace(s) == "" {
		return nil
	}
	return s
}

// ── Acceptance ──────────────────────────────────────────────────────────────

// Acceptance is everything a proposal contributes to a contract at signature.
//
// Read in one query and handed over as a value: the contract copies these
// terms rather than referencing the proposal, so editing or withdrawing a
// proposal later cannot rewrite a live agreement.
type Acceptance struct {
	ProposalID    uuid.UUID
	ProjectID     uuid.UUID
	ProjectTitle  string
	ProjectStatus string
	ClientID      uuid.UUID
	DeveloperID   uuid.UUID
	Status        string
	AmountMinor   int64
	Currency      string
	DeliveryDays  int
	Milestones    []AcceptanceMilestone
}

type AcceptanceMilestone struct {
	Position    int
	Title       string
	Detail      string
	AmountMinor int64
	Days        *int
}

func (s *Store) AcceptanceFacts(ctx context.Context, proposalID uuid.UUID) (Acceptance, error) {
	var a Acceptance
	a.ProposalID = proposalID
	err := s.db.QueryRow(ctx, `
		SELECT pr.project_id, pj.title, pj.status, pj.client_id, pr.developer_id,
		       pr.status, pr.amount_minor, pr.currency, pr.delivery_days
		FROM proposals pr JOIN projects pj ON pj.id = pr.project_id
		WHERE pr.id = $1`, proposalID).
		Scan(&a.ProjectID, &a.ProjectTitle, &a.ProjectStatus, &a.ClientID,
			&a.DeveloperID, &a.Status, &a.AmountMinor, &a.Currency, &a.DeliveryDays)
	if database.IsNoRows(err) {
		return a, ErrNotFound
	}
	if err != nil {
		return a, fmt.Errorf("load acceptance facts: %w", err)
	}

	rows, err := s.db.Query(ctx, `
		SELECT position, title, coalesce(detail, ''), amount_minor, days
		FROM proposal_milestones WHERE proposal_id = $1 ORDER BY position`, proposalID)
	if err != nil {
		return a, fmt.Errorf("load proposed milestones: %w", err)
	}
	defer rows.Close()
	for rows.Next() {
		var m AcceptanceMilestone
		if err := rows.Scan(&m.Position, &m.Title, &m.Detail, &m.AmountMinor, &m.Days); err != nil {
			return a, err
		}
		a.Milestones = append(a.Milestones, m)
	}
	return a, rows.Err()
}

// MarkAccepted closes the proposal against a signed contract.
//
// The status is part of the WHERE clause, so two clients clicking accept on
// two proposals at the same moment cannot both succeed on the same project:
// the second writes nothing and the caller learns it raced.
func (s *Store) MarkAccepted(ctx context.Context, proposalID, contractID uuid.UUID) error {
	tag, err := s.db.Exec(ctx, `
		UPDATE proposals SET status = 'accepted', responded_at = now(), updated_at = now()
		WHERE id = $1 AND status IN ('submitted','viewed','shortlisted')`, proposalID)
	if err != nil {
		return fmt.Errorf("accept proposal: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return fmt.Errorf("proposal is no longer open")
	}
	return nil
}

// DeclineOthers closes the remaining live proposals on a hired project.
//
// With a reason, and it is the honest one: a developer whose proposal sits
// unanswered for weeks stops writing them, and "the client hired someone else"
// is information they can act on.
func (s *Store) DeclineOthers(ctx context.Context, projectID, acceptedID uuid.UUID,
	reason string) (int, error) {

	tag, err := s.db.Exec(ctx, `
		UPDATE proposals SET status = 'declined', decline_reason = $3,
		                     responded_at = now(), updated_at = now()
		WHERE project_id = $1 AND id <> $2
		  AND status IN ('submitted','viewed','shortlisted')`,
		projectID, acceptedID, nullIfBlank(reason))
	if err != nil {
		return 0, fmt.Errorf("decline remaining proposals: %w", err)
	}
	return int(tag.RowsAffected()), nil
}
