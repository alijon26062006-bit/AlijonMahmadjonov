package messaging

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/files"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/logx"
	"github.com/averix/api/internal/platform/validate"
	"github.com/averix/api/internal/security"
)

// Notifier delivers what the socket could not: an email or a push to someone
// who is not looking at the page. Nil until phase 7.
type Notifier interface {
	MessageReceived(ctx context.Context, conversationID, messageID, recipientID uuid.UUID,
		senderName, preview string)
}

// Moderator receives content that needs a human look.
type Moderator interface {
	Flag(ctx context.Context, subjectType string, subjectID uuid.UUID, reason string)
}

// Settings is the runtime configuration read here.
type Settings interface {
	Int(ctx context.Context, key string, fallback int) int
}

type Service struct {
	store     *Store
	files     *files.Store
	hub       *Hub
	settings  Settings
	notifier  Notifier
	moderator Moderator
}

func NewService(store *Store, fileStore *files.Store, hub *Hub, settings Settings,
	notifier Notifier, moderator Moderator) *Service {

	return &Service{
		store: store, files: fileStore, hub: hub, settings: settings,
		notifier: notifier, moderator: moderator,
	}
}

func (s *Service) Hub() *Hub { return s.hub }

// ── Reads ───────────────────────────────────────────────────────────────────

func (s *Service) Inbox(ctx context.Context, id *security.Identity) ([]Card, error) {
	if !id.Authenticated() {
		return nil, httpx.ErrUnauthenticated
	}
	cards, err := s.store.ForUser(ctx, id.UserID, 50)
	if err != nil {
		return nil, httpx.Internalf(err, "list conversations")
	}
	return cards, nil
}

func (s *Service) UnreadTotal(ctx context.Context, id *security.Identity) (int, error) {
	if !id.Authenticated() {
		return 0, httpx.ErrUnauthenticated
	}
	total, err := s.store.UnreadTotal(ctx, id.UserID)
	if err != nil {
		return 0, httpx.Internalf(err, "count unread messages")
	}
	return total, nil
}

// View returns one thread's header.
func (s *Service) View(ctx context.Context, id *security.Identity, conversationID uuid.UUID) (*Conversation, error) {
	membership, err := s.authorise(ctx, id, conversationID)
	if err != nil {
		return nil, err
	}
	conversation, err := s.store.ByID(ctx, conversationID, id.UserID)
	if err != nil {
		return nil, notFound(err, conversationID)
	}
	conversation.CanSend = s.canSend(membership, id)
	return conversation, nil
}

// Messages returns a page of a thread.
func (s *Service) Messages(ctx context.Context, id *security.Identity,
	conversationID uuid.UUID, cursor string, limit int) (*Page, error) {

	if _, err := s.authorise(ctx, id, conversationID); err != nil {
		return nil, err
	}
	page, err := s.store.Messages(ctx, conversationID, id.UserID, cursor, limit)
	if err != nil {
		if strings.Contains(err.Error(), "invalid cursor") {
			return nil, httpx.ErrBadRequest.Wrap(err)
		}
		return nil, httpx.Internalf(err, "read messages")
	}
	s.signAttachments(ctx, page.Messages)
	return page, nil
}

// authorise is the single membership gate. Everything in this package goes
// through it, which is why no endpoint can forget the check.
func (s *Service) authorise(ctx context.Context, id *security.Identity,
	conversationID uuid.UUID) (Membership, error) {

	membership, err := s.store.MembershipOf(ctx, conversationID)
	if err != nil {
		return membership, notFound(err, conversationID)
	}
	if !id.Authenticated() {
		return membership, httpx.ErrUnauthenticated
	}
	if membership.Includes(id.UserID) {
		return membership, nil
	}
	// A moderator investigating a report reads threads through the admin
	// interface, where the access is logged; here, a non-participant simply
	// does not see that the thread exists.
	if id.ActiveRole == security.RoleAdmin {
		return membership, nil
	}
	return membership, httpx.NotFoundf("conversation %s does not exist", conversationID)
}

func (s *Service) canSend(m Membership, id *security.Identity) bool {
	return !m.IsLocked && m.Includes(id.UserID)
}

// signAttachments issues a short-lived URL per attachment.
//
// Signed per read rather than stored: an attachment belongs to the thread, and
// a permanent link would outlive the participant's access to it.
func (s *Service) signAttachments(ctx context.Context, messages []Message) {
	for i := range messages {
		for j := range messages[i].Attachments {
			attachment := &messages[i].Attachments[j]
			file, err := s.files.ByID(ctx, attachment.FileID)
			if err != nil {
				continue
			}
			url, err := s.files.SignedURL(ctx, file, 30*time.Minute)
			if err != nil {
				logx.From(ctx).Warn("messaging: could not sign an attachment URL", "error", err)
				continue
			}
			attachment.URL = url
		}
	}
}

// ── Sending ─────────────────────────────────────────────────────────────────

type SendRequest struct {
	Body         string `json:"body"`
	Kind         string `json:"kind"`
	CodeLanguage string `json:"code_language"`
	ReplyToID    string `json:"reply_to_id"`
	// Ids of files this sender already uploaded. Ownership is re-checked.
	FileIDs []string `json:"file_ids"`
}

func (s *Service) Send(ctx context.Context, id *security.Identity, conversationID uuid.UUID,
	in SendRequest) (*Message, error) {

	membership, err := s.authorise(ctx, id, conversationID)
	if err != nil {
		return nil, err
	}
	if !membership.Includes(id.UserID) {
		// An admin may read a thread but not write in it: a message from a
		// party that the party did not send would corrupt the record a dispute
		// is judged on.
		e := *httpx.ErrForbidden
		e.Message = "You're not a participant in this conversation."
		return nil, &e
	}
	if membership.IsLocked {
		e := *httpx.ErrConflict
		e.Code = "conversation_locked"
		e.Message = "This conversation is closed. It stays readable, but no new messages can be added."
		return nil, &e
	}

	v := validate.New()
	kind := strings.TrimSpace(in.Kind)
	if kind == "" {
		kind = KindText
	}
	kind = v.OneOf("kind", "The message type", kind, KindText, KindCode)

	body := strings.TrimSpace(in.Body)
	if length := len([]rune(body)); length > MaxBodyRunes {
		v.Addf("body", "That message is %d characters. Please keep it under %d — anything longer is better as a file.",
			length, MaxBodyRunes)
	}
	if kind == KindCode && body == "" {
		v.Add("body", "Paste the code you want to share.")
	}

	fileIDs, err := s.resolveAttachments(ctx, id.UserID, in.FileIDs, v)
	if err != nil {
		return nil, err
	}
	if body == "" && len(fileIDs) == 0 {
		v.Add("body", "Write something or attach a file.")
	}

	var replyTo *uuid.UUID
	if raw := strings.TrimSpace(in.ReplyToID); raw != "" {
		parsed, err := uuid.Parse(raw)
		if err != nil {
			v.Add("reply_to_id", "That message reference isn't valid.")
		} else {
			// A reply must point at a message in this same thread, or a
			// crafted id would pull another conversation's message into the
			// client's rendering.
			target, err := s.store.MessageByID(ctx, parsed, id.UserID)
			if err != nil || target.ConversationID != conversationID {
				v.Add("reply_to_id", "You can only reply to a message in this conversation.")
			} else {
				replyTo = &parsed
			}
		}
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	// A flood guard on top of the endpoint's rate limit: the limiter protects
	// the server, this protects the other person's attention.
	perMinute := s.settings.Int(ctx, "messages.max_per_minute", 30)
	recent, err := s.store.CountRecent(ctx, id.UserID, time.Minute)
	if err == nil && recent >= perMinute {
		e := *httpx.ErrRateLimited
		e.Code = "message_flood"
		e.Message = "You're sending messages very quickly. Take a moment and try again."
		e.RetryAfter = 30
		return nil, &e
	}

	messageID, err := s.store.Insert(ctx, NewMessage{
		ConversationID: conversationID,
		SenderID:       id.UserID,
		Kind:           kind,
		Body:           body,
		CodeLanguage:   codeLanguage(kind, in.CodeLanguage),
		ReplyToID:      replyTo,
		FileIDs:        fileIDs,
	})
	if err != nil {
		return nil, httpx.Internalf(err, "send message")
	}

	message, err := s.store.MessageByID(ctx, messageID, id.UserID)
	if err != nil {
		return nil, httpx.Internalf(err, "read the sent message")
	}
	s.signAttachments(ctx, []Message{*message})

	// Contact details in a first message are the classic way to take a deal
	// off-platform before any protection applies. Flagged for a human rather
	// than blocked: sometimes a phone number is genuinely the answer.
	if found := validate.ContactDetails(body); len(found) > 0 && s.moderator != nil {
		s.moderator.Flag(ctx, "message", messageID,
			"contains contact details: "+strings.Join(found, ", "))
	}

	s.fanOut(ctx, membership, message, id)
	return message, nil
}

func codeLanguage(kind, language string) string {
	if kind != KindCode {
		return ""
	}
	language = strings.ToLower(strings.TrimSpace(language))
	if len(language) > 24 {
		return ""
	}
	for _, r := range language {
		if !(r >= 'a' && r <= 'z') && !(r >= '0' && r <= '9') && r != '+' && r != '-' && r != '#' {
			return ""
		}
	}
	return language
}

// resolveAttachments checks that every attached file belongs to the sender and
// was uploaded for a message.
//
// Ownership is the gate here, exactly as it is for a portfolio image: a file
// id is guessable in principle, and this is what makes guessing useless.
func (s *Service) resolveAttachments(ctx context.Context, ownerID uuid.UUID,
	raw []string, v *validate.Errors) ([]uuid.UUID, error) {

	if len(raw) == 0 {
		return nil, nil
	}
	if len(raw) > MaxAttachments {
		v.Addf("file_ids", "You can attach up to %d files to one message.", MaxAttachments)
		return nil, nil
	}

	out := make([]uuid.UUID, 0, len(raw))
	for _, value := range raw {
		parsed, err := uuid.Parse(strings.TrimSpace(value))
		if err != nil {
			v.Add("file_ids", "One of those attachments isn't a valid reference.")
			return nil, nil
		}
		file, err := s.files.OwnedByID(ctx, parsed, ownerID)
		if err != nil {
			// The id is not echoed back: a refusal that confirms which ids
			// exist is a probe's reward.
			v.Add("file_ids", "We couldn't find one of those uploads. Please upload it again.")
			return nil, nil
		}
		if file.Purpose != files.PurposeMessageAttachment {
			v.Add("file_ids", "One of those uploads wasn't made for a message.")
			return nil, nil
		}
		out = append(out, parsed)
	}
	return out, nil
}

// fanOut pushes the message to everyone else on the thread and hands the ones
// who are not connected to the notifier.
func (s *Service) fanOut(ctx context.Context, m Membership, message *Message, sender *security.Identity) {
	preview := message.Body
	if len([]rune(preview)) > 120 {
		preview = string([]rune(preview)[:120]) + "…"
	}

	for _, userID := range m.Participants {
		if userID == sender.UserID {
			continue
		}
		// The recipient's copy is not the sender's: is_mine differs, and
		// sending one struct to both would tell the recipient they wrote it.
		copyForRecipient := *message
		copyForRecipient.IsMine = false
		unread, _ := s.store.UnreadFor(ctx, m.ConversationID, userID)

		if s.hub != nil {
			s.hub.Publish(ctx, []uuid.UUID{userID}, Event{
				Type:           EventMessage,
				ConversationID: m.ConversationID,
				Message:        &copyForRecipient,
				UnreadCount:    &unread,
			})
		}

		// Someone with the thread open has already seen it; someone who is
		// not connected gets an email or a push, once phase 7 wires one in.
		if s.notifier != nil && !m.Muted[userID] && (s.hub == nil || !s.hub.Online(userID)) {
			name := sender.Username
			s.notifier.MessageReceived(ctx, m.ConversationID, message.ID, userID, name, preview)
		}
	}

	// The sender's other devices see their own message appear.
	if s.hub != nil {
		s.hub.Publish(ctx, []uuid.UUID{sender.UserID}, Event{
			Type:           EventMessage,
			ConversationID: m.ConversationID,
			Message:        message,
		})
	}
}

// ── System entries ──────────────────────────────────────────────────────────

// PostSystem writes a milestone or contract event into the thread.
//
// This is what makes the workspace conversation a complete record: the state
// lives on the contract, and the thread carries a line saying when it changed
// and who changed it, without duplicating the state itself.
func (s *Service) PostSystem(ctx context.Context, conversationID uuid.UUID, event string,
	milestoneID *uuid.UUID, payload map[string]any) error {

	messageID, err := s.store.Insert(ctx, NewMessage{
		ConversationID: conversationID,
		Kind:           KindSystem,
		SystemEvent:    event,
		SystemPayload:  payload,
		MilestoneID:    milestoneID,
	})
	if err != nil {
		return fmt.Errorf("post system message: %w", err)
	}

	membership, err := s.store.MembershipOf(ctx, conversationID)
	if err != nil {
		return nil
	}
	message, err := s.store.MessageByID(ctx, messageID, uuid.Nil)
	if err != nil || s.hub == nil {
		return nil
	}
	s.hub.Publish(ctx, membership.Participants, Event{
		Type:           EventMessage,
		ConversationID: conversationID,
		Message:        message,
	})
	return nil
}

// ── Read state ──────────────────────────────────────────────────────────────

func (s *Service) MarkRead(ctx context.Context, id *security.Identity,
	conversationID uuid.UUID) (time.Time, error) {

	membership, err := s.authorise(ctx, id, conversationID)
	if err != nil {
		return time.Time{}, err
	}
	if !membership.Includes(id.UserID) {
		return time.Time{}, httpx.NotFoundf("conversation %s does not exist", conversationID)
	}

	readAt, err := s.store.MarkRead(ctx, conversationID, id.UserID)
	if err != nil {
		return time.Time{}, httpx.Internalf(err, "mark conversation read")
	}

	if s.hub != nil {
		userID := id.UserID
		others := make([]uuid.UUID, 0, len(membership.Participants))
		for _, participant := range membership.Participants {
			if participant != userID {
				others = append(others, participant)
			}
		}
		s.hub.Publish(ctx, others, Event{
			Type:           EventRead,
			ConversationID: conversationID,
			UserID:         &userID,
			ReadAt:         &readAt,
		})
	}
	return readAt, nil
}

func (s *Service) SetMuted(ctx context.Context, id *security.Identity,
	conversationID uuid.UUID, muted bool) error {

	membership, err := s.authorise(ctx, id, conversationID)
	if err != nil {
		return err
	}
	if !membership.Includes(id.UserID) {
		return httpx.NotFoundf("conversation %s does not exist", conversationID)
	}
	if err := s.store.SetMuted(ctx, conversationID, id.UserID, muted); err != nil {
		return httpx.Internalf(err, "update notification preference")
	}
	return nil
}

// Delete removes a message's content. Only its author, and only the content:
// the row stays so replies and the thread's shape survive.
func (s *Service) Delete(ctx context.Context, id *security.Identity, messageID uuid.UUID) error {
	if !id.Authenticated() {
		return httpx.ErrUnauthenticated
	}
	if err := s.store.SoftDelete(ctx, messageID, id.UserID); err != nil {
		if errors.Is(err, ErrNotFound) {
			return httpx.NotFoundf("message %s does not exist", messageID)
		}
		return httpx.Internalf(err, "delete message")
	}
	return nil
}

// ── Starting a thread ───────────────────────────────────────────────────────

// OpenForProposal returns the thread for a proposal, creating it on first use.
//
// Either party may open it, and only those two: this is the one place a
// conversation can begin before a contract exists, and it is anchored to a
// proposal that already went through the proposal rules.
func (s *Service) OpenForProposal(ctx context.Context, id *security.Identity,
	proposalID uuid.UUID) (*Conversation, error) {

	if !id.Authenticated() {
		return nil, httpx.ErrUnauthenticated
	}
	conversationID, err := s.store.EnsureForProposal(ctx, proposalID)
	if err != nil {
		if errors.Is(err, ErrNotFound) {
			return nil, httpx.NotFoundf("proposal %s does not exist", proposalID)
		}
		return nil, httpx.Internalf(err, "open conversation")
	}
	// The membership check happens after creation deliberately: the thread's
	// participants are the proposal's two parties, so a stranger who reaches
	// here gets a 404 from the same gate as everyone else.
	return s.View(ctx, id, conversationID)
}

func notFound(err error, conversationID uuid.UUID) error {
	if errors.Is(err, ErrNotFound) {
		return httpx.NotFoundf("conversation %s does not exist", conversationID)
	}
	return httpx.Internalf(err, "load conversation")
}
