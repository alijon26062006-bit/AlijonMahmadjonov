package developers_test

import (
	"context"
	"net/http"
	"strconv"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

// Уровень — это утверждение о человеке, и считается он из сделок, а не из
// доброго отношения администратора. Здесь проверяется и то, как он растёт, и
// то, что его можно потерять.
func TestSellerLevelIsEarnedAndCanBeLost(t *testing.T) {
	h := testsupport.New(t)
	h.PublishDeveloper("levelup", "backend-developer", "python", "postgresql")
	client := h.NewClient("acmeco")
	// Контракт ссылается на проект, поэтому он нужен хотя бы один — дальше
	// сделки вставляются прямо в таблицу, из которой считается уровень.
	projectID := h.PublishProject(client, "Telegram bot for an online clothing store",
		"telegram-bots", []string{"python", "postgresql"}, 50000, 90000)

	var devID, clientID string
	h.QueryRow([]any{&devID}, `SELECT id FROM users WHERE username = 'levelup'`)
	h.QueryRow([]any{&clientID}, `SELECT id FROM users WHERE username = 'acmeco'`)

	// Пока сделок нет — новичок, и значка нет: отсутствие истории не награда.
	profile := h.Client().GET("/developers/levelup").OK(t, http.StatusOK)
	if profile.String("seller_level") != "new" {
		t.Errorf("seller_level = %q, want new", profile.String("seller_level"))
	}
	if hasLevelBadge(profile.Data) {
		t.Error("«Новичок» не должен висеть значком на профиле")
	}

	// Десять завершённых сделок — «Продвинутый».
	seedFinishedContracts(h, projectID, clientID, devID, 10, "completed")
	if _, err := h.App.Developers.RefreshSellerLevels(context.Background()); err != nil {
		t.Fatalf("refresh levels: %v", err)
	}
	profile = h.Client().GET("/developers/levelup").OK(t, http.StatusOK)
	if profile.String("seller_level") != "advanced" {
		t.Fatalf("seller_level = %q after ten deals, want advanced", profile.String("seller_level"))
	}
	if !hasLevelBadge(profile.Data) {
		t.Error("заработанный уровень должен быть виден заказчику значком")
	}
	if n := h.Count(`SELECT count(*) FROM notifications WHERE type = 'seller_level_changed'`); n != 1 {
		t.Errorf("level notifications = %d, want 1", n)
	}

	// Повторный прогон ничего не меняет и вторых уведомлений не шлёт.
	if _, err := h.App.Developers.RefreshSellerLevels(context.Background()); err != nil {
		t.Fatalf("second refresh: %v", err)
	}
	if n := h.Count(`SELECT count(*) FROM notifications WHERE type = 'seller_level_changed'`); n != 1 {
		t.Errorf("пересчёт без изменений разослал уведомления: %d", n)
	}

	// Сорванные заказы возвращают на «Новичка»: уровень держится на свежей
	// истории, а не на однажды выданном звании.
	seedFinishedContracts(h, projectID, clientID, devID, 4, "cancelled")
	if _, err := h.App.Developers.RefreshSellerLevels(context.Background()); err != nil {
		t.Fatalf("refresh after failures: %v", err)
	}
	profile = h.Client().GET("/developers/levelup").OK(t, http.StatusOK)
	if profile.String("seller_level") != "new" {
		t.Errorf("seller_level = %q after four failures, want new", profile.String("seller_level"))
	}
	if n := h.Count(`SELECT count(*) FROM notifications WHERE type = 'seller_level_changed'`); n != 2 {
		t.Errorf("падение уровня тоже должно быть сообщено: %d", n)
	}
}

// Вовремя отклонённый заказ провалом не считается: отказаться честно лучше,
// чем взять и пропасть.
func TestDecliningInTimeIsNotAFailure(t *testing.T) {
	h := testsupport.New(t)
	h.PublishDeveloper("levelup", "backend-developer", "python")
	client := h.NewClient("acmeco")
	projectID := h.PublishProject(client, "Telegram bot for an online clothing store",
		"telegram-bots", []string{"python"}, 50000, 90000)

	var devID, clientID string
	h.QueryRow([]any{&devID}, `SELECT id FROM users WHERE username = 'levelup'`)
	h.QueryRow([]any{&clientID}, `SELECT id FROM users WHERE username = 'acmeco'`)

	seedFinishedContracts(h, projectID, clientID, devID, 10, "completed")
	// Четыре заказа, от которых исполнитель отказался до срока ответа.
	for i := 0; i < 4; i++ {
		h.Exec(`
			INSERT INTO contracts (reference, project_id, client_id, developer_id, title,
			                       amount_minor, currency, payout_minor, status,
			                       developer_confirm_deadline, cancelled_at)
			VALUES ('AVX-DECL-' || $4, $3, $1, $2, 'Отклонённый заказ',
			        10000, 'USD', 10000, 'cancelled', now() + interval '2 hours', now())`,
			clientID, devID, projectID, strconv.Itoa(i))
	}

	if _, err := h.App.Developers.RefreshSellerLevels(context.Background()); err != nil {
		t.Fatalf("refresh: %v", err)
	}
	profile := h.Client().GET("/developers/levelup").OK(t, http.StatusOK)
	if profile.String("seller_level") != "advanced" {
		t.Errorf("seller_level = %q, want advanced — отказ в срок не провал", profile.String("seller_level"))
	}
}

// seedFinishedContracts writes finished contracts straight to the table: the
// level is computed from them, and driving ten deals through the interface
// would test the interface rather than the rule.
func seedFinishedContracts(h *testsupport.Harness, projectID, clientID, devID string,
	n int, status string) {

	for i := 0; i < n; i++ {
		h.Exec(`
			INSERT INTO contracts (reference, project_id, client_id, developer_id, title,
			                       amount_minor, currency, payout_minor, status,
			                       progress_percent, completed_at, cancelled_at)
			VALUES ('AVX-SEED-' || $4 || '-' || $5, $3, $1, $2, 'Сделка ' || $5,
			        10000, 'USD', 10000, $4,
			        CASE WHEN $4 = 'cancelled' THEN 100 ELSE 0 END,
			        CASE WHEN $4 = 'completed' THEN now() ELSE NULL END,
			        CASE WHEN $4 = 'cancelled' THEN now() ELSE NULL END)`,
			clientID, devID, projectID, status, strconv.Itoa(i))
	}
}

func hasLevelBadge(data map[string]any) bool {
	badges, _ := data["badges"].([]any)
	for _, entry := range badges {
		badge, _ := entry.(map[string]any)
		kind, _ := badge["kind"].(string)
		if kind == "seller_level_advanced" || kind == "seller_level_professional" {
			return true
		}
	}
	return false
}
