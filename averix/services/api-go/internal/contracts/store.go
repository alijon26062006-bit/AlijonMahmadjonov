package contracts

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/logx"
)

type Store struct {
	db        *database.DB
	publicURL func(string) string
}

func NewStore(db *database.DB, publicURL func(string) string) *Store {
	if publicURL == nil {
		publicURL = func(key string) string { return key }
	}
	return &Store{db: db, publicURL: publicURL}
}

var (
	ErrNotFound      = errors.New("contract not found")
	ErrBadTransition = errors.New("that milestone cannot move to that state")
	ErrRaced         = errors.New("the milestone changed while the request was in flight")
)

// ── Creation ────────────────────────────────────────────────────────────────

// NewContract is everything needed to sign one, already validated and with the
// fee already computed.
type NewContract struct {
	ProjectID       uuid.UUID
	ProposalID      uuid.UUID
	ClientID        uuid.UUID
	DeveloperID     uuid.UUID
	Title           string
	AmountMinor     int64
	Currency        string
	FeePercent      float64
	FeeMinor        int64
	PayoutMinor     int64
	DeliveryDays    int
	DueOn           *time.Time
	PriceVisibility string
	Milestones      []NewMilestone
	IsDemo          bool
}

type NewMilestone struct {
	Position    int
	Title       string
	Detail      string
	AmountMinor int64
	DueOn       *time.Time
}

// Create writes the contract, its membership, its milestones and the workspace
// conversation in one transaction.
//
// All of it or none of it: a contract whose participants row failed to write
// would be a contract nobody can open, and a conversation created without the
// contract would be a thread anchored to nothing.
func (s *Store) Create(ctx context.Context, in NewContract) (uuid.UUID, error) {
	reference, err := newReference()
	if err != nil {
		return uuid.Nil, err
	}

	var contractID uuid.UUID
	err = s.db.InTx(ctx, func(q database.Querier) error {
		err := q.QueryRow(ctx, `
			INSERT INTO contracts
			  (reference, project_id, proposal_id, client_id, developer_id, title,
			   amount_minor, currency, fee_percent, fee_minor, payout_minor,
			   status, delivery_days, due_on, price_visibility, starts_on, is_demo)
			VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,current_date,$16)
			RETURNING id`,
			reference, in.ProjectID, nullUUID(in.ProposalID), in.ClientID, in.DeveloperID,
			in.Title, in.AmountMinor, defaultTo(in.Currency, "USD"), in.FeePercent,
			in.FeeMinor, in.PayoutMinor, StatusPendingFunding, nullIfZero(in.DeliveryDays),
			in.DueOn, in.PriceVisibility, in.IsDemo).Scan(&contractID)
		if err != nil {
			return fmt.Errorf("insert contract: %w", err)
		}

		for _, party := range []struct {
			id   uuid.UUID
			role string
		}{{in.ClientID, RoleClient}, {in.DeveloperID, RoleDeveloper}} {
			if _, err := q.Exec(ctx, `
				INSERT INTO contract_participants (contract_id, user_id, role)
				VALUES ($1, $2, $3)`, contractID, party.id, party.role); err != nil {
				return fmt.Errorf("insert participant: %w", err)
			}
		}

		for _, milestone := range in.Milestones {
			if _, err := q.Exec(ctx, `
				INSERT INTO milestones
				  (contract_id, position, title, detail, amount_minor, currency, due_on)
				VALUES ($1,$2,$3,$4,$5,$6,$7)`,
				contractID, milestone.Position, milestone.Title,
				nullIfBlank(milestone.Detail), milestone.AmountMinor,
				defaultTo(in.Currency, "USD"), milestone.DueOn); err != nil {
				return fmt.Errorf("insert milestone: %w", err)
			}
		}

		// The workspace thread. Anchored to the contract, so there is no
		// free-floating inbox anywhere in the product.
		var conversationID uuid.UUID
		err = q.QueryRow(ctx, `
			INSERT INTO conversations (project_id, contract_id, proposal_id, subject)
			VALUES ($1, $2, $3, $4) RETURNING id`,
			in.ProjectID, contractID, nullUUID(in.ProposalID), in.Title).Scan(&conversationID)
		if err != nil {
			return fmt.Errorf("create workspace conversation: %w", err)
		}
		for _, userID := range []uuid.UUID{in.ClientID, in.DeveloperID} {
			if _, err := q.Exec(ctx, `
				INSERT INTO conversation_participants (conversation_id, user_id)
				VALUES ($1, $2) ON CONFLICT DO NOTHING`, conversationID, userID); err != nil {
				return fmt.Errorf("add conversation participant: %w", err)
			}
		}
		return nil
	})
	return contractID, err
}

// newReference builds the human-readable contract number.
//
// Random rather than sequential: a sequential reference tells anyone who holds
// one how many contracts the platform has signed, which is nobody's business.
func newReference() (string, error) {
	suffix, err := cryptox.RandomHex(4)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("AVX-%d-%s", time.Now().UTC().Year(), strings.ToUpper(suffix)), nil
}

// ── Reads ───────────────────────────────────────────────────────────────────

const contractSelect = `
	SELECT c.id, c.reference, c.title, c.status, c.progress_percent,
	       c.amount_minor, c.fee_minor, c.payout_minor, c.released_minor,
	       c.funded_minor, c.currency, c.fee_percent,
	       c.starts_on, c.due_on, c.delivery_days,
	       c.price_visibility, c.client_allows_showcase,
	       c.completed_at, c.cancelled_at, coalesce(c.cancellation_reason, ''),
	       c.created_at, c.updated_at,
	       p.id, p.slug, p.title, coalesce(cat.name, ''),
	       cl.id, cl.username, cl.full_name,
	       dv.id, dv.username, dv.full_name, coalesce(dp.professional_title, ''),
	       clp.derivatives, dvp.derivatives
	FROM contracts c
	JOIN projects p  ON p.id = c.project_id
	LEFT JOIN categories cat ON cat.id = p.category_id
	JOIN users cl    ON cl.id = c.client_id
	JOIN users dv    ON dv.id = c.developer_id
	LEFT JOIN developer_profiles dp ON dp.user_id = dv.id
	LEFT JOIN developer_photos clp ON clp.user_id = cl.id AND clp.is_current
	LEFT JOIN developer_photos dvp ON dvp.user_id = dv.id AND dvp.is_current`

func (s *Store) scan(row interface{ Scan(...any) error }) (*Contract, error) {
	var c Contract
	var amount, fee, payout, released, funded int64
	var feePercent float64
	var clientPhoto, developerPhoto map[string]map[string]string

	err := row.Scan(&c.ID, &c.Reference, &c.Title, &c.Status, &c.ProgressPercent,
		&amount, &fee, &payout, &released, &funded, &c.Currency, &feePercent,
		&c.StartsOn, &c.DueOn, &c.DeliveryDays,
		&c.PriceVisibility, &c.ClientAllowsShowcase,
		&c.CompletedAt, &c.CancelledAt, &c.CancellationReason,
		&c.CreatedAt, &c.UpdatedAt,
		&c.Project.ID, &c.Project.Slug, &c.Project.Title, &c.Project.Category,
		&c.Client.ID, &c.Client.Username, &c.Client.FullName,
		&c.Developer.ID, &c.Developer.Username, &c.Developer.FullName, &c.Developer.Title,
		&clientPhoto, &developerPhoto)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("scan contract: %w", err)
	}

	c.AmountMinor, c.FeeMinor, c.PayoutMinor = &amount, &fee, &payout
	c.ReleasedMinor, c.FundedMinor = &released, &funded
	c.FeePercent = fmt.Sprintf("%.2f", feePercent)
	c.Client.Role, c.Developer.Role = RoleClient, RoleDeveloper
	c.Client.PhotoURL = s.avatarURL(clientPhoto)
	c.Developer.PhotoURL = s.avatarURL(developerPhoto)
	return &c, nil
}

func (s *Store) avatarURL(derivatives map[string]map[string]string) string {
	for _, format := range []string{"webp", "jpeg"} {
		sizes, ok := derivatives[format]
		if !ok {
			continue
		}
		if key, ok := sizes["128"]; ok {
			return s.publicURL(key)
		}
		for _, key := range sizes {
			return s.publicURL(key)
		}
	}
	return ""
}

func (s *Store) ByID(ctx context.Context, id uuid.UUID) (*Contract, error) {
	contract, err := s.scan(s.db.QueryRow(ctx, contractSelect+" WHERE c.id = $1", id))
	if err != nil {
		return nil, err
	}
	if contract.Milestones, err = s.milestonesFor(ctx, id); err != nil {
		return nil, err
	}
	if contract.Participants, err = s.participantsFor(ctx, id); err != nil {
		return nil, err
	}
	return contract, nil
}

func (s *Store) ByReference(ctx context.Context, reference string) (*Contract, error) {
	var id uuid.UUID
	err := s.db.QueryRow(ctx, `SELECT id FROM contracts WHERE reference = $1`,
		strings.ToUpper(strings.TrimSpace(reference))).Scan(&id)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	return s.ByID(ctx, id)
}

// Membership is what every authorisation check in the workspace resolves to.
type Membership struct {
	ContractID  uuid.UUID
	ClientID    uuid.UUID
	DeveloperID uuid.UUID
	Status      string
	// Everyone currently on the contract, observers included.
	Participants []uuid.UUID
	Roles        map[uuid.UUID]string
	CanMessage   map[uuid.UUID]bool
	CanUpload    map[uuid.UUID]bool
}

// MembershipOf loads a contract's membership without loading the contract.
//
// Every protected path calls this first, so "may this caller touch this
// contract" is answered by one query against contract_participants rather than
// by each endpoint comparing ids for itself.
func (s *Store) MembershipOf(ctx context.Context, contractID uuid.UUID) (Membership, error) {
	m := Membership{
		ContractID: contractID,
		Roles:      map[uuid.UUID]string{},
		CanMessage: map[uuid.UUID]bool{},
		CanUpload:  map[uuid.UUID]bool{},
	}
	err := s.db.QueryRow(ctx,
		`SELECT client_id, developer_id, status FROM contracts WHERE id = $1`,
		contractID).Scan(&m.ClientID, &m.DeveloperID, &m.Status)
	if database.IsNoRows(err) {
		return m, ErrNotFound
	}
	if err != nil {
		return m, fmt.Errorf("load contract membership: %w", err)
	}

	rows, err := s.db.Query(ctx, `
		SELECT user_id, role, can_message, can_upload
		FROM contract_participants
		WHERE contract_id = $1 AND removed_at IS NULL`, contractID)
	if err != nil {
		return m, fmt.Errorf("load participants: %w", err)
	}
	defer rows.Close()
	for rows.Next() {
		var userID uuid.UUID
		var role string
		var canMessage, canUpload bool
		if err := rows.Scan(&userID, &role, &canMessage, &canUpload); err != nil {
			return m, err
		}
		m.Participants = append(m.Participants, userID)
		m.Roles[userID] = role
		m.CanMessage[userID] = canMessage
		m.CanUpload[userID] = canUpload
	}
	return m, rows.Err()
}

func (s *Store) participantsFor(ctx context.Context, contractID uuid.UUID) ([]PartyRef, error) {
	rows, err := s.db.Query(ctx, `
		SELECT u.id, u.username, u.full_name, cp.role, cp.can_message, cp.can_upload,
		       ph.derivatives
		FROM contract_participants cp
		JOIN users u ON u.id = cp.user_id
		LEFT JOIN developer_photos ph ON ph.user_id = u.id AND ph.is_current
		WHERE cp.contract_id = $1 AND cp.removed_at IS NULL
		ORDER BY cp.created_at`, contractID)
	if err != nil {
		return nil, fmt.Errorf("query participants: %w", err)
	}
	defer rows.Close()

	out := []PartyRef{}
	for rows.Next() {
		var ref PartyRef
		var photo map[string]map[string]string
		if err := rows.Scan(&ref.ID, &ref.Username, &ref.FullName, &ref.Role,
			&ref.CanMessage, &ref.CanUpload, &photo); err != nil {
			return nil, err
		}
		ref.PhotoURL = s.avatarURL(photo)
		out = append(out, ref)
	}
	return out, rows.Err()
}

func (s *Store) milestonesFor(ctx context.Context, contractID uuid.UUID) ([]Milestone, error) {
	rows, err := s.db.Query(ctx, `
		SELECT id, contract_id, position, title, coalesce(detail, ''), amount_minor,
		       currency, status, due_on, revision_count, revision_limit,
		       submitted_at, coalesce(submission_note, ''), approved_at, released_at,
		       coalesce(revision_note, ''), created_at, updated_at
		FROM milestones WHERE contract_id = $1 ORDER BY position`, contractID)
	if err != nil {
		return nil, fmt.Errorf("query milestones: %w", err)
	}
	defer rows.Close()

	out := []Milestone{}
	for rows.Next() {
		var m Milestone
		var amount int64
		if err := rows.Scan(&m.ID, &m.ContractID, &m.Position, &m.Title, &m.Detail,
			&amount, &m.Currency, &m.Status, &m.DueOn, &m.RevisionCount,
			&m.RevisionLimit, &m.SubmittedAt, &m.SubmissionNote, &m.ApprovedAt,
			&m.ReleasedAt, &m.RevisionNote, &m.CreatedAt, &m.UpdatedAt); err != nil {
			return nil, err
		}
		m.AmountMinor = &amount
		out = append(out, m)
	}
	return out, rows.Err()
}

// MilestoneByID loads one milestone with the contract it belongs to, so the
// caller never has to trust a contract id supplied alongside it.
func (s *Store) MilestoneByID(ctx context.Context, milestoneID uuid.UUID) (*Milestone, error) {
	var m Milestone
	var amount int64
	err := s.db.QueryRow(ctx, `
		SELECT id, contract_id, position, title, coalesce(detail, ''), amount_minor,
		       currency, status, due_on, revision_count, revision_limit,
		       submitted_at, coalesce(submission_note, ''), approved_at, released_at,
		       coalesce(revision_note, ''), created_at, updated_at
		FROM milestones WHERE id = $1`, milestoneID).
		Scan(&m.ID, &m.ContractID, &m.Position, &m.Title, &m.Detail, &amount,
			&m.Currency, &m.Status, &m.DueOn, &m.RevisionCount, &m.RevisionLimit,
			&m.SubmittedAt, &m.SubmissionNote, &m.ApprovedAt, &m.ReleasedAt,
			&m.RevisionNote, &m.CreatedAt, &m.UpdatedAt)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("load milestone: %w", err)
	}
	m.AmountMinor = &amount
	return &m, nil
}

func (s *Store) EventsFor(ctx context.Context, milestoneID uuid.UUID) ([]MilestoneEvent, error) {
	rows, err := s.db.Query(ctx, `
		SELECT e.id, coalesce(e.from_status, ''), e.to_status, coalesce(e.note, ''),
		       e.created_at, u.id, u.username, u.full_name
		FROM milestone_events e
		LEFT JOIN users u ON u.id = e.actor_id
		WHERE e.milestone_id = $1
		ORDER BY e.created_at`, milestoneID)
	if err != nil {
		return nil, fmt.Errorf("query milestone events: %w", err)
	}
	defer rows.Close()

	out := []MilestoneEvent{}
	for rows.Next() {
		var e MilestoneEvent
		var actorID *uuid.UUID
		var username, fullName *string
		if err := rows.Scan(&e.ID, &e.FromStatus, &e.ToStatus, &e.Note, &e.CreatedAt,
			&actorID, &username, &fullName); err != nil {
			return nil, err
		}
		if actorID != nil {
			e.Actor = &PartyRef{ID: *actorID, Username: deref(username), FullName: deref(fullName)}
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

// ForUser lists a user's contracts, newest activity first.
func (s *Store) ForUser(ctx context.Context, userID uuid.UUID, status string, limit int) ([]Card, error) {
	if limit <= 0 || limit > 100 {
		limit = 30
	}
	filter := ""
	args := []any{userID, limit}
	if status != "" {
		filter = " AND c.status = $3"
		args = append(args, status)
	}

	rows, err := s.db.Query(ctx, `
		SELECT c.id, c.reference, c.title, c.status, c.progress_percent,
		       c.amount_minor, c.currency, c.due_on, c.updated_at,
		       cp.role,
		       other.id, other.username, other.full_name,
		       coalesce(odp.professional_title, ''), oph.derivatives,
		       coalesce(conv.unread_count, 0)
		FROM contract_participants cp
		JOIN contracts c ON c.id = cp.contract_id
		JOIN users other ON other.id = CASE
		       WHEN c.client_id = cp.user_id THEN c.developer_id ELSE c.client_id END
		LEFT JOIN developer_profiles odp ON odp.user_id = other.id
		LEFT JOIN developer_photos oph ON oph.user_id = other.id AND oph.is_current
		LEFT JOIN (
		  SELECT cv.contract_id, cvp.user_id, cvp.unread_count
		  FROM conversations cv
		  JOIN conversation_participants cvp ON cvp.conversation_id = cv.id
		) conv ON conv.contract_id = c.id AND conv.user_id = cp.user_id
		WHERE cp.user_id = $1 AND cp.removed_at IS NULL`+filter+`
		ORDER BY c.updated_at DESC
		LIMIT $2`, args...)
	if err != nil {
		return nil, fmt.Errorf("query contracts: %w", err)
	}
	defer rows.Close()

	cards := []Card{}
	ids := []uuid.UUID{}
	for rows.Next() {
		var card Card
		var amount int64
		var photo map[string]map[string]string
		if err := rows.Scan(&card.ID, &card.Reference, &card.Title, &card.Status,
			&card.ProgressPercent, &amount, &card.Currency, &card.DueOn,
			&card.UpdatedAt, &card.MyRole,
			&card.Counterparty.ID, &card.Counterparty.Username,
			&card.Counterparty.FullName, &card.Counterparty.Title, &photo,
			&card.UnreadCount); err != nil {
			return nil, fmt.Errorf("scan contract card: %w", err)
		}
		card.AmountMinor = &amount
		card.Counterparty.PhotoURL = s.avatarURL(photo)
		cards = append(cards, card)
		ids = append(ids, card.ID)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	// The next milestone for every card in one query rather than one per card.
	if len(ids) > 0 {
		next, err := s.nextMilestones(ctx, ids)
		if err != nil {
			return nil, err
		}
		for i := range cards {
			if milestone, ok := next[cards[i].ID]; ok {
				m := milestone
				cards[i].NextMilestone = &m
				cards[i].NeedsMyAction = waitingOn(m.Status) == cards[i].MyRole
			}
		}
	}
	return cards, nil
}

// nextMilestones finds the earliest unfinished milestone per contract.
func (s *Store) nextMilestones(ctx context.Context, contractIDs []uuid.UUID) (map[uuid.UUID]Milestone, error) {
	rows, err := s.db.Query(ctx, `
		SELECT DISTINCT ON (contract_id)
		       id, contract_id, position, title, amount_minor, currency, status,
		       due_on, revision_count, revision_limit, created_at, updated_at
		FROM milestones
		WHERE contract_id = ANY($1) AND status NOT IN ('released','cancelled')
		ORDER BY contract_id, position`, contractIDs)
	if err != nil {
		return nil, fmt.Errorf("query next milestones: %w", err)
	}
	defer rows.Close()

	out := map[uuid.UUID]Milestone{}
	for rows.Next() {
		var m Milestone
		var amount int64
		if err := rows.Scan(&m.ID, &m.ContractID, &m.Position, &m.Title, &amount,
			&m.Currency, &m.Status, &m.DueOn, &m.RevisionCount, &m.RevisionLimit,
			&m.CreatedAt, &m.UpdatedAt); err != nil {
			return nil, err
		}
		m.AmountMinor = &amount
		out[m.ContractID] = m
	}
	return out, rows.Err()
}

// waitingOn says whose move it is, which is what drives "needs my action".
func waitingOn(status string) string {
	switch status {
	case MilestoneDraft:
		return RoleClient
	case MilestoneFunded, MilestoneInProgress, MilestoneRevision:
		return RoleDeveloper
	case MilestoneSubmitted:
		return RoleClient
	}
	return ""
}

// ── Transitions ─────────────────────────────────────────────────────────────

// TransitionInput is one milestone move.
type TransitionInput struct {
	MilestoneID uuid.UUID
	From        string
	To          string
	ActorID     uuid.UUID
	Note        string
	// Set when the move is a revision request, so the count is bumped in the
	// same statement as the status.
	CountRevision bool
}

// Transition moves a milestone and records the event.
//
// The current status is part of the UPDATE's WHERE clause, so two concurrent
// requests cannot both read "submitted" and both approve: the second writes
// nothing and gets ErrRaced.
func (s *Store) Transition(ctx context.Context, in TransitionInput) (*Milestone, error) {
	var milestone *Milestone
	err := s.db.InTx(ctx, func(q database.Querier) error {
		// The extra columns differ per target state, so the argument list is
		// built alongside them: passing placeholders a statement does not use
		// is an error, not a no-op.
		fields := ", updated_at = now()"
		args := []any{in.MilestoneID, in.To, in.From}
		switch in.To {
		case MilestoneSubmitted:
			fields += ", submitted_at = now(), submission_note = nullif($4, '')"
			args = append(args, in.Note)
		case MilestoneRevision:
			fields += ", revision_note = nullif($4, ''), revision_count = revision_count + 1"
			args = append(args, in.Note)
		case MilestoneApproved:
			fields += ", approved_at = now(), approved_by = $4"
			args = append(args, actorOrNil(in.ActorID))
		case MilestoneReleased:
			fields += ", released_at = now()"
		case MilestoneCancelled:
			fields += ", cancelled_at = now()"
		}

		tag, err := q.Exec(ctx,
			`UPDATE milestones SET status = $2`+fields+
				` WHERE id = $1 AND status = $3`, args...)
		if err != nil {
			return fmt.Errorf("transition milestone: %w", err)
		}
		if tag.RowsAffected() == 0 {
			return ErrRaced
		}

		if _, err := q.Exec(ctx, `
			INSERT INTO milestone_events (milestone_id, actor_id, from_status, to_status, note)
			VALUES ($1, $2, $3, $4, $5)`,
			in.MilestoneID, actorOrNil(in.ActorID), in.From, in.To,
			nullIfBlank(in.Note)); err != nil {
			return fmt.Errorf("record milestone event: %w", err)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	milestone, err = s.MilestoneByID(ctx, in.MilestoneID)
	return milestone, err
}

// SetContractStatus moves the contract itself.
func (s *Store) SetContractStatus(ctx context.Context, contractID uuid.UUID, status string,
	actorID *uuid.UUID, reason string) error {

	// As with a milestone move, the columns and the arguments are built
	// together: a statement handed placeholders it does not use is an error.
	extra := ""
	args := []any{contractID, status}
	switch status {
	case StatusCompleted:
		extra = ", completed_at = now()"
	case StatusCancelled:
		extra = ", cancelled_at = now(), cancelled_by = $3, cancellation_reason = nullif($4, '')"
		args = append(args, actorID, reason)
	}
	_, err := s.db.Exec(ctx,
		`UPDATE contracts SET status = $2, updated_at = now()`+extra+` WHERE id = $1`, args...)
	if err != nil {
		return fmt.Errorf("set contract status: %w", err)
	}
	return nil
}

// SettleIfFinished completes a contract once every milestone is finished.
//
// Called after each approval. "Finished" means approved, released or
// cancelled: a cancelled milestone is settled business, and a contract whose
// remaining work was cancelled should not hang open forever.
func (s *Store) SettleIfFinished(ctx context.Context, contractID uuid.UUID) (bool, error) {
	var open, total int
	err := s.db.QueryRow(ctx, `
		SELECT count(*) FILTER (WHERE status NOT IN ('approved','released','cancelled')),
		       count(*)
		FROM milestones WHERE contract_id = $1`, contractID).Scan(&open, &total)
	if err != nil {
		return false, fmt.Errorf("count open milestones: %w", err)
	}
	if total == 0 || open > 0 {
		return false, nil
	}

	tag, err := s.db.Exec(ctx, `
		UPDATE contracts SET status = $2, completed_at = now(), updated_at = now()
		WHERE id = $1 AND status NOT IN ('completed','cancelled','closed','disputed')`,
		contractID, StatusCompleted)
	if err != nil {
		return false, fmt.Errorf("complete contract: %w", err)
	}
	return tag.RowsAffected() == 1, nil
}

// ActivateOnFirstFunding moves a contract out of pending_funding.
func (s *Store) ActivateOnFirstFunding(ctx context.Context, contractID uuid.UUID) error {
	_, err := s.db.Exec(ctx, `
		UPDATE contracts SET status = $2, updated_at = now()
		WHERE id = $1 AND status = $3`, contractID, StatusActive, StatusPendingFunding)
	return err
}

// ── Participants ────────────────────────────────────────────────────────────

func (s *Store) AddParticipant(ctx context.Context, contractID, userID, addedBy uuid.UUID,
	role string, canMessage, canUpload bool) error {

	_, err := s.db.Exec(ctx, `
		INSERT INTO contract_participants
		  (contract_id, user_id, role, can_message, can_upload, added_by)
		VALUES ($1,$2,$3,$4,$5,$6)
		ON CONFLICT (contract_id, user_id) DO UPDATE
		SET role = excluded.role, can_message = excluded.can_message,
		    can_upload = excluded.can_upload, removed_at = NULL`,
		contractID, userID, role, canMessage, canUpload, addedBy)
	if err != nil {
		return fmt.Errorf("add participant: %w", err)
	}
	return nil
}

func (s *Store) RemoveParticipant(ctx context.Context, contractID, userID uuid.UUID) error {
	// The client and the developer are the contract; only an observer can be
	// removed, which the SQL enforces rather than the caller remembering to.
	tag, err := s.db.Exec(ctx, `
		UPDATE contract_participants SET removed_at = now()
		WHERE contract_id = $1 AND user_id = $2 AND role = 'observer' AND removed_at IS NULL`,
		contractID, userID)
	if err != nil {
		return fmt.Errorf("remove participant: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

// ── Deliverables ────────────────────────────────────────────────────────────

type NewDeliverable struct {
	ContractID  uuid.UUID
	MilestoneID *uuid.UUID
	Kind        string
	Title       string
	Detail      string
	FileID      *uuid.UUID
	URL         string
	SubmittedBy uuid.UUID
}

func (s *Store) AddDeliverable(ctx context.Context, in NewDeliverable) (uuid.UUID, error) {
	var id uuid.UUID
	err := s.db.QueryRow(ctx, `
		INSERT INTO deliverables
		  (contract_id, milestone_id, kind, title, detail, file_id, url, submitted_by)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id`,
		in.ContractID, in.MilestoneID, in.Kind, in.Title, nullIfBlank(in.Detail),
		in.FileID, nullIfBlank(in.URL), in.SubmittedBy).Scan(&id)
	if err != nil {
		return uuid.Nil, fmt.Errorf("insert deliverable: %w", err)
	}
	return id, nil
}

// DeliverablesFor loads a contract's hand-overs. File URLs are not built here:
// a private object gets a signed URL from the service, after the caller's
// entitlement has been established.
func (s *Store) DeliverablesFor(ctx context.Context, contractID uuid.UUID) ([]Deliverable, error) {
	rows, err := s.db.Query(ctx, `
		SELECT d.id, d.milestone_id, d.kind, d.title, coalesce(d.detail, ''),
		       d.file_id, coalesce(d.url, ''), d.accepted_at, d.created_at,
		       u.id, u.username, u.full_name,
		       f.original_name, f.byte_size, f.detected_mime
		FROM deliverables d
		JOIN users u ON u.id = d.submitted_by
		LEFT JOIN files f ON f.id = d.file_id AND f.deleted_at IS NULL
		WHERE d.contract_id = $1
		ORDER BY d.created_at`, contractID)
	if err != nil {
		return nil, fmt.Errorf("query deliverables: %w", err)
	}
	defer rows.Close()

	out := []Deliverable{}
	for rows.Next() {
		var d Deliverable
		var submitter PartyRef
		var name, mime *string
		var size *int64
		if err := rows.Scan(&d.ID, &d.MilestoneID, &d.Kind, &d.Title, &d.Detail,
			&d.FileID, &d.URL, &d.AcceptedAt, &d.CreatedAt,
			&submitter.ID, &submitter.Username, &submitter.FullName,
			&name, &size, &mime); err != nil {
			return nil, err
		}
		d.SubmittedBy = &submitter
		d.FileName, d.FileByteSize, d.FileMIME = deref(name), size, deref(mime)
		out = append(out, d)
	}
	return out, rows.Err()
}

// AcceptDeliverables marks a milestone's hand-overs accepted, which is what an
// approval means for the files themselves.
func (s *Store) AcceptDeliverables(ctx context.Context, milestoneID uuid.UUID) error {
	_, err := s.db.Exec(ctx, `
		UPDATE deliverables SET accepted_at = now()
		WHERE milestone_id = $1 AND accepted_at IS NULL`, milestoneID)
	return err
}

// ConversationFor returns the workspace thread id for a contract.
func (s *Store) ConversationFor(ctx context.Context, contractID uuid.UUID) (uuid.UUID, error) {
	var id uuid.UUID
	err := s.db.QueryRow(ctx,
		`SELECT id FROM conversations WHERE contract_id = $1`, contractID).Scan(&id)
	if database.IsNoRows(err) {
		return uuid.Nil, ErrNotFound
	}
	return id, err
}

// setShowcase records whether the client agrees to the work appearing on the
// developer's public profile once it is finished.
func (s *Store) setShowcase(ctx context.Context, contractID uuid.UUID, allowed bool) error {
	_, err := s.db.Exec(ctx,
		`UPDATE contracts SET client_allows_showcase = $2, updated_at = now() WHERE id = $1`,
		contractID, allowed)
	return err
}

// cancelOpenMilestones closes out the work a cancelled contract will not see.
func (s *Store) cancelOpenMilestones(ctx context.Context, contractID uuid.UUID) error {
	_, err := s.db.Exec(ctx, `
		UPDATE milestones SET status = 'cancelled', cancelled_at = now(), updated_at = now()
		WHERE contract_id = $1 AND status IN ('draft','funded','in_progress','revision_requested')`,
		contractID)
	return err
}

func (s *Store) userIDByUsername(ctx context.Context, username string) (uuid.UUID, error) {
	var id uuid.UUID
	err := s.db.QueryRow(ctx,
		`SELECT id FROM users WHERE username = $1 AND deleted_at IS NULL AND status = 'active'`,
		strings.ToLower(strings.TrimSpace(username))).Scan(&id)
	if database.IsNoRows(err) {
		return uuid.Nil, ErrNotFound
	}
	return id, err
}

// addConversationParticipant puts an observer on the workspace thread.
func (s *Store) addConversationParticipant(ctx context.Context, contractID, userID uuid.UUID) error {
	_, err := s.db.Exec(ctx, `
		INSERT INTO conversation_participants (conversation_id, user_id)
		SELECT id, $2 FROM conversations WHERE contract_id = $1
		ON CONFLICT DO NOTHING`, contractID, userID)
	return err
}

// fundingFacts reads a milestone with its contract in one query.
func (s *Store) fundingFacts(ctx context.Context, milestoneID uuid.UUID) (FundingFacts, error) {
	var f FundingFacts
	f.MilestoneID = milestoneID
	err := s.db.QueryRow(ctx, `
		SELECT m.title, m.status, m.amount_minor, m.currency,
		       c.id, c.reference, c.title, c.status, c.client_id, c.developer_id,
		       c.fee_percent
		FROM milestones m JOIN contracts c ON c.id = m.contract_id
		WHERE m.id = $1`, milestoneID).
		Scan(&f.MilestoneTitle, &f.MilestoneStatus, &f.AmountMinor, &f.Currency,
			&f.ContractID, &f.ContractReference, &f.ContractTitle, &f.ContractStatus,
			&f.ClientID, &f.DeveloperID, &f.FeePercent)
	if database.IsNoRows(err) {
		return f, ErrNotFound
	}
	if err != nil {
		return f, fmt.Errorf("load funding facts: %w", err)
	}
	return f, nil
}

// ── Helpers ─────────────────────────────────────────────────────────────────

func logWarn(ctx context.Context, message string, err error) {
	logx.From(ctx).Warn(message, "error", err)
}

func actorOrNil(id uuid.UUID) any {
	if id == uuid.Nil {
		return nil
	}
	return id
}

func nullIfBlank(s string) any {
	if strings.TrimSpace(s) == "" {
		return nil
	}
	return s
}

// nullUUID turns the zero id into SQL NULL. A contract that came from a
// service order has no proposal, and a zero uuid would violate the foreign key.
func nullUUID(id uuid.UUID) any {
	if id == uuid.Nil {
		return nil
	}
	return id
}

func nullIfZero(v int) any {
	if v == 0 {
		return nil
	}
	return v
}

func defaultTo(v, fallback string) string {
	if strings.TrimSpace(v) == "" {
		return fallback
	}
	return v
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}
