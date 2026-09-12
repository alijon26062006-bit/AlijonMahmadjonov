// Package proposals owns the developer's bid and the client's review of it.
//
// The product decision this package enforces: a proposal is a document, not a
// message. Price, delivery, approach and relevant experience are all required,
// with real minimum lengths, so "ready to do it" cannot be submitted at all.
// That is what makes the client's inbox worth opening.
package proposals

import (
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/matching"
)

// Proposal is the full document, as its author and its recipient see it.
type Proposal struct {
	ID        uuid.UUID `json:"id"`
	ProjectID uuid.UUID `json:"project_id"`

	AmountMinor   int64  `json:"amount_minor"`
	Currency      string `json:"currency"`
	FeeMinor      int64  `json:"fee_minor"`
	PayoutMinor   int64  `json:"payout_minor"`
	AmountDisplay string `json:"amount_display"`
	DeliveryDays  int    `json:"delivery_days"`

	CoverLetter        string `json:"cover_letter"`
	Approach           string `json:"approach"`
	RelevantExperience string `json:"relevant_experience"`
	Questions          string `json:"questions,omitempty"`

	Milestones []Milestone    `json:"milestones,omitempty"`
	Evidence   []EvidenceItem `json:"evidence,omitempty"`

	Status        string `json:"status"`
	ClientNote    string `json:"client_note,omitempty"`
	DeclineReason string `json:"decline_reason,omitempty"`

	// The match as it stood when the proposal was submitted. Snapshotted so a
	// later weight change does not silently rewrite what the client was shown.
	MatchScore     *int            `json:"match_score,omitempty"`
	MatchBreakdown *matching.Score `json:"match_breakdown,omitempty"`

	Developer DeveloperCard `json:"developer"`

	ViewedAt      *time.Time `json:"viewed_at,omitempty"`
	ShortlistedAt *time.Time `json:"shortlisted_at,omitempty"`
	RespondedAt   *time.Time `json:"responded_at,omitempty"`
	WithdrawnAt   *time.Time `json:"withdrawn_at,omitempty"`
	CreatedAt     time.Time  `json:"created_at"`
	UpdatedAt     time.Time  `json:"updated_at"`

	// Set for the developer viewing their own proposal.
	IsAuthor bool `json:"is_author,omitempty"`
}

// Card is the compact shape the client's proposal list renders.
type Card struct {
	ID        uuid.UUID `json:"id"`
	ProjectID uuid.UUID `json:"project_id"`

	AmountMinor   int64  `json:"amount_minor"`
	Currency      string `json:"currency"`
	AmountDisplay string `json:"amount_display"`
	DeliveryDays  int    `json:"delivery_days"`

	// The first two lines of the cover letter, so the client can triage
	// without opening each one.
	Preview string `json:"preview"`

	MatchScore      *int              `json:"match_score,omitempty"`
	MatchHighlights []matching.Reason `json:"match_highlights,omitempty"`

	Developer DeveloperCard `json:"developer"`

	// The single most relevant piece of past work, which is what a client
	// actually looks at when comparing.
	TopEvidence *EvidenceItem `json:"top_evidence,omitempty"`

	Status         string     `json:"status"`
	MilestoneCount int        `json:"milestone_count"`
	ViewedAt       *time.Time `json:"viewed_at,omitempty"`
	ShortlistedAt  *time.Time `json:"shortlisted_at,omitempty"`
	CreatedAt      time.Time  `json:"created_at"`
}

// DeveloperCard is the developer summary shown on a proposal. It is built from
// the public profile, so nothing private can appear here.
type DeveloperCard struct {
	UserID            uuid.UUID `json:"user_id"`
	Username          string    `json:"username"`
	FullName          string    `json:"full_name"`
	ProfessionalTitle string    `json:"professional_title,omitempty"`
	PhotoURL          string    `json:"photo_url,omitempty"`
	Placeholder       string    `json:"placeholder,omitempty"`

	RatingAvg           *float64 `json:"rating_avg,omitempty"`
	RatingCount         int      `json:"rating_count"`
	ProjectsCompleted   int      `json:"projects_completed"`
	SuccessRate         *float64 `json:"success_rate,omitempty"`
	ResponseTimeSeconds *int     `json:"response_time_seconds,omitempty"`

	// At most five, matching the project's requirements first so a client
	// scanning a list sees the relevant ones.
	Skills []string `json:"skills"`

	Availability     string `json:"availability"`
	CountryCode      string `json:"country_code,omitempty"`
	IdentityVerified bool   `json:"identity_verified"`
	GitHubConnected  bool   `json:"github_connected"`
}

// Milestone is a step the developer proposes.
type Milestone struct {
	ID            uuid.UUID `json:"id,omitempty"`
	Position      int       `json:"position"`
	Title         string    `json:"title"`
	Detail        string    `json:"detail,omitempty"`
	AmountMinor   int64     `json:"amount_minor"`
	AmountDisplay string    `json:"amount_display,omitempty"`
	Days          *int      `json:"days,omitempty"`
}

// EvidenceItem is a piece of past work attached as evidence.
//
// Kind distinguishes the two kinds of trust, and the UI must render them
// differently: an AVERIX-verified contract is the platform's word, a portfolio
// item is the developer's.
type EvidenceItem struct {
	Kind  string    `json:"kind"` // "averix_verified" | "portfolio"
	ID    uuid.UUID `json:"id"`
	Title string    `json:"title"`
	Note  string    `json:"note,omitempty"`

	Technologies []string   `json:"technologies,omitempty"`
	CompletedAt  *time.Time `json:"completed_at,omitempty"`
	ClientRating *float64   `json:"client_rating,omitempty"`
	// Present only when the price visibility rules allow it.
	ValueDisplay string `json:"value_display,omitempty"`
	// For a portfolio item, where to see it.
	URL      string `json:"url,omitempty"`
	CoverURL string `json:"cover_url,omitempty"`
	Slug     string `json:"slug,omitempty"`
}

// SortOrder is how a client can order the proposal list. These are the tabs
// from the specification, and each answers a different question.
type SortOrder string

const (
	// SortRecommended blends match, track record and price into the order the
	// platform would suggest. The default.
	SortRecommended  SortOrder = "recommended"
	SortBestMatch    SortOrder = "best_match"
	SortNewest       SortOrder = "newest"
	SortPriceLow     SortOrder = "price_low"
	SortFastest      SortOrder = "fastest"
	SortHighestRated SortOrder = "highest_rated"
	SortShortlisted  SortOrder = "shortlisted"
)

func (s SortOrder) Valid() bool {
	switch s {
	case SortRecommended, SortBestMatch, SortNewest, SortPriceLow,
		SortFastest, SortHighestRated, SortShortlisted:
		return true
	}
	return false
}

// Status values.
const (
	StatusDraft       = "draft"
	StatusSubmitted   = "submitted"
	StatusViewed      = "viewed"
	StatusShortlisted = "shortlisted"
	StatusAccepted    = "accepted"
	StatusDeclined    = "declined"
	StatusWithdrawn   = "withdrawn"
	StatusExpired     = "expired"
)

// Live reports whether a status still represents an open bid.
func Live(status string) bool {
	switch status {
	case StatusSubmitted, StatusViewed, StatusShortlisted:
		return true
	}
	return false
}
