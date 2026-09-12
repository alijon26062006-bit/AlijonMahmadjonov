package files

import (
	"errors"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/storage"
)

// Handlers serve stored objects.
//
// These routes exist for the filesystem driver, which is what development and
// a single-server deployment use. With S3 the public URL points at the bucket
// or the CDN and a private URL is signed by the provider, so nothing here is
// on the hot path — but the contract is identical either way, which is what
// lets the driver change without touching any caller.
type Handlers struct {
	blobs storage.Store
}

func NewHandlers(blobs storage.Store) *Handlers {
	return &Handlers{blobs: blobs}
}

func (h *Handlers) Register(r *httpx.Router) {
	// Public objects: avatars, portfolio screenshots, service covers. No
	// session, because these appear in lists a visitor loads by the dozen.
	r.GET("/files/public/{key...}", h.servePublic)
	// Private objects: the signature in the query string is the authorisation.
	// It was issued by an endpoint that had already checked entitlement, and
	// it expires.
	r.GET("/files/private/{key...}", h.servePrivate)
}

func (h *Handlers) servePublic(w http.ResponseWriter, r *http.Request) error {
	key := r.PathValue("key")
	if err := storage.ValidateKey(key); err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	// A public key contains random bytes, so the object at it never changes.
	w.Header().Set("Cache-Control", "public, max-age=31536000, immutable")
	return h.stream(w, r, key, storage.Public, "")
}

func (h *Handlers) servePrivate(w http.ResponseWriter, r *http.Request) error {
	key := r.PathValue("key")
	if err := storage.ValidateKey(key); err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}

	signer, ok := h.blobs.(storage.Signer)
	if !ok {
		// The configured driver signs its own URLs, so this route is not the
		// one that serves them.
		return httpx.ErrNotFound
	}

	expires, err := strconv.ParseInt(r.URL.Query().Get("expires"), 10, 64)
	if err != nil {
		return httpx.ErrForbidden.Wrap(errors.New("missing expiry"))
	}
	if err := signer.VerifySignature(key, expires, r.URL.Query().Get("signature")); err != nil {
		// Deliberately the same answer for an expired link and a forged one:
		// the difference is of no use to anybody but an attacker.
		e := *httpx.ErrForbidden
		e.Message = "This link has expired. Please reopen the page to get a new one."
		return e.Wrap(err)
	}

	// A private object must never be cached by a shared cache.
	w.Header().Set("Cache-Control", "private, no-store")
	return h.stream(w, r, key, storage.Private, r.URL.Query().Get("download"))
}

func (h *Handlers) stream(w http.ResponseWriter, r *http.Request, key string,
	visibility storage.Visibility, downloadName string) error {

	reader, object, err := h.blobs.Get(r.Context(), key, visibility)
	if errors.Is(err, storage.ErrNotFound) {
		return httpx.ErrNotFound
	}
	if err != nil {
		return httpx.Internalf(err, "read stored object")
	}
	defer reader.Close()

	contentType := object.ContentType
	if contentType == "" {
		contentType = "application/octet-stream"
	}
	w.Header().Set("Content-Type", contentType)
	// The browser must not sniff a different type out of the bytes: an upload
	// that somehow got past detection still cannot be executed as HTML.
	w.Header().Set("X-Content-Type-Options", "nosniff")
	// Nothing served from here is ever framed or scripted by us.
	w.Header().Set("Content-Security-Policy", "default-src 'none'; sandbox")
	if object.Size > 0 {
		w.Header().Set("Content-Length", strconv.FormatInt(object.Size, 10))
	}
	if !object.ModifiedAt.IsZero() {
		w.Header().Set("Last-Modified", object.ModifiedAt.UTC().Format(http.TimeFormat))
	}
	// Anything that is not an image is offered as a download rather than
	// rendered, which is the other half of not trusting an upload.
	disposition := "inline"
	if !strings.HasPrefix(contentType, "image/") {
		disposition = "attachment"
	}
	if downloadName != "" {
		w.Header().Set("Content-Disposition",
			fmt.Sprintf("%s; filename*=UTF-8''%s", disposition, urlEscape(downloadName)))
	} else {
		w.Header().Set("Content-Disposition", disposition)
	}

	w.WriteHeader(http.StatusOK)
	if r.Method == http.MethodHead {
		return nil
	}
	if _, err := io.Copy(w, reader); err != nil {
		// The status line is already out; there is nothing to tell the client
		// but the truncated body itself.
		return nil
	}
	return nil
}

// urlEscape percent-encodes a filename for the RFC 5987 form of
// Content-Disposition, so a name with a space or a non-ASCII character does
// not break the header.
func urlEscape(name string) string {
	var b strings.Builder
	for _, byteValue := range []byte(name) {
		switch {
		case byteValue >= 'a' && byteValue <= 'z',
			byteValue >= 'A' && byteValue <= 'Z',
			byteValue >= '0' && byteValue <= '9',
			byteValue == '.', byteValue == '-', byteValue == '_':
			b.WriteByte(byteValue)
		default:
			fmt.Fprintf(&b, "%%%02X", byteValue)
		}
	}
	return b.String()
}
