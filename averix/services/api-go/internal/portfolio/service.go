package portfolio

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/files"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/imaging"
	"github.com/averix/api/internal/platform/logx"
	"github.com/averix/api/internal/platform/urlguard"
	"github.com/averix/api/internal/platform/validate"
	"github.com/averix/api/internal/preview"
	"github.com/averix/api/internal/security"
)

// Taxonomy is the reference data this module reads. An interface so portfolio
// depends on the shape it needs rather than on the taxonomy package.
type Taxonomy interface {
	ResolveSkillIDs(ctx context.Context, slugs []string) ([]uuid.UUID, []string, error)
	CategoryIDBySlug(ctx context.Context, slug string) (uuid.UUID, error)
}

type Service struct {
	store       *Store
	screenshots *Screenshots
	taxonomy    Taxonomy
	prober      *preview.Prober
	audit       *audit.Recorder
	// urlOptions is strict in production and permissive only in development,
	// where previewing http://localhost:3000 is a real workflow.
	urlOptions urlguard.Options
}

func NewService(store *Store, screenshots *Screenshots, taxonomy Taxonomy,
	prober *preview.Prober, rec *audit.Recorder, devMode bool) *Service {

	options := urlguard.DefaultOptions()
	if devMode {
		options = urlguard.DevelopmentOptions()
	}
	return &Service{
		store: store, screenshots: screenshots, taxonomy: taxonomy,
		prober: prober, audit: rec, urlOptions: options,
	}
}

// Audit actions this module records. A portfolio item is public claim-making,
// so who published what and when is worth keeping.
const (
	actionCreated   = "portfolio.created"
	actionUpdated   = "portfolio.updated"
	actionPublished = "portfolio.published"
	actionDeleted   = "portfolio.deleted"
)

// ── Requests ────────────────────────────────────────────────────────────────

// SaveRequest is the create and update body. Every field is a pointer on
// update so "not sent" and "cleared" are different things; create reads the
// same struct with the required fields checked.
type SaveRequest struct {
	Title            string   `json:"title"`
	ShortDescription string   `json:"short_description"`
	Description      string   `json:"description"`
	CategorySlug     string   `json:"category_slug"`
	DeveloperRole    string   `json:"developer_role"`
	Technologies     []string `json:"technologies"`
	ProjectURL       string   `json:"project_url"`
	RepositoryURL    string   `json:"repository_url"`
	CompletedOn      string   `json:"completed_on"`
	DurationDays     *int     `json:"duration_days"`
	ValueMinor       *int64   `json:"value_minor"`
	Currency         string   `json:"currency"`
	ValueVisibility  string   `json:"value_visibility"`
	DemoStatus       string   `json:"demo_status"`
}

// MaxTechnologies per item. A portfolio entry that lists twenty technologies
// tells a client nothing; the five or six that mattered do.
const MaxTechnologies = 10

// MaxLinks per item.
const MaxLinks = 6

var valueVisibilities = []string{"public", "range", "hidden", "private"}

var demoStatuses = []string{
	DemoNone, DemoLive, DemoStaging, DemoOffline, DemoPrivateRepo, DemoNDA,
}

type validated struct {
	title            string
	shortDescription string
	description      string
	developerRole    string
	categoryID       *uuid.UUID
	skillIDs         []uuid.UUID
	projectURL       string
	projectHost      string
	repositoryURL    string
	completedOn      *time.Time
	durationDays     *int
	valueMinor       *int64
	currency         string
	valueVisibility  string
	demoStatus       string
	// Which fields the request actually carried, so an update leaves the rest
	// alone.
	sent map[string]bool
}

func (s *Service) validate(ctx context.Context, in SaveRequest, creating bool) (*validated, error) {
	v := validate.New()
	out := &validated{sent: map[string]bool{}}

	title := strings.TrimSpace(in.Title)
	if creating || title != "" {
		v.Required("title", "A title", title)
		v.Length("title", "The title", title, 3, 120)
		v.NoControlChars("title", "The title", title)
		out.title = title
		out.sent["title"] = true
	}

	if short := strings.TrimSpace(in.ShortDescription); short != "" {
		v.Length("short_description", "The one-line summary", short, 0, 200)
		out.shortDescription = short
		out.sent["short_description"] = true
	}

	if desc := strings.TrimSpace(in.Description); desc != "" {
		v.Length("description", "The description", desc, 0, 8000)
		if validate.LooksLikeSpam(desc) {
			v.Add("description", "This description doesn't read like a description of your work. Please rewrite it.")
		}
		out.description = desc
		out.sent["description"] = true
	}

	if role := strings.TrimSpace(in.DeveloperRole); role != "" {
		v.Length("developer_role", "Your role", role, 0, 120)
		out.developerRole = role
		out.sent["developer_role"] = true
	}

	if slug := strings.TrimSpace(in.CategorySlug); slug != "" {
		categoryID, err := s.taxonomy.CategoryIDBySlug(ctx, slug)
		if err != nil {
			v.Add("category_slug", "That category doesn't exist. Please choose one from the list.")
		} else {
			out.categoryID = &categoryID
			out.sent["category_slug"] = true
		}
	}

	if in.Technologies != nil {
		if len(in.Technologies) > MaxTechnologies {
			v.Addf("technologies", "Choose up to %d technologies — the ones that mattered on this project.",
				MaxTechnologies)
		} else {
			ids, unknown, err := s.taxonomy.ResolveSkillIDs(ctx, in.Technologies)
			if err != nil {
				return nil, httpx.Internalf(err, "resolve technologies")
			}
			if len(unknown) > 0 {
				v.Addf("technologies", "We don't recognise %s. Please pick from the list.",
					strings.Join(unknown, ", "))
			}
			out.skillIDs = ids
			out.sent["technologies"] = true
		}
	}

	// The two URLs go through the same guard as everything else a visitor
	// might click: scheme allow-list, no internal addresses, no javascript:.
	if raw := strings.TrimSpace(in.ProjectURL); raw != "" {
		result, err := urlguard.Normalise(raw, s.urlOptions)
		if err != nil {
			v.Add("project_url", urlMessage(err))
		} else {
			out.projectURL = result.URL
			out.projectHost = result.Host
			out.sent["project_url"] = true
		}
	}

	if raw := strings.TrimSpace(in.RepositoryURL); raw != "" {
		result, err := urlguard.Normalise(raw, s.urlOptions)
		if err != nil {
			v.Add("repository_url", urlMessage(err))
		} else {
			out.repositoryURL = result.URL
			out.sent["repository_url"] = true
		}
	}

	if raw := strings.TrimSpace(in.CompletedOn); raw != "" {
		when, err := time.Parse("2006-01-02", raw)
		switch {
		case err != nil:
			v.Add("completed_on", "Use a date in the form 2024-08-31.")
		case when.After(time.Now().AddDate(0, 0, 1)):
			v.Add("completed_on", "A completion date can't be in the future.")
		case when.Year() < 1990:
			v.Add("completed_on", "That date looks too far in the past.")
		default:
			out.completedOn = &when
			out.sent["completed_on"] = true
		}
	}

	if in.DurationDays != nil {
		v.IntRange("duration_days", "The duration", *in.DurationDays, 1, 3650)
		out.durationDays = in.DurationDays
		out.sent["duration_days"] = true
	}

	if in.ValueMinor != nil {
		v.MoneyMinor("value_minor", "The project value", *in.ValueMinor, 0, 100_000_000_00)
		out.valueMinor = in.ValueMinor
		out.sent["value_minor"] = true
	}
	if currency := strings.TrimSpace(in.Currency); currency != "" {
		out.currency = v.Currency("currency", currency)
		out.sent["currency"] = true
	}
	if visibility := strings.TrimSpace(in.ValueVisibility); visibility != "" {
		out.valueVisibility = v.OneOf("value_visibility", "The value visibility",
			visibility, valueVisibilities...)
		out.sent["value_visibility"] = true
	} else if creating {
		// Hidden by default. A developer has to choose to publish a figure;
		// nothing about their earnings is public by accident.
		out.valueVisibility = "hidden"
		out.sent["value_visibility"] = true
	}

	if status := strings.TrimSpace(in.DemoStatus); status != "" {
		out.demoStatus = v.OneOf("demo_status", "The demo status", status, demoStatuses...)
		out.sent["demo_status"] = true
	} else if creating {
		out.demoStatus = DemoNone
		out.sent["demo_status"] = true
	}

	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}
	return out, nil
}

// urlMessage turns a rejection into something a developer can act on without
// leaking why our network layer refused it.
func urlMessage(err error) string {
	var rejection *urlguard.Rejection
	if errors.As(err, &rejection) {
		return rejection.Human()
	}
	return "That link isn't valid. Please check it and try again."
}

// ── Writes ──────────────────────────────────────────────────────────────────

func (s *Service) Create(ctx context.Context, id *security.Identity, in SaveRequest) (*Project, error) {
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return nil, forbid(err)
	}

	v, err := s.validate(ctx, in, true)
	if err != nil {
		return nil, err
	}

	projectID, err := s.store.Create(ctx, New{
		DeveloperID:      id.UserID,
		Title:            v.title,
		ShortDescription: v.shortDescription,
		Description:      v.description,
		CategoryID:       v.categoryID,
		DeveloperRole:    v.developerRole,
		ProjectURL:       v.projectURL,
		ProjectHost:      v.projectHost,
		RepositoryURL:    v.repositoryURL,
		CompletedOn:      v.completedOn,
		DurationDays:     v.durationDays,
		ValueMinor:       v.valueMinor,
		Currency:         v.currency,
		ValueVisibility:  v.valueVisibility,
		DemoStatus:       v.demoStatus,
		SkillIDs:         v.skillIDs,
	})
	if errors.Is(err, ErrTooMany) {
		e := *httpx.ErrConflict
		e.Code = "portfolio_full"
		e.Message = fmt.Sprintf(
			"Your portfolio already has %d projects. Remove one to add another.", MaxProjects)
		return nil, &e
	}
	if err != nil {
		return nil, httpx.Internalf(err, "create portfolio project")
	}

	s.audit.RecordRequest(ctx, audit.Entry{
		Action: actionCreated, SubjectType: "portfolio_project", SubjectID: &projectID,
	})
	return s.owned(ctx, projectID, id.UserID)
}

func (s *Service) Update(ctx context.Context, id *security.Identity, projectID uuid.UUID, in SaveRequest) (*Project, error) {
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return nil, forbid(err)
	}

	existing, err := s.store.ByID(ctx, projectID)
	if err != nil {
		return nil, notFound(err, projectID)
	}
	// Not Forbidden: a developer probing ids should not learn which ones exist.
	if existing.DeveloperID != id.UserID {
		s.audit.Denial(ctx, "portfolio_project", &projectID, "not the owner")
		return nil, httpx.NotFoundf("portfolio project %s does not exist", projectID)
	}

	v, err := s.validate(ctx, in, false)
	if err != nil {
		return nil, err
	}

	update := Update{SkillIDs: v.skillIDs, ReplaceSkills: v.sent["technologies"]}
	if v.sent["title"] {
		update.Title = &v.title
	}
	if v.sent["short_description"] {
		update.ShortDescription = &v.shortDescription
	}
	if v.sent["description"] {
		update.Description = &v.description
	}
	if v.sent["developer_role"] {
		update.DeveloperRole = &v.developerRole
	}
	if v.sent["category_slug"] {
		update.CategoryID = v.categoryID
	}
	if v.sent["project_url"] {
		update.ProjectURL = &v.projectURL
		update.ProjectHost = &v.projectHost
		// The stored verdict describes the old address, so it is discarded
		// rather than carried over to a different site.
		update.ResetEmbeddable = v.projectURL != existing.ProjectURL
	}
	if v.sent["repository_url"] {
		update.RepositoryURL = &v.repositoryURL
	}
	if v.sent["completed_on"] {
		update.CompletedOn = v.completedOn
	}
	if v.sent["duration_days"] {
		update.DurationDays = v.durationDays
	}
	if v.sent["value_minor"] {
		update.ValueMinor = v.valueMinor
	}
	if v.sent["currency"] {
		update.Currency = &v.currency
	}
	if v.sent["value_visibility"] {
		update.ValueVisibility = &v.valueVisibility
	}
	if v.sent["demo_status"] {
		update.DemoStatus = &v.demoStatus
	}

	if err := s.store.Update(ctx, projectID, id.UserID, update); err != nil {
		if errors.Is(err, ErrNotFound) {
			return nil, httpx.NotFoundf("portfolio project %s does not exist", projectID)
		}
		return nil, httpx.Internalf(err, "update portfolio project")
	}

	s.audit.RecordRequest(ctx, audit.Entry{
		Action: actionUpdated, SubjectType: "portfolio_project", SubjectID: &projectID,
	})
	return s.owned(ctx, projectID, id.UserID)
}

// SetPublished publishes or unpublishes an item.
//
// Publishing has a bar: an empty card on a public profile costs the developer
// credibility, so the item has to say what the work was and show or link to
// something.
func (s *Service) SetPublished(ctx context.Context, id *security.Identity,
	projectID uuid.UUID, published bool) (*Project, error) {

	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return nil, forbid(err)
	}

	project, err := s.store.ByID(ctx, projectID)
	if err != nil {
		return nil, notFound(err, projectID)
	}
	if project.DeveloperID != id.UserID {
		s.audit.Denial(ctx, "portfolio_project", &projectID, "not the owner")
		return nil, httpx.NotFoundf("portfolio project %s does not exist", projectID)
	}

	if published {
		if fields := publishGaps(project); len(fields) > 0 {
			return nil, httpx.Validation(fields)
		}
	}

	if err := s.store.Update(ctx, projectID, id.UserID, Update{IsPublished: &published}); err != nil {
		return nil, httpx.Internalf(err, "publish portfolio project")
	}
	if published {
		s.audit.RecordRequest(ctx, audit.Entry{
			Action: actionPublished, SubjectType: "portfolio_project", SubjectID: &projectID,
		})
	}
	return s.owned(ctx, projectID, id.UserID)
}

func publishGaps(p *Project) map[string]string {
	gaps := map[string]string{}
	if len([]rune(p.Description)) < 80 && len([]rune(p.ShortDescription)) < 80 {
		gaps["description"] = "Add a description of at least 80 characters before publishing — clients read this first."
	}
	if len(p.Skills) == 0 {
		gaps["technologies"] = "Add at least one technology so this project can be matched to relevant work."
	}
	if len(p.Images) == 0 && p.ProjectURL == "" && p.RepositoryURL == "" {
		gaps["images"] = "Add a screenshot, a live link or a repository link so there's something to show."
	}
	return gaps
}

func (s *Service) Delete(ctx context.Context, id *security.Identity, projectID uuid.UUID) error {
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return forbid(err)
	}

	// The images are collected first: once the row is gone the derivative keys
	// are unreachable, and the objects would be paid for forever.
	project, err := s.store.ByID(ctx, projectID)
	if err != nil {
		return notFound(err, projectID)
	}
	if project.DeveloperID != id.UserID {
		s.audit.Denial(ctx, "portfolio_project", &projectID, "not the owner")
		return httpx.NotFoundf("portfolio project %s does not exist", projectID)
	}
	for _, image := range project.Images {
		if err := s.screenshots.Remove(ctx, image.ID, id.UserID); err != nil &&
			!errors.Is(err, ErrNotFound) {
			return httpx.Internalf(err, "remove portfolio image")
		}
	}

	if err := s.store.Delete(ctx, projectID, id.UserID); err != nil {
		if errors.Is(err, ErrNotFound) {
			return httpx.NotFoundf("portfolio project %s does not exist", projectID)
		}
		return httpx.Internalf(err, "delete portfolio project")
	}
	s.audit.RecordRequest(ctx, audit.Entry{
		Action: actionDeleted, SubjectType: "portfolio_project", SubjectID: &projectID,
	})
	return nil
}

func (s *Service) Reorder(ctx context.Context, id *security.Identity, ordered []string) error {
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return forbid(err)
	}
	ids, err := parseIDs(ordered, "projects")
	if err != nil {
		return err
	}
	if err := s.store.Reorder(ctx, id.UserID, ids); err != nil {
		return httpx.Internalf(err, "reorder portfolio")
	}
	return nil
}

// ── Images ──────────────────────────────────────────────────────────────────

func (s *Service) AddImage(ctx context.Context, id *security.Identity, in ScreenshotInput) (*Image, error) {
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return nil, forbid(err)
	}
	in.DeveloperID = id.UserID

	image, err := s.screenshots.Add(ctx, in)
	switch {
	case errors.Is(err, ErrNotFound):
		return nil, httpx.NotFoundf("portfolio project %s does not exist", in.ProjectID)
	case errors.Is(err, ErrTooManyImages):
		e := *httpx.ErrConflict
		e.Code = "gallery_full"
		e.Message = fmt.Sprintf("This project already has %d images.", MaxImages)
		return nil, &e
	case err != nil:
		return nil, imageError(err)
	}
	return image, nil
}

func (s *Service) RemoveImage(ctx context.Context, id *security.Identity, imageID uuid.UUID) error {
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return forbid(err)
	}
	if err := s.screenshots.Remove(ctx, imageID, id.UserID); err != nil {
		if errors.Is(err, ErrNotFound) {
			return httpx.NotFoundf("image %s does not exist", imageID)
		}
		return httpx.Internalf(err, "remove portfolio image")
	}
	return nil
}

func (s *Service) ReorderImages(ctx context.Context, id *security.Identity,
	projectID uuid.UUID, ordered []string) error {

	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return forbid(err)
	}
	ids, err := parseIDs(ordered, "images")
	if err != nil {
		return err
	}
	if err := s.store.ReorderImages(ctx, projectID, id.UserID, ids); err != nil {
		if errors.Is(err, ErrNotFound) {
			return httpx.NotFoundf("portfolio project %s does not exist", projectID)
		}
		return httpx.Internalf(err, "reorder images")
	}
	return nil
}

// SetCover chooses which gallery image is the cover.
func (s *Service) SetCover(ctx context.Context, id *security.Identity,
	projectID, imageID uuid.UUID) (*Project, error) {

	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return nil, forbid(err)
	}

	project, err := s.store.ByID(ctx, projectID)
	if err != nil {
		return nil, notFound(err, projectID)
	}
	if project.DeveloperID != id.UserID {
		s.audit.Denial(ctx, "portfolio_project", &projectID, "not the owner")
		return nil, httpx.NotFoundf("portfolio project %s does not exist", projectID)
	}

	var fileID *uuid.UUID
	for _, image := range project.Images {
		if image.ID == imageID {
			chosen := image.FileID
			fileID = &chosen
			break
		}
	}
	if fileID == nil {
		return nil, httpx.Validation(map[string]string{
			"image_id": "That image isn't part of this project.",
		})
	}

	if err := s.store.Update(ctx, projectID, id.UserID, Update{CoverFileID: fileID}); err != nil {
		return nil, httpx.Internalf(err, "set cover")
	}
	return s.owned(ctx, projectID, id.UserID)
}

// ── Links ───────────────────────────────────────────────────────────────────

type LinkRequest struct {
	Label string `json:"label"`
	URL   string `json:"url"`
	Kind  string `json:"kind"`
}

func (s *Service) AddLink(ctx context.Context, id *security.Identity,
	projectID uuid.UUID, in LinkRequest) (*Link, error) {

	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return nil, forbid(err)
	}

	v := validate.New()
	label := strings.TrimSpace(in.Label)
	v.Required("label", "A label", label)
	v.Length("label", "The label", label, 2, 40)
	v.NoControlChars("label", "The label", label)
	kind := in.Kind
	if strings.TrimSpace(kind) == "" {
		kind = LinkOther
	}
	kind = v.OneOf("kind", "The link type", kind, LinkLive, LinkRepository,
		LinkCaseStudy, LinkAppStore, LinkPlayStore, LinkArticle, LinkOther)

	var normalised urlguard.Result
	if raw := strings.TrimSpace(in.URL); raw == "" {
		v.Add("url", "Add the address this link should open.")
	} else {
		result, err := urlguard.Normalise(raw, s.urlOptions)
		if err != nil {
			v.Add("url", urlMessage(err))
		} else {
			normalised = result
		}
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	existing, err := s.store.ByID(ctx, projectID)
	if err != nil {
		return nil, notFound(err, projectID)
	}
	if existing.DeveloperID != id.UserID {
		s.audit.Denial(ctx, "portfolio_project", &projectID, "not the owner")
		return nil, httpx.NotFoundf("portfolio project %s does not exist", projectID)
	}
	if len(existing.Links) >= MaxLinks {
		e := *httpx.ErrConflict
		e.Code = "links_full"
		e.Message = fmt.Sprintf("This project already has %d links.", MaxLinks)
		return nil, &e
	}

	linkID, err := s.store.AddLink(ctx, projectID, id.UserID, label,
		normalised.URL, normalised.Host, kind)
	if err != nil {
		if errors.Is(err, ErrNotFound) {
			return nil, httpx.NotFoundf("portfolio project %s does not exist", projectID)
		}
		return nil, httpx.Internalf(err, "add portfolio link")
	}
	return &Link{ID: linkID, Label: label, URL: normalised.URL, Host: normalised.Host, Kind: kind}, nil
}

func (s *Service) RemoveLink(ctx context.Context, id *security.Identity, linkID uuid.UUID) error {
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return forbid(err)
	}
	if err := s.store.RemoveLink(ctx, linkID, id.UserID); err != nil {
		if errors.Is(err, ErrNotFound) {
			return httpx.NotFoundf("link %s does not exist", linkID)
		}
		return httpx.Internalf(err, "remove portfolio link")
	}
	return nil
}

// ── Reads ───────────────────────────────────────────────────────────────────

// Mine lists the caller's own portfolio, drafts included.
func (s *Service) Mine(ctx context.Context, id *security.Identity) ([]Card, error) {
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return nil, forbid(err)
	}
	cards, err := s.store.ForDeveloper(ctx, id.UserID, true)
	if err != nil {
		return nil, httpx.Internalf(err, "list portfolio")
	}
	return cards, nil
}

// ForUsername lists what a visitor may see of one developer's portfolio.
func (s *Service) ForUsername(ctx context.Context, id *security.Identity, username string) ([]Card, error) {
	developerID, err := s.store.DeveloperIDByUsername(ctx, username)
	if err != nil {
		return nil, httpx.NotFoundf("developer %s does not exist", username)
	}
	cards, err := s.store.ForDeveloper(ctx, developerID, s.canSeeDrafts(id, developerID))
	if err != nil {
		return nil, httpx.Internalf(err, "list portfolio")
	}
	return cards, nil
}

// View returns one project, by the developer's username and the project slug.
func (s *Service) View(ctx context.Context, id *security.Identity, username, slug string) (*Project, error) {
	project, err := s.store.BySlug(ctx, username, slug)
	if err != nil {
		return nil, httpx.NotFoundf("portfolio project %s does not exist", slug)
	}

	owner := id.Authenticated() && id.UserID == project.DeveloperID
	if !s.visible(project, id, owner) {
		// A draft or hidden item does not exist as far as a visitor is
		// concerned, which is also what stops slug enumeration.
		return nil, httpx.NotFoundf("portfolio project %s does not exist", slug)
	}

	s.redact(project, owner || id.IsModerator())
	project.IsOwner = owner
	if !owner {
		s.store.RecordView(ctx, project.ID)
	}
	return project, nil
}

// Owned returns one of the caller's own projects by id, for the editor.
func (s *Service) Owned(ctx context.Context, id *security.Identity, projectID uuid.UUID) (*Project, error) {
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return nil, forbid(err)
	}
	return s.owned(ctx, projectID, id.UserID)
}

func (s *Service) owned(ctx context.Context, projectID, developerID uuid.UUID) (*Project, error) {
	project, err := s.store.ByID(ctx, projectID)
	if err != nil {
		return nil, notFound(err, projectID)
	}
	if project.DeveloperID != developerID {
		return nil, httpx.NotFoundf("portfolio project %s does not exist", projectID)
	}
	s.redact(project, true)
	project.IsOwner = true
	return project, nil
}

func (s *Service) canSeeDrafts(id *security.Identity, developerID uuid.UUID) bool {
	if !id.Authenticated() {
		return false
	}
	return id.UserID == developerID || id.IsModerator()
}

func (s *Service) visible(p *Project, id *security.Identity, owner bool) bool {
	if owner || id.IsModerator() {
		return true
	}
	return p.IsPublished && p.ModerationState == "approved"
}

// redact applies the price-visibility ladder and withholds what a visitor has
// no business seeing.
//
// The raw figure leaves the server only for the owner: a range or a "Private
// contract" label has to be computed here, because sending the number and
// formatting it in the browser would publish it.
func (s *Service) redact(p *Project, owner bool) {
	if p.ValueMinor != nil {
		p.ValueDisplay = FormatVisibleValue(*p.ValueMinor, p.Currency, p.ValueVisibility)
	}
	if !owner {
		p.ValueMinor = nil
		if p.ValueVisibility != "public" {
			p.Currency = ""
		}
		p.ModerationNote = ""
		// The probe's reason is written for the developer's own settings page
		// ("your site sends X-Frame-Options: DENY"), not for a visitor.
		p.EmbeddableReason = ""
	}
}

// ── Preview ─────────────────────────────────────────────────────────────────

// probeTTL is how long a verdict is trusted. A site that starts refusing
// framing should be noticed within a day, and re-probing on every visit would
// make our server a fetcher for anyone who can open a profile.
const probeTTL = 24 * time.Hour

// Preview returns what the in-app browser needs to open a project's live site.
//
// Nothing here navigates the visitor away: the response describes a frame, and
// the frame's permissions are decided on the server (see preview.BuildFrame).
func (s *Service) Preview(ctx context.Context, id *security.Identity, username, slug string) (*PreviewResponse, error) {
	project, err := s.store.BySlug(ctx, username, slug)
	if err != nil {
		return nil, httpx.NotFoundf("portfolio project %s does not exist", slug)
	}
	owner := id.Authenticated() && id.UserID == project.DeveloperID
	if !s.visible(project, id, owner) {
		return nil, httpx.NotFoundf("portfolio project %s does not exist", slug)
	}
	if project.ProjectURL == "" {
		return nil, httpx.Validation(map[string]string{
			"project_url": "This project doesn't have a live link.",
		})
	}

	result := s.verdictFor(ctx, project, false)
	developer, err := s.store.DeveloperRefFor(ctx, project.DeveloperID)
	if err != nil {
		return nil, httpx.Internalf(err, "load developer")
	}

	response := &PreviewResponse{
		Project: PreviewProject{
			ID: project.ID, Slug: project.Slug, Title: project.Title, Developer: developer,
		},
		Frame: preview.BuildFrame(result),
	}
	// When the site refuses to be framed — which is its right, and is never
	// worked around — the visitor gets the developer's own screenshot and a
	// button that opens the site in a new tab.
	if result.Verdict != preview.Allowed && project.Cover != nil {
		cover := *project.Cover
		response.Fallback = &cover
	}
	if !owner {
		response.Frame.Reason = ""
	}
	return response, nil
}

// CheckURL re-probes the developer's own link on demand, for the editor's
// "check this link" button.
func (s *Service) CheckURL(ctx context.Context, id *security.Identity, projectID uuid.UUID) (*preview.Result, error) {
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return nil, forbid(err)
	}
	project, err := s.store.ByID(ctx, projectID)
	if err != nil {
		return nil, notFound(err, projectID)
	}
	if project.DeveloperID != id.UserID {
		s.audit.Denial(ctx, "portfolio_project", &projectID, "not the owner")
		return nil, httpx.NotFoundf("portfolio project %s does not exist", projectID)
	}
	if project.ProjectURL == "" {
		return nil, httpx.Validation(map[string]string{
			"project_url": "Add a live link first.",
		})
	}
	result := s.verdictFor(ctx, project, true)
	return &result, nil
}

// verdictFor returns the cached verdict, re-probing when it is missing, stale,
// or the caller asked for a fresh answer.
//
// Only the developer's own already-validated, already-stored URL is ever
// probed. There is no endpoint that takes a URL and fetches it, which is what
// keeps this from being an open SSRF proxy.
func (s *Service) verdictFor(ctx context.Context, p *Project, force bool) preview.Result {
	fresh := p.EmbeddableCheckedAt != nil && time.Since(*p.EmbeddableCheckedAt) < probeTTL
	if !force && fresh && preview.Verdict(p.Embeddable) != preview.Unknown {
		return preview.Result{
			URL:       p.ProjectURL,
			Host:      p.ProjectHost,
			Verdict:   preview.Verdict(p.Embeddable),
			Reason:    p.EmbeddableReason,
			Title:     p.Title,
			CheckedAt: *p.EmbeddableCheckedAt,
		}
	}

	result := s.prober.Probe(ctx, p.ProjectURL)
	if err := s.store.SaveEmbeddable(ctx, p.ID, string(result.Verdict), result.Reason); err != nil {
		logWarn(ctx, "portfolio: could not store the preview verdict", err)
	}
	return result
}

// ── Helpers ─────────────────────────────────────────────────────────────────

func parseIDs(raw []string, field string) ([]uuid.UUID, error) {
	ids := make([]uuid.UUID, 0, len(raw))
	for _, value := range raw {
		parsed, err := uuid.Parse(strings.TrimSpace(value))
		if err != nil {
			return nil, httpx.Validation(map[string]string{
				field: "That list contains something that isn't a valid reference.",
			})
		}
		ids = append(ids, parsed)
	}
	return ids, nil
}

func notFound(err error, projectID uuid.UUID) error {
	if errors.Is(err, ErrNotFound) {
		return httpx.NotFoundf("portfolio project %s does not exist", projectID)
	}
	return httpx.Internalf(err, "load portfolio project")
}

func forbid(err error) error {
	e := *httpx.ErrForbidden
	e.Message = "Switch to your developer profile to manage your portfolio."
	return e.Wrap(err)
}

// imageError maps the upload pipeline's failures onto messages a person can
// act on, without describing our internals.
func imageError(err error) error {
	switch {
	case errors.Is(err, ErrImageTooLarge), errors.Is(err, files.ErrTooLarge):
		e := *httpx.ErrPayloadTooLarge
		e.Message = "That image is too large. Please choose one under 10 MB."
		return e.Wrap(err)
	case errors.Is(err, imaging.ErrUnsupportedFormat), errors.Is(err, files.ErrTypeNotAllowed):
		e := *httpx.ErrUnsupportedMedia
		e.Message = "That image format isn't supported. Please use a JPEG, PNG or WebP file."
		return e.Wrap(err)
	case errors.Is(err, imaging.ErrNotAnImage):
		e := *httpx.ErrUnsupportedMedia
		e.Message = "That file isn't an image."
		return e.Wrap(err)
	case errors.Is(err, imaging.ErrDimensions):
		return httpx.Validation(map[string]string{
			"image": "That image is either too small or too large. Please use one between 16 and 12000 pixels on each side.",
		}).Wrap(err)
	case errors.Is(err, imaging.ErrDecompressionBomb):
		e := *httpx.ErrUnsupportedMedia
		e.Message = "That image couldn't be processed."
		return e.Wrap(err)
	case errors.Is(err, files.ErrEmpty):
		return httpx.Validation(map[string]string{"image": "That file is empty."}).Wrap(err)
	}
	return httpx.Internalf(err, "store screenshot")
}

func logWarn(ctx context.Context, message string, err error) {
	logx.From(ctx).Warn(message, "error", err)
}
