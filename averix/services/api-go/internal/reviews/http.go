package reviews

import (
	"net/http"
	"strconv"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

type Handlers struct{ svc *Service }

func NewHandlers(svc *Service) *Handlers { return &Handlers{svc: svc} }

type Middleware struct {
	Require    httpx.Middleware
	CSRF       httpx.Middleware
	RequireDev httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	// On a contract, for its parties.
	contract := r.Group("/contracts", mw.Require)
	contract.GET("/{id}/reviews", h.forContract)
	contract.POST("/{id}/reviews", mw.CSRF(h.submit))

	answer := r.Group("/reviews", mw.Require, mw.CSRF)
	answer.POST("/{id}/response", h.respond)

	// Public: what a profile shows. Anonymous visitors may read these.
	pub := r.Group("")
	pub.GET("/developers/{username}/reviews", h.publicDeveloper)
	pub.GET("/developers/{username}/history", h.history)
	pub.GET("/clients/{username}/reviews", h.publicClient)

	// The owner hides an entry from their profile; nothing else about it can
	// change.
	me := r.Group("/developers/me/history", mw.Require, mw.RequireDev, mw.CSRF)
	me.PUT("/{id}/visibility", h.setHistoryVisibility)
}

func (h *Handlers) forContract(w http.ResponseWriter, r *http.Request) error {
	contractID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	panel, err := h.svc.ForContract(r.Context(), security.FromContext(r.Context()), contractID)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, panel)
}

func (h *Handlers) submit(w http.ResponseWriter, r *http.Request) error {
	contractID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	var body SubmitRequest
	if err := httpx.DecodeJSON(w, r, &body, 16<<10); err != nil {
		return err
	}
	review, err := h.svc.Submit(r.Context(), security.FromContext(r.Context()), contractID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusCreated, review)
}

func (h *Handlers) respond(w http.ResponseWriter, r *http.Request) error {
	reviewID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	var body struct {
		Response string `json:"response"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 8<<10); err != nil {
		return err
	}
	review, err := h.svc.Respond(r.Context(), security.FromContext(r.Context()), reviewID, body.Response)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, review)
}

func (h *Handlers) publicDeveloper(w http.ResponseWriter, r *http.Request) error {
	return h.public(w, r, DirectionOfDeveloper)
}

func (h *Handlers) publicClient(w http.ResponseWriter, r *http.Request) error {
	return h.public(w, r, DirectionOfClient)
}

func (h *Handlers) public(w http.ResponseWriter, r *http.Request, direction string) error {
	q := r.URL.Query()
	var before *time.Time
	if raw := q.Get("before"); raw != "" {
		t, err := time.Parse(time.RFC3339Nano, raw)
		if err != nil {
			return httpx.Validation(map[string]string{"before": "Неверный формат времени."})
		}
		before = &t
	}
	limit, _ := strconv.Atoi(q.Get("limit"))
	list, summary, err := h.svc.PublicFor(r.Context(), r.PathValue("username"), direction, before, limit)
	if err != nil {
		return err
	}
	meta := map[string]any{"summary": summary, "categories": categoriesFor(direction)}
	if n := len(list); n > 0 && n >= limit && limit > 0 {
		meta["next_before"] = list[n-1].PublishedAt.Format(time.RFC3339Nano)
	}
	return httpx.JSONMeta(w, http.StatusOK, list, meta)
}

func (h *Handlers) history(w http.ResponseWriter, r *http.Request) error {
	entries, err := h.svc.HistoryFor(r.Context(), security.FromContext(r.Context()), r.PathValue("username"))
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, entries, map[string]any{"count": len(entries)})
}

func (h *Handlers) setHistoryVisibility(w http.ResponseWriter, r *http.Request) error {
	entryID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	var body struct {
		Visible bool `json:"visible"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 1<<10); err != nil {
		return err
	}
	if err := h.svc.SetHistoryVisibility(r.Context(), security.FromContext(r.Context()), entryID, body.Visible); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"visible": body.Visible})
}
