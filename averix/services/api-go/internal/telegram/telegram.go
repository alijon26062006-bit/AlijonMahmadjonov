// Package telegram sends an operator a short notice that something needs a
// person, and nothing else.
//
// It exists in the shape it does because of one rule: a chat is not a place
// for an identity document. Telegram keeps messages on its own servers, in
// the history of every member of the chat, on their phones, in their desktop
// cache, in their cloud backups — and nobody on the platform can delete any of
// those copies when the document's retention date arrives.
//
// So this package cannot send a file. There is no method that takes bytes, no
// method that takes a storage key, and no method that takes a document id. The
// only thing it sends is a line of text and a link back into the admin panel,
// where the real checks live: the named permission, the password typed again,
// the two-minute ticket, and the access log.
//
// When no bot is configured it is honest about it: nothing is queued, nothing
// pretends to have been sent, and the admin panel reports the integration as
// not set up rather than silently doing nothing.
package telegram

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/averix/api/internal/platform/logx"
)

// Config is what an operator sets to turn this on.
type Config struct {
	// BotToken comes from @BotFather. It is a credential: it never appears in
	// a response, a log line or an error message.
	BotToken string
	// ChatID is the staff chat that receives the notices. A group of the
	// people who already have accounts in the panel — the message is useless
	// to anyone else, because every link behind it asks for a session.
	ChatID string
	// BaseURL is the Telegram API root, overridable so tests never talk to
	// the real one.
	BaseURL string
	// AppURL is the platform's own address, for the links in the messages.
	AppURL  string
	Timeout time.Duration
}

func (c Config) Configured() bool { return c.BotToken != "" && c.ChatID != "" }

type Client struct {
	cfg  Config
	http *http.Client
}

func New(cfg Config) *Client {
	if cfg.BaseURL == "" {
		cfg.BaseURL = "https://api.telegram.org"
	}
	if cfg.Timeout == 0 {
		cfg.Timeout = 10 * time.Second
	}
	return &Client{cfg: cfg, http: &http.Client{Timeout: cfg.Timeout}}
}

// ErrNotConfigured is what every send returns when there is no bot. Callers
// treat it as "nothing to do", not as a failure worth retrying.
var ErrNotConfigured = errors.New("telegram is not configured")

func (c *Client) Configured() bool { return c != nil && c.cfg.Configured() }

// Status is what the admin panel shows about this integration.
func (c *Client) Status() map[string]any {
	if c == nil || !c.cfg.Configured() {
		return map[string]any{
			"configured": false,
			"reason":     "Не заданы TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID.",
			"carries":    "ссылку и одну строку текста",
		}
	}
	return map[string]any{
		"configured": true,
		"chat":       masked(c.cfg.ChatID),
		"carries":    "ссылку и одну строку текста",
	}
}

// IdentitySubmitted tells the staff chat that somebody is waiting.
//
// Note what the arguments are: a reference and a user id. Not a name, not an
// email, not a document type, not a country — a support person reading the
// chat learns only that there is work, and has to sign in to learn anything
// about whom.
func (c *Client) IdentitySubmitted(ctx context.Context, reference string, userID fmt.Stringer) error {
	return c.send(ctx, strings.Join([]string{
		"Новая заявка на проверку личности.",
		"Аккаунт: " + reference,
		"Открыть: " + c.link("/admin/users/"+userID.String()),
		"",
		"Документы в чат не отправляются: их видно только в панели, после ввода пароля.",
	}, "\n"))
}

// NeedsAttention is the general-purpose notice: a queue got long, a dispute
// was opened. One line and a link, same as above.
func (c *Client) NeedsAttention(ctx context.Context, what, path string) error {
	return c.send(ctx, what+"\nОткрыть: "+c.link(path))
}

func (c *Client) link(path string) string {
	if !strings.HasPrefix(path, "/") {
		path = "/" + path
	}
	return strings.TrimRight(c.cfg.AppURL, "/") + path
}

// send posts one text message. It is deliberately the only way out of this
// package, and it takes a string — there is no overload that takes a file.
func (c *Client) send(ctx context.Context, text string) error {
	if !c.Configured() {
		return ErrNotConfigured
	}
	body, err := json.Marshal(map[string]any{
		"chat_id": c.cfg.ChatID,
		"text":    text,
		// A link preview would make Telegram fetch the page and cache whatever
		// it renders. Nothing sensitive is at these addresses without a
		// session, but there is no reason to let a third party try.
		"disable_web_page_preview": true,
	})
	if err != nil {
		return fmt.Errorf("encode telegram message: %w", err)
	}

	url := strings.TrimRight(c.cfg.BaseURL, "/") + "/bot" + c.cfg.BotToken + "/sendMessage"
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("build telegram request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.http.Do(req)
	if err != nil {
		// The token is in the URL, so the error is never passed through as-is.
		return errors.New("telegram request failed")
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return fmt.Errorf("telegram answered %d", resp.StatusCode)
	}
	return nil
}

// Notify sends and swallows, for callers that must not fail because a chat
// integration is down. A notice that did not arrive is logged, once, without
// the token and without the text.
func (c *Client) Notify(ctx context.Context, send func(context.Context) error) {
	if !c.Configured() {
		return
	}
	if err := send(ctx); err != nil && !errors.Is(err, ErrNotConfigured) {
		logx.From(ctx).Warn("telegram: notice not delivered", "error", err)
	}
}

// masked shows enough of a chat id to recognise it and not enough to use it.
func masked(id string) string {
	if len(id) <= 4 {
		return "…"
	}
	return "…" + id[len(id)-4:]
}
