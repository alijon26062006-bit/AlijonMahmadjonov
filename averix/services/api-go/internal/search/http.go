package search

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
	Require       httpx.Middleware
	CSRF          httpx.Middleware
	RequireClient httpx.Middleware
	RequireDev    httpx.Middleware
	RateLimit     httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	// The catalogue and the search box are public. They are rate limited
	// because a catalogue is the cheapest thing to scrape.
	pub := r.Group("")
	pub.GET("/freelancers", mw.RateLimit(h.freelancers))
	pub.GET("/search", mw.RateLimit(h.everything))

	client := r.Group("/freelancers", mw.Require, mw.RequireClient, mw.CSRF)
	client.POST("/{username}/save", h.saveFreelancer)
	client.DELETE("/{username}/save", h.unsaveFreelancer)

	saved := r.Group("/me", mw.Require, mw.RequireClient)
	saved.GET("/saved-freelancers", h.savedFreelancers)

	dev := r.Group("/projects", mw.Require, mw.RequireDev, mw.CSRF)
	dev.POST("/{id}/save", h.saveProject)
	dev.DELETE("/{id}/save", h.unsaveProject)
}

func (h *Handlers) freelancers(w http.ResponseWriter, r *http.Request) error {
	q := r.URL.Query()
	query := FreelancerQuery{
		Sector:         strings.TrimSpace(q.Get("sector")),
		Specialisation: strings.TrimSpace(q.Get("specialisation")),
		Text:           strings.TrimSpace(q.Get("q")),
		Availability:   strings.TrimSpace(q.Get("availability")),
		Verified:       q.Get("verified") == "true",
		Sort:           q.Get("sort"),
	}
	for _, raw := range strings.Split(q.Get("skills"), ",") {
		if slug := strings.TrimSpace(raw); slug != "" {
			query.Skills = append(query.Skills, slug)
		}
	}
	if len(query.Skills) > 8 {
		return httpx.Validation(map[string]string{"skills": "Не больше восьми навыков в фильтре."})
	}
	if v, err := strconv.ParseInt(q.Get("min_rate"), 10, 64); err == nil && v >= 0 {
		query.MinRateMinor = &v
	}
	if v, err := strconv.ParseInt(q.Get("max_rate"), 10, 64); err == nil && v > 0 {
		query.MaxRateMinor = &v
	}
	switch query.Availability {
	case "", "available", "limited", "booked", "unavailable":
	default:
		return httpx.Validation(map[string]string{"availability": "Неизвестное значение доступности."})
	}
	query.Offset, _ = strconv.Atoi(q.Get("offset"))
	query.Limit, _ = strconv.Atoi(q.Get("limit"))
	if id := security.FromContext(r.Context()); id.Authenticated() {
		query.ViewerID = &id.UserID
	}
	cards, meta, err := h.svc.Freelancers(r.Context(), query)
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, cards, meta)
}

func (h *Handlers) everything(w http.ResponseWriter, r *http.Request) error {
	results, err := h.svc.Everything(r.Context(), security.FromContext(r.Context()), r.URL.Query().Get("q"))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, results)
}

func (h *Handlers) saveFreelancer(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Note string `json:"note"`
	}
	if r.ContentLength != 0 {
		if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
			return err
		}
	}
	if err := h.svc.SaveFreelancer(r.Context(), security.FromContext(r.Context()),
		r.PathValue("username"), body.Note); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"saved": true})
}

func (h *Handlers) unsaveFreelancer(w http.ResponseWriter, r *http.Request) error {
	if err := h.svc.UnsaveFreelancer(r.Context(), security.FromContext(r.Context()), r.PathValue("username")); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"saved": false})
}

func (h *Handlers) savedFreelancers(w http.ResponseWriter, r *http.Request) error {
	out, err := h.svc.SavedFreelancers(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, out, map[string]any{"count": len(out)})
}

func (h *Handlers) saveProject(w http.ResponseWriter, r *http.Request) error {
	projectID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	if err := h.svc.SaveProject(r.Context(), security.FromContext(r.Context()), projectID); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"saved": true})
}

func (h *Handlers) unsaveProject(w http.ResponseWriter, r *http.Request) error {
	projectID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	if err := h.svc.UnsaveProject(r.Context(), security.FromContext(r.Context()), projectID); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"saved": false})
}
