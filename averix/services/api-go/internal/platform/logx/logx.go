// Package logx builds the application logger and carries request context into it.
package logx

import (
	"context"
	"log/slog"
	"os"
	"strings"
)

type ctxKey int

const (
	ctxRequestID ctxKey = iota
	ctxUserID
	ctxLogger
)

// New builds a logger. JSON in production so logs are queryable; text in
// development so they are readable.
func New(level, format string) *slog.Logger {
	var lv slog.Level
	switch strings.ToLower(level) {
	case "debug":
		lv = slog.LevelDebug
	case "warn", "warning":
		lv = slog.LevelWarn
	case "error":
		lv = slog.LevelError
	default:
		lv = slog.LevelInfo
	}

	opts := &slog.HandlerOptions{Level: lv, ReplaceAttr: redact}
	var h slog.Handler
	if strings.ToLower(format) == "text" {
		h = slog.NewTextHandler(os.Stdout, opts)
	} else {
		h = slog.NewJSONHandler(os.Stdout, opts)
	}
	return slog.New(h)
}

// Attribute keys whose values must never reach a log line, whatever a caller
// passes. Cheaper to enforce here once than to audit every call site.
var secretKeys = map[string]struct{}{
	"password": {}, "password_hash": {}, "token": {}, "access_token": {},
	"refresh_token": {}, "secret": {}, "cookie": {}, "authorization": {},
	"csrf_token": {}, "verifier": {}, "client_secret": {}, "api_key": {},
	"card": {}, "cvc": {},
}

func redact(_ []string, a slog.Attr) slog.Attr {
	if _, secret := secretKeys[strings.ToLower(a.Key)]; secret {
		return slog.String(a.Key, "[redacted]")
	}
	return a
}

func WithRequestID(ctx context.Context, id string) context.Context {
	return context.WithValue(ctx, ctxRequestID, id)
}

func RequestID(ctx context.Context) string {
	if v, ok := ctx.Value(ctxRequestID).(string); ok {
		return v
	}
	return ""
}

func WithUserID(ctx context.Context, id string) context.Context {
	return context.WithValue(ctx, ctxUserID, id)
}

func UserID(ctx context.Context) string {
	if v, ok := ctx.Value(ctxUserID).(string); ok {
		return v
	}
	return ""
}

func WithLogger(ctx context.Context, l *slog.Logger) context.Context {
	return context.WithValue(ctx, ctxLogger, l)
}

// From returns the request-scoped logger, already tagged with the request id
// and user, falling back to the default logger outside a request.
func From(ctx context.Context) *slog.Logger {
	if l, ok := ctx.Value(ctxLogger).(*slog.Logger); ok {
		return l
	}
	l := slog.Default()
	if id := RequestID(ctx); id != "" {
		l = l.With("request_id", id)
	}
	return l
}
