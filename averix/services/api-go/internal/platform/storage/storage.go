// Package storage abstracts object storage behind one interface with an
// S3-compatible driver for real deployments and a filesystem driver for local
// development, so no module has to know which is in use.
package storage

import (
	"context"
	"errors"
	"fmt"
	"io"
	"path"
	"strings"
	"time"

	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/platform/cryptox"
)

// Visibility decides which bucket an object lands in and therefore whether it
// can be read without authorisation.
type Visibility string

const (
	// Private objects require a signed URL, issued only after an authorisation
	// check. Contract deliverables, message attachments, dispute evidence.
	Private Visibility = "private"
	// Public objects are CDN-cacheable. Profile photos, portfolio covers.
	Public Visibility = "public"
)

type Object struct {
	Key         string
	Size        int64
	ContentType string
	ETag        string
	ModifiedAt  time.Time
}

type PutOptions struct {
	ContentType string
	Visibility  Visibility
	// Cache-Control for the stored object. Public derivatives are immutable
	// because their key contains a random component.
	CacheControl string
	// Filename offered to a browser on download.
	DownloadName string
	Metadata     map[string]string
}

var ErrNotFound = errors.New("object not found")

type Store interface {
	Put(ctx context.Context, key string, r io.Reader, size int64, opts PutOptions) (Object, error)
	Get(ctx context.Context, key string, vis Visibility) (io.ReadCloser, Object, error)
	Delete(ctx context.Context, key string, vis Visibility) error
	Exists(ctx context.Context, key string, vis Visibility) (bool, error)
	// SignedURL returns a time-limited URL for a private object.
	SignedURL(ctx context.Context, key string, ttl time.Duration, downloadName string) (string, error)
	// PublicURL returns the stable URL of a public object.
	PublicURL(key string) string
	Health(ctx context.Context) error
	Driver() string
}

// NewKey builds a storage key.
//
// The key is composed from the purpose, a date shard and random bytes — never
// from the uploaded filename. An upload called "../../etc/passwd" or
// "avatar.php.jpg" therefore cannot influence where it is written or what it
// is served as. The original name is kept in the database for display only.
func NewKey(purpose, ownerID, extension string) (string, error) {
	rnd, err := cryptox.RandomHex(16)
	if err != nil {
		return "", err
	}
	ext := strings.ToLower(strings.TrimPrefix(extension, "."))
	if !safeExtension(ext) {
		ext = "bin"
	}
	// Shard by owner prefix and month so a bucket listing stays navigable.
	owner := "anon"
	if len(ownerID) >= 8 {
		owner = ownerID[:8]
	}
	return path.Join(
		sanitiseSegment(purpose),
		time.Now().UTC().Format("2006/01"),
		owner,
		rnd+"."+ext,
	), nil
}

// The complete set of extensions AVERIX will ever write. Anything else becomes
// ".bin", so a key can never end in an executable or script extension.
var allowedExtensions = map[string]struct{}{
	"jpg": {}, "jpeg": {}, "png": {}, "webp": {}, "avif": {}, "gif": {},
	"svg": {}, "pdf": {}, "zip": {}, "txt": {}, "md": {}, "csv": {},
	"json": {}, "log": {}, "docx": {}, "xlsx": {}, "pptx": {}, "mp4": {},
	"webm": {}, "bin": {},
}

func safeExtension(ext string) bool {
	if ext == "" || len(ext) > 5 {
		return false
	}
	_, ok := allowedExtensions[ext]
	return ok
}

func sanitiseSegment(s string) string {
	var b strings.Builder
	for _, r := range strings.ToLower(s) {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '-' || r == '_' {
			b.WriteRune(r)
		}
	}
	if b.Len() == 0 {
		return "misc"
	}
	return b.String()
}

// ValidateKey rejects a key that could escape its prefix. Every driver calls
// this before touching the backing store, so a key that somehow arrived from
// user input still cannot traverse.
func ValidateKey(key string) error {
	if key == "" {
		return errors.New("empty storage key")
	}
	if len(key) > 512 {
		return errors.New("storage key is too long")
	}
	if strings.HasPrefix(key, "/") || strings.Contains(key, "..") ||
		strings.Contains(key, "\\") || strings.ContainsAny(key, "\x00\n\r") {
		return fmt.Errorf("unsafe storage key %q", key)
	}
	if path.Clean(key) != key {
		return fmt.Errorf("storage key %q is not canonical", key)
	}
	return nil
}

// New builds the configured driver.
func New(ctx context.Context, cfg config.Storage) (Store, error) {
	switch cfg.Driver {
	case "s3":
		return newS3(ctx, cfg)
	case "filesystem":
		return newFilesystem(cfg)
	default:
		return nil, fmt.Errorf("unknown storage driver %q", cfg.Driver)
	}
}
