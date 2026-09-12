// Package portfolio owns a developer's self-declared work.
//
// The product draws a hard line between this and completed_project_history:
// a portfolio item is the developer's word, a verified contract is the
// platform's. They are separate tables, separate types and separate sections
// of the profile, and nothing here can produce a verified entry.
package portfolio

import (
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/preview"
)

// Project is one portfolio item.
type Project struct {
	ID               uuid.UUID `json:"id"`
	DeveloperID      uuid.UUID `json:"developer_id"`
	Slug             string    `json:"slug"`
	Title            string    `json:"title"`
	ShortDescription string    `json:"short_description,omitempty"`
	Description      string    `json:"description,omitempty"`

	Category *CategoryRef `json:"category,omitempty"`
	Skills   []SkillRef   `json:"skills"`
	// What the developer did on it, in their own words.
	DeveloperRole string `json:"developer_role,omitempty"`

	Cover  *Image  `json:"cover,omitempty"`
	Images []Image `json:"images"`
	Links  []Link  `json:"links"`

	// The live URL, already normalised and validated.
	ProjectURL string `json:"project_url,omitempty"`
	// The host, for the preview browser's address bar.
	ProjectHost string `json:"project_host,omitempty"`
	// Whether the site can be shown inside AVERIX, from the server-side probe.
	Embeddable          string     `json:"embeddable"`
	EmbeddableReason    string     `json:"embeddable_reason,omitempty"`
	EmbeddableCheckedAt *time.Time `json:"embeddable_checked_at,omitempty"`
	RepositoryURL       string     `json:"repository_url,omitempty"`

	CompletedOn  *time.Time `json:"completed_on,omitempty"`
	DurationDays *int       `json:"duration_days,omitempty"`

	// The value, if the developer chose to show one, already resolved through
	// the visibility ladder. The raw figure is never serialised unless the
	// visibility is "public".
	ValueDisplay    string `json:"value_display,omitempty"`
	ValueVisibility string `json:"value_visibility"`
	// Present only to the owner, so they can see and edit what they entered.
	ValueMinor *int64 `json:"value_minor,omitempty"`
	Currency   string `json:"currency,omitempty"`

	DemoStatus  string `json:"demo_status"`
	IsPublished bool   `json:"is_published"`
	IsFeatured  bool   `json:"is_featured"`
	SortOrder   int    `json:"sort_order"`
	ViewCount   int    `json:"view_count"`

	ModerationState string `json:"moderation_state,omitempty"`
	ModerationNote  string `json:"moderation_note,omitempty"`

	// This is the field that keeps the two kinds of trust apart in the API as
	// well as in the database. Always "portfolio" here.
	Kind string `json:"kind"`

	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`

	IsOwner bool `json:"is_owner,omitempty"`
}

// Card is the compact shape a profile's portfolio grid renders.
type Card struct {
	ID    uuid.UUID `json:"id"`
	Slug  string    `json:"slug"`
	Title string    `json:"title"`
	// One line, from the short description.
	Excerpt string `json:"excerpt,omitempty"`
	// At most four technologies, which is what fits on a card.
	Skills []SkillRef `json:"skills"`
	Cover  *Image     `json:"cover,omitempty"`

	ProjectHost string `json:"project_host,omitempty"`
	// Whether the live-preview button should be offered at all.
	CanPreview   bool       `json:"can_preview"`
	DemoStatus   string     `json:"demo_status"`
	CompletedOn  *time.Time `json:"completed_on,omitempty"`
	ValueDisplay string     `json:"value_display,omitempty"`
	Kind         string     `json:"kind"`
	IsFeatured   bool       `json:"is_featured"`
}

type Image struct {
	ID      uuid.UUID `json:"id"`
	FileID  uuid.UUID `json:"file_id"`
	URL     string    `json:"url"`
	Caption string    `json:"caption,omitempty"`
	AltText string    `json:"alt_text,omitempty"`
	// Position in the gallery. Zero is the cover unless a cover is set.
	Position int  `json:"position"`
	Width    *int `json:"width,omitempty"`
	Height   *int `json:"height,omitempty"`
	// Average colour, so a loading image is a tinted block rather than a
	// white flash on a slow connection.
	Placeholder string `json:"placeholder,omitempty"`
	// The re-encoded sizes, so the gallery can ask for 480px on a phone
	// instead of downloading a 1920px screenshot. WebP first, JPEG after, and
	// URL above as the plain fallback for a client that reads neither.
	Variants []Variant `json:"variants,omitempty"`
}

// Variant is one rendered size of a screenshot.
type Variant struct {
	Format string `json:"format"`
	Width  int    `json:"width"`
	URL    string `json:"url"`
}

type Link struct {
	ID    uuid.UUID `json:"id"`
	Label string    `json:"label"`
	URL   string    `json:"url"`
	Host  string    `json:"host"`
	Kind  string    `json:"kind"`
}

type CategoryRef struct {
	Slug string `json:"slug"`
	Name string `json:"name"`
}

type SkillRef struct {
	Slug   string `json:"slug"`
	Name   string `json:"name"`
	Colour string `json:"colour,omitempty"`
}

// PreviewResponse is what the in-app browser needs to open a project.
type PreviewResponse struct {
	Project PreviewProject `json:"project"`
	Frame   preview.Frame  `json:"frame"`
	// The screenshot to show instead when the site refuses to be framed.
	Fallback *Image `json:"fallback,omitempty"`
}

// PreviewProject is the minimum the preview header needs: enough to render the
// browser chrome and the "back to profile" link, and nothing more.
type PreviewProject struct {
	ID        uuid.UUID    `json:"id"`
	Slug      string       `json:"slug"`
	Title     string       `json:"title"`
	Developer DeveloperRef `json:"developer"`
}

type DeveloperRef struct {
	Username string `json:"username"`
	FullName string `json:"full_name"`
	Title    string `json:"title,omitempty"`
	PhotoURL string `json:"photo_url,omitempty"`
}

// Link kinds, matching the database's CHECK constraint.
const (
	LinkLive       = "live"
	LinkRepository = "repository"
	LinkCaseStudy  = "case_study"
	LinkAppStore   = "app_store"
	LinkPlayStore  = "play_store"
	LinkArticle    = "article"
	LinkOther      = "other"
)

// Demo statuses. "nda" and "private_repo" exist because a developer often
// cannot show their best work, and saying so is better than an empty card.
const (
	DemoNone        = "none"
	DemoLive        = "live"
	DemoStaging     = "staging"
	DemoOffline     = "offline"
	DemoPrivateRepo = "private_repo"
	DemoNDA         = "nda"
)

// Kind values, so the interface can render the two kinds of trust differently.
const (
	KindPortfolio = "portfolio"
	KindVerified  = "averix_verified"
)
