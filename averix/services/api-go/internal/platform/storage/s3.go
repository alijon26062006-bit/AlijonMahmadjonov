package storage

import (
	"context"
	"fmt"
	"io"
	"net/url"
	"strings"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"

	"github.com/averix/api/internal/config"
)

// s3Store talks to any S3-compatible endpoint: AWS, MinIO, Backblaze B2,
// Cloudflare R2, Hetzner Object Storage.
type s3Store struct {
	client        *minio.Client
	privateBucket string
	publicBucket  string
	publicBaseURL string
	signedTTL     time.Duration
}

func newS3(ctx context.Context, cfg config.Storage) (Store, error) {
	endpoint := strings.TrimPrefix(strings.TrimPrefix(cfg.Endpoint, "https://"), "http://")
	client, err := minio.New(endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(cfg.AccessKey, cfg.SecretKey, ""),
		Secure: cfg.UseSSL,
		Region: cfg.Region,
	})
	if err != nil {
		return nil, fmt.Errorf("create S3 client: %w", err)
	}

	s := &s3Store{
		client:        client,
		privateBucket: cfg.Bucket,
		publicBucket:  cfg.PublicBucket,
		publicBaseURL: cfg.PublicBaseURL,
		signedTTL:     cfg.SignedURLTTL,
	}

	// Create the buckets if they are missing, so a fresh deployment works
	// without a manual console step.
	checkCtx, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()
	for _, bucket := range []string{s.privateBucket, s.publicBucket} {
		exists, err := client.BucketExists(checkCtx, bucket)
		if err != nil {
			return nil, fmt.Errorf("check bucket %s: %w", bucket, err)
		}
		if !exists {
			if err := client.MakeBucket(checkCtx, bucket, minio.MakeBucketOptions{Region: cfg.Region}); err != nil {
				return nil, fmt.Errorf("create bucket %s: %w", bucket, err)
			}
		}
	}
	return s, nil
}

func (s *s3Store) bucket(vis Visibility) string {
	if vis == Public {
		return s.publicBucket
	}
	return s.privateBucket
}

func (s *s3Store) Put(ctx context.Context, key string, r io.Reader, size int64, opts PutOptions) (Object, error) {
	if err := ValidateKey(key); err != nil {
		return Object{}, err
	}
	putOpts := minio.PutObjectOptions{
		ContentType:  opts.ContentType,
		CacheControl: opts.CacheControl,
		UserMetadata: opts.Metadata,
	}
	if putOpts.ContentType == "" {
		putOpts.ContentType = "application/octet-stream"
	}
	if putOpts.CacheControl == "" {
		if opts.Visibility == Public {
			// Public keys carry random bytes, so the content at a key never
			// changes and can be cached for a year.
			putOpts.CacheControl = "public, max-age=31536000, immutable"
		} else {
			putOpts.CacheControl = "private, no-store"
		}
	}
	if opts.DownloadName != "" {
		putOpts.ContentDisposition = contentDisposition(opts.DownloadName)
	}

	info, err := s.client.PutObject(ctx, s.bucket(opts.Visibility), key, r, size, putOpts)
	if err != nil {
		return Object{}, fmt.Errorf("put object %s: %w", key, err)
	}
	return Object{
		Key:         key,
		Size:        info.Size,
		ContentType: putOpts.ContentType,
		ETag:        info.ETag,
		ModifiedAt:  time.Now().UTC(),
	}, nil
}

func (s *s3Store) Get(ctx context.Context, key string, vis Visibility) (io.ReadCloser, Object, error) {
	if err := ValidateKey(key); err != nil {
		return nil, Object{}, err
	}
	obj, err := s.client.GetObject(ctx, s.bucket(vis), key, minio.GetObjectOptions{})
	if err != nil {
		return nil, Object{}, fmt.Errorf("get object %s: %w", key, err)
	}
	stat, err := obj.Stat()
	if err != nil {
		_ = obj.Close()
		if minio.ToErrorResponse(err).Code == "NoSuchKey" {
			return nil, Object{}, ErrNotFound
		}
		return nil, Object{}, fmt.Errorf("stat object %s: %w", key, err)
	}
	return obj, Object{
		Key:         key,
		Size:        stat.Size,
		ContentType: stat.ContentType,
		ETag:        stat.ETag,
		ModifiedAt:  stat.LastModified,
	}, nil
}

func (s *s3Store) Delete(ctx context.Context, key string, vis Visibility) error {
	if err := ValidateKey(key); err != nil {
		return err
	}
	return s.client.RemoveObject(ctx, s.bucket(vis), key, minio.RemoveObjectOptions{})
}

func (s *s3Store) Exists(ctx context.Context, key string, vis Visibility) (bool, error) {
	if err := ValidateKey(key); err != nil {
		return false, err
	}
	_, err := s.client.StatObject(ctx, s.bucket(vis), key, minio.StatObjectOptions{})
	if err != nil {
		if minio.ToErrorResponse(err).Code == "NoSuchKey" {
			return false, nil
		}
		return false, err
	}
	return true, nil
}

func (s *s3Store) SignedURL(ctx context.Context, key string, ttl time.Duration, downloadName string) (string, error) {
	if err := ValidateKey(key); err != nil {
		return "", err
	}
	if ttl <= 0 {
		ttl = s.signedTTL
	}
	params := url.Values{}
	if downloadName != "" {
		params.Set("response-content-disposition", contentDisposition(downloadName))
	}
	u, err := s.client.PresignedGetObject(ctx, s.privateBucket, key, ttl, params)
	if err != nil {
		return "", fmt.Errorf("sign url for %s: %w", key, err)
	}
	return u.String(), nil
}

func (s *s3Store) PublicURL(key string) string {
	if s.publicBaseURL != "" {
		return s.publicBaseURL + "/" + key
	}
	scheme := "https"
	if !s.client.EndpointURL().IsAbs() {
		scheme = "http"
	}
	return fmt.Sprintf("%s://%s/%s/%s", scheme, s.client.EndpointURL().Host, s.publicBucket, key)
}

func (s *s3Store) Health(ctx context.Context) error {
	_, err := s.client.BucketExists(ctx, s.privateBucket)
	return err
}

func (s *s3Store) Driver() string { return "s3" }

// contentDisposition builds a header that cannot be used to inject other
// headers or to smuggle a different filename past the browser.
func contentDisposition(name string) string {
	clean := make([]rune, 0, len(name))
	for _, r := range name {
		switch {
		case r < 0x20 || r == 0x7f, r == '"', r == '\\', r == '/', r == ';':
			clean = append(clean, '_')
		default:
			clean = append(clean, r)
		}
	}
	safe := strings.TrimSpace(string(clean))
	if safe == "" {
		safe = "download"
	}
	if len(safe) > 120 {
		safe = safe[:120]
	}
	// RFC 5987 filename* carries the real name; the ASCII fallback keeps old
	// clients working.
	return fmt.Sprintf(`attachment; filename="%s"; filename*=UTF-8''%s`,
		asciiFallback(safe), url.PathEscape(safe))
}

func asciiFallback(s string) string {
	var b strings.Builder
	for _, r := range s {
		if r < 0x80 {
			b.WriteRune(r)
		} else {
			b.WriteByte('_')
		}
	}
	return b.String()
}
