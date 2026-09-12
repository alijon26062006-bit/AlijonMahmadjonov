// Package testsupport builds a real application against a real database for
// integration tests.
//
// The tests here talk to PostgreSQL rather than a mock, because the behaviour
// being asserted — unique constraints, deferred cap triggers, the milestone
// progress trigger, authorisation joins — lives in the database. A mock would
// pass while production failed.
package testsupport

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/app"
	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/storage"
)

// Harness is a running application with an HTTP test server in front of it.
type Harness struct {
	T      *testing.T
	App    *app.App
	Server *httptest.Server
	DB     *database.DB
}

// New builds the harness, skipping the test when no test database is
// configured, so `go test ./...` still works on a machine without one.
func New(t *testing.T) *Harness { return NewWith(t, nil) }

// NewWith builds the harness with extra environment, for the tests that need
// an integration pointed at a fake (GitHub, the analysis service).
func NewWith(t *testing.T, extra map[string]string) *Harness {
	t.Helper()

	base := os.Getenv("TEST_DATABASE_URL")
	if base == "" {
		t.Skip("TEST_DATABASE_URL is not set; skipping integration test")
	}

	// Each test package gets its own database.
	//
	// `go test ./...` runs packages in parallel, and the harness truncates the
	// tables it owns between tests. Sharing one database means two packages
	// delete each other's fixtures mid-test — which passes when each package
	// is run alone and fails in CI, the worst possible failure mode. A
	// database per package removes the interference rather than papering over
	// it with `-p 1`.
	dsn, err := databaseForPackage(base)
	if err != nil {
		t.Fatalf("prepare per-package test database: %v", err)
	}

	// The environment the application reads is set here rather than in each
	// test, so a test cannot accidentally run against a real deployment.
	env := map[string]string{
		"APP_ENV":      "test",
		"APP_URL":      "http://localhost:3000",
		"API_URL":      "http://localhost:8080",
		"DATABASE_URL": dsn,
		"REDIS_URL":    envOr("TEST_REDIS_URL", "redis://localhost:6379/15"),
		// A key prefix per package, for the same reason as the database per
		// package: the rate limiter is keyed by client address, every test
		// connects from 127.0.0.1, and parallel packages sharing one Redis
		// would exhaust each other's sign-up allowance. That failed only
		// under `go test ./...`, which is the worst way for it to fail.
		"REDIS_PREFIX": "averix-test-" + packageSuffix(),
		"S3_DRIVER":    "filesystem",
		"STORAGE_ROOT": t.TempDir(),
		"LOG_LEVEL":    envOr("TEST_LOG_LEVEL", "error"),
		"LOG_FORMAT":   "text",
		// The lowest cost bcrypt will accept: correctness is what is under
		// test, and cost 12 would make the suite take minutes.
		"BCRYPT_COST": "10",
		// High enough that the limiter does not interfere with a test that
		// deliberately makes many requests; the limiter has its own tests.
		"RATE_LIMIT_ANON": "10000",
		"RATE_LIMIT_AUTH": "10000",
	}
	for k, v := range env {
		t.Setenv(k, v)
	}
	// Applied after the defaults so a test can override any of them.
	for k, v := range extra {
		t.Setenv(k, v)
	}

	cfg, loadErr := config.Load()
	if loadErr != nil {
		t.Fatalf("load test configuration: %v", loadErr)
	}

	ctx := context.Background()
	application, buildErr := app.Build(ctx, cfg)
	if buildErr != nil {
		t.Fatalf("build application: %v", buildErr)
	}

	if _, err := application.DB.Migrate(ctx); err != nil {
		application.Close()
		t.Fatalf("migrate test database: %v", err)
	}

	h := &Harness{
		T:      t,
		App:    application,
		Server: httptest.NewServer(application.Handler()),
		DB:     application.DB,
	}
	h.Reset()

	t.Cleanup(func() {
		h.Server.Close()
		application.Close()
	})
	return h
}

// Reset truncates the tables tests write to, leaving the reference taxonomy in
// place. Truncating rather than recreating the schema keeps each test fast
// while still guaranteeing isolation.
func (h *Harness) Reset() {
	h.T.Helper()
	ctx := context.Background()
	// Ordered by dependency, though CASCADE handles the rest. Reference tables
	// (specialisations, categories, skills and their joins) are intentionally
	// absent: they are migration content, not test fixtures.
	tables := []string{
		"audit_logs", "admin_actions", "dispute_messages", "disputes",
		"moderation_queue", "reports", "notification_deliveries", "notifications",
		"push_subscriptions", "notification_preferences", "email_log",
		"ledger_entries", "payment_webhook_events", "payment_transactions",
		"payment_intents", "reviews", "completed_project_skills",
		"completed_project_history", "portfolio_links", "portfolio_skills",
		"portfolio_images", "portfolio_projects", "service_portfolio_links",
		"service_tiers", "service_skills", "services", "project_views",
		"saved_projects", "saved_developers", "message_receipts",
		"message_attachments", "messages", "conversation_participants",
		"conversations", "files", "deliverables", "milestone_events",
		"milestones", "contract_participants", "contracts", "match_scores",
		"proposal_portfolio_links", "proposal_milestones", "proposals",
		"assistant_sessions", "project_invitations", "project_attachments",
		"project_features", "project_specialisations", "project_skills",
		"projects", "github_analysis", "github_detected_technologies",
		"github_repository_languages", "github_repositories", "github_accounts",
		"user_languages", "developer_photos", "developer_skills",
		"developer_specialisations", "developer_profiles", "client_profiles",
		"rate_limit_events", "oauth_states", "auth_tokens", "sessions",
		"user_roles", "users",
	}
	stmt := "TRUNCATE " + strings.Join(tables, ", ") + " CASCADE"
	if _, err := h.DB.Exec(ctx, stmt); err != nil {
		h.T.Fatalf("reset test database: %v", err)
	}
	// The rate limiter is shared state across tests when Redis is present.
	if h.App.Cache != nil {
		_ = h.App.Cache.DeletePrefix(ctx, "rl")
		_ = h.App.Cache.DeletePrefix(ctx, "tax")
	}
}

// URL builds an absolute URL against the test server.
func (h *Harness) URL(path string) string {
	if !strings.HasPrefix(path, "/") {
		path = "/" + path
	}
	return h.Server.URL + path
}

// APIURL builds a URL under /api/v1.
func (h *Harness) APIURL(path string) string {
	return h.URL("/api/v1" + path)
}

// Exec runs a statement directly, for arranging fixtures a test needs that no
// endpoint creates (a completed contract, an expired session).
func (h *Harness) Exec(sql string, args ...any) {
	h.T.Helper()
	if _, err := h.DB.Exec(context.Background(), sql, args...); err != nil {
		h.T.Fatalf("exec fixture SQL: %v\n%s", err, sql)
	}
}

// QueryRow scans a single row, for asserting on state an endpoint changed.
func (h *Harness) QueryRow(dest []any, sql string, args ...any) {
	h.T.Helper()
	if err := h.DB.QueryRow(context.Background(), sql, args...).Scan(dest...); err != nil {
		h.T.Fatalf("query fixture SQL: %v\n%s", err, sql)
	}
}

// Count returns a row count, the most common assertion in these tests.
func (h *Harness) Count(sql string, args ...any) int {
	h.T.Helper()
	var n int
	if err := h.DB.QueryRow(context.Background(), sql, args...).Scan(&n); err != nil {
		h.T.Fatalf("count: %v\n%s", err, sql)
	}
	return n
}

// WaitFor polls until cond is true, for the handful of places where work
// continues after the response (audit writes on a detached context).
func (h *Harness) WaitFor(what string, cond func() bool) {
	h.T.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		if cond() {
			return
		}
		time.Sleep(25 * time.Millisecond)
	}
	h.T.Fatalf("timed out waiting for %s", what)
}

func envOr(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}

// NoRedirect is used by clients that must observe a 3xx rather than follow it.
var NoRedirect = func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }

var _ = fmt.Sprintf

// Public and Private mirror the storage visibilities, so a test can read an
// object back without importing the storage package.
const (
	Public  = storage.Public
	Private = storage.Private
)

// ReadObject reads a stored object's bytes.
func (h *Harness) ReadObject(key string, vis storage.Visibility) []byte {
	h.T.Helper()
	reader, _, err := h.App.Storage.Get(context.Background(), key, vis)
	if err != nil {
		h.T.Fatalf("read stored object %s: %v", key, err)
	}
	defer reader.Close()
	data, err := io.ReadAll(reader)
	if err != nil {
		h.T.Fatalf("read object body: %v", err)
	}
	return data
}

// ObjectExists reports whether a stored object is still present, which is how
// the tests prove that superseded derivatives are cleaned up.
func (h *Harness) ObjectExists(key string, vis storage.Visibility) bool {
	h.T.Helper()
	ok, err := h.App.Storage.Exists(context.Background(), key, vis)
	return err == nil && ok
}

// ── Fixtures ────────────────────────────────────────────────────────────────

// Developer is a signed-in developer with a published profile.
type Developer struct {
	Client   *Client
	Username string
	UserID   string
}

// PublishDeveloper runs the whole onboarding flow, so tests that need a
// searchable developer do not each repeat nine requests.
func (h *Harness) PublishDeveloper(username, specialisation string, technologies ...string) *Developer {
	h.T.Helper()

	c := h.Client()
	c.RegisterDeveloper(username)

	c.PUT("/developers/me/basics", map[string]any{
		"full_name": "Test " + username, "country_code": "TJ", "city": "Dushanbe",
		"languages": []map[string]string{{"language": "English", "proficiency": "fluent"}},
	}).OK(h.T, 200)
	c.PUT("/developers/me/specialisation", map[string]any{"slug": specialisation}).OK(h.T, 200)

	if len(technologies) == 0 {
		technologies = []string{"go", "postgresql", "docker"}
	}
	entries := make([]map[string]any, 0, len(technologies))
	for _, slug := range technologies {
		entries = append(entries, map[string]any{"slug": slug, "level": "strong"})
	}
	c.PUT("/developers/me/technologies", map[string]any{"technologies": entries}).OK(h.T, 200)
	c.PUT("/developers/me/experience", map[string]any{
		"experience_level": "senior", "years_experience": 6,
		"hourly_rate_minor": 3000, "currency": "USD",
	}).OK(h.T, 200)
	c.PUT("/developers/me/availability", map[string]any{
		"availability": "available", "hours_per_week": 35,
		"show_location": true, "show_hourly_rate": true,
	}).OK(h.T, 200)
	c.PUT("/developers/me/bio", map[string]any{
		"bio": "I build backend systems and integrations, mostly APIs backed by " +
			"PostgreSQL. I have shipped payment flows and admin panels, and I care " +
			"about migrations that run safely and errors that say something useful.",
	}).OK(h.T, 200)

	h.Verify(username)
	c.POST("/developers/me/finish", nil).OK(h.T, 200)

	return &Developer{Client: c, Username: username, UserID: c.UserID()}
}

// ClientAccount is a signed-in client with a confirmed address.
type ClientAccount struct {
	Client   *Client
	Username string
	UserID   string
}

// NewClient registers a client and confirms their email, which publishing a
// project requires.
func (h *Harness) NewClient(username string) *ClientAccount {
	h.T.Helper()
	c := h.Client()
	c.RegisterClient(username)
	h.Verify(username)
	// The session caches nothing, but the identity is re-resolved per request,
	// so the confirmed address is visible immediately.
	return &ClientAccount{Client: c, Username: username, UserID: c.UserID()}
}

// Verify marks an account's email address confirmed.
func (h *Harness) Verify(username string) {
	h.T.Helper()
	h.Exec(`UPDATE users SET email_verified_at = now() WHERE username = $1`, username)
}

// PublishProject creates and publishes a project for a client, returning its id.
func (h *Harness) PublishProject(c *ClientAccount, title, categorySlug string,
	required []string, budgetMin, budgetMax int64) string {
	h.T.Helper()

	res := c.Client.POST("/projects", map[string]any{
		"title":            title,
		"description":      "We need this built properly. " + title + ". The scope is clear and the timeline is real.",
		"category_slug":    categorySlug,
		"required_skills":  required,
		"budget_type":      "range",
		"budget_min_minor": budgetMin,
		"budget_max_minor": budgetMax,
		"currency":         "USD",
		"duration_days":    14,
		"publish":          true,
	}).OK(h.T, 201)

	id := res.String("id")
	if id == "" {
		h.T.Fatalf("project creation returned no id: %s", res.Raw)
	}
	if res.String("status") != "open" {
		h.T.Fatalf("project status = %q, want open", res.String("status"))
	}
	return id
}

// SetSetting changes a platform setting for the duration of one test and
// restores it afterwards.
//
// It goes through the store's own Set, which invalidates the cache: writing
// the row directly would leave the previous value cached for up to thirty
// seconds and make the test flaky rather than failing.
func (h *Harness) SetSetting(key string, value any) {
	h.T.Helper()
	ctx := context.Background()

	var previous json.RawMessage
	existed := true
	if err := h.DB.QueryRow(ctx,
		`SELECT value FROM platform_settings WHERE key = $1`, key).Scan(&previous); err != nil {
		existed = false
	}

	if err := h.App.Settings.Set(ctx, key, value, uuid.Nil); err != nil {
		h.T.Fatalf("set platform setting %s: %v", key, err)
	}

	h.T.Cleanup(func() {
		restoreCtx := context.Background()
		if !existed {
			_, _ = h.DB.Exec(restoreCtx, `DELETE FROM platform_settings WHERE key = $1`, key)
		} else {
			var decoded any
			if err := json.Unmarshal(previous, &decoded); err == nil {
				_ = h.App.Settings.Set(restoreCtx, key, decoded, uuid.Nil)
			}
		}
	})
}

// databaseForPackage returns a DSN pointing at a database named after the test
// binary, creating it if it does not exist.
//
// The name comes from the binary rather than from a caller's file path so that
// every test in a package shares one database and no two packages share any.
func databaseForPackage(base string) (string, error) {
	parsed, err := url.Parse(base)
	if err != nil {
		return "", fmt.Errorf("parse TEST_DATABASE_URL: %w", err)
	}

	suffix := packageSuffix()
	if suffix == "" {
		return base, nil
	}
	name := strings.TrimPrefix(parsed.Path, "/") + "_" + suffix
	// PostgreSQL truncates identifiers at 63 bytes; a silently truncated name
	// could collide with another package's.
	if len(name) > 60 {
		name = name[:60]
	}

	// Connect to the server's default database to issue CREATE DATABASE, which
	// cannot run inside a transaction or against the database being created.
	admin := *parsed
	admin.Path = "/postgres"

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	adminDB, err := database.Connect(ctx, config.Database{
		URL: admin.String(), MaxConns: 2, MinConns: 1,
		MaxConnLifetime: time.Minute, MaxConnIdleTime: time.Minute,
		StatementTimeout: 15 * time.Second,
	})
	if err != nil {
		// No permission to create databases: fall back to the shared one. The
		// suite still runs, and `-p 1` makes it reliable.
		return base, nil
	}
	defer adminDB.Close()

	var exists bool
	if err := adminDB.QueryRow(ctx,
		`SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = $1)`, name).Scan(&exists); err != nil {
		return base, nil
	}
	if !exists {
		// A concurrent creation is not an error: whichever call wins, the
		// database exists afterwards.
		if _, err := adminDB.Exec(ctx, `CREATE DATABASE "`+name+`"`); err != nil &&
			!strings.Contains(err.Error(), "already exists") {
			return base, nil
		}
	}

	out := *parsed
	out.Path = "/" + name
	return out.String(), nil
}

// packageSuffix derives a short identifier from the test binary's name.
func packageSuffix() string {
	binary := filepath.Base(os.Args[0])
	binary = strings.TrimSuffix(binary, ".test")
	binary = strings.TrimSuffix(binary, ".exe")

	var b strings.Builder
	for _, r := range strings.ToLower(binary) {
		switch {
		case r >= 'a' && r <= 'z', r >= '0' && r <= '9':
			b.WriteRune(r)
		case r == '_', r == '-', r == '.':
			b.WriteByte('_')
		}
	}
	out := b.String()
	if out == "" || out == "main" {
		return ""
	}
	return out
}

// FakeGitHub is an httptest server standing in for GitHub's API and OAuth
// endpoints.
//
// The flow is worth testing end to end — the state is single-use, the identity
// comes from the token rather than from anything the caller supplies, and a
// second account must not be able to claim the same GitHub identity. None of
// that can be checked against the real GitHub.
type FakeGitHub struct {
	Server *httptest.Server
	// The identity /user returns. Tests change it to simulate a different
	// GitHub account.
	UserID    int64
	Login     string
	Name      string
	Repos     []map[string]any
	Languages map[string]map[string]int64
	Files     map[string]map[string]string
	// Set to make the token exchange or the user lookup fail.
	FailExchange bool
	FailUser     bool
	// Scopes the exchange reports back.
	Scopes string
	// Recorded for assertions.
	ExchangedCodes []string
	mu             sync.Mutex
}

// NewFakeGitHub starts the fake and returns it with the environment variables
// that point the application at it.
func NewFakeGitHub(t *testing.T) *FakeGitHub {
	t.Helper()

	fake := &FakeGitHub{
		UserID:    424242,
		Login:     "alidev",
		Name:      "Ali Mahmadjonov",
		Scopes:    "read:user,user:email",
		Languages: map[string]map[string]int64{},
		Files:     map[string]map[string]string{},
	}

	mux := http.NewServeMux()

	mux.HandleFunc("POST /login/oauth/access_token", func(w http.ResponseWriter, r *http.Request) {
		_ = r.ParseForm()
		fake.mu.Lock()
		fake.ExchangedCodes = append(fake.ExchangedCodes, r.FormValue("code"))
		failing := fake.FailExchange
		scopes := fake.Scopes
		fake.mu.Unlock()

		w.Header().Set("Content-Type", "application/json")
		if failing {
			_ = json.NewEncoder(w).Encode(map[string]any{
				"error":             "bad_verification_code",
				"error_description": "the code is invalid",
			})
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"access_token": "gho_" + r.FormValue("code"),
			"token_type":   "bearer",
			"scope":        scopes,
		})
	})

	mux.HandleFunc("GET /user", func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") == "" {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		fake.mu.Lock()
		failing, id, login, name := fake.FailUser, fake.UserID, fake.Login, fake.Name
		fake.mu.Unlock()

		if failing {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"id":           id,
			"login":        login,
			"name":         name,
			"html_url":     "https://github.com/" + login,
			"avatar_url":   "https://avatars.example/" + login,
			"public_repos": 12,
			"followers":    34,
			"created_at":   "2019-04-01T10:00:00Z",
		})
	})

	mux.HandleFunc("GET /user/repos", func(w http.ResponseWriter, r *http.Request) {
		fake.mu.Lock()
		repos := fake.Repos
		fake.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		// One page: the client stops when a page is short.
		if r.URL.Query().Get("page") != "1" && r.URL.Query().Get("page") != "" {
			_ = json.NewEncoder(w).Encode([]any{})
			return
		}
		_ = json.NewEncoder(w).Encode(repos)
	})

	mux.HandleFunc("GET /repos/{owner}/{repo}/languages", func(w http.ResponseWriter, r *http.Request) {
		key := r.PathValue("owner") + "/" + r.PathValue("repo")
		fake.mu.Lock()
		languages := fake.Languages[key]
		fake.mu.Unlock()
		if languages == nil {
			languages = map[string]int64{}
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(languages)
	})

	// One handler for both the root listing and a single file: Go's ServeMux
	// treats "/contents/" and "/contents/{path...}" as the same pattern, and
	// an empty path means the listing.
	mux.HandleFunc("GET /repos/{owner}/{repo}/contents/{path...}",
		func(w http.ResponseWriter, r *http.Request) {
			key := r.PathValue("owner") + "/" + r.PathValue("repo")
			path := r.PathValue("path")

			fake.mu.Lock()
			files := fake.Files[key]
			fake.mu.Unlock()

			w.Header().Set("Content-Type", "application/json")

			if path == "" {
				// The root listing, so the analyser only asks for manifests
				// that exist rather than guessing sixteen names per repository.
				entries := make([]map[string]any, 0, len(files))
				for name := range files {
					entries = append(entries, map[string]any{"name": name, "type": "file"})
				}
				_ = json.NewEncoder(w).Encode(entries)
				return
			}

			content, ok := files[path]
			if !ok {
				w.WriteHeader(http.StatusNotFound)
				return
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"type":     "file",
				"size":     len(content),
				"encoding": "base64",
				"content":  base64.StdEncoding.EncodeToString([]byte(content)),
			})
		})

	mux.HandleFunc("GET /repos/{owner}/{repo}/readme", func(w http.ResponseWriter, r *http.Request) {
		key := r.PathValue("owner") + "/" + r.PathValue("repo")
		fake.mu.Lock()
		content, ok := fake.Files[key]["README.md"]
		fake.mu.Unlock()
		if !ok {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"size":     len(content),
			"encoding": "base64",
			"content":  base64.StdEncoding.EncodeToString([]byte(content)),
		})
	})

	fake.Server = httptest.NewServer(mux)
	t.Cleanup(fake.Server.Close)
	return fake
}

// Env returns the environment that points the application at the fake.
func (f *FakeGitHub) Env() map[string]string {
	return map[string]string{
		"GITHUB_CLIENT_ID":     "test-client-id",
		"GITHUB_CLIENT_SECRET": "test-client-secret-long-enough",
		"GITHUB_API_BASE_URL":  f.Server.URL,
		"GITHUB_AUTHORIZE_URL": f.Server.URL + "/login/oauth/authorize",
		"GITHUB_TOKEN_URL":     f.Server.URL + "/login/oauth/access_token",
	}
}

// SetIdentity changes the account /user reports.
func (f *FakeGitHub) SetIdentity(id int64, login string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.UserID, f.Login = id, login
}

// AddRepository registers a repository with its languages and files.
func (f *FakeGitHub) AddRepository(repo map[string]any, languages map[string]int64, files map[string]string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.Repos = append(f.Repos, repo)
	fullName, _ := repo["full_name"].(string)
	if languages != nil {
		f.Languages[fullName] = languages
	}
	if files != nil {
		f.Files[fullName] = files
	}
}

// Fail makes the exchange or the user lookup fail.
func (f *FakeGitHub) Fail(exchange, user bool) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.FailExchange, f.FailUser = exchange, user
}
