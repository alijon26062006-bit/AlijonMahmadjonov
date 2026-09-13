package reviews_test

import (
	"context"
	"net/http"
	"strings"
	"testing"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/testsupport"
)

func proposal(projectID string) map[string]any {
	return map[string]any{
		"project_id": projectID, "amount_minor": 65000, "currency": "USD", "delivery_days": 12,
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

// completedContract hires through the API, then finishes the contract the way
// the state machine would — the milestone flow is contracts' own test; what
// matters here is a contract that is genuinely completed.
func completedContract(t *testing.T, h *testsupport.Harness) (string, *testsupport.ClientAccount, *testsupport.Developer) {
	t.Helper()
	client := h.NewClient("acmeco")
	projectID := h.PublishProject(client, "Telegram bot for an online clothing store",
		"telegram-bots", []string{"python", "telegram-api", "postgresql"}, 50000, 80000)
	dev := h.PublishDeveloper("telegramdev", "telegram-developer", "python", "telegram-api", "postgresql")
	proposalID := dev.Client.POST("/proposals", proposal(projectID)).OK(t, http.StatusCreated).String("id")
	contractID := client.Client.POST("/contracts", map[string]any{"proposal_id": proposalID}).
		OK(t, http.StatusCreated).String("id")

	h.Exec(`UPDATE contracts SET status = 'completed', completed_at = now(), progress_percent = 100 WHERE id = $1`, contractID)
	h.App.Reviews.ContractCompleted(context.Background(), uuid.MustParse(contractID))
	return contractID, client, dev
}

func TestReviewsAreBlindUntilBothSubmit(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, dev := completedContract(t, h)

	// Completion wrote the verified history entry, derived from the contract.
	history := h.Client().GET("/developers/telegramdev/history").OK(t, http.StatusOK)
	if len(history.List) != 1 {
		t.Fatalf("history entries = %d, want 1", len(history.List))
	}
	entry := history.List[0].(map[string]any)
	if entry["title"] != "Telegram bot for an online clothing store" {
		t.Errorf("history title = %v", entry["title"])
	}
	if entry["client_rating"] != nil {
		t.Error("no rating before a review is published")
	}

	panel := client.Client.GET("/contracts/"+contractID+"/reviews").OK(t, http.StatusOK)
	if !panel.Bool("can_review") {
		t.Fatalf("the client must be able to review a completed contract: %s", panel.Raw)
	}
	if panel.String("my_direction") != "of_developer" {
		t.Errorf("my_direction = %q, want of_developer", panel.String("my_direction"))
	}

	// The client scores with the wrong categories: rejected field by field.
	bad := client.Client.POST("/contracts/"+contractID+"/reviews", map[string]any{
		"scores": map[string]int{"clarity": 5},
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if _, ok := bad.Fields["scores.quality"]; !ok {
		t.Errorf("a missing category must be named, got %v", bad.Fields)
	}
	if _, ok := bad.Fields["scores.clarity"]; !ok {
		t.Errorf("a category from the other side must be rejected, got %v", bad.Fields)
	}

	mine := client.Client.POST("/contracts/"+contractID+"/reviews", map[string]any{
		"scores":           map[string]int{"quality": 5, "communication": 4, "technical": 5, "deadline": 4},
		"comment":          "Сделал всё, как договаривались, и предупредил заранее о задержке с оплатой.",
		"would_work_again": true,
	}).OK(t, http.StatusCreated)
	if mine.Float("overall") != 4.5 {
		t.Errorf("overall = %v, want the mean 4.5", mine.Data["overall"])
	}
	if mine.Data["published_at"] != nil {
		t.Error("a single review must not be published yet")
	}

	// The freelancer sees that the client has written, not what.
	theirs := dev.Client.GET("/contracts/"+contractID+"/reviews").OK(t, http.StatusOK)
	ofDev, _ := theirs.Data["of_developer"].(map[string]any)
	if ofDev["submitted"] != true {
		t.Error("the other side's submission is not a secret")
	}
	if ofDev["review"] != nil {
		t.Error("the other side's content must be withheld until publication")
	}
	if got := h.Count(`SELECT count(*) FROM notifications WHERE type = 'review_received'`); got != 1 {
		t.Errorf("review_received notifications = %d, want 1", got)
	}

	// Nothing public yet.
	public := h.Client().GET("/developers/telegramdev/reviews").OK(t, http.StatusOK)
	if len(public.List) != 0 {
		t.Errorf("unpublished review is visible publicly: %d", len(public.List))
	}

	// A second attempt from the same side is refused.
	client.Client.POST("/contracts/"+contractID+"/reviews", map[string]any{
		"scores": map[string]int{"quality": 1, "communication": 1, "technical": 1, "deadline": 1},
	}).Fails(t, http.StatusConflict, "already_reviewed")

	// The freelancer writes theirs: both publish together.
	dev.Client.POST("/contracts/"+contractID+"/reviews", map[string]any{
		"scores": map[string]int{"communication": 5, "clarity": 4, "collaboration": 5, "payment_reliability": 5},
	}).OK(t, http.StatusCreated)

	public = h.Client().GET("/developers/telegramdev/reviews").OK(t, http.StatusOK)
	if len(public.List) != 1 {
		t.Fatalf("published developer reviews = %d, want 1", len(public.List))
	}
	summary, _ := public.Meta["summary"].(map[string]any)
	if summary == nil || summary["count"] != float64(1) {
		t.Errorf("summary = %v, want count 1", public.Meta["summary"])
	}
	clientReviews := h.Client().GET("/clients/acmeco/reviews").OK(t, http.StatusOK)
	if len(clientReviews.List) != 1 {
		t.Errorf("published client reviews = %d, want 1", len(clientReviews.List))
	}

	// The profile aggregates and the history entry follow the publication.
	profile := h.Client().GET("/developers/telegramdev").OK(t, http.StatusOK)
	rep, _ := profile.Data["reputation"].(map[string]any)
	if rep == nil || rep["rating_count"] != float64(1) || rep["rating_avg"] != 4.5 {
		t.Errorf("reputation = %v, want one rating of 4.5", profile.Data["reputation"])
	}
	history = h.Client().GET("/developers/telegramdev/history").OK(t, http.StatusOK)
	entry = history.List[0].(map[string]any)
	if entry["client_rating"] != 4.5 {
		t.Errorf("history client_rating = %v, want 4.5", entry["client_rating"])
	}

	// The subject may answer once, in public.
	reviewID := mine.String("id")
	answered := dev.Client.POST("/reviews/"+reviewID+"/response", map[string]any{
		"response": "Спасибо! Было приятно работать, задача была поставлена очень чётко.",
	}).OK(t, http.StatusOK)
	if !strings.Contains(answered.String("response"), "Спасибо") {
		t.Errorf("response not recorded: %s", answered.Raw)
	}
	dev.Client.POST("/reviews/"+reviewID+"/response", map[string]any{
		"response": "И ещё раз спасибо, второй ответ не нужен.",
	}).Fails(t, http.StatusNotFound, "not_found")
	// The author cannot answer their own review.
	client.Client.POST("/reviews/"+reviewID+"/response", map[string]any{
		"response": "Пытаюсь ответить сам себе, чего быть не должно.",
	}).Fails(t, http.StatusNotFound, "not_found")
}

func TestReviewRequiresACompletedContractAndAParty(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("acmeco")
	projectID := h.PublishProject(client, "Telegram bot for an online clothing store",
		"telegram-bots", []string{"python", "telegram-api"}, 50000, 80000)
	dev := h.PublishDeveloper("telegramdev", "telegram-developer", "python", "telegram-api")
	proposalID := dev.Client.POST("/proposals", proposal(projectID)).OK(t, http.StatusCreated).String("id")
	contractID := client.Client.POST("/contracts", map[string]any{"proposal_id": proposalID}).
		OK(t, http.StatusCreated).String("id")

	body := map[string]any{"scores": map[string]int{"quality": 5, "communication": 5, "technical": 5, "deadline": 5}}
	client.Client.POST("/contracts/"+contractID+"/reviews", body).
		Fails(t, http.StatusConflict, "contract_not_completed")

	// A stranger gets not found, not forbidden: the contract's existence is
	// not theirs to learn.
	stranger := h.NewClient("stranger")
	stranger.Client.POST("/contracts/"+contractID+"/reviews", body).
		Fails(t, http.StatusNotFound, "not_found")
	stranger.Client.GET("/contracts/"+contractID+"/reviews").
		Fails(t, http.StatusNotFound, "not_found")
}

func TestSingleReviewPublishesWhenTheWindowCloses(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, _ := completedContract(t, h)

	client.Client.POST("/contracts/"+contractID+"/reviews", map[string]any{
		"scores": map[string]int{"quality": 3, "communication": 3, "technical": 3, "deadline": 3},
	}).OK(t, http.StatusCreated)

	summary, err := h.App.Reviews.PublishExpired(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if summary != "" {
		t.Errorf("nothing should publish inside the window, got %q", summary)
	}

	// Move completion back past the window; the worker publishes the lone review.
	h.Exec(`UPDATE contracts SET completed_at = now() - interval '15 days' WHERE id = $1`, contractID)
	summary, err = h.App.Reviews.PublishExpired(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(summary, "published 1") {
		t.Errorf("summary = %q", summary)
	}
	public := h.Client().GET("/developers/telegramdev/reviews").OK(t, http.StatusOK)
	if len(public.List) != 1 {
		t.Errorf("published reviews after the window = %d, want 1", len(public.List))
	}

	// And the window is closed for the side that stayed silent.
	panel := client.Client.GET("/contracts/"+contractID+"/reviews").OK(t, http.StatusOK)
	if panel.Bool("can_review") {
		t.Error("the author's side is done; can_review must be false")
	}
}
