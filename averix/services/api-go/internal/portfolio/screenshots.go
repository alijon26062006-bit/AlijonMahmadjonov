package portfolio

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"strconv"

	"github.com/google/uuid"

	"github.com/averix/api/internal/files"
	"github.com/averix/api/internal/platform/imaging"
	"github.com/averix/api/internal/platform/logx"
	"github.com/averix/api/internal/platform/storage"
)

// Screenshots turns a screenshot upload into the sizes the product serves.
//
// The uploaded bytes are never served. Every image is decoded and re-encoded,
// which is both a compression decision (a 4 MB PNG screenshot becomes a
// ~120 KB WebP) and a security one: whatever else was in the container —
// a trailing payload, a colour profile, EXIF with a location — does not
// survive a re-encode.
type Screenshots struct {
	store    *Store
	files    *files.Store
	blobs    storage.Store
	maxBytes int64
}

func NewScreenshots(store *Store, fileStore *files.Store, blobs storage.Store, maxBytes int64) *Screenshots {
	if maxBytes <= 0 {
		maxBytes = 10 << 20
	}
	return &Screenshots{store: store, files: fileStore, blobs: blobs, maxBytes: maxBytes}
}

var (
	ErrImageTooLarge = errors.New("image is larger than the limit")
	ErrTooManyImages = errors.New("this project already has the maximum number of images")
)

// MaxImages per project. A gallery a visitor swipes through on a phone stops
// being read long before this.
const MaxImages = 12

type ScreenshotInput struct {
	DeveloperID  uuid.UUID
	ProjectID    uuid.UUID
	DeclaredName string
	DeclaredMIME string
	Caption      string
	AltText      string
	Reader       io.Reader
}

// Add stores one screenshot and attaches it to the project.
func (s *Screenshots) Add(ctx context.Context, in ScreenshotInput) (*Image, error) {
	count, err := s.store.CountImages(ctx, in.ProjectID, in.DeveloperID)
	if err != nil {
		return nil, err
	}
	if count >= MaxImages {
		return nil, ErrTooManyImages
	}

	// Read once: the format has to be identified from the bytes before
	// anything decodes them, and an over-size upload is rejected rather than
	// truncated.
	raw, err := io.ReadAll(io.LimitReader(in.Reader, s.maxBytes+1))
	if err != nil {
		return nil, fmt.Errorf("read screenshot: %w", err)
	}
	if int64(len(raw)) > s.maxBytes {
		return nil, ErrImageTooLarge
	}

	img, _, err := imaging.Decode(bytes.NewReader(raw), s.maxBytes)
	if err != nil {
		return nil, err
	}

	derivatives, err := imaging.BuildScreenshotSet(img, imaging.DefaultEncodeOptions())
	if err != nil {
		return nil, fmt.Errorf("render screenshot sizes: %w", err)
	}
	if len(derivatives) == 0 {
		return nil, fmt.Errorf("render screenshot sizes: no output")
	}

	// The largest WebP is the canonical file: it is the one recorded in
	// `files`, so an orphan sweep and a delete have a single row to work from.
	canonical := largest(derivatives, imaging.WebP)
	if canonical == nil {
		canonical = &derivatives[len(derivatives)-1]
	}

	file, err := s.files.Save(ctx, files.UploadInput{
		OwnerID: in.DeveloperID,
		Purpose: files.PurposePortfolio,
		// What the browser sent, kept for the record. The stored bytes are our
		// own re-encoded output, which is what detect() sees.
		DeclaredName: in.DeclaredName,
		DeclaredMIME: in.DeclaredMIME,
		Reader:       bytes.NewReader(canonical.Bytes),
	})
	if err != nil {
		return nil, err
	}

	// The remaining sizes are plain objects rather than `files` rows: they are
	// derived output, they are deleted with the image, and giving each one a
	// row would put four extra entries in every orphan sweep.
	sources := map[string]map[string]string{}
	written := []string{}
	put := func(format string, width int, key string) {
		if sources[format] == nil {
			sources[format] = map[string]string{}
		}
		sources[format][strconv.Itoa(width)] = key
	}
	put(formatName(canonical.Format), canonical.Width, file.StorageKey())

	for i := range derivatives {
		d := &derivatives[i]
		if d == canonical {
			continue
		}
		key, err := storage.NewKey("portfolio", in.DeveloperID.String(), d.Format.Extension())
		if err != nil {
			s.rollback(ctx, file.ID, in.DeveloperID, written)
			return nil, fmt.Errorf("build derivative key: %w", err)
		}
		if _, err := s.blobs.Put(ctx, key, bytes.NewReader(d.Bytes), int64(len(d.Bytes)),
			storage.PutOptions{
				ContentType: string(d.Format),
				Visibility:  storage.Public,
				// The key carries random bytes, so the object at it never
				// changes and may be cached for as long as anyone likes.
				CacheControl: "public, max-age=31536000, immutable",
			}); err != nil {
			s.rollback(ctx, file.ID, in.DeveloperID, written)
			return nil, fmt.Errorf("store derivative: %w", err)
		}
		written = append(written, key)
		put(formatName(d.Format), d.Width, key)
	}

	placeholder := imaging.AverageColour(img)
	imageID, err := s.store.AddImage(ctx, in.ProjectID, in.DeveloperID, file.ID,
		in.Caption, in.AltText, placeholder, sources)
	if err != nil {
		s.rollback(ctx, file.ID, in.DeveloperID, written)
		return nil, err
	}

	width, height := canonical.Width, canonical.Height
	return &Image{
		ID:          imageID,
		FileID:      file.ID,
		URL:         file.URL,
		Caption:     in.Caption,
		AltText:     in.AltText,
		Position:    count,
		Width:       &width,
		Height:      &height,
		Placeholder: placeholder,
		Variants:    s.store.variants(sources),
	}, nil
}

// Remove detaches an image and deletes every object behind it.
func (s *Screenshots) Remove(ctx context.Context, imageID, developerID uuid.UUID) error {
	keys, err := s.store.DerivativeKeys(ctx, imageID)
	if err != nil {
		return err
	}
	fileID, err := s.store.RemoveImage(ctx, imageID, developerID)
	if err != nil {
		return err
	}
	// The row is gone, so the objects are unreachable either way; a storage
	// failure here is a cleanup problem, not a request failure.
	if err := s.files.Delete(ctx, fileID, developerID); err != nil {
		logx.From(ctx).Warn("portfolio: could not delete screenshot file",
			"file_id", fileID, "error", err)
	}
	s.deleteObjects(ctx, keys)
	return nil
}

// rollback undoes a partial upload so a failure halfway through does not leave
// objects nothing points at.
func (s *Screenshots) rollback(ctx context.Context, fileID, ownerID uuid.UUID, keys []string) {
	detached := context.WithoutCancel(ctx)
	if err := s.files.Delete(detached, fileID, ownerID); err != nil {
		logx.From(ctx).Warn("portfolio: could not roll back screenshot file",
			"file_id", fileID, "error", err)
	}
	s.deleteObjects(detached, keys)
}

func (s *Screenshots) deleteObjects(ctx context.Context, keys []string) {
	for _, key := range keys {
		if err := s.blobs.Delete(context.WithoutCancel(ctx), key, storage.Public); err != nil {
			logx.From(ctx).Warn("portfolio: could not delete screenshot derivative",
				"key", key, "error", err)
		}
	}
}

// largest returns the widest derivative in one format.
func largest(derivatives []imaging.Derivative, format imaging.Kind) *imaging.Derivative {
	var best *imaging.Derivative
	for i := range derivatives {
		d := &derivatives[i]
		if d.Format != format {
			continue
		}
		if best == nil || d.Width > best.Width {
			best = d
		}
	}
	return best
}

func formatName(k imaging.Kind) string {
	if k == imaging.WebP {
		return "webp"
	}
	return "jpeg"
}
