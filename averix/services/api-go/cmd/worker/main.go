// Command worker runs AVERIX's background work: scheduled maintenance and the
// job queue.
//
// A separate process from the API on purpose. A sweep that takes a minute must
// not compete with a request that has to answer in fifty milliseconds, and a
// deployment can restart one without the other.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/app"
	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/platform/logx"
	"github.com/averix/api/internal/worker"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintf(os.Stderr, "averix-worker: %v\n", err)
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}

	log := logx.New(cfg.LogLevel, cfg.LogFormat)
	slog.SetDefault(log)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()
	ctx = logx.WithLogger(ctx, log)

	application, err := app.Build(ctx, cfg)
	if err != nil {
		return err
	}
	defer application.Close()

	w := worker.New(application.DB)

	// ── Maintenance ─────────────────────────────────────────────────────────

	// A session that expired is not a session. Removing the rows keeps the
	// table small and keeps a leaked database backup from carrying live ones.
	w.Schedule("purge-expired-sessions", time.Hour, func(ctx context.Context) (string, error) {
		removed, err := application.AuthStore.PurgeExpiredSessions(ctx)
		if err != nil || removed == 0 {
			return "", err
		}
		return fmt.Sprintf("removed %d expired session(s)", removed), nil
	})

	// An upload that was never attached to anything is paid for forever
	// otherwise. The delay is generous: someone may be halfway through a form.
	w.Schedule("purge-orphaned-files", 6*time.Hour, func(ctx context.Context) (string, error) {
		removed, err := application.Files.PurgeOrphans(ctx, 48*time.Hour)
		if err != nil || removed == 0 {
			return "", err
		}
		return fmt.Sprintf("removed %d orphaned file(s)", removed), nil
	})

	// A project nobody hired for stops being open. Expiring it is kinder than
	// leaving developers to propose on something abandoned two months ago.
	w.Schedule("expire-projects", time.Hour, func(ctx context.Context) (string, error) {
		tag, err := application.DB.Exec(ctx, `
			UPDATE projects SET status = 'expired', updated_at = now()
			WHERE status = 'open' AND expires_at IS NOT NULL AND expires_at < now()`)
		if err != nil || tag.RowsAffected() == 0 {
			return "", err
		}
		return fmt.Sprintf("expired %d project(s)", tag.RowsAffected()), nil
	})

	// A proposal on a project that closed without it is answered by the state
	// of the project; marking it keeps the developer's list honest.
	w.Schedule("expire-proposals", 6*time.Hour, func(ctx context.Context) (string, error) {
		tag, err := application.DB.Exec(ctx, `
			UPDATE proposals p SET status = 'expired', updated_at = now()
			FROM projects pj
			WHERE pj.id = p.project_id
			  AND p.status IN ('submitted','viewed','shortlisted')
			  AND pj.status IN ('expired','cancelled')`)
		if err != nil || tag.RowsAffected() == 0 {
			return "", err
		}
		return fmt.Sprintf("expired %d proposal(s)", tag.RowsAffected()), nil
	})

	// Single-use tokens that were never used, and OAuth states that were never
	// returned. Both are short-lived by design and must not accumulate.
	w.Schedule("purge-stale-tokens", time.Hour, func(ctx context.Context) (string, error) {
		if _, err := application.DB.Exec(ctx,
			`DELETE FROM auth_tokens WHERE expires_at < now() - interval '7 days'`); err != nil {
			return "", err
		}
		if _, err := application.DB.Exec(ctx,
			`DELETE FROM oauth_states WHERE expires_at < now() - interval '1 day'`); err != nil {
			return "", err
		}
		return "", nil
	})

	// Jobs whose worker died mid-run.
	w.Schedule("release-stalled-jobs", 5*time.Minute, w.ReleaseStale)

	// Finished jobs are kept long enough to investigate a failure and no
	// longer; dead ones stay, because somebody should look at those.
	w.Schedule("prune-finished-jobs", 24*time.Hour, func(ctx context.Context) (string, error) {
		tag, err := application.DB.Exec(ctx, `
			DELETE FROM jobs
			WHERE status = 'succeeded' AND finished_at < now() - interval '7 days'`)
		if err != nil || tag.RowsAffected() == 0 {
			return "", err
		}
		return fmt.Sprintf("pruned %d finished job(s)", tag.RowsAffected()), nil
	})

	// ── Queued work ─────────────────────────────────────────────────────────

	// A GitHub sync reads dozens of repositories and calls the analysis
	// service; a developer pressing "connect" should not wait for it.
	w.Handle("github.sync", func(ctx context.Context, payload json.RawMessage) error {
		var request struct {
			UserID  string `json:"user_id"`
			Trigger string `json:"trigger"`
		}
		if err := json.Unmarshal(payload, &request); err != nil {
			return err
		}
		userID, err := uuid.Parse(request.UserID)
		if err != nil {
			return fmt.Errorf("job payload has no valid user_id: %w", err)
		}
		trigger := request.Trigger
		if trigger == "" {
			trigger = "scheduled"
		}
		return application.GitHub.SyncForUser(ctx, userID, trigger)
	})

	// Re-checking whether a portfolio link can still be framed, so nobody's
	// profile keeps a preview button that dies on click.
	w.Handle("preview.recheck", func(ctx context.Context, payload json.RawMessage) error {
		var request struct {
			ProjectID string `json:"project_id"`
		}
		if err := json.Unmarshal(payload, &request); err != nil {
			return err
		}
		projectID, err := uuid.Parse(request.ProjectID)
		if err != nil {
			return fmt.Errorf("job payload has no valid project_id: %w", err)
		}
		return application.Portfolio.RecheckPreview(ctx, projectID)
	})

	log.Info("worker configured",
		"environment", string(cfg.Env),
		"storage", cfg.Storage.Driver,
		"ai_service", cfg.AI.Configured())

	return w.Run(ctx)
}
