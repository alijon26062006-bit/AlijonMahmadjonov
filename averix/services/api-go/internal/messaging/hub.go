package messaging

import (
	"context"
	"encoding/json"
	"net/http"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/websocket"

	"github.com/averix/api/internal/platform/logx"
)

// Hub keeps the open sockets and fans events out to them.
//
// Connections are keyed by user, not by conversation: a person has one socket
// and receives events for every thread they are on. That keeps a phone to a
// single connection instead of one per open chat, and it means a thread they
// were just added to starts delivering without a reconnect.
//
// Delivery is best effort by design. The socket is a live update, never the
// record: everything it carries is already in the database, so a dropped
// frame costs a refresh and nothing else.
type Hub struct {
	mu          sync.RWMutex
	connections map[uuid.UUID]map[*connection]struct{}
}

func NewHub() *Hub {
	return &Hub{connections: map[uuid.UUID]map[*connection]struct{}{}}
}

type connection struct {
	userID uuid.UUID
	socket *websocket.Conn
	send   chan []byte
	closed chan struct{}
	once   sync.Once
}

const (
	// How long a write may take before the connection is considered stuck.
	writeWait = 10 * time.Second
	// A client that has not answered a ping in this long is gone.
	pongWait = 60 * time.Second
	// Pings go out comfortably inside the pong deadline.
	pingPeriod = (pongWait * 9) / 10
	// Nothing a client sends over the socket is acted on, so the read limit is
	// tiny: it exists to close a connection that tries to stream at us.
	maxIncoming = 4 << 10
	// A slow consumer is disconnected rather than allowed to consume memory.
	sendBuffer = 64
)

// Upgrader checks the origin itself rather than trusting the default, which
// accepts any origin when the Origin header is absent.
func newUpgrader(allowedOrigin string) *websocket.Upgrader {
	return &websocket.Upgrader{
		HandshakeTimeout: 10 * time.Second,
		ReadBufferSize:   1024,
		WriteBufferSize:  4096,
		CheckOrigin: func(r *http.Request) bool {
			origin := r.Header.Get("Origin")
			if origin == "" {
				// A browser always sends Origin on a WebSocket handshake. Its
				// absence means a non-browser client, which has no session
				// cookie to ride on anyway — but there is no reason to accept
				// it here.
				return false
			}
			return origin == allowedOrigin
		},
	}
}

// Connect upgrades a request and registers the socket.
func (h *Hub) Connect(w http.ResponseWriter, r *http.Request, userID uuid.UUID,
	upgrader *websocket.Upgrader) error {

	socket, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		// Upgrade has already written its own response.
		return nil
	}

	c := &connection{
		userID: userID,
		socket: socket,
		send:   make(chan []byte, sendBuffer),
		closed: make(chan struct{}),
	}
	h.add(c)

	go h.writePump(c)
	h.readPump(c)
	return nil
}

func (h *Hub) add(c *connection) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if h.connections[c.userID] == nil {
		h.connections[c.userID] = map[*connection]struct{}{}
	}
	h.connections[c.userID][c] = struct{}{}
}

func (h *Hub) remove(c *connection) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if set, ok := h.connections[c.userID]; ok {
		delete(set, c)
		if len(set) == 0 {
			delete(h.connections, c.userID)
		}
	}
}

// readPump drains anything the client sends and keeps the liveness deadline
// fresh. Nothing arriving over the socket is acted on: every write to AVERIX
// goes through an authenticated, CSRF-checked HTTP request, so a hijacked
// socket cannot send a message as its owner.
func (h *Hub) readPump(c *connection) {
	defer func() {
		h.remove(c)
		c.close()
	}()

	c.socket.SetReadLimit(maxIncoming)
	_ = c.socket.SetReadDeadline(time.Now().Add(pongWait))
	c.socket.SetPongHandler(func(string) error {
		return c.socket.SetReadDeadline(time.Now().Add(pongWait))
	})

	for {
		if _, _, err := c.socket.ReadMessage(); err != nil {
			return
		}
	}
}

func (h *Hub) writePump(c *connection) {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		c.close()
	}()

	for {
		select {
		case payload, ok := <-c.send:
			_ = c.socket.SetWriteDeadline(time.Now().Add(writeWait))
			if !ok {
				_ = c.socket.WriteMessage(websocket.CloseMessage, nil)
				return
			}
			if err := c.socket.WriteMessage(websocket.TextMessage, payload); err != nil {
				return
			}
		case <-ticker.C:
			_ = c.socket.SetWriteDeadline(time.Now().Add(writeWait))
			if err := c.socket.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		case <-c.closed:
			return
		}
	}
}

func (c *connection) close() {
	c.once.Do(func() {
		close(c.closed)
		_ = c.socket.Close()
	})
}

// Publish sends an event to a set of users.
//
// A connection whose buffer is full is dropped rather than waited on: one
// stalled phone must not hold up a milestone update to everyone else.
func (h *Hub) Publish(ctx context.Context, recipients []uuid.UUID, event Event) {
	event.SentAt = time.Now().UTC()
	h.PublishRaw(ctx, recipients, event)
}

// PublishRaw fans out any JSON-encodable payload. The socket carries more
// than chat: a notification arrives on the same connection, so the bell can
// update without polling — and it uses this rather than a second hub.
func (h *Hub) PublishRaw(ctx context.Context, recipients []uuid.UUID, payload any) {
	if len(recipients) == 0 {
		return
	}
	encoded, err := json.Marshal(payload)
	if err != nil {
		logx.From(ctx).Error("messaging: could not encode a realtime event", "error", err)
		return
	}
	h.deliver(recipients, encoded)
}

func (h *Hub) deliver(recipients []uuid.UUID, payload []byte) {

	h.mu.RLock()
	targets := make([]*connection, 0, len(recipients))
	for _, userID := range recipients {
		for c := range h.connections[userID] {
			targets = append(targets, c)
		}
	}
	h.mu.RUnlock()

	for _, c := range targets {
		select {
		case c.send <- payload:
		default:
			c.close()
		}
	}
}

// Online reports whether a user has at least one live socket. Used to decide
// whether an email is worth sending, not to show a presence dot.
func (h *Hub) Online(userID uuid.UUID) bool {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.connections[userID]) > 0
}

// Connections reports the number of open sockets, for the health endpoint.
func (h *Hub) Connections() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	total := 0
	for _, set := range h.connections {
		total += len(set)
	}
	return total
}
