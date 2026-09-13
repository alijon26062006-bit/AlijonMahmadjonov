// Package admin is the operator's side of the marketplace: who is on it,
// what the platform charges, which switches are on, and the record of every
// decision. It grants nothing the security model does not already name — an
// administrator is a role with permissions, checked here per action, not a
// bypass.
package admin

import (
	"time"

	"github.com/google/uuid"
)

// Overview is the numbers an operator looks at every morning.
type Overview struct {
	Users struct {
		Total       int `json:"total"`
		Clients     int `json:"clients"`
		Freelancers int `json:"freelancers"`
		Listed      int `json:"listed_freelancers"`
		NewThisWeek int `json:"new_this_week"`
		Suspended   int `json:"suspended"`
	} `json:"users"`
	Marketplace struct {
		OpenProjects     int `json:"open_projects"`
		ActiveServices   int `json:"active_services"`
		ActiveContracts  int `json:"active_contracts"`
		CompletedMonth   int `json:"completed_this_month"`
		ProposalsWeek    int `json:"proposals_this_week"`
		OpenDisputes     int `json:"open_disputes"`
		PublishedReviews int `json:"published_reviews"`
	} `json:"marketplace"`
	// Gross value of contracts completed this month, per currency, and the
	// platform's fee share of it. Minor units.
	Money     []MoneyRow `json:"money"`
	Attention struct {
		ModerationPending   int `json:"moderation_pending"`
		ModerationEscalated int `json:"moderation_escalated"`
		OpenReports         int `json:"open_reports"`
		PendingPayments     int `json:"pending_payments"`
	} `json:"attention"`
	Integrations map[string]bool `json:"integrations"`
	Version      string          `json:"version"`
}

type MoneyRow struct {
	Currency   string `json:"currency"`
	GrossMinor int64  `json:"gross_minor"`
	FeeMinor   int64  `json:"fee_minor"`
	Contracts  int    `json:"contracts"`
}

// UserRow is one line of the user list.
type UserRow struct {
	ID               uuid.UUID  `json:"id"`
	Username         string     `json:"username"`
	FullName         string     `json:"full_name"`
	Email            string     `json:"email"`
	Status           string     `json:"status"`
	Roles            []string   `json:"roles"`
	EmailVerified    bool       `json:"email_verified"`
	IdentityVerified bool       `json:"identity_verified"`
	SuspendedReason  string     `json:"suspended_reason,omitempty"`
	SuspendedUntil   *time.Time `json:"suspended_until,omitempty"`
	CreatedAt        time.Time  `json:"created_at"`
	LastSeenAt       *time.Time `json:"last_seen_at,omitempty"`
}

// UserDetail adds the figures a decision about a person needs.
type UserDetail struct {
	UserRow
	CountryCode      string `json:"country_code,omitempty"`
	City             string `json:"city,omitempty"`
	ProjectsPosted   int    `json:"projects_posted"`
	ContractsTotal   int    `json:"contracts_total"`
	ContractsActive  int    `json:"contracts_active"`
	ReportsAgainst   int    `json:"reports_against"`
	ReportsFiled     int    `json:"reports_filed"`
	Warnings         int    `json:"warnings"`
	ActiveSessions   int    `json:"active_sessions"`
	GitHubConnected  bool   `json:"github_connected"`
	FreelancerListed bool   `json:"freelancer_listed"`
}

type UserQuery struct {
	Text   string
	Status string
	Role   string
	Limit  int
	Offset int
}

// SettingRow is one platform setting with the catalogue's description of it.
type SettingRow struct {
	Key         string    `json:"key"`
	Label       string    `json:"label"`
	Description string    `json:"description,omitempty"`
	Type        string    `json:"type"` // int | bool | string
	Value       any       `json:"value"`
	Scope       string    `json:"scope"`
	Min         *int      `json:"min,omitempty"`
	Max         *int      `json:"max,omitempty"`
	UpdatedAt   time.Time `json:"updated_at"`
	Group       string    `json:"group"`
}

// catalogue is the closed set of settings an administrator may change from
// the panel. A key outside it is refused: a typo must not create a setting
// nothing reads.
type settingSpec struct {
	Label, Description, Type, Group string
	Min, Max                        *int
	Options                         []string
}

func intPtr(n int) *int { return &n }

var catalogue = map[string]settingSpec{
	"platform.fee_basis_points":      {Label: "Комиссия платформы", Description: "В базисных пунктах: 1000 = 10%. Фиксируется на контракте при подписании и не меняет уже подписанные.", Type: "int", Group: "money", Min: intPtr(0), Max: intPtr(3000)},
	"payments.provider":              {Label: "Платёжный провайдер", Description: "manual — перевод по реквизитам, который подтверждает администратор.", Type: "string", Group: "money", Options: []string{"manual"}},
	"proposals.max_per_day":          {Label: "Откликов в сутки на исполнителя", Type: "int", Group: "limits", Min: intPtr(1), Max: intPtr(100)},
	"proposals.min_cover_letter":     {Label: "Минимальная длина сопроводительного письма", Type: "int", Group: "limits", Min: intPtr(0), Max: intPtr(2000)},
	"projects.max_open_per_client":   {Label: "Открытых проектов у одного заказчика", Type: "int", Group: "limits", Min: intPtr(1), Max: intPtr(100)},
	"services.max_per_developer":     {Label: "Услуг у одного исполнителя", Type: "int", Group: "limits", Min: intPtr(1), Max: intPtr(100)},
	"messages.max_per_minute":        {Label: "Сообщений в минуту", Description: "Защита от флуда в переписке.", Type: "int", Group: "limits", Min: intPtr(5), Max: intPtr(300)},
	"reviews.window_days":            {Label: "Окно для отзыва, дней", Description: "Сколько дней после завершения контракта можно оставить отзыв; по истечении одиночный отзыв публикуется сам.", Type: "int", Group: "marketplace", Min: intPtr(3), Max: intPtr(60)},
	"feed.threshold_override":        {Label: "Порог ленты «Для вас»", Description: "Минимальный балл совпадения, чтобы проект попал в ленту. −1 — использовать порог из набора весов.", Type: "int", Group: "marketplace", Min: intPtr(-1), Max: intPtr(100)},
	"preview.enabled":                {Label: "Предпросмотр сайтов из портфолио", Type: "bool", Group: "marketplace"},
	"uploads.max_image_bytes":        {Label: "Максимальный размер изображения, байт", Type: "int", Group: "limits", Min: intPtr(1 << 20), Max: intPtr(50 << 20)},
	"uploads.max_file_bytes":         {Label: "Максимальный размер файла, байт", Type: "int", Group: "limits", Min: intPtr(1 << 20), Max: intPtr(200 << 20)},
	"platform.support_email":         {Label: "Адрес поддержки", Description: "Показывается в подвале и в письмах о блокировке.", Type: "string", Group: "platform"},
	"platform.maintenance_notice":    {Label: "Объявление на всех страницах", Description: "Пусто — ничего не показывается. Текст — баннер вверху каждой страницы.", Type: "string", Group: "platform"},
	"payments.manual.account_name":   {Label: "Получатель перевода", Type: "string", Group: "manual_payments"},
	"payments.manual.account_number": {Label: "Номер счёта или карты", Type: "string", Group: "manual_payments"},
	"payments.manual.bank_name":      {Label: "Банк", Type: "string", Group: "manual_payments"},
	"payments.manual.extra_label":    {Label: "Дополнительное поле — название", Type: "string", Group: "manual_payments"},
	"payments.manual.extra_value":    {Label: "Дополнительное поле — значение", Type: "string", Group: "manual_payments"},
	"payments.manual.note":           {Label: "Примечание для плательщика", Type: "string", Group: "manual_payments"},
}

// AuditRow is one line of the audit log.
type AuditRow struct {
	ID          int64          `json:"id"`
	ActorID     *uuid.UUID     `json:"actor_id,omitempty"`
	ActorName   string         `json:"actor_name,omitempty"`
	ActorRole   string         `json:"actor_role,omitempty"`
	Action      string         `json:"action"`
	SubjectType string         `json:"subject_type,omitempty"`
	SubjectID   *uuid.UUID     `json:"subject_id,omitempty"`
	Outcome     string         `json:"outcome"`
	Detail      string         `json:"detail,omitempty"`
	IP          string         `json:"ip,omitempty"`
	Before      map[string]any `json:"before,omitempty"`
	After       map[string]any `json:"after,omitempty"`
	CreatedAt   time.Time      `json:"created_at"`
}

type AuditQuery struct {
	ActorID     *uuid.UUID
	Action      string
	SubjectType string
	SubjectID   *uuid.UUID
	Outcome     string
	Limit       int
	Offset      int
}
