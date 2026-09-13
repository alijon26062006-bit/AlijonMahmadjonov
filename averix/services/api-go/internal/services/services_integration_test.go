package services_test

import (
	"net/http"
	"strings"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

func offer() map[string]any {
	return map[string]any{
		"title":         "Telegram-бот для приёма заказов под ключ",
		"summary":       "Бот с каталогом, корзиной и оплатой — за неделю, с исходниками.",
		"description":   strings.Repeat("Сделаю Telegram-бота для приёма заказов: каталог, корзина, оплата, уведомления менеджеру. ", 2),
		"category_slug": "telegram-bots",
		"currency":      "USD",
		"revisions":     2,
		"skills":        []string{"python", "telegram-api"},
		"tiers": []map[string]any{
			{"name": "Базовый", "price_minor": 30000, "delivery_days": 7, "revisions": 1,
				"includes": []string{"Каталог", "Корзина"}},
			{"name": "Стандарт", "price_minor": 60000, "delivery_days": 10, "revisions": 2,
				"includes": []string{"Каталог", "Корзина", "Оплата"}},
		},
	}
}

func TestPublishAndOrderAService(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("botmaker", "telegram-developer", "python", "telegram-api")
	client := h.NewClient("buyer")

	// A draft may be saved without skills; publishing is where the full
	// standard applies.
	thin := offer()
	delete(thin, "skills")
	delete(thin, "summary")
	created := dev.Client.POST("/services", thin).OK(t, http.StatusCreated)
	serviceID := created.String("id")
	if created.String("status") != "draft" {
		t.Fatalf("status = %q, want draft", created.String("status"))
	}
	if created.String("from_display") != "$300" {
		t.Errorf("from_display = %q, want $300 (the base tier)", created.String("from_display"))
	}

	problems := dev.Client.POST("/services/"+serviceID+"/publish", nil).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if _, ok := problems.Fields["skills"]; !ok {
		t.Errorf("publishing without skills must say so, got %v", problems.Fields)
	}

	// Nobody else sees a draft, not even as "exists".
	client.Client.GET("/services/"+serviceID).Fails(t, http.StatusNotFound, "not_found")
	if list := h.Client().GET("/services").OK(t, http.StatusOK); len(list.List) != 0 {
		t.Errorf("a draft appeared in the catalogue")
	}

	dev.Client.PATCH("/services/"+serviceID, offer()).OK(t, http.StatusOK)
	live := dev.Client.POST("/services/"+serviceID+"/publish", nil).OK(t, http.StatusOK)
	if live.String("status") != "active" {
		t.Fatalf("status after publish = %q", live.String("status"))
	}

	// Public now: anonymous catalogue, category filter, search, seller list.
	catalogue := h.Client().GET("/services?category=it").OK(t, http.StatusOK)
	if len(catalogue.List) != 1 {
		t.Fatalf("catalogue under the IT sector = %d, want 1", len(catalogue.List))
	}
	if h.Client().GET("/services?category=design").OK(t, http.StatusOK).List != nil {
		if n := len(h.Client().GET("/services?category=design").OK(t, http.StatusOK).List); n != 0 {
			t.Errorf("a Telegram service is listed under design: %d", n)
		}
	}
	search := h.Client().GET("/services?q="+"заказов").OK(t, http.StatusOK)
	if len(search.List) != 1 {
		t.Errorf("Russian full-text search found %d, want 1", len(search.List))
	}
	seller := h.Client().GET("/developers/botmaker/services").OK(t, http.StatusOK)
	if len(seller.List) != 1 {
		t.Errorf("seller list = %d, want 1", len(seller.List))
	}
	page := client.Client.GET("/services/"+serviceID).OK(t, http.StatusOK)
	if !page.Bool("can_order") {
		t.Error("a client viewing a live service must be able to order it")
	}
	if page.Data["moderation_state"] != nil {
		t.Error("moderation state is not a buyer's business")
	}

	// The seller cannot buy their own service; a client with a thin brief is
	// told what is missing; a wrong tier does not exist.
	dev.Client.POST("/services/"+serviceID+"/order", map[string]any{"tier": 1, "brief": "x"}).
		Fails(t, http.StatusForbidden, "forbidden")
	client.Client.POST("/services/"+serviceID+"/order", map[string]any{"tier": 3, "brief": "short"}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	order := client.Client.POST("/services/"+serviceID+"/order", map[string]any{
		"tier":  2,
		"brief": "Магазин домашней выпечки: 40 позиций, самовывоз и доставка по городу, оплата картой.",
	}).OK(t, http.StatusCreated)
	if order.String("status") != "pending_funding" {
		t.Errorf("order contract status = %q, want pending_funding", order.String("status"))
	}
	if order.Float("amount_minor") != 60000 {
		t.Errorf("amount_minor = %v, want the tier price 60000", order.Data["amount_minor"])
	}
	milestones, _ := order.Data["milestones"].([]any)
	if len(milestones) != 1 {
		t.Errorf("an order is one milestone, got %d", len(milestones))
	}
	if !strings.Contains(order.String("title"), "Стандарт") {
		t.Errorf("the contract title should name the tier, got %q", order.String("title"))
	}

	// The seller sees the new contract and the order counted.
	mine := dev.Client.GET("/contracts").OK(t, http.StatusOK)
	if len(mine.List) != 1 {
		t.Errorf("seller contracts = %d, want 1", len(mine.List))
	}
	after := dev.Client.GET("/services/"+serviceID).OK(t, http.StatusOK)
	if after.Float("orders_count") != 1 {
		t.Errorf("orders_count = %v, want 1", after.Data["orders_count"])
	}
	// The hidden project behind the order never reaches a feed.
	if got := h.Count(`SELECT count(*) FROM projects WHERE visibility = 'private' AND status = 'in_progress'`); got != 1 {
		t.Errorf("order projects = %d, want 1 private in-progress project", got)
	}
	feed := dev.Client.GET("/projects?tab=recent").OK(t, http.StatusOK)
	if len(feed.List) != 0 {
		t.Errorf("the order's project leaked into the feed: %d", len(feed.List))
	}

	// Paused services leave the catalogue but stay the owner's.
	dev.Client.POST("/services/"+serviceID+"/pause", nil).OK(t, http.StatusOK)
	if n := len(h.Client().GET("/services").OK(t, http.StatusOK).List); n != 0 {
		t.Errorf("a paused service is still in the catalogue: %d", n)
	}
	if n := len(dev.Client.GET("/services/mine/list").OK(t, http.StatusOK).List); n != 1 {
		t.Errorf("the owner's list = %d, want 1", n)
	}
	dev.Client.POST("/services/"+serviceID+"/archive", nil).OK(t, http.StatusOK)
	dev.Client.POST("/services/"+serviceID+"/publish", nil).Fails(t, http.StatusConflict, "service_status_conflict")
}

func TestServiceValidation(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("botmaker", "telegram-developer", "python")

	bad := offer()
	bad["tiers"] = []map[string]any{
		{"name": "Дорогой", "price_minor": 60000, "delivery_days": 7},
		{"name": "Дешёвый", "price_minor": 30000, "delivery_days": 7},
	}
	res := dev.Client.POST("/services", bad).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if _, ok := res.Fields["tiers.1.price_minor"]; !ok {
		t.Errorf("tiers must ascend in price, got %v", res.Fields)
	}

	stranger := h.PublishDeveloper("other", "backend-developer", "go")
	created := dev.Client.POST("/services", offer()).OK(t, http.StatusCreated)
	stranger.Client.PATCH("/services/"+created.String("id"), offer()).Fails(t, http.StatusNotFound, "not_found")
	stranger.Client.POST("/services/"+created.String("id")+"/publish", nil).Fails(t, http.StatusNotFound, "not_found")
}
