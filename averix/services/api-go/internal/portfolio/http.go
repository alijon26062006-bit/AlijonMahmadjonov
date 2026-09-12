package portfolio

import (
	"errors"
	"fmt"
	"io"
	"mime"
	"mime/multipart"
	"net/http"
	"strings"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

type Handlers struct {
	svc      *Service
	maxImage int64
}

func NewHandlers(svc *Service, maxImageBytes int64) *Handlers {
	if maxImageBytes <= 0 {
		maxImageBytes = 10 << 20
	}
	return &Handlers{svc: svc, maxImage: maxImageBytes}
}

type Middleware struct {
	Require         httpx.Middleware
	CSRF            httpx.Middleware
	RequireDev      httpx.Middleware
	RateLimitUpload httpx.Middleware
	RateLimitProbe  httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	// Public: a portfolio is the page a client lands on from a shared link, so
	// it reads without a session. The service decides what a visitor may see.
	pub := r.Group("/developers")
	pub.GET("/{username}/portfolio", h.list)
	pub.GET("/{username}/portfolio/{slug}", h.view)
	// The in-app browser's instructions. A GET because it is a read of one
	// project's already-stored, already-validated link.
	pub.GET("/{username}/portfolio/{slug}/preview", h.preview)

	me := r.Group("/portfolio", mw.Require, mw.RequireDev)
	me.GET("", h.mine)
	me.GET("/{id}", h.owned)

	write := r.Group("/portfolio", mw.Require, mw.RequireDev, mw.CSRF)
	write.POST("", h.create)
	write.PATCH("/{id}", h.update)
	write.DELETE("/{id}", h.remove)
	write.POST("/{id}/publish", h.publish)
	write.PUT("/order", h.reorder)

	write.POST("/{id}/images", mw.RateLimitUpload(h.addImage))
	write.PUT("/{id}/images/order", h.reorderImages)
	write.PUT("/{id}/cover", h.setCover)
	write.DELETE("/images/{imageID}", h.removeImage)

	write.POST("/{id}/links", h.addLink)
	write.DELETE("/links/{linkID}", h.removeLink)

	// Probing costs an outbound request, so it is limited well below the
	// general write allowance.
	write.POST("/{id}/check-url", mw.RateLimitProbe(h.checkURL))
}

// ── Public ──────────────────────────────────────────────────────────────────

func (h *Handlers) list(w http.ResponseWriter, r *http.Request) error {
	cards, err := h.svc.ForUsername(r.Context(), security.FromContext(r.Context()),
		r.PathValue("username"))
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, cards, map[string]any{"count": len(cards)})
}

func (h *Handlers) view(w http.ResponseWriter, r *http.Request) error {
	project, err := h.svc.View(r.Context(), security.FromContext(r.Context()),
		r.PathValue("username"), r.PathValue("slug"))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, project)
}

func (h *Handlers) preview(w http.ResponseWriter, r *http.Request) error {
	response, err := h.svc.Preview(r.Context(), security.FromContext(r.Context()),
		r.PathValue("username"), r.PathValue("slug"))
	if err != nil {
		return err
	}
	// The frame instructions are per-visitor only in that the reason is
	// withheld; the verdict itself is shared, so a short cache is safe and
	// keeps a popular profile from re-probing on every open.
	w.Header().Set("Cache-Control", "private, max-age=60")
	return httpx.JSON(w, http.StatusOK, response)
}

// ── The developer's own portfolio ───────────────────────────────────────────

func (h *Handlers) mine(w http.ResponseWriter, r *http.Request) error {
	cards, err := h.svc.Mine(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, cards, map[string]any{
		"count": len(cards), "max": MaxProjects,
	})
}

func (h *Handlers) owned(w http.ResponseWriter, r *http.Request) error {
	projectID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	project, err := h.svc.Owned(r.Context(), security.FromContext(r.Context()), projectID)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, project)
}

func (h *Handlers) create(w http.ResponseWriter, r *http.Request) error {
	var body SaveRequest
	if err := httpx.DecodeJSON(w, r, &body, 32<<10); err != nil {
		return err
	}
	project, err := h.svc.Create(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusCreated, project)
}

func (h *Handlers) update(w http.ResponseWriter, r *http.Request) error {
	projectID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body SaveRequest
	if err := httpx.DecodeJSON(w, r, &body, 32<<10); err != nil {
		return err
	}
	project, err := h.svc.Update(r.Context(), security.FromContext(r.Context()), projectID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, project)
}

func (h *Handlers) publish(w http.ResponseWriter, r *http.Request) error {
	projectID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body struct {
		Published *bool `json:"published"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 1<<10); err != nil {
		return err
	}
	published := true
	if body.Published != nil {
		published = *body.Published
	}
	project, err := h.svc.SetPublished(r.Context(), security.FromContext(r.Context()),
		projectID, published)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, project)
}

func (h *Handlers) remove(w http.ResponseWriter, r *http.Request) error {
	projectID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	if err := h.svc.Delete(r.Context(), security.FromContext(r.Context()), projectID); err != nil {
		return err
	}
	return httpx.NoContent(w)
}

func (h *Handlers) reorder(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Order []string `json:"order"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 8<<10); err != nil {
		return err
	}
	if err := h.svc.Reorder(r.Context(), security.FromContext(r.Context()), body.Order); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"ordered": len(body.Order)})
}

// ── Images ──────────────────────────────────────────────────────────────────

func (h *Handlers) addImage(w http.ResponseWriter, r *http.Request) error {
	projectID, err := pathID(r, "id")
	if err != nil {
		return err
	}

	part, fields, err := h.readImagePart(w, r)
	if err != nil {
		return err
	}
	defer part.Close()

	image, err := h.svc.AddImage(r.Context(), security.FromContext(r.Context()), ScreenshotInput{
		ProjectID:    projectID,
		DeclaredName: part.FileName(),
		DeclaredMIME: part.Header.Get("Content-Type"),
		Caption:      fields["caption"],
		AltText:      fields["alt_text"],
		Reader:       part,
	})
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusCreated, image)
}

func (h *Handlers) removeImage(w http.ResponseWriter, r *http.Request) error {
	imageID, err := pathID(r, "imageID")
	if err != nil {
		return err
	}
	if err := h.svc.RemoveImage(r.Context(), security.FromContext(r.Context()), imageID); err != nil {
		return err
	}
	return httpx.NoContent(w)
}

func (h *Handlers) reorderImages(w http.ResponseWriter, r *http.Request) error {
	projectID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body struct {
		Order []string `json:"order"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 8<<10); err != nil {
		return err
	}
	if err := h.svc.ReorderImages(r.Context(), security.FromContext(r.Context()),
		projectID, body.Order); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"ordered": len(body.Order)})
}

func (h *Handlers) setCover(w http.ResponseWriter, r *http.Request) error {
	projectID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body struct {
		ImageID string `json:"image_id"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 1<<10); err != nil {
		return err
	}
	imageID, err := uuid.Parse(strings.TrimSpace(body.ImageID))
	if err != nil {
		return httpx.Validation(map[string]string{"image_id": "That image reference isn't valid."})
	}
	project, err := h.svc.SetCover(r.Context(), security.FromContext(r.Context()), projectID, imageID)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, project)
}

// ── Links and the URL check ─────────────────────────────────────────────────

func (h *Handlers) addLink(w http.ResponseWriter, r *http.Request) error {
	projectID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body LinkRequest
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	link, err := h.svc.AddLink(r.Context(), security.FromContext(r.Context()), projectID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusCreated, link)
}

func (h *Handlers) removeLink(w http.ResponseWriter, r *http.Request) error {
	linkID, err := pathID(r, "linkID")
	if err != nil {
		return err
	}
	if err := h.svc.RemoveLink(r.Context(), security.FromContext(r.Context()), linkID); err != nil {
		return err
	}
	return httpx.NoContent(w)
}

// checkURL re-probes the project's own stored link.
//
// Deliberately no URL in the body: an endpoint that fetches whatever address
// it is handed is an SSRF proxy, however carefully the address is validated.
// The only thing probed is what the developer already saved.
func (h *Handlers) checkURL(w http.ResponseWriter, r *http.Request) error {
	projectID, err := pathID(r, "id")
	if err != nil {
		return err
	}
	result, err := h.svc.CheckURL(r.Context(), security.FromContext(r.Context()), projectID)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, result)
}

// ── Helpers ─────────────────────────────────────────────────────────────────

func pathID(r *http.Request, name string) (uuid.UUID, error) {
	parsed, err := uuid.Parse(r.PathValue(name))
	if err != nil {
		return uuid.Nil, httpx.ErrBadRequest.Wrap(
			fmt.Errorf("%s is not a valid identifier", name))
	}
	return parsed, nil
}

// readImagePart streams the file part out of a multipart body and collects the
// small text fields that came with it.
//
// multipart.Reader rather than r.FormFile: FormFile spools the whole upload to
// a temporary file before anything has decided whether the format is even
// acceptable.
func (h *Handlers) readImagePart(w http.ResponseWriter, r *http.Request) (*multipart.Part, map[string]string, error) {
	contentType := r.Header.Get("Content-Type")
	mediaType, params, err := mime.ParseMediaType(contentType)
	if err != nil || !strings.HasPrefix(mediaType, "multipart/form-data") {
		return nil, nil, httpx.ErrUnsupportedMedia.Wrap(
			fmt.Errorf("expected multipart/form-data, got %q", contentType))
	}
	boundary, ok := params["boundary"]
	if !ok {
		return nil, nil, httpx.ErrBadRequest.Wrap(errors.New("multipart body has no boundary"))
	}
	if r.ContentLength > h.maxImage+(64<<10) {
		return nil, nil, httpx.ErrPayloadTooLarge.Wrap(
			fmt.Errorf("content-length %d exceeds the image limit", r.ContentLength))
	}

	r.Body = http.MaxBytesReader(w, r.Body, h.maxImage+(64<<10))
	reader := multipart.NewReader(r.Body, boundary)

	fields := map[string]string{}
	for {
		part, err := reader.NextPart()
		if errors.Is(err, io.EOF) {
			return nil, nil, httpx.Validation(map[string]string{
				"image": "Choose an image to upload.",
			})
		}
		if err != nil {
			return nil, nil, httpx.ErrBadRequest.Wrap(fmt.Errorf("read multipart body: %w", err))
		}
		// The text fields are read before the file, which is how a client is
		// expected to order them; anything after the file is ignored because
		// the file is streamed straight into the pipeline.
		if part.FileName() == "" {
			name := part.FormName()
			if name == "caption" || name == "alt_text" {
				value, err := io.ReadAll(io.LimitReader(part, 1<<10))
				if err == nil {
					fields[name] = strings.TrimSpace(string(value))
				}
			}
			_ = part.Close()
			continue
		}
		if part.FormName() != "image" {
			_ = part.Close()
			continue
		}
		return part, fields, nil
	}
}
