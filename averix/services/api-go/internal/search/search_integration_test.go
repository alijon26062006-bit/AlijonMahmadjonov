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

// Площадку можно смотреть без регистрации.
//
// Проверяется не «страница открылась», а то, что незнакомец видит то же, что
// участник: каталог исполнителей, профиль, портфолио, отзывы, услуги и все
// открытые заказы. Аккаунт спрашивают на действии, а не на входе.
func TestAVisitorWithoutAnAccountSeesTheMarketplace(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("otkrytyi", "telegram-developer", "python", "telegram-api")
	client := h.NewClient("zakazchik")
	projectID := h.PublishProject(client, "Бот для записи в барбершоп", "telegram-bots",
		[]string{"python"}, 40000, 90000)

	// Ни одного cookie: это посетитель с улицы.
	visitor := h.Client()

	catalogue := visitor.GET("/freelancers").OK(t, http.StatusOK)
	if len(catalogue.List) == 0 {
		t.Error("каталог исполнителей должен открываться без входа")
	}

	profile := visitor.GET("/developers/otkrytyi").OK(t, http.StatusOK)
	if profile.String("username") != "otkrytyi" {
		t.Errorf("профиль исполнителя не открылся: %s", profile.Raw)
	}
	visitor.GET("/developers/otkrytyi/portfolio").OK(t, http.StatusOK)
	visitor.GET("/developers/otkrytyi/reviews").OK(t, http.StatusOK)
	visitor.GET("/developers/otkrytyi/services").OK(t, http.StatusOK)
	visitor.GET("/taxonomy/specialisations").OK(t, http.StatusOK)
	visitor.GET("/taxonomy/categories").OK(t, http.StatusOK)

	// Все опубликованные заказы — публичный каталог и публичная страница.
	open := visitor.GET("/projects/browse").OK(t, http.StatusOK)
	if len(open.List) != 1 {
		t.Fatalf("открытых заказов видно %d, ждали один: %s", len(open.List), open.Raw)
	}
	first, _ := open.List[0].(map[string]any)
	if first["title"] != "Бот для записи в барбершоп" {
		t.Errorf("в каталоге не тот заказ: %v", first)
	}
	if first["budget_display"] == "" {
		t.Error("в карточке заказа должен быть бюджет")
	}

	slug, _ := first["slug"].(string)
	page := visitor.GET("/projects/"+slug).OK(t, http.StatusOK)
	if page.String("title") == "" {
		t.Errorf("страница заказа не открылась: %s", page.Raw)
	}

	// Фильтры каталога работают и без входа.
	byCategory := visitor.GET("/projects/browse?category=telegram-bots").OK(t, http.StatusOK)
	if len(byCategory.List) != 1 {
		t.Errorf("фильтр по направлению вернул %d", len(byCategory.List))
	}
	if empty := visitor.GET("/projects/browse?category=web-development").OK(t, http.StatusOK); len(empty.List) != 0 {
		t.Errorf("чужое направление вернуло %d заказов", len(empty.List))
	}
	if bySkill := visitor.GET("/projects/browse?skills=python").OK(t, http.StatusOK); len(bySkill.List) != 1 {
		t.Errorf("фильтр по навыку вернул %d", len(bySkill.List))
	}
	if byText := visitor.GET("/projects/browse?q=барбершоп").OK(t, http.StatusOK); len(byText.List) != 1 {
		t.Errorf("поиск по словам вернул %d", len(byText.List))
	}

	// А вот действие требует аккаунта — и отказ приходит от сервера, а не от
	// спрятанной кнопки.
	visitor.POST("/proposals", map[string]any{"project_id": projectID}).
		Fails(t, http.StatusUnauthorized, "unauthenticated")
	visitor.POST("/projects", map[string]any{"title": "Что-нибудь"}).
		Fails(t, http.StatusUnauthorized, "unauthenticated")
	// Переписка начинается с отклика или заказа услуги, и оба закрыты для
	// гостя; сам список бесед — тоже.
	visitor.GET("/conversations").Fails(t, http.StatusUnauthorized, "unauthenticated")
	_ = dev
}

// Черновики и снятые заказы в публичный каталог не попадают.
func TestTheOpenCatalogueShowsOnlyOpenWork(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("hiding")

	draft := client.Client.POST("/projects", map[string]any{
		"title":            "Черновик, который никто не должен видеть",
		"description":      "Пока думаю, что именно мне нужно, и не публикую это никому.",
		"category_slug":    "telegram-bots",
		"required_skills":  []string{"python"},
		"budget_type":      "range",
		"budget_min_minor": 10000, "budget_max_minor": 20000,
		"currency": "USD", "duration_days": 7,
	}).OK(t, http.StatusCreated)

	published := h.PublishProject(client, "Открытый заказ", "telegram-bots",
		[]string{"python"}, 30000, 50000)

	visitor := h.Client()
	open := visitor.GET("/projects/browse").OK(t, http.StatusOK)
	if len(open.List) != 1 {
		t.Fatalf("в каталоге %d заказов, ждали только опубликованный: %s", len(open.List), open.Raw)
	}
	if first, _ := open.List[0].(map[string]any); first["id"] != published {
		t.Errorf("в каталоге не тот заказ: %v", first)
	}
	_ = draft
}
