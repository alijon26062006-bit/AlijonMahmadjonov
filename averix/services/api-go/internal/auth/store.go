// Package auth owns registration, sign-in, sessions and the middleware that
// turns a cookie into an authenticated identity.
package auth

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/security"
)

type Store struct {
	db *database.DB
}

func NewStore(db *database.DB) *Store { return &Store{db: db} }

var (
	ErrNotFound      = errors.New("not found")
	ErrEmailTaken    = errors.New("email already registered")
	ErrUsernameTaken = errors.New("username already taken")
)

// Account is the row behind a sign-in attempt.
type Account struct {
	ID                 uuid.UUID
	Email              string
	EmailVerifiedAt    *time.Time
	Username           string
	PasswordHash       string
	FullName           string
	Status             string
	SuspendedReason    *string
	IdentityVerifiedAt *time.Time
	FailedLoginCount   int
	LockedUntil        *time.Time
	Roles              []security.Role
	CreatedAt          time.Time
}

func (a *Account) Locked() bool {
	return a.LockedUntil != nil && a.LockedUntil.After(time.Now())
}

const accountColumns = `
	u.id, u.email, u.email_verified_at, u.username, coalesce(u.password_hash, ''),
	u.full_name, u.status, u.suspended_reason, u.identity_verified_at,
	u.failed_login_count, u.locked_until, u.created_at,
	coalesce(array_agg(r.role) FILTER (WHERE r.role IS NOT NULL), '{}')`

func scanAccount(row interface {
	Scan(dest ...any) error
}) (*Account, error) {
	var a Account
	var roles []string
	err := row.Scan(&a.ID, &a.Email, &a.EmailVerifiedAt, &a.Username, &a.PasswordHash,
		&a.FullName, &a.Status, &a.SuspendedReason, &a.IdentityVerifiedAt,
		&a.FailedLoginCount, &a.LockedUntil, &a.CreatedAt, &roles)
	if err != nil {
		return nil, err
	}
	for _, r := range roles {
		a.Roles = append(a.Roles, security.Role(r))
	}
	return &a, nil
}

// AccountByEmail looks up a sign-in candidate. Soft-deleted rows are excluded
// so a deleted account cannot be signed into.
func (s *Store) AccountByEmail(ctx context.Context, email string) (*Account, error) {
	row := s.db.QueryRow(ctx, `
		SELECT `+accountColumns+`
		FROM users u
		LEFT JOIN user_roles r ON r.user_id = u.id
		WHERE u.email = $1 AND u.deleted_at IS NULL
		GROUP BY u.id`, email)
	a, err := scanAccount(row)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("look up account by email: %w", err)
	}
	return a, nil
}

func (s *Store) AccountByID(ctx context.Context, id uuid.UUID) (*Account, error) {
	row := s.db.QueryRow(ctx, `
		SELECT `+accountColumns+`
		FROM users u
		LEFT JOIN user_roles r ON r.user_id = u.id
		WHERE u.id = $1 AND u.deleted_at IS NULL
		GROUP BY u.id`, id)
	a, err := scanAccount(row)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("look up account by id: %w", err)
	}
	return a, nil
}

// EmailAvailable and UsernameAvailable back the live checks in the sign-up
// form. They are deliberately separate from the insert: the unique indexes
// remain the authority, so a race between two sign-ups still ends in one
// account, not two.
func (s *Store) EmailAvailable(ctx context.Context, email string) (bool, error) {
	var exists bool
	err := s.db.QueryRow(ctx,
		`SELECT EXISTS (SELECT 1 FROM users WHERE email = $1 AND deleted_at IS NULL)`,
		email).Scan(&exists)
	return !exists, err
}

func (s *Store) UsernameAvailable(ctx context.Context, username string) (bool, error) {
	var exists bool
	err := s.db.QueryRow(ctx,
		`SELECT EXISTS (SELECT 1 FROM users WHERE username = $1 AND deleted_at IS NULL)`,
		username).Scan(&exists)
	return !exists, err
}

// NewAccount is a registration request that has already been validated.
type NewAccount struct {
	Email        string
	Username     string
	PasswordHash string
	FullName     string
	Role         security.Role
	Locale       string
	Timezone     string
	CountryCode  string
}

// CreateAccount inserts the user, its role and the matching profile row in one
// transaction, so a user can never exist without the profile its interface
// needs.
func (s *Store) CreateAccount(ctx context.Context, in NewAccount) (*Account, error) {
	var id uuid.UUID
	err := s.db.InTx(ctx, func(q database.Querier) error {
		err := q.QueryRow(ctx, `
			INSERT INTO users (email, username, password_hash, full_name, status,
			                   locale, timezone, country_code)
			VALUES ($1, $2, $3, $4, 'active', $5, $6, $7)
			RETURNING id`,
			// NULL rather than an empty string when the account signs in with
			// Google: "no password" and "the password is the empty string" must
			// not be the same value in the column that guards sign-in.
			in.Email, in.Username, nullIfBlank(in.PasswordHash), in.FullName,
			defaultTo(in.Locale, "en"), defaultTo(in.Timezone, "UTC"),
			nullIfBlank(in.CountryCode)).Scan(&id)
		if err != nil {
			switch {
			case database.IsUniqueViolation(err, "users_email_key"):
				return ErrEmailTaken
			case database.IsUniqueViolation(err, "users_username_key"):
				return ErrUsernameTaken
			}
			return fmt.Errorf("insert user: %w", err)
		}

		// An account with no role yet: registration created it, and the next
		// screen asks which side of the marketplace this person is on. No role
		// row and no profile row until they answer — a half-filled developer
		// profile nobody asked for would otherwise exist for everyone who
		// closed the tab.
		if in.Role == "" {
			return nil
		}

		if _, err := q.Exec(ctx,
			`INSERT INTO user_roles (user_id, role) VALUES ($1, $2)`, id, in.Role); err != nil {
			return fmt.Errorf("insert role: %w", err)
		}

		switch in.Role {
		case security.RoleClient:
			_, err = q.Exec(ctx, `INSERT INTO client_profiles (user_id) VALUES ($1)`, id)
		case security.RoleDeveloper:
			// A developer starts at onboarding step 1 and is not searchable
			// until the flow completes, so an empty profile never appears in
			// anyone's results.
			_, err = q.Exec(ctx,
				`INSERT INTO developer_profiles (user_id, onboarding_step, is_searchable)
				 VALUES ($1, 1, false)`, id)
		default:
			return fmt.Errorf("cannot self-register with role %q", in.Role)
		}
		if err != nil {
			return fmt.Errorf("insert profile: %w", err)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return s.AccountByID(ctx, id)
}

// AddRole gives an existing account a second interface, creating the profile
// row it needs. Idempotent.
func (s *Store) AddRole(ctx context.Context, userID uuid.UUID, role security.Role) error {
	return s.db.InTx(ctx, func(q database.Querier) error {
		if _, err := q.Exec(ctx,
			`INSERT INTO user_roles (user_id, role) VALUES ($1, $2)
			 ON CONFLICT (user_id, role) DO NOTHING`, userID, role); err != nil {
			return fmt.Errorf("insert role: %w", err)
		}
		var err error
		switch role {
		case security.RoleClient:
			_, err = q.Exec(ctx,
				`INSERT INTO client_profiles (user_id) VALUES ($1) ON CONFLICT DO NOTHING`, userID)
		case security.RoleDeveloper:
			_, err = q.Exec(ctx,
				`INSERT INTO developer_profiles (user_id, onboarding_step, is_searchable)
				 VALUES ($1, 1, false) ON CONFLICT DO NOTHING`, userID)
		}
		if err != nil {
			return fmt.Errorf("insert profile for role %s: %w", role, err)
		}
		return nil
	})
}

// ── Failed login tracking ───────────────────────────────────────────────────

// RecordFailedLogin increments the counter and locks the account once it passes
// the threshold. This lives in Postgres rather than only in Redis so a cache
// restart cannot reset an attacker's progress.
func (s *Store) RecordFailedLogin(ctx context.Context, userID uuid.UUID, maxAttempts int, lockFor time.Duration) (locked bool, err error) {
	err = s.db.QueryRow(ctx, `
		UPDATE users SET
		  failed_login_count = failed_login_count + 1,
		  locked_until = CASE
		    WHEN failed_login_count + 1 >= $2 THEN now() + $3::interval
		    ELSE locked_until
		  END
		WHERE id = $1
		RETURNING locked_until IS NOT NULL AND locked_until > now()`,
		userID, maxAttempts, fmt.Sprintf("%d seconds", int(lockFor.Seconds()))).Scan(&locked)
	if err != nil {
		return false, fmt.Errorf("record failed login: %w", err)
	}
	return locked, nil
}

func (s *Store) ClearFailedLogins(ctx context.Context, userID uuid.UUID) error {
	_, err := s.db.Exec(ctx,
		`UPDATE users SET failed_login_count = 0, locked_until = NULL, last_seen_at = now()
		 WHERE id = $1`, userID)
	return err
}

func (s *Store) UpdatePasswordHash(ctx context.Context, userID uuid.UUID, hash string) error {
	_, err := s.db.Exec(ctx,
		`UPDATE users SET password_hash = $2, updated_at = now() WHERE id = $1`, userID, hash)
	return err
}

func (s *Store) MarkEmailVerified(ctx context.Context, userID uuid.UUID) error {
	_, err := s.db.Exec(ctx,
		`UPDATE users SET email_verified_at = coalesce(email_verified_at, now()),
		                  status = CASE WHEN status = 'pending' THEN 'active' ELSE status END,
		                  updated_at = now()
		 WHERE id = $1`, userID)
	return err
}

func (s *Store) TouchLastSeen(ctx context.Context, userID uuid.UUID) {
	// Best-effort presence: a failure here is not worth failing a request over.
	_, _ = s.db.Exec(context.WithoutCancel(ctx),
		`UPDATE users SET last_seen_at = now() WHERE id = $1`, userID)
}

func defaultTo(v, fallback string) string {
	if v == "" {
		return fallback
	}
	return v
}

func nullIfBlank(v string) any {
	if v == "" {
		return nil
	}
	return v
}

// GrantedPermissions lists the permissions handed to an account by name, on
// top of whatever its role already grants.
func (s *Store) GrantedPermissions(ctx context.Context, userID uuid.UUID) ([]security.Permission, error) {
	rows, err := s.db.Query(ctx, `
		SELECT permission FROM admin_permission_grants
		WHERE user_id = $1 AND revoked_at IS NULL`, userID)
	if err != nil {
		return nil, fmt.Errorf("list granted permissions: %w", err)
	}
	defer rows.Close()

	var out []security.Permission
	for rows.Next() {
		var p string
		if err := rows.Scan(&p); err != nil {
			return nil, err
		}
		out = append(out, security.Permission(p))
	}
	return out, rows.Err()
}

// PasswordHash returns the stored hash for an account, for the places that
// re-check a password mid-session rather than at sign-in.
func (s *Store) PasswordHash(ctx context.Context, userID uuid.UUID) (string, error) {
	var hash string
	err := s.db.QueryRow(ctx,
		`SELECT password_hash FROM users WHERE id = $1 AND deleted_at IS NULL`, userID).Scan(&hash)
	if database.IsNoRows(err) {
		return "", ErrNotFound
	}
	if err != nil {
		return "", fmt.Errorf("load password hash: %w", err)
	}
	return hash, nil
}
