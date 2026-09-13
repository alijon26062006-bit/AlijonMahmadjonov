// Package account is a person's own settings: who they are, how to reach
// them, and how to leave. Everything about a role — a freelancer's profile,
// a client's company — lives in that role's module; this is the part every
// account has regardless.
package account

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/auth"
	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/logx"
	"github.com/averix/api/internal/platform/validate"
	"github.com/averix/api/internal/security"
)

// Settings is what the settings screen shows.
type Settings struct {
	UserID           uuid.UUID  `json:"user_id"`
	Email            string     `json:"email"`
	EmailVerified    bool       `json:"email_verified"`
	PendingEmail     string     `json:"pending_email,omitempty"`
	Username         string     `json:"username"`
	FullName         string     `json:"full_name"`
	Headline         string     `json:"headline,omitempty"`
	Timezone         string     `json:"timezone"`
	Locale           string     `json:"locale"`
	CountryCode      string     `json:"country_code,omitempty"`
	City             string     `json:"city,omitempty"`
	Roles            []string   `json:"roles"`
	IdentityVerified bool       `json:"identity_verified"`
	Status           string     `json:"status"`
	ActiveSessions   int        `json:"active_sessions"`
	MemberSince      time.Time  `json:"member_since"`
	HasPassword      bool       `json:"has_password"`
	GitHubConnected  bool       `json:"github_connected"`
	LastSeenAt       *time.Time `json:"last_seen_at,omitempty"`
}

type UpdateRequest struct {
	FullName    *string `json:"full_name"`
	Headline    *string `json:"headline"`
	Timezone    *string `json:"timezone"`
	Locale      *string `json:"locale"`
	CountryCode *string `json:"country_code"`
	City        *string `json:"city"`
}

// Mailer is the two messages an email change needs.
type Mailer interface {
	SendEmailChange(ctx context.Context, userID uuid.UUID, newEmail, name, token string) error
	SendEmailChanged(ctx context.Context, userID uuid.UUID, oldEmail, name, newEmail string) error
	Configured() bool
}

type Service struct {
	db     *database.DB
	auth   *auth.Store
	mailer Mailer
	audit  *audit.Recorder
}

func NewService(db *database.DB, authStore *auth.Store, mailer Mailer, rec *audit.Recorder) *Service {
	return &Service{db: db, auth: authStore, mailer: mailer, audit: rec}
}

func (s *Service) Me(ctx context.Context, id *security.Identity) (*Settings, error) {
	var out Settings
	var headline, country, city *string
	var emailVerifiedAt, identityAt *time.Time
	var passwordHash string
	var roles []string
	err := s.db.QueryRow(ctx, `
		SELECT u.id, u.email, u.email_verified_at, u.username, u.full_name, u.headline, u.timezone,
		       u.locale, u.country_code, u.city, u.identity_verified_at, u.status, u.created_at,
		       coalesce(u.password_hash, ''), u.last_seen_at,
		       coalesce((SELECT array_agg(r.role ORDER BY r.role) FROM user_roles r WHERE r.user_id = u.id), '{}'),
		       (SELECT count(*) FROM sessions se WHERE se.user_id = u.id AND se.revoked_at IS NULL AND se.expires_at > now()),
		       EXISTS (SELECT 1 FROM github_accounts g WHERE g.user_id = u.id AND g.revoked_at IS NULL),
		       coalesce((SELECT t.payload->>'email' FROM auth_tokens t
		                 WHERE t.user_id = u.id AND t.purpose = 'email_change'
		                   AND t.consumed_at IS NULL AND t.expires_at > now()
		                 ORDER BY t.created_at DESC LIMIT 1), '')
		FROM users u WHERE u.id = $1 AND u.deleted_at IS NULL`, id.UserID).
		Scan(&out.UserID, &out.Email, &emailVerifiedAt, &out.Username, &out.FullName, &headline, &out.Timezone,
			&out.Locale, &country, &city, &identityAt, &out.Status, &out.MemberSince,
			&passwordHash, &out.LastSeenAt, &roles, &out.ActiveSessions, &out.GitHubConnected, &out.PendingEmail)
	if err != nil {
		return nil, httpx.Internalf(err, "load account")
	}
	out.EmailVerified = emailVerifiedAt != nil
	out.IdentityVerified = identityAt != nil
	out.Headline, out.CountryCode, out.City = deref(headline), deref(country), deref(city)
	out.HasPassword = passwordHash != ""
	out.Roles = roles
	if out.Roles == nil {
		out.Roles = []string{}
	}
	return &out, nil
}

func (s *Service) Update(ctx context.Context, id *security.Identity, in UpdateRequest) (*Settings, error) {
	v := validate.New()
	sets := []string{}
	args := []any{id.UserID}
	set := func(column string, value any) {
		args = append(args, value)
		sets = append(sets, fmt.Sprintf("%s = $%d", column, len(args)))
	}
	if in.FullName != nil {
		name := strings.TrimSpace(*in.FullName)
		v.Length("full_name", "Имя", name, 2, 120)
		v.NoControlChars("full_name", "Имя", name)
		set("full_name", name)
	}
	if in.Headline != nil {
		h := strings.TrimSpace(*in.Headline)
		if len([]rune(h)) > 120 {
			v.Add("headline", "Не длиннее 120 символов.")
		}
		set("headline", nullIfEmpty(h))
	}
	if in.Timezone != nil {
		tz := strings.TrimSpace(*in.Timezone)
		if _, err := time.LoadLocation(tz); err != nil || tz == "" {
			v.Add("timezone", "Неизвестный часовой пояс — укажите, например, Europe/Moscow или Asia/Tashkent.")
		}
		set("timezone", tz)
	}
	if in.Locale != nil {
		loc := strings.TrimSpace(*in.Locale)
		if loc != "ru" && loc != "en" && loc != "uz" {
			v.Add("locale", "Доступные языки: ru, en, uz.")
		}
		set("locale", loc)
	}
	if in.CountryCode != nil {
		cc := strings.ToUpper(strings.TrimSpace(*in.CountryCode))
		if cc != "" && len(cc) != 2 {
			v.Add("country_code", "Код страны — две буквы, например RU или UZ.")
		}
		set("country_code", nullIfEmpty(cc))
	}
	if in.City != nil {
		city := strings.TrimSpace(*in.City)
		if len([]rune(city)) > 80 {
			v.Add("city", "Не длиннее 80 символов.")
		}
		set("city", nullIfEmpty(city))
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}
	if len(sets) == 0 {
		return s.Me(ctx, id)
	}
	sets = append(sets, "updated_at = now()")
	if _, err := s.db.Exec(ctx, "UPDATE users SET "+strings.Join(sets, ", ")+" WHERE id = $1", args...); err != nil {
		return nil, httpx.Internalf(err, "update account")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: "account.updated", SubjectType: "user", SubjectID: &id.UserID})
	return s.Me(ctx, id)
}

// ── Email change ────────────────────────────────────────────────────────────

type EmailChangeRequest struct {
	NewEmail string `json:"new_email"`
	Password string `json:"password"`
}

// RequestEmailChange starts the change: the new address gets a link, the
// account keeps the old one until the link is used. The password is asked
// for because an open session on a shared computer must not be enough to
// take an account by swapping its address.
func (s *Service) RequestEmailChange(ctx context.Context, id *security.Identity, in EmailChangeRequest) error {
	v := validate.New()
	email := v.Email("new_email", in.NewEmail)
	if v.Any() {
		return httpx.Validation(v.Fields())
	}
	account, err := s.auth.AccountByID(ctx, id.UserID)
	if err != nil {
		return httpx.Internalf(err, "load account")
	}
	if !cryptox.VerifyPassword(account.PasswordHash, in.Password) {
		s.audit.Denial(ctx, "user", &id.UserID, "email change with a wrong password")
		return httpx.Validation(map[string]string{"password": "Неверный пароль."})
	}
	if strings.EqualFold(email, account.Email) {
		return httpx.Validation(map[string]string{"new_email": "Это и есть ваш текущий адрес."})
	}
	available, err := s.auth.EmailAvailable(ctx, email)
	if err != nil {
		return httpx.Internalf(err, "check email")
	}
	if !available {
		// The same answer as for a taken address at registration, so this
		// endpoint cannot be used to find out who has an account.
		return httpx.Validation(map[string]string{"new_email": "Этот адрес нельзя использовать."})
	}
	if s.mailer == nil || !s.mailer.Configured() {
		e := *httpx.ErrConflict
		e.Code = "email_not_configured"
		e.Message = "Смена адреса требует отправки письма, а почта на этом сервере ещё не настроена. Обратитесь в поддержку."
		return &e
	}
	_ = s.auth.InvalidateTokens(ctx, id.UserID, auth.PurposeEmailChange)
	token, err := s.auth.IssueToken(ctx, id.UserID, auth.PurposeEmailChange, map[string]any{"email": email}, time.Hour)
	if err != nil {
		return httpx.Internalf(err, "issue email change token")
	}
	if err := s.mailer.SendEmailChange(ctx, id.UserID, email, account.FullName, token); err != nil {
		logx.From(ctx).Warn("account: email change message not sent", "error", err)
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: "account.email_change_requested", SubjectType: "user", SubjectID: &id.UserID})
	return nil
}

// ConfirmEmailChange burns the token and swaps the address. Works without a
// session: the link may well be opened on another device.
func (s *Service) ConfirmEmailChange(ctx context.Context, token string) error {
	userID, payload, err := s.auth.ConsumeToken(ctx, strings.TrimSpace(token), auth.PurposeEmailChange)
	if err != nil {
		e := *httpx.ErrValidation
		e.Code = "token_invalid"
		e.Message = "Ссылка недействительна или уже использована. Запросите смену адреса ещё раз."
		return &e
	}
	email, _ := payload["email"].(string)
	if email == "" {
		return httpx.Internalf(errors.New("email change token without an address"), "confirm email")
	}
	account, err := s.auth.AccountByID(ctx, userID)
	if err != nil {
		return httpx.Internalf(err, "load account")
	}
	available, err := s.auth.EmailAvailable(ctx, email)
	if err != nil {
		return httpx.Internalf(err, "check email")
	}
	if !available {
		e := *httpx.ErrConflict
		e.Code = "email_taken"
		e.Message = "Этот адрес уже занят другим аккаунтом."
		return &e
	}
	if _, err := s.db.Exec(ctx, `
		UPDATE users SET email = $2, email_verified_at = now(), updated_at = now() WHERE id = $1`,
		userID, email); err != nil {
		return httpx.Internalf(err, "change email")
	}
	if s.mailer != nil {
		_ = s.mailer.SendEmailChanged(ctx, userID, account.Email, account.FullName, email)
	}
	s.audit.Record(ctx, audit.Entry{ActorID: &userID, Action: "account.email_changed", SubjectType: "user", SubjectID: &userID,
		Before: map[string]any{"email": account.Email}, After: map[string]any{"email": email}})
	return nil
}

// ── Leaving ─────────────────────────────────────────────────────────────────

// Deactivate closes the account: it stops signing in and disappears from
// every list, but nothing is deleted — contracts, reviews and payments are
// the other party's record too, and a deactivated account can be restored
// by support. Refused while a contract is still running: money and work in
// flight need a person on both ends.
func (s *Service) Deactivate(ctx context.Context, id *security.Identity, password string) error {
	account, err := s.auth.AccountByID(ctx, id.UserID)
	if err != nil {
		return httpx.Internalf(err, "load account")
	}
	if !cryptox.VerifyPassword(account.PasswordHash, password) {
		s.audit.Denial(ctx, "user", &id.UserID, "deactivation with a wrong password")
		return httpx.Validation(map[string]string{"password": "Неверный пароль."})
	}
	var active int
	if err := s.db.QueryRow(ctx, `
		SELECT count(*) FROM contracts
		WHERE (client_id = $1 OR developer_id = $1)
		  AND status IN ('pending_funding', 'active', 'paused', 'submitted', 'disputed')`, id.UserID).Scan(&active); err != nil {
		return httpx.Internalf(err, "count active contracts")
	}
	if active > 0 {
		e := *httpx.ErrConflict
		e.Code = "contracts_in_progress"
		e.Message = fmt.Sprintf("У вас %d незавершённых контрактов. Завершите или отмените их, прежде чем закрывать аккаунт.", active)
		return &e
	}
	err = s.db.InTx(ctx, func(q database.Querier) error {
		if _, err := q.Exec(ctx, `
			UPDATE users SET status = 'deactivated', updated_at = now() WHERE id = $1`, id.UserID); err != nil {
			return err
		}
		if _, err := q.Exec(ctx, `
			UPDATE developer_profiles SET is_searchable = false, updated_at = now() WHERE user_id = $1`, id.UserID); err != nil {
			return err
		}
		if _, err := q.Exec(ctx, `
			UPDATE services SET status = 'archived', updated_at = now()
			WHERE developer_id = $1 AND status <> 'archived'`, id.UserID); err != nil {
			return err
		}
		_, err := q.Exec(ctx, `UPDATE sessions SET revoked_at = now() WHERE user_id = $1 AND revoked_at IS NULL`, id.UserID)
		return err
	})
	if err != nil {
		return httpx.Internalf(err, "deactivate account")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: "account.deactivated", SubjectType: "user", SubjectID: &id.UserID})
	return nil
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

func nullIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}
