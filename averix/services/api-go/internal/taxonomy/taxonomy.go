// Package taxonomy serves the closed software taxonomy: specialisations,
// the category tree and the technology list.
//
// These endpoints are the only ones in the product that are safe to cache
// aggressively and serve to anonymous visitors, because the data is reference
// data rather than anyone's content.
package taxonomy

import (
	"context"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/cache"
	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/httpx"
)

type Specialisation struct {
	ID          uuid.UUID `json:"id"`
	Slug        string    `json:"slug"`
	Name        string    `json:"name"`
	ShortName   string    `json:"short_name"`
	Description string    `json:"description,omitempty"`
	SortOrder   int       `json:"sort_order"`
}

type Category struct {
	ID          uuid.UUID  `json:"id"`
	ParentID    *uuid.UUID `json:"parent_id,omitempty"`
	Slug        string     `json:"slug"`
	Name        string     `json:"name"`
	Description string     `json:"description,omitempty"`
	Path        string     `json:"path"`
	Depth       int        `json:"depth"`
	SortOrder   int        `json:"sort_order"`
	Children    []Category `json:"children,omitempty"`
}

type Skill struct {
	ID       uuid.UUID  `json:"id"`
	Slug     string     `json:"slug"`
	Name     string     `json:"name"`
	Kind     string     `json:"kind"`
	ParentID *uuid.UUID `json:"parent_id,omitempty"`
	Colour   string     `json:"colour,omitempty"`
	IsCore   bool       `json:"is_core,omitempty"`
}

type Store struct{ db *database.DB }

func NewStore(db *database.DB) *Store { return &Store{db: db} }

func (s *Store) Specialisations(ctx context.Context) ([]Specialisation, error) {
	rows, err := s.db.Query(ctx, `
		SELECT id, slug, name, short_name, coalesce(description, ''), sort_order
		FROM specialisations WHERE is_active ORDER BY sort_order, name`)
	if err != nil {
		return nil, fmt.Errorf("query specialisations: %w", err)
	}
	defer rows.Close()

	var out []Specialisation
	for rows.Next() {
		var sp Specialisation
		if err := rows.Scan(&sp.ID, &sp.Slug, &sp.Name, &sp.ShortName, &sp.Description, &sp.SortOrder); err != nil {
			return nil, fmt.Errorf("scan specialisation: %w", err)
		}
		out = append(out, sp)
	}
	return out, rows.Err()
}

// CategoryTree returns the hierarchy assembled in one query. The `path` column
// makes the nesting a sort rather than a recursive walk.
func (s *Store) CategoryTree(ctx context.Context) ([]Category, error) {
	rows, err := s.db.Query(ctx, `
		SELECT id, parent_id, slug, name, coalesce(description, ''), path, depth, sort_order
		FROM categories WHERE is_active ORDER BY depth, sort_order, name`)
	if err != nil {
		return nil, fmt.Errorf("query categories: %w", err)
	}
	defer rows.Close()

	var flat []Category
	for rows.Next() {
		var c Category
		if err := rows.Scan(&c.ID, &c.ParentID, &c.Slug, &c.Name, &c.Description,
			&c.Path, &c.Depth, &c.SortOrder); err != nil {
			return nil, fmt.Errorf("scan category: %w", err)
		}
		flat = append(flat, c)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	// Index children by parent once, then assemble depth-first. Building the
	// tree in a single downward pass would attach grandchildren to a copy of
	// the parent rather than the one the caller receives.
	byParent := make(map[uuid.UUID][]Category, len(flat))
	var roots []Category
	for _, c := range flat {
		if c.ParentID == nil {
			roots = append(roots, c)
			continue
		}
		byParent[*c.ParentID] = append(byParent[*c.ParentID], c)
	}

	var attach func(c Category) Category
	attach = func(c Category) Category {
		children := byParent[c.ID]
		if len(children) == 0 {
			return c
		}
		c.Children = make([]Category, 0, len(children))
		for _, child := range children {
			c.Children = append(c.Children, attach(child))
		}
		return c
	}
	for i := range roots {
		roots[i] = attach(roots[i])
	}
	return roots, nil
}

func (s *Store) Skills(ctx context.Context, kind, query string, limit int) ([]Skill, error) {
	if limit <= 0 || limit > 300 {
		limit = 300
	}
	rows, err := s.db.Query(ctx, `
		SELECT id, slug, name, kind, parent_id, coalesce(colour, '')
		FROM skills
		WHERE is_active
		  AND ($1 = '' OR kind = $1)
		  AND ($2 = '' OR name ILIKE '%' || $2 || '%' OR slug ILIKE '%' || $2 || '%')
		ORDER BY usage_count DESC, name
		LIMIT $3`, kind, query, limit)
	if err != nil {
		return nil, fmt.Errorf("query skills: %w", err)
	}
	defer rows.Close()
	return scanSkills(rows)
}

// SkillsForSpecialisation returns the relevant technologies for a
// specialisation, which is what keeps the onboarding picker to a usable size
// instead of listing all 87 options.
func (s *Store) SkillsForSpecialisation(ctx context.Context, slug string) ([]Skill, error) {
	rows, err := s.db.Query(ctx, `
		SELECT sk.id, sk.slug, sk.name, sk.kind, sk.parent_id, coalesce(sk.colour, ''), ss.is_core
		FROM specialisation_skills ss
		JOIN specialisations sp ON sp.id = ss.specialisation_id
		JOIN skills sk ON sk.id = ss.skill_id
		WHERE sp.slug = $1 AND sk.is_active
		ORDER BY ss.is_core DESC, sk.kind, sk.name`, slug)
	if err != nil {
		return nil, fmt.Errorf("query specialisation skills: %w", err)
	}
	defer rows.Close()

	var out []Skill
	for rows.Next() {
		var sk Skill
		if err := rows.Scan(&sk.ID, &sk.Slug, &sk.Name, &sk.Kind, &sk.ParentID, &sk.Colour, &sk.IsCore); err != nil {
			return nil, fmt.Errorf("scan skill: %w", err)
		}
		out = append(out, sk)
	}
	return out, rows.Err()
}

// SkillsForCategory returns the technologies a category implies, used to
// pre-fill the project wizard.
func (s *Store) SkillsForCategory(ctx context.Context, slug string) ([]Skill, error) {
	rows, err := s.db.Query(ctx, `
		SELECT sk.id, sk.slug, sk.name, sk.kind, sk.parent_id, coalesce(sk.colour, '')
		FROM category_skills cs
		JOIN categories c ON c.id = cs.category_id
		JOIN skills sk ON sk.id = cs.skill_id
		WHERE c.slug = $1 AND sk.is_active
		ORDER BY cs.weight DESC, sk.name`, slug)
	if err != nil {
		return nil, fmt.Errorf("query category skills: %w", err)
	}
	defer rows.Close()
	return scanSkills(rows)
}

func scanSkills(rows interface {
	Next() bool
	Scan(...any) error
	Err() error
}) ([]Skill, error) {
	var out []Skill
	for rows.Next() {
		var sk Skill
		if err := rows.Scan(&sk.ID, &sk.Slug, &sk.Name, &sk.Kind, &sk.ParentID, &sk.Colour); err != nil {
			return nil, fmt.Errorf("scan skill: %w", err)
		}
		out = append(out, sk)
	}
	return out, rows.Err()
}

// ResolveSkillIDs turns slugs into ids, reporting any that do not exist.
//
// Every write path takes slugs from the client and resolves them here, so an
// arbitrary uuid in a request body cannot attach a row that does not belong to
// the taxonomy.
func (s *Store) ResolveSkillIDs(ctx context.Context, slugs []string) ([]uuid.UUID, []string, error) {
	if len(slugs) == 0 {
		return nil, nil, nil
	}
	rows, err := s.db.Query(ctx,
		`SELECT slug, id FROM skills WHERE slug = ANY($1) AND is_active`, slugs)
	if err != nil {
		return nil, nil, fmt.Errorf("resolve skills: %w", err)
	}
	defer rows.Close()

	found := map[string]uuid.UUID{}
	for rows.Next() {
		var slug string
		var id uuid.UUID
		if err := rows.Scan(&slug, &id); err != nil {
			return nil, nil, err
		}
		found[slug] = id
	}
	if err := rows.Err(); err != nil {
		return nil, nil, err
	}

	ids := make([]uuid.UUID, 0, len(slugs))
	var unknown []string
	seen := map[uuid.UUID]bool{}
	for _, slug := range slugs {
		id, ok := found[strings.ToLower(strings.TrimSpace(slug))]
		if !ok {
			unknown = append(unknown, slug)
			continue
		}
		if !seen[id] {
			ids = append(ids, id)
			seen[id] = true
		}
	}
	return ids, unknown, nil
}

func (s *Store) SpecialisationIDBySlug(ctx context.Context, slug string) (uuid.UUID, error) {
	var id uuid.UUID
	err := s.db.QueryRow(ctx,
		`SELECT id FROM specialisations WHERE slug = $1 AND is_active`, slug).Scan(&id)
	if database.IsNoRows(err) {
		return uuid.Nil, fmt.Errorf("unknown specialisation %q", slug)
	}
	return id, err
}

func (s *Store) CategoryIDBySlug(ctx context.Context, slug string) (uuid.UUID, error) {
	var id uuid.UUID
	err := s.db.QueryRow(ctx,
		`SELECT id FROM categories WHERE slug = $1 AND is_active`, slug).Scan(&id)
	if database.IsNoRows(err) {
		return uuid.Nil, fmt.Errorf("unknown category %q", slug)
	}
	return id, err
}

// ── HTTP ────────────────────────────────────────────────────────────────────

type Handlers struct {
	store *Store
	cache *cache.Cache
}

func NewHandlers(store *Store, c *cache.Cache) *Handlers {
	return &Handlers{store: store, cache: c}
}

// Reference data changes only when an administrator edits it, so a long cache
// is correct; the admin panel busts these keys on write.
const referenceTTL = 30 * time.Minute

func (h *Handlers) Register(r *httpx.Router) {
	g := r.Group("/taxonomy")
	g.GET("/specialisations", h.specialisations)
	g.GET("/categories", h.categories)
	g.GET("/skills", h.skills)
	g.GET("/specialisations/{slug}/skills", h.specialisationSkills)
	g.GET("/categories/{slug}/skills", h.categorySkills)
}

func (h *Handlers) specialisations(w http.ResponseWriter, r *http.Request) error {
	out, err := cache.Remember(r.Context(), h.cache, "tax:specialisations", referenceTTL,
		func() ([]Specialisation, error) { return h.store.Specialisations(r.Context()) })
	if err != nil {
		return httpx.Internalf(err, "load specialisations")
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) categories(w http.ResponseWriter, r *http.Request) error {
	out, err := cache.Remember(r.Context(), h.cache, "tax:categories", referenceTTL,
		func() ([]Category, error) { return h.store.CategoryTree(r.Context()) })
	if err != nil {
		return httpx.Internalf(err, "load categories")
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) skills(w http.ResponseWriter, r *http.Request) error {
	kind := strings.TrimSpace(r.URL.Query().Get("kind"))
	query := strings.TrimSpace(r.URL.Query().Get("q"))

	// A search is not cached: the key space is unbounded and the query is fast.
	if query != "" {
		out, err := h.store.Skills(r.Context(), kind, query, 50)
		if err != nil {
			return httpx.Internalf(err, "search skills")
		}
		return httpx.JSON(w, http.StatusOK, out)
	}
	out, err := cache.Remember(r.Context(), h.cache, "tax:skills:"+kind, referenceTTL,
		func() ([]Skill, error) { return h.store.Skills(r.Context(), kind, "", 300) })
	if err != nil {
		return httpx.Internalf(err, "load skills")
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) specialisationSkills(w http.ResponseWriter, r *http.Request) error {
	slug := r.PathValue("slug")
	out, err := cache.Remember(r.Context(), h.cache, "tax:spec-skills:"+slug, referenceTTL,
		func() ([]Skill, error) { return h.store.SkillsForSpecialisation(r.Context(), slug) })
	if err != nil {
		return httpx.Internalf(err, "load specialisation skills")
	}
	if len(out) == 0 {
		return httpx.NotFoundf("specialisation %q has no technologies or does not exist", slug)
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) categorySkills(w http.ResponseWriter, r *http.Request) error {
	slug := r.PathValue("slug")
	out, err := cache.Remember(r.Context(), h.cache, "tax:cat-skills:"+slug, referenceTTL,
		func() ([]Skill, error) { return h.store.SkillsForCategory(r.Context(), slug) })
	if err != nil {
		return httpx.Internalf(err, "load category skills")
	}
	return httpx.JSON(w, http.StatusOK, out)
}

// Invalidate clears the reference caches, called by the admin panel after an
// edit so a change is visible immediately rather than in half an hour.
func (h *Handlers) Invalidate(ctx context.Context) error {
	if h.cache == nil {
		return nil
	}
	return h.cache.DeletePrefix(ctx, "tax:")
}
