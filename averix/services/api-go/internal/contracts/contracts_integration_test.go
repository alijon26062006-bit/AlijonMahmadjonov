package contracts_test

import (
	"net/http"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

// hire runs the whole path up to a signed contract: a published project, a
// proposal on it, and the client accepting.
func hire(t *testing.T, h *testsupport.Harness) (contractID string,
	client *testsupport.ClientAccount, dev *testsupport.Developer) {

	t.Helper()
	client = h.NewClient("acmeco")
	projectID := h.PublishProject(client, "Telegram bot for an online clothing store",
		"telegram-bots", []string{"python", "telegram-api", "postgresql"}, 50000, 80000)

	dev = h.PublishDeveloper("telegramdev", "telegram-developer",
		"python", "telegram-api", "postgresql")
	proposalID := dev.Client.POST("/proposals", proposal(projectID)).
		OK(t, http.StatusCreated).String("id")

	res := client.Client.POST("/contracts", map[string]any{
		"proposal_id": proposalID,
	}).OK(t, http.StatusCreated)
	return res.String("id"), client, dev
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
			{"title": "Catalogue and admin", "amount_minor": 30000, "days": 5,
				"detail": "Products, categories and the staff admin screen."},
			{"title": "Cart, orders and payment", "amount_minor": 35000, "days": 7,
				"detail": "Customer flow end to end, then the payment step."},
		},
	}
}

// fundMilestone simulates what the payments module writes when money settles.
//
// Funding itself belongs to the payment provider and is covered by that
// module's own tests; here it is the precondition for everything after it, so
// the test writes the state the provider would write rather than pretending
// the API can fund without one.
func fundMilestone(h *testsupport.Harness, milestoneID string) {
	h.Exec(`UPDATE milestones SET status = 'funded' WHERE id = $1`, milestoneID)
	h.Exec(`UPDATE contracts SET status = 'active'
	        WHERE id = (SELECT contract_id FROM milestones WHERE id = $1)`, milestoneID)
}

func milestoneIDs(t *testing.T, res *testsupport.Response) []string {
	t.Helper()
	raw, ok := res.Data["milestones"].([]any)
	if !ok || len(raw) == 0 {
		t.Fatalf("contract carries no milestones: %s", res.Raw)
	}
	out := make([]string, 0, len(raw))
	for _, entry := range raw {
		milestone, _ := entry.(map[string]any)
		out = append(out, milestone["id"].(string))
	}
	return out
}

// ── Signing ─────────────────────────────────────────────────────────────────

func TestAcceptingAProposalSignsAContract(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, dev := hire(t, h)

	res := client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK)
	if res.String("status") != "pending_funding" {
		t.Errorf("status = %q, want pending_funding — nothing is active before money", res.String("status"))
	}
	if res.String("my_role") != "client" {
		t.Errorf("my_role = %q, want client", res.String("my_role"))
	}
	if res.Float("amount_minor") != 65000 {
		t.Errorf("amount_minor = %v, want the proposal's price", res.Data["amount_minor"])
	}
	// The fee is frozen at signature: 10% of 65000 by default.
	if res.Float("fee_minor") != 6500 || res.Float("payout_minor") != 58500 {
		t.Errorf("fee = %v, payout = %v, want 6500 and 58500",
			res.Data["fee_minor"], res.Data["payout_minor"])
	}
	if reference := res.String("reference"); len(reference) < 8 {
		t.Errorf("reference = %q, want a human-readable contract number", reference)
	}

	milestones := milestoneIDs(t, res)
	if len(milestones) != 2 {
		t.Errorf("got %d milestones, want the two the developer proposed", len(milestones))
	}

	// The developer sees the same contract from their side.
	devView := dev.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK)
	if devView.String("my_role") != "developer" {
		t.Errorf("the developer's my_role = %q", devView.String("my_role"))
	}

	// And the project is no longer open for proposals.
	project := client.Client.GET("/projects/"+res.Data["project"].(map[string]any)["id"].(string)).
		OK(t, http.StatusOK)
	if project.String("status") != "in_progress" {
		t.Errorf("project status = %q, want in_progress", project.String("status"))
	}
}

func TestHiringDeclinesTheOtherProposalsWithAReason(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("acmeco")
	projectID := h.PublishProject(client, "Telegram bot for an online clothing store",
		"telegram-bots", []string{"python", "telegram-api", "postgresql"}, 50000, 80000)

	winner := h.PublishDeveloper("winnerdev", "telegram-developer", "python", "telegram-api")
	loser := h.PublishDeveloper("loserdev", "telegram-developer", "python", "telegram-api")
	winning := winner.Client.POST("/proposals", proposal(projectID)).
		OK(t, http.StatusCreated).String("id")
	losing := loser.Client.POST("/proposals", proposal(projectID)).
		OK(t, http.StatusCreated).String("id")

	client.Client.POST("/contracts", map[string]any{"proposal_id": winning}).
		OK(t, http.StatusCreated)

	// The other developer is told, rather than left waiting indefinitely.
	res := loser.Client.GET("/proposals/"+losing).OK(t, http.StatusOK)
	if res.String("status") != "declined" {
		t.Errorf("the other proposal is %q, want declined", res.String("status"))
	}
}

func TestOnlyTheProjectsClientCanHire(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("acmeco")
	projectID := h.PublishProject(client, "Telegram bot for an online clothing store",
		"telegram-bots", []string{"python", "telegram-api", "postgresql"}, 50000, 80000)
	dev := h.PublishDeveloper("telegramdev", "telegram-developer", "python", "telegram-api")
	proposalID := dev.Client.POST("/proposals", proposal(projectID)).
		OK(t, http.StatusCreated).String("id")

	// A different client cannot hire on someone else's project, and is not
	// told the proposal exists.
	intruder := h.NewClient("otherco")
	intruder.Client.POST("/contracts", map[string]any{"proposal_id": proposalID}).
		Fails(t, http.StatusNotFound, "not_found")

	// Neither can the developer hire themselves.
	dev.Client.POST("/contracts", map[string]any{"proposal_id": proposalID}).
		Fails(t, http.StatusForbidden, "forbidden")
}

func TestTheSameProposalCannotBeAcceptedTwice(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("acmeco")
	projectID := h.PublishProject(client, "Telegram bot for an online clothing store",
		"telegram-bots", []string{"python", "telegram-api", "postgresql"}, 50000, 80000)
	dev := h.PublishDeveloper("telegramdev", "telegram-developer", "python", "telegram-api")
	proposalID := dev.Client.POST("/proposals", proposal(projectID)).
		OK(t, http.StatusCreated).String("id")

	client.Client.POST("/contracts", map[string]any{"proposal_id": proposalID}).
		OK(t, http.StatusCreated)
	client.Client.POST("/contracts", map[string]any{"proposal_id": proposalID}).
		Fails(t, http.StatusConflict, "proposal_not_open")
}

// ── Access ──────────────────────────────────────────────────────────────────

// Changing the id in the URL must not open someone else's agreement.
func TestAStrangerCannotSeeAContract(t *testing.T) {
	h := testsupport.New(t)
	contractID, _, _ := hire(t, h)

	stranger := h.PublishDeveloper("nosydev", "backend-developer")
	stranger.Client.GET("/contracts/"+contractID).Fails(t, http.StatusNotFound, "not_found")
	stranger.Client.POST("/contracts/"+contractID+"/cancel", map[string]any{
		"reason": "I would like this contract to go away please.",
	}).Fails(t, http.StatusNotFound, "not_found")

	// An anonymous caller is asked to sign in; a signed-in stranger is told the
	// contract does not exist. Both are refused, and neither learns anything.
	anonymous := h.Client()
	anonymous.GET("/contracts/"+contractID).Fails(t, http.StatusUnauthorized, "unauthenticated")
}

func TestAnObserverSeesTheWorkButNotTheMoney(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, _ := hire(t, h)
	helper := h.PublishDeveloper("helperdev", "backend-developer")

	client.Client.POST("/contracts/"+contractID+"/observers", map[string]any{
		"username": "helperdev",
	}).OK(t, http.StatusOK)

	res := helper.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK)
	if res.String("my_role") != "observer" {
		t.Fatalf("my_role = %q, want observer", res.String("my_role"))
	}
	if _, present := res.Data["amount_minor"]; present {
		t.Error("an observer must not see what the contract is worth")
	}
	milestones, _ := res.Data["milestones"].([]any)
	if len(milestones) == 0 {
		t.Fatal("an observer should still see the work")
	}
	first, _ := milestones[0].(map[string]any)
	if _, present := first["amount_minor"]; present {
		t.Error("an observer must not see a milestone's value")
	}

	// And an observer cannot act on the work.
	client.Client.DELETE("/contracts/"+contractID+"/observers/"+helper.UserID).
		OK(t, http.StatusNoContent)
	helper.Client.GET("/contracts/"+contractID).Fails(t, http.StatusNotFound, "not_found")
}

// ── The milestone state machine ─────────────────────────────────────────────

func TestFundingSaysSoWhenPaymentsAreNotConfigured(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, _ := hire(t, h)
	milestones := milestoneIDs(t, client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK))

	// No provider is configured on this environment. The endpoint says exactly
	// that rather than pretending the milestone was funded.
	res := client.Client.POST("/milestones/"+milestones[0]+"/fund", nil).
		Fails(t, http.StatusServiceUnavailable, "payments_not_configured")
	if res.Message == "" {
		t.Error("the refusal should explain itself")
	}

	// And nothing moved.
	if h.Count(`SELECT count(*) FROM milestones WHERE status <> 'draft'`) != 0 {
		t.Error("a refused funding attempt must not change a milestone")
	}
}

func TestMilestoneFlowFromFundedToApproved(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, dev := hire(t, h)
	milestones := milestoneIDs(t, client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK))
	first := milestones[0]

	// Work cannot start before the money is there.
	dev.Client.POST("/milestones/"+first+"/start", nil).
		Fails(t, http.StatusConflict, "milestone_state")

	fundMilestone(h, first)

	res := dev.Client.POST("/milestones/"+first+"/start", nil).OK(t, http.StatusOK)
	if res.String("status") != "in_progress" {
		t.Fatalf("status = %q, want in_progress", res.String("status"))
	}

	// A submission has to say what is being handed over.
	dev.Client.POST("/milestones/"+first+"/submit", map[string]any{}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	res = dev.Client.POST("/milestones/"+first+"/submit", map[string]any{
		"note": "The catalogue, categories and the staff admin screen are on the staging bot.",
		"deliverables": []map[string]any{
			{"kind": "link", "title": "Staging bot", "url": "https://staging.example.org/bot"},
		},
	}).OK(t, http.StatusOK)
	if res.String("status") != "submitted" {
		t.Fatalf("status = %q, want submitted", res.String("status"))
	}

	// The client sends it back once, with a reason.
	dev.Client.POST("/milestones/"+first+"/request-revision", map[string]any{
		"note": "The category list is missing the sale section.",
	}).Fails(t, http.StatusForbidden, "not_your_move")

	client.Client.POST("/milestones/"+first+"/request-revision", map[string]any{"note": "fix"}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	res = client.Client.POST("/milestones/"+first+"/request-revision", map[string]any{
		"note": "The category list is missing the sale section, and the admin screen doesn't paginate.",
	}).OK(t, http.StatusOK)
	if res.String("status") != "revision_requested" || res.Float("revision_count") != 1 {
		t.Fatalf("after a revision: status %q, count %v",
			res.String("status"), res.Data["revision_count"])
	}

	res = dev.Client.POST("/milestones/"+first+"/submit", map[string]any{
		"note": "Sale section added and the admin list now pages at fifty rows.",
	}).OK(t, http.StatusOK)

	// The developer cannot approve their own work.
	dev.Client.POST("/milestones/"+first+"/approve", nil).
		Fails(t, http.StatusForbidden, "not_your_move")

	res = client.Client.POST("/milestones/"+first+"/approve", nil).OK(t, http.StatusOK)
	if res.String("status") != "approved" {
		t.Fatalf("status = %q, want approved", res.String("status"))
	}
	if res.Data["approved_at"] == nil {
		t.Error("an approval should be dated")
	}

	// Approving twice is a conflict, not a second approval.
	client.Client.POST("/milestones/"+first+"/approve", nil).
		Fails(t, http.StatusConflict, "milestone_state")

	// Every move is on the record, which is what a dispute reads.
	contract := client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK)
	milestone := contract.Data["milestones"].([]any)[0].(map[string]any)
	events, _ := milestone["events"].([]any)
	if len(events) < 5 {
		t.Errorf("got %d recorded events, want one per move", len(events))
	}
	if contract.Float("progress_percent") == 0 {
		t.Error("approving a milestone should move the contract's progress")
	}
}

func TestRevisionLimitEndsInADisputeNotALoop(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, dev := hire(t, h)
	milestones := milestoneIDs(t, client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK))
	first := milestones[0]
	fundMilestone(h, first)
	dev.Client.POST("/milestones/"+first+"/start", nil).OK(t, http.StatusOK)

	for i := 0; i < 2; i++ {
		dev.Client.POST("/milestones/"+first+"/submit", map[string]any{
			"note": "Submitting the catalogue work for review, round " + string(rune('A'+i)) + ".",
		}).OK(t, http.StatusOK)
		client.Client.POST("/milestones/"+first+"/request-revision", map[string]any{
			"note": "Still missing the sale section and the pagination we discussed.",
		}).OK(t, http.StatusOK)
	}

	dev.Client.POST("/milestones/"+first+"/submit", map[string]any{
		"note": "Third submission with both points addressed in full.",
	}).OK(t, http.StatusOK)

	// The agreed revisions are used up: the next step is a dispute, and the
	// message says so instead of refusing without a way forward.
	res := client.Client.POST("/milestones/"+first+"/request-revision", map[string]any{
		"note": "I would like yet another round of changes on this milestone.",
	}).Fails(t, http.StatusConflict, "revision_limit_reached")
	if res.Message == "" {
		t.Error("the refusal should tell the client what to do instead")
	}

	dispute := client.Client.POST("/milestones/"+first+"/dispute", map[string]any{
		"note": "We have been round three times and the sale section still isn't there. Please look at this.",
	}).OK(t, http.StatusOK)
	if dispute.String("status") != "disputed" {
		t.Fatalf("status = %q, want disputed", dispute.String("status"))
	}
	contract := client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK)
	if contract.String("status") != "disputed" {
		t.Errorf("contract status = %q, want disputed", contract.String("status"))
	}
}

func TestApprovingEveryMilestoneCompletesTheContract(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, dev := hire(t, h)
	contract := client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK)
	projectID := contract.Data["project"].(map[string]any)["id"].(string)

	for _, milestoneID := range milestoneIDs(t, contract) {
		fundMilestone(h, milestoneID)
		dev.Client.POST("/milestones/"+milestoneID+"/start", nil).OK(t, http.StatusOK)
		dev.Client.POST("/milestones/"+milestoneID+"/submit", map[string]any{
			"note": "This part is finished and deployed to the staging bot for review.",
		}).OK(t, http.StatusOK)
		client.Client.POST("/milestones/"+milestoneID+"/approve", nil).OK(t, http.StatusOK)
	}

	res := client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK)
	if res.String("status") != "completed" {
		t.Fatalf("contract status = %q, want completed", res.String("status"))
	}
	if res.Float("progress_percent") != 100 {
		t.Errorf("progress = %v, want 100", res.Data["progress_percent"])
	}

	project := client.Client.GET("/projects/"+projectID).OK(t, http.StatusOK)
	if project.String("status") != "completed" {
		t.Errorf("project status = %q, want completed", project.String("status"))
	}
}

// A release is the payment provider's word, never a party's.
func TestNoPartyCanDeclareAMilestonePaid(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, _ := hire(t, h)
	milestones := milestoneIDs(t, client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK))

	// There is no release endpoint at all, which is the point: the only path
	// to "released" is the payments module reporting a settled payout.
	client.Client.POST("/milestones/"+milestones[0]+"/release", nil).
		Fails(t, http.StatusNotFound, "not_found")
	if h.Count(`SELECT count(*) FROM milestones WHERE status = 'released'`) != 0 {
		t.Error("nothing should be marked released")
	}
}

// ── Deliverables ────────────────────────────────────────────────────────────

func TestDeliverableLinksGoThroughTheSameURLGuard(t *testing.T) {
	h := testsupport.New(t)
	contractID, _, dev := hire(t, h)

	for _, bad := range []string{
		"javascript:alert(1)",
		"http://169.254.169.254/latest/meta-data/",
		"https://192.168.1.10/build",
		"file:///etc/passwd",
	} {
		dev.Client.POST("/contracts/"+contractID+"/deliverables", map[string]any{
			"kind": "link", "title": "Build", "url": bad,
		}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	}

	res := dev.Client.POST("/contracts/"+contractID+"/deliverables", map[string]any{
		"kind": "repository", "title": "Source", "url": "https://github.com/example/bot",
	}).OK(t, http.StatusCreated)
	if res.String("host") != "github.com" {
		t.Errorf("host = %q, want github.com", res.String("host"))
	}
}

func TestADeliverableCannotAttachSomeoneElsesFile(t *testing.T) {
	h := testsupport.New(t)
	contractID, _, dev := hire(t, h)

	// A file id that belongs to nobody on this contract is refused without
	// confirming whether it exists.
	dev.Client.POST("/contracts/"+contractID+"/deliverables", map[string]any{
		"kind": "file", "title": "Build output",
		"file_id": "11111111-2222-3333-4444-555555555555",
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
}

// ── Cancellation ────────────────────────────────────────────────────────────

func TestCancellingNeedsAReasonAndStopsOnceWorkIsDelivered(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, dev := hire(t, h)
	milestones := milestoneIDs(t, client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK))

	client.Client.POST("/contracts/"+contractID+"/cancel", map[string]any{"reason": "no"}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	// The developer cannot cancel; that is what a dispute is for.
	dev.Client.POST("/contracts/"+contractID+"/cancel", map[string]any{
		"reason": "The client has gone quiet and I would like to close this.",
	}).Fails(t, http.StatusForbidden, "not_your_move")

	fundMilestone(h, milestones[0])
	dev.Client.POST("/milestones/"+milestones[0]+"/start", nil).OK(t, http.StatusOK)
	dev.Client.POST("/milestones/"+milestones[0]+"/submit", map[string]any{
		"note": "The catalogue and admin screens are ready for review on staging.",
	}).OK(t, http.StatusOK)

	// Work has been delivered: unwinding that is a dispute, not a cancellation.
	client.Client.POST("/contracts/"+contractID+"/cancel", map[string]any{
		"reason": "We have decided to build this in-house after all.",
	}).Fails(t, http.StatusConflict, "work_delivered")
}

func TestCancellingBeforeAnyWorkClosesTheContract(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, _ := hire(t, h)

	res := client.Client.POST("/contracts/"+contractID+"/cancel", map[string]any{
		"reason": "Our budget for this quarter was pulled, so we can't go ahead.",
	}).OK(t, http.StatusOK)
	if res.String("status") != "cancelled" {
		t.Fatalf("status = %q, want cancelled", res.String("status"))
	}
	if res.String("cancellation_reason") == "" {
		t.Error("the reason should be kept — the developer is owed the explanation")
	}
	if h.Count(`SELECT count(*) FROM milestones WHERE status <> 'cancelled'`) != 0 {
		t.Error("a cancelled contract should not leave live milestones behind")
	}
}

// ── Lists ───────────────────────────────────────────────────────────────────

func TestContractListsShowEachSideTheirOwnView(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, dev := hire(t, h)

	clientList := client.Client.GET("/contracts").OK(t, http.StatusOK)
	if len(clientList.List) != 1 {
		t.Fatalf("the client sees %d contracts, want 1", len(clientList.List))
	}
	card, _ := clientList.List[0].(map[string]any)
	if card["my_role"] != "client" {
		t.Errorf("my_role = %v, want client", card["my_role"])
	}
	counterparty, _ := card["counterparty"].(map[string]any)
	if counterparty["username"] != "telegramdev" {
		t.Errorf("the client's counterparty is %v, want the developer", counterparty["username"])
	}

	devList := dev.Client.GET("/contracts").OK(t, http.StatusOK)
	devCard, _ := devList.List[0].(map[string]any)
	if devCard["my_role"] != "developer" {
		t.Errorf("the developer's my_role = %v", devCard["my_role"])
	}
	if devCard["id"] != contractID {
		t.Errorf("the developer sees contract %v, want %s", devCard["id"], contractID)
	}
}
