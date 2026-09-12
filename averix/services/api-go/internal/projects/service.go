package projects

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/matching"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/validate"
	"github.com/averix/api/internal/security"
	"github.com/averix/api/internal/taxonomy"
)

// Settings are the runtime limits an administrator can change without a deploy.
type Settings interface {
	Int(ctx context.Context, key string, fallback int) int
	Bool(ctx context.Context, key string, fallback bool) bool
}

type Service struct {
	store    *Store
	taxonomy *taxonomy.Store
	matching *matching.Store
	audit    *audit.Recorder
	settings Settings
}

func NewService(store *Store, tax *taxonomy.Store, match *matching.Store,
	rec *audit.Recorder, settings Settings) *Service {
	return &Service{store: store, taxonomy: tax, matching: match, audit: rec, settings: settings}
}

// ── Creation ────────────────────────────────────────────────────────────────

type CreateRequest struct {
	Title            string           `json:"title"`
	Summary          string           `json:"summary"`
	Description      string           `json:"description"`
	CategorySlug     string           `json:"category_slug"`
	RequiredSkills   []string         `json:"required_skills"`
	OptionalSkills   []string         `json:"optional_skills"`
	Features         []FeatureRequest `json:"features"`
	BudgetType       string           `json:"budget_type"`
	BudgetMinMinor   *int64           `json:"budget_min_minor"`
	BudgetMaxMinor   *int64           `json:"budget_max_minor"`
	Currency         string           `json:"currency"`
	DurationDays     *int             `json:"duration_days"`
	Deadline         *string          `json:"deadline"`
	Starts           string           `json:"starts"`
	ExperienceWanted string           `json:"experience_wanted"`
	OverlapFromUTC   *int             `json:"overlap_from_utc"`
	OverlapToUTC     *int             `json:"overlap_to_utc"`
	Visibility       string           `json:"visibility"`
	// Set when the brief came out of the AI wizard, so provenance is recorded.
	AssistantSessionID *string `json:"assistant_session_id"`
	// Publish immediately rather than saving as a draft.
	Publish bool `json:"publish"`
}

type FeatureRequest struct {
	Title    string `json:"title"`
	Detail   string `json:"detail"`
	Required bool   `json:"required"`
	Origin   string `json:"origin"`
}

func (s *Service) Create(ctx context.Context, id *security.Identity, in CreateRequest) (*Project, error) {
	if err := s.requireClient(id); err != nil {
		return nil, err
	}

	// A client with fifteen open briefs and no hires is either confused or
	// spamming; both are better served by a limit than by a moderation queue.
	maxOpen := s.settings.Int(ctx, "projects.max_open_per_client", 15)
	open, err := s.store.OpenProjectCount(ctx, id.UserID)
	if err != nil {
		return nil, httpx.Internalf(err, "count open projects")
	}
	if open >= maxOpen {
		e := *httpx.ErrConflict
		e.Code = "too_many_open_projects"
		e.Message = fmt.Sprintf(
			"You have %d projects open or in draft. Close or publish some before adding another.", open)
		return nil, &e
	}

	validated, err := s.validateCreate(ctx, in)
	if err != nil {
		return nil, err
	}
	validated.ClientID = id.UserID

	projectID, err := s.store.Create(ctx, *validated)
	if err != nil {
		return nil, httpx.Internalf(err, "create project")
	}

	if in.Publish {
		if _, err := s.publish(ctx, id, projectID); err != nil {
			// The draft exists; the client can publish it from the UI.
			return s.ownProject(ctx, id, projectID)
		}
	}
	return s.ownProject(ctx, id, projectID)
}

func (s *Service) validateCreate(ctx context.Context, in CreateRequest) (*NewProject, error) {
	v := validate.New()

	title := v.Required("title", "Project title", in.Title)
	v.Length("title", "Project title", in.Title, 8, 140)
	v.NoControlChars("title", "Project title", in.Title)

	description := v.Required("description", "Project description", in.Description)
	// 40 characters is the floor the database enforces; the client shows a
	// counter, so anything shorter is a deliberate attempt to post nothing.
	v.Length("description", "Project description", in.Description, 40, 20000)
	v.NoControlChars("description", "Project description", in.Description)

	if in.Summary != "" {
		v.Length("summary", "Summary", in.Summary, 0, 300)
	}

	budgetType := v.OneOf("budget_type", "Budget type", defaultTo(in.BudgetType, "fixed"),
		"fixed", "range", "hourly")
	currency := v.Currency("currency", in.Currency)
	visibility := v.OneOf("visibility", "Visibility", defaultTo(in.Visibility, "public"),
		"public", "invite_only", "private")

	if in.BudgetMinMinor != nil {
		v.MoneyMinor("budget_min_minor", "Minimum budget", *in.BudgetMinMinor, 1000, 10_000_000_00)
	}
	if in.BudgetMaxMinor != nil {
		v.MoneyMinor("budget_max_minor", "Maximum budget", *in.BudgetMaxMinor, 1000, 10_000_000_00)
	}
	if in.BudgetMinMinor != nil && in.BudgetMaxMinor != nil && *in.BudgetMinMinor > *in.BudgetMaxMinor {
		v.Add("budget_max_minor", "The maximum budget must be at least the minimum.")
	}
	if in.BudgetMinMinor == nil && in.BudgetMaxMinor == nil {
		v.Add("budget_max_minor", "Set a budget so developers know what to propose.")
	}
	if budgetType == "range" && (in.BudgetMinMinor == nil || in.BudgetMaxMinor == nil) {
		v.Add("budget_min_minor", "A budget range needs both a minimum and a maximum.")
	}

	if in.DurationDays != nil {
		v.IntRange("duration_days", "Duration", *in.DurationDays, 1, 1095)
	}
	if in.Starts != "" {
		v.OneOf("starts", "Start time", in.Starts,
			"immediately", "within_week", "within_month", "flexible")
	}
	if in.ExperienceWanted != "" {
		v.OneOf("experience_wanted", "Experience wanted", in.ExperienceWanted,
			"any", "junior", "mid", "senior", "lead")
	}
	if in.OverlapFromUTC != nil {
		v.IntRange("overlap_from_utc", "Overlap start", *in.OverlapFromUTC, -12, 14)
	}
	if in.OverlapToUTC != nil {
		v.IntRange("overlap_to_utc", "Overlap end", *in.OverlapToUTC, -12, 14)
	}

	var deadline *time.Time
	if in.Deadline != nil && *in.Deadline != "" {
		parsed, err := time.Parse("2006-01-02", *in.Deadline)
		switch {
		case err != nil:
			v.Add("deadline", "Use the format YYYY-MM-DD.")
		case parsed.Before(time.Now().AddDate(0, 0, -1)):
			v.Add("deadline", "The deadline is in the past.")
		default:
			deadline = &parsed
		}
	}

	if strings.TrimSpace(in.CategorySlug) == "" {
		v.Add("category_slug", "Choose what kind of work this is.")
	}
	if len(in.RequiredSkills) > 15 {
		v.Add("required_skills", "List up to 15 required technologies.")
	}
	if len(in.OptionalSkills) > 15 {
		v.Add("optional_skills", "List up to 15 nice-to-have technologies.")
	}
	if len(in.Features) > 40 {
		v.Add("features", "That is more features than a single project should carry.")
	}
	for i, f := range in.Features {
		if strings.TrimSpace(f.Title) == "" {
			v.Addf(fmt.Sprintf("features.%d.title", i), "Describe the feature.")
		}
		if len(f.Title) > 160 {
			v.Addf(fmt.Sprintf("features.%d.title", i), "Keep the feature title under 160 characters.")
		}
	}

	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	categoryID, err := s.taxonomy.CategoryIDBySlug(ctx, strings.TrimSpace(in.CategorySlug))
	if err != nil {
		return nil, httpx.Validation(map[string]string{
			"category_slug": "That isn't one of the available categories.",
		})
	}

	requiredIDs, unknown, err := s.taxonomy.ResolveSkillIDs(ctx, in.RequiredSkills)
	if err != nil {
		return nil, httpx.Internalf(err, "resolve required skills")
	}
	if len(unknown) > 0 {
		return nil, httpx.Validation(map[string]string{
			"required_skills": fmt.Sprintf("We don't recognise: %s.", strings.Join(unknown, ", ")),
		})
	}
	optionalIDs, unknown, err := s.taxonomy.ResolveSkillIDs(ctx, in.OptionalSkills)
	if err != nil {
		return nil, httpx.Internalf(err, "resolve optional skills")
	}
	if len(unknown) > 0 {
		return nil, httpx.Validation(map[string]string{
			"optional_skills": fmt.Sprintf("We don't recognise: %s.", strings.Join(unknown, ", ")),
		})
	}

	var assistantSession *uuid.UUID
	origin := "manual"
	if in.AssistantSessionID != nil && *in.AssistantSessionID != "" {
		parsed, err := uuid.Parse(*in.AssistantSessionID)
		if err != nil {
			return nil, httpx.Validation(map[string]string{
				"assistant_session_id": "That draft reference isn't valid.",
			})
		}
		assistantSession = &parsed
		origin = "assistant"
	}

	features := make([]NewFeature, 0, len(in.Features))
	for _, f := range in.Features {
		featureOrigin := "client"
		if f.Origin == "assistant" {
			featureOrigin = "assistant"
		}
		features = append(features, NewFeature{
			Title:    strings.TrimSpace(f.Title),
			Detail:   strings.TrimSpace(f.Detail),
			Required: f.Required,
			Origin:   featureOrigin,
		})
	}

	return &NewProject{
		Title:            title,
		Summary:          strings.TrimSpace(in.Summary),
		Description:      description,
		CategoryID:       categoryID,
		BudgetType:       budgetType,
		BudgetMinMinor:   in.BudgetMinMinor,
		BudgetMaxMinor:   in.BudgetMaxMinor,
		Currency:         currency,
		DurationDays:     in.DurationDays,
		Deadline:         deadline,
		Starts:           in.Starts,
		ExperienceWanted: in.ExperienceWanted,
		OverlapFromUTC:   in.OverlapFromUTC,
		OverlapToUTC:     in.OverlapToUTC,
		Visibility:       visibility,
		Origin:           origin,
		AssistantSession: assistantSession,
		RequiredSkills:   requiredIDs,
		OptionalSkills:   optionalIDs,
		Features:         features,
	}, nil
}

// ── Publish ─────────────────────────────────────────────────────────────────

// Publish moves a draft to open, after checking it is worth a developer's time.
func (s *Service) Publish(ctx context.Context, id *security.Identity, projectID uuid.UUID) (*Project, error) {
	if err := s.requireClient(id); err != nil {
		return nil, err
	}
	if err := s.requireOwner(ctx, id, projectID); err != nil {
		return nil, err
	}
	return s.publish(ctx, id, projectID)
}

func (s *Service) publish(ctx context.Context, id *security.Identity, projectID uuid.UUID) (*Project, error) {
	project, err := s.store.ByID(ctx, projectID)
	if err != nil {
		return nil, s.mapStoreError(err)
	}

	// Publishing requires a confirmed address: a brief is a public invitation
	// to spend hours writing a proposal, and an unverified client could be
	// anyone.
	if !id.EmailVerified {
		e := *httpx.ErrForbidden
		e.Code = "email_not_verified"
		e.Message = "Please confirm your email address before publishing a project."
		return nil, &e
	}

	v := validate.New()
	if len(project.Skills) == 0 {
		v.Add("required_skills", "Add at least one technology so the right developers see this.")
	}
	if project.Budget.MinMinor == nil && project.Budget.MaxMinor == nil {
		v.Add("budget", "Set a budget before publishing.")
	}
	if len(project.Targeting) == 0 {
		// Nobody would ever see it, which is a configuration problem rather
		// than the client's mistake — so say something useful.
		v.Add("category_slug", "This category isn't matched to any specialisation yet. Please choose another.")
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	if _, err := s.store.Transition(ctx, projectID, StatusOpen); err != nil {
		if errors.Is(err, ErrBadTransition) {
			e := *httpx.ErrConflict
			e.Code = "cannot_publish"
			e.Message = "This project can't be published from its current state."
			return nil, e.Wrap(err)
		}
		return nil, httpx.Internalf(err, "publish project")
	}

	s.audit.RecordRequest(ctx, audit.Entry{
		Action: audit.ActionProjectPublished, SubjectType: "project", SubjectID: &projectID,
		After: map[string]any{
			"reference": project.Reference,
			"category":  project.Category.Slug,
			"targeting": len(project.Targeting),
		},
	})
	return s.ownProject(ctx, id, projectID)
}

// ── Reads ───────────────────────────────────────────────────────────────────

// View returns a project as the caller is entitled to see it.
func (s *Service) View(ctx context.Context, viewer *security.Identity, slugOrID string) (*Project, error) {
	project, err := s.load(ctx, slugOrID)
	if err != nil {
		return nil, err
	}

	isOwner := viewer.Authenticated() && viewer.UserID == project.Client.UserID
	isStaff := viewer.Authenticated() &&
		(viewer.ActiveRole == security.RoleAdmin || viewer.ActiveRole == security.RoleModerator)

	// A draft, a private brief, or a hidden one is nobody's business but its
	// owner's. Reporting "exists but hidden" would leak that it is there.
	visible := project.Status == StatusOpen && project.ModerationState == "approved"
	if !visible && !isOwner && !isStaff {
		// An invited developer may see an invite-only project, and so may a
		// developer already involved in it: once someone has proposed on a
		// brief or been hired for it, the brief is part of their own record —
		// and the contract workspace links straight to it.
		allowed := false
		if viewer.Authenticated() && viewer.ActiveRole == security.RoleDeveloper {
			allowed, _ = s.store.IsInvited(ctx, project.ID, viewer.UserID)
			if !allowed {
				allowed, _ = s.store.IsInvolved(ctx, project.ID, viewer.UserID)
			}
		}
		if !allowed {
			return nil, httpx.NotFoundf("project %s is not visible to this caller", project.Reference)
		}
	}
	if project.Visibility == "private" && !isOwner && !isStaff {
		invited, _ := s.store.IsInvited(ctx, project.ID, viewer.UserID)
		if !invited {
			return nil, httpx.NotFoundf("project %s is private", project.Reference)
		}
	}

	project.IsOwner = isOwner
	if !isOwner {
		// Moderation notes are between the client and staff.
		project.ModerationNote = ""
	}

	if viewer.Authenticated() && viewer.ActiveRole == security.RoleDeveloper {
		if err := s.decorateForDeveloper(ctx, project, viewer.UserID); err != nil {
			return nil, err
		}
		var viewerID *uuid.UUID = &viewer.UserID
		s.store.RecordView(ctx, project.ID, viewerID, "direct")
	} else if !isOwner {
		s.store.RecordView(ctx, project.ID, nil, "direct")
	}
	return project, nil
}

// decorateForDeveloper attaches the viewer's own match, proposal and save state.
func (s *Service) decorateForDeveloper(ctx context.Context, project *Project, developerID uuid.UUID) error {
	proposed, err := s.store.HasProposed(ctx, project.ID, developerID)
	if err != nil {
		return httpx.Internalf(err, "check existing proposal")
	}
	project.HasProposed = proposed

	saved, _ := s.store.IsSaved(ctx, project.ID, developerID)
	project.IsSaved = saved
	invited, _ := s.store.IsInvited(ctx, project.ID, developerID)
	project.IsInvited = invited

	weights, err := s.matching.ActiveWeights(ctx)
	if err != nil {
		// Scoring is a decoration on this screen; the project itself still
		// renders without it.
		return nil
	}
	if cached, ok := s.matching.CachedScore(ctx, project.ID, developerID, weights.Version, time.Hour); ok {
		project.Match = &cached
		return nil
	}

	projectFacts, err := s.matching.ProjectFactsByID(ctx, project.ID)
	if err != nil {
		return nil
	}
	developerFacts, err := s.matching.DeveloperFactsByID(ctx, developerID)
	if err != nil {
		return nil
	}
	score := matching.NewEngine(weights).Score(projectFacts, developerFacts)
	project.Match = &score
	_ = s.matching.SaveScore(context.WithoutCancel(ctx), project.ID, developerID, score)
	return nil
}

// Feed returns a page of the developer's personalised feed.
func (s *Service) Feed(ctx context.Context, id *security.Identity, q FeedQuery) (*FeedPage, error) {
	if err := s.requireDeveloper(id); err != nil {
		return nil, err
	}
	q.DeveloperID = id.UserID

	weights, err := s.matching.ActiveWeights(ctx)
	if err != nil {
		weights = matching.DefaultWeights()
	}
	threshold := weights.FeedThreshold
	if override := s.settings.Int(ctx, "feed.threshold_override", -1); override >= 0 {
		threshold = override
	}

	facts, err := s.matching.DeveloperFactsByID(ctx, id.UserID)
	if err != nil {
		return nil, httpx.Internalf(err, "load developer facts")
	}

	page, err := s.store.Feed(ctx, q, matching.NewEngine(weights), facts, threshold)
	if err != nil {
		return nil, httpx.Internalf(err, "load feed")
	}
	return page, nil
}

func (s *Service) Tabs(ctx context.Context, id *security.Identity) ([]Tab, error) {
	if err := s.requireDeveloper(id); err != nil {
		return nil, err
	}
	tabs, err := s.store.Tabs(ctx, id.UserID)
	if err != nil {
		return nil, httpx.Internalf(err, "load feed tabs")
	}
	return tabs, nil
}

// MyProjects lists the caller's own projects.
func (s *Service) MyProjects(ctx context.Context, id *security.Identity, status string) ([]Project, error) {
	if err := s.requireClient(id); err != nil {
		return nil, err
	}
	if status != "" && !isKnownStatus(status) {
		return nil, httpx.Validation(map[string]string{"status": "That isn't a project status."})
	}
	projects, err := s.store.ClientProjects(ctx, id.UserID, status, 100)
	if err != nil {
		return nil, httpx.Internalf(err, "load client projects")
	}
	for i := range projects {
		projects[i].IsOwner = true
	}
	return projects, nil
}

// ── Updates ─────────────────────────────────────────────────────────────────

type UpdateRequest struct {
	Title            *string          `json:"title"`
	Summary          *string          `json:"summary"`
	Description      *string          `json:"description"`
	CategorySlug     *string          `json:"category_slug"`
	RequiredSkills   []string         `json:"required_skills"`
	OptionalSkills   []string         `json:"optional_skills"`
	Features         []FeatureRequest `json:"features"`
	BudgetType       *string          `json:"budget_type"`
	BudgetMinMinor   *int64           `json:"budget_min_minor"`
	BudgetMaxMinor   *int64           `json:"budget_max_minor"`
	Currency         *string          `json:"currency"`
	DurationDays     *int             `json:"duration_days"`
	Deadline         *string          `json:"deadline"`
	Starts           *string          `json:"starts"`
	ExperienceWanted *string          `json:"experience_wanted"`
	OverlapFromUTC   *int             `json:"overlap_from_utc"`
	OverlapToUTC     *int             `json:"overlap_to_utc"`
	Visibility       *string          `json:"visibility"`
}

func (s *Service) Update(ctx context.Context, id *security.Identity, projectID uuid.UUID, in UpdateRequest) (*Project, error) {
	if err := s.requireClient(id); err != nil {
		return nil, err
	}
	if err := s.requireOwner(ctx, id, projectID); err != nil {
		return nil, err
	}

	existing, err := s.store.ByID(ctx, projectID)
	if err != nil {
		return nil, s.mapStoreError(err)
	}
	// Once someone is working on it, the brief is part of a contract and
	// cannot be rewritten unilaterally.
	if existing.Status == StatusInProgress || existing.Status == StatusCompleted {
		e := *httpx.ErrConflict
		e.Code = "project_locked"
		e.Message = "This project is already under contract, so its brief can't be changed. Talk to the developer in the workspace."
		return nil, &e
	}

	v := validate.New()
	update := UpdateInput{}

	if in.Title != nil {
		v.Length("title", "Project title", *in.Title, 8, 140)
		trimmed := strings.TrimSpace(*in.Title)
		update.Title = &trimmed
	}
	if in.Summary != nil {
		v.Length("summary", "Summary", *in.Summary, 0, 300)
		trimmed := strings.TrimSpace(*in.Summary)
		update.Summary = &trimmed
	}
	if in.Description != nil {
		v.Length("description", "Project description", *in.Description, 40, 20000)
		trimmed := strings.TrimSpace(*in.Description)
		update.Description = &trimmed
	}
	if in.BudgetType != nil {
		value := v.OneOf("budget_type", "Budget type", *in.BudgetType, "fixed", "range", "hourly")
		update.BudgetType = &value
	}
	if in.Currency != nil {
		value := v.Currency("currency", *in.Currency)
		update.Currency = &value
	}
	if in.Visibility != nil {
		value := v.OneOf("visibility", "Visibility", *in.Visibility, "public", "invite_only", "private")
		update.Visibility = &value
	}
	if in.BudgetMinMinor != nil {
		v.MoneyMinor("budget_min_minor", "Minimum budget", *in.BudgetMinMinor, 1000, 10_000_000_00)
		update.BudgetMinMinor = in.BudgetMinMinor
	}
	if in.BudgetMaxMinor != nil {
		v.MoneyMinor("budget_max_minor", "Maximum budget", *in.BudgetMaxMinor, 1000, 10_000_000_00)
		update.BudgetMaxMinor = in.BudgetMaxMinor
	}
	if in.DurationDays != nil {
		v.IntRange("duration_days", "Duration", *in.DurationDays, 1, 1095)
		update.DurationDays = in.DurationDays
	}
	if in.Starts != nil {
		value := v.OneOf("starts", "Start time", *in.Starts,
			"immediately", "within_week", "within_month", "flexible")
		update.Starts = &value
	}
	if in.ExperienceWanted != nil {
		value := v.OneOf("experience_wanted", "Experience wanted", *in.ExperienceWanted,
			"any", "junior", "mid", "senior", "lead")
		update.ExperienceWanted = &value
	}
	if in.OverlapFromUTC != nil {
		v.IntRange("overlap_from_utc", "Overlap start", *in.OverlapFromUTC, -12, 14)
		update.OverlapFromUTC = in.OverlapFromUTC
	}
	if in.OverlapToUTC != nil {
		v.IntRange("overlap_to_utc", "Overlap end", *in.OverlapToUTC, -12, 14)
		update.OverlapToUTC = in.OverlapToUTC
	}
	if in.Deadline != nil && *in.Deadline != "" {
		parsed, err := time.Parse("2006-01-02", *in.Deadline)
		if err != nil {
			v.Add("deadline", "Use the format YYYY-MM-DD.")
		} else {
			update.Deadline = &parsed
		}
	}
	if in.CategorySlug != nil {
		categoryID, err := s.taxonomy.CategoryIDBySlug(ctx, strings.TrimSpace(*in.CategorySlug))
		if err != nil {
			v.Add("category_slug", "That isn't one of the available categories.")
		} else {
			update.CategoryID = &categoryID
		}
	}
	if in.RequiredSkills != nil || in.OptionalSkills != nil {
		if len(in.RequiredSkills) > 15 {
			v.Add("required_skills", "List up to 15 required technologies.")
		}
		requiredIDs, unknown, err := s.taxonomy.ResolveSkillIDs(ctx, in.RequiredSkills)
		if err != nil {
			return nil, httpx.Internalf(err, "resolve required skills")
		}
		if len(unknown) > 0 {
			v.Addf("required_skills", "We don't recognise: %s.", strings.Join(unknown, ", "))
		}
		optionalIDs, unknown, err := s.taxonomy.ResolveSkillIDs(ctx, in.OptionalSkills)
		if err != nil {
			return nil, httpx.Internalf(err, "resolve optional skills")
		}
		if len(unknown) > 0 {
			v.Addf("optional_skills", "We don't recognise: %s.", strings.Join(unknown, ", "))
		}
		update.RequiredSkills = requiredIDs
		update.OptionalSkills = optionalIDs
		update.ReplaceSkills = true
	}
	if in.Features != nil {
		for i, f := range in.Features {
			if strings.TrimSpace(f.Title) == "" {
				v.Addf(fmt.Sprintf("features.%d.title", i), "Describe the feature.")
			}
		}
		features := make([]NewFeature, 0, len(in.Features))
		for _, f := range in.Features {
			features = append(features, NewFeature{
				Title: strings.TrimSpace(f.Title), Detail: strings.TrimSpace(f.Detail),
				Required: f.Required, Origin: "client",
			})
		}
		update.Features = features
		update.ReplaceFeatures = true
	}

	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	if err := s.store.Update(ctx, projectID, update); err != nil {
		return nil, httpx.Internalf(err, "update project")
	}

	// The requirements changed, so every cached score for this project is
	// stale. Dropping them is cheaper and more honest than recomputing eagerly.
	if update.ReplaceSkills || update.CategoryID != nil {
		_ = s.matching.InvalidateForProject(context.WithoutCancel(ctx), projectID)
	}
	return s.ownProject(ctx, id, projectID)
}

// Cancel closes a brief. Proposals are left in place so developers can see what
// happened rather than finding the project simply gone.
func (s *Service) Cancel(ctx context.Context, id *security.Identity, projectID uuid.UUID, reason string) error {
	if err := s.requireClient(id); err != nil {
		return err
	}
	if err := s.requireOwner(ctx, id, projectID); err != nil {
		return err
	}

	if _, err := s.store.Transition(ctx, projectID, StatusCancelled); err != nil {
		if errors.Is(err, ErrBadTransition) {
			e := *httpx.ErrConflict
			e.Code = "cannot_cancel"
			e.Message = "This project can't be cancelled from its current state."
			return e.Wrap(err)
		}
		return httpx.Internalf(err, "cancel project")
	}
	s.audit.RecordRequest(ctx, audit.Entry{
		Action: audit.ActionProjectCancelled, SubjectType: "project", SubjectID: &projectID,
		Detail: reason,
	})
	return nil
}

// ── Helpers ─────────────────────────────────────────────────────────────────

func (s *Service) load(ctx context.Context, slugOrID string) (*Project, error) {
	if id, err := uuid.Parse(slugOrID); err == nil {
		project, err := s.store.ByID(ctx, id)
		return project, s.mapStoreError(err)
	}
	project, err := s.store.BySlug(ctx, slugOrID)
	return project, s.mapStoreError(err)
}

func (s *Service) ownProject(ctx context.Context, id *security.Identity, projectID uuid.UUID) (*Project, error) {
	project, err := s.store.ByID(ctx, projectID)
	if err != nil {
		return nil, s.mapStoreError(err)
	}
	project.IsOwner = true
	return project, nil
}

// requireOwner is the authorisation gate for every write.
//
// It resolves ownership from the database rather than from anything in the
// request, which is what makes swapping one project id for another useless.
func (s *Service) requireOwner(ctx context.Context, id *security.Identity, projectID uuid.UUID) error {
	owner, _, err := s.store.OwnerOf(ctx, projectID)
	if errors.Is(err, ErrNotFound) {
		return httpx.NotFoundf("project %s does not exist", projectID)
	}
	if err != nil {
		return httpx.Internalf(err, "resolve project owner")
	}
	if owner != id.UserID {
		s.audit.Denial(ctx, "project", &projectID, "caller does not own this project")
		// A 404 rather than a 403: confirming that someone else's project
		// exists is itself a disclosure.
		return httpx.NotFoundf("project %s does not belong to user %s", projectID, id.UserID)
	}
	return nil
}

func (s *Service) requireClient(id *security.Identity) error {
	if !id.Authenticated() {
		return httpx.ErrUnauthenticated
	}
	if err := security.RequireRole(id, security.RoleClient); err != nil {
		return httpx.ErrForbidden.Wrap(err)
	}
	return nil
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

func (s *Service) mapStoreError(err error) error {
	switch {
	case err == nil:
		return nil
	case errors.Is(err, ErrNotFound):
		return httpx.ErrNotFound.Wrap(err)
	case errors.Is(err, ErrBadTransition):
		return httpx.ErrConflict.Wrap(err)
	}
	return httpx.Internalf(err, "project store")
}

// Store exposes the store to the modules that read projects (proposals,
// contracts, search).
func (s *Service) Store() *Store { return s.store }

func isKnownStatus(status string) bool {
	_, ok := canTransition[status]
	return ok
}

func defaultTo(v, fallback string) string {
	if strings.TrimSpace(v) == "" {
		return fallback
	}
	return v
}
