package search_test

import (
	"net/http"
	"strings"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

func TestFreelancerCatalogueFiltersAndHides(t *testing.T) {
	h := testsupport.New(t)
	h.PublishDeveloper("gopher", "backend-developer", "go", "postgresql")
	h.PublishDeveloper("botmaker", "telegram-developer", "python", "telegram-api")
	// Registered but never finished onboarding: invisible.
	h.Client().RegisterDeveloper("halfway").OK(t, http.StatusCreated)

	all := h.Client().GET("/freelancers").OK(t, http.StatusOK)
	if len(all.List) != 2 {
		t.Fatalf("catalogue = %d, want the two published freelancers: %s", len(all.List), all.Raw)
	}
	if all.Meta["total"] != float64(2) {
		t.Errorf("meta.total = %v, want 2", all.Meta["total"])
	}
	first := all.List[0].(map[string]any)
	if first["sector_slug"] != "it" {
		t.Errorf("sector_slug = %v, want it", first["sector_slug"])
	}
	if skills, _ := first["skills"].([]any); len(skills) == 0 {
		t.Error("cards must carry skills")
	}
	if _, present := first["email"]; present {
		t.Error("a catalogue card must never carry an email")
	}

	bySkill := h.Client().GET("/freelancers?skills=telegram-api").OK(t, http.StatusOK)
	if len(bySkill.List) != 1 || bySkill.List[0].(map[string]any)["username"] != "botmaker" {
		t.Errorf("skill filter returned %s", bySkill.Raw)
	}
	both := h.Client().GET("/freelancers?skills=go,telegram-api").OK(t, http.StatusOK)
	if len(both.List) != 0 {
		t.Errorf("requiring both skills should match nobody, got %d", len(both.List))
	}
	bySector := h.Client().GET("/freelancers?sector=design").OK(t, http.StatusOK)
	if len(bySector.List) != 0 {
		t.Errorf("no designer exists, got %d", len(bySector.List))
	}
	bySpec := h.Client().GET("/freelancers?specialisation=backend-developer").OK(t, http.StatusOK)
	if len(bySpec.List) != 1 {
		t.Errorf("specialisation filter = %d, want 1", len(bySpec.List))
	}
	byText := h.Client().GET("/freelancers?q=gopher").OK(t, http.StatusOK)
	if len(byText.List) != 1 {
		t.Errorf("text filter = %d, want 1", len(byText.List))
	}

	// Switching visibility off removes a person from the catalogue at once.
	h.Exec(`UPDATE developer_profiles SET is_searchable = false WHERE user_id = (SELECT id FROM users WHERE username = 'gopher')`)
	after := h.Client().GET("/freelancers").OK(t, http.StatusOK)
	if len(after.List) != 1 {
		t.Errorf("after hiding gopher the catalogue = %d, want 1", len(after.List))
	}
}

func TestFavourites(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("gopher", "backend-developer", "go")
	client := h.NewClient("acme")

	client.Client.POST("/freelancers/gopher/save", map[string]any{"note": "Понравилось портфолио"}).OK(t, http.StatusOK)
	client.Client.POST("/freelancers/nobody/save", nil).Fails(t, http.StatusNotFound, "not_found")
	// A freelancer cannot keep a client list this way; the role decides.
	dev.Client.POST("/freelancers/gopher/save", nil).Fails(t, http.StatusForbidden, "forbidden")

	saved := client.Client.GET("/me/saved-freelancers").OK(t, http.StatusOK)
	if len(saved.List) != 1 {
		t.Fatalf("saved = %d, want 1: %s", len(saved.List), saved.Raw)
	}
	entry := saved.List[0].(map[string]any)
	if entry["note"] != "Понравилось портфолио" {
		t.Errorf("note = %v", entry["note"])
	}
	catalogue := client.Client.GET("/freelancers").OK(t, http.StatusOK)
	if catalogue.List[0].(map[string]any)["is_saved"] != true {
		t.Error("the catalogue must mark a saved freelancer for the client who saved them")
	}
	// Another client does not see the first client's favourites.
	other := h.NewClient("otherco")
	if other.Client.GET("/freelancers").OK(t, http.StatusOK).List[0].(map[string]any)["is_saved"] == true {
		t.Error("favourites leaked between clients")
	}

	client.Client.DELETE("/freelancers/gopher/save").OK(t, http.StatusOK)
	if n := len(client.Client.GET("/me/saved-freelancers").OK(t, http.StatusOK).List); n != 0 {
		t.Errorf("after unsave = %d, want 0", n)
	}

	// Projects, from the freelancer's side.
	projectID := h.PublishProject(client, "Telegram bot for an online clothing store",
		"telegram-bots", []string{"python"}, 50000, 80000)
	dev.Client.POST("/projects/"+projectID+"/save", nil).OK(t, http.StatusOK)
	feed := dev.Client.GET("/projects?tab=saved").OK(t, http.StatusOK)
	if len(feed.List) != 1 {
		t.Errorf("saved tab = %d, want 1", len(feed.List))
	}
	dev.Client.DELETE("/projects/"+projectID+"/save").OK(t, http.StatusOK)
	if n := len(dev.Client.GET("/projects?tab=saved").OK(t, http.StatusOK).List); n != 0 {
		t.Errorf("saved tab after unsave = %d, want 0", n)
	}
}

func TestGlobalSearch(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("acme")
	h.PublishProject(client, "Telegram bot for an online clothing store", "telegram-bots", []string{"python"}, 50000, 80000)
	h.PublishDeveloper("botmaker", "telegram-developer", "python", "telegram-api")

	h.Client().GET("/search?q=a").Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	res := h.Client().GET("/search?q=telegram").OK(t, http.StatusOK)
	totals, _ := res.Data["totals"].(map[string]any)
	if totals["projects"] != float64(1) {
		t.Errorf("projects total = %v, want 1: %s", totals["projects"], res.Raw)
	}
	if totals["freelancers"] != float64(1) {
		t.Errorf("freelancers total = %v, want 1", totals["freelancers"])
	}
	projects, _ := res.Data["projects"].([]any)
	if len(projects) != 1 {
		t.Fatalf("projects = %d", len(projects))
	}
	hit := projects[0].(map[string]any)
	if !strings.Contains(hit["budget_display"].(string), "$500") {
		t.Errorf("budget_display = %v", hit["budget_display"])
	}
}
