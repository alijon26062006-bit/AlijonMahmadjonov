package developers

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/database"
)

type Store struct {
	db *database.DB
	// publicURL turns a storage key into a servable URL. Held here so the
	// profile loaders can shape a photo set without every caller passing it.
	publicURL func(string) string
}

func NewStore(db *database.DB, publicURL func(string) string) *Store {
	if publicURL == nil {
		publicURL = func(key string) string { return key }
	}
	return &Store{db: db, publicURL: publicURL}
}

var (
	ErrNotFound = errors.New("developer not found")
	// ErrTooManySpecialisations and ErrTooManySkills surface the database's cap
	// triggers as domain errors, so the HTTP layer returns a field-level
	// message rather than a 500.
	ErrTooManySpecialisations = errors.New("a developer may hold at most 3 additional specialisations")
	ErrTooManySkills          = errors.New("a developer may list at most 15 primary technologies")
)

// profileRow is the wide row both the private and public loaders read. Keeping
// one query means the two views can never disagree about the underlying data —
// only about what they expose.
const profileSelect = `
	SELECT
	  u.id, u.username, u.full_name, u.email, u.country_code, u.city, u.timezone,
	  u.identity_verified_at IS NOT NULL, u.email_verified_at IS NOT NULL,
	  u.last_seen_at, u.created_at,
	  sp.slug, sp.name, sp.short_name,
	  d.professional_title, d.bio, d.experience_level, d.years_experience,
	  d.hourly_rate_minor, d.min_project_minor, d.rate_currency,
	  d.availability, d.hours_per_week, d.available_from,
	  d.overlap_from_utc, d.overlap_to_utc,
	  d.show_location, d.show_hourly_rate, d.open_to_invitations,
	  d.rating_avg, d.rating_count, d.rating_quality, d.rating_communication,
	  d.rating_technical, d.rating_deadline,
	  d.projects_completed, d.success_rate, d.on_time_rate, d.repeat_client_count,
	  d.response_time_seconds, d.total_earned_minor, d.earnings_currency,
	  d.onboarding_step, d.onboarding_completed_at, d.profile_completeness,
	  d.seller_level, d.is_searchable, d.is_featured, d.moderation_state
	FROM users u
	JOIN developer_profiles d ON d.user_id = u.id
	LEFT JOIN specialisations sp ON sp.id = d.primary_specialisation_id
	WHERE u.deleted_at IS NULL`

type profileRow struct {
	Profile
	// Raw nullable columns that need shaping before they reach the model.
	primarySlug, primaryName, primaryShort *string
	availableFrom                          *time.Time
}

func (s *Store) scanProfile(ctx context.Context, where string, arg any) (*Profile, error) {
	row := s.db.QueryRow(ctx, profileSelect+" AND "+where, arg)

	var p Profile
	var (
		email                                  string
		country, city, tz                      *string
		title, bio, expLevel                   *string
		primarySlug, primaryName, primaryShort *string
		completedAt                            *time.Time
		availableFrom                          *time.Time
		earnedMinor                            int64
		earningsCur                            string
	)
	err := row.Scan(
		&p.UserID, &p.Username, &p.FullName, &email, &country, &city, &tz,
		&p.IdentityVerified, &p.EmailVerified, &p.LastSeenAt, &p.MemberSince,
		&primarySlug, &primaryName, &primaryShort,
		&title, &bio, &expLevel, &p.YearsExperience,
		&p.HourlyRateMinor, &p.MinProjectMinor, &p.RateCurrency,
		&p.Availability, &p.HoursPerWeek, &availableFrom,
		&p.OverlapFromUTC, &p.OverlapToUTC,
		&p.ShowLocation, &p.ShowHourlyRate, &p.OpenToInvitations,
		&p.Reputation.RatingAvg, &p.Reputation.RatingCount,
		&p.Reputation.RatingQuality, &p.Reputation.RatingCommunication,
		&p.Reputation.RatingTechnical, &p.Reputation.RatingDeadline,
		&p.Reputation.ProjectsCompleted, &p.Reputation.SuccessRate,
		&p.Reputation.OnTimeRate, &p.Reputation.RepeatClients,
		&p.Reputation.ResponseTimeSeconds, &earnedMinor, &earningsCur,
		&p.Onboarding.Step, &completedAt, &p.Onboarding.Completeness,
		&p.SellerLevel, &p.IsSearchable, &p.IsFeatured, &p.ModerationState,
	)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("scan developer profile: %w", err)
	}

	p.Email = email
	p.CountryCode = deref(country)
	p.City = deref(city)
	p.Timezone = deref(tz)
	p.ProfessionalTitle = deref(title)
	p.Bio = deref(bio)
	p.ExperienceLevel = deref(expLevel)
	p.AvailableFrom = availableFrom
	if primarySlug != nil {
		p.PrimarySpecialisation = &SpecialisationRef{
			Slug: *primarySlug, Name: deref(primaryName), ShortName: deref(primaryShort),
		}
	}
	p.Onboarding.TotalSteps = TotalOnboardingSteps
	p.Onboarding.CompletedAt = completedAt
	p.Onboarding.Completed = completedAt != nil
	p.Earnings = &Earnings{TotalEarnedMinor: earnedMinor, Currency: earningsCur}

	// The related collections are separate queries rather than a wide join with
	// array_agg: three small indexed lookups are faster than one query that
	// multiplies rows, and they keep the scan readable.
	if p.AdditionalSpecialisations, err = s.additionalSpecialisations(ctx, p.UserID); err != nil {
		return nil, err
	}
	if p.Skills, err = s.skills(ctx, p.UserID); err != nil {
		return nil, err
	}
	if p.Languages, err = s.languages(ctx, p.UserID); err != nil {
		return nil, err
	}
	if p.Photo, err = s.Photo(ctx, p.UserID, s.publicURL); err != nil {
		return nil, err
	}
	return &p, nil
}

// ByID loads a profile by user id.
func (s *Store) ByID(ctx context.Context, id uuid.UUID) (*Profile, error) {
	return s.scanProfile(ctx, "u.id = $1", id)
}

// ByUsername loads a profile by handle, which is what the public URL uses.
func (s *Store) ByUsername(ctx context.Context, username string) (*Profile, error) {
	return s.scanProfile(ctx, "u.username = $1", strings.ToLower(strings.TrimSpace(username)))
}

func (s *Store) additionalSpecialisations(ctx context.Context, userID uuid.UUID) ([]SpecialisationRef, error) {
	rows, err := s.db.Query(ctx, `
		SELECT sp.slug, sp.name, sp.short_name
		FROM developer_specialisations ds
		JOIN specialisations sp ON sp.id = ds.specialisation_id
		WHERE ds.user_id = $1 AND sp.is_active
		ORDER BY sp.sort_order`, userID)
	if err != nil {
		return nil, fmt.Errorf("query additional specialisations: %w", err)
	}
	defer rows.Close()

	out := []SpecialisationRef{}
	for rows.Next() {
		var r SpecialisationRef
		if err := rows.Scan(&r.Slug, &r.Name, &r.ShortName); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func (s *Store) skills(ctx context.Context, userID uuid.UUID) ([]SkillRef, error) {
	rows, err := s.db.Query(ctx, `
		SELECT sk.slug, sk.name, sk.kind, coalesce(sk.colour, ''),
		       ds.level, ds.years, ds.evidence, ds.is_primary
		FROM developer_skills ds
		JOIN skills sk ON sk.id = ds.skill_id
		WHERE ds.user_id = $1 AND sk.is_active
		ORDER BY ds.is_primary DESC, ds.sort_order, sk.name`, userID)
	if err != nil {
		return nil, fmt.Errorf("query developer skills: %w", err)
	}
	defer rows.Close()

	out := []SkillRef{}
	for rows.Next() {
		var r SkillRef
		if err := rows.Scan(&r.Slug, &r.Name, &r.Kind, &r.Colour,
			&r.Level, &r.Years, &r.Evidence, &r.IsPrimary); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func (s *Store) languages(ctx context.Context, userID uuid.UUID) ([]Language, error) {
	rows, err := s.db.Query(ctx,
		`SELECT language, proficiency FROM user_languages WHERE user_id = $1 ORDER BY language`, userID)
	if err != nil {
		return nil, fmt.Errorf("query languages: %w", err)
	}
	defer rows.Close()

	out := []Language{}
	for rows.Next() {
		var l Language
		if err := rows.Scan(&l.Language, &l.Proficiency); err != nil {
			return nil, err
		}
		out = append(out, l)
	}
	return out, rows.Err()
}

// ── Onboarding writes ───────────────────────────────────────────────────────

type BasicsInput struct {
	FullName    string
	CountryCode string
	City        string
	Timezone    string
	Languages   []Language
}

func (s *Store) SaveBasics(ctx context.Context, userID uuid.UUID, in BasicsInput) error {
	return s.db.InTx(ctx, func(q database.Querier) error {
		if _, err := q.Exec(ctx, `
			UPDATE users SET full_name = $2, country_code = $3, city = $4,
			                 timezone = coalesce($5, timezone), updated_at = now()
			WHERE id = $1`,
			userID, in.FullName, nullIfBlank(strings.ToUpper(in.CountryCode)),
			nullIfBlank(in.City), nullIfBlank(in.Timezone)); err != nil {
			return fmt.Errorf("update user basics: %w", err)
		}

		// Languages are replaced wholesale: the client always sends the full
		// list, and a diff would be more code for no benefit at this size.
		if _, err := q.Exec(ctx, `DELETE FROM user_languages WHERE user_id = $1`, userID); err != nil {
			return fmt.Errorf("clear languages: %w", err)
		}
		for _, l := range in.Languages {
			if _, err := q.Exec(ctx, `
				INSERT INTO user_languages (user_id, language, proficiency)
				VALUES ($1, $2, $3) ON CONFLICT (user_id, language) DO UPDATE
				SET proficiency = excluded.proficiency`,
				userID, l.Language, l.Proficiency); err != nil {
				return fmt.Errorf("insert language %q: %w", l.Language, err)
			}
		}
		return nil
	})
}

// SetPrimarySpecialisation also clears it from the additional list, so the two
// can never name the same thing.
func (s *Store) SetPrimarySpecialisation(ctx context.Context, userID, specialisationID uuid.UUID, title string) error {
	return s.db.InTx(ctx, func(q database.Querier) error {
		if _, err := q.Exec(ctx,
			`DELETE FROM developer_specialisations WHERE user_id = $1 AND specialisation_id = $2`,
			userID, specialisationID); err != nil {
			return fmt.Errorf("clear duplicate specialisation: %w", err)
		}
		_, err := q.Exec(ctx, `
			UPDATE developer_profiles
			   SET primary_specialisation_id = $2,
			       professional_title = coalesce(nullif($3, ''), professional_title),
			       updated_at = now()
			 WHERE user_id = $1`, userID, specialisationID, title)
		if err != nil {
			return fmt.Errorf("set primary specialisation: %w", err)
		}
		return nil
	})
}

// SetAdditionalSpecialisations replaces the list. The cap is a deferred
// constraint trigger, so it fires on commit and is translated here.
func (s *Store) SetAdditionalSpecialisations(ctx context.Context, userID uuid.UUID, ids []uuid.UUID) error {
	err := s.db.InTx(ctx, func(q database.Querier) error {
		if _, err := q.Exec(ctx,
			`DELETE FROM developer_specialisations WHERE user_id = $1`, userID); err != nil {
			return fmt.Errorf("clear additional specialisations: %w", err)
		}
		for _, id := range ids {
			if _, err := q.Exec(ctx,
				`INSERT INTO developer_specialisations (user_id, specialisation_id)
				 VALUES ($1, $2) ON CONFLICT DO NOTHING`, userID, id); err != nil {
				return fmt.Errorf("insert additional specialisation: %w", err)
			}
		}
		return nil
	})
	if database.IsCheckViolation(err) {
		msg := database.CheckMessage(err)
		if strings.Contains(msg, "duplicate") {
			return fmt.Errorf("an additional area cannot repeat your main profession")
		}
		return ErrTooManySpecialisations
	}
	return err
}

type SkillInput struct {
	SkillID uuid.UUID
	Level   string
	Years   *int
	Primary bool
}

// SetSkills replaces the technology list, preserving any evidence the GitHub
// analysis has attached: a developer re-editing their list must not erase the
// platform's own corroboration.
func (s *Store) SetSkills(ctx context.Context, userID uuid.UUID, skills []SkillInput) error {
	err := s.db.InTx(ctx, func(q database.Querier) error {
		evidence := map[uuid.UUID][]string{}
		rows, err := q.Query(ctx,
			`SELECT skill_id, evidence FROM developer_skills WHERE user_id = $1`, userID)
		if err != nil {
			return fmt.Errorf("read existing skill evidence: %w", err)
		}
		for rows.Next() {
			var id uuid.UUID
			var ev []string
			if err := rows.Scan(&id, &ev); err != nil {
				rows.Close()
				return err
			}
			evidence[id] = ev
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return err
		}

		if _, err := q.Exec(ctx, `DELETE FROM developer_skills WHERE user_id = $1`, userID); err != nil {
			return fmt.Errorf("clear skills: %w", err)
		}
		for i, sk := range skills {
			if _, err := q.Exec(ctx, `
				INSERT INTO developer_skills (user_id, skill_id, level, years, is_primary, evidence, sort_order)
				VALUES ($1, $2, $3, $4, $5, $6, $7)`,
				userID, sk.SkillID, sk.Level, sk.Years, sk.Primary,
				database.Array(evidence[sk.SkillID]), i); err != nil {
				return fmt.Errorf("insert skill: %w", err)
			}
		}
		return nil
	})
	if database.IsCheckViolation(err) {
		return ErrTooManySkills
	}
	return err
}

type ExperienceInput struct {
	Level           string
	Years           *int
	HourlyRateMinor *int64
	MinProjectMinor *int64
	Currency        string
}

func (s *Store) SaveExperience(ctx context.Context, userID uuid.UUID, in ExperienceInput) error {
	_, err := s.db.Exec(ctx, `
		UPDATE developer_profiles SET
		  experience_level  = $2,
		  years_experience  = $3,
		  hourly_rate_minor = $4,
		  min_project_minor = $5,
		  rate_currency     = coalesce(nullif($6, ''), rate_currency),
		  updated_at        = now()
		WHERE user_id = $1`,
		userID, nullIfBlank(in.Level), in.Years, in.HourlyRateMinor,
		in.MinProjectMinor, in.Currency)
	if err != nil {
		return fmt.Errorf("save experience: %w", err)
	}
	return nil
}

type AvailabilityInput struct {
	Availability   string
	HoursPerWeek   *int
	AvailableFrom  *time.Time
	OverlapFromUTC *int
	OverlapToUTC   *int
	OpenToInvites  *bool
	ShowLocation   *bool
	ShowHourlyRate *bool
}

func (s *Store) SaveAvailability(ctx context.Context, userID uuid.UUID, in AvailabilityInput) error {
	_, err := s.db.Exec(ctx, `
		UPDATE developer_profiles SET
		  availability        = $2,
		  hours_per_week      = $3,
		  available_from      = $4,
		  overlap_from_utc    = $5,
		  overlap_to_utc      = $6,
		  open_to_invitations = coalesce($7, open_to_invitations),
		  show_location       = coalesce($8, show_location),
		  show_hourly_rate    = coalesce($9, show_hourly_rate),
		  updated_at          = now()
		WHERE user_id = $1`,
		userID, in.Availability, in.HoursPerWeek, in.AvailableFrom,
		in.OverlapFromUTC, in.OverlapToUTC, in.OpenToInvites,
		in.ShowLocation, in.ShowHourlyRate)
	if err != nil {
		return fmt.Errorf("save availability: %w", err)
	}
	return nil
}

func (s *Store) SaveBio(ctx context.Context, userID uuid.UUID, bio, title string) error {
	_, err := s.db.Exec(ctx, `
		UPDATE developer_profiles
		   SET bio = $2,
		       professional_title = coalesce(nullif($3, ''), professional_title),
		       updated_at = now()
		 WHERE user_id = $1`, userID, nullIfBlank(bio), title)
	if err != nil {
		return fmt.Errorf("save bio: %w", err)
	}
	return nil
}

// AdvanceOnboarding records progress. The step only ever moves forward, so
// revisiting step 2 from the summary screen does not reset the flow.
func (s *Store) AdvanceOnboarding(ctx context.Context, userID uuid.UUID, step int) error {
	_, err := s.db.Exec(ctx, `
		UPDATE developer_profiles
		   SET onboarding_step = greatest(onboarding_step, $2), updated_at = now()
		 WHERE user_id = $1`, userID, step)
	return err
}

// CompleteOnboarding marks the flow done and makes the profile discoverable.
//
// Searchability is set here and nowhere else: a profile becomes visible to
// clients exactly when its owner finishes the flow, never as a side effect of
// some other write.
func (s *Store) CompleteOnboarding(ctx context.Context, userID uuid.UUID, completeness int) error {
	_, err := s.db.Exec(ctx, `
		UPDATE developer_profiles SET
		  onboarding_step         = $3,
		  onboarding_completed_at = coalesce(onboarding_completed_at, now()),
		  profile_completeness    = $2,
		  is_searchable           = true,
		  updated_at              = now()
		WHERE user_id = $1`, userID, completeness, TotalOnboardingSteps)
	if err != nil {
		return fmt.Errorf("complete onboarding: %w", err)
	}
	return nil
}

// WorkSamples counts what a freelancer can show a client: entries they added
// to their portfolio, and work finished through AVERIX, which the platform
// vouches for itself.
//
// One of these is required before the application is sent. A profile without a
// single piece of work asks a client to take a stranger's word for it, and
// that is the thing this marketplace exists not to do.
func (s *Store) WorkSamples(ctx context.Context, userID uuid.UUID) (int, error) {
	var n int
	err := s.db.QueryRow(ctx, `
		SELECT (SELECT count(*) FROM portfolio_projects p
		         -- Опубликованные: черновик, который никто не видит, заказчику
		         -- ничего не показывает.
		         WHERE p.developer_id = $1 AND p.is_published
		           AND p.moderation_state <> 'rejected')
		     + (SELECT count(*) FROM completed_project_history h
		         WHERE h.developer_id = $1)`, userID).Scan(&n)
	if err != nil {
		return 0, fmt.Errorf("count work samples: %w", err)
	}
	return n, nil
}

// SubmitForReview is what the last step of the form does: the profile is
// complete, it goes to a person, and until that person says yes it is not in
// the catalogue.
func (s *Store) SubmitForReview(ctx context.Context, userID uuid.UUID, completeness int) error {
	_, err := s.db.Exec(ctx, `
		UPDATE developer_profiles SET
		  onboarding_step         = $3,
		  onboarding_completed_at = coalesce(onboarding_completed_at, now()),
		  profile_completeness    = $2,
		  moderation_state        = 'pending',
		  -- Not in the catalogue yet. Appearing there is what approval grants.
		  is_searchable           = false,
		  updated_at              = now()
		WHERE user_id = $1`, userID, completeness, TotalOnboardingSteps)
	if err != nil {
		return fmt.Errorf("submit profile for review: %w", err)
	}
	return nil
}

func (s *Store) SaveCompleteness(ctx context.Context, userID uuid.UUID, completeness int) error {
	_, err := s.db.Exec(ctx,
		`UPDATE developer_profiles SET profile_completeness = $2 WHERE user_id = $1`,
		userID, completeness)
	return err
}

// SetSearchable is used by moderation and by the developer's own privacy
// toggle to hide a profile without deleting it.
func (s *Store) SetSearchable(ctx context.Context, userID uuid.UUID, searchable bool) error {
	_, err := s.db.Exec(ctx,
		`UPDATE developer_profiles SET is_searchable = $2, updated_at = now() WHERE user_id = $1`,
		userID, searchable)
	return err
}

// IsSaved reports whether a client has bookmarked this developer, for the
// public profile's save button.
func (s *Store) IsSaved(ctx context.Context, clientID, developerID uuid.UUID) (bool, error) {
	var saved bool
	err := s.db.QueryRow(ctx,
		`SELECT EXISTS (SELECT 1 FROM saved_developers WHERE client_id = $1 AND developer_id = $2)`,
		clientID, developerID).Scan(&saved)
	return saved, err
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

func nullIfBlank(s string) any {
	if strings.TrimSpace(s) == "" {
		return nil
	}
	return s
}

// ── Уровень исполнителя ─────────────────────────────────────────────────────

// LevelChange is one freelancer whose level moved, either way.
type LevelChange struct {
	UserID uuid.UUID
	From   string
	To     string
}

// RefreshSellerLevels recomputes every freelancer's level and returns the ones
// that changed.
//
// The numbers come from contracts rather than from a counter kept up to date
// by hand: a level is a claim about someone's record, and the record is the
// contracts table. Only the last hundred finished deals count, so a bad month
// three years ago does not follow a person forever — and a good year does not
// excuse this month.
//
// What counts as a failure is deliberately narrow. A client who cancels before
// any work started is not the freelancer's fault; declining an order in time
// is not a failure at all — refusing honestly is better than accepting and
// disappearing. Cancelling after work began, and letting an order expire
// unanswered, are.
func (s *Store) RefreshSellerLevels(ctx context.Context) ([]LevelChange, error) {
	rows, err := s.db.Query(ctx, `
		WITH recent AS (
			SELECT c.developer_id, c.status, c.cancelled_by, c.progress_percent,
			       c.developer_confirm_deadline, c.developer_confirmed_at, c.cancelled_at,
			       row_number() OVER (
			           PARTITION BY c.developer_id
			           ORDER BY coalesce(c.completed_at, c.cancelled_at, c.updated_at) DESC) AS n
			FROM contracts c
			WHERE c.status IN ('completed','cancelled') AND NOT c.is_demo
		),
		stats AS (
			SELECT developer_id,
			       count(*) FILTER (WHERE status = 'completed') AS completed,
			       count(*) FILTER (WHERE status = 'cancelled' AND (
			           cancelled_by = developer_id
			           OR progress_percent > 0
			           OR (developer_confirm_deadline IS NOT NULL
			               AND developer_confirmed_at IS NULL
			               AND cancelled_at > developer_confirm_deadline))) AS failed
			FROM recent WHERE n <= 100 GROUP BY developer_id
		),
		levelled AS (
			SELECT dp.user_id, dp.seller_level AS was,
			       CASE
			         WHEN coalesce(s.completed, 0) >= 50
			              AND coalesce(s.failed, 0) <= 0.08 *
			                  greatest(coalesce(s.completed, 0) + coalesce(s.failed, 0), 1)
			              AND (dp.rating_avg IS NULL OR dp.rating_avg >= 4.5) THEN 'professional'
			         WHEN coalesce(s.completed, 0) >= 10
			              AND coalesce(s.failed, 0) <= 0.10 *
			                  greatest(coalesce(s.completed, 0) + coalesce(s.failed, 0), 1)
			              AND (dp.rating_avg IS NULL OR dp.rating_avg >= 4.0) THEN 'advanced'
			         ELSE 'new'
			       END AS level
			FROM developer_profiles dp
			LEFT JOIN stats s ON s.developer_id = dp.user_id
		)
		UPDATE developer_profiles d
		SET seller_level = l.level, seller_level_updated_at = now()
		FROM levelled l
		WHERE d.user_id = l.user_id AND d.seller_level IS DISTINCT FROM l.level
		RETURNING d.user_id, l.was, l.level`)
	if err != nil {
		return nil, fmt.Errorf("refresh seller levels: %w", err)
	}
	defer rows.Close()

	out := []LevelChange{}
	for rows.Next() {
		var change LevelChange
		if err := rows.Scan(&change.UserID, &change.From, &change.To); err != nil {
			return nil, err
		}
		out = append(out, change)
	}
	return out, rows.Err()
}

// SellerLevel reads one freelancer's level, for the rules that depend on it.
func (s *Store) SellerLevel(ctx context.Context, userID uuid.UUID) (string, error) {
	var level string
	err := s.db.QueryRow(ctx,
		`SELECT seller_level FROM developer_profiles WHERE user_id = $1`, userID).Scan(&level)
	if database.IsNoRows(err) {
		return "new", nil
	}
	if err != nil {
		return "", fmt.Errorf("read seller level: %w", err)
	}
	return level, nil
}
