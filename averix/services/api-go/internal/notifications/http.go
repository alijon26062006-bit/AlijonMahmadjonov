package notifications

import (
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

type Handlers struct {
	svc            *Service
	pushConfigured bool
	vapidPublicKey string
}

func NewHandlers(svc *Service, pushConfigured bool, vapidPublicKey string) *Handlers {
	return &Handlers{svc: svc, pushConfigured: pushConfigured, vapidPublicKey: vapidPublicKey}
}

type Middleware struct {
	Require httpx.Middleware
	CSRF    httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	read := r.Group("/notifications", mw.Require)
	read.GET("", h.list)
	read.GET("/unread", h.unread)
	read.GET("/preferences", h.preferences)

	write := r.Group("/notifications", mw.Require, mw.CSRF)
	write.POST("/read-all", h.readAll)
	write.POST("/{id}/read", h.read)
	write.PUT("/preferences", h.savePreferences)
	write.POST("/push", h.subscribePush)
	write.DELETE("/push", h.unsubscribePush)
}

func (h *Handlers) list(w http.ResponseWriter, r *http.Request) error {
	id := security.FromContext(r.Context())
	q := r.URL.Query()

	var before *time.Time
	if raw := q.Get("before"); raw != "" {
		t, err := time.Parse(time.RFC3339Nano, raw)
		if err != nil {
			return httpx.Validation(map[string]string{"before": "Неверный формат времени."})
		}
		before = &t
	}
	limit, _ := strconv.Atoi(q.Get("limit"))
	page, err := h.svc.store.List(r.Context(), id.UserID, before, q.Get("unread") == "true", limit)
	if err != nil {
		return httpx.Internalf(err, "list notifications")
	}
	meta := map[string]any{"unread": page.Unread}
	if page.NextBefore != nil {
		meta["next_before"] = page.NextBefore.Format(time.RFC3339Nano)
	}
	return httpx.JSONMeta(w, http.StatusOK, page.Items, meta)
}

func (h *Handlers) unread(w http.ResponseWriter, r *http.Request) error {
	id := security.FromContext(r.Context())
	n, err := h.svc.store.UnreadCount(r.Context(), id.UserID)
	if err != nil {
		return httpx.Internalf(err, "count unread notifications")
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"unread": n})
}

func (h *Handlers) read(w http.ResponseWriter, r *http.Request) error {
	id := security.FromContext(r.Context())
	notificationID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	err = h.svc.store.MarkRead(r.Context(), id.UserID, notificationID)
	switch {
	case errors.Is(err, ErrNotFound):
		return httpx.NotFoundf("notification %s does not exist", notificationID)
	case err != nil:
		return httpx.Internalf(err, "mark notification read")
	}
	unread, _ := h.svc.store.UnreadCount(r.Context(), id.UserID)
	return httpx.JSON(w, http.StatusOK, map[string]any{"read": true, "unread": unread})
}

func (h *Handlers) readAll(w http.ResponseWriter, r *http.Request) error {
	id := security.FromContext(r.Context())
	n, err := h.svc.store.MarkAllRead(r.Context(), id.UserID)
	if err != nil {
		return httpx.Internalf(err, "mark all notifications read")
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"marked": n, "unread": 0})
}

func (h *Handlers) preferences(w http.ResponseWriter, r *http.Request) error {
	id := security.FromContext(r.Context())
	groups, err := h.svc.store.Preferences(r.Context(), id.UserID)
	if err != nil {
		return httpx.Internalf(err, "load notification preferences")
	}
	return httpx.JSONMeta(w, http.StatusOK, groups, map[string]any{
		"email_configured": h.svc.mailer != nil && h.svc.mailer.Configured(),
		"push_configured":  h.pushConfigured,
		"vapid_public_key": h.vapidPublicKey,
	})
}

func (h *Handlers) savePreferences(w http.ResponseWriter, r *http.Request) error {
	id := security.FromContext(r.Context())
	var body struct {
		Preferences []Preference `json:"preferences"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 32<<10); err != nil {
		return err
	}
	if len(body.Preferences) == 0 || len(body.Preferences) > len(catalogue) {
		return httpx.Validation(map[string]string{"preferences": "Передайте хотя бы одну настройку."})
	}
	for _, p := range body.Preferences {
		if !Known(p.Type) {
			return httpx.Validation(map[string]string{"preferences": "Неизвестный тип уведомления: " + p.Type})
		}
		if err := h.svc.store.SavePreference(r.Context(), id.UserID, p); err != nil {
			return httpx.Internalf(err, "save notification preference")
		}
	}
	groups, err := h.svc.store.Preferences(r.Context(), id.UserID)
	if err != nil {
		return httpx.Internalf(err, "reload notification preferences")
	}
	return httpx.JSON(w, http.StatusOK, groups)
}

func (h *Handlers) subscribePush(w http.ResponseWriter, r *http.Request) error {
	id := security.FromContext(r.Context())
	var sub PushSubscription
	if err := httpx.DecodeJSON(w, r, &sub, 8<<10); err != nil {
		return err
	}
	sub.Endpoint = strings.TrimSpace(sub.Endpoint)
	if !strings.HasPrefix(sub.Endpoint, "https://") || sub.P256dh == "" || sub.Auth == "" {
		return httpx.Validation(map[string]string{"endpoint": "Подписка неполная: нужны endpoint (https), p256dh и auth."})
	}
	if err := h.svc.store.SavePushSubscription(r.Context(), id.UserID, sub, r.UserAgent()); err != nil {
		return httpx.Internalf(err, "save push subscription")
	}
	return httpx.JSON(w, http.StatusCreated, map[string]any{
		"subscribed":      true,
		"push_configured": h.pushConfigured,
	})
}

func (h *Handlers) unsubscribePush(w http.ResponseWriter, r *http.Request) error {
	id := security.FromContext(r.Context())
	endpoint := strings.TrimSpace(r.URL.Query().Get("endpoint"))
	if endpoint == "" {
		return httpx.Validation(map[string]string{"endpoint": "Укажите endpoint подписки."})
	}
	if err := h.svc.store.DeletePushSubscription(r.Context(), id.UserID, endpoint); err != nil {
		return httpx.Internalf(err, "delete push subscription")
	}
	return httpx.NoContent(w)
}
