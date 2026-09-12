package messaging

import (
	"context"
	"encoding/base64"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/database"
)

type Store struct {
	db        *database.DB
	publicURL func(string) string
}

func NewStore(db *database.DB, publicURL func(string) string) *Store {
	if publicURL == nil {
		publicURL = func(key string) string { return key }
	}
	return &Store{db: db, publicURL: publicURL}
}

var (
	ErrNotFound = errors.New("conversation not found")
	ErrLocked   = errors.New("conversation is locked")
)

// ── Membership ──────────────────────────────────────────────────────────────

// Membership is who is on a thread and what they may do, which is the answer
// to every authorisation question in this package.
type Membership struct {
	ConversationID uuid.UUID
	ContractID     *uuid.UUID
	ProjectID      *uuid.UUID
	IsLocked       bool
	Participants   []uuid.UUID
	Muted          map[uuid.UUID]bool
}

func (m Membership) Includes(userID uuid.UUID) bool {
	for _, id := range m.Participants {
		if id == userID {
			return true
		}
	}
	return false
}

func (s *Store) MembershipOf(ctx context.Context, conversationID uuid.UUID) (Membership, error) {
	m := Membership{ConversationID: conversationID, Muted: map[uuid.UUID]bool{}}
	err := s.db.QueryRow(ctx,
		`SELECT contract_id, project_id, is_locked FROM conversations WHERE id = $1`,
		conversationID).Scan(&m.ContractID, &m.ProjectID, &m.IsLocked)
	if database.IsNoRows(err) {
		return m, ErrNotFound
	}
	if err != nil {
		return m, fmt.Errorf("load conversation: %w", err)
	}

	rows, err := s.db.Query(ctx,
		`SELECT user_id, muted FROM conversation_participants WHERE conversation_id = $1`,
		conversationID)
	if err != nil {
		return m, fmt.Errorf("load conversation participants: %w", err)
	}
	defer rows.Close()
	for rows.Next() {
		var userID uuid.UUID
		var muted bool
		if err := rows.Scan(&userID, &muted); err != nil {
			return m, err
		}
		m.Participants = append(m.Participants, userID)
		m.Muted[userID] = muted
	}
	return m, rows.Err()
}

// ── Threads ─────────────────────────────────────────────────────────────────

// EnsureForProposal returns the thread for a proposal, creating it the first
// time either party writes.
//
// Created on demand rather than with every proposal: a project with forty
// proposals should not get forty empty threads in the client's list.
func (s *Store) EnsureForProposal(ctx context.Context, proposalID uuid.UUID) (uuid.UUID, error) {
	var conversationID uuid.UUID
	err := s.db.InTx(ctx, func(q database.Querier) error {
		var projectID, clientID, developerID uuid.UUID
		var subject string
		err := q.QueryRow(ctx, `
			SELECT pr.project_id, pj.client_id, pr.developer_id, pj.title
			FROM proposals pr JOIN projects pj ON pj.id = pr.project_id
			WHERE pr.id = $1`, proposalID).
			Scan(&projectID, &clientID, &developerID, &subject)
		if database.IsNoRows(err) {
			return ErrNotFound
		}
		if err != nil {
			return err
		}

		err = q.QueryRow(ctx,
			`SELECT id FROM conversations WHERE proposal_id = $1`, proposalID).Scan(&conversationID)
		if err == nil {
			return nil
		}
		if !database.IsNoRows(err) {
			return err
		}

		if err := q.QueryRow(ctx, `
			INSERT INTO conversations (project_id, proposal_id, subject)
			VALUES ($1, $2, $3) RETURNING id`,
			projectID, proposalID, subject).Scan(&conversationID); err != nil {
			return fmt.Errorf("create proposal conversation: %w", err)
		}
		for _, userID := range []uuid.UUID{clientID, developerID} {
			if _, err := q.Exec(ctx, `
				INSERT INTO conversation_participants (conversation_id, user_id)
				VALUES ($1, $2) ON CONFLICT DO NOTHING`, conversationID, userID); err != nil {
				return err
			}
		}
		return nil
	})
	return conversationID, err
}

func (s *Store) ByID(ctx context.Context, conversationID, viewerID uuid.UUID) (*Conversation, error) {
	var c Conversation
	err := s.db.QueryRow(ctx, `
		SELECT cv.id, cv.project_id, cv.contract_id, cv.proposal_id,
		       coalesce(cv.subject, ''), cv.is_locked, cv.message_count,
		       cv.last_message_at, cv.created_at,
		       coalesce(cvp.unread_count, 0)
		FROM conversations cv
		LEFT JOIN conversation_participants cvp
		       ON cvp.conversation_id = cv.id AND cvp.user_id = $2
		WHERE cv.id = $1`, conversationID, viewerID).
		Scan(&c.ID, &c.ProjectID, &c.ContractID, &c.ProposalID, &c.Subject,
			&c.IsLocked, &c.MessageCount, &c.LastMessageAt, &c.CreatedAt, &c.UnreadCount)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("load conversation: %w", err)
	}

	people, err := s.peopleFor(ctx, conversationID)
	if err != nil {
		return nil, err
	}
	c.Participants = people
	return &c, nil
}

func (s *Store) peopleFor(ctx context.Context, conversationID uuid.UUID) ([]Person, error) {
	rows, err := s.db.Query(ctx, `
		SELECT u.id, u.username, u.full_name, ph.derivatives,
		       coalesce(cp.role, '')
		FROM conversation_participants cvp
		JOIN users u ON u.id = cvp.user_id
		LEFT JOIN developer_photos ph ON ph.user_id = u.id AND ph.is_current
		LEFT JOIN conversations cv ON cv.id = cvp.conversation_id
		LEFT JOIN contract_participants cp
		       ON cp.contract_id = cv.contract_id AND cp.user_id = u.id
		WHERE cvp.conversation_id = $1
		ORDER BY cvp.created_at`, conversationID)
	if err != nil {
		return nil, fmt.Errorf("load conversation people: %w", err)
	}
	defer rows.Close()

	out := []Person{}
	for rows.Next() {
		var person Person
		var photo map[string]map[string]string
		if err := rows.Scan(&person.ID, &person.Username, &person.FullName,
			&photo, &person.Role); err != nil {
			return nil, err
		}
		person.PhotoURL = s.avatarURL(photo)
		out = append(out, person)
	}
	return out, rows.Err()
}

func (s *Store) avatarURL(derivatives map[string]map[string]string) string {
	for _, format := range []string{"webp", "jpeg"} {
		sizes, ok := derivatives[format]
		if !ok {
			continue
		}
		if key, ok := sizes["64"]; ok {
			return s.publicURL(key)
		}
		for _, key := range sizes {
			return s.publicURL(key)
		}
	}
	return ""
}

// ForUser lists a person's threads, most recent activity first.
func (s *Store) ForUser(ctx context.Context, userID uuid.UUID, limit int) ([]Card, error) {
	if limit <= 0 || limit > 100 {
		limit = 30
	}
	rows, err := s.db.Query(ctx, `
		SELECT cv.id, coalesce(cv.subject, ''), cv.contract_id, cv.project_id,
		       coalesce(pj.title, ''), cvp.unread_count, cv.last_message_at,
		       other.id, other.username, other.full_name, oph.derivatives,
		       coalesce((
		         SELECT CASE
		                  WHEN m.deleted_at IS NOT NULL THEN ''
		                  WHEN m.kind = 'system' THEN coalesce(m.system_event, '')
		                  ELSE left(coalesce(m.body, ''), 120)
		                END
		         FROM messages m WHERE m.conversation_id = cv.id
		         ORDER BY m.created_at DESC LIMIT 1), '')
		FROM conversation_participants cvp
		JOIN conversations cv ON cv.id = cvp.conversation_id
		LEFT JOIN projects pj ON pj.id = cv.project_id
		LEFT JOIN LATERAL (
		  SELECT u.id, u.username, u.full_name
		  FROM conversation_participants other_cvp
		  JOIN users u ON u.id = other_cvp.user_id
		  WHERE other_cvp.conversation_id = cv.id AND other_cvp.user_id <> $1
		  ORDER BY other_cvp.created_at
		  LIMIT 1
		) other ON true
		LEFT JOIN developer_photos oph ON oph.user_id = other.id AND oph.is_current
		WHERE cvp.user_id = $1 AND cv.last_message_at IS NOT NULL
		ORDER BY cv.last_message_at DESC
		LIMIT $2`, userID, limit)
	if err != nil {
		return nil, fmt.Errorf("list conversations: %w", err)
	}
	defer rows.Close()

	out := []Card{}
	for rows.Next() {
		var card Card
		var photo map[string]map[string]string
		var otherID *uuid.UUID
		var username, fullName *string
		if err := rows.Scan(&card.ID, &card.Subject, &card.ContractID, &card.ProjectID,
			&card.ProjectTitle, &card.UnreadCount, &card.LastMessageAt,
			&otherID, &username, &fullName, &photo, &card.Preview); err != nil {
			return nil, fmt.Errorf("scan conversation card: %w", err)
		}
		if otherID != nil {
			card.Counterparty = Person{
				ID: *otherID, Username: deref(username), FullName: deref(fullName),
				PhotoURL: s.avatarURL(photo),
			}
		}
		out = append(out, card)
	}
	return out, rows.Err()
}

func (s *Store) UnreadTotal(ctx context.Context, userID uuid.UUID) (int, error) {
	var total int
	err := s.db.QueryRow(ctx,
		`SELECT coalesce(sum(unread_count), 0) FROM conversation_participants WHERE user_id = $1`,
		userID).Scan(&total)
	return total, err
}

// ── Messages ────────────────────────────────────────────────────────────────

// Messages reads a page, newest first, with a keyset cursor.
//
// Keyset rather than OFFSET: a thread people are writing in shifts under an
// offset, which shows duplicates and skips messages.
func (s *Store) Messages(ctx context.Context, conversationID, viewerID uuid.UUID,
	cursor string, limit int) (*Page, error) {

	if limit <= 0 || limit > 100 {
		limit = 40
	}
	before, beforeID, err := decodeCursor(cursor)
	if err != nil {
		return nil, err
	}

	condition := ""
	args := []any{conversationID, limit + 1}
	if beforeID != uuid.Nil {
		condition = " AND (m.created_at, m.id) < ($3, $4)"
		args = append(args, before, beforeID)
	}

	rows, err := s.db.Query(ctx, `
		SELECT m.id, m.conversation_id, m.kind, coalesce(m.body, ''),
		       coalesce(m.code_language, ''), m.reply_to_id, m.milestone_id,
		       coalesce(m.system_event, ''), m.system_payload,
		       m.edited_at, m.deleted_at, m.created_at,
		       u.id, u.username, u.full_name, ph.derivatives
		FROM messages m
		LEFT JOIN users u ON u.id = m.sender_id
		LEFT JOIN developer_photos ph ON ph.user_id = u.id AND ph.is_current
		WHERE m.conversation_id = $1`+condition+`
		ORDER BY m.created_at DESC, m.id DESC
		LIMIT $2`, args...)
	if err != nil {
		return nil, fmt.Errorf("query messages: %w", err)
	}
	defer rows.Close()

	page := &Page{Messages: []Message{}}
	ids := []uuid.UUID{}
	for rows.Next() {
		var m Message
		var senderID *uuid.UUID
		var username, fullName *string
		var photo map[string]map[string]string
		var deletedAt *time.Time
		if err := rows.Scan(&m.ID, &m.ConversationID, &m.Kind, &m.Body,
			&m.CodeLanguage, &m.ReplyToID, &m.MilestoneID, &m.SystemEvent,
			&m.SystemPayload, &m.EditedAt, &deletedAt, &m.CreatedAt,
			&senderID, &username, &fullName, &photo); err != nil {
			return nil, fmt.Errorf("scan message: %w", err)
		}
		if senderID != nil {
			m.Sender = &Person{
				ID: *senderID, Username: deref(username), FullName: deref(fullName),
				PhotoURL: s.avatarURL(photo),
			}
			m.IsMine = *senderID == viewerID
		}
		if deletedAt != nil {
			// The row stays so the thread's shape is preserved, but its
			// content does not come back.
			m.IsDeleted = true
			m.Body, m.CodeLanguage = "", ""
		}
		page.Messages = append(page.Messages, m)
		ids = append(ids, m.ID)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	if len(page.Messages) > limit {
		page.Messages = page.Messages[:limit]
		ids = ids[:limit]
		page.HasMore = true
		last := page.Messages[len(page.Messages)-1]
		page.NextCursor = encodeCursor(last.CreatedAt, last.ID)
	}

	if len(ids) > 0 {
		attachments, err := s.attachmentsFor(ctx, ids)
		if err != nil {
			return nil, err
		}
		for i := range page.Messages {
			page.Messages[i].Attachments = attachments[page.Messages[i].ID]
		}
	}

	// Oldest first within the page: that is the order a thread reads in.
	for i, j := 0, len(page.Messages)-1; i < j; i, j = i+1, j-1 {
		page.Messages[i], page.Messages[j] = page.Messages[j], page.Messages[i]
	}
	return page, nil
}

func (s *Store) attachmentsFor(ctx context.Context, messageIDs []uuid.UUID) (map[uuid.UUID][]Attachment, error) {
	rows, err := s.db.Query(ctx, `
		SELECT ma.message_id, ma.id, ma.file_id, f.original_name, f.byte_size,
		       f.detected_mime, f.width, f.height
		FROM message_attachments ma
		JOIN files f ON f.id = ma.file_id AND f.deleted_at IS NULL
		WHERE ma.message_id = ANY($1)
		ORDER BY ma.sort_order`, messageIDs)
	if err != nil {
		return nil, fmt.Errorf("query attachments: %w", err)
	}
	defer rows.Close()

	out := map[uuid.UUID][]Attachment{}
	for rows.Next() {
		var messageID uuid.UUID
		var a Attachment
		if err := rows.Scan(&messageID, &a.ID, &a.FileID, &a.Name, &a.ByteSize,
			&a.MIME, &a.Width, &a.Height); err != nil {
			return nil, err
		}
		a.IsImage = strings.HasPrefix(a.MIME, "image/")
		out[messageID] = append(out[messageID], a)
	}
	return out, rows.Err()
}

// NewMessage is one message to write.
type NewMessage struct {
	ConversationID uuid.UUID
	SenderID       uuid.UUID
	Kind           string
	Body           string
	CodeLanguage   string
	ReplyToID      *uuid.UUID
	MilestoneID    *uuid.UUID
	SystemEvent    string
	SystemPayload  map[string]any
	FileIDs        []uuid.UUID
}

// Insert writes a message and its attachments in one transaction.
//
// One transaction because the "a message must say something" rule is a
// deferred constraint trigger: the attachments have to be visible before the
// commit, or a message carrying only a file would be rejected.
func (s *Store) Insert(ctx context.Context, in NewMessage) (uuid.UUID, error) {
	var messageID uuid.UUID
	err := s.db.InTx(ctx, func(q database.Querier) error {
		var payload any
		if len(in.SystemPayload) > 0 {
			payload = in.SystemPayload
		}
		err := q.QueryRow(ctx, `
			INSERT INTO messages
			  (conversation_id, sender_id, kind, body, code_language, reply_to_id,
			   milestone_id, system_event, system_payload)
			VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
			RETURNING id`,
			in.ConversationID, senderOrNil(in.SenderID), in.Kind,
			nullIfBlank(in.Body), nullIfBlank(in.CodeLanguage), in.ReplyToID,
			in.MilestoneID, nullIfBlank(in.SystemEvent), payload).Scan(&messageID)
		if err != nil {
			return fmt.Errorf("insert message: %w", err)
		}

		for position, fileID := range in.FileIDs {
			if _, err := q.Exec(ctx, `
				INSERT INTO message_attachments (message_id, file_id, sort_order)
				VALUES ($1, $2, $3)`, messageID, fileID, position); err != nil {
				return fmt.Errorf("attach file: %w", err)
			}
		}
		return nil
	})
	return messageID, err
}

// MessageByID reads one message back, which is what the realtime fan-out sends.
func (s *Store) MessageByID(ctx context.Context, messageID, viewerID uuid.UUID) (*Message, error) {
	var m Message
	var senderID *uuid.UUID
	var username, fullName *string
	var photo map[string]map[string]string
	var deletedAt *time.Time

	err := s.db.QueryRow(ctx, `
		SELECT m.id, m.conversation_id, m.kind, coalesce(m.body, ''),
		       coalesce(m.code_language, ''), m.reply_to_id, m.milestone_id,
		       coalesce(m.system_event, ''), m.system_payload,
		       m.edited_at, m.deleted_at, m.created_at,
		       u.id, u.username, u.full_name, ph.derivatives
		FROM messages m
		LEFT JOIN users u ON u.id = m.sender_id
		LEFT JOIN developer_photos ph ON ph.user_id = u.id AND ph.is_current
		WHERE m.id = $1`, messageID).
		Scan(&m.ID, &m.ConversationID, &m.Kind, &m.Body, &m.CodeLanguage,
			&m.ReplyToID, &m.MilestoneID, &m.SystemEvent, &m.SystemPayload,
			&m.EditedAt, &deletedAt, &m.CreatedAt,
			&senderID, &username, &fullName, &photo)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("load message: %w", err)
	}
	if senderID != nil {
		m.Sender = &Person{
			ID: *senderID, Username: deref(username), FullName: deref(fullName),
			PhotoURL: s.avatarURL(photo),
		}
		m.IsMine = *senderID == viewerID
	}
	if deletedAt != nil {
		m.IsDeleted = true
		m.Body = ""
	}

	attachments, err := s.attachmentsFor(ctx, []uuid.UUID{messageID})
	if err != nil {
		return nil, err
	}
	m.Attachments = attachments[messageID]
	return &m, nil
}

// SoftDelete removes a message's content, keeping the row so the thread's
// shape and any reply that points at it survive.
func (s *Store) SoftDelete(ctx context.Context, messageID, senderID uuid.UUID) error {
	tag, err := s.db.Exec(ctx, `
		UPDATE messages SET deleted_at = now(), body = NULL
		WHERE id = $1 AND sender_id = $2 AND deleted_at IS NULL`, messageID, senderID)
	if err != nil {
		return fmt.Errorf("delete message: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

// MarkRead clears a participant's unread counter and records receipts.
func (s *Store) MarkRead(ctx context.Context, conversationID, userID uuid.UUID) (time.Time, error) {
	var readAt time.Time
	err := s.db.InTx(ctx, func(q database.Querier) error {
		err := q.QueryRow(ctx, `
			UPDATE conversation_participants
			   SET last_read_at = now(), unread_count = 0
			 WHERE conversation_id = $1 AND user_id = $2
			RETURNING last_read_at`, conversationID, userID).Scan(&readAt)
		if database.IsNoRows(err) {
			return ErrNotFound
		}
		if err != nil {
			return fmt.Errorf("mark conversation read: %w", err)
		}

		// Receipts for what was actually read, so "seen" is a fact rather than
		// an assumption about when someone had the window open.
		if _, err := q.Exec(ctx, `
			INSERT INTO message_receipts (message_id, user_id)
			SELECT m.id, $2 FROM messages m
			WHERE m.conversation_id = $1 AND (m.sender_id IS NULL OR m.sender_id <> $2)
			ON CONFLICT DO NOTHING`, conversationID, userID); err != nil {
			return fmt.Errorf("record read receipts: %w", err)
		}
		return nil
	})
	return readAt, err
}

func (s *Store) UnreadFor(ctx context.Context, conversationID, userID uuid.UUID) (int, error) {
	var unread int
	err := s.db.QueryRow(ctx, `
		SELECT unread_count FROM conversation_participants
		WHERE conversation_id = $1 AND user_id = $2`, conversationID, userID).Scan(&unread)
	if database.IsNoRows(err) {
		return 0, nil
	}
	return unread, err
}

func (s *Store) SetMuted(ctx context.Context, conversationID, userID uuid.UUID, muted bool) error {
	tag, err := s.db.Exec(ctx, `
		UPDATE conversation_participants SET muted = $3
		WHERE conversation_id = $1 AND user_id = $2`, conversationID, userID, muted)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

// CountRecent counts a sender's messages in a window, for the flood guard.
func (s *Store) CountRecent(ctx context.Context, senderID uuid.UUID, window time.Duration) (int, error) {
	var n int
	err := s.db.QueryRow(ctx, `
		SELECT count(*) FROM messages
		WHERE sender_id = $1 AND created_at > now() - $2::interval`,
		senderID, fmt.Sprintf("%d seconds", int(window.Seconds()))).Scan(&n)
	return n, err
}

// ── Cursor ──────────────────────────────────────────────────────────────────

// The cursor carries the sort key, not an offset, and is opaque so a client
// cannot construct one that reads outside the thread.
func encodeCursor(at time.Time, id uuid.UUID) string {
	raw := strconv.FormatInt(at.UTC().UnixMicro(), 10) + ":" + id.String()
	return base64.RawURLEncoding.EncodeToString([]byte(raw))
}

func decodeCursor(cursor string) (time.Time, uuid.UUID, error) {
	if strings.TrimSpace(cursor) == "" {
		return time.Time{}, uuid.Nil, nil
	}
	raw, err := base64.RawURLEncoding.DecodeString(cursor)
	if err != nil {
		return time.Time{}, uuid.Nil, fmt.Errorf("invalid cursor")
	}
	parts := strings.SplitN(string(raw), ":", 2)
	if len(parts) != 2 {
		return time.Time{}, uuid.Nil, fmt.Errorf("invalid cursor")
	}
	micros, err := strconv.ParseInt(parts[0], 10, 64)
	if err != nil {
		return time.Time{}, uuid.Nil, fmt.Errorf("invalid cursor")
	}
	id, err := uuid.Parse(parts[1])
	if err != nil {
		return time.Time{}, uuid.Nil, fmt.Errorf("invalid cursor")
	}
	return time.UnixMicro(micros).UTC(), id, nil
}

func senderOrNil(id uuid.UUID) any {
	if id == uuid.Nil {
		return nil
	}
	return id
}

func nullIfBlank(s string) any {
	if strings.TrimSpace(s) == "" {
		return nil
	}
	return s
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}
