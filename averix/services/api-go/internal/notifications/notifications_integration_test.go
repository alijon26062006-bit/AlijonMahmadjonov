package notifications_test

import (
	"context"
	"net/http"
	"strings"
	"testing"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/testsupport"
)

func mustUUID(t *testing.T, raw string) uuid.UUID {
	t.Helper()
	id, err := uuid.Parse(raw)
	if err != nil {
		t.Fatalf("not a uuid: %q", raw)
	}
	return id
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
			"I build the customer flow. Payment goes in after the cart works end to " +
			"end, because testing payment against a half-built cart wastes everyone's time.",
		"relevant_experience": "Six years of Python, most of it on Telegram bots and " +
			"backend services with PostgreSQL behind them.",
	}
}

func TestProposalNotifiesTheClient(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("shopowner")
	projectID := h.PublishProject(client, "Telegram bot for a clothing store",
		"telegram-bots", []string{"python", "telegram-api"}, 50000, 80000)
	dev := h.PublishDeveloper("botmaker", "telegram-developer", "python", "telegram-api")

	before := client.Client.GET("/notifications/unread").OK(t, http.StatusOK)
	if before.Float("unread") != 0 {
		t.Fatalf("a fresh client has %v unread, want 0", before.Data["unread"])
	}

	dev.Client.POST("/proposals", proposal(projectID)).OK(t, http.StatusCreated)

	res := client.Client.GET("/notifications").OK(t, http.StatusOK)
	if len(res.List) != 1 {
		t.Fatalf("notifications = %d, want 1: %s", len(res.List), res.Raw)
	}
	n := res.List[0].(map[string]any)
	if n["type"] != "proposal_received" {
		t.Errorf("type = %v, want proposal_received", n["type"])
	}
	title, _ := n["title"].(string)
	if !strings.Contains(title, "Telegram bot for a clothing store") {
		t.Errorf("the title should name the project, got %q", title)
	}
	body, _ := n["body"].(string)
	if !strings.Contains(body, "botmaker") {
		t.Errorf("the body should name who proposed, got %q", body)
	}
	href, _ := n["href"].(string)
	if !strings.HasPrefix(href, "/projects/") || !strings.HasSuffix(href, "/proposals") {
		t.Errorf("href = %q, want /projects/<slug>/proposals", href)
	}
	if n["read_at"] != nil {
		t.Error("a fresh notification must be unread")
	}
	if meta, _ := res.Meta["unread"].(float64); meta != 1 {
		t.Errorf("meta.unread = %v, want 1", res.Meta["unread"])
	}

	// The client's email is verified, so an email delivery is queued; the
	// in-app one is delivered by the act of writing the row.
	if got := h.Count(`SELECT count(*) FROM notification_deliveries WHERE channel = 'email' AND status = 'queued'`); got != 1 {
		t.Errorf("queued email deliveries = %d, want 1", got)
	}
	if got := h.Count(`SELECT count(*) FROM notification_deliveries WHERE channel = 'in_app' AND status = 'delivered'`); got != 1 {
		t.Errorf("delivered in-app rows = %d, want 1", got)
	}

	// Without SMTP the worker records the reason rather than pretending.
	summary, err := h.App.Notifier.DeliverPending(context.Background())
	if err != nil {
		t.Fatalf("DeliverPending: %v", err)
	}
	if !strings.Contains(summary, "1 skipped") {
		t.Errorf("summary = %q, want one skipped delivery", summary)
	}
	if got := h.Count(`SELECT count(*) FROM notification_deliveries WHERE channel = 'email' AND status = 'skipped' AND error = 'smtp_not_configured'`); got != 1 {
		t.Errorf("skipped-for-no-smtp rows = %d, want 1", got)
	}

	// The developer must not see the client's notification, by id or at all.
	id, _ := n["id"].(string)
	dev.Client.POST("/notifications/"+id+"/read", nil).Fails(t, http.StatusNotFound, "not_found")
	mine := dev.Client.GET("/notifications").OK(t, http.StatusOK)
	if len(mine.List) != 0 {
		t.Errorf("the developer sees %d notifications, want 0", len(mine.List))
	}

	// Reading it clears the badge.
	read := client.Client.POST("/notifications/"+id+"/read", nil).OK(t, http.StatusOK)
	if read.Float("unread") != 0 {
		t.Errorf("unread after reading = %v, want 0", read.Data["unread"])
	}
	again := client.Client.GET("/notifications?unread=true").OK(t, http.StatusOK)
	if len(again.List) != 0 {
		t.Errorf("unread filter still returns %d, want 0", len(again.List))
	}
}

func TestPreferencesSuppressEmailButNotTheRecord(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("quietclient")
	projectID := h.PublishProject(client, "Landing page copy for a bakery",
		"telegram-bots", []string{"python"}, 20000, 40000)
	dev := h.PublishDeveloper("writer", "telegram-developer", "python")

	groups := client.Client.GET("/notifications/preferences").OK(t, http.StatusOK)
	if len(groups.List) == 0 {
		t.Fatal("preferences must be grouped and non-empty")
	}
	if groups.Meta["email_configured"] != false {
		t.Errorf("email_configured = %v, want false in tests", groups.Meta["email_configured"])
	}

	client.Client.PUT("/notifications/preferences", map[string]any{
		"preferences": []map[string]any{
			{"type": "proposal_received", "in_app": true, "email": false, "push": false},
		},
	}).OK(t, http.StatusOK)

	dev.Client.POST("/proposals", proposal(projectID)).OK(t, http.StatusCreated)

	if got := h.Count(`SELECT count(*) FROM notifications WHERE type = 'proposal_received'`); got != 1 {
		t.Fatalf("notifications = %d, want 1 — switching email off must not lose the record", got)
	}
	if got := h.Count(`SELECT count(*) FROM notification_deliveries WHERE channel = 'email' AND status = 'suppressed'`); got != 1 {
		t.Errorf("suppressed email rows = %d, want 1", got)
	}

	// A locked type keeps in-app on whatever the client sends.
	client.Client.PUT("/notifications/preferences", map[string]any{
		"preferences": []map[string]any{
			{"type": "milestone_released", "in_app": false, "email": false, "push": false},
		},
	}).OK(t, http.StatusOK)
	var inApp bool
	h.QueryRow([]any{&inApp},
		`SELECT in_app FROM notification_preferences WHERE type = 'milestone_released'`)
	if !inApp {
		t.Error("milestone_released is locked to in-app and must stay on")
	}

	client.Client.PUT("/notifications/preferences", map[string]any{
		"preferences": []map[string]any{{"type": "made_up", "email": true}},
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
}

func TestUnverifiedEmailIsSkippedNotSent(t *testing.T) {
	h := testsupport.New(t)
	// Register a client without confirming the address.
	c := h.Client()
	c.RegisterClient("unverified").OK(t, http.StatusCreated)

	// A message from a stranger is not possible without a thread, so drive
	// the notifier directly: the channel decision is the thing under test.
	userID := c.UserID()
	h.App.Notifier.AccountWarning(context.Background(), mustUUID(t, userID), "Проверка канала")

	if got := h.Count(`SELECT count(*) FROM notification_deliveries WHERE channel = 'email' AND status = 'skipped' AND error = 'email not verified'`); got != 1 {
		t.Errorf("skipped-for-unverified rows = %d, want 1", got)
	}
	res := c.GET("/notifications").OK(t, http.StatusOK)
	if len(res.List) != 1 {
		t.Errorf("the in-app notification must still exist, got %d", len(res.List))
	}
}
