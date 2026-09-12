package projects

import (
	"net/http"
	"strconv"
	"strings"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

type Handlers struct{ svc *Service }

func NewHandlers(svc *Service) *Handlers { return &Handlers{svc: svc} }

type Middleware struct {
	Resolve        httpx.Middleware
	Require        httpx.Middleware
	CSRF           httpx.Middleware
	RequireClient  httpx.Middleware
	RequireDev     httpx.Middleware
	VerifiedEmail  httpx.Middleware
	RateLimitWrite httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	// A published project is a public page: it is what a shared link opens,
	// and search engines should be able to see it.
	pub := r.Group("/projects")
	pub.GET("/{slug}", h.view)

	// The developer feed.
	feed := r.Group("/projects", mw.Require, mw.RequireDev)
	feed.GET("", h.feed)
	feed.GET("/feed/tabs", h.tabs)

	// Client-owned writes.
	own := r.Group("/projects", mw.Require, mw.RequireClient, mw.CSRF)
	// Creating a draft does not require a confirmed address: a client who has
	// just signed up should be able to write their brief while the
	// confirmation email is in flight. Publishing does require it, and the
	// service enforces that.
	own.POST("", mw.RateLimitWrite(h.create))
	own.GET("/mine/list", h.mine)
	own.PATCH("/{id}", h.update)
	own.POST("/{id}/publish", mw.VerifiedEmail(h.publish))
	own.POST("/{id}/cancel", h.cancel)
}

func (h *Handlers) create(w http.ResponseWriter, r *http.Request) error {
	var body CreateRequest
	if err := httpx.DecodeJSON(w, r, &body, 64<<10); err != nil {
		return err
	}
	project, err := h.svc.Create(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusCreated, project)
}

func (h *Handlers) view(w http.ResponseWriter, r *http.Request) error {
	project, err := h.svc.View(r.Context(), security.FromContext(r.Context()), r.PathValue("slug"))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, project)
}

func (h *Handlers) update(w http.ResponseWriter, r *http.Request) error {
	projectID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	var body UpdateRequest
	if err := httpx.DecodeJSON(w, r, &body, 64<<10); err != nil {
		return err
	}
	project, err := h.svc.Update(r.Context(), security.FromContext(r.Context()), projectID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, project)
}

func (h *Handlers) publish(w http.ResponseWriter, r *http.Request) error {
	projectID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	project, err := h.svc.Publish(r.Context(), security.FromContext(r.Context()), projectID)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, project)
}

func (h *Handlers) cancel(w http.ResponseWriter, r *http.Request) error {
	projectID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	var body struct {
		Reason string `json:"reason"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	if err := h.svc.Cancel(r.Context(), security.FromContext(r.Context()), projectID, body.Reason); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"status": StatusCancelled})
}

func (h *Handlers) mine(w http.ResponseWriter, r *http.Request) error {
	projects, err := h.svc.MyProjects(r.Context(), security.FromContext(r.Context()),
		r.URL.Query().Get("status"))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, projects)
}

func (h *Handlers) tabs(w http.ResponseWriter, r *http.Request) error {
	tabs, err := h.svc.Tabs(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, tabs)
}

func (h *Handlers) feed(w http.ResponseWriter, r *http.Request) error {
	q := r.URL.Query()

	query := FeedQuery{
		Tab:    FeedTab(defaultTo(q.Get("tab"), string(TabForYou))),
		Search: strings.TrimSpace(q.Get("q")),
		Sort:   q.Get("sort"),
		Limit:  atoiDefault(q.Get("limit"), defaultFeedLimit),
	}

	// A tab value that is not one of the known ones is treated as a category
	// filter, which is how the category tabs are addressed.
	switch query.Tab {
	case TabForYou, TabRecent, TabSaved, TabInvitations:
	default:
		query.CategorySlug = string(query.Tab)
		query.Tab = TabCategory
	}

	if raw := q.Get("skills"); raw != "" {
		for _, slug := range strings.Split(raw, ",") {
			if slug = strings.TrimSpace(slug); slug != "" {
				query.SkillSlugs = append(query.SkillSlugs, slug)
			}
		}
		if len(query.SkillSlugs) > 20 {
			return httpx.Validation(map[string]string{"skills": "Filter by up to 20 technologies."})
		}
	}
	if raw := q.Get("budget_min"); raw != "" {
		if v, err := strconv.ParseInt(raw, 10, 64); err == nil && v >= 0 {
			query.BudgetMin = &v
		}
	}
	if raw := q.Get("budget_max"); raw != "" {
		if v, err := strconv.ParseInt(raw, 10, 64); err == nil && v >= 0 {
			query.BudgetMax = &v
		}
	}
	if cursor := q.Get("cursor"); cursor != "" {
		t, id, err := DecodeCursor(cursor)
		if err != nil {
			return httpx.Validation(map[string]string{"cursor": "That page reference isn't valid."})
		}
		query.CursorTime, query.CursorID = t, id
	}

	page, err := h.svc.Feed(r.Context(), security.FromContext(r.Context()), query)
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, page.Cards, map[string]any{
		"has_more":    page.HasMore,
		"next_cursor": page.NextCursor,
		"tab":         string(query.Tab),
	})
}

func atoiDefault(raw string, fallback int) int {
	if n, err := strconv.Atoi(raw); err == nil {
		return n
	}
	return fallback
}
