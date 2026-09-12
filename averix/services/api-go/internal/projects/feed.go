package projects

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/matching"
)

// FeedQuery describes one page of a developer's feed.
type FeedQuery struct {
	DeveloperID uuid.UUID
	Tab         FeedTab
	// For TabCategory.
	CategorySlug string
	// Free-text filter applied on top of the tab.
	Search string
	// Filters the mobile filter sheet exposes.
	SkillSlugs []string
	BudgetMin  *int64
	BudgetMax  *int64
	Limit      int
	// Keyset pagination: the published_at and id of the last row seen.
	CursorTime *time.Time
	CursorID   *uuid.UUID
	// Ordering: "match", "newest", "budget_high", "fewest_proposals".
	Sort string
}

// FeedPage is one page plus the cursor for the next.
type FeedPage struct {
	Cards      []FeedCard `json:"projects"`
	NextCursor string     `json:"next_cursor,omitempty"`
	HasMore    bool       `json:"has_more"`
	Total      *int       `json:"total,omitempty"`
}

const defaultFeedLimit = 20

// Feed returns the projects a developer should see.
//
// The targeting join is the heart of the product's promise: a project appears
// only if it targets one of this developer's specialisations. That is an inner
// join on project_specialisations, not a scoring penalty, so an iOS developer
// cannot see a Telegram bot brief however the rest of the query is tuned.
//
// Scoring happens after the SQL, on a bounded candidate set, because the score
// needs facts (GitHub manifests, completed-contract overlap) that do not belong
// in a feed query.
func (s *Store) Feed(ctx context.Context, q FeedQuery, engine *matching.Engine,
	facts matching.DeveloperFacts, threshold int) (*FeedPage, error) {

	if q.Limit <= 0 || q.Limit > 50 {
		q.Limit = defaultFeedLimit
	}

	// Over-fetch: scoring discards candidates below the threshold, so asking
	// for exactly a page's worth would return a short page.
	fetch := q.Limit * 3
	if fetch > 150 {
		fetch = 150
	}

	where := []string{
		"p.status = 'open'",
		"p.moderation_state = 'approved'",
		// A client's own project never appears in their developer feed.
		"p.client_id <> $1",
		// Nothing they have already bid on.
		`NOT EXISTS (SELECT 1 FROM proposals pr
		             WHERE pr.project_id = p.id AND pr.developer_id = $1
		               AND pr.status NOT IN ('withdrawn','expired'))`,
	}
	args := []any{q.DeveloperID}
	arg := func(v any) string {
		args = append(args, v)
		return fmt.Sprintf("$%d", len(args))
	}

	// Visibility: public projects, plus invite-only ones this developer was
	// actually invited to.
	where = append(where, `(p.visibility = 'public' OR EXISTS (
		SELECT 1 FROM project_invitations pi
		WHERE pi.project_id = p.id AND pi.developer_id = $1))`)

	joins := []string{}
	switch q.Tab {
	case TabSaved:
		joins = append(joins, "JOIN saved_projects sp ON sp.project_id = p.id AND sp.developer_id = $1")
	case TabInvitations:
		joins = append(joins,
			"JOIN project_invitations inv ON inv.project_id = p.id AND inv.developer_id = $1")
		where = append(where, "inv.status IN ('sent','viewed')")
	case TabCategory:
		if q.CategorySlug != "" {
			// Matches the category and everything beneath it, which is what the
			// materialised path column is for.
			where = append(where, fmt.Sprintf(
				`c.path LIKE (SELECT path || '%%' FROM categories WHERE slug = %s)`,
				arg(q.CategorySlug)))
		}
	}

	// Targeting. Saved and invitation tabs skip it: a developer who bookmarked
	// a project, or a client who invited them personally, has overridden the
	// automatic targeting, and hiding it would be obtuse.
	//
	// EXISTS rather than a join: a project targeting three of this developer's
	// specialisations must appear once, and a join would need DISTINCT ON,
	// which imposes its own leading ORDER BY and would silently override the
	// feed's ordering — breaking keyset pagination.
	if q.Tab != TabSaved && q.Tab != TabInvitations {
		where = append(where, `EXISTS (
			SELECT 1 FROM project_specialisations ps
			JOIN developer_targeting dt ON dt.specialisation_id = ps.specialisation_id
			WHERE ps.project_id = p.id)`)
	}

	if q.Search != "" {
		where = append(where, fmt.Sprintf(
			`(p.search_doc @@ plainto_tsquery('simple', %s) OR p.title ILIKE '%%' || %s || '%%')`,
			arg(q.Search), arg(q.Search)))
	}
	if len(q.SkillSlugs) > 0 {
		where = append(where, fmt.Sprintf(
			`EXISTS (SELECT 1 FROM project_skills pk JOIN skills sk ON sk.id = pk.skill_id
			         WHERE pk.project_id = p.id AND sk.slug = ANY(%s))`, arg(q.SkillSlugs)))
	}
	if q.BudgetMin != nil {
		where = append(where, fmt.Sprintf("coalesce(p.budget_max_minor, p.budget_min_minor) >= %s", arg(*q.BudgetMin)))
	}
	if q.BudgetMax != nil {
		where = append(where, fmt.Sprintf("coalesce(p.budget_min_minor, p.budget_max_minor) <= %s", arg(*q.BudgetMax)))
	}
	if q.CursorTime != nil && q.CursorID != nil {
		// Keyset pagination rather than OFFSET: a feed that shifts as projects
		// are published would otherwise duplicate and skip rows.
		where = append(where, fmt.Sprintf("(p.published_at, p.id) < (%s, %s)",
			arg(*q.CursorTime), arg(*q.CursorID)))
	}

	order := "p.published_at DESC, p.id DESC"
	switch q.Sort {
	case "budget_high":
		order = "coalesce(p.budget_max_minor, p.budget_min_minor) DESC NULLS LAST, p.published_at DESC, p.id DESC"
	case "fewest_proposals":
		order = "p.proposals_count ASC, p.published_at DESC, p.id DESC"
	}

	// developer_targeting is a CTE of this developer's specialisations, with
	// the primary one weighted fully and the additional ones at 0.8 — the same
	// treatment the engine applies, so the SQL's ordering and the final score
	// agree about who is a better fit.
	query := `
	WITH developer_targeting AS (
	  SELECT d.primary_specialisation_id AS specialisation_id, 1.0::numeric AS weight
	  FROM developer_profiles d WHERE d.user_id = $1 AND d.primary_specialisation_id IS NOT NULL
	  UNION
	  SELECT ds.specialisation_id, 0.8::numeric
	  FROM developer_specialisations ds WHERE ds.user_id = $1
	)
	SELECT p.id, p.slug, p.reference, p.title, coalesce(p.summary, ''), p.description,
	       c.slug, c.name,
	       p.budget_type, p.budget_min_minor, p.budget_max_minor, p.currency,
	       p.proposals_count, p.published_at,
	       coalesce(u.country_code, ''), cp.hires_made,
	       cp.payment_verified_at IS NOT NULL,
	       EXISTS (SELECT 1 FROM saved_projects s
	               WHERE s.project_id = p.id AND s.developer_id = $1),
	       EXISTS (SELECT 1 FROM project_invitations i
	               WHERE i.project_id = p.id AND i.developer_id = $1)
	FROM projects p
	JOIN categories c ON c.id = p.category_id
	JOIN users u ON u.id = p.client_id
	JOIN client_profiles cp ON cp.user_id = u.id
	` + strings.Join(joins, "\n\t") + `
	WHERE ` + strings.Join(where, "\n\t  AND ") + `
	ORDER BY ` + order + `
	LIMIT ` + fmt.Sprintf("%d", fetch)

	rows, err := s.db.Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("query feed: %w", err)
	}

	type candidate struct {
		card        FeedCard
		description string
	}
	var candidates []candidate
	for rows.Next() {
		var c candidate
		if err := rows.Scan(
			&c.card.ID, &c.card.Slug, &c.card.Reference, &c.card.Title,
			&c.card.Excerpt, &c.description,
			&c.card.Category.Slug, &c.card.Category.Name,
			&c.card.Budget.Type, &c.card.Budget.MinMinor, &c.card.Budget.MaxMinor,
			&c.card.Budget.Currency,
			&c.card.ProposalsCount, &c.card.PublishedAt,
			&c.card.ClientCountry, &c.card.ClientHires, &c.card.ClientVerified,
			&c.card.IsSaved, &c.card.IsInvited,
		); err != nil {
			rows.Close()
			return nil, fmt.Errorf("scan feed row: %w", err)
		}
		candidates = append(candidates, c)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate feed: %w", err)
	}

	// Score the candidates and drop the ones below the threshold.
	page := &FeedPage{Cards: []FeedCard{}}
	for _, c := range candidates {
		card := c.card
		if card.Excerpt == "" {
			card.Excerpt = firstSentence(c.description, 140)
		}
		card.Budget.Display = formatBudget(card.Budget)

		skills, err := s.skillsFor(ctx, card.ID)
		if err != nil {
			return nil, err
		}
		// Five tags is what fits on a 375px card without wrapping to a third
		// line; the rest are on the project page.
		if len(skills) > 5 {
			skills = skills[:5]
		}
		card.Skills = skills

		if engine != nil {
			projectFacts, err := s.projectFactsFor(ctx, card.ID, card.Category.Slug)
			if err != nil {
				return nil, err
			}
			score := engine.Score(projectFacts, facts)
			if score.Excluded {
				continue
			}
			// The "For you" tab is where the threshold applies; the other tabs
			// are explicit requests and must not hide what was asked for.
			if q.Tab == TabForYou && score.Total < threshold {
				continue
			}
			total := score.Total
			card.MatchScore = &total
			card.MatchHighlights = score.Highlights
		}

		page.Cards = append(page.Cards, card)
		if len(page.Cards) >= q.Limit {
			break
		}
	}

	// The For You tab orders by fit, with recency breaking ties, unless the
	// developer asked for a different ordering.
	if (q.Tab == TabForYou && q.Sort == "") || q.Sort == "match" {
		sortByMatchThenRecency(page.Cards)
	}

	page.HasMore = len(candidates) > len(page.Cards)
	if n := len(page.Cards); n > 0 && page.HasMore {
		last := page.Cards[n-1]
		if last.PublishedAt != nil {
			page.NextCursor = encodeCursor(*last.PublishedAt, last.ID)
		}
	}
	return page, nil
}

// projectFactsFor loads the scoring inputs for one candidate. The skills and
// targeting are small indexed lookups; loading them per candidate keeps the
// feed query itself simple and its plan stable.
func (s *Store) projectFactsFor(ctx context.Context, projectID uuid.UUID, categorySlug string) (matching.ProjectFacts, error) {
	facts := matching.ProjectFacts{
		CategorySlug:          categorySlug,
		TargetSpecialisations: map[string]float64{},
	}

	rows, err := s.db.Query(ctx, `
		SELECT sk.slug, ps.is_required
		FROM project_skills ps JOIN skills sk ON sk.id = ps.skill_id
		WHERE ps.project_id = $1`, projectID)
	if err != nil {
		return facts, fmt.Errorf("load candidate skills: %w", err)
	}
	for rows.Next() {
		var slug string
		var required bool
		if err := rows.Scan(&slug, &required); err != nil {
			rows.Close()
			return facts, err
		}
		if required {
			facts.RequiredSkills = append(facts.RequiredSkills, slug)
		} else {
			facts.OptionalSkills = append(facts.OptionalSkills, slug)
		}
	}
	rows.Close()

	rows, err = s.db.Query(ctx, `
		SELECT sp.slug, ps.relevance
		FROM project_specialisations ps
		JOIN specialisations sp ON sp.id = ps.specialisation_id
		WHERE ps.project_id = $1`, projectID)
	if err != nil {
		return facts, fmt.Errorf("load candidate targeting: %w", err)
	}
	for rows.Next() {
		var slug string
		var relevance float64
		if err := rows.Scan(&slug, &relevance); err != nil {
			rows.Close()
			return facts, err
		}
		facts.TargetSpecialisations[slug] = relevance
	}
	rows.Close()

	var budgetMin, budgetMax *int64
	var duration *int
	var experience *string
	err = s.db.QueryRow(ctx, `
		SELECT budget_min_minor, budget_max_minor, currency, budget_type,
		       duration_days, experience_wanted, overlap_from_utc, overlap_to_utc
		FROM projects WHERE id = $1`, projectID).
		Scan(&budgetMin, &budgetMax, &facts.Currency, &facts.BudgetType,
			&duration, &experience, &facts.OverlapFromUTC, &facts.OverlapToUTC)
	if err != nil {
		return facts, fmt.Errorf("load candidate budget: %w", err)
	}
	if budgetMin != nil {
		facts.BudgetMinMinor = *budgetMin
	}
	if budgetMax != nil {
		facts.BudgetMaxMinor = *budgetMax
	}
	if duration != nil {
		facts.DurationDays = *duration
	}
	if experience != nil {
		facts.ExperienceWanted = *experience
	}
	return facts, nil
}

// ClientProjects lists a client's own projects for their dashboard.
func (s *Store) ClientProjects(ctx context.Context, clientID uuid.UUID, status string, limit int) ([]Project, error) {
	if limit <= 0 || limit > 100 {
		limit = 25
	}
	condition := ""
	args := []any{clientID, limit}
	if status != "" {
		condition = " AND p.status = $3"
		args = append(args, status)
	}

	rows, err := s.db.Query(ctx,
		projectSelect+" WHERE p.client_id = $1"+condition+
			" ORDER BY p.created_at DESC LIMIT $2", args...)
	if err != nil {
		return nil, fmt.Errorf("query client projects: %w", err)
	}
	defer rows.Close()

	out := []Project{}
	for rows.Next() {
		p, err := s.scanProject(rows)
		if err != nil {
			return nil, err
		}
		skills, err := s.skillsFor(ctx, p.ID)
		if err != nil {
			return nil, err
		}
		p.Skills = skills
		out = append(out, *p)
	}
	return out, rows.Err()
}

// Tabs builds the developer feed's tab set from the taxonomy and the
// developer's own specialisations, so the tabs match what they actually do
// rather than being a fixed list.
func (s *Store) Tabs(ctx context.Context, developerID uuid.UUID) ([]Tab, error) {
	tabs := []Tab{
		{Key: string(TabForYou), Label: "For you"},
	}

	rows, err := s.db.Query(ctx, `
		SELECT DISTINCT c.slug, c.name, c.sort_order
		FROM category_specialisations cs
		JOIN categories c ON c.id = cs.category_id
		WHERE c.depth = 0 AND c.is_active
		  AND cs.relevance >= 0.6
		  AND cs.specialisation_id IN (
		    SELECT primary_specialisation_id FROM developer_profiles
		    WHERE user_id = $1 AND primary_specialisation_id IS NOT NULL
		    UNION
		    SELECT specialisation_id FROM developer_specialisations WHERE user_id = $1
		  )
		ORDER BY c.sort_order
		LIMIT 5`, developerID)
	if err != nil {
		return nil, fmt.Errorf("query feed tabs: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var slug, name string
		var order int
		if err := rows.Scan(&slug, &name, &order); err != nil {
			return nil, err
		}
		tabs = append(tabs, Tab{Key: slug, Label: name, CategorySlug: slug})
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	var invitations int
	_ = s.db.QueryRow(ctx, `
		SELECT count(*) FROM project_invitations
		WHERE developer_id = $1 AND status IN ('sent','viewed')`, developerID).Scan(&invitations)
	if invitations > 0 {
		tabs = append(tabs, Tab{Key: string(TabInvitations), Label: "Invitations", Count: &invitations})
	}

	var saved int
	_ = s.db.QueryRow(ctx,
		`SELECT count(*) FROM saved_projects WHERE developer_id = $1`, developerID).Scan(&saved)
	tabs = append(tabs, Tab{Key: string(TabSaved), Label: "Saved", Count: &saved})
	tabs = append(tabs, Tab{Key: string(TabRecent), Label: "Recent"})
	return tabs, nil
}

// HasProposed reports whether a developer already bid, so the project page can
// show their proposal rather than a bid button.
func (s *Store) HasProposed(ctx context.Context, projectID, developerID uuid.UUID) (bool, error) {
	var exists bool
	err := s.db.QueryRow(ctx, `
		SELECT EXISTS (SELECT 1 FROM proposals
		               WHERE project_id = $1 AND developer_id = $2
		                 AND status NOT IN ('withdrawn','expired'))`,
		projectID, developerID).Scan(&exists)
	return exists, err
}

func (s *Store) IsSaved(ctx context.Context, projectID, developerID uuid.UUID) (bool, error) {
	var exists bool
	err := s.db.QueryRow(ctx,
		`SELECT EXISTS (SELECT 1 FROM saved_projects WHERE project_id = $1 AND developer_id = $2)`,
		projectID, developerID).Scan(&exists)
	return exists, err
}

func (s *Store) IsInvited(ctx context.Context, projectID, developerID uuid.UUID) (bool, error) {
	var exists bool
	err := s.db.QueryRow(ctx,
		`SELECT EXISTS (SELECT 1 FROM project_invitations WHERE project_id = $1 AND developer_id = $2)`,
		projectID, developerID).Scan(&exists)
	return exists, err
}

// sortByMatchThenRecency orders the feed by fit, breaking ties on freshness.
//
// A pure match ordering would leave a stale 96% above a fresh 94% for weeks,
// so recency is the tiebreaker rather than a separate sort option nobody uses.
func sortByMatchThenRecency(cards []FeedCard) {
	score := func(c FeedCard) int {
		if c.MatchScore == nil {
			return 0
		}
		return *c.MatchScore
	}
	// Insertion sort: a page is at most 50 cards, and a stable sort keeps the
	// SQL ordering as the final tiebreaker.
	for i := 1; i < len(cards); i++ {
		for j := i; j > 0; j-- {
			a, b := cards[j-1], cards[j]
			if score(a) > score(b) {
				break
			}
			if score(a) == score(b) {
				if a.PublishedAt == nil || b.PublishedAt == nil ||
					!b.PublishedAt.After(*a.PublishedAt) {
					break
				}
			}
			cards[j-1], cards[j] = cards[j], cards[j-1]
		}
	}
}

// firstSentence trims a description down to a card-sized excerpt, ending on a
// sentence boundary where there is one nearby.
func firstSentence(text string, limit int) string {
	text = strings.TrimSpace(strings.ReplaceAll(text, "\n", " "))
	for strings.Contains(text, "  ") {
		text = strings.ReplaceAll(text, "  ", " ")
	}
	if len(text) <= limit {
		return text
	}
	window := text[:limit]
	if idx := strings.LastIndexAny(window, ".!?"); idx > limit/2 {
		return window[:idx+1]
	}
	if idx := strings.LastIndex(window, " "); idx > 0 {
		return window[:idx] + "…"
	}
	return window + "…"
}

// Cursors are opaque to the client: "<unix-nanos>.<uuid>".
func encodeCursor(t time.Time, id uuid.UUID) string {
	return fmt.Sprintf("%d.%s", t.UnixNano(), id.String())
}

// DecodeCursor parses a cursor, rejecting anything malformed rather than
// silently restarting the feed from the top.
func DecodeCursor(cursor string) (*time.Time, *uuid.UUID, error) {
	if cursor == "" {
		return nil, nil, nil
	}
	nanos, rawID, ok := strings.Cut(cursor, ".")
	if !ok {
		return nil, nil, fmt.Errorf("malformed cursor")
	}
	var ns int64
	if _, err := fmt.Sscanf(nanos, "%d", &ns); err != nil {
		return nil, nil, fmt.Errorf("malformed cursor timestamp")
	}
	id, err := uuid.Parse(rawID)
	if err != nil {
		return nil, nil, fmt.Errorf("malformed cursor id")
	}
	t := time.Unix(0, ns).UTC()
	return &t, &id, nil
}
