package matching

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/database"
)

type Store struct{ db *database.DB }

func NewStore(db *database.DB) *Store { return &Store{db: db} }

// ActiveWeights loads the live weight set, falling back to the launch defaults
// if an administrator has somehow deactivated every set.
func (s *Store) ActiveWeights(ctx context.Context) (Weights, error) {
	var w Weights
	err := s.db.QueryRow(ctx, `
		SELECT version, technical, track_record, github, availability,
		       platform_history, budget_fit, feed_threshold
		FROM matching_weights WHERE is_active`).
		Scan(&w.Version, &w.Technical, &w.TrackRecord, &w.GitHub,
			&w.Availability, &w.PlatformHistory, &w.BudgetFit, &w.FeedThreshold)
	if database.IsNoRows(err) {
		return DefaultWeights(), nil
	}
	if err != nil {
		return DefaultWeights(), fmt.Errorf("load matching weights: %w", err)
	}
	if err := w.Valid(); err != nil {
		// A stored set that fails validation is a configuration bug; refusing
		// to score at all would be worse than falling back.
		return DefaultWeights(), fmt.Errorf("stored weight set %d is invalid: %w", w.Version, err)
	}
	return w, nil
}

// SaveWeights stores a new version and activates it. Previous versions are
// kept, so a change is auditable and revertible.
func (s *Store) SaveWeights(ctx context.Context, w Weights, note string, by uuid.UUID) (int, error) {
	if err := w.Valid(); err != nil {
		return 0, err
	}
	var version int
	err := s.db.InTx(ctx, func(q database.Querier) error {
		if err := q.QueryRow(ctx,
			`SELECT coalesce(max(version), 0) + 1 FROM matching_weights`).Scan(&version); err != nil {
			return fmt.Errorf("allocate weight version: %w", err)
		}
		// The partial unique index allows only one active row.
		if _, err := q.Exec(ctx,
			`UPDATE matching_weights SET is_active = false WHERE is_active`); err != nil {
			return fmt.Errorf("deactivate previous weights: %w", err)
		}
		if _, err := q.Exec(ctx, `
			INSERT INTO matching_weights
			  (version, technical, track_record, github, availability,
			   platform_history, budget_fit, feed_threshold, is_active, note, created_by)
			VALUES ($1,$2,$3,$4,$5,$6,$7,$8,true,$9,$10)`,
			version, w.Technical, w.TrackRecord, w.GitHub, w.Availability,
			w.PlatformHistory, w.BudgetFit, w.FeedThreshold, nullIfBlank(note), nullUUID(by)); err != nil {
			return fmt.Errorf("insert weights: %w", err)
		}
		return nil
	})
	return version, err
}

// WeightHistory lists the versions for the admin panel.
func (s *Store) WeightHistory(ctx context.Context, limit int) ([]map[string]any, error) {
	if limit <= 0 || limit > 100 {
		limit = 20
	}
	rows, err := s.db.Query(ctx, `
		SELECT w.version, w.technical, w.track_record, w.github, w.availability,
		       w.platform_history, w.budget_fit, w.feed_threshold, w.is_active,
		       coalesce(w.note, ''), w.created_at, coalesce(u.username, '')
		FROM matching_weights w
		LEFT JOIN users u ON u.id = w.created_by
		ORDER BY w.version DESC LIMIT $1`, limit)
	if err != nil {
		return nil, fmt.Errorf("query weight history: %w", err)
	}
	defer rows.Close()

	out := []map[string]any{}
	for rows.Next() {
		var w Weights
		var active bool
		var note, author string
		var createdAt time.Time
		if err := rows.Scan(&w.Version, &w.Technical, &w.TrackRecord, &w.GitHub,
			&w.Availability, &w.PlatformHistory, &w.BudgetFit, &w.FeedThreshold,
			&active, &note, &createdAt, &author); err != nil {
			return nil, err
		}
		out = append(out, map[string]any{
			"version": w.Version, "weights": w, "is_active": active,
			"note": note, "created_at": createdAt, "created_by": author,
		})
	}
	return out, rows.Err()
}

// ── Fact loading ────────────────────────────────────────────────────────────

// ProjectFactsByID assembles everything the engine needs about a project.
func (s *Store) ProjectFactsByID(ctx context.Context, projectID uuid.UUID) (ProjectFacts, error) {
	var f ProjectFacts
	var budgetMin, budgetMax *int64
	var duration *int
	var experience *string

	err := s.db.QueryRow(ctx, `
		SELECT c.slug, p.budget_min_minor, p.budget_max_minor, p.currency, p.budget_type,
		       p.duration_days, p.experience_wanted, p.overlap_from_utc, p.overlap_to_utc
		FROM projects p
		JOIN categories c ON c.id = p.category_id
		WHERE p.id = $1`, projectID).
		Scan(&f.CategorySlug, &budgetMin, &budgetMax, &f.Currency, &f.BudgetType,
			&duration, &experience, &f.OverlapFromUTC, &f.OverlapToUTC)
	if err != nil {
		return f, fmt.Errorf("load project facts: %w", err)
	}
	if budgetMin != nil {
		f.BudgetMinMinor = *budgetMin
	}
	if budgetMax != nil {
		f.BudgetMaxMinor = *budgetMax
	}
	if duration != nil {
		f.DurationDays = *duration
	}
	if experience != nil {
		f.ExperienceWanted = *experience
	}

	rows, err := s.db.Query(ctx, `
		SELECT sk.slug, ps.is_required
		FROM project_skills ps JOIN skills sk ON sk.id = ps.skill_id
		WHERE ps.project_id = $1`, projectID)
	if err != nil {
		return f, fmt.Errorf("load project skills: %w", err)
	}
	for rows.Next() {
		var slug string
		var required bool
		if err := rows.Scan(&slug, &required); err != nil {
			rows.Close()
			return f, err
		}
		if required {
			f.RequiredSkills = append(f.RequiredSkills, slug)
		} else {
			f.OptionalSkills = append(f.OptionalSkills, slug)
		}
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return f, err
	}

	// Targeting comes from the project's own rows, which the resolver wrote
	// from the category mapping and the client may have adjusted.
	f.TargetSpecialisations = map[string]float64{}
	rows, err = s.db.Query(ctx, `
		SELECT sp.slug, ps.relevance
		FROM project_specialisations ps
		JOIN specialisations sp ON sp.id = ps.specialisation_id
		WHERE ps.project_id = $1`, projectID)
	if err != nil {
		return f, fmt.Errorf("load project targeting: %w", err)
	}
	defer rows.Close()
	for rows.Next() {
		var slug string
		var relevance float64
		if err := rows.Scan(&slug, &relevance); err != nil {
			return f, err
		}
		f.TargetSpecialisations[slug] = relevance
	}
	return f, rows.Err()
}

// DeveloperFactsByID assembles everything the engine needs about a developer.
func (s *Store) DeveloperFactsByID(ctx context.Context, userID uuid.UUID) (DeveloperFacts, error) {
	f := DeveloperFacts{
		UserID:             userID.String(),
		Skills:             map[string]SkillFact{},
		GitHubTechnologies: map[string]float64{},
		GitHubLanguages:    map[string]float64{},
	}

	var primarySpec *string
	err := s.db.QueryRow(ctx, `
		SELECT sp.slug, d.availability, d.hours_per_week, d.available_from,
		       d.overlap_from_utc, d.overlap_to_utc, d.open_to_invitations,
		       d.experience_level, d.years_experience, d.hourly_rate_minor,
		       d.min_project_minor, d.rate_currency,
		       d.rating_avg, d.rating_count, d.projects_completed,
		       d.success_rate, d.on_time_rate, d.repeat_client_count,
		       d.response_time_seconds, u.identity_verified_at IS NOT NULL
		FROM developer_profiles d
		JOIN users u ON u.id = d.user_id
		LEFT JOIN specialisations sp ON sp.id = d.primary_specialisation_id
		WHERE d.user_id = $1`, userID).
		Scan(&primarySpec, &f.Availability, &f.HoursPerWeek, &f.AvailableFrom,
			&f.OverlapFromUTC, &f.OverlapToUTC, &f.OpenToInvites,
			&nullableString{&f.ExperienceLevel}, &f.YearsExperience, &f.HourlyRateMinor,
			&f.MinProjectMinor, &f.RateCurrency,
			&f.RatingAvg, &f.RatingCount, &f.ProjectsCompleted,
			&f.SuccessRate, &f.OnTimeRate, &f.RepeatClients,
			&f.ResponseTimeSeconds, &f.IdentityVerified)
	if err != nil {
		return f, fmt.Errorf("load developer facts: %w", err)
	}
	if primarySpec != nil {
		f.PrimarySpecialisation = *primarySpec
	}

	rows, err := s.db.Query(ctx,
		`SELECT sp.slug FROM developer_specialisations ds
		 JOIN specialisations sp ON sp.id = ds.specialisation_id
		 WHERE ds.user_id = $1`, userID)
	if err != nil {
		return f, fmt.Errorf("load additional specialisations: %w", err)
	}
	for rows.Next() {
		var slug string
		if err := rows.Scan(&slug); err != nil {
			rows.Close()
			return f, err
		}
		f.AdditionalSpecialisations = append(f.AdditionalSpecialisations, slug)
	}
	rows.Close()

	rows, err = s.db.Query(ctx, `
		SELECT sk.slug, ds.level, ds.years, ds.evidence
		FROM developer_skills ds JOIN skills sk ON sk.id = ds.skill_id
		WHERE ds.user_id = $1`, userID)
	if err != nil {
		return f, fmt.Errorf("load developer skills: %w", err)
	}
	for rows.Next() {
		var slug, level string
		var years *int
		var evidence []string
		if err := rows.Scan(&slug, &level, &years, &evidence); err != nil {
			rows.Close()
			return f, err
		}
		f.Skills[slug] = SkillFact{Level: level, Years: years, Evidence: evidence}
	}
	rows.Close()

	// Only completed AVERIX contracts count as a track record. A self-declared
	// portfolio item is deliberately not loaded here.
	rows, err = s.db.Query(ctx, `
		SELECT coalesce(c.slug, ''), h.client_rating, h.completed_at, h.value_minor,
		       coalesce(array_agg(sk.slug) FILTER (WHERE sk.slug IS NOT NULL), '{}')
		FROM completed_project_history h
		LEFT JOIN categories c ON c.id = h.category_id
		LEFT JOIN completed_project_skills cps ON cps.history_id = h.id
		LEFT JOIN skills sk ON sk.id = cps.skill_id
		WHERE h.developer_id = $1
		GROUP BY h.id, c.slug
		ORDER BY h.completed_at DESC
		LIMIT 50`, userID)
	if err != nil {
		return f, fmt.Errorf("load completed history: %w", err)
	}
	for rows.Next() {
		var done CompletedFact
		if err := rows.Scan(&done.CategorySlug, &done.ClientRating,
			&done.CompletedAt, &done.ValueMinor, &done.Skills); err != nil {
			rows.Close()
			return f, err
		}
		f.CompletedProjects = append(f.CompletedProjects, done)
	}
	rows.Close()

	// GitHub evidence: detected technologies at their best confidence, and the
	// language share from the most recent successful analysis.
	err = s.db.QueryRow(ctx,
		`SELECT true FROM github_accounts WHERE user_id = $1 AND revoked_at IS NULL`,
		userID).Scan(&f.GitHubConnected)
	if err != nil && !database.IsNoRows(err) {
		return f, fmt.Errorf("check github connection: %w", err)
	}

	if f.GitHubConnected {
		rows, err = s.db.Query(ctx, `
			SELECT sk.slug, max(dt.confidence)
			FROM github_detected_technologies dt
			JOIN skills sk ON sk.id = dt.skill_id
			JOIN github_repositories gr ON gr.id = dt.repository_id
			JOIN github_accounts ga ON ga.id = gr.github_account_id
			WHERE ga.user_id = $1 AND ga.revoked_at IS NULL
			  AND dt.source <> 'language-stats'
			GROUP BY sk.slug`, userID)
		if err != nil {
			return f, fmt.Errorf("load detected technologies: %w", err)
		}
		for rows.Next() {
			var slug string
			var confidence float64
			if err := rows.Scan(&slug, &confidence); err != nil {
				rows.Close()
				return f, err
			}
			f.GitHubTechnologies[slug] = confidence
		}
		rows.Close()

		var stats []byte
		err = s.db.QueryRow(ctx, `
			SELECT language_stats FROM github_analysis a
			JOIN github_accounts ga ON ga.id = a.github_account_id
			WHERE ga.user_id = $1 AND a.status IN ('succeeded','partial')
			ORDER BY a.created_at DESC LIMIT 1`, userID).Scan(&stats)
		if err == nil && len(stats) > 0 {
			var parsed []struct {
				Language string  `json:"language"`
				Share    float64 `json:"share"`
			}
			if json.Unmarshal(stats, &parsed) == nil {
				for _, entry := range parsed {
					// Language names are mapped onto skill slugs through the
					// taxonomy's github_aliases, resolved below.
					f.GitHubLanguages[languageSlug(entry.Language)] = entry.Share
				}
			}
		}
	}
	return f, nil
}

// languageSlug maps a GitHub language name onto a taxonomy slug. The common
// cases are handled inline; anything unrecognised is lowercased, which is
// harmless because an unmatched slug simply scores nothing.
func languageSlug(language string) string {
	switch language {
	case "Go":
		return "go"
	case "Python":
		return "python"
	case "TypeScript":
		return "typescript"
	case "JavaScript":
		return "javascript"
	case "PHP":
		return "php"
	case "Java":
		return "java"
	case "Kotlin":
		return "kotlin"
	case "Swift":
		return "swift"
	case "Rust":
		return "rust"
	case "C#":
		return "csharp"
	case "Ruby":
		return "ruby"
	case "Dart":
		return "dart"
	case "Shell", "Shell Script":
		return "bash"
	case "PLpgSQL", "TSQL", "SQL":
		return "sql"
	case "Dockerfile":
		return "docker"
	case "HCL":
		return "terraform"
	case "Svelte":
		return "svelte"
	case "Vue":
		return "vue"
	}
	out := make([]byte, 0, len(language))
	for i := 0; i < len(language); i++ {
		c := language[i]
		switch {
		case c >= 'A' && c <= 'Z':
			out = append(out, c+32)
		case c >= 'a' && c <= 'z', c >= '0' && c <= '9':
			out = append(out, c)
		case c == ' ', c == '_':
			out = append(out, '-')
		}
	}
	return string(out)
}

// ── Score persistence ───────────────────────────────────────────────────────

// SaveScore caches a score. The weights version is stored with it so a weight
// change invalidates by comparison rather than by truncating the table.
func (s *Store) SaveScore(ctx context.Context, projectID, developerID uuid.UUID, score Score) error {
	breakdown, err := json.Marshal(score)
	if err != nil {
		return fmt.Errorf("encode score breakdown: %w", err)
	}
	_, err = s.db.Exec(ctx, `
		INSERT INTO match_scores (project_id, developer_id, score, breakdown, weights_version, computed_at)
		VALUES ($1, $2, $3, $4, $5, now())
		ON CONFLICT (project_id, developer_id) DO UPDATE SET
		  score = excluded.score,
		  breakdown = excluded.breakdown,
		  weights_version = excluded.weights_version,
		  computed_at = now()`,
		projectID, developerID, score.Total, breakdown, score.WeightsVersion)
	if err != nil {
		return fmt.Errorf("save match score: %w", err)
	}
	return nil
}

// CachedScore returns a stored score if it was computed under the current
// weights and is fresh enough.
func (s *Store) CachedScore(ctx context.Context, projectID, developerID uuid.UUID,
	weightsVersion int, maxAge time.Duration) (Score, bool) {

	var raw []byte
	var version int
	var computedAt time.Time
	err := s.db.QueryRow(ctx, `
		SELECT breakdown, weights_version, computed_at
		FROM match_scores WHERE project_id = $1 AND developer_id = $2`,
		projectID, developerID).Scan(&raw, &version, &computedAt)
	if err != nil || version != weightsVersion {
		return Score{}, false
	}
	if maxAge > 0 && time.Since(computedAt) > maxAge {
		return Score{}, false
	}
	var score Score
	if err := json.Unmarshal(raw, &score); err != nil {
		return Score{}, false
	}
	return score, true
}

// InvalidateForDeveloper drops a developer's cached scores, called when their
// profile, skills or GitHub analysis change.
func (s *Store) InvalidateForDeveloper(ctx context.Context, developerID uuid.UUID) error {
	_, err := s.db.Exec(ctx, `DELETE FROM match_scores WHERE developer_id = $1`, developerID)
	return err
}

// InvalidateForProject drops a project's cached scores, called when its
// requirements change.
func (s *Store) InvalidateForProject(ctx context.Context, projectID uuid.UUID) error {
	_, err := s.db.Exec(ctx, `DELETE FROM match_scores WHERE project_id = $1`, projectID)
	return err
}

// nullableString scans a nullable text column into a plain string, treating
// NULL as the empty string.
type nullableString struct{ dst *string }

func (n *nullableString) Scan(src any) error {
	switch v := src.(type) {
	case nil:
		*n.dst = ""
	case string:
		*n.dst = v
	case []byte:
		*n.dst = string(v)
	default:
		return fmt.Errorf("cannot scan %T into a string", src)
	}
	return nil
}

func nullIfBlank(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func nullUUID(id uuid.UUID) any {
	if id == uuid.Nil {
		return nil
	}
	return id
}
