package search

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/google/uuid"

	"github.com/averix/api/internal/notifications"
	"github.com/averix/api/internal/platform/database"
)

var ErrNotFound = errors.New("not found")

type Store struct {
	db        *database.DB
	publicURL func(string) string
}

func NewStore(db *database.DB, publicURL func(string) string) *Store {
	return &Store{db: db, publicURL: publicURL}
}

// visibleFreelancers is the one rule every freelancer query shares: finished
// onboarding, chose to be listed, in good standing, not under moderation.
const visibleFreelancers = `
	u.deleted_at IS NULL AND u.status = 'active'
	AND d.is_searchable AND d.moderation_state = 'approved'
	AND d.onboarding_completed_at IS NOT NULL`

const cardColumns = `
	u.id, u.username, u.full_name, ph.derivatives,
	coalesce(d.professional_title, ''),
	sp.slug, sp.name, sp.short_name,
	sector.slug,
	d.rating_avg, d.rating_count, d.projects_completed,
	d.hourly_rate_minor, d.rate_currency, d.show_hourly_rate,
	d.availability,
	d.show_location, u.city, u.country_code,
	u.identity_verified_at IS NOT NULL,
	EXISTS (SELECT 1 FROM github_accounts g WHERE g.user_id = u.id AND g.revoked_at IS NULL),
	d.is_featured, u.last_seen_at,
	($1::uuid IS NOT NULL AND EXISTS (SELECT 1 FROM saved_developers sd WHERE sd.client_id = $1 AND sd.developer_id = u.id))`

const cardJoins = `
	FROM users u
	JOIN developer_profiles d ON d.user_id = u.id
	LEFT JOIN specialisations sp ON sp.id = d.primary_specialisation_id
	LEFT JOIN LATERAL (
	  SELECT c.slug FROM category_specialisations cs
	  JOIN categories c ON c.id = cs.category_id
	  WHERE cs.specialisation_id = d.primary_specialisation_id AND c.depth = 0
	  ORDER BY cs.relevance DESC LIMIT 1
	) sector ON true
	LEFT JOIN LATERAL (
	  SELECT derivatives FROM developer_photos p
	  WHERE p.user_id = u.id AND p.is_current AND p.moderation_state = 'approved' LIMIT 1
	) ph ON true`

type scanner interface{ Scan(dest ...any) error }

func (s *Store) scanCard(row scanner) (*FreelancerCard, error) {
	var c FreelancerCard
	var photo map[string]map[string]string
	var specSlug, specName, specShort, sectorSlug *string
	var rate *int64
	var rateCurrency string
	var showRate, showLocation bool
	var city, country *string
	err := row.Scan(&c.UserID, &c.Username, &c.FullName, &photo,
		&c.ProfessionalTitle,
		&specSlug, &specName, &specShort,
		&sectorSlug,
		&c.RatingAvg, &c.RatingCount, &c.ProjectsCompleted,
		&rate, &rateCurrency, &showRate,
		&c.Availability,
		&showLocation, &city, &country,
		&c.IdentityVerified, &c.GitHubVerified,
		&c.IsFeatured, &c.LastSeenAt,
		&c.IsSaved)
	if err != nil {
		return nil, err
	}
	if specSlug != nil {
		c.Specialisation = &SpecialisationRef{Slug: *specSlug, Name: deref(specName), ShortName: deref(specShort)}
	}
	if sectorSlug != nil {
		c.SectorSlug = *sectorSlug
	}
	if showRate && rate != nil {
		c.HourlyRateMinor = rate
		c.RateCurrency = strings.TrimSpace(rateCurrency)
		c.RateDisplay = notifications.FormatMoney(*rate, c.RateCurrency) + "/ч"
	}
	if showLocation {
		parts := []string{}
		if city != nil && *city != "" {
			parts = append(parts, *city)
		}
		if country != nil && *country != "" {
			parts = append(parts, strings.ToUpper(*country))
		}
		c.Location = strings.Join(parts, ", ")
	}
	if s.publicURL != nil {
		for _, format := range []string{"webp", "jpeg"} {
			if key, ok := photo[format]["128"]; ok && key != "" {
				c.PhotoURL = s.publicURL(key)
				break
			}
			if key, ok := photo[format]["64"]; ok && key != "" {
				c.PhotoURL = s.publicURL(key)
				break
			}
		}
	}
	c.Skills = []SkillRef{}
	return &c, nil
}

// skillsFor attaches the top skills to a batch of cards in one query rather
// than one per card.
func (s *Store) skillsFor(ctx context.Context, cards []FreelancerCard) error {
	if len(cards) == 0 {
		return nil
	}
	ids := make([]uuid.UUID, len(cards))
	index := map[uuid.UUID]int{}
	for i, c := range cards {
		ids[i] = c.UserID
		index[c.UserID] = i
	}
	rows, err := s.db.Query(ctx, `
		SELECT ds.user_id, k.slug, k.name, coalesce(k.colour, ''),
		       'github' = ANY(ds.evidence) OR 'contract' = ANY(ds.evidence)
		FROM developer_skills ds
		JOIN skills k ON k.id = ds.skill_id
		WHERE ds.user_id = ANY($1)
		ORDER BY ds.user_id, ds.is_primary DESC, ds.sort_order, k.name`, ids)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var userID uuid.UUID
		var sk SkillRef
		if err := rows.Scan(&userID, &sk.Slug, &sk.Name, &sk.Colour, &sk.Verified); err != nil {
			return err
		}
		i := index[userID]
		if len(cards[i].Skills) < 6 {
			cards[i].Skills = append(cards[i].Skills, sk)
		}
	}
	return rows.Err()
}

// Freelancers runs the catalogue query.
func (s *Store) Freelancers(ctx context.Context, q FreelancerQuery) ([]FreelancerCard, int, error) {
	args := []any{q.ViewerID}
	arg := func(v any) string {
		args = append(args, v)
		return fmt.Sprintf("$%d", len(args))
	}
	where := []string{visibleFreelancers}

	if q.Sector != "" {
		where = append(where, fmt.Sprintf(`EXISTS (
			SELECT 1 FROM category_specialisations cs
			JOIN categories c ON c.id = cs.category_id
			WHERE c.slug = %s AND c.depth = 0
			  AND cs.specialisation_id IN (
			    SELECT d.primary_specialisation_id
			    UNION SELECT specialisation_id FROM developer_specialisations x WHERE x.user_id = u.id))`,
			arg(q.Sector)))
	}
	if q.Specialisation != "" {
		where = append(where, fmt.Sprintf(`(sp.slug = %[1]s OR EXISTS (
			SELECT 1 FROM developer_specialisations x JOIN specialisations y ON y.id = x.specialisation_id
			WHERE x.user_id = u.id AND y.slug = %[1]s))`, arg(q.Specialisation)))
	}
	if len(q.Skills) > 0 {
		p := arg(q.Skills)
		where = append(where, fmt.Sprintf(`(
			SELECT count(DISTINCT k.slug) FROM developer_skills ds JOIN skills k ON k.id = ds.skill_id
			WHERE ds.user_id = u.id AND k.slug = ANY(%[1]s)) = cardinality(%[1]s::text[])`, p))
	}
	if q.Text != "" {
		p := arg(q.Text)
		where = append(where, fmt.Sprintf(`(
			u.full_name ILIKE '%%' || %[1]s || '%%'
			OR u.username ILIKE '%%' || %[1]s || '%%'
			OR d.professional_title ILIKE '%%' || %[1]s || '%%'
			OR sp.name ILIKE '%%' || %[1]s || '%%'
			OR EXISTS (SELECT 1 FROM developer_skills ds JOIN skills k ON k.id = ds.skill_id
			           WHERE ds.user_id = u.id AND k.name ILIKE '%%' || %[1]s || '%%'))`, p))
	}
	if q.MinRateMinor != nil {
		where = append(where, "d.show_hourly_rate AND d.hourly_rate_minor >= "+arg(*q.MinRateMinor))
	}
	if q.MaxRateMinor != nil {
		where = append(where, "d.show_hourly_rate AND d.hourly_rate_minor <= "+arg(*q.MaxRateMinor))
	}
	if q.Availability != "" {
		where = append(where, "d.availability = "+arg(q.Availability))
	}
	if q.Verified {
		where = append(where, "u.identity_verified_at IS NOT NULL")
	}

	order := "d.is_featured DESC, d.rating_avg DESC NULLS LAST, d.projects_completed DESC, u.last_seen_at DESC NULLS LAST"
	switch q.Sort {
	case "rating":
		order = "d.rating_avg DESC NULLS LAST, d.rating_count DESC, d.projects_completed DESC"
	case "rate_asc":
		order = "d.show_hourly_rate DESC, d.hourly_rate_minor ASC NULLS LAST"
	case "rate_desc":
		order = "d.show_hourly_rate DESC, d.hourly_rate_minor DESC NULLS LAST"
	case "newest":
		order = "d.onboarding_completed_at DESC"
	case "active":
		order = "u.last_seen_at DESC NULLS LAST"
	}

	limit := q.Limit
	if limit <= 0 || limit > 48 {
		limit = 24
	}
	offset := q.Offset
	if offset < 0 || offset > 960 {
		offset = 0
	}
	clause := strings.Join(where, " AND ")

	// The count shares the argument list with the page query, whose first
	// argument is the viewer; the count does not read it, and pgx refuses an
	// argument no placeholder names, so the viewer is referenced in a
	// predicate that is always true.
	var total int
	if err := s.db.QueryRow(ctx, "SELECT count(*)"+cardJoins+
		" WHERE ($1::uuid IS NULL OR $1::uuid IS NOT NULL) AND "+clause, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count freelancers: %w", err)
	}
	rows, err := s.db.Query(ctx, "SELECT "+cardColumns+cardJoins+" WHERE "+clause+
		" ORDER BY "+order+fmt.Sprintf(" LIMIT %d OFFSET %d", limit, offset), args...)
	if err != nil {
		return nil, 0, fmt.Errorf("list freelancers: %w", err)
	}
	defer rows.Close()
	cards := []FreelancerCard{}
	for rows.Next() {
		c, err := s.scanCard(rows)
		if err != nil {
			return nil, 0, err
		}
		cards = append(cards, *c)
	}
	if err := rows.Err(); err != nil {
		return nil, 0, err
	}
	if err := s.skillsFor(ctx, cards); err != nil {
		return nil, 0, err
	}
	return cards, total, nil
}

// ── Favourites ──────────────────────────────────────────────────────────────

func (s *Store) userIDByUsername(ctx context.Context, username string) (uuid.UUID, error) {
	var id uuid.UUID
	err := s.db.QueryRow(ctx,
		`SELECT id FROM users WHERE username = lower(btrim($1)) AND deleted_at IS NULL`, username).Scan(&id)
	if database.IsNoRows(err) {
		return uuid.Nil, ErrNotFound
	}
	return id, err
}

func (s *Store) SaveFreelancer(ctx context.Context, clientID, developerID uuid.UUID, note string) error {
	_, err := s.db.Exec(ctx, `
		INSERT INTO saved_developers (client_id, developer_id, note)
		VALUES ($1, $2, nullif($3, ''))
		ON CONFLICT (client_id, developer_id) DO UPDATE SET note = EXCLUDED.note`,
		clientID, developerID, note)
	return err
}

func (s *Store) UnsaveFreelancer(ctx context.Context, clientID, developerID uuid.UUID) error {
	_, err := s.db.Exec(ctx,
		`DELETE FROM saved_developers WHERE client_id = $1 AND developer_id = $2`, clientID, developerID)
	return err
}

func (s *Store) SavedFreelancers(ctx context.Context, clientID uuid.UUID) ([]SavedFreelancer, error) {
	rows, err := s.db.Query(ctx, "SELECT "+cardColumns+`, coalesce(sd.note, ''), sd.created_at`+cardJoins+`
		JOIN saved_developers sd ON sd.developer_id = u.id AND sd.client_id = $1
		WHERE u.deleted_at IS NULL
		ORDER BY sd.created_at DESC`, clientID)
	if err != nil {
		return nil, fmt.Errorf("list saved freelancers: %w", err)
	}
	defer rows.Close()
	out := []SavedFreelancer{}
	for rows.Next() {
		// The card scanner reads the shared columns; the two extra ones ride
		// behind them, so scan through an adapter that hands them over.
		var saved SavedFreelancer
		var photo map[string]map[string]string
		var specSlug, specName, specShort, sectorSlug *string
		var rate *int64
		var rateCurrency string
		var showRate, showLocation bool
		var city, country *string
		c := &saved.FreelancerCard
		if err := rows.Scan(&c.UserID, &c.Username, &c.FullName, &photo,
			&c.ProfessionalTitle, &specSlug, &specName, &specShort, &sectorSlug,
			&c.RatingAvg, &c.RatingCount, &c.ProjectsCompleted,
			&rate, &rateCurrency, &showRate, &c.Availability,
			&showLocation, &city, &country,
			&c.IdentityVerified, &c.GitHubVerified, &c.IsFeatured, &c.LastSeenAt,
			&c.IsSaved, &c.Note, &saved.SavedAt); err != nil {
			return nil, err
		}
		if specSlug != nil {
			c.Specialisation = &SpecialisationRef{Slug: *specSlug, Name: deref(specName), ShortName: deref(specShort)}
		}
		if sectorSlug != nil {
			c.SectorSlug = *sectorSlug
		}
		if showRate && rate != nil {
			c.HourlyRateMinor = rate
			c.RateCurrency = strings.TrimSpace(rateCurrency)
			c.RateDisplay = notifications.FormatMoney(*rate, c.RateCurrency) + "/ч"
		}
		if showLocation && city != nil {
			c.Location = *city
		}
		if s.publicURL != nil {
			for _, format := range []string{"webp", "jpeg"} {
				if key, ok := photo[format]["64"]; ok && key != "" {
					c.PhotoURL = s.publicURL(key)
					break
				}
			}
		}
		c.Skills = []SkillRef{}
		out = append(out, saved)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	cards := make([]FreelancerCard, len(out))
	for i := range out {
		cards[i] = out[i].FreelancerCard
	}
	if err := s.skillsFor(ctx, cards); err != nil {
		return nil, err
	}
	for i := range out {
		out[i].Skills = cards[i].Skills
	}
	return out, nil
}

func (s *Store) SaveProject(ctx context.Context, developerID, projectID uuid.UUID) error {
	tag, err := s.db.Exec(ctx, `
		INSERT INTO saved_projects (developer_id, project_id)
		SELECT $1, p.id FROM projects p
		WHERE p.id = $2 AND p.status = 'open' AND p.visibility <> 'private'
		ON CONFLICT DO NOTHING`, developerID, projectID)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		var exists bool
		_ = s.db.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM saved_projects WHERE developer_id = $1 AND project_id = $2)`,
			developerID, projectID).Scan(&exists)
		if !exists {
			return ErrNotFound
		}
	}
	return nil
}

func (s *Store) UnsaveProject(ctx context.Context, developerID, projectID uuid.UUID) error {
	_, err := s.db.Exec(ctx,
		`DELETE FROM saved_projects WHERE developer_id = $1 AND project_id = $2`, developerID, projectID)
	return err
}

// ── Global search ───────────────────────────────────────────────────────────

func (s *Store) Projects(ctx context.Context, text string, limit int) ([]ProjectHit, int, error) {
	if limit <= 0 || limit > 20 {
		limit = 5
	}
	const where = `
		p.status = 'open' AND p.visibility = 'public' AND p.moderation_state = 'approved'
		AND (p.search_doc @@ websearch_to_tsquery('russian', $1)
		     OR p.search_doc @@ websearch_to_tsquery('simple', $1)
		     OR p.title ILIKE '%' || $1 || '%')`
	var total int
	if err := s.db.QueryRow(ctx, `SELECT count(*) FROM projects p WHERE `+where, text).Scan(&total); err != nil {
		return nil, 0, err
	}
	rows, err := s.db.Query(ctx, `
		SELECT p.id, p.slug, p.title, coalesce(p.summary, left(p.description, 160)),
		       c.name, c.slug, p.budget_type, p.budget_min_minor, p.budget_max_minor, p.currency,
		       p.proposals_count, p.published_at
		FROM projects p JOIN categories c ON c.id = p.category_id
		WHERE `+where+`
		ORDER BY ts_rank(p.search_doc, websearch_to_tsquery('russian', $1)) DESC, p.published_at DESC
		LIMIT $2`, text, limit)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	out := []ProjectHit{}
	for rows.Next() {
		var h ProjectHit
		var budgetType, currency string
		var minMinor, maxMinor *int64
		if err := rows.Scan(&h.ID, &h.Slug, &h.Title, &h.Excerpt, &h.CategoryName, &h.CategorySlug,
			&budgetType, &minMinor, &maxMinor, &currency, &h.Proposals, &h.PublishedAt); err != nil {
			return nil, 0, err
		}
		h.BudgetDisplay = budgetDisplay(budgetType, minMinor, maxMinor, strings.TrimSpace(currency))
		out = append(out, h)
	}
	return out, total, rows.Err()
}

func budgetDisplay(kind string, minMinor, maxMinor *int64, currency string) string {
	switch {
	case kind == "hourly" && maxMinor != nil:
		return "до " + notifications.FormatMoney(*maxMinor, currency) + "/ч"
	case kind == "hourly" && minMinor != nil:
		return "от " + notifications.FormatMoney(*minMinor, currency) + "/ч"
	case minMinor != nil && maxMinor != nil && *minMinor != *maxMinor:
		return notifications.FormatMoney(*minMinor, currency) + " – " + notifications.FormatMoney(*maxMinor, currency)
	case maxMinor != nil:
		return notifications.FormatMoney(*maxMinor, currency)
	case minMinor != nil:
		return "от " + notifications.FormatMoney(*minMinor, currency)
	}
	return "Бюджет обсуждается"
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}
