package services

import (
	"net/http"
	"strconv"
	"strings"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

type Handlers struct{ svc *Svc }

func NewHandlers(svc *Svc) *Handlers { return &Handlers{svc: svc} }

type Middleware struct {
	Require        httpx.Middleware
	CSRF           httpx.Middleware
	RequireDev     httpx.Middleware
	RequireClient  httpx.Middleware
	VerifiedEmail  httpx.Middleware
	RateLimitOrder httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	// The catalogue and a service page are public: a visitor decides whether
	// to sign up by looking at what is on offer.
	pub := r.Group("/services")
	pub.GET("", h.catalogue)
	pub.GET("/{id}", h.view)

	sellers := r.Group("/developers")
	sellers.GET("/{username}/services", h.forSeller)

	// The owner's editor. "mine" is registered before "{id}" would match it.
	own := r.Group("/services", mw.Require, mw.RequireDev, mw.CSRF)
	own.GET("/mine/list", h.mine)
	own.POST("", h.create)
	own.PATCH("/{id}", h.update)
	own.POST("/{id}/publish", h.publish)
	own.POST("/{id}/pause", h.pause)
	own.POST("/{id}/archive", h.archive)

	buy := r.Group("/services", mw.Require, mw.RequireClient, mw.CSRF)
	buy.POST("/{id}/order", mw.VerifiedEmail(mw.RateLimitOrder(h.order)))
}

func (h *Handlers) catalogue(w http.ResponseWriter, r *http.Request) error {
	q := r.URL.Query()
	query := Query{
		CategorySlug: strings.TrimSpace(q.Get("category")),
		Text:         strings.TrimSpace(q.Get("q")),
		Currency:     strings.ToUpper(strings.TrimSpace(q.Get("currency"))),
		Sort:         q.Get("sort"),
	}
	if v, err := strconv.ParseInt(q.Get("min"), 10, 64); err == nil && v >= 0 {
		query.MinMinor = &v
	}
	if v, err := strconv.ParseInt(q.Get("max"), 10, 64); err == nil && v > 0 {
		query.MaxMinor = &v
	}
	if v, err := strconv.Atoi(q.Get("delivery")); err == nil && v > 0 {
		query.MaxDelivery = &v
	}
	query.Offset, _ = strconv.Atoi(q.Get("offset"))
	query.Limit, _ = strconv.Atoi(q.Get("limit"))
	if id := security.FromContext(r.Context()); id.Authenticated() {
		query.ViewerID = &id.UserID
	}

	cards, meta, err := h.svc.Catalogue(r.Context(), query)
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, cards, meta)
}

func (h *Handlers) view(w http.ResponseWriter, r *http.Request) error {
	serviceID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	service, err := h.svc.View(r.Context(), security.FromContext(r.Context()), serviceID)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, service)
}

func (h *Handlers) forSeller(w http.ResponseWriter, r *http.Request) error {
	cards, err := h.svc.ForSeller(r.Context(), security.FromContext(r.Context()), r.PathValue("username"))
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, cards, map[string]any{"count": len(cards)})
}

func (h *Handlers) mine(w http.ResponseWriter, r *http.Request) error {
	cards, err := h.svc.Mine(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, cards, map[string]any{"count": len(cards)})
}

func (h *Handlers) create(w http.ResponseWriter, r *http.Request) error {
	var body UpsertRequest
	if err := httpx.DecodeJSON(w, r, &body, 64<<10); err != nil {
		return err
	}
	service, err := h.svc.Create(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusCreated, service)
}

func (h *Handlers) update(w http.ResponseWriter, r *http.Request) error {
	serviceID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	var body UpsertRequest
	if err := httpx.DecodeJSON(w, r, &body, 64<<10); err != nil {
		return err
	}
	service, err := h.svc.Update(r.Context(), security.FromContext(r.Context()), serviceID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, service)
}

func (h *Handlers) publish(w http.ResponseWriter, r *http.Request) error {
	return h.transition(w, r, StatusActive)
}

func (h *Handlers) pause(w http.ResponseWriter, r *http.Request) error {
	return h.transition(w, r, StatusPaused)
}

func (h *Handlers) archive(w http.ResponseWriter, r *http.Request) error {
	return h.transition(w, r, StatusArchived)
}

func (h *Handlers) transition(w http.ResponseWriter, r *http.Request, to string) error {
	serviceID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	service, err := h.svc.SetStatus(r.Context(), security.FromContext(r.Context()), serviceID, to)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, service)
}

func (h *Handlers) order(w http.ResponseWriter, r *http.Request) error {
	serviceID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	var body OrderRequest
	if err := httpx.DecodeJSON(w, r, &body, 32<<10); err != nil {
		return err
	}
	contract, err := h.svc.Order(r.Context(), security.FromContext(r.Context()), serviceID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusCreated, contract)
}
