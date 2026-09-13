// Package reviews owns what the two sides of a finished contract say about
// each other, and the verified history that a finished contract leaves on
// the freelancer's profile.
//
// Two rules shape everything here:
//
//   - A review is written blind. Neither side sees the other's until both
//     have submitted, or the window closes — so nothing is written in
//     retaliation for something already read.
//   - A review is about a contract that actually happened on the platform.
//     There is no other way to create one, which is what makes the rating
//     on a profile mean something.
package reviews

import (
	"time"

	"github.com/google/uuid"
)

const (
	// DirectionOfDeveloper is the client's review of the freelancer.
	DirectionOfDeveloper = "of_developer"
	// DirectionOfClient is the freelancer's review of the client.
	DirectionOfClient = "of_client"
)

// The named categories each side scores. The keys are the column names;
// the labels are what the form shows.
var (
	DeveloperCategories = []Category{
		{Key: "quality", Label: "Качество работы", Hint: "Результат соответствует тому, о чём договорились"},
		{Key: "communication", Label: "Общение", Hint: "Отвечал по делу и вовремя"},
		{Key: "technical", Label: "Профессионализм", Hint: "Знает своё дело, предлагал решения"},
		{Key: "deadline", Label: "Сроки", Hint: "Уложился в договорённые сроки"},
	}
	ClientCategories = []Category{
		{Key: "communication", Label: "Общение", Hint: "Был на связи и отвечал понятно"},
		{Key: "clarity", Label: "Ясность задачи", Hint: "Требования были понятны и не менялись на ходу"},
		{Key: "collaboration", Label: "Сотрудничество", Hint: "Давал обратную связь и принимал работу без затягивания"},
		{Key: "payment_reliability", Label: "Оплата", Hint: "Платил вовремя и без споров"},
	}
)

type Category struct {
	Key   string `json:"key"`
	Label string `json:"label"`
	Hint  string `json:"hint,omitempty"`
}

func categoriesFor(direction string) []Category {
	if direction == DirectionOfClient {
		return ClientCategories
	}
	return DeveloperCategories
}

// Party is the person on either end of a review.
type Party struct {
	UserID   uuid.UUID `json:"user_id"`
	Username string    `json:"username"`
	FullName string    `json:"full_name"`
	PhotoURL string    `json:"photo_url,omitempty"`
}

// Review is one side's account of a contract.
type Review struct {
	ID         uuid.UUID `json:"id"`
	ContractID uuid.UUID `json:"contract_id"`
	Direction  string    `json:"direction"`
	Author     Party     `json:"author"`
	Subject    Party     `json:"subject"`

	Overall float64 `json:"overall"`
	// Category scores keyed by category; only the categories for this
	// direction are present.
	Scores         map[string]float64 `json:"scores"`
	Comment        string             `json:"comment,omitempty"`
	WouldWorkAgain *bool              `json:"would_work_again,omitempty"`

	Response   string     `json:"response,omitempty"`
	ResponseAt *time.Time `json:"response_at,omitempty"`

	PublishedAt *time.Time `json:"published_at,omitempty"`
	CreatedAt   time.Time  `json:"created_at"`

	ContractTitle string `json:"contract_title,omitempty"`
	// Set for the caller's own review, so the interface can offer "respond"
	// only where it applies.
	IsMine     bool `json:"is_mine,omitempty"`
	IsAboutMe  bool `json:"is_about_me,omitempty"`
	CanRespond bool `json:"can_respond,omitempty"`
}

// Side is one direction's state on a contract as the caller sees it. The
// content is withheld until publication, but whether the other side has
// written is not a secret: knowing they have is what prompts you to.
type Side struct {
	Direction  string     `json:"direction"`
	Submitted  bool       `json:"submitted"`
	Published  bool       `json:"published"`
	Review     *Review    `json:"review,omitempty"`
	Categories []Category `json:"categories"`
}

// ContractReviews is the review panel on a workspace.
type ContractReviews struct {
	ContractID uuid.UUID `json:"contract_id"`
	// Whether the caller may write a review right now, and if not, why.
	CanReview      bool       `json:"can_review"`
	Reason         string     `json:"reason,omitempty"`
	MyDirection    string     `json:"my_direction,omitempty"`
	WindowClosesAt *time.Time `json:"window_closes_at,omitempty"`
	OfDeveloper    Side       `json:"of_developer"`
	OfClient       Side       `json:"of_client"`
}

// SubmitRequest is what a form posts.
type SubmitRequest struct {
	Scores         map[string]int `json:"scores"`
	Comment        string         `json:"comment"`
	WouldWorkAgain *bool          `json:"would_work_again"`
}

// HistoryEntry is a finished contract as it appears on a profile: a
// verified fact, never editable, only hideable.
type HistoryEntry struct {
	ID           uuid.UUID  `json:"id"`
	ContractID   uuid.UUID  `json:"contract_id"`
	Title        string     `json:"title"`
	Summary      string     `json:"summary,omitempty"`
	Category     *string    `json:"category,omitempty"`
	ClientRating *float64   `json:"client_rating,omitempty"`
	ReviewID     *uuid.UUID `json:"review_id,omitempty"`
	// Shown according to the contract's price visibility: the exact figure,
	// a range, or nothing.
	ValueDisplay string    `json:"value_display,omitempty"`
	DurationDays *int      `json:"duration_days,omitempty"`
	CompletedAt  time.Time `json:"completed_at"`
	IsVisible    bool      `json:"is_visible"`
}
