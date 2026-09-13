// Package notifications tells people what happened while they were not
// looking: in the app, by email, and — once keys are configured — by push.
//
// A notification is a row first and a delivery second. The row is the record
// a person sees in their list; deliveries are the attempts to reach them on
// each channel, kept separately so an email that bounced does not erase the
// notification, and so a channel a person switched off is recorded as
// suppressed rather than pretended sent.
package notifications

import (
	"time"

	"github.com/google/uuid"
)

// The closed set of notification types. It mirrors the CHECK constraint on
// the table: a type not listed here cannot be stored, so adding one is a
// migration and a constant, deliberately.
const (
	TypeProposalReceived    = "proposal_received"
	TypeProposalAccepted    = "proposal_accepted"
	TypeProposalDeclined    = "proposal_declined"
	TypeProposalShortlisted = "proposal_shortlisted"
	TypeProjectInvitation   = "project_invitation"
	TypeProjectPublished    = "project_published"
	TypeProjectRecommended  = "project_recommended"
	TypeMessageReceived     = "message_received"
	TypeMilestoneSubmitted  = "milestone_submitted"
	TypeMilestoneRevision   = "milestone_revision_requested"
	TypeMilestoneApproved   = "milestone_approved"
	TypeMilestoneReleased   = "milestone_released"
	TypePaymentSucceeded    = "payment_succeeded"
	TypePaymentFailed       = "payment_failed"
	TypePaymentRefunded     = "payment_refunded"
	TypeReviewReceived      = "review_received"
	TypeReviewPublished     = "review_published"
	TypeGitHubComplete      = "github_analysis_complete"
	TypeGitHubFailed        = "github_analysis_failed"
	TypeContractStarted     = "contract_started"
	TypeContractCompleted   = "contract_completed"
	TypeContractCancelled   = "contract_cancelled"
	TypeDisputeOpened       = "dispute_opened"
	TypeDisputeResolved     = "dispute_resolved"
	TypeAccountVerified     = "account_verified"
	TypeAccountWarning      = "account_warning"
	TypeAccountSuspended    = "account_suspended"
	TypeIdentitySubmitted   = "identity_submitted"
	TypeIdentityApproved    = "identity_approved"
	TypeIdentityRejected    = "identity_rejected"
	TypeIdentityResubmit    = "identity_resubmit_requested"
)

// Channels.
const (
	ChannelInApp = "in_app"
	ChannelEmail = "email"
	ChannelPush  = "push"
)

// Delivery states, mirroring the table.
const (
	DeliveryQueued     = "queued"
	DeliverySent       = "sent"
	DeliveryDelivered  = "delivered"
	DeliveryFailed     = "failed"
	DeliverySkipped    = "skipped"
	DeliverySuppressed = "suppressed"
)

// Notification is what the list shows.
type Notification struct {
	ID        uuid.UUID  `json:"id"`
	Type      string     `json:"type"`
	Title     string     `json:"title"`
	Body      string     `json:"body,omitempty"`
	Href      string     `json:"href,omitempty"`
	Priority  string     `json:"priority"`
	ReadAt    *time.Time `json:"read_at,omitempty"`
	CreatedAt time.Time  `json:"created_at"`
	// Who caused it, when it was a person: the name and photo the list shows
	// next to the text.
	Actor *Actor `json:"actor,omitempty"`
}

type Actor struct {
	UserID   uuid.UUID `json:"user_id"`
	Username string    `json:"username"`
	FullName string    `json:"full_name"`
	PhotoURL string    `json:"photo_url,omitempty"`
}

// Preference is one row of the per-type channel matrix. A type without a row
// gets the defaults for that type, so a new type needs no backfill.
type Preference struct {
	Type  string `json:"type"`
	Label string `json:"label"`
	// Which channels this type may use at all. A milestone release cannot be
	// switched off in the app: money moving is not optional information.
	InAppLocked bool `json:"in_app_locked"`
	InApp       bool `json:"in_app"`
	Email       bool `json:"email"`
	Push        bool `json:"push"`
}

// Group names the section a preference is shown under.
type PreferenceGroup struct {
	Key         string       `json:"key"`
	Label       string       `json:"label"`
	Preferences []Preference `json:"preferences"`
}

// Input is what a module hands over. Everything a person will read is
// already composed: the notifier, not the store, knows how to phrase a
// declined proposal.
type Input struct {
	UserID   uuid.UUID
	Type     string
	Title    string
	Body     string
	Href     string
	Priority string
	ActorID  *uuid.UUID
	// Loose references for the list's grouping and for admin diagnostics.
	ProjectID   *uuid.UUID
	ContractID  *uuid.UUID
	ProposalID  *uuid.UUID
	MilestoneID *uuid.UUID
	Metadata    map[string]any
	// Email subject and body, when the type is emailable. Empty means the
	// title and body are used as they are.
	EmailSubject string
	EmailBody    string
}

// catalogue is the per-type default behaviour: which channels apply and
// under which heading the preference is shown. Types absent from it are
// in-app only.
type typeInfo struct {
	Group       string
	Label       string
	Email       bool
	Push        bool
	InAppLocked bool
	// Whether an email is pointless when the person has the app open. A
	// message is; a milestone release is not, because the record of money
	// moving belongs in their inbox regardless.
	SuppressWhenOnline bool
}

var catalogue = map[string]typeInfo{
	TypeProposalReceived:    {Group: "proposals", Label: "Новый отклик на ваш проект", Email: true, Push: true},
	TypeProposalAccepted:    {Group: "proposals", Label: "Ваш отклик принят", Email: true, Push: true, InAppLocked: true},
	TypeProposalDeclined:    {Group: "proposals", Label: "Ваш отклик отклонён", Email: true, Push: false},
	TypeProposalShortlisted: {Group: "proposals", Label: "Ваш отклик в шорт-листе", Email: true, Push: true},
	TypeProjectInvitation:   {Group: "proposals", Label: "Приглашение в проект", Email: true, Push: true},
	TypeProjectPublished:    {Group: "projects", Label: "Ваш проект опубликован", Email: false, Push: false},
	TypeProjectRecommended:  {Group: "projects", Label: "Подходящие вам проекты", Email: true, Push: false},
	TypeMessageReceived:     {Group: "messages", Label: "Новое сообщение", Email: true, Push: true, SuppressWhenOnline: true},
	TypeMilestoneSubmitted:  {Group: "contracts", Label: "Этап сдан на проверку", Email: true, Push: true, InAppLocked: true},
	TypeMilestoneRevision:   {Group: "contracts", Label: "Запрошены правки", Email: true, Push: true, InAppLocked: true},
	TypeMilestoneApproved:   {Group: "contracts", Label: "Этап принят", Email: true, Push: true, InAppLocked: true},
	TypeMilestoneReleased:   {Group: "contracts", Label: "Оплата этапа переведена", Email: true, Push: true, InAppLocked: true},
	TypePaymentSucceeded:    {Group: "payments", Label: "Платёж подтверждён", Email: true, Push: true, InAppLocked: true},
	TypePaymentFailed:       {Group: "payments", Label: "Платёж не прошёл", Email: true, Push: true, InAppLocked: true},
	TypePaymentRefunded:     {Group: "payments", Label: "Возврат средств", Email: true, Push: true, InAppLocked: true},
	TypeReviewReceived:      {Group: "reviews", Label: "Вам оставили отзыв", Email: true, Push: true},
	TypeReviewPublished:     {Group: "reviews", Label: "Отзыв опубликован", Email: true, Push: false},
	TypeGitHubComplete:      {Group: "account", Label: "Анализ GitHub завершён", Email: false, Push: false},
	TypeGitHubFailed:        {Group: "account", Label: "Анализ GitHub не удался", Email: false, Push: false},
	TypeContractStarted:     {Group: "contracts", Label: "Контракт подписан", Email: true, Push: true, InAppLocked: true},
	TypeContractCompleted:   {Group: "contracts", Label: "Контракт завершён", Email: true, Push: true, InAppLocked: true},
	TypeContractCancelled:   {Group: "contracts", Label: "Контракт отменён", Email: true, Push: true, InAppLocked: true},
	TypeDisputeOpened:       {Group: "contracts", Label: "Открыт спор", Email: true, Push: true, InAppLocked: true},
	TypeDisputeResolved:     {Group: "contracts", Label: "Спор решён", Email: true, Push: true, InAppLocked: true},
	TypeAccountVerified:     {Group: "account", Label: "Аккаунт подтверждён", Email: true, Push: false, InAppLocked: true},
	TypeAccountWarning:      {Group: "account", Label: "Предупреждение по аккаунту", Email: true, Push: true, InAppLocked: true},
	TypeAccountSuspended:    {Group: "account", Label: "Аккаунт заблокирован", Email: true, Push: false, InAppLocked: true},
	TypeIdentitySubmitted:   {Group: "account", Label: "Документы приняты на проверку", Email: true, Push: false, InAppLocked: true},
	TypeIdentityApproved:    {Group: "account", Label: "Личность подтверждена", Email: true, Push: true, InAppLocked: true},
	TypeIdentityRejected:    {Group: "account", Label: "Проверка личности отклонена", Email: true, Push: true, InAppLocked: true},
	TypeIdentityResubmit:    {Group: "account", Label: "Нужно переснять документ", Email: true, Push: true, InAppLocked: true},
}

var groupLabels = []struct{ Key, Label string }{
	{"proposals", "Отклики и приглашения"},
	{"projects", "Проекты"},
	{"messages", "Сообщения"},
	{"contracts", "Контракты и этапы"},
	{"payments", "Платежи"},
	{"reviews", "Отзывы"},
	{"account", "Аккаунт"},
}

// Known reports whether a type exists in the catalogue.
func Known(kind string) bool {
	_, ok := catalogue[kind]
	return ok
}

// Page is a keyset-paginated list.
type Page struct {
	Items      []Notification `json:"items"`
	NextBefore *time.Time     `json:"next_before,omitempty"`
	Unread     int            `json:"unread"`
}
