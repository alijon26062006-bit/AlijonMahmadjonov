package telegram

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/google/uuid"
)

// An unconfigured integration does nothing at all — it does not queue, retry
// or pretend. The panel shows it as not set up, which is the honest state.
func TestNothingIsSentWithoutABot(t *testing.T) {
	c := New(Config{AppURL: "https://averix.dev"})
	if c.Configured() {
		t.Fatal("a client with no token must not report itself configured")
	}
	if err := c.IdentitySubmitted(context.Background(), "AVX-1234", uuid.New()); err != ErrNotConfigured {
		t.Fatalf("error = %v, want ErrNotConfigured", err)
	}
	if status := c.Status(); status["configured"] != false || status["reason"] == "" {
		t.Errorf("status must say what is missing: %v", status)
	}
}

// The message about a verification carries a reference and a link and nothing
// else: no name, no email, no document type, and above all no image.
func TestTheNoticeCarriesOnlyALink(t *testing.T) {
	var sent map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/sendMessage") {
			t.Errorf("telegram may only be asked to send a message, got %s", r.URL.Path)
		}
		body, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(body, &sent)
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer server.Close()

	userID := uuid.New()
	c := New(Config{BotToken: "test-token", ChatID: "-100500", BaseURL: server.URL, AppURL: "https://averix.dev"})
	if err := c.IdentitySubmitted(context.Background(), "AVX-ABCD1234", userID); err != nil {
		t.Fatalf("send: %v", err)
	}

	text, _ := sent["text"].(string)
	if !strings.Contains(text, "AVX-ABCD1234") {
		t.Errorf("the notice must name the account by reference: %q", text)
	}
	if !strings.Contains(text, "https://averix.dev/admin/users/"+userID.String()) {
		t.Errorf("the notice must link into the panel: %q", text)
	}
	if sent["disable_web_page_preview"] != true {
		t.Error("link previews must be off: Telegram would fetch and cache the page")
	}
	for _, forbidden := range []string{"passport", "паспорт", "storage", "identity/", "document_id"} {
		if strings.Contains(strings.ToLower(text), forbidden) {
			t.Errorf("the notice must say nothing about the documents themselves, found %q in %q", forbidden, text)
		}
	}
	// The whole payload is a chat id, a line of text and a flag. If a photo
	// or a document ever appeared here, this is where it would show up.
	for key := range sent {
		switch key {
		case "chat_id", "text", "disable_web_page_preview":
		default:
			t.Errorf("unexpected field %q in a telegram payload", key)
		}
	}
}

// A masked chat id is enough to recognise the chat in the panel and useless
// for anything else.
func TestConfiguredStatusHidesTheChat(t *testing.T) {
	c := New(Config{BotToken: "token", ChatID: "-1001234567890"})
	status := c.Status()
	if status["configured"] != true {
		t.Fatalf("status = %v", status)
	}
	if chat, _ := status["chat"].(string); chat != "…7890" {
		t.Errorf("chat = %q, want the masked form", chat)
	}
}
