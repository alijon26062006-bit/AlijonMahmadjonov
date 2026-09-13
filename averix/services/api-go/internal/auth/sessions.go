package auth

import (
	"context"
	"errors"
	"fmt"
	"net"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/security"
)

// Session is a server-side session. Nothing about the user's authorisation
// lives in the cookie, so revoking a session takes effect on the next request
// rather than when a token happens to expire.
type Session struct {
	ID         uuid.UUID
	UserID     uuid.UUID
	ActiveRole security.Role
	CSRFToken  string
	UserAgent  string
	IP         string
	ExpiresAt  time.Time
	LastUsedAt time.Time
	CreatedAt  time.Time
}

var ErrSessionInvalid = errors.New("session is not valid")

// CreateSession issues a new session and returns the token for the cookie.
func (s *Store) CreateSession(ctx context.Context, userID uuid.UUID, role security.Role,
	userAgent, ip string, ttl time.Duration) (cryptox.SessionToken, *Session, error) {

	token, err := cryptox.NewSessionToken()
	if err != nil {
		return cryptox.SessionToken{}, nil, err
	}
	csrf, err := cryptox.RandomToken(32)
	if err != nil {
		return cryptox.SessionToken{}, nil, err
	}

	var sess Session
	err = s.db.QueryRow(ctx, `
		INSERT INTO sessions (user_id, selector, verifier_hash, active_role,
		                      user_agent, ip, csrf_token, expires_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, now() + $8::interval)
		RETURNING id, user_id, active_role, csrf_token, expires_at, last_used_at, created_at`,
		userID, token.Selector, cryptox.HashVerifier(token.Verifier), role,
		truncateUA(userAgent), nullIP(ip), csrf,
		fmt.Sprintf("%d seconds", int(ttl.Seconds()))).
		Scan(&sess.ID, &sess.UserID, &sess.ActiveRole, &sess.CSRFToken,
			&sess.ExpiresAt, &sess.LastUsedAt, &sess.CreatedAt)
	if err != nil {
		return cryptox.SessionToken{}, nil, fmt.Errorf("create session: %w", err)
	}
	return token, &sess, nil
}

// ResolveSession turns a cookie value into an identity.
//
// The verifier is compared in constant time against its stored hash, so a
// timing oracle cannot be used to discover a valid session. An expired,
// revoked, or idle-timed-out session is indistinguishable from a wrong one.
func (s *Store) ResolveSession(ctx context.Context, raw string, idleTTL time.Duration) (*security.Identity, error) {
	token, err := cryptox.ParseSessionToken(raw)
	if err != nil {
		return nil, ErrSessionInvalid
	}

	var (
		sessionID        uuid.UUID
		userID           uuid.UUID
		verifierHash     []byte
		activeRole       string
		csrfToken        string
		expiresAt        time.Time
		lastUsedAt       time.Time
		username         string
		email            string
		status           string
		emailVerified    bool
		identityVerified bool
		roles            []string
		granted          []string
	)
	err = s.db.QueryRow(ctx, `
		SELECT s.id, s.user_id, s.verifier_hash, s.active_role, s.csrf_token,
		       s.expires_at, s.last_used_at,
		       u.username, u.email, u.status,
		       u.email_verified_at IS NOT NULL, u.identity_verified_at IS NOT NULL,
		       coalesce(array_agg(r.role) FILTER (WHERE r.role IS NOT NULL), '{}'),
		       coalesce(array_agg(DISTINCT g.permission) FILTER (WHERE g.permission IS NOT NULL), '{}')
		FROM sessions s
		JOIN users u ON u.id = s.user_id
		LEFT JOIN user_roles r ON r.user_id = u.id
		LEFT JOIN admin_permission_grants g ON g.user_id = u.id AND g.revoked_at IS NULL
		WHERE s.selector = $1
		  AND s.revoked_at IS NULL
		  AND s.expires_at > now()
		  AND u.deleted_at IS NULL
		GROUP BY s.id, u.id`, token.Selector).
		Scan(&sessionID, &userID, &verifierHash, &activeRole, &csrfToken,
			&expiresAt, &lastUsedAt, &username, &email, &status,
			&emailVerified, &identityVerified, &roles, &granted)
	if database.IsNoRows(err) {
		return nil, ErrSessionInvalid
	}
	if err != nil {
		return nil, fmt.Errorf("resolve session: %w", err)
	}

	if !cryptox.VerifierMatches(verifierHash, token.Verifier) {
		// A valid selector with a wrong verifier means the cookie was tampered
		// with or an old one is being replayed. Revoke the session: whichever
		// it is, it should not continue to work.
		_ = s.RevokeSession(context.WithoutCancel(ctx), sessionID)
		return nil, ErrSessionInvalid
	}

	// Idle timeout, separate from absolute expiry: an abandoned session on a
	// shared machine stops working long before its 30-day life is up.
	if idleTTL > 0 && time.Since(lastUsedAt) > idleTTL {
		_ = s.RevokeSession(context.WithoutCancel(ctx), sessionID)
		return nil, ErrSessionInvalid
	}

	// A suspended account keeps its session row but is refused here, so the
	// suspension is effective immediately rather than at next sign-in.
	if status == "suspended" || status == "deactivated" {
		return nil, fmt.Errorf("%w: account is %s", ErrSessionInvalid, status)
	}

	// The session's active role must still be held; a revoked role must not
	// keep working until the cookie expires.
	role := security.Role(activeRole)
	held := false
	identity := &security.Identity{
		UserID:           userID,
		SessionID:        sessionID,
		Username:         username,
		Email:            email,
		ActiveRole:       role,
		Status:           status,
		EmailVerified:    emailVerified,
		IdentityVerified: identityVerified,
		CSRFToken:        csrfToken,
	}
	for _, r := range roles {
		identity.Roles = append(identity.Roles, security.Role(r))
		if security.Role(r) == role {
			held = true
		}
	}
	for _, p := range granted {
		identity.Granted = append(identity.Granted, security.Permission(p))
	}
	if !held {
		_ = s.RevokeSession(context.WithoutCancel(ctx), sessionID)
		return nil, fmt.Errorf("%w: role %q is no longer held", ErrSessionInvalid, role)
	}

	// last_used_at drives the idle timeout, so it is refreshed — but only once
	// a minute, to keep a busy session from writing on every request.
	if time.Since(lastUsedAt) > time.Minute {
		go func() {
			bg, cancel := context.WithTimeout(context.WithoutCancel(ctx), 3*time.Second)
			defer cancel()
			_, _ = s.db.Exec(bg,
				`UPDATE sessions SET last_used_at = now() WHERE id = $1`, sessionID)
		}()
	}
	return identity, nil
}

func (s *Store) RevokeSession(ctx context.Context, sessionID uuid.UUID) error {
	_, err := s.db.Exec(ctx,
		`UPDATE sessions SET revoked_at = now() WHERE id = $1 AND revoked_at IS NULL`, sessionID)
	return err
}

// RevokeAllSessions signs a user out everywhere. Called on password change and
// on suspension, where leaving other devices signed in would defeat the point.
func (s *Store) RevokeAllSessions(ctx context.Context, userID uuid.UUID, except uuid.UUID) (int, error) {
	tag, err := s.db.Exec(ctx,
		`UPDATE sessions SET revoked_at = now()
		 WHERE user_id = $1 AND revoked_at IS NULL AND ($2::uuid IS NULL OR id <> $2)`,
		userID, nullUUID(except))
	if err != nil {
		return 0, fmt.Errorf("revoke sessions: %w", err)
	}
	return int(tag.RowsAffected()), nil
}

// SwitchRole re-issues the session's active role.
//
// A new session is not minted: the same cookie continues to work, but the role
// it authorises changes, and the CSRF token is rotated so a form rendered under
// the previous role cannot be submitted against the new one.
func (s *Store) SwitchRole(ctx context.Context, sessionID, userID uuid.UUID, role security.Role) (string, error) {
	csrf, err := cryptox.RandomToken(32)
	if err != nil {
		return "", err
	}
	tag, err := s.db.Exec(ctx, `
		UPDATE sessions SET active_role = $3, csrf_token = $4, last_used_at = now()
		WHERE id = $1 AND user_id = $2 AND revoked_at IS NULL
		  AND EXISTS (SELECT 1 FROM user_roles WHERE user_id = $2 AND role = $3)`,
		sessionID, userID, role, csrf)
	if err != nil {
		return "", fmt.Errorf("switch role: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return "", fmt.Errorf("%w: role %q is not held by this account", ErrSessionInvalid, role)
	}
	return csrf, nil
}

// ActiveSessions lists a user's live sessions for the security settings page.
func (s *Store) ActiveSessions(ctx context.Context, userID uuid.UUID) ([]Session, error) {
	rows, err := s.db.Query(ctx, `
		SELECT id, user_id, active_role, '', coalesce(user_agent, ''),
		       coalesce(host(ip), ''), expires_at, last_used_at, created_at
		FROM sessions
		WHERE user_id = $1 AND revoked_at IS NULL AND expires_at > now()
		ORDER BY last_used_at DESC`, userID)
	if err != nil {
		return nil, fmt.Errorf("list sessions: %w", err)
	}
	defer rows.Close()

	var out []Session
	for rows.Next() {
		var s Session
		if err := rows.Scan(&s.ID, &s.UserID, &s.ActiveRole, &s.CSRFToken,
			&s.UserAgent, &s.IP, &s.ExpiresAt, &s.LastUsedAt, &s.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan session: %w", err)
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

// PurgeExpiredSessions is run by the worker. Revoked and expired rows are kept
// for a week first, so a support question about "I was signed out" can still be
// answered.
func (s *Store) PurgeExpiredSessions(ctx context.Context) (int, error) {
	tag, err := s.db.Exec(ctx, `
		DELETE FROM sessions
		WHERE (expires_at < now() - interval '7 days')
		   OR (revoked_at IS NOT NULL AND revoked_at < now() - interval '7 days')`)
	if err != nil {
		return 0, err
	}
	return int(tag.RowsAffected()), nil
}

// ── Single-use tokens ───────────────────────────────────────────────────────

type TokenPurpose string

const (
	PurposeEmailVerify   TokenPurpose = "email_verify"
	PurposePasswordReset TokenPurpose = "password_reset"
	PurposeEmailChange   TokenPurpose = "email_change"
	PurposeInvite        TokenPurpose = "invite"
)

// IssueToken creates a single-use token and returns the value to send by email.
// Only its hash is stored, so a database leak does not hand over password
// reset links.
func (s *Store) IssueToken(ctx context.Context, userID uuid.UUID, purpose TokenPurpose,
	payload map[string]any, ttl time.Duration) (string, error) {

	token, err := cryptox.RandomToken(32)
	if err != nil {
		return "", err
	}
	if payload == nil {
		payload = map[string]any{}
	}
	_, err = s.db.Exec(ctx, `
		INSERT INTO auth_tokens (user_id, purpose, token_hash, payload, expires_at)
		VALUES ($1, $2, $3, $4, now() + $5::interval)`,
		userID, purpose, cryptox.HashToken(token), payload,
		fmt.Sprintf("%d seconds", int(ttl.Seconds())))
	if err != nil {
		return "", fmt.Errorf("issue token: %w", err)
	}
	return token, nil
}

// ConsumeToken validates and burns a token in one statement, so a link cannot
// be used twice even if it is clicked twice simultaneously.
func (s *Store) ConsumeToken(ctx context.Context, token string, purpose TokenPurpose) (uuid.UUID, map[string]any, error) {
	var (
		userID  *uuid.UUID
		payload map[string]any
	)
	err := s.db.QueryRow(ctx, `
		UPDATE auth_tokens SET consumed_at = now()
		WHERE token_hash = $1 AND purpose = $2
		  AND consumed_at IS NULL AND expires_at > now()
		RETURNING user_id, payload`,
		cryptox.HashToken(token), purpose).Scan(&userID, &payload)
	if database.IsNoRows(err) {
		return uuid.Nil, nil, ErrNotFound
	}
	if err != nil {
		return uuid.Nil, nil, fmt.Errorf("consume token: %w", err)
	}
	if userID == nil {
		return uuid.Nil, payload, nil
	}
	return *userID, payload, nil
}

// InvalidateTokens burns outstanding tokens of a purpose, so requesting a
// second password reset makes the first link stop working.
func (s *Store) InvalidateTokens(ctx context.Context, userID uuid.UUID, purpose TokenPurpose) error {
	_, err := s.db.Exec(ctx,
		`UPDATE auth_tokens SET consumed_at = now()
		 WHERE user_id = $1 AND purpose = $2 AND consumed_at IS NULL`, userID, purpose)
	return err
}

func truncateUA(ua string) any {
	if ua == "" {
		return nil
	}
	if len(ua) > 400 {
		return ua[:400]
	}
	return ua
}

func nullIP(ip string) any {
	if ip == "" {
		return nil
	}
	if net.ParseIP(ip) == nil {
		return nil
	}
	return ip
}

func nullUUID(id uuid.UUID) any {
	if id == uuid.Nil {
		return nil
	}
	return id
}
