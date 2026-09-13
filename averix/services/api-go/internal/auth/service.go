package auth

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/platform/cache"
	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/logx"
	"github.com/averix/api/internal/platform/validate"
	"github.com/averix/api/internal/security"
)

// Mailer is the subset of the notification system auth needs. Kept as an
// interface so auth does not depend on the notifications module, and so tests
// can assert that a reset email was queued without an SMTP server.
type Mailer interface {
	SendEmailVerification(ctx context.Context, userID uuid.UUID, email, name, token string) error
	SendPasswordReset(ctx context.Context, userID uuid.UUID, email, name, token string) error
	SendPasswordChanged(ctx context.Context, userID uuid.UUID, email, name string) error
}

type Service struct {
	store  *Store
	cache  *cache.Cache
	cfg    *config.Config
	audit  *audit.Recorder
	mailer Mailer
}

func NewService(store *Store, c *cache.Cache, cfg *config.Config, rec *audit.Recorder, mailer Mailer) *Service {
	return &Service{store: store, cache: c, cfg: cfg, audit: rec, mailer: mailer}
}

// ── Registration ────────────────────────────────────────────────────────────

type RegisterInput struct {
	Email       string
	Username    string
	Password    string
	FullName    string
	Role        string
	Locale      string
	Timezone    string
	CountryCode string
	AcceptTerms bool
}

type AuthResult struct {
	Identity *security.Identity
	Token    cryptox.SessionToken
	Session  *Session
	// True when the account was just created, so the web app knows to route
	// into onboarding rather than the dashboard.
	IsNew bool
}

func (s *Service) Register(ctx context.Context, in RegisterInput, userAgent, ip string) (*AuthResult, error) {
	v := validate.New()
	email := v.Email("email", in.Email)
	username := v.Username("username", in.Username)
	v.Password("password", in.Password, s.cfg.Auth.PasswordMinLen)
	fullName := v.Required("full_name", "Имя и фамилия", in.FullName)
	v.Length("full_name", "Имя и фамилия", in.FullName, 2, 120)
	v.NoControlChars("full_name", "Имя и фамилия", in.FullName)

	role := security.Role(strings.TrimSpace(in.Role))
	if role != security.RoleClient && role != security.RoleDeveloper {
		v.Add("role", "Выберите: вы ищете исполнителя или работу.")
	}
	if !in.AcceptTerms {
		v.Add("accept_terms", "Примите условия, чтобы продолжить.")
	}
	// A password that contains the email or username is trivially guessable
	// once either is known, and both are public on this product.
	if in.Password != "" {
		lower := strings.ToLower(in.Password)
		if username != "" && strings.Contains(lower, username) {
			v.Add("password", "Пароль не должен содержать ваше имя пользователя.")
		}
		if local, _, ok := strings.Cut(email, "@"); ok && len(local) > 3 && strings.Contains(lower, local) {
			v.Add("password", "Пароль не должен содержать ваш адрес почты.")
		}
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	hash, err := cryptox.HashPassword(in.Password, s.cfg.Auth.BcryptCost)
	if err != nil {
		return nil, httpx.Internalf(err, "hash password")
	}

	account, err := s.store.CreateAccount(ctx, NewAccount{
		Email:        email,
		Username:     username,
		PasswordHash: hash,
		FullName:     fullName,
		Role:         role,
		Locale:       in.Locale,
		Timezone:     in.Timezone,
		CountryCode:  strings.ToUpper(in.CountryCode),
	})
	switch {
	case errors.Is(err, ErrEmailTaken):
		return nil, httpx.ErrEmailTaken.Wrap(err)
	case errors.Is(err, ErrUsernameTaken):
		return nil, httpx.ErrUsernameTaken.Wrap(err)
	case err != nil:
		return nil, httpx.Internalf(err, "create account")
	}

	s.audit.Record(ctx, audit.Entry{
		ActorID: &account.ID, ActorRole: string(role),
		Action: audit.ActionRegister, SubjectType: "user", SubjectID: &account.ID,
		IP: ip, UserAgent: userAgent,
		After: map[string]any{"role": role, "username": username},
	})

	// Email verification is issued but does not gate sign-in: blocking a brand
	// new developer at the door because a message is slow loses them. Verified
	// status is what gates being searchable and submitting proposals.
	s.sendVerificationEmail(ctx, account)

	result, err := s.issueSession(ctx, account, role, userAgent, ip)
	if err != nil {
		return nil, err
	}
	result.IsNew = true
	return result, nil
}

// ── Sign-in ─────────────────────────────────────────────────────────────────

type LoginInput struct {
	Email    string
	Password string
	// Optional: which interface to open. Defaults to the account's only role,
	// or client when it holds both.
	Role string
}

func (s *Service) Login(ctx context.Context, in LoginInput, userAgent, ip string) (*AuthResult, error) {
	email := strings.ToLower(strings.TrimSpace(in.Email))
	if email == "" || in.Password == "" {
		return nil, httpx.ErrInvalidCredentials
	}

	account, err := s.store.AccountByEmail(ctx, email)
	if errors.Is(err, ErrNotFound) {
		// The same error and roughly the same work as a wrong password, so the
		// response cannot be used to enumerate which addresses have accounts.
		_, _ = cryptox.HashPassword(in.Password, s.cfg.Auth.BcryptCost)
		s.audit.Record(ctx, audit.Entry{
			Action: audit.ActionLoginFailed, SubjectType: "user",
			IP: ip, UserAgent: userAgent, Outcome: audit.Denied,
			Detail: "no account for the supplied address",
		})
		return nil, httpx.ErrInvalidCredentials
	}
	if err != nil {
		return nil, httpx.Internalf(err, "look up account")
	}

	if account.Locked() {
		s.audit.Record(ctx, audit.Entry{
			ActorID: &account.ID, Action: audit.ActionLoginFailed,
			SubjectType: "user", SubjectID: &account.ID,
			IP: ip, UserAgent: userAgent, Outcome: audit.Denied,
			Detail: "account is locked after repeated failures",
		})
		e := *httpx.ErrAccountLocked
		e.RetryAfter = int(time.Until(*account.LockedUntil).Seconds()) + 1
		return nil, &e
	}

	if !cryptox.VerifyPassword(account.PasswordHash, in.Password) {
		locked, lockErr := s.store.RecordFailedLogin(ctx, account.ID,
			s.cfg.Auth.MaxFailedLogins, s.cfg.Auth.LockoutDuration)
		if lockErr != nil {
			logx.From(ctx).Error("could not record failed login", "error", lockErr)
		}
		s.audit.Record(ctx, audit.Entry{
			ActorID: &account.ID, Action: audit.ActionLoginFailed,
			SubjectType: "user", SubjectID: &account.ID,
			IP: ip, UserAgent: userAgent, Outcome: audit.Denied,
			Detail: "wrong password",
		})
		if locked {
			e := *httpx.ErrAccountLocked
			e.RetryAfter = int(s.cfg.Auth.LockoutDuration.Seconds())
			return nil, &e
		}
		return nil, httpx.ErrInvalidCredentials
	}

	switch account.Status {
	case "suspended":
		reason := "Your account is suspended."
		if account.SuspendedReason != nil && *account.SuspendedReason != "" {
			reason = "Your account is suspended: " + *account.SuspendedReason
		}
		e := *httpx.ErrForbidden
		e.Code = "account_suspended"
		e.Message = reason + " Contact support if you think this is a mistake."
		return nil, &e
	case "deactivated":
		e := *httpx.ErrForbidden
		e.Code = "account_deactivated"
		e.Message = "Этот аккаунт деактивирован."
		return nil, &e
	}

	if len(account.Roles) == 0 {
		return nil, httpx.ErrForbidden.Wrap(errors.New("account holds no roles"))
	}

	role, err := s.resolveLoginRole(account, in.Role)
	if err != nil {
		return nil, err
	}

	if err := s.store.ClearFailedLogins(ctx, account.ID); err != nil {
		logx.From(ctx).Warn("could not clear failed logins", "error", err)
	}
	// The per-address rate-limit window is cleared too, so a user who mistyped
	// twice is not throttled after signing in successfully.
	if s.cache != nil {
		_ = s.cache.Reset(ctx, "login", email)
	}

	// A cost increase in configuration is applied on the next successful login
	// rather than requiring everyone to reset their password.
	if cryptox.NeedsRehash(account.PasswordHash, s.cfg.Auth.BcryptCost) {
		if newHash, err := cryptox.HashPassword(in.Password, s.cfg.Auth.BcryptCost); err == nil {
			if err := s.store.UpdatePasswordHash(ctx, account.ID, newHash); err != nil {
				logx.From(ctx).Warn("could not upgrade password hash", "error", err)
			}
		}
	}

	s.audit.Record(ctx, audit.Entry{
		ActorID: &account.ID, ActorRole: string(role),
		Action: audit.ActionLogin, SubjectType: "user", SubjectID: &account.ID,
		IP: ip, UserAgent: userAgent,
	})
	return s.issueSession(ctx, account, role, userAgent, ip)
}

func (s *Service) resolveLoginRole(account *Account, requested string) (security.Role, error) {
	holds := func(r security.Role) bool {
		for _, have := range account.Roles {
			if have == r {
				return true
			}
		}
		return false
	}

	if requested != "" {
		r := security.Role(strings.TrimSpace(requested))
		if !r.Valid() || !holds(r) {
			return "", httpx.ErrForbidden.Wrap(fmt.Errorf("account does not hold role %q", requested))
		}
		return r, nil
	}

	// Staff land in the admin interface; otherwise the single role, and client
	// when both are held, because that is the mode a dual account uses most.
	for _, preferred := range []security.Role{
		security.RoleAdmin, security.RoleModerator, security.RoleClient, security.RoleDeveloper,
	} {
		if holds(preferred) {
			return preferred, nil
		}
	}
	return account.Roles[0], nil
}

func (s *Service) issueSession(ctx context.Context, account *Account, role security.Role,
	userAgent, ip string) (*AuthResult, error) {

	token, sess, err := s.store.CreateSession(ctx, account.ID, role, userAgent, ip, s.cfg.Auth.SessionTTL)
	if err != nil {
		return nil, httpx.Internalf(err, "create session")
	}

	identity := &security.Identity{
		UserID:           account.ID,
		SessionID:        sess.ID,
		Username:         account.Username,
		Email:            account.Email,
		ActiveRole:       role,
		Roles:            account.Roles,
		Status:           account.Status,
		EmailVerified:    account.EmailVerifiedAt != nil,
		IdentityVerified: account.IdentityVerifiedAt != nil,
		CSRFToken:        sess.CSRFToken,
	}
	return &AuthResult{Identity: identity, Token: token, Session: sess}, nil
}

// ── Sign-out ────────────────────────────────────────────────────────────────

func (s *Service) Logout(ctx context.Context, id *security.Identity) error {
	if !id.Authenticated() {
		return nil
	}
	if err := s.store.RevokeSession(ctx, id.SessionID); err != nil {
		return httpx.Internalf(err, "revoke session")
	}
	s.audit.RecordRequest(ctx, audit.Entry{
		Action: audit.ActionLogout, SubjectType: "session", SubjectID: &id.SessionID,
	})
	return nil
}

func (s *Service) LogoutEverywhere(ctx context.Context, id *security.Identity) (int, error) {
	if !id.Authenticated() {
		return 0, httpx.ErrUnauthenticated
	}
	n, err := s.store.RevokeAllSessions(ctx, id.UserID, uuid.Nil)
	if err != nil {
		return 0, httpx.Internalf(err, "revoke all sessions")
	}
	s.audit.RecordRequest(ctx, audit.Entry{
		Action: audit.ActionSessionRevoked, SubjectType: "user", SubjectID: &id.UserID,
		Detail: fmt.Sprintf("%d sessions revoked", n),
	})
	return n, nil
}

// ── Role switching ──────────────────────────────────────────────────────────

// SwitchRole moves the current session into another interface the account holds.
func (s *Service) SwitchRole(ctx context.Context, id *security.Identity, requested string) (string, error) {
	if !id.Authenticated() {
		return "", httpx.ErrUnauthenticated
	}
	role := security.Role(strings.TrimSpace(requested))
	if !role.Valid() {
		return "", httpx.Validation(map[string]string{"role": "Такого интерфейса нет."})
	}
	if !id.HasRole(role) {
		return "", httpx.Forbiddenf("account does not hold role %q", role)
	}
	if role == id.ActiveRole {
		return id.CSRFToken, nil
	}

	csrf, err := s.store.SwitchRole(ctx, id.SessionID, id.UserID, role)
	if err != nil {
		if errors.Is(err, ErrSessionInvalid) {
			return "", httpx.ErrForbidden.Wrap(err)
		}
		return "", httpx.Internalf(err, "switch role")
	}
	s.audit.RecordRequest(ctx, audit.Entry{
		Action: audit.ActionRoleSwitched, SubjectType: "session", SubjectID: &id.SessionID,
		Before: map[string]any{"role": id.ActiveRole},
		After:  map[string]any{"role": role},
	})
	return csrf, nil
}

// AddRole gives an existing account the second interface.
func (s *Service) AddRole(ctx context.Context, id *security.Identity, requested string) error {
	if !id.Authenticated() {
		return httpx.ErrUnauthenticated
	}
	role := security.Role(strings.TrimSpace(requested))
	if role != security.RoleClient && role != security.RoleDeveloper {
		return httpx.Validation(map[string]string{
			"role": "Можно добавить роль заказчика или исполнителя.",
		})
	}
	if id.HasRole(role) {
		return nil
	}
	if err := s.store.AddRole(ctx, id.UserID, role); err != nil {
		return httpx.Internalf(err, "add role")
	}
	s.audit.RecordRequest(ctx, audit.Entry{
		Action: audit.ActionRoleGranted, SubjectType: "user", SubjectID: &id.UserID,
		After: map[string]any{"role": role, "self_service": true},
	})
	return nil
}

// ── Password management ─────────────────────────────────────────────────────

// RequestPasswordReset always reports success.
//
// Telling the caller whether an address has an account turns this endpoint into
// an account enumeration oracle, so the response is identical either way and
// the email is only sent when there is somewhere to send it.
func (s *Service) RequestPasswordReset(ctx context.Context, rawEmail, ip string) error {
	email := strings.ToLower(strings.TrimSpace(rawEmail))
	if email == "" {
		return nil
	}
	account, err := s.store.AccountByEmail(ctx, email)
	if err != nil {
		if !errors.Is(err, ErrNotFound) {
			logx.From(ctx).Error("password reset lookup failed", "error", err)
		}
		return nil
	}
	if account.Status == "deactivated" {
		return nil
	}

	// A new request invalidates the previous link.
	if err := s.store.InvalidateTokens(ctx, account.ID, PurposePasswordReset); err != nil {
		logx.From(ctx).Warn("could not invalidate previous reset tokens", "error", err)
	}
	token, err := s.store.IssueToken(ctx, account.ID, PurposePasswordReset, nil, time.Hour)
	if err != nil {
		logx.From(ctx).Error("could not issue reset token", "error", err)
		return nil
	}
	if s.mailer != nil {
		if err := s.mailer.SendPasswordReset(ctx, account.ID, account.Email, account.FullName, token); err != nil {
			logx.From(ctx).Error("could not queue password reset email", "error", err)
		}
	}
	s.audit.Record(ctx, audit.Entry{
		ActorID: &account.ID, Action: audit.ActionPasswordReset,
		SubjectType: "user", SubjectID: &account.ID, IP: ip,
		Detail: "reset requested",
	})
	return nil
}

type ResetPasswordInput struct {
	Token    string
	Password string
}

func (s *Service) ResetPassword(ctx context.Context, in ResetPasswordInput, ip string) error {
	v := validate.New()
	v.Password("password", in.Password, s.cfg.Auth.PasswordMinLen)
	if strings.TrimSpace(in.Token) == "" {
		v.Add("token", "Ссылка для смены пароля неполная.")
	}
	if v.Any() {
		return httpx.Validation(v.Fields())
	}

	userID, _, err := s.store.ConsumeToken(ctx, in.Token, PurposePasswordReset)
	if errors.Is(err, ErrNotFound) {
		e := *httpx.ErrBadRequest
		e.Code = "reset_link_invalid"
		e.Message = "Ссылка для смены пароля устарела или уже использована. Запросите новую."
		return &e
	}
	if err != nil {
		return httpx.Internalf(err, "consume reset token")
	}

	hash, err := cryptox.HashPassword(in.Password, s.cfg.Auth.BcryptCost)
	if err != nil {
		return httpx.Internalf(err, "hash password")
	}
	if err := s.store.UpdatePasswordHash(ctx, userID, hash); err != nil {
		return httpx.Internalf(err, "update password")
	}
	if err := s.store.ClearFailedLogins(ctx, userID); err != nil {
		logx.From(ctx).Warn("could not clear failed logins after reset", "error", err)
	}
	// Every existing session is revoked: if the reset was triggered because the
	// account was compromised, leaving the attacker signed in defeats it.
	if _, err := s.store.RevokeAllSessions(ctx, userID, uuid.Nil); err != nil {
		logx.From(ctx).Error("could not revoke sessions after password reset", "error", err)
	}

	if account, err := s.store.AccountByID(ctx, userID); err == nil && s.mailer != nil {
		if err := s.mailer.SendPasswordChanged(ctx, account.ID, account.Email, account.FullName); err != nil {
			logx.From(ctx).Warn("could not queue password-changed notice", "error", err)
		}
	}
	s.audit.Record(ctx, audit.Entry{
		ActorID: &userID, Action: audit.ActionPasswordChanged,
		SubjectType: "user", SubjectID: &userID, IP: ip,
		Detail: "via reset link; all sessions revoked",
	})
	return nil
}

type ChangePasswordInput struct {
	CurrentPassword string
	NewPassword     string
}

func (s *Service) ChangePassword(ctx context.Context, id *security.Identity, in ChangePasswordInput) error {
	if !id.Authenticated() {
		return httpx.ErrUnauthenticated
	}
	v := validate.New()
	v.Password("new_password", in.NewPassword, s.cfg.Auth.PasswordMinLen)
	if in.CurrentPassword == "" {
		v.Add("current_password", "Введите текущий пароль.")
	}
	if in.CurrentPassword == in.NewPassword {
		v.Add("new_password", "Выберите пароль, которым вы здесь ещё не пользовались.")
	}
	if v.Any() {
		return httpx.Validation(v.Fields())
	}

	account, err := s.store.AccountByID(ctx, id.UserID)
	if err != nil {
		return httpx.Internalf(err, "load account")
	}
	// Re-authenticating before a password change is what stops a stolen session
	// from being turned into permanent account takeover.
	if !cryptox.VerifyPassword(account.PasswordHash, in.CurrentPassword) {
		return httpx.Validation(map[string]string{
			"current_password": "Это не ваш текущий пароль.",
		})
	}

	hash, err := cryptox.HashPassword(in.NewPassword, s.cfg.Auth.BcryptCost)
	if err != nil {
		return httpx.Internalf(err, "hash password")
	}
	if err := s.store.UpdatePasswordHash(ctx, id.UserID, hash); err != nil {
		return httpx.Internalf(err, "update password")
	}
	// Other devices are signed out; this session survives so the user is not
	// kicked out of the page they are on.
	if _, err := s.store.RevokeAllSessions(ctx, id.UserID, id.SessionID); err != nil {
		logx.From(ctx).Error("could not revoke other sessions", "error", err)
	}
	if s.mailer != nil {
		if err := s.mailer.SendPasswordChanged(ctx, account.ID, account.Email, account.FullName); err != nil {
			logx.From(ctx).Warn("could not queue password-changed notice", "error", err)
		}
	}
	s.audit.RecordRequest(ctx, audit.Entry{
		Action: audit.ActionPasswordChanged, SubjectType: "user", SubjectID: &id.UserID,
		Detail: "changed while signed in; other sessions revoked",
	})
	return nil
}

// ── Email verification ──────────────────────────────────────────────────────

// sendVerificationEmail issues the token and hands it to the mailer.
//
// The token is created whether or not mail is configured: it is the record that
// verification is pending, and an environment without SMTP must still be able
// to complete the flow (an administrator can read the pending token, and the
// development seed prints one). Only delivery depends on the mailer.
func (s *Service) sendVerificationEmail(ctx context.Context, account *Account) {
	token, err := s.store.IssueToken(ctx, account.ID, PurposeEmailVerify, nil, 48*time.Hour)
	if err != nil {
		logx.From(ctx).Error("could not issue verification token", "error", err)
		return
	}
	if s.mailer == nil {
		logx.From(ctx).Warn("email delivery is not configured; verification token issued but not sent",
			"user_id", account.ID.String())
		return
	}
	if err := s.mailer.SendEmailVerification(ctx, account.ID, account.Email, account.FullName, token); err != nil {
		logx.From(ctx).Error("could not queue verification email", "error", err)
	}
}

func (s *Service) VerifyEmail(ctx context.Context, token string) error {
	userID, _, err := s.store.ConsumeToken(ctx, token, PurposeEmailVerify)
	if errors.Is(err, ErrNotFound) {
		e := *httpx.ErrBadRequest
		e.Code = "verification_link_invalid"
		e.Message = "Ссылка для подтверждения устарела или уже использована."
		return &e
	}
	if err != nil {
		return httpx.Internalf(err, "consume verification token")
	}
	if err := s.store.MarkEmailVerified(ctx, userID); err != nil {
		return httpx.Internalf(err, "mark email verified")
	}
	s.audit.Record(ctx, audit.Entry{
		ActorID: &userID, Action: audit.ActionEmailVerified,
		SubjectType: "user", SubjectID: &userID,
	})
	return nil
}

func (s *Service) ResendVerification(ctx context.Context, id *security.Identity) error {
	if !id.Authenticated() {
		return httpx.ErrUnauthenticated
	}
	if id.EmailVerified {
		return nil
	}
	account, err := s.store.AccountByID(ctx, id.UserID)
	if err != nil {
		return httpx.Internalf(err, "load account")
	}
	if err := s.store.InvalidateTokens(ctx, id.UserID, PurposeEmailVerify); err != nil {
		logx.From(ctx).Warn("could not invalidate previous verification tokens", "error", err)
	}
	s.sendVerificationEmail(ctx, account)
	return nil
}

// ── Availability checks ─────────────────────────────────────────────────────

// Availability backs the live sign-up field checks. It reports only whether a
// value can be used, never anything about an existing account.
func (s *Service) Availability(ctx context.Context, field, value string) (bool, string, error) {
	v := validate.New()
	switch field {
	case "email":
		normalised := v.Email("email", value)
		if v.Any() {
			return false, v.Fields()["email"], nil
		}
		ok, err := s.store.EmailAvailable(ctx, normalised)
		if err != nil {
			return false, "", httpx.Internalf(err, "check email availability")
		}
		if !ok {
			return false, "An account with this email already exists.", nil
		}
		return true, "", nil
	case "username":
		normalised := v.Username("username", value)
		if v.Any() {
			return false, v.Fields()["username"], nil
		}
		ok, err := s.store.UsernameAvailable(ctx, normalised)
		if err != nil {
			return false, "", httpx.Internalf(err, "check username availability")
		}
		if !ok {
			return false, "That username is already taken.", nil
		}
		return true, "", nil
	}
	return false, "", httpx.ErrBadRequest.Wrap(fmt.Errorf("unknown field %q", field))
}

func (s *Service) Sessions(ctx context.Context, id *security.Identity) ([]Session, error) {
	if !id.Authenticated() {
		return nil, httpx.ErrUnauthenticated
	}
	sessions, err := s.store.ActiveSessions(ctx, id.UserID)
	if err != nil {
		return nil, httpx.Internalf(err, "list sessions")
	}
	return sessions, nil
}

func (s *Service) RevokeSession(ctx context.Context, id *security.Identity, sessionID uuid.UUID) error {
	if !id.Authenticated() {
		return httpx.ErrUnauthenticated
	}
	// Scoped to the caller's own sessions, so a session id from elsewhere
	// cannot be revoked by guessing it.
	sessions, err := s.store.ActiveSessions(ctx, id.UserID)
	if err != nil {
		return httpx.Internalf(err, "list sessions")
	}
	for _, sess := range sessions {
		if sess.ID == sessionID {
			if err := s.store.RevokeSession(ctx, sessionID); err != nil {
				return httpx.Internalf(err, "revoke session")
			}
			s.audit.RecordRequest(ctx, audit.Entry{
				Action: audit.ActionSessionRevoked, SubjectType: "session", SubjectID: &sessionID,
			})
			return nil
		}
	}
	return httpx.ErrNotFound.Wrap(fmt.Errorf("session %s does not belong to user %s", sessionID, id.UserID))
}

// Store exposes the store for the middleware, which needs session resolution
// without the rest of the service.
func (s *Service) Store() *Store { return s.store }
