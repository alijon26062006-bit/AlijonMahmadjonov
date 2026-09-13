package payments

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/contracts"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/logx"
	"github.com/averix/api/internal/platform/validate"
	"github.com/averix/api/internal/security"
)

// Contracts is the part of the contracts module this one drives.
type Contracts interface {
	FundingFacts(ctx context.Context, milestoneID uuid.UUID) (contracts.FundingFacts, error)
	EnsureParty(ctx context.Context, id *security.Identity, contractID uuid.UUID) (string, error)
	MarkFunded(ctx context.Context, milestoneID uuid.UUID) error
	MarkReleased(ctx context.Context, milestoneID uuid.UUID) error
}

// Settings is the runtime configuration read here, including the manual
// provider's transfer details.
type Settings interface {
	String(ctx context.Context, key, fallback string) string
	Int(ctx context.Context, key string, fallback int) int
	Bool(ctx context.Context, key string, fallback bool) bool
	Set(ctx context.Context, key string, value any, by uuid.UUID) error
}

// Notifier tells someone money moved. Nil until notifications are wired.
type Notifier interface {
	PaymentConfirmed(ctx context.Context, recipientID, contractID uuid.UUID,
		amountMinor int64, currency, kind string)
}

type Service struct {
	store     *Store
	registry  *Registry
	contracts Contracts
	audit     *audit.Recorder
	settings  Settings
	notifier  Notifier
}

func NewService(store *Store, registry *Registry, contractsService Contracts,
	rec *audit.Recorder, settings Settings, notifier Notifier) *Service {

	return &Service{
		store: store, registry: registry, contracts: contractsService,
		audit: rec, settings: settings, notifier: notifier,
	}
}

// Configured reports whether money can move in this environment at all.
//
// This is what the contracts module asks before offering a Fund button, and
// what the client screen uses to show a configuration state instead.
func (s *Service) Configured() bool {
	_, ok := s.registry.Active(s.preferredCode())
	return ok
}

func (s *Service) preferredCode() string {
	if s.settings == nil {
		return "manual"
	}
	return s.settings.String(context.Background(), "payments.provider", "manual")
}

func (s *Service) active(ctx context.Context) (Provider, error) {
	preferred := "manual"
	if s.settings != nil {
		preferred = s.settings.String(ctx, "payments.provider", "manual")
	}
	provider, ok := s.registry.Active(preferred)
	if !ok {
		e := *httpx.ErrNotConfigured
		e.Code = "payments_not_configured"
		e.Message = "Платежи пока не настроены: администратор ещё не указал реквизиты для перевода."
		return nil, &e
	}
	return provider, nil
}

// SyncProviders records what this build can do with each provider, so the
// admin panel shows the same truth the code enforces rather than a list of
// hopes from a migration.
func (s *Service) SyncProviders(ctx context.Context) {
	for _, provider := range s.registry.All() {
		if err := s.store.SyncProvider(ctx, provider.Code(), provider.Configured(),
			provider.Capabilities(), provider.SupportedCurrencies()); err != nil {
			logx.From(ctx).Warn("payments: could not record the provider state",
				"provider", provider.Code(), "error", err)
		}
	}
}

// ── Funding ─────────────────────────────────────────────────────────────────

// Fund starts the payment for a milestone.
//
// With the manual provider this does not move money: it records what the
// client owes, hands back the transfer details and the reference to quote,
// and waits. The milestone becomes funded only when an administrator confirms
// the transfer arrived — which is the honest shape of a platform that does not
// hold funds.
func (s *Service) Fund(ctx context.Context, id *security.Identity, milestoneID uuid.UUID) (*Payment, error) {
	facts, err := s.contracts.FundingFacts(ctx, milestoneID)
	if err != nil {
		return nil, httpx.NotFoundf("milestone %s does not exist", milestoneID)
	}
	role, err := s.contracts.EnsureParty(ctx, id, facts.ContractID)
	if err != nil {
		return nil, err
	}
	if role != contracts.RoleClient {
		e := *httpx.ErrForbidden
		e.Code = "not_your_move"
		e.Message = "Оплачивает этап только заказчик."
		return nil, &e
	}
	if facts.MilestoneStatus != contracts.MilestoneDraft {
		e := *httpx.ErrConflict
		e.Code = "milestone_state"
		e.Message = "Этот этап уже оплачен."
		return nil, &e
	}

	provider, err := s.active(ctx)
	if err != nil {
		return nil, err
	}

	// The amount comes from the milestone, never from the request: a client
	// who could name their own figure could fund a $5,000 milestone with $5.
	intent, created, err := s.store.Create(ctx, NewIntent{
		ContractID:   &facts.ContractID,
		MilestoneID:  &milestoneID,
		PayerID:      facts.ClientID,
		PayeeID:      &facts.DeveloperID,
		ProviderCode: provider.Code(),
		Direction:    DirectionCharge,
		AmountMinor:  facts.AmountMinor,
		FeeMinor:     feeFor(facts.AmountMinor, facts.FeePercent),
		Currency:     facts.Currency,
		// Derived from the milestone, so a double-clicked button, a retry and
		// a refreshed page all land on the same charge.
		IdempotencyKey: "milestone:" + milestoneID.String() + ":charge",
	})
	if err != nil {
		return nil, httpx.Internalf(err, "create payment intent")
	}

	if created {
		result, err := provider.CreatePayment(ctx, Request{
			Reference:         intent.Reference,
			Direction:         DirectionCharge,
			AmountMinor:       intent.AmountMinor,
			Currency:          intent.Currency,
			PayerID:           facts.ClientID,
			PayeeID:           facts.DeveloperID,
			ContractReference: facts.ContractReference,
			Description:       facts.ContractTitle + " — " + facts.MilestoneTitle,
			IdempotencyKey:    "milestone:" + milestoneID.String() + ":charge",
		})
		if err != nil {
			_ = s.store.Fail(ctx, intent.ID, "provider_error", err.Error())
			if errors.Is(err, ErrNotConfigured) {
				e := *httpx.ErrNotConfigured
				e.Code = "payments_not_configured"
				e.Message = "Платежи на площадке пока не настроены."
				return nil, &e
			}
			return nil, httpx.Internalf(err, "start payment")
		}
		if err := s.store.ApplyResult(ctx, intent.ID, result); err != nil {
			return nil, httpx.Internalf(err, "record payment result")
		}
		intent.Status = result.Status
		intent.ProviderRef = result.ProviderRef

		s.audit.RecordRequest(ctx, audit.Entry{
			Action: audit.ActionPaymentCreated, SubjectType: "payment_intent",
			SubjectID: &intent.ID,
			After: map[string]any{
				"amount_minor": intent.AmountMinor, "currency": intent.Currency,
				"provider": provider.Code(), "milestone_id": milestoneID,
			},
		})
		return s.present(intent, result.Instructions, result.RedirectURL), nil
	}

	// A repeat of a request already in flight: the same intent, the same
	// instructions, no second charge.
	return s.present(intent, s.instructionsFor(ctx, provider, intent, facts), ""), nil
}

// instructionsFor rebuilds the payer's instructions for an existing intent, so
// reopening the page shows the same reference rather than a new one.
func (s *Service) instructionsFor(ctx context.Context, provider Provider,
	intent *StoredIntent, facts contracts.FundingFacts) []Instruction {

	manual, ok := provider.(*Manual)
	if !ok {
		return nil
	}
	return manual.instructions(ctx, Request{
		Reference:         intent.Reference,
		AmountMinor:       intent.AmountMinor,
		Currency:          intent.Currency,
		ContractReference: facts.ContractReference,
	})
}

// feeFor computes a milestone's share of the contract's frozen fee rate.
func feeFor(amountMinor int64, percent float64) int64 {
	fee := amountMinor * int64(percent*100) / 10000
	if fee < 0 {
		return 0
	}
	if fee > amountMinor {
		return amountMinor
	}
	return fee
}

// ── Release ─────────────────────────────────────────────────────────────────

// ReleaseMilestone queues the payout for an approved milestone.
//
// Called by the contracts module when a client approves work. It creates the
// payout intent and stops there: with the manual provider an administrator
// sends the money and confirms it, and only that confirmation marks the
// milestone released. Approving work and paying for it stay separate events,
// which is what lets a dispute sit between them.
func (s *Service) ReleaseMilestone(ctx context.Context, contractID, milestoneID uuid.UUID) error {
	facts, err := s.contracts.FundingFacts(ctx, milestoneID)
	if err != nil {
		return err
	}
	provider, providerErr := s.registry.Active(s.preferredCode())
	if !providerErr {
		return fmt.Errorf("%w", ErrNotConfigured)
	}

	fee := feeFor(facts.AmountMinor, facts.FeePercent)
	intent, created, err := s.store.Create(ctx, NewIntent{
		ContractID:   &contractID,
		MilestoneID:  &milestoneID,
		PayerID:      facts.ClientID,
		PayeeID:      &facts.DeveloperID,
		ProviderCode: provider.Code(),
		Direction:    DirectionPayout,
		// The developer is paid the milestone less the platform fee. Both
		// figures are stored, so the ledger can show the deduction rather than
		// a number that does not add up.
		AmountMinor:    facts.AmountMinor,
		FeeMinor:       fee,
		Currency:       facts.Currency,
		IdempotencyKey: "milestone:" + milestoneID.String() + ":payout",
	})
	if err != nil {
		return fmt.Errorf("create payout intent: %w", err)
	}
	if !created {
		return nil
	}

	result, err := provider.CreatePayment(ctx, Request{
		Reference:         intent.Reference,
		Direction:         DirectionPayout,
		AmountMinor:       facts.AmountMinor - fee,
		Currency:          facts.Currency,
		PayerID:           facts.ClientID,
		PayeeID:           facts.DeveloperID,
		ContractReference: facts.ContractReference,
		Description:       facts.ContractTitle + " — " + facts.MilestoneTitle,
		IdempotencyKey:    "milestone:" + milestoneID.String() + ":payout",
	})
	if err != nil {
		_ = s.store.Fail(ctx, intent.ID, "provider_error", err.Error())
		return fmt.Errorf("queue payout: %w", err)
	}
	return s.store.ApplyResult(ctx, intent.ID, result)
}

// ── Administration ──────────────────────────────────────────────────────────

// ConfirmRequest is an administrator saying money actually moved.
type ConfirmRequest struct {
	// What was actually received or sent, in minor units. Required, and
	// checked against the intent: an administrator confirming the wrong line
	// of a bank statement should be stopped by the amount, not by luck.
	AmountMinor int64  `json:"amount_minor"`
	Reference   string `json:"reference"`
	Note        string `json:"note"`
}

// ConfirmCharge records that a client's transfer arrived and funds the
// milestone.
//
// This is the one place a milestone becomes funded, it requires an
// administrator, and it writes an audit entry with the amount, the reference
// and who confirmed it. With no gateway to check against, that record is the
// only evidence there is — so it is not optional and it is not editable.
func (s *Service) ConfirmCharge(ctx context.Context, id *security.Identity,
	intentID uuid.UUID, in ConfirmRequest) (*Payment, error) {

	if err := s.requirePermission(ctx, id, security.PermPaymentManage, intentID); err != nil {
		return nil, err
	}

	intent, err := s.store.ByID(ctx, intentID)
	if err != nil {
		return nil, httpx.NotFoundf("payment %s does not exist", intentID)
	}
	if intent.Direction != DirectionCharge {
		return nil, httpx.Validation(map[string]string{
			"payment": "Этот платёж — не перевод от заказчика.",
		})
	}
	if err := s.checkAmount(intent, in.AmountMinor); err != nil {
		return nil, err
	}

	// The expected statuses are part of the update, so two administrators
	// confirming the same transfer cannot both fund the milestone.
	if err := s.store.Settle(ctx, intentID,
		[]string{StatusCreated, StatusRequiresAction, StatusProcessing, StatusHeld},
		StatusSucceeded); err != nil {
		if errors.Is(err, ErrAlreadySettled) {
			e := *httpx.ErrConflict
			e.Code = "already_settled"
			e.Message = "Этот платёж уже подтверждён."
			return nil, &e
		}
		return nil, httpx.Internalf(err, "settle payment")
	}

	if err := s.store.RecordTransaction(ctx, intentID, Transaction{
		Kind:        "capture",
		AmountMinor: in.AmountMinor,
		Currency:    intent.Currency,
		ProviderRef: strings.TrimSpace(in.Reference),
		OccurredAt:  time.Now().UTC(),
		Raw: map[string]any{
			"confirmed_by": id.Username,
			"note":         strings.TrimSpace(in.Note),
			"method":       "administrator_confirmation",
		},
	}); err != nil {
		logWarn(ctx, "payments: could not record the confirmation", err)
	}

	if intent.MilestoneID != nil {
		if err := s.contracts.MarkFunded(ctx, *intent.MilestoneID); err != nil {
			logWarn(ctx, "payments: could not mark the milestone funded", err)
		}
	}

	s.audit.RecordRequest(ctx, audit.Entry{
		Action: audit.ActionPaymentCreated, SubjectType: "payment_intent",
		SubjectID: &intentID,
		Before:    map[string]any{"status": intent.Status},
		After: map[string]any{
			"status": StatusSucceeded, "confirmed_amount_minor": in.AmountMinor,
			"bank_reference": strings.TrimSpace(in.Reference),
		},
		Detail: strings.TrimSpace(in.Note),
	})

	if s.notifier != nil && intent.ContractID != nil {
		s.notifier.PaymentConfirmed(ctx, intent.PayerID, *intent.ContractID,
			intent.AmountMinor, intent.Currency, "funded")
		if intent.PayeeID != nil {
			s.notifier.PaymentConfirmed(ctx, *intent.PayeeID, *intent.ContractID,
				intent.AmountMinor, intent.Currency, "funded")
		}
	}

	updated, err := s.store.ByID(ctx, intentID)
	if err != nil {
		return nil, httpx.Internalf(err, "read payment")
	}
	return s.present(updated, nil, ""), nil
}

// ConfirmPayout records that the developer was actually paid.
//
// Separate permission from confirming a charge: taking money in and sending it
// out are different powers, and an administrator who can do one should not
// automatically be able to do the other.
func (s *Service) ConfirmPayout(ctx context.Context, id *security.Identity,
	intentID uuid.UUID, in ConfirmRequest) (*Payment, error) {

	if err := s.requirePermission(ctx, id, security.PermPaymentRelease, intentID); err != nil {
		return nil, err
	}

	intent, err := s.store.ByID(ctx, intentID)
	if err != nil {
		return nil, httpx.NotFoundf("payment %s does not exist", intentID)
	}
	if intent.Direction != DirectionPayout {
		return nil, httpx.Validation(map[string]string{
			"payment": "Этот платёж — не выплата.",
		})
	}
	net := intent.AmountMinor - intent.FeeMinor
	if in.AmountMinor != net {
		return nil, httpx.Validation(map[string]string{
			"amount_minor": fmt.Sprintf(
				"This payout is %s after the platform fee. Confirm that amount, or investigate before recording it.",
				formatMoney(net, intent.Currency)),
		})
	}

	if err := s.store.Settle(ctx, intentID,
		[]string{StatusCreated, StatusRequiresAction, StatusProcessing, StatusHeld},
		StatusSucceeded); err != nil {
		if errors.Is(err, ErrAlreadySettled) {
			e := *httpx.ErrConflict
			e.Code = "already_settled"
			e.Message = "Эта выплата уже записана."
			return nil, &e
		}
		return nil, httpx.Internalf(err, "settle payout")
	}

	if err := s.store.RecordTransaction(ctx, intentID, Transaction{
		Kind: "payout", AmountMinor: net, Currency: intent.Currency,
		ProviderRef: strings.TrimSpace(in.Reference), OccurredAt: time.Now().UTC(),
		Raw: map[string]any{
			"confirmed_by": id.Username, "note": strings.TrimSpace(in.Note),
			"method": "administrator_confirmation",
		},
	}); err != nil {
		logWarn(ctx, "payments: could not record the payout", err)
	}

	// The developer's ledger: what they earned, what the platform took, and
	// what was sent. Three lines rather than one net figure, because a
	// developer is entitled to see the deduction.
	if intent.PayeeID != nil {
		description := "Milestone payment"
		if err := s.store.AppendLedger(ctx,
			LedgerEntry{
				UserID: *intent.PayeeID, IntentID: &intentID, ContractID: intent.ContractID,
				Kind: EntryEarning, AmountMinor: intent.AmountMinor,
				Currency: intent.Currency, Description: description,
			},
			LedgerEntry{
				UserID: *intent.PayeeID, IntentID: &intentID, ContractID: intent.ContractID,
				Kind: EntryFee, AmountMinor: -intent.FeeMinor,
				Currency: intent.Currency, Description: "Platform fee",
			},
			LedgerEntry{
				UserID: *intent.PayeeID, IntentID: &intentID, ContractID: intent.ContractID,
				Kind: EntryPayout, AmountMinor: -net,
				Currency: intent.Currency, Description: "Paid out",
			},
		); err != nil {
			// Deliberately fatal to the request: a payout recorded without its
			// ledger entries is a developer who cannot see what they were
			// paid, and the administrator needs to know it did not land.
			return nil, httpx.Internalf(err, "write the ledger entries")
		}
	}

	if intent.MilestoneID != nil {
		if err := s.contracts.MarkReleased(ctx, *intent.MilestoneID); err != nil {
			logWarn(ctx, "payments: could not mark the milestone released", err)
		}
	}

	s.audit.RecordRequest(ctx, audit.Entry{
		Action: audit.ActionPaymentReleased, SubjectType: "payment_intent",
		SubjectID: &intentID,
		After: map[string]any{
			"paid_minor": net, "currency": intent.Currency,
			"bank_reference": strings.TrimSpace(in.Reference),
		},
		Detail: strings.TrimSpace(in.Note),
	})

	if s.notifier != nil && intent.ContractID != nil && intent.PayeeID != nil {
		s.notifier.PaymentConfirmed(ctx, *intent.PayeeID, *intent.ContractID,
			net, intent.Currency, "paid")
	}

	updated, err := s.store.ByID(ctx, intentID)
	if err != nil {
		return nil, httpx.Internalf(err, "read payout")
	}
	return s.present(updated, nil, ""), nil
}

// RejectRequest is an administrator saying a transfer never arrived.
type RejectRequest struct {
	Reason string `json:"reason"`
}

// Reject marks a payment failed, with a reason the payer can read.
func (s *Service) Reject(ctx context.Context, id *security.Identity,
	intentID uuid.UUID, in RejectRequest) (*Payment, error) {

	if err := s.requirePermission(ctx, id, security.PermPaymentManage, intentID); err != nil {
		return nil, err
	}
	if len(strings.TrimSpace(in.Reason)) < 10 {
		return nil, httpx.Validation(map[string]string{
			"reason": "Объясните причину: плательщик увидит её и должен понимать, что делать дальше.",
		})
	}

	intent, err := s.store.ByID(ctx, intentID)
	if err != nil {
		return nil, httpx.NotFoundf("payment %s does not exist", intentID)
	}
	if intent.Status == StatusSucceeded {
		e := *httpx.ErrConflict
		e.Code = "already_settled"
		e.Message = "Платёж уже подтверждён — используйте возврат."
		return nil, &e
	}
	if err := s.store.Fail(ctx, intentID, "not_received", strings.TrimSpace(in.Reason)); err != nil {
		return nil, httpx.Internalf(err, "reject payment")
	}

	s.audit.RecordRequest(ctx, audit.Entry{
		Action: audit.ActionPaymentCreated, SubjectType: "payment_intent",
		SubjectID: &intentID, Outcome: audit.Failure,
		After:  map[string]any{"status": StatusFailed},
		Detail: strings.TrimSpace(in.Reason),
	})

	updated, err := s.store.ByID(ctx, intentID)
	if err != nil {
		return nil, httpx.Internalf(err, "read payment")
	}
	return s.present(updated, nil, ""), nil
}

// RefundRequest is a partial or full return of a confirmed charge.
type RefundRequest struct {
	AmountMinor int64  `json:"amount_minor"`
	Reason      string `json:"reason"`
}

func (s *Service) Refund(ctx context.Context, id *security.Identity,
	intentID uuid.UUID, in RefundRequest) (*Payment, error) {

	if err := s.requirePermission(ctx, id, security.PermPaymentRelease, intentID); err != nil {
		return nil, err
	}
	intent, err := s.store.ByID(ctx, intentID)
	if err != nil {
		return nil, httpx.NotFoundf("payment %s does not exist", intentID)
	}
	if intent.Status != StatusSucceeded && intent.Status != StatusPartiallyRefunded {
		e := *httpx.ErrConflict
		e.Code = "not_refundable"
		e.Message = "Вернуть можно только подтверждённый платёж."
		return nil, &e
	}
	remaining := intent.AmountMinor - intent.RefundedMinor
	if in.AmountMinor <= 0 || in.AmountMinor > remaining {
		return nil, httpx.Validation(map[string]string{
			"amount_minor": fmt.Sprintf("At most %s can still be refunded on this payment.",
				formatMoney(remaining, intent.Currency)),
		})
	}
	if len(strings.TrimSpace(in.Reason)) < 10 {
		return nil, httpx.Validation(map[string]string{
			"reason": "Запишите, почему делается возврат.",
		})
	}

	provider, ok := s.registry.Get(intent.ProviderCode)
	if !ok {
		return nil, httpx.Internalf(ErrNotConfigured, "provider %s", intent.ProviderCode)
	}
	result, err := provider.Refund(ctx, Intent{
		ID: intent.ID, Reference: intent.Reference, Direction: intent.Direction,
		AmountMinor: intent.AmountMinor, Currency: intent.Currency,
		Status: intent.Status, ProviderRef: intent.ProviderRef,
	}, in.AmountMinor, strings.TrimSpace(in.Reason))
	if err != nil {
		return nil, httpx.Internalf(err, "start refund")
	}

	if err := s.store.RecordRefund(ctx, intentID, in.AmountMinor, result, id.Username,
		strings.TrimSpace(in.Reason)); err != nil {
		return nil, httpx.Internalf(err, "record refund")
	}

	s.audit.RecordRequest(ctx, audit.Entry{
		Action: audit.ActionPaymentRefunded, SubjectType: "payment_intent",
		SubjectID: &intentID,
		After:     map[string]any{"refunded_minor": in.AmountMinor, "currency": intent.Currency},
		Detail:    strings.TrimSpace(in.Reason),
	})

	updated, err := s.store.ByID(ctx, intentID)
	if err != nil {
		return nil, httpx.Internalf(err, "read payment")
	}
	return s.present(updated, nil, ""), nil
}

// Queue is the administrator's work list.
func (s *Service) Queue(ctx context.Context, id *security.Identity, direction string) ([]PendingItem, error) {
	if err := security.RequirePermission(id, security.PermPaymentManage); err != nil {
		s.audit.Denial(ctx, "payment_queue", nil, "caller lacks payment.manage")
		return nil, forbidden("You don't have access to the payment queue.")
	}
	if direction != "" && direction != DirectionCharge && direction != DirectionPayout &&
		direction != DirectionRefund {
		return nil, httpx.Validation(map[string]string{"direction": "Неизвестное направление платежа."})
	}
	return s.store.Pending(ctx, direction, 100)
}

// Providers lists every provider and whether it is configured here.
func (s *Service) Providers(ctx context.Context, id *security.Identity) ([]ProviderRow, error) {
	if err := security.RequirePermission(id, security.PermPaymentManage); err != nil {
		return nil, forbidden("You don't have access to the payment settings.")
	}
	s.SyncProviders(ctx)
	return s.store.Providers(ctx)
}

// ── Manual transfer details ─────────────────────────────────────────────────

// ManualDetailsRequest is what an administrator fills in so clients have
// somewhere to send money.
type ManualDetailsRequest struct {
	AccountName   string `json:"account_name"`
	AccountNumber string `json:"account_number"`
	BankName      string `json:"bank_name"`
	// A free-text pair for whatever this market uses: IBAN, SWIFT, a card
	// number, a wallet address. The product does not assume one country's
	// banking.
	ExtraLabel string `json:"extra_label"`
	ExtraValue string `json:"extra_value"`
	Note       string `json:"note"`
}

// ManualDetails returns the configured transfer details, for the admin form.
func (s *Service) ManualDetails(ctx context.Context, id *security.Identity) (*ManualDetailsRequest, error) {
	if err := security.RequirePermission(id, security.PermPaymentManage); err != nil {
		return nil, forbidden("You don't have access to the payment settings.")
	}
	return &ManualDetailsRequest{
		AccountName:   s.settings.String(ctx, "payments.manual.account_name", ""),
		AccountNumber: s.settings.String(ctx, "payments.manual.account_number", ""),
		BankName:      s.settings.String(ctx, "payments.manual.bank_name", ""),
		ExtraLabel:    s.settings.String(ctx, "payments.manual.extra_label", ""),
		ExtraValue:    s.settings.String(ctx, "payments.manual.extra_value", ""),
		Note:          s.settings.String(ctx, "payments.manual.note", ""),
	}, nil
}

// SetManualDetails stores them.
//
// These are shown verbatim to every client who funds a milestone, so they are
// validated like anything else a stranger will read: bounded, no control
// characters, and no markup.
func (s *Service) SetManualDetails(ctx context.Context, id *security.Identity,
	in ManualDetailsRequest) (*ManualDetailsRequest, error) {

	if err := security.RequirePermission(id, security.PermPaymentManage); err != nil {
		s.audit.Denial(ctx, "payment_settings", nil, "caller lacks payment.manage")
		return nil, forbidden("You don't have access to the payment settings.")
	}

	v := validate.New()
	name := strings.TrimSpace(in.AccountName)
	v.Required("account_name", "Получатель перевода", name)
	v.Length("account_name", "Получатель перевода", name, 2, 120)
	v.NoControlChars("account_name", "Получатель перевода", name)

	number := strings.TrimSpace(in.AccountNumber)
	extraLabel := strings.TrimSpace(in.ExtraLabel)
	extraValue := strings.TrimSpace(in.ExtraValue)
	if number == "" && extraValue == "" {
		v.Add("account_number",
			"Укажите номер счёта — или используйте дополнительное поле для IBAN, карты или кошелька.")
	}
	for field, value := range map[string]string{
		"account_number": number, "bank_name": strings.TrimSpace(in.BankName),
		"extra_label": extraLabel, "extra_value": extraValue,
	} {
		if value == "" {
			continue
		}
		v.Length(field, "Это поле", value, 1, 160)
		v.NoControlChars(field, "Это поле", value)
	}
	if extraValue != "" && extraLabel == "" {
		v.Add("extra_label", "Назовите дополнительное поле — иначе плательщик не поймёт, что это.")
	}
	note := strings.TrimSpace(in.Note)
	if note != "" {
		v.Length("note", "Примечание", note, 0, 400)
		v.NoControlChars("note", "Примечание", note)
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	values := map[string]string{
		"payments.manual.account_name":   name,
		"payments.manual.account_number": number,
		"payments.manual.bank_name":      strings.TrimSpace(in.BankName),
		"payments.manual.extra_label":    extraLabel,
		"payments.manual.extra_value":    extraValue,
		"payments.manual.note":           note,
	}
	for key, value := range values {
		if err := s.settings.Set(ctx, key, value, id.UserID); err != nil {
			return nil, httpx.Internalf(err, "store transfer details")
		}
	}

	// Recorded without the account number: an audit log is read by more people
	// than the settings screen, and the change is what matters, not the digits.
	s.audit.RecordRequest(ctx, audit.Entry{
		Action: audit.ActionSettingChanged, SubjectType: "payment_settings",
		After: map[string]any{
			"provider": "manual", "account_name": name,
			"has_account_number": number != "", "has_extra_field": extraValue != "",
		},
	})
	s.SyncProviders(ctx)

	return s.ManualDetails(ctx, id)
}

func (s *Service) requirePermission(ctx context.Context, id *security.Identity,
	permission security.Permission, subjectID uuid.UUID) error {

	if err := security.RequirePermission(id, permission); err != nil {
		s.audit.Denial(ctx, "payment_intent", &subjectID,
			fmt.Sprintf("caller lacks %s", permission))
		return forbidden("You don't have permission to do that.")
	}
	return nil
}

func (s *Service) checkAmount(intent *StoredIntent, confirmed int64) error {
	if confirmed == intent.AmountMinor {
		return nil
	}
	// A mismatch is not rounded away or accepted with a note: the difference
	// is somebody's money, and an administrator should look at it.
	return httpx.Validation(map[string]string{
		"amount_minor": fmt.Sprintf(
			"This payment is for %s. Confirm the exact amount, or reject it and ask the client what they sent.",
			formatMoney(intent.AmountMinor, intent.Currency)),
	})
}

// ── Reads for the parties ───────────────────────────────────────────────────

// ForContract lists a contract's payments to the people on it.
func (s *Service) ForContract(ctx context.Context, id *security.Identity,
	contractID uuid.UUID) ([]*Payment, error) {

	role, err := s.contracts.EnsureParty(ctx, id, contractID)
	if err != nil {
		return nil, err
	}
	if role == contracts.RoleObserver {
		// An observer sees the work, never what it cost.
		e := *httpx.ErrForbidden
		e.Message = "Платежи по этой сделке — дело заказчика и исполнителя."
		return nil, &e
	}

	intents, err := s.store.ForContract(ctx, contractID)
	if err != nil {
		return nil, httpx.Internalf(err, "list contract payments")
	}
	out := make([]*Payment, 0, len(intents))
	for _, intent := range intents {
		out = append(out, s.present(intent, nil, ""))
	}
	return out, nil
}

// MyBalance returns the caller's own ledger.
//
// The developer's balance and earnings are private by construction: there is
// no endpoint that returns anyone else's, and nothing here is ever attached to
// a public profile.
func (s *Service) MyBalance(ctx context.Context, id *security.Identity, currency string) (*Balance, error) {
	if !id.Authenticated() {
		return nil, httpx.ErrUnauthenticated
	}
	if strings.TrimSpace(currency) == "" {
		currency = "USD"
	}
	balance, err := s.store.BalanceFor(ctx, id.UserID, currency)
	if err != nil {
		return nil, httpx.Internalf(err, "read balance")
	}
	entries, err := s.store.LedgerFor(ctx, id.UserID, currency, 50)
	if err != nil {
		return nil, httpx.Internalf(err, "read ledger")
	}
	balance.Entries = entries
	return &balance, nil
}

// ── Webhooks ────────────────────────────────────────────────────────────────

// Webhook records and processes a provider callback.
//
// Every delivery is stored before anything acts on it, verified or not: a
// replay is then a no-op against the unique event id, and a run of rejected
// signatures is visible rather than silently dropped.
func (s *Service) Webhook(ctx context.Context, providerCode string,
	headers map[string][]string, body []byte) error {

	provider, ok := s.registry.Get(providerCode)
	if !ok {
		return httpx.NotFoundf("no provider %q", providerCode)
	}
	verifier, ok := provider.(WebhookVerifier)
	if !ok {
		// A provider with no callbacks has no webhook endpoint. Saying so is
		// better than accepting a body and pretending to process it.
		e := *httpx.ErrNotConfigured
		e.Code = "no_webhooks"
		e.Message = "Этот платёжный провайдер не присылает уведомлений."
		return &e
	}

	eventID, eventType, verifyErr := verifier.VerifyWebhook(headers, body)
	detail := ""
	if verifyErr != nil {
		detail = verifyErr.Error()
	}
	recordID, fresh, err := s.store.RecordWebhook(ctx, providerCode, eventID, eventType,
		verifyErr == nil, detail, body)
	if err != nil {
		return httpx.Internalf(err, "record webhook")
	}

	if verifyErr != nil {
		s.audit.RecordRequest(ctx, audit.Entry{
			Action: audit.ActionWebhookRejected, SubjectType: "payment_webhook",
			Outcome: audit.Denied, Detail: detail,
		})
		// The same answer for a forged signature and a malformed body: an
		// attacker learns nothing from the difference.
		e := *httpx.ErrForbidden
		e.Code = "webhook_rejected"
		e.Message = "Не удалось проверить запрос."
		return &e
	}
	if !fresh {
		// Already delivered once. Answering 200 stops the provider retrying.
		return nil
	}

	// Provider-specific handling belongs with the provider that sends them;
	// until a gateway is wired in there is nothing to dispatch, and recording
	// the verified event is the whole job.
	return s.store.MarkWebhookProcessed(ctx, recordID, nil)
}

// ── Presentation ────────────────────────────────────────────────────────────

func (s *Service) present(intent *StoredIntent, instructions []Instruction, redirect string) *Payment {
	return &Payment{
		ID:            intent.ID,
		Reference:     intent.Reference,
		ContractID:    intent.ContractID,
		MilestoneID:   intent.MilestoneID,
		Direction:     intent.Direction,
		AmountMinor:   intent.AmountMinor,
		FeeMinor:      intent.FeeMinor,
		Currency:      intent.Currency,
		Status:        intent.Status,
		StatusLabel:   StatusLabel(intent.Direction, intent.Status),
		Provider:      intent.ProviderCode,
		Instructions:  instructions,
		RedirectURL:   redirect,
		RefundedMinor: intent.RefundedMinor,
		CreatedAt:     intent.CreatedAt,
		ConfirmedAt:   intent.ConfirmedAt,
		FailureReason: intent.FailureMessage,
	}
}

func forbidden(message string) error {
	e := *httpx.ErrForbidden
	e.Message = message
	return &e
}

func logWarn(ctx context.Context, message string, err error) {
	logx.From(ctx).Warn(message, "error", err)
}
