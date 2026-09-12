package portfolio

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/database"
)

type Store struct {
	db        *database.DB
	publicURL func(string) string
}

func NewStore(db *database.DB, publicURL func(string) string) *Store {
	if publicURL == nil {
		publicURL = func(key string) string { return key }
	}
	return &Store{db: db, publicURL: publicURL}
}

var (
	ErrNotFound = errors.New("portfolio project not found")
	ErrTooMany  = errors.New("too many portfolio projects")
)

// MaxProjects is a product limit, not a storage one: a profile with fifty
// portfolio entries is less persuasive than one with eight good ones, and a
// client will not read past the first screen.
const MaxProjects = 24

type New struct {
	DeveloperID      uuid.UUID
	Title            string
	ShortDescription string
	Description      string
	CategoryID       *uuid.UUID
	DeveloperRole    string
	ProjectURL       string
	ProjectHost      string
	RepositoryURL    string
	CompletedOn      *time.Time
	DurationDays     *int
	ValueMinor       *int64
	Currency         string
	ValueVisibility  string
	DemoStatus       string
	SkillIDs         []uuid.UUID
	IsDemo           bool
}

func (s *Store) Create(ctx context.Context, in New) (uuid.UUID, error) {
	var count int
	if err := s.db.QueryRow(ctx,
		`SELECT count(*) FROM portfolio_projects WHERE developer_id = $1`,
		in.DeveloperID).Scan(&count); err != nil {
		return uuid.Nil, fmt.Errorf("count portfolio projects: %w", err)
	}
	if count >= MaxProjects {
		return uuid.Nil, ErrTooMany
	}

	slug, err := s.uniqueSlug(ctx, in.DeveloperID, in.Title)
	if err != nil {
		return uuid.Nil, err
	}

	var id uuid.UUID
	err = s.db.InTx(ctx, func(q database.Querier) error {
		err := q.QueryRow(ctx, `
			INSERT INTO portfolio_projects
			  (developer_id, slug, title, short_description, description, category_id,
			   developer_role, project_url, project_url_host, repository_url,
			   completed_on, duration_days, value_minor, currency, value_visibility,
			   demo_status, sort_order, is_demo)
			VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
			RETURNING id`,
			in.DeveloperID, slug, in.Title, nullIfBlank(in.ShortDescription),
			nullIfBlank(in.Description), in.CategoryID, nullIfBlank(in.DeveloperRole),
			nullIfBlank(in.ProjectURL), nullIfBlank(in.ProjectHost),
			nullIfBlank(in.RepositoryURL), in.CompletedOn, in.DurationDays,
			in.ValueMinor, defaultTo(in.Currency, "USD"), in.ValueVisibility,
			in.DemoStatus, count, in.IsDemo).Scan(&id)
		if err != nil {
			return fmt.Errorf("insert portfolio project: %w", err)
		}
		for _, skillID := range in.SkillIDs {
			if _, err := q.Exec(ctx,
				`INSERT INTO portfolio_skills (portfolio_project_id, skill_id)
				 VALUES ($1, $2) ON CONFLICT DO NOTHING`, id, skillID); err != nil {
				return fmt.Errorf("insert portfolio skill: %w", err)
			}
		}
		return nil
	})
	return id, err
}

func (s *Store) uniqueSlug(ctx context.Context, developerID uuid.UUID, title string) (string, error) {
	base := slugify(title)
	if base == "" {
		base = "project"
	}
	if len(base) > 60 {
		base = strings.Trim(base[:60], "-")
	}

	// The slug is per developer, so two developers may both have
	// /developers/x/portfolio/marketplace-api. A collision within one
	// developer's own portfolio gets a suffix.
	var taken bool
	if err := s.db.QueryRow(ctx,
		`SELECT EXISTS (SELECT 1 FROM portfolio_projects WHERE developer_id = $1 AND slug = $2)`,
		developerID, base).Scan(&taken); err != nil {
		return "", fmt.Errorf("check slug: %w", err)
	}
	if !taken {
		return base, nil
	}
	suffix, err := cryptox.RandomHex(2)
	if err != nil {
		return "", err
	}
	return base + "-" + suffix, nil
}

// ── Reads ───────────────────────────────────────────────────────────────────

const projectSelect = `
	SELECT pp.id, pp.developer_id, pp.slug, pp.title,
	       coalesce(pp.short_description, ''), coalesce(pp.description, ''),
	       c.slug, c.name, coalesce(pp.developer_role, ''),
	       coalesce(pp.project_url, ''), coalesce(pp.project_url_host, ''),
	       pp.embeddable, coalesce(pp.embeddable_reason, ''), pp.embeddable_checked_at,
	       coalesce(pp.repository_url, ''),
	       pp.completed_on, pp.duration_days,
	       pp.value_minor, pp.currency, pp.value_visibility,
	       pp.demo_status, pp.is_published, pp.is_featured, pp.sort_order,
	       pp.view_count, pp.moderation_state, coalesce(pp.moderation_note, ''),
	       pp.cover_file_id, pp.created_at, pp.updated_at
	FROM portfolio_projects pp
	LEFT JOIN categories c ON c.id = pp.category_id`

func (s *Store) scan(row interface{ Scan(...any) error }) (*Project, *uuid.UUID, error) {
	var p Project
	var categorySlug, categoryName *string
	var coverFileID *uuid.UUID

	err := row.Scan(&p.ID, &p.DeveloperID, &p.Slug, &p.Title,
		&p.ShortDescription, &p.Description,
		&categorySlug, &categoryName, &p.DeveloperRole,
		&p.ProjectURL, &p.ProjectHost,
		&p.Embeddable, &p.EmbeddableReason, &p.EmbeddableCheckedAt,
		&p.RepositoryURL,
		&p.CompletedOn, &p.DurationDays,
		&p.ValueMinor, &p.Currency, &p.ValueVisibility,
		&p.DemoStatus, &p.IsPublished, &p.IsFeatured, &p.SortOrder,
		&p.ViewCount, &p.ModerationState, &p.ModerationNote,
		&coverFileID, &p.CreatedAt, &p.UpdatedAt)
	if database.IsNoRows(err) {
		return nil, nil, ErrNotFound
	}
	if err != nil {
		return nil, nil, fmt.Errorf("scan portfolio project: %w", err)
	}
	if categorySlug != nil {
		p.Category = &CategoryRef{Slug: *categorySlug, Name: deref(categoryName)}
	}
	p.Kind = KindPortfolio
	return &p, coverFileID, nil
}

func (s *Store) ByID(ctx context.Context, id uuid.UUID) (*Project, error) {
	project, coverID, err := s.scan(s.db.QueryRow(ctx, projectSelect+" WHERE pp.id = $1", id))
	if err != nil {
		return nil, err
	}
	return s.hydrate(ctx, project, coverID)
}

// BySlug resolves the public URL form: a developer's username and the
// project's own slug.
func (s *Store) BySlug(ctx context.Context, username, slug string) (*Project, error) {
	project, coverID, err := s.scan(s.db.QueryRow(ctx, projectSelect+`
		JOIN users u ON u.id = pp.developer_id
		WHERE u.username = $1 AND pp.slug = $2 AND u.deleted_at IS NULL`,
		strings.ToLower(username), slug))
	if err != nil {
		return nil, err
	}
	return s.hydrate(ctx, project, coverID)
}

func (s *Store) hydrate(ctx context.Context, p *Project, coverFileID *uuid.UUID) (*Project, error) {
	images, err := s.images(ctx, p.ID)
	if err != nil {
		return nil, err
	}
	p.Images = images

	// The cover is the explicitly chosen file, or the first gallery image.
	// That is what makes "the first image becomes the cover" true without a
	// second field to keep in sync.
	if coverFileID != nil {
		for i := range images {
			if images[i].FileID == *coverFileID {
				cover := images[i]
				p.Cover = &cover
				break
			}
		}
	}
	if p.Cover == nil && len(images) > 0 {
		cover := images[0]
		p.Cover = &cover
	}

	if p.Skills, err = s.skills(ctx, p.ID); err != nil {
		return nil, err
	}
	if p.Links, err = s.links(ctx, p.ID); err != nil {
		return nil, err
	}
	return p, nil
}

func (s *Store) images(ctx context.Context, projectID uuid.UUID) ([]Image, error) {
	rows, err := s.db.Query(ctx, `
		SELECT pi.id, pi.file_id, f.storage_key, coalesce(pi.caption, ''),
		       coalesce(pi.alt_text, ''), pi.position, f.width, f.height,
		       coalesce(pi.placeholder, ''), pi.derivatives
		FROM portfolio_images pi
		JOIN files f ON f.id = pi.file_id AND f.deleted_at IS NULL
		WHERE pi.portfolio_project_id = $1
		ORDER BY pi.position`, projectID)
	if err != nil {
		return nil, fmt.Errorf("query portfolio images: %w", err)
	}
	defer rows.Close()

	out := []Image{}
	for rows.Next() {
		var img Image
		var key string
		var derivatives map[string]map[string]string
		if err := rows.Scan(&img.ID, &img.FileID, &key, &img.Caption,
			&img.AltText, &img.Position, &img.Width, &img.Height,
			&img.Placeholder, &derivatives); err != nil {
			return nil, err
		}
		img.URL = s.publicURL(key)
		img.Variants = s.variants(derivatives)
		out = append(out, img)
	}
	return out, rows.Err()
}

// variants flattens the stored {format: {width: key}} map into the ordered
// list a gallery renders as a srcset. WebP first so a browser that supports
// it never downloads the JPEG.
func (s *Store) variants(derivatives map[string]map[string]string) []Variant {
	if len(derivatives) == 0 {
		return nil
	}
	var out []Variant
	for _, format := range []string{"webp", "jpeg"} {
		widths := derivatives[format]
		if len(widths) == 0 {
			continue
		}
		keys := make([]string, 0, len(widths))
		for width := range widths {
			keys = append(keys, width)
		}
		sort.Slice(keys, func(i, j int) bool { return atoi(keys[i]) < atoi(keys[j]) })
		for _, width := range keys {
			out = append(out, Variant{
				Format: format,
				Width:  atoi(width),
				URL:    s.publicURL(widths[width]),
			})
		}
	}
	return out
}

// DerivativeKeys returns every stored object belonging to one image, which is
// what a delete has to remove. Keys, not URLs: a URL cannot be deleted.
func (s *Store) DerivativeKeys(ctx context.Context, imageID uuid.UUID) ([]string, error) {
	var derivatives map[string]map[string]string
	err := s.db.QueryRow(ctx,
		`SELECT derivatives FROM portfolio_images WHERE id = $1`, imageID).Scan(&derivatives)
	if database.IsNoRows(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var keys []string
	for _, widths := range derivatives {
		for _, key := range widths {
			keys = append(keys, key)
		}
	}
	return keys, nil
}

func (s *Store) skills(ctx context.Context, projectID uuid.UUID) ([]SkillRef, error) {
	rows, err := s.db.Query(ctx, `
		SELECT sk.slug, sk.name, coalesce(sk.colour, '')
		FROM portfolio_skills ps JOIN skills sk ON sk.id = ps.skill_id
		WHERE ps.portfolio_project_id = $1 AND sk.is_active
		ORDER BY sk.name`, projectID)
	if err != nil {
		return nil, fmt.Errorf("query portfolio skills: %w", err)
	}
	defer rows.Close()

	out := []SkillRef{}
	for rows.Next() {
		var sk SkillRef
		if err := rows.Scan(&sk.Slug, &sk.Name, &sk.Colour); err != nil {
			return nil, err
		}
		out = append(out, sk)
	}
	return out, rows.Err()
}

func (s *Store) links(ctx context.Context, projectID uuid.UUID) ([]Link, error) {
	rows, err := s.db.Query(ctx, `
		SELECT id, label, url, url_host, kind FROM portfolio_links
		WHERE portfolio_project_id = $1 ORDER BY sort_order, label`, projectID)
	if err != nil {
		return nil, fmt.Errorf("query portfolio links: %w", err)
	}
	defer rows.Close()

	out := []Link{}
	for rows.Next() {
		var l Link
		if err := rows.Scan(&l.ID, &l.Label, &l.URL, &l.Host, &l.Kind); err != nil {
			return nil, err
		}
		out = append(out, l)
	}
	return out, rows.Err()
}

// ForDeveloper lists a developer's portfolio.
//
// includeUnpublished is true only for the owner and for staff, so a draft
// entry is invisible to a visitor.
func (s *Store) ForDeveloper(ctx context.Context, developerID uuid.UUID, includeUnpublished bool) ([]Card, error) {
	condition := " AND pp.is_published AND pp.moderation_state = 'approved'"
	if includeUnpublished {
		condition = ""
	}

	rows, err := s.db.Query(ctx, `
		SELECT pp.id, pp.slug, pp.title, coalesce(pp.short_description, ''),
		       coalesce(pp.project_url_host, ''), pp.embeddable, pp.demo_status,
		       pp.completed_on, pp.value_minor, pp.currency, pp.value_visibility,
		       pp.is_featured, pp.is_published,
		       coalesce(
		         (SELECT f.storage_key FROM portfolio_images pi
		          JOIN files f ON f.id = pi.file_id AND f.deleted_at IS NULL
		          WHERE pi.portfolio_project_id = pp.id
		          ORDER BY (pi.file_id = pp.cover_file_id) DESC, pi.position
		          LIMIT 1), ''),
		       coalesce(
		         (SELECT coalesce(pi.placeholder, '') FROM portfolio_images pi
		          WHERE pi.portfolio_project_id = pp.id
		          ORDER BY (pi.file_id = pp.cover_file_id) DESC, pi.position
		          LIMIT 1), '')
		FROM portfolio_projects pp
		WHERE pp.developer_id = $1`+condition+`
		ORDER BY pp.is_featured DESC, pp.sort_order, pp.created_at DESC`, developerID)
	if err != nil {
		return nil, fmt.Errorf("query portfolio cards: %w", err)
	}
	defer rows.Close()

	cards := []Card{}
	ids := []uuid.UUID{}
	for rows.Next() {
		var c Card
		var embeddable, visibility, currency, coverKey, placeholder string
		var valueMinor *int64
		var published bool

		if err := rows.Scan(&c.ID, &c.Slug, &c.Title, &c.Excerpt,
			&c.ProjectHost, &embeddable, &c.DemoStatus, &c.CompletedOn,
			&valueMinor, &currency, &visibility, &c.IsFeatured, &published,
			&coverKey, &placeholder); err != nil {
			return nil, fmt.Errorf("scan portfolio card: %w", err)
		}

		c.Kind = KindPortfolio
		// The live-preview button is offered only when there is a URL and the
		// probe did not refuse it. Offering it for a blocked site would put a
		// dead button on the card.
		c.CanPreview = c.ProjectHost != "" && embeddable != "blocked"
		if valueMinor != nil {
			c.ValueDisplay = FormatVisibleValue(*valueMinor, currency, visibility)
		}
		if coverKey != "" {
			c.Cover = &Image{URL: s.publicURL(coverKey), Placeholder: placeholder}
		}
		cards = append(cards, c)
		ids = append(ids, c.ID)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	// The technologies for every card in one query rather than one per card.
	if len(ids) > 0 {
		skillRows, err := s.db.Query(ctx, `
			SELECT ps.portfolio_project_id, sk.slug, sk.name, coalesce(sk.colour, '')
			FROM portfolio_skills ps
			JOIN skills sk ON sk.id = ps.skill_id
			WHERE ps.portfolio_project_id = ANY($1) AND sk.is_active
			ORDER BY sk.name`, ids)
		if err != nil {
			return nil, fmt.Errorf("query card skills: %w", err)
		}
		byProject := map[uuid.UUID][]SkillRef{}
		for skillRows.Next() {
			var projectID uuid.UUID
			var sk SkillRef
			if err := skillRows.Scan(&projectID, &sk.Slug, &sk.Name, &sk.Colour); err != nil {
				skillRows.Close()
				return nil, err
			}
			byProject[projectID] = append(byProject[projectID], sk)
		}
		skillRows.Close()

		for i := range cards {
			skills := byProject[cards[i].ID]
			// Four tags is what fits on a card at 375px.
			if len(skills) > 4 {
				skills = skills[:4]
			}
			cards[i].Skills = skills
		}
	}
	return cards, nil
}

// ── Writes ──────────────────────────────────────────────────────────────────

type Update struct {
	Title            *string
	ShortDescription *string
	Description      *string
	CategoryID       *uuid.UUID
	DeveloperRole    *string
	ProjectURL       *string
	ProjectHost      *string
	RepositoryURL    *string
	CompletedOn      *time.Time
	DurationDays     *int
	ValueMinor       *int64
	Currency         *string
	ValueVisibility  *string
	DemoStatus       *string
	IsPublished      *bool
	IsFeatured       *bool
	CoverFileID      *uuid.UUID
	SkillIDs         []uuid.UUID
	ReplaceSkills    bool
	// Set when the URL changed, so the stored probe verdict is cleared.
	ResetEmbeddable bool
}

func (s *Store) Update(ctx context.Context, projectID, developerID uuid.UUID, in Update) error {
	return s.db.InTx(ctx, func(q database.Querier) error {
		embeddableReset := ""
		if in.ResetEmbeddable {
			// A changed URL invalidates the verdict: the old answer describes
			// a different site.
			embeddableReset = `, embeddable = 'unknown', embeddable_reason = NULL,
			                    embeddable_checked_at = NULL`
		}

		tag, err := q.Exec(ctx, `
			UPDATE portfolio_projects SET
			  title             = coalesce($3, title),
			  short_description = coalesce($4, short_description),
			  description       = coalesce($5, description),
			  category_id       = coalesce($6, category_id),
			  developer_role    = coalesce($7, developer_role),
			  project_url       = coalesce($8, project_url),
			  project_url_host  = coalesce($9, project_url_host),
			  repository_url    = coalesce($10, repository_url),
			  completed_on      = coalesce($11, completed_on),
			  duration_days     = coalesce($12, duration_days),
			  value_minor       = coalesce($13, value_minor),
			  currency          = coalesce($14, currency),
			  value_visibility  = coalesce($15, value_visibility),
			  demo_status       = coalesce($16, demo_status),
			  is_published      = coalesce($17, is_published),
			  is_featured       = coalesce($18, is_featured),
			  cover_file_id     = coalesce($19, cover_file_id),
			  updated_at        = now()`+embeddableReset+`
			WHERE id = $1 AND developer_id = $2`,
			projectID, developerID, in.Title, in.ShortDescription, in.Description,
			in.CategoryID, in.DeveloperRole, in.ProjectURL, in.ProjectHost,
			in.RepositoryURL, in.CompletedOn, in.DurationDays, in.ValueMinor,
			in.Currency, in.ValueVisibility, in.DemoStatus, in.IsPublished,
			in.IsFeatured, in.CoverFileID)
		if err != nil {
			return fmt.Errorf("update portfolio project: %w", err)
		}
		// Scoping the write to the owner means a wrong id affects nothing,
		// and the zero row count is how the caller learns that.
		if tag.RowsAffected() == 0 {
			return ErrNotFound
		}

		if in.ReplaceSkills {
			if _, err := q.Exec(ctx,
				`DELETE FROM portfolio_skills WHERE portfolio_project_id = $1`, projectID); err != nil {
				return fmt.Errorf("clear portfolio skills: %w", err)
			}
			for _, skillID := range in.SkillIDs {
				if _, err := q.Exec(ctx,
					`INSERT INTO portfolio_skills (portfolio_project_id, skill_id)
					 VALUES ($1, $2) ON CONFLICT DO NOTHING`, projectID, skillID); err != nil {
					return fmt.Errorf("insert portfolio skill: %w", err)
				}
			}
		}
		return nil
	})
}

func (s *Store) Delete(ctx context.Context, projectID, developerID uuid.UUID) error {
	tag, err := s.db.Exec(ctx,
		`DELETE FROM portfolio_projects WHERE id = $1 AND developer_id = $2`,
		projectID, developerID)
	if err != nil {
		return fmt.Errorf("delete portfolio project: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

// Reorder sets the display order from a list of ids.
//
// The ids are filtered to the developer's own in one statement, so a foreign
// id in the list is ignored rather than reordering someone else's portfolio.
func (s *Store) Reorder(ctx context.Context, developerID uuid.UUID, ordered []uuid.UUID) error {
	return s.db.InTx(ctx, func(q database.Querier) error {
		for position, id := range ordered {
			if _, err := q.Exec(ctx,
				`UPDATE portfolio_projects SET sort_order = $3, updated_at = now()
				 WHERE id = $1 AND developer_id = $2`, id, developerID, position); err != nil {
				return fmt.Errorf("reorder portfolio: %w", err)
			}
		}
		return nil
	})
}

// ── Images ──────────────────────────────────────────────────────────────────

// AddImage appends a gallery image. The first one added becomes the cover by
// virtue of being at position zero.
func (s *Store) AddImage(ctx context.Context, projectID, developerID, fileID uuid.UUID,
	caption, altText, placeholder string, derivatives map[string]map[string]string) (uuid.UUID, error) {

	if derivatives == nil {
		derivatives = map[string]map[string]string{}
	}

	var imageID uuid.UUID
	err := s.db.InTx(ctx, func(q database.Querier) error {
		// Ownership of the project is re-checked here rather than trusted
		// from the caller.
		var owner uuid.UUID
		if err := q.QueryRow(ctx,
			`SELECT developer_id FROM portfolio_projects WHERE id = $1`, projectID).Scan(&owner); err != nil {
			if database.IsNoRows(err) {
				return ErrNotFound
			}
			return err
		}
		if owner != developerID {
			return ErrNotFound
		}

		var next int
		if err := q.QueryRow(ctx,
			`SELECT coalesce(max(position) + 1, 0) FROM portfolio_images
			 WHERE portfolio_project_id = $1`, projectID).Scan(&next); err != nil {
			return fmt.Errorf("find next image position: %w", err)
		}

		err := q.QueryRow(ctx, `
			INSERT INTO portfolio_images
			  (portfolio_project_id, file_id, caption, alt_text, position,
			   placeholder, derivatives)
			VALUES ($1, $2, $3, $4, $5, $6, $7)
			RETURNING id`,
			projectID, fileID, nullIfBlank(caption), nullIfBlank(altText),
			next, nullIfBlank(placeholder), derivatives).Scan(&imageID)
		if err != nil {
			return fmt.Errorf("insert portfolio image: %w", err)
		}
		return nil
	})
	return imageID, err
}

// CountImages counts a project's gallery, and doubles as the ownership check
// before an upload is accepted: a project that is not the caller's reports
// not-found rather than a count.
func (s *Store) CountImages(ctx context.Context, projectID, developerID uuid.UUID) (int, error) {
	var count int
	err := s.db.QueryRow(ctx, `
		SELECT (SELECT count(*) FROM portfolio_images pi
		        WHERE pi.portfolio_project_id = pp.id)
		FROM portfolio_projects pp
		WHERE pp.id = $1 AND pp.developer_id = $2`, projectID, developerID).Scan(&count)
	if database.IsNoRows(err) {
		return 0, ErrNotFound
	}
	if err != nil {
		return 0, fmt.Errorf("count portfolio images: %w", err)
	}
	return count, nil
}

// ReorderImages sets the gallery order, which is what the drag-and-drop
// editor saves.
//
// Positions are written in two passes because of the unique index on
// (project, position): shifting everything to a negative range first means an
// intermediate state never collides.
func (s *Store) ReorderImages(ctx context.Context, projectID, developerID uuid.UUID, ordered []uuid.UUID) error {
	return s.db.InTx(ctx, func(q database.Querier) error {
		var owner uuid.UUID
		if err := q.QueryRow(ctx,
			`SELECT developer_id FROM portfolio_projects WHERE id = $1`, projectID).Scan(&owner); err != nil {
			if database.IsNoRows(err) {
				return ErrNotFound
			}
			return err
		}
		if owner != developerID {
			return ErrNotFound
		}

		if _, err := q.Exec(ctx,
			`UPDATE portfolio_images SET position = -position - 1
			 WHERE portfolio_project_id = $1`, projectID); err != nil {
			return fmt.Errorf("stage image positions: %w", err)
		}
		for position, imageID := range ordered {
			if _, err := q.Exec(ctx,
				`UPDATE portfolio_images SET position = $3
				 WHERE id = $1 AND portfolio_project_id = $2`,
				imageID, projectID, position); err != nil {
				return fmt.Errorf("reorder images: %w", err)
			}
		}
		// Anything the client did not name keeps a stable order after the
		// named ones rather than being lost.
		if _, err := q.Exec(ctx, `
			WITH remaining AS (
			  SELECT id, row_number() OVER (ORDER BY position) + $2 AS new_position
			  FROM portfolio_images
			  WHERE portfolio_project_id = $1 AND position < 0
			)
			UPDATE portfolio_images pi SET position = r.new_position - 1
			FROM remaining r WHERE pi.id = r.id`, projectID, len(ordered)); err != nil {
			return fmt.Errorf("settle unnamed image positions: %w", err)
		}
		return nil
	})
}

func (s *Store) RemoveImage(ctx context.Context, imageID, developerID uuid.UUID) (uuid.UUID, error) {
	var fileID uuid.UUID
	err := s.db.QueryRow(ctx, `
		DELETE FROM portfolio_images pi
		USING portfolio_projects pp
		WHERE pi.id = $1 AND pp.id = pi.portfolio_project_id AND pp.developer_id = $2
		RETURNING pi.file_id`, imageID, developerID).Scan(&fileID)
	if database.IsNoRows(err) {
		return uuid.Nil, ErrNotFound
	}
	return fileID, err
}

// ── Links ───────────────────────────────────────────────────────────────────

func (s *Store) AddLink(ctx context.Context, projectID, developerID uuid.UUID,
	label, url, host, kind string) (uuid.UUID, error) {

	var id uuid.UUID
	err := s.db.QueryRow(ctx, `
		INSERT INTO portfolio_links (portfolio_project_id, label, url, url_host, kind)
		SELECT $1, $3, $4, $5, $6
		FROM portfolio_projects WHERE id = $1 AND developer_id = $2
		RETURNING id`, projectID, developerID, label, url, host, kind).Scan(&id)
	if database.IsNoRows(err) {
		return uuid.Nil, ErrNotFound
	}
	return id, err
}

func (s *Store) RemoveLink(ctx context.Context, linkID, developerID uuid.UUID) error {
	tag, err := s.db.Exec(ctx, `
		DELETE FROM portfolio_links pl
		USING portfolio_projects pp
		WHERE pl.id = $1 AND pp.id = pl.portfolio_project_id AND pp.developer_id = $2`,
		linkID, developerID)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

// ── Preview verdict ─────────────────────────────────────────────────────────

// SaveEmbeddable records the probe's verdict.
func (s *Store) SaveEmbeddable(ctx context.Context, projectID uuid.UUID, verdict, reason string) error {
	_, err := s.db.Exec(ctx, `
		UPDATE portfolio_projects
		   SET embeddable = $2, embeddable_reason = $3,
		       embeddable_checked_at = now(), updated_at = now()
		 WHERE id = $1`, projectID, verdict, nullIfBlank(reason))
	return err
}

func (s *Store) RecordView(ctx context.Context, projectID uuid.UUID) {
	_, _ = s.db.Exec(context.WithoutCancel(ctx),
		`UPDATE portfolio_projects SET view_count = view_count + 1 WHERE id = $1`, projectID)
}

// DeveloperFor resolves the owner and the public visibility of a project, for
// the authorisation checks.
func (s *Store) DeveloperFor(ctx context.Context, projectID uuid.UUID) (uuid.UUID, bool, error) {
	var owner uuid.UUID
	var visible bool
	err := s.db.QueryRow(ctx, `
		SELECT developer_id, is_published AND moderation_state = 'approved'
		FROM portfolio_projects WHERE id = $1`, projectID).Scan(&owner, &visible)
	if database.IsNoRows(err) {
		return uuid.Nil, false, ErrNotFound
	}
	return owner, visible, err
}

// DeveloperIDByUsername resolves the public URL's username to a developer.
//
// A dedicated lookup rather than loading the whole profile: listing someone's
// portfolio does not need their bio, their skills or their photo set.
func (s *Store) DeveloperIDByUsername(ctx context.Context, username string) (uuid.UUID, error) {
	var id uuid.UUID
	err := s.db.QueryRow(ctx, `
		SELECT u.id FROM users u
		JOIN developer_profiles d ON d.user_id = u.id
		WHERE u.username = $1 AND u.deleted_at IS NULL`,
		strings.ToLower(strings.TrimSpace(username))).Scan(&id)
	if database.IsNoRows(err) {
		return uuid.Nil, ErrNotFound
	}
	return id, err
}

// DeveloperRefFor loads the header the preview page shows, so a visitor can
// always get back to whose work they are looking at.
func (s *Store) DeveloperRefFor(ctx context.Context, developerID uuid.UUID) (DeveloperRef, error) {
	var ref DeveloperRef
	var derivatives map[string]map[string]string
	err := s.db.QueryRow(ctx, `
		SELECT u.username, u.full_name, coalesce(d.professional_title, ''), ph.derivatives
		FROM users u
		JOIN developer_profiles d ON d.user_id = u.id
		LEFT JOIN developer_photos ph ON ph.user_id = u.id AND ph.is_current
		WHERE u.id = $1`, developerID).
		Scan(&ref.Username, &ref.FullName, &ref.Title, &derivatives)
	if err != nil {
		return ref, err
	}
	for _, format := range []string{"webp", "jpeg"} {
		if sizes, ok := derivatives[format]; ok {
			if key, ok := sizes["128"]; ok {
				ref.PhotoURL = s.publicURL(key)
				break
			}
			for _, key := range sizes {
				ref.PhotoURL = s.publicURL(key)
				break
			}
		}
	}
	return ref, nil
}

// ── Helpers ─────────────────────────────────────────────────────────────────

// FormatVisibleValue applies the price visibility ladder.
//
// "private" reads as "Private contract" rather than being omitted: the work
// happened, and hiding its existence would misrepresent the developer's
// history. Only the figure is withheld.
func FormatVisibleValue(minor int64, currency, visibility string) string {
	switch visibility {
	case "public":
		return formatMoney(minor, currency)
	case "range":
		return formatRange(minor, currency)
	case "private":
		return "Private contract"
	}
	return ""
}

func formatMoney(minor int64, currency string) string {
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

func formatRange(minor int64, currency string) string {
	symbol := map[string]string{"USD": "$", "EUR": "€", "GBP": "£"}[currency]
	if symbol == "" {
		symbol = currency + " "
	}
	bands := []struct {
		upto  int64
		lower string
		upper string
	}{
		{25000, "", "250"},
		{50000, "250", "500"},
		{100000, "500", "1,000"},
		{250000, "1,000", "2,500"},
		{500000, "2,500", "5,000"},
		{1000000, "5,000", "10,000"},
		{2500000, "10,000", "25,000"},
	}
	for _, band := range bands {
		if minor < band.upto {
			if band.lower == "" {
				return "under " + symbol + band.upper
			}
			return symbol + band.lower + "–" + symbol + band.upper
		}
	}
	return symbol + "25,000+"
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

func nullIfBlank(s string) any {
	if strings.TrimSpace(s) == "" {
		return nil
	}
	return s
}

func defaultTo(v, fallback string) string {
	if strings.TrimSpace(v) == "" {
		return fallback
	}
	return v
}

func atoi(s string) int {
	v, _ := strconv.Atoi(s)
	return v
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}
