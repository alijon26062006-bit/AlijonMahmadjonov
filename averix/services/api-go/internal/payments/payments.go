// Package payments orchestrates money without ever holding it.
//
// AVERIX is not a payment institution and makes no escrow claim. What this
// package owns is the platform's own ledger: what was asked for, what a
// provider (or an administrator) reported back, and what a developer has
// earned. The movement of funds happens elsewhere — through a gateway when one
// is configured, or through a bank transfer an administrator confirms when one
// is not.
//
// The Provider interface is the seam. Nothing above it knows which provider is
// in use, so adding a gateway later is a new file here rather than a change to
// contracts, milestones or the workspace.
package payments

import (
	"context"
	"errors"
	"time"

	"github.com/google/uuid"
)

// Provider is one way for money to move.
//
// Deliberately small and deliberately about intent rather than mechanics: a
// provider is asked to charge, to pay out, to refund, and to say what happened.
// Anything provider-specific — redirect flows, hosted fields, webhooks — lives
// behind these five calls.
type Provider interface {
	Code() string
	DisplayName() string
	// Configured reports whether this provider can actually be used in this
	// environment. A provider that is present but unconfigured is shown as a
	// configuration state, never as a dead button.
	Configured() bool
	// Capabilities is what the product may honestly say about it. A provider
	// without "hold" must never be described to a user as escrow.
	Capabilities() []string
	SupportedCurrencies() []string

	CreatePayment(ctx context.Context, in Request) (Result, error)
	GetStatus(ctx context.Context, intent Intent) (Result, error)
	Release(ctx context.Context, intent Intent) (Result, error)
	Refund(ctx context.Context, intent Intent, amountMinor int64, reason string) (Result, error)
	GetTransaction(ctx context.Context, providerRef string) (Transaction, error)
}

// WebhookVerifier is implemented by providers that call back.
//
// Separate from Provider because a provider that has no webhooks should not
// have to pretend it verifies them, and the endpoint can tell the difference.
type WebhookVerifier interface {
	// VerifyWebhook checks the signature over the raw body. It must return an
	// error for anything it cannot prove, and it must never be skipped.
	VerifyWebhook(header map[string][]string, body []byte) (eventID, eventType string, err error)
}

// Direction of an intent.
const (
	DirectionCharge = "charge"
	DirectionPayout = "payout"
	DirectionRefund = "refund"
)

// Intent statuses, matching the database's CHECK constraint.
const (
	StatusCreated           = "created"
	StatusRequiresAction    = "requires_action"
	StatusProcessing        = "processing"
	StatusHeld              = "held"
	StatusSucceeded         = "succeeded"
	StatusFailed            = "failed"
	StatusCancelled         = "cancelled"
	StatusRefunded          = "refunded"
	StatusPartiallyRefunded = "partially_refunded"
)

// Capabilities a provider may declare.
const (
	CapabilityCharge  = "charge"
	CapabilityPayout  = "payout"
	CapabilityRefund  = "refund"
	CapabilityHold    = "hold"
	CapabilityWebhook = "webhook"
)

// Request is what the platform asks a provider to do.
type Request struct {
	Reference   string
	Direction   string
	AmountMinor int64
	Currency    string
	// Who pays and who is paid. A payout has no payer beyond the platform.
	PayerID uuid.UUID
	PayeeID uuid.UUID
	// What this is for, so an administrator confirming a bank transfer can see
	// which contract it belongs to without opening three screens.
	ContractReference string
	Description       string
	// The key that makes a retry safe. Derived from the milestone, so a
	// double-clicked button cannot create two charges.
	IdempotencyKey string
}

// Intent is a stored payment intent, as a provider sees it.
type Intent struct {
	ID          uuid.UUID
	Reference   string
	Direction   string
	AmountMinor int64
	Currency    string
	Status      string
	ProviderRef string
}

// Result is what a provider reports.
type Result struct {
	Status      string
	ProviderRef string
	// Where the payer must be sent, when the provider needs a redirect.
	RedirectURL string
	// What the payer has to do, in plain language, when the provider is manual.
	Instructions []Instruction
	// Free-form, already redacted of anything secret.
	Meta          map[string]any
	FailureCode   string
	FailureReason string
	OccurredAt    time.Time
}

// Instruction is one line of "here is how to pay".
type Instruction struct {
	Label string `json:"label"`
	Value string `json:"value"`
	// Whether the value is the one that must be copied exactly — the payment
	// reference, usually — so the interface can emphasise it.
	Critical bool `json:"critical,omitempty"`
}

// Transaction is one movement a provider reported.
type Transaction struct {
	Kind        string
	AmountMinor int64
	Currency    string
	ProviderRef string
	EventID     string
	OccurredAt  time.Time
	Raw         map[string]any
}

var (
	ErrNotFound        = errors.New("payment not found")
	ErrNotSupported    = errors.New("this provider does not support that operation")
	ErrNotConfigured   = errors.New("no payment provider is configured")
	ErrAlreadySettled  = errors.New("this payment has already been settled")
	ErrAmountMismatch  = errors.New("the confirmed amount does not match the payment")
	ErrWebhookRejected = errors.New("webhook signature could not be verified")
)

// Registry holds the providers this build knows about.
//
// The manual provider is always registered: an environment with no gateway
// still has to be able to run a marketplace, and "an administrator confirms
// the transfer" is a real answer rather than a placeholder.
type Registry struct {
	providers map[string]Provider
	order     []string
}

func NewRegistry(providers ...Provider) *Registry {
	r := &Registry{providers: map[string]Provider{}}
	for _, provider := range providers {
		r.providers[provider.Code()] = provider
		r.order = append(r.order, provider.Code())
	}
	return r
}

func (r *Registry) Get(code string) (Provider, bool) {
	provider, ok := r.providers[code]
	return provider, ok
}

// Active returns the provider the platform should use.
//
// The preferred code comes from settings; anything unconfigured falls through
// to the next one, and the manual provider is the floor.
func (r *Registry) Active(preferred string) (Provider, bool) {
	if provider, ok := r.providers[preferred]; ok && provider.Configured() {
		return provider, true
	}
	for _, code := range r.order {
		if provider := r.providers[code]; provider.Configured() {
			return provider, true
		}
	}
	return nil, false
}

// All lists every provider with its configuration state, for the admin panel.
func (r *Registry) All() []Provider {
	out := make([]Provider, 0, len(r.order))
	for _, code := range r.order {
		out = append(out, r.providers[code])
	}
	return out
}

// ── API shapes ──────────────────────────────────────────────────────────────

// Payment is one intent as the product shows it.
type Payment struct {
	ID          uuid.UUID  `json:"id"`
	Reference   string     `json:"reference"`
	ContractID  *uuid.UUID `json:"contract_id,omitempty"`
	MilestoneID *uuid.UUID `json:"milestone_id,omitempty"`
	Direction   string     `json:"direction"`
	AmountMinor int64      `json:"amount_minor"`
	FeeMinor    int64      `json:"fee_minor"`
	Currency    string     `json:"currency"`
	Status      string     `json:"status"`
	Provider    string     `json:"provider"`
	// Plain-language state for a person, because "requires_action" is not a
	// sentence: "Waiting for your transfer", "Waiting for confirmation".
	StatusLabel  string        `json:"status_label"`
	Instructions []Instruction `json:"instructions,omitempty"`
	RedirectURL  string        `json:"redirect_url,omitempty"`
	// Present only for the payer, the payee and staff.
	RefundedMinor int64      `json:"refunded_minor,omitempty"`
	CreatedAt     time.Time  `json:"created_at"`
	ConfirmedAt   *time.Time `json:"confirmed_at,omitempty"`
	FailureReason string     `json:"failure_reason,omitempty"`
}

// Balance is a developer's own money. Never public, never on a profile, never
// in a card: only the owner and an administrator can reach it.
type Balance struct {
	Currency       string  `json:"currency"`
	AvailableMinor int64   `json:"available_minor"`
	PendingMinor   int64   `json:"pending_minor"`
	LifetimeMinor  int64   `json:"lifetime_minor"`
	FeesMinor      int64   `json:"fees_minor"`
	Entries        []Entry `json:"entries,omitempty"`
}

// Entry is one line of the developer's ledger.
type Entry struct {
	ID                uuid.UUID  `json:"id"`
	Kind              string     `json:"kind"`
	AmountMinor       int64      `json:"amount_minor"`
	Currency          string     `json:"currency"`
	BalanceAfterMinor int64      `json:"balance_after_minor"`
	Description       string     `json:"description,omitempty"`
	ContractID        *uuid.UUID `json:"contract_id,omitempty"`
	CreatedAt         time.Time  `json:"created_at"`
}

// Ledger entry kinds.
const (
	EntryEarning    = "earning"
	EntryFee        = "fee"
	EntryPayout     = "payout"
	EntryRefund     = "refund"
	EntryAdjustment = "adjustment"
)

// StatusLabel turns an intent's state into something a person can read.
func StatusLabel(direction, status string) string {
	switch status {
	case StatusCreated, StatusRequiresAction:
		if direction == DirectionCharge {
			return "Waiting for your transfer"
		}
		return "Queued for payout"
	case StatusProcessing:
		if direction == DirectionCharge {
			return "Waiting for confirmation"
		}
		return "Payout being sent"
	case StatusHeld:
		return "Funds held"
	case StatusSucceeded:
		if direction == DirectionCharge {
			return "Funded"
		}
		return "Paid"
	case StatusFailed:
		return "Failed"
	case StatusCancelled:
		return "Cancelled"
	case StatusRefunded:
		return "Refunded"
	case StatusPartiallyRefunded:
		return "Partly refunded"
	}
	return status
}
