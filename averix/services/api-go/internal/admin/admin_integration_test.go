package admin_test

import (
	"net/http"
	"strings"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

func TestOverviewAndUserManagement(t *testing.T) {
	h := testsupport.New(t)
	root := h.NewAdmin("operator")
	dev := h.PublishDeveloper("gopher", "backend-developer", "go")
	client := h.NewClient("acme")

	// A client cannot see the dashboard at all: the role gate comes first.
	client.Client.GET("/admin/overview").Fails(t, http.StatusForbidden, "forbidden")

	overview := root.Client.GET("/admin/overview").OK(t, http.StatusOK)
	users, _ := overview.Data["users"].(map[string]any)
	if users["total"] != float64(3) {
		t.Errorf("users.total = %v, want 3: %s", users["total"], overview.Raw)
	}
	integrations, _ := overview.Data["integrations"].(map[string]any)
	if integrations["email"] != false {
		t.Errorf("email must read not configured in tests, got %v", integrations["email"])
	}

	list := root.Client.GET("/admin/users?role=developer").OK(t, http.StatusOK)
	if len(list.List) != 1 || list.List[0].(map[string]any)["username"] != "gopher" {
		t.Fatalf("developer list = %s", list.Raw)
	}
	search := root.Client.GET("/admin/users?q=acm").OK(t, http.StatusOK)
	if len(search.List) != 1 {
		t.Errorf("search by fragment = %d, want 1", len(search.List))
	}

	detail := root.Client.GET("/admin/users/"+dev.UserID).OK(t, http.StatusOK)
	if detail.Bool("freelancer_listed") != true {
		t.Errorf("a published freelancer is listed: %s", detail.Raw)
	}

	// Suspension: a reason is required, the person is told, their sessions end.
	root.Client.POST("/admin/users/"+dev.UserID+"/suspend", map[string]any{"reason": "x"}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	root.Client.POST("/admin/users/"+dev.UserID+"/suspend", map[string]any{
		"reason": "Предложение оплаты мимо платформы в переписке", "days": 7,
	}).OK(t, http.StatusOK)
	dev.Client.GET("/notifications").Fails(t, http.StatusUnauthorized, "")
	if got := h.Count(`SELECT count(*) FROM notifications WHERE type = 'account_suspended'`); got != 1 {
		t.Errorf("account_suspended notifications = %d, want 1", got)
	}
	if n := len(h.Client().GET("/freelancers").OK(t, http.StatusOK).List); n != 0 {
		t.Errorf("a suspended freelancer is still in the catalogue: %d", n)
	}
	if got := h.Count(`SELECT count(*) FROM audit_logs WHERE action = 'user.suspended'`); got != 1 {
		t.Errorf("audit rows for the suspension = %d, want 1", got)
	}
	root.Client.POST("/admin/users/"+dev.UserID+"/unsuspend", nil).OK(t, http.StatusOK)

	// Self-protection: nobody suspends themselves or drops their own admin role.
	root.Client.POST("/admin/users/"+root.UserID+"/suspend", map[string]any{"reason": "тестовая причина"}).
		Fails(t, http.StatusForbidden, "forbidden")
	root.Client.DELETE("/admin/users/"+root.UserID+"/roles/admin").Fails(t, http.StatusForbidden, "forbidden")

	// Roles: grant moderator to the client, then take it away; the last role stays.
	root.Client.POST("/admin/users/"+client.UserID+"/roles", map[string]any{"role": "moderator"}).OK(t, http.StatusOK)
	root.Client.DELETE("/admin/users/"+client.UserID+"/roles/moderator").OK(t, http.StatusOK)
	root.Client.DELETE("/admin/users/"+client.UserID+"/roles/client").Fails(t, http.StatusConflict, "last_role")

	root.Client.PUT("/admin/users/"+dev.UserID+"/identity", map[string]any{"verified": true}).OK(t, http.StatusOK)
	if !root.Client.GET("/admin/users/"+dev.UserID).OK(t, http.StatusOK).Bool("identity_verified") {
		t.Error("identity verification did not stick")
	}

	audit := root.Client.GET("/admin/audit?action=user.").OK(t, http.StatusOK)
	if len(audit.List) < 4 {
		t.Errorf("audit rows for user actions = %d, want at least 4", len(audit.List))
	}
}

func TestSettingsAndFlagsAndWeights(t *testing.T) {
	h := testsupport.New(t)
	root := h.NewAdmin("operator")

	rows := root.Client.GET("/admin/settings").OK(t, http.StatusOK)
	if len(rows.List) < 15 {
		t.Fatalf("settings catalogue = %d rows", len(rows.List))
	}
	root.Client.PUT("/admin/settings/platform.fee_basis_points", map[string]any{"value": 5000}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	root.Client.PUT("/admin/settings/platform.fee_basis_points", map[string]any{"value": 1500}).OK(t, http.StatusOK)
	root.Client.PUT("/admin/settings/made.up", map[string]any{"value": 1}).Fails(t, http.StatusNotFound, "not_found")
	root.Client.PUT("/admin/settings/payments.provider", map[string]any{"value": "stripe"}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	var fee int
	h.QueryRow([]any{&fee}, `SELECT (value)::int FROM platform_settings WHERE key = 'platform.fee_basis_points'`)
	if fee != 1500 {
		t.Errorf("stored fee = %d, want 1500", fee)
	}

	// The test database starts with no flags (the harness truncates them);
	// setting one creates it, and the list shows it.
	root.Client.PUT("/admin/flags/github_analysis", map[string]any{"enabled": true, "rollout_percent": 50}).OK(t, http.StatusOK)
	root.Client.PUT("/admin/flags/github_analysis", map[string]any{"enabled": true, "rollout_percent": 150}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	flags := root.Client.GET("/admin/flags").OK(t, http.StatusOK)
	if len(flags.List) != 1 || flags.List[0].(map[string]any)["rollout_percent"] != float64(50) {
		t.Fatalf("flags = %s", flags.Raw)
	}

	weights := root.Client.GET("/admin/matching/weights").OK(t, http.StatusOK)
	if weights.Float("technical") <= 0 {
		t.Errorf("weights = %s", weights.Raw)
	}
	bad := map[string]any{"technical": 0.9, "track_record": 0.9, "github": 0, "availability": 0,
		"platform_history": 0, "budget_fit": 0, "feed_threshold": 40, "note": "проверка суммы"}
	res := root.Client.PUT("/admin/matching/weights", bad).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if !strings.Contains(res.Fields["weights"], "1") {
		t.Errorf("the sum rule must be named: %v", res.Fields)
	}
	good := map[string]any{"technical": 0.4, "track_record": 0.2, "github": 0.1, "availability": 0.1,
		"platform_history": 0.1, "budget_fit": 0.1, "feed_threshold": 40, "note": "больше веса технике"}
	saved := root.Client.PUT("/admin/matching/weights", good).OK(t, http.StatusOK)
	if saved.Float("version") < 1 {
		t.Errorf("a saved weight set must carry its version, got %v", saved.Data["version"])
	}
	// The new set is the active one from now on, and the history keeps the note.
	active := root.Client.GET("/admin/matching/weights").OK(t, http.StatusOK)
	if active.Float("technical") != 0.4 {
		t.Errorf("active technical weight = %v, want 0.4", active.Data["technical"])
	}
	if history, _ := active.Meta["history"].([]any); len(history) == 0 {
		t.Error("the weight history must list the change")
	}
}

func TestModeratorSeesQueueNotSettings(t *testing.T) {
	h := testsupport.New(t)
	root := h.NewAdmin("operator")
	mod := h.NewClient("modclient")
	root.Client.POST("/admin/users/"+mod.UserID+"/roles", map[string]any{"role": "moderator"}).OK(t, http.StatusOK)
	mod.Client.POST("/auth/role/switch", map[string]any{"role": "moderator"}).OK(t, http.StatusOK)

	mod.Client.GET("/admin/overview").OK(t, http.StatusOK)
	mod.Client.GET("/admin/moderation/queue").OK(t, http.StatusOK)
	mod.Client.GET("/admin/settings").Fails(t, http.StatusForbidden, "forbidden")
	mod.Client.GET("/admin/users").Fails(t, http.StatusForbidden, "forbidden")
}
