package auth

import (
	"errors"
	"net/http"
	"strings"
	"time"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/platform/cache"
	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/logx"
	"github.com/averix/api/internal/security"
)

// Middleware turns cookies into identities and enforces the request-level
// security checks.
type Middleware struct {
	store *Store
	cfg   *config.Config
	cache *cache.Cache
	audit *audit.Recorder
}

func NewMiddleware(store *Store, cfg *config.Config, c *cache.Cache, rec *audit.Recorder) *Middleware {
	return &Middleware{store: store, cfg: cfg, cache: c, audit: rec}
}

// Resolve attaches the caller's identity when a valid session cookie is
// present, and leaves the request anonymous otherwise.
//
// It never rejects: public endpoints need to run for anonymous visitors, and
// requiring authentication is a separate, explicit middleware. An invalid
// cookie is cleared so the browser stops sending it.
func (m *Middleware) Resolve() httpx.Middleware {
	return func(next httpx.Handler) httpx.Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			cookie, err := r.Cookie(m.cfg.Auth.CookieName)
			if err != nil || cookie.Value == "" {
				return next(w, r)
			}

			identity, err := m.store.ResolveSession(r.Context(), cookie.Value, m.cfg.Auth.SessionIdleTTL)
			if err != nil {
				if !errors.Is(err, ErrSessionInvalid) {
					logx.From(r.Context()).Error("session resolution failed", "error", err)
				}
				m.ClearCookie(w)
				return next(w, r)
			}

			ctx := security.WithIdentity(r.Context(), identity)
			ctx = logx.WithUserID(ctx, identity.UserID.String())
			ctx = logx.WithLogger(ctx, logx.From(ctx).With(
				"user_id", identity.UserID.String(),
				"role", string(identity.ActiveRole)))
			return next(w, r.WithContext(ctx))
		}
	}
}

// Require refuses anonymous callers.
func (m *Middleware) Require() httpx.Middleware {
	return func(next httpx.Handler) httpx.Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			id := security.FromContext(r.Context())
			if !id.Authenticated() {
				return httpx.ErrUnauthenticated
			}
			if id.Status != "active" {
				return httpx.Forbiddenf("account status is %q", id.Status)
			}
			return next(w, r)
		}
	}
}

// RequireRole refuses a caller whose session is not in one of the given roles.
func (m *Middleware) RequireRole(roles ...security.Role) httpx.Middleware {
	return func(next httpx.Handler) httpx.Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			id := security.FromContext(r.Context())
			if err := security.RequireRole(id, roles...); err != nil {
				m.audit.Denial(r.Context(), "endpoint", nil, err.Error())
				if !id.Authenticated() {
					return httpx.ErrUnauthenticated
				}
				return httpx.ErrForbidden.Wrap(err)
			}
			return next(w, r)
		}
	}
}

// RequirePermission refuses a caller whose active role lacks a capability.
func (m *Middleware) RequirePermission(p security.Permission) httpx.Middleware {
	return func(next httpx.Handler) httpx.Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			id := security.FromContext(r.Context())
			if err := security.RequirePermission(id, p); err != nil {
				m.audit.Denial(r.Context(), string(p), nil, err.Error())
				if !id.Authenticated() {
					return httpx.ErrUnauthenticated
				}
				return httpx.ErrForbidden.Wrap(err)
			}
			return next(w, r)
		}
	}
}

// RequireVerifiedEmail gates the actions where an unverified address would let
// someone act on the platform under an address they do not control: submitting
// proposals, publishing projects, being searchable.
func (m *Middleware) RequireVerifiedEmail() httpx.Middleware {
	return func(next httpx.Handler) httpx.Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			id := security.FromContext(r.Context())
			if !id.Authenticated() {
				return httpx.ErrUnauthenticated
			}
			if !id.EmailVerified {
				e := *httpx.ErrForbidden
				e.Code = "email_not_verified"
				e.Message = "Подтвердите адрес почты, чтобы продолжить. Мы отправили вам ссылку."
				return &e
			}
			return next(w, r)
		}
	}
}

// CSRF protects cookie-authenticated state changes with a double-submit token.
//
// The session's token must arrive in the X-CSRF-Token header. A cross-site form
// post can carry the cookie but cannot read the token to set the header, and a
// cross-origin fetch that could set the header is blocked by the CORS
// allow-list before it reaches this point.
func (m *Middleware) CSRF() httpx.Middleware {
	return func(next httpx.Handler) httpx.Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			switch r.Method {
			case http.MethodGet, http.MethodHead, http.MethodOptions:
				return next(w, r)
			}

			id := security.FromContext(r.Context())
			if !id.Authenticated() {
				// Nothing to forge against: an anonymous request carries no
				// authority, and the endpoint's own auth check will refuse it
				// if it needs one.
				return next(w, r)
			}

			supplied := r.Header.Get("X-CSRF-Token")
			if supplied == "" || !cryptox.ConstantTimeEquals(id.CSRFToken, supplied) {
				m.audit.Denial(r.Context(), "csrf", nil, "missing or mismatched CSRF token")
				return httpx.ErrCSRF
			}

			// Origin is checked as well where the browser sends it: belt and
			// braces against a token leaked into a page on another site.
			if origin := r.Header.Get("Origin"); origin != "" {
				if !m.originAllowed(origin) {
					m.audit.Denial(r.Context(), "csrf", nil, "request origin "+origin+" is not allowed")
					return httpx.ErrCSRF
				}
			}
			return next(w, r)
		}
	}
}

func (m *Middleware) originAllowed(origin string) bool {
	origin = strings.TrimRight(origin, "/")
	for _, allowed := range []string{m.cfg.AppURL, m.cfg.APIURL} {
		if strings.TrimRight(allowed, "/") == origin {
			return true
		}
	}
	return false
}

// RateLimit applies the sliding-window limiter, keyed by user when signed in
// and by address otherwise, so one noisy IP behind a NAT cannot exhaust the
// allowance of everyone sharing it.
func (m *Middleware) RateLimit(bucket string, limit int, window time.Duration) httpx.Middleware {
	return func(next httpx.Handler) httpx.Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			if m.cache == nil {
				return next(w, r)
			}
			subject := httpx.ClientIP(r.Context())
			if id := security.FromContext(r.Context()); id.Authenticated() {
				subject = "u:" + id.UserID.String()
			}
			if subject == "" {
				subject = "unknown"
			}

			allowance, err := m.cache.Allow(r.Context(), bucket, subject, limit, window)
			if err != nil {
				// The limiter failed open; say so loudly rather than silently
				// running unprotected.
				logx.From(r.Context()).Warn("rate limiter unavailable, allowing request",
					"bucket", bucket, "error", err)
			}
			if !allowance.Allowed {
				m.audit.RecordRequest(r.Context(), audit.Entry{
					Action: audit.ActionRateLimited, SubjectType: "endpoint",
					Outcome: audit.Denied,
					Detail:  "bucket " + bucket,
				})
				e := *httpx.ErrRateLimited
				e.RetryAfter = int(allowance.RetryAfter.Seconds()) + 1
				return &e
			}
			return next(w, r)
		}
	}
}

// RateLimitOnSuccess refuses a caller who is over the limit, but charges the
// window only when the handler succeeds.
//
// Used where the thing being limited is the outcome rather than the attempt:
// creating accounts, submitting proposals, publishing projects. Sign-in is
// deliberately not one of these — there, the failures are precisely what needs
// limiting.
func (m *Middleware) RateLimitOnSuccess(bucket string, limit int, window time.Duration) httpx.Middleware {
	return func(next httpx.Handler) httpx.Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			if m.cache == nil {
				return next(w, r)
			}
			subject := httpx.ClientIP(r.Context())
			if id := security.FromContext(r.Context()); id.Authenticated() {
				subject = "u:" + id.UserID.String()
			}
			if subject == "" {
				subject = "unknown"
			}

			allowance, err := m.cache.Peek(r.Context(), bucket, subject, limit, window)
			if err != nil {
				logx.From(r.Context()).Warn("rate limiter unavailable, allowing request",
					"bucket", bucket, "error", err)
			}
			if !allowance.Allowed {
				m.audit.RecordRequest(r.Context(), audit.Entry{
					Action: audit.ActionRateLimited, SubjectType: "endpoint",
					Outcome: audit.Denied, Detail: "bucket " + bucket,
				})
				e := *httpx.ErrRateLimited
				e.RetryAfter = int(allowance.RetryAfter.Seconds()) + 1
				return &e
			}

			if err := next(w, r); err != nil {
				return err
			}
			if consumeErr := m.cache.Consume(r.Context(), bucket, subject, window); consumeErr != nil {
				logx.From(r.Context()).Warn("could not charge rate limit window",
					"bucket", bucket, "error", consumeErr)
			}
			return nil
		}
	}
}

// ── Cookies ─────────────────────────────────────────────────────────────────

// SetCookie writes the session cookie.
//
// HttpOnly so script cannot read it, Secure everywhere but plain-HTTP
// localhost, and SameSite=Lax rather than Strict because the GitHub OAuth
// callback is a cross-site top-level navigation back into the app and Strict
// would drop the cookie on arrival.
func (m *Middleware) SetCookie(w http.ResponseWriter, token cryptox.SessionToken) {
	http.SetCookie(w, &http.Cookie{
		Name:     m.cfg.Auth.CookieName,
		Value:    token.String(),
		Path:     "/",
		Domain:   m.cfg.Auth.CookieDomain,
		MaxAge:   int(m.cfg.Auth.SessionTTL.Seconds()),
		HttpOnly: true,
		Secure:   m.cfg.SecureCookies(),
		SameSite: http.SameSiteLaxMode,
	})
}

func (m *Middleware) ClearCookie(w http.ResponseWriter) {
	http.SetCookie(w, &http.Cookie{
		Name:     m.cfg.Auth.CookieName,
		Value:    "",
		Path:     "/",
		Domain:   m.cfg.Auth.CookieDomain,
		MaxAge:   -1,
		HttpOnly: true,
		Secure:   m.cfg.SecureCookies(),
		SameSite: http.SameSiteLaxMode,
	})
}
