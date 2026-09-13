package account_test

import (
	"net/http"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

func TestAccountSettings(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("acme")

	me := client.Client.GET("/account").OK(t, http.StatusOK)
	if me.String("username") != "acme" || !me.Bool("email_verified") {
		t.Fatalf("account = %s", me.Raw)
	}
	if me.Float("active_sessions") < 1 {
		t.Errorf("the current session must count, got %v", me.Data["active_sessions"])
	}

	client.Client.PATCH("/account", map[string]any{"timezone": "Mars/Olympus"}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	updated := client.Client.PATCH("/account", map[string]any{
		"full_name": "Ирина Ковалёва", "timezone": "Asia/Tashkent", "country_code": "uz", "city": "Ташкент", "locale": "ru",
	}).OK(t, http.StatusOK)
	if updated.String("full_name") != "Ирина Ковалёва" || updated.String("country_code") != "UZ" {
		t.Errorf("update not applied: %s", updated.Raw)
	}

	// Changing the address needs the password, and mail to send the link.
	client.Client.POST("/account/email", map[string]any{"new_email": "new@example.test", "password": "wrong-password-1"}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	client.Client.POST("/account/email", map[string]any{"new_email": "new@example.test", "password": "quiet-lantern-4417"}).
		Fails(t, http.StatusConflict, "email_not_configured")
	client.Client.POST("/account/email/confirm", map[string]any{"token": "nonsense"}).
		Fails(t, http.StatusUnprocessableEntity, "token_invalid")

	// Deactivation needs the password too, and ends the session.
	client.Client.POST("/account/deactivate", map[string]any{"password": "nope"}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	client.Client.POST("/account/deactivate", map[string]any{"password": "quiet-lantern-4417"}).OK(t, http.StatusOK)
	client.Client.GET("/account").Fails(t, http.StatusUnauthorized, "")
	var status string
	h.QueryRow([]any{&status}, `SELECT status FROM users WHERE username = 'acme'`)
	if status != "deactivated" {
		t.Errorf("status = %q, want deactivated", status)
	}
}

func TestDeactivationRefusedWithOpenContract(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("acme")
	projectID := h.PublishProject(client, "Telegram bot for an online clothing store",
		"telegram-bots", []string{"python"}, 50000, 80000)
	dev := h.PublishDeveloper("botmaker", "telegram-developer", "python")
	proposalID := dev.Client.POST("/proposals", map[string]any{
		"project_id": projectID, "amount_minor": 65000, "currency": "USD", "delivery_days": 12,
		"cover_letter": "I have built three Telegram commerce bots, the most recent one for a clothing retailer " +
			"with about 400 orders a month. Your catalogue and cart requirements map closely onto that.",
		"approach": "I would start with the data model for products, orders and customers, then the admin side " +
			"so your staff can load the catalogue while I build the customer flow, then payment last.",
		"relevant_experience": "Six years of Python, most of it on Telegram bots with PostgreSQL behind them.",
	}).OK(t, http.StatusCreated).String("id")
	client.Client.POST("/contracts", map[string]any{"proposal_id": proposalID}).OK(t, http.StatusCreated)

	res := dev.Client.POST("/account/deactivate", map[string]any{"password": "quiet-lantern-4417"}).
		Fails(t, http.StatusConflict, "contracts_in_progress")
	if res.Message == "" {
		t.Error("the refusal must explain itself")
	}
}
