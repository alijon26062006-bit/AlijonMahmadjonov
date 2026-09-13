package notifications

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"github.com/averix/api/internal/platform/database"
)

var ErrNotFound = errors.New("notification not found")

type Store struct {
	db        *database.DB
	publicURL func(key string) string
}

func NewStore(db *database.DB, publicURL func(string) string) *Store {
	return &Store{db: db, publicURL: publicURL}
}

// recipient is what deciding the channels needs: the address, whether it is
// verified, and whether a push subscription exists at all.
type recipient struct {
	Email         string
	EmailVerified bool
	Status        string
	HasPush       bool
	Pref          *Preference
}

func (s *Store) recipient(ctx context.Context, userID uuid.UUID, kind string) (recipient, error) {
	var r recipient
	var prefInApp, prefEmail, prefPush *bool
	err := s.db.QueryRow(ctx, `
		SELECT u.email, u.email_verified_at IS NOT NULL, u.status,
		       EXISTS (SELECT 1 FROM push_subscriptions ps WHERE ps.user_id = u.id),
		       p.in_app, p.email, p.push
		FROM users u
		LEFT JOIN notification_preferences p ON p.user_id = u.id AND p.type = $2
		WHERE u.id = $1`, userID, kind).
		Scan(&r.Email, &r.EmailVerified, &r.Status, &r.HasPush, &prefInApp, &prefEmail, &prefPush)
	if err != nil {
		return r, err
	}
	if prefInApp != nil {
		r.Pref = &Preference{Type: kind, InApp: *prefInApp, Email: *prefEmail, Push: *prefPush}
	}
	return r, nil
}

// Create writes the notification and its delivery rows in one transaction.
//
// The channel decision is made here, once, and recorded: a channel the
// person switched off gets a suppressed delivery row rather than no row, so
// "why did I not get an email about this" has an answer in the database.
func (s *Store) Create(ctx context.Context, in Input, online bool) (uuid.UUID, error) {
	info, ok := catalogue[in.Type]
	if !ok {
		return uuid.Nil, fmt.Errorf("unknown notification type %q", in.Type)
	}
	who, err := s.recipient(ctx, in.UserID, in.Type)
	if err != nil {
		return uuid.Nil, fmt.Errorf("load recipient: %w", err)
	}

	wantInApp, wantEmail, wantPush := true, info.Email, info.Push
	if who.Pref != nil {
		if !info.InAppLocked {
			wantInApp = who.Pref.InApp
		}
		wantEmail = wantEmail && who.Pref.Email
		wantPush = wantPush && who.Pref.Push
	}
	if in.Priority == "" {
		in.Priority = "normal"
	}
	metadata, err := json.Marshal(nonNil(in.Metadata))
	if err != nil {
		return uuid.Nil, err
	}

	var id uuid.UUID
	err = s.db.InTx(ctx, func(q database.Querier) error {
		if err := q.QueryRow(ctx, `
			INSERT INTO notifications
			  (user_id, type, title, body, href, actor_id, project_id, contract_id,
			   proposal_id, milestone_id, metadata, priority)
			VALUES ($1,$2,$3,nullif($4,''),nullif($5,''),$6,$7,$8,$9,$10,$11,$12)
			RETURNING id`,
			in.UserID, in.Type, in.Title, in.Body, in.Href, in.ActorID, in.ProjectID,
			in.ContractID, in.ProposalID, in.MilestoneID, metadata, in.Priority).Scan(&id); err != nil {
			return err
		}

		deliver := func(channel, status, reason string) error {
			var next *time.Time
			if status == DeliveryQueued {
				now := time.Now()
				next = &now
			}
			_, err := q.Exec(ctx, `
				INSERT INTO notification_deliveries (notification_id, channel, status, error, next_attempt_at)
				VALUES ($1, $2, $3, nullif($4, ''), $5)`, id, channel, status, reason, next)
			return err
		}

		// In-app is delivered by the act of inserting the row; the delivery
		// record says whether the person will see it in their list.
		if wantInApp {
			if err := deliver(ChannelInApp, DeliveryDelivered, ""); err != nil {
				return err
			}
		} else if err := deliver(ChannelInApp, DeliverySuppressed, "switched off"); err != nil {
			return err
		}

		switch {
		case !info.Email:
			// Not an emailable type: no row, nothing to explain.
		case who.Status != "active":
			if err := deliver(ChannelEmail, DeliverySkipped, "account "+who.Status); err != nil {
				return err
			}
		case !who.EmailVerified:
			if err := deliver(ChannelEmail, DeliverySkipped, "email not verified"); err != nil {
				return err
			}
		case !wantEmail:
			if err := deliver(ChannelEmail, DeliverySuppressed, "switched off"); err != nil {
				return err
			}
		case info.SuppressWhenOnline && online:
			if err := deliver(ChannelEmail, DeliverySuppressed, "online"); err != nil {
				return err
			}
		default:
			if err := deliver(ChannelEmail, DeliveryQueued, ""); err != nil {
				return err
			}
		}

		switch {
		case !info.Push:
		case !who.HasPush:
			// No subscription, no row: nothing was promised on this channel.
		case !wantPush:
			if err := deliver(ChannelPush, DeliverySuppressed, "switched off"); err != nil {
				return err
			}
		default:
			if err := deliver(ChannelPush, DeliveryQueued, ""); err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		return uuid.Nil, err
	}
	return id, nil
}

func nonNil(m map[string]any) map[string]any {
	if m == nil {
		return map[string]any{}
	}
	return m
}

// List returns a page, newest first, keyed on created_at.
func (s *Store) List(ctx context.Context, userID uuid.UUID, before *time.Time,
	unreadOnly bool, limit int) (Page, error) {

	if limit <= 0 || limit > 50 {
		limit = 30
	}
	rows, err := s.db.Query(ctx, `
		SELECT n.id, n.type, n.title, coalesce(n.body, ''), coalesce(n.href, ''), n.priority,
		       n.read_at, n.created_at,
		       a.id, a.username, a.full_name, ph.derivatives
		FROM notifications n
		LEFT JOIN users a ON a.id = n.actor_id
		LEFT JOIN LATERAL (
		  SELECT p.derivatives FROM developer_photos p
		  WHERE p.user_id = a.id AND p.is_current AND p.moderation_state = 'approved'
		  LIMIT 1
		) ph ON true
		WHERE n.user_id = $1
		  AND ($2::timestamptz IS NULL OR n.created_at < $2)
		  AND (NOT $3 OR n.read_at IS NULL)
		ORDER BY n.created_at DESC
		LIMIT $4`, userID, before, unreadOnly, limit+1)
	if err != nil {
		return Page{}, fmt.Errorf("list notifications: %w", err)
	}
	defer rows.Close()

	page := Page{Items: []Notification{}}
	for rows.Next() {
		var n Notification
		var actorID *uuid.UUID
		var username, fullName *string
		var derivatives map[string]map[string]string
		if err := rows.Scan(&n.ID, &n.Type, &n.Title, &n.Body, &n.Href, &n.Priority,
			&n.ReadAt, &n.CreatedAt, &actorID, &username, &fullName, &derivatives); err != nil {
			return Page{}, err
		}
		if actorID != nil {
			n.Actor = &Actor{UserID: *actorID, Username: deref(username), FullName: deref(fullName)}
			n.Actor.PhotoURL = s.avatarURL(derivatives, "64")
		}
		page.Items = append(page.Items, n)
	}
	if err := rows.Err(); err != nil {
		return Page{}, err
	}
	if len(page.Items) > limit {
		last := page.Items[limit-1].CreatedAt
		page.NextBefore = &last
		page.Items = page.Items[:limit]
	}
	page.Unread, err = s.UnreadCount(ctx, userID)
	return page, err
}

// avatarURL picks the smallest useful rendition, preferring the modern
// format; the same rule the proposal cards use, so a face looks the same
// everywhere.
func (s *Store) avatarURL(derivatives map[string]map[string]string, size string) string {
	if s.publicURL == nil {
		return ""
	}
	for _, format := range []string{"webp", "jpeg", "avif"} {
		if key, ok := derivatives[format][size]; ok && key != "" {
			return s.publicURL(key)
		}
	}
	return ""
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

func (s *Store) UnreadCount(ctx context.Context, userID uuid.UUID) (int, error) {
	var n int
	err := s.db.QueryRow(ctx,
		`SELECT count(*) FROM notifications WHERE user_id = $1 AND read_at IS NULL`, userID).Scan(&n)
	return n, err
}

// MarkRead is scoped to the owner in the WHERE clause, so a guessed id
// belonging to someone else reads as not found.
func (s *Store) MarkRead(ctx context.Context, userID, id uuid.UUID) error {
	tag, err := s.db.Exec(ctx, `
		UPDATE notifications SET read_at = coalesce(read_at, now())
		WHERE id = $1 AND user_id = $2`, id, userID)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (s *Store) MarkAllRead(ctx context.Context, userID uuid.UUID) (int, error) {
	tag, err := s.db.Exec(ctx, `
		UPDATE notifications SET read_at = now()
		WHERE user_id = $1 AND read_at IS NULL`, userID)
	if err != nil {
		return 0, err
	}
	return int(tag.RowsAffected()), nil
}

// ── Preferences ─────────────────────────────────────────────────────────────

func (s *Store) Preferences(ctx context.Context, userID uuid.UUID) ([]PreferenceGroup, error) {
	rows, err := s.db.Query(ctx,
		`SELECT type, in_app, email, push FROM notification_preferences WHERE user_id = $1`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	saved := map[string]Preference{}
	for rows.Next() {
		var p Preference
		if err := rows.Scan(&p.Type, &p.InApp, &p.Email, &p.Push); err != nil {
			return nil, err
		}
		saved[p.Type] = p
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	byGroup := map[string][]Preference{}
	for kind, info := range catalogue {
		p := Preference{Type: kind, Label: info.Label, InAppLocked: info.InAppLocked,
			InApp: true, Email: info.Email, Push: info.Push}
		if row, ok := saved[kind]; ok {
			if !info.InAppLocked {
				p.InApp = row.InApp
			}
			p.Email = info.Email && row.Email
			p.Push = info.Push && row.Push
		}
		byGroup[info.Group] = append(byGroup[info.Group], p)
	}
	out := make([]PreferenceGroup, 0, len(groupLabels))
	for _, g := range groupLabels {
		prefs := byGroup[g.Key]
		if len(prefs) == 0 {
			continue
		}
		sortPreferences(prefs)
		out = append(out, PreferenceGroup{Key: g.Key, Label: g.Label, Preferences: prefs})
	}
	return out, nil
}

func sortPreferences(p []Preference) {
	for i := 1; i < len(p); i++ {
		for j := i; j > 0 && p[j].Label < p[j-1].Label; j-- {
			p[j], p[j-1] = p[j-1], p[j]
		}
	}
}

// SavePreference upserts one row. The in-app switch is ignored for a locked
// type: the store, not the handler, is where that rule cannot be bypassed.
func (s *Store) SavePreference(ctx context.Context, userID uuid.UUID, p Preference) error {
	info, ok := catalogue[p.Type]
	if !ok {
		return fmt.Errorf("unknown notification type %q", p.Type)
	}
	inApp := p.InApp
	if info.InAppLocked {
		inApp = true
	}
	_, err := s.db.Exec(ctx, `
		INSERT INTO notification_preferences (user_id, type, in_app, email, push)
		VALUES ($1, $2, $3, $4, $5)
		ON CONFLICT (user_id, type) DO UPDATE
		  SET in_app = EXCLUDED.in_app, email = EXCLUDED.email, push = EXCLUDED.push,
		      updated_at = now()`,
		userID, p.Type, inApp, p.Email, p.Push)
	return err
}

// ── Push subscriptions ──────────────────────────────────────────────────────

type PushSubscription struct {
	Endpoint string `json:"endpoint"`
	P256dh   string `json:"p256dh"`
	Auth     string `json:"auth"`
}

func (s *Store) SavePushSubscription(ctx context.Context, userID uuid.UUID, sub PushSubscription,
	userAgent string) error {

	_, err := s.db.Exec(ctx, `
		INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, user_agent)
		SELECT $1, $2, $3, $4, nullif($5, '')
		WHERE NOT EXISTS (SELECT 1 FROM push_subscriptions WHERE user_id = $1 AND endpoint = $2)`,
		userID, sub.Endpoint, sub.P256dh, sub.Auth, userAgent)
	return err
}

func (s *Store) DeletePushSubscription(ctx context.Context, userID uuid.UUID, endpoint string) error {
	_, err := s.db.Exec(ctx,
		`DELETE FROM push_subscriptions WHERE user_id = $1 AND endpoint = $2`, userID, endpoint)
	return err
}

// ── Delivery queue ──────────────────────────────────────────────────────────

// pendingDelivery is one queued attempt with everything needed to make it.
type pendingDelivery struct {
	ID             uuid.UUID
	NotificationID uuid.UUID
	Channel        string
	Attempts       int
	UserID         uuid.UUID
	Email          string
	FullName       string
	Type           string
	Title          string
	Body           string
	Href           string
	Metadata       map[string]any
}

// claimPending takes a batch of queued deliveries, marking them so a second
// worker skips them. Attempts is incremented on claim so a crash mid-send
// still counts.
func (s *Store) claimPending(ctx context.Context, limit int) ([]pendingDelivery, error) {
	rows, err := s.db.Query(ctx, `
		WITH claimed AS (
		  UPDATE notification_deliveries d
		  SET attempts = attempts + 1, next_attempt_at = now() + interval '10 minutes'
		  WHERE d.id IN (
		    SELECT id FROM notification_deliveries
		    WHERE status IN ('queued', 'failed') AND next_attempt_at <= now()
		      AND channel IN ('email', 'push') AND attempts < 5
		    ORDER BY next_attempt_at
		    FOR UPDATE SKIP LOCKED
		    LIMIT $1)
		  RETURNING d.id, d.notification_id, d.channel, d.attempts)
		SELECT c.id, c.notification_id, c.channel, c.attempts,
		       n.user_id, u.email, u.full_name, n.type, n.title, coalesce(n.body, ''),
		       coalesce(n.href, ''), n.metadata
		FROM claimed c
		JOIN notifications n ON n.id = c.notification_id
		JOIN users u ON u.id = n.user_id`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var out []pendingDelivery
	for rows.Next() {
		var d pendingDelivery
		var metadata []byte
		if err := rows.Scan(&d.ID, &d.NotificationID, &d.Channel, &d.Attempts, &d.UserID,
			&d.Email, &d.FullName, &d.Type, &d.Title, &d.Body, &d.Href, &metadata); err != nil {
			return nil, err
		}
		_ = json.Unmarshal(metadata, &d.Metadata)
		out = append(out, d)
	}
	return out, rows.Err()
}

func (s *Store) finishDelivery(ctx context.Context, id uuid.UUID, status, providerRef, reason string) error {
	_, err := s.db.Exec(ctx, `
		UPDATE notification_deliveries
		SET status = $2, provider_ref = nullif($3, ''), error = nullif($4, ''),
		    sent_at = CASE WHEN $2 = 'sent' THEN now() ELSE sent_at END,
		    next_attempt_at = CASE WHEN $2 = 'failed' THEN next_attempt_at ELSE NULL END
		WHERE id = $1`, id, status, providerRef, reason)
	return err
}

// ── Email log ───────────────────────────────────────────────────────────────

func (s *Store) logEmail(ctx context.Context, userID *uuid.UUID, to, template, subject,
	status, providerRef, reason string) error {

	_, err := s.db.Exec(ctx, `
		INSERT INTO email_log (user_id, to_address, template, subject, status, provider_ref, error, sent_at)
		VALUES ($1, $2, $3, $4, $5, nullif($6, ''), nullif($7, ''),
		        CASE WHEN $5 = 'sent' THEN now() ELSE NULL END)`,
		userID, to, template, subject, status, providerRef, reason)
	return err
}

// Slugs the notifier needs for links. Lookups rather than parameters, so a
// module that only knows an id does not have to learn the URL scheme.
func (s *Store) projectSlug(ctx context.Context, projectID uuid.UUID) string {
	var slug string
	err := s.db.QueryRow(ctx, `SELECT slug FROM projects WHERE id = $1`, projectID).Scan(&slug)
	if errors.Is(err, pgx.ErrNoRows) || err != nil {
		return ""
	}
	return slug
}

func (s *Store) projectTitle(ctx context.Context, projectID uuid.UUID) string {
	var title string
	_ = s.db.QueryRow(ctx, `SELECT title FROM projects WHERE id = $1`, projectID).Scan(&title)
	return title
}

func (s *Store) contractTitle(ctx context.Context, contractID uuid.UUID) string {
	var title string
	_ = s.db.QueryRow(ctx, `SELECT title FROM contracts WHERE id = $1`, contractID).Scan(&title)
	return title
}

func (s *Store) milestoneTitle(ctx context.Context, milestoneID uuid.UUID) string {
	var title string
	_ = s.db.QueryRow(ctx, `SELECT title FROM milestones WHERE id = $1`, milestoneID).Scan(&title)
	return title
}

func (s *Store) userName(ctx context.Context, userID uuid.UUID) string {
	var name string
	_ = s.db.QueryRow(ctx, `SELECT full_name FROM users WHERE id = $1`, userID).Scan(&name)
	return name
}
