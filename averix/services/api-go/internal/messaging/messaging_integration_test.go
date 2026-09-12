package messaging_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"mime/multipart"
	"net/http"
	"net/textproto"
	"strings"
	"testing"
	"time"

	"github.com/gorilla/websocket"

	"github.com/averix/api/internal/platform/testsupport"
)

// workspace hires a developer and returns the contract's conversation.
func workspace(t *testing.T, h *testsupport.Harness) (conversationID string,
	client *testsupport.ClientAccount, dev *testsupport.Developer) {

	t.Helper()
	client = h.NewClient("acmeco")
	projectID := h.PublishProject(client, "Telegram bot for an online clothing store",
		"telegram-bots", []string{"python", "telegram-api", "postgresql"}, 50000, 80000)
	dev = h.PublishDeveloper("telegramdev", "telegram-developer",
		"python", "telegram-api", "postgresql")

	proposalID := dev.Client.POST("/proposals", proposal(projectID)).
		OK(t, http.StatusCreated).String("id")
	client.Client.POST("/contracts", map[string]any{"proposal_id": proposalID}).
		OK(t, http.StatusCreated)

	var id string
	h.QueryRow([]any{&id}, `SELECT id::text FROM conversations WHERE contract_id IS NOT NULL`)
	if id == "" {
		t.Fatal("hiring did not open a workspace conversation")
	}
	return id, client, dev
}

func proposal(projectID string) map[string]any {
	return map[string]any{
		"project_id":    projectID,
		"amount_minor":  65000,
		"currency":      "USD",
		"delivery_days": 12,
		"cover_letter": "I have built three Telegram commerce bots, the most recent one " +
			"for a clothing retailer with about 400 orders a month. Your catalogue and " +
			"cart requirements map closely onto that, and the payment step is the part " +
			"I would want to agree in detail before starting.",
		"approach": "I would start with the data model for products, orders and " +
			"customers, then the admin side so your staff can load the catalogue while " +
			"I build the customer flow. Payment goes in after the cart works end to end.",
		"relevant_experience": "Six years of Python, most of it on Telegram bots and " +
			"backend services with PostgreSQL behind them.",
	}
}

// ── The thread itself ───────────────────────────────────────────────────────

func TestHiringOpensTheWorkspaceThread(t *testing.T) {
	h := testsupport.New(t)
	conversationID, client, dev := workspace(t, h)

	res := client.Client.GET("/conversations/"+conversationID).OK(t, http.StatusOK)
	if res.Data["contract_id"] == nil {
		t.Error("the workspace thread should be anchored to the contract")
	}
	if !res.Bool("can_send") {
		t.Error("a party to the contract should be able to write in it")
	}
	participants, _ := res.Data["participants"].([]any)
	if len(participants) != 2 {
		t.Errorf("got %d participants, want the client and the developer", len(participants))
	}

	// The thread already carries the contract's own events, so the
	// conversation is a complete record of what happened.
	page := dev.Client.GET("/conversations/"+conversationID+"/messages").OK(t, http.StatusOK)
	messages, _ := page.Data["messages"].([]any)
	if len(messages) == 0 {
		t.Fatal("the workspace thread should open with the contract event")
	}
	first, _ := messages[0].(map[string]any)
	if first["kind"] != "system" || first["system_event"] != "contract.signed" {
		t.Errorf("first entry = %v, want the contract.signed system event", first)
	}
}

// There is no free-floating inbox: a conversation only exists against work.
func TestAStrangerCannotOpenOrReadAThread(t *testing.T) {
	h := testsupport.New(t)
	conversationID, _, _ := workspace(t, h)

	stranger := h.PublishDeveloper("nosydev", "backend-developer")
	stranger.Client.GET("/conversations/"+conversationID).
		Fails(t, http.StatusNotFound, "not_found")
	stranger.Client.GET("/conversations/"+conversationID+"/messages").
		Fails(t, http.StatusNotFound, "not_found")
	stranger.Client.POST("/conversations/"+conversationID+"/messages", map[string]any{
		"body": "Hello, I would like to work on this project too.",
	}).Fails(t, http.StatusNotFound, "not_found")

	// And there is no endpoint that starts a conversation with a person.
	stranger.Client.POST("/conversations", map[string]any{
		"username": "telegramdev", "body": "hi",
	}).Fails(t, http.StatusNotFound, "not_found")
}

// ── Sending ─────────────────────────────────────────────────────────────────

func TestSendingAndReadingAMessage(t *testing.T) {
	h := testsupport.New(t)
	conversationID, client, dev := workspace(t, h)

	sent := client.Client.POST("/conversations/"+conversationID+"/messages", map[string]any{
		"body": "Morning — the product photos are in the shared drive now.",
	}).OK(t, http.StatusCreated)
	if !sent.Bool("is_mine") {
		t.Error("the sender should be told the message is theirs")
	}

	// The developer has an unread message.
	unread := dev.Client.GET("/conversations/unread").OK(t, http.StatusOK)
	if unread.Float("unread") != 1 {
		t.Errorf("unread = %v, want 1", unread.Data["unread"])
	}

	page := dev.Client.GET("/conversations/"+conversationID+"/messages").OK(t, http.StatusOK)
	messages, _ := page.Data["messages"].([]any)
	last, _ := messages[len(messages)-1].(map[string]any)
	if last["body"] != "Morning — the product photos are in the shared drive now." {
		t.Errorf("last message = %v", last["body"])
	}
	if last["is_mine"] == true {
		t.Error("the recipient must not be told they wrote it")
	}

	dev.Client.POST("/conversations/"+conversationID+"/read", nil).OK(t, http.StatusOK)
	unread = dev.Client.GET("/conversations/unread").OK(t, http.StatusOK)
	if unread.Float("unread") != 0 {
		t.Errorf("after reading, unread = %v, want 0", unread.Data["unread"])
	}

	// The inbox shows the thread with a preview of the last line.
	inbox := dev.Client.GET("/conversations").OK(t, http.StatusOK)
	if len(inbox.List) != 1 {
		t.Fatalf("the developer sees %d threads, want 1", len(inbox.List))
	}
	card, _ := inbox.List[0].(map[string]any)
	counterparty, _ := card["counterparty"].(map[string]any)
	if counterparty["username"] != "acmeco" {
		t.Errorf("counterparty = %v, want the client", counterparty["username"])
	}
	if preview, _ := card["preview"].(string); !strings.Contains(preview, "product photos") {
		t.Errorf("preview = %q", preview)
	}
}

func TestAMessageMustSaySomething(t *testing.T) {
	h := testsupport.New(t)
	conversationID, client, _ := workspace(t, h)

	client.Client.POST("/conversations/"+conversationID+"/messages", map[string]any{"body": "   "}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	client.Client.POST("/conversations/"+conversationID+"/messages", map[string]any{
		"body": strings.Repeat("a", 8001),
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	client.Client.POST("/conversations/"+conversationID+"/messages", map[string]any{
		"kind": "code", "body": "",
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
}

func TestReplyingOnlyWorksWithinTheSameThread(t *testing.T) {
	h := testsupport.New(t)
	conversationID, client, dev := workspace(t, h)

	mine := client.Client.POST("/conversations/"+conversationID+"/messages", map[string]any{
		"body": "Question about the catalogue import format.",
	}).OK(t, http.StatusCreated).String("id")

	res := dev.Client.POST("/conversations/"+conversationID+"/messages", map[string]any{
		"body": "CSV with a header row works best.", "reply_to_id": mine,
	}).OK(t, http.StatusCreated)
	if res.String("reply_to_id") != mine {
		t.Errorf("reply_to_id = %q, want %q", res.String("reply_to_id"), mine)
	}

	// A message from another thread cannot be pulled into this one.
	other := h.NewClient("otherco")
	otherProject := h.PublishProject(other, "A second project entirely",
		"telegram-bots", []string{"python"}, 10000, 20000)
	otherDev := h.PublishDeveloper("seconddev", "telegram-developer", "python", "telegram-api")
	otherProposal := otherDev.Client.POST("/proposals", proposal(otherProject)).
		OK(t, http.StatusCreated).String("id")
	other.Client.POST("/contracts", map[string]any{"proposal_id": otherProposal}).
		OK(t, http.StatusCreated)

	var foreignConversation string
	h.QueryRow([]any{&foreignConversation}, `
		SELECT cv.id::text FROM conversations cv
		JOIN contracts c ON c.id = cv.contract_id WHERE c.client_id = $1::uuid`, other.UserID)
	foreignMessage := other.Client.POST("/conversations/"+foreignConversation+"/messages",
		map[string]any{"body": "A message in a different contract's thread."}).
		OK(t, http.StatusCreated).String("id")

	client.Client.POST("/conversations/"+conversationID+"/messages", map[string]any{
		"body": "Trying to reply across threads.", "reply_to_id": foreignMessage,
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
}

func TestDeletingAMessageKeepsTheThreadIntact(t *testing.T) {
	h := testsupport.New(t)
	conversationID, client, dev := workspace(t, h)

	messageID := client.Client.POST("/conversations/"+conversationID+"/messages",
		map[string]any{"body": "Sent this to the wrong thread, sorry."}).
		OK(t, http.StatusCreated).String("id")

	// Only its author may remove it.
	dev.Client.DELETE("/messages/"+messageID).Fails(t, http.StatusNotFound, "not_found")
	client.Client.DELETE("/messages/"+messageID).OK(t, http.StatusNoContent)

	page := dev.Client.GET("/conversations/"+conversationID+"/messages").OK(t, http.StatusOK)
	messages, _ := page.Data["messages"].([]any)
	last, _ := messages[len(messages)-1].(map[string]any)
	if last["is_deleted"] != true {
		t.Errorf("the deleted message should be marked, got %v", last)
	}
	if body, _ := last["body"].(string); body != "" {
		t.Errorf("a deleted message must not return its content, got %q", body)
	}
}

// ── Attachments ─────────────────────────────────────────────────────────────

func TestAttachingAFileToAMessage(t *testing.T) {
	h := testsupport.New(t)
	conversationID, client, dev := workspace(t, h)

	upload := uploadAttachment(t, client.Client, "screenshot.png", pngFixture(600, 400)).
		OK(t, http.StatusCreated)
	fileID := upload.String("id")
	if upload.String("access") != "private" {
		t.Errorf("access = %q — a message attachment is the thread's business",
			upload.String("access"))
	}

	sent := client.Client.POST("/conversations/"+conversationID+"/messages", map[string]any{
		"body": "Here's the screen I meant.", "file_ids": []string{fileID},
	}).OK(t, http.StatusCreated)
	attachments, _ := sent.Data["attachments"].([]any)
	if len(attachments) != 1 {
		t.Fatalf("attachments = %v, want one", sent.Data["attachments"])
	}
	attachment, _ := attachments[0].(map[string]any)
	if attachment["is_image"] != true {
		t.Error("a PNG should be marked as an image so it renders inline")
	}
	if url, _ := attachment["url"].(string); !strings.Contains(url, "signature=") {
		t.Errorf("attachment url = %q, want a signed link", url)
	}

	// The other party sees it too, with their own signed link.
	page := dev.Client.GET("/conversations/"+conversationID+"/messages").OK(t, http.StatusOK)
	messages, _ := page.Data["messages"].([]any)
	last, _ := messages[len(messages)-1].(map[string]any)
	lastAttachments, _ := last["attachments"].([]any)
	if len(lastAttachments) != 1 {
		t.Fatal("the recipient should see the attachment")
	}
}

// A file id is guessable in principle; ownership is what makes guessing
// useless.
func TestAnotherPersonsUploadCannotBeAttached(t *testing.T) {
	h := testsupport.New(t)
	conversationID, client, dev := workspace(t, h)

	theirs := uploadAttachment(t, dev.Client, "theirs.png", pngFixture(400, 300)).
		OK(t, http.StatusCreated).String("id")

	res := client.Client.POST("/conversations/"+conversationID+"/messages", map[string]any{
		"body": "Attaching a file that isn't mine.", "file_ids": []string{theirs},
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if strings.Contains(fmt.Sprint(res.Fields), theirs) {
		t.Error("the refusal must not echo the id back")
	}
}

func TestExecutableAttachmentsAreRefused(t *testing.T) {
	h := testsupport.New(t)
	_, client, _ := workspace(t, h)

	// Named like a document, actually an ELF binary. The bytes decide.
	binary := append([]byte{0x7f, 'E', 'L', 'F', 2, 1, 1, 0}, bytes.Repeat([]byte{0}, 64)...)
	uploadAttachment(t, client.Client, "report.pdf", binary).
		Fails(t, http.StatusUnsupportedMediaType, "unsupported_media_type")

	// And an HTML page dressed as an image.
	html := []byte("<!DOCTYPE html><html><script>alert(1)</script></html>")
	uploadAttachment(t, client.Client, "diagram.png", html).
		Fails(t, http.StatusUnsupportedMediaType, "unsupported_media_type")
}

// ── Milestone events in the thread ──────────────────────────────────────────

func TestMilestoneEventsAppearInTheThread(t *testing.T) {
	h := testsupport.New(t)
	conversationID, client, dev := workspace(t, h)

	var milestoneID string
	h.QueryRow([]any{&milestoneID},
		`SELECT id::text FROM milestones ORDER BY position LIMIT 1`)
	h.Exec(`UPDATE milestones SET status = 'funded' WHERE id = $1::uuid`, milestoneID)

	dev.Client.POST("/milestones/"+milestoneID+"/start", nil).OK(t, http.StatusOK)
	dev.Client.POST("/milestones/"+milestoneID+"/submit", map[string]any{
		"note": "The catalogue import and the admin screen are ready for review.",
	}).OK(t, http.StatusOK)

	page := client.Client.GET("/conversations/"+conversationID+"/messages").OK(t, http.StatusOK)
	messages, _ := page.Data["messages"].([]any)
	events := map[string]bool{}
	for _, entry := range messages {
		message, _ := entry.(map[string]any)
		if message["kind"] == "system" {
			events[fmt.Sprint(message["system_event"])] = true
		}
	}
	for _, want := range []string{"contract.signed", "milestone.in_progress", "milestone.submitted"} {
		if !events[want] {
			t.Errorf("the thread is missing the %s entry (has %v)", want, events)
		}
	}
}

// ── Realtime ────────────────────────────────────────────────────────────────

// The socket is a live update, not a second way in: it delivers what the
// database already holds, and nothing sent over it is acted on.
func TestTheSocketDeliversAMessageToTheOtherParty(t *testing.T) {
	h := testsupport.New(t)
	conversationID, client, dev := workspace(t, h)

	socket := dial(t, h, dev.Client)
	defer socket.Close()

	client.Client.POST("/conversations/"+conversationID+"/messages", map[string]any{
		"body": "Are you free for fifteen minutes this afternoon?",
	}).OK(t, http.StatusCreated)

	event := readEvent(t, socket)
	if event.Type != "message" {
		t.Fatalf("event type = %q, want message", event.Type)
	}
	if event.Message == nil || event.Message.Body != "Are you free for fifteen minutes this afternoon?" {
		t.Fatalf("event carried %+v", event.Message)
	}
	if event.Message.IsMine {
		t.Error("the recipient's copy must not claim they wrote it")
	}
	if event.UnreadCount == nil || *event.UnreadCount != 1 {
		t.Errorf("unread_count = %v, want 1 so the badge needs no second request",
			event.UnreadCount)
	}

	// Reading it tells the sender, which is what a delivery receipt is.
	senderSocket := dial(t, h, client.Client)
	defer senderSocket.Close()
	dev.Client.POST("/conversations/"+conversationID+"/read", nil).OK(t, http.StatusOK)

	readEventReceived := readEvent(t, senderSocket)
	if readEventReceived.Type != "read" {
		t.Errorf("event type = %q, want read", readEventReceived.Type)
	}
}

func TestTheSocketRefusesAnUnauthenticatedOrForeignOriginConnection(t *testing.T) {
	h := testsupport.New(t)
	_, _, dev := workspace(t, h)

	url := strings.Replace(h.APIURL("/ws"), "http://", "ws://", 1)

	// No session at all.
	_, resp, err := websocket.DefaultDialer.Dial(url, http.Header{
		"Origin": []string{"http://localhost:3000"},
	})
	if err == nil {
		t.Fatal("an unauthenticated socket was accepted")
	}
	if resp != nil && resp.StatusCode != http.StatusUnauthorized {
		t.Errorf("status = %d, want 401", resp.StatusCode)
	}

	// A real session, but the handshake comes from somewhere else. This is the
	// cross-site hijack the Origin check exists for.
	_, resp, err = websocket.DefaultDialer.Dial(url, http.Header{
		"Origin": []string{"https://evil.example"},
		"Cookie": []string{dev.Client.CookieHeader()},
	})
	if err == nil {
		t.Fatal("a socket from a foreign origin was accepted")
	}
	if resp != nil && resp.StatusCode != http.StatusForbidden {
		t.Errorf("status = %d, want 403", resp.StatusCode)
	}
}

// ── Helpers ─────────────────────────────────────────────────────────────────

func dial(t *testing.T, h *testsupport.Harness, c *testsupport.Client) *websocket.Conn {
	t.Helper()
	url := strings.Replace(h.APIURL("/ws"), "http://", "ws://", 1)
	socket, _, err := websocket.DefaultDialer.Dial(url, http.Header{
		"Origin": []string{"http://localhost:3000"},
		"Cookie": []string{c.CookieHeader()},
	})
	if err != nil {
		t.Fatalf("open websocket: %v", err)
	}
	return socket
}

type socketEvent struct {
	Type           string `json:"type"`
	ConversationID string `json:"conversation_id"`
	UnreadCount    *int   `json:"unread_count"`
	Message        *struct {
		ID     string `json:"id"`
		Body   string `json:"body"`
		Kind   string `json:"kind"`
		IsMine bool   `json:"is_mine"`
	} `json:"message"`
}

func readEvent(t *testing.T, socket *websocket.Conn) socketEvent {
	t.Helper()
	_ = socket.SetReadDeadline(time.Now().Add(5 * time.Second))
	_, raw, err := socket.ReadMessage()
	if err != nil {
		t.Fatalf("read from websocket: %v", err)
	}
	var event socketEvent
	if err := json.Unmarshal(raw, &event); err != nil {
		t.Fatalf("decode socket frame %s: %v", raw, err)
	}
	return event
}

func uploadAttachment(t *testing.T, c *testsupport.Client, filename string,
	body []byte) *testsupport.Response {

	t.Helper()
	var buf bytes.Buffer
	w := multipart.NewWriter(&buf)
	headers := textproto.MIMEHeader{}
	headers.Set("Content-Disposition",
		fmt.Sprintf(`form-data; name="file"; filename=%q`, filename))
	headers.Set("Content-Type", "application/octet-stream")
	part, err := w.CreatePart(headers)
	if err != nil {
		t.Fatalf("create form file: %v", err)
	}
	if _, err := part.Write(body); err != nil {
		t.Fatalf("write form file: %v", err)
	}
	if err := w.Close(); err != nil {
		t.Fatalf("close multipart writer: %v", err)
	}
	return c.Multipart("/messages/attachments", w.FormDataContentType(), buf.Bytes())
}

func pngFixture(width, height int) []byte {
	m := image.NewNRGBA(image.Rect(0, 0, width, height))
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			m.Set(x, y, color.NRGBA{R: uint8(x % 256), G: uint8(y % 256), B: 90, A: 255})
		}
	}
	var buf bytes.Buffer
	if err := png.Encode(&buf, m); err != nil {
		panic(err)
	}
	return buf.Bytes()
}
