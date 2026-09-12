package httpx

import (
	"bufio"
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"net"
	"net/http"
	"runtime/debug"
	"strings"
	"time"

	"github.com/averix/api/internal/platform/logx"
)

// RequestID assigns an id to every request, propagates it in the context and
// returns it in a header so a user-visible error can be traced to one log line.
func RequestID() Middleware {
	return func(next Handler) Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			id := r.Header.Get("X-Request-Id")
			// An inbound value is only trusted for correlation if it looks sane.
			if len(id) == 0 || len(id) > 64 || strings.ContainsAny(id, "\r\n ") {
				id = newID()
			}
			ctx := logx.WithRequestID(r.Context(), id)
			w.Header().Set("X-Request-Id", id)
			return next(w, r.WithContext(ctx))
		}
	}
}

func newID() string {
	var b [12]byte
	_, _ = rand.Read(b[:])
	return hex.EncodeToString(b[:])
}

// Errors renders a handler's error into the response.
//
// It must sit inside RequestID and Logger so the request it renders with is the
// one those middlewares augmented — the router's own fallback holds the
// original request, whose context has no request id, which would leave every
// error body without the reference a user needs to quote to support.
func Errors() Middleware {
	return func(next Handler) Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			if err := next(w, r); err != nil {
				WriteError(w, r, err)
			}
			return nil
		}
	}
}

// Logger attaches a request-scoped logger and records the outcome once.
func Logger() Middleware {
	return func(next Handler) Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			start := time.Now()
			log := logx.From(r.Context()).With(
				"request_id", logx.RequestID(r.Context()),
				"method", r.Method,
				"path", r.URL.Path,
			)
			ctx := logx.WithLogger(r.Context(), log)
			rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}

			err := next(rec, r.WithContext(ctx))

			// Failures are logged by WriteError with their cause; logging them
			// again here would double every error line.
			if err == nil {
				log.Info("request",
					"status", rec.status,
					"bytes", rec.written,
					"duration_ms", time.Since(start).Milliseconds())
			}
			return err
		}
	}
}

type statusRecorder struct {
	http.ResponseWriter
	status  int
	written int
	wrote   bool
}

func (s *statusRecorder) WriteHeader(code int) {
	if !s.wrote {
		s.status = code
		s.wrote = true
	}
	s.ResponseWriter.WriteHeader(code)
}

func (s *statusRecorder) Write(b []byte) (int, error) {
	s.wrote = true
	n, err := s.ResponseWriter.Write(b)
	s.written += n
	return n, err
}

// Unwrap lets http.ResponseController reach the underlying writer, which SSE
// flushing needs.
func (s *statusRecorder) Unwrap() http.ResponseWriter { return s.ResponseWriter }

// Hijack passes the connection through to the WebSocket upgrade.
//
// Unwrap alone is not enough: the upgrade asserts http.Hijacker on the writer
// it is handed, and a wrapper that only implements Unwrap fails that assertion
// — which shows up as "bad handshake" on the client with nothing in the log.
func (s *statusRecorder) Hijack() (net.Conn, *bufio.ReadWriter, error) {
	hijacker, ok := s.ResponseWriter.(http.Hijacker)
	if !ok {
		return nil, nil, fmt.Errorf("the underlying writer does not support hijacking")
	}
	// The status is recorded here because a hijacked connection never calls
	// WriteHeader, and the access log would otherwise report a zero.
	if !s.wrote {
		s.status = http.StatusSwitchingProtocols
		s.wrote = true
	}
	return hijacker.Hijack()
}

// Flush passes a flush through, for a streamed response.
func (s *statusRecorder) Flush() {
	if flusher, ok := s.ResponseWriter.(http.Flusher); ok {
		flusher.Flush()
	}
}

// Recover turns a panic into a 500 with the stack in the log, so one bad
// request cannot take the process down.
func Recover() Middleware {
	return func(next Handler) Handler {
		return func(w http.ResponseWriter, r *http.Request) (err error) {
			defer func() {
				if p := recover(); p != nil {
					// A client that hangs up mid-write surfaces as a panic in
					// some handlers; that is not a server fault.
					if p == http.ErrAbortHandler {
						panic(p)
					}
					logx.From(r.Context()).Error("panic recovered",
						"panic", fmt.Sprint(p),
						"stack", string(debug.Stack()))
					err = ErrInternal.Wrap(fmt.Errorf("panic: %v", p))
				}
			}()
			return next(w, r)
		}
	}
}

// SecurityHeaders applies the headers that protect the API itself.
//
// The API serves JSON, so its CSP is maximally restrictive: nothing may load,
// frame or be framed. The web app sets its own, looser policy — including the
// frame-src that the sandboxed project preview needs.
func SecurityHeaders() Middleware {
	return func(next Handler) Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			h := w.Header()
			h.Set("X-Content-Type-Options", "nosniff")
			h.Set("X-Frame-Options", "DENY")
			h.Set("Referrer-Policy", "strict-origin-when-cross-origin")
			h.Set("Cross-Origin-Resource-Policy", "same-site")
			h.Set("Cross-Origin-Opener-Policy", "same-origin")
			h.Set("Permissions-Policy",
				"accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()")
			h.Set("Content-Security-Policy",
				"default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
			// API responses are per-user; a shared cache must never hold them.
			h.Set("Cache-Control", "no-store, private")
			h.Set("Vary", "Origin, Cookie")
			return next(w, r)
		}
	}
}

// CORS allows exactly the web app's origin with credentials.
//
// There is no wildcard and no origin reflection: the allow-list is built from
// configuration, so a malicious site cannot talk to the API as a signed-in user.
func CORS(allowed []string) Middleware {
	allowSet := make(map[string]struct{}, len(allowed))
	for _, o := range allowed {
		if o = strings.TrimRight(strings.TrimSpace(o), "/"); o != "" {
			allowSet[o] = struct{}{}
		}
	}
	return func(next Handler) Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			origin := strings.TrimRight(r.Header.Get("Origin"), "/")
			if origin != "" {
				if _, ok := allowSet[origin]; ok {
					h := w.Header()
					h.Set("Access-Control-Allow-Origin", origin)
					h.Set("Access-Control-Allow-Credentials", "true")
					h.Set("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
					h.Set("Access-Control-Allow-Headers",
						"Content-Type, X-CSRF-Token, X-Request-Id, Idempotency-Key")
					h.Set("Access-Control-Expose-Headers", "X-Request-Id, Retry-After")
					h.Set("Access-Control-Max-Age", "600")
				}
			}
			if r.Method == http.MethodOptions {
				w.WriteHeader(http.StatusNoContent)
				return nil
			}
			return next(w, r)
		}
	}
}

// Timeout bounds how long a handler may run.
func Timeout(d time.Duration) Middleware {
	return func(next Handler) Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			ctx, cancel := context.WithTimeout(r.Context(), d)
			defer cancel()
			err := next(w, r.WithContext(ctx))
			if errors.Is(err, context.DeadlineExceeded) {
				return ErrUnavailable.Wrap(err)
			}
			return err
		}
	}
}

// MaxBody caps the request body before a handler reads it.
func MaxBody(limit int64) Middleware {
	return func(next Handler) Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			if r.ContentLength > limit {
				return ErrPayloadTooLarge.Wrap(fmt.Errorf("content-length %d exceeds %d", r.ContentLength, limit))
			}
			r.Body = http.MaxBytesReader(w, r.Body, limit)
			return next(w, r)
		}
	}
}

type ctxKey int

const ctxClientIP ctxKey = iota

// RealIP resolves the client address, trusting proxy headers only when the
// deployment says there is a proxy in front. Trusting them unconditionally
// would let any caller forge the address used for rate limiting and audit logs.
func RealIP(trustProxy bool) Middleware {
	return func(next Handler) Handler {
		return func(w http.ResponseWriter, r *http.Request) error {
			ip := directIP(r)
			if trustProxy {
				if v := r.Header.Get("X-Forwarded-For"); v != "" {
					// Left-most entry is the original client.
					if first := strings.TrimSpace(strings.Split(v, ",")[0]); first != "" {
						if parsed := net.ParseIP(first); parsed != nil {
							ip = parsed.String()
						}
					}
				} else if v := r.Header.Get("X-Real-Ip"); v != "" {
					if parsed := net.ParseIP(strings.TrimSpace(v)); parsed != nil {
						ip = parsed.String()
					}
				}
			}
			return next(w, r.WithContext(context.WithValue(r.Context(), ctxClientIP, ip)))
		}
	}
}

func directIP(r *http.Request) string {
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return host
}

// ClientIP returns the resolved client address.
func ClientIP(ctx context.Context) string {
	if v, ok := ctx.Value(ctxClientIP).(string); ok {
		return v
	}
	return ""
}
