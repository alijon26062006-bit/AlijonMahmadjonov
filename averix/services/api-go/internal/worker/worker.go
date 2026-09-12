// Package worker runs the work that must happen without anyone asking.
//
// Two kinds of it. Scheduled maintenance — expiring what has expired, sweeping
// what nothing references — and queued jobs the API enqueues rather than doing
// inside a request, because a client waiting on a GitHub sync is a client
// watching a spinner.
//
// Everything here is idempotent and safe to run twice: a worker that is
// restarted mid-task must not corrupt anything, and two workers must not
// double a job. The queue's claim is a single UPDATE, which is what makes the
// second true.
package worker

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math/rand"
	"os"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/logx"
)

// Handler runs one queued job.
type Handler func(ctx context.Context, payload json.RawMessage) error

// Task is a piece of scheduled maintenance.
type Task struct {
	Name     string
	Every    time.Duration
	Run      func(ctx context.Context) (string, error)
	lastRun  time.Time
	failures int
}

type Worker struct {
	db       *database.DB
	tasks    []*Task
	handlers map[string]Handler
	// Identifies this process in the jobs table, so a job locked by a worker
	// that died can be recognised and released.
	id string
}

func New(db *database.DB) *Worker {
	host, _ := os.Hostname()
	if host == "" {
		host = "worker"
	}
	return &Worker{
		db:       db,
		handlers: map[string]Handler{},
		id:       fmt.Sprintf("%s-%d", host, os.Getpid()),
	}
}

// Schedule adds a maintenance task.
func (w *Worker) Schedule(name string, every time.Duration, run func(context.Context) (string, error)) {
	w.tasks = append(w.tasks, &Task{Name: name, Every: every, Run: run})
}

// Handle registers a handler for a queued job kind.
func (w *Worker) Handle(kind string, handler Handler) {
	w.handlers[kind] = handler
}

// Run works until the context is cancelled.
//
// One loop with a short tick rather than a goroutine per task: the work here
// is measured in seconds a day, and a single loop makes "what is this process
// doing" answerable from one place.
func (w *Worker) Run(ctx context.Context) error {
	log := logx.From(ctx)
	log.Info("worker starting", "id", w.id, "tasks", len(w.tasks), "handlers", len(w.handlers))

	// A little jitter at start-up, so two workers restarted together do not
	// run every task in lockstep for the rest of their lives.
	select {
	case <-time.After(time.Duration(rand.Intn(3000)) * time.Millisecond):
	case <-ctx.Done():
		return nil
	}

	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Info("worker stopping")
			return nil
		case <-ticker.C:
			w.runDueTasks(ctx)
			w.drainQueue(ctx)
		}
	}
}

func (w *Worker) runDueTasks(ctx context.Context) {
	now := time.Now()
	for _, task := range w.tasks {
		if !task.lastRun.IsZero() && now.Sub(task.lastRun) < task.Every {
			continue
		}
		task.lastRun = now

		taskCtx, cancel := context.WithTimeout(ctx, 5*time.Minute)
		started := time.Now()
		summary, err := task.Run(taskCtx)
		cancel()

		log := logx.From(ctx).With("task", task.Name, "took_ms", time.Since(started).Milliseconds())
		if err != nil {
			task.failures++
			// A task that fails forever is a problem worth noticing, but it
			// must not take the worker down with it.
			log.Error("scheduled task failed", "error", err, "consecutive_failures", task.failures)
			continue
		}
		task.failures = 0
		if summary != "" {
			log.Info("scheduled task", "result", summary)
		}
	}
}

// ── The queue ───────────────────────────────────────────────────────────────

type job struct {
	ID          uuid.UUID
	Kind        string
	Payload     json.RawMessage
	Attempts    int
	MaxAttempts int
}

// drainQueue claims and runs due jobs until there are none left.
func (w *Worker) drainQueue(ctx context.Context) {
	for i := 0; i < 25; i++ {
		if ctx.Err() != nil {
			return
		}
		claimed, err := w.claim(ctx)
		if err != nil {
			logx.From(ctx).Error("worker: could not claim a job", "error", err)
			return
		}
		if claimed == nil {
			return
		}
		w.run(ctx, claimed)
	}
}

// claim takes one job.
//
// The claim is a single UPDATE with SKIP LOCKED, so two workers racing for the
// same row cannot both get it, and a slow handler does not block the others.
func (w *Worker) claim(ctx context.Context) (*job, error) {
	var claimed job
	err := w.db.QueryRow(ctx, `
		UPDATE jobs SET status = 'running', attempts = attempts + 1,
		                locked_by = $1, locked_at = now(), updated_at = now()
		WHERE id = (
		  SELECT id FROM jobs
		   WHERE status = 'queued' AND run_after <= now()
		   ORDER BY run_after
		   FOR UPDATE SKIP LOCKED
		   LIMIT 1
		)
		RETURNING id, kind, payload, attempts, max_attempts`, w.id).
		Scan(&claimed.ID, &claimed.Kind, &claimed.Payload, &claimed.Attempts, &claimed.MaxAttempts)
	if database.IsNoRows(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &claimed, nil
}

func (w *Worker) run(ctx context.Context, j *job) {
	log := logx.From(ctx).With("job", j.Kind, "job_id", j.ID, "attempt", j.Attempts)

	handler, ok := w.handlers[j.Kind]
	if !ok {
		// An unknown kind is a deployment mismatch, not a transient failure:
		// retrying it every minute for a day helps nobody.
		w.fail(ctx, j, fmt.Errorf("no handler registered for %q", j.Kind), true)
		log.Error("worker: unknown job kind")
		return
	}

	jobCtx, cancel := context.WithTimeout(ctx, 10*time.Minute)
	defer cancel()

	started := time.Now()
	if err := handler(jobCtx, j.Payload); err != nil {
		w.fail(ctx, j, err, false)
		log.Error("job failed", "error", err, "took_ms", time.Since(started).Milliseconds())
		return
	}

	if _, err := w.db.Exec(context.WithoutCancel(ctx), `
		UPDATE jobs SET status = 'succeeded', finished_at = now(), locked_by = NULL,
		                last_error = NULL, updated_at = now()
		WHERE id = $1`, j.ID); err != nil {
		log.Error("worker: could not record a finished job", "error", err)
	}
	log.Info("job done", "took_ms", time.Since(started).Milliseconds())
}

// fail records a failure and decides whether to retry.
//
// Exponential backoff, and a job that has used its attempts becomes "dead"
// rather than disappearing: a job nobody can see failed is a bug report
// nobody gets.
func (w *Worker) fail(ctx context.Context, j *job, cause error, permanent bool) {
	detached := context.WithoutCancel(ctx)

	if permanent || j.Attempts >= j.MaxAttempts {
		_, _ = w.db.Exec(detached, `
			UPDATE jobs SET status = 'dead', finished_at = now(), locked_by = NULL,
			                last_error = $2, updated_at = now()
			WHERE id = $1`, j.ID, truncate(cause.Error()))
		return
	}

	backoff := time.Duration(1<<uint(j.Attempts)) * time.Minute
	if backoff > time.Hour {
		backoff = time.Hour
	}
	_, _ = w.db.Exec(detached, `
		UPDATE jobs SET status = 'queued', run_after = now() + $3::interval,
		                locked_by = NULL, locked_at = NULL, last_error = $2,
		                updated_at = now()
		WHERE id = $1`, j.ID, truncate(cause.Error()),
		fmt.Sprintf("%d seconds", int(backoff.Seconds())))
}

// ReleaseStale returns jobs whose worker died to the queue.
//
// A process killed mid-job leaves a row marked running and locked by a worker
// that no longer exists. Without this they would sit there forever.
func (w *Worker) ReleaseStale(ctx context.Context) (string, error) {
	tag, err := w.db.Exec(ctx, `
		UPDATE jobs SET status = 'queued', locked_by = NULL, locked_at = NULL,
		                updated_at = now()
		WHERE status = 'running' AND locked_at < now() - interval '15 minutes'`)
	if err != nil {
		return "", err
	}
	if tag.RowsAffected() == 0 {
		return "", nil
	}
	return fmt.Sprintf("released %d stalled job(s)", tag.RowsAffected()), nil
}

// Enqueue adds a job. Used by the API, and by tasks that fan work out.
func Enqueue(ctx context.Context, db *database.DB, kind string, payload any, dedupeKey string) error {
	encoded, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	_, err = db.Exec(ctx, `
		INSERT INTO jobs (kind, payload, dedupe_key)
		VALUES ($1, $2, nullif($3, ''))
		ON CONFLICT (kind, dedupe_key) DO NOTHING`, kind, encoded, dedupeKey)
	if err != nil && !errors.Is(err, context.Canceled) {
		return fmt.Errorf("enqueue %s: %w", kind, err)
	}
	return nil
}

func truncate(s string) string {
	const limit = 2000
	if len(s) <= limit {
		return s
	}
	return s[:limit] + "…"
}
