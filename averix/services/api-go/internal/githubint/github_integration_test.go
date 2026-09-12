package githubint_test

import (
	"net/http"
	"net/url"
	"strings"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

// startConnect returns the authorisation URL and the state inside it.
func startConnect(t *testing.T, dev *testsupport.Developer, body map[string]any) (string, string) {
	t.Helper()
	res := dev.Client.POST("/github/connect", body).OK(t, http.StatusOK)

	authorizeURL := res.String("authorize_url")
	if authorizeURL == "" {
		t.Fatalf("no authorize_url in the response: %s", res.Raw)
	}
	parsed, err := url.Parse(authorizeURL)
	if err != nil {
		t.Fatalf("authorize_url is not a URL: %v", err)
	}
	state := parsed.Query().Get("state")
	if state == "" {
		t.Fatal("the authorisation URL carries no state")
	}
	return authorizeURL, state
}

func TestGitHubReportsNotConfiguredWithoutCredentials(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("nogithub", "backend-developer", "go")

	status := dev.Client.GET("/github/status").OK(t, http.StatusOK)
	if status.Bool("configured") {
		t.Error("GitHub must report itself unconfigured when no credentials are set")
	}
	if status.Bool("connected") {
		t.Error("nothing can be connected without credentials")
	}

	// Connecting says so plainly rather than failing obscurely.
	res := dev.Client.POST("/github/connect", map[string]any{}).
		Fails(t, http.StatusServiceUnavailable, "not_configured")
	if !strings.Contains(strings.ToLower(res.Message), "github") {
		t.Errorf("the message should name GitHub, got %q", res.Message)
	}
}

func TestGitHubConnectFlow(t *testing.T) {
	fake := testsupport.NewFakeGitHub(t)
	h := testsupport.NewWith(t, fake.Env())
	dev := h.PublishDeveloper("alidev", "backend-developer", "go", "postgresql", "docker")

	status := dev.Client.GET("/github/status").OK(t, http.StatusOK)
	if !status.Bool("configured") {
		t.Fatal("GitHub should report itself configured")
	}
	if status.Bool("connected") {
		t.Error("nothing is connected yet")
	}

	authorizeURL, state := startConnect(t, dev, map[string]any{
		"redirect_to": "/onboarding/github?step=7",
	})

	// The authorisation URL must carry the client id, the callback and the
	// minimum scopes — and not the private-repository scope.
	parsed, _ := url.Parse(authorizeURL)
	query := parsed.Query()
	if query.Get("client_id") != "test-client-id" {
		t.Errorf("client_id = %q", query.Get("client_id"))
	}
	if query.Get("redirect_uri") == "" {
		t.Error("the authorisation URL must carry a callback")
	}
	scopes := query.Get("scope")
	if strings.Contains(scopes, "repo") && !strings.Contains(scopes, "read:user") {
		t.Errorf("scopes = %q; a plain connection must not ask for repo", scopes)
	}
	if strings.Fields(scopes) != nil {
		for _, scope := range strings.Fields(scopes) {
			if scope == "repo" {
				t.Error("a plain connection must not request the repo scope")
			}
		}
	}

	// The callback links the account.
	callback := dev.Client.Raw(http.MethodGet,
		"/github/callback?code=test-code&state="+state, nil)
	if callback.Status != http.StatusSeeOther {
		t.Fatalf("the callback returned %d, want a redirect (body: %s)", callback.Status, callback.Raw)
	}
	location := callback.Header.Get("Location")
	if !strings.Contains(location, "/onboarding/github") {
		t.Errorf("the callback redirected to %q, want the requested destination", location)
	}
	if !strings.Contains(location, "github=connected") {
		t.Errorf("the redirect should report the outcome, got %q", location)
	}

	status = dev.Client.GET("/github/status").OK(t, http.StatusOK)
	if !status.Bool("connected") {
		t.Fatal("the account should be connected after the callback")
	}
	account, _ := status.Data["account"].(map[string]any)
	if account["login"] != "alidev" {
		t.Errorf("login = %v, want alidev", account["login"])
	}
	if account["github_user_id"].(float64) != 424242 {
		t.Errorf("github_user_id = %v, want the id from /user", account["github_user_id"])
	}
	// The identity comes from GitHub's own response, so it is proof of
	// ownership rather than a claim.
	if status.Bool("private_granted") {
		t.Error("private access must not be granted by a plain connection")
	}

	// The stored token is encrypted and is never serialised.
	for _, forbidden := range []string{"access_token", "gho_", "test-client-secret"} {
		if strings.Contains(string(status.Raw), forbidden) {
			t.Errorf("the status response leaks %q", forbidden)
		}
	}
	var stored []byte
	h.QueryRow([]any{&stored}, `
		SELECT access_token_enc FROM github_accounts
		WHERE user_id = (SELECT id FROM users WHERE username = 'alidev')
		  AND revoked_at IS NULL`)
	if len(stored) == 0 {
		t.Fatal("no token was stored")
	}
	if strings.Contains(string(stored), "gho_") {
		t.Error("the access token is stored in plaintext")
	}
}

// The state is single-use, so a replayed callback link does nothing.
func TestCallbackStateIsSingleUse(t *testing.T) {
	fake := testsupport.NewFakeGitHub(t)
	h := testsupport.NewWith(t, fake.Env())
	dev := h.PublishDeveloper("replaydev", "backend-developer", "go")

	_, state := startConnect(t, dev, map[string]any{})

	first := dev.Client.Raw(http.MethodGet, "/github/callback?code=code-one&state="+state, nil)
	if first.Status != http.StatusSeeOther {
		t.Fatalf("the first callback returned %d", first.Status)
	}

	second := dev.Client.Raw(http.MethodGet, "/github/callback?code=code-two&state="+state, nil)
	if second.Status != http.StatusSeeOther {
		t.Fatalf("the replayed callback returned %d", second.Status)
	}
	if !strings.Contains(second.Header.Get("Location"), "github=failed") {
		t.Errorf("a replayed state must fail, redirected to %q", second.Header.Get("Location"))
	}
	if !strings.Contains(second.Header.Get("Location"), "github_state_invalid") {
		t.Errorf("the failure reason should be the invalid state, got %q",
			second.Header.Get("Location"))
	}

	// Only the first code was exchanged.
	if len(fake.ExchangedCodes) != 1 {
		t.Errorf("codes exchanged = %v, want only the first", fake.ExchangedCodes)
	}
}

func TestCallbackRejectsAForgedState(t *testing.T) {
	fake := testsupport.NewFakeGitHub(t)
	h := testsupport.NewWith(t, fake.Env())
	dev := h.PublishDeveloper("forgedev", "backend-developer", "go")

	for _, state := range []string{"", "made-up-state", strings.Repeat("a", 64)} {
		res := dev.Client.Raw(http.MethodGet, "/github/callback?code=c&state="+state, nil)
		if res.Status != http.StatusSeeOther {
			t.Fatalf("state %q: status %d", state, res.Status)
		}
		if !strings.Contains(res.Header.Get("Location"), "github=failed") {
			t.Errorf("state %q was accepted", state)
		}
	}
	if len(fake.ExchangedCodes) != 0 {
		t.Errorf("a forged state must not reach the token exchange, exchanged %v", fake.ExchangedCodes)
	}
	if n := h.Count(`SELECT count(*) FROM github_accounts`); n != 0 {
		t.Errorf("github_accounts = %d, want 0", n)
	}
}

// A redirect_to pointing off the platform must not be honoured: a crafted
// authorisation link would otherwise bounce a signed-in user to an attacker's
// page with the flow looking legitimate.
func TestCallbackRefusesOpenRedirects(t *testing.T) {
	fake := testsupport.NewFakeGitHub(t)
	h := testsupport.NewWith(t, fake.Env())
	dev := h.PublishDeveloper("redirectdev", "backend-developer", "go")

	for _, hostile := range []string{
		"https://evil.example/steal",
		"//evil.example/steal",
		"http://evil.example",
		"/\\evil.example",
	} {
		_, state := startConnect(t, dev, map[string]any{"redirect_to": hostile})
		res := dev.Client.Raw(http.MethodGet, "/github/callback?code=c&state="+state, nil)
		location := res.Header.Get("Location")
		if strings.Contains(location, "evil.example") {
			t.Errorf("redirect_to %q sent the browser to %q", hostile, location)
		}
		if !strings.HasPrefix(location, "http://localhost:3000") {
			t.Errorf("redirect_to %q left the application: %q", hostile, location)
		}
	}
}

// One GitHub identity cannot be claimed by two AVERIX accounts, or the
// verification badge would mean nothing.
func TestGitHubIdentityCannotBeClaimedTwice(t *testing.T) {
	fake := testsupport.NewFakeGitHub(t)
	h := testsupport.NewWith(t, fake.Env())

	first := h.PublishDeveloper("firstdev", "backend-developer", "go")
	_, state := startConnect(t, first, map[string]any{})
	first.Client.Raw(http.MethodGet, "/github/callback?code=c1&state="+state, nil)

	if !first.Client.GET("/github/status").Bool("connected") {
		t.Fatal("the first developer should be connected")
	}

	// A second developer authorises the same GitHub account.
	second := h.PublishDeveloper("seconddev", "backend-developer", "go")
	_, state = startConnect(t, second, map[string]any{})
	res := second.Client.Raw(http.MethodGet, "/github/callback?code=c2&state="+state, nil)
	if !strings.Contains(res.Header.Get("Location"), "github_already_connected") {
		t.Errorf("the second claim should be refused, redirected to %q", res.Header.Get("Location"))
	}

	if second.Client.GET("/github/status").Bool("connected") {
		t.Error("the second developer must not be connected to a claimed identity")
	}
	if !first.Client.GET("/github/status").Bool("connected") {
		t.Error("the first developer's connection must be unaffected")
	}
	if n := h.Count(`SELECT count(*) FROM github_accounts WHERE revoked_at IS NULL`); n != 1 {
		t.Errorf("live github_accounts = %d, want 1", n)
	}
}

// Private repository access is a separate, explicit consent. A developer must
// never find that connecting their account also gave away their private code.
func TestPrivateAccessIsASecondConsent(t *testing.T) {
	fake := testsupport.NewFakeGitHub(t)
	h := testsupport.NewWith(t, fake.Env())
	dev := h.PublishDeveloper("privatedev", "backend-developer", "go")

	// It cannot be asked for before the account is connected at all.
	dev.Client.POST("/github/connect", map[string]any{"want_private_access": true}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	_, state := startConnect(t, dev, map[string]any{})
	dev.Client.Raw(http.MethodGet, "/github/callback?code=c1&state="+state, nil)

	status := dev.Client.GET("/github/status").OK(t, http.StatusOK)
	if status.Bool("private_granted") {
		t.Fatal("a plain connection must not grant private access")
	}
	if !status.Bool("can_grant_private") {
		t.Error("a connected developer should be offered the second consent")
	}

	// Now the second consent, which asks for the repo scope.
	authorizeURL, state := startConnect(t, dev, map[string]any{"want_private_access": true})
	parsed, _ := url.Parse(authorizeURL)
	granted := false
	for _, scope := range strings.Fields(parsed.Query().Get("scope")) {
		if scope == "repo" {
			granted = true
		}
	}
	if !granted {
		t.Errorf("the private-access flow must request the repo scope, got %q",
			parsed.Query().Get("scope"))
	}

	fake.Scopes = "read:user,user:email,repo"
	res := dev.Client.Raw(http.MethodGet, "/github/callback?code=c2&state="+state, nil)
	if !strings.Contains(res.Header.Get("Location"), "github=private_granted") {
		t.Errorf("the redirect should report the grant, got %q", res.Header.Get("Location"))
	}

	status = dev.Client.GET("/github/status").OK(t, http.StatusOK)
	if !status.Bool("private_granted") {
		t.Error("private access should be recorded after the second consent")
	}
}

func TestGitHubSyncDetectsTechnologiesAndSuggestsPortfolioWork(t *testing.T) {
	fake := testsupport.NewFakeGitHub(t)
	fake.AddRepository(
		map[string]any{
			"id": 1001, "name": "store-bot", "full_name": "alidev/store-bot",
			"description": "Telegram bot for a clothing store: catalogue, cart and orders.",
			"html_url":    "https://github.com/alidev/store-bot",
			"homepage":    "https://bot.example.com",
			"topics":      []string{"telegram", "python"},
			"language":    "Python", "stargazers_count": 14, "size": 1200,
			"default_branch": "main", "pushed_at": "2026-08-01T10:00:00Z",
		},
		map[string]int64{"Python": 82000, "Dockerfile": 900},
		map[string]string{
			"requirements.txt": "aiogram==3.13.1\nasyncpg~=0.29\nredis>=5.0\n",
			"Dockerfile":       "FROM python:3.12-slim\n",
			"README.md":        "# Store bot\n\nA Telegram bot for browsing a catalogue and ordering.",
		},
	)
	fake.AddRepository(
		map[string]any{
			"id": 1002, "name": "scratch", "full_name": "alidev/scratch",
			"html_url": "https://github.com/alidev/scratch",
			"language": "Python", "size": 12,
		},
		map[string]int64{"Python": 400},
		nil,
	)
	fake.AddRepository(
		map[string]any{
			"id": 1003, "name": "forked-thing", "full_name": "alidev/forked-thing",
			"description": "A fork of something else.",
			"html_url":    "https://github.com/alidev/forked-thing",
			"fork":        true, "language": "Ruby", "size": 9000,
		},
		map[string]int64{"Ruby": 5000000},
		map[string]string{"Gemfile": "gem \"rails\"\n"},
	)

	h := testsupport.NewWith(t, fake.Env())
	dev := h.PublishDeveloper("alidev", "telegram-developer", "python", "telegram-api", "postgresql")

	_, state := startConnect(t, dev, map[string]any{})
	dev.Client.Raw(http.MethodGet, "/github/callback?code=c&state="+state, nil)

	analysis := dev.Client.POST("/github/sync", nil).OK(t, http.StatusOK)

	// Without the analysis service configured, the deterministic findings
	// stand on their own and the run is recorded as partial.
	if analysis.String("status") != "partial" {
		t.Errorf("status = %q; without the analysis service the run is partial",
			analysis.String("status"))
	}
	if analysis.String("ai_summary") != "" {
		t.Error("no summary may be produced without a model")
	}
	if analysis.Float("repos_seen") != 3 {
		t.Errorf("repos_seen = %v, want 3", analysis.Data["repos_seen"])
	}

	// Technologies come from the manifests.
	technologies, _ := analysis.Data["technology_summary"].([]any)
	slugs := map[string]bool{}
	for _, raw := range technologies {
		entry := raw.(map[string]any)
		slugs[entry["slug"].(string)] = true
	}
	for _, expected := range []string{"python", "aiogram", "postgresql", "redis", "docker"} {
		if !slugs[expected] {
			t.Errorf("%s was not detected (got %v)", expected, keysOf(slugs))
		}
	}
	// A fork's dependencies are still evidence of exposure.
	if !slugs["ruby"] {
		t.Error("a fork's dependencies should still be recorded")
	}

	// A fork's bytes must not count towards language share.
	languages, _ := analysis.Data["language_stats"].([]any)
	seen := map[string]float64{}
	for _, raw := range languages {
		entry := raw.(map[string]any)
		seen[entry["language"].(string)] = entry["share"].(float64)
	}
	if _, present := seen["Ruby"]; present {
		t.Error("a fork's 5MB of Ruby must not appear in the developer's language share")
	}
	if seen["Python"] < 0.9 {
		t.Errorf("Python share = %.2f, want nearly all of it", seen["Python"])
	}

	// The declared technologies the code corroborates get evidence attached.
	var evidence []string
	h.QueryRow([]any{&evidence}, `
		SELECT ds.evidence FROM developer_skills ds
		JOIN skills sk ON sk.id = ds.skill_id
		JOIN users u ON u.id = ds.user_id
		WHERE u.username = 'alidev' AND sk.slug = 'python'`)
	if len(evidence) == 0 || evidence[0] != "github" {
		t.Errorf("evidence on the declared Python skill = %v, want [github]", evidence)
	}
	// A technology found in the code but not declared must not be added.
	if n := h.Count(`
		SELECT count(*) FROM developer_skills ds
		JOIN skills sk ON sk.id = ds.skill_id
		JOIN users u ON u.id = ds.user_id
		WHERE u.username = 'alidev' AND sk.slug = 'redis'`); n != 0 {
		t.Error("the analysis must not add a technology to a developer's profile")
	}

	// Portfolio candidates: the described, documented, deployed repository
	// only.
	candidates := dev.Client.GET("/github/portfolio-candidates").OK(t, http.StatusOK)
	if len(candidates.List) != 1 {
		t.Fatalf("portfolio candidates = %d, want 1 (%s)", len(candidates.List), candidates.Raw)
	}
	candidate := candidates.List[0].(map[string]any)
	if candidate["full_name"] != "alidev/store-bot" {
		t.Errorf("the candidate is %v, want alidev/store-bot", candidate["full_name"])
	}
	if candidate["reason"] == "" {
		t.Error("a candidate must carry the reason it was suggested")
	}
}

func TestSyncRequiresAConnectedAccount(t *testing.T) {
	fake := testsupport.NewFakeGitHub(t)
	h := testsupport.NewWith(t, fake.Env())
	dev := h.PublishDeveloper("unconnected", "backend-developer", "go")

	res := dev.Client.POST("/github/sync", nil).Fails(t, http.StatusNotFound, "github_not_connected")
	if !strings.Contains(strings.ToLower(res.Message), "connect") {
		t.Errorf("the message should tell the developer what to do, got %q", res.Message)
	}
}

func TestDisconnectDestroysTheStoredToken(t *testing.T) {
	fake := testsupport.NewFakeGitHub(t)
	h := testsupport.NewWith(t, fake.Env())
	dev := h.PublishDeveloper("leavingdev", "backend-developer", "go")

	_, state := startConnect(t, dev, map[string]any{})
	dev.Client.Raw(http.MethodGet, "/github/callback?code=c&state="+state, nil)
	if !dev.Client.GET("/github/status").Bool("connected") {
		t.Fatal("should be connected")
	}

	dev.Client.DELETE("/github/connection").OK(t, http.StatusNoContent)

	if dev.Client.GET("/github/status").Bool("connected") {
		t.Error("the account should be disconnected")
	}
	var tokenPresent bool
	h.QueryRow([]any{&tokenPresent}, `
		SELECT access_token_enc IS NOT NULL FROM github_accounts
		WHERE user_id = (SELECT id FROM users WHERE username = 'leavingdev')
		ORDER BY created_at DESC LIMIT 1`)
	if tokenPresent {
		t.Error("disconnecting must destroy the stored token, not merely hide it")
	}

	// Reconnecting works.
	_, state = startConnect(t, dev, map[string]any{})
	dev.Client.Raw(http.MethodGet, "/github/callback?code=c2&state="+state, nil)
	if !dev.Client.GET("/github/status").Bool("connected") {
		t.Error("reconnecting after a disconnect should work")
	}
}

func TestGitHubEndpointsAreDeveloperOnly(t *testing.T) {
	fake := testsupport.NewFakeGitHub(t)
	h := testsupport.NewWith(t, fake.Env())

	client := h.NewClient("clientaccount")
	client.Client.GET("/github/status").Fails(t, http.StatusForbidden, "forbidden")
	client.Client.POST("/github/connect", map[string]any{}).Fails(t, http.StatusForbidden, "forbidden")
	client.Client.POST("/github/sync", nil).Fails(t, http.StatusForbidden, "forbidden")

	h.Client().GET("/github/status").Fails(t, http.StatusUnauthorized, "unauthenticated")
}

func TestTokenExchangeFailureIsReportedCleanly(t *testing.T) {
	fake := testsupport.NewFakeGitHub(t)
	h := testsupport.NewWith(t, fake.Env())
	dev := h.PublishDeveloper("failuredev", "backend-developer", "go")

	_, state := startConnect(t, dev, map[string]any{})
	fake.Fail(true, false)

	res := dev.Client.Raw(http.MethodGet, "/github/callback?code=bad&state="+state, nil)
	location := res.Header.Get("Location")
	if !strings.Contains(location, "github_exchange_failed") {
		t.Errorf("the failure should be named in the redirect, got %q", location)
	}
	// GitHub's own error text can name the client id and must not be relayed.
	if strings.Contains(location, "client") || strings.Contains(location, "verification") {
		t.Errorf("the redirect leaks GitHub's error detail: %q", location)
	}
	if n := h.Count(`SELECT count(*) FROM github_accounts`); n != 0 {
		t.Errorf("github_accounts = %d after a failed exchange, want 0", n)
	}
}

func TestDecliningAtGitHubIsNotAnError(t *testing.T) {
	fake := testsupport.NewFakeGitHub(t)
	h := testsupport.NewWith(t, fake.Env())
	dev := h.PublishDeveloper("decliner", "backend-developer", "go")

	res := dev.Client.Raw(http.MethodGet,
		"/github/callback?error=access_denied&error_description=The+user+denied+access", nil)
	if res.Status != http.StatusSeeOther {
		t.Fatalf("status = %d, want a redirect", res.Status)
	}
	if !strings.Contains(res.Header.Get("Location"), "github=cancelled") {
		t.Errorf("declining should redirect to a cancelled state, got %q", res.Header.Get("Location"))
	}
}

func keysOf(m map[string]bool) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}
