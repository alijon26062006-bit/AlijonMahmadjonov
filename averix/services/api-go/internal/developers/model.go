// Package developers owns developer profiles: the onboarding flow, the
// professional details, the profile photo and the public profile page.
package developers

import (
	"time"

	"github.com/google/uuid"
)

// Profile is the developer's own view of their profile — everything, including
// the private figures.
type Profile struct {
	UserID   uuid.UUID `json:"user_id"`
	Username string    `json:"username"`
	FullName string    `json:"full_name"`
	Email    string    `json:"email,omitempty"`

	PrimarySpecialisation     *SpecialisationRef  `json:"primary_specialisation,omitempty"`
	AdditionalSpecialisations []SpecialisationRef `json:"additional_specialisations"`
	ProfessionalTitle         string              `json:"professional_title,omitempty"`
	Bio                       string              `json:"bio,omitempty"`
	Skills                    []SkillRef          `json:"skills"`

	ExperienceLevel string `json:"experience_level,omitempty"`
	YearsExperience *int   `json:"years_experience,omitempty"`

	HourlyRateMinor *int64 `json:"hourly_rate_minor,omitempty"`
	MinProjectMinor *int64 `json:"min_project_minor,omitempty"`
	RateCurrency    string `json:"rate_currency"`

	Availability   string     `json:"availability"`
	HoursPerWeek   *int       `json:"hours_per_week,omitempty"`
	AvailableFrom  *time.Time `json:"available_from,omitempty"`
	OverlapFromUTC *int       `json:"overlap_from_utc,omitempty"`
	OverlapToUTC   *int       `json:"overlap_to_utc,omitempty"`

	CountryCode string     `json:"country_code,omitempty"`
	City        string     `json:"city,omitempty"`
	Timezone    string     `json:"timezone,omitempty"`
	Languages   []Language `json:"languages"`

	ShowLocation      bool `json:"show_location"`
	ShowHourlyRate    bool `json:"show_hourly_rate"`
	OpenToInvitations bool `json:"open_to_invitations"`

	Photo *PhotoSet `json:"photo,omitempty"`

	Reputation Reputation `json:"reputation"`

	// Private. Only ever serialised to the owner and to an admin.
	Earnings *Earnings `json:"earnings,omitempty"`

	Onboarding Onboarding `json:"onboarding"`

	GitHub *GitHubSummary `json:"github,omitempty"`

	IdentityVerified bool   `json:"identity_verified"`
	EmailVerified    bool   `json:"email_verified"`
	IsSearchable     bool   `json:"is_searchable"`
	IsFeatured       bool   `json:"is_featured"`
	ModerationState  string `json:"moderation_state,omitempty"`

	LastSeenAt  *time.Time `json:"last_seen_at,omitempty"`
	MemberSince time.Time  `json:"member_since"`
}

// PublicProfile is what a visitor sees. It is a separate type rather than the
// same struct with omitempty, so a new private field cannot leak by being
// forgotten — it has to be added here deliberately to become public.
type PublicProfile struct {
	UserID   uuid.UUID `json:"user_id"`
	Username string    `json:"username"`
	FullName string    `json:"full_name"`

	PrimarySpecialisation     *SpecialisationRef  `json:"primary_specialisation,omitempty"`
	AdditionalSpecialisations []SpecialisationRef `json:"additional_specialisations"`
	ProfessionalTitle         string              `json:"professional_title,omitempty"`
	Bio                       string              `json:"bio,omitempty"`
	Skills                    []SkillRef          `json:"skills"`

	ExperienceLevel string `json:"experience_level,omitempty"`
	YearsExperience *int   `json:"years_experience,omitempty"`

	// Present only when the developer chose to show it.
	HourlyRateMinor *int64 `json:"hourly_rate_minor,omitempty"`
	RateCurrency    string `json:"rate_currency,omitempty"`

	Availability  string     `json:"availability"`
	HoursPerWeek  *int       `json:"hours_per_week,omitempty"`
	AvailableFrom *time.Time `json:"available_from,omitempty"`

	// Present only when the developer chose to show it.
	Location  string     `json:"location,omitempty"`
	Languages []Language `json:"languages"`

	Photo *PhotoSet `json:"photo,omitempty"`

	Reputation Reputation `json:"reputation"`
	Badges     []Badge    `json:"badges"`

	GitHub *GitHubSummary `json:"github,omitempty"`

	MemberSince time.Time  `json:"member_since"`
	LastSeenAt  *time.Time `json:"last_seen_at,omitempty"`

	// Set for the developer viewing their own public profile.
	IsOwner bool `json:"is_owner,omitempty"`
	// Set when the viewing client has saved this developer.
	IsSaved bool `json:"is_saved,omitempty"`
}

type SpecialisationRef struct {
	Slug      string `json:"slug"`
	Name      string `json:"name"`
	ShortName string `json:"short_name"`
}

type SkillRef struct {
	Slug   string `json:"slug"`
	Name   string `json:"name"`
	Kind   string `json:"kind"`
	Level  string `json:"level,omitempty"`
	Years  *int   `json:"years,omitempty"`
	Colour string `json:"colour,omitempty"`
	// Where the corroboration came from: "github", "contract". Empty means
	// self-declared, which the UI shows differently.
	Evidence  []string `json:"evidence,omitempty"`
	IsPrimary bool     `json:"is_primary,omitempty"`
}

type Language struct {
	Language    string `json:"language"`
	Proficiency string `json:"proficiency"`
}

// PhotoSet is the rendered avatar in every size and format the product uses.
type PhotoSet struct {
	// Blur-up placeholder, an average colour rather than a base64 image so the
	// payload stays small on a mobile connection.
	Placeholder string `json:"placeholder,omitempty"`
	CropShape   string `json:"crop_shape"`
	// {"webp": {"64": "https://…"}, "jpeg": {...}}
	Sources map[string]map[string]string `json:"sources"`
	// The largest available size, for the profile portrait.
	Width int `json:"width"`
}

// Reputation is derived entirely from completed AVERIX contracts.
type Reputation struct {
	RatingAvg           *float64 `json:"rating_avg,omitempty"`
	RatingCount         int      `json:"rating_count"`
	RatingQuality       *float64 `json:"rating_quality,omitempty"`
	RatingCommunication *float64 `json:"rating_communication,omitempty"`
	RatingTechnical     *float64 `json:"rating_technical,omitempty"`
	RatingDeadline      *float64 `json:"rating_deadline,omitempty"`
	ProjectsCompleted   int      `json:"projects_completed"`
	SuccessRate         *float64 `json:"success_rate,omitempty"`
	OnTimeRate          *float64 `json:"on_time_rate,omitempty"`
	RepeatClients       int      `json:"repeat_clients"`
	// Median first response to a client message, in seconds.
	ResponseTimeSeconds *int `json:"response_time_seconds,omitempty"`
}

// Earnings is private to the owner. It is a separate struct so that including
// it requires an explicit decision at the call site.
type Earnings struct {
	TotalEarnedMinor int64  `json:"total_earned_minor"`
	Currency         string `json:"currency"`
	ActiveContracts  int    `json:"active_contracts"`
	PendingMinor     int64  `json:"pending_minor"`
}

type Badge struct {
	// "identity_verified" | "github_verified" | "available" | "top_rated" |
	// "fast_responder" | "featured"
	Kind  string `json:"kind"`
	Label string `json:"label"`
}

type GitHubSummary struct {
	Login       string    `json:"login"`
	ProfileURL  string    `json:"profile_url"`
	VerifiedAt  time.Time `json:"verified_at"`
	PublicRepos int       `json:"public_repos"`
	// Share of code by language, straight from GitHub's byte counts. Never
	// presented as a proficiency rating anywhere in the product.
	LanguageShare []LanguageShare `json:"language_share,omitempty"`
	// Prose written by the AI service, always rendered with its label.
	AISummary      string     `json:"ai_summary,omitempty"`
	AIGeneratedAt  *time.Time `json:"ai_generated_at,omitempty"`
	FocusAreas     []string   `json:"focus_areas,omitempty"`
	LastAnalysedAt *time.Time `json:"last_analysed_at,omitempty"`
	AnalysisState  string     `json:"analysis_state,omitempty"`
}

type LanguageShare struct {
	Language string  `json:"language"`
	Bytes    int64   `json:"bytes"`
	Share    float64 `json:"share"`
}

// Onboarding tracks the nine-step flow.
type Onboarding struct {
	Step         int        `json:"step"`
	TotalSteps   int        `json:"total_steps"`
	Completed    bool       `json:"completed"`
	CompletedAt  *time.Time `json:"completed_at,omitempty"`
	Completeness int        `json:"completeness"`
	// What is still missing, so the UI can prompt for the highest-value item
	// rather than a generic "complete your profile".
	Missing []MissingItem `json:"missing,omitempty"`
}

type MissingItem struct {
	Key   string `json:"key"`
	Label string `json:"label"`
	// How much completing this adds, so the UI can order the prompts.
	Weight int `json:"weight"`
	Step   int `json:"step"`
}

// The nine onboarding steps, in order. The labels are what the flow's header
// shows, and the keys are what the client posts to.
var OnboardingSteps = []struct {
	Step  int
	Key   string
	Label string
	// Whether the step may be skipped and returned to later. GitHub and
	// portfolio are genuinely optional; a specialisation is not.
	Optional bool
}{
	{1, "basics", "About you", false},
	{2, "specialisation", "Your main profession", false},
	{3, "additional_specialisations", "Other areas you work in", true},
	{4, "technologies", "Technologies", false},
	{5, "experience", "Experience", false},
	{6, "portfolio", "Portfolio", true},
	{7, "github", "GitHub", true},
	{8, "availability", "Availability", false},
	{9, "bio", "Your professional summary", false},
}

const TotalOnboardingSteps = 9
