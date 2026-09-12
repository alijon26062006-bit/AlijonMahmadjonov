package contracts

import (
	"context"
	"fmt"
	"net/http"
	"strings"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

type Handlers struct {
	svc *Service
}

// milestoneAction is the signature every milestone endpoint shares.
type milestoneAction func(ctx context.Context, id *security.Identity,
	milestoneID uuid.UUID, in MoveRequest) (*Milestone, error)

func NewHandlers(svc *Service) *Handlers { return &Handlers{svc: svc} }

type Middleware struct {
	Require       httpx.Middleware
	CSRF          httpx.Middleware
	RequireClient httpx.Middleware
	VerifiedEmail httpx.Middleware
	RateLimitHire httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	// Reads: either party, an observer, or staff. Which one the caller is comes
	// back in my_role, so the interface knows which workspace to draw.
	read := r.Group("/contracts", mw.Require)
	read.GET("", h.mine)
	read.GET("/{id}", h.view)
	// Looked up by query rather than by a path segment: a reference in the
	// path collides with /contracts/{id}/... once another module hangs an
	// endpoint off a contract, and a collision that only appears when a later
	// module is added is a trap.
	read.GET("/by-reference", h.byReference)

	// Hiring is the client's move, and it costs money, so it carries the
	// verified-email requirement and its own limit.
	hire := r.Group("/contracts", mw.Require, mw.RequireClient, mw.CSRF)
	hire.POST("", mw.VerifiedEmail(mw.RateLimitHire(h.accept)))

	write := r.Group("/contracts", mw.Require, mw.CSRF)
	write.POST("/{id}/cancel", h.cancel)
	write.POST("/{id}/deliverables", h.addDeliverable)
	write.POST("/{id}/observers", h.addObserver)
	write.DELETE("/{id}/observers/{userID}", h.removeObserver)

	// Milestone actions are addressed by the milestone's own id: the contract
	// is resolved from it server-side, so a mismatched pair in the URL cannot
	// be used to act on someone else's work.
	milestones := r.Group("/milestones", mw.Require, mw.CSRF)
	milestones.POST("/{id}/start", h.start)
	milestones.POST("/{id}/submit", h.submit)
	milestones.POST("/{id}/request-revision", h.requestRevision)
	milestones.POST("/{id}/approve", h.approve)
	milestones.POST("/{id}/dispute", h.dispute)
	milestones.POST("/{id}/cancel", h.cancelMilestone)
}

func (h *Handlers) mine(w http.ResponseWriter, r *http.Request) error {
	cards, err := h.svc.Mine(r.Context(), security.FromContext(r.Context()),
		strings.TrimSpace(r.URL.Query().Get("status")))
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, cards, map[string]any{"count": len(cards)})
}

func (h *Handlers) view(w http.ResponseWriter, r *http.Request) error {
	contractID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	contract, err := h.svc.View(r.Context(), security.FromContext(r.Context()), contractID)
	if err != nil {
		return err
	}
	// A contract carries signed deliverable URLs and the parties' terms:
	// nothing here may sit in a shared cache.
	w.Header().Set("Cache-Control", "private, no-store")
	return httpx.JSON(w, http.StatusOK, contract)
}

func (h *Handlers) byReference(w http.ResponseWriter, r *http.Request) error {
	reference := strings.TrimSpace(r.URL.Query().Get("reference"))
	if reference == "" {
		return httpx.Validation(map[string]string{
			"reference": "Enter the contract reference, for example AVX-2026-1A2B3C4D.",
		})
	}
	contract, err := h.svc.ByReference(r.Context(), security.FromContext(r.Context()), reference)
	if err != nil {
		return err
	}
	w.Header().Set("Cache-Control", "private, no-store")
	return httpx.JSON(w, http.StatusOK, contract)
}

func (h *Handlers) accept(w http.ResponseWriter, r *http.Request) error {
	var body AcceptRequest
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	contract, err := h.svc.Accept(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusCreated, contract)
}

func (h *Handlers) cancel(w http.ResponseWriter, r *http.Request) error {
	contractID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body CancelRequest
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	contract, err := h.svc.Cancel(r.Context(), security.FromContext(r.Context()),
		contractID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, contract)
}

func (h *Handlers) addDeliverable(w http.ResponseWriter, r *http.Request) error {
	contractID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body struct {
		DeliverableRequest
		MilestoneID string `json:"milestone_id"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 8<<10); err != nil {
		return err
	}

	var milestoneID *uuid.UUID
	if raw := strings.TrimSpace(body.MilestoneID); raw != "" {
		parsed, err := uuid.Parse(raw)
		if err != nil {
			return httpx.Validation(map[string]string{
				"milestone_id": "That milestone reference isn't valid.",
			})
		}
		milestoneID = &parsed
	}

	deliverable, err := h.svc.AddDeliverable(r.Context(), security.FromContext(r.Context()),
		contractID, milestoneID, body.DeliverableRequest)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusCreated, deliverable)
}

func (h *Handlers) addObserver(w http.ResponseWriter, r *http.Request) error {
	contractID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body ParticipantRequest
	if err := httpx.DecodeJSON(w, r, &body, 2<<10); err != nil {
		return err
	}
	contract, err := h.svc.AddObserver(r.Context(), security.FromContext(r.Context()),
		contractID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, contract)
}

func (h *Handlers) removeObserver(w http.ResponseWriter, r *http.Request) error {
	contractID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	userID, err := pathID(r, "userID")
	if err != nil {
		return err
	}
	if err := h.svc.RemoveObserver(r.Context(), security.FromContext(r.Context()),
		contractID, userID); err != nil {
		return err
	}
	return httpx.NoContent(w)
}

// ── Milestone actions ───────────────────────────────────────────────────────

func (h *Handlers) start(w http.ResponseWriter, r *http.Request) error {
	return h.milestoneAction(w, r, h.svc.Start)
}

func (h *Handlers) submit(w http.ResponseWriter, r *http.Request) error {
	return h.milestoneAction(w, r, h.svc.Submit)
}

func (h *Handlers) requestRevision(w http.ResponseWriter, r *http.Request) error {
	return h.milestoneAction(w, r, h.svc.RequestRevision)
}

func (h *Handlers) approve(w http.ResponseWriter, r *http.Request) error {
	return h.milestoneAction(w, r, h.svc.Approve)
}

func (h *Handlers) dispute(w http.ResponseWriter, r *http.Request) error {
	return h.milestoneAction(w, r, h.svc.Dispute)
}

func (h *Handlers) cancelMilestone(w http.ResponseWriter, r *http.Request) error {
	return h.milestoneAction(w, r, h.svc.CancelMilestone)
}

// milestoneAction is the shape every milestone endpoint shares: parse the id,
// decode the note and any deliverables, call the service, return the milestone.
func (h *Handlers) milestoneAction(w http.ResponseWriter, r *http.Request,
	action milestoneAction) error {

	milestoneID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body MoveRequest
	if r.ContentLength != 0 {
		if err := httpx.DecodeJSON(w, r, &body, 16<<10); err != nil {
			return err
		}
	}
	milestone, err := action(r.Context(), security.FromContext(r.Context()), milestoneID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, milestone)
}

func pathID(r *http.Request, name string) (uuid.UUID, error) {
	parsed, err := uuid.Parse(r.PathValue(name))
	if err != nil {
		return uuid.Nil, httpx.ErrBadRequest.Wrap(
			fmt.Errorf("%s is not a valid identifier", name))
	}
	return parsed, nil
}
