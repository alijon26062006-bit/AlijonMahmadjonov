package contracts

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
	"github.com/averix/api/internal/platform/urlguard"
	"github.com/averix/api/internal/platform/validate"
	"github.com/averix/api/internal/security"
)

// Proposals is the slice of the proposals module this one needs. An interface
// so contracts does not import proposals, which would make the dependency
// circular once proposals starts linking back to a signed contract.
type Proposals interface {
	AcceptanceFacts(ctx context.Context, proposalID uuid.UUID) (Acceptance, error)
	MarkAccepted(ctx context.Context, proposalID, contractID uuid.UUID) error
	DeclineOthers(ctx context.Context, projectID, acceptedID uuid.UUID, reason string) (int, error)
}

// Acceptance is what a proposal contributes to a contract at signature.
type Acceptance struct {
	ProposalID    uuid.UUID
	ProjectID     uuid.UUID
	ProjectTitle  string
	ProjectStatus string
	ClientID      uuid.UUID
	DeveloperID   uuid.UUID
	Status        string
	AmountMinor   int64
	Currency      string
	DeliveryDays  int
	RevisionLimit int
	Milestones    []NewMilestone
}

// Projects lets the contract move the project's own lifecycle.
type Projects interface {
	Transition(ctx context.Context, projectID uuid.UUID, to string) (string, error)
}

// Settings is the runtime configuration read here.
type Settings interface {
	Int(ctx context.Context, key string, fallback int) int
}

// Funder is the payments module, seen from here.
//
// Deliberately narrow: contracts does not start payments, ask for
// instructions or know what a provider is. It needs two things — whether
// money can move at all in this environment, so a button is not offered when
// it cannot, and a way to say "this milestone was approved, pay the
// developer". Everything else about money lives in the payments module,
// including the endpoint a client funds through.
//
// Nil until a provider exists; every call site checks and says so plainly
// rather than pretending a milestone was funded.
type Funder interface {
	Configured() bool
	// ReleaseMilestone queues the payout for an approved milestone.
	ReleaseMilestone(ctx context.Context, contractID, milestoneID uuid.UUID) error
}

// Notifier tells the other party what happened. Nil until phase 7.
type Notifier interface {
	MilestoneChanged(ctx context.Context, contractID, milestoneID, recipientID uuid.UUID,
		status string)
	ContractSigned(ctx context.Context, contractID, developerID uuid.UUID)
}

// SystemMessenger writes the milestone events into the workspace thread, so
// the conversation is a complete record without duplicating state.
type SystemMessenger interface {
	PostSystem(ctx context.Context, conversationID uuid.UUID, event string,
		milestoneID *uuid.UUID, payload map[string]any) error
}

type Service struct {
	store     *Store
	proposals Proposals
	projects  Projects
	files     *files.Store
	audit     *audit.Recorder
	settings  Settings
	funder    Funder
	notifier  Notifier
	messenger SystemMessenger
	urlOpts   urlguard.Options
}

func NewService(store *Store, proposals Proposals, projects Projects, fileStore *files.Store,
	rec *audit.Recorder, settings Settings, funder Funder, notifier Notifier,
	messenger SystemMessenger, devMode bool) *Service {

	options := urlguard.DefaultOptions()
	if devMode {
		options = urlguard.DevelopmentOptions()
	}
	return &Service{
		store: store, proposals: proposals, projects: projects, files: fileStore,
		audit: rec, settings: settings, funder: funder, notifier: notifier,
		messenger: messenger, urlOpts: options,
	}
}

// AttachFunder wires the payments module in after construction.
//
// Contracts and payments each need the other: a contract asks whether money
// can move, and payments asks a contract what a milestone is worth. Rather
// than merge the two or invent a third module to hold both, the dependency is
// set once at start-up, in the one place that already builds the graph.
func (s *Service) AttachFunder(funder Funder) { s.funder = funder }

// ── Signing ─────────────────────────────────────────────────────────────────

// AcceptRequest is the client's acceptance of a proposal.
type AcceptRequest struct {
	ProposalID string `json:"proposal_id"`
	// How the finished contract may appear on the developer's public profile.
	// The client's default is a range: the developer earns the right to show
	// the work, not the right to publish what the client paid.
	PriceVisibility string `json:"price_visibility"`
	AllowShowcase   *bool  `json:"allow_showcase"`
}

// Accept turns a proposal into a contract.
//
// One transaction's worth of consequence: the contract, its membership, its
// milestones and its workspace thread are written together (see Store.Create),
// then the proposal is marked accepted, the other live proposals are declined
// with a reason, and the project moves to in_progress.
func (s *Service) Accept(ctx context.Context, id *security.Identity, in AcceptRequest) (*Contract, error) {
	if err := security.RequireRole(id, security.RoleClient); err != nil {
		return nil, forbidRole("Switch to your client profile to hire a developer.", err)
	}

	proposalID, err := uuid.Parse(strings.TrimSpace(in.ProposalID))
	if err != nil {
		return nil, httpx.Validation(map[string]string{
			"proposal_id": "That proposal reference isn't valid.",
		})
	}

	facts, err := s.proposals.AcceptanceFacts(ctx, proposalID)
	if err != nil {
		return nil, httpx.NotFoundf("proposal %s does not exist", proposalID)
	}
	// The client of the project is the only one who can hire on it. Answering
	// 404 rather than 403 keeps a stranger from confirming the id exists.
	if facts.ClientID != id.UserID {
		s.audit.Denial(ctx, "proposal", &proposalID, "not the project's client")
		return nil, httpx.NotFoundf("proposal %s does not exist", proposalID)
	}
	if !isLive(facts.Status) {
		e := *httpx.ErrConflict
		e.Code = "proposal_not_open"
		e.Message = "This proposal is no longer open. Ask the developer to send a new one."
		return nil, &e
	}
	if facts.ProjectStatus != "open" {
		e := *httpx.ErrConflict
		e.Code = "project_not_open"
		e.Message = "This project isn't open for hiring. Reopen it first."
		return nil, &e
	}

	visibility := strings.TrimSpace(in.PriceVisibility)
	if visibility == "" {
		visibility = "range"
	}
	v := validate.New()
	visibility = v.OneOf("price_visibility", "The price visibility", visibility,
		"public", "range", "hidden", "private")
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	// The platform fee is ours and is computed here, then frozen on the
	// contract: a later change to the fee schedule must not rewrite what the
	// parties agreed to today.
	feePercent, feeMinor := s.feeFor(ctx, facts.AmountMinor)
	allowShowcase := true
	if in.AllowShowcase != nil {
		allowShowcase = *in.AllowShowcase
	}

	milestones := facts.Milestones
	if len(milestones) == 0 {
		// A proposal without a schedule becomes a single milestone for the
		// whole amount, which is what "fixed price, one delivery" means.
		milestones = []NewMilestone{{
			Position: 1, Title: facts.ProjectTitle, AmountMinor: facts.AmountMinor,
		}}
	}

	var due *time.Time
	if facts.DeliveryDays > 0 {
		when := time.Now().AddDate(0, 0, facts.DeliveryDays)
		due = &when
	}

	contractID, err := s.store.Create(ctx, NewContract{
		ProjectID:       facts.ProjectID,
		ProposalID:      proposalID,
		ClientID:        facts.ClientID,
		DeveloperID:     facts.DeveloperID,
		Title:           facts.ProjectTitle,
		AmountMinor:     facts.AmountMinor,
		Currency:        facts.Currency,
		FeePercent:      feePercent,
		FeeMinor:        feeMinor,
		PayoutMinor:     facts.AmountMinor - feeMinor,
		DeliveryDays:    facts.DeliveryDays,
		DueOn:           due,
		PriceVisibility: visibility,
		Milestones:      milestones,
	})
	if err != nil {
		return nil, httpx.Internalf(err, "create contract")
	}

	if err := s.proposals.MarkAccepted(ctx, proposalID, contractID); err != nil {
		return nil, httpx.Internalf(err, "mark proposal accepted")
	}
	// The other developers are told, with a reason. Leaving a proposal in
	// limbo because the client moved on is how a marketplace loses developers.
	if _, err := s.proposals.DeclineOthers(ctx, facts.ProjectID, proposalID,
		"The client hired another developer for this project."); err != nil {
		logWarn(ctx, "contracts: could not decline the remaining proposals", err)
	}
	if _, err := s.projects.Transition(ctx, facts.ProjectID, "in_progress"); err != nil {
		logWarn(ctx, "contracts: could not move the project to in_progress", err)
	}

	if !allowShowcase {
		if err := s.store.setShowcase(ctx, contractID, false); err != nil {
			logWarn(ctx, "contracts: could not store the showcase preference", err)
		}
	}

	s.audit.RecordRequest(ctx, audit.Entry{
		Action:      audit.ActionProposalAccepted,
		SubjectType: "proposal",
		SubjectID:   &proposalID,
		After: map[string]any{
			"contract_id":  contractID,
			"amount_minor": facts.AmountMinor,
			"currency":     facts.Currency,
			"fee_minor":    feeMinor,
		},
	})
	s.audit.RecordRequest(ctx, audit.Entry{
		Action: audit.ActionContractCreated, SubjectType: "contract", SubjectID: &contractID,
	})

	if s.notifier != nil {
		s.notifier.ContractSigned(ctx, contractID, facts.DeveloperID)
	}
	s.postSystem(ctx, contractID, "contract.signed", nil, map[string]any{
		"reference": "",
	})

	return s.View(ctx, id, contractID)
}

// feeFor computes the platform fee.
//
// Integer arithmetic on minor units throughout: a float percentage of a
// currency amount is how rounding errors become accounting disputes.
func (s *Service) feeFor(ctx context.Context, amountMinor int64) (float64, int64) {
	basisPoints := int64(s.settings.Int(ctx, "platform.fee_basis_points", 1000))
	if basisPoints < 0 {
		basisPoints = 0
	}
	if basisPoints > 3000 {
		basisPoints = 3000
	}
	fee := amountMinor * basisPoints / 10000
	return float64(basisPoints) / 100, fee
}

func isLive(status string) bool {
	switch status {
	case "submitted", "viewed", "shortlisted":
		return true
	}
	return false
}

// ── Reads ───────────────────────────────────────────────────────────────────

// Mine lists the caller's contracts, whichever side they are on.
func (s *Service) Mine(ctx context.Context, id *security.Identity, status string) ([]Card, error) {
	if !id.Authenticated() {
		return nil, httpx.ErrUnauthenticated
	}
	if status != "" && !knownContractStatus(status) {
		return nil, httpx.Validation(map[string]string{"status": "That status isn't one we use."})
	}
	cards, err := s.store.ForUser(ctx, id.UserID, status, 30)
	if err != nil {
		return nil, httpx.Internalf(err, "list contracts")
	}
	return cards, nil
}

// ByReference resolves the human-readable contract number, which is what
// appears in an email or an invoice.
func (s *Service) ByReference(ctx context.Context, id *security.Identity,
	reference string) (*Contract, error) {

	contract, err := s.store.ByReference(ctx, reference)
	if err != nil {
		if errors.Is(err, ErrNotFound) {
			return nil, httpx.NotFoundf("contract %s does not exist", reference)
		}
		return nil, httpx.Internalf(err, "load contract by reference")
	}
	return s.View(ctx, id, contract.ID)
}

// View returns the workspace's contract, with everything the caller is
// entitled to see and nothing else.
func (s *Service) View(ctx context.Context, id *security.Identity, contractID uuid.UUID) (*Contract, error) {
	membership, err := s.store.MembershipOf(ctx, contractID)
	if err != nil {
		return nil, notFound(err, contractID)
	}
	role, err := s.authoriseRead(ctx, id, membership)
	if err != nil {
		return nil, err
	}

	contract, err := s.store.ByID(ctx, contractID)
	if err != nil {
		return nil, notFound(err, contractID)
	}

	deliverables, err := s.store.DeliverablesFor(ctx, contractID)
	if err != nil {
		return nil, httpx.Internalf(err, "load deliverables")
	}
	s.signDeliverables(ctx, deliverables)

	// Deliverables hang off their milestone, and the loose ones off the
	// contract, which is how the workspace renders them.
	byMilestone := map[uuid.UUID][]Deliverable{}
	loose := []Deliverable{}
	for _, d := range deliverables {
		if d.MilestoneID == nil {
			loose = append(loose, d)
			continue
		}
		byMilestone[*d.MilestoneID] = append(byMilestone[*d.MilestoneID], d)
	}
	for i := range contract.Milestones {
		milestone := &contract.Milestones[i]
		milestone.Deliverables = byMilestone[milestone.ID]
		events, err := s.store.EventsFor(ctx, milestone.ID)
		if err != nil {
			return nil, httpx.Internalf(err, "load milestone history")
		}
		milestone.Events = events
	}
	contract.Deliverables = loose

	contract.MyRole = role
	contract.Can = capabilitiesFor(role, contract, membership, id.UserID, s.fundingAvailable())
	s.redact(contract, role)

	if role == roleAdmin {
		// Staff access to a contract is logged every time it is used. The
		// parties are entitled to know an administrator read their agreement.
		s.audit.RecordRequest(ctx, audit.Entry{
			Action: audit.ActionContractViewedByAdmin, SubjectType: "contract",
			SubjectID: &contractID,
		})
	}
	return contract, nil
}

// authoriseRead resolves the caller's position on the contract.
func (s *Service) authoriseRead(ctx context.Context, id *security.Identity, m Membership) (string, error) {
	party := security.Party{
		ClientID:     m.ClientID,
		DeveloperID:  m.DeveloperID,
		Participants: m.Participants,
	}
	if err := security.CanRead(id, "contract", party); err != nil {
		s.audit.Denial(ctx, "contract", &m.ContractID, "caller is not a party")
		// Not 403: whether a contract exists is itself information about two
		// other people's business.
		return "", httpx.NotFoundf("contract %s does not exist", m.ContractID)
	}
	if role, ok := m.Roles[id.UserID]; ok {
		return role, nil
	}
	return roleAdmin, nil
}

// authoriseAction resolves the caller's position for a write, which is
// stricter: a moderator may read a contract but not act on it.
func (s *Service) authoriseAction(ctx context.Context, id *security.Identity, m Membership) (string, error) {
	role, ok := m.Roles[id.UserID]
	if ok {
		return role, nil
	}
	if id.ActiveRole == security.RoleAdmin {
		return roleAdmin, nil
	}
	s.audit.Denial(ctx, "contract", &m.ContractID, "caller is not a party")
	return "", httpx.NotFoundf("contract %s does not exist", m.ContractID)
}

// redact withholds what a caller's position does not entitle them to.
func (s *Service) redact(c *Contract, role string) {
	if role != RoleObserver {
		return
	}
	// An observer is on the workspace to help with the work. What it cost is
	// the two parties' business.
	c.AmountMinor, c.FeeMinor, c.PayoutMinor = nil, nil, nil
	c.ReleasedMinor, c.FundedMinor = nil, nil
	c.Currency, c.FeePercent = "", ""
	for i := range c.Milestones {
		c.Milestones[i].AmountMinor = nil
		c.Milestones[i].Currency = ""
	}
}

// signDeliverables issues a short-lived URL for each stored file.
//
// Signed per request rather than stored: a deliverable is the parties'
// business, and a permanent link would outlive the contract.
func (s *Service) signDeliverables(ctx context.Context, deliverables []Deliverable) {
	for i := range deliverables {
		d := &deliverables[i]
		if d.FileID == nil {
			continue
		}
		file, err := s.files.ByID(ctx, *d.FileID)
		if err != nil {
			continue
		}
		url, err := s.files.SignedURL(ctx, file, 15*time.Minute)
		if err != nil {
			logWarn(ctx, "contracts: could not sign a deliverable URL", err)
			continue
		}
		d.FileURL = url
	}
}

// capabilitiesFor decides which actions the interface should offer.
//
// The same rules the service enforces, computed once for the client so a
// button that would be refused is never drawn.
func capabilitiesFor(role string, c *Contract, m Membership, userID uuid.UUID, funding bool) Can {
	can := Can{
		Message: m.CanMessage[userID],
		Upload:  m.CanUpload[userID],
	}
	settled := c.Status == StatusCompleted || c.Status == StatusCancelled ||
		c.Status == StatusClosed
	if settled || role == RoleObserver || role == roleAdmin {
		return can
	}

	for _, milestone := range c.Milestones {
		switch milestone.Status {
		case MilestoneDraft:
			can.FundMilestone = can.FundMilestone || (role == RoleClient && funding)
		case MilestoneFunded:
			can.StartMilestone = can.StartMilestone || role == RoleDeveloper
		case MilestoneInProgress, MilestoneRevision:
			can.SubmitWork = can.SubmitWork || role == RoleDeveloper
		case MilestoneSubmitted:
			if role == RoleClient {
				can.Approve = true
				can.RequestRevision = milestone.RevisionCount < milestone.RevisionLimit
			}
		case MilestoneApproved:
			can.Release = can.Release || (role == RoleClient && funding)
		}
		if milestone.Status != MilestoneReleased && milestone.Status != MilestoneCancelled {
			can.Dispute = true
		}
	}
	can.Cancel = role == RoleClient && c.ProgressPercent == 0
	can.AddParticipant = role == RoleClient || role == RoleDeveloper
	return can
}

func (s *Service) fundingAvailable() bool {
	return s.funder != nil && s.funder.Configured()
}

// ── Milestone moves ─────────────────────────────────────────────────────────

// MoveRequest is one milestone action from a party.
type MoveRequest struct {
	Note string `json:"note"`
	// For a submission: the hand-overs that come with it.
	Deliverables []DeliverableRequest `json:"deliverables"`
}

// Start moves a funded milestone into progress. The note is optional here —
// "started" needs no explanation.
func (s *Service) Start(ctx context.Context, id *security.Identity, milestoneID uuid.UUID,
	in MoveRequest) (*Milestone, error) {

	return s.move(ctx, id, milestoneID, MilestoneInProgress, MoveRequest{Note: in.Note})
}

// Submit hands work over for review.
func (s *Service) Submit(ctx context.Context, id *security.Identity, milestoneID uuid.UUID,
	in MoveRequest) (*Milestone, error) {

	if strings.TrimSpace(in.Note) == "" && len(in.Deliverables) == 0 {
		return nil, httpx.Validation(map[string]string{
			"note": "Say what you're handing over, or attach the work itself.",
		})
	}
	return s.move(ctx, id, milestoneID, MilestoneSubmitted, in)
}

// RequestRevision sends work back, within the agreed limit.
func (s *Service) RequestRevision(ctx context.Context, id *security.Identity,
	milestoneID uuid.UUID, in MoveRequest) (*Milestone, error) {

	if len(strings.TrimSpace(in.Note)) < 20 {
		return nil, httpx.Validation(map[string]string{
			"note": "Explain what needs changing — at least a sentence. A revision without a reason wastes everyone's time.",
		})
	}
	return s.move(ctx, id, milestoneID, MilestoneRevision, in)
}

// Approve accepts the work. It does not move money: releasing is a separate
// step through the payment provider, and approving is the client saying the
// work is done.
func (s *Service) Approve(ctx context.Context, id *security.Identity, milestoneID uuid.UUID,
	in MoveRequest) (*Milestone, error) {

	return s.move(ctx, id, milestoneID, MilestoneApproved, in)
}

// Dispute freezes a milestone for a human to look at.
func (s *Service) Dispute(ctx context.Context, id *security.Identity, milestoneID uuid.UUID,
	in MoveRequest) (*Milestone, error) {

	if len(strings.TrimSpace(in.Note)) < 30 {
		return nil, httpx.Validation(map[string]string{
			"note": "Describe the problem in a few sentences so we can look into it properly.",
		})
	}
	return s.move(ctx, id, milestoneID, MilestoneDisputed, in)
}

// CancelMilestone cancels work that has not started.
func (s *Service) CancelMilestone(ctx context.Context, id *security.Identity,
	milestoneID uuid.UUID, in MoveRequest) (*Milestone, error) {

	return s.move(ctx, id, milestoneID, MilestoneCancelled, in)
}

// move is the one path every milestone action takes.
//
// It checks, in this order: the milestone exists, the caller is a party, the
// transition is legal, and the caller is the party entitled to make it. Doing
// it in one place is why no endpoint can forget one of the four.
func (s *Service) move(ctx context.Context, id *security.Identity, milestoneID uuid.UUID,
	to string, in MoveRequest) (*Milestone, error) {

	milestone, err := s.store.MilestoneByID(ctx, milestoneID)
	if err != nil {
		return nil, notFoundMilestone(err, milestoneID)
	}
	membership, err := s.store.MembershipOf(ctx, milestone.ContractID)
	if err != nil {
		return nil, notFound(err, milestone.ContractID)
	}
	role, err := s.authoriseAction(ctx, id, membership)
	if err != nil {
		return nil, err
	}

	if !CanTransition(milestone.Status, to) {
		e := *httpx.ErrConflict
		e.Code = "milestone_state"
		e.Message = transitionMessage(milestone.Status, to)
		return nil, e.Wrap(fmt.Errorf("%w: %s -> %s", ErrBadTransition, milestone.Status, to))
	}

	if err := s.entitled(ctx, role, to, milestoneID); err != nil {
		return nil, err
	}

	if to == MilestoneRevision && milestone.RevisionCount >= milestone.RevisionLimit {
		e := *httpx.ErrConflict
		e.Code = "revision_limit_reached"
		e.Message = fmt.Sprintf(
			"You've used the %d revisions agreed for this milestone. If the work still isn't right, open a dispute and we'll look at it.",
			milestone.RevisionLimit)
		return nil, &e
	}

	// Deliverables are attached before the transition, inside the same
	// request, so a submission is never recorded without the work it claims.
	if to == MilestoneSubmitted && len(in.Deliverables) > 0 {
		for _, request := range in.Deliverables {
			if _, err := s.addDeliverable(ctx, id, milestone.ContractID, &milestoneID,
				role, request); err != nil {
				return nil, err
			}
		}
	}

	updated, err := s.store.Transition(ctx, TransitionInput{
		MilestoneID: milestoneID,
		From:        milestone.Status,
		To:          to,
		ActorID:     id.UserID,
		Note:        strings.TrimSpace(in.Note),
	})
	if errors.Is(err, ErrRaced) {
		e := *httpx.ErrConflict
		e.Code = "milestone_changed"
		e.Message = "This milestone was just updated by the other party. Please refresh and try again."
		return nil, &e
	}
	if err != nil {
		return nil, httpx.Internalf(err, "move milestone")
	}

	s.afterMove(ctx, id, membership, milestone, updated, to)
	return updated, nil
}

// entitled checks that the caller's position allows this particular move.
func (s *Service) entitled(ctx context.Context, role, to string, milestoneID uuid.UUID) error {
	wanted := ActorFor(to)
	switch {
	case wanted == "either" && (role == RoleClient || role == RoleDeveloper):
		return nil
	case wanted == role:
		return nil
	case wanted == "system":
		// Released is the payment provider's word, not a party's. Exposing it
		// as an endpoint would let a client mark money paid that never moved.
		e := *httpx.ErrForbidden
		e.Code = "not_your_move"
		e.Message = "This step happens automatically once the payment settles."
		return &e
	}
	s.audit.Denial(ctx, "milestone", &milestoneID,
		fmt.Sprintf("%s attempted a move reserved for %s", role, wanted))
	e := *httpx.ErrForbidden
	e.Code = "not_your_move"
	e.Message = notYourMoveMessage(to)
	return &e
}

// afterMove handles the consequences: the workspace record, the other party's
// notification, accepted deliverables and contract settlement.
func (s *Service) afterMove(ctx context.Context, id *security.Identity, m Membership,
	before, after *Milestone, to string) {

	s.postSystem(ctx, m.ContractID, "milestone."+to, &after.ID, map[string]any{
		"title":    after.Title,
		"position": after.Position,
	})

	if s.notifier != nil {
		recipient := m.DeveloperID
		if id.UserID == m.DeveloperID {
			recipient = m.ClientID
		}
		s.notifier.MilestoneChanged(ctx, m.ContractID, after.ID, recipient, to)
	}

	switch to {
	case MilestoneApproved:
		if err := s.store.AcceptDeliverables(ctx, after.ID); err != nil {
			logWarn(ctx, "contracts: could not mark deliverables accepted", err)
		}
		s.audit.RecordRequest(ctx, audit.Entry{
			Action: audit.ActionMilestoneApproved, SubjectType: "milestone",
			SubjectID: &after.ID,
			Before:    map[string]any{"status": before.Status},
			After:     map[string]any{"status": to},
		})
		// Approval is what the release waits on; the money moves through the
		// provider, never from here.
		if s.fundingAvailable() {
			if err := s.funder.ReleaseMilestone(ctx, m.ContractID, after.ID); err != nil {
				logWarn(ctx, "contracts: could not start the release", err)
			}
		}
		s.settle(ctx, m.ContractID)
	case MilestoneReleased:
		s.settle(ctx, m.ContractID)
	case MilestoneDisputed:
		if err := s.store.SetContractStatus(ctx, m.ContractID, StatusDisputed, nil, ""); err != nil {
			logWarn(ctx, "contracts: could not mark the contract disputed", err)
		}
	}
}

func (s *Service) settle(ctx context.Context, contractID uuid.UUID) {
	completed, err := s.store.SettleIfFinished(ctx, contractID)
	if err != nil {
		logWarn(ctx, "contracts: could not settle the contract", err)
		return
	}
	if !completed {
		return
	}
	s.postSystem(ctx, contractID, "contract.completed", nil, nil)
	// The project itself is finished too; a completed contract on an
	// in-progress project would leave the client's dashboard lying.
	contract, err := s.store.ByID(ctx, contractID)
	if err == nil {
		if _, err := s.projects.Transition(ctx, contract.Project.ID, "completed"); err != nil {
			logWarn(ctx, "contracts: could not complete the project", err)
		}
	}
}

// MarkFunded records that a payment for a milestone settled.
//
// Called by the payments module, never from an HTTP handler: a party cannot
// declare their own money received.
func (s *Service) MarkFunded(ctx context.Context, milestoneID uuid.UUID) error {
	milestone, err := s.store.MilestoneByID(ctx, milestoneID)
	if err != nil {
		return err
	}
	if milestone.Status != MilestoneDraft {
		return nil
	}
	if _, err := s.store.Transition(ctx, TransitionInput{
		MilestoneID: milestoneID, From: MilestoneDraft, To: MilestoneFunded,
		Note: "Funds received.",
	}); err != nil {
		return err
	}
	if err := s.store.ActivateOnFirstFunding(ctx, milestone.ContractID); err != nil {
		return err
	}
	s.postSystem(ctx, milestone.ContractID, "milestone.funded", &milestoneID, nil)
	return nil
}

// MarkReleased records that a payout completed. Also only for the payments
// module.
func (s *Service) MarkReleased(ctx context.Context, milestoneID uuid.UUID) error {
	milestone, err := s.store.MilestoneByID(ctx, milestoneID)
	if err != nil {
		return err
	}
	if milestone.Status != MilestoneApproved {
		return nil
	}
	if _, err := s.store.Transition(ctx, TransitionInput{
		MilestoneID: milestoneID, From: MilestoneApproved, To: MilestoneReleased,
		Note: "Payment released to the developer.",
	}); err != nil {
		return err
	}
	s.postSystem(ctx, milestone.ContractID, "milestone.released", &milestoneID, nil)
	s.settle(ctx, milestone.ContractID)
	return nil
}

// ── What the payments module needs ──────────────────────────────────────────

// FundingFacts is everything the payments module needs about a milestone, in
// one read: who the parties are, what it is worth, and whether it is in a
// state where money should move.
//
// Exported as a value rather than by handing over the store, so payments
// cannot reach into a contract's other fields or write to one.
type FundingFacts struct {
	MilestoneID       uuid.UUID
	MilestoneTitle    string
	MilestoneStatus   string
	ContractID        uuid.UUID
	ContractReference string
	ContractTitle     string
	ContractStatus    string
	ClientID          uuid.UUID
	DeveloperID       uuid.UUID
	AmountMinor       int64
	Currency          string
	// The fee percentage frozen on the contract at signature, so a milestone
	// payout uses the rate the parties agreed to rather than today's schedule.
	FeePercent float64
}

func (s *Service) FundingFacts(ctx context.Context, milestoneID uuid.UUID) (FundingFacts, error) {
	return s.store.fundingFacts(ctx, milestoneID)
}

// EnsureParty resolves a caller's position on a contract, for a module that
// needs the same membership gate without duplicating it.
func (s *Service) EnsureParty(ctx context.Context, id *security.Identity,
	contractID uuid.UUID) (string, error) {

	membership, err := s.store.MembershipOf(ctx, contractID)
	if err != nil {
		return "", notFound(err, contractID)
	}
	return s.authoriseAction(ctx, id, membership)
}

// ── Deliverables ────────────────────────────────────────────────────────────

// DeliverableRequest is one hand-over.
type DeliverableRequest struct {
	Kind   string `json:"kind"`
	Title  string `json:"title"`
	Detail string `json:"detail"`
	// For kind "file": an id the caller already uploaded. Ownership is
	// re-checked, so another user's file id cannot be attached.
	FileID string `json:"file_id"`
	// For kind "link" or "repository".
	URL string `json:"url"`
}

func (s *Service) AddDeliverable(ctx context.Context, id *security.Identity,
	contractID uuid.UUID, milestoneID *uuid.UUID, in DeliverableRequest) (*Deliverable, error) {

	membership, err := s.store.MembershipOf(ctx, contractID)
	if err != nil {
		return nil, notFound(err, contractID)
	}
	role, err := s.authoriseAction(ctx, id, membership)
	if err != nil {
		return nil, err
	}
	if !membership.CanUpload[id.UserID] && role != roleAdmin {
		e := *httpx.ErrForbidden
		e.Message = "You don't have upload access on this contract."
		return nil, &e
	}
	if milestoneID != nil {
		milestone, err := s.store.MilestoneByID(ctx, *milestoneID)
		if err != nil || milestone.ContractID != contractID {
			return nil, httpx.Validation(map[string]string{
				"milestone_id": "That milestone isn't part of this contract.",
			})
		}
	}
	return s.addDeliverable(ctx, id, contractID, milestoneID, role, in)
}

func (s *Service) addDeliverable(ctx context.Context, id *security.Identity,
	contractID uuid.UUID, milestoneID *uuid.UUID, role string,
	in DeliverableRequest) (*Deliverable, error) {

	v := validate.New()
	kind := v.OneOf("kind", "The deliverable type", defaultKind(in.Kind),
		DeliverableFile, DeliverableLink, DeliverableRepository, DeliverableNote)
	title := strings.TrimSpace(in.Title)
	v.Required("title", "A title", title)
	v.Length("title", "The title", title, 2, 160)
	v.NoControlChars("title", "The title", title)
	if detail := strings.TrimSpace(in.Detail); detail != "" {
		v.Length("detail", "The description", detail, 0, 4000)
	}

	var fileID *uuid.UUID
	var normalised urlguard.Result
	switch kind {
	case DeliverableFile:
		parsed, err := uuid.Parse(strings.TrimSpace(in.FileID))
		if err != nil {
			v.Add("file_id", "Upload the file first, then attach it.")
			break
		}
		// Ownership is the gate: the uploader must be the caller. This is what
		// stops someone attaching a file id they guessed.
		file, err := s.files.OwnedByID(ctx, parsed, id.UserID)
		if err != nil {
			v.Add("file_id", "We couldn't find that upload. Please upload the file again.")
			break
		}
		if file.Purpose != files.PurposeDeliverable {
			v.Add("file_id", "That upload wasn't made for a deliverable.")
			break
		}
		fileID = &parsed
	case DeliverableLink, DeliverableRepository:
		result, err := urlguard.Normalise(strings.TrimSpace(in.URL), s.urlOpts)
		if err != nil {
			v.Add("url", urlMessage(err))
			break
		}
		normalised = result
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	deliverableID, err := s.store.AddDeliverable(ctx, NewDeliverable{
		ContractID:  contractID,
		MilestoneID: milestoneID,
		Kind:        kind,
		Title:       title,
		Detail:      strings.TrimSpace(in.Detail),
		FileID:      fileID,
		URL:         normalised.URL,
		SubmittedBy: id.UserID,
	})
	if err != nil {
		return nil, httpx.Internalf(err, "add deliverable")
	}

	out := &Deliverable{
		ID: deliverableID, MilestoneID: milestoneID, Kind: kind, Title: title,
		Detail: strings.TrimSpace(in.Detail), FileID: fileID,
		URL: normalised.URL, Host: normalised.Host, CreatedAt: time.Now(),
	}
	if fileID != nil {
		if file, err := s.files.ByID(ctx, *fileID); err == nil {
			out.FileName, out.FileMIME = file.OriginalName, file.MIME
			size := file.ByteSize
			out.FileByteSize = &size
			if url, err := s.files.SignedURL(ctx, file, 15*time.Minute); err == nil {
				out.FileURL = url
			}
		}
	}
	return out, nil
}

func defaultKind(kind string) string {
	if strings.TrimSpace(kind) == "" {
		return DeliverableFile
	}
	return strings.TrimSpace(kind)
}

// ── Participants ────────────────────────────────────────────────────────────

type ParticipantRequest struct {
	Username   string `json:"username"`
	CanMessage *bool  `json:"can_message"`
	CanUpload  *bool  `json:"can_upload"`
}

// AddObserver puts a third person on the workspace — a designer the client
// brought in, a teammate the developer works with.
//
// Only ever an observer: the two parties to the agreement are fixed at
// signature and cannot be added or swapped later.
func (s *Service) AddObserver(ctx context.Context, id *security.Identity,
	contractID uuid.UUID, in ParticipantRequest) (*Contract, error) {

	membership, err := s.store.MembershipOf(ctx, contractID)
	if err != nil {
		return nil, notFound(err, contractID)
	}
	role, err := s.authoriseAction(ctx, id, membership)
	if err != nil {
		return nil, err
	}
	if role != RoleClient && role != RoleDeveloper {
		e := *httpx.ErrForbidden
		e.Message = "Only the client or the developer can add someone to this workspace."
		return nil, &e
	}

	userID, err := s.store.userIDByUsername(ctx, in.Username)
	if err != nil {
		return nil, httpx.Validation(map[string]string{
			"username": "We couldn't find that account.",
		})
	}
	if userID == membership.ClientID || userID == membership.DeveloperID {
		return nil, httpx.Validation(map[string]string{
			"username": "That person is already a party to this contract.",
		})
	}

	canMessage, canUpload := true, false
	if in.CanMessage != nil {
		canMessage = *in.CanMessage
	}
	if in.CanUpload != nil {
		canUpload = *in.CanUpload
	}
	if err := s.store.AddParticipant(ctx, contractID, userID, id.UserID,
		RoleObserver, canMessage, canUpload); err != nil {
		return nil, httpx.Internalf(err, "add observer")
	}
	if err := s.store.addConversationParticipant(ctx, contractID, userID); err != nil {
		logWarn(ctx, "contracts: could not add the observer to the thread", err)
	}
	return s.View(ctx, id, contractID)
}

func (s *Service) RemoveObserver(ctx context.Context, id *security.Identity,
	contractID, userID uuid.UUID) error {

	membership, err := s.store.MembershipOf(ctx, contractID)
	if err != nil {
		return notFound(err, contractID)
	}
	role, err := s.authoriseAction(ctx, id, membership)
	if err != nil {
		return err
	}
	if role != RoleClient && role != RoleDeveloper {
		e := *httpx.ErrForbidden
		e.Message = "Only the client or the developer can change who is on this workspace."
		return &e
	}
	if err := s.store.RemoveParticipant(ctx, contractID, userID); err != nil {
		if errors.Is(err, ErrNotFound) {
			return httpx.NotFoundf("that person is not an observer on contract %s", contractID)
		}
		return httpx.Internalf(err, "remove observer")
	}
	return nil
}

// ── Cancellation ────────────────────────────────────────────────────────────

type CancelRequest struct {
	Reason string `json:"reason"`
}

// Cancel ends a contract no work has been approved on.
//
// Once a milestone has been approved there is delivered work and possibly
// released money, and unwinding that is a dispute rather than a cancellation.
func (s *Service) Cancel(ctx context.Context, id *security.Identity, contractID uuid.UUID,
	in CancelRequest) (*Contract, error) {

	membership, err := s.store.MembershipOf(ctx, contractID)
	if err != nil {
		return nil, notFound(err, contractID)
	}
	role, err := s.authoriseAction(ctx, id, membership)
	if err != nil {
		return nil, err
	}
	if role != RoleClient {
		e := *httpx.ErrForbidden
		e.Code = "not_your_move"
		e.Message = "Only the client can cancel a contract. If something has gone wrong, open a dispute."
		return nil, &e
	}
	if len(strings.TrimSpace(in.Reason)) < 20 {
		return nil, httpx.Validation(map[string]string{
			"reason": "Please say why you're cancelling — the developer is owed an explanation.",
		})
	}

	contract, err := s.store.ByID(ctx, contractID)
	if err != nil {
		return nil, notFound(err, contractID)
	}
	for _, milestone := range contract.Milestones {
		switch milestone.Status {
		case MilestoneApproved, MilestoneReleased, MilestoneSubmitted:
			e := *httpx.ErrConflict
			e.Code = "work_delivered"
			e.Message = "Work has already been delivered on this contract, so it can't simply be cancelled. Open a dispute and we'll help resolve it."
			return nil, &e
		}
	}

	actor := id.UserID
	if err := s.store.SetContractStatus(ctx, contractID, StatusCancelled, &actor,
		strings.TrimSpace(in.Reason)); err != nil {
		return nil, httpx.Internalf(err, "cancel contract")
	}
	if err := s.store.cancelOpenMilestones(ctx, contractID); err != nil {
		logWarn(ctx, "contracts: could not cancel the remaining milestones", err)
	}
	s.postSystem(ctx, contractID, "contract.cancelled", nil, nil)
	s.audit.RecordRequest(ctx, audit.Entry{
		Action: audit.ActionProjectCancelled, SubjectType: "contract", SubjectID: &contractID,
		Detail: strings.TrimSpace(in.Reason),
	})
	return s.View(ctx, id, contractID)
}

// ── Helpers ─────────────────────────────────────────────────────────────────

func (s *Service) postSystem(ctx context.Context, contractID uuid.UUID, event string,
	milestoneID *uuid.UUID, payload map[string]any) {

	if s.messenger == nil {
		return
	}
	conversationID, err := s.store.ConversationFor(ctx, contractID)
	if err != nil {
		return
	}
	if err := s.messenger.PostSystem(ctx, conversationID, event, milestoneID, payload); err != nil {
		logWarn(ctx, "contracts: could not post the workspace event", err)
	}
}

func knownContractStatus(status string) bool {
	switch status {
	case StatusPendingFunding, StatusActive, StatusPaused, StatusSubmitted,
		StatusCompleted, StatusCancelled, StatusDisputed, StatusClosed:
		return true
	}
	return false
}

// transitionMessage explains a refused move in terms of the work rather than
// the state machine.
func transitionMessage(from, to string) string {
	switch {
	case to == MilestoneInProgress && from == MilestoneDraft:
		return "This milestone hasn't been funded yet, so work can't start on it."
	case to == MilestoneSubmitted && from == MilestoneDraft:
		return "This milestone hasn't been funded yet."
	case to == MilestoneSubmitted && from == MilestoneSubmitted:
		return "This work is already with the client for review."
	case to == MilestoneApproved && from != MilestoneSubmitted:
		return "There's nothing submitted to approve on this milestone yet."
	case to == MilestoneRevision && from != MilestoneSubmitted:
		return "There's no submitted work to send back."
	case from == MilestoneReleased:
		return "This milestone is finished and paid."
	case from == MilestoneCancelled:
		return "This milestone was cancelled."
	}
	return "This milestone can't move to that state from where it is now."
}

func notYourMoveMessage(to string) string {
	switch to {
	case MilestoneApproved:
		return "Only the client can approve work."
	case MilestoneRevision:
		return "Only the client can ask for a revision."
	case MilestoneSubmitted:
		return "Only the developer can submit work."
	case MilestoneInProgress:
		return "Only the developer can start a milestone."
	case MilestoneFunded:
		return "Only the client can fund a milestone."
	case MilestoneCancelled:
		return "Only the client can cancel a milestone."
	}
	return "That action isn't yours to take on this contract."
}

func urlMessage(err error) string {
	var rejection *urlguard.Rejection
	if errors.As(err, &rejection) {
		return rejection.Human()
	}
	return "That link isn't valid. Please check it and try again."
}

func notFound(err error, contractID uuid.UUID) error {
	if errors.Is(err, ErrNotFound) {
		return httpx.NotFoundf("contract %s does not exist", contractID)
	}
	return httpx.Internalf(err, "load contract")
}

func notFoundMilestone(err error, milestoneID uuid.UUID) error {
	if errors.Is(err, ErrNotFound) {
		return httpx.NotFoundf("milestone %s does not exist", milestoneID)
	}
	return httpx.Internalf(err, "load milestone")
}

func forbidRole(message string, err error) error {
	e := *httpx.ErrForbidden
	e.Message = message
	return e.Wrap(err)
}
