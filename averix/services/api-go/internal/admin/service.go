package admin

import (
	"context"
	"errors"
	"fmt"
	"math"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/auth"
	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/contracts"
	"github.com/averix/api/internal/matching"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
	"github.com/averix/api/internal/settings"
)

// Notifier is what the operator's actions tell the person.
type Notifier interface {
	AccountSuspended(ctx context.Context, userID uuid.UUID, reason string)
	AccountWarning(ctx context.Context, userID uuid.UUID, reason string)
	DisputeResolved(ctx context.Context, userID, contractID uuid.UUID, outcome string)
}

type Service struct {
	store     *Store
	auth      *auth.Store
	settings  *settings.Store
	matching  *matching.Store
	contracts *contracts.Service
	notifier  Notifier
	audit     *audit.Recorder
	cfg       *config.Config
	version   string
}

func NewService(store *Store, authStore *auth.Store, settingsStore *settings.Store, matchingStore *matching.Store,
	contractsSvc *contracts.Service, notifier Notifier, rec *audit.Recorder, cfg *config.Config, version string) *Service {
	return &Service{store: store, auth: authStore, settings: settingsStore, matching: matchingStore,
		contracts: contractsSvc, notifier: notifier, audit: rec, cfg: cfg, version: version}
}

func (s *Service) require(ctx context.Context, id *security.Identity, perm security.Permission, what string) error {
	if err := security.RequirePermission(id, perm); err != nil {
		s.audit.Denial(ctx, "admin", nil, "caller lacks "+string(perm))
		return httpx.Forbiddenf("%s needs the %s permission", what, perm)
	}
	return nil
}

// ── Overview ────────────────────────────────────────────────────────────────

func (s *Service) Overview(ctx context.Context, id *security.Identity) (*Overview, error) {
	if err := s.require(ctx, id, security.PermAdminDashboard, "the dashboard"); err != nil {
		return nil, err
	}
	o, err := s.store.Overview(ctx)
	if err != nil {
		return nil, httpx.Internalf(err, "load overview")
	}
	o.Attention.PendingPayments = s.store.PendingPayments(ctx)
	o.Integrations = map[string]bool{
		"email":  s.cfg.Mail.Enabled && s.cfg.Mail.Host != "",
		"github": s.cfg.GitHub.Configured(),
		"ai":     s.cfg.AI.Configured(),
		"push":   s.cfg.Push.Configured(),
	}
	o.Version = s.version
	return o, nil
}

// ── Users ───────────────────────────────────────────────────────────────────

func (s *Service) Users(ctx context.Context, id *security.Identity, q UserQuery) ([]UserRow, int, error) {
	if err := s.require(ctx, id, security.PermUserManage, "the user list"); err != nil {
		return nil, 0, err
	}
	switch q.Status {
	case "", "pending", "active", "suspended", "deactivated":
	default:
		return nil, 0, httpx.Validation(map[string]string{"status": "Неизвестный статус."})
	}
	if q.Role != "" && !security.Role(q.Role).Valid() {
		return nil, 0, httpx.Validation(map[string]string{"role": "Неизвестная роль."})
	}
	users, total, err := s.store.Users(ctx, q)
	if err != nil {
		return nil, 0, httpx.Internalf(err, "list users")
	}
	return users, total, nil
}

func (s *Service) User(ctx context.Context, id *security.Identity, userID uuid.UUID) (*UserDetail, error) {
	if err := s.require(ctx, id, security.PermUserManage, "a user's detail"); err != nil {
		return nil, err
	}
	d, err := s.store.User(ctx, userID)
	switch {
	case errors.Is(err, ErrNotFound):
		return nil, httpx.NotFoundf("user %s does not exist", userID)
	case err != nil:
		return nil, httpx.Internalf(err, "load user")
	}
	return d, nil
}

type SuspendRequest struct {
	Reason string `json:"reason"`
	// Days until the suspension lifts on its own; zero means until an
	// administrator lifts it.
	Days int `json:"days"`
}

func (s *Service) Suspend(ctx context.Context, id *security.Identity, userID uuid.UUID, in SuspendRequest) error {
	if err := s.require(ctx, id, security.PermUserManage, "suspending"); err != nil {
		return err
	}
	if userID == id.UserID {
		return httpx.Forbiddenf("you cannot suspend yourself")
	}
	reason := strings.TrimSpace(in.Reason)
	if len([]rune(reason)) < 10 {
		return httpx.Validation(map[string]string{"reason": "Укажите причину — её увидит человек."})
	}
	if in.Days < 0 || in.Days > 365 {
		return httpx.Validation(map[string]string{"days": "От 0 (бессрочно) до 365 дней."})
	}
	target, err := s.auth.AccountByID(ctx, userID)
	if err != nil {
		return httpx.NotFoundf("user %s does not exist", userID)
	}
	for _, role := range target.Roles {
		if role == security.RoleAdmin && !id.IsAdmin() {
			return httpx.Forbiddenf("only an administrator can suspend an administrator")
		}
	}
	var until *time.Time
	if in.Days > 0 {
		when := time.Now().AddDate(0, 0, in.Days)
		until = &when
	}
	err = s.store.SetSuspended(ctx, userID, reason, until)
	switch {
	case errors.Is(err, ErrNotFound):
		return httpx.NotFoundf("user %s does not exist", userID)
	case err != nil:
		return httpx.Internalf(err, "suspend user")
	}
	if _, err := s.auth.RevokeAllSessions(ctx, userID, uuid.Nil); err != nil {
		return httpx.Internalf(err, "end the user's sessions")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: audit.ActionUserSuspended, SubjectType: "user", SubjectID: &userID,
		Detail: reason, After: map[string]any{"until": until}})
	if s.notifier != nil {
		s.notifier.AccountSuspended(context.WithoutCancel(ctx), userID, reason)
	}
	return nil
}

func (s *Service) Unsuspend(ctx context.Context, id *security.Identity, userID uuid.UUID) error {
	if err := s.require(ctx, id, security.PermUserManage, "lifting a suspension"); err != nil {
		return err
	}
	err := s.store.Unsuspend(ctx, userID)
	switch {
	case errors.Is(err, ErrNotFound):
		return httpx.NotFoundf("user %s is not suspended", userID)
	case err != nil:
		return httpx.Internalf(err, "unsuspend user")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: audit.ActionUserUnsuspended, SubjectType: "user", SubjectID: &userID})
	return nil
}

func (s *Service) Warn(ctx context.Context, id *security.Identity, userID uuid.UUID, reason string) error {
	if err := s.require(ctx, id, security.PermUserManage, "warning a user"); err != nil {
		return err
	}
	reason = strings.TrimSpace(reason)
	if len([]rune(reason)) < 10 {
		return httpx.Validation(map[string]string{"reason": "Напишите, за что предупреждение."})
	}
	if _, err := s.auth.AccountByID(ctx, userID); err != nil {
		return httpx.NotFoundf("user %s does not exist", userID)
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: audit.ActionUserWarned, SubjectType: "user", SubjectID: &userID, Detail: reason})
	if s.notifier != nil {
		s.notifier.AccountWarning(context.WithoutCancel(ctx), userID, reason)
	}
	return nil
}

func (s *Service) GrantRole(ctx context.Context, id *security.Identity, userID uuid.UUID, role string) error {
	if err := s.require(ctx, id, security.PermRoleGrant, "granting a role"); err != nil {
		return err
	}
	r := security.Role(role)
	if !r.Valid() {
		return httpx.Validation(map[string]string{"role": "Неизвестная роль."})
	}
	if r == security.RoleAdmin && !id.IsAdmin() {
		return httpx.Forbiddenf("only an administrator can grant the administrator role")
	}
	if _, err := s.auth.AccountByID(ctx, userID); err != nil {
		return httpx.NotFoundf("user %s does not exist", userID)
	}
	if err := s.auth.AddRole(ctx, userID, r); err != nil {
		return httpx.Internalf(err, "grant role")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: audit.ActionRoleGranted, SubjectType: "user", SubjectID: &userID, Detail: role})
	return nil
}

func (s *Service) RevokeRole(ctx context.Context, id *security.Identity, userID uuid.UUID, role string) error {
	if err := s.require(ctx, id, security.PermRoleGrant, "revoking a role"); err != nil {
		return err
	}
	r := security.Role(role)
	if !r.Valid() {
		return httpx.Validation(map[string]string{"role": "Неизвестная роль."})
	}
	if userID == id.UserID && r == security.RoleAdmin {
		// The last administrator removing their own role is how a platform
		// ends up with nobody who can fix anything.
		return httpx.Forbiddenf("you cannot revoke your own administrator role")
	}
	err := s.store.RevokeRole(ctx, userID, role)
	switch {
	case errors.Is(err, errLastRole):
		e := *httpx.ErrConflict
		e.Code = "last_role"
		e.Message = "У аккаунта должна остаться хотя бы одна роль. Заблокируйте аккаунт, если он не должен работать."
		return &e
	case errors.Is(err, ErrNotFound):
		return httpx.NotFoundf("user %s does not hold the %s role", userID, role)
	case err != nil:
		return httpx.Internalf(err, "revoke role")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: audit.ActionRoleRevoked, SubjectType: "user", SubjectID: &userID, Detail: role})
	return nil
}

func (s *Service) VerifyIdentity(ctx context.Context, id *security.Identity, userID uuid.UUID, verified bool) error {
	if err := s.require(ctx, id, security.PermUserManage, "identity verification"); err != nil {
		return err
	}
	err := s.store.VerifyIdentity(ctx, userID, verified)
	switch {
	case errors.Is(err, ErrNotFound):
		return httpx.NotFoundf("user %s does not exist", userID)
	case err != nil:
		return httpx.Internalf(err, "verify identity")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: audit.ActionIdentityVerified, SubjectType: "user", SubjectID: &userID,
		After: map[string]any{"verified": verified}})
	return nil
}

// ── Settings ────────────────────────────────────────────────────────────────

func (s *Service) Settings(ctx context.Context, id *security.Identity) ([]SettingRow, error) {
	if err := s.require(ctx, id, security.PermSettingsManage, "the settings"); err != nil {
		return nil, err
	}
	rows, err := s.store.Settings(ctx)
	if err != nil {
		return nil, httpx.Internalf(err, "load settings")
	}
	return rows, nil
}

// SetSetting validates against the catalogue: the type, the range, the
// options. A value the code does not read cannot be written from here.
func (s *Service) SetSetting(ctx context.Context, id *security.Identity, key string, value any) error {
	if err := s.require(ctx, id, security.PermSettingsManage, "changing a setting"); err != nil {
		return err
	}
	spec, ok := catalogue[key]
	if !ok {
		return httpx.NotFoundf("setting %s is not one the panel can change", key)
	}
	var stored any
	switch spec.Type {
	case "int":
		f, ok := value.(float64)
		if !ok || f != math.Trunc(f) {
			return httpx.Validation(map[string]string{"value": "Нужно целое число."})
		}
		n := int(f)
		if spec.Min != nil && n < *spec.Min || spec.Max != nil && n > *spec.Max {
			return httpx.Validation(map[string]string{"value": fmt.Sprintf("Допустимо от %d до %d.", deref(spec.Min), deref(spec.Max))})
		}
		stored = n
	case "bool":
		b, ok := value.(bool)
		if !ok {
			return httpx.Validation(map[string]string{"value": "Нужно true или false."})
		}
		stored = b
	default:
		str, ok := value.(string)
		if !ok {
			return httpx.Validation(map[string]string{"value": "Нужна строка."})
		}
		str = strings.TrimSpace(str)
		if len([]rune(str)) > 500 {
			return httpx.Validation(map[string]string{"value": "Не длиннее 500 символов."})
		}
		if len(spec.Options) > 0 {
			allowed := false
			for _, o := range spec.Options {
				if o == str {
					allowed = true
				}
			}
			if !allowed {
				return httpx.Validation(map[string]string{"value": "Допустимые значения: " + strings.Join(spec.Options, ", ")})
			}
		}
		stored = str
	}
	previous := s.settingValue(ctx, key, spec.Type)
	if err := s.settings.Set(ctx, key, stored, id.UserID); err != nil {
		return httpx.Internalf(err, "save setting")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: audit.ActionSettingChanged, SubjectType: "setting", Detail: key,
		Before: map[string]any{"value": previous}, After: map[string]any{"value": stored}})
	return nil
}

func (s *Service) settingValue(ctx context.Context, key, kind string) any {
	switch kind {
	case "int":
		return s.settings.Int(ctx, key, 0)
	case "bool":
		return s.settings.Bool(ctx, key, false)
	}
	return s.settings.String(ctx, key, "")
}

func deref(n *int) int {
	if n == nil {
		return 0
	}
	return *n
}

// ── Feature flags ───────────────────────────────────────────────────────────

func (s *Service) Flags(ctx context.Context, id *security.Identity) ([]settings.Flag, error) {
	if err := s.require(ctx, id, security.PermSettingsManage, "feature flags"); err != nil {
		return nil, err
	}
	flags, err := s.settings.Flags(ctx)
	if err != nil {
		return nil, httpx.Internalf(err, "load flags")
	}
	return flags, nil
}

func (s *Service) SetFlag(ctx context.Context, id *security.Identity, key string, enabled bool, rollout int) error {
	if err := s.require(ctx, id, security.PermSettingsManage, "changing a flag"); err != nil {
		return err
	}
	if rollout < 0 || rollout > 100 {
		return httpx.Validation(map[string]string{"rollout_percent": "От 0 до 100."})
	}
	if err := s.settings.SetFlag(ctx, key, enabled, rollout, id.UserID); err != nil {
		return httpx.Internalf(err, "save flag")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: audit.ActionFeatureFlagChanged, SubjectType: "flag", Detail: key,
		After: map[string]any{"enabled": enabled, "rollout_percent": rollout}})
	return nil
}

// ── Matching ────────────────────────────────────────────────────────────────

func (s *Service) Weights(ctx context.Context, id *security.Identity) (matching.Weights, []map[string]any, error) {
	if err := s.require(ctx, id, security.PermMatchingConfigure, "the matching weights"); err != nil {
		return matching.Weights{}, nil, err
	}
	w, err := s.matching.ActiveWeights(ctx)
	if err != nil {
		return matching.Weights{}, nil, httpx.Internalf(err, "load weights")
	}
	history, _ := s.matching.WeightHistory(ctx, 10)
	return w, history, nil
}

type WeightsRequest struct {
	matching.Weights
	Note string `json:"note"`
}

func (s *Service) SetWeights(ctx context.Context, id *security.Identity, in WeightsRequest) (matching.Weights, error) {
	if err := s.require(ctx, id, security.PermMatchingConfigure, "changing the matching weights"); err != nil {
		return matching.Weights{}, err
	}
	w := in.Weights
	sum := w.Technical + w.TrackRecord + w.GitHub + w.Availability + w.PlatformHistory + w.BudgetFit
	problems := map[string]string{}
	for name, v := range map[string]float64{"technical": w.Technical, "track_record": w.TrackRecord, "github": w.GitHub,
		"availability": w.Availability, "platform_history": w.PlatformHistory, "budget_fit": w.BudgetFit} {
		if v < 0 || v > 1 {
			problems[name] = "Вес — доля от 0 до 1."
		}
	}
	if math.Abs(sum-1) > 0.001 {
		problems["weights"] = fmt.Sprintf("Веса должны в сумме давать 1, сейчас %.3f.", sum)
	}
	if w.FeedThreshold < 0 || w.FeedThreshold > 100 {
		problems["feed_threshold"] = "Порог ленты — от 0 до 100."
	}
	if len(strings.TrimSpace(in.Note)) < 5 {
		problems["note"] = "Напишите, зачем меняете веса — это попадёт в историю."
	}
	if len(problems) > 0 {
		return matching.Weights{}, httpx.Validation(problems)
	}
	version, err := s.matching.SaveWeights(ctx, w, strings.TrimSpace(in.Note), id.UserID)
	if err != nil {
		return matching.Weights{}, httpx.Internalf(err, "save weights")
	}
	w.Version = version
	s.audit.RecordRequest(ctx, audit.Entry{Action: audit.ActionMatchingWeightsChanged, SubjectType: "matching",
		Detail: in.Note, After: map[string]any{"version": version}})
	return w, nil
}

// ── Disputes ────────────────────────────────────────────────────────────────

func (s *Service) Disputes(ctx context.Context, id *security.Identity) ([]contracts.DisputedMilestone, error) {
	return s.contracts.OpenDisputes(ctx, id)
}

func (s *Service) ResolveDispute(ctx context.Context, id *security.Identity, milestoneID uuid.UUID,
	in contracts.DisputeOutcome) (*contracts.Milestone, error) {

	m, err := s.contracts.ResolveDispute(ctx, id, milestoneID, in)
	if err != nil {
		return nil, err
	}
	if s.notifier != nil {
		outcome := map[string]string{
			"developer_favoured": "Спор решён в пользу исполнителя: этап принят.",
			"client_favoured":    "Спор решён в пользу заказчика: этап отменён, средства возвращаются.",
			"no_action":          "Спор закрыт без изменений: работа по этапу продолжается.",
		}[in.Outcome] + " " + strings.TrimSpace(in.Note)
		facts, ferr := s.contracts.FundingFacts(ctx, milestoneID)
		if ferr == nil {
			s.notifier.DisputeResolved(context.WithoutCancel(ctx), facts.ClientID, facts.ContractID, outcome)
			s.notifier.DisputeResolved(context.WithoutCancel(ctx), facts.DeveloperID, facts.ContractID, outcome)
		}
	}
	return m, nil
}

// ── Audit ───────────────────────────────────────────────────────────────────

func (s *Service) Audit(ctx context.Context, id *security.Identity, q AuditQuery) ([]AuditRow, int, error) {
	if err := s.require(ctx, id, security.PermAuditRead, "the audit log"); err != nil {
		return nil, 0, err
	}
	rows, total, err := s.store.Audit(ctx, q)
	if err != nil {
		return nil, 0, httpx.Internalf(err, "load audit log")
	}
	return rows, total, nil
}
