package payments

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/averix/api/internal/platform/money"
)

// Manual is the provider for environments with no gateway.
//
// It is not a stub. The money really moves — by bank transfer, between the two
// people — and AVERIX records the intent, shows the payer exactly what to send
// and with which reference, and waits for an administrator to confirm that the
// transfer arrived before a milestone counts as funded.
//
// What this deliberately does NOT do is claim to hold anything. There is no
// escrow here: the platform records and reconciles, a person confirms, and the
// product says so in those words wherever a client is asked to pay.
type Manual struct {
	// Where a client should send money, read from platform settings on every
	// use rather than captured at start-up: a bank account changes as an
	// operational act, and the next payer must see the new details without a
	// redeployment. Without them the provider reports itself unconfigured,
	// because instructions with no account number are not instructions.
	read func(context.Context) ManualSettings
}

// ManualSettings is what an administrator fills in once, in the admin panel.
type ManualSettings struct {
	AccountName   string
	AccountNumber string
	BankName      string
	// IBAN, SWIFT, a card number, a wallet address — whatever this market
	// actually uses. Free text so the product is not opinionated about one
	// country's banking.
	ExtraLabel string
	ExtraValue string
	Note       string
	Currencies []string
}

func NewManual(read func(context.Context) ManualSettings) *Manual {
	if read == nil {
		read = func(context.Context) ManualSettings { return ManualSettings{} }
	}
	return &Manual{read: read}
}

func (m *Manual) current(ctx context.Context) ManualSettings {
	settings := m.read(ctx)
	if len(settings.Currencies) == 0 {
		settings.Currencies = []string{"USD", "EUR"}
	}
	return settings
}

func (m *Manual) Code() string        { return "manual" }
func (m *Manual) DisplayName() string { return "Manual bank transfer" }

// Configured reports whether an administrator has actually entered the details
// a payer would need. Without them the product shows a configuration state
// instead of asking someone to transfer money to nowhere.
func (m *Manual) Configured() bool {
	settings := m.current(context.Background())
	return strings.TrimSpace(settings.AccountName) != "" &&
		(strings.TrimSpace(settings.AccountNumber) != "" ||
			strings.TrimSpace(settings.ExtraValue) != "")
}

// Capabilities deliberately omits "hold". A bank transfer between two people
// is not escrow, and the product must never describe it as such.
func (m *Manual) Capabilities() []string {
	return []string{CapabilityCharge, CapabilityPayout, CapabilityRefund}
}

func (m *Manual) SupportedCurrencies() []string {
	return m.current(context.Background()).Currencies
}

// CreatePayment records what the payer has to do.
//
// The status is requires_action rather than processing: the platform is
// waiting on a human, and saying so is what keeps the client's screen honest.
func (m *Manual) CreatePayment(ctx context.Context, in Request) (Result, error) {
	if !m.Configured() {
		return Result{}, fmt.Errorf("%w: transfer details have not been set up", ErrNotConfigured)
	}

	switch in.Direction {
	case DirectionCharge:
		return Result{
			Status:       StatusRequiresAction,
			ProviderRef:  in.Reference,
			Instructions: m.instructions(ctx, in),
			OccurredAt:   time.Now().UTC(),
			Meta: map[string]any{
				"method": "bank_transfer",
				"note":   "Awaiting an administrator's confirmation that the transfer arrived.",
			},
		}, nil
	case DirectionPayout:
		// A payout is queued for an administrator to send. Nothing is claimed
		// to have been paid until they confirm it.
		return Result{
			Status:      StatusProcessing,
			ProviderRef: in.Reference,
			OccurredAt:  time.Now().UTC(),
			Meta: map[string]any{
				"method": "bank_transfer",
				"note":   "Queued for an administrator to send and confirm.",
			},
		}, nil
	case DirectionRefund:
		return Result{
			Status:      StatusProcessing,
			ProviderRef: in.Reference,
			OccurredAt:  time.Now().UTC(),
			Meta:        map[string]any{"method": "bank_transfer"},
		}, nil
	}
	return Result{}, fmt.Errorf("%w: direction %q", ErrNotSupported, in.Direction)
}

// instructions render what the payer has to do, in the order they will do it.
func (m *Manual) instructions(ctx context.Context, in Request) []Instruction {
	settings := m.current(ctx)
	out := []Instruction{
		{Label: "Сумма", Value: formatMoney(in.AmountMinor, in.Currency), Critical: true},
		// The reference is what lets an administrator match an anonymous bank
		// line to this milestone. It is the one field that must be exact.
		{Label: "Номер платежа", Value: in.Reference, Critical: true},
		{Label: "Получатель", Value: settings.AccountName},
	}
	if settings.AccountNumber != "" {
		out = append(out, Instruction{Label: "Счёт или карта", Value: settings.AccountNumber})
	}
	if settings.BankName != "" {
		out = append(out, Instruction{Label: "Банк", Value: settings.BankName})
	}
	if settings.ExtraLabel != "" && settings.ExtraValue != "" {
		out = append(out, Instruction{Label: settings.ExtraLabel, Value: settings.ExtraValue})
	}
	if in.ContractReference != "" {
		out = append(out, Instruction{Label: "Сделка", Value: in.ContractReference})
	}
	if settings.Note != "" {
		out = append(out, Instruction{Label: "Примечание", Value: settings.Note})
	}
	return out
}

// GetStatus has nothing external to ask. The stored status is the truth,
// because with this provider the platform's own record is the only record —
// which is exactly why confirmations are restricted and audited.
func (m *Manual) GetStatus(ctx context.Context, intent Intent) (Result, error) {
	return Result{
		Status:      intent.Status,
		ProviderRef: intent.ProviderRef,
		OccurredAt:  time.Now().UTC(),
	}, nil
}

// Release queues a payout. It does not pay: a person sends the money and
// confirms it, and only that confirmation marks the milestone released.
func (m *Manual) Release(ctx context.Context, intent Intent) (Result, error) {
	if !m.Configured() {
		return Result{}, ErrNotConfigured
	}
	return Result{
		Status:      StatusProcessing,
		ProviderRef: intent.ProviderRef,
		OccurredAt:  time.Now().UTC(),
		Meta:        map[string]any{"note": "Queued for an administrator to send."},
	}, nil
}

func (m *Manual) Refund(ctx context.Context, intent Intent, amountMinor int64, reason string) (Result, error) {
	if amountMinor <= 0 || amountMinor > intent.AmountMinor {
		return Result{}, ErrAmountMismatch
	}
	return Result{
		Status:      StatusProcessing,
		ProviderRef: intent.ProviderRef,
		OccurredAt:  time.Now().UTC(),
		Meta:        map[string]any{"reason": reason},
	}, nil
}

// GetTransaction has no external ledger to read. Returning "not supported"
// rather than an invented transaction is the honest answer, and the caller
// falls back to the platform's own records.
func (m *Manual) GetTransaction(ctx context.Context, providerRef string) (Transaction, error) {
	return Transaction{}, fmt.Errorf("%w: the manual provider has no external ledger", ErrNotSupported)
}

func formatMoney(minor int64, currency string) string {
	return money.Format(minor, currency)
}
