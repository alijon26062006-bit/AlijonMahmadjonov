package auth

import (
	"net/http"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

// Handlers exposes /api/v1/auth.
type Handlers struct {
	svc *Service
	mw  *Middleware
}

func NewHandlers(svc *Service, mw *Middleware) *Handlers {
	return &Handlers{svc: svc, mw: mw}
}

// Register mounts the routes. The limits differ per endpoint because the risk
// does: credential stuffing hammers sign-in, and enumeration hammers the
// availability check.
func (h *Handlers) Register(r *httpx.Router) {
	pub := r.Group("/auth")

	pub.POST("/register", h.mw.RateLimitOnSuccess("register", 5, time.Hour)(h.register))
	pub.POST("/login", h.mw.RateLimit("login", 10, 10*time.Minute)(h.login))
	pub.POST("/password/forgot", h.mw.RateLimit("password_forgot", 5, time.Hour)(h.forgotPassword))
	pub.POST("/password/reset", h.mw.RateLimit("password_reset", 10, time.Hour)(h.resetPassword))
	pub.POST("/email/verify", h.mw.RateLimit("email_verify", 20, time.Hour)(h.verifyEmail))
	pub.GET("/availability", h.mw.RateLimit("availability", 60, time.Minute)(h.availability))

	// GET so a signed-out visit returns a clean anonymous answer rather than
	// a 401 the web app has to special-case on first load.
	pub.GET("/session", h.session)

	authed := r.Group("/auth", h.mw.Require(), h.mw.CSRF())
	authed.POST("/logout", h.logout)
	authed.POST("/logout-everywhere", h.logoutEverywhere)
	authed.POST("/role/switch", h.switchRole)
	authed.POST("/role/add", h.addRole)
	authed.POST("/password/change", h.mw.RateLimit("password_change", 5, time.Hour)(h.changePassword))
	authed.POST("/email/resend", h.mw.RateLimit("email_resend", 3, time.Hour)(h.resendVerification))
	authed.GET("/sessions", h.listSessions)
	authed.DELETE("/sessions/{id}", h.revokeSession)
}

// sessionResponse is the shape the web app's auth store consumes. It carries
// the CSRF token because the client needs it for every subsequent mutation,
// and permissions so the UI can hide actions the caller could not perform.
type sessionResponse struct {
	Authenticated    bool     `json:"authenticated"`
	UserID           string   `json:"user_id,omitempty"`
	Username         string   `json:"username,omitempty"`
	Email            string   `json:"email,omitempty"`
	ActiveRole       string   `json:"active_role,omitempty"`
	Roles            []string `json:"roles,omitempty"`
	EmailVerified    bool     `json:"email_verified"`
	IdentityVerified bool     `json:"identity_verified"`
	CSRFToken        string   `json:"csrf_token,omitempty"`
	Permissions      []string `json:"permissions,omitempty"`
	IsNew            bool     `json:"is_new,omitempty"`
}

func toSessionResponse(id *security.Identity, isNew bool) sessionResponse {
	if !id.Authenticated() {
		return sessionResponse{Authenticated: false}
	}
	roles := make([]string, 0, len(id.Roles))
	for _, r := range id.Roles {
		roles = append(roles, string(r))
	}
	return sessionResponse{
		Authenticated:    true,
		UserID:           id.UserID.String(),
		Username:         id.Username,
		Email:            id.Email,
		ActiveRole:       string(id.ActiveRole),
		Roles:            roles,
		EmailVerified:    id.EmailVerified,
		IdentityVerified: id.IdentityVerified,
		CSRFToken:        id.CSRFToken,
		Permissions:      id.Permissions(),
		IsNew:            isNew,
	}
}

func (h *Handlers) register(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Email       string `json:"email"`
		Username    string `json:"username"`
		Password    string `json:"password"`
		FullName    string `json:"full_name"`
		Role        string `json:"role"`
		Locale      string `json:"locale"`
		Timezone    string `json:"timezone"`
		CountryCode string `json:"country_code"`
		AcceptTerms bool   `json:"accept_terms"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 8<<10); err != nil {
		return err
	}

	result, err := h.svc.Register(r.Context(), RegisterInput{
		Email:       body.Email,
		Username:    body.Username,
		Password:    body.Password,
		FullName:    body.FullName,
		Role:        body.Role,
		Locale:      body.Locale,
		Timezone:    body.Timezone,
		CountryCode: body.CountryCode,
		AcceptTerms: body.AcceptTerms,
	}, r.UserAgent(), httpx.ClientIP(r.Context()))
	if err != nil {
		return err
	}

	h.mw.SetCookie(w, result.Token)
	return httpx.JSON(w, http.StatusCreated, toSessionResponse(result.Identity, true))
}

func (h *Handlers) login(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Email    string `json:"email"`
		Password string `json:"password"`
		Role     string `json:"role"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}

	result, err := h.svc.Login(r.Context(), LoginInput{
		Email:    body.Email,
		Password: body.Password,
		Role:     body.Role,
	}, r.UserAgent(), httpx.ClientIP(r.Context()))
	if err != nil {
		return err
	}

	h.mw.SetCookie(w, result.Token)
	return httpx.JSON(w, http.StatusOK, toSessionResponse(result.Identity, false))
}

// session answers "who am I". The route is public so that a page can ask
// before it knows, and the answer for a visitor without a session is 401 —
// not 200 carrying an identity of zero values. Answering 200 tells a client
// it is signed in as a user with no id, which is how a signed-out visitor
// ends up looking at a signed-in screen where every request fails.
func (h *Handlers) session(w http.ResponseWriter, r *http.Request) error {
	id := security.FromContext(r.Context())
	if !id.Authenticated() {
		return httpx.ErrUnauthenticated
	}
	return httpx.JSON(w, http.StatusOK, toSessionResponse(id, false))
}

func (h *Handlers) logout(w http.ResponseWriter, r *http.Request) error {
	if err := h.svc.Logout(r.Context(), security.FromContext(r.Context())); err != nil {
		return err
	}
	h.mw.ClearCookie(w)
	return httpx.JSON(w, http.StatusOK, map[string]any{"signed_out": true})
}

func (h *Handlers) logoutEverywhere(w http.ResponseWriter, r *http.Request) error {
	n, err := h.svc.LogoutEverywhere(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	h.mw.ClearCookie(w)
	return httpx.JSON(w, http.StatusOK, map[string]any{"signed_out": true, "sessions_ended": n})
}

func (h *Handlers) switchRole(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Role string `json:"role"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 1<<10); err != nil {
		return err
	}
	id := security.FromContext(r.Context())
	csrf, err := h.svc.SwitchRole(r.Context(), id, body.Role)
	if err != nil {
		return err
	}
	// The identity in this request's context still carries the old role, so
	// the response is built from the new values directly.
	updated := *id
	updated.ActiveRole = security.Role(body.Role)
	updated.CSRFToken = csrf
	return httpx.JSON(w, http.StatusOK, toSessionResponse(&updated, false))
}

func (h *Handlers) addRole(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Role string `json:"role"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 1<<10); err != nil {
		return err
	}
	if err := h.svc.AddRole(r.Context(), security.FromContext(r.Context()), body.Role); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"role_added": body.Role})
}

func (h *Handlers) forgotPassword(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Email string `json:"email"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 1<<10); err != nil {
		return err
	}
	if err := h.svc.RequestPasswordReset(r.Context(), body.Email, httpx.ClientIP(r.Context())); err != nil {
		return err
	}
	// Identical for a known and an unknown address, by design.
	return httpx.JSON(w, http.StatusOK, map[string]any{
		"message": "If an account exists for that address, we've sent a reset link.",
	})
}

func (h *Handlers) resetPassword(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Token    string `json:"token"`
		Password string `json:"password"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	if err := h.svc.ResetPassword(r.Context(),
		ResetPasswordInput{Token: body.Token, Password: body.Password},
		httpx.ClientIP(r.Context())); err != nil {
		return err
	}
	h.mw.ClearCookie(w)
	return httpx.JSON(w, http.StatusOK, map[string]any{
		"message": "Your password has been changed. Please sign in.",
	})
}

func (h *Handlers) changePassword(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		CurrentPassword string `json:"current_password"`
		NewPassword     string `json:"new_password"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	if err := h.svc.ChangePassword(r.Context(), security.FromContext(r.Context()),
		ChangePasswordInput{CurrentPassword: body.CurrentPassword, NewPassword: body.NewPassword}); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{
		"message": "Your password has been changed. Other devices have been signed out.",
	})
}

func (h *Handlers) verifyEmail(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Token string `json:"token"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 2<<10); err != nil {
		return err
	}
	if err := h.svc.VerifyEmail(r.Context(), body.Token); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"verified": true})
}

func (h *Handlers) resendVerification(w http.ResponseWriter, r *http.Request) error {
	if err := h.svc.ResendVerification(r.Context(), security.FromContext(r.Context())); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{
		"message": "We've sent a new confirmation link to your email address.",
	})
}

func (h *Handlers) availability(w http.ResponseWriter, r *http.Request) error {
	field := r.URL.Query().Get("field")
	value := r.URL.Query().Get("value")
	available, reason, err := h.svc.Availability(r.Context(), field, value)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{
		"field":     field,
		"available": available,
		"reason":    reason,
	})
}

func (h *Handlers) listSessions(w http.ResponseWriter, r *http.Request) error {
	id := security.FromContext(r.Context())
	sessions, err := h.svc.Sessions(r.Context(), id)
	if err != nil {
		return err
	}
	type row struct {
		ID        string    `json:"id"`
		Current   bool      `json:"current"`
		Role      string    `json:"role"`
		UserAgent string    `json:"user_agent,omitempty"`
		IP        string    `json:"ip,omitempty"`
		LastUsed  time.Time `json:"last_used_at"`
		Created   time.Time `json:"created_at"`
		Expires   time.Time `json:"expires_at"`
	}
	out := make([]row, 0, len(sessions))
	for _, s := range sessions {
		out = append(out, row{
			ID:        s.ID.String(),
			Current:   s.ID == id.SessionID,
			Role:      string(s.ActiveRole),
			UserAgent: s.UserAgent,
			IP:        s.IP,
			LastUsed:  s.LastUsedAt,
			Created:   s.CreatedAt,
			Expires:   s.ExpiresAt,
		})
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) revokeSession(w http.ResponseWriter, r *http.Request) error {
	sessionID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	id := security.FromContext(r.Context())
	if err := h.svc.RevokeSession(r.Context(), id, sessionID); err != nil {
		return err
	}
	if sessionID == id.SessionID {
		h.mw.ClearCookie(w)
	}
	return httpx.NoContent(w)
}
