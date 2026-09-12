package proposals_test

import (
	"net/http"
	"strings"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

// A substantive proposal, the shape the product is designed around.
func goodProposal(projectID string) map[string]any {
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
			"I build the customer flow. Payment goes in after the cart works end to " +
			"end, because testing payment against a half-built cart wastes everyone's time.",
		"relevant_experience": "Six years of Python, most of it on Telegram bots and " +
			"backend services with PostgreSQL behind them.",
		"questions": "Do you already have a payment provider, or should I recommend one?",
	}
}

func setupProject(t *testing.T, h *testsupport.Harness) (string, *testsupport.ClientAccount) {
	t.Helper()
	client := h.NewClient("botclient")
	projectID := h.PublishProject(client, "Telegram bot for an online clothing store",
		"telegram-bots", []string{"python", "telegram-api", "postgresql"}, 50000, 80000)
	return projectID, client
}

func TestSubmitProposal(t *testing.T) {
	h := testsupport.New(t)
	projectID, _ := setupProject(t, h)
	dev := h.PublishDeveloper("telegramdev", "telegram-developer",
		"python", "telegram-api", "postgresql")

	res := dev.Client.POST("/proposals", goodProposal(projectID)).OK(t, http.StatusCreated)

	if res.String("status") != "submitted" {
		t.Errorf("status = %q, want submitted", res.String("status"))
	}
	if res.String("amount_display") != "$650" {
		t.Errorf("amount_display = %q, want $650", res.String("amount_display"))
	}
	if res.Float("delivery_days") != 12 {
		t.Errorf("delivery_days = %v, want 12", res.Data["delivery_days"])
	}
	if !res.Bool("is_author") {
		t.Error("the submitting developer must be told they are the author")
	}

	// The match is snapshotted at submission so a later weight change cannot
	// rewrite what the client was shown.
	if res.Data["match_score"] == nil {
		t.Error("a proposal must carry the match score as it stood when submitted")
	}
	breakdown, _ := res.Data["match_breakdown"].(map[string]any)
	if breakdown == nil {
		t.Fatal("a proposal must carry the match reasoning")
	}
	if dims, _ := breakdown["dimensions"].([]any); len(dims) != 6 {
		t.Errorf("the snapshot carries %d dimensions, want 6", len(dims))
	}

	// The project's proposal count is maintained.
	if n := h.Count(`SELECT proposals_count FROM projects WHERE id = $1`, projectID); n != 1 {
		t.Errorf("proposals_count = %d, want 1", n)
	}
}

// This is the product's central anti-spam decision: a proposal is a document,
// not a message, so "ready to do it" cannot be submitted at all.
func TestThinProposalsAreRefused(t *testing.T) {
	h := testsupport.New(t)
	projectID, _ := setupProject(t, h)
	dev := h.PublishDeveloper("spammer", "telegram-developer", "python", "telegram-api")

	cases := []struct {
		name   string
		mutate func(map[string]any)
		field  string
	}{
		{"ready to do it", func(b map[string]any) {
			b["cover_letter"] = "Ready to do it."
		}, "cover_letter"},
		{"i can do this", func(b map[string]any) {
			b["cover_letter"] = "Hi, I can do this project. Please contact me."
		}, "cover_letter"},
		{"no approach", func(b map[string]any) { b["approach"] = "" }, "approach"},
		{"one-line approach", func(b map[string]any) {
			b["approach"] = "I will use Python."
		}, "approach"},
		{"no relevant experience", func(b map[string]any) {
			b["relevant_experience"] = ""
		}, "relevant_experience"},
		{"padded with one word", func(b map[string]any) {
			b["cover_letter"] = strings.Repeat("professional ", 40)
		}, "cover_letter"},
		{"no price", func(b map[string]any) { b["amount_minor"] = 0 }, "amount_minor"},
		{"no delivery estimate", func(b map[string]any) { b["delivery_days"] = 0 }, "delivery_days"},
		{"absurd delivery estimate", func(b map[string]any) { b["delivery_days"] = 5000 }, "delivery_days"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			body := goodProposal(projectID)
			tc.mutate(body)
			res := dev.Client.POST("/proposals", body).
				Fails(t, http.StatusUnprocessableEntity, "validation_failed")
			if _, ok := res.Fields[tc.field]; !ok {
				t.Errorf("expected a problem on %q, got %v", tc.field, res.Fields)
			}
		})
	}
	if n := h.Count(`SELECT count(*) FROM proposals`); n != 0 {
		t.Errorf("proposals = %d, want 0 — none of those should have been accepted", n)
	}
}

func TestMilestonesMustAddUpToThePrice(t *testing.T) {
	h := testsupport.New(t)
	projectID, _ := setupProject(t, h)
	dev := h.PublishDeveloper("planner", "telegram-developer", "python", "telegram-api")

	body := goodProposal(projectID)
	body["milestones"] = []map[string]any{
		{"title": "Catalogue and data model", "amount_minor": 20000, "days": 4},
		{"title": "Cart and checkout", "amount_minor": 20000, "days": 4},
		// 40,000 against a 65,000 price.
	}
	res := dev.Client.POST("/proposals", body).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if !strings.Contains(res.Fields["milestones"], "$650") {
		t.Errorf("the message should name both figures, got %q", res.Fields["milestones"])
	}

	body["milestones"] = []map[string]any{
		{"title": "Catalogue and data model", "amount_minor": 20000, "days": 4},
		{"title": "Cart and checkout", "amount_minor": 25000, "days": 4},
		{"title": "Payment and admin panel", "amount_minor": 20000, "days": 4},
	}
	created := dev.Client.POST("/proposals", body).OK(t, http.StatusCreated)
	milestones, _ := created.Data["milestones"].([]any)
	if len(milestones) != 3 {
		t.Fatalf("milestones = %d, want 3", len(milestones))
	}
	first := milestones[0].(map[string]any)
	if first["position"].(float64) != 1 {
		t.Errorf("first milestone position = %v, want 1", first["position"])
	}
	if first["amount_display"] != "$200" {
		t.Errorf("first milestone display = %v, want $200", first["amount_display"])
	}
}

func TestOneLiveProposalPerProject(t *testing.T) {
	h := testsupport.New(t)
	projectID, _ := setupProject(t, h)
	dev := h.PublishDeveloper("onceonly", "telegram-developer", "python", "telegram-api")

	first := dev.Client.POST("/proposals", goodProposal(projectID)).OK(t, http.StatusCreated)
	dev.Client.POST("/proposals", goodProposal(projectID)).
		Fails(t, http.StatusConflict, "already_proposed")

	// Withdrawing frees the slot.
	dev.Client.POST("/proposals/"+first.String("id")+"/withdraw", nil).OK(t, http.StatusOK)
	dev.Client.POST("/proposals", goodProposal(projectID)).OK(t, http.StatusCreated)

	if n := h.Count(`SELECT count(*) FROM proposals WHERE status NOT IN ('withdrawn')`); n != 1 {
		t.Errorf("live proposals = %d, want 1", n)
	}
	// The count on the project reflects the withdrawal.
	if n := h.Count(`SELECT proposals_count FROM projects WHERE id = $1`, projectID); n != 1 {
		t.Errorf("proposals_count = %d, want 1 after a withdraw and a resubmit", n)
	}
}

func TestCannotBidOnAClosedOrOwnProject(t *testing.T) {
	h := testsupport.New(t)
	projectID, client := setupProject(t, h)
	dev := h.PublishDeveloper("latebidder", "telegram-developer", "python", "telegram-api")

	client.Client.POST("/projects/"+projectID+"/cancel",
		map[string]any{"reason": "no longer needed"}).OK(t, http.StatusOK)

	dev.Client.POST("/proposals", goodProposal(projectID)).
		Fails(t, http.StatusConflict, "project_closed")

	// A dual-role account cannot bid on its own brief.
	dual := h.PublishDeveloper("dualbidder", "backend-developer", "go", "postgresql")
	dual.Client.POST("/auth/role/add", map[string]any{"role": "client"}).OK(t, http.StatusOK)
	dual.Client.POST("/auth/role/switch", map[string]any{"role": "client"}).OK(t, http.StatusOK)
	own := dual.Client.POST("/projects", map[string]any{
		"title":            "A project I am posting myself here",
		"description":      strings.Repeat("a real description here. ", 5),
		"category_slug":    "backend-development",
		"required_skills":  []string{"go"},
		"budget_max_minor": 200000,
		"currency":         "USD",
		"publish":          true,
	}).OK(t, http.StatusCreated)
	dual.Client.POST("/auth/role/switch", map[string]any{"role": "developer"}).OK(t, http.StatusOK)

	body := goodProposal(own.String("id"))
	res := dual.Client.POST("/proposals", body)
	if res.Status == http.StatusCreated {
		t.Error("a client must not be able to bid on their own project")
	}
}

// The daily cap is what stops one developer carpet-bombing every open brief.
func TestDailyProposalCapApplies(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("manyprojects")
	dev := h.PublishDeveloper("prolific", "backend-developer", "go", "postgresql", "docker")

	h.SetSetting("proposals.max_per_day", 3)

	var lastStatus int
	var lastCode string
	for i := 0; i < 5; i++ {
		projectID := h.PublishProject(client,
			"Backend service number "+string(rune('A'+i))+" for us", "backend-development",
			[]string{"go", "postgresql"}, 100000, 300000)
		res := dev.Client.POST("/proposals", goodProposal(projectID))
		lastStatus, lastCode = res.Status, res.Code
		if res.Status == http.StatusTooManyRequests {
			if i < 3 {
				t.Fatalf("the cap fired after only %d proposals", i)
			}
			break
		}
	}
	if lastStatus != http.StatusTooManyRequests || lastCode != "proposal_limit_reached" {
		t.Errorf("the daily cap never fired: last status %d, code %q", lastStatus, lastCode)
	}
}

// ── Authorisation: the proposal inbox is the most sensitive list on the
//    platform, because it contains competitors' prices.

func TestProposalsAreVisibleOnlyToTheirParties(t *testing.T) {
	h := testsupport.New(t)
	projectID, client := setupProject(t, h)
	dev := h.PublishDeveloper("bidder", "telegram-developer", "python", "telegram-api")

	created := dev.Client.POST("/proposals", goodProposal(projectID)).OK(t, http.StatusCreated)
	proposalID := created.String("id")

	// The author and the client on the project can read it.
	dev.Client.GET("/proposals/"+proposalID).OK(t, http.StatusOK)
	client.Client.GET("/proposals/"+proposalID).OK(t, http.StatusOK)

	// A competing developer cannot — and gets a 404, because confirming that
	// a proposal exists tells them someone else bid.
	competitor := h.PublishDeveloper("competitor", "telegram-developer", "python", "telegram-api")
	competitor.Client.GET("/proposals/"+proposalID).Fails(t, http.StatusNotFound, "not_found")

	// Neither can an unrelated client.
	other := h.NewClient("unrelatedclient")
	other.Client.GET("/proposals/"+proposalID).Fails(t, http.StatusNotFound, "not_found")

	// Nor an anonymous visitor.
	h.Client().GET("/proposals/"+proposalID).Fails(t, http.StatusUnauthorized, "unauthenticated")
}

func TestProposalListIsOwnerOnly(t *testing.T) {
	h := testsupport.New(t)
	projectID, client := setupProject(t, h)
	dev := h.PublishDeveloper("listbidder", "telegram-developer", "python", "telegram-api")
	dev.Client.POST("/proposals", goodProposal(projectID)).OK(t, http.StatusCreated)

	own := client.Client.GET("/projects/"+projectID+"/proposals").OK(t, http.StatusOK)
	if len(own.List) != 1 {
		t.Errorf("the project owner sees %d proposals, want 1", len(own.List))
	}

	// Changing the project id in the URL reaches nothing.
	attacker := h.NewClient("attackerclient")
	attacker.Client.GET("/projects/"+projectID+"/proposals").
		Fails(t, http.StatusNotFound, "not_found")
	// A developer has no route to the list at all.
	dev.Client.GET("/projects/"+projectID+"/proposals").
		Fails(t, http.StatusForbidden, "forbidden")
}

func TestClientTriageNoteIsNotVisibleToTheDeveloper(t *testing.T) {
	h := testsupport.New(t)
	projectID, client := setupProject(t, h)
	dev := h.PublishDeveloper("notedbidder", "telegram-developer", "python", "telegram-api")
	created := dev.Client.POST("/proposals", goodProposal(projectID)).OK(t, http.StatusCreated)
	proposalID := created.String("id")

	client.Client.POST("/proposals/"+proposalID+"/shortlist", map[string]any{
		"shortlisted": true,
		"note":        "Cheapest of the three, but I am not sure about the timeline.",
	}).OK(t, http.StatusOK)

	clientView := client.Client.GET("/proposals/"+proposalID).OK(t, http.StatusOK)
	if clientView.String("client_note") == "" {
		t.Error("the client must see their own note")
	}

	devView := dev.Client.GET("/proposals/"+proposalID).OK(t, http.StatusOK)
	if devView.String("client_note") != "" {
		t.Errorf("the developer must not see the client's private note, got %q",
			devView.String("client_note"))
	}
	listed := dev.Client.GET("/proposals/mine").OK(t, http.StatusOK)
	for _, raw := range listed.List {
		row := raw.(map[string]any)
		if note, _ := row["client_note"].(string); note != "" {
			t.Errorf("the client's note leaked into the developer's own list: %q", note)
		}
	}
}

// Evidence must belong to the developer attaching it.
func TestCannotAttachSomeoneElsesWorkAsEvidence(t *testing.T) {
	h := testsupport.New(t)
	projectID, _ := setupProject(t, h)

	victim := h.PublishDeveloper("victimdev", "telegram-developer", "python", "telegram-api")
	attacker := h.PublishDeveloper("attackerdev", "telegram-developer", "python", "telegram-api")

	// A published portfolio project belonging to the victim.
	var portfolioID string
	h.QueryRow([]any{&portfolioID}, `
		INSERT INTO portfolio_projects (developer_id, slug, title, description, is_published)
		VALUES ((SELECT id FROM users WHERE username = 'victimdev'),
		        'victim-work', 'Work that belongs to someone else',
		        'A real portfolio project.', true)
		RETURNING id::text`)

	body := goodProposal(projectID)
	body["portfolio_ids"] = []string{portfolioID}
	res := attacker.Client.POST("/proposals", body).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if res.Fields["portfolio_ids"] == "" {
		t.Error("attaching another developer's work must be refused on the field")
	}
	// The message must not confirm that the id exists.
	if strings.Contains(res.Fields["portfolio_ids"], portfolioID) {
		t.Error("the message echoes the id, confirming it exists")
	}
	if n := h.Count(`SELECT count(*) FROM proposals`); n != 0 {
		t.Errorf("proposals = %d, want 0", n)
	}

	// The owner can attach it.
	ownBody := goodProposal(projectID)
	ownBody["portfolio_ids"] = []string{portfolioID}
	created := victim.Client.POST("/proposals", ownBody).OK(t, http.StatusCreated)
	evidence, _ := created.Data["evidence"].([]any)
	if len(evidence) != 1 {
		t.Fatalf("evidence = %d, want 1", len(evidence))
	}
	item := evidence[0].(map[string]any)
	if item["kind"] != "portfolio" {
		t.Errorf("evidence kind = %v, want portfolio", item["kind"])
	}
}

// ── Client triage ───────────────────────────────────────────────────────────

func TestViewingAProposalMarksItViewed(t *testing.T) {
	h := testsupport.New(t)
	projectID, client := setupProject(t, h)
	dev := h.PublishDeveloper("viewedbidder", "telegram-developer", "python", "telegram-api")
	created := dev.Client.POST("/proposals", goodProposal(projectID)).OK(t, http.StatusCreated)
	proposalID := created.String("id")

	// The developer reading their own proposal does not mark it viewed.
	dev.Client.GET("/proposals/"+proposalID).OK(t, http.StatusOK)
	if n := h.Count(`SELECT count(*) FROM proposals WHERE viewed_at IS NOT NULL`); n != 0 {
		t.Error("the author reading their own proposal must not mark it viewed")
	}

	client.Client.GET("/proposals/"+proposalID).OK(t, http.StatusOK)
	h.WaitFor("the proposal to be marked viewed", func() bool {
		return h.Count(`SELECT count(*) FROM proposals WHERE viewed_at IS NOT NULL`) == 1
	})
	var status string
	h.QueryRow([]any{&status}, `SELECT status FROM proposals WHERE id = $1`, proposalID)
	if status != "viewed" {
		t.Errorf("status = %q after the client opened it, want viewed", status)
	}
}

func TestShortlistAndDecline(t *testing.T) {
	h := testsupport.New(t)
	projectID, client := setupProject(t, h)
	dev := h.PublishDeveloper("triaged", "telegram-developer", "python", "telegram-api")
	created := dev.Client.POST("/proposals", goodProposal(projectID)).OK(t, http.StatusCreated)
	proposalID := created.String("id")

	client.Client.POST("/proposals/"+proposalID+"/shortlist",
		map[string]any{"shortlisted": true}).OK(t, http.StatusOK)
	if n := h.Count(`SELECT shortlisted_count FROM projects WHERE id = $1`, projectID); n != 1 {
		t.Errorf("shortlisted_count = %d, want 1", n)
	}

	// Un-shortlisting reverses it without losing the viewed state.
	client.Client.POST("/proposals/"+proposalID+"/shortlist",
		map[string]any{"shortlisted": false}).OK(t, http.StatusOK)
	if n := h.Count(`SELECT shortlisted_count FROM projects WHERE id = $1`, projectID); n != 0 {
		t.Errorf("shortlisted_count = %d, want 0", n)
	}
	var status string
	h.QueryRow([]any{&status}, `SELECT status FROM proposals WHERE id = $1`, proposalID)
	if status != "viewed" {
		t.Errorf("status = %q after un-shortlisting, want viewed", status)
	}

	client.Client.POST("/proposals/"+proposalID+"/decline",
		map[string]any{"reason": "Going with someone who has done payments before."}).
		OK(t, http.StatusOK)

	// Declining twice is refused rather than silently repeated.
	client.Client.POST("/proposals/"+proposalID+"/decline", map[string]any{"reason": "again"}).
		Fails(t, http.StatusConflict, "cannot_decline")

	// The developer sees the outcome.
	view := dev.Client.GET("/proposals/"+proposalID).OK(t, http.StatusOK)
	if view.String("status") != "declined" {
		t.Errorf("status = %q, want declined", view.String("status"))
	}
	if view.String("decline_reason") == "" {
		t.Error("the developer should see why it was declined")
	}
}

func TestProposalOrdering(t *testing.T) {
	h := testsupport.New(t)
	projectID, client := setupProject(t, h)

	cheapSlow := h.PublishDeveloper("cheapslow", "telegram-developer", "python", "telegram-api")
	body := goodProposal(projectID)
	body["amount_minor"] = 40000
	body["delivery_days"] = 30
	cheapSlow.Client.POST("/proposals", body).OK(t, http.StatusCreated)

	dearFast := h.PublishDeveloper("dearfast", "telegram-developer",
		"python", "telegram-api", "postgresql")
	body = goodProposal(projectID)
	body["amount_minor"] = 78000
	body["delivery_days"] = 7
	dearFast.Client.POST("/proposals", body).OK(t, http.StatusCreated)

	byPrice := client.Client.GET("/projects/"+projectID+"/proposals?sort=price_low").
		OK(t, http.StatusOK)
	if first := byPrice.List[0].(map[string]any); first["amount_minor"].(float64) != 40000 {
		t.Errorf("price_low put %v first, want 40000", first["amount_minor"])
	}

	byFastest := client.Client.GET("/projects/"+projectID+"/proposals?sort=fastest").
		OK(t, http.StatusOK)
	if first := byFastest.List[0].(map[string]any); first["delivery_days"].(float64) != 7 {
		t.Errorf("fastest put %v days first, want 7", first["delivery_days"])
	}

	// The recommended order puts the better technical match first: the
	// developer who has all three required technologies.
	recommended := client.Client.GET("/projects/"+projectID+"/proposals?sort=recommended").
		OK(t, http.StatusOK)
	first := recommended.List[0].(map[string]any)
	developer := first["developer"].(map[string]any)
	if developer["username"] != "dearfast" {
		t.Errorf("recommended put %v first; the closer technical match should lead",
			developer["username"])
	}

	// An unknown sort is refused rather than silently ignored.
	client.Client.GET("/projects/"+projectID+"/proposals?sort=whatever").
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
}

func TestProposalCardsAreCompactAndComparable(t *testing.T) {
	h := testsupport.New(t)
	projectID, client := setupProject(t, h)
	dev := h.PublishDeveloper("cardbidder", "telegram-developer",
		"python", "telegram-api", "postgresql", "redis", "docker", "go")
	dev.Client.POST("/proposals", goodProposal(projectID)).OK(t, http.StatusCreated)

	res := client.Client.GET("/projects/"+projectID+"/proposals").OK(t, http.StatusOK)
	card := res.List[0].(map[string]any)

	for _, field := range []string{"amount_display", "delivery_days", "preview",
		"match_score", "developer", "status"} {
		if card[field] == nil {
			t.Errorf("a proposal card is missing %q", field)
		}
	}
	if preview, _ := card["preview"].(string); len(preview) > 200 {
		t.Errorf("the preview is %d characters; the card shows about two lines", len(preview))
	}

	developer := card["developer"].(map[string]any)
	skills, _ := developer["skills"].([]any)
	if len(skills) > 5 {
		t.Errorf("a card lists %d technologies; five is what fits", len(skills))
	}
	// The project's own requirements come first, so a client scanning sees
	// the relevant ones.
	if len(skills) > 0 {
		leading := skills[0].(string)
		if leading != "Python" && leading != "Telegram Bot API" && leading != "PostgreSQL" {
			t.Errorf("the first listed technology is %q; a required one should lead", leading)
		}
	}
	// Nothing private about the developer appears on a card.
	for _, forbidden := range []string{"email", "total_earned_minor", "earnings"} {
		if _, present := developer[forbidden]; present {
			t.Errorf("a proposal card exposes %q", forbidden)
		}
	}
	if highlights, _ := card["match_highlights"].([]any); len(highlights) == 0 {
		t.Error("a card's match score must be expandable into reasons")
	}
}

func TestWithdrawIsAuthorOnly(t *testing.T) {
	h := testsupport.New(t)
	projectID, client := setupProject(t, h)
	dev := h.PublishDeveloper("author", "telegram-developer", "python", "telegram-api")
	created := dev.Client.POST("/proposals", goodProposal(projectID)).OK(t, http.StatusCreated)
	proposalID := created.String("id")

	other := h.PublishDeveloper("notauthor", "telegram-developer", "python", "telegram-api")
	other.Client.POST("/proposals/"+proposalID+"/withdraw", nil).
		Fails(t, http.StatusNotFound, "not_found")

	// A client cannot withdraw a developer's proposal either — the endpoint is
	// developer-only.
	client.Client.POST("/proposals/"+proposalID+"/withdraw", nil).
		Fails(t, http.StatusForbidden, "forbidden")

	dev.Client.POST("/proposals/"+proposalID+"/withdraw", nil).OK(t, http.StatusOK)
}

func TestSubmittingRequiresAConfirmedAddress(t *testing.T) {
	h := testsupport.New(t)
	projectID, _ := setupProject(t, h)

	c := h.Client()
	c.RegisterDeveloper("unconfirmed")
	// Onboarding is incomplete and the address unconfirmed; either is enough
	// to refuse, and the confirmation check comes first in the middleware.
	c.POST("/proposals", goodProposal(projectID)).
		Fails(t, http.StatusForbidden, "email_not_verified")
}
