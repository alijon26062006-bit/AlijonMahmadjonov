// Package identity owns the verification of a person's documents.
//
// Everything here exists because an identity document is not an ordinary
// upload. It is a passport photograph: it cannot live next to avatars, it
// cannot have a public URL, it cannot be readable by whoever happens to hold a
// staff role, and it cannot be kept forever because nobody remembered to
// delete it.
//
// The rules this package enforces:
//
//  1. Documents are written to their own prefix in the private bucket with
//     random keys, and are never recorded in the shared files table. There is
//     no code path that turns one of these keys into a public URL.
//  2. Reading a document requires a permission that no role grants — it is
//     handed to one account at a time and recorded — plus a password
//     re-authentication that expires in minutes.
//  3. Every read is written to an access log before the bytes are served. A
//     reviewer who opened a passport and changed nothing still leaves a trace.
//  4. Raw images have a retention date. When it passes, the images are deleted
//     and the verification result stays.
package identity

import (
	"time"

	"github.com/google/uuid"
)

// Status is the state of one verification case.
const (
	StatusDraft     = "draft"
	StatusSubmitted = "submitted"
	StatusUnderRev  = "under_review"
	StatusResubmit  = "resubmit_requested"
	StatusApproved  = "approved"
	StatusRejected  = "rejected"
	StatusSuspended = "suspended"
	StatusExpired   = "expired"
)

// Kind is which side of the document an image shows.
const (
	KindFront              = "front"
	KindBack               = "back"
	KindSelfie             = "selfie"
	KindSelfieWithDocument = "selfie_with_document"
)

// DocumentTypes is the closed set of documents accepted for verification.
var DocumentTypes = []struct {
	Key, Label string
	NeedsBack  bool
}{
	{"national_id", "Удостоверение личности", true},
	{"passport", "Паспорт", false},
	{"driver_licence", "Водительское удостоверение", true},
	{"residence_permit", "Вид на жительство", true},
}

func documentType(key string) (string, bool, bool) {
	for _, t := range DocumentTypes {
		if t.Key == key {
			return t.Label, t.NeedsBack, true
		}
	}
	return "", false, false
}

// ResubmitReasons is the closed set of reasons a reviewer may give when asking
// for a new photograph. Closed because a free-text reason is what produces
// "переснимите" with no explanation of what was wrong.
var ResubmitReasons = []struct {
	Key, Label string
	Kinds      []string
}{
	{"front_blurry", "Лицевая сторона не в фокусе", []string{KindFront}},
	{"back_blurry", "Оборотная сторона не в фокусе", []string{KindBack}},
	{"cropped", "Документ обрезан — нужен целиком, с краями", []string{KindFront, KindBack}},
	{"glare", "Блики перекрывают данные", []string{KindFront, KindBack}},
	{"expired", "Срок действия документа истёк", []string{KindFront}},
	{"unreadable", "Данные невозможно прочитать", []string{KindFront, KindBack}},
	{"selfie_unclear", "Лицо на селфи плохо видно", []string{KindSelfie, KindSelfieWithDocument}},
	{"selfie_requirements", "Селфи не соответствует требованиям", []string{KindSelfie, KindSelfieWithDocument}},
	{"document_not_visible", "На селфи не видно документ", []string{KindSelfieWithDocument}},
	{"mismatch", "Данные документа не совпадают с профилем", []string{KindFront}},
	{"new_photo_required", "Нужна новая фотография", nil},
}

func resubmitReason(key string) (string, []string, bool) {
	for _, r := range ResubmitReasons {
		if r.Key == key {
			return r.Label, r.Kinds, true
		}
	}
	return "", nil, false
}

// Case is one verification, as the owner and the reviewer both see it. It
// carries no image data and no storage keys: those never leave the server.
type Case struct {
	ID             uuid.UUID  `json:"id"`
	UserID         uuid.UUID  `json:"user_id"`
	Status         string     `json:"status"`
	StatusLabel    string     `json:"status_label"`
	DocumentType   string     `json:"document_type,omitempty"`
	DocumentLabel  string     `json:"document_label,omitempty"`
	CountryCode    string     `json:"country_code,omitempty"`
	SubmittedAt    *time.Time `json:"submitted_at,omitempty"`
	ReviewedAt     *time.Time `json:"reviewed_at,omitempty"`
	ReviewedBy     *uuid.UUID `json:"reviewed_by,omitempty"`
	ReviewerName   string     `json:"reviewer_name,omitempty"`
	DecisionReason string     `json:"decision_reason,omitempty"`
	// Which images the reviewer asked to be retaken, with the reason in words.
	Resubmit []ResubmitItem `json:"resubmit,omitempty"`
	// What this case still needs before it can be submitted.
	Required           []string   `json:"required"`
	Missing            []string   `json:"missing"`
	Documents          []Document `json:"documents"`
	RetentionExpiresAt *time.Time `json:"retention_expires_at,omitempty"`
	CreatedAt          time.Time  `json:"created_at"`
	UpdatedAt          time.Time  `json:"updated_at"`
}

type ResubmitItem struct {
	Key   string `json:"key"`
	Label string `json:"label"`
}

// Document describes an uploaded image without exposing where it is stored.
// The owner sees only that it exists; a reviewer additionally gets an id they
// can exchange for a short-lived viewing token.
type Document struct {
	ID        uuid.UUID  `json:"id"`
	Kind      string     `json:"kind"`
	KindLabel string     `json:"kind_label"`
	MIME      string     `json:"mime"`
	ByteSize  int64      `json:"byte_size"`
	Width     *int       `json:"width,omitempty"`
	Height    *int       `json:"height,omitempty"`
	Status    string     `json:"status"`
	CreatedAt time.Time  `json:"created_at"`
	DeletedAt *time.Time `json:"deleted_at,omitempty"`
}

func kindLabel(kind string) string {
	switch kind {
	case KindFront:
		return "Лицевая сторона"
	case KindBack:
		return "Оборотная сторона"
	case KindSelfie:
		return "Селфи"
	case KindSelfieWithDocument:
		return "Селфи с документом"
	}
	return kind
}

func statusLabel(status string) string {
	switch status {
	case StatusDraft:
		return "Черновик"
	case StatusSubmitted:
		return "Отправлено на проверку"
	case StatusUnderRev:
		return "На проверке"
	case StatusResubmit:
		return "Нужно переснять"
	case StatusApproved:
		return "Подтверждено"
	case StatusRejected:
		return "Отклонено"
	case StatusSuspended:
		return "Приостановлено"
	case StatusExpired:
		return "Истекло"
	}
	return status
}

// QueueItem is one line of the reviewer's queue. It names the person and the
// state of their case, and nothing from the documents themselves.
type QueueItem struct {
	ID           uuid.UUID `json:"id"`
	UserID       uuid.UUID `json:"user_id"`
	Username     string    `json:"username"`
	FullName     string    `json:"full_name"`
	Status       string    `json:"status"`
	StatusLabel  string    `json:"status_label"`
	DocumentType string    `json:"document_type,omitempty"`
	// Название документа словами. Очередь читают сотрудники, у которых нет
	// роли исполнителя, — а список типов документов живёт за формой подачи,
	// которая только для исполнителей. Проще прислать готовую подпись.
	DocumentLabel string     `json:"document_label,omitempty"`
	CountryCode   string     `json:"country_code,omitempty"`
	SubmittedAt   *time.Time `json:"submitted_at,omitempty"`
	WaitingHours  int        `json:"waiting_hours"`
	Documents     int        `json:"documents"`
}

// AccessEntry is one line of the log of who looked at what.
type AccessEntry struct {
	ID         int64      `json:"id"`
	ActorID    *uuid.UUID `json:"actor_id,omitempty"`
	ActorName  string     `json:"actor_name,omitempty"`
	SubjectID  *uuid.UUID `json:"subject_user_id,omitempty"`
	Resource   string     `json:"resource_type"`
	ResourceID string     `json:"resource_id,omitempty"`
	Action     string     `json:"action"`
	Reason     string     `json:"reason,omitempty"`
	IP         string     `json:"ip,omitempty"`
	CreatedAt  time.Time  `json:"created_at"`
}

// ReviewAction is one decision in a case's history.
type ReviewAction struct {
	ID        int64      `json:"id"`
	ActorID   *uuid.UUID `json:"actor_id,omitempty"`
	ActorName string     `json:"actor_name,omitempty"`
	Action    string     `json:"action"`
	Reason    string     `json:"reason,omitempty"`
	Detail    string     `json:"detail,omitempty"`
	CreatedAt time.Time  `json:"created_at"`
}
