package proposals

import (
	"context"
	"net/http"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

// ProjectOwners resolves who owns a project, which the proposal list needs for
// its authorisation check. An interface so this module does not import
// projects (which already imports matching, and would create a cycle).
type ProjectOwners interface {
	OwnerOf(ctx context.Context, projectID uuid.UUID) (uuid.UUID, string, error)
}

type Handlers struct {
	svc    *Service
	owners ProjectOwners
}

func NewHandlers(svc *Service, owners ProjectOwners) *Handlers {
	return &Handlers{svc: svc, owners: owners}
}

type Middleware struct {
	Require        httpx.Middleware
	CSRF           httpx.Middleware
	RequireClient  httpx.Middleware
	RequireDev     httpx.Middleware
	VerifiedEmail  httpx.Middleware
	RateLimitWrite httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	dev := r.Group("/proposals", mw.Require, mw.RequireDev, mw.CSRF)
	dev.POST("", mw.VerifiedEmail(mw.RateLimitWrite(h.submit)))
	dev.GET("/mine", h.mine)
	dev.POST("/{id}/withdraw", h.withdraw)

	// Either party may read a proposal they are on; the service decides which.
	both := r.Group("/proposals", mw.Require)
	both.GET("/{id}", h.view)

	client := r.Group("/proposals", mw.Require, mw.RequireClient, mw.CSRF)
	client.POST("/{id}/shortlist", h.shortlist)
	client.POST("/{id}/decline", h.decline)

	// The client's list of proposals on one of their projects.
	list := r.Group("/projects", mw.Require, mw.RequireClient)
	list.GET("/{id}/proposals", h.forProject)
}

func (h *Handlers) submit(w http.ResponseWriter, r *http.Request) error {
	var body SubmitRequest
	if err := httpx.DecodeJSON(w, r, &body, 64<<10); err != nil {
		return err
	}
	proposal, err := h.svc.Submit(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusCreated, proposal)
}

func (h *Handlers) view(w http.ResponseWriter, r *http.Request) error {
	proposalID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	proposal, err := h.svc.View(r.Context(), security.FromContext(r.Context()), proposalID)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, proposal)
}

func (h *Handlers) mine(w http.ResponseWriter, r *http.Request) error {
	proposals, err := h.svc.Mine(r.Context(), security.FromContext(r.Context()),
		r.URL.Query().Get("status"))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, proposals)
}

func (h *Handlers) forProject(w http.ResponseWriter, r *http.Request) error {
	projectID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}

	owner, _, err := h.owners.OwnerOf(r.Context(), projectID)
	if err != nil {
		return httpx.NotFoundf("project %s does not exist", projectID)
	}

	sort := SortOrder(r.URL.Query().Get("sort"))
	cards, err := h.svc.ForProject(r.Context(), security.FromContext(r.Context()),
		projectID, sort, owner)
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, cards, map[string]any{
		"count": len(cards),
		"sort":  string(sort),
	})
}

func (h *Handlers) shortlist(w http.ResponseWriter, r *http.Request) error {
	proposalID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	var body struct {
		Shortlisted bool   `json:"shortlisted"`
		Note        string `json:"note"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	if err := h.svc.Shortlist(r.Context(), security.FromContext(r.Context()),
		proposalID, body.Shortlisted, body.Note); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"shortlisted": body.Shortlisted})
}

func (h *Handlers) decline(w http.ResponseWriter, r *http.Request) error {
	proposalID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	var body struct {
		Reason string `json:"reason"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	if err := h.svc.Decline(r.Context(), security.FromContext(r.Context()),
		proposalID, body.Reason); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"status": StatusDeclined})
}

func (h *Handlers) withdraw(w http.ResponseWriter, r *http.Request) error {
	proposalID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	if err := h.svc.Withdraw(r.Context(), security.FromContext(r.Context()), proposalID); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"status": StatusWithdrawn})
}
