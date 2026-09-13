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
	"github.com/averix/api/internal/platform/money"
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
	coalesce(u.suspended_reason, ''), u.suspended_until, u.created_at, u.last_seen_at,
	coalesce(u.phone, ''), coalesce(u.country_code, ''), coalesce(u.city, ''),
	coalesce((SELECT v.status FROM identity_verifications v
	           WHERE v.user_id = u.id
	           ORDER BY (v.status IN ('draft','submitted','under_review','resubmit_requested')) DESC,
	                    v.created_at DESC LIMIT 1), 'none'),
	coalesce((SELECT d.is_searchable FROM developer_profiles d WHERE d.user_id = u.id), false),
	coalesce((SELECT p.derivatives->'webp'->>'64' FROM developer_photos p
	           WHERE p.user_id = u.id AND p.is_current AND p.moderation_state = 'approved' LIMIT 1), '')`

func scanUser(row interface{ Scan(...any) error }, u *UserRow) error {
	return row.Scan(&u.ID, &u.Username, &u.FullName, &u.Email, &u.Status, &u.Roles,
		&u.EmailVerified, &u.IdentityVerified, &u.SuspendedReason, &u.SuspendedUntil,
		&u.CreatedAt, &u.LastSeenAt,
		&u.Phone, &u.CountryCode, &u.City, &u.IdentityStatus, &u.FreelancerListed, &u.photoKey)
}

func (s *Store) Users(ctx context.Context, q UserQuery) ([]UserRow, int, error) {
	args := []any{}
	arg := func(v any) string {
		args = append(args, v)
		return fmt.Sprintf("$%d", len(args))
	}
	where := []string{"u.deleted_at IS NULL"}
	if q.Text != "" {
		// One box, every way a person is named here: @handle, full name, any
		// part of it, an address, a phone with or without punctuation, or the
		// account's own id pasted from a support ticket.
		text := strings.TrimPrefix(strings.TrimSpace(q.Text), "@")
		p := arg(text)
		digits := arg(digitsOf(text))
		terms := []string{
			fmt.Sprintf("u.username ILIKE '%%' || %[1]s || '%%'", p),
			fmt.Sprintf("u.full_name ILIKE '%%' || %[1]s || '%%'", p),
			fmt.Sprintf("u.email::text ILIKE '%%' || %[1]s || '%%'", p),
			fmt.Sprintf("(%[1]s <> '' AND u.phone_digits LIKE '%%' || %[1]s || '%%')", digits),
		}
		if id, err := uuid.Parse(text); err == nil {
			terms = append(terms, "u.id = "+arg(id))
		} else if short := strings.TrimPrefix(strings.ToLower(text), "avx-"); len(short) >= 6 && short != strings.ToLower(text) {
			// The panel shows accounts as AVX-xxxxxxxx: the first eight
			// characters of the id. Searching for what is on screen must work.
			terms = append(terms, "u.id::text LIKE "+arg(short+"%"))
		}
		where = append(where, "("+strings.Join(terms, " OR ")+")")
	}
	if q.Status != "" {
		where = append(where, "u.status = "+arg(q.Status))
	}
	if q.Role != "" {
		where = append(where, "EXISTS (SELECT 1 FROM user_roles r WHERE r.user_id = u.id AND r.role = "+arg(q.Role)+")")
	}
	switch q.Identity {
	case "":
	case "verified":
		where = append(where, "u.identity_verified_at IS NOT NULL")
	case "unverified":
		where = append(where, "u.identity_verified_at IS NULL")
	case "none":
		where = append(where, "NOT EXISTS (SELECT 1 FROM identity_verifications v WHERE v.user_id = u.id)")
	default:
		where = append(where, "EXISTS (SELECT 1 FROM identity_verifications v WHERE v.user_id = u.id AND v.status = "+arg(q.Identity)+")")
	}
	if q.Country != "" {
		where = append(where, "upper(u.country_code) = "+arg(strings.ToUpper(q.Country)))
	}
	if q.Listed {
		where = append(where, "EXISTS (SELECT 1 FROM developer_profiles d WHERE d.user_id = u.id AND d.is_searchable)")
	}
	if q.Reported {
		where = append(where, "EXISTS (SELECT 1 FROM reports r WHERE r.subject_type = 'user' AND r.subject_id = u.id)")
	}
	if q.Specialisation != "" {
		where = append(where, `EXISTS (
			SELECT 1 FROM developer_profiles d
			JOIN specialisations sp ON sp.id = d.primary_specialisation_id
			WHERE d.user_id = u.id AND sp.slug = `+arg(q.Specialisation)+`)`)
	}
	if q.RegisteredFrom != nil {
		where = append(where, "u.created_at >= "+arg(*q.RegisteredFrom))
	}
	if q.RegisteredTo != nil {
		where = append(where, "u.created_at < "+arg(*q.RegisteredTo))
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
	var timezone, locale *string
	err := s.db.QueryRow(ctx, `
		SELECT u.timezone, u.locale,
		       (SELECT count(*) FROM projects p WHERE p.client_id = u.id),
		       (SELECT count(*) FROM projects p WHERE p.client_id = u.id AND p.status = 'open'),
		       (SELECT count(*) FROM contracts c WHERE c.client_id = u.id OR c.developer_id = u.id),
		       (SELECT count(*) FROM contracts c WHERE (c.client_id = u.id OR c.developer_id = u.id)
		          AND c.status IN ('pending_funding','active','paused','submitted','disputed')),
		       (SELECT count(*) FROM contracts c WHERE (c.client_id = u.id OR c.developer_id = u.id)
		          AND c.status = 'completed'),
		       (SELECT count(*) FROM milestones m
		          JOIN contracts c ON c.id = m.contract_id
		         WHERE (c.client_id = u.id OR c.developer_id = u.id) AND m.status = 'disputed'),
		       (SELECT count(*) FROM reports r WHERE r.subject_type = 'user' AND r.subject_id = u.id),
		       (SELECT count(*) FROM reports r WHERE r.reporter_id = u.id),
		       (SELECT count(*) FROM audit_logs a WHERE a.subject_type = 'user' AND a.subject_id = u.id AND a.action = 'user.warned'),
		       (SELECT count(*) FROM sessions se WHERE se.user_id = u.id AND se.revoked_at IS NULL AND se.expires_at > now()),
		       EXISTS (SELECT 1 FROM github_accounts g WHERE g.user_id = u.id AND g.revoked_at IS NULL),
		       (SELECT max(se.created_at) FROM sessions se WHERE se.user_id = u.id),
		       (SELECT max(a.created_at) FROM audit_logs a
		         WHERE a.actor_id = u.id AND a.action IN ('auth.password_changed','auth.password_reset'))
		FROM users u WHERE u.id = $1`, id).
		Scan(&timezone, &locale, &d.ProjectsPosted, &d.ProjectsOpen, &d.ContractsTotal,
			&d.ContractsActive, &d.ContractsDone, &d.Disputes, &d.ReportsAgainst,
			&d.ReportsFiled, &d.Warnings, &d.ActiveSessions, &d.GitHubConnected,
			&d.LastLoginAt, &d.PasswordChangedAt)
	if err != nil {
		return nil, err
	}
	d.Timezone, d.Locale = derefText(timezone), derefText(locale)
	// Said plainly rather than left blank: an empty field reads as "off",
	// and there is a difference between "this person has not enabled it" and
	// "the product does not offer it yet".
	d.TwoFactor = "not_available"
	d.ProfessionalStatus = professionalStatus(d.FreelancerListed, d.Roles)

	grants, err := s.Grants(ctx, id)
	if err != nil {
		return nil, err
	}
	d.Grants = grants
	return &d, nil
}

func derefText(v *string) string {
	if v == nil {
		return ""
	}
	return *v
}

func professionalStatus(listed bool, roles []string) string {
	isDeveloper := false
	for _, r := range roles {
		if r == "developer" {
			isDeveloper = true
		}
	}
	switch {
	case !isDeveloper:
		return "not_a_freelancer"
	case listed:
		return "published"
	default:
		return "draft"
	}
}

// Grants lists the permissions handed to an account by name.
func (s *Store) Grants(ctx context.Context, userID uuid.UUID) ([]Grant, error) {
	rows, err := s.db.Query(ctx, `
		SELECT g.permission, g.granted_by, b.full_name, g.granted_at, coalesce(g.note, '')
		FROM admin_permission_grants g
		LEFT JOIN users b ON b.id = g.granted_by
		WHERE g.user_id = $1 AND g.revoked_at IS NULL
		ORDER BY g.granted_at`, userID)
	if err != nil {
		return nil, fmt.Errorf("list permission grants: %w", err)
	}
	defer rows.Close()

	out := []Grant{}
	for rows.Next() {
		var g Grant
		var name *string
		if err := rows.Scan(&g.Permission, &g.GrantedBy, &name, &g.GrantedAt, &g.Note); err != nil {
			return nil, err
		}
		g.GrantedName = derefText(name)
		g.Label = permissionLabel(g.Permission)
		out = append(out, g)
	}
	return out, rows.Err()
}

// Grant hands a permission to an account, or updates the note on one it
// already has.
func (s *Store) Grant(ctx context.Context, userID, by uuid.UUID, permission, note string) error {
	_, err := s.db.Exec(ctx, `
		INSERT INTO admin_permission_grants (user_id, permission, granted_by, note)
		VALUES ($1,$2,$3,nullif($4,''))
		ON CONFLICT (user_id, permission) WHERE revoked_at IS NULL
		DO UPDATE SET note = excluded.note, granted_by = excluded.granted_by, granted_at = now()`,
		userID, permission, by, note)
	if err != nil {
		return fmt.Errorf("grant permission: %w", err)
	}
	return nil
}

// Revoke withdraws a permission, keeping the record that it was once held.
func (s *Store) Revoke(ctx context.Context, userID, by uuid.UUID, permission string) error {
	_, err := s.db.Exec(ctx, `
		UPDATE admin_permission_grants
		   SET revoked_at = now(), revoked_by = $3
		 WHERE user_id = $1 AND permission = $2 AND revoked_at IS NULL`, userID, permission, by)
	if err != nil {
		return fmt.Errorf("revoke permission: %w", err)
	}
	return nil
}

// permissionLabel names a permission for the panel.
func permissionLabel(p string) string {
	switch p {
	case "identity_verification.view":
		return "Смотреть документы, удостоверяющие личность"
	case "identity_verification.review":
		return "Принимать решения по проверке личности"
	case "payments.view":
		return "Видеть платежи пользователя"
	case "security.view":
		return "Видеть сеансы и вход в аккаунт"
	case "audit.read":
		return "Читать журналы"
	case "users.view":
		return "Видеть список пользователей"
	}
	return p
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

// digitsOf reduces a phone to the digits it is stored by, so "+7 (999)
// 123-45-67" finds the same account as "9991234567".
func digitsOf(s string) string {
	var b strings.Builder
	for _, r := range s {
		if r >= '0' && r <= '9' {
			b.WriteRune(r)
		}
	}
	if b.Len() < 3 {
		return ""
	}
	return b.String()
}

// SetStatus moves an account between states, recording the reason when there
// is one. A suspension sets its own expiry; a block has none by definition.
func (s *Store) SetStatus(ctx context.Context, id uuid.UUID, status, reason string) error {
	tag, err := s.db.Exec(ctx, `
		UPDATE users
		   SET status = $2,
		       suspended_reason = nullif($3, ''),
		       suspended_until = NULL,
		       updated_at = now()
		 WHERE id = $1 AND deleted_at IS NULL`, id, status, reason)
	if err != nil {
		return fmt.Errorf("set account status: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

// UserProjects is the marketplace history of one account, from both sides.
type UserProjects struct {
	Posted    []ProjectRow  `json:"posted"`
	Contracts []ContractRow `json:"contracts"`
}

type ProjectRow struct {
	ID        uuid.UUID  `json:"id"`
	Slug      string     `json:"slug"`
	Reference string     `json:"reference"`
	Title     string     `json:"title"`
	Status    string     `json:"status"`
	Budget    string     `json:"budget_display,omitempty"`
	Proposals int        `json:"proposals_count"`
	CreatedAt time.Time  `json:"created_at"`
	Published *time.Time `json:"published_at,omitempty"`
}

type ContractRow struct {
	ID          uuid.UUID  `json:"id"`
	Reference   string     `json:"reference"`
	Title       string     `json:"title"`
	Status      string     `json:"status"`
	Role        string     `json:"role"`
	Counterpart string     `json:"counterparty"`
	AmountMinor *int64     `json:"amount_minor,omitempty"`
	Currency    string     `json:"currency,omitempty"`
	CreatedAt   time.Time  `json:"created_at"`
	CompletedAt *time.Time `json:"completed_at,omitempty"`
}

func (s *Store) UserProjects(ctx context.Context, userID uuid.UUID) (*UserProjects, error) {
	out := &UserProjects{Posted: []ProjectRow{}, Contracts: []ContractRow{}}

	rows, err := s.db.Query(ctx, `
		SELECT p.id, p.slug, p.reference, p.title, p.status,
		       p.budget_min_minor, p.budget_max_minor, coalesce(p.currency, 'RUB'),
		       p.proposals_count, p.created_at, p.published_at
		FROM projects p WHERE p.client_id = $1
		ORDER BY p.created_at DESC LIMIT 100`, userID)
	if err != nil {
		return nil, fmt.Errorf("list posted projects: %w", err)
	}
	for rows.Next() {
		var p ProjectRow
		var min, max *int64
		var currency string
		if err := rows.Scan(&p.ID, &p.Slug, &p.Reference, &p.Title, &p.Status,
			&min, &max, &currency, &p.Proposals, &p.CreatedAt, &p.Published); err != nil {
			rows.Close()
			return nil, err
		}
		p.Budget = money.Range(min, max, currency)
		out.Posted = append(out.Posted, p)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}

	rows, err = s.db.Query(ctx, `
		SELECT c.id, c.reference, c.title, c.status,
		       CASE WHEN c.client_id = $1 THEN 'client' ELSE 'developer' END,
		       CASE WHEN c.client_id = $1 THEN dev.full_name ELSE cl.full_name END,
		       c.amount_minor, coalesce(c.currency, ''), c.created_at, c.completed_at
		FROM contracts c
		JOIN users cl ON cl.id = c.client_id
		JOIN users dev ON dev.id = c.developer_id
		WHERE c.client_id = $1 OR c.developer_id = $1
		ORDER BY c.created_at DESC LIMIT 100`, userID)
	if err != nil {
		return nil, fmt.Errorf("list contracts: %w", err)
	}
	defer rows.Close()
	for rows.Next() {
		var c ContractRow
		if err := rows.Scan(&c.ID, &c.Reference, &c.Title, &c.Status, &c.Role,
			&c.Counterpart, &c.AmountMinor, &c.Currency, &c.CreatedAt, &c.CompletedAt); err != nil {
			return nil, err
		}
		out.Contracts = append(out.Contracts, c)
	}
	return out, rows.Err()
}

// PaymentRow is one movement of money, with the destination masked.
type PaymentRow struct {
	ID          uuid.UUID `json:"id"`
	Reference   string    `json:"reference"`
	Direction   string    `json:"direction"`
	AmountMinor int64     `json:"amount_minor"`
	FeeMinor    int64     `json:"fee_minor"`
	Currency    string    `json:"currency"`
	Status      string    `json:"status"`
	Provider    string    `json:"provider"`
	// What the money was for, never who it was paid to in full.
	ContractRef   string     `json:"contract_reference,omitempty"`
	Destination   string     `json:"destination,omitempty"`
	RefundedMinor int64      `json:"refunded_minor"`
	CreatedAt     time.Time  `json:"created_at"`
	CapturedAt    *time.Time `json:"captured_at,omitempty"`
}

func (s *Store) UserPayments(ctx context.Context, userID uuid.UUID) ([]PaymentRow, error) {
	rows, err := s.db.Query(ctx, `
		SELECT pi.id, pi.reference, pi.direction, pi.amount_minor, pi.fee_minor,
		       pi.currency, pi.status, pi.provider_code,
		       coalesce(c.reference, ''), coalesce(pi.refunded_minor, 0),
		       pi.created_at, pi.captured_at,
		       -- Only the three fields a provider may report about an
		       -- instrument, never the payload itself: whatever else a
		       -- provider chose to send back stays in the database.
		       pi.provider_meta -> 'brand', pi.provider_meta -> 'last4',
		       pi.provider_meta -> 'bank'
		FROM payment_intents pi
		LEFT JOIN contracts c ON c.id = pi.contract_id
		WHERE pi.payer_id = $1 OR pi.payee_id = $1
		ORDER BY pi.created_at DESC LIMIT 100`, userID)
	if err != nil {
		return nil, fmt.Errorf("list payments: %w", err)
	}
	defer rows.Close()

	out := []PaymentRow{}
	for rows.Next() {
		var p PaymentRow
		var brand, last4, bank *string
		if err := rows.Scan(&p.ID, &p.Reference, &p.Direction, &p.AmountMinor, &p.FeeMinor,
			&p.Currency, &p.Status, &p.Provider, &p.ContractRef, &p.RefundedMinor,
			&p.CreatedAt, &p.CapturedAt, &brand, &last4, &bank); err != nil {
			return nil, err
		}
		p.Destination = maskedInstrument(derefText(brand), derefText(last4), derefText(bank))
		out = append(out, p)
	}
	return out, rows.Err()
}

// maskedInstrument is everything an administrator is allowed to learn about
// how money moved: enough to match a payment against a bank statement, never
// enough to charge the card again.
//
// The platform stores no card number and no account number — there is no
// column for one. This only shapes what a provider reported back, and takes
// nothing but the last four digits even if the provider sent more.
func maskedInstrument(brand, last4, bank string) string {
	digits := digitsOf(last4)
	if len(digits) > 4 {
		digits = digits[len(digits)-4:]
	}
	parts := make([]string, 0, 3)
	if brand = strings.TrimSpace(brand); brand != "" && len(brand) <= 32 {
		parts = append(parts, brand)
	}
	if digits != "" {
		parts = append(parts, "•••• "+digits)
	}
	if bank = strings.TrimSpace(bank); bank != "" && len(bank) <= 64 {
		parts = append(parts, bank)
	}
	return strings.Join(parts, " · ")
}

// UserSecurity is how an account is being signed into.
type UserSecurity struct {
	TwoFactor         string        `json:"two_factor"`
	Sessions          []SessionRow  `json:"sessions"`
	Events            []SecurityRow `json:"events"`
	GitHubConnected   bool          `json:"github_connected"`
	GitHubLogin       string        `json:"github_login,omitempty"`
	PasswordChangedAt *time.Time    `json:"password_changed_at,omitempty"`
	FailedLogins      int           `json:"failed_logins"`
	LockedUntil       *time.Time    `json:"locked_until,omitempty"`
}

type SessionRow struct {
	ID        uuid.UUID `json:"id"`
	Role      string    `json:"role"`
	UserAgent string    `json:"user_agent,omitempty"`
	IP        string    `json:"ip,omitempty"`
	LastUsed  time.Time `json:"last_used_at"`
	CreatedAt time.Time `json:"created_at"`
	ExpiresAt time.Time `json:"expires_at"`
}

type SecurityRow struct {
	Action    string    `json:"action"`
	Outcome   string    `json:"outcome"`
	IP        string    `json:"ip,omitempty"`
	Detail    string    `json:"detail,omitempty"`
	CreatedAt time.Time `json:"created_at"`
}

func (s *Store) UserSecurity(ctx context.Context, userID uuid.UUID) (*UserSecurity, error) {
	out := &UserSecurity{TwoFactor: "not_available", Sessions: []SessionRow{}, Events: []SecurityRow{}}

	// Neither the password hash nor any token is read here. What an
	// administrator needs is when things happened, not what the secrets are.
	err := s.db.QueryRow(ctx, `
		SELECT u.failed_login_count, u.locked_until,
		       EXISTS (SELECT 1 FROM github_accounts g WHERE g.user_id = u.id AND g.revoked_at IS NULL),
		       coalesce((SELECT g.login FROM github_accounts g
		                  WHERE g.user_id = u.id AND g.revoked_at IS NULL LIMIT 1), ''),
		       (SELECT max(a.created_at) FROM audit_logs a
		         WHERE a.actor_id = u.id AND a.action IN ('auth.password_changed','auth.password_reset'))
		FROM users u WHERE u.id = $1`, userID).
		Scan(&out.FailedLogins, &out.LockedUntil, &out.GitHubConnected, &out.GitHubLogin,
			&out.PasswordChangedAt)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("load security overview: %w", err)
	}

	rows, err := s.db.Query(ctx, `
		SELECT id, active_role, coalesce(user_agent, ''), coalesce(host(ip), ''),
		       last_used_at, created_at, expires_at
		FROM sessions
		WHERE user_id = $1 AND revoked_at IS NULL AND expires_at > now()
		ORDER BY last_used_at DESC LIMIT 20`, userID)
	if err != nil {
		return nil, fmt.Errorf("list sessions: %w", err)
	}
	for rows.Next() {
		var se SessionRow
		if err := rows.Scan(&se.ID, &se.Role, &se.UserAgent, &se.IP,
			&se.LastUsed, &se.CreatedAt, &se.ExpiresAt); err != nil {
			rows.Close()
			return nil, err
		}
		out.Sessions = append(out.Sessions, se)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}

	rows, err = s.db.Query(ctx, `
		SELECT action, outcome, coalesce(host(ip), ''), coalesce(detail, ''), created_at
		FROM audit_logs
		WHERE (actor_id = $1 OR (subject_type = 'user' AND subject_id = $1))
		  AND (action LIKE 'auth.%' OR action = 'access.denied')
		ORDER BY created_at DESC LIMIT 50`, userID)
	if err != nil {
		return nil, fmt.Errorf("list security events: %w", err)
	}
	defer rows.Close()
	for rows.Next() {
		var e SecurityRow
		if err := rows.Scan(&e.Action, &e.Outcome, &e.IP, &e.Detail, &e.CreatedAt); err != nil {
			return nil, err
		}
		out.Events = append(out.Events, e)
	}
	return out, rows.Err()
}
