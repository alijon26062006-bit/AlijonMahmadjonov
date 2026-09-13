// Package search is how a client finds a freelancer and how anyone finds
// anything: the freelancer catalogue, the global search box, and the
// favourites that let a person keep what they found.
//
// Only what a person chose to make public is searchable, and only while the
// account is in good standing: a profile that is not finished, a suspended
// account or one under moderation does not appear, whatever the query.
package search

import (
	"time"

	"github.com/google/uuid"
)

type SkillRef struct {
	Slug   string `json:"slug"`
	Name   string `json:"name"`
	Colour string `json:"colour,omitempty"`
	// Corroborated by GitHub analysis or a completed contract, as opposed to
	// self-declared. The card draws the difference.
	Verified bool `json:"verified,omitempty"`
}

type SpecialisationRef struct {
	Slug      string `json:"slug"`
	Name      string `json:"name"`
	ShortName string `json:"short_name"`
}

// FreelancerCard is one tile in the catalogue: enough to decide whether to
// open the profile, nothing the person chose to hide.
type FreelancerCard struct {
	UserID            uuid.UUID          `json:"user_id"`
	Username          string             `json:"username"`
	FullName          string             `json:"full_name"`
	PhotoURL          string             `json:"photo_url,omitempty"`
	ProfessionalTitle string             `json:"professional_title,omitempty"`
	Specialisation    *SpecialisationRef `json:"specialisation,omitempty"`
	SectorSlug        string             `json:"sector_slug,omitempty"`
	Skills            []SkillRef         `json:"skills"`

	RatingAvg         *float64 `json:"rating_avg,omitempty"`
	RatingCount       int      `json:"rating_count"`
	ProjectsCompleted int      `json:"projects_completed"`

	// Present only when the freelancer shows their rate.
	HourlyRateMinor *int64 `json:"hourly_rate_minor,omitempty"`
	RateCurrency    string `json:"rate_currency,omitempty"`
	RateDisplay     string `json:"rate_display,omitempty"`

	Availability string `json:"availability"`
	// Present only when the freelancer shows their location.
	Location string `json:"location,omitempty"`

	IdentityVerified bool       `json:"identity_verified"`
	GitHubVerified   bool       `json:"github_verified"`
	IsFeatured       bool       `json:"is_featured,omitempty"`
	LastSeenAt       *time.Time `json:"last_seen_at,omitempty"`

	// For the signed-in client: whether this person is in their favourites.
	IsSaved bool   `json:"is_saved,omitempty"`
	Note    string `json:"note,omitempty"`
}

// FreelancerQuery is the catalogue's filter set.
type FreelancerQuery struct {
	Sector         string
	Specialisation string
	Skills         []string
	Text           string
	MinRateMinor   *int64
	MaxRateMinor   *int64
	Availability   string
	Verified       bool
	Sort           string // relevance | rating | rate_asc | rate_desc | newest | active
	Offset         int
	Limit          int
	ViewerID       *uuid.UUID
}

// ProjectHit is an open brief as the global search shows it.
type ProjectHit struct {
	ID            uuid.UUID  `json:"id"`
	Slug          string     `json:"slug"`
	Title         string     `json:"title"`
	Excerpt       string     `json:"excerpt,omitempty"`
	CategoryName  string     `json:"category_name"`
	CategorySlug  string     `json:"category_slug"`
	BudgetDisplay string     `json:"budget_display"`
	Proposals     int        `json:"proposals_count"`
	PublishedAt   *time.Time `json:"published_at,omitempty"`
}

// Results is the global search response: a few of each kind, with totals so
// the interface can offer "see all 42 freelancers".
type Results struct {
	Query       string           `json:"query"`
	Freelancers []FreelancerCard `json:"freelancers"`
	Services    any              `json:"services"`
	Projects    []ProjectHit     `json:"projects"`
	Totals      map[string]int   `json:"totals"`
}

// SavedFreelancer is a favourite with the client's private note.
type SavedFreelancer struct {
	FreelancerCard
	SavedAt time.Time `json:"saved_at"`
}
