package proposals

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/google/uuid"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/matching"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/validate"
	"github.com/averix/api/internal/security"
)

// Settings is the runtime configuration this module reads.
type Settings interface {
	Int(ctx context.Context, key string, fallback int) int
}

// FeeResolver computes the platform fee for an amount. Kept as an interface so
// proposals does not depend on the payments module.
type FeeResolver interface {
	FeeFor(ctx context.Context, amountMinor int64, currency string) (percent float64, feeMinor int64, err error)
}

// Moderator receives content that needs a human look.
type Moderator interface {
	Flag(ctx context.Context, subjectType string, subjectID uuid.UUID, reason string)
}

// Notifier tells the other party something happened.
type Notifier interface {
	ProposalReceived(ctx context.Context, clientID, projectID, proposalID uuid.UUID, developerName string)
	ProposalShortlisted(ctx context.Context, developerID, projectID, proposalID uuid.UUID)
	ProposalDeclined(ctx context.Context, developerID, projectID, proposalID uuid.UUID, reason string)
}

type Service struct {
	store     *Store
	matching  *matching.Store
	audit     *audit.Recorder
	settings  Settings
	fees      FeeResolver
	moderator Moderator
	notifier  Notifier
}

func NewService(store *Store, match *matching.Store, rec *audit.Recorder,
	settings Settings, fees FeeResolver, moderator Moderator, notifier Notifier) *Service {
	return &Service{
		store: store, matching: match, audit: rec, settings: settings,
		fees: fees, moderator: moderator, notifier: notifier,
	}
}

// ── Submission ──────────────────────────────────────────────────────────────

type SubmitRequest struct {
	ProjectID          string             `json:"project_id"`
	AmountMinor        int64              `json:"amount_minor"`
	Currency           string             `json:"currency"`
	DeliveryDays       int                `json:"delivery_days"`
	CoverLetter        string             `json:"cover_letter"`
	Approach           string             `json:"approach"`
	RelevantExperience string             `json:"relevant_experience"`
	Questions          string             `json:"questions"`
	Milestones         []MilestoneRequest `json:"milestones"`
	// Evidence: ids of the developer's own portfolio items and verified
	// contracts.
	PortfolioIDs []string `json:"portfolio_ids"`
	HistoryIDs   []string `json:"history_ids"`
}

type MilestoneRequest struct {
	Title       string `json:"title"`
	Detail      string `json:"detail"`
	AmountMinor int64  `json:"amount_minor"`
	Days        *int   `json:"days"`
}

func (s *Service) Submit(ctx context.Context, id *security.Identity, in SubmitRequest) (*Proposal, error) {
	if err := s.requireDeveloper(id); err != nil {
		return nil, err
	}

	projectID, err := uuid.Parse(strings.TrimSpace(in.ProjectID))
	if err != nil {
		return nil, httpx.Validation(map[string]string{"project_id": "That project reference isn't valid."})
	}

	// A daily cap is what stops one developer carpet-bombing fifty projects.
	// It is deliberately generous: a working developer bidding thoughtfully
	// will not reach it.
	maxPerDay := s.settings.Int(ctx, "proposals.max_per_day", 10)
	sentToday, err := s.store.CountToday(ctx, id.UserID)
	if err != nil {
		return nil, httpx.Internalf(err, "count today's proposals")
	}
	if sentToday >= maxPerDay {
		e := *httpx.ErrRateLimited
		e.Code = "proposal_limit_reached"
		e.Message = fmt.Sprintf(
			"You've sent %d proposals today. Take the time to tailor the next one — the limit resets in 24 hours.",
			sentToday)
		e.RetryAfter = 3600
		return nil, &e
	}

	validated, err := s.validateSubmission(ctx, in)
	if err != nil {
		return nil, err
	}
	validated.ProjectID = projectID
	validated.DeveloperID = id.UserID

	// Evidence must belong to the caller. Filtering rather than trusting the
	// ids is what stops a developer attaching someone else's verified contract
	// as their own.
	portfolioIDs, historyIDs, err := s.resolveEvidence(ctx, id.UserID, in.PortfolioIDs, in.HistoryIDs)
	if err != nil {
		return nil, err
	}
	validated.PortfolioIDs = portfolioIDs
	validated.HistoryIDs = historyIDs

	// The fee is resolved now and stored, so the developer sees what they will
	// actually be paid before they submit.
	if s.fees != nil {
		_, feeMinor, err := s.fees.FeeFor(ctx, validated.AmountMinor, validated.Currency)
		if err == nil {
			validated.FeeMinor = feeMinor
		}
	}

	// The match is snapshotted at submission time.
	if weights, err := s.matching.ActiveWeights(ctx); err == nil {
		projectFacts, pErr := s.matching.ProjectFactsByID(ctx, projectID)
		developerFacts, dErr := s.matching.DeveloperFactsByID(ctx, id.UserID)
		if pErr == nil && dErr == nil {
			score := matching.NewEngine(weights).Score(projectFacts, developerFacts)
			validated.MatchScore = &score
		}
	}

	proposalID, err := s.store.Create(ctx, *validated)
	switch {
	case errors.Is(err, ErrAlreadyProposed):
		e := *httpx.ErrConflict
		e.Code = "already_proposed"
		e.Message = "You've already sent a proposal for this project. Withdraw it first if you want to send a new one."
		return nil, &e
	case errors.Is(err, ErrProjectClosed):
		e := *httpx.ErrConflict
		e.Code = "project_closed"
		e.Message = "This project is no longer accepting proposals."
		return nil, &e
	case errors.Is(err, ErrNotFound):
		return nil, httpx.NotFoundf("project %s does not exist", projectID)
	case err != nil:
		return nil, httpx.Internalf(err, "create proposal")
	}

	// Contact details in a proposal are flagged rather than blocked: a
	// legitimate proposal may cite a GitHub URL, and silently refusing a
	// developer's work with no explanation is worse than a review queue.
	if s.moderator != nil {
		combined := in.CoverLetter + "\n" + in.Approach + "\n" + in.RelevantExperience
		if found := validate.ContactDetails(combined); len(found) > 0 {
			s.moderator.Flag(context.WithoutCancel(ctx), "proposal", proposalID,
				"contains contact details: "+strings.Join(found, ", "))
		}
	}

	parties, err := s.store.PartiesOf(ctx, proposalID)
	if err == nil && s.notifier != nil {
		s.notifier.ProposalReceived(context.WithoutCancel(ctx),
			parties.ClientID, projectID, proposalID, id.Username)
	}

	proposal, err := s.store.ByID(ctx, proposalID)
	if err != nil {
		return nil, httpx.Internalf(err, "load created proposal")
	}
	proposal.IsAuthor = true
	return proposal, nil
}

// validateSubmission enforces the product's minimum standard for a proposal.
func (s *Service) validateSubmission(ctx context.Context, in SubmitRequest) (*New, error) {
	v := validate.New()

	currency := v.Currency("currency", in.Currency)
	v.MoneyMinor("amount_minor", "Your price", in.AmountMinor, 1000, 10_000_000_00)
	v.IntRange("delivery_days", "Delivery time", in.DeliveryDays, 1, 730)

	// The minimum lengths are the product decision. The client shows a live
	// counter for each field, so the requirement is visible before submitting
	// rather than a surprise on the way back.
	minCover := s.settings.Int(ctx, "proposals.min_cover_letter", 120)
	v.Length("cover_letter", "Your message", in.CoverLetter, minCover, 4000)
	v.Length("approach", "Your approach", in.Approach, 120, 4000)
	v.Length("relevant_experience", "Relevant experience", in.RelevantExperience, 60, 3000)
	if in.Questions != "" {
		v.Length("questions", "Your questions", in.Questions, 0, 2000)
	}
	v.NoControlChars("cover_letter", "Your message", in.CoverLetter)
	v.NoControlChars("approach", "Your approach", in.Approach)

	// Length alone is easy to game with a wall of one repeated word.
	for field, label := range map[string]string{
		"cover_letter": "Your message", "approach": "Your approach",
	} {
		text := in.CoverLetter
		if field == "approach" {
			text = in.Approach
		}
		if validate.LooksLikeSpam(text) {
			v.Addf(field, "%s needs to say something specific about this project.", label)
		}
	}

	if len(in.Milestones) > 20 {
		v.Add("milestones", "Twenty milestones is more than a proposal should need.")
	}
	milestones := make([]Milestone, 0, len(in.Milestones))
	var milestoneTotal int64
	for i, m := range in.Milestones {
		field := fmt.Sprintf("milestones.%d", i)
		if strings.TrimSpace(m.Title) == "" {
			v.Addf(field+".title", "Name this milestone.")
		}
		if len(m.Title) > 160 {
			v.Addf(field+".title", "Keep the milestone title under 160 characters.")
		}
		if m.AmountMinor <= 0 {
			v.Addf(field+".amount_minor", "Set an amount for this milestone.")
		}
		if m.Days != nil {
			v.IntRange(field+".days", "Milestone duration", *m.Days, 1, 365)
		}
		milestoneTotal += m.AmountMinor
		milestones = append(milestones, Milestone{
			Position:    i + 1,
			Title:       strings.TrimSpace(m.Title),
			Detail:      strings.TrimSpace(m.Detail),
			AmountMinor: m.AmountMinor,
			Days:        m.Days,
		})
	}
	// Milestones that do not add up to the price would produce a contract
	// nobody agreed to, so the mismatch is refused here rather than reconciled
	// later.
	if len(milestones) > 0 && milestoneTotal != in.AmountMinor {
		v.Addf("milestones", "Your milestones add up to %s but your price is %s.",
			FormatMoney(milestoneTotal, currency), FormatMoney(in.AmountMinor, currency))
	}

	if len(in.PortfolioIDs)+len(in.HistoryIDs) > 6 {
		v.Add("portfolio_ids", "Attach up to six pieces of past work — the most relevant ones.")
	}

	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	return &New{
		AmountMinor:        in.AmountMinor,
		Currency:           currency,
		DeliveryDays:       in.DeliveryDays,
		CoverLetter:        strings.TrimSpace(in.CoverLetter),
		Approach:           strings.TrimSpace(in.Approach),
		RelevantExperience: strings.TrimSpace(in.RelevantExperience),
		Questions:          strings.TrimSpace(in.Questions),
		Milestones:         milestones,
	}, nil
}

func (s *Service) resolveEvidence(ctx context.Context, developerID uuid.UUID,
	rawPortfolio, rawHistory []string) ([]uuid.UUID, []uuid.UUID, error) {

	parse := func(field string, raw []string) ([]uuid.UUID, error) {
		out := make([]uuid.UUID, 0, len(raw))
		for _, s := range raw {
			id, err := uuid.Parse(strings.TrimSpace(s))
			if err != nil {
				return nil, httpx.Validation(map[string]string{
					field: "One of the attached items isn't a valid reference.",
				})
			}
			out = append(out, id)
		}
		return out, nil
	}

	portfolioIDs, err := parse("portfolio_ids", rawPortfolio)
	if err != nil {
		return nil, nil, err
	}
	historyIDs, err := parse("history_ids", rawHistory)
	if err != nil {
		return nil, nil, err
	}

	ownedPortfolio, ownedHistory, err := s.store.OwnedEvidence(ctx, developerID, portfolioIDs, historyIDs)
	if err != nil {
		return nil, nil, httpx.Internalf(err, "verify evidence ownership")
	}
	// A count mismatch means at least one id was not theirs. The response does
	// not say which, so the endpoint cannot be used to discover what exists.
	if len(ownedPortfolio) != len(portfolioIDs) {
		s.audit.Denial(ctx, "portfolio_project", nil,
			"proposal attached portfolio items the developer does not own")
		return nil, nil, httpx.Validation(map[string]string{
			"portfolio_ids": "One of the attached portfolio projects isn't available.",
		})
	}
	if len(ownedHistory) != len(historyIDs) {
		s.audit.Denial(ctx, "completed_project_history", nil,
			"proposal attached verified history the developer does not own")
		return nil, nil, httpx.Validation(map[string]string{
			"history_ids": "One of the attached completed projects isn't available.",
		})
	}
	return ownedPortfolio, ownedHistory, nil
}

// ── Reading ─────────────────────────────────────────────────────────────────

// View returns a proposal to a party to it.
//
// Opening a proposal as the client also marks it viewed, which is what the
// developer's "viewed" indicator reads.
func (s *Service) View(ctx context.Context, id *security.Identity, proposalID uuid.UUID) (*Proposal, error) {
	if !id.Authenticated() {
		return nil, httpx.ErrUnauthenticated
	}

	parties, err := s.store.PartiesOf(ctx, proposalID)
	if errors.Is(err, ErrNotFound) {
		return nil, httpx.NotFoundf("proposal %s does not exist", proposalID)
	}
	if err != nil {
		return nil, httpx.Internalf(err, "resolve proposal parties")
	}

	isClient := id.UserID == parties.ClientID && id.ActiveRole == security.RoleClient
	isDeveloper := id.UserID == parties.DeveloperID && id.ActiveRole == security.RoleDeveloper
	isStaff := id.ActiveRole == security.RoleAdmin || id.ActiveRole == security.RoleModerator

	if !isClient && !isDeveloper && !isStaff {
		s.audit.Denial(ctx, "proposal", &proposalID, "caller is not a party to this proposal")
		// A 404: confirming that a proposal exists tells a competitor that
		// someone else bid.
		return nil, httpx.NotFoundf("proposal %s is not visible to user %s", proposalID, id.UserID)
	}

	proposal, err := s.store.ByID(ctx, proposalID)
	if err != nil {
		return nil, httpx.Internalf(err, "load proposal")
	}
	proposal.IsAuthor = isDeveloper

	if isClient {
		if err := s.store.MarkViewed(context.WithoutCancel(ctx), proposalID); err != nil {
			// Not worth failing the read over.
			_ = err
		}
	}
	if !isClient && !isStaff {
		// The client's private triage note is not the developer's business.
		proposal.ClientNote = ""
	}
	return proposal, nil
}

// ForProject lists the proposals on a client's own project.
func (s *Service) ForProject(ctx context.Context, id *security.Identity,
	projectID uuid.UUID, sort SortOrder, projectOwner uuid.UUID) ([]Card, error) {

	if !id.Authenticated() {
		return nil, httpx.ErrUnauthenticated
	}
	isStaff := id.ActiveRole == security.RoleAdmin || id.ActiveRole == security.RoleModerator
	if id.UserID != projectOwner && !isStaff {
		s.audit.Denial(ctx, "project", &projectID, "caller does not own this project's proposals")
		return nil, httpx.NotFoundf("project %s does not belong to user %s", projectID, id.UserID)
	}
	if sort != "" && !sort.Valid() {
		return nil, httpx.Validation(map[string]string{"sort": "That isn't one of the available orders."})
	}

	cards, err := s.store.ForProject(ctx, projectID, sort, 200)
	if err != nil {
		return nil, httpx.Internalf(err, "list proposals")
	}
	return cards, nil
}

// Mine lists the caller's own proposals.
func (s *Service) Mine(ctx context.Context, id *security.Identity, status string) ([]Proposal, error) {
	if err := s.requireDeveloper(id); err != nil {
		return nil, err
	}
	proposals, err := s.store.ForDeveloper(ctx, id.UserID, status, 100)
	if err != nil {
		return nil, httpx.Internalf(err, "list own proposals")
	}
	for i := range proposals {
		// A developer never sees the client's private note about them.
		proposals[i].ClientNote = ""
	}
	return proposals, nil
}

// ── Client actions ──────────────────────────────────────────────────────────

func (s *Service) Shortlist(ctx context.Context, id *security.Identity, proposalID uuid.UUID,
	shortlisted bool, note string) error {

	parties, err := s.requireClientParty(ctx, id, proposalID)
	if err != nil {
		return err
	}
	if len(note) > 1000 {
		return httpx.Validation(map[string]string{"note": "Keep your note under 1000 characters."})
	}

	if err := s.store.SetShortlisted(ctx, proposalID, shortlisted, strings.TrimSpace(note)); err != nil {
		return httpx.Internalf(err, "shortlist proposal")
	}
	if shortlisted && s.notifier != nil {
		s.notifier.ProposalShortlisted(context.WithoutCancel(ctx),
			parties.DeveloperID, parties.ProjectID, proposalID)
	}
	return nil
}

func (s *Service) Decline(ctx context.Context, id *security.Identity, proposalID uuid.UUID, reason string) error {
	parties, err := s.requireClientParty(ctx, id, proposalID)
	if err != nil {
		return err
	}
	if !Live(parties.Status) {
		e := *httpx.ErrConflict
		e.Code = "cannot_decline"
		e.Message = "This proposal has already been responded to."
		return &e
	}
	if len(reason) > 1000 {
		return httpx.Validation(map[string]string{"reason": "Keep your reason under 1000 characters."})
	}

	if err := s.store.Decline(ctx, proposalID, strings.TrimSpace(reason)); err != nil {
		return httpx.Internalf(err, "decline proposal")
	}
	if s.notifier != nil {
		s.notifier.ProposalDeclined(context.WithoutCancel(ctx),
			parties.DeveloperID, parties.ProjectID, proposalID, reason)
	}
	return nil
}

// Withdraw lets a developer retract their own bid.
func (s *Service) Withdraw(ctx context.Context, id *security.Identity, proposalID uuid.UUID) error {
	if err := s.requireDeveloper(id); err != nil {
		return err
	}
	parties, err := s.store.PartiesOf(ctx, proposalID)
	if errors.Is(err, ErrNotFound) {
		return httpx.NotFoundf("proposal %s does not exist", proposalID)
	}
	if err != nil {
		return httpx.Internalf(err, "resolve proposal parties")
	}
	if parties.DeveloperID != id.UserID {
		s.audit.Denial(ctx, "proposal", &proposalID, "caller is not the author of this proposal")
		return httpx.NotFoundf("proposal %s does not belong to user %s", proposalID, id.UserID)
	}
	if parties.Status == StatusAccepted {
		e := *httpx.ErrConflict
		e.Code = "already_accepted"
		e.Message = "This proposal has been accepted. Talk to the client in the workspace if something has changed."
		return &e
	}

	if err := s.store.Withdraw(ctx, proposalID, id.UserID); err != nil {
		e := *httpx.ErrConflict
		e.Code = "cannot_withdraw"
		e.Message = "This proposal can't be withdrawn in its current state."
		return e.Wrap(err)
	}
	return nil
}

// ── Helpers ─────────────────────────────────────────────────────────────────

// requireClientParty is the authorisation gate for every client action on a
// proposal: the caller must be the client on the project it belongs to.
func (s *Service) requireClientParty(ctx context.Context, id *security.Identity, proposalID uuid.UUID) (Parties, error) {
	if !id.Authenticated() {
		return Parties{}, httpx.ErrUnauthenticated
	}
	if err := security.RequireRole(id, security.RoleClient); err != nil {
		return Parties{}, httpx.ErrForbidden.Wrap(err)
	}

	parties, err := s.store.PartiesOf(ctx, proposalID)
	if errors.Is(err, ErrNotFound) {
		return parties, httpx.NotFoundf("proposal %s does not exist", proposalID)
	}
	if err != nil {
		return parties, httpx.Internalf(err, "resolve proposal parties")
	}
	if parties.ClientID != id.UserID {
		s.audit.Denial(ctx, "proposal", &proposalID, "caller is not the client on this project")
		return parties, httpx.NotFoundf("proposal %s is not on a project owned by %s", proposalID, id.UserID)
	}
	return parties, nil
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

// Store exposes the store to the contracts module, which reads an accepted
// proposal to build a contract.
func (s *Service) Store() *Store { return s.store }
