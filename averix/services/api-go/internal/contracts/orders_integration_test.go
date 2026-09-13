package contracts_test

import (
	"context"
	"net/http"
	"strings"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

// orderAService publishes a service and buys it, returning the contract that
// is now waiting for the freelancer's answer.
func orderAService(t *testing.T, h *testsupport.Harness) (contractID string,
	client *testsupport.ClientAccount, dev *testsupport.Developer) {

	t.Helper()
	dev = h.PublishDeveloper("botmaker", "telegram-developer", "python", "telegram-api")
	client = h.NewClient("bakery")

	service := map[string]any{
		"title":         "Telegram-бот для приёма заказов под ключ",
		"summary":       "Бот с каталогом, корзиной и оплатой — за неделю, с исходниками.",
		"description":   strings.Repeat("Сделаю Telegram-бота: каталог, корзина, оплата, уведомления менеджеру. ", 2),
		"category_slug": "telegram-bots",
		"currency":      "USD",
		"revisions":     2,
		"skills":        []string{"python", "telegram-api"},
		"tiers": []map[string]any{
			{"name": "Базовый", "price_minor": 30000, "delivery_days": 7, "revisions": 1,
				"includes": []string{"Каталог", "Корзина"}},
		},
	}
	serviceID := dev.Client.POST("/services", service).OK(t, http.StatusCreated).String("id")
	dev.Client.POST("/services/"+serviceID+"/publish", nil).OK(t, http.StatusOK)

	order := client.Client.POST("/services/"+serviceID+"/order", map[string]any{
		"tier":  1,
		"brief": "Магазин домашней выпечки: 40 позиций, самовывоз и доставка по городу, оплата картой.",
	}).OK(t, http.StatusCreated)
	return order.String("id"), client, dev
}

// Услугу заказывают, ни о чём не спрашивая исполнителя, поэтому согласие
// должно быть его отдельным действием, а не отсутствием отказа.
func TestAServiceOrderWaitsForTheFreelancer(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, dev := orderAService(t, h)

	waiting := client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK)
	if !waiting.Bool("awaiting_confirmation") {
		t.Fatalf("a fresh service order must wait for the freelancer: %s", waiting.Raw)
	}
	if waiting.Data["confirm_deadline"] == nil {
		t.Error("the client is entitled to know by when they will have an answer")
	}

	// Пока ответа нет, по сделке ничего не двигается — даже оплата.
	seen := dev.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK)
	can, _ := seen.Data["can"].(map[string]any)
	if can["confirm_order"] != true {
		t.Errorf("the freelancer needs a way to accept, got %v", can)
	}
	if can["start_milestone"] == true || can["submit_work"] == true {
		t.Errorf("work must not start before the order is accepted: %v", can)
	}
	milestones := milestoneIDs(t, seen)
	dev.Client.POST("/milestones/"+milestones[0]+"/start", nil).
		Fails(t, http.StatusConflict, "order_not_confirmed")

	// Принять заказ может только исполнитель.
	client.Client.POST("/contracts/"+contractID+"/confirm", nil).
		Fails(t, http.StatusForbidden, "forbidden")

	confirmed := dev.Client.POST("/contracts/"+contractID+"/confirm", nil).OK(t, http.StatusOK)
	if confirmed.Bool("awaiting_confirmation") {
		t.Error("after accepting, the order is an ordinary contract")
	}
	if confirmed.Data["confirmed_at"] == nil {
		t.Error("the moment of acceptance is part of the record")
	}
	if n := h.Count(`SELECT count(*) FROM notifications WHERE type = 'order_confirmed'`); n != 1 {
		t.Errorf("order_confirmed notifications = %d, want one for the client", n)
	}

	// Второй раз принять нельзя: ответ уже дан.
	dev.Client.POST("/contracts/"+contractID+"/confirm", nil).
		Fails(t, http.StatusConflict, "order_not_awaiting")

	// А сделка из отклика подтверждения не требует: согласие там — сам отклик,
	// и спрашивать второй раз значило бы не верить первому.
	hiredID, hiringClient, _ := hire(t, h)
	hired := hiringClient.Client.GET("/contracts/"+hiredID).OK(t, http.StatusOK)
	if hired.Bool("awaiting_confirmation") {
		t.Error("a contract from an accepted proposal must not wait for a second yes")
	}
	if hired.Data["confirm_deadline"] != nil {
		t.Error("there is no confirmation window on a hire from a proposal")
	}
}

// Отказ лучше молчания: заказчик узнаёт сразу и идёт к другому.
func TestTheFreelancerCanDeclineAnOrder(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, dev := orderAService(t, h)

	dev.Client.POST("/contracts/"+contractID+"/decline", map[string]any{
		"reason": "Занят до конца месяца, не успею в срок.",
	}).OK(t, http.StatusOK)

	after := client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK)
	if after.String("status") != "cancelled" {
		t.Errorf("status = %q, want cancelled", after.String("status"))
	}
	if reason := after.String("cancellation_reason"); !strings.Contains(reason, "Занят до конца месяца") {
		t.Errorf("the client should see why, got %q", reason)
	}
	if n := h.Count(`SELECT count(*) FROM notifications WHERE type = 'order_declined'`); n != 1 {
		t.Errorf("order_declined notifications = %d, want 1", n)
	}
}

// Молчание исполнителя заканчивается отменой, а не бесконечным ожиданием.
func TestAnUnansweredOrderCancelsItself(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, _ := orderAService(t, h)

	// Время двигать нельзя, поэтому двигается срок — он и есть предмет проверки.
	h.Exec(`UPDATE contracts SET developer_confirm_deadline = now() - interval '1 hour'
	        WHERE id = $1`, contractID)

	if _, err := h.App.Contracts.ExpireUnconfirmedOrders(context.Background()); err != nil {
		t.Fatalf("expire unanswered orders: %v", err)
	}

	after := client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK)
	if after.String("status") != "cancelled" {
		t.Errorf("status = %q, want cancelled", after.String("status"))
	}
	if n := h.Count(`SELECT count(*) FROM notifications WHERE type = 'order_expired'`); n != 2 {
		t.Errorf("order_expired notifications = %d, want one for each side", n)
	}

	// Повторный прогон ничего не ломает и не шлёт вторых писем.
	if _, err := h.App.Contracts.ExpireUnconfirmedOrders(context.Background()); err != nil {
		t.Fatalf("second run: %v", err)
	}
	if n := h.Count(`SELECT count(*) FROM notifications WHERE type = 'order_expired'`); n != 2 {
		t.Errorf("the task is not idempotent: %d notifications", n)
	}
}

// Сданная работа, на которую заказчик не ответил, принимается сама: иначе
// деньги исполнителя заморожены навсегда.
func TestDeliveredWorkIsAcceptedOnItsOwn(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, dev := hire(t, h)

	res := client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK)
	milestones := milestoneIDs(t, res)
	fundMilestone(h, milestones[0])
	dev.Client.POST("/milestones/"+milestones[0]+"/start", nil).OK(t, http.StatusOK)
	submitted := dev.Client.POST("/milestones/"+milestones[0]+"/submit", map[string]any{
		"note": "Бот собран, каталог и оплата работают. Видео с демонстрацией во вложении.",
	}).OK(t, http.StatusOK)
	if submitted.Data["auto_approve_at"] == nil {
		t.Fatalf("submitting must start the acceptance clock: %s", submitted.Raw)
	}

	// До срока ничего не происходит.
	if _, err := h.App.Contracts.AutoApproveDelivered(context.Background()); err != nil {
		t.Fatalf("auto-approve: %v", err)
	}
	var status string
	h.QueryRow([]any{&status}, `SELECT status FROM milestones WHERE id = $1`, milestones[0])
	if status != "submitted" {
		t.Fatalf("status = %q before the deadline, want submitted", status)
	}

	h.Exec(`UPDATE milestones SET auto_approve_at = now() - interval '1 minute' WHERE id = $1`,
		milestones[0])
	if _, err := h.App.Contracts.AutoApproveDelivered(context.Background()); err != nil {
		t.Fatalf("auto-approve after the deadline: %v", err)
	}
	h.QueryRow([]any{&status}, `SELECT status FROM milestones WHERE id = $1`, milestones[0])
	if status != "approved" {
		t.Errorf("status = %q, want approved", status)
	}
	if n := h.Count(`SELECT count(*) FROM notifications WHERE type = 'milestone_auto_approved'`); n != 2 {
		t.Errorf("auto-approval notifications = %d, want one for each side", n)
	}
	// В истории этапа видно, что принял не человек.
	if n := h.Count(`SELECT count(*) FROM milestone_events
	                 WHERE milestone_id = $1 AND to_status = 'approved' AND actor_id IS NULL`,
		milestones[0]); n != 1 {
		t.Errorf("the history must say nobody approved it: %d", n)
	}
}

// Запрошенные правки останавливают часы: иначе доработка приняла бы сама себя.
func TestRequestingRevisionStopsTheClock(t *testing.T) {
	h := testsupport.New(t)
	contractID, client, dev := hire(t, h)

	res := client.Client.GET("/contracts/"+contractID).OK(t, http.StatusOK)
	milestones := milestoneIDs(t, res)
	fundMilestone(h, milestones[0])
	dev.Client.POST("/milestones/"+milestones[0]+"/start", nil).OK(t, http.StatusOK)
	dev.Client.POST("/milestones/"+milestones[0]+"/submit", map[string]any{
		"note": "Бот собран, каталог и оплата работают. Видео с демонстрацией во вложении.",
	}).OK(t, http.StatusOK)
	client.Client.POST("/milestones/"+milestones[0]+"/request-revision", map[string]any{
		"note": "Корзина теряет позиции при смене количества — поправьте, пожалуйста.",
	}).OK(t, http.StatusOK)

	if n := h.Count(`SELECT count(*) FROM milestones WHERE id = $1 AND auto_approve_at IS NULL`,
		milestones[0]); n != 1 {
		t.Error("a revision request must clear the acceptance deadline")
	}
}
