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
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

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
func New(t *testing.T) *Harness {
	t.Helper()

	dsn := os.Getenv("TEST_DATABASE_URL")
	if dsn == "" {
		t.Skip("TEST_DATABASE_URL is not set; skipping integration test")
	}

	// The environment the application reads is set here rather than in each
	// test, so a test cannot accidentally run against a real deployment.
	env := map[string]string{
		"APP_ENV":      "test",
		"APP_URL":      "http://localhost:3000",
		"API_URL":      "http://localhost:8080",
		"DATABASE_URL": dsn,
		"REDIS_URL":    envOr("TEST_REDIS_URL", "redis://localhost:6379/15"),
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

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("load test configuration: %v", err)
	}

	ctx := context.Background()
	application, err := app.Build(ctx, cfg)
	if err != nil {
		t.Fatalf("build application: %v", err)
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
