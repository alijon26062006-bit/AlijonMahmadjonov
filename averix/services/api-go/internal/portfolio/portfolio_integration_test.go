package portfolio_test

import (
	"bytes"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"net/textproto"
	"strings"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

// ── The happy path ──────────────────────────────────────────────────────────

func TestPortfolioLifecycle(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("alidev", "backend-developer", "go", "postgresql", "docker")
	c := dev.Client

	created := c.POST("/portfolio", map[string]any{
		"title":             "Warehouse stock API",
		"short_description": "A stock and ordering API for a wholesaler",
		"description": "A Go service that replaced a spreadsheet-driven stock process. " +
			"It exposes an ordering API, reconciles deliveries against invoices and " +
			"pushes low-stock alerts to the warehouse team.",
		"category_slug":  "api-development",
		"developer_role": "Backend developer",
		"technologies":   []string{"go", "postgresql", "docker"},
		"completed_on":   "2025-03-14",
		"duration_days":  45,
	}).OK(t, http.StatusCreated)

	projectID := created.String("id")
	if projectID == "" {
		t.Fatal("create did not return an id")
	}
	if created.String("slug") != "warehouse-stock-api" {
		t.Errorf("slug = %q, want warehouse-stock-api", created.String("slug"))
	}
	if created.String("kind") != "portfolio" {
		t.Errorf("kind = %q — a self-declared item must never be labelled verified",
			created.String("kind"))
	}
	if created.Bool("is_published") {
		t.Error("a new item must start as a draft")
	}

	// A draft is invisible to a visitor, including its very existence.
	anon := h.Client()
	list := anon.GET("/developers/alidev/portfolio").OK(t, http.StatusOK)
	if len(list.List) != 0 {
		t.Errorf("a visitor sees %d unpublished items, want 0", len(list.List))
	}
	anon.GET("/developers/alidev/portfolio/warehouse-stock-api").
		Fails(t, http.StatusNotFound, "not_found")

	// Publishing needs something to show.
	res := c.POST("/portfolio/"+projectID+"/publish", map[string]any{"published": true}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if res.Fields["images"] == "" {
		t.Errorf("publishing without anything to show should say so, got fields %v", res.Fields)
	}

	uploadScreenshot(t, c, projectID, "screen.png", pngFixture(1600, 900)).
		OK(t, http.StatusCreated)

	c.POST("/portfolio/"+projectID+"/publish", map[string]any{"published": true}).
		OK(t, http.StatusOK)

	// Now the visitor sees a card with a cover.
	list = anon.GET("/developers/alidev/portfolio").OK(t, http.StatusOK)
	if len(list.List) != 1 {
		t.Fatalf("a visitor sees %d published items, want 1", len(list.List))
	}
	card, _ := list.List[0].(map[string]any)
	if card["cover"] == nil {
		t.Error("a published card with a screenshot must carry a cover")
	}
	if skills, ok := card["skills"].([]any); !ok || len(skills) != 3 {
		t.Errorf("card skills = %v, want the three technologies", card["skills"])
	}

	detail := anon.GET("/developers/alidev/portfolio/warehouse-stock-api").OK(t, http.StatusOK)
	if detail.String("developer_role") != "Backend developer" {
		t.Errorf("developer_role = %q", detail.String("developer_role"))
	}
	if detail.Bool("is_owner") {
		t.Error("a visitor is not the owner")
	}
}

func TestUnpublishHidesAnItemAgain(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("hidedev", "backend-developer")
	projectID := publishablePortfolioItem(t, dev.Client, "Invoice reconciler")

	anon := h.Client()
	anon.GET("/developers/hidedev/portfolio/invoice-reconciler").OK(t, http.StatusOK)

	dev.Client.POST("/portfolio/"+projectID+"/publish", map[string]any{"published": false}).
		OK(t, http.StatusOK)
	anon.GET("/developers/hidedev/portfolio/invoice-reconciler").
		Fails(t, http.StatusNotFound, "not_found")
}

// ── Authorisation ───────────────────────────────────────────────────────────

// Changing the id in the URL must not reach someone else's work.
func TestAnotherDeveloperCannotTouchYourPortfolio(t *testing.T) {
	h := testsupport.New(t)
	owner := h.PublishDeveloper("ownerdev", "backend-developer")
	projectID := publishablePortfolioItem(t, owner.Client, "Ledger service")

	intruder := h.PublishDeveloper("intruderdev", "backend-developer")
	i := intruder.Client

	// Not 403: a refusal that confirms the id exists is itself a disclosure.
	i.GET("/portfolio/"+projectID).Fails(t, http.StatusNotFound, "not_found")
	i.PATCH("/portfolio/"+projectID, map[string]any{"title": "Mine now"}).
		Fails(t, http.StatusNotFound, "not_found")
	i.DELETE("/portfolio/"+projectID).Fails(t, http.StatusNotFound, "not_found")
	i.POST("/portfolio/"+projectID+"/publish", map[string]any{"published": false}).
		Fails(t, http.StatusNotFound, "not_found")
	i.POST("/portfolio/"+projectID+"/links", map[string]any{
		"label": "Case study", "url": "https://example.org/case",
	}).Fails(t, http.StatusNotFound, "not_found")
	i.POST("/portfolio/"+projectID+"/check-url", nil).
		Fails(t, http.StatusNotFound, "not_found")

	// And the owner's item is untouched.
	owner.Client.GET("/portfolio/"+projectID).OK(t, http.StatusOK)
}

func TestAClientAccountCannotKeepAPortfolio(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("acmeco")
	client.Client.POST("/portfolio", map[string]any{"title": "Something"}).
		Fails(t, http.StatusForbidden, "forbidden")
}

func TestAnotherDeveloperCannotDeleteYourScreenshot(t *testing.T) {
	h := testsupport.New(t)
	owner := h.PublishDeveloper("shotowner", "backend-developer")
	projectID := createPortfolioItem(t, owner.Client, "Fleet tracker")
	image := uploadScreenshot(t, owner.Client, projectID, "a.png", pngFixture(900, 600)).
		OK(t, http.StatusCreated)
	imageID := image.String("id")

	intruder := h.PublishDeveloper("shotthief", "backend-developer")
	intruder.Client.DELETE("/portfolio/images/"+imageID).
		Fails(t, http.StatusNotFound, "not_found")

	// The file is still there for its owner.
	detail := owner.Client.GET("/portfolio/"+projectID).OK(t, http.StatusOK)
	if images, ok := detail.Data["images"].([]any); !ok || len(images) != 1 {
		t.Errorf("images = %v, want the one that was uploaded", detail.Data["images"])
	}
}

// ── URL security ────────────────────────────────────────────────────────────

func TestDangerousProjectURLsAreRefused(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("urldev", "backend-developer")
	projectID := createPortfolioItem(t, dev.Client, "URL checks")

	for _, raw := range []string{
		"javascript:alert(document.cookie)",
		"data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
		"file:///etc/passwd",
		"vbscript:msgbox(1)",
		"http://169.254.169.254/latest/meta-data/",
		"http://metadata.google.internal/computeMetadata/v1/",
		"https://10.1.2.3/admin",
		"https://192.168.0.10/",
		"https://[fd00::1]/",
		"ftp://files.example.org/pub",
		"ws://example.org/socket",
		"https://internal.corp/dashboard",
	} {
		res := dev.Client.PATCH("/portfolio/"+projectID, map[string]any{"project_url": raw})
		if res.Status != http.StatusUnprocessableEntity {
			t.Errorf("project_url %q was accepted with status %d — it must be refused",
				raw, res.Status)
			continue
		}
		if res.Fields["project_url"] == "" {
			t.Errorf("project_url %q was refused without telling the developer why", raw)
		}
	}

	// The same guard applies to the extra links, which a visitor also clicks.
	dev.Client.POST("/portfolio/"+projectID+"/links", map[string]any{
		"label": "Case study", "url": "javascript:alert(1)",
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
}

func TestProjectURLIsNormalisedAndStored(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("normdev", "backend-developer")
	projectID := createPortfolioItem(t, dev.Client, "Normalising")

	res := dev.Client.PATCH("/portfolio/"+projectID, map[string]any{
		"project_url": "  HTTPS://Stock.Example.Org:443/App?utm_source=x  ",
	}).OK(t, http.StatusOK)

	if got := res.String("project_host"); got != "stock.example.org" {
		t.Errorf("project_host = %q, want stock.example.org", got)
	}
	if got := res.String("project_url"); !strings.HasPrefix(got, "https://stock.example.org/") {
		t.Errorf("project_url = %q, want a normalised https URL", got)
	}
}

// ── Money ───────────────────────────────────────────────────────────────────

// The figure itself must never leave the server unless the developer made it
// public, and a private contract still shows that the work happened.
func TestProjectValueVisibilityLadder(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("moneydev", "backend-developer")
	projectID := publishablePortfolioItem(t, dev.Client, "Billing rework")
	anon := h.Client()

	cases := []struct {
		visibility  string
		wantDisplay string
		wantFigure  bool
	}{
		{"public", "$1 200", false},
		{"range", "$1 000 – 1 500", false},
		{"private", "Закрытая сделка", false},
		{"hidden", "", false},
	}
	for _, tc := range cases {
		dev.Client.PATCH("/portfolio/"+projectID, map[string]any{
			"value_minor": 120000, "currency": "USD", "value_visibility": tc.visibility,
		}).OK(t, http.StatusOK)

		public := anon.GET("/developers/moneydev/portfolio/billing-rework").OK(t, http.StatusOK)
		if got := public.String("value_display"); got != tc.wantDisplay {
			t.Errorf("%s: value_display = %q, want %q", tc.visibility, got, tc.wantDisplay)
		}
		if _, present := public.Data["value_minor"]; present != tc.wantFigure {
			t.Errorf("%s: value_minor present = %v, want %v", tc.visibility, present, tc.wantFigure)
		}

		// The owner always sees their own figure, because they have to edit it.
		own := dev.Client.GET("/portfolio/"+projectID).OK(t, http.StatusOK)
		if own.Float("value_minor") != 120000 {
			t.Errorf("%s: the owner cannot see their own value (%v)",
				tc.visibility, own.Data["value_minor"])
		}
	}
}

// ── Screenshots ─────────────────────────────────────────────────────────────

// The uploaded bytes are never what gets served: everything is re-encoded into
// the sizes the product renders.
func TestScreenshotsAreReEncodedIntoServableSizes(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("shotdev", "backend-developer")
	projectID := createPortfolioItem(t, dev.Client, "Gallery")

	res := uploadScreenshot(t, dev.Client, projectID, "raw-screenshot.png", pngFixture(1800, 1000)).
		OK(t, http.StatusCreated)

	variants, ok := res.Data["variants"].([]any)
	if !ok || len(variants) == 0 {
		t.Fatalf("variants = %v, want the rendered sizes", res.Data["variants"])
	}
	formats := map[string]bool{}
	widths := map[int]bool{}
	for _, raw := range variants {
		variant, _ := raw.(map[string]any)
		formats[fmt.Sprint(variant["format"])] = true
		widths[int(variant["width"].(float64))] = true
		if url, _ := variant["url"].(string); url == "" {
			t.Error("a variant was returned without a URL")
		}
	}
	if !formats["webp"] || !formats["jpeg"] {
		t.Errorf("formats = %v, want both webp and jpeg", formats)
	}
	if !widths[480] || !widths[960] {
		t.Errorf("widths = %v, want the phone and card sizes", widths)
	}
	if res.String("placeholder") == "" {
		t.Error("no placeholder colour was stored, so a loading image will flash white")
	}

	// The stored file is our own output, not the PNG that was uploaded.
	var detected string
	h.QueryRow([]any{&detected}, `
		SELECT f.detected_mime FROM files f
		JOIN portfolio_images pi ON pi.file_id = f.id
		WHERE pi.id = $1`, res.String("id"))
	if detected != "image/webp" {
		t.Errorf("stored mime = %q, want image/webp — the upload should be re-encoded", detected)
	}
	if h.Count(`SELECT count(*) FROM files WHERE declared_mime = 'image/png'`) != 1 {
		t.Error("the browser's declared type should still be recorded for the audit trail")
	}
}

// A file is typed from its bytes, never from its name or the browser's claim.
func TestDisguisedUploadIsRefused(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("fakedev", "backend-developer")
	projectID := createPortfolioItem(t, dev.Client, "Uploads")

	html := []byte("<!DOCTYPE html><html><script>alert(document.cookie)</script></html>")
	uploadScreenshot(t, dev.Client, projectID, "screenshot.png", html).
		Fails(t, http.StatusUnsupportedMediaType, "unsupported_media_type")

	if h.Count(`SELECT count(*) FROM files`) != 0 {
		t.Error("a refused upload must not leave a file row behind")
	}
}

func TestGalleryOrderAndCoverAreTheDevelopersChoice(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("orderdev", "backend-developer")
	c := dev.Client
	projectID := createPortfolioItem(t, c, "Ordering")

	first := uploadScreenshot(t, c, projectID, "one.png", pngFixture(800, 500)).
		OK(t, http.StatusCreated).String("id")
	second := uploadScreenshot(t, c, projectID, "two.png", pngFixture(800, 500)).
		OK(t, http.StatusCreated).String("id")
	third := uploadScreenshot(t, c, projectID, "three.png", pngFixture(800, 500)).
		OK(t, http.StatusCreated).String("id")

	// The first image is the cover until one is chosen.
	detail := c.GET("/portfolio/"+projectID).OK(t, http.StatusOK)
	cover, _ := detail.Data["cover"].(map[string]any)
	if cover == nil || cover["id"] != first {
		t.Errorf("cover = %v, want the first image", detail.Data["cover"])
	}

	c.PUT("/portfolio/"+projectID+"/images/order", map[string]any{
		"order": []string{third, first, second},
	}).OK(t, http.StatusOK)

	detail = c.GET("/portfolio/"+projectID).OK(t, http.StatusOK)
	images, _ := detail.Data["images"].([]any)
	if len(images) != 3 {
		t.Fatalf("images = %v", detail.Data["images"])
	}
	want := []string{third, first, second}
	for i, raw := range images {
		got, _ := raw.(map[string]any)
		if got["id"] != want[i] {
			t.Errorf("image %d = %v, want %s", i, got["id"], want[i])
		}
	}

	c.PUT("/portfolio/"+projectID+"/cover", map[string]any{"image_id": second}).
		OK(t, http.StatusOK)
	detail = c.GET("/portfolio/"+projectID).OK(t, http.StatusOK)
	cover, _ = detail.Data["cover"].(map[string]any)
	if cover == nil || cover["id"] != second {
		t.Errorf("cover = %v, want the chosen image", detail.Data["cover"])
	}

	// An image that belongs to another project cannot become this one's cover.
	other := createPortfolioItem(t, c, "Another project")
	foreign := uploadScreenshot(t, c, other, "x.png", pngFixture(800, 500)).
		OK(t, http.StatusCreated).String("id")
	c.PUT("/portfolio/"+projectID+"/cover", map[string]any{"image_id": foreign}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
}

func TestRemovingAScreenshotRemovesItsObjects(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("cleandev", "backend-developer")
	c := dev.Client
	projectID := createPortfolioItem(t, c, "Cleanup")

	image := uploadScreenshot(t, c, projectID, "one.png", pngFixture(1200, 800)).
		OK(t, http.StatusCreated)
	var keys []string
	h.QueryRow([]any{&keys}, `
		SELECT array(SELECT jsonb_path_query(derivatives, '$.*.*')::text
		             FROM portfolio_images WHERE id = $1)`, image.String("id"))
	if len(keys) < 2 {
		t.Fatalf("expected several stored objects, got %v", keys)
	}

	c.DELETE("/portfolio/images/"+image.String("id")).OK(t, http.StatusNoContent)

	for _, quoted := range keys {
		key := strings.Trim(quoted, `"`)
		if h.ObjectExists(key, "public") {
			t.Errorf("object %s survived the delete", key)
		}
	}
	if h.Count(`SELECT count(*) FROM files WHERE deleted_at IS NULL`) != 0 {
		t.Error("the file row should be marked deleted")
	}
}

// ── The in-app preview browser ──────────────────────────────────────────────

// A site that refuses to be framed is honoured, never worked around.
func TestPreviewHonoursAFramingRefusal(t *testing.T) {
	h := testsupport.New(t)
	site := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Frame-Options", "DENY")
		fmt.Fprint(w, "<html><head><title>Locked down</title></head><body>hi</body></html>")
	}))
	defer site.Close()

	dev := h.PublishDeveloper("framedev", "backend-developer")
	projectID := publishablePortfolioItem(t, dev.Client, "Framed project")
	dev.Client.PATCH("/portfolio/"+projectID, map[string]any{"project_url": site.URL}).
		OK(t, http.StatusOK)
	uploadScreenshot(t, dev.Client, projectID, "shot.png", pngFixture(1200, 800)).
		OK(t, http.StatusCreated)

	anon := h.Client()
	res := anon.GET("/developers/framedev/portfolio/framed-project/preview").OK(t, http.StatusOK)

	frame, _ := res.Data["frame"].(map[string]any)
	if frame["verdict"] != "blocked" {
		t.Fatalf("verdict = %v, want blocked", frame["verdict"])
	}
	if frame["sandbox"] != nil {
		t.Error("a blocked frame must carry no iframe attributes at all")
	}
	if res.Data["fallback"] == nil {
		t.Error("a blocked preview should fall back to the developer's screenshot")
	}

	// The developer sees why, in their own editor; the visitor does not.
	if frame["reason"] != nil {
		t.Errorf("a visitor was told %v — that explanation is for the developer",
			frame["reason"])
	}
	own := dev.Client.POST("/portfolio/"+projectID+"/check-url", nil).OK(t, http.StatusOK)
	if own.String("verdict") != "blocked" || own.String("reason") == "" {
		t.Errorf("the owner's check returned %v", own.Data)
	}
}

func TestPreviewFrameWithholdsAccessToAverix(t *testing.T) {
	h := testsupport.New(t)
	site := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, "<html><head><title>Open site</title></head><body>hi</body></html>")
	}))
	defer site.Close()

	dev := h.PublishDeveloper("opendev", "backend-developer")
	projectID := publishablePortfolioItem(t, dev.Client, "Open project")
	dev.Client.PATCH("/portfolio/"+projectID, map[string]any{"project_url": site.URL}).
		OK(t, http.StatusOK)

	res := h.Client().GET("/developers/opendev/portfolio/open-project/preview").
		OK(t, http.StatusOK)
	frame, _ := res.Data["frame"].(map[string]any)
	if frame["verdict"] != "allowed" {
		t.Fatalf("verdict = %v, want allowed (frame: %v)", frame["verdict"], frame)
	}

	sandbox, _ := frame["sandbox"].(string)
	if !strings.Contains(sandbox, "allow-scripts") {
		t.Errorf("sandbox = %q, a preview without scripts is not a preview", sandbox)
	}
	// The one that matters: with allow-same-origin a same-origin embedded page
	// could read the parent document, and with it the session.
	for _, forbidden := range []string{
		"allow-same-origin", "allow-top-navigation", "allow-forms",
		"allow-modals", "allow-downloads", "allow-storage-access",
	} {
		if strings.Contains(sandbox, forbidden) {
			t.Errorf("sandbox = %q must not grant %s", sandbox, forbidden)
		}
	}
	if policy, _ := frame["permissions_policy"].(string); !strings.Contains(policy, "camera=()") {
		t.Errorf("permissions_policy = %q, want the device permissions withheld", policy)
	}
	if referrer, _ := frame["referrer_policy"].(string); referrer != "strict-origin" {
		t.Errorf("referrer_policy = %q, want strict-origin", referrer)
	}
	devices, _ := frame["devices"].([]any)
	if len(devices) != 3 {
		t.Errorf("devices = %v, want mobile, tablet and desktop", devices)
	}
}

// The verdict is cached, so opening a popular profile does not turn our server
// into a fetcher.
func TestPreviewVerdictIsCached(t *testing.T) {
	h := testsupport.New(t)
	var hits int
	site := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits++
		fmt.Fprint(w, "<html><head><title>Cached</title></head></html>")
	}))
	defer site.Close()

	dev := h.PublishDeveloper("cachedev", "backend-developer")
	projectID := publishablePortfolioItem(t, dev.Client, "Cached project")
	dev.Client.PATCH("/portfolio/"+projectID, map[string]any{"project_url": site.URL}).
		OK(t, http.StatusOK)

	anon := h.Client()
	for i := 0; i < 3; i++ {
		anon.GET("/developers/cachedev/portfolio/cached-project/preview").OK(t, http.StatusOK)
	}
	if hits != 1 {
		t.Errorf("the site was probed %d times for three visits, want 1", hits)
	}

	// Changing the URL invalidates the verdict: the old answer described a
	// different site.
	dev.Client.PATCH("/portfolio/"+projectID, map[string]any{
		"project_url": site.URL + "/other",
	}).OK(t, http.StatusOK)
	anon.GET("/developers/cachedev/portfolio/cached-project/preview").OK(t, http.StatusOK)
	if hits != 2 {
		t.Errorf("a changed URL was not re-probed (hits = %d)", hits)
	}
}

func TestPreviewNeedsALiveLink(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("nolinkdev", "backend-developer")
	publishablePortfolioItem(t, dev.Client, "No link")

	h.Client().GET("/developers/nolinkdev/portfolio/no-link/preview").
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
}

// ── Links ───────────────────────────────────────────────────────────────────

func TestLinksAreValidatedAndCapped(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("linkdev", "backend-developer")
	c := dev.Client
	projectID := createPortfolioItem(t, c, "Links")

	res := c.POST("/portfolio/"+projectID+"/links", map[string]any{
		"label": "Case study", "url": "example.org/write-up", "kind": "case_study",
	}).OK(t, http.StatusCreated)
	if res.String("host") != "example.org" {
		t.Errorf("host = %q, want example.org", res.String("host"))
	}

	c.POST("/portfolio/"+projectID+"/links", map[string]any{
		"label": "Bad kind", "url": "https://example.org", "kind": "totally-made-up",
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	for i := 0; i < 5; i++ {
		c.POST("/portfolio/"+projectID+"/links", map[string]any{
			"label": fmt.Sprintf("Link %d", i), "url": fmt.Sprintf("https://example.org/%d", i),
		}).OK(t, http.StatusCreated)
	}
	c.POST("/portfolio/"+projectID+"/links", map[string]any{
		"label": "One too many", "url": "https://example.org/last",
	}).Fails(t, http.StatusConflict, "links_full")

	removable := res.String("id")
	c.DELETE("/portfolio/links/"+removable).OK(t, http.StatusNoContent)
	c.DELETE("/portfolio/links/"+removable).Fails(t, http.StatusNotFound, "not_found")
}

// ── Limits and validation ───────────────────────────────────────────────────

func TestPortfolioValidationRefusesNonsense(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("validdev", "backend-developer")
	c := dev.Client

	c.POST("/portfolio", map[string]any{"title": "ab"}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	c.POST("/portfolio", map[string]any{
		"title": "Fine title", "technologies": []string{"go", "not-a-technology"},
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	c.POST("/portfolio", map[string]any{
		"title": "Fine title", "completed_on": "2099-01-01",
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	c.POST("/portfolio", map[string]any{
		"title": "Fine title", "value_visibility": "everyone",
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	c.POST("/portfolio", map[string]any{
		"title":        "Fine title",
		"technologies": []string{"go", "python", "postgresql", "redis", "docker", "kubernetes", "nginx", "fastapi", "django", "flask", "celery"},
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
}

func TestPortfolioIsCapped(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("capdev", "backend-developer")
	c := dev.Client

	// Inserted directly: the point is the API's refusal at the boundary, not
	// twenty-four round trips.
	h.Exec(`
		INSERT INTO portfolio_projects (developer_id, slug, title)
		SELECT $1, 'filler-' || g, 'Filler ' || g FROM generate_series(1, 24) g`,
		dev.UserID)

	c.POST("/portfolio", map[string]any{"title": "One too many"}).
		Fails(t, http.StatusConflict, "portfolio_full")
}

// ── Helpers ─────────────────────────────────────────────────────────────────

func createPortfolioItem(t *testing.T, c *testsupport.Client, title string) string {
	t.Helper()
	res := c.POST("/portfolio", map[string]any{
		"title":          title,
		"description":    "A working service built for a real client, described at enough length to pass the publishing bar without padding.",
		"technologies":   []string{"go", "postgresql"},
		"developer_role": "Backend developer",
	}).OK(t, http.StatusCreated)
	return res.String("id")
}

// publishablePortfolioItem creates an item that meets the publishing bar and
// publishes it.
func publishablePortfolioItem(t *testing.T, c *testsupport.Client, title string) string {
	t.Helper()
	projectID := createPortfolioItem(t, c, title)
	uploadScreenshot(t, c, projectID, "cover.png", pngFixture(1200, 800)).
		OK(t, http.StatusCreated)
	c.POST("/portfolio/"+projectID+"/publish", map[string]any{"published": true}).
		OK(t, http.StatusOK)
	return projectID
}

func uploadScreenshot(t *testing.T, c *testsupport.Client, projectID, filename string,
	body []byte) *testsupport.Response {
	t.Helper()

	var buf bytes.Buffer
	w := multipart.NewWriter(&buf)
	if err := w.WriteField("caption", "The stock overview"); err != nil {
		t.Fatalf("write field: %v", err)
	}
	// The part carries the type a browser would claim, which the pipeline
	// records and then ignores: the bytes decide.
	headers := textproto.MIMEHeader{}
	headers.Set("Content-Disposition",
		fmt.Sprintf(`form-data; name="image"; filename=%q`, filename))
	headers.Set("Content-Type", declaredTypeFor(filename))
	part, err := w.CreatePart(headers)
	if err != nil {
		t.Fatalf("create form file: %v", err)
	}
	if _, err := part.Write(body); err != nil {
		t.Fatalf("write form file: %v", err)
	}
	if err := w.Close(); err != nil {
		t.Fatalf("close multipart writer: %v", err)
	}
	return c.Multipart("/portfolio/"+projectID+"/images", w.FormDataContentType(), buf.Bytes())
}

// declaredTypeFor is what a browser would send for a file with this name —
// derived from the extension, which is exactly why the server never trusts it.
func declaredTypeFor(filename string) string {
	if strings.HasSuffix(filename, ".png") {
		return "image/png"
	}
	return "application/octet-stream"
}

func pngFixture(width, height int) []byte {
	m := image.NewNRGBA(image.Rect(0, 0, width, height))
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			m.Set(x, y, color.NRGBA{
				R: uint8(x * 255 / width),
				G: uint8(y * 255 / height),
				B: 120,
				A: 255,
			})
		}
	}
	var buf bytes.Buffer
	if err := png.Encode(&buf, m); err != nil {
		panic(err)
	}
	return buf.Bytes()
}
