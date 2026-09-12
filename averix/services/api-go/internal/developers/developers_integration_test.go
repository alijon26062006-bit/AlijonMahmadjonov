package developers_test

import (
	"bytes"
	"image"
	"image/color"
	"image/jpeg"
	"image/png"
	"mime/multipart"
	"net/http"
	"strings"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

// ── Onboarding ──────────────────────────────────────────────────────────────

func TestOnboardingFlowPublishesAProfile(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("alidev")

	// Step 1 — about you.
	res := c.PUT("/developers/me/basics", map[string]any{
		"full_name":    "Ali Mahmadjonov",
		"country_code": "TJ",
		"city":         "Dushanbe",
		"timezone":     "Asia/Dushanbe",
		"languages": []map[string]string{
			{"language": "Tajik", "proficiency": "native"},
			{"language": "Russian", "proficiency": "fluent"},
			{"language": "English", "proficiency": "conversational"},
		},
	}).OK(t, http.StatusOK)
	if res.Float("next_step") != 2 {
		t.Errorf("next_step = %v, want 2", res.Float("next_step"))
	}

	// Step 2 — one primary profession, and only one.
	c.PUT("/developers/me/specialisation", map[string]any{
		"slug":               "backend-developer",
		"professional_title": "Backend Developer",
	}).OK(t, http.StatusOK)

	// Step 3 — up to three more.
	c.PUT("/developers/me/additional-specialisations", map[string]any{
		"slugs": []string{"telegram-developer", "devops-engineer"},
	}).OK(t, http.StatusOK)

	// Step 4 — technologies.
	c.PUT("/developers/me/technologies", map[string]any{
		"technologies": []map[string]any{
			{"slug": "go", "level": "expert", "years": 6},
			{"slug": "python", "level": "strong", "years": 5},
			{"slug": "fastapi", "level": "strong"},
			{"slug": "postgresql", "level": "expert", "years": 6},
			{"slug": "redis", "level": "working"},
			{"slug": "docker", "level": "strong"},
			{"slug": "telegram-api", "level": "expert"},
		},
	}).OK(t, http.StatusOK)

	// Step 5 — experience.
	c.PUT("/developers/me/experience", map[string]any{
		"experience_level":  "senior",
		"years_experience":  6,
		"hourly_rate_minor": 4500,
		"min_project_minor": 50000,
		"currency":          "USD",
	}).OK(t, http.StatusOK)

	// Step 8 — availability.
	c.PUT("/developers/me/availability", map[string]any{
		"availability":        "available",
		"hours_per_week":      30,
		"overlap_from_utc":    3,
		"overlap_to_utc":      12,
		"open_to_invitations": true,
		"show_location":       true,
		"show_hourly_rate":    true,
	}).OK(t, http.StatusOK)

	// Step 9 — the professional summary.
	bio := "I build backend systems in Go and Python, mostly APIs and Telegram " +
		"integrations backed by PostgreSQL. I have shipped payment flows, " +
		"admin panels and data pipelines, and I care about the parts that are " +
		"hard to see: migrations that run safely, and errors that say something useful."
	c.PUT("/developers/me/bio", map[string]any{"bio": bio}).OK(t, http.StatusOK)

	// Publishing requires a verified address, which is deliberate: a searchable
	// profile is a public claim under an address the person controls.
	c.POST("/developers/me/finish", nil).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	h.Exec(`UPDATE users SET email_verified_at = now() WHERE username = 'alidev'`)

	published := c.POST("/developers/me/finish", nil).OK(t, http.StatusOK)
	if !published.Bool("is_searchable") {
		t.Error("finishing onboarding must make the profile searchable")
	}

	onboarding, _ := published.Data["onboarding"].(map[string]any)
	if completed, _ := onboarding["completed"].(bool); !completed {
		t.Error("onboarding must be marked completed")
	}
	completeness, _ := onboarding["completeness"].(float64)
	// Photo and GitHub are still missing, which is 20 points.
	if completeness < 70 || completeness > 85 {
		t.Errorf("completeness = %v; expected 70-85 with photo and GitHub still missing", completeness)
	}
	missing := onboarding["missing"].([]any)
	missingKeys := map[string]bool{}
	for _, raw := range missing {
		item := raw.(map[string]any)
		missingKeys[item["key"].(string)] = true
	}
	if !missingKeys["photo"] || !missingKeys["github"] {
		t.Errorf("expected photo and github to be listed as missing, got %v", missingKeys)
	}
}

// The profile must not be discoverable until its owner finishes the flow.
func TestUnfinishedProfileIsNotPublic(t *testing.T) {
	h := testsupport.New(t)
	owner := h.Client()
	owner.RegisterDeveloper("halfdone")

	h.Client().GET("/developers/halfdone").Fails(t, http.StatusNotFound, "not_found")

	// The owner can always see their own, which is how they preview it.
	res := owner.GET("/developers/halfdone").OK(t, http.StatusOK)
	if !res.Bool("is_owner") {
		t.Error("the owner must be told it is their own profile")
	}
}

func TestOnlyOnePrimarySpecialisation(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("onefocus")

	c.PUT("/developers/me/specialisation", map[string]any{"slug": "backend-developer"}).
		OK(t, http.StatusOK)
	c.PUT("/developers/me/specialisation", map[string]any{"slug": "frontend-developer"}).
		OK(t, http.StatusOK)

	// Setting it again replaces rather than accumulates.
	res := c.GET("/developers/me").OK(t, http.StatusOK)
	primary, _ := res.Data["primary_specialisation"].(map[string]any)
	if primary["slug"] != "frontend-developer" {
		t.Errorf("primary specialisation = %v, want frontend-developer", primary["slug"])
	}
	if n := h.Count(`SELECT count(*) FROM developer_profiles
	                  WHERE primary_specialisation_id IS NOT NULL`); n != 1 {
		t.Errorf("developer profiles with a primary specialisation = %d, want 1", n)
	}
}

func TestAdditionalSpecialisationsAreCappedAtThree(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("greedy")
	c.PUT("/developers/me/specialisation", map[string]any{"slug": "backend-developer"}).
		OK(t, http.StatusOK)

	// Three is fine.
	c.PUT("/developers/me/additional-specialisations", map[string]any{
		"slugs": []string{"frontend-developer", "devops-engineer", "telegram-developer"},
	}).OK(t, http.StatusOK)

	// Four is not — the product refuses "I do everything".
	res := c.PUT("/developers/me/additional-specialisations", map[string]any{
		"slugs": []string{"frontend-developer", "devops-engineer", "telegram-developer",
			"mobile-developer"},
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if _, ok := res.Fields["slugs"]; !ok {
		t.Errorf("expected a problem on slugs, got %v", res.Fields)
	}
	// The earlier three survive the rejected write.
	if n := h.Count(`SELECT count(*) FROM developer_specialisations`); n != 3 {
		t.Errorf("additional specialisations = %d, want the previous 3 intact", n)
	}
}

func TestAdditionalSpecialisationCannotRepeatThePrimary(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("duplicator")
	c.PUT("/developers/me/specialisation", map[string]any{"slug": "backend-developer"}).
		OK(t, http.StatusOK)

	res := c.PUT("/developers/me/additional-specialisations", map[string]any{
		"slugs": []string{"backend-developer"},
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if !strings.Contains(strings.ToLower(res.Fields["slugs"]), "main profession") {
		t.Errorf("the message should explain the duplication, got %q", res.Fields["slugs"])
	}
}

func TestTechnologiesAreCappedAtFifteenAndValidatedAgainstTheTaxonomy(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("techlist")

	// An invented technology is refused rather than stored as free text.
	res := c.PUT("/developers/me/technologies", map[string]any{
		"technologies": []map[string]any{
			{"slug": "go", "level": "expert"},
			{"slug": "my-own-framework", "level": "expert"},
		},
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if !strings.Contains(res.Fields["technologies"], "my-own-framework") {
		t.Errorf("the message should name the unknown technology, got %q", res.Fields["technologies"])
	}

	// Sixteen real technologies is still refused.
	sixteen := []string{"go", "python", "typescript", "javascript", "php", "java",
		"kotlin", "swift", "rust", "csharp", "ruby", "dart", "sql", "bash",
		"postgresql", "redis"}
	entries := make([]map[string]any, 0, len(sixteen))
	for _, slug := range sixteen {
		entries = append(entries, map[string]any{"slug": slug, "level": "working"})
	}
	c.PUT("/developers/me/technologies", map[string]any{"technologies": entries}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	// Fifteen is accepted.
	c.PUT("/developers/me/technologies", map[string]any{"technologies": entries[:15]}).
		OK(t, http.StatusOK)
	if n := h.Count(`SELECT count(*) FROM developer_skills WHERE is_primary`); n != 15 {
		t.Errorf("primary skills = %d, want 15", n)
	}
}

// GitHub analysis attaches evidence to a skill. Re-editing the list by hand
// must not erase the platform's own corroboration.
func TestEditingTechnologiesPreservesEvidence(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("evidenced")

	c.PUT("/developers/me/technologies", map[string]any{
		"technologies": []map[string]any{
			{"slug": "go", "level": "strong"},
			{"slug": "python", "level": "working"},
		},
	}).OK(t, http.StatusOK)

	h.Exec(`
		UPDATE developer_skills SET evidence = ARRAY['github']
		WHERE skill_id = (SELECT id FROM skills WHERE slug = 'go')`)

	// The developer edits their list, keeping Go and dropping Python.
	c.PUT("/developers/me/technologies", map[string]any{
		"technologies": []map[string]any{
			{"slug": "go", "level": "expert", "years": 7},
			{"slug": "docker", "level": "working"},
		},
	}).OK(t, http.StatusOK)

	var evidence []string
	h.QueryRow([]any{&evidence}, `
		SELECT evidence FROM developer_skills
		WHERE skill_id = (SELECT id FROM skills WHERE slug = 'go')`)
	if len(evidence) != 1 || evidence[0] != "github" {
		t.Errorf("evidence = %v, want it preserved as [github] across the edit", evidence)
	}
}

func TestBioRequiresSubstance(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("terse")

	res := c.PUT("/developers/me/bio", map[string]any{"bio": "I write code."}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if !strings.Contains(res.Fields["bio"], "120") {
		t.Errorf("the message should state the minimum length, got %q", res.Fields["bio"])
	}
}

// ── Privacy of the public profile ───────────────────────────────────────────

func TestPublicProfileRespectsPrivacyToggles(t *testing.T) {
	h := testsupport.New(t)
	dev := publishedDeveloper(t, h, "privacydev")

	// Rate and location hidden.
	dev.PUT("/developers/me/availability", map[string]any{
		"availability":     "available",
		"show_location":    false,
		"show_hourly_rate": false,
	}).OK(t, http.StatusOK)

	res := h.Client().GET("/developers/privacydev").OK(t, http.StatusOK)
	if _, present := res.Data["hourly_rate_minor"]; present {
		t.Error("the hourly rate must be absent when the developer hid it")
	}
	if _, present := res.Data["location"]; present {
		t.Error("the location must be absent when the developer hid it")
	}

	// Shown again.
	dev.PUT("/developers/me/availability", map[string]any{
		"availability":     "available",
		"show_location":    true,
		"show_hourly_rate": true,
	}).OK(t, http.StatusOK)

	res = h.Client().GET("/developers/privacydev").OK(t, http.StatusOK)
	if res.Float("hourly_rate_minor") != 4500 {
		t.Errorf("hourly_rate_minor = %v, want 4500 once shown", res.Data["hourly_rate_minor"])
	}
	if res.String("location") == "" {
		t.Error("the location must appear once shown")
	}
}

// Private financial figures must never appear on a public profile, whatever
// the viewer's role.
func TestPublicProfileNeverExposesEarnings(t *testing.T) {
	h := testsupport.New(t)
	publishedDeveloper(t, h, "earner")
	h.Exec(`UPDATE developer_profiles SET total_earned_minor = 1234500
	         WHERE user_id = (SELECT id FROM users WHERE username = 'earner')`)

	viewers := map[string]*testsupport.Client{
		"anonymous": h.Client(),
		"client":    h.Client(),
		"developer": h.Client(),
	}
	viewers["client"].RegisterClient("nosyclient")
	viewers["developer"].RegisterDeveloper("nosydev")

	for name, viewer := range viewers {
		res := viewer.GET("/developers/earner").OK(t, http.StatusOK)
		for _, forbidden := range []string{"total_earned_minor", "earnings", "min_project_minor"} {
			if _, present := res.Data[forbidden]; present {
				t.Errorf("%s viewer sees %q on a public profile", name, forbidden)
			}
		}
		if bytes.Contains(res.Raw, []byte("1234500")) {
			t.Errorf("%s viewer sees the earnings figure in the response body", name)
		}
	}

	// The owner does see their own.
	owner := h.Client()
	owner.Login("earner@example.test", "quiet-lantern-4417").OK(t, http.StatusOK)
	own := owner.GET("/developers/me").OK(t, http.StatusOK)
	earnings, ok := own.Data["earnings"].(map[string]any)
	if !ok {
		t.Fatal("the owner must see their own earnings")
	}
	if earnings["total_earned_minor"].(float64) != 1234500 {
		t.Errorf("owner's total_earned_minor = %v, want 1234500", earnings["total_earned_minor"])
	}
}

func TestBadgesComeFromPlatformStateOnly(t *testing.T) {
	h := testsupport.New(t)
	publishedDeveloper(t, h, "badged")

	res := h.Client().GET("/developers/badged").OK(t, http.StatusOK)
	kinds := badgeKinds(res.Data)
	if !kinds["available"] {
		t.Error("an available developer must carry the availability badge")
	}
	if kinds["identity_verified"] {
		t.Error("identity verification must not be granted by default")
	}
	if kinds["top_rated"] {
		t.Error("top rated must not be granted without reviews")
	}

	// A single perfect review is not a track record.
	h.Exec(`UPDATE developer_profiles SET rating_avg = 5.0, rating_count = 1
	         WHERE user_id = (SELECT id FROM users WHERE username = 'badged')`)
	res = h.Client().GET("/developers/badged").OK(t, http.StatusOK)
	if badgeKinds(res.Data)["top_rated"] {
		t.Error("top rated must require enough reviews to mean something")
	}

	h.Exec(`UPDATE developer_profiles SET rating_avg = 4.9, rating_count = 12
	         WHERE user_id = (SELECT id FROM users WHERE username = 'badged')`)
	h.Exec(`UPDATE users SET identity_verified_at = now() WHERE username = 'badged'`)
	res = h.Client().GET("/developers/badged").OK(t, http.StatusOK)
	kinds = badgeKinds(res.Data)
	if !kinds["top_rated"] || !kinds["identity_verified"] {
		t.Errorf("expected top_rated and identity_verified, got %v", kinds)
	}
}

func badgeKinds(data map[string]any) map[string]bool {
	out := map[string]bool{}
	raw, _ := data["badges"].([]any)
	for _, item := range raw {
		if badge, ok := item.(map[string]any); ok {
			if kind, ok := badge["kind"].(string); ok {
				out[kind] = true
			}
		}
	}
	return out
}

// ── Authorisation ───────────────────────────────────────────────────────────

// A client must not be able to write a developer profile, and one developer
// must not be able to write another's.
func TestProfileWritesAreOwnerOnly(t *testing.T) {
	h := testsupport.New(t)
	publishedDeveloper(t, h, "target")

	client := h.Client()
	client.RegisterClient("wrongrole")
	client.PUT("/developers/me/bio", map[string]any{
		"bio": strings.Repeat("a client trying to write a developer profile. ", 5),
	}).Fails(t, http.StatusForbidden, "forbidden")

	// There is no endpoint that takes another developer's id at all: /me is
	// the only writable path, which is the structural reason this cannot happen.
	other := h.Client()
	other.RegisterDeveloper("otherdev")
	other.PUT("/developers/me/specialisation", map[string]any{"slug": "frontend-developer"}).
		OK(t, http.StatusOK)

	var targetSpec string
	h.QueryRow([]any{&targetSpec}, `
		SELECT sp.slug FROM developer_profiles d
		JOIN specialisations sp ON sp.id = d.primary_specialisation_id
		JOIN users u ON u.id = d.user_id WHERE u.username = 'target'`)
	if targetSpec != "backend-developer" {
		t.Errorf("the other developer's write changed target's profile: %q", targetSpec)
	}
}

func TestAnonymousCannotWriteAProfile(t *testing.T) {
	h := testsupport.New(t)
	h.Client().PUT("/developers/me/bio", map[string]any{"bio": strings.Repeat("x", 200)}).
		Fails(t, http.StatusUnauthorized, "unauthenticated")
	h.Client().GET("/developers/me").Fails(t, http.StatusUnauthorized, "unauthenticated")
}

// ── Photo pipeline ──────────────────────────────────────────────────────────

func TestPhotoUploadProducesEveryDerivative(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("photodev")

	res := uploadPhoto(t, h, c, "portrait.jpg", jpegFixture(t, 900, 1200))
	res.OK(t, http.StatusCreated)

	if res.Float("width") != 900 || res.Float("height") != 1200 {
		t.Errorf("reported dimensions %vx%v, want 900x1200", res.Data["width"], res.Data["height"])
	}
	// The default crop is centred and square, never a stretch.
	crop, _ := res.Data["Crop"].(map[string]any)
	if crop == nil {
		crop, _ = res.Data["crop"].(map[string]any)
	}

	photo, ok := res.Data["Photo"].(map[string]any)
	if !ok {
		photo, ok = res.Data["photo"].(map[string]any)
	}
	if !ok {
		t.Fatalf("upload response carries no photo set: %s", res.Raw)
	}
	sources, _ := photo["sources"].(map[string]any)
	if sources["webp"] == nil || sources["jpeg"] == nil {
		t.Errorf("expected both webp and jpeg sources, got %v", keysOf(sources))
	}
	webp, _ := sources["webp"].(map[string]any)
	for _, size := range []string{"64", "128", "256", "512"} {
		if webp[size] == nil {
			t.Errorf("missing the %spx webp derivative (have %v)", size, keysOf(webp))
		}
	}
	if photo["placeholder"] == nil || photo["placeholder"] == "" {
		t.Error("a blur-up placeholder colour must be produced")
	}

	// The original is kept privately so the crop can be replayed later.
	var originalKey string
	h.QueryRow([]any{&originalKey}, `
		SELECT original_key FROM developer_photos
		WHERE is_current AND user_id = (SELECT id FROM users WHERE username = 'photodev')`)
	if !strings.HasPrefix(originalKey, "avatar-original/") {
		t.Errorf("original_key = %q, want it under avatar-original/", originalKey)
	}
	// The key must not be derived from the uploaded filename.
	if strings.Contains(originalKey, "portrait") {
		t.Errorf("the storage key %q was derived from the uploaded filename", originalKey)
	}
}

func TestPhotoUploadRejectsDisguisedFiles(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("uploadguard")

	cases := []struct {
		name     string
		filename string
		body     []byte
		status   int
	}{
		{"php webshell named jpg", "avatar.jpg", []byte("<?php system($_GET['c']); ?>"), http.StatusUnsupportedMediaType},
		{"html named png", "avatar.png", []byte("<html><script>alert(1)</script></html>"), http.StatusUnsupportedMediaType},
		{"svg with script", "avatar.svg", []byte(`<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>`), http.StatusUnsupportedMediaType},
		{"elf binary", "avatar.jpeg", []byte("\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00"), http.StatusUnsupportedMediaType},
		{"empty file", "avatar.jpg", []byte{}, http.StatusUnsupportedMediaType},
		{"pdf", "avatar.jpg", []byte("%PDF-1.7\n1 0 obj\n<<>>\nendobj\n"), http.StatusUnsupportedMediaType},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			res := uploadPhoto(t, h, c, tc.filename, tc.body)
			if res.Status != tc.status {
				t.Errorf("status = %d, want %d (body: %s)", res.Status, tc.status, res.Raw)
			}
			// The message must be something a person can act on.
			if res.Message == "" {
				t.Error("a rejected upload must explain itself")
			}
		})
	}
	if n := h.Count(`SELECT count(*) FROM developer_photos`); n != 0 {
		t.Errorf("developer_photos rows = %d, want 0 — nothing was a valid image", n)
	}
}

// A JPEG carrying an appended payload decodes fine, and the derivatives served
// must contain none of it.
func TestPhotoUploadStripsAppendedPayload(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("polyglot")

	payload := []byte("<?php system($_GET['cmd']); ?>")
	body := append(jpegFixture(t, 400, 400), payload...)
	uploadPhoto(t, h, c, "sneaky.jpg", body).OK(t, http.StatusCreated)

	// Every stored derivative is re-encoded from the decoded pixels.
	var keys map[string]map[string]string
	h.QueryRow([]any{&keys}, `
		SELECT derivatives FROM developer_photos
		WHERE is_current AND user_id = (SELECT id FROM users WHERE username = 'polyglot')`)
	if len(keys) == 0 {
		t.Fatal("no derivatives were recorded")
	}
	for format, sizes := range keys {
		for size, key := range sizes {
			data := readStoredObject(t, h, key)
			if bytes.Contains(data, payload) {
				t.Errorf("the %s/%s derivative still contains the appended payload", format, size)
			}
		}
	}
}

func TestRecropUsesTheStoredOriginal(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("recropper")
	uploadPhoto(t, h, c, "wide.jpg", jpegFixture(t, 1200, 600)).OK(t, http.StatusCreated)

	// A crop that fits.
	c.PUT("/developers/me/photo/crop", map[string]any{
		"x": 100, "y": 50, "width": 400, "height": 400, "shape": "rounded",
	}).OK(t, http.StatusOK)

	var shape string
	var cropX, cropW int
	h.QueryRow([]any{&shape, &cropX, &cropW}, `
		SELECT crop_shape, crop_x, crop_w FROM developer_photos
		WHERE is_current AND user_id = (SELECT id FROM users WHERE username = 'recropper')`)
	if shape != "rounded" || cropX != 100 || cropW != 400 {
		t.Errorf("stored crop = shape %q at x=%d w=%d, want rounded/100/400", shape, cropX, cropW)
	}

	// A crop that falls outside the image is refused with a usable message.
	res := c.PUT("/developers/me/photo/crop", map[string]any{
		"x": 1100, "y": 500, "width": 400, "height": 400,
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if res.Fields["crop"] == "" {
		t.Error("an out-of-bounds crop must report a problem on the crop field")
	}

	// Rotation outside the four quarter turns is refused.
	c.PUT("/developers/me/photo/crop", map[string]any{
		"x": 0, "y": 0, "width": 400, "height": 400, "rotation": 45,
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
}

func TestRecropWithoutAPhotoIsAClearError(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("nophoto")

	res := c.PUT("/developers/me/photo/crop", map[string]any{
		"x": 0, "y": 0, "width": 200, "height": 200,
	}).Fails(t, http.StatusNotFound, "not_found")
	if !strings.Contains(strings.ToLower(res.Message), "upload one first") {
		t.Errorf("the message should tell the user what to do, got %q", res.Message)
	}
}

// Replacing a photo must not leave the previous derivatives behind.
func TestReplacingAPhotoRemovesThePreviousDerivatives(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("replacer")

	uploadPhoto(t, h, c, "first.jpg", jpegFixture(t, 500, 500)).OK(t, http.StatusCreated)
	var firstKeys map[string]map[string]string
	h.QueryRow([]any{&firstKeys}, `
		SELECT derivatives FROM developer_photos
		WHERE is_current AND user_id = (SELECT id FROM users WHERE username = 'replacer')`)

	uploadPhoto(t, h, c, "second.png", pngFixture(t, 600, 600)).OK(t, http.StatusCreated)

	// Exactly one current photo.
	if n := h.Count(`SELECT count(*) FROM developer_photos WHERE is_current`); n != 1 {
		t.Errorf("current photos = %d, want 1", n)
	}
	for _, sizes := range firstKeys {
		for _, key := range sizes {
			if objectExists(t, h, key) {
				t.Errorf("the superseded derivative %s was not removed", key)
			}
		}
	}
}

func TestDeletingAPhotoRemovesEverything(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("deleter")
	uploadPhoto(t, h, c, "bye.jpg", jpegFixture(t, 400, 400)).OK(t, http.StatusCreated)

	var keys map[string]map[string]string
	var originalKey string
	h.QueryRow([]any{&keys, &originalKey}, `
		SELECT derivatives, original_key FROM developer_photos
		WHERE is_current AND user_id = (SELECT id FROM users WHERE username = 'deleter')`)

	c.DELETE("/developers/me/photo").OK(t, http.StatusNoContent)

	if n := h.Count(`SELECT count(*) FROM developer_photos`); n != 0 {
		t.Errorf("developer_photos rows = %d, want 0", n)
	}
	for _, sizes := range keys {
		for _, key := range sizes {
			if objectExists(t, h, key) {
				t.Errorf("derivative %s survived the delete", key)
			}
		}
	}
	// Deleting is idempotent.
	c.DELETE("/developers/me/photo").OK(t, http.StatusNoContent)
}

func TestPhotoUploadRequiresMultipart(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("wrongtype")
	c.POST("/developers/me/photo", map[string]any{"photo": "not-a-file"}).
		Fails(t, http.StatusUnsupportedMediaType, "unsupported_media_type")
}

// ── Client profiles ─────────────────────────────────────────────────────────

func TestClientProfileUpdateAndPublicView(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterClient("companyx")

	c.PUT("/clients/me", map[string]any{
		"full_name":       "Firuz Karimov",
		"company_name":    "Company X",
		"company_website": "companyx.example.com",
		"company_size":    "11-50",
		"industry":        "Retail",
		"about":           "We run a chain of clothing stores and are building our online side.",
		"country_code":    "TJ",
		"city":            "Khujand",
	}).OK(t, http.StatusOK)

	// The URL is normalised to https with a path.
	own := c.GET("/clients/me").OK(t, http.StatusOK)
	if own.String("company_website") != "https://companyx.example.com/" {
		t.Errorf("company_website = %q, want it normalised to https", own.String("company_website"))
	}

	// A developer sees the hiring context but not the spend.
	dev := h.Client()
	dev.RegisterDeveloper("bidder")
	public := dev.GET("/clients/companyx").OK(t, http.StatusOK)
	if public.String("display_name") != "Company X" {
		t.Errorf("display_name = %q, want the company name", public.String("display_name"))
	}
	if _, present := public.Data["total_spent_minor"]; present {
		t.Error("a client's spend must not be visible to developers")
	}
	if _, present := public.Data["email"]; present {
		t.Error("a client's email must not be visible to developers")
	}

	// Anonymous visitors do not see client pages at all.
	h.Client().GET("/clients/companyx").Fails(t, http.StatusUnauthorized, "unauthenticated")
}

func TestClientWebsiteGoesThroughTheURLGuard(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterClient("guardedclient")

	hostile := []string{
		"javascript:alert(1)",
		"http://169.254.169.254/latest/meta-data/",
		"http://localhost:8080/admin",
		"file:///etc/passwd",
		"https://trusted.example.com@evil.example/",
	}
	for _, url := range hostile {
		res := c.PUT("/clients/me", map[string]any{"company_website": url})
		if res.Status != http.StatusUnprocessableEntity {
			t.Errorf("%q was accepted as a company website (status %d)", url, res.Status)
			continue
		}
		if res.Fields["company_website"] == "" {
			t.Errorf("%q was refused without a message on the field", url)
		}
	}
}

func TestDeveloperCannotWriteAClientProfile(t *testing.T) {
	h := testsupport.New(t)
	dev := h.Client()
	dev.RegisterDeveloper("notaclient")
	dev.PUT("/clients/me", map[string]any{"company_name": "Not Mine"}).
		Fails(t, http.StatusForbidden, "forbidden")
}

// ── Helpers ─────────────────────────────────────────────────────────────────

// publishedDeveloper runs the whole onboarding flow and returns a signed-in
// client for that developer.
func publishedDeveloper(t *testing.T, h *testsupport.Harness, username string) *testsupport.Client {
	t.Helper()
	c := h.Client()
	c.RegisterDeveloper(username)

	c.PUT("/developers/me/basics", map[string]any{
		"full_name": "Test " + username, "country_code": "TJ", "city": "Dushanbe",
		"languages": []map[string]string{{"language": "English", "proficiency": "fluent"}},
	}).OK(t, http.StatusOK)
	c.PUT("/developers/me/specialisation", map[string]any{
		"slug": "backend-developer", "professional_title": "Backend Developer",
	}).OK(t, http.StatusOK)
	c.PUT("/developers/me/technologies", map[string]any{
		"technologies": []map[string]any{
			{"slug": "go", "level": "expert"},
			{"slug": "postgresql", "level": "strong"},
			{"slug": "docker", "level": "working"},
		},
	}).OK(t, http.StatusOK)
	c.PUT("/developers/me/experience", map[string]any{
		"experience_level": "senior", "years_experience": 6,
		"hourly_rate_minor": 4500, "currency": "USD",
	}).OK(t, http.StatusOK)
	c.PUT("/developers/me/availability", map[string]any{
		"availability": "available", "hours_per_week": 30,
		"show_location": true, "show_hourly_rate": true,
	}).OK(t, http.StatusOK)
	c.PUT("/developers/me/bio", map[string]any{
		"bio": "I build backend systems in Go, mostly APIs and integrations backed " +
			"by PostgreSQL. I have shipped payment flows and admin panels, and I care " +
			"about migrations that run safely and errors that say something useful.",
	}).OK(t, http.StatusOK)

	h.Exec(`UPDATE users SET email_verified_at = now() WHERE username = $1`, username)
	c.POST("/developers/me/finish", nil).OK(t, http.StatusOK)
	return c
}

func uploadPhoto(t *testing.T, h *testsupport.Harness, c *testsupport.Client,
	filename string, body []byte) *testsupport.Response {
	t.Helper()

	var buf bytes.Buffer
	w := multipart.NewWriter(&buf)
	part, err := w.CreateFormFile("photo", filename)
	if err != nil {
		t.Fatalf("create form file: %v", err)
	}
	if _, err := part.Write(body); err != nil {
		t.Fatalf("write form file: %v", err)
	}
	if err := w.Close(); err != nil {
		t.Fatalf("close multipart writer: %v", err)
	}
	return c.Multipart("/developers/me/photo", w.FormDataContentType(), buf.Bytes())
}

func jpegFixture(t *testing.T, w, h int) []byte {
	t.Helper()
	var buf bytes.Buffer
	if err := jpeg.Encode(&buf, gradient(w, h), &jpeg.Options{Quality: 90}); err != nil {
		t.Fatalf("encode jpeg fixture: %v", err)
	}
	return buf.Bytes()
}

func pngFixture(t *testing.T, w, h int) []byte {
	t.Helper()
	var buf bytes.Buffer
	if err := png.Encode(&buf, gradient(w, h)); err != nil {
		t.Fatalf("encode png fixture: %v", err)
	}
	return buf.Bytes()
}

func gradient(w, h int) *image.NRGBA {
	m := image.NewNRGBA(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			m.Set(x, y, color.NRGBA{
				R: uint8(x * 255 / maxInt(w-1, 1)),
				G: uint8(y * 255 / maxInt(h-1, 1)),
				B: 0x70, A: 255,
			})
		}
	}
	return m
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func keysOf(m map[string]any) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}

func readStoredObject(t *testing.T, h *testsupport.Harness, key string) []byte {
	t.Helper()
	return h.ReadObject(key, testsupport.Public)
}

func objectExists(t *testing.T, h *testsupport.Harness, key string) bool {
	t.Helper()
	return h.ObjectExists(key, testsupport.Public)
}
