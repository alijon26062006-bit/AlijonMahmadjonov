package projects_test

import (
	"net/http"
	"strings"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

func TestCreateAndPublishAProject(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("storeowner")

	res := client.Client.POST("/projects", map[string]any{
		"title":   "Telegram bot for an online clothing store",
		"summary": "Catalogue, cart and payments inside Telegram.",
		"description": "We run a clothing store and want customers to browse and order " +
			"inside Telegram. We need a catalogue, a cart, payment, delivery details " +
			"and an admin panel for our staff to manage orders.",
		"category_slug":    "telegram-bots",
		"required_skills":  []string{"python", "telegram-api", "postgresql"},
		"optional_skills":  []string{"redis", "docker"},
		"budget_type":      "range",
		"budget_min_minor": 50000,
		"budget_max_minor": 80000,
		"currency":         "USD",
		"duration_days":    14,
		"starts":           "within_week",
		"features": []map[string]any{
			{"title": "Product catalogue", "required": true},
			{"title": "Shopping cart", "required": true},
			{"title": "Payment", "required": true},
			{"title": "Admin panel", "required": true},
		},
	}).OK(t, http.StatusCreated)

	if res.String("status") != "draft" {
		t.Errorf("a new project must start as a draft, got %q", res.String("status"))
	}
	if res.String("reference") == "" || !strings.HasPrefix(res.String("reference"), "AVX-") {
		t.Errorf("reference = %q, want an AVX- reference", res.String("reference"))
	}
	budget, _ := res.Data["budget"].(map[string]any)
	if budget["display"] != "$500 – $800" {
		t.Errorf("budget display = %v, want $500 – $800", budget["display"])
	}

	// Targeting is resolved from the category, not supplied by the client.
	targeting, _ := res.Data["targeting"].([]any)
	if len(targeting) == 0 {
		t.Fatal("a project must be targeted at specialisations on creation")
	}
	targeted := map[string]float64{}
	for _, raw := range targeting {
		row := raw.(map[string]any)
		targeted[row["slug"].(string)] = row["relevance"].(float64)
	}
	if targeted["telegram-developer"] != 1.0 {
		t.Errorf("telegram-developer relevance = %v, want 1.0", targeted["telegram-developer"])
	}
	if targeted["backend-developer"] != 0.65 {
		t.Errorf("backend-developer relevance = %v, want 0.65", targeted["backend-developer"])
	}
	if _, present := targeted["mobile-developer"]; present {
		t.Error("a Telegram bot project must not target mobile developers")
	}
	if _, present := targeted["ui-ux-designer"]; present {
		t.Error("a Telegram bot project must not target UI/UX designers")
	}

	projectID := res.String("id")
	published := client.Client.POST("/projects/"+projectID+"/publish", nil).OK(t, http.StatusOK)
	if published.String("status") != "open" {
		t.Errorf("status = %q after publishing, want open", published.String("status"))
	}
	if published.Data["published_at"] == nil {
		t.Error("published_at must be set")
	}
}

func TestProjectValidationRefusesEmptyBriefs(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("vague")

	cases := []struct {
		name  string
		body  map[string]any
		field string
	}{
		{"no title", map[string]any{"description": strings.Repeat("a real description here. ", 5),
			"category_slug": "telegram-bots", "budget_max_minor": 50000}, "title"},
		{"title too short", map[string]any{"title": "Bot",
			"description":   strings.Repeat("a real description here. ", 5),
			"category_slug": "telegram-bots", "budget_max_minor": 50000}, "title"},
		{"description too short", map[string]any{"title": "A Telegram bot for my store",
			"description": "Need bot.", "category_slug": "telegram-bots",
			"budget_max_minor": 50000}, "description"},
		{"no category", map[string]any{"title": "A Telegram bot for my store",
			"description":      strings.Repeat("a real description here. ", 5),
			"budget_max_minor": 50000}, "category_slug"},
		{"unknown category", map[string]any{"title": "A Telegram bot for my store",
			"description":   strings.Repeat("a real description here. ", 5),
			"category_slug": "cat-grooming", "budget_max_minor": 50000}, "category_slug"},
		{"no budget", map[string]any{"title": "A Telegram bot for my store",
			"description":   strings.Repeat("a real description here. ", 5),
			"category_slug": "telegram-bots"}, "budget_max_minor"},
		{"inverted budget", map[string]any{"title": "A Telegram bot for my store",
			"description":   strings.Repeat("a real description here. ", 5),
			"category_slug": "telegram-bots", "budget_type": "range",
			"budget_min_minor": 80000, "budget_max_minor": 50000}, "budget_max_minor"},
		{"unknown technology", map[string]any{"title": "A Telegram bot for my store",
			"description":   strings.Repeat("a real description here. ", 5),
			"category_slug": "telegram-bots", "budget_max_minor": 50000,
			"required_skills": []string{"python", "my-invented-framework"}}, "required_skills"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			res := client.Client.POST("/projects", tc.body).
				Fails(t, http.StatusUnprocessableEntity, "validation_failed")
			if _, ok := res.Fields[tc.field]; !ok {
				t.Errorf("expected a problem on %q, got %v", tc.field, res.Fields)
			}
		})
	}
}

func TestPublishingRequiresTechnologiesAndAConfirmedAddress(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterClient("unverified")

	res := c.POST("/projects", map[string]any{
		"title":            "A backend service we need built",
		"description":      strings.Repeat("a real description here. ", 5),
		"category_slug":    "backend-development",
		"budget_max_minor": 200000,
		"currency":         "USD",
	}).OK(t, http.StatusCreated)
	projectID := res.String("id")

	// Unconfirmed address.
	c.POST("/projects/"+projectID+"/publish", nil).
		Fails(t, http.StatusForbidden, "email_not_verified")

	h.Verify("unverified")

	// Confirmed, but no technologies: nobody would be targeted well.
	missing := c.POST("/projects/"+projectID+"/publish", nil).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if _, ok := missing.Fields["required_skills"]; !ok {
		t.Errorf("expected a problem on required_skills, got %v", missing.Fields)
	}

	c.PATCH("/projects/"+projectID, map[string]any{
		"required_skills": []string{"go", "postgresql"},
	}).OK(t, http.StatusOK)
	c.POST("/projects/"+projectID+"/publish", nil).OK(t, http.StatusOK)
}

// The headline promise: a project reaches the developers it is aimed at, and
// nobody else.
func TestFeedTargetingReachesTheRightDevelopersOnly(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("botclient")
	h.PublishProject(client, "Telegram bot for an online store", "telegram-bots",
		[]string{"python", "telegram-api", "postgresql"}, 50000, 80000)

	telegramDev := h.PublishDeveloper("telegramdev", "telegram-developer",
		"python", "telegram-api", "postgresql", "redis")
	backendDev := h.PublishDeveloper("pythondev", "backend-developer",
		"python", "postgresql", "docker")
	mobileDev := h.PublishDeveloper("iosdev", "mobile-developer", "swift", "kotlin")
	designer := h.PublishDeveloper("designer", "ui-ux-designer", "figma", "accessibility")

	cases := []struct {
		name      string
		dev       *testsupport.Developer
		shouldSee bool
	}{
		{"telegram specialist", telegramDev, true},
		{"python backend developer", backendDev, true},
		{"iOS developer", mobileDev, false},
		{"UI/UX designer", designer, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			res := tc.dev.Client.GET("/projects?tab=for_you").OK(t, http.StatusOK)
			if tc.shouldSee && len(res.List) == 0 {
				t.Errorf("%s should see the Telegram bot project but their feed is empty", tc.name)
			}
			if !tc.shouldSee && len(res.List) != 0 {
				t.Errorf("%s must not see the Telegram bot project, but sees %d",
					tc.name, len(res.List))
			}
		})
	}

	// And the specialist ranks above the adjacent match.
	specialistFeed := telegramDev.Client.GET("/projects?tab=for_you").OK(t, http.StatusOK)
	backendFeed := backendDev.Client.GET("/projects?tab=for_you").OK(t, http.StatusOK)
	specialistScore := firstMatchScore(t, specialistFeed.List)
	backendScore := firstMatchScore(t, backendFeed.List)
	if specialistScore <= backendScore {
		t.Errorf("the Telegram specialist scored %d and the backend developer %d; the specialist should rank higher",
			specialistScore, backendScore)
	}
}

// Every score in the feed must be expandable into reasons.
func TestFeedCardsCarryTheirMatchReasoning(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("reasonsclient")
	h.PublishProject(client, "Telegram bot with payments", "telegram-bots",
		[]string{"python", "telegram-api", "postgresql"}, 50000, 80000)
	dev := h.PublishDeveloper("reasondev", "telegram-developer",
		"python", "telegram-api", "postgresql")

	res := dev.Client.GET("/projects?tab=for_you").OK(t, http.StatusOK)
	if len(res.List) == 0 {
		t.Fatal("the feed is empty")
	}
	card := res.List[0].(map[string]any)

	if card["match_score"] == nil {
		t.Fatal("a feed card must carry a match score")
	}
	highlights, _ := card["match_highlights"].([]any)
	if len(highlights) == 0 {
		t.Fatal("a match score with no reasons is decoration")
	}
	labels := map[string]bool{}
	for _, raw := range highlights {
		item := raw.(map[string]any)
		label, _ := item["label"].(string)
		if label == "" {
			t.Error("a highlight has no label")
		}
		labels[label] = true
	}
	for _, want := range []string{"Python", "Telegram API", "PostgreSQL"} {
		if !labels[want] {
			t.Errorf("expected %q among the reasons, got %v", want, keysOf(labels))
		}
	}

	// The card must be compact: at most five technology tags.
	skills, _ := card["skills"].([]any)
	if len(skills) > 5 {
		t.Errorf("a feed card carries %d technology tags; the design allows five", len(skills))
	}
	if card["budget"] == nil {
		t.Error("a feed card must carry a pre-formatted budget")
	}
	budget := card["budget"].(map[string]any)
	if budget["display"] == "" {
		t.Error("the budget must be pre-formatted for the card")
	}
}

func TestFeedExcludesOwnAndAlreadyBidProjects(t *testing.T) {
	h := testsupport.New(t)

	// An account holding both roles: their own project must not appear in
	// their developer feed.
	dual := h.PublishDeveloper("dualrole", "backend-developer", "go", "postgresql")
	dual.Client.POST("/auth/role/add", map[string]any{"role": "client"}).OK(t, http.StatusOK)
	dual.Client.POST("/auth/role/switch", map[string]any{"role": "client"}).OK(t, http.StatusOK)
	own := dual.Client.POST("/projects", map[string]any{
		"title":            "A Go service I am posting myself",
		"description":      strings.Repeat("a real description here. ", 5),
		"category_slug":    "backend-development",
		"required_skills":  []string{"go", "postgresql"},
		"budget_max_minor": 200000,
		"currency":         "USD",
		"publish":          true,
	}).OK(t, http.StatusCreated)
	if own.String("status") != "open" {
		t.Fatalf("the project did not publish: %s", own.Raw)
	}
	dual.Client.POST("/auth/role/switch", map[string]any{"role": "developer"}).OK(t, http.StatusOK)

	feed := dual.Client.GET("/projects?tab=for_you").OK(t, http.StatusOK)
	for _, raw := range feed.List {
		card := raw.(map[string]any)
		if card["id"] == own.String("id") {
			t.Error("a client's own project must not appear in their developer feed")
		}
	}

	// A project already bid on drops out of the feed.
	client := h.NewClient("otherclient")
	projectID := h.PublishProject(client, "Another Go service to build", "backend-development",
		[]string{"go", "postgresql"}, 100000, 200000)

	before := dual.Client.GET("/projects?tab=for_you").OK(t, http.StatusOK)
	if !containsID(before.List, projectID) {
		t.Fatal("the project should be in the feed before bidding")
	}

	dual.Client.POST("/proposals", map[string]any{
		"project_id":    projectID,
		"amount_minor":  150000,
		"currency":      "USD",
		"delivery_days": 14,
		"cover_letter": "I have built several Go services with PostgreSQL behind them, " +
			"including one that handled order processing for a retailer. I would start " +
			"with the data model and the API contract before any handler code.",
		"approach": "First the schema and migrations, then the API contract, then the " +
			"handlers with tests at each step. I would set up CI on day one so nothing " +
			"lands without the tests passing, and deploy behind a reverse proxy.",
		"relevant_experience": "Six years of Go, mostly APIs and data-heavy services " +
			"backed by PostgreSQL, with Docker deployments.",
	}).OK(t, http.StatusCreated)

	after := dual.Client.GET("/projects?tab=for_you").OK(t, http.StatusOK)
	if containsID(after.List, projectID) {
		t.Error("a project already bid on must drop out of the feed")
	}
}

func TestFeedPaginationDoesNotRepeatOrSkip(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("bulkclient")
	for i := 0; i < 12; i++ {
		h.PublishProject(client,
			"Backend service number "+string(rune('A'+i))+" to build", "backend-development",
			[]string{"go", "postgresql"}, 100000, 200000)
	}
	dev := h.PublishDeveloper("paginator", "backend-developer", "go", "postgresql", "docker")

	seen := map[string]bool{}
	cursor := ""
	for page := 0; page < 5; page++ {
		url := "/projects?tab=recent&limit=5"
		if cursor != "" {
			url += "&cursor=" + cursor
		}
		res := dev.Client.GET(url).OK(t, http.StatusOK)
		for _, raw := range res.List {
			card := raw.(map[string]any)
			id := card["id"].(string)
			if seen[id] {
				t.Errorf("project %s appeared on two pages", id)
			}
			seen[id] = true
		}
		next, _ := res.Meta["next_cursor"].(string)
		hasMore, _ := res.Meta["has_more"].(bool)
		if !hasMore || next == "" {
			break
		}
		cursor = next
	}
	if len(seen) < 12 {
		t.Errorf("pagination surfaced %d of 12 projects", len(seen))
	}

	// A malformed cursor is refused rather than silently restarting.
	dev.Client.GET("/projects?tab=recent&cursor=nonsense").
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
}

// Changing a project id in the URL must not reach someone else's draft.
func TestDraftsAndPrivateProjectsAreNotVisibleToOthers(t *testing.T) {
	h := testsupport.New(t)
	owner := h.NewClient("draftowner")

	draft := owner.Client.POST("/projects", map[string]any{
		"title":            "A draft nobody else should see",
		"description":      strings.Repeat("a real description here. ", 5),
		"category_slug":    "backend-development",
		"required_skills":  []string{"go"},
		"budget_max_minor": 100000,
		"currency":         "USD",
	}).OK(t, http.StatusCreated)
	draftID := draft.String("id")

	// The owner sees it.
	owner.Client.GET("/projects/"+draftID).OK(t, http.StatusOK)

	// Nobody else does — and gets a 404 rather than a 403, so its existence is
	// not confirmed.
	h.Client().GET("/projects/"+draftID).Fails(t, http.StatusNotFound, "not_found")

	otherClient := h.NewClient("nosyclient")
	otherClient.Client.GET("/projects/"+draftID).Fails(t, http.StatusNotFound, "not_found")

	dev := h.PublishDeveloper("nosydev", "backend-developer", "go")
	dev.Client.GET("/projects/"+draftID).Fails(t, http.StatusNotFound, "not_found")
}

func TestOnlyTheOwnerCanChangeAProject(t *testing.T) {
	h := testsupport.New(t)
	owner := h.NewClient("realowner")
	projectID := h.PublishProject(owner, "A project with one owner", "backend-development",
		[]string{"go"}, 100000, 200000)

	attacker := h.NewClient("attackerclient")
	attacker.Client.PATCH("/projects/"+projectID, map[string]any{"title": "Hijacked title here"}).
		Fails(t, http.StatusNotFound, "not_found")
	attacker.Client.POST("/projects/"+projectID+"/cancel", map[string]any{"reason": "mine now"}).
		Fails(t, http.StatusNotFound, "not_found")
	attacker.Client.POST("/projects/"+projectID+"/publish", nil).
		Fails(t, http.StatusNotFound, "not_found")

	// The project is untouched.
	res := owner.Client.GET("/projects/"+projectID).OK(t, http.StatusOK)
	if res.String("title") != "A project with one owner" {
		t.Errorf("title = %q; another client's write got through", res.String("title"))
	}
	if res.String("status") != "open" {
		t.Errorf("status = %q; another client's cancel got through", res.String("status"))
	}
}

func TestDeveloperCannotCreateProjects(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("wrongrole", "backend-developer", "go")
	dev.Client.POST("/projects", map[string]any{
		"title":            "A developer trying to post a project",
		"description":      strings.Repeat("a real description here. ", 5),
		"category_slug":    "backend-development",
		"budget_max_minor": 100000,
	}).Fails(t, http.StatusForbidden, "forbidden")
}

// A project under contract cannot have its brief rewritten.
func TestProjectUnderContractIsLocked(t *testing.T) {
	h := testsupport.New(t)
	owner := h.NewClient("lockedowner")
	projectID := h.PublishProject(owner, "A project that will be under contract",
		"backend-development", []string{"go"}, 100000, 200000)

	h.Exec(`UPDATE projects SET status = 'in_progress' WHERE id = $1`, projectID)

	res := owner.Client.PATCH("/projects/"+projectID,
		map[string]any{"title": "Changing the deal after signing"}).
		Fails(t, http.StatusConflict, "project_locked")
	if !strings.Contains(res.Message, "рабочем пространстве") {
		t.Errorf("the message should point at the workspace, got %q", res.Message)
	}
}

func TestFeedTabsReflectTheDevelopersSpecialisations(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("tabowner", "telegram-developer",
		"python", "telegram-api", "postgresql")

	res := dev.Client.GET("/projects/feed/tabs").OK(t, http.StatusOK)
	if len(res.List) < 3 {
		t.Fatalf("tabs = %d, want at least For you, a category and Saved", len(res.List))
	}
	keys := []string{}
	for _, raw := range res.List {
		tab := raw.(map[string]any)
		keys = append(keys, tab["key"].(string))
		if tab["label"] == "" {
			t.Error("a tab has no label")
		}
	}
	if keys[0] != "for_you" {
		t.Errorf("the first tab is %q, want for_you", keys[0])
	}
	joined := strings.Join(keys, ",")
	if !strings.Contains(joined, "telegram") {
		t.Errorf("a Telegram developer's tabs should include a Telegram category, got %v", keys)
	}
	if !strings.Contains(joined, "saved") {
		t.Errorf("tabs should include Saved, got %v", keys)
	}
	// A Telegram developer has no reason for a mobile tab.
	if strings.Contains(joined, "mobile-applications") {
		t.Errorf("a Telegram developer should not get a mobile tab, got %v", keys)
	}
}

func firstMatchScore(t *testing.T, list []any) int {
	t.Helper()
	if len(list) == 0 {
		return 0
	}
	card := list[0].(map[string]any)
	score, ok := card["match_score"].(float64)
	if !ok {
		t.Fatalf("card carries no match score: %v", card)
	}
	return int(score)
}

func containsID(list []any, id string) bool {
	for _, raw := range list {
		card, ok := raw.(map[string]any)
		if ok && card["id"] == id {
			return true
		}
	}
	return false
}

func keysOf(m map[string]bool) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}
