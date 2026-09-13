package moderation_test

import (
	"net/http"
	"strings"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

func TestReportsAndTheQueue(t *testing.T) {
	h := testsupport.New(t)
	root := h.NewAdmin("operator")
	dev := h.PublishDeveloper("seller", "telegram-developer", "python", "telegram-api")
	client := h.NewClient("buyer")

	// A service whose description invites people off the platform is flagged
	// on creation, without being refused.
	created := dev.Client.POST("/services", map[string]any{
		"title":         "Telegram-бот для приёма заказов под ключ",
		"summary":       "Бот с каталогом, корзиной и оплатой — за неделю, с исходниками.",
		"description":   strings.Repeat("Сделаю бота под ключ. ", 4) + "Пишите мне напрямую в telegram @seller_direct или на +7 999 123-45-67, договоримся дешевле.",
		"category_slug": "telegram-bots", "currency": "USD", "revisions": 1,
		"skills": []string{"python"},
		"tiers":  []map[string]any{{"name": "Базовый", "price_minor": 30000, "delivery_days": 7}},
	}).OK(t, http.StatusCreated)
	serviceID := created.String("id")
	dev.Client.POST("/services/"+serviceID+"/publish", nil).OK(t, http.StatusOK)

	queue := root.Client.GET("/admin/moderation/queue").OK(t, http.StatusOK)
	if len(queue.List) != 1 {
		t.Fatalf("queue = %d, want the flagged service: %s", len(queue.List), queue.Raw)
	}
	item := queue.List[0].(map[string]any)
	if item["subject_type"] != "service" || item["origin"] != "automatic" {
		t.Errorf("queue item = %v", item)
	}
	preview, _ := item["preview"].(map[string]any)
	if preview["owner_username"] != "seller" {
		t.Errorf("preview must name the owner: %v", preview)
	}

	// A user report on the same service raises priority instead of duplicating.
	reasons := h.Client().GET("/reports/reasons").OK(t, http.StatusOK)
	if len(reasons.List) < 5 {
		t.Fatal("report reasons must be listed")
	}
	client.Client.POST("/reports", map[string]any{
		"subject_type": "service", "subject_id": serviceID, "reason": "off_platform_payment",
	}).OK(t, http.StatusCreated)
	client.Client.POST("/reports", map[string]any{
		"subject_type": "service", "subject_id": serviceID, "reason": "nonsense",
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	client.Client.POST("/reports", map[string]any{
		"subject_type": "user", "subject_id": client.UserID, "reason": "spam",
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	queue = root.Client.GET("/admin/moderation/queue").OK(t, http.StatusOK)
	if len(queue.List) != 1 {
		t.Fatalf("a report must not duplicate the queue item, got %d", len(queue.List))
	}
	if queue.List[0].(map[string]any)["reports"] != float64(1) {
		t.Errorf("reports count on the item = %v, want 1", queue.List[0].(map[string]any)["reports"])
	}
	itemID := queue.List[0].(map[string]any)["id"].(string)

	// Rejecting hides the service everywhere and tells the owner why.
	root.Client.POST("/admin/moderation/queue/"+itemID+"/decide", map[string]any{"outcome": "reject", "note": "x"}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	root.Client.POST("/admin/moderation/queue/"+itemID+"/decide", map[string]any{
		"outcome": "reject", "note": "Контакты в описании: общение и оплата только через платформу.", "warn": true,
	}).OK(t, http.StatusOK)

	h.Client().GET("/services/"+serviceID).Fails(t, http.StatusNotFound, "not_found")
	if n := len(h.Client().GET("/services").OK(t, http.StatusOK).List); n != 0 {
		t.Errorf("a hidden service is still in the catalogue: %d", n)
	}
	if got := h.Count(`SELECT count(*) FROM notifications WHERE type = 'account_warning'`); got != 1 {
		t.Errorf("owner warnings = %d, want 1", got)
	}
	if got := h.Count(`SELECT count(*) FROM audit_logs WHERE action = 'moderation.content_hidden'`); got != 1 {
		t.Errorf("hidden-content audit rows = %d, want 1", got)
	}
	// The owner cannot simply republish past the decision.
	dev.Client.POST("/services/"+serviceID+"/pause", nil).OK(t, http.StatusOK)
	dev.Client.POST("/services/"+serviceID+"/publish", nil).Fails(t, http.StatusConflict, "service_on_moderation")

	// Reports have their own resolution.
	reports := root.Client.GET("/admin/moderation/reports").OK(t, http.StatusOK)
	if len(reports.List) != 1 {
		t.Fatalf("open reports = %d, want 1", len(reports.List))
	}
	reportID := reports.List[0].(map[string]any)["id"].(string)
	root.Client.POST("/admin/moderation/reports/"+reportID+"/resolve", map[string]any{
		"status": "actioned", "resolution": "Услуга скрыта, владелец предупреждён.",
	}).OK(t, http.StatusOK)
	if n := len(root.Client.GET("/admin/moderation/reports").OK(t, http.StatusOK).List); n != 0 {
		t.Errorf("resolved report still open: %d", n)
	}

	// Ordinary users never see the queue.
	client.Client.GET("/admin/moderation/queue").Fails(t, http.StatusForbidden, "forbidden")
}
