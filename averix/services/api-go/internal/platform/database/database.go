// Package database owns the PostgreSQL connection pool and transaction helpers.
package database

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/averix/api/internal/config"
)

// DB wraps the pool. Queries go through it so every module shares one pool and
// one set of timeouts.
type DB struct {
	Pool *pgxpool.Pool
}

func Connect(ctx context.Context, cfg config.Database) (*DB, error) {
	poolCfg, err := pgxpool.ParseConfig(cfg.URL)
	if err != nil {
		return nil, fmt.Errorf("parse DATABASE_URL: %w", err)
	}
	poolCfg.MaxConns = cfg.MaxConns
	poolCfg.MinConns = cfg.MinConns
	poolCfg.MaxConnLifetime = cfg.MaxConnLifetime
	poolCfg.MaxConnIdleTime = cfg.MaxConnIdleTime
	poolCfg.HealthCheckPeriod = 30 * time.Second

	// A statement timeout set on the connection is the backstop for a query
	// that escapes its context deadline — a runaway scan cannot pin a
	// connection indefinitely.
	if poolCfg.ConnConfig.RuntimeParams == nil {
		poolCfg.ConnConfig.RuntimeParams = map[string]string{}
	}
	poolCfg.ConnConfig.RuntimeParams["statement_timeout"] =
		fmt.Sprintf("%d", cfg.StatementTimeout.Milliseconds())
	poolCfg.ConnConfig.RuntimeParams["idle_in_transaction_session_timeout"] = "30000"
	poolCfg.ConnConfig.RuntimeParams["application_name"] = "averix-api"

	pool, err := pgxpool.NewWithConfig(ctx, poolCfg)
	if err != nil {
		return nil, fmt.Errorf("create pool: %w", err)
	}

	pingCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	if err := pool.Ping(pingCtx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("ping database: %w", err)
	}
	return &DB{Pool: pool}, nil
}

func (db *DB) Close() { db.Pool.Close() }

func (db *DB) Ping(ctx context.Context) error { return db.Pool.Ping(ctx) }

// Querier is satisfied by both the pool and a transaction, so a store method
// works inside or outside a transaction without duplication.
type Querier interface {
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
}

func (db *DB) Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error) {
	return db.Pool.Query(ctx, sql, args...)
}

func (db *DB) QueryRow(ctx context.Context, sql string, args ...any) pgx.Row {
	return db.Pool.QueryRow(ctx, sql, args...)
}

func (db *DB) Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error) {
	return db.Pool.Exec(ctx, sql, args...)
}

// InTx runs fn inside a transaction, committing on success and rolling back on
// error or panic. Deferred constraint triggers (the specialisation and skill
// caps) only fire at commit, so their violations surface from Commit and are
// translated here like any other constraint error.
func (db *DB) InTx(ctx context.Context, fn func(Querier) error) error {
	tx, err := db.Pool.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return fmt.Errorf("begin transaction: %w", err)
	}
	committed := false
	defer func() {
		if !committed {
			// The parent context may already be cancelled, so the rollback gets
			// its own short-lived one.
			rbCtx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 5*time.Second)
			defer cancel()
			_ = tx.Rollback(rbCtx)
		}
	}()

	if err := fn(tx); err != nil {
		return err
	}
	if err := tx.Commit(ctx); err != nil {
		return fmt.Errorf("commit transaction: %w", err)
	}
	committed = true
	return nil
}

// ── Error inspection ────────────────────────────────────────────────────────
// Stores use these instead of matching on error strings, so a Postgres message
// change cannot silently turn a conflict into a 500.

func IsNoRows(err error) bool { return errors.Is(err, pgx.ErrNoRows) }

func pgErr(err error) *pgconn.PgError {
	var e *pgconn.PgError
	if errors.As(err, &e) {
		return e
	}
	return nil
}

// IsUniqueViolation reports a duplicate key, optionally for a named constraint.
func IsUniqueViolation(err error, constraint ...string) bool {
	e := pgErr(err)
	if e == nil || e.Code != "23505" {
		return false
	}
	if len(constraint) == 0 {
		return true
	}
	for _, c := range constraint {
		if e.ConstraintName == c {
			return true
		}
	}
	return false
}

func IsForeignKeyViolation(err error) bool {
	e := pgErr(err)
	return e != nil && e.Code == "23503"
}

// IsCheckViolation covers both row CHECK constraints and the RAISE EXCEPTION
// with SQLSTATE 23514 used by the cap triggers.
func IsCheckViolation(err error, constraint ...string) bool {
	e := pgErr(err)
	if e == nil || e.Code != "23514" {
		return false
	}
	if len(constraint) == 0 {
		return true
	}
	for _, c := range constraint {
		if e.ConstraintName == c {
			return true
		}
	}
	return false
}

// CheckMessage returns the message a cap trigger raised, for turning a database
// rule into a field-level validation error.
func CheckMessage(err error) string {
	if e := pgErr(err); e != nil {
		return e.Message
	}
	return ""
}

func IsSerializationFailure(err error) bool {
	e := pgErr(err)
	return e != nil && (e.Code == "40001" || e.Code == "40P01")
}

// Stats exposes pool numbers for the readiness endpoint.
func (db *DB) Stats() map[string]any {
	s := db.Pool.Stat()
	return map[string]any{
		"acquired":         s.AcquiredConns(),
		"idle":             s.IdleConns(),
		"total":            s.TotalConns(),
		"max":              s.MaxConns(),
		"acquire_count":    s.AcquireCount(),
		"canceled_acquire": s.CanceledAcquireCount(),
	}
}

// Array prepares a slice for a NOT NULL array column.
//
// A nil Go slice is written as SQL NULL, which a `text[] NOT NULL DEFAULT '{}'`
// column refuses — and the difference between "no topics" and "unknown
// topics" is not one the schema wants to carry. Every write to such a column
// goes through this, so an absent field means an empty array rather than a
// failed insert.
func Array[T any](values []T) []T {
	if values == nil {
		return []T{}
	}
	return values
}
