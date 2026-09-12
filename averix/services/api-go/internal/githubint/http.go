package githubint

import (
	"net/http"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

type Handlers struct{ svc *Service }

func NewHandlers(svc *Service) *Handlers { return &Handlers{svc: svc} }

type Middleware struct {
	Require       httpx.Middleware
	CSRF          httpx.Middleware
	RequireDev    httpx.Middleware
	RateLimitSync httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	g := r.Group("/github", mw.Require, mw.RequireDev)
	g.GET("/status", h.status)
	g.GET("/portfolio-candidates", h.candidates)

	write := r.Group("/github", mw.Require, mw.RequireDev, mw.CSRF)
	write.POST("/connect", h.connect)
	write.POST("/sync", mw.RateLimitSync(h.sync))
	write.DELETE("/connection", h.disconnect)

	// The callback is a top-level browser navigation back from GitHub, so it
	// is a GET, carries no CSRF token, and redirects rather than returning
	// JSON. Its safety rests on the single-use state and on the fact that it
	// only ever links an account to the user the state names.
	r.GET("/github/callback", h.callback)
}

func (h *Handlers) status(w http.ResponseWriter, r *http.Request) error {
	status, err := h.svc.Status(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, status)
}

func (h *Handlers) connect(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		RedirectTo  string `json:"redirect_to"`
		WantPrivate bool   `json:"want_private_access"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 2<<10); err != nil {
		return err
	}

	url, err := h.svc.StartConnect(r.Context(), security.FromContext(r.Context()),
		body.RedirectTo, body.WantPrivate)
	if err != nil {
		return err
	}
	// The URL is returned rather than a redirect issued: the web app opens it
	// itself, which keeps the fetch/redirect semantics simple and lets the
	// client show a "taking you to GitHub" state.
	return httpx.JSON(w, http.StatusOK, map[string]any{"authorize_url": url})
}

func (h *Handlers) callback(w http.ResponseWriter, r *http.Request) error {
	query := r.URL.Query()

	// GitHub reports a user who declined with an error parameter rather than a
	// failed request; that is not an error to show as one.
	if reason := query.Get("error"); reason != "" {
		http.Redirect(w, r,
			SafeRedirect(h.svc.cfg.AppURL, "/settings/github?github=cancelled"),
			http.StatusSeeOther)
		return nil
	}

	result, err := h.svc.Callback(r.Context(), query.Get("code"), query.Get("state"))
	if err != nil {
		// The browser is mid-navigation; a JSON error body would be shown as
		// raw text. The app's own page explains what happened.
		apiErr := httpx.AsError(err)
		http.Redirect(w, r,
			SafeRedirect(h.svc.cfg.AppURL, "/settings/github?github=failed&reason="+apiErr.Code),
			http.StatusSeeOther)
		return nil
	}

	destination := result.RedirectTo
	if result.PrivateGranted {
		destination += queryJoin(destination) + "github=private_granted"
	} else {
		destination += queryJoin(destination) + "github=connected"
	}
	http.Redirect(w, r, destination, http.StatusSeeOther)
	return nil
}

func (h *Handlers) sync(w http.ResponseWriter, r *http.Request) error {
	analysis, err := h.svc.Sync(r.Context(), security.FromContext(r.Context()), "manual")
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, analysis)
}

func (h *Handlers) disconnect(w http.ResponseWriter, r *http.Request) error {
	if err := h.svc.Disconnect(r.Context(), security.FromContext(r.Context())); err != nil {
		return err
	}
	return httpx.NoContent(w)
}

func (h *Handlers) candidates(w http.ResponseWriter, r *http.Request) error {
	candidates, err := h.svc.PortfolioCandidates(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, candidates)
}

func queryJoin(url string) string {
	for i := 0; i < len(url); i++ {
		if url[i] == '?' {
			return "&"
		}
	}
	return "?"
}
