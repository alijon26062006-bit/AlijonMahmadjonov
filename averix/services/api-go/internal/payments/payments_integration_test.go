package payments_test

import (
	"net/http"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

// setup hires a developer and returns the contract, its first milestone and
// everyone involved.
func setup(t *testing.T, h *testsupport.Harness) (contractID, milestoneID string,
	client *testsupport.ClientAccount, dev *testsupport.Developer) {

	t.Helper()
	client = h.NewClient("acmeco")
	projectID := h.PublishProject(client, "Telegram bot for an online clothing store",
		"telegram-bots", []string{"python", "telegram-api", "postgresql"}, 50000, 80000)
	dev = h.PublishDeveloper("telegramdev", "telegram-developer",
		"python", "telegram-api", "postgresql")

	proposalID := dev.Client.POST("/proposals", proposal(projectID)).
		OK(t, http.StatusCreated).String("id")
	contract := client.Client.POST("/contracts", map[string]any{"proposal_id": proposalID}).
		OK(t, http.StatusCreated)

	contractID = contract.String("id")
	milestones, _ := contract.Data["milestones"].([]any)
	first, _ := milestones[0].(map[string]any)
	return contractID, first["id"].(string), client, dev
}

func proposal(projectID string) map[string]any {
	return map[string]any{
		"project_id":    projectID,
		"amount_minor":  65000,
		"currency":      "USD",
		"delivery_days": 12,
		"cover_letter": "I have built three Telegram commerce bots, the most recent one " +
			"for a clothing retailer with about 400 orders a month. Your catalogue and " +
			"cart requirements map closely onto that, and the payment step is the part " +
			"I would want to agree in detail before starting.",
		"approach": "I would start with the data model for products, orders and " +
			"customers, then the admin side so your staff can load the catalogue while " +
			"I build the customer flow. Payment goes in after the cart works end to end.",
		"relevant_experience": "Six years of Python, most of it on Telegram bots and " +
			"backend services with PostgreSQL behind them.",
		"milestones": []map[string]any{
			{"title": "Catalogue and admin", "amount_minor": 30000, "days": 5},
			{"title": "Cart, orders and payment", "amount_minor": 35000, "days": 7},
		},
	}
}

// configure fills in the transfer details, which is what makes the manual
// provider usable at all.
func configure(t *testing.T, h *testsupport.Harness) *testsupport.Admin {
	t.Helper()
	admin := h.NewAdmin("platformadmin")
	admin.Client.PUT("/admin/payments/manual-details", map[string]any{
		"account_name":   "AVERIX Operations",
		"account_number": "TJ02 0000 1111 2222 3333",
		"bank_name":      "Amonatbonk",
		"extra_label":    "SWIFT",
		"extra_value":    "AMONTJ22",
		"note":           "Please quote the payment reference exactly.",
	}).OK(t, http.StatusOK)
	return admin
}

// ── Configuration ───────────────────────────────────────────────────────────

// With no transfer details entered, the product says so instead of asking a
// client to send money nowhere.
func TestFundingSaysSoBeforeAnyoneHasSetUpPayments(t *testing.T) {
	h := testsupport.New(t)
	_, milestoneID, client, _ := setup(t, h)

	res := client.Client.POST("/milestones/"+milestoneID+"/fund", nil).
		Fails(t, http.StatusServiceUnavailable, "payments_not_configured")
	if res.Message == "" {
		t.Error("the refusal should explain what is missing")
	}
	if h.Count(`SELECT count(*) FROM payment_intents`) != 0 {
		t.Error("nothing should have been recorded")
	}
	if h.Count(`SELECT count(*) FROM milestones WHERE status <> 'draft'`) != 0 {
		t.Error("no milestone should have moved")
	}
}

func TestOnlyAnAdministratorCanSetTheTransferDetails(t *testing.T) {
	h := testsupport.New(t)
	_, _, client, dev := setup(t, h)

	for _, caller := range []*testsupport.Client{client.Client, dev.Client} {
		caller.PUT("/admin/payments/manual-details", map[string]any{
			"account_name": "Not mine", "account_number": "123",
		}).Fails(t, http.StatusForbidden, "forbidden")
		caller.GET("/admin/payments/queue").Fails(t, http.StatusForbidden, "forbidden")
	}

	admin := configure(t, h)
	details := admin.Client.GET("/admin/payments/manual-details").OK(t, http.StatusOK)
	if details.String("account_name") != "AVERIX Operations" {
		t.Errorf("account_name = %q", details.String("account_name"))
	}

	// The provider reports itself configured once the details exist.
	providers := admin.Client.GET("/admin/payments/providers").OK(t, http.StatusOK)
	found := false
	for _, entry := range providers.List {
		row, _ := entry.(map[string]any)
		if row["code"] == "manual" {
			found = true
			if row["is_configured"] != true {
				t.Error("the manual provider should be configured once details are entered")
			}
			// And it must never claim to hold funds.
			capabilities, _ := row["capabilities"].([]any)
			for _, capability := range capabilities {
				if capability == "hold" {
					t.Error("a bank transfer is not escrow and must not claim to hold funds")
				}
			}
		}
	}
	if !found {
		t.Error("the manual provider should be listed")
	}
}

func TestTransferDetailsAreValidated(t *testing.T) {
	h := testsupport.New(t)
	admin := h.NewAdmin("platformadmin")

	admin.Client.PUT("/admin/payments/manual-details", map[string]any{
		"account_name": "", "account_number": "123",
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	// A name with nowhere to send money is not a configuration.
	admin.Client.PUT("/admin/payments/manual-details", map[string]any{
		"account_name": "AVERIX Operations",
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	// An extra field without a label would render as an unexplained string on
	// the client's payment screen.
	admin.Client.PUT("/admin/payments/manual-details", map[string]any{
		"account_name": "AVERIX Operations", "extra_value": "AMONTJ22",
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
}

// ── Funding ─────────────────────────────────────────────────────────────────

func TestFundingProducesInstructionsAndWaitsForConfirmation(t *testing.T) {
	h := testsupport.New(t)
	_, milestoneID, client, dev := setup(t, h)
	configure(t, h)

	res := client.Client.POST("/milestones/"+milestoneID+"/fund", nil).
		OK(t, http.StatusCreated)

	if res.String("status") != "requires_action" {
		t.Errorf("status = %q, want requires_action", res.String("status"))
	}
	if res.String("status_label") != "Waiting for your transfer" {
		t.Errorf("status_label = %q — a person should not have to read a state name",
			res.String("status_label"))
	}
	reference := res.String("reference")
	if reference == "" {
		t.Fatal("the client needs a reference to quote on the transfer")
	}

	instructions, _ := res.Data["instructions"].([]any)
	if len(instructions) < 4 {
		t.Fatalf("instructions = %v, want the details a payer needs", res.Data["instructions"])
	}
	labels := map[string]string{}
	for _, entry := range instructions {
		instruction, _ := entry.(map[string]any)
		labels[instruction["label"].(string)] = instruction["value"].(string)
	}
	if labels["Amount"] != "$300.00" {
		t.Errorf("amount = %q, want the milestone's value", labels["Amount"])
	}
	if labels["Payment reference"] != reference {
		t.Errorf("the quoted reference (%q) must match the payment (%q)",
			labels["Payment reference"], reference)
	}
	if labels["Account name"] != "AVERIX Operations" {
		t.Errorf("account name = %q", labels["Account name"])
	}

	// Nothing has moved: the milestone is not funded by asking to pay.
	if h.Count(`SELECT count(*) FROM milestones WHERE status = 'funded'`) != 0 {
		t.Error("a milestone must not be funded before the money is confirmed")
	}
	dev.Client.POST("/milestones/"+milestoneID+"/start", nil).
		Fails(t, http.StatusConflict, "milestone_state")
}

// A double-clicked button must not create two charges.
func TestFundingIsIdempotent(t *testing.T) {
	h := testsupport.New(t)
	_, milestoneID, client, _ := setup(t, h)
	configure(t, h)

	first := client.Client.POST("/milestones/"+milestoneID+"/fund", nil).OK(t, http.StatusCreated)
	second := client.Client.POST("/milestones/"+milestoneID+"/fund", nil).OK(t, http.StatusCreated)

	if first.String("reference") != second.String("reference") {
		t.Errorf("two references for one milestone: %q and %q",
			first.String("reference"), second.String("reference"))
	}
	if count := h.Count(`SELECT count(*) FROM payment_intents WHERE direction = 'charge'`); count != 1 {
		t.Errorf("%d charges recorded for one milestone, want 1", count)
	}
	// The second response still carries the instructions, so reopening the
	// page shows the same reference rather than a new one.
	if instructions, _ := second.Data["instructions"].([]any); len(instructions) == 0 {
		t.Error("the repeated request should still show how to pay")
	}
}

func TestOnlyTheClientCanFundAndOnlyTheirOwnMilestone(t *testing.T) {
	h := testsupport.New(t)
	_, milestoneID, _, dev := setup(t, h)
	configure(t, h)

	dev.Client.POST("/milestones/"+milestoneID+"/fund", nil).
		Fails(t, http.StatusForbidden, "forbidden")

	stranger := h.NewClient("otherco")
	stranger.Client.POST("/milestones/"+milestoneID+"/fund", nil).
		Fails(t, http.StatusNotFound, "not_found")
}

// ── Confirmation ────────────────────────────────────────────────────────────

func TestConfirmingATransferFundsTheMilestone(t *testing.T) {
	h := testsupport.New(t)
	contractID, milestoneID, client, dev := setup(t, h)
	admin := configure(t, h)

	payment := client.Client.POST("/milestones/"+milestoneID+"/fund", nil).
		OK(t, http.StatusCreated)
	intentID := payment.String("id")

	queue := admin.Client.GET("/admin/payments/queue?direction=charge").OK(t, http.StatusOK)
	if len(queue.List) != 1 {
		t.Fatalf("the queue holds %d items, want the one transfer", len(queue.List))
	}
	item, _ := queue.List[0].(map[string]any)
	if item["payer_username"] != "acmeco" || item["milestone_title"] == "" {
		t.Errorf("the queue row should say who owes what and for which milestone: %v", item)
	}

	// The amount is checked: confirming the wrong line of a bank statement
	// should be stopped by the figure rather than by luck.
	admin.Client.POST("/admin/payments/"+intentID+"/confirm", map[string]any{
		"amount_minor": 29000, "reference": "BANK-1",
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	res := admin.Client.POST("/admin/payments/"+intentID+"/confirm", map[string]any{
		"amount_minor": 30000, "reference": "BANK-1", "note": "Received 12:04, Amonatbonk.",
	}).OK(t, http.StatusOK)
	if res.String("status") != "succeeded" || res.String("status_label") != "Funded" {
		t.Fatalf("after confirmation: %v", res.Data)
	}

	// The milestone is funded and the contract is live.
	contract := client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK)
	if contract.String("status") != "active" {
		t.Errorf("contract status = %q, want active", contract.String("status"))
	}
	milestone, _ := contract.Data["milestones"].([]any)[0].(map[string]any)
	if milestone["status"] != "funded" {
		t.Errorf("milestone status = %v, want funded", milestone["status"])
	}
	dev.Client.POST("/milestones/"+milestoneID+"/start", nil).OK(t, http.StatusOK)

	// Who confirmed it, for how much, against which bank reference: with no
	// gateway to check against, this record is the only evidence there is.
	if h.Count(`SELECT count(*) FROM audit_logs
	            WHERE action = 'payment.created' AND actor_id = $1::uuid`, admin.UserID) == 0 {
		t.Error("an administrator's confirmation must be audited")
	}
	if h.Count(`SELECT count(*) FROM payment_transactions WHERE kind = 'capture'`) != 1 {
		t.Error("the confirmation should append a transaction")
	}
}

// Two administrators confirming the same transfer must not fund it twice.
func TestATransferCannotBeConfirmedTwice(t *testing.T) {
	h := testsupport.New(t)
	_, milestoneID, client, _ := setup(t, h)
	admin := configure(t, h)

	intentID := client.Client.POST("/milestones/"+milestoneID+"/fund", nil).
		OK(t, http.StatusCreated).String("id")

	admin.Client.POST("/admin/payments/"+intentID+"/confirm", map[string]any{
		"amount_minor": 30000, "reference": "BANK-1",
	}).OK(t, http.StatusOK)
	admin.Client.POST("/admin/payments/"+intentID+"/confirm", map[string]any{
		"amount_minor": 30000, "reference": "BANK-1",
	}).Fails(t, http.StatusConflict, "already_settled")
}

func TestATransferThatNeverArrivedIsRejectedWithAReason(t *testing.T) {
	h := testsupport.New(t)
	_, milestoneID, client, _ := setup(t, h)
	admin := configure(t, h)

	intentID := client.Client.POST("/milestones/"+milestoneID+"/fund", nil).
		OK(t, http.StatusCreated).String("id")

	admin.Client.POST("/admin/payments/"+intentID+"/reject", map[string]any{"reason": "no"}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	res := admin.Client.POST("/admin/payments/"+intentID+"/reject", map[string]any{
		"reason": "Nothing arrived within seven days and the client did not respond.",
	}).OK(t, http.StatusOK)
	if res.String("status") != "failed" {
		t.Errorf("status = %q, want failed", res.String("status"))
	}
	if res.String("failure_reason") == "" {
		t.Error("the payer should be told why")
	}
	if h.Count(`SELECT count(*) FROM milestones WHERE status = 'funded'`) != 0 {
		t.Error("a rejected transfer must not fund anything")
	}
}

// ── Payouts ─────────────────────────────────────────────────────────────────

func TestApprovalQueuesAPayoutAndConfirmingItPaysTheDeveloper(t *testing.T) {
	h := testsupport.New(t)
	_, milestoneID, client, dev := setup(t, h)
	admin := configure(t, h)

	intentID := client.Client.POST("/milestones/"+milestoneID+"/fund", nil).
		OK(t, http.StatusCreated).String("id")
	admin.Client.POST("/admin/payments/"+intentID+"/confirm", map[string]any{
		"amount_minor": 30000, "reference": "BANK-1",
	}).OK(t, http.StatusOK)

	dev.Client.POST("/milestones/"+milestoneID+"/start", nil).OK(t, http.StatusOK)
	dev.Client.POST("/milestones/"+milestoneID+"/submit", map[string]any{
		"note": "The catalogue and the admin screen are ready on the staging bot.",
	}).OK(t, http.StatusOK)
	client.Client.POST("/milestones/"+milestoneID+"/approve", nil).OK(t, http.StatusOK)

	// Approving the work queues the payout; it does not pay it.
	queue := admin.Client.GET("/admin/payments/queue?direction=payout").OK(t, http.StatusOK)
	if len(queue.List) != 1 {
		t.Fatalf("the payout queue holds %d items, want 1", len(queue.List))
	}
	payout, _ := queue.List[0].(map[string]any)
	payoutID := payout["id"].(string)
	if payout["payee_username"] != "telegramdev" {
		t.Errorf("payee = %v, want the developer", payout["payee_username"])
	}
	if h.Count(`SELECT count(*) FROM milestones WHERE status = 'released'`) != 0 {
		t.Error("approving work must not mark money paid")
	}

	// The developer sees it as pending: earned, not yet received.
	balance := dev.Client.GET("/me/balance").OK(t, http.StatusOK)
	if balance.Float("pending_minor") != 27000 {
		t.Errorf("pending = %v, want 27000 (300.00 less the 10%% fee)",
			balance.Data["pending_minor"])
	}
	if balance.Float("available_minor") != 0 {
		t.Errorf("available = %v, want 0 before the payout is sent",
			balance.Data["available_minor"])
	}

	// The confirmed figure is the net one; confirming the gross would mean
	// someone sent the fee to the developer too.
	admin.Client.POST("/admin/payments/"+payoutID+"/confirm-payout", map[string]any{
		"amount_minor": 30000, "reference": "OUT-1",
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	admin.Client.POST("/admin/payments/"+payoutID+"/confirm-payout", map[string]any{
		"amount_minor": 27000, "reference": "OUT-1", "note": "Sent 14:20.",
	}).OK(t, http.StatusOK)

	if h.Count(`SELECT count(*) FROM milestones WHERE id = $1::uuid AND status = 'released'`,
		milestoneID) != 1 {
		t.Error("a confirmed payout should release the milestone")
	}

	// The ledger shows the deduction rather than a net figure that does not
	// add up.
	balance = dev.Client.GET("/me/balance").OK(t, http.StatusOK)
	if balance.Float("lifetime_minor") != 30000 {
		t.Errorf("lifetime = %v, want the gross 30000", balance.Data["lifetime_minor"])
	}
	if balance.Float("fees_minor") != 3000 {
		t.Errorf("fees = %v, want 3000", balance.Data["fees_minor"])
	}
	if balance.Float("available_minor") != 0 {
		t.Errorf("available = %v, want 0 once the money has been sent",
			balance.Data["available_minor"])
	}
	entries, _ := balance.Data["entries"].([]any)
	if len(entries) != 3 {
		t.Errorf("got %d ledger entries, want earning, fee and payout", len(entries))
	}
}

// A developer's balance is private. There is no endpoint for anyone else's.
func TestABalanceIsOnlyEverYourOwn(t *testing.T) {
	h := testsupport.New(t)
	_, _, client, dev := setup(t, h)

	mine := dev.Client.GET("/me/balance").OK(t, http.StatusOK)
	if _, present := mine.Data["available_minor"]; !present {
		t.Error("a developer should see their own balance")
	}

	// The client's own balance is their own, not the developer's.
	theirs := client.Client.GET("/me/balance").OK(t, http.StatusOK)
	if theirs.Float("lifetime_minor") != 0 {
		t.Error("one account's balance must never contain another's earnings")
	}

	// And nothing about earnings appears on the public profile.
	profile := h.Client().GET("/developers/telegramdev").OK(t, http.StatusOK)
	for _, forbidden := range []string{"balance", "available_minor", "lifetime_minor", "earnings"} {
		if _, present := profile.Data[forbidden]; present {
			t.Errorf("the public profile exposes %q", forbidden)
		}
	}
}

// ── Refunds ─────────────────────────────────────────────────────────────────

func TestRefundingAConfirmedTransfer(t *testing.T) {
	h := testsupport.New(t)
	_, milestoneID, client, _ := setup(t, h)
	admin := configure(t, h)

	intentID := client.Client.POST("/milestones/"+milestoneID+"/fund", nil).
		OK(t, http.StatusCreated).String("id")
	admin.Client.POST("/admin/payments/"+intentID+"/confirm", map[string]any{
		"amount_minor": 30000, "reference": "BANK-1",
	}).OK(t, http.StatusOK)

	// More than was paid cannot be returned.
	admin.Client.POST("/admin/payments/"+intentID+"/refund", map[string]any{
		"amount_minor": 40000, "reason": "The client changed their mind.",
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	partial := admin.Client.POST("/admin/payments/"+intentID+"/refund", map[string]any{
		"amount_minor": 10000, "reason": "Scope reduced after the first call.",
	}).OK(t, http.StatusOK)
	if partial.String("status") != "partially_refunded" {
		t.Errorf("status = %q, want partially_refunded", partial.String("status"))
	}

	full := admin.Client.POST("/admin/payments/"+intentID+"/refund", map[string]any{
		"amount_minor": 20000, "reason": "The rest returned; the contract was cancelled.",
	}).OK(t, http.StatusOK)
	if full.String("status") != "refunded" {
		t.Errorf("status = %q, want refunded", full.String("status"))
	}

	// And no more.
	admin.Client.POST("/admin/payments/"+intentID+"/refund", map[string]any{
		"amount_minor": 100, "reason": "One more attempt at the same money.",
	}).Fails(t, http.StatusConflict, "not_refundable")
}

// ── Parties and webhooks ────────────────────────────────────────────────────

func TestBothPartiesSeeTheContractsPaymentsAndAnObserverDoesNot(t *testing.T) {
	h := testsupport.New(t)
	contractID, milestoneID, client, dev := setup(t, h)
	configure(t, h)
	client.Client.POST("/milestones/"+milestoneID+"/fund", nil).OK(t, http.StatusCreated)

	for _, caller := range []*testsupport.Client{client.Client, dev.Client} {
		res := caller.GET("/contracts/"+contractID+"/payments").OK(t, http.StatusOK)
		if len(res.List) != 1 {
			t.Errorf("a party sees %d payments, want 1", len(res.List))
		}
	}

	helper := h.PublishDeveloper("helperdev", "backend-developer")
	client.Client.POST("/contracts/"+contractID+"/observers", map[string]any{
		"username": "helperdev",
	}).OK(t, http.StatusOK)
	helper.Client.GET("/contracts/"+contractID+"/payments").
		Fails(t, http.StatusForbidden, "forbidden")

	stranger := h.NewClient("otherco")
	stranger.Client.GET("/contracts/"+contractID+"/payments").
		Fails(t, http.StatusNotFound, "not_found")
}

// The webhook endpoint exists for providers that call back. The manual
// provider does not, and says so rather than accepting a body and pretending.
func TestTheWebhookEndpointRefusesWhatItCannotVerify(t *testing.T) {
	h := testsupport.New(t)
	anon := h.Client()

	anon.Raw(http.MethodPost, "/payments/webhook/manual", []byte(`{"event":"payment.succeeded"}`)).
		Fails(t, http.StatusServiceUnavailable, "no_webhooks")
	anon.Raw(http.MethodPost, "/payments/webhook/nonesuch", []byte(`{}`)).
		Fails(t, http.StatusNotFound, "not_found")

	if h.Count(`SELECT count(*) FROM payment_intents`) != 0 {
		t.Error("an unverifiable callback must not create a payment")
	}
}
