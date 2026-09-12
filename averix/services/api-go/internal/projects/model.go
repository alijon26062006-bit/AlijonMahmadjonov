// Package projects owns the client's brief: creation, the personalised
// developer feed, and the targeting that decides whose feed it reaches.
package projects

import (
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/matching"
)

// Project is the full record, as its client sees it.
type Project struct {
	ID          uuid.UUID `json:"id"`
	Reference   string    `json:"reference"`
	Slug        string    `json:"slug"`
	Title       string    `json:"title"`
	Summary     string    `json:"summary,omitempty"`
	Description string    `json:"description"`

	Category CategoryRef `json:"category"`
	Skills   []SkillRef  `json:"skills"`
	Features []Feature   `json:"features,omitempty"`
	// Specialisations this brief is aimed at, with the relevance the taxonomy
	// assigned. Shown to the client so the targeting is not a black box.
	Targeting []TargetRef `json:"targeting,omitempty"`

	Status     string `json:"status"`
	Visibility string `json:"visibility"`

	Budget Budget `json:"budget"`

	DurationDays *int       `json:"duration_days,omitempty"`
	Deadline     *time.Time `json:"deadline,omitempty"`
	Starts       string     `json:"starts,omitempty"`

	ExperienceWanted string `json:"experience_wanted,omitempty"`
	OverlapFromUTC   *int   `json:"overlap_from_utc,omitempty"`
	OverlapToUTC     *int   `json:"overlap_to_utc,omitempty"`

	Client ClientRef `json:"client"`

	ProposalsCount   int `json:"proposals_count"`
	InvitationsCount int `json:"invitations_count"`
	ViewsCount       int `json:"views_count"`
	ShortlistedCount int `json:"shortlisted_count"`

	Origin          string `json:"origin"`
	ModerationState string `json:"moderation_state,omitempty"`
	ModerationNote  string `json:"moderation_note,omitempty"`

	PublishedAt *time.Time `json:"published_at,omitempty"`
	ExpiresAt   *time.Time `json:"expires_at,omitempty"`
	CompletedAt *time.Time `json:"completed_at,omitempty"`
	CreatedAt   time.Time  `json:"created_at"`
	UpdatedAt   time.Time  `json:"updated_at"`

	// Set for the developer viewing it: their match, whether they have already
	// proposed, whether they saved it.
	Match       *matching.Score `json:"match,omitempty"`
	HasProposed bool            `json:"has_proposed,omitempty"`
	IsSaved     bool            `json:"is_saved,omitempty"`
	IsInvited   bool            `json:"is_invited,omitempty"`
	IsOwner     bool            `json:"is_owner,omitempty"`
}

// FeedCard is the compact shape the mobile feed renders.
//
// A separate, deliberately small type: the feed is the screen most likely to
// be loaded on a slow connection, and sending a full project for each of
// twenty cards would be wasteful. Nothing here is text the card does not show.
type FeedCard struct {
	ID        uuid.UUID `json:"id"`
	Slug      string    `json:"slug"`
	Reference string    `json:"reference"`
	Title     string    `json:"title"`
	// One line, from the summary or the first sentence of the description.
	Excerpt string `json:"excerpt,omitempty"`

	Category CategoryRef `json:"category"`
	// At most five, which is what fits on a 375px card.
	Skills []SkillRef `json:"skills"`

	Budget Budget `json:"budget"`

	ProposalsCount int        `json:"proposals_count"`
	PublishedAt    *time.Time `json:"published_at,omitempty"`

	// The match score and its top reasons, so "94% match" is expandable
	// in place without another request.
	MatchScore      *int              `json:"match_score,omitempty"`
	MatchHighlights []matching.Reason `json:"match_highlights,omitempty"`

	ClientCountry  string `json:"client_country,omitempty"`
	ClientHires    int    `json:"client_hires"`
	ClientVerified bool   `json:"client_verified"`

	HasProposed bool `json:"has_proposed,omitempty"`
	IsSaved     bool `json:"is_saved,omitempty"`
	IsInvited   bool `json:"is_invited,omitempty"`
}

type Budget struct {
	Type     string `json:"type"`
	MinMinor *int64 `json:"min_minor,omitempty"`
	MaxMinor *int64 `json:"max_minor,omitempty"`
	Currency string `json:"currency"`
	// Pre-formatted for display, so twenty cards do not each run currency
	// formatting in the browser.
	Display string `json:"display"`
}

type CategoryRef struct {
	Slug string `json:"slug"`
	Name string `json:"name"`
	Path string `json:"path,omitempty"`
}

type SkillRef struct {
	Slug     string `json:"slug"`
	Name     string `json:"name"`
	Colour   string `json:"colour,omitempty"`
	Required bool   `json:"required"`
}

type TargetRef struct {
	Slug      string  `json:"slug"`
	Name      string  `json:"name"`
	Relevance float64 `json:"relevance"`
}

type Feature struct {
	ID       uuid.UUID `json:"id"`
	Title    string    `json:"title"`
	Detail   string    `json:"detail,omitempty"`
	Required bool      `json:"required"`
	Origin   string    `json:"origin"`
}

type ClientRef struct {
	UserID      uuid.UUID `json:"user_id"`
	Username    string    `json:"username"`
	DisplayName string    `json:"display_name"`
	CountryCode string    `json:"country_code,omitempty"`
	HiresMade   int       `json:"hires_made"`
	RatingAvg   *float64  `json:"rating_avg,omitempty"`
	RatingCount int       `json:"rating_count"`
	Verified    bool      `json:"verified"`
	MemberSince time.Time `json:"member_since"`
}

// FeedTab is one of the tabs on the developer home screen.
type FeedTab string

const (
	// TabForYou is the personalised feed: targeted and above the match
	// threshold, ordered by a blend of fit and freshness.
	TabForYou FeedTab = "for_you"
	// TabRecent is everything targeted at the developer, newest first.
	TabRecent FeedTab = "recent"
	// TabSaved is what they bookmarked.
	TabSaved FeedTab = "saved"
	// TabInvitations is projects a client invited them to.
	TabInvitations FeedTab = "invitations"
	// A category tab, e.g. "backend", "telegram", "ai".
	TabCategory FeedTab = "category"
)

// Tab describes a feed tab for the client to render.
type Tab struct {
	Key   string `json:"key"`
	Label string `json:"label"`
	// For a category tab, which category slug it filters to.
	CategorySlug string `json:"category_slug,omitempty"`
	Count        *int   `json:"count,omitempty"`
}

// Status values, kept as constants because the state machine is checked in
// several modules.
const (
	StatusDraft         = "draft"
	StatusPendingReview = "pending_review"
	StatusOpen          = "open"
	StatusInProgress    = "in_progress"
	StatusCompleted     = "completed"
	StatusCancelled     = "cancelled"
	StatusExpired       = "expired"
)

// canTransition encodes the project lifecycle. Anything not listed is refused,
// so an invalid transition is impossible rather than merely unlikely.
var canTransition = map[string]map[string]bool{
	StatusDraft:         {StatusPendingReview: true, StatusOpen: true, StatusCancelled: true},
	StatusPendingReview: {StatusOpen: true, StatusDraft: true, StatusCancelled: true},
	StatusOpen:          {StatusInProgress: true, StatusCancelled: true, StatusExpired: true, StatusDraft: true},
	StatusInProgress:    {StatusCompleted: true, StatusCancelled: true},
	StatusCompleted:     {},
	StatusCancelled:     {},
	StatusExpired:       {StatusOpen: true, StatusCancelled: true},
}

// CanTransition reports whether a status change is allowed.
func CanTransition(from, to string) bool {
	allowed, ok := canTransition[from]
	if !ok {
		return false
	}
	return allowed[to]
}
