package payments

import (
	"fmt"
	"io"
	"net/http"
	"strings"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

type Handlers struct {
	svc *Service
}

func NewHandlers(svc *Service) *Handlers { return &Handlers{svc: svc} }

type Middleware struct {
	Require       httpx.Middleware
	CSRF          httpx.Middleware
	RequireClient httpx.Middleware
	RequireAdmin  httpx.Middleware
	VerifiedEmail httpx.Middleware
	RateLimitFund httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	// Funding a milestone is the client's action. It creates nothing but an
	// intent: with the manual provider it hands back the transfer details and
	// the reference to quote, and the milestone stays unfunded until an
	// administrator confirms the money arrived.
	client := r.Group("/milestones", mw.Require, mw.RequireClient, mw.CSRF)
	client.POST("/{id}/fund", mw.VerifiedEmail(mw.RateLimitFund(h.fund)))

	parties := r.Group("/contracts", mw.Require)
	parties.GET("/{id}/payments", h.forContract)

	// A person's own money. There is no endpoint for anyone else's.
	me := r.Group("/me", mw.Require)
	me.GET("/balance", h.balance)

	admin := r.Group("/admin/payments", mw.Require, mw.RequireAdmin)
	admin.GET("/queue", h.queue)
	admin.GET("/providers", h.providers)
	admin.GET("/manual-details", h.manualDetails)

	adminWrite := r.Group("/admin/payments", mw.Require, mw.RequireAdmin, mw.CSRF)
	adminWrite.POST("/{id}/confirm", h.confirm)
	adminWrite.POST("/{id}/confirm-payout", h.confirmPayout)
	adminWrite.POST("/{id}/reject", h.reject)
	adminWrite.POST("/{id}/refund", h.refund)
	adminWrite.PUT("/manual-details", h.setManualDetails)

	// The provider callback. Outside the session entirely — a gateway has no
	// cookie — and authenticated by its signature instead, which is verified
	// before anything is acted on.
	r.POST("/payments/webhook/{provider}", h.webhook)
}

func (h *Handlers) fund(w http.ResponseWriter, r *http.Request) error {
	milestoneID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	payment, err := h.svc.Fund(r.Context(), security.FromContext(r.Context()), milestoneID)
	if err != nil {
		return err
	}
	// Transfer instructions carry an account number: never a shared cache.
	w.Header().Set("Cache-Control", "private, no-store")
	return httpx.JSON(w, http.StatusCreated, payment)
}

func (h *Handlers) forContract(w http.ResponseWriter, r *http.Request) error {
	contractID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	payments, err := h.svc.ForContract(r.Context(), security.FromContext(r.Context()), contractID)
	if err != nil {
		return err
	}
	w.Header().Set("Cache-Control", "private, no-store")
	return httpx.JSONMeta(w, http.StatusOK, payments, map[string]any{"count": len(payments)})
}

func (h *Handlers) balance(w http.ResponseWriter, r *http.Request) error {
	balance, err := h.svc.MyBalance(r.Context(), security.FromContext(r.Context()),
		r.URL.Query().Get("currency"))
	if err != nil {
		return err
	}
	w.Header().Set("Cache-Control", "private, no-store")
	return httpx.JSON(w, http.StatusOK, balance)
}

// ── Administration ──────────────────────────────────────────────────────────

func (h *Handlers) queue(w http.ResponseWriter, r *http.Request) error {
	items, err := h.svc.Queue(r.Context(), security.FromContext(r.Context()),
		strings.TrimSpace(r.URL.Query().Get("direction")))
	if err != nil {
		return err
	}
	w.Header().Set("Cache-Control", "private, no-store")
	return httpx.JSONMeta(w, http.StatusOK, items, map[string]any{"count": len(items)})
}

func (h *Handlers) providers(w http.ResponseWriter, r *http.Request) error {
	rows, err := h.svc.Providers(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, rows)
}

func (h *Handlers) manualDetails(w http.ResponseWriter, r *http.Request) error {
	details, err := h.svc.ManualDetails(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	w.Header().Set("Cache-Control", "private, no-store")
	return httpx.JSON(w, http.StatusOK, details)
}

func (h *Handlers) setManualDetails(w http.ResponseWriter, r *http.Request) error {
	var body ManualDetailsRequest
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	details, err := h.svc.SetManualDetails(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, details)
}

func (h *Handlers) confirm(w http.ResponseWriter, r *http.Request) error {
	intentID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body ConfirmRequest
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	payment, err := h.svc.ConfirmCharge(r.Context(), security.FromContext(r.Context()),
		intentID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, payment)
}

func (h *Handlers) confirmPayout(w http.ResponseWriter, r *http.Request) error {
	intentID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body ConfirmRequest
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	payment, err := h.svc.ConfirmPayout(r.Context(), security.FromContext(r.Context()),
		intentID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, payment)
}

func (h *Handlers) reject(w http.ResponseWriter, r *http.Request) error {
	intentID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body RejectRequest
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	payment, err := h.svc.Reject(r.Context(), security.FromContext(r.Context()), intentID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, payment)
}

func (h *Handlers) refund(w http.ResponseWriter, r *http.Request) error {
	intentID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body RefundRequest
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	payment, err := h.svc.Refund(r.Context(), security.FromContext(r.Context()), intentID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, payment)
}

// webhook takes a provider callback.
//
// The body is read raw and capped: a signature is computed over exactly the
// bytes that arrived, so parsing first and re-encoding would verify something
// the provider never sent.
func (h *Handlers) webhook(w http.ResponseWriter, r *http.Request) error {
	body, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	if err := h.svc.Webhook(r.Context(), r.PathValue("provider"), r.Header, body); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"received": true})
}

func pathID(r *http.Request, name string) (uuid.UUID, error) {
	parsed, err := uuid.Parse(r.PathValue(name))
	if err != nil {
		return uuid.Nil, httpx.ErrBadRequest.Wrap(
			fmt.Errorf("%s is not a valid identifier", name))
	}
	return parsed, nil
}
