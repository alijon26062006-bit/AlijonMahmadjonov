package matching

import (
	"encoding/json"
	"math"
	"testing"
	"time"
)

func fixedEngine() *Engine {
	e := NewEngine(DefaultWeights())
	// A fixed clock so recency-sensitive assertions are stable.
	e.now = func() time.Time { return time.Date(2026, 9, 12, 12, 0, 0, 0, time.UTC) }
	return e
}

func months(n int) time.Time {
	return time.Date(2026, 9, 12, 12, 0, 0, 0, time.UTC).AddDate(0, -n, 0)
}

// telegramBotProject is the example from the product specification: a Telegram
// bot for an online store, Python and PostgreSQL, $500-$800.
func telegramBotProject() ProjectFacts {
	return ProjectFacts{
		CategorySlug:   "telegram-bots",
		RequiredSkills: []string{"python", "telegram-api", "postgresql"},
		OptionalSkills: []string{"redis", "docker"},
		TargetSpecialisations: map[string]float64{
			"telegram-developer":      1.00,
			"backend-developer":       0.65,
			"fullstack-developer":     0.50,
			"ai-automation-developer": 0.35,
		},
		BudgetMinMinor:   50000,
		BudgetMaxMinor:   80000,
		Currency:         "USD",
		BudgetType:       "range",
		DurationDays:     14,
		ExperienceWanted: "mid",
	}
}

// telegramSpecialist is the developer the project is aimed at.
func telegramSpecialist() DeveloperFacts {
	rating := 4.9
	success := 96.0
	onTime := 92.0
	response := 720
	rate := int64(2500)
	years := 6
	return DeveloperFacts{
		UserID:                "dev-telegram",
		PrimarySpecialisation: "telegram-developer",
		Skills: map[string]SkillFact{
			"python":       {Level: "expert", Years: &years, Evidence: []string{"github"}},
			"telegram-api": {Level: "expert", Evidence: []string{"contract"}},
			"postgresql":   {Level: "strong"},
			"redis":        {Level: "working"},
			"docker":       {Level: "working"},
		},
		CompletedProjects: []CompletedFact{
			{CategorySlug: "telegram-bots", Skills: []string{"python", "telegram-api", "postgresql"},
				CompletedAt: months(2), ClientRating: ptrFloat(5.0), ValueMinor: 65000},
			{CategorySlug: "telegram-bots", Skills: []string{"python", "telegram-api"},
				CompletedAt: months(7), ClientRating: ptrFloat(4.8), ValueMinor: 90000},
			{CategorySlug: "backend-development", Skills: []string{"python", "postgresql"},
				CompletedAt: months(11), ClientRating: ptrFloat(5.0), ValueMinor: 180000},
		},
		GitHubConnected:     true,
		GitHubTechnologies:  map[string]float64{"python": 0.95, "telegram-api": 0.9, "postgresql": 0.8},
		GitHubLanguages:     map[string]float64{"python": 0.62, "sql": 0.11},
		Availability:        "available",
		OpenToInvites:       true,
		ExperienceLevel:     "senior",
		YearsExperience:     &years,
		HourlyRateMinor:     &rate,
		RateCurrency:        "USD",
		RatingAvg:           &rating,
		RatingCount:         22,
		ProjectsCompleted:   38,
		SuccessRate:         &success,
		OnTimeRate:          &onTime,
		RepeatClients:       6,
		ResponseTimeSeconds: &response,
		IdentityVerified:    true,
	}
}

// The specification's central requirement: an iOS developer and a React
// designer must not see a Telegram bot project at all.
func TestIrrelevantSpecialisationsAreExcludedNotRanked(t *testing.T) {
	e := fixedEngine()
	project := telegramBotProject()

	for _, spec := range []string{"mobile-developer", "ui-ux-designer", "frontend-developer", "devops-engineer"} {
		d := DeveloperFacts{
			UserID:                "dev-" + spec,
			PrimarySpecialisation: spec,
			// Deliberately excellent on every other axis, to prove that
			// targeting is a gate and not just another weighted input.
			Skills: map[string]SkillFact{
				"python": {Level: "expert"}, "telegram-api": {Level: "expert"},
				"postgresql": {Level: "expert"},
			},
			Availability:      "available",
			OpenToInvites:     true,
			ExperienceLevel:   "lead",
			RatingAvg:         ptrFloat(5.0),
			RatingCount:       50,
			ProjectsCompleted: 60,
			SuccessRate:       ptrFloat(100),
			GitHubConnected:   true,
		}
		score := e.Score(project, d)
		if !score.Excluded {
			t.Errorf("%s was scored %d for a Telegram bot project; it must be excluded",
				spec, score.Total)
		}
		if score.Total != 0 {
			t.Errorf("%s scored %d, want 0", spec, score.Total)
		}
		if score.ExclusionReason == "" {
			t.Errorf("%s was excluded without a reason", spec)
		}
	}
}

func TestSpecialistOutranksAdjacentAndGenericDevelopers(t *testing.T) {
	e := fixedEngine()
	project := telegramBotProject()

	specialist := e.Score(project, telegramSpecialist())

	// A Python backend developer: right stack, wrong specialism.
	backend := telegramSpecialist()
	backend.UserID = "dev-backend"
	backend.PrimarySpecialisation = "backend-developer"
	backend.CompletedProjects = []CompletedFact{
		{CategorySlug: "backend-development", Skills: []string{"python", "postgresql"},
			CompletedAt: months(3), ClientRating: ptrFloat(4.9)},
	}
	backendScore := e.Score(project, backend)

	// A full-stack developer with a thinner match.
	fullstack := DeveloperFacts{
		UserID:                "dev-fullstack",
		PrimarySpecialisation: "fullstack-developer",
		Skills: map[string]SkillFact{
			"python": {Level: "working"}, "postgresql": {Level: "working"},
		},
		Availability:    "limited",
		OpenToInvites:   true,
		ExperienceLevel: "mid",
		GitHubConnected: false,
	}
	fullstackScore := e.Score(project, fullstack)

	if specialist.Total <= backendScore.Total {
		t.Errorf("the Telegram specialist (%d) must outrank the backend developer (%d)",
			specialist.Total, backendScore.Total)
	}
	if backendScore.Total <= fullstackScore.Total {
		t.Errorf("the backend developer (%d) must outrank the thin full-stack match (%d)",
			backendScore.Total, fullstackScore.Total)
	}
	if specialist.Total < 80 {
		t.Errorf("the ideal candidate scored only %d; the scale is miscalibrated", specialist.Total)
	}
	if specialist.Total > 100 {
		t.Errorf("score %d exceeds 100", specialist.Total)
	}
}

// A score with no reasons is decoration. Every score must be expandable into
// the facts that produced it.
func TestEveryScoreCarriesItsReasoning(t *testing.T) {
	e := fixedEngine()
	score := e.Score(telegramBotProject(), telegramSpecialist())

	if len(score.Dimensions) != 6 {
		t.Fatalf("dimensions = %d, want 6", len(score.Dimensions))
	}
	wantKeys := map[string]bool{
		"technical": false, "track_record": false, "github": false,
		"availability": false, "platform_history": false, "budget_fit": false,
	}
	pointsTotal := 0.0
	for _, dim := range score.Dimensions {
		if _, known := wantKeys[dim.Key]; !known {
			t.Errorf("unexpected dimension %q", dim.Key)
		}
		wantKeys[dim.Key] = true
		if dim.Label == "" {
			t.Errorf("dimension %q has no label", dim.Key)
		}
		if len(dim.Reasons) == 0 {
			t.Errorf("dimension %q produced no reasons", dim.Key)
		}
		if dim.Raw < 0 || dim.Raw > 1 {
			t.Errorf("dimension %q raw = %.3f, outside 0-1", dim.Key, dim.Raw)
		}
		pointsTotal += dim.Points
	}
	for key, seen := range wantKeys {
		if !seen {
			t.Errorf("dimension %q is missing", key)
		}
	}
	// The total is never more than its parts: specialisation relevance scales
	// the sum down and can never scale it up. The half-point tolerance is the
	// rounding to a whole percentage.
	if float64(score.Total) > pointsTotal+0.5 {
		t.Errorf("the total (%d) exceeds the sum of the dimensions (%.1f); points are being invented",
			score.Total, pointsTotal)
	}

	// The highlights are what the UI shows under "Why?".
	if len(score.Highlights) == 0 {
		t.Fatal("a score must carry highlights")
	}
	if len(score.Highlights) > 6 {
		t.Errorf("highlights = %d; the UI shows at most 6", len(score.Highlights))
	}
	labels := map[string]bool{}
	for _, r := range score.Highlights {
		if r.Label == "" {
			t.Error("a highlight has no label")
		}
		labels[r.Label] = true
	}
	// The specification's example: Python ✓ Telegram ✓ PostgreSQL ✓
	for _, want := range []string{"Python", "Telegram API", "PostgreSQL"} {
		if !labels[want] {
			t.Errorf("expected %q among the highlights, got %v", want, keysOf(labels))
		}
	}
}

// Highlights must show the gap as well as the strengths, or a client comparing
// developers is being sold to rather than informed.
func TestHighlightsIncludeTheMostSignificantGap(t *testing.T) {
	e := fixedEngine()
	project := telegramBotProject()

	d := telegramSpecialist()
	delete(d.Skills, "postgresql")
	delete(d.GitHubTechnologies, "postgresql")

	score := e.Score(project, d)
	foundUnmet := false
	for _, r := range score.Highlights {
		if !r.Met {
			foundUnmet = true
			if r.Label != "PostgreSQL" {
				t.Errorf("the surfaced gap is %q; PostgreSQL is the missing requirement", r.Label)
			}
		}
	}
	if !foundUnmet {
		t.Error("a developer missing a required technology must have the gap in their highlights")
	}
}

// Determinism: the same inputs must always produce the same number. This is
// the test that fails if anyone reaches for a random component.
func TestScoringIsDeterministic(t *testing.T) {
	e := fixedEngine()
	project := telegramBotProject()
	dev := telegramSpecialist()

	first := e.Score(project, dev)
	for i := 0; i < 50; i++ {
		again := e.Score(project, dev)
		if again.Total != first.Total {
			t.Fatalf("run %d scored %d, first run scored %d — the engine is not deterministic",
				i, again.Total, first.Total)
		}
	}
	// And across engine instances built from the same weights.
	other := fixedEngine()
	if other.Score(project, dev).Total != first.Total {
		t.Error("a fresh engine with the same weights produced a different score")
	}
}

func TestMissingRequirementsLowerTheTechnicalDimension(t *testing.T) {
	e := fixedEngine()
	project := telegramBotProject()

	full := e.Score(project, telegramSpecialist())

	partial := telegramSpecialist()
	delete(partial.Skills, "telegram-api")
	delete(partial.GitHubTechnologies, "telegram-api")
	partialScore := e.Score(project, partial)

	none := telegramSpecialist()
	none.Skills = map[string]SkillFact{}
	none.GitHubTechnologies = map[string]float64{}
	none.GitHubLanguages = map[string]float64{}
	noneScore := e.Score(project, none)

	if partialScore.Total >= full.Total {
		t.Errorf("missing a requirement must lower the score: %d vs %d", partialScore.Total, full.Total)
	}
	if noneScore.Total >= partialScore.Total {
		t.Errorf("missing every requirement must score lower still: %d vs %d",
			noneScore.Total, partialScore.Total)
	}
	if dimension(noneScore, "technical").Raw != 0 {
		t.Errorf("technical raw = %.3f with no matching technologies, want 0",
			dimension(noneScore, "technical").Raw)
	}
}

// Corroborated skills must count for more than self-declared ones, or the
// declaration is worth as much as the evidence.
func TestCorroboratedSkillsScoreHigherThanSelfDeclared(t *testing.T) {
	e := fixedEngine()
	project := telegramBotProject()

	declared := telegramSpecialist()
	for slug, fact := range declared.Skills {
		fact.Evidence = nil
		declared.Skills[slug] = fact
	}
	declared.GitHubTechnologies = map[string]float64{}
	declared.GitHubConnected = false

	corroborated := telegramSpecialist()

	if e.Score(project, corroborated).Total <= e.Score(project, declared).Total {
		t.Error("evidence from GitHub and completed contracts must outweigh a bare self-declaration")
	}
}

// The specification is explicit: code share is never converted into a
// competence rating. Language share alone must stay a weak signal.
func TestLanguageShareAloneIsAWeakSignal(t *testing.T) {
	e := fixedEngine()
	project := ProjectFacts{
		CategorySlug:          "backend-development",
		RequiredSkills:        []string{"go"},
		TargetSpecialisations: map[string]float64{"backend-developer": 1.0},
	}

	// 97% Go in their public code, but nothing declared and no manifest.
	languageOnly := DeveloperFacts{
		UserID:                "dev-language-only",
		PrimarySpecialisation: "backend-developer",
		GitHubConnected:       true,
		GitHubLanguages:       map[string]float64{"go": 0.97},
		Availability:          "available",
		OpenToInvites:         true,
	}
	// A go.mod entry: actual evidence of use.
	manifest := languageOnly
	manifest.UserID = "dev-manifest"
	manifest.GitHubTechnologies = map[string]float64{"go": 0.9}

	languageDim := dimension(e.Score(project, languageOnly), "github")
	manifestDim := dimension(e.Score(project, manifest), "github")

	if languageDim.Raw > 0.55 {
		t.Errorf("github raw from language share alone = %.2f; 97%% Go code must not read as near-certainty",
			languageDim.Raw)
	}
	if manifestDim.Raw <= languageDim.Raw {
		t.Errorf("a go.mod entry (%.2f) must count for more than language share (%.2f)",
			manifestDim.Raw, languageDim.Raw)
	}
	// The wording shown to a user must describe code, not knowledge.
	for _, r := range languageDim.Reasons {
		if r.Detail != "" && !contains(r.Detail, "code") {
			t.Errorf("language-share reason reads %q; it must describe code share", r.Detail)
		}
	}
}

func TestRecentWorkCountsForMoreThanOldWork(t *testing.T) {
	e := fixedEngine()
	project := telegramBotProject()

	recent := telegramSpecialist()
	recent.CompletedProjects = []CompletedFact{
		{CategorySlug: "telegram-bots", Skills: []string{"python", "telegram-api", "postgresql"},
			CompletedAt: months(2), ClientRating: ptrFloat(5.0)},
	}
	old := telegramSpecialist()
	old.CompletedProjects = []CompletedFact{
		{CategorySlug: "telegram-bots", Skills: []string{"python", "telegram-api", "postgresql"},
			CompletedAt: months(48), ClientRating: ptrFloat(5.0)},
	}

	recentDim := dimension(e.Score(project, recent), "track_record")
	oldDim := dimension(e.Score(project, old), "track_record")
	if recentDim.Raw <= oldDim.Raw {
		t.Errorf("recent work (%.3f) must count for more than four-year-old work (%.3f)",
			recentDim.Raw, oldDim.Raw)
	}
}

// A newcomer must be visible. A marketplace whose matcher buries everyone
// without history never acquires anyone with history.
func TestNewDeveloperIsNotBuried(t *testing.T) {
	e := fixedEngine()
	project := telegramBotProject()

	years := 5
	rate := int64(2000)
	newcomer := DeveloperFacts{
		UserID:                "dev-new",
		PrimarySpecialisation: "telegram-developer",
		Skills: map[string]SkillFact{
			"python":       {Level: "expert", Years: &years, Evidence: []string{"github"}},
			"telegram-api": {Level: "strong", Evidence: []string{"github"}},
			"postgresql":   {Level: "strong"},
			"redis":        {Level: "working"},
		},
		GitHubConnected:    true,
		GitHubTechnologies: map[string]float64{"python": 0.9, "telegram-api": 0.85, "postgresql": 0.7},
		Availability:       "available",
		OpenToInvites:      true,
		ExperienceLevel:    "senior",
		HourlyRateMinor:    &rate,
		RateCurrency:       "USD",
		IdentityVerified:   true,
	}

	score := e.Score(project, newcomer)
	if score.Total < DefaultWeights().FeedThreshold {
		t.Errorf("a strong newcomer scored %d, below the feed threshold of %d — they would never be seen",
			score.Total, DefaultWeights().FeedThreshold)
	}
	history := dimension(score, "platform_history")
	if history.Raw < 0.5 {
		t.Errorf("platform history raw = %.2f for a newcomer; the benefit of the doubt is 0.5 or above",
			history.Raw)
	}
	// And it must be labelled honestly rather than presented as a track record.
	labelled := false
	for _, r := range history.Reasons {
		if contains(r.Label, "New to AVERIX") {
			labelled = true
		}
	}
	if !labelled {
		t.Error("a newcomer's lack of history must be stated, not hidden behind a neutral score")
	}
}

func TestUnavailableDeveloperScoresLower(t *testing.T) {
	e := fixedEngine()
	project := telegramBotProject()

	states := []struct {
		availability string
		wantRaw      float64
	}{
		{"available", 1.0},
		{"limited", 0.65},
		{"booked", 0.25},
		{"unavailable", 0.0},
	}
	previous := math.Inf(1)
	for _, tc := range states {
		d := telegramSpecialist()
		d.Availability = tc.availability
		dim := dimension(e.Score(project, d), "availability")
		if math.Abs(dim.Raw-tc.wantRaw) > 0.01 {
			t.Errorf("%s availability raw = %.2f, want %.2f", tc.availability, dim.Raw, tc.wantRaw)
		}
		if dim.Raw > previous {
			t.Errorf("%s scored higher than the state above it", tc.availability)
		}
		previous = dim.Raw
	}
}

func TestBudgetMismatchIsSurfaced(t *testing.T) {
	e := fixedEngine()
	project := telegramBotProject() // $500-$800

	// A developer who does not take projects under $5,000.
	tooBig := telegramSpecialist()
	minimum := int64(500000)
	tooBig.MinProjectMinor = &minimum

	dim := dimension(e.Score(project, tooBig), "budget_fit")
	if dim.Raw > 0.2 {
		t.Errorf("budget_fit raw = %.2f when the project is below the developer's minimum", dim.Raw)
	}
	surfaced := false
	for _, r := range dim.Reasons {
		if !r.Met && contains(r.Label, "minimum project size") {
			surfaced = true
		}
	}
	if !surfaced {
		t.Error("a project below the developer's minimum must say so")
	}
}

func TestWeightsAreConfigurable(t *testing.T) {
	project := telegramBotProject()
	dev := telegramSpecialist()
	// Strip the history so the two weightings genuinely disagree.
	dev.CompletedProjects = nil
	dev.RatingAvg = nil
	dev.RatingCount = 0
	dev.ProjectsCompleted = 0
	dev.SuccessRate = nil
	dev.OnTimeRate = nil
	dev.RepeatClients = 0

	technicalHeavy := Weights{
		Version: 2, Technical: 0.70, TrackRecord: 0.05, GitHub: 0.15,
		Availability: 0.05, PlatformHistory: 0.03, BudgetFit: 0.02, FeedThreshold: 35,
	}
	if err := technicalHeavy.Valid(); err != nil {
		t.Fatalf("the test weight set is invalid: %v", err)
	}

	baseline := fixedEngine().Score(project, dev)
	weighted := NewEngine(technicalHeavy)
	weighted.now = fixedEngine().now
	adjusted := weighted.Score(project, dev)

	if adjusted.Total == baseline.Total {
		t.Error("changing the weights must change the score")
	}
	if adjusted.WeightsVersion != 2 {
		t.Errorf("weights_version = %d, want 2 so cached scores can be invalidated",
			adjusted.WeightsVersion)
	}
	// A developer with the stack but no history should do better under a
	// technical-heavy weighting.
	if adjusted.Total <= baseline.Total {
		t.Errorf("under a technical-heavy weighting this developer scored %d, want more than %d",
			adjusted.Total, baseline.Total)
	}
}

func TestInvalidWeightsAreRejected(t *testing.T) {
	cases := []struct {
		name string
		w    Weights
	}{
		{"sum below one", Weights{Technical: 0.5, TrackRecord: 0.2}},
		{"sum above one", Weights{Technical: 0.5, TrackRecord: 0.5, GitHub: 0.5,
			Availability: 0.1, PlatformHistory: 0.1, BudgetFit: 0.1}},
		{"negative weight", Weights{Technical: -0.1, TrackRecord: 0.4, GitHub: 0.2,
			Availability: 0.2, PlatformHistory: 0.2, BudgetFit: 0.1}},
		{"threshold out of range", Weights{Technical: 0.35, TrackRecord: 0.2, GitHub: 0.15,
			Availability: 0.1, PlatformHistory: 0.1, BudgetFit: 0.1, FeedThreshold: 150}},
	}
	for _, tc := range cases {
		if err := tc.w.Valid(); err == nil {
			t.Errorf("%s: invalid weights were accepted", tc.name)
		}
	}
	if err := DefaultWeights().Valid(); err != nil {
		t.Errorf("the default weights are invalid: %v", err)
	}
}

// An untargeted project (a category with no specialisation mapping) must be
// open to everyone rather than to nobody.
func TestUntargetedProjectIsOpenToAll(t *testing.T) {
	e := fixedEngine()
	project := ProjectFacts{
		CategorySlug:   "integrations",
		RequiredSkills: []string{"rest"},
	}
	d := DeveloperFacts{
		UserID:                "dev-any",
		PrimarySpecialisation: "ui-ux-designer",
		Skills:                map[string]SkillFact{"rest": {Level: "working"}},
		Availability:          "available",
		OpenToInvites:         true,
	}
	score := e.Score(project, d)
	if score.Excluded {
		t.Error("a project with no targeting must not exclude anyone")
	}
	if score.Total == 0 {
		t.Error("a project with no targeting should still produce a score")
	}
}

// The score and its reasoning are serialised into the proposal snapshot and
// into the API response, so the shape has to survive a round trip.
func TestScoreSerialisesForStorageAndDisplay(t *testing.T) {
	score := fixedEngine().Score(telegramBotProject(), telegramSpecialist())

	raw, err := json.Marshal(score)
	if err != nil {
		t.Fatalf("marshal score: %v", err)
	}
	var back Score
	if err := json.Unmarshal(raw, &back); err != nil {
		t.Fatalf("unmarshal score: %v", err)
	}
	if back.Total != score.Total {
		t.Errorf("total did not survive the round trip: %d vs %d", back.Total, score.Total)
	}
	if len(back.Dimensions) != len(score.Dimensions) {
		t.Errorf("dimensions did not survive: %d vs %d", len(back.Dimensions), len(score.Dimensions))
	}
	if len(back.Highlights) != len(score.Highlights) {
		t.Errorf("highlights did not survive: %d vs %d", len(back.Highlights), len(score.Highlights))
	}
	for _, dim := range back.Dimensions {
		if len(dim.Reasons) == 0 {
			t.Errorf("dimension %q lost its reasons in serialisation", dim.Key)
		}
	}
}

func TestSkillLabelsAreReadable(t *testing.T) {
	cases := map[string]string{
		"postgresql":         "PostgreSQL",
		"nextjs":             "Next.js",
		"telegram-api":       "Telegram API",
		"telegram-mini-apps": "Telegram Mini Apps",
		"csharp":             "C#",
		"spring-boot":        "Spring Boot",
		"react-native":       "React Native",
		"graphql":            "GraphQL",
		"go":                 "Go",
		"python":             "Python",
		"docker":             "Docker",
		"github-actions":     "GitHub Actions",
	}
	for slug, want := range cases {
		if got := skillLabel(slug); got != want {
			t.Errorf("skillLabel(%q) = %q, want %q", slug, got, want)
		}
	}
}

func dimension(s Score, key string) Dimension {
	for _, d := range s.Dimensions {
		if d.Key == key {
			return d
		}
	}
	return Dimension{}
}

func ptrFloat(v float64) *float64 { return &v }

func contains(haystack, needle string) bool {
	return len(needle) <= len(haystack) && indexOf(haystack, needle) >= 0
}

func indexOf(s, sub string) int {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}

func keysOf(m map[string]bool) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}
