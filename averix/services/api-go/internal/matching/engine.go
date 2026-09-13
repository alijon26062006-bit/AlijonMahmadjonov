// Package matching scores how well a developer fits a project, and explains
// why.
//
// Two rules shape everything here:
//
//  1. No score without reasons. Every dimension returns the facts it judged,
//     so "94% match" can always be expanded into "Python ✓ Telegram ✓
//     PostgreSQL ✓ 3 similar projects ✓ Available ✓". A percentage a user
//     cannot interrogate is decoration.
//
//  2. Nothing is invented. Every input is a fact already in the database — a
//     declared technology, a completed contract, a GitHub manifest, an
//     availability setting. There is no random component and no opaque model.
//
// Weights are configuration, not code: an administrator changes them and the
// change is versioned, so cached scores can be invalidated by comparing
// versions rather than by guessing.
package matching

import (
	"fmt"
	"math"
	"sort"
	"strings"
	"time"

	"github.com/averix/api/internal/platform/money"
)

// Weights is one versioned weight set. They sum to 1.
type Weights struct {
	Version         int     `json:"version"`
	Technical       float64 `json:"technical"`
	TrackRecord     float64 `json:"track_record"`
	GitHub          float64 `json:"github"`
	Availability    float64 `json:"availability"`
	PlatformHistory float64 `json:"platform_history"`
	BudgetFit       float64 `json:"budget_fit"`
	// Below this score a project is not surfaced in a developer's feed at all.
	FeedThreshold int `json:"feed_threshold"`
}

// DefaultWeights are the launch values from the product specification.
func DefaultWeights() Weights {
	return Weights{
		Version:         1,
		Technical:       0.35,
		TrackRecord:     0.20,
		GitHub:          0.15,
		Availability:    0.10,
		PlatformHistory: 0.10,
		BudgetFit:       0.10,
		FeedThreshold:   35,
	}
}

func (w Weights) Sum() float64 {
	return w.Technical + w.TrackRecord + w.GitHub + w.Availability +
		w.PlatformHistory + w.BudgetFit
}

func (w Weights) Valid() error {
	if math.Abs(w.Sum()-1.0) > 0.001 {
		return fmt.Errorf("weights must sum to 1.0, got %.3f", w.Sum())
	}
	for name, v := range map[string]float64{
		"technical": w.Technical, "track_record": w.TrackRecord,
		"github": w.GitHub, "availability": w.Availability,
		"platform_history": w.PlatformHistory, "budget_fit": w.BudgetFit,
	} {
		if v < 0 || v > 1 {
			return fmt.Errorf("weight %s must be between 0 and 1, got %.3f", name, v)
		}
	}
	if w.FeedThreshold < 0 || w.FeedThreshold > 100 {
		return fmt.Errorf("feed threshold must be between 0 and 100, got %d", w.FeedThreshold)
	}
	return nil
}

// ── Inputs ──────────────────────────────────────────────────────────────────

// ProjectFacts is everything the matcher knows about a project.
type ProjectFacts struct {
	CategorySlug string
	// Technologies the client marked as required, and the nice-to-haves.
	RequiredSkills []string
	OptionalSkills []string
	// Specialisations the project targets, with the relevance the taxonomy
	// assigns. This is what excludes an iOS developer from a Telegram bot.
	TargetSpecialisations map[string]float64

	BudgetMinMinor int64
	BudgetMaxMinor int64
	Currency       string
	BudgetType     string

	ExperienceWanted string
	DurationDays     int
	OverlapFromUTC   *int
	OverlapToUTC     *int
}

// DeveloperFacts is everything the matcher knows about a developer.
type DeveloperFacts struct {
	UserID string
	// Declared technologies, lowercased slugs.
	Skills map[string]SkillFact
	// Primary and additional specialisations.
	PrimarySpecialisation     string
	AdditionalSpecialisations []string

	// Completed AVERIX contracts, most recent first. Only these count as a
	// track record — a self-declared portfolio item does not.
	CompletedProjects []CompletedFact

	// Technologies corroborated by GitHub manifests, and the share of code by
	// language. Language share is a weak signal and is treated as one.
	GitHubTechnologies map[string]float64
	GitHubLanguages    map[string]float64
	GitHubConnected    bool

	Availability   string
	HoursPerWeek   *int
	AvailableFrom  *time.Time
	OverlapFromUTC *int
	OverlapToUTC   *int
	OpenToInvites  bool

	ExperienceLevel string
	YearsExperience *int
	HourlyRateMinor *int64
	MinProjectMinor *int64
	RateCurrency    string

	RatingAvg           *float64
	RatingCount         int
	ProjectsCompleted   int
	SuccessRate         *float64
	OnTimeRate          *float64
	RepeatClients       int
	ResponseTimeSeconds *int
	IdentityVerified    bool
}

type SkillFact struct {
	Level string
	Years *int
	// Where the corroboration came from, if any.
	Evidence []string
}

// CompletedFact is one finished AVERIX contract.
type CompletedFact struct {
	CategorySlug string
	Skills       []string
	CompletedAt  time.Time
	ClientRating *float64
	ValueMinor   int64
}

// ── Output ──────────────────────────────────────────────────────────────────

// Score is the result: a number and the reasoning behind it.
type Score struct {
	Total          int         `json:"total"`
	WeightsVersion int         `json:"weights_version"`
	Dimensions     []Dimension `json:"dimensions"`
	// The short list the UI shows under "Why?", already ordered by how much
	// each fact contributed.
	Highlights []Reason `json:"highlights"`
	// Set when the developer is not a plausible fit at all, with the reason.
	Excluded        bool   `json:"excluded,omitempty"`
	ExclusionReason string `json:"exclusion_reason,omitempty"`
}

// Dimension is one weighted component.
type Dimension struct {
	Key    string  `json:"key"`
	Label  string  `json:"label"`
	Weight float64 `json:"weight"`
	// 0-1, before the weight is applied.
	Raw float64 `json:"raw"`
	// The contribution to the total, in points out of 100.
	Points  float64  `json:"points"`
	Reasons []Reason `json:"reasons"`
}

// Reason is one fact the matcher judged, phrased for a person.
type Reason struct {
	Label string `json:"label"`
	Met   bool   `json:"met"`
	// Optional detail, e.g. "3 similar projects".
	Detail string `json:"detail,omitempty"`
	// How much this fact contributed, for ordering the highlights.
	Weight float64 `json:"-"`
}

// ── The engine ──────────────────────────────────────────────────────────────

type Engine struct {
	weights Weights
	now     func() time.Time
}

func NewEngine(w Weights) *Engine {
	return &Engine{weights: w, now: time.Now}
}

// Weights returns the active set, so a caller can record the version it scored
// under.
func (e *Engine) Weights() Weights { return e.weights }

// Score computes the fit.
func (e *Engine) Score(p ProjectFacts, d DeveloperFacts) Score {
	// Targeting is a gate, not a dimension. A project that does not target any
	// of the developer's specialisations is not a weak match, it is the wrong
	// person — and showing it would train developers to ignore the feed.
	relevance, targeted := e.specialisationRelevance(p, d)
	if !targeted {
		return Score{
			Total:           0,
			WeightsVersion:  e.weights.Version,
			Excluded:        true,
			ExclusionReason: "This project is aimed at a different specialisation.",
		}
	}

	dims := []Dimension{
		e.technical(p, d),
		e.trackRecord(p, d),
		e.github(p, d),
		e.availability(p, d),
		e.platformHistory(p, d),
		e.budgetFit(p, d),
	}

	total := 0.0
	for i := range dims {
		dims[i].Points = dims[i].Raw * dims[i].Weight * 100
		total += dims[i].Points
	}

	// Specialisation relevance scales the whole score rather than adding to it:
	// a full-stack developer who is a 0.5 fit for a Telegram project should not
	// out-score a Telegram specialist by being marginally better on every other
	// axis. The floor keeps a genuinely relevant secondary match visible.
	scaled := total * (0.65 + 0.35*relevance)

	score := Score{
		Total:          int(math.Round(math.Min(100, math.Max(0, scaled)))),
		WeightsVersion: e.weights.Version,
		Dimensions:     dims,
	}
	score.Highlights = highlightsFrom(dims)
	return score
}

// specialisationRelevance resolves how relevant this project is to what the
// developer does. The primary specialisation counts fully; an additional one
// counts at 80%, because it is a secondary area by the developer's own account.
func (e *Engine) specialisationRelevance(p ProjectFacts, d DeveloperFacts) (float64, bool) {
	if len(p.TargetSpecialisations) == 0 {
		// An untargeted project (no category mapping) is open to everyone
		// rather than to no one.
		return 1.0, true
	}

	best := 0.0
	if r, ok := p.TargetSpecialisations[d.PrimarySpecialisation]; ok {
		best = r
	}
	for _, slug := range d.AdditionalSpecialisations {
		if r, ok := p.TargetSpecialisations[slug]; ok && r*0.8 > best {
			best = r * 0.8
		}
	}
	return best, best > 0
}

// technical judges the required technologies. This is the heaviest dimension
// because it is the one a client cares about most: a developer who does not
// know the stack cannot do the work, however good their history.
func (e *Engine) technical(p ProjectFacts, d DeveloperFacts) Dimension {
	dim := Dimension{
		Key: "technical", Label: "Совпадение по навыкам", Weight: e.weights.Technical,
	}

	if len(p.RequiredSkills) == 0 && len(p.OptionalSkills) == 0 {
		// Nothing specified: neutral rather than a free full mark.
		dim.Raw = 0.6
		dim.Reasons = []Reason{{Label: "Конкретные навыки не указаны", Met: true}}
		return dim
	}

	// Required technologies carry four fifths of the dimension; the
	// nice-to-haves are the remaining fifth.
	requiredHit, requiredTotal := 0.0, 0.0
	for _, slug := range p.RequiredSkills {
		requiredTotal++
		fact, declared := d.Skills[slug]
		corroborated := false
		if _, fromGitHub := d.GitHubTechnologies[slug]; fromGitHub {
			corroborated = true
		}
		for _, ev := range fact.Evidence {
			if ev != "" {
				corroborated = true
			}
		}

		switch {
		case declared && corroborated:
			// Declared and backed by a manifest or a completed contract.
			requiredHit += 1.0
			dim.Reasons = append(dim.Reasons, Reason{
				Label: skillLabel(slug), Met: true, Detail: "подтверждено", Weight: 1.0,
			})
		case declared:
			requiredHit += levelCredit(fact.Level)
			dim.Reasons = append(dim.Reasons, Reason{
				Label: skillLabel(slug), Met: true, Detail: fact.Level, Weight: levelCredit(fact.Level),
			})
		case corroborated:
			// In their GitHub but not on their profile — real, but the
			// developer has not claimed it, so it counts for less.
			requiredHit += 0.6
			dim.Reasons = append(dim.Reasons, Reason{
				Label: skillLabel(slug), Met: true, Detail: "найдено в GitHub", Weight: 0.6,
			})
		default:
			dim.Reasons = append(dim.Reasons, Reason{Label: skillLabel(slug), Met: false})
		}
	}

	optionalHit, optionalTotal := 0.0, 0.0
	for _, slug := range p.OptionalSkills {
		optionalTotal++
		if fact, ok := d.Skills[slug]; ok {
			optionalHit += levelCredit(fact.Level)
			dim.Reasons = append(dim.Reasons, Reason{
				Label: skillLabel(slug), Met: true, Detail: "желательно", Weight: 0.3,
			})
		}
	}

	switch {
	case requiredTotal > 0 && optionalTotal > 0:
		dim.Raw = 0.8*(requiredHit/requiredTotal) + 0.2*(optionalHit/optionalTotal)
	case requiredTotal > 0:
		dim.Raw = requiredHit / requiredTotal
	default:
		dim.Raw = optionalHit / optionalTotal
	}
	dim.Raw = clamp01(dim.Raw)
	return dim
}

// levelCredit converts a self-declared level into partial credit. Nothing
// reaches 1.0 from a self-declaration alone — that requires corroboration.
func levelCredit(level string) float64 {
	switch level {
	case "expert":
		return 0.95
	case "strong":
		return 0.85
	case "working":
		return 0.7
	case "familiar":
		return 0.45
	}
	return 0.6
}

// trackRecord judges completed AVERIX contracts in the same area. Recency
// matters: work from four years ago says less than work from last quarter.
func (e *Engine) trackRecord(p ProjectFacts, d DeveloperFacts) Dimension {
	dim := Dimension{
		Key: "track_record", Label: "Подходящие завершённые заказы", Weight: e.weights.TrackRecord,
	}

	if len(d.CompletedProjects) == 0 {
		dim.Reasons = []Reason{{Label: "Завершённых заказов на AVERIX пока нет", Met: false}}
		return dim
	}

	required := make(map[string]bool, len(p.RequiredSkills))
	for _, slug := range p.RequiredSkills {
		required[slug] = true
	}

	now := e.now()
	relevant := 0
	sameCategory := 0
	credit := 0.0
	for _, done := range d.CompletedProjects {
		overlap := 0
		for _, slug := range done.Skills {
			if required[slug] {
				overlap++
			}
		}
		categoryMatch := done.CategorySlug == p.CategorySlug
		if overlap == 0 && !categoryMatch {
			continue
		}
		relevant++
		if categoryMatch {
			sameCategory++
		}

		// Each relevant project contributes, weighted by how much of the stack
		// it shared, whether it was the same kind of work, how it was rated,
		// and how recently it finished.
		share := 0.0
		if len(required) > 0 {
			share = float64(overlap) / float64(len(required))
		}
		quality := 0.8
		if done.ClientRating != nil {
			quality = clamp01(*done.ClientRating / 5.0)
		}
		months := now.Sub(done.CompletedAt).Hours() / 24 / 30
		recency := 1.0
		switch {
		case months > 36:
			recency = 0.4
		case months > 18:
			recency = 0.65
		case months > 6:
			recency = 0.85
		}

		weight := 0.5 * share
		if categoryMatch {
			weight += 0.5
		}
		credit += clamp01(weight) * quality * recency
	}

	if relevant == 0 {
		dim.Reasons = []Reason{{
			Label:  "Завершённых работ в этой области нет",
			Met:    false,
			Detail: fmt.Sprintf("%d в других областях", len(d.CompletedProjects)),
		}}
		return dim
	}

	// Three strong relevant projects is treated as a full track record. More
	// than that does not keep raising the score: the difference between three
	// and thirty matters far less to a client than the difference between zero
	// and three.
	dim.Raw = clamp01(credit / 3.0)
	detail := fmt.Sprintf("%d похожих %s", relevant, plural(relevant, "заказ", "заказа", "заказов"))
	if sameCategory > 0 {
		detail += fmt.Sprintf(", из них %d в этой же категории", sameCategory)
	}
	dim.Reasons = append(dim.Reasons, Reason{
		Label: "Подходящие завершённые работы", Met: true, Detail: detail, Weight: dim.Raw,
	})
	return dim
}

// github judges what the developer's public code actually shows.
//
// Manifest evidence (a go.mod entry) is strong; language share is weak and is
// capped accordingly, because 90% Go in a repository of tutorials says less
// than one dependency in a shipped service.
func (e *Engine) github(p ProjectFacts, d DeveloperFacts) Dimension {
	dim := Dimension{Key: "github", Label: "Подтверждение из GitHub", Weight: e.weights.GitHub}

	if !d.GitHubConnected {
		dim.Reasons = []Reason{{Label: "GitHub не подключён", Met: false}}
		return dim
	}
	if len(p.RequiredSkills) == 0 {
		dim.Raw = 0.5
		dim.Reasons = []Reason{{Label: "GitHub подключён", Met: true}}
		return dim
	}

	manifestHits, languageHits := 0.0, 0.0
	for _, slug := range p.RequiredSkills {
		if confidence, ok := d.GitHubTechnologies[slug]; ok {
			manifestHits += clamp01(confidence)
			dim.Reasons = append(dim.Reasons, Reason{
				Label: skillLabel(slug), Met: true, Detail: "в его репозиториях", Weight: 0.8,
			})
			continue
		}
		if share, ok := d.GitHubLanguages[slug]; ok && share > 0.05 {
			// Language share alone caps at 0.5: it is a hint, not proof, and
			// the product never converts code percentage into competence.
			languageHits += math.Min(0.5, share*2)
			dim.Reasons = append(dim.Reasons, Reason{
				Label:  skillLabel(slug),
				Met:    true,
				Detail: fmt.Sprintf("%.0f%% его публичного кода", share*100),
				Weight: 0.4,
			})
		}
	}

	dim.Raw = clamp01((manifestHits + languageHits) / float64(len(p.RequiredSkills)))
	// Connecting GitHub at all is worth something: it is a verified identity
	// and public work, which is more than an unconnected profile offers.
	if dim.Raw < 0.25 {
		dim.Raw = 0.25
		if len(dim.Reasons) == 0 {
			dim.Reasons = []Reason{{Label: "GitHub подключён", Met: true,
				Detail: "совпадающих навыков нет", Weight: 0.25}}
		}
	}
	return dim
}

// availability judges whether the developer can actually start.
func (e *Engine) availability(p ProjectFacts, d DeveloperFacts) Dimension {
	dim := Dimension{Key: "availability", Label: "Доступность", Weight: e.weights.Availability}

	switch d.Availability {
	case "available":
		dim.Raw = 1.0
		dim.Reasons = append(dim.Reasons, Reason{Label: "Свободен для заказов", Met: true, Weight: 1.0})
	case "limited":
		dim.Raw = 0.65
		dim.Reasons = append(dim.Reasons, Reason{Label: "Ограниченная занятость", Met: true, Weight: 0.65})
	case "booked":
		dim.Raw = 0.25
		dim.Reasons = append(dim.Reasons, Reason{Label: "Сейчас занят", Met: false})
	default:
		dim.Raw = 0.0
		dim.Reasons = append(dim.Reasons, Reason{Label: "Не берёт заказы", Met: false})
		return dim
	}

	if !d.OpenToInvites {
		dim.Raw *= 0.8
	}

	// A start date after the project wants to begin is a real problem, so it
	// reduces the dimension rather than being noted and ignored.
	if d.AvailableFrom != nil && d.AvailableFrom.After(e.now().AddDate(0, 0, 30)) {
		dim.Raw *= 0.5
		dim.Reasons = append(dim.Reasons, Reason{
			Label:  "Освободится не раньше чем через месяц",
			Met:    false,
			Detail: formatDate(*d.AvailableFrom),
		})
	}

	// Timezone overlap, when the client asked for one.
	if p.OverlapFromUTC != nil && p.OverlapToUTC != nil &&
		d.OverlapFromUTC != nil && d.OverlapToUTC != nil {
		overlap := min(*p.OverlapToUTC, *d.OverlapToUTC) - max(*p.OverlapFromUTC, *d.OverlapFromUTC)
		switch {
		case overlap >= 4:
			dim.Reasons = append(dim.Reasons, Reason{
				Label: "Пересечение рабочих часов", Met: true,
				Detail: fmt.Sprintf("%d %s", overlap, plural(overlap, "час", "часа", "часов")), Weight: 0.5,
			})
		case overlap > 0:
			dim.Raw *= 0.9
			dim.Reasons = append(dim.Reasons, Reason{
				Label: "Рабочие часы пересекаются мало", Met: true,
				Detail: fmt.Sprintf("%d %s", overlap, plural(overlap, "час", "часа", "часов")),
			})
		default:
			dim.Raw *= 0.7
			dim.Reasons = append(dim.Reasons, Reason{Label: "Рабочие часы не пересекаются", Met: false})
		}
	}

	dim.Raw = clamp01(dim.Raw)
	return dim
}

// platformHistory judges reliability on AVERIX itself: ratings, success rate,
// punctuality, repeat clients.
func (e *Engine) platformHistory(p ProjectFacts, d DeveloperFacts) Dimension {
	dim := Dimension{
		Key: "platform_history", Label: "История работ на AVERIX", Weight: e.weights.PlatformHistory,
	}

	if d.RatingCount == 0 && d.ProjectsCompleted == 0 {
		// A new developer is not penalised into invisibility: they are given
		// the benefit of the doubt, clearly labelled, because a marketplace
		// that never surfaces newcomers has no newcomers.
		dim.Raw = 0.5
		dim.Reasons = []Reason{{Label: "Новичок на AVERIX", Met: true, Detail: "истории пока нет"}}
		if d.IdentityVerified {
			dim.Raw = 0.6
			dim.Reasons = append(dim.Reasons, Reason{Label: "Личность подтверждена", Met: true, Weight: 0.3})
		}
		return dim
	}

	components := 0.0
	weightSum := 0.0

	if d.RatingAvg != nil && d.RatingCount > 0 {
		// Confidence grows with the number of reviews: one five-star review is
		// not the same evidence as twenty.
		confidence := math.Min(1.0, float64(d.RatingCount)/8.0)
		normalised := clamp01((*d.RatingAvg - 1) / 4)
		components += (0.5 + 0.5*confidence) * normalised * 0.45
		weightSum += 0.45
		dim.Reasons = append(dim.Reasons, Reason{
			Label:  "Оценки заказчиков",
			Met:    *d.RatingAvg >= 4.0,
			Detail: fmt.Sprintf("%.1f по %d %s", *d.RatingAvg, d.RatingCount, plural(d.RatingCount, "отзыву", "отзывам", "отзывам")),
			Weight: normalised,
		})
	}
	if d.SuccessRate != nil {
		components += clamp01(*d.SuccessRate/100) * 0.25
		weightSum += 0.25
		dim.Reasons = append(dim.Reasons, Reason{
			Label:  "Доля успешных заказов",
			Met:    *d.SuccessRate >= 85,
			Detail: fmt.Sprintf("%.0f%%", *d.SuccessRate),
			Weight: clamp01(*d.SuccessRate / 100),
		})
	}
	if d.OnTimeRate != nil {
		components += clamp01(*d.OnTimeRate/100) * 0.2
		weightSum += 0.2
		dim.Reasons = append(dim.Reasons, Reason{
			Label:  "Сдаёт в срок",
			Met:    *d.OnTimeRate >= 80,
			Detail: fmt.Sprintf("%.0f%%", *d.OnTimeRate),
		})
	}
	if d.RepeatClients > 0 {
		components += math.Min(1.0, float64(d.RepeatClients)/3.0) * 0.1
		weightSum += 0.1
		dim.Reasons = append(dim.Reasons, Reason{
			Label:  "Заказчики, нанявшие повторно",
			Met:    true,
			Detail: fmt.Sprintf("%d", d.RepeatClients),
			Weight: 0.6,
		})
	}

	if weightSum > 0 {
		dim.Raw = clamp01(components / weightSum)
	} else {
		dim.Raw = 0.5
	}

	if d.ResponseTimeSeconds != nil && *d.ResponseTimeSeconds <= 3600 {
		dim.Reasons = append(dim.Reasons, Reason{
			Label:  "Быстро отвечает",
			Met:    true,
			Detail: humaniseDuration(*d.ResponseTimeSeconds),
			Weight: 0.4,
		})
	}
	return dim
}

// budgetFit judges whether the money works for both sides. A mismatch here is
// the most common reason a proposal goes nowhere, so it is worth scoring rather
// than discovering after a conversation.
func (e *Engine) budgetFit(p ProjectFacts, d DeveloperFacts) Dimension {
	dim := Dimension{Key: "budget_fit", Label: "Бюджет и пожелания", Weight: e.weights.BudgetFit}

	// Experience level is part of "client preferences".
	experienceOK := true
	if p.ExperienceWanted != "" && p.ExperienceWanted != "any" && d.ExperienceLevel != "" {
		wanted := experienceRank(p.ExperienceWanted)
		have := experienceRank(d.ExperienceLevel)
		switch {
		case have >= wanted:
			dim.Reasons = append(dim.Reasons, Reason{
				Label: "Уровень опыта", Met: true,
				Detail: capitalise(d.ExperienceLevel), Weight: 0.5,
			})
		case wanted-have == 1:
			experienceOK = false
			dim.Reasons = append(dim.Reasons, Reason{
				Label: "Немного ниже требуемого уровня опыта", Met: false,
			})
		default:
			experienceOK = false
			dim.Reasons = append(dim.Reasons, Reason{
				Label:  "Ниже требуемого уровня опыта",
				Met:    false,
				Detail: fmt.Sprintf("требуется уровень: %s", experienceLabel(p.ExperienceWanted)),
			})
		}
	}

	budgetScore := 0.7
	if p.BudgetMaxMinor > 0 {
		switch {
		case d.MinProjectMinor != nil && *d.MinProjectMinor > p.BudgetMaxMinor:
			// The developer has said they do not take work this small. This is
			// a hard mismatch, not a soft preference.
			budgetScore = 0.05
			dim.Reasons = append(dim.Reasons, Reason{
				Label:  "Меньше его минимального заказа",
				Met:    false,
				Detail: formatMoney(*d.MinProjectMinor, d.RateCurrency),
			})
		case d.HourlyRateMinor != nil:
			// The matcher does not estimate effort. Nobody — not the client,
			// not the developer, and certainly not this function — knows how
			// many hours a brief will take, and multiplying a rate by calendar
			// days produced a number that was confidently wrong.
			//
			// What can be judged is whether the budget could fund a serious
			// engagement at this developer's rate at all. Below a day's work
			// the two sides are not in the same conversation; below a week's
			// it is tight and worth flagging; above that the money is a matter
			// for the proposal, not the matcher.
			const hoursForADay, hoursForAWeek = 8, 25
			switch {
			case p.BudgetMaxMinor < *d.HourlyRateMinor*hoursForADay:
				budgetScore = 0.2
				dim.Reasons = append(dim.Reasons, Reason{
					Label:  "Бюджета не хватает даже на день его работы",
					Met:    false,
					Detail: formatMoney(*d.HourlyRateMinor, d.RateCurrency) + " в час",
				})
			case p.BudgetMaxMinor < *d.HourlyRateMinor*hoursForAWeek:
				budgetScore = 0.6
				dim.Reasons = append(dim.Reasons, Reason{
					Label:  "Бюджет для его ставки тесноват",
					Met:    true,
					Detail: formatMoney(*d.HourlyRateMinor, d.RateCurrency) + " в час",
					Weight: 0.3,
				})
			default:
				budgetScore = 1.0
				dim.Reasons = append(dim.Reasons, Reason{
					Label:  "Бюджет соответствует его ставке",
					Met:    true,
					Detail: formatMoney(*d.HourlyRateMinor, d.RateCurrency) + " в час",
					Weight: 0.7,
				})
			}
		default:
			budgetScore = 0.8
		}
	}

	if !experienceOK {
		budgetScore *= 0.7
	}
	if len(dim.Reasons) == 0 {
		dim.Reasons = append(dim.Reasons, Reason{Label: "Бюджет вопросов не вызывает", Met: true})
	}
	dim.Raw = clamp01(budgetScore)
	return dim
}

// highlightsFrom picks the facts worth showing under "Why?".
//
// Met facts come first, ordered by contribution, then the most significant
// unmet one — a client deciding between developers needs to see the gap, not
// only the strengths.
func highlightsFrom(dims []Dimension) []Reason {
	var met, unmet []Reason
	for _, dim := range dims {
		for _, reason := range dim.Reasons {
			reason.Weight *= dim.Weight
			if reason.Met {
				met = append(met, reason)
			} else {
				unmet = append(unmet, reason)
			}
		}
	}
	sort.SliceStable(met, func(i, j int) bool { return met[i].Weight > met[j].Weight })
	sort.SliceStable(unmet, func(i, j int) bool { return unmet[i].Weight > unmet[j].Weight })

	const maxHighlights = 6
	out := make([]Reason, 0, maxHighlights)
	for _, r := range met {
		if len(out) >= maxHighlights-1 {
			break
		}
		out = append(out, r)
	}
	if len(unmet) > 0 && len(out) < maxHighlights {
		out = append(out, unmet[0])
	}
	return out
}

// capitalise upper-cases the first rune. strings.Title is deprecated and
// would also capitalise every word, which is wrong for a single label.
func capitalise(s string) string {
	if s == "" {
		return s
	}
	return strings.ToUpper(s[:1]) + s[1:]
}

func experienceRank(level string) int {
	switch level {
	case "junior":
		return 1
	case "mid":
		return 2
	case "senior":
		return 3
	case "lead":
		return 4
	}
	return 0
}

func clamp01(v float64) float64 {
	if v < 0 {
		return 0
	}
	if v > 1 {
		return 1
	}
	return v
}

// skillLabel turns a slug into something readable when the caller has not
// supplied a display name.
func skillLabel(slug string) string {
	switch slug {
	case "postgresql":
		return "PostgreSQL"
	case "mysql":
		return "MySQL"
	case "nextjs":
		return "Next.js"
	case "nodejs":
		return "Node.js"
	case "telegram-api":
		return "Telegram API"
	case "telegram-mini-apps":
		return "Telegram Mini Apps"
	case "csharp":
		return "C#"
	case "aspnet-core":
		return "ASP.NET Core"
	case "spring-boot":
		return "Spring Boot"
	case "react-native":
		return "React Native"
	case "graphql":
		return "GraphQL"
	case "grpc":
		return "gRPC"
	case "rest":
		return "REST"
	case "oauth2":
		return "OAuth 2.0"
	case "ci-cd":
		return "CI/CD"
	case "github-actions":
		return "GitHub Actions"
	case "gitlab-ci":
		return "GitLab CI"
	case "aws":
		return "AWS"
	case "gcp":
		return "Google Cloud"
	case "s3":
		return "S3"
	case "sql":
		return "SQL"
	case "openai-api":
		return "OpenAI API"
	case "anthropic-api":
		return "Anthropic API"
	case "opencv":
		return "OpenCV"
	case "pytorch":
		return "PyTorch"
	case "ui-ux":
		return "UI/UX"
	}
	parts := strings.Split(slug, "-")
	for i, part := range parts {
		if part == "" {
			continue
		}
		parts[i] = strings.ToUpper(part[:1]) + part[1:]
	}
	return strings.Join(parts, " ")
}

// plural picks the Russian form for a count: 1 отзыв, 2 отзыва, 5 отзывов.
func plural(n int, one, few, many string) string {
	mod100 := n % 100
	if mod100 > 10 && mod100 < 20 {
		return many
	}
	switch n % 10 {
	case 1:
		return one
	case 2, 3, 4:
		return few
	default:
		return many
	}
}

// formatDate writes a date the way it is read aloud in Russian.
func formatDate(t time.Time) string {
	months := [...]string{"января", "февраля", "марта", "апреля", "мая", "июня",
		"июля", "августа", "сентября", "октября", "ноября", "декабря"}
	return fmt.Sprintf("%d %s %d", t.Day(), months[int(t.Month())-1], t.Year())
}

// experienceLabel names an experience level for a person rather than a column.
func experienceLabel(level string) string {
	switch level {
	case "junior":
		return "начинающий"
	case "mid":
		return "уверенный"
	case "senior":
		return "опытный"
	case "lead":
		return "эксперт"
	case "any", "":
		return "любой"
	default:
		return level
	}
}

func humaniseDuration(seconds int) string {
	switch {
	case seconds < 60:
		return "меньше минуты"
	case seconds < 3600:
		return fmt.Sprintf("%d мин", seconds/60)
	case seconds < 86400:
		n := seconds / 3600
		return fmt.Sprintf("%d %s", n, plural(n, "час", "часа", "часов"))
	default:
		n := seconds / 86400
		return fmt.Sprintf("%d %s", n, plural(n, "день", "дня", "дней"))
	}
}

func formatMoney(minor int64, currency string) string {
	return money.Format(minor, currency)
}
