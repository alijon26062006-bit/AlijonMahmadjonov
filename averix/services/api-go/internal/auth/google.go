// Sign in with Google.
//
// The point of this file is that a person can start using the marketplace
// without inventing another password. Everything it does is the ordinary
// authorisation-code flow; what matters is what it refuses to do:
//
//   - it will not trust an email address Google itself has not verified,
//     because that address is what links this login to an existing account;
//   - it links by Google's stable subject id rather than by the address, so a
//     person who changes their Google email keeps their account, and an
//     address that changes hands does not inherit one;
//   - it creates accounts with no role, like ordinary registration does, and
//     sends the person to the same two cards;
//   - without a client id and secret it does nothing at all, and the sign-in
//     page does not show a button. A button that cannot work is worse than no
//     button.
package auth

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

type Google struct {
	cfg   config.Google
	db    *database.DB
	store *Store
	svc   *Service
	http  *http.Client
}

func NewGoogle(cfg config.Google, db *database.DB, store *Store, svc *Service) *Google {
	return &Google{
		cfg: cfg, db: db, store: store, svc: svc,
		http: &http.Client{Timeout: 15 * time.Second},
	}
}

func (g *Google) Configured() bool { return g != nil && g.cfg.Configured() }

var errGoogleNotConfigured = errors.New("google sign-in is not configured")

// Start records a single-use state and returns the address to send the browser
// to. The state lives in the database rather than in a cookie: the callback is
// a cross-site top-level navigation, and a strict browser may not send the
// cookie back.
func (g *Google) Start(ctx context.Context, redirectTo string) (string, error) {
	if !g.Configured() {
		return "", errGoogleNotConfigured
	}
	state, err := cryptox.RandomToken(32)
	if err != nil {
		return "", err
	}
	if _, err := g.db.Exec(ctx, `
		INSERT INTO oauth_states (state, provider, redirect_to, expires_at)
		VALUES ($1, 'google', $2, now() + interval '15 minutes')`,
		state, nullIfBlank(safeRedirect(redirectTo))); err != nil {
		return "", fmt.Errorf("record oauth state: %w", err)
	}

	query := url.Values{}
	query.Set("client_id", g.cfg.ClientID)
	query.Set("redirect_uri", g.cfg.CallbackURL)
	query.Set("response_type", "code")
	query.Set("scope", "openid email profile")
	query.Set("state", state)
	// Ask for the account chooser rather than silently reusing whichever
	// Google account the browser happens to be signed into.
	query.Set("prompt", "select_account")
	return g.cfg.AuthorizeURL + "?" + query.Encode(), nil
}

// safeRedirect keeps a destination inside this site. Anything else — a scheme,
// a host, a protocol-relative "//evil" — is dropped rather than corrected.
func safeRedirect(path string) string {
	path = strings.TrimSpace(path)
	if !strings.HasPrefix(path, "/") || strings.HasPrefix(path, "//") || strings.Contains(path, "\\") {
		return ""
	}
	if len(path) > 300 {
		return ""
	}
	return path
}

type googleProfile struct {
	Sub           string `json:"sub"`
	Email         string `json:"email"`
	EmailVerified bool   `json:"email_verified"`
	Name          string `json:"name"`
	GivenName     string `json:"given_name"`
	Locale        string `json:"locale"`
}

// Callback finishes the flow and returns a session, plus where to send the
// browser next.
func (g *Google) Callback(ctx context.Context, code, state, userAgent, ip string) (*AuthResult, string, error) {
	if !g.Configured() {
		return nil, "", errGoogleNotConfigured
	}

	var redirectTo *string
	err := g.db.QueryRow(ctx, `
		UPDATE oauth_states SET consumed_at = now()
		WHERE state = $1 AND provider = 'google'
		  AND consumed_at IS NULL AND expires_at > now()
		RETURNING redirect_to`, state).Scan(&redirectTo)
	if database.IsNoRows(err) {
		return nil, "", httpx.ErrForbidden.Wrap(errors.New("the sign-in link has expired or was already used"))
	}
	if err != nil {
		return nil, "", httpx.Internalf(err, "consume oauth state")
	}

	profile, err := g.exchange(ctx, code)
	if err != nil {
		return nil, "", err
	}
	// Google says whether it has verified this address. If it has not, the
	// address proves nothing and must not be used to find an account.
	if profile.Sub == "" || profile.Email == "" || !profile.EmailVerified {
		return nil, "", httpx.ErrForbidden.Wrap(errors.New("google did not confirm the address"))
	}

	account, err := g.accountFor(ctx, profile)
	if err != nil {
		return nil, "", err
	}

	switch account.Status {
	case "suspended", "deactivated":
		e := *httpx.ErrForbidden
		e.Code = "account_" + account.Status
		e.Message = "Этот аккаунт недоступен."
		return nil, "", &e
	}

	role := security.RolePending
	if len(account.Roles) > 0 {
		if role, err = g.svc.resolveLoginRole(account, ""); err != nil {
			return nil, "", err
		}
	}
	result, err := g.svc.issueSession(ctx, account, role, userAgent, ip)
	if err != nil {
		return nil, "", err
	}
	g.svc.audit.Record(ctx, audit.Entry{
		ActorID: &account.ID, ActorRole: string(role),
		Action: audit.ActionLogin, SubjectType: "user", SubjectID: &account.ID,
		IP: ip, UserAgent: userAgent, Detail: "google",
	})

	destination := "/"
	if redirectTo != nil {
		destination = *redirectTo
	}
	return result, destination, nil
}

// exchange turns the one-time code into a profile. The access token is used
// once, here, and never stored: this integration signs people in, it does not
// read anything of theirs afterwards.
func (g *Google) exchange(ctx context.Context, code string) (*googleProfile, error) {
	form := url.Values{}
	form.Set("code", code)
	form.Set("client_id", g.cfg.ClientID)
	form.Set("client_secret", g.cfg.ClientSecret)
	form.Set("redirect_uri", g.cfg.CallbackURL)
	form.Set("grant_type", "authorization_code")

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, g.cfg.TokenURL,
		strings.NewReader(form.Encode()))
	if err != nil {
		return nil, httpx.Internalf(err, "build token request")
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Accept", "application/json")

	resp, err := g.http.Do(req)
	if err != nil {
		// The secret is in the body of that request; the error is never passed
		// through in case a future Go version starts quoting it.
		return nil, httpx.Internalf(errors.New("token request failed"), "exchange google code")
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return nil, httpx.ErrForbidden.Wrap(fmt.Errorf("google refused the code (%d)", resp.StatusCode))
	}
	var token struct {
		AccessToken string `json:"access_token"`
	}
	if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&token); err != nil || token.AccessToken == "" {
		return nil, httpx.ErrForbidden.Wrap(errors.New("google issued no access token"))
	}

	info, err := http.NewRequestWithContext(ctx, http.MethodGet, g.cfg.UserInfoURL, nil)
	if err != nil {
		return nil, httpx.Internalf(err, "build userinfo request")
	}
	info.Header.Set("Authorization", "Bearer "+token.AccessToken)
	info.Header.Set("Accept", "application/json")

	profileResp, err := g.http.Do(info)
	if err != nil {
		return nil, httpx.Internalf(errors.New("userinfo request failed"), "read google profile")
	}
	defer profileResp.Body.Close()
	if profileResp.StatusCode >= 300 {
		return nil, httpx.ErrForbidden.Wrap(fmt.Errorf("google refused the profile request (%d)", profileResp.StatusCode))
	}
	var profile googleProfile
	if err := json.NewDecoder(io.LimitReader(profileResp.Body, 1<<20)).Decode(&profile); err != nil {
		return nil, httpx.ErrForbidden.Wrap(errors.New("google returned a profile we could not read"))
	}
	return &profile, nil
}

// accountFor finds the account this Google identity belongs to, or makes one.
func (g *Google) accountFor(ctx context.Context, profile *googleProfile) (*Account, error) {
	email := strings.ToLower(strings.TrimSpace(profile.Email))

	// 1. The stable subject id. This is the link that survives an address
	//    change at Google.
	var id uuid.UUID
	err := g.db.QueryRow(ctx,
		`SELECT id FROM users WHERE google_sub = $1 AND deleted_at IS NULL`, profile.Sub).Scan(&id)
	if err == nil {
		return g.store.AccountByID(ctx, id)
	}
	if !database.IsNoRows(err) {
		return nil, httpx.Internalf(err, "look up google account")
	}

	// 2. An existing account with the same verified address: the same person
	//    who signed up with a password. Link the two rather than refuse.
	existing, err := g.store.AccountByEmail(ctx, email)
	switch {
	case err == nil:
		if _, err := g.db.Exec(ctx,
			`UPDATE users SET google_sub = $2, email_verified_at = coalesce(email_verified_at, now())
			 WHERE id = $1`, existing.ID, profile.Sub); err != nil {
			return nil, httpx.Internalf(err, "link google account")
		}
		return g.store.AccountByID(ctx, existing.ID)
	case !errors.Is(err, ErrNotFound):
		return nil, httpx.Internalf(err, "look up account by email")
	}

	// 3. Nobody yet. Create the account with no role — the next screen asks.
	username, err := g.freeUsername(ctx, email)
	if err != nil {
		return nil, err
	}
	name := strings.TrimSpace(profile.Name)
	if name == "" {
		name = strings.TrimSpace(profile.GivenName)
	}
	if name == "" {
		name = username
	}

	account, err := g.store.CreateAccount(ctx, NewAccount{
		Email:    email,
		Username: username,
		FullName: name,
		// No password: this account signs in with Google. One can be set later
		// from settings, which is what makes the account usable without it.
		PasswordHash: "",
		Role:         "",
		Locale:       "ru",
		Timezone:     "UTC",
	})
	if err != nil {
		return nil, httpx.Internalf(err, "create account from google")
	}
	if _, err := g.db.Exec(ctx,
		`UPDATE users SET google_sub = $2, email_verified_at = now() WHERE id = $1`,
		account.ID, profile.Sub); err != nil {
		return nil, httpx.Internalf(err, "record google subject")
	}
	return g.store.AccountByID(ctx, account.ID)
}

var notUsernameChars = regexp.MustCompile(`[^a-z0-9_-]+`)

// freeUsername makes a username out of the address and, if it is taken, adds
// digits until it is not. The person can change it later; what matters here is
// that signing in with Google never stops to ask for one.
func (g *Google) freeUsername(ctx context.Context, email string) (string, error) {
	local, _, _ := strings.Cut(email, "@")
	base := notUsernameChars.ReplaceAllString(strings.ToLower(local), "")
	base = strings.Trim(base, "-_")
	if len(base) < 3 {
		base = "user" + base
	}
	if len(base) > 24 {
		base = base[:24]
	}

	for attempt := 0; attempt < 20; attempt++ {
		candidate := base
		if attempt > 0 {
			suffix, err := cryptox.RandomHex(2)
			if err != nil {
				return "", httpx.Internalf(err, "generate username suffix")
			}
			candidate = base + suffix
		}
		free, err := g.store.UsernameAvailable(ctx, candidate)
		if err != nil {
			return "", httpx.Internalf(err, "check username")
		}
		if free {
			return candidate, nil
		}
	}
	return "", httpx.Internalf(errors.New("no free username"), "generate username")
}
