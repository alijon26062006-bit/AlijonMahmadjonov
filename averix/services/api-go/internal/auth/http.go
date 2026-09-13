package auth

import (
	"net/http"
	"net/url"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/logx"
	"github.com/averix/api/internal/security"
)

// Handlers exposes /api/v1/auth.
type Handlers struct {
	svc *Service
	mw  *Middleware
	// Optional: nil-safe, and absent on a deployment with no Google credentials.
	google *Google
	// Where to send a browser after an OAuth round trip.
	appURL string
}

func NewHandlers(svc *Service, mw *Middleware, google *Google, appURL string) *Handlers {
	return &Handlers{svc: svc, mw: mw, google: google, appURL: appURL}
}

// Register mounts the routes. The limits differ per endpoint because the risk
// does: credential stuffing hammers sign-in, and enumeration hammers the
// availability check.
func (h *Handlers) Register(r *httpx.Router) {
	pub := r.Group("/auth")

	// What the sign-in screen may offer. A button for a provider this
	// deployment has no credentials for is never rendered.
	pub.GET("/providers", h.providers)
	if h.google.Configured() {
		pub.GET("/google/start", h.mw.RateLimit("google_start", 20, time.Hour)(h.googleStart))
		pub.GET("/google/callback", h.googleCallback)
	}

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
	// The screen right after registration. Separate from role/add because it
	// answers a different question — "кто вы здесь", once — and because it is
	// the one thing a session without a role is allowed to do.
	authed.POST("/role/choose", h.chooseRole)
	authed.POST("/password/change", h.mw.RateLimit("password_change", 5, time.Hour)(h.changePassword))
	authed.POST("/email/resend", h.mw.RateLimit("email_resend", 3, time.Hour)(h.resendVerification))
	authed.GET("/sessions", h.listSessions)
	authed.DELETE("/sessions/{id}", h.revokeSession)
}

// sessionResponse is the shape the web app's auth store consumes. It carries
// the CSRF token because the client needs it for every subsequent mutation,
// and permissions so the UI can hide actions the caller could not perform.
type sessionResponse struct {
	Authenticated bool   `json:"authenticated"`
	UserID        string `json:"user_id,omitempty"`
	Username      string `json:"username,omitempty"`
	Email         string `json:"email,omitempty"`
	ActiveRole    string `json:"active_role,omitempty"`
	// Always present, even when empty. An account that has not chosen a side
	// yet holds no roles, and a missing field rather than an empty list is how
	// a client ends up calling .includes on undefined.
	Roles            []string `json:"roles"`
	EmailVerified    bool     `json:"email_verified"`
	IdentityVerified bool     `json:"identity_verified"`
	CSRFToken        string   `json:"csrf_token,omitempty"`
	Permissions      []string `json:"permissions"`
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

// providers is public: the sign-in page asks before anyone is signed in.
func (h *Handlers) providers(w http.ResponseWriter, r *http.Request) error {
	return httpx.JSON(w, http.StatusOK, map[string]any{
		"password": true,
		"google":   h.google.Configured(),
	})
}

func (h *Handlers) googleStart(w http.ResponseWriter, r *http.Request) error {
	target, err := h.google.Start(r.Context(), r.URL.Query().Get("next"))
	if err != nil {
		return httpx.Internalf(err, "start google sign-in")
	}
	http.Redirect(w, r, target, http.StatusFound)
	return nil
}

// googleCallback is the browser coming back from Google. It answers with a
// redirect in every case, including failure: a person who cancelled at Google
// should land on the sign-in page with a word about it, not on a JSON error.
func (h *Handlers) googleCallback(w http.ResponseWriter, r *http.Request) error {
	query := r.URL.Query()
	if reason := query.Get("error"); reason != "" {
		http.Redirect(w, r, h.appURL+"/login?google="+url.QueryEscape(reason), http.StatusFound)
		return nil
	}

	result, destination, err := h.google.Callback(r.Context(),
		query.Get("code"), query.Get("state"), r.UserAgent(), httpx.ClientIP(r.Context()))
	if err != nil {
		logx.From(r.Context()).Warn("google sign-in failed", "error", err)
		http.Redirect(w, r, h.appURL+"/login?google=failed", http.StatusFound)
		return nil
	}

	h.mw.SetCookie(w, result.Token)
	// Where to land: the two cards when there is no role yet, otherwise where
	// they were going before they were asked to sign in.
	if result.Identity.ActiveRole == security.RolePending {
		destination = "/welcome"
	} else if destination == "" || destination == "/" {
		destination = "/dashboard"
		if result.Identity.ActiveRole == security.RoleDeveloper {
			destination = "/feed"
		}
	}
	http.Redirect(w, r, h.appURL+destination, http.StatusFound)
	return nil
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

// chooseRole turns a pending account into a client or a freelancer.
func (h *Handlers) chooseRole(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Role string `json:"role"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 1<<10); err != nil {
		return err
	}
	updated, err := h.svc.ChooseRole(r.Context(), security.FromContext(r.Context()), body.Role)
	if err != nil {
		return err
	}
	// Marked as new so the web app routes into onboarding rather than into a
	// dashboard that has nothing on it yet.
	return httpx.JSON(w, http.StatusOK, toSessionResponse(updated, true))
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
