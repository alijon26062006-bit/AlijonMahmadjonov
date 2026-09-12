// Package messaging is the conversation attached to work.
//
// Every thread is anchored: to a proposal before hiring, to a contract after.
// There is no way to start a conversation with someone because you liked their
// profile, and no global inbox — which is the whole point. AVERIX is where work
// is agreed and delivered, not a social messenger, and the schema enforces
// that rather than the interface merely discouraging it.
package messaging

import (
	"time"

	"github.com/google/uuid"
)

// Conversation is one thread.
type Conversation struct {
	ID uuid.UUID `json:"id"`
	// Exactly one of these anchors it, and both are shown so the interface can
	// link back to the work.
	ProjectID  *uuid.UUID `json:"project_id,omitempty"`
	ContractID *uuid.UUID `json:"contract_id,omitempty"`
	ProposalID *uuid.UUID `json:"proposal_id,omitempty"`

	Subject       string     `json:"subject,omitempty"`
	Participants  []Person   `json:"participants"`
	IsLocked      bool       `json:"is_locked"`
	MessageCount  int        `json:"message_count"`
	LastMessageAt *time.Time `json:"last_message_at,omitempty"`
	UnreadCount   int        `json:"unread_count"`
	// Whether the caller may write here at all, so the composer can be
	// disabled rather than failing on send.
	CanSend   bool      `json:"can_send"`
	CreatedAt time.Time `json:"created_at"`
}

// Card is the list row.
type Card struct {
	ID uuid.UUID `json:"id"`
	// The other person, which is who the reader thinks of the thread as.
	Counterparty  Person     `json:"counterparty"`
	Subject       string     `json:"subject,omitempty"`
	ContractID    *uuid.UUID `json:"contract_id,omitempty"`
	ProjectID     *uuid.UUID `json:"project_id,omitempty"`
	ProjectTitle  string     `json:"project_title,omitempty"`
	Preview       string     `json:"preview,omitempty"`
	UnreadCount   int        `json:"unread_count"`
	LastMessageAt *time.Time `json:"last_message_at,omitempty"`
}

// Message is one entry in a thread.
type Message struct {
	ID             uuid.UUID  `json:"id"`
	ConversationID uuid.UUID  `json:"conversation_id"`
	Sender         *Person    `json:"sender,omitempty"`
	Kind           string     `json:"kind"`
	Body           string     `json:"body,omitempty"`
	CodeLanguage   string     `json:"code_language,omitempty"`
	ReplyToID      *uuid.UUID `json:"reply_to_id,omitempty"`

	// A system entry carries the event rather than prose, so the client can
	// render it as a status line and translate it.
	SystemEvent   string         `json:"system_event,omitempty"`
	SystemPayload map[string]any `json:"system_payload,omitempty"`
	MilestoneID   *uuid.UUID     `json:"milestone_id,omitempty"`

	Attachments []Attachment `json:"attachments,omitempty"`
	EditedAt    *time.Time   `json:"edited_at,omitempty"`
	IsDeleted   bool         `json:"is_deleted,omitempty"`
	// Whether the caller wrote it, so the bubble knows which side it is on.
	IsMine    bool        `json:"is_mine"`
	ReadBy    []uuid.UUID `json:"read_by,omitempty"`
	CreatedAt time.Time   `json:"created_at"`
}

// Attachment is a file on a message. The URL is signed per request and short
// lived: an attachment is the thread's business, not the internet's.
type Attachment struct {
	ID       uuid.UUID `json:"id"`
	FileID   uuid.UUID `json:"file_id"`
	Name     string    `json:"name"`
	ByteSize int64     `json:"byte_size"`
	MIME     string    `json:"mime"`
	URL      string    `json:"url,omitempty"`
	Width    *int      `json:"width,omitempty"`
	Height   *int      `json:"height,omitempty"`
	IsImage  bool      `json:"is_image"`
}

type Person struct {
	ID       uuid.UUID `json:"id"`
	Username string    `json:"username"`
	FullName string    `json:"full_name"`
	PhotoURL string    `json:"photo_url,omitempty"`
	Role     string    `json:"role,omitempty"`
}

// Page is a keyset page of messages, oldest first within the page.
type Page struct {
	Messages []Message `json:"messages"`
	// Cursor to pass back for the previous (older) page, empty when the start
	// of the thread has been reached.
	NextCursor string `json:"next_cursor,omitempty"`
	HasMore    bool   `json:"has_more"`
}

// Message kinds, matching the database's CHECK constraint.
const (
	KindText         = "text"
	KindCode         = "code"
	KindSystem       = "system"
	KindMilestoneRef = "milestone_ref"
	KindProjectRef   = "project_ref"
)

// Realtime event types pushed over the socket. Deliberately few: a message
// arriving, a message read, and a thread's state changing. No presence, no
// typing indicators, no reactions — this is a work thread.
const (
	EventMessage      = "message"
	EventRead         = "read"
	EventConversation = "conversation"
)

// Event is one realtime frame.
type Event struct {
	Type           string    `json:"type"`
	ConversationID uuid.UUID `json:"conversation_id"`
	Message        *Message  `json:"message,omitempty"`
	// For a read event: who read, and up to when.
	UserID *uuid.UUID `json:"user_id,omitempty"`
	ReadAt *time.Time `json:"read_at,omitempty"`
	// The recipient's own unread count after this event, so the badge does not
	// need a second request.
	UnreadCount *int      `json:"unread_count,omitempty"`
	SentAt      time.Time `json:"sent_at"`
}

// MaxBodyRunes is the longest message the product accepts.
//
// Generous enough for a real explanation of a bug, short enough that the
// thread stays readable on a phone. Anything longer belongs in a file.
const MaxBodyRunes = 8000

// MaxAttachments per message.
const MaxAttachments = 10
