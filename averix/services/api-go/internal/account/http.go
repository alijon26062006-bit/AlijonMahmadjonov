package account

import (
	"net/http"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

type Handlers struct {
	svc *Service
	// Clears the cookie after a deactivation so the browser does not keep
	// sending a session that will be refused.
	clearCookie func(http.ResponseWriter)
}

func NewHandlers(svc *Service, clearCookie func(http.ResponseWriter)) *Handlers {
	return &Handlers{svc: svc, clearCookie: clearCookie}
}

type Middleware struct {
	Require   httpx.Middleware
	CSRF      httpx.Middleware
	RateLimit httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	read := r.Group("/account", mw.Require)
	read.GET("", h.me)

	write := r.Group("/account", mw.Require, mw.CSRF)
	write.PATCH("", h.update)
	write.POST("/email", mw.RateLimit(h.requestEmailChange))
	write.POST("/deactivate", mw.RateLimit(h.deactivate))

	// The confirmation link is opened without a session as often as with one.
	r.Group("/account").POST("/email/confirm", mw.RateLimit(h.confirmEmailChange))
}

func (h *Handlers) me(w http.ResponseWriter, r *http.Request) error {
	out, err := h.svc.Me(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) update(w http.ResponseWriter, r *http.Request) error {
	var body UpdateRequest
	if err := httpx.DecodeJSON(w, r, &body, 8<<10); err != nil {
		return err
	}
	out, err := h.svc.Update(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) requestEmailChange(w http.ResponseWriter, r *http.Request) error {
	var body EmailChangeRequest
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	if err := h.svc.RequestEmailChange(r.Context(), security.FromContext(r.Context()), body); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{
		"sent": true, "message": "Мы отправили ссылку на новый адрес. Адрес сменится, когда вы её откроете.",
	})
}

func (h *Handlers) confirmEmailChange(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Token string `json:"token"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 2<<10); err != nil {
		return err
	}
	if err := h.svc.ConfirmEmailChange(r.Context(), body.Token); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"changed": true})
}

func (h *Handlers) deactivate(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Password string `json:"password"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 2<<10); err != nil {
		return err
	}
	if err := h.svc.Deactivate(r.Context(), security.FromContext(r.Context()), body.Password); err != nil {
		return err
	}
	if h.clearCookie != nil {
		h.clearCookie(w)
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"deactivated": true})
}
