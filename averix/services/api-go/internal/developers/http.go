package developers

import (
	"errors"
	"fmt"
	"io"
	"mime"
	"mime/multipart"
	"net/http"
	"strings"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/imaging"
	"github.com/averix/api/internal/security"
)

type Handlers struct {
	svc      *Service
	photos   *PhotoService
	maxPhoto int64
}

// Middleware bundles the auth middleware this module needs, so the module does
// not depend on the auth package directly.
type Middleware struct {
	Require         httpx.Middleware
	CSRF            httpx.Middleware
	RequireDev      httpx.Middleware
	RateLimitUpload httpx.Middleware
}

func NewHandlers(svc *Service, photos *PhotoService, maxPhotoBytes int64) *Handlers {
	return &Handlers{svc: svc, photos: photos, maxPhoto: maxPhotoBytes}
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	// The public profile is anonymous-readable: it is the page a client lands
	// on from search or from a shared link.
	pub := r.Group("/developers")
	pub.GET("/{username}", h.publicProfile)

	me := r.Group("/developers/me", mw.Require, mw.RequireDev, mw.CSRF)
	me.GET("", h.me)
	me.PUT("/basics", h.saveBasics)
	me.PUT("/specialisation", h.saveSpecialisation)
	me.PUT("/additional-specialisations", h.saveAdditionalSpecialisations)
	me.PUT("/technologies", h.saveTechnologies)
	me.PUT("/experience", h.saveExperience)
	me.PUT("/availability", h.saveAvailability)
	me.PUT("/bio", h.saveBio)
	me.POST("/finish", h.finish)
	me.PUT("/visibility", h.setVisibility)

	// Uploads are multipart rather than JSON and are rate limited separately:
	// each one costs image decoding and several object writes.
	me.POST("/photo", mw.RateLimitUpload(h.uploadPhoto))
	me.PUT("/photo/crop", h.recropPhoto)
	me.DELETE("/photo", h.deletePhoto)
}

func (h *Handlers) me(w http.ResponseWriter, r *http.Request) error {
	profile, err := h.svc.Me(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, profile)
}

func (h *Handlers) publicProfile(w http.ResponseWriter, r *http.Request) error {
	username := r.PathValue("username")
	profile, err := h.svc.Public(r.Context(), username, security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	// A public profile is the same for every anonymous visitor, so it may be
	// cached briefly at the edge. The Vary on Cookie in SecurityHeaders keeps a
	// signed-in variant (with is_saved) from being served to someone else.
	if !security.FromContext(r.Context()).Authenticated() {
		w.Header().Set("Cache-Control", "public, max-age=60, stale-while-revalidate=300")
	}
	return httpx.JSON(w, http.StatusOK, profile)
}

func (h *Handlers) saveBasics(w http.ResponseWriter, r *http.Request) error {
	var body BasicsRequest
	if err := httpx.DecodeJSON(w, r, &body, 8<<10); err != nil {
		return err
	}
	res, err := h.svc.SaveBasics(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, res)
}

func (h *Handlers) saveSpecialisation(w http.ResponseWriter, r *http.Request) error {
	var body SpecialisationRequest
	if err := httpx.DecodeJSON(w, r, &body, 2<<10); err != nil {
		return err
	}
	res, err := h.svc.SavePrimarySpecialisation(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, res)
}

func (h *Handlers) saveAdditionalSpecialisations(w http.ResponseWriter, r *http.Request) error {
	var body AdditionalSpecialisationsRequest
	if err := httpx.DecodeJSON(w, r, &body, 2<<10); err != nil {
		return err
	}
	res, err := h.svc.SaveAdditionalSpecialisations(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, res)
}

func (h *Handlers) saveTechnologies(w http.ResponseWriter, r *http.Request) error {
	var body TechnologyRequest
	if err := httpx.DecodeJSON(w, r, &body, 8<<10); err != nil {
		return err
	}
	res, err := h.svc.SaveTechnologies(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, res)
}

func (h *Handlers) saveExperience(w http.ResponseWriter, r *http.Request) error {
	var body ExperienceRequest
	if err := httpx.DecodeJSON(w, r, &body, 2<<10); err != nil {
		return err
	}
	res, err := h.svc.SaveExperience(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, res)
}

func (h *Handlers) saveAvailability(w http.ResponseWriter, r *http.Request) error {
	var body AvailabilityRequest
	if err := httpx.DecodeJSON(w, r, &body, 2<<10); err != nil {
		return err
	}
	res, err := h.svc.SaveAvailability(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, res)
}

func (h *Handlers) saveBio(w http.ResponseWriter, r *http.Request) error {
	var body BioRequest
	if err := httpx.DecodeJSON(w, r, &body, 16<<10); err != nil {
		return err
	}
	res, err := h.svc.SaveBio(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, res)
}

func (h *Handlers) finish(w http.ResponseWriter, r *http.Request) error {
	profile, err := h.svc.Finish(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, profile)
}

func (h *Handlers) setVisibility(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Searchable bool `json:"searchable"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 1<<10); err != nil {
		return err
	}
	if err := h.svc.SetVisibility(r.Context(), security.FromContext(r.Context()), body.Searchable); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"searchable": body.Searchable})
}

// ── Photo ───────────────────────────────────────────────────────────────────

func (h *Handlers) uploadPhoto(w http.ResponseWriter, r *http.Request) error {
	id := security.FromContext(r.Context())

	part, declaredMIME, err := h.readSinglePart(w, r, "photo")
	if err != nil {
		return err
	}
	defer part.Close()

	result, err := h.photos.Upload(r.Context(), id.UserID, part, declaredMIME)
	if err != nil {
		return photoError(err)
	}
	return httpx.JSON(w, http.StatusCreated, result)
}

func (h *Handlers) recropPhoto(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		X        int    `json:"x"`
		Y        int    `json:"y"`
		Width    int    `json:"width"`
		Height   int    `json:"height"`
		Rotation int    `json:"rotation"`
		Shape    string `json:"shape"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 1<<10); err != nil {
		return err
	}

	shape := imaging.CropShape(strings.ToLower(strings.TrimSpace(body.Shape)))
	if shape != imaging.Circle && shape != imaging.Rounded {
		shape = imaging.Circle
	}

	id := security.FromContext(r.Context())
	set, err := h.photos.Recrop(r.Context(), id.UserID, imaging.Crop{
		X: body.X, Y: body.Y, W: body.Width, H: body.Height,
		Rotation: body.Rotation, Shape: shape,
	})
	if err != nil {
		return photoError(err)
	}
	return httpx.JSON(w, http.StatusOK, set)
}

func (h *Handlers) deletePhoto(w http.ResponseWriter, r *http.Request) error {
	id := security.FromContext(r.Context())
	if err := h.photos.Remove(r.Context(), id.UserID); err != nil {
		return httpx.Internalf(err, "remove photo")
	}
	return httpx.NoContent(w)
}

// readSinglePart streams one named file part out of a multipart body without
// buffering the whole request.
//
// multipart.Reader is used rather than r.FormFile because FormFile spools the
// entire upload to a temporary file first, and a stream that is going to be
// rejected for being the wrong format should be rejected before it is written
// anywhere.
func (h *Handlers) readSinglePart(w http.ResponseWriter, r *http.Request, field string) (io.ReadCloser, string, error) {
	contentType := r.Header.Get("Content-Type")
	mediaType, params, err := mime.ParseMediaType(contentType)
	if err != nil || !strings.HasPrefix(mediaType, "multipart/form-data") {
		return nil, "", httpx.ErrUnsupportedMedia.Wrap(
			fmt.Errorf("expected multipart/form-data, got %q", contentType))
	}
	boundary, ok := params["boundary"]
	if !ok {
		return nil, "", httpx.ErrBadRequest.Wrap(errors.New("multipart body has no boundary"))
	}
	if r.ContentLength > h.maxPhoto+(64<<10) {
		return nil, "", httpx.ErrPayloadTooLarge.Wrap(
			fmt.Errorf("content-length %d exceeds the image limit", r.ContentLength))
	}

	r.Body = http.MaxBytesReader(w, r.Body, h.maxPhoto+(64<<10))
	reader := multipart.NewReader(r.Body, boundary)

	for {
		part, err := reader.NextPart()
		if errors.Is(err, io.EOF) {
			return nil, "", httpx.Validation(map[string]string{
				field: "Choose an image to upload.",
			})
		}
		if err != nil {
			return nil, "", httpx.ErrBadRequest.Wrap(fmt.Errorf("read multipart body: %w", err))
		}
		if part.FormName() != field {
			_ = part.Close()
			continue
		}
		if part.FileName() == "" {
			_ = part.Close()
			return nil, "", httpx.Validation(map[string]string{field: "Choose an image file."})
		}
		// The declared type is carried through for the record but is never
		// trusted: imaging.Inspect decides what the file actually is.
		return part, part.Header.Get("Content-Type"), nil
	}
}

// photoError maps the pipeline's failures onto messages a person can act on.
func photoError(err error) error {
	switch {
	case errors.Is(err, ErrPhotoTooLarge):
		e := *httpx.ErrPayloadTooLarge
		e.Message = "That image is too large. Please choose one under 10 MB."
		return &e
	case errors.Is(err, imaging.ErrUnsupportedFormat):
		e := *httpx.ErrUnsupportedMedia
		e.Message = "That image format isn't supported. Please use a JPEG, PNG or WebP file."
		return e.Wrap(err)
	case errors.Is(err, imaging.ErrNotAnImage):
		e := *httpx.ErrUnsupportedMedia
		e.Message = "That file isn't an image."
		return e.Wrap(err)
	case errors.Is(err, imaging.ErrDimensions):
		return httpx.Validation(map[string]string{
			"photo": "That image is either too small or too large. Please use one between 16 and 12000 pixels on each side.",
		}).Wrap(err)
	case errors.Is(err, imaging.ErrDecompressionBomb):
		e := *httpx.ErrUnsupportedMedia
		e.Message = "That image couldn't be processed."
		return e.Wrap(err)
	case errors.Is(err, ErrInvalidCrop):
		return httpx.Validation(map[string]string{
			"crop": "That crop doesn't fit inside the image. Please adjust it and try again.",
		}).Wrap(err)
	case errors.Is(err, ErrNoPhoto):
		e := *httpx.ErrNotFound
		e.Message = "There's no photo to adjust yet. Upload one first."
		return e.Wrap(err)
	case errors.Is(err, ErrPhotoUnreadable):
		e := *httpx.ErrBadRequest
		e.Message = "We couldn't read that file. Please try uploading it again."
		return e.Wrap(err)
	}
	return httpx.Internalf(err, "process photo")
}
