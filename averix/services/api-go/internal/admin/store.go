package admin

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/database"
)

var ErrNotFound = errors.New("not found")

type Store struct{ db *database.DB }

func NewStore(db *database.DB) *Store { return &Store{db: db} }

// ── Overview ────────────────────────────────────────────────────────────────

func (s *Store) Overview(ctx context.Context) (*Overview, error) {
	var o Overview
	err := s.db.QueryRow(ctx, `
		SELECT
		  (SELECT count(*) FROM users WHERE deleted_at IS NULL),
		  (SELECT count(*) FROM user_roles WHERE role = 'client'),
		  (SELECT count(*) FROM user_roles WHERE role = 'developer'),
		  (SELECT count(*) FROM developer_profiles WHERE is_searchable AND onboarding_completed_at IS NOT NULL),
		  (SELECT count(*) FROM users WHERE created_at > now() - interval '7 days'),
		  (SELECT count(*) FROM users WHERE status = 'suspended'),
		  (SELECT count(*) FROM projects WHERE status = 'open' AND visibility = 'public'),
		  (SELECT count(*) FROM services WHERE status = 'active' AND moderation_state = 'approved'),
		  (SELECT count(*) FROM contracts WHERE status IN ('pending_funding','active','paused','submitted')),
		  (SELECT count(*) FROM contracts WHERE status = 'completed' AND completed_at >= date_trunc('month', now())),
		  (SELECT count(*) FROM proposals WHERE created_at > now() - interval '7 days'),
		  (SELECT count(*) FROM milestones WHERE status = 'disputed'),
		  (SELECT count(*) FROM reviews WHERE published_at IS NOT NULL),
		  (SELECT count(*) FROM moderation_queue WHERE status = 'pending'),
		  (SELECT count(*) FROM moderation_queue WHERE status = 'escalated'),
		  (SELECT count(*) FROM reports WHERE status = 'open')`).
		Scan(&o.Users.Total, &o.Users.Clients, &o.Users.Freelancers, &o.Users.Listed, &o.Users.NewThisWeek,
			&o.Users.Suspended, &o.Marketplace.OpenProjects, &o.Marketplace.ActiveServices,
			&o.Marketplace.ActiveContracts, &o.Marketplace.CompletedMonth, &o.Marketplace.ProposalsWeek,
			&o.Marketplace.OpenDisputes, &o.Marketplace.PublishedReviews,
			&o.Attention.ModerationPending, &o.Attention.ModerationEscalated, &o.Attention.OpenReports)
	if err != nil {
		return nil, fmt.Errorf("overview counts: %w", err)
	}

	rows, err := s.db.Query(ctx, `
		SELECT btrim(currency), coalesce(sum(amount_minor), 0), coalesce(sum(fee_minor), 0), count(*)
		FROM contracts
		WHERE status = 'completed' AND completed_at >= date_trunc('month', now())
		GROUP BY currency ORDER BY sum(amount_minor) DESC`)
	if err != nil {
		return nil, fmt.Errorf("overview money: %w", err)
	}
	defer rows.Close()
	o.Money = []MoneyRow{}
	for rows.Next() {
		var m MoneyRow
		if err := rows.Scan(&m.Currency, &m.GrossMinor, &m.FeeMinor, &m.Contracts); err != nil {
			return nil, err
		}
		o.Money = append(o.Money, m)
	}
	return &o, rows.Err()
}

func (s *Store) PendingPayments(ctx context.Context) int {
	var n int
	_ = s.db.QueryRow(ctx, `SELECT count(*) FROM payment_intents WHERE status IN ('requires_action','pending')`).Scan(&n)
	return n
}

// ── Users ───────────────────────────────────────────────────────────────────

const userColumns = `
	u.id, u.username, u.full_name, u.email, u.status,
	coalesce((SELECT array_agg(r.role ORDER BY r.role) FROM user_roles r WHERE r.user_id = u.id), '{}'),
	u.email_verified_at IS NOT NULL, u.identity_verified_at IS NOT NULL,
	coalesce(u.suspended_reason, ''), u.suspended_until, u.created_at, u.last_seen_at`

func scanUser(row interface{ Scan(...any) error }, u *UserRow) error {
	return row.Scan(&u.ID, &u.Username, &u.FullName, &u.Email, &u.Status, &u.Roles,
		&u.EmailVerified, &u.IdentityVerified, &u.SuspendedReason, &u.SuspendedUntil, &u.CreatedAt, &u.LastSeenAt)
}

func (s *Store) Users(ctx context.Context, q UserQuery) ([]UserRow, int, error) {
	args := []any{}
	arg := func(v any) string {
		args = append(args, v)
		return fmt.Sprintf("$%d", len(args))
	}
	where := []string{"u.deleted_at IS NULL"}
	if q.Text != "" {
		p := arg(q.Text)
		where = append(where, fmt.Sprintf(`(u.username ILIKE '%%' || %[1]s || '%%' OR u.full_name ILIKE '%%' || %[1]s || '%%' OR u.email::text ILIKE '%%' || %[1]s || '%%')`, p))
	}
	if q.Status != "" {
		where = append(where, "u.status = "+arg(q.Status))
	}
	if q.Role != "" {
		where = append(where, "EXISTS (SELECT 1 FROM user_roles r WHERE r.user_id = u.id AND r.role = "+arg(q.Role)+")")
	}
	limit := q.Limit
	if limit <= 0 || limit > 100 {
		limit = 30
	}
	offset := q.Offset
	if offset < 0 {
		offset = 0
	}
	clause := strings.Join(where, " AND ")
	var total int
	if err := s.db.QueryRow(ctx, "SELECT count(*) FROM users u WHERE "+clause, args...).Scan(&total); err != nil {
		return nil, 0, err
	}
	rows, err := s.db.Query(ctx, "SELECT "+userColumns+" FROM users u WHERE "+clause+
		fmt.Sprintf(" ORDER BY u.created_at DESC LIMIT %d OFFSET %d", limit, offset), args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	out := []UserRow{}
	for rows.Next() {
		var u UserRow
		if err := scanUser(rows, &u); err != nil {
			return nil, 0, err
		}
		out = append(out, u)
	}
	return out, total, rows.Err()
}

func (s *Store) User(ctx context.Context, id uuid.UUID) (*UserDetail, error) {
	var d UserDetail
	if err := scanUser(s.db.QueryRow(ctx, "SELECT "+userColumns+" FROM users u WHERE u.id = $1 AND u.deleted_at IS NULL", id), &d.UserRow); err != nil {
		if database.IsNoRows(err) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	var country, city *string
	err := s.db.QueryRow(ctx, `
		SELECT u.country_code, u.city,
		       (SELECT count(*) FROM projects p WHERE p.client_id = u.id),
		       (SELECT count(*) FROM contracts c WHERE c.client_id = u.id OR c.developer_id = u.id),
		       (SELECT count(*) FROM contracts c WHERE (c.client_id = u.id OR c.developer_id = u.id)
		          AND c.status IN ('pending_funding','active','paused','submitted','disputed')),
		       (SELECT count(*) FROM reports r WHERE r.subject_type = 'user' AND r.subject_id = u.id),
		       (SELECT count(*) FROM reports r WHERE r.reporter_id = u.id),
		       (SELECT count(*) FROM audit_logs a WHERE a.subject_type = 'user' AND a.subject_id = u.id AND a.action = 'user.warned'),
		       (SELECT count(*) FROM sessions se WHERE se.user_id = u.id AND se.revoked_at IS NULL AND se.expires_at > now()),
		       EXISTS (SELECT 1 FROM github_accounts g WHERE g.user_id = u.id AND g.revoked_at IS NULL),
		       coalesce((SELECT d.is_searchable FROM developer_profiles d WHERE d.user_id = u.id), false)
		FROM users u WHERE u.id = $1`, id).
		Scan(&country, &city, &d.ProjectsPosted, &d.ContractsTotal, &d.ContractsActive, &d.ReportsAgainst,
			&d.ReportsFiled, &d.Warnings, &d.ActiveSessions, &d.GitHubConnected, &d.FreelancerListed)
	if err != nil {
		return nil, err
	}
	if country != nil {
		d.CountryCode = *country
	}
	if city != nil {
		d.City = *city
	}
	return &d, nil
}

func (s *Store) SetSuspended(ctx context.Context, id uuid.UUID, reason string, until *time.Time) error {
	tag, err := s.db.Exec(ctx, `
		UPDATE users SET status = 'suspended', suspended_reason = $2, suspended_until = $3, updated_at = now()
		WHERE id = $1 AND deleted_at IS NULL AND status <> 'deactivated'`, id, reason, until)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	_, _ = s.db.Exec(ctx, `UPDATE developer_profiles SET is_searchable = false WHERE user_id = $1`, id)
	return nil
}

func (s *Store) Unsuspend(ctx context.Context, id uuid.UUID) error {
	tag, err := s.db.Exec(ctx, `
		UPDATE users SET status = 'active', suspended_reason = NULL, suspended_until = NULL, updated_at = now()
		WHERE id = $1 AND status = 'suspended'`, id)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (s *Store) RevokeRole(ctx context.Context, id uuid.UUID, role string) error {
	return s.db.InTx(ctx, func(q database.Querier) error {
		var roles int
		if err := q.QueryRow(ctx, `SELECT count(*) FROM user_roles WHERE user_id = $1`, id).Scan(&roles); err != nil {
			return err
		}
		if roles <= 1 {
			return errLastRole
		}
		tag, err := q.Exec(ctx, `DELETE FROM user_roles WHERE user_id = $1 AND role = $2`, id, role)
		if err != nil {
			return err
		}
		if tag.RowsAffected() == 0 {
			return ErrNotFound
		}
		// A session acting in the revoked role ends now, not at its expiry.
		_, err = q.Exec(ctx, `UPDATE sessions SET revoked_at = now() WHERE user_id = $1 AND active_role = $2 AND revoked_at IS NULL`, id, role)
		return err
	})
}

var errLastRole = errors.New("cannot revoke the only role")

func (s *Store) VerifyIdentity(ctx context.Context, id uuid.UUID, verified bool) error {
	tag, err := s.db.Exec(ctx, `
		UPDATE users SET identity_verified_at = CASE WHEN $2 THEN coalesce(identity_verified_at, now()) ELSE NULL END,
		                 updated_at = now()
		WHERE id = $1 AND deleted_at IS NULL`, id, verified)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

// ── Settings ────────────────────────────────────────────────────────────────

func (s *Store) Settings(ctx context.Context) ([]SettingRow, error) {
	rows, err := s.db.Query(ctx, `SELECT key, value, coalesce(description, ''), scope, updated_at FROM platform_settings`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	stored := map[string]SettingRow{}
	for rows.Next() {
		var r SettingRow
		var raw []byte
		if err := rows.Scan(&r.Key, &raw, &r.Description, &r.Scope, &r.UpdatedAt); err != nil {
			return nil, err
		}
		_ = json.Unmarshal(raw, &r.Value)
		stored[r.Key] = r
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	out := make([]SettingRow, 0, len(catalogue))
	for key, spec := range catalogue {
		row := SettingRow{Key: key, Label: spec.Label, Description: spec.Description, Type: spec.Type,
			Group: spec.Group, Min: spec.Min, Max: spec.Max, Scope: "private"}
		if have, ok := stored[key]; ok {
			row.Value, row.Scope, row.UpdatedAt = have.Value, have.Scope, have.UpdatedAt
			if row.Description == "" {
				row.Description = have.Description
			}
		}
		out = append(out, row)
	}
	sortRows(out)
	return out, nil
}

func sortRows(rows []SettingRow) {
	for i := 1; i < len(rows); i++ {
		for j := i; j > 0 && (rows[j].Group < rows[j-1].Group || (rows[j].Group == rows[j-1].Group && rows[j].Key < rows[j-1].Key)); j-- {
			rows[j], rows[j-1] = rows[j-1], rows[j]
		}
	}
}

// ── Audit ───────────────────────────────────────────────────────────────────

func (s *Store) Audit(ctx context.Context, q AuditQuery) ([]AuditRow, int, error) {
	args := []any{}
	arg := func(v any) string {
		args = append(args, v)
		return fmt.Sprintf("$%d", len(args))
	}
	where := []string{"true"}
	if q.ActorID != nil {
		where = append(where, "a.actor_id = "+arg(*q.ActorID))
	}
	if q.Action != "" {
		where = append(where, "a.action LIKE "+arg(q.Action+"%"))
	}
	if q.SubjectType != "" {
		where = append(where, "a.subject_type = "+arg(q.SubjectType))
	}
	if q.SubjectID != nil {
		where = append(where, "a.subject_id = "+arg(*q.SubjectID))
	}
	if q.Outcome != "" {
		where = append(where, "a.outcome = "+arg(q.Outcome))
	}
	limit := q.Limit
	if limit <= 0 || limit > 200 {
		limit = 50
	}
	offset := q.Offset
	if offset < 0 {
		offset = 0
	}
	clause := strings.Join(where, " AND ")
	var total int
	if err := s.db.QueryRow(ctx, "SELECT count(*) FROM audit_logs a WHERE "+clause, args...).Scan(&total); err != nil {
		return nil, 0, err
	}
	rows, err := s.db.Query(ctx, `
		SELECT a.id, a.actor_id, coalesce(u.username, ''), coalesce(a.actor_role, ''), a.action,
		       coalesce(a.subject_type, ''), a.subject_id, a.outcome, coalesce(a.detail, ''),
		       coalesce(host(a.ip), ''), a.before, a.after, a.created_at
		FROM audit_logs a LEFT JOIN users u ON u.id = a.actor_id
		WHERE `+clause+fmt.Sprintf(" ORDER BY a.created_at DESC LIMIT %d OFFSET %d", limit, offset), args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	out := []AuditRow{}
	for rows.Next() {
		var r AuditRow
		var before, after []byte
		if err := rows.Scan(&r.ID, &r.ActorID, &r.ActorName, &r.ActorRole, &r.Action, &r.SubjectType, &r.SubjectID,
			&r.Outcome, &r.Detail, &r.IP, &before, &after, &r.CreatedAt); err != nil {
			return nil, 0, err
		}
		_ = json.Unmarshal(before, &r.Before)
		_ = json.Unmarshal(after, &r.After)
		out = append(out, r)
	}
	return out, total, rows.Err()
}
