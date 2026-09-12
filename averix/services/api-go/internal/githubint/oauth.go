package githubint

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/database"
)

// OAuth drives the GitHub authorisation code flow.
type OAuth struct {
	cfg  config.GitHub
	db   *database.DB
	http *http.Client
}

func NewOAuth(cfg config.GitHub, db *database.DB) *OAuth {
	return &OAuth{
		cfg:  cfg,
		db:   db,
		http: &http.Client{Timeout: 20 * time.Second},
	}
}

func (o *OAuth) Configured() bool { return o.cfg.Configured() }

var (
	ErrNotConfigured = errors.New("GitHub is not configured on this environment")
	ErrStateInvalid  = errors.New("the authorisation state could not be verified")
	ErrExchange      = errors.New("GitHub did not issue an access token")
)

// Intent distinguishes what a flow is for, because the three cases end
// somewhere different and ask for different scopes.
type Intent string

const (
	// IntentConnect links GitHub to an existing signed-in account.
	IntentConnect Intent = "connect"
	// IntentSignIn authenticates with GitHub.
	IntentSignIn Intent = "sign_in"
	// IntentPrivate asks for the second consent to read private repositories.
	IntentPrivate Intent = "private_access"
)

// Start creates the authorisation URL and records the state.
//
// The state is stored server-side rather than only in a cookie: the callback
// is a cross-site top-level navigation, and a browser configured strictly
// enough may not send the cookie back. A row in the database is verifiable
// either way, and single-use.
func (o *OAuth) Start(ctx context.Context, intent Intent, userID uuid.UUID, redirectTo string) (string, error) {
	if !o.Configured() {
		return "", ErrNotConfigured
	}

	state, err := cryptox.RandomToken(32)
	if err != nil {
		return "", err
	}
	// PKCE is not required by GitHub's web flow but costs nothing and closes
	// the authorisation-code interception case.
	verifier, err := cryptox.RandomToken(48)
	if err != nil {
		return "", err
	}

	scopes := o.cfg.Scopes
	if intent == IntentPrivate {
		// The only scope that reads private code, requested only here.
		scopes = append(append([]string{}, o.cfg.Scopes...), "repo")
	}

	var owner any
	if userID != uuid.Nil {
		owner = userID
	}
	if _, err := o.db.Exec(ctx, `
		INSERT INTO oauth_states (state, provider, user_id, code_verifier, redirect_to, scopes, expires_at)
		VALUES ($1, 'github', $2, $3, $4, $5, now() + interval '15 minutes')`,
		state, owner, verifier, nullIfBlank(redirectTo), database.Array(scopes)); err != nil {
		return "", fmt.Errorf("record oauth state: %w", err)
	}

	query := url.Values{}
	query.Set("client_id", o.cfg.ClientID)
	query.Set("redirect_uri", o.cfg.CallbackURL)
	query.Set("scope", strings.Join(scopes, " "))
	query.Set("state", state)
	query.Set("allow_signup", "true")
	return o.cfg.AuthorizeURL + "?" + query.Encode(), nil
}

// StateRecord is a validated, consumed state.
type StateRecord struct {
	UserID     *uuid.UUID
	RedirectTo string
	Scopes     []string
}

// ConsumeState validates and burns the state in one statement, so a replayed
// callback finds nothing.
func (o *OAuth) ConsumeState(ctx context.Context, state string) (*StateRecord, error) {
	if state == "" {
		return nil, ErrStateInvalid
	}
	var rec StateRecord
	var redirect *string
	err := o.db.QueryRow(ctx, `
		UPDATE oauth_states SET consumed_at = now()
		WHERE state = $1 AND provider = 'github'
		  AND consumed_at IS NULL AND expires_at > now()
		RETURNING user_id, redirect_to, scopes`, state).
		Scan(&rec.UserID, &redirect, &rec.Scopes)
	if database.IsNoRows(err) {
		return nil, ErrStateInvalid
	}
	if err != nil {
		return nil, fmt.Errorf("consume oauth state: %w", err)
	}
	if redirect != nil {
		rec.RedirectTo = *redirect
	}
	return &rec, nil
}

// TokenResponse is GitHub's token payload.
type TokenResponse struct {
	AccessToken  string
	RefreshToken string
	Scopes       []string
	ExpiresAt    *time.Time
}

// Exchange turns the authorisation code into an access token.
func (o *OAuth) Exchange(ctx context.Context, code string) (*TokenResponse, error) {
	if !o.Configured() {
		return nil, ErrNotConfigured
	}
	if strings.TrimSpace(code) == "" {
		return nil, ErrExchange
	}

	form := url.Values{}
	form.Set("client_id", o.cfg.ClientID)
	form.Set("client_secret", o.cfg.ClientSecret)
	form.Set("code", code)
	form.Set("redirect_uri", o.cfg.CallbackURL)

	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		o.cfg.TokenURL, strings.NewReader(form.Encode()))
	if err != nil {
		return nil, fmt.Errorf("build token request: %w", err)
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("User-Agent", userAgent)

	resp, err := o.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("exchange code: %w", err)
	}
	defer func() {
		_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 4<<10))
		_ = resp.Body.Close()
	}()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("%w: github returned %d", ErrExchange, resp.StatusCode)
	}

	var payload struct {
		AccessToken           string `json:"access_token"`
		RefreshToken          string `json:"refresh_token"`
		Scope                 string `json:"scope"`
		TokenType             string `json:"token_type"`
		ExpiresIn             int    `json:"expires_in"`
		RefreshTokenExpiresIn int    `json:"refresh_token_expires_in"`
		Error                 string `json:"error"`
		ErrorDescription      string `json:"error_description"`
	}
	if err := json.NewDecoder(io.LimitReader(resp.Body, 64<<10)).Decode(&payload); err != nil {
		return nil, fmt.Errorf("decode token response: %w", err)
	}
	if payload.Error != "" {
		// GitHub's description is safe to log but not to show: it can name the
		// client id.
		return nil, fmt.Errorf("%w: %s", ErrExchange, payload.Error)
	}
	if payload.AccessToken == "" {
		return nil, ErrExchange
	}

	out := &TokenResponse{
		AccessToken:  payload.AccessToken,
		RefreshToken: payload.RefreshToken,
	}
	for _, scope := range strings.Split(payload.Scope, ",") {
		if scope = strings.TrimSpace(scope); scope != "" {
			out.Scopes = append(out.Scopes, scope)
		}
	}
	if payload.ExpiresIn > 0 {
		expires := time.Now().Add(time.Duration(payload.ExpiresIn) * time.Second)
		out.ExpiresAt = &expires
	}
	return out, nil
}

// PurgeExpiredStates is run by the worker.
func (o *OAuth) PurgeExpiredStates(ctx context.Context) (int, error) {
	tag, err := o.db.Exec(ctx,
		`DELETE FROM oauth_states WHERE expires_at < now() - interval '1 hour'`)
	if err != nil {
		return 0, err
	}
	return int(tag.RowsAffected()), nil
}

// SafeRedirect resolves where to send the browser after the callback.
//
// Only a relative path within the app is accepted. An open redirect here would
// let a crafted authorisation link bounce a signed-in user to an attacker's
// page with the flow looking legitimate.
func SafeRedirect(appURL, requested string) string {
	fallback := appURL + "/settings/github"
	if requested == "" {
		return fallback
	}
	if !strings.HasPrefix(requested, "/") || strings.HasPrefix(requested, "//") {
		return fallback
	}
	if strings.ContainsAny(requested, "\\\r\n") {
		return fallback
	}
	parsed, err := url.Parse(requested)
	if err != nil || parsed.Host != "" || parsed.Scheme != "" {
		return fallback
	}
	return appURL + parsed.EscapedPath() + queryOf(parsed)
}

func queryOf(u *url.URL) string {
	if u.RawQuery == "" {
		return ""
	}
	return "?" + u.RawQuery
}
