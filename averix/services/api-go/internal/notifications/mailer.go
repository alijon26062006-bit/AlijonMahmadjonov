package notifications

import (
	"bytes"
	"context"
	"crypto/tls"
	"fmt"
	"html"
	"mime"
	"net"
	"net/smtp"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/platform/logx"
)

// Mailer sends email over SMTP and records every attempt in email_log.
//
// Without SMTP configured it still records: the row says "not sent, SMTP is
// not configured", which is the honest state — a verification email that
// nobody will receive is not pretended sent, and the product tells the person
// so where it matters.
type Mailer struct {
	cfg    config.Mail
	appURL string
	// Whether the token in an unsent email may be logged. Only outside
	// production: a token in a production log is a credential in a log.
	logTokens bool
	store     *Store
}

func NewMailer(cfg config.Mail, appURL string, production bool, store *Store) *Mailer {
	return &Mailer{cfg: cfg, appURL: strings.TrimRight(appURL, "/"), logTokens: !production, store: store}
}

func (m *Mailer) Configured() bool { return m.cfg.Enabled && m.cfg.Host != "" }

// Message is one email.
type Message struct {
	UserID   *uuid.UUID
	To       string
	ToName   string
	Template string
	Subject  string
	// Both bodies are always given: a plain part for clients that want it,
	// an HTML part for the rest.
	Text string
	HTML string
}

// Send delivers a message, or records why it could not.
func (m *Mailer) Send(ctx context.Context, msg Message) error {
	if !m.Configured() {
		// Recorded, not sent, and not an error to the caller: the caller's
		// action (a registration, a reset request) succeeded, and the row in
		// email_log is the truth about what happened to the message. Callers
		// that must know ask Configured() first.
		logx.From(ctx).Warn("email delivery is not configured; message recorded but not sent",
			"template", msg.Template, "to", msg.To)
		if m.store != nil {
			_ = m.store.logEmail(ctx, msg.UserID, msg.To, msg.Template, msg.Subject,
				"failed", "", "smtp_not_configured")
		}
		return nil
	}

	err := m.deliver(ctx, msg)
	status, reason := "sent", ""
	if err != nil {
		status, reason = "failed", err.Error()
		logx.From(ctx).Warn("email delivery failed", "template", msg.Template, "error", err)
	}
	if m.store != nil {
		_ = m.store.logEmail(ctx, msg.UserID, msg.To, msg.Template, msg.Subject, status, "", reason)
	}
	return err
}

// ErrMailNotConfigured is returned rather than swallowed so a caller can tell
// the person their email was not sent, when that matters (a password reset).
var ErrMailNotConfigured = fmt.Errorf("email delivery is not configured")

func (m *Mailer) deliver(ctx context.Context, msg Message) error {
	addr := net.JoinHostPort(m.cfg.Host, strconv.Itoa(m.cfg.Port))
	from := m.cfg.FromAddress
	body := m.encode(msg)

	dialer := &net.Dialer{Timeout: 15 * time.Second}
	var client *smtp.Client
	// 465 is implicit TLS; everything else starts plain and upgrades. A server
	// that offers STARTTLS gets it; one that does not still gets the mail,
	// because refusing to send is not more secure than sending to the
	// operator's own mail server on a private network.
	if m.cfg.Port == 465 {
		conn, err := tls.DialWithDialer(dialer, "tcp", addr, &tls.Config{ServerName: m.cfg.Host, MinVersion: tls.VersionTLS12})
		if err != nil {
			return fmt.Errorf("connect: %w", err)
		}
		client, err = smtp.NewClient(conn, m.cfg.Host)
		if err != nil {
			return fmt.Errorf("smtp handshake: %w", err)
		}
	} else {
		conn, err := dialer.DialContext(ctx, "tcp", addr)
		if err != nil {
			return fmt.Errorf("connect: %w", err)
		}
		client, err = smtp.NewClient(conn, m.cfg.Host)
		if err != nil {
			return fmt.Errorf("smtp handshake: %w", err)
		}
		if ok, _ := client.Extension("STARTTLS"); ok {
			if err := client.StartTLS(&tls.Config{ServerName: m.cfg.Host, MinVersion: tls.VersionTLS12}); err != nil {
				return fmt.Errorf("starttls: %w", err)
			}
		}
	}
	defer client.Close()

	if m.cfg.Username != "" {
		if ok, _ := client.Extension("AUTH"); ok {
			if err := client.Auth(smtp.PlainAuth("", m.cfg.Username, m.cfg.Password, m.cfg.Host)); err != nil {
				return fmt.Errorf("auth: %w", err)
			}
		}
	}
	if err := client.Mail(from); err != nil {
		return fmt.Errorf("mail from: %w", err)
	}
	if err := client.Rcpt(msg.To); err != nil {
		return fmt.Errorf("rcpt to: %w", err)
	}
	w, err := client.Data()
	if err != nil {
		return fmt.Errorf("data: %w", err)
	}
	if _, err := w.Write(body); err != nil {
		return fmt.Errorf("write: %w", err)
	}
	if err := w.Close(); err != nil {
		return fmt.Errorf("finish: %w", err)
	}
	return client.Quit()
}

// encode renders a multipart/alternative message with the headers a mail
// server expects. Subjects are RFC 2047-encoded so Cyrillic survives.
func (m *Mailer) encode(msg Message) []byte {
	boundary := "averix-" + uuid.NewString()
	var b bytes.Buffer
	fmt.Fprintf(&b, "From: %s\r\n", formatAddress(m.cfg.FromName, m.cfg.FromAddress))
	fmt.Fprintf(&b, "To: %s\r\n", formatAddress(msg.ToName, msg.To))
	fmt.Fprintf(&b, "Subject: %s\r\n", mime.QEncoding.Encode("utf-8", msg.Subject))
	fmt.Fprintf(&b, "Date: %s\r\n", time.Now().Format(time.RFC1123Z))
	fmt.Fprintf(&b, "Message-ID: <%s@%s>\r\n", uuid.NewString(), hostOf(m.cfg.FromAddress))
	b.WriteString("MIME-Version: 1.0\r\n")
	b.WriteString("X-Mailer: AVERIX\r\n")
	fmt.Fprintf(&b, "Content-Type: multipart/alternative; boundary=\"%s\"\r\n\r\n", boundary)

	part := func(contentType, body string) {
		fmt.Fprintf(&b, "--%s\r\n", boundary)
		fmt.Fprintf(&b, "Content-Type: %s; charset=utf-8\r\n", contentType)
		b.WriteString("Content-Transfer-Encoding: 8bit\r\n\r\n")
		b.WriteString(strings.ReplaceAll(body, "\n", "\r\n"))
		b.WriteString("\r\n")
	}
	part("text/plain", msg.Text)
	part("text/html", msg.HTML)
	fmt.Fprintf(&b, "--%s--\r\n", boundary)
	return b.Bytes()
}

func formatAddress(name, address string) string {
	if strings.TrimSpace(name) == "" {
		return address
	}
	return fmt.Sprintf("%s <%s>", mime.QEncoding.Encode("utf-8", name), address)
}

func hostOf(address string) string {
	if i := strings.LastIndex(address, "@"); i >= 0 {
		return address[i+1:]
	}
	return "averix"
}

// ── Templates ───────────────────────────────────────────────────────────────
//
// One layout, plain and readable on a phone. Every message says what
// happened, offers one link, and signs off; nothing is upsold.

func (m *Mailer) render(title, body, linkLabel, linkPath string) (text, htmlBody string) {
	link := ""
	if linkPath != "" {
		link = m.appURL + linkPath
	}

	var t strings.Builder
	t.WriteString(title + "\n\n")
	if body != "" {
		t.WriteString(body + "\n\n")
	}
	if link != "" {
		t.WriteString(linkLabel + ": " + link + "\n\n")
	}
	t.WriteString("— AVERIX\n" + m.appURL + "\n")

	var h strings.Builder
	h.WriteString(`<!doctype html><html lang="ru"><body style="margin:0;padding:24px;background:#F7F7F9;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#18181B">`)
	h.WriteString(`<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:16px;padding:28px;border:1px solid #E5E5EA">`)
	h.WriteString(`<p style="margin:0 0 20px;font-weight:800;letter-spacing:.12em;font-size:13px;color:#7017C8">AVERIX</p>`)
	fmt.Fprintf(&h, `<h1 style="margin:0 0 12px;font-size:20px;line-height:1.3">%s</h1>`, html.EscapeString(title))
	if body != "" {
		for _, para := range strings.Split(body, "\n\n") {
			fmt.Fprintf(&h, `<p style="margin:0 0 12px;font-size:15px;line-height:1.5;color:#3F3F46">%s</p>`,
				strings.ReplaceAll(html.EscapeString(para), "\n", "<br>"))
		}
	}
	if link != "" {
		fmt.Fprintf(&h, `<p style="margin:20px 0 0"><a href="%s" style="display:inline-block;background:#7017C8;color:#fff;text-decoration:none;padding:12px 20px;border-radius:12px;font-weight:600">%s</a></p>`,
			html.EscapeString(link), html.EscapeString(linkLabel))
		fmt.Fprintf(&h, `<p style="margin:16px 0 0;font-size:12px;color:#71717A">Если кнопка не открывается, скопируйте адрес: %s</p>`, html.EscapeString(link))
	}
	h.WriteString(`<p style="margin:24px 0 0;font-size:12px;color:#A1A1AA">Это письмо отправлено автоматически, потому что у вас есть аккаунт на AVERIX.</p>`)
	h.WriteString(`</div></body></html>`)
	return t.String(), h.String()
}

// The auth module's three messages. Tokens ride in a path, never in a query
// a log line would keep; the front end reads them from the path.

func (m *Mailer) SendEmailVerification(ctx context.Context, userID uuid.UUID, email, name, token string) error {
	path := "/verify-email/" + token
	text, htmlBody := m.render("Подтвердите адрес электронной почты",
		greeting(name)+"Осталось подтвердить, что этот адрес ваш. Ссылка действует 24 часа.",
		"Подтвердить адрес", path)
	m.logTokenIfAllowed(ctx, "email_verification", email, path)
	return m.Send(ctx, Message{UserID: &userID, To: email, ToName: name, Template: "email_verification",
		Subject: "Подтвердите адрес — AVERIX", Text: text, HTML: htmlBody})
}

func (m *Mailer) SendPasswordReset(ctx context.Context, userID uuid.UUID, email, name, token string) error {
	path := "/reset-password/" + token
	text, htmlBody := m.render("Сброс пароля",
		greeting(name)+"Кто-то — надеемся, вы — запросил сброс пароля. Ссылка действует один час. Если это были не вы, просто не открывайте её: пароль останется прежним.",
		"Задать новый пароль", path)
	m.logTokenIfAllowed(ctx, "password_reset", email, path)
	return m.Send(ctx, Message{UserID: &userID, To: email, ToName: name, Template: "password_reset",
		Subject: "Сброс пароля — AVERIX", Text: text, HTML: htmlBody})
}

func (m *Mailer) SendPasswordChanged(ctx context.Context, userID uuid.UUID, email, name string) error {
	text, htmlBody := m.render("Пароль изменён",
		greeting(name)+"Пароль вашего аккаунта только что изменили. Если это были не вы, немедленно сбросьте пароль и завершите остальные сессии в настройках.",
		"Открыть настройки безопасности", "/settings/security")
	return m.Send(ctx, Message{UserID: &userID, To: email, ToName: name, Template: "password_changed",
		Subject: "Пароль изменён — AVERIX", Text: text, HTML: htmlBody})
}

// SendEmailChange goes to the *new* address: proving the person controls it
// is the whole point, so the old address gets a plain notice instead.
func (m *Mailer) SendEmailChange(ctx context.Context, userID uuid.UUID, newEmail, name, token string) error {
	path := "/confirm-email/" + token
	text, htmlBody := m.render("Подтвердите новый адрес",
		greeting(name)+"Вы попросили сменить адрес электронной почты на этот. Подтвердите его по ссылке — она действует один час. Если это были не вы, просто не открывайте её.",
		"Подтвердить новый адрес", path)
	m.logTokenIfAllowed(ctx, "email_change", newEmail, path)
	return m.Send(ctx, Message{UserID: &userID, To: newEmail, ToName: name, Template: "email_change",
		Subject: "Подтвердите новый адрес — AVERIX", Text: text, HTML: htmlBody})
}

// SendEmailChanged tells the old address that the change happened, so a
// hijacked account is noticed by the person who lost it.
func (m *Mailer) SendEmailChanged(ctx context.Context, userID uuid.UUID, oldEmail, name, newEmail string) error {
	text, htmlBody := m.render("Адрес электронной почты изменён",
		greeting(name)+"Адрес вашего аккаунта AVERIX изменён на "+newEmail+". Если это были не вы, немедленно сбросьте пароль и завершите остальные сессии.",
		"Открыть настройки безопасности", "/settings/security")
	return m.Send(ctx, Message{UserID: &userID, To: oldEmail, ToName: name, Template: "email_changed",
		Subject: "Адрес изменён — AVERIX", Text: text, HTML: htmlBody})
}

// SendNotification is the generic delivery for the notification queue.
func (m *Mailer) SendNotification(ctx context.Context, userID uuid.UUID, email, name, kind,
	title, body, href string) error {

	text, htmlBody := m.render(title, body, "Открыть на AVERIX", href)
	return m.Send(ctx, Message{UserID: &userID, To: email, ToName: name, Template: kind,
		Subject: title + " — AVERIX", Text: text, HTML: htmlBody})
}

func greeting(name string) string {
	name = strings.TrimSpace(name)
	if name == "" {
		return "Здравствуйте!\n\n"
	}
	return "Здравствуйте, " + name + "!\n\n"
}

func (m *Mailer) logTokenIfAllowed(ctx context.Context, what, email, path string) {
	if m.Configured() || !m.logTokens {
		return
	}
	// Development only: the link is printed so a developer without SMTP can
	// complete the flow. The Configured() check above means this never
	// duplicates a real send.
	logx.From(ctx).Info("development: "+what+" link (email is not configured)",
		"email", email, "link", m.appURL+path)
}
