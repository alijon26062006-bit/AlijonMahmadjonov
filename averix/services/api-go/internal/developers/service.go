package developers

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/validate"
	"github.com/averix/api/internal/security"
	"github.com/averix/api/internal/taxonomy"
)

type Service struct {
	store    *Store
	taxonomy *taxonomy.Store
	audit    *audit.Recorder
}

func NewService(store *Store, tax *taxonomy.Store, rec *audit.Recorder) *Service {
	return &Service{store: store, taxonomy: tax, audit: rec}
}

// Me returns the caller's own profile, including the private figures.
func (s *Service) Me(ctx context.Context, id *security.Identity) (*Profile, error) {
	if !id.Authenticated() {
		return nil, httpx.ErrUnauthenticated
	}
	profile, err := s.store.ByID(ctx, id.UserID)
	if errors.Is(err, ErrNotFound) {
		return nil, httpx.NotFoundf("no developer profile for user %s", id.UserID)
	}
	if err != nil {
		return nil, httpx.Internalf(err, "load own profile")
	}
	profile.Onboarding = s.assessOnboarding(profile)
	return profile, nil
}

// Public returns a developer's public profile.
//
// A profile that is hidden, unpublished or still in onboarding is a 404 to
// everyone but its owner and staff: reporting "exists but hidden" would leak
// that the account is there.
func (s *Service) Public(ctx context.Context, username string, viewer *security.Identity) (*PublicProfile, error) {
	profile, err := s.store.ByUsername(ctx, username)
	if errors.Is(err, ErrNotFound) {
		return nil, httpx.NotFoundf("no developer profile for username %q", username)
	}
	if err != nil {
		return nil, httpx.Internalf(err, "load public profile")
	}

	isOwner := viewer.Authenticated() && viewer.UserID == profile.UserID
	isStaff := viewer.Authenticated() &&
		(viewer.ActiveRole == security.RoleAdmin || viewer.ActiveRole == security.RoleModerator)

	visible := profile.IsSearchable && profile.ModerationState == "approved"
	if !visible && !isOwner && !isStaff {
		return nil, httpx.NotFoundf("developer %q is not publicly visible", username)
	}

	public := toPublic(profile)
	public.IsOwner = isOwner

	// The save button's state, only for a client who could act on it.
	if viewer.Authenticated() && viewer.ActiveRole == security.RoleClient {
		saved, err := s.store.IsSaved(ctx, viewer.UserID, profile.UserID)
		if err == nil {
			public.IsSaved = saved
		}
	}
	return public, nil
}

// toPublic projects a full profile onto the public shape.
//
// Copying field by field is the point: a private field added to Profile does
// not appear here unless someone writes the line, so the default for anything
// new is "not published".
func toPublic(p *Profile) *PublicProfile {
	out := &PublicProfile{
		UserID:                    p.UserID,
		Username:                  p.Username,
		FullName:                  p.FullName,
		PrimarySpecialisation:     p.PrimarySpecialisation,
		AdditionalSpecialisations: p.AdditionalSpecialisations,
		ProfessionalTitle:         p.ProfessionalTitle,
		Bio:                       p.Bio,
		Skills:                    p.Skills,
		ExperienceLevel:           p.ExperienceLevel,
		YearsExperience:           p.YearsExperience,
		Availability:              p.Availability,
		HoursPerWeek:              p.HoursPerWeek,
		AvailableFrom:             p.AvailableFrom,
		Languages:                 p.Languages,
		Photo:                     p.Photo,
		Reputation:                p.Reputation,
		GitHub:                    p.GitHub,
		MemberSince:               p.MemberSince,
		LastSeenAt:                p.LastSeenAt,
	}
	// Both of these are opt-in, and both default to the developer's choice
	// rather than to disclosure.
	if p.ShowHourlyRate && p.HourlyRateMinor != nil {
		out.HourlyRateMinor = p.HourlyRateMinor
		out.RateCurrency = p.RateCurrency
	}
	if p.ShowLocation {
		out.Location = formatLocation(p.City, p.CountryCode)
	}
	out.Badges = badgesFor(p)
	return out
}

func formatLocation(city, country string) string {
	switch {
	case city != "" && country != "":
		return city + ", " + country
	case country != "":
		return country
	default:
		return city
	}
}

// badgesFor derives the trust markers shown under a developer's name.
//
// Every one of them is earned from platform state, never self-declared: that
// is what makes them worth showing.
func badgesFor(p *Profile) []Badge {
	badges := []Badge{}
	if p.IdentityVerified {
		badges = append(badges, Badge{Kind: "identity_verified", Label: "Identity verified"})
	}
	if p.GitHub != nil && !p.GitHub.VerifiedAt.IsZero() {
		badges = append(badges, Badge{Kind: "github_verified", Label: "GitHub connected"})
	}
	if p.Availability == "available" {
		badges = append(badges, Badge{Kind: "available", Label: "Available for work"})
	}
	// Top rated needs both a high average and enough reviews for it to mean
	// something; one five-star review is not a track record.
	if p.Reputation.RatingAvg != nil && *p.Reputation.RatingAvg >= 4.8 && p.Reputation.RatingCount >= 5 {
		badges = append(badges, Badge{Kind: "top_rated", Label: "Top rated"})
	}
	if p.Reputation.ResponseTimeSeconds != nil && *p.Reputation.ResponseTimeSeconds <= 3600 &&
		p.Reputation.RatingCount >= 3 {
		badges = append(badges, Badge{Kind: "fast_responder", Label: "Responds quickly"})
	}
	if p.IsFeatured {
		badges = append(badges, Badge{Kind: "featured", Label: "Featured"})
	}
	return badges
}

// ── Profile completeness ────────────────────────────────────────────────────

// completenessItem is one thing that contributes to a complete profile. The
// weights add to 100 and are ordered so the UI prompts for the highest-value
// gap first — a missing bio matters more to a client than a missing city.
var completenessItems = []struct {
	Key    string
	Label  string
	Weight int
	Step   int
	Has    func(*Profile) bool
}{
	{"photo", "Profile photo", 15, 1, func(p *Profile) bool { return p.Photo != nil }},
	{"specialisation", "Main profession", 15, 2, func(p *Profile) bool { return p.PrimarySpecialisation != nil }},
	{"technologies", "Technologies", 15, 4, func(p *Profile) bool { return countPrimarySkills(p) >= 3 }},
	{"bio", "Professional summary", 15, 9, func(p *Profile) bool {
		return len([]rune(strings.TrimSpace(p.Bio))) >= 120
	}},
	{"experience", "Experience level", 10, 5, func(p *Profile) bool { return p.ExperienceLevel != "" }},
	{"availability", "Availability", 10, 8, func(p *Profile) bool { return p.Availability != "unavailable" }},
	{"rate", "Your rate", 5, 5, func(p *Profile) bool { return p.HourlyRateMinor != nil }},
	{"github", "GitHub account", 5, 7, func(p *Profile) bool { return p.GitHub != nil }},
	{"languages", "Languages you speak", 5, 1, func(p *Profile) bool { return len(p.Languages) > 0 }},
	{"location", "Location", 5, 1, func(p *Profile) bool { return p.CountryCode != "" }},
}

func countPrimarySkills(p *Profile) int {
	n := 0
	for _, sk := range p.Skills {
		if sk.IsPrimary {
			n++
		}
	}
	return n
}

// assessOnboarding computes completeness and what is still missing.
func (s *Service) assessOnboarding(p *Profile) Onboarding {
	total := 0
	missing := []MissingItem{}
	for _, item := range completenessItems {
		if item.Has(p) {
			total += item.Weight
			continue
		}
		missing = append(missing, MissingItem{
			Key: item.Key, Label: item.Label, Weight: item.Weight, Step: item.Step,
		})
	}
	return Onboarding{
		Step:         p.Onboarding.Step,
		TotalSteps:   TotalOnboardingSteps,
		Completed:    p.Onboarding.Completed,
		CompletedAt:  p.Onboarding.CompletedAt,
		Completeness: total,
		Missing:      missing,
	}
}

// refreshCompleteness recomputes and persists the score after a profile write,
// so the dashboard's prompt is current without a background job.
func (s *Service) refreshCompleteness(ctx context.Context, userID uuid.UUID) {
	profile, err := s.store.ByID(ctx, userID)
	if err != nil {
		return
	}
	assessment := s.assessOnboarding(profile)
	_ = s.store.SaveCompleteness(context.WithoutCancel(ctx), userID, assessment.Completeness)
}

// ── Onboarding steps ────────────────────────────────────────────────────────

// StepResult is returned by every onboarding write so the client can render
// progress without a second request.
type StepResult struct {
	Step       int        `json:"step"`
	NextStep   int        `json:"next_step"`
	Onboarding Onboarding `json:"onboarding"`
	Profile    *Profile   `json:"profile,omitempty"`
}

type BasicsRequest struct {
	FullName    string     `json:"full_name"`
	CountryCode string     `json:"country_code"`
	City        string     `json:"city"`
	Timezone    string     `json:"timezone"`
	Languages   []Language `json:"languages"`
}

func (s *Service) SaveBasics(ctx context.Context, id *security.Identity, in BasicsRequest) (*StepResult, error) {
	if err := s.requireDeveloper(id); err != nil {
		return nil, err
	}

	v := validate.New()
	name := v.Required("full_name", "Your name", in.FullName)
	v.Length("full_name", "Your name", in.FullName, 2, 120)
	v.NoControlChars("full_name", "Your name", in.FullName)
	if in.CountryCode != "" && len(in.CountryCode) != 2 {
		v.Add("country_code", "Use a two-letter country code.")
	}
	if in.City != "" {
		v.Length("city", "City", in.City, 1, 80)
	}
	if len(in.Languages) > 10 {
		v.Add("languages", "You can list up to 10 languages.")
	}
	for i, l := range in.Languages {
		if strings.TrimSpace(l.Language) == "" {
			v.Addf(fmt.Sprintf("languages.%d", i), "Name the language.")
		}
		v.OneOf(fmt.Sprintf("languages.%d.proficiency", i), "Proficiency", l.Proficiency,
			"basic", "conversational", "fluent", "native")
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	if err := s.store.SaveBasics(ctx, id.UserID, BasicsInput{
		FullName:    name,
		CountryCode: in.CountryCode,
		City:        strings.TrimSpace(in.City),
		Timezone:    strings.TrimSpace(in.Timezone),
		Languages:   in.Languages,
	}); err != nil {
		return nil, httpx.Internalf(err, "save basics")
	}
	return s.completeStep(ctx, id, 1)
}

type SpecialisationRequest struct {
	Slug  string `json:"slug"`
	Title string `json:"professional_title"`
}

func (s *Service) SavePrimarySpecialisation(ctx context.Context, id *security.Identity, in SpecialisationRequest) (*StepResult, error) {
	if err := s.requireDeveloper(id); err != nil {
		return nil, err
	}

	v := validate.New()
	slug := v.Required("slug", "Your main profession", in.Slug)
	if in.Title != "" {
		v.Length("professional_title", "Your title", in.Title, 3, 80)
		v.NoControlChars("professional_title", "Your title", in.Title)
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	// The slug is resolved against the taxonomy rather than trusted, so a
	// request cannot attach a specialisation that does not exist.
	specID, err := s.taxonomy.SpecialisationIDBySlug(ctx, slug)
	if err != nil {
		return nil, httpx.Validation(map[string]string{
			"slug": "That isn't one of the available professions.",
		})
	}

	if err := s.store.SetPrimarySpecialisation(ctx, id.UserID, specID, strings.TrimSpace(in.Title)); err != nil {
		return nil, httpx.Internalf(err, "set primary specialisation")
	}
	return s.completeStep(ctx, id, 2)
}

type AdditionalSpecialisationsRequest struct {
	Slugs []string `json:"slugs"`
}

func (s *Service) SaveAdditionalSpecialisations(ctx context.Context, id *security.Identity, in AdditionalSpecialisationsRequest) (*StepResult, error) {
	if err := s.requireDeveloper(id); err != nil {
		return nil, err
	}
	// The cap is a product decision, not a storage limit: a developer who
	// claims every area is claiming none of them credibly, and the matcher
	// would have nothing to work with.
	if len(in.Slugs) > 3 {
		return nil, httpx.Validation(map[string]string{
			"slugs": "Choose up to 3 additional areas. Your main profession is what clients see first.",
		})
	}

	ids := make([]uuid.UUID, 0, len(in.Slugs))
	for _, slug := range in.Slugs {
		specID, err := s.taxonomy.SpecialisationIDBySlug(ctx, strings.TrimSpace(slug))
		if err != nil {
			return nil, httpx.Validation(map[string]string{
				"slugs": fmt.Sprintf("%q isn't one of the available professions.", slug),
			})
		}
		ids = append(ids, specID)
	}

	err := s.store.SetAdditionalSpecialisations(ctx, id.UserID, ids)
	switch {
	case errors.Is(err, ErrTooManySpecialisations):
		return nil, httpx.Validation(map[string]string{"slugs": "Choose up to 3 additional areas."})
	case err != nil && strings.Contains(err.Error(), "repeat your main profession"):
		return nil, httpx.Validation(map[string]string{
			"slugs": "An additional area can't repeat your main profession.",
		})
	case err != nil:
		return nil, httpx.Internalf(err, "set additional specialisations")
	}
	return s.completeStep(ctx, id, 3)
}

type TechnologyRequest struct {
	Technologies []TechnologyEntry `json:"technologies"`
}

type TechnologyEntry struct {
	Slug  string `json:"slug"`
	Level string `json:"level"`
	Years *int   `json:"years,omitempty"`
}

func (s *Service) SaveTechnologies(ctx context.Context, id *security.Identity, in TechnologyRequest) (*StepResult, error) {
	if err := s.requireDeveloper(id); err != nil {
		return nil, err
	}

	v := validate.New()
	if len(in.Technologies) == 0 {
		v.Add("technologies", "Choose at least one technology you work with.")
	}
	if len(in.Technologies) > 15 {
		v.Add("technologies", "Choose up to 15 technologies — the ones you'd actually take work in.")
	}
	slugs := make([]string, 0, len(in.Technologies))
	for i, t := range in.Technologies {
		slugs = append(slugs, strings.TrimSpace(t.Slug))
		v.OneOf(fmt.Sprintf("technologies.%d.level", i), "Level", t.Level,
			"familiar", "working", "strong", "expert")
		if t.Years != nil {
			v.IntRange(fmt.Sprintf("technologies.%d.years", i), "Years", *t.Years, 0, 50)
		}
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	ids, unknown, err := s.taxonomy.ResolveSkillIDs(ctx, slugs)
	if err != nil {
		return nil, httpx.Internalf(err, "resolve technologies")
	}
	if len(unknown) > 0 {
		return nil, httpx.Validation(map[string]string{
			"technologies": fmt.Sprintf("We don't recognise: %s.", strings.Join(unknown, ", ")),
		})
	}

	// Positional alignment is safe because ResolveSkillIDs preserves input
	// order and unknown slugs have already been rejected.
	inputs := make([]SkillInput, 0, len(ids))
	for i, skillID := range ids {
		entry := in.Technologies[i]
		inputs = append(inputs, SkillInput{
			SkillID: skillID,
			Level:   entry.Level,
			Years:   entry.Years,
			Primary: true,
		})
	}

	if err := s.store.SetSkills(ctx, id.UserID, inputs); err != nil {
		if errors.Is(err, ErrTooManySkills) {
			return nil, httpx.Validation(map[string]string{
				"technologies": "Choose up to 15 technologies.",
			})
		}
		return nil, httpx.Internalf(err, "save technologies")
	}
	return s.completeStep(ctx, id, 4)
}

type ExperienceRequest struct {
	Level           string `json:"experience_level"`
	Years           *int   `json:"years_experience"`
	HourlyRateMinor *int64 `json:"hourly_rate_minor"`
	MinProjectMinor *int64 `json:"min_project_minor"`
	Currency        string `json:"currency"`
}

func (s *Service) SaveExperience(ctx context.Context, id *security.Identity, in ExperienceRequest) (*StepResult, error) {
	if err := s.requireDeveloper(id); err != nil {
		return nil, err
	}

	v := validate.New()
	level := v.OneOf("experience_level", "Experience level", in.Level,
		"junior", "mid", "senior", "lead")
	if in.Years != nil {
		v.IntRange("years_experience", "Years of experience", *in.Years, 0, 50)
	}
	currency := v.Currency("currency", in.Currency)
	if in.HourlyRateMinor != nil {
		// A floor and a ceiling: a $0 rate is a mistake, and a $10,000/hour
		// rate is a typo or a test.
		v.MoneyMinor("hourly_rate_minor", "Hourly rate", *in.HourlyRateMinor, 100, 100_000_00)
	}
	if in.MinProjectMinor != nil {
		v.MoneyMinor("min_project_minor", "Minimum project", *in.MinProjectMinor, 0, 1_000_000_00)
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	if err := s.store.SaveExperience(ctx, id.UserID, ExperienceInput{
		Level:           level,
		Years:           in.Years,
		HourlyRateMinor: in.HourlyRateMinor,
		MinProjectMinor: in.MinProjectMinor,
		Currency:        currency,
	}); err != nil {
		return nil, httpx.Internalf(err, "save experience")
	}
	return s.completeStep(ctx, id, 5)
}

type AvailabilityRequest struct {
	Availability   string  `json:"availability"`
	HoursPerWeek   *int    `json:"hours_per_week"`
	AvailableFrom  *string `json:"available_from"`
	OverlapFromUTC *int    `json:"overlap_from_utc"`
	OverlapToUTC   *int    `json:"overlap_to_utc"`
	OpenToInvites  *bool   `json:"open_to_invitations"`
	ShowLocation   *bool   `json:"show_location"`
	ShowHourlyRate *bool   `json:"show_hourly_rate"`
}

func (s *Service) SaveAvailability(ctx context.Context, id *security.Identity, in AvailabilityRequest) (*StepResult, error) {
	if err := s.requireDeveloper(id); err != nil {
		return nil, err
	}

	v := validate.New()
	availability := v.OneOf("availability", "Availability", in.Availability,
		"available", "limited", "booked", "unavailable")
	if in.HoursPerWeek != nil {
		v.IntRange("hours_per_week", "Hours per week", *in.HoursPerWeek, 1, 80)
	}
	if in.OverlapFromUTC != nil {
		v.IntRange("overlap_from_utc", "Timezone overlap start", *in.OverlapFromUTC, -12, 14)
	}
	if in.OverlapToUTC != nil {
		v.IntRange("overlap_to_utc", "Timezone overlap end", *in.OverlapToUTC, -12, 14)
	}
	if in.OverlapFromUTC != nil && in.OverlapToUTC != nil && *in.OverlapFromUTC > *in.OverlapToUTC {
		v.Add("overlap_to_utc", "The end of your overlap window must come after the start.")
	}

	var availableFrom *time.Time
	if in.AvailableFrom != nil && *in.AvailableFrom != "" {
		parsed, err := time.Parse("2006-01-02", *in.AvailableFrom)
		if err != nil {
			v.Add("available_from", "Use the format YYYY-MM-DD.")
		} else {
			availableFrom = &parsed
		}
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	if err := s.store.SaveAvailability(ctx, id.UserID, AvailabilityInput{
		Availability:   availability,
		HoursPerWeek:   in.HoursPerWeek,
		AvailableFrom:  availableFrom,
		OverlapFromUTC: in.OverlapFromUTC,
		OverlapToUTC:   in.OverlapToUTC,
		OpenToInvites:  in.OpenToInvites,
		ShowLocation:   in.ShowLocation,
		ShowHourlyRate: in.ShowHourlyRate,
	}); err != nil {
		return nil, httpx.Internalf(err, "save availability")
	}
	return s.completeStep(ctx, id, 8)
}

type BioRequest struct {
	Bio   string `json:"bio"`
	Title string `json:"professional_title"`
}

func (s *Service) SaveBio(ctx context.Context, id *security.Identity, in BioRequest) (*StepResult, error) {
	if err := s.requireDeveloper(id); err != nil {
		return nil, err
	}

	v := validate.New()
	// A floor of 120 characters is the product's judgement that three words is
	// not a professional summary, and the client shows a live counter so the
	// requirement is visible before submitting.
	v.Length("bio", "Your professional summary", in.Bio, 120, 3000)
	v.NoControlChars("bio", "Your professional summary", in.Bio)
	if in.Title != "" {
		v.Length("professional_title", "Your title", in.Title, 3, 80)
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	if err := s.store.SaveBio(ctx, id.UserID, strings.TrimSpace(in.Bio), strings.TrimSpace(in.Title)); err != nil {
		return nil, httpx.Internalf(err, "save bio")
	}
	return s.completeStep(ctx, id, 9)
}

// Finish completes onboarding and makes the profile discoverable.
func (s *Service) Finish(ctx context.Context, id *security.Identity) (*Profile, error) {
	if err := s.requireDeveloper(id); err != nil {
		return nil, err
	}
	profile, err := s.store.ByID(ctx, id.UserID)
	if err != nil {
		return nil, httpx.Internalf(err, "load profile")
	}

	// The mandatory steps must actually be done. Publishing an empty profile
	// would waste a client's time and the developer's first impression.
	v := validate.New()
	if profile.PrimarySpecialisation == nil {
		v.Add("specialisation", "Choose your main profession before publishing.")
	}
	if countPrimarySkills(profile) == 0 {
		v.Add("technologies", "Add the technologies you work with before publishing.")
	}
	if len([]rune(strings.TrimSpace(profile.Bio))) < 120 {
		v.Add("bio", "Write your professional summary before publishing.")
	}
	if profile.ExperienceLevel == "" {
		v.Add("experience_level", "Set your experience level before publishing.")
	}
	if !id.EmailVerified {
		v.Add("email", "Confirm your email address before publishing your profile.")
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	assessment := s.assessOnboarding(profile)
	if err := s.store.CompleteOnboarding(ctx, id.UserID, assessment.Completeness); err != nil {
		return nil, httpx.Internalf(err, "complete onboarding")
	}

	s.audit.RecordRequest(ctx, audit.Entry{
		Action: "developer.profile_published", SubjectType: "developer_profile",
		SubjectID: &id.UserID,
		After:     map[string]any{"completeness": assessment.Completeness},
	})

	updated, err := s.store.ByID(ctx, id.UserID)
	if err != nil {
		return nil, httpx.Internalf(err, "reload profile")
	}
	updated.Onboarding = s.assessOnboarding(updated)
	return updated, nil
}

// SetVisibility lets a developer hide their profile without deleting it, which
// is what someone who is fully booked actually wants.
func (s *Service) SetVisibility(ctx context.Context, id *security.Identity, searchable bool) error {
	if err := s.requireDeveloper(id); err != nil {
		return err
	}
	profile, err := s.store.ByID(ctx, id.UserID)
	if err != nil {
		return httpx.Internalf(err, "load profile")
	}
	if searchable && !profile.Onboarding.Completed {
		return httpx.Validation(map[string]string{
			"searchable": "Finish setting up your profile before making it visible.",
		})
	}
	if err := s.store.SetSearchable(ctx, id.UserID, searchable); err != nil {
		return httpx.Internalf(err, "set visibility")
	}
	return nil
}

func (s *Service) completeStep(ctx context.Context, id *security.Identity, step int) (*StepResult, error) {
	if err := s.store.AdvanceOnboarding(ctx, id.UserID, step+1); err != nil {
		return nil, httpx.Internalf(err, "advance onboarding")
	}
	s.refreshCompleteness(ctx, id.UserID)

	profile, err := s.store.ByID(ctx, id.UserID)
	if err != nil {
		return nil, httpx.Internalf(err, "reload profile")
	}
	assessment := s.assessOnboarding(profile)
	profile.Onboarding = assessment

	next := step + 1
	if next > TotalOnboardingSteps {
		next = TotalOnboardingSteps
	}
	return &StepResult{
		Step:       step,
		NextStep:   next,
		Onboarding: assessment,
		Profile:    profile,
	}, nil
}

func (s *Service) requireDeveloper(id *security.Identity) error {
	if !id.Authenticated() {
		return httpx.ErrUnauthenticated
	}
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return httpx.ErrForbidden.Wrap(err)
	}
	return nil
}

// Store exposes the store for the modules that need to read a developer's
// public shape (proposals, search, matching).
func (s *Service) Store() *Store { return s.store }
