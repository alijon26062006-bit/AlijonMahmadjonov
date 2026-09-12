// Package contracts owns the agreement between a client and a developer, and
// the milestones money moves through.
//
// Two rules shape everything here.
//
// The contract is the source of truth for access: workspace, files, messages
// and payment authorisation all resolve through contract_participants rather
// than by comparing user ids at each endpoint.
//
// And the state machine is closed. A milestone moves only along a transition
// this package lists, only when the party entitled to make that move asks for
// it, and every move is recorded with who made it — which is what a dispute
// investigation reads later.
package contracts

import (
	"time"

	"github.com/google/uuid"
)

// Contract is one agreement.
type Contract struct {
	ID        uuid.UUID `json:"id"`
	Reference string    `json:"reference"`
	Title     string    `json:"title"`

	Project   ProjectRef `json:"project"`
	Client    PartyRef   `json:"client"`
	Developer PartyRef   `json:"developer"`

	Status          string `json:"status"`
	ProgressPercent int    `json:"progress_percent"`

	// Money, in minor units with an explicit currency. Withheld from an
	// observer, who is on the workspace to help with the work rather than to
	// see what it cost.
	AmountMinor   *int64 `json:"amount_minor,omitempty"`
	FeeMinor      *int64 `json:"fee_minor,omitempty"`
	PayoutMinor   *int64 `json:"payout_minor,omitempty"`
	ReleasedMinor *int64 `json:"released_minor,omitempty"`
	FundedMinor   *int64 `json:"funded_minor,omitempty"`
	Currency      string `json:"currency,omitempty"`
	FeePercent    string `json:"fee_percent,omitempty"`

	StartsOn     *time.Time `json:"starts_on,omitempty"`
	DueOn        *time.Time `json:"due_on,omitempty"`
	DeliveryDays *int       `json:"delivery_days,omitempty"`

	// How this contract may appear on the developer's public profile once it
	// is finished. The developer's balance and earnings are never public
	// whatever this says.
	PriceVisibility      string `json:"price_visibility"`
	ClientAllowsShowcase bool   `json:"client_allows_showcase"`

	Milestones   []Milestone   `json:"milestones"`
	Deliverables []Deliverable `json:"deliverables,omitempty"`
	Participants []PartyRef    `json:"participants,omitempty"`

	CompletedAt        *time.Time `json:"completed_at,omitempty"`
	CancelledAt        *time.Time `json:"cancelled_at,omitempty"`
	CancellationReason string     `json:"cancellation_reason,omitempty"`

	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`

	// The caller's own position, so the interface knows which screen to draw
	// without inferring it from the ids.
	MyRole string `json:"my_role"`
	Can    Can    `json:"can"`
}

// Card is the compact shape a dashboard list renders.
type Card struct {
	ID        uuid.UUID `json:"id"`
	Reference string    `json:"reference"`
	Title     string    `json:"title"`
	Status    string    `json:"status"`
	// The other party, which is who the reader actually cares about.
	Counterparty    PartyRef   `json:"counterparty"`
	ProgressPercent int        `json:"progress_percent"`
	AmountMinor     *int64     `json:"amount_minor,omitempty"`
	Currency        string     `json:"currency,omitempty"`
	NextMilestone   *Milestone `json:"next_milestone,omitempty"`
	DueOn           *time.Time `json:"due_on,omitempty"`
	// What is waiting on the reader, which is what a dashboard is for.
	NeedsMyAction bool      `json:"needs_my_action"`
	UnreadCount   int       `json:"unread_count"`
	UpdatedAt     time.Time `json:"updated_at"`
	MyRole        string    `json:"my_role"`
}

// Can lists the actions the caller may take right now. The interface uses it
// to decide which buttons exist at all — a button that returns 403 is worse
// than no button.
type Can struct {
	Message         bool `json:"message"`
	Upload          bool `json:"upload"`
	FundMilestone   bool `json:"fund_milestone"`
	StartMilestone  bool `json:"start_milestone"`
	SubmitWork      bool `json:"submit_work"`
	RequestRevision bool `json:"request_revision"`
	Approve         bool `json:"approve"`
	Release         bool `json:"release"`
	Cancel          bool `json:"cancel"`
	Dispute         bool `json:"dispute"`
	AddParticipant  bool `json:"add_participant"`
}

type Milestone struct {
	ID          uuid.UUID `json:"id"`
	ContractID  uuid.UUID `json:"contract_id"`
	Position    int       `json:"position"`
	Title       string    `json:"title"`
	Detail      string    `json:"detail,omitempty"`
	AmountMinor *int64    `json:"amount_minor,omitempty"`
	Currency    string    `json:"currency,omitempty"`
	Status      string    `json:"status"`

	DueOn          *time.Time `json:"due_on,omitempty"`
	RevisionCount  int        `json:"revision_count"`
	RevisionLimit  int        `json:"revision_limit"`
	SubmittedAt    *time.Time `json:"submitted_at,omitempty"`
	SubmissionNote string     `json:"submission_note,omitempty"`
	ApprovedAt     *time.Time `json:"approved_at,omitempty"`
	ReleasedAt     *time.Time `json:"released_at,omitempty"`
	RevisionNote   string     `json:"revision_note,omitempty"`

	Deliverables []Deliverable    `json:"deliverables,omitempty"`
	Events       []MilestoneEvent `json:"events,omitempty"`

	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// MilestoneEvent is one recorded state change.
type MilestoneEvent struct {
	ID         uuid.UUID `json:"id"`
	FromStatus string    `json:"from_status,omitempty"`
	ToStatus   string    `json:"to_status"`
	Actor      *PartyRef `json:"actor,omitempty"`
	Note       string    `json:"note,omitempty"`
	CreatedAt  time.Time `json:"created_at"`
}

// Deliverable is what the developer hands over.
type Deliverable struct {
	ID          uuid.UUID  `json:"id"`
	MilestoneID *uuid.UUID `json:"milestone_id,omitempty"`
	Kind        string     `json:"kind"`
	Title       string     `json:"title"`
	Detail      string     `json:"detail,omitempty"`

	FileID *uuid.UUID `json:"file_id,omitempty"`
	// A short-lived signed URL, issued only to a caller the contract admits.
	// Never a permanent link: a deliverable is the parties' business.
	FileURL      string `json:"file_url,omitempty"`
	FileName     string `json:"file_name,omitempty"`
	FileByteSize *int64 `json:"file_byte_size,omitempty"`
	FileMIME     string `json:"file_mime,omitempty"`

	URL  string `json:"url,omitempty"`
	Host string `json:"host,omitempty"`

	SubmittedBy *PartyRef  `json:"submitted_by,omitempty"`
	AcceptedAt  *time.Time `json:"accepted_at,omitempty"`
	CreatedAt   time.Time  `json:"created_at"`
}

type ProjectRef struct {
	ID       uuid.UUID `json:"id"`
	Slug     string    `json:"slug"`
	Title    string    `json:"title"`
	Category string    `json:"category,omitempty"`
}

type PartyRef struct {
	ID         uuid.UUID `json:"id"`
	Username   string    `json:"username"`
	FullName   string    `json:"full_name"`
	Title      string    `json:"title,omitempty"`
	PhotoURL   string    `json:"photo_url,omitempty"`
	Role       string    `json:"role,omitempty"`
	CanMessage bool      `json:"can_message,omitempty"`
	CanUpload  bool      `json:"can_upload,omitempty"`
}

// Contract statuses.
const (
	StatusPendingFunding = "pending_funding"
	StatusActive         = "active"
	StatusPaused         = "paused"
	StatusSubmitted      = "submitted"
	StatusCompleted      = "completed"
	StatusCancelled      = "cancelled"
	StatusDisputed       = "disputed"
	StatusClosed         = "closed"
)

// Milestone statuses. The order is the happy path.
const (
	MilestoneDraft      = "draft"
	MilestoneFunded     = "funded"
	MilestoneInProgress = "in_progress"
	MilestoneSubmitted  = "submitted"
	MilestoneRevision   = "revision_requested"
	MilestoneApproved   = "approved"
	MilestoneReleased   = "released"
	MilestoneDisputed   = "disputed"
	MilestoneCancelled  = "cancelled"
)

// Participant roles.
const (
	RoleClient    = "client"
	RoleDeveloper = "developer"
	RoleObserver  = "observer"
	// roleAdmin is not a participant role: staff access comes from the admin
	// role and is written to the audit log on every use. It appears only as
	// the caller's own MyRole, so the interface can show an admin view.
	roleAdmin = "admin"
)

// milestoneTransitions is the whole state machine. Anything not listed here
// cannot happen, which is the point: an invalid transition is impossible
// rather than merely unlikely.
//
// Who may make each move is a separate question, answered by actorFor below —
// keeping "is this move legal" and "may you make it" apart is what stops a
// developer approving their own work.
var milestoneTransitions = map[string]map[string]bool{
	MilestoneDraft:      {MilestoneFunded: true, MilestoneCancelled: true},
	MilestoneFunded:     {MilestoneInProgress: true, MilestoneCancelled: true, MilestoneDisputed: true},
	MilestoneInProgress: {MilestoneSubmitted: true, MilestoneDisputed: true, MilestoneCancelled: true},
	MilestoneSubmitted:  {MilestoneApproved: true, MilestoneRevision: true, MilestoneDisputed: true},
	MilestoneRevision:   {MilestoneSubmitted: true, MilestoneDisputed: true, MilestoneCancelled: true},
	MilestoneApproved:   {MilestoneReleased: true, MilestoneDisputed: true},
	MilestoneReleased:   {MilestoneDisputed: true},
	MilestoneDisputed:   {MilestoneInProgress: true, MilestoneApproved: true, MilestoneCancelled: true},
	MilestoneCancelled:  {},
}

// CanTransition reports whether a milestone may move between two states.
func CanTransition(from, to string) bool {
	allowed, ok := milestoneTransitions[from]
	return ok && allowed[to]
}

// actorFor says which party is entitled to make a move.
//
// "client" and "developer" mean exactly one of them; "system" means no party
// may ask for it directly — the move is the consequence of something else
// (a payment settling, a dispute resolution) and comes from the module that
// owns that event.
var actorFor = map[string]string{
	MilestoneFunded:     RoleClient,
	MilestoneInProgress: RoleDeveloper,
	MilestoneSubmitted:  RoleDeveloper,
	MilestoneRevision:   RoleClient,
	MilestoneApproved:   RoleClient,
	MilestoneReleased:   "system",
	MilestoneDisputed:   "either",
	MilestoneCancelled:  RoleClient,
}

// ActorFor returns the party entitled to move a milestone into a status.
func ActorFor(to string) string { return actorFor[to] }

// Deliverable kinds.
const (
	DeliverableFile       = "file"
	DeliverableLink       = "link"
	DeliverableRepository = "repository"
	DeliverableNote       = "note"
)
