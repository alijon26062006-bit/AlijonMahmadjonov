// Package settings serves the runtime configuration an administrator can
// change without a deploy, and the feature flags that gate incomplete work.
//
// Values are cached briefly: a settings read happens on almost every request,
// and a change that takes thirty seconds to appear is an acceptable trade for
// not hitting the database each time.
package settings

import (
	"context"
	"encoding/json"
	"strconv"
	"sync"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/logx"
)

const cacheTTL = 30 * time.Second

type Store struct {
	db *database.DB

	mu       sync.RWMutex
	values   map[string]json.RawMessage
	flags    map[string]Flag
	loadedAt time.Time
}

type Flag struct {
	Key             string      `json:"key"`
	Description     string      `json:"description,omitempty"`
	Enabled         bool        `json:"enabled"`
	RolloutPercent  int         `json:"rollout_percent"`
	EnabledForRoles []string    `json:"enabled_for_roles,omitempty"`
	EnabledForUsers []uuid.UUID `json:"-"`
}

func NewStore(db *database.DB) *Store {
	return &Store{db: db, values: map[string]json.RawMessage{}, flags: map[string]Flag{}}
}

// refresh reloads the cache when it has expired. A failure leaves the previous
// values in place: stale settings are better than none.
func (s *Store) refresh(ctx context.Context) {
	s.mu.RLock()
	fresh := time.Since(s.loadedAt) < cacheTTL
	s.mu.RUnlock()
	if fresh {
		return
	}

	values := map[string]json.RawMessage{}
	rows, err := s.db.Query(ctx, `SELECT key, value FROM platform_settings`)
	if err != nil {
		logx.From(ctx).Warn("could not load platform settings", "error", err)
		return
	}
	for rows.Next() {
		var key string
		var raw []byte
		if err := rows.Scan(&key, &raw); err != nil {
			rows.Close()
			return
		}
		values[key] = raw
	}
	rows.Close()

	flags := map[string]Flag{}
	rows, err = s.db.Query(ctx, `
		SELECT key, coalesce(description, ''), is_enabled, rollout_percent,
		       enabled_for_roles, enabled_for_users
		FROM feature_flags`)
	if err != nil {
		logx.From(ctx).Warn("could not load feature flags", "error", err)
		return
	}
	for rows.Next() {
		var f Flag
		if err := rows.Scan(&f.Key, &f.Description, &f.Enabled, &f.RolloutPercent,
			&f.EnabledForRoles, &f.EnabledForUsers); err != nil {
			rows.Close()
			return
		}
		flags[f.Key] = f
	}
	rows.Close()

	s.mu.Lock()
	s.values = values
	s.flags = flags
	s.loadedAt = time.Now()
	s.mu.Unlock()
}

func (s *Store) raw(ctx context.Context, key string) (json.RawMessage, bool) {
	s.refresh(ctx)
	s.mu.RLock()
	defer s.mu.RUnlock()
	v, ok := s.values[key]
	return v, ok
}

// Int reads an integer setting, falling back when it is absent or malformed.
func (s *Store) Int(ctx context.Context, key string, fallback int) int {
	raw, ok := s.raw(ctx, key)
	if !ok {
		return fallback
	}
	var n int
	if err := json.Unmarshal(raw, &n); err != nil {
		return fallback
	}
	return n
}

func (s *Store) Bool(ctx context.Context, key string, fallback bool) bool {
	raw, ok := s.raw(ctx, key)
	if !ok {
		return fallback
	}
	var b bool
	if err := json.Unmarshal(raw, &b); err != nil {
		return fallback
	}
	return b
}

func (s *Store) String(ctx context.Context, key, fallback string) string {
	raw, ok := s.raw(ctx, key)
	if !ok {
		return fallback
	}
	var str string
	if err := json.Unmarshal(raw, &str); err != nil {
		return fallback
	}
	return str
}

// Int64 reads a setting that may be stored as a number or as a string, which
// is what happens when a value exceeds what JSON numbers represent exactly.
func (s *Store) Int64(ctx context.Context, key string, fallback int64) int64 {
	raw, ok := s.raw(ctx, key)
	if !ok {
		return fallback
	}
	var n int64
	if err := json.Unmarshal(raw, &n); err == nil {
		return n
	}
	var str string
	if err := json.Unmarshal(raw, &str); err == nil {
		if parsed, err := strconv.ParseInt(str, 10, 64); err == nil {
			return parsed
		}
	}
	return fallback
}

// Set writes a setting and invalidates the cache.
func (s *Store) Set(ctx context.Context, key string, value any, by uuid.UUID) error {
	raw, err := json.Marshal(value)
	if err != nil {
		return err
	}
	if _, err := s.db.Exec(ctx, `
		INSERT INTO platform_settings (key, value, updated_by)
		VALUES ($1, $2, $3)
		ON CONFLICT (key) DO UPDATE SET value = excluded.value,
		                               updated_by = excluded.updated_by,
		                               updated_at = now()`,
		key, raw, nullUUID(by)); err != nil {
		return err
	}
	s.invalidate()
	return nil
}

// Invalidate drops the cached snapshot.
//
// Exported because settings can change outside this process — another API
// instance, a migration, or a test resetting its fixtures — and a thirty
// second window of stale configuration is a confusing thing to debug.
func (s *Store) Invalidate() { s.invalidate() }

// Public returns the settings the web app is allowed to read, so the client
// knows the upload limits and which features are on without a private
// endpoint.
func (s *Store) Public(ctx context.Context) (map[string]any, error) {
	rows, err := s.db.Query(ctx,
		`SELECT key, value FROM platform_settings WHERE scope = 'public'`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	out := map[string]any{}
	for rows.Next() {
		var key string
		var raw []byte
		if err := rows.Scan(&key, &raw); err != nil {
			return nil, err
		}
		var value any
		if err := json.Unmarshal(raw, &value); err == nil {
			out[key] = value
		}
	}
	return out, rows.Err()
}

// ── Feature flags ───────────────────────────────────────────────────────────

// Enabled reports whether a flag is on for a specific user.
//
// The rollout percentage is resolved from a stable hash of the user id, so a
// user does not flip in and out of a partial rollout between requests.
func (s *Store) Enabled(ctx context.Context, key string, userID uuid.UUID, role string) bool {
	s.refresh(ctx)
	s.mu.RLock()
	flag, ok := s.flags[key]
	s.mu.RUnlock()
	if !ok {
		// An unknown flag is off. A typo must not silently enable something.
		return false
	}
	if !flag.Enabled {
		return false
	}

	for _, id := range flag.EnabledForUsers {
		if id == userID {
			return true
		}
	}
	for _, r := range flag.EnabledForRoles {
		if r == role {
			return true
		}
	}
	switch {
	case flag.RolloutPercent >= 100:
		return true
	case flag.RolloutPercent <= 0:
		return false
	}
	return bucketOf(userID) < flag.RolloutPercent
}

// bucketOf maps a user id onto 0-99 deterministically.
func bucketOf(id uuid.UUID) int {
	// FNV-1a over the raw bytes: cheap, stable, and spread evenly enough for
	// a percentage rollout.
	const (
		offset uint32 = 2166136261
		prime  uint32 = 16777619
	)
	hash := offset
	for _, b := range id {
		hash ^= uint32(b)
		hash *= prime
	}
	return int(hash % 100)
}

// Flags lists every flag for the admin panel.
func (s *Store) Flags(ctx context.Context) ([]Flag, error) {
	s.refresh(ctx)
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]Flag, 0, len(s.flags))
	for _, f := range s.flags {
		out = append(out, f)
	}
	return out, nil
}

func (s *Store) SetFlag(ctx context.Context, key string, enabled bool, rollout int, by uuid.UUID) error {
	if rollout < 0 {
		rollout = 0
	}
	if rollout > 100 {
		rollout = 100
	}
	if _, err := s.db.Exec(ctx, `
		INSERT INTO feature_flags (key, is_enabled, rollout_percent, updated_by)
		VALUES ($1, $2, $3, $4)
		ON CONFLICT (key) DO UPDATE SET is_enabled = excluded.is_enabled,
		                               rollout_percent = excluded.rollout_percent,
		                               updated_by = excluded.updated_by,
		                               updated_at = now()`,
		key, enabled, rollout, nullUUID(by)); err != nil {
		return err
	}
	s.invalidate()
	return nil
}

func (s *Store) invalidate() {
	s.mu.Lock()
	s.loadedAt = time.Time{}
	s.mu.Unlock()
}

func nullUUID(id uuid.UUID) any {
	if id == uuid.Nil {
		return nil
	}
	return id
}
