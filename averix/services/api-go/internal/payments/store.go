package payments

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/database"
)

type Store struct {
	db *database.DB
}

func NewStore(db *database.DB) *Store { return &Store{db: db} }

// NewIntent is a payment the platform is about to ask for.
type NewIntent struct {
	ContractID     *uuid.UUID
	MilestoneID    *uuid.UUID
	PayerID        uuid.UUID
	PayeeID        *uuid.UUID
	ProviderCode   string
	Direction      string
	AmountMinor    int64
	FeeMinor       int64
	Currency       string
	IdempotencyKey string
}

// StoredIntent is the row.
type StoredIntent struct {
	ID             uuid.UUID
	Reference      string
	ContractID     *uuid.UUID
	MilestoneID    *uuid.UUID
	PayerID        uuid.UUID
	PayeeID        *uuid.UUID
	ProviderCode   string
	Direction      string
	AmountMinor    int64
	FeeMinor       int64
	Currency       string
	Status         string
	ProviderRef    string
	ProviderMeta   map[string]any
	RefundedMinor  int64
	FailureMessage string
	CreatedAt      time.Time
	ConfirmedAt    *time.Time
}

// Create records an intent, or returns the existing one for the same key.
//
// The idempotency key is a unique index, so a double-clicked Pay button, a
// retried request and a duplicated webhook all converge on one charge rather
// than three. The caller is told which of the two happened, because a fresh
// intent needs the provider called and an existing one does not.
func (s *Store) Create(ctx context.Context, in NewIntent) (*StoredIntent, bool, error) {
	if existing, err := s.ByIdempotencyKey(ctx, in.ProviderCode, in.IdempotencyKey); err == nil {
		return existing, false, nil
	} else if !errors.Is(err, ErrNotFound) {
		return nil, false, err
	}

	reference, err := newReference(in.Direction)
	if err != nil {
		return nil, false, err
	}

	var id uuid.UUID
	err = s.db.QueryRow(ctx, `
		INSERT INTO payment_intents
		  (reference, contract_id, milestone_id, payer_id, payee_id, provider_code,
		   direction, amount_minor, fee_minor, currency, status, idempotency_key)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
		RETURNING id`,
		reference, in.ContractID, in.MilestoneID, in.PayerID, in.PayeeID,
		in.ProviderCode, in.Direction, in.AmountMinor, in.FeeMinor,
		strings.ToUpper(in.Currency), StatusCreated, in.IdempotencyKey).Scan(&id)
	if database.IsUniqueViolation(err) {
		// Another request won the race on the same key; its intent is the one.
		existing, lookupErr := s.ByIdempotencyKey(ctx, in.ProviderCode, in.IdempotencyKey)
		if lookupErr != nil {
			return nil, false, lookupErr
		}
		return existing, false, nil
	}
	if err != nil {
		return nil, false, fmt.Errorf("create payment intent: %w", err)
	}

	intent, err := s.ByID(ctx, id)
	return intent, true, err
}

// newReference is what a payer types into their bank's reference field.
//
// Short, unambiguous and case-insensitive to read back: an administrator
// matching a bank statement line to a milestone reads this off a screen.
func newReference(direction string) (string, error) {
	prefix := "PAY"
	switch direction {
	case DirectionPayout:
		prefix = "OUT"
	case DirectionRefund:
		prefix = "REF"
	}
	suffix, err := cryptox.RandomHex(4)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("%s-%s", prefix, strings.ToUpper(suffix)), nil
}

const intentSelect = `
	SELECT id, reference, contract_id, milestone_id, payer_id, payee_id,
	       provider_code, direction, amount_minor, fee_minor, currency, status,
	       coalesce(provider_ref, ''), provider_meta, refunded_minor,
	       coalesce(failure_message, ''), created_at, captured_at
	FROM payment_intents`

func (s *Store) scan(row interface{ Scan(...any) error }) (*StoredIntent, error) {
	var intent StoredIntent
	err := row.Scan(&intent.ID, &intent.Reference, &intent.ContractID, &intent.MilestoneID,
		&intent.PayerID, &intent.PayeeID, &intent.ProviderCode, &intent.Direction,
		&intent.AmountMinor, &intent.FeeMinor, &intent.Currency, &intent.Status,
		&intent.ProviderRef, &intent.ProviderMeta, &intent.RefundedMinor,
		&intent.FailureMessage, &intent.CreatedAt, &intent.ConfirmedAt)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("scan payment intent: %w", err)
	}
	return &intent, nil
}

func (s *Store) ByID(ctx context.Context, id uuid.UUID) (*StoredIntent, error) {
	return s.scan(s.db.QueryRow(ctx, intentSelect+" WHERE id = $1", id))
}

func (s *Store) ByReference(ctx context.Context, reference string) (*StoredIntent, error) {
	return s.scan(s.db.QueryRow(ctx, intentSelect+" WHERE reference = $1",
		strings.ToUpper(strings.TrimSpace(reference))))
}

func (s *Store) ByIdempotencyKey(ctx context.Context, providerCode, key string) (*StoredIntent, error) {
	return s.scan(s.db.QueryRow(ctx,
		intentSelect+" WHERE provider_code = $1 AND idempotency_key = $2", providerCode, key))
}

// ApplyResult records what a provider reported.
func (s *Store) ApplyResult(ctx context.Context, intentID uuid.UUID, result Result) error {
	timestamps := ""
	switch result.Status {
	case StatusHeld:
		timestamps = ", authorised_at = coalesce(authorised_at, now())"
	case StatusSucceeded:
		timestamps = ", captured_at = coalesce(captured_at, now())"
	}
	meta := result.Meta
	if meta == nil {
		meta = map[string]any{}
	}
	_, err := s.db.Exec(ctx, `
		UPDATE payment_intents
		   SET status = $2,
		       provider_ref = coalesce(nullif($3, ''), provider_ref),
		       provider_status = nullif($4, ''),
		       failure_code = nullif($5, ''),
		       failure_message = nullif($6, ''),
		       provider_meta = $7,
		       updated_at = now()`+timestamps+`
		 WHERE id = $1`,
		intentID, result.Status, result.ProviderRef, result.Status,
		result.FailureCode, result.FailureReason, meta)
	if err != nil {
		return fmt.Errorf("apply payment result: %w", err)
	}
	return nil
}

// Settle moves an intent to a terminal state, but only from the state the
// caller believed it was in.
//
// The expected status is part of the WHERE clause, so two administrators
// confirming the same transfer at the same moment cannot both succeed — the
// second is told it was already settled rather than funding a milestone twice.
func (s *Store) Settle(ctx context.Context, intentID uuid.UUID, from []string, to string) error {
	tag, err := s.db.Exec(ctx, `
		UPDATE payment_intents
		   SET status = $2, captured_at = coalesce(captured_at, now()),
		       released_at = CASE WHEN direction = 'payout' THEN now() ELSE released_at END,
		       updated_at = now()
		 WHERE id = $1 AND status = ANY($3)`, intentID, to, from)
	if err != nil {
		return fmt.Errorf("settle payment: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return ErrAlreadySettled
	}
	return nil
}

func (s *Store) Fail(ctx context.Context, intentID uuid.UUID, code, message string) error {
	_, err := s.db.Exec(ctx, `
		UPDATE payment_intents SET status = $2, failure_code = nullif($3, ''),
		       failure_message = nullif($4, ''), updated_at = now()
		 WHERE id = $1 AND status NOT IN ('succeeded','refunded')`,
		intentID, StatusFailed, code, message)
	return err
}

// RecordTransaction appends a movement. Append only: a provider's report is
// evidence, and evidence is not edited.
func (s *Store) RecordTransaction(ctx context.Context, intentID uuid.UUID, t Transaction) error {
	raw := t.Raw
	if raw == nil {
		raw = map[string]any{}
	}
	_, err := s.db.Exec(ctx, `
		INSERT INTO payment_transactions
		  (intent_id, kind, amount_minor, currency, provider_ref, provider_event_id,
		   occurred_at, raw)
		VALUES ($1,$2,$3,$4,$5,$6,coalesce($7, now()),$8)
		ON CONFLICT (provider_event_id) WHERE provider_event_id IS NOT NULL DO NOTHING`,
		intentID, t.Kind, t.AmountMinor, strings.ToUpper(t.Currency),
		nullIfBlank(t.ProviderRef), nullIfBlank(t.EventID), nullTime(t.OccurredAt), raw)
	if err != nil {
		return fmt.Errorf("record payment transaction: %w", err)
	}
	return nil
}

func (s *Store) TransactionsFor(ctx context.Context, intentID uuid.UUID) ([]Transaction, error) {
	rows, err := s.db.Query(ctx, `
		SELECT kind, amount_minor, currency, coalesce(provider_ref, ''),
		       coalesce(provider_event_id, ''), occurred_at, raw
		FROM payment_transactions WHERE intent_id = $1 ORDER BY occurred_at`, intentID)
	if err != nil {
		return nil, fmt.Errorf("query payment transactions: %w", err)
	}
	defer rows.Close()

	out := []Transaction{}
	for rows.Next() {
		var t Transaction
		if err := rows.Scan(&t.Kind, &t.AmountMinor, &t.Currency, &t.ProviderRef,
			&t.EventID, &t.OccurredAt, &t.Raw); err != nil {
			return nil, err
		}
		out = append(out, t)
	}
	return out, rows.Err()
}

// RecordRefund books a refund against a confirmed charge.
//
// The refunded total and the intent's status move together with the
// transaction row, so a refund can never be recorded without the money it
// claims to have returned, or counted twice past the original amount — the
// CHECK on refunded_minor makes the second case a database error rather than a
// quiet overdraft.
func (s *Store) RecordRefund(ctx context.Context, intentID uuid.UUID, amountMinor int64,
	result Result, confirmedBy, reason string) error {

	return s.db.InTx(ctx, func(q database.Querier) error {
		var refunded, total int64
		if err := q.QueryRow(ctx, `
			UPDATE payment_intents
			   SET refunded_minor = refunded_minor + $2,
			       status = CASE WHEN refunded_minor + $2 >= amount_minor
			                     THEN 'refunded' ELSE 'partially_refunded' END,
			       updated_at = now()
			 WHERE id = $1 AND status IN ('succeeded','partially_refunded')
			RETURNING refunded_minor, amount_minor`, intentID, amountMinor).
			Scan(&refunded, &total); err != nil {
			if database.IsNoRows(err) {
				return ErrAlreadySettled
			}
			return fmt.Errorf("apply refund: %w", err)
		}

		if _, err := q.Exec(ctx, `
			INSERT INTO payment_transactions
			  (intent_id, kind, amount_minor, currency, provider_ref, raw)
			SELECT $1, 'refund', $2, currency, $3, $4
			FROM payment_intents WHERE id = $1`,
			intentID, -amountMinor, nullIfBlank(result.ProviderRef),
			map[string]any{
				"confirmed_by": confirmedBy,
				"reason":       reason,
				"method":       "administrator_confirmation",
			}); err != nil {
			return fmt.Errorf("record refund transaction: %w", err)
		}
		return nil
	})
}

// ── Queues and lists ────────────────────────────────────────────────────────

// Pending lists what an administrator has to act on: transfers a client says
// they have sent, and payouts waiting to go out.
func (s *Store) Pending(ctx context.Context, direction string, limit int) ([]PendingItem, error) {
	if limit <= 0 || limit > 200 {
		limit = 50
	}
	filter := ""
	args := []any{limit}
	if direction != "" {
		filter = " AND pi.direction = $2"
		args = append(args, direction)
	}

	rows, err := s.db.Query(ctx, `
		SELECT pi.id, pi.reference, pi.direction, pi.amount_minor, pi.fee_minor,
		       pi.currency, pi.status, pi.created_at, pi.provider_code,
		       c.id, c.reference, c.title,
		       m.id, m.title,
		       payer.username, payer.full_name,
		       payee.username, payee.full_name
		FROM payment_intents pi
		LEFT JOIN contracts c ON c.id = pi.contract_id
		LEFT JOIN milestones m ON m.id = pi.milestone_id
		JOIN users payer ON payer.id = pi.payer_id
		LEFT JOIN users payee ON payee.id = pi.payee_id
		WHERE pi.status IN ('created','requires_action','processing','held')`+filter+`
		ORDER BY pi.created_at
		LIMIT $1`, args...)
	if err != nil {
		return nil, fmt.Errorf("query pending payments: %w", err)
	}
	defer rows.Close()

	out := []PendingItem{}
	for rows.Next() {
		var item PendingItem
		var contractID, milestoneID *uuid.UUID
		var contractRef, contractTitle, milestoneTitle *string
		var payeeUsername, payeeName *string
		if err := rows.Scan(&item.ID, &item.Reference, &item.Direction, &item.AmountMinor,
			&item.FeeMinor, &item.Currency, &item.Status, &item.CreatedAt, &item.Provider,
			&contractID, &contractRef, &contractTitle, &milestoneID, &milestoneTitle,
			&item.PayerUsername, &item.PayerName, &payeeUsername, &payeeName); err != nil {
			return nil, fmt.Errorf("scan pending payment: %w", err)
		}
		item.ContractID = contractID
		item.ContractReference = deref(contractRef)
		item.ContractTitle = deref(contractTitle)
		item.MilestoneID = milestoneID
		item.MilestoneTitle = deref(milestoneTitle)
		item.PayeeUsername = deref(payeeUsername)
		item.PayeeName = deref(payeeName)
		item.StatusLabel = StatusLabel(item.Direction, item.Status)
		out = append(out, item)
	}
	return out, rows.Err()
}

// PendingItem is one row of the administrator's queue.
type PendingItem struct {
	ID                uuid.UUID  `json:"id"`
	Reference         string     `json:"reference"`
	Direction         string     `json:"direction"`
	AmountMinor       int64      `json:"amount_minor"`
	FeeMinor          int64      `json:"fee_minor"`
	Currency          string     `json:"currency"`
	Status            string     `json:"status"`
	StatusLabel       string     `json:"status_label"`
	Provider          string     `json:"provider"`
	ContractID        *uuid.UUID `json:"contract_id,omitempty"`
	ContractReference string     `json:"contract_reference,omitempty"`
	ContractTitle     string     `json:"contract_title,omitempty"`
	MilestoneID       *uuid.UUID `json:"milestone_id,omitempty"`
	MilestoneTitle    string     `json:"milestone_title,omitempty"`
	PayerUsername     string     `json:"payer_username"`
	PayerName         string     `json:"payer_name"`
	PayeeUsername     string     `json:"payee_username,omitempty"`
	PayeeName         string     `json:"payee_name,omitempty"`
	CreatedAt         time.Time  `json:"created_at"`
}

// ForContract lists a contract's payments, for the two parties.
func (s *Store) ForContract(ctx context.Context, contractID uuid.UUID) ([]*StoredIntent, error) {
	rows, err := s.db.Query(ctx,
		intentSelect+" WHERE contract_id = $1 ORDER BY created_at", contractID)
	if err != nil {
		return nil, fmt.Errorf("query contract payments: %w", err)
	}
	defer rows.Close()

	out := []*StoredIntent{}
	for rows.Next() {
		intent, err := s.scan(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, intent)
	}
	return out, rows.Err()
}

// ── Ledger ──────────────────────────────────────────────────────────────────

// LedgerEntry is one movement on a developer's balance.
type LedgerEntry struct {
	UserID      uuid.UUID
	IntentID    *uuid.UUID
	ContractID  *uuid.UUID
	Kind        string
	AmountMinor int64
	Currency    string
	Description string
}

// AppendLedger writes entries and keeps the running balance correct.
//
// The balance is computed inside the same transaction as the insert, and the
// user's rows are locked while it happens: two concurrent releases would
// otherwise both read the same starting balance and write two rows claiming
// the same balance_after.
func (s *Store) AppendLedger(ctx context.Context, entries ...LedgerEntry) error {
	if len(entries) == 0 {
		return nil
	}
	return s.db.InTx(ctx, func(q database.Querier) error {
		for _, entry := range entries {
			currency := strings.ToUpper(entry.Currency)
			// One writer per user and currency for the length of the
			// transaction. A row lock cannot do this job: the balance is an
			// aggregate, and two concurrent releases would otherwise both read
			// the same total and write two rows claiming the same
			// balance_after — which is how a ledger stops adding up.
			if _, err := q.Exec(ctx,
				`SELECT pg_advisory_xact_lock(hashtextextended($1 || ':' || $2, 0))`,
				entry.UserID.String(), currency); err != nil {
				return fmt.Errorf("lock ledger: %w", err)
			}

			var balance int64
			if err := q.QueryRow(ctx, `
				SELECT coalesce(sum(amount_minor), 0) FROM ledger_entries
				WHERE user_id = $1 AND currency = $2`,
				entry.UserID, currency).Scan(&balance); err != nil {
				return fmt.Errorf("read ledger balance: %w", err)
			}
			if _, err := q.Exec(ctx, `
				INSERT INTO ledger_entries
				  (user_id, intent_id, contract_id, kind, amount_minor, currency,
				   balance_after_minor, description)
				VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`,
				entry.UserID, entry.IntentID, entry.ContractID, entry.Kind,
				entry.AmountMinor, currency,
				balance+entry.AmountMinor, nullIfBlank(entry.Description)); err != nil {
				return fmt.Errorf("append ledger entry: %w", err)
			}
		}
		return nil
	})
}

// BalanceFor totals a developer's ledger.
func (s *Store) BalanceFor(ctx context.Context, userID uuid.UUID, currency string) (Balance, error) {
	balance := Balance{Currency: strings.ToUpper(currency)}
	err := s.db.QueryRow(ctx, `
		SELECT coalesce(sum(amount_minor), 0),
		       coalesce(sum(amount_minor) FILTER (WHERE kind = 'earning'), 0),
		       coalesce(-sum(amount_minor) FILTER (WHERE kind = 'fee'), 0)
		FROM ledger_entries WHERE user_id = $1 AND currency = $2`,
		userID, balance.Currency).
		Scan(&balance.AvailableMinor, &balance.LifetimeMinor, &balance.FeesMinor)
	if err != nil {
		return balance, fmt.Errorf("read balance: %w", err)
	}

	// Pending is work that is approved but whose payout has not been confirmed
	// yet — money the developer has earned and not received.
	err = s.db.QueryRow(ctx, `
		SELECT coalesce(sum(amount_minor - fee_minor), 0)
		FROM payment_intents
		WHERE payee_id = $1 AND currency = $2 AND direction = 'payout'
		  AND status IN ('created','requires_action','processing','held')`,
		userID, balance.Currency).Scan(&balance.PendingMinor)
	if err != nil {
		return balance, fmt.Errorf("read pending payouts: %w", err)
	}
	return balance, nil
}

func (s *Store) LedgerFor(ctx context.Context, userID uuid.UUID, currency string, limit int) ([]Entry, error) {
	if limit <= 0 || limit > 200 {
		limit = 50
	}
	rows, err := s.db.Query(ctx, `
		SELECT id, kind, amount_minor, currency, balance_after_minor,
		       coalesce(description, ''), contract_id, created_at
		FROM ledger_entries
		WHERE user_id = $1 AND currency = $2
		ORDER BY created_at DESC LIMIT $3`, userID, strings.ToUpper(currency), limit)
	if err != nil {
		return nil, fmt.Errorf("query ledger: %w", err)
	}
	defer rows.Close()

	out := []Entry{}
	for rows.Next() {
		var entry Entry
		if err := rows.Scan(&entry.ID, &entry.Kind, &entry.AmountMinor, &entry.Currency,
			&entry.BalanceAfterMinor, &entry.Description, &entry.ContractID,
			&entry.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, entry)
	}
	return out, rows.Err()
}

// ── Providers and fees ──────────────────────────────────────────────────────

// SyncProvider records what this build can actually do with a provider, so the
// admin panel reads the same truth the code enforces.
func (s *Store) SyncProvider(ctx context.Context, code string, configured bool,
	capabilities []string, currencies []string) error {

	_, err := s.db.Exec(ctx, `
		UPDATE payment_providers
		   SET is_configured = $2, capabilities = $3, supported_currencies = $4,
		       updated_at = now()
		 WHERE code = $1`, code, configured,
		database.Array[string](capabilities), database.Array[string](currencies))
	return err
}

func (s *Store) SetEnabled(ctx context.Context, code string, enabled bool) error {
	tag, err := s.db.Exec(ctx,
		`UPDATE payment_providers SET is_enabled = $2, updated_at = now() WHERE code = $1`,
		code, enabled)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

// ProviderRow is what the admin panel shows about a provider.
type ProviderRow struct {
	Code         string   `json:"code"`
	DisplayName  string   `json:"display_name"`
	IsConfigured bool     `json:"is_configured"`
	IsEnabled    bool     `json:"is_enabled"`
	Capabilities []string `json:"capabilities"`
	Currencies   []string `json:"supported_currencies"`
	ConfigNote   string   `json:"config_note,omitempty"`
}

func (s *Store) Providers(ctx context.Context) ([]ProviderRow, error) {
	rows, err := s.db.Query(ctx, `
		SELECT code, display_name, is_configured, is_enabled, capabilities,
		       supported_currencies, coalesce(config_note, '')
		FROM payment_providers ORDER BY code`)
	if err != nil {
		return nil, fmt.Errorf("query payment providers: %w", err)
	}
	defer rows.Close()

	out := []ProviderRow{}
	for rows.Next() {
		var row ProviderRow
		if err := rows.Scan(&row.Code, &row.DisplayName, &row.IsConfigured,
			&row.IsEnabled, &row.Capabilities, &row.Currencies, &row.ConfigNote); err != nil {
			return nil, err
		}
		out = append(out, row)
	}
	return out, rows.Err()
}

// FeeFor resolves the platform fee for an amount from the schedule.
//
// The highest band at or below the amount wins, which is what "8% above
// $2,000" means. The result is snapshotted onto the contract at signature, so
// changing the schedule never rewrites a signed deal.
func (s *Store) FeeFor(ctx context.Context, amountMinor int64, currency string) (float64, int64, error) {
	var percent float64
	var flat int64
	err := s.db.QueryRow(ctx, `
		SELECT percent, flat_minor FROM fee_schedules
		WHERE is_active AND currency = $1 AND from_minor <= $2
		  AND effective_from <= now()
		ORDER BY from_minor DESC LIMIT 1`, strings.ToUpper(currency), amountMinor).
		Scan(&percent, &flat)
	if database.IsNoRows(err) {
		return 0, 0, nil
	}
	if err != nil {
		return 0, 0, fmt.Errorf("resolve fee: %w", err)
	}
	// Integer arithmetic on minor units: a float percentage of money is how
	// rounding errors become accounting disputes.
	fee := amountMinor*int64(percent*100)/10000 + flat
	if fee < 0 {
		fee = 0
	}
	if fee > amountMinor {
		fee = amountMinor
	}
	return percent, fee, nil
}

// ── Webhooks ────────────────────────────────────────────────────────────────

// RecordWebhook stores a delivery before anything acts on it, verified or not.
//
// A rejected signature is kept deliberately: a run of them is the signal that
// someone is probing the endpoint, and that is worth being able to see.
func (s *Store) RecordWebhook(ctx context.Context, providerCode, eventID, eventType string,
	valid bool, detail string, payload []byte) (uuid.UUID, bool, error) {

	var id uuid.UUID
	err := s.db.QueryRow(ctx, `
		INSERT INTO payment_webhook_events
		  (provider_code, provider_event_id, event_type, signature_valid,
		   signature_detail, payload)
		VALUES ($1,$2,$3,$4,$5,$6)
		RETURNING id`,
		providerCode, nullIfBlank(eventID), nullIfBlank(eventType), valid,
		nullIfBlank(detail), payload).Scan(&id)
	if database.IsUniqueViolation(err) {
		// A replayed delivery. Recording it once is enough; acting on it twice
		// is what the unique index exists to prevent.
		return uuid.Nil, false, nil
	}
	if err != nil {
		return uuid.Nil, false, fmt.Errorf("record webhook: %w", err)
	}
	return id, true, nil
}

func (s *Store) MarkWebhookProcessed(ctx context.Context, id uuid.UUID, processErr error) error {
	detail := ""
	if processErr != nil {
		detail = processErr.Error()
	}
	_, err := s.db.Exec(ctx, `
		UPDATE payment_webhook_events SET processed_at = now(), process_error = nullif($2, '')
		WHERE id = $1`, id, detail)
	return err
}

func nullIfBlank(s string) any {
	if strings.TrimSpace(s) == "" {
		return nil
	}
	return s
}

func nullTime(t time.Time) any {
	if t.IsZero() {
		return nil
	}
	return t
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}
