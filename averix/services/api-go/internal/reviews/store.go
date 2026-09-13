package reviews

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/money"
)

var (
	ErrAlreadyReviewed = errors.New("this side has already reviewed the contract")
	ErrNotFound        = errors.New("review not found")
)

type Store struct {
	db        *database.DB
	publicURL func(string) string
}

func NewStore(db *database.DB, publicURL func(string) string) *Store {
	return &Store{db: db, publicURL: publicURL}
}

// contractFacts is what deciding whether a review may be written needs.
type contractFacts struct {
	ID          uuid.UUID
	Title       string
	ClientID    uuid.UUID
	DeveloperID uuid.UUID
	Status      string
	CompletedAt *time.Time
}

func (s *Store) contract(ctx context.Context, contractID uuid.UUID) (contractFacts, error) {
	var f contractFacts
	err := s.db.QueryRow(ctx, `
		SELECT id, title, client_id, developer_id, status, completed_at
		FROM contracts WHERE id = $1`, contractID).
		Scan(&f.ID, &f.Title, &f.ClientID, &f.DeveloperID, &f.Status, &f.CompletedAt)
	if database.IsNoRows(err) {
		return f, ErrNotFound
	}
	return f, err
}

type newReview struct {
	ContractID     uuid.UUID
	AuthorID       uuid.UUID
	SubjectID      uuid.UUID
	Direction      string
	Overall        float64
	Scores         map[string]float64
	Comment        string
	WouldWorkAgain *bool
}

// Create inserts one side's review. The unique index on (contract, author)
// is what makes "one per side" true under concurrency, not a check first.
func (s *Store) Create(ctx context.Context, in newReview) (uuid.UUID, error) {
	score := func(key string) *float64 {
		if v, ok := in.Scores[key]; ok {
			return &v
		}
		return nil
	}
	var id uuid.UUID
	err := s.db.QueryRow(ctx, `
		INSERT INTO reviews
		  (contract_id, author_id, subject_id, direction, overall,
		   quality, communication, technical, deadline,
		   clarity, collaboration, payment_reliability,
		   comment, would_work_again)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,nullif($13,''),$14)
		RETURNING id`,
		in.ContractID, in.AuthorID, in.SubjectID, in.Direction, in.Overall,
		score("quality"), score("communication"), score("technical"), score("deadline"),
		score("clarity"), score("collaboration"), score("payment_reliability"),
		in.Comment, in.WouldWorkAgain).Scan(&id)
	if database.IsUniqueViolation(err, "reviews_one_per_side_key") {
		return uuid.Nil, ErrAlreadyReviewed
	}
	return id, err
}

// PublishIfBothSubmitted flips both reviews to published in one statement
// when both exist, and reports whether it did.
func (s *Store) PublishIfBothSubmitted(ctx context.Context, contractID uuid.UUID) (bool, error) {
	tag, err := s.db.Exec(ctx, `
		UPDATE reviews SET published_at = now()
		WHERE contract_id = $1 AND published_at IS NULL
		  AND (SELECT count(*) FROM reviews r WHERE r.contract_id = $1) = 2`, contractID)
	if err != nil {
		return false, err
	}
	published := tag.RowsAffected() > 0
	if published {
		err = s.attachToHistory(ctx, contractID)
	}
	return published, err
}

// PublishExpired publishes single-sided reviews whose window has closed: the
// other side chose not to write, and silence must not veto a review.
func (s *Store) PublishExpired(ctx context.Context, window time.Duration) ([]uuid.UUID, error) {
	rows, err := s.db.Query(ctx, `
		UPDATE reviews r SET published_at = now()
		FROM contracts c
		WHERE c.id = r.contract_id AND r.published_at IS NULL
		  AND c.completed_at IS NOT NULL AND c.completed_at < now() - $1::interval
		RETURNING r.contract_id`, fmt.Sprintf("%d seconds", int(window.Seconds())))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var contracts []uuid.UUID
	for rows.Next() {
		var id uuid.UUID
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		contracts = append(contracts, id)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	for _, id := range contracts {
		if err := s.attachToHistory(ctx, id); err != nil {
			return contracts, err
		}
	}
	return contracts, nil
}

// attachToHistory copies the client's published rating onto the verified
// history entry, which is what the profile shows next to the project.
func (s *Store) attachToHistory(ctx context.Context, contractID uuid.UUID) error {
	_, err := s.db.Exec(ctx, `
		UPDATE completed_project_history h
		SET client_rating = r.overall, review_id = r.id, updated_at = now()
		FROM reviews r
		WHERE r.contract_id = h.contract_id AND h.contract_id = $1
		  AND r.direction = 'of_developer' AND r.published_at IS NOT NULL`, contractID)
	return err
}

const selectReview = `
	SELECT r.id, r.contract_id, r.direction, r.overall,
	       r.quality, r.communication, r.technical, r.deadline,
	       r.clarity, r.collaboration, r.payment_reliability,
	       coalesce(r.comment, ''), r.would_work_again,
	       coalesce(r.response, ''), r.response_at, r.published_at, r.created_at,
	       a.id, a.username, a.full_name, ap.derivatives,
	       s.id, s.username, s.full_name, sp.derivatives,
	       c.title
	FROM reviews r
	JOIN contracts c ON c.id = r.contract_id
	JOIN users a ON a.id = r.author_id
	JOIN users s ON s.id = r.subject_id
	LEFT JOIN LATERAL (SELECT derivatives FROM developer_photos p
	                   WHERE p.user_id = a.id AND p.is_current AND p.moderation_state = 'approved' LIMIT 1) ap ON true
	LEFT JOIN LATERAL (SELECT derivatives FROM developer_photos p
	                   WHERE p.user_id = s.id AND p.is_current AND p.moderation_state = 'approved' LIMIT 1) sp ON true`

type scanner interface {
	Scan(dest ...any) error
}

func (s *Store) scan(row scanner) (*Review, error) {
	var r Review
	var quality, communication, technical, deadline, clarity, collaboration, payment *float64
	var authorPhoto, subjectPhoto map[string]map[string]string
	err := row.Scan(&r.ID, &r.ContractID, &r.Direction, &r.Overall,
		&quality, &communication, &technical, &deadline,
		&clarity, &collaboration, &payment,
		&r.Comment, &r.WouldWorkAgain,
		&r.Response, &r.ResponseAt, &r.PublishedAt, &r.CreatedAt,
		&r.Author.UserID, &r.Author.Username, &r.Author.FullName, &authorPhoto,
		&r.Subject.UserID, &r.Subject.Username, &r.Subject.FullName, &subjectPhoto,
		&r.ContractTitle)
	if err != nil {
		return nil, err
	}
	r.Author.PhotoURL = s.avatarURL(authorPhoto)
	r.Subject.PhotoURL = s.avatarURL(subjectPhoto)
	r.Scores = map[string]float64{}
	put := func(key string, v *float64) {
		if v != nil {
			r.Scores[key] = *v
		}
	}
	put("quality", quality)
	put("communication", communication)
	put("technical", technical)
	put("deadline", deadline)
	put("clarity", clarity)
	put("collaboration", collaboration)
	put("payment_reliability", payment)
	return &r, nil
}

func (s *Store) avatarURL(derivatives map[string]map[string]string) string {
	if s.publicURL == nil {
		return ""
	}
	for _, format := range []string{"webp", "jpeg"} {
		if key, ok := derivatives[format]["64"]; ok && key != "" {
			return s.publicURL(key)
		}
	}
	return ""
}

// ForContract returns both sides' reviews regardless of publication; the
// service decides what the caller may see.
func (s *Store) ForContract(ctx context.Context, contractID uuid.UUID) ([]*Review, error) {
	rows, err := s.db.Query(ctx, selectReview+` WHERE r.contract_id = $1 ORDER BY r.created_at`, contractID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Review
	for rows.Next() {
		r, err := s.scan(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func (s *Store) ByID(ctx context.Context, id uuid.UUID) (*Review, error) {
	r, err := s.scan(s.db.QueryRow(ctx, selectReview+` WHERE r.id = $1`, id))
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	return r, err
}

// Public lists published, approved reviews about a person, newest first.
func (s *Store) Public(ctx context.Context, subjectID uuid.UUID, direction string,
	before *time.Time, limit int) ([]*Review, error) {

	if limit <= 0 || limit > 50 {
		limit = 20
	}
	rows, err := s.db.Query(ctx, selectReview+`
		WHERE r.subject_id = $1 AND r.direction = $2
		  AND r.published_at IS NOT NULL AND r.moderation_state = 'approved'
		  AND ($3::timestamptz IS NULL OR r.published_at < $3)
		ORDER BY r.published_at DESC
		LIMIT $4`, subjectID, direction, before, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []*Review{}
	for rows.Next() {
		r, err := s.scan(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// Summary is the headline figures for a profile's review section.
type Summary struct {
	Count          int                `json:"count"`
	Average        *float64           `json:"average,omitempty"`
	Categories     map[string]float64 `json:"categories"`
	WouldWorkAgain *float64           `json:"would_work_again_share,omitempty"`
}

func (s *Store) Summarise(ctx context.Context, subjectID uuid.UUID, direction string) (Summary, error) {
	sum := Summary{Categories: map[string]float64{}}
	var q, comm, tech, dl, cl, col, pay, again *float64
	err := s.db.QueryRow(ctx, `
		SELECT count(*), round(avg(overall), 2),
		       round(avg(quality), 2), round(avg(communication), 2), round(avg(technical), 2),
		       round(avg(deadline), 2), round(avg(clarity), 2), round(avg(collaboration), 2),
		       round(avg(payment_reliability), 2),
		       round(avg(CASE WHEN would_work_again THEN 1 WHEN would_work_again = false THEN 0 END), 2)
		FROM reviews
		WHERE subject_id = $1 AND direction = $2
		  AND published_at IS NOT NULL AND moderation_state = 'approved'`, subjectID, direction).
		Scan(&sum.Count, &sum.Average, &q, &comm, &tech, &dl, &cl, &col, &pay, &again)
	if err != nil {
		return sum, err
	}
	for key, v := range map[string]*float64{"quality": q, "communication": comm, "technical": tech,
		"deadline": dl, "clarity": cl, "collaboration": col, "payment_reliability": pay} {
		if v != nil {
			sum.Categories[key] = *v
		}
	}
	sum.WouldWorkAgain = again
	return sum, nil
}

// Respond records the subject's one reply.
func (s *Store) Respond(ctx context.Context, reviewID, subjectID uuid.UUID, text string) error {
	tag, err := s.db.Exec(ctx, `
		UPDATE reviews SET response = $3, response_at = now()
		WHERE id = $1 AND subject_id = $2 AND published_at IS NOT NULL AND response IS NULL`,
		reviewID, subjectID, text)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (s *Store) userIDByUsername(ctx context.Context, username string) (uuid.UUID, error) {
	var id uuid.UUID
	err := s.db.QueryRow(ctx, `SELECT id FROM users WHERE username = lower(btrim($1))`, username).Scan(&id)
	if database.IsNoRows(err) {
		return uuid.Nil, ErrNotFound
	}
	return id, err
}

// ── Verified history ────────────────────────────────────────────────────────

// RecordCompletion writes the history entry for a finished contract. It is
// derived entirely from the contract and the project — the freelancer never
// types a word of it — and a repeat call is a no-op.
func (s *Store) RecordCompletion(ctx context.Context, contractID uuid.UUID) error {
	_, err := s.db.Exec(ctx, `
		INSERT INTO completed_project_history
		  (developer_id, contract_id, project_id, client_id, title, summary, category_id,
		   value_minor, currency, value_visibility, duration_days, completed_at)
		SELECT c.developer_id, c.id, c.project_id, c.client_id, c.title, p.summary, p.category_id,
		       c.amount_minor, c.currency, c.price_visibility,
		       CASE WHEN c.starts_on IS NOT NULL
		            THEN greatest(1, (c.completed_at::date - c.starts_on))
		            ELSE greatest(1, (c.completed_at::date - c.created_at::date)) END,
		       c.completed_at
		FROM contracts c
		JOIN projects p ON p.id = c.project_id
		WHERE c.id = $1 AND c.status = 'completed' AND c.completed_at IS NOT NULL
		ON CONFLICT (contract_id) DO NOTHING`, contractID)
	return err
}

// History lists a freelancer's verified entries. Hidden entries are included
// only for the owner, who may hide but never delete or edit them.
func (s *Store) History(ctx context.Context, developerID uuid.UUID, includeHidden bool) ([]HistoryEntry, error) {
	rows, err := s.db.Query(ctx, `
		SELECT h.id, h.contract_id, h.title, coalesce(h.summary, ''), cat.name,
		       h.client_rating, h.review_id, h.value_minor, h.currency, h.value_visibility,
		       h.duration_days, h.completed_at, h.is_visible
		FROM completed_project_history h
		LEFT JOIN categories cat ON cat.id = h.category_id
		WHERE h.developer_id = $1 AND ($2 OR h.is_visible)
		ORDER BY h.completed_at DESC`, developerID, includeHidden)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []HistoryEntry{}
	for rows.Next() {
		var e HistoryEntry
		var valueMinor int64
		var currency, visibility string
		if err := rows.Scan(&e.ID, &e.ContractID, &e.Title, &e.Summary, &e.Category,
			&e.ClientRating, &e.ReviewID, &valueMinor, &currency, &visibility,
			&e.DurationDays, &e.CompletedAt, &e.IsVisible); err != nil {
			return nil, err
		}
		e.ValueDisplay = displayValue(valueMinor, currency, visibility)
		out = append(out, e)
	}
	return out, rows.Err()
}

func (s *Store) SetHistoryVisibility(ctx context.Context, developerID, entryID uuid.UUID, visible bool) error {
	tag, err := s.db.Exec(ctx, `
		UPDATE completed_project_history SET is_visible = $3, updated_at = now()
		WHERE id = $1 AND developer_id = $2`, entryID, developerID, visible)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

// displayValue renders a contract's value according to the visibility the
// parties agreed: the figure, a bracket, or nothing. The developer's total
// earnings are never derivable from what is shown here.
func displayValue(minor int64, currency, visibility string) string {
	return money.Visible(minor, currency, visibility)
}

// bracket returns a round band around an amount so "about this much" is
// honest without being exact.
