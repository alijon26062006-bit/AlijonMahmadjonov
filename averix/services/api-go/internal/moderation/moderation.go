// Package moderation is where content goes when a rule may have been broken
// and a person has to decide. Nothing here is automatic beyond the queue
// itself: a regex can flag, only a moderator can hide.
//
// Two sources feed the queue. Modules flag their own content (a proposal
// with a phone number in it, a service description inviting people off the
// platform), and users report what they see. Both end up as rows a
// moderator works through, with the decision and who made it recorded.
package moderation

import (
	"time"

	"github.com/google/uuid"
)

// Subject types a report or a queue item may point at. Mirrors the CHECK
// constraints; "user" reports go to the queue as escalations rather than
// being hidden, because a person is not content.
const (
	SubjectUser             = "user"
	SubjectProject          = "project"
	SubjectProposal         = "proposal"
	SubjectPortfolioProject = "portfolio_project"
	SubjectService          = "service"
	SubjectReview           = "review"
	SubjectMessage          = "message"
	SubjectDeveloperProfile = "developer_profile"
	SubjectPhoto            = "photo"
)

var reportReasons = map[string]string{
	"spam":                 "Спам",
	"fraud":                "Мошенничество",
	"off_platform_payment": "Предложение оплаты мимо платформы",
	"plagiarism":           "Чужая работа выдаётся за свою",
	"abuse":                "Оскорбления или угрозы",
	"misleading":           "Вводит в заблуждение",
	"nsfw":                 "Недопустимый контент",
	"impersonation":        "Выдаёт себя за другого",
	"security":             "Вредоносные ссылки или файлы",
	"other":                "Другое",
}

// ReportReasons is the list a report form shows.
func ReportReasons() []Reason {
	out := make([]Reason, 0, len(reportReasons))
	for _, key := range []string{"spam", "fraud", "off_platform_payment", "plagiarism", "abuse",
		"misleading", "nsfw", "impersonation", "security", "other"} {
		out = append(out, Reason{Key: key, Label: reportReasons[key]})
	}
	return out
}

type Reason struct {
	Key   string `json:"key"`
	Label string `json:"label"`
}

// ReportRequest is what a user files.
type ReportRequest struct {
	SubjectType string `json:"subject_type"`
	SubjectID   string `json:"subject_id"`
	Reason      string `json:"reason"`
	Detail      string `json:"detail"`
}

// QueueItem is one thing waiting for a decision, with enough context to
// decide without opening ten tabs.
type QueueItem struct {
	ID          uuid.UUID `json:"id"`
	SubjectType string    `json:"subject_type"`
	SubjectID   uuid.UUID `json:"subject_id"`
	Reason      string    `json:"reason"`
	Origin      string    `json:"origin"`
	Priority    int       `json:"priority"`
	Status      string    `json:"status"`
	CreatedAt   time.Time `json:"created_at"`
	// A title and an excerpt of the subject, resolved per type, and the
	// person it belongs to.
	Preview  Preview   `json:"preview"`
	Decision *Decision `json:"decision,omitempty"`
	Reports  int       `json:"reports"`
	Href     string    `json:"href,omitempty"`
}

type Preview struct {
	Title    string    `json:"title,omitempty"`
	Excerpt  string    `json:"excerpt,omitempty"`
	OwnerID  uuid.UUID `json:"owner_id,omitempty"`
	Username string    `json:"owner_username,omitempty"`
	State    string    `json:"moderation_state,omitempty"`
}

type Decision struct {
	By      uuid.UUID `json:"by"`
	ByName  string    `json:"by_name,omitempty"`
	Note    string    `json:"note,omitempty"`
	Outcome string    `json:"outcome"`
	At      time.Time `json:"at"`
}

// DecideRequest is the moderator's action on a queue item.
type DecideRequest struct {
	// "approve" leaves the content visible; "reject" hides it; "escalate"
	// hands it to an administrator.
	Outcome string `json:"outcome"`
	Note    string `json:"note"`
	// For a rejection: whether to also warn the owner.
	Warn bool `json:"warn"`
}

// Report is one user's report as the admin list shows it.
type Report struct {
	ID          uuid.UUID  `json:"id"`
	SubjectType string     `json:"subject_type"`
	SubjectID   uuid.UUID  `json:"subject_id"`
	Reason      string     `json:"reason"`
	ReasonLabel string     `json:"reason_label"`
	Detail      string     `json:"detail,omitempty"`
	Status      string     `json:"status"`
	Reporter    *Person    `json:"reporter,omitempty"`
	Resolution  string     `json:"resolution,omitempty"`
	ResolvedAt  *time.Time `json:"resolved_at,omitempty"`
	CreatedAt   time.Time  `json:"created_at"`
	Preview     Preview    `json:"preview"`
}

type Person struct {
	UserID   uuid.UUID `json:"user_id"`
	Username string    `json:"username"`
	FullName string    `json:"full_name"`
}
