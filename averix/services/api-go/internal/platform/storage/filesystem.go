package storage

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/platform/cryptox"
)

// fsStore writes to the local disk. Development only — config.Load refuses
// S3_DRIVER=filesystem in production, because nothing here survives a container
// restart or works across replicas.
type fsStore struct {
	root      string
	baseURL   string
	signKey   []byte
	signedTTL time.Duration
}

func newFilesystem(cfg config.Storage) (Store, error) {
	root, err := filepath.Abs(cfg.Root)
	if err != nil {
		return nil, fmt.Errorf("resolve storage root: %w", err)
	}
	for _, vis := range []Visibility{Private, Public} {
		if err := os.MkdirAll(filepath.Join(root, string(vis)), 0o750); err != nil {
			return nil, fmt.Errorf("create storage directory: %w", err)
		}
	}
	// Signing key for local "signed" URLs. Random per process, so a link from a
	// previous run stops working — which is the behaviour a signed URL should
	// have anyway.
	key, err := cryptox.RandomHex(32)
	if err != nil {
		return nil, err
	}
	base := cfg.PublicBaseURL
	if base == "" {
		base = "/api/v1/files"
	}
	return &fsStore{
		root:      root,
		baseURL:   strings.TrimRight(base, "/"),
		signKey:   []byte(key),
		signedTTL: cfg.SignedURLTTL,
	}, nil
}

// resolve turns a key into an absolute path, refusing anything that escapes the
// visibility root even if ValidateKey somehow let it through.
func (f *fsStore) resolve(key string, vis Visibility) (string, error) {
	if err := ValidateKey(key); err != nil {
		return "", err
	}
	base := filepath.Join(f.root, string(vis))
	full := filepath.Join(base, filepath.FromSlash(key))
	rel, err := filepath.Rel(base, full)
	if err != nil || strings.HasPrefix(rel, "..") {
		return "", fmt.Errorf("storage key %q escapes its root", key)
	}
	return full, nil
}

func (f *fsStore) Put(ctx context.Context, key string, r io.Reader, size int64, opts PutOptions) (Object, error) {
	full, err := f.resolve(key, opts.Visibility)
	if err != nil {
		return Object{}, err
	}
	if err := os.MkdirAll(filepath.Dir(full), 0o750); err != nil {
		return Object{}, fmt.Errorf("create directory for %s: %w", key, err)
	}

	// Write to a temporary file and rename, so a failed upload never leaves a
	// partial object at a key the database already references.
	tmp, err := os.CreateTemp(filepath.Dir(full), ".upload-*")
	if err != nil {
		return Object{}, fmt.Errorf("create temp file: %w", err)
	}
	tmpName := tmp.Name()
	defer func() {
		_ = tmp.Close()
		_ = os.Remove(tmpName)
	}()

	written, err := io.Copy(tmp, r)
	if err != nil {
		return Object{}, fmt.Errorf("write %s: %w", key, err)
	}
	if err := tmp.Sync(); err != nil {
		return Object{}, fmt.Errorf("sync %s: %w", key, err)
	}
	if err := tmp.Close(); err != nil {
		return Object{}, fmt.Errorf("close %s: %w", key, err)
	}
	if err := os.Chmod(tmpName, 0o640); err != nil {
		return Object{}, fmt.Errorf("chmod %s: %w", key, err)
	}
	if err := os.Rename(tmpName, full); err != nil {
		return Object{}, fmt.Errorf("commit %s: %w", key, err)
	}

	// The content type belongs with the object; a sidecar keeps the filesystem
	// driver honest about what Get should report.
	_ = os.WriteFile(full+".type", []byte(opts.ContentType), 0o640)

	return Object{
		Key:         key,
		Size:        written,
		ContentType: opts.ContentType,
		ModifiedAt:  time.Now().UTC(),
	}, nil
}

func (f *fsStore) Get(ctx context.Context, key string, vis Visibility) (io.ReadCloser, Object, error) {
	full, err := f.resolve(key, vis)
	if err != nil {
		return nil, Object{}, err
	}
	file, err := os.Open(full)
	if errors.Is(err, os.ErrNotExist) {
		return nil, Object{}, ErrNotFound
	}
	if err != nil {
		return nil, Object{}, fmt.Errorf("open %s: %w", key, err)
	}
	info, err := file.Stat()
	if err != nil {
		_ = file.Close()
		return nil, Object{}, fmt.Errorf("stat %s: %w", key, err)
	}
	contentType := "application/octet-stream"
	if raw, err := os.ReadFile(full + ".type"); err == nil && len(raw) > 0 {
		contentType = string(raw)
	}
	return file, Object{
		Key:         key,
		Size:        info.Size(),
		ContentType: contentType,
		ModifiedAt:  info.ModTime(),
	}, nil
}

func (f *fsStore) Delete(ctx context.Context, key string, vis Visibility) error {
	full, err := f.resolve(key, vis)
	if err != nil {
		return err
	}
	_ = os.Remove(full + ".type")
	if err := os.Remove(full); err != nil && !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("delete %s: %w", key, err)
	}
	return nil
}

func (f *fsStore) Exists(ctx context.Context, key string, vis Visibility) (bool, error) {
	full, err := f.resolve(key, vis)
	if err != nil {
		return false, err
	}
	_, err = os.Stat(full)
	if errors.Is(err, os.ErrNotExist) {
		return false, nil
	}
	return err == nil, err
}

// SignedURL mirrors the S3 contract: a URL that expires and cannot be forged.
// The API's own file endpoint verifies the signature before streaming.
func (f *fsStore) SignedURL(ctx context.Context, key string, ttl time.Duration, downloadName string) (string, error) {
	if err := ValidateKey(key); err != nil {
		return "", err
	}
	if ttl <= 0 {
		ttl = f.signedTTL
	}
	expires := time.Now().Add(ttl).Unix()
	sig := f.sign(key, expires)
	q := url.Values{}
	q.Set("expires", strconv.FormatInt(expires, 10))
	q.Set("signature", sig)
	if downloadName != "" {
		q.Set("download", downloadName)
	}
	return fmt.Sprintf("%s/private/%s?%s", f.baseURL, key, q.Encode()), nil
}

// VerifySignature is used by the file endpoint under the filesystem driver.
func (f *fsStore) VerifySignature(key string, expires int64, signature string) error {
	if time.Now().Unix() > expires {
		return errors.New("signature has expired")
	}
	want := f.sign(key, expires)
	if !hmac.Equal([]byte(want), []byte(signature)) {
		return errors.New("signature does not match")
	}
	return nil
}

func (f *fsStore) sign(key string, expires int64) string {
	mac := hmac.New(sha256.New, f.signKey)
	fmt.Fprintf(mac, "%s\n%d", key, expires)
	return hex.EncodeToString(mac.Sum(nil))
}

func (f *fsStore) PublicURL(key string) string {
	return f.baseURL + "/public/" + key
}

func (f *fsStore) Health(ctx context.Context) error {
	probe := filepath.Join(f.root, ".health")
	if err := os.WriteFile(probe, []byte(time.Now().Format(time.RFC3339)), 0o640); err != nil {
		return fmt.Errorf("storage root is not writable: %w", err)
	}
	return os.Remove(probe)
}

func (f *fsStore) Driver() string { return "filesystem" }

// Signer is implemented by drivers whose signed URLs the API verifies itself.
type Signer interface {
	VerifySignature(key string, expires int64, signature string) error
}
