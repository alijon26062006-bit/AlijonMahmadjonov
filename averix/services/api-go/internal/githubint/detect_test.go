package githubint

import (
	"strings"
	"testing"
)

func slugsOf(findings []Finding) map[string]float64 {
	out := map[string]float64{}
	for _, f := range findings {
		if f.SkillSlug == "" {
			continue
		}
		if f.Confidence > out[f.SkillSlug] {
			out[f.SkillSlug] = f.Confidence
		}
	}
	return out
}

func TestDetectGoMod(t *testing.T) {
	content := `module github.com/example/service

go 1.25.0

require (
	github.com/gin-gonic/gin v1.10.0
	github.com/jackc/pgx/v5 v5.11.0
	github.com/redis/go-redis/v9 v9.22.0
	google.golang.org/grpc v1.62.0
	github.com/go-telegram-bot-api/telegram-bot-api/v5 v5.5.1
	github.com/some/unknown-library v0.1.0
)`
	got := slugsOf(Detect("go.mod", content))

	for slug, minimum := range map[string]float64{
		"go": 1.0, "gin": 0.9, "postgresql": 0.85, "redis": 0.85,
		"grpc": 0.85, "telegram-api": 0.9,
	} {
		if got[slug] < minimum {
			t.Errorf("go.mod: %s confidence = %.2f, want at least %.2f", slug, got[slug], minimum)
		}
	}
	// An unrecognised dependency must not invent a technology.
	if len(got) > 6 {
		t.Errorf("go.mod produced %d technologies, want 6 known ones: %v", len(got), got)
	}
	// It is still recorded, so the map can be improved later.
	recorded := false
	for _, f := range Detect("go.mod", content) {
		if strings.Contains(f.RawName, "unknown-library") {
			recorded = true
			if f.SkillSlug != "" {
				t.Error("an unrecognised dependency must not be linked to a skill")
			}
		}
	}
	if !recorded {
		t.Error("an unrecognised dependency should still be recorded")
	}
}

func TestDetectPythonManifests(t *testing.T) {
	requirements := `# production
fastapi==0.115.0
uvicorn[standard]>=0.30
asyncpg~=0.29
aiogram==3.13.1
redis>=5.0
anthropic==0.40.0
-r dev-requirements.txt
`
	got := slugsOf(Detect("requirements.txt", requirements))
	for _, slug := range []string{"python", "fastapi", "postgresql", "aiogram", "redis", "anthropic-api"} {
		if got[slug] == 0 {
			t.Errorf("requirements.txt did not detect %s (got %v)", slug, got)
		}
	}

	poetry := `[tool.poetry]
name = "service"

[tool.poetry.dependencies]
python = "^3.12"
django = "^5.0"
psycopg2-binary = "^2.9"
celery = "^5.4"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
`
	got = slugsOf(Detect("pyproject.toml", poetry))
	for _, slug := range []string{"python", "django", "postgresql", "celery"} {
		if got[slug] == 0 {
			t.Errorf("pyproject.toml did not detect %s (got %v)", slug, got)
		}
	}
}

func TestDetectPackageJSON(t *testing.T) {
	content := `{
	  "name": "web",
	  "dependencies": {
	    "next": "15.0.0",
	    "react": "19.0.0",
	    "@telegram-apps/sdk": "^2.0.0",
	    "pg": "^8.11.0",
	    "stripe": "^16.0.0"
	  },
	  "devDependencies": {
	    "typescript": "^5.6.0",
	    "@playwright/test": "^1.48.0",
	    "tailwindcss": "^3.4.0"
	  }
	}`
	got := slugsOf(Detect("package.json", content))
	for _, slug := range []string{"nextjs", "react", "telegram-mini-apps", "postgresql",
		"stripe", "typescript", "testing", "tailwind"} {
		if got[slug] == 0 {
			t.Errorf("package.json did not detect %s (got %v)", slug, got)
		}
	}
	// A dev dependency is weaker evidence than a production one.
	if got["typescript"] >= got["nextjs"] {
		t.Errorf("a dev dependency (%.2f) should count for less than a production one (%.2f)",
			got["typescript"], got["nextjs"])
	}
}

// react-native must not be mistaken for react merely because react is a
// prefix of it.
func TestMostSpecificDependencyWins(t *testing.T) {
	content := `{"dependencies": {"react-native": "0.76.0", "react": "18.3.1"}}`
	findings := Detect("package.json", content)

	byRaw := map[string]string{}
	for _, f := range findings {
		byRaw[f.RawName] = f.SkillSlug
	}
	if byRaw["react-native"] != "react-native" {
		t.Errorf("react-native resolved to %q, want react-native", byRaw["react-native"])
	}
	if byRaw["react"] != "react" {
		t.Errorf("react resolved to %q, want react", byRaw["react"])
	}
}

func TestDetectDockerAndCompose(t *testing.T) {
	dockerfile := `FROM golang:1.25-alpine AS build
WORKDIR /src
RUN go build -o /app ./cmd/api

FROM alpine:3.20
COPY --from=build /app /app
`
	got := slugsOf(Detect("Dockerfile", dockerfile))
	if got["docker"] == 0 {
		t.Error("a Dockerfile must prove Docker")
	}
	if got["go"] == 0 {
		t.Error("a golang base image should be detected")
	}

	compose := `services:
  api:
    build: .
  db:
    image: postgres:16-alpine
  cache:
    image: redis:7-alpine
  proxy:
    image: nginx:1.27
  metrics:
    image: prom/prometheus:latest
`
	got = slugsOf(Detect("docker-compose.yml", compose))
	for _, slug := range []string{"docker", "postgresql", "redis", "nginx", "prometheus"} {
		if got[slug] == 0 {
			t.Errorf("docker-compose.yml did not detect %s (got %v)", slug, got)
		}
	}
}

func TestDetectPHPAndJava(t *testing.T) {
	composer := `{"require": {"php": "^8.3", "laravel/framework": "^11.0",
	              "predis/predis": "^2.2", "stripe/stripe-php": "^15.0"}}`
	got := slugsOf(Detect("composer.json", composer))
	for _, slug := range []string{"php", "laravel", "redis", "stripe"} {
		if got[slug] == 0 {
			t.Errorf("composer.json did not detect %s (got %v)", slug, got)
		}
	}

	gradle := `plugins { id("org.springframework.boot") version "3.3.0" }
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.jetbrains.kotlin:kotlin-stdlib")
}`
	got = slugsOf(Detect("build.gradle.kts", gradle))
	if got["spring-boot"] == 0 {
		t.Errorf("build.gradle did not detect Spring Boot (got %v)", got)
	}
	if got["kotlin"] == 0 {
		t.Errorf("build.gradle did not detect Kotlin (got %v)", got)
	}
}

func TestDetectIgnoresGarbage(t *testing.T) {
	for _, tc := range []struct{ file, content string }{
		{"package.json", "not json at all"},
		{"package.json", ""},
		{"go.mod", ""},
		{"composer.json", "{{{"},
		{"unknown.txt", "fastapi==1.0"},
		{"requirements.txt", "   \n# only comments\n"},
	} {
		findings := Detect(tc.file, tc.content)
		for _, f := range findings {
			if f.SkillSlug != "" && tc.file == "unknown.txt" {
				t.Errorf("an unrecognised manifest name must produce nothing, got %v", f)
			}
		}
	}
}

// The specification is explicit that code share must never be converted into
// a competence rating. LanguageShares returns shares only — there is no field
// to put a rating in.
func TestLanguageSharesReportCodeOnly(t *testing.T) {
	totals := map[string]int64{
		"Go": 390000, "Python": 310000, "TypeScript": 180000,
		"Shell": 60000, "Dockerfile": 30000, "Makefile": 20000, "HTML": 10000,
	}
	stats := LanguageShares(totals, 3)

	if len(stats) != 4 {
		t.Fatalf("stats = %d, want the top 3 plus Other", len(stats))
	}
	if stats[0].Language != "Go" || stats[1].Language != "Python" || stats[2].Language != "TypeScript" {
		t.Errorf("order = %s, %s, %s; want Go, Python, TypeScript",
			stats[0].Language, stats[1].Language, stats[2].Language)
	}
	if stats[3].Language != "Other" {
		t.Errorf("the fourth entry is %q, want Other", stats[3].Language)
	}

	// The shares must add to 1: collapsing the tail must not lose any.
	var sum float64
	for _, s := range stats {
		sum += s.Share
		if s.Share <= 0 || s.Share > 1 {
			t.Errorf("%s share = %.4f, outside 0-1", s.Language, s.Share)
		}
	}
	if sum < 0.999 || sum > 1.001 {
		t.Errorf("shares add to %.4f, want 1", sum)
	}
	// 39% of the code, reported as exactly that.
	if got := stats[0].Share; got < 0.38 || got > 0.40 {
		t.Errorf("Go share = %.3f, want about 0.39", got)
	}
	if stats[0].Bytes != 390000 {
		t.Errorf("Go bytes = %d, want the raw count preserved", stats[0].Bytes)
	}
}

func TestLanguageSharesHandlesEmptyInput(t *testing.T) {
	if stats := LanguageShares(nil, 5); stats != nil {
		t.Errorf("no languages should produce no stats, got %v", stats)
	}
	if stats := LanguageShares(map[string]int64{"Go": 0}, 5); stats != nil {
		t.Errorf("zero bytes should produce no stats, got %v", stats)
	}
}

func TestLanguageSharesAreStable(t *testing.T) {
	// Equal byte counts must order deterministically, or the profile reshuffles
	// on every analysis.
	totals := map[string]int64{"Go": 1000, "Rust": 1000, "Python": 1000}
	first := LanguageShares(totals, 5)
	for i := 0; i < 20; i++ {
		again := LanguageShares(totals, 5)
		for j := range first {
			if first[j].Language != again[j].Language {
				t.Fatalf("ordering is unstable: %s then %s at position %d",
					first[j].Language, again[j].Language, j)
			}
		}
	}
}

func TestSummariseTechnologiesRewardsBreadth(t *testing.T) {
	oneRepo := [][]Finding{
		{{SkillSlug: "go", Source: "go.mod", Confidence: 1.0}},
	}
	fourRepos := [][]Finding{
		{{SkillSlug: "python", Source: "requirements.txt", Confidence: 0.9}},
		{{SkillSlug: "python", Source: "pyproject.toml", Confidence: 0.9}},
		{{SkillSlug: "python", Source: "Dockerfile", Confidence: 0.7}},
		{{SkillSlug: "python", Source: "requirements.txt", Confidence: 0.9}},
	}

	single := SummariseTechnologies(oneRepo, map[string]string{"go": "Go"})
	across := SummariseTechnologies(fourRepos, map[string]string{"python": "Python"})

	if len(single) != 1 || len(across) != 1 {
		t.Fatalf("expected one technology each, got %d and %d", len(single), len(across))
	}
	if single[0].Repositories != 1 {
		t.Errorf("repositories = %d, want 1", single[0].Repositories)
	}
	if across[0].Repositories != 4 {
		t.Errorf("repositories = %d, want 4", across[0].Repositories)
	}
	// Appearing in four repositories should not be outscored by one perfect hit.
	if across[0].Confidence < 0.85 {
		t.Errorf("confidence across four repositories = %.2f, want 0.85 or more",
			across[0].Confidence)
	}
	if len(across[0].Sources) != 3 {
		t.Errorf("sources = %v, want the three distinct manifests", across[0].Sources)
	}
	if across[0].Name != "Python" {
		t.Errorf("name = %q, want the taxonomy's display name", across[0].Name)
	}
}

func TestSummariseTechnologiesOrdersByStrength(t *testing.T) {
	perRepo := [][]Finding{
		{
			{SkillSlug: "go", Source: "go.mod", Confidence: 1.0},
			{SkillSlug: "redis", Source: "go.mod", Confidence: 0.9},
			{SkillSlug: "testing", Source: "go.mod", Confidence: 0.5},
		},
		{
			{SkillSlug: "go", Source: "go.mod", Confidence: 1.0},
			{SkillSlug: "redis", Source: "docker-compose.yml", Confidence: 0.85},
		},
	}
	out := SummariseTechnologies(perRepo, nil)
	if len(out) != 3 {
		t.Fatalf("technologies = %d, want 3", len(out))
	}
	if out[0].Slug != "go" {
		t.Errorf("the strongest technology is %q, want go", out[0].Slug)
	}
	if out[len(out)-1].Slug != "testing" {
		t.Errorf("the weakest technology is %q, want testing", out[len(out)-1].Slug)
	}
	for i := 1; i < len(out); i++ {
		if out[i-1].Confidence < out[i].Confidence {
			t.Errorf("output is not ordered by confidence: %.2f then %.2f",
				out[i-1].Confidence, out[i].Confidence)
		}
	}
}

func TestPortfolioWorthiness(t *testing.T) {
	substantial := Repository{
		Name: "marketplace-api", Description: "Backend for a marketplace, Go and PostgreSQL.",
		Size: 1800, Stars: 12, Homepage: "https://demo.example.com",
		Topics: []string{"go", "postgresql"},
	}
	if ok, reason := PortfolioWorthiness(substantial, true, 8); !ok {
		t.Errorf("a described, documented, deployed repository should be a candidate (%s)", reason)
	} else if reason == "" {
		t.Error("a candidate must carry the reason it was suggested")
	}

	cases := []struct {
		name string
		repo Repository
	}{
		{"a fork", Repository{Fork: true, Description: "d", Size: 5000, Homepage: "https://x.example"}},
		{"private", Repository{Private: true, Description: "d", Size: 5000}},
		{"archived", Repository{Archived: true, Description: "d", Size: 5000, Homepage: "https://x.example"}},
		{"tiny", Repository{Description: "d", Size: 4}},
		{"undescribed and undocumented", Repository{Name: "scratch", Size: 200}},
	}
	for _, tc := range cases {
		if ok, _ := PortfolioWorthiness(tc.repo, false, 0); ok {
			t.Errorf("%s must not be suggested as portfolio work", tc.name)
		}
	}

	// A useful internal tool with no stars still qualifies on its substance.
	unstarred := Repository{
		Name: "deploy-tool", Description: "Zero-downtime deploys for our services.",
		Size: 900,
	}
	if ok, _ := PortfolioWorthiness(unstarred, true, 5); !ok {
		t.Error("a substantial, documented repository should qualify without stars")
	}
}

func TestSafeRedirectRefusesOpenRedirects(t *testing.T) {
	const app = "https://averix.example"

	hostile := []string{
		"https://evil.example/steal",
		"//evil.example/steal",
		"http://evil.example",
		"/\\evil.example",
		"javascript:alert(1)",
		"/path\r\nLocation: https://evil.example",
	}
	for _, requested := range hostile {
		got := SafeRedirect(app, requested)
		if !strings.HasPrefix(got, app) {
			t.Errorf("SafeRedirect(%q) = %q, which leaves the application", requested, got)
		}
		if strings.Contains(got, "evil.example") {
			t.Errorf("SafeRedirect(%q) = %q, which reaches the attacker's host", requested, got)
		}
	}

	for requested, want := range map[string]string{
		"":                          app + "/settings/github",
		"/settings/github":          app + "/settings/github",
		"/onboarding/github?step=7": app + "/onboarding/github?step=7",
		"/developers/ali":           app + "/developers/ali",
	} {
		if got := SafeRedirect(app, requested); got != want {
			t.Errorf("SafeRedirect(%q) = %q, want %q", requested, got, want)
		}
	}
}
