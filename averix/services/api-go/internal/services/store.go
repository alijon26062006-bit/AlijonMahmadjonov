package services

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/notifications"
	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/validate"
)

var ErrNotFound = errors.New("service not found")

type Store struct {
	db        *database.DB
	publicURL func(string) string
}

func NewStore(db *database.DB, publicURL func(string) string) *Store {
	return &Store{db: db, publicURL: publicURL}
}

// newService is the validated shape the service layer hands over.
type newService struct {
	DeveloperID  uuid.UUID
	Title        string
	Summary      string
	Description  string
	CategoryID   uuid.UUID
	CoverFileID  *uuid.UUID
	Currency     string
	Revisions    int
	Tiers        []TierInput
	SkillIDs     []uuid.UUID
	PortfolioIDs []uuid.UUID
}

func fromTiers(tiers []TierInput) (fromMinor int64, deliveryDays int) {
	if len(tiers) == 0 {
		return 0, 0
	}
	return tiers[0].PriceMinor, tiers[0].DeliveryDays
}

// Create writes the service and its tiers, skills and portfolio links in one
// transaction. The slug is unique per freelancer, so two people can both
// sell "Логотип за день" without either being renamed.
func (s *Store) Create(ctx context.Context, in newService) (uuid.UUID, error) {
	fromMinor, delivery := fromTiers(in.Tiers)
	var id uuid.UUID
	err := s.db.InTx(ctx, func(q database.Querier) error {
		slug, err := s.uniqueSlug(ctx, q, in.DeveloperID, in.Title)
		if err != nil {
			return err
		}
		if err := q.QueryRow(ctx, `
			INSERT INTO services
			  (developer_id, slug, title, summary, description, category_id, cover_file_id,
			   from_minor, currency, delivery_days, revisions, status)
			VALUES ($1,$2,$3,nullif($4,''),$5,$6,$7,$8,$9,$10,$11,'draft')
			RETURNING id`,
			in.DeveloperID, slug, in.Title, in.Summary, in.Description, in.CategoryID, in.CoverFileID,
			fromMinor, in.Currency, delivery, in.Revisions).Scan(&id); err != nil {
			return fmt.Errorf("insert service: %w", err)
		}
		return s.writeChildren(ctx, q, id, in.DeveloperID, in)
	})
	return id, err
}

// Update replaces every editable field. Partial updates would let a stale
// editor silently keep an old tier list next to a new description.
func (s *Store) Update(ctx context.Context, id uuid.UUID, in newService) error {
	fromMinor, delivery := fromTiers(in.Tiers)
	return s.db.InTx(ctx, func(q database.Querier) error {
		tag, err := q.Exec(ctx, `
			UPDATE services
			SET title = $2, summary = nullif($3, ''), description = $4, category_id = $5,
			    cover_file_id = $6, from_minor = $7, currency = $8, delivery_days = $9,
			    revisions = $10, updated_at = now()
			WHERE id = $1 AND developer_id = $11`,
			id, in.Title, in.Summary, in.Description, in.CategoryID, in.CoverFileID,
			fromMinor, in.Currency, delivery, in.Revisions, in.DeveloperID)
		if err != nil {
			return fmt.Errorf("update service: %w", err)
		}
		if tag.RowsAffected() == 0 {
			return ErrNotFound
		}
		for _, table := range []string{"service_tiers", "service_skills", "service_portfolio_links"} {
			if _, err := q.Exec(ctx, `DELETE FROM `+table+` WHERE service_id = $1`, id); err != nil {
				return err
			}
		}
		return s.writeChildren(ctx, q, id, in.DeveloperID, in)
	})
}

func (s *Store) writeChildren(ctx context.Context, q database.Querier, id, ownerID uuid.UUID, in newService) error {
	for i, tier := range in.Tiers {
		if _, err := q.Exec(ctx, `
			INSERT INTO service_tiers (service_id, position, name, price_minor, delivery_days, revisions, includes)
			VALUES ($1,$2,$3,$4,$5,$6,$7)`,
			id, i+1, tier.Name, tier.PriceMinor, tier.DeliveryDays, tier.Revisions,
			database.Array(tier.Includes)); err != nil {
			return fmt.Errorf("insert tier: %w", err)
		}
	}
	for _, skillID := range in.SkillIDs {
		if _, err := q.Exec(ctx, `
			INSERT INTO service_skills (service_id, skill_id) VALUES ($1, $2)
			ON CONFLICT DO NOTHING`, id, skillID); err != nil {
			return fmt.Errorf("insert skill: %w", err)
		}
	}
	// Only the freelancer's own portfolio may be attached: the join to the
	// owner is in the INSERT, so a foreign id inserts nothing.
	for i, portfolioID := range in.PortfolioIDs {
		if _, err := q.Exec(ctx, `
			INSERT INTO service_portfolio_links (service_id, portfolio_project_id, sort_order)
			SELECT $1, p.id, $3 FROM portfolio_projects p
			WHERE p.id = $2 AND p.developer_id = $4
			ON CONFLICT DO NOTHING`, id, portfolioID, (i+1)*10, ownerID); err != nil {
			return fmt.Errorf("link portfolio: %w", err)
		}
	}
	return nil
}

func (s *Store) uniqueSlug(ctx context.Context, q database.Querier, ownerID uuid.UUID, title string) (string, error) {
	base := validate.Slugify(title)
	if base == "" {
		base = "service"
	}
	if len(base) > 60 {
		base = base[:60]
	}
	slug := base
	for attempt := 2; attempt < 50; attempt++ {
		var exists bool
		if err := q.QueryRow(ctx,
			`SELECT EXISTS (SELECT 1 FROM services WHERE developer_id = $1 AND slug = $2)`,
			ownerID, slug).Scan(&exists); err != nil {
			return "", err
		}
		if !exists {
			return slug, nil
		}
		slug = fmt.Sprintf("%s-%d", base, attempt)
	}
	return "", fmt.Errorf("could not find a free slug for %q", title)
}

// SetStatus moves a service between draft, active, paused and archived.
// Publishing requires the moderation state to be clean; the WHERE says so.
func (s *Store) SetStatus(ctx context.Context, id, ownerID uuid.UUID, to string) error {
	tag, err := s.db.Exec(ctx, `
		UPDATE services SET status = $3, updated_at = now()
		WHERE id = $1 AND developer_id = $2
		  AND ($3 <> 'active' OR moderation_state IN ('approved', 'pending'))`, id, ownerID, to)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (s *Store) OwnerOf(ctx context.Context, id uuid.UUID) (uuid.UUID, string, error) {
	var owner uuid.UUID
	var status string
	err := s.db.QueryRow(ctx, `SELECT developer_id, status FROM services WHERE id = $1`, id).Scan(&owner, &status)
	if database.IsNoRows(err) {
		return uuid.Nil, "", ErrNotFound
	}
	return owner, status, err
}

func (s *Store) CountActive(ctx context.Context, ownerID uuid.UUID) (int, error) {
	var n int
	err := s.db.QueryRow(ctx,
		`SELECT count(*) FROM services WHERE developer_id = $1 AND status IN ('draft','active','paused')`,
		ownerID).Scan(&n)
	return n, err
}

// ── Reads ───────────────────────────────────────────────────────────────────

const cardColumns = `
	s.id, s.slug, s.title, coalesce(s.summary, ''), s.status,
	c.slug, c.name, c.path,
	f.storage_key, f.access,
	s.from_minor, s.currency, s.delivery_days, s.orders_count, s.rating_avg, s.rating_count,
	s.created_at,
	u.id, u.username, u.full_name, ph.derivatives,
	coalesce(dp.professional_title, ''), dp.rating_avg, dp.rating_count, dp.projects_completed,
	dp.availability`

const cardJoins = `
	FROM services s
	JOIN categories c ON c.id = s.category_id
	JOIN users u ON u.id = s.developer_id
	JOIN developer_profiles dp ON dp.user_id = s.developer_id
	LEFT JOIN files f ON f.id = s.cover_file_id AND f.deleted_at IS NULL
	LEFT JOIN LATERAL (SELECT derivatives FROM developer_photos p
	                   WHERE p.user_id = u.id AND p.is_current AND p.moderation_state = 'approved' LIMIT 1) ph ON true`

type scanner interface{ Scan(dest ...any) error }

func (s *Store) scanCard(row scanner) (*Card, error) {
	var card Card
	var coverKey, coverAccess *string
	var photo map[string]map[string]string
	err := row.Scan(&card.ID, &card.Slug, &card.Title, &card.Summary, &card.Status,
		&card.Category.Slug, &card.Category.Name, &card.Category.Path,
		&coverKey, &coverAccess,
		&card.FromMinor, &card.Currency, &card.DeliveryDays, &card.OrdersCount, &card.RatingAvg, &card.RatingCount,
		&card.CreatedAt,
		&card.Seller.UserID, &card.Seller.Username, &card.Seller.FullName, &photo,
		&card.Seller.ProfessionalTitle, &card.Seller.RatingAvg, &card.Seller.RatingCount,
		&card.Seller.ProjectsCompleted, &card.Seller.Availability)
	if err != nil {
		return nil, err
	}
	card.Currency = strings.TrimSpace(card.Currency)
	card.FromDisplay = notifications.FormatMoney(card.FromMinor, card.Currency)
	if coverKey != nil && coverAccess != nil && *coverAccess == "public" && s.publicURL != nil {
		card.CoverURL = s.publicURL(*coverKey)
	}
	if s.publicURL != nil {
		for _, format := range []string{"webp", "jpeg"} {
			if key, ok := photo[format]["64"]; ok && key != "" {
				card.Seller.PhotoURL = s.publicURL(key)
				break
			}
		}
	}
	return &card, nil
}

// ByID loads the full service. Visibility is the service layer's decision.
func (s *Store) ByID(ctx context.Context, id uuid.UUID) (*Service, error) {
	row := s.db.QueryRow(ctx, `SELECT `+cardColumns+`,
		s.description, s.revisions, s.view_count, s.moderation_state, s.updated_at,
		s.developer_id`+cardJoins+` WHERE s.id = $1`, id)

	var out Service
	var coverKey, coverAccess *string
	var photo map[string]map[string]string
	var ownerID uuid.UUID
	err := row.Scan(&out.ID, &out.Slug, &out.Title, &out.Summary, &out.Status,
		&out.Category.Slug, &out.Category.Name, &out.Category.Path,
		&coverKey, &coverAccess,
		&out.FromMinor, &out.Currency, &out.DeliveryDays, &out.OrdersCount, &out.RatingAvg, &out.RatingCount,
		&out.CreatedAt,
		&out.Seller.UserID, &out.Seller.Username, &out.Seller.FullName, &photo,
		&out.Seller.ProfessionalTitle, &out.Seller.RatingAvg, &out.Seller.RatingCount,
		&out.Seller.ProjectsCompleted, &out.Seller.Availability,
		&out.Description, &out.Revisions, &out.ViewCount, &out.ModerationState, &out.UpdatedAt,
		&ownerID)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("load service: %w", err)
	}
	out.Currency = strings.TrimSpace(out.Currency)
	out.FromDisplay = notifications.FormatMoney(out.FromMinor, out.Currency)
	if coverKey != nil && coverAccess != nil && *coverAccess == "public" && s.publicURL != nil {
		out.CoverURL = s.publicURL(*coverKey)
	}
	if s.publicURL != nil {
		for _, format := range []string{"webp", "jpeg"} {
			if key, ok := photo[format]["64"]; ok && key != "" {
				out.Seller.PhotoURL = s.publicURL(key)
				break
			}
		}
	}

	tiers, err := s.db.Query(ctx, `
		SELECT id, position, name, price_minor, delivery_days, revisions, includes
		FROM service_tiers WHERE service_id = $1 ORDER BY position`, id)
	if err != nil {
		return nil, err
	}
	out.Tiers = []Tier{}
	for tiers.Next() {
		var t Tier
		if err := tiers.Scan(&t.ID, &t.Position, &t.Name, &t.PriceMinor, &t.DeliveryDays, &t.Revisions, &t.Includes); err != nil {
			tiers.Close()
			return nil, err
		}
		if t.Includes == nil {
			t.Includes = []string{}
		}
		t.PriceDisplay = notifications.FormatMoney(t.PriceMinor, out.Currency)
		out.Tiers = append(out.Tiers, t)
	}
	tiers.Close()

	skills, err := s.db.Query(ctx, `
		SELECT sk.slug, sk.name, coalesce(sk.colour, '')
		FROM service_skills ss JOIN skills sk ON sk.id = ss.skill_id
		WHERE ss.service_id = $1 ORDER BY sk.name`, id)
	if err != nil {
		return nil, err
	}
	out.Skills = []SkillRef{}
	for skills.Next() {
		var sk SkillRef
		if err := skills.Scan(&sk.Slug, &sk.Name, &sk.Colour); err != nil {
			skills.Close()
			return nil, err
		}
		out.Skills = append(out.Skills, sk)
	}
	skills.Close()

	links, err := s.db.Query(ctx, `
		SELECT portfolio_project_id FROM service_portfolio_links
		WHERE service_id = $1 ORDER BY sort_order`, id)
	if err != nil {
		return nil, err
	}
	out.PortfolioIDs = []uuid.UUID{}
	for links.Next() {
		var pid uuid.UUID
		if err := links.Scan(&pid); err != nil {
			links.Close()
			return nil, err
		}
		out.PortfolioIDs = append(out.PortfolioIDs, pid)
	}
	links.Close()
	return &out, nil
}

// Tier returns one price point, for an order.
func (s *Store) Tier(ctx context.Context, serviceID uuid.UUID, position int) (*Tier, error) {
	var t Tier
	err := s.db.QueryRow(ctx, `
		SELECT id, position, name, price_minor, delivery_days, revisions, includes
		FROM service_tiers WHERE service_id = $1 AND position = $2`, serviceID, position).
		Scan(&t.ID, &t.Position, &t.Name, &t.PriceMinor, &t.DeliveryDays, &t.Revisions, &t.Includes)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	return &t, err
}

// Catalogue is the public listing. Only live, approved services appear;
// the freelancer's own drafts are a different list.
func (s *Store) Catalogue(ctx context.Context, q Query) ([]Card, int, error) {
	where := []string{"s.status = 'active'", "s.moderation_state = 'approved'", "dp.is_searchable"}
	args := []any{}
	arg := func(v any) string {
		args = append(args, v)
		return fmt.Sprintf("$%d", len(args))
	}
	if q.CategorySlug != "" {
		where = append(where, fmt.Sprintf(
			`c.path LIKE (SELECT path || '%%' FROM categories WHERE slug = %s)`, arg(q.CategorySlug)))
	}
	textArg := ""
	if q.Text != "" {
		textArg = arg(q.Text)
		where = append(where, fmt.Sprintf(
			`(s.search_doc @@ websearch_to_tsquery('russian', %s)
			  OR s.search_doc @@ websearch_to_tsquery('simple', %s)
			  OR s.title ILIKE '%%' || %s || '%%')`, textArg, textArg, textArg))
	}
	if q.MinMinor != nil {
		where = append(where, "s.from_minor >= "+arg(*q.MinMinor))
	}
	if q.MaxMinor != nil {
		where = append(where, "s.from_minor <= "+arg(*q.MaxMinor))
	}
	if q.MaxDelivery != nil {
		where = append(where, "s.delivery_days <= "+arg(*q.MaxDelivery))
	}
	if q.Currency != "" {
		where = append(where, "s.currency = "+arg(q.Currency))
	}

	order := "s.created_at DESC"
	switch q.Sort {
	case "price_asc":
		order = "s.from_minor ASC, s.created_at DESC"
	case "price_desc":
		order = "s.from_minor DESC, s.created_at DESC"
	case "rating":
		order = "s.rating_avg DESC NULLS LAST, s.rating_count DESC, s.created_at DESC"
	case "popular":
		order = "s.orders_count DESC, s.rating_avg DESC NULLS LAST, s.created_at DESC"
	case "relevance":
		// Reuses the text placeholder: the count query below runs with the
		// same argument list and must reference every placeholder in it.
		if textArg != "" {
			order = fmt.Sprintf("ts_rank(s.search_doc, websearch_to_tsquery('russian', %s)) DESC, s.orders_count DESC",
				textArg)
		}
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
	var total int
	if err := s.db.QueryRow(ctx, `SELECT count(*)`+cardJoins+` WHERE `+clause, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count services: %w", err)
	}

	rows, err := s.db.Query(ctx, `SELECT `+cardColumns+cardJoins+` WHERE `+clause+
		` ORDER BY `+order+fmt.Sprintf(" LIMIT %d OFFSET %d", limit, offset), args...)
	if err != nil {
		return nil, 0, fmt.Errorf("list services: %w", err)
	}
	defer rows.Close()
	cards := []Card{}
	for rows.Next() {
		card, err := s.scanCard(rows)
		if err != nil {
			return nil, 0, err
		}
		cards = append(cards, *card)
	}
	return cards, total, rows.Err()
}

// ForSeller lists one freelancer's services: live ones for the public, all
// of them for the owner.
func (s *Store) ForSeller(ctx context.Context, sellerID uuid.UUID, includeAll bool) ([]Card, error) {
	rows, err := s.db.Query(ctx, `SELECT `+cardColumns+cardJoins+`
		WHERE s.developer_id = $1
		  AND ($2 OR (s.status = 'active' AND s.moderation_state = 'approved'))
		  AND s.status <> 'archived'
		ORDER BY s.status = 'active' DESC, s.updated_at DESC`, sellerID, includeAll)
	if err != nil {
		return nil, fmt.Errorf("list seller services: %w", err)
	}
	defer rows.Close()
	cards := []Card{}
	for rows.Next() {
		card, err := s.scanCard(rows)
		if err != nil {
			return nil, err
		}
		cards = append(cards, *card)
	}
	return cards, rows.Err()
}

func (s *Store) SellerIDByUsername(ctx context.Context, username string) (uuid.UUID, error) {
	var id uuid.UUID
	err := s.db.QueryRow(ctx, `SELECT id FROM users WHERE username = lower(btrim($1))`, username).Scan(&id)
	if database.IsNoRows(err) {
		return uuid.Nil, ErrNotFound
	}
	return id, err
}

func (s *Store) RecordView(ctx context.Context, id uuid.UUID) {
	_, _ = s.db.Exec(ctx, `UPDATE services SET view_count = view_count + 1 WHERE id = $1`, id)
}

func (s *Store) RecordOrder(ctx context.Context, id uuid.UUID) error {
	_, err := s.db.Exec(ctx, `UPDATE services SET orders_count = orders_count + 1, updated_at = now() WHERE id = $1`, id)
	return err
}

// MarkOrderProject moves the hidden project an order created straight to
// in_progress: it was never open for proposals and must never appear in a
// feed.
func (s *Store) MarkOrderProject(ctx context.Context, projectID, developerID uuid.UUID) error {
	_, err := s.db.Exec(ctx, `
		UPDATE projects
		SET status = 'in_progress', published_at = now(), hired_developer_id = $2, updated_at = now()
		WHERE id = $1`, projectID, developerID)
	return err
}

// OwnedFile confirms a cover image belongs to the caller and is an image.
func (s *Store) OwnedFile(ctx context.Context, fileID, ownerID uuid.UUID) (bool, error) {
	var ok bool
	err := s.db.QueryRow(ctx, `
		SELECT EXISTS (SELECT 1 FROM files
		               WHERE id = $1 AND owner_id = $2 AND deleted_at IS NULL
		                 AND detected_mime LIKE 'image/%')`, fileID, ownerID).Scan(&ok)
	return ok, err
}

func (s *Store) touch(ctx context.Context, id uuid.UUID, when time.Time) {
	_, _ = s.db.Exec(ctx, `UPDATE services SET updated_at = $2 WHERE id = $1`, id, when)
}
