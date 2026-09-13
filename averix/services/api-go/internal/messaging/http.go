package messaging

import (
	"errors"
	"fmt"
	"io"
	"mime"
	"mime/multipart"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/websocket"

	"github.com/averix/api/internal/files"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

type Handlers struct {
	svc      *Service
	files    *files.Store
	upgrader *websocket.Upgrader
	maxFile  int64
}

func NewHandlers(svc *Service, fileStore *files.Store, appOrigin string, maxFileBytes int64) *Handlers {
	if maxFileBytes <= 0 {
		maxFileBytes = 25 << 20
	}
	return &Handlers{
		svc:      svc,
		files:    fileStore,
		upgrader: newUpgrader(strings.TrimRight(appOrigin, "/")),
		maxFile:  maxFileBytes,
	}
}

type Middleware struct {
	Require         httpx.Middleware
	CSRF            httpx.Middleware
	RateLimitSend   httpx.Middleware
	RateLimitUpload httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	read := r.Group("/conversations", mw.Require)
	read.GET("", h.inbox)
	read.GET("/unread", h.unread)
	read.GET("/{id}", h.view)
	read.GET("/{id}/messages", h.messages)

	write := r.Group("/conversations", mw.Require, mw.CSRF)
	write.POST("/{id}/messages", mw.RateLimitSend(h.send))
	write.POST("/{id}/read", h.markRead)
	write.PUT("/{id}/muted", h.setMuted)
	// Opening the thread for a proposal is how a conversation starts before a
	// contract exists; there is no endpoint that starts one from nothing. It
	// hangs off the proposal rather than off /conversations, where a literal
	// path segment would collide with a conversation id.
	r.Group("/proposals", mw.Require, mw.CSRF).
		POST("/{proposalID}/conversation", h.openForProposal)

	messages := r.Group("/messages", mw.Require, mw.CSRF)
	messages.DELETE("/{id}", h.remove)
	// Attachments are uploaded first and referenced by id when the message is
	// sent, so a failed send does not lose the file and a file is never
	// attached without an ownership check.
	messages.POST("/attachments", mw.RateLimitUpload(h.uploadAttachment))

	// The realtime socket. One per person, carrying events for every thread
	// they are on.
	r.Group("", mw.Require).GET("/ws", h.socket)
}

func (h *Handlers) inbox(w http.ResponseWriter, r *http.Request) error {
	cards, err := h.svc.Inbox(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, cards, map[string]any{"count": len(cards)})
}

func (h *Handlers) unread(w http.ResponseWriter, r *http.Request) error {
	total, err := h.svc.UnreadTotal(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"unread": total})
}

func (h *Handlers) view(w http.ResponseWriter, r *http.Request) error {
	conversationID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	conversation, err := h.svc.View(r.Context(), security.FromContext(r.Context()), conversationID)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, conversation)
}

func (h *Handlers) messages(w http.ResponseWriter, r *http.Request) error {
	conversationID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	page, err := h.svc.Messages(r.Context(), security.FromContext(r.Context()),
		conversationID, r.URL.Query().Get("cursor"), limit)
	if err != nil {
		return err
	}
	// Signed attachment URLs and private correspondence: never a shared cache.
	w.Header().Set("Cache-Control", "private, no-store")
	return httpx.JSON(w, http.StatusOK, page)
}

func (h *Handlers) send(w http.ResponseWriter, r *http.Request) error {
	conversationID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body SendRequest
	if err := httpx.DecodeJSON(w, r, &body, 64<<10); err != nil {
		return err
	}
	message, err := h.svc.Send(r.Context(), security.FromContext(r.Context()),
		conversationID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusCreated, message)
}

func (h *Handlers) markRead(w http.ResponseWriter, r *http.Request) error {
	conversationID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	readAt, err := h.svc.MarkRead(r.Context(), security.FromContext(r.Context()), conversationID)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"read_at": readAt})
}

func (h *Handlers) setMuted(w http.ResponseWriter, r *http.Request) error {
	conversationID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body struct {
		Muted bool `json:"muted"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 1<<10); err != nil {
		return err
	}
	if err := h.svc.SetMuted(r.Context(), security.FromContext(r.Context()),
		conversationID, body.Muted); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"muted": body.Muted})
}

func (h *Handlers) openForProposal(w http.ResponseWriter, r *http.Request) error {
	proposalID, err := pathID(r, "proposalID")
	if err != nil {
		return err
	}
	conversation, err := h.svc.OpenForProposal(r.Context(),
		security.FromContext(r.Context()), proposalID)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, conversation)
}

func (h *Handlers) remove(w http.ResponseWriter, r *http.Request) error {
	messageID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	if err := h.svc.Delete(r.Context(), security.FromContext(r.Context()), messageID); err != nil {
		return err
	}
	return httpx.NoContent(w)
}

// uploadAttachment stores a file for a message that has not been sent yet.
//
// The upload is private and belongs to the uploader until a message references
// it; an upload that is never sent is swept up by the orphan purge.
func (h *Handlers) uploadAttachment(w http.ResponseWriter, r *http.Request) error {
	id := security.FromContext(r.Context())

	part, err := h.readFilePart(w, r)
	if err != nil {
		return err
	}
	defer part.Close()

	file, err := h.files.Save(r.Context(), files.UploadInput{
		OwnerID:      id.UserID,
		Purpose:      files.PurposeMessageAttachment,
		DeclaredName: part.FileName(),
		DeclaredMIME: part.Header.Get("Content-Type"),
		Reader:       part,
	})
	if err != nil {
		return uploadError(err)
	}

	signed, err := h.files.SignedURL(r.Context(), file, 30*time.Minute)
	if err == nil {
		file.URL = signed
	}
	return httpx.JSON(w, http.StatusCreated, file)
}

// socket upgrades the connection and keeps it until the client goes away.
//
// Authentication is the ordinary session: the Require middleware has already
// resolved the identity, so an unauthenticated upgrade never reaches here. The
// socket carries no authority of its own — nothing a client sends over it is
// acted on — so a stolen connection can read what its owner could read and
// change nothing.
func (h *Handlers) socket(w http.ResponseWriter, r *http.Request) error {
	id := security.FromContext(r.Context())
	if !id.Authenticated() {
		return httpx.ErrUnauthenticated
	}
	return h.svc.Hub().Connect(w, r, id.UserID, h.upgrader)
}

// readFilePart streams the file out of a multipart body without spooling it.
func (h *Handlers) readFilePart(w http.ResponseWriter, r *http.Request) (*multipart.Part, error) {
	contentType := r.Header.Get("Content-Type")
	mediaType, params, err := mime.ParseMediaType(contentType)
	if err != nil || !strings.HasPrefix(mediaType, "multipart/form-data") {
		return nil, httpx.ErrUnsupportedMedia.Wrap(
			fmt.Errorf("expected multipart/form-data, got %q", contentType))
	}
	boundary, ok := params["boundary"]
	if !ok {
		return nil, httpx.ErrBadRequest.Wrap(errors.New("multipart body has no boundary"))
	}
	if r.ContentLength > h.maxFile+(64<<10) {
		return nil, httpx.ErrPayloadTooLarge.Wrap(
			fmt.Errorf("content-length %d exceeds the attachment limit", r.ContentLength))
	}

	r.Body = http.MaxBytesReader(w, r.Body, h.maxFile+(64<<10))
	reader := multipart.NewReader(r.Body, boundary)
	for {
		part, err := reader.NextPart()
		if errors.Is(err, io.EOF) {
			return nil, httpx.Validation(map[string]string{"file": "Выберите файл для загрузки."})
		}
		if err != nil {
			return nil, httpx.ErrBadRequest.Wrap(fmt.Errorf("read multipart body: %w", err))
		}
		if part.FileName() == "" || part.FormName() != "file" {
			_ = part.Close()
			continue
		}
		return part, nil
	}
}

// uploadError maps the store's failures onto something a person can act on.
func uploadError(err error) error {
	switch {
	case errors.Is(err, files.ErrTooLarge):
		e := *httpx.ErrPayloadTooLarge
		e.Message = "Файл слишком большой для вложения. Предел — 25 МБ."
		return e.Wrap(err)
	case errors.Is(err, files.ErrTypeNotAllowed):
		e := *httpx.ErrUnsupportedMedia
		e.Message = "Такой тип файла приложить нельзя. Принимаются изображения, PDF, документы и zip-архивы."
		return e.Wrap(err)
	case errors.Is(err, files.ErrEmpty):
		return httpx.Validation(map[string]string{"file": "Файл пустой."}).Wrap(err)
	}
	return httpx.Internalf(err, "store attachment")
}

func pathID(r *http.Request, name string) (uuid.UUID, error) {
	parsed, err := uuid.Parse(r.PathValue(name))
	if err != nil {
		return uuid.Nil, httpx.ErrBadRequest.Wrap(
			fmt.Errorf("%s is not a valid identifier", name))
	}
	return parsed, nil
}
