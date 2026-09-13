package identity

import (
	"context"
	"io"
	"mime"
	"mime/multipart"
	"net/http"
	"strconv"
	"strings"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

type Handlers struct{ svc *Service }

func NewHandlers(svc *Service) *Handlers { return &Handlers{svc: svc} }

type Middleware struct {
	Require         httpx.Middleware
	CSRF            httpx.Middleware
	RequireStaff    httpx.Middleware
	RateLimitUpload httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	// The owner's own case. Reading it needs nothing but a session; a person
	// may always see the state of their own verification.
	me := r.Group("/account/identity", mw.Require)
	me.GET("", h.mine)
	me.GET("/options", h.options)

	write := r.Group("/account/identity", mw.Require, mw.CSRF)
	write.POST("", h.saveDetails)
	write.POST("/documents", mw.RateLimitUpload(h.upload))
	write.POST("/submit", h.submit)

	// The reviewer's side. Every route below additionally requires the
	// identity permission and a recent password check — enforced in the
	// service, not here, so a new route cannot forget it.
	staff := r.Group("/admin/identity", mw.Require, mw.RequireStaff)
	staff.GET("/queue", h.queue)
	staff.GET("/reasons", h.reasons)
	staff.GET("/users/{userID}", h.forUser)
	staff.GET("/users/{userID}/access-log", h.accessLog)
	staff.GET("/cases/{id}/history", h.history)
	staff.GET("/documents/{docID}/file", h.stream)

	staffWrite := r.Group("/admin/identity", mw.Require, mw.RequireStaff, mw.CSRF)
	staffWrite.POST("/unlock", h.unlock)
	staffWrite.POST("/documents/{docID}/token", h.viewToken)
	staffWrite.POST("/cases/{id}/decide", h.decide)
}

// ── The owner ───────────────────────────────────────────────────────────────

func (h *Handlers) mine(w http.ResponseWriter, r *http.Request) error {
	out, err := h.svc.Mine(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}

// options tells the form what it may offer, so the list of document types
// lives in one place rather than being retyped in the web app.
func (h *Handlers) options(w http.ResponseWriter, r *http.Request) error {
	// The form itself is only for freelancers; so is the list it renders from.
	if err := requireFreelancer(security.FromContext(r.Context())); err != nil {
		return err
	}
	types := make([]map[string]any, 0, len(DocumentTypes))
	for _, t := range DocumentTypes {
		types = append(types, map[string]any{"key": t.Key, "label": t.Label, "needs_back": t.NeedsBack})
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{
		"document_types":       types,
		"selfie_with_document": h.svc.settings.Bool(r.Context(), "identity.selfie_with_document", false),
		"max_bytes":            maxDocumentBytes,
	})
}

func (h *Handlers) saveDetails(w http.ResponseWriter, r *http.Request) error {
	var body DetailsRequest
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	out, err := h.svc.SaveDetails(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) upload(w http.ResponseWriter, r *http.Request) error {
	kind, part, err := readSinglePart(w, r)
	if err != nil {
		return err
	}
	defer part.Close()

	out, err := h.svc.Upload(r.Context(), security.FromContext(r.Context()), kind, part)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusCreated, out)
}

// readSinglePart streams one multipart file without buffering it to disk, and
// takes the requested side from the form rather than from the filename.
func readSinglePart(w http.ResponseWriter, r *http.Request) (string, multipart.File, error) {
	mediaType, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if err != nil || !strings.HasPrefix(mediaType, "multipart/") {
		return "", nil, httpx.ErrUnsupportedMedia.Wrap(err)
	}
	r.Body = http.MaxBytesReader(w, r.Body, maxDocumentBytes+1<<20)
	if err := r.ParseMultipartForm(4 << 20); err != nil {
		return "", nil, httpx.ErrPayloadTooLarge.Wrap(err)
	}
	kind := strings.TrimSpace(r.FormValue("kind"))
	file, _, err := r.FormFile("file")
	if err != nil {
		return "", nil, httpx.Validation(map[string]string{"file": "Выберите изображение."})
	}
	return kind, file, nil
}

func (h *Handlers) submit(w http.ResponseWriter, r *http.Request) error {
	out, err := h.svc.SubmitForReview(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}

// ── The reviewer ────────────────────────────────────────────────────────────

func (h *Handlers) unlock(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Password string `json:"password"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 2<<10); err != nil {
		return err
	}
	until, err := h.svc.Unlock(withAgent(r), security.FromContext(r.Context()), body.Password)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"unlocked_until": until})
}

func (h *Handlers) queue(w http.ResponseWriter, r *http.Request) error {
	q := r.URL.Query()
	limit, _ := strconv.Atoi(q.Get("limit"))
	offset, _ := strconv.Atoi(q.Get("offset"))
	items, total, err := h.svc.Queue(withAgent(r), security.FromContext(r.Context()), QueueQuery{
		Status: strings.TrimSpace(q.Get("status")), Limit: limit, Offset: offset,
	})
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, items, map[string]any{"total": total, "offset": offset})
}

// reasons lists the closed set a reviewer may pick from, with which images
// each one is about.
func (h *Handlers) reasons(w http.ResponseWriter, r *http.Request) error {
	if err := h.svc.requireView(security.FromContext(r.Context())); err != nil {
		return err
	}
	out := make([]map[string]any, 0, len(ResubmitReasons))
	for _, reason := range ResubmitReasons {
		out = append(out, map[string]any{"key": reason.Key, "label": reason.Label, "kinds": reason.Kinds})
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) forUser(w http.ResponseWriter, r *http.Request) error {
	userID, err := uuid.Parse(r.PathValue("userID"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	out, err := h.svc.ForUser(withAgent(r), security.FromContext(r.Context()), userID)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) history(w http.ResponseWriter, r *http.Request) error {
	caseID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	out, err := h.svc.History(withAgent(r), security.FromContext(r.Context()), caseID)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) accessLog(w http.ResponseWriter, r *http.Request) error {
	userID, err := uuid.Parse(r.PathValue("userID"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	out, err := h.svc.AccessLog(withAgent(r), security.FromContext(r.Context()), userID, limit)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) viewToken(w http.ResponseWriter, r *http.Request) error {
	docID, err := uuid.Parse(r.PathValue("docID"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	var body struct {
		Reason string `json:"reason"`
	}
	if r.ContentLength != 0 {
		if err := httpx.DecodeJSON(w, r, &body, 2<<10); err != nil {
			return err
		}
	}
	out, err := h.svc.ViewToken(withAgent(r), security.FromContext(r.Context()), docID, strings.TrimSpace(body.Reason))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusCreated, out)
}

// stream serves the image itself.
//
// The response carries headers that keep it out of every cache along the way:
// a passport photograph must not survive in a proxy, a browser's disk cache or
// a back-button restore.
func (h *Handlers) stream(w http.ResponseWriter, r *http.Request) error {
	docID, err := uuid.Parse(r.PathValue("docID"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	body, contentType, err := h.svc.Stream(withAgent(r), security.FromContext(r.Context()),
		docID, strings.TrimSpace(r.URL.Query().Get("t")))
	if err != nil {
		return err
	}
	defer body.Close()

	w.Header().Set("Content-Type", contentType)
	w.Header().Set("Cache-Control", "no-store, no-cache, must-revalidate, private")
	w.Header().Set("Pragma", "no-cache")
	w.Header().Set("Content-Disposition", "inline")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	// Nothing on this response may be embedded anywhere else.
	w.Header().Set("Content-Security-Policy", "default-src 'none'; sandbox")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.WriteHeader(http.StatusOK)
	_, _ = io.Copy(w, body)
	return nil
}

func (h *Handlers) decide(w http.ResponseWriter, r *http.Request) error {
	caseID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	var body DecisionRequest
	if err := httpx.DecodeJSON(w, r, &body, 8<<10); err != nil {
		return err
	}
	out, err := h.svc.Decide(withAgent(r), security.FromContext(r.Context()), caseID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}

// withAgent carries the caller's browser into the access log without every
// handler repeating the plumbing.
func withAgent(r *http.Request) context.Context {
	return WithUserAgent(r.Context(), r.UserAgent())
}
