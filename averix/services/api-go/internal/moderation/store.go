package moderation

import (
	"context"
	"errors"
	"fmt"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/database"
)

var ErrNotFound = errors.New("not found")

type Store struct{ db *database.DB }

func NewStore(db *database.DB) *Store { return &Store{db: db} }

// subjectTables maps a subject to the table that carries its
// moderation_state. A subject absent from the map cannot be hidden by the
// moderator directly — a user is suspended, a message is not content that
// stays visible — and the queue shows the decision as "escalate to admin".
var subjectTables = map[string]struct {
	Table, Owner string
}{
	SubjectProject:          {"projects", "client_id"},
	SubjectService:          {"services", "developer_id"},
	SubjectReview:           {"reviews", "author_id"},
	SubjectPortfolioProject: {"portfolio_projects", "developer_id"},
	SubjectDeveloperProfile: {"developer_profiles", "user_id"},
	SubjectPhoto:            {"developer_photos", "user_id"},
}

// Flag adds a queue item. Repeated flags on the same subject raise the
// existing pending item's priority instead of adding a duplicate: one
// decision covers all of them.
func (s *Store) Flag(ctx context.Context, subjectType string, subjectID uuid.UUID, reason, origin string, priority int) error {
	tag, err := s.db.Exec(ctx, `
		UPDATE moderation_queue
		SET priority = least(100, priority + 10),
		    reason = CASE WHEN reason = $3 THEN reason ELSE reason || '; ' || $3 END
		WHERE subject_type = $1 AND subject_id = $2 AND status = 'pending'`,
		subjectType, subjectID, reason)
	if err != nil {
		return err
	}
	if tag.RowsAffected() > 0 {
		return nil
	}
	_, err = s.db.Exec(ctx, `
		INSERT INTO moderation_queue (subject_type, subject_id, reason, origin, priority)
		VALUES ($1, $2, $3, $4, $5)`, subjectType, subjectID, reason, origin, priority)
	return err
}

// FileReport records a user's report and queues the subject if it is not
// already waiting.
func (s *Store) FileReport(ctx context.Context, reporterID uuid.UUID, in ReportRequest, subjectID uuid.UUID) (uuid.UUID, error) {
	var id uuid.UUID
	err := s.db.InTx(ctx, func(q database.Querier) error {
		if err := q.QueryRow(ctx, `
			INSERT INTO reports (reporter_id, subject_type, subject_id, reason, detail)
			VALUES ($1, $2, $3, $4, nullif($5, ''))
			RETURNING id`, reporterID, in.SubjectType, subjectID, in.Reason, in.Detail).Scan(&id); err != nil {
			return err
		}
		tag, err := q.Exec(ctx, `
			UPDATE moderation_queue SET priority = least(100, priority + 15)
			WHERE subject_type = $1 AND subject_id = $2 AND status = 'pending'`, in.SubjectType, subjectID)
		if err != nil {
			return err
		}
		if tag.RowsAffected() == 0 {
			// A queue row per reportable subject type; users are escalated
			// straight to an administrator's attention.
			queueType := in.SubjectType
			if _, ok := subjectTables[queueType]; !ok {
				queueType = SubjectDeveloperProfile
				if in.SubjectType != SubjectUser {
					queueType = SubjectProject
				}
			}
			if in.SubjectType == SubjectUser {
				_, err = q.Exec(ctx, `
					INSERT INTO moderation_queue (subject_type, subject_id, reason, origin, priority, status)
					VALUES ('developer_profile', $1, $2, 'report', 70, 'escalated')`,
					subjectID, "report: "+in.Reason)
				return err
			}
			if in.SubjectType == SubjectMessage || in.SubjectType == SubjectProposal {
				_, err = q.Exec(ctx, `
					INSERT INTO moderation_queue (subject_type, subject_id, reason, origin, priority, status)
					VALUES ('project', $1, $2, 'report', 60, 'escalated')`,
					subjectID, "report on "+in.SubjectType+": "+in.Reason)
				return err
			}
			_, err = q.Exec(ctx, `
				INSERT INTO moderation_queue (subject_type, subject_id, reason, origin, priority)
				VALUES ($1, $2, $3, 'report', 60)`, queueType, subjectID, "report: "+in.Reason)
		}
		return err
	})
	return id, err
}

// SubjectExists checks that a report points at something real, per type.
func (s *Store) SubjectExists(ctx context.Context, subjectType string, subjectID uuid.UUID) (bool, error) {
	table := map[string]string{
		SubjectUser: "users", SubjectProject: "projects", SubjectProposal: "proposals",
		SubjectPortfolioProject: "portfolio_projects", SubjectService: "services",
		SubjectReview: "reviews", SubjectMessage: "messages",
	}[subjectType]
	if table == "" {
		return false, nil
	}
	var ok bool
	err := s.db.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM `+table+` WHERE id = $1)`, subjectID).Scan(&ok)
	return ok, err
}

// ── The queue ───────────────────────────────────────────────────────────────

const queueColumns = `
	m.id, m.subject_type, m.subject_id, m.reason, m.origin, m.priority, m.status, m.created_at,
	m.reviewed_by, coalesce(rb.full_name, ''), coalesce(m.review_note, ''), m.reviewed_at,
	(SELECT count(*) FROM reports r WHERE r.subject_type = m.subject_type AND r.subject_id = m.subject_id)`

func (s *Store) Queue(ctx context.Context, status string, limit, offset int) ([]QueueItem, int, error) {
	if status == "" {
		status = "pending"
	}
	if limit <= 0 || limit > 100 {
		limit = 30
	}
	var total int
	if err := s.db.QueryRow(ctx, `SELECT count(*) FROM moderation_queue WHERE status = $1`, status).Scan(&total); err != nil {
		return nil, 0, err
	}
	rows, err := s.db.Query(ctx, `SELECT `+queueColumns+`
		FROM moderation_queue m
		LEFT JOIN users rb ON rb.id = m.reviewed_by
		WHERE m.status = $1
		ORDER BY m.priority DESC, m.created_at
		LIMIT $2 OFFSET $3`, status, limit, offset)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	items := []QueueItem{}
	for rows.Next() {
		item, err := s.scanQueue(rows)
		if err != nil {
			return nil, 0, err
		}
		items = append(items, *item)
	}
	if err := rows.Err(); err != nil {
		return nil, 0, err
	}
	for i := range items {
		items[i].Preview = s.preview(ctx, items[i].SubjectType, items[i].SubjectID)
		items[i].Href = hrefFor(items[i].SubjectType, items[i].SubjectID, items[i].Preview)
	}
	return items, total, nil
}

func (s *Store) QueueItem(ctx context.Context, id uuid.UUID) (*QueueItem, error) {
	item, err := s.scanQueue(s.db.QueryRow(ctx, `SELECT `+queueColumns+`
		FROM moderation_queue m LEFT JOIN users rb ON rb.id = m.reviewed_by WHERE m.id = $1`, id))
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	item.Preview = s.preview(ctx, item.SubjectType, item.SubjectID)
	item.Href = hrefFor(item.SubjectType, item.SubjectID, item.Preview)
	return item, nil
}

func (s *Store) scanQueue(row interface{ Scan(...any) error }) (*QueueItem, error) {
	var item QueueItem
	var by *uuid.UUID
	var byName, note string
	var at *timeOrNil
	if err := row.Scan(&item.ID, &item.SubjectType, &item.SubjectID, &item.Reason, &item.Origin,
		&item.Priority, &item.Status, &item.CreatedAt, &by, &byName, &note, &at, &item.Reports); err != nil {
		return nil, err
	}
	if by != nil && at != nil {
		item.Decision = &Decision{By: *by, ByName: byName, Note: note, Outcome: item.Status, At: at.Time}
	}
	return &item, nil
}

// preview resolves a subject to a title, an excerpt and its owner.
func (s *Store) preview(ctx context.Context, subjectType string, subjectID uuid.UUID) Preview {
	var p Preview
	var query string
	switch subjectType {
	case SubjectProject:
		query = `SELECT p.title, left(p.description, 240), u.id, u.username, p.moderation_state
		         FROM projects p JOIN users u ON u.id = p.client_id WHERE p.id = $1`
	case SubjectService:
		query = `SELECT s.title, left(s.description, 240), u.id, u.username, s.moderation_state
		         FROM services s JOIN users u ON u.id = s.developer_id WHERE s.id = $1`
	case SubjectReview:
		query = `SELECT 'Отзыв по контракту ' || c.title, coalesce(left(r.comment, 240), ''), u.id, u.username, r.moderation_state
		         FROM reviews r JOIN users u ON u.id = r.author_id JOIN contracts c ON c.id = r.contract_id WHERE r.id = $1`
	case SubjectPortfolioProject:
		query = `SELECT p.title, coalesce(left(p.description, 240), ''), u.id, u.username, p.moderation_state
		         FROM portfolio_projects p JOIN users u ON u.id = p.developer_id WHERE p.id = $1`
	case SubjectDeveloperProfile:
		query = `SELECT u.full_name, coalesce(left(d.bio, 240), ''), u.id, u.username, d.moderation_state
		         FROM developer_profiles d JOIN users u ON u.id = d.user_id WHERE d.user_id = $1`
	case SubjectPhoto:
		query = `SELECT 'Фото профиля', '', u.id, u.username, ph.moderation_state
		         FROM developer_photos ph JOIN users u ON u.id = ph.user_id WHERE ph.id = $1`
	case SubjectProposal:
		query = `SELECT 'Отклик на ' || pj.title, left(pr.cover_letter, 240), u.id, u.username, ''
		         FROM proposals pr JOIN users u ON u.id = pr.developer_id JOIN projects pj ON pj.id = pr.project_id WHERE pr.id = $1`
	default:
		return p
	}
	_ = s.db.QueryRow(ctx, query, subjectID).Scan(&p.Title, &p.Excerpt, &p.OwnerID, &p.Username, &p.State)
	return p
}

func hrefFor(subjectType string, subjectID uuid.UUID, p Preview) string {
	switch subjectType {
	case SubjectService:
		return "/services/" + subjectID.String()
	case SubjectDeveloperProfile, SubjectPhoto:
		if p.Username != "" {
			return "/developers/" + p.Username
		}
	case SubjectPortfolioProject:
		if p.Username != "" {
			return "/developers/" + p.Username
		}
	}
	return ""
}

// Decide records the outcome and, for a rejection, hides the content.
// Hidden means moderation_state = 'hidden' on the subject's own table, which
// every public query already excludes — nothing is deleted.
func (s *Store) Decide(ctx context.Context, id, moderatorID uuid.UUID, outcome, note string) (*QueueItem, error) {
	item, err := s.QueueItem(ctx, id)
	if err != nil {
		return nil, err
	}
	status := map[string]string{"approve": "approved", "reject": "rejected", "escalate": "escalated"}[outcome]
	if status == "" {
		return nil, fmt.Errorf("unknown outcome %q", outcome)
	}
	err = s.db.InTx(ctx, func(q database.Querier) error {
		tag, err := q.Exec(ctx, `
			UPDATE moderation_queue
			SET status = $2, reviewed_by = $3, review_note = nullif($4, ''), reviewed_at = now()
			WHERE id = $1 AND status IN ('pending', 'escalated')`, id, status, moderatorID, note)
		if err != nil {
			return err
		}
		if tag.RowsAffected() == 0 {
			return ErrNotFound
		}
		target, hideable := subjectTables[item.SubjectType]
		if !hideable {
			return nil
		}
		state := "approved"
		if outcome == "reject" {
			state = "hidden"
		}
		if outcome == "escalate" {
			state = "pending"
		}
		_, err = q.Exec(ctx, `UPDATE `+target.Table+` SET moderation_state = $2 WHERE id = $1`, item.SubjectID, state)
		if item.SubjectType == SubjectDeveloperProfile {
			_, err = q.Exec(ctx, `UPDATE developer_profiles SET moderation_state = $2 WHERE user_id = $1`, item.SubjectID, state)
		}
		return err
	})
	if err != nil {
		return nil, err
	}
	return s.QueueItem(ctx, id)
}

// ── Reports ─────────────────────────────────────────────────────────────────

func (s *Store) Reports(ctx context.Context, status string, limit, offset int) ([]Report, int, error) {
	if status == "" {
		status = "open"
	}
	if limit <= 0 || limit > 100 {
		limit = 30
	}
	var total int
	if err := s.db.QueryRow(ctx, `SELECT count(*) FROM reports WHERE status = $1`, status).Scan(&total); err != nil {
		return nil, 0, err
	}
	rows, err := s.db.Query(ctx, `
		SELECT r.id, r.subject_type, r.subject_id, r.reason, coalesce(r.detail, ''), r.status,
		       u.id, u.username, u.full_name, coalesce(r.resolution, ''), r.resolved_at, r.created_at
		FROM reports r
		LEFT JOIN users u ON u.id = r.reporter_id
		WHERE r.status = $1
		ORDER BY r.created_at
		LIMIT $2 OFFSET $3`, status, limit, offset)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	out := []Report{}
	for rows.Next() {
		var r Report
		var reporterID *uuid.UUID
		var username, fullName *string
		if err := rows.Scan(&r.ID, &r.SubjectType, &r.SubjectID, &r.Reason, &r.Detail, &r.Status,
			&reporterID, &username, &fullName, &r.Resolution, &r.ResolvedAt, &r.CreatedAt); err != nil {
			return nil, 0, err
		}
		r.ReasonLabel = reportReasons[r.Reason]
		if reporterID != nil {
			r.Reporter = &Person{UserID: *reporterID, Username: deref(username), FullName: deref(fullName)}
		}
		out = append(out, r)
	}
	if err := rows.Err(); err != nil {
		return nil, 0, err
	}
	for i := range out {
		out[i].Preview = s.preview(ctx, out[i].SubjectType, out[i].SubjectID)
	}
	return out, total, nil
}

func (s *Store) ResolveReport(ctx context.Context, id, byID uuid.UUID, status, resolution string) error {
	tag, err := s.db.Exec(ctx, `
		UPDATE reports
		SET status = $2, resolution = nullif($3, ''), assigned_to = $4, resolved_at = now()
		WHERE id = $1 AND status IN ('open', 'reviewing')`, id, status, resolution, byID)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (s *Store) Counts(ctx context.Context) (pending, escalated, openReports int, err error) {
	err = s.db.QueryRow(ctx, `
		SELECT (SELECT count(*) FROM moderation_queue WHERE status = 'pending'),
		       (SELECT count(*) FROM moderation_queue WHERE status = 'escalated'),
		       (SELECT count(*) FROM reports WHERE status = 'open')`).Scan(&pending, &escalated, &openReports)
	return
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}
