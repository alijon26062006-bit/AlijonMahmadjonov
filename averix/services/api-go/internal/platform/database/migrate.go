package database

import (
	"context"
	"crypto/sha256"
	"embed"
	"encoding/hex"
	"errors"
	"fmt"
	"io/fs"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

// Migrations are embedded so the binary carries its own schema: a deployment is
// one artefact, and `averixctl migrate` cannot drift from the image it ships in.
//
//go:embed all:migrations
var migrationFS embed.FS

type Migration struct {
	Version  int
	Name     string
	UpSQL    string
	DownSQL  string
	Checksum string
}

type AppliedMigration struct {
	Version    int
	Name       string
	Checksum   string
	AppliedAt  time.Time
	DurationMS int64
}

// LoadMigrations reads the embedded set, pairing up/down files by version.
func LoadMigrations() ([]Migration, error) {
	entries, err := fs.ReadDir(migrationFS, "migrations")
	if err != nil {
		return nil, fmt.Errorf("read embedded migrations: %w", err)
	}

	byVersion := map[int]*Migration{}
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		name := e.Name()
		if !strings.HasSuffix(name, ".sql") {
			continue
		}
		// 0004_profiles.up.sql -> version 4, name "profiles", direction "up"
		parts := strings.SplitN(name, "_", 2)
		if len(parts) != 2 {
			return nil, fmt.Errorf("migration %q does not start with a version prefix", name)
		}
		version, err := strconv.Atoi(parts[0])
		if err != nil {
			return nil, fmt.Errorf("migration %q has a non-numeric version: %w", name, err)
		}
		rest := strings.TrimSuffix(parts[1], ".sql")
		direction := "up"
		switch {
		case strings.HasSuffix(rest, ".up"):
			rest, direction = strings.TrimSuffix(rest, ".up"), "up"
		case strings.HasSuffix(rest, ".down"):
			rest, direction = strings.TrimSuffix(rest, ".down"), "down"
		default:
			return nil, fmt.Errorf("migration %q must end in .up.sql or .down.sql", name)
		}

		body, err := migrationFS.ReadFile("migrations/" + name)
		if err != nil {
			return nil, fmt.Errorf("read %s: %w", name, err)
		}
		m := byVersion[version]
		if m == nil {
			m = &Migration{Version: version, Name: rest}
			byVersion[version] = m
		}
		if direction == "up" {
			m.UpSQL = string(body)
			sum := sha256.Sum256(body)
			m.Checksum = hex.EncodeToString(sum[:])
		} else {
			m.DownSQL = string(body)
		}
	}

	out := make([]Migration, 0, len(byVersion))
	for _, m := range byVersion {
		if m.UpSQL == "" {
			return nil, fmt.Errorf("migration %d (%s) has no .up.sql", m.Version, m.Name)
		}
		out = append(out, *m)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Version < out[j].Version })
	return out, nil
}

const migrationsTable = `
CREATE TABLE IF NOT EXISTS schema_migrations (
  version     int PRIMARY KEY,
  name        text NOT NULL,
  checksum    text NOT NULL,
  duration_ms bigint NOT NULL,
  applied_at  timestamptz NOT NULL DEFAULT now()
)`

// Migrate applies every pending migration, each in its own transaction.
//
// An advisory lock serialises concurrent runners: rolling deployments start
// several API containers at once and only one may migrate. The others block,
// then find nothing to do.
func (db *DB) Migrate(ctx context.Context) ([]int, error) {
	migrations, err := LoadMigrations()
	if err != nil {
		return nil, err
	}

	conn, err := db.Pool.Acquire(ctx)
	if err != nil {
		return nil, fmt.Errorf("acquire connection: %w", err)
	}
	defer conn.Release()

	// Arbitrary but stable key; any other AVERIX process uses the same one.
	const lockKey = 0x41564558 // "AVEX"
	if _, err := conn.Exec(ctx, "SELECT pg_advisory_lock($1)", lockKey); err != nil {
		return nil, fmt.Errorf("acquire migration lock: %w", err)
	}
	defer func() {
		unlockCtx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 5*time.Second)
		defer cancel()
		_, _ = conn.Exec(unlockCtx, "SELECT pg_advisory_unlock($1)", lockKey)
	}()

	if _, err := conn.Exec(ctx, migrationsTable); err != nil {
		return nil, fmt.Errorf("create schema_migrations: %w", err)
	}

	applied := map[int]AppliedMigration{}
	rows, err := conn.Query(ctx, `SELECT version, name, checksum, applied_at FROM schema_migrations`)
	if err != nil {
		return nil, fmt.Errorf("read schema_migrations: %w", err)
	}
	for rows.Next() {
		var a AppliedMigration
		if err := rows.Scan(&a.Version, &a.Name, &a.Checksum, &a.AppliedAt); err != nil {
			rows.Close()
			return nil, fmt.Errorf("scan schema_migrations: %w", err)
		}
		applied[a.Version] = a
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate schema_migrations: %w", err)
	}

	var ran []int
	for _, m := range migrations {
		if prev, ok := applied[m.Version]; ok {
			// An edited migration is a deployment bug, not something to fix
			// silently: the database and the code now disagree.
			if prev.Checksum != m.Checksum {
				return ran, fmt.Errorf(
					"migration %04d_%s was modified after it was applied (recorded %s, found %s); "+
						"add a new migration instead of editing an applied one",
					m.Version, m.Name, prev.Checksum[:12], m.Checksum[:12])
			}
			continue
		}

		start := time.Now()
		err := func() error {
			tx, err := conn.Begin(ctx)
			if err != nil {
				return err
			}
			defer func() { _ = tx.Rollback(context.WithoutCancel(ctx)) }()

			if _, err := tx.Exec(ctx, m.UpSQL); err != nil {
				return err
			}
			if _, err := tx.Exec(ctx,
				`INSERT INTO schema_migrations (version, name, checksum, duration_ms)
				 VALUES ($1, $2, $3, $4)`,
				m.Version, m.Name, m.Checksum, time.Since(start).Milliseconds()); err != nil {
				return err
			}
			return tx.Commit(ctx)
		}()
		if err != nil {
			return ran, fmt.Errorf("apply migration %04d_%s: %w", m.Version, m.Name, err)
		}
		ran = append(ran, m.Version)
	}
	return ran, nil
}

// Rollback reverts the newest applied migration. Deliberately one at a time:
// unwinding several steps in one command is how production data gets lost.
func (db *DB) Rollback(ctx context.Context) (int, error) {
	migrations, err := LoadMigrations()
	if err != nil {
		return 0, err
	}
	byVersion := map[int]Migration{}
	for _, m := range migrations {
		byVersion[m.Version] = m
	}

	var version int
	var name string
	err = db.Pool.QueryRow(ctx,
		`SELECT version, name FROM schema_migrations ORDER BY version DESC LIMIT 1`).
		Scan(&version, &name)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, errors.New("no migrations have been applied")
	}
	if err != nil {
		return 0, fmt.Errorf("find latest migration: %w", err)
	}

	m, ok := byVersion[version]
	if !ok {
		return 0, fmt.Errorf("migration %04d_%s is applied but not present in this build", version, name)
	}
	if strings.TrimSpace(m.DownSQL) == "" {
		return 0, fmt.Errorf("migration %04d_%s has no down migration", version, name)
	}

	err = db.InTx(ctx, func(q Querier) error {
		if _, err := q.Exec(ctx, m.DownSQL); err != nil {
			return err
		}
		_, err := q.Exec(ctx, `DELETE FROM schema_migrations WHERE version = $1`, version)
		return err
	})
	if err != nil {
		return 0, fmt.Errorf("roll back %04d_%s: %w", version, name, err)
	}
	return version, nil
}

// MigrationStatus lists every known migration and whether it is applied, for
// `averixctl migrate status` and the admin panel's system page.
func (db *DB) MigrationStatus(ctx context.Context) ([]map[string]any, error) {
	migrations, err := LoadMigrations()
	if err != nil {
		return nil, err
	}
	applied := map[int]time.Time{}
	rows, err := db.Pool.Query(ctx, `SELECT version, applied_at FROM schema_migrations`)
	if err == nil {
		for rows.Next() {
			var v int
			var at time.Time
			if err := rows.Scan(&v, &at); err == nil {
				applied[v] = at
			}
		}
		rows.Close()
	}

	out := make([]map[string]any, 0, len(migrations))
	for _, m := range migrations {
		row := map[string]any{
			"version":  m.Version,
			"name":     m.Name,
			"applied":  false,
			"has_down": strings.TrimSpace(m.DownSQL) != "",
		}
		if at, ok := applied[m.Version]; ok {
			row["applied"] = true
			row["applied_at"] = at
		}
		out = append(out, row)
	}
	return out, nil
}
