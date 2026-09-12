package developers

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"image"
	"io"
	"strconv"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/imaging"
	"github.com/averix/api/internal/platform/storage"
)

// Photo returns the current avatar as a ready-to-render source set.
//
// The database holds storage keys, not URLs: keys are what a delete needs, and
// a change of CDN hostname must not orphan every existing avatar. The public
// URL is derived here, on read.
func (s *Store) Photo(ctx context.Context, userID uuid.UUID, publicURL func(string) string) (*PhotoSet, error) {
	keys, placeholder, shape, err := s.photoKeys(ctx, userID)
	if err != nil || keys == nil {
		return nil, err
	}

	sources := map[string]map[string]string{}
	widest := 0
	for format, sizes := range keys {
		sources[format] = make(map[string]string, len(sizes))
		for size, key := range sizes {
			sources[format][size] = publicURL(key)
			if n, convErr := strconv.Atoi(size); convErr == nil && n > widest {
				widest = n
			}
		}
	}
	return &PhotoSet{
		Placeholder: placeholder,
		CropShape:   shape,
		Sources:     sources,
		Width:       widest,
	}, nil
}

func (s *Store) photoKeys(ctx context.Context, userID uuid.UUID) (map[string]map[string]string, string, string, error) {
	var (
		keys        map[string]map[string]string
		placeholder *string
		shape       string
	)
	err := s.db.QueryRow(ctx, `
		SELECT derivatives, placeholder, crop_shape
		FROM developer_photos
		WHERE user_id = $1 AND is_current AND moderation_state <> 'rejected'`,
		userID).Scan(&keys, &placeholder, &shape)
	if database.IsNoRows(err) {
		return nil, "", "", nil
	}
	if err != nil {
		return nil, "", "", fmt.Errorf("load photo: %w", err)
	}
	if len(keys) == 0 {
		return nil, "", "", nil
	}
	return keys, deref(placeholder), shape, nil
}

// PhotoRecord is a stored upload with its replayable crop geometry.
type PhotoRecord struct {
	ID          uuid.UUID
	UserID      uuid.UUID
	OriginalKey string
	OriginalW   int
	OriginalH   int
	Crop        imaging.Crop
	Derivatives map[string]map[string]string
	Placeholder string
	CreatedAt   time.Time
}

// CurrentPhotoRecord loads the geometry so the editor can be reopened on the
// existing crop rather than starting from the whole image again.
func (s *Store) CurrentPhotoRecord(ctx context.Context, userID uuid.UUID) (*PhotoRecord, error) {
	var r PhotoRecord
	var shape string
	err := s.db.QueryRow(ctx, `
		SELECT id, user_id, original_key, original_width, original_height,
		       crop_x, crop_y, crop_w, crop_h, rotation, crop_shape,
		       derivatives, coalesce(placeholder, ''), created_at
		FROM developer_photos
		WHERE user_id = $1 AND is_current`, userID).
		Scan(&r.ID, &r.UserID, &r.OriginalKey, &r.OriginalW, &r.OriginalH,
			&r.Crop.X, &r.Crop.Y, &r.Crop.W, &r.Crop.H, &r.Crop.Rotation, &shape,
			&r.Derivatives, &r.Placeholder, &r.CreatedAt)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("load photo record: %w", err)
	}
	r.Crop.Shape = imaging.CropShape(shape)
	return &r, nil
}

type savePhotoInput struct {
	UserID      uuid.UUID
	OriginalKey string
	Bytes       int64
	MIME        string
	Width       int
	Height      int
	Crop        imaging.Crop
	Derivatives map[string]map[string]string
	Placeholder string
}

// savePhoto replaces the current avatar in one transaction, returning the keys
// of the derivatives it superseded so the caller can delete them afterwards.
func (s *Store) savePhoto(ctx context.Context, in savePhotoInput) (uuid.UUID, []string, error) {
	var newID uuid.UUID
	var stale []string

	err := s.db.InTx(ctx, func(q database.Querier) error {
		rows, err := q.Query(ctx,
			`SELECT derivatives FROM developer_photos WHERE user_id = $1 AND is_current`, in.UserID)
		if err != nil {
			return fmt.Errorf("read previous photo: %w", err)
		}
		for rows.Next() {
			var prev map[string]map[string]string
			if err := rows.Scan(&prev); err != nil {
				rows.Close()
				return err
			}
			for _, sizes := range prev {
				for _, key := range sizes {
					stale = append(stale, key)
				}
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return err
		}

		// The unique index on (user_id) WHERE is_current means the old row has
		// to be stood down before the new one is inserted.
		if _, err := q.Exec(ctx,
			`UPDATE developer_photos SET is_current = false, updated_at = now()
			 WHERE user_id = $1 AND is_current`, in.UserID); err != nil {
			return fmt.Errorf("stand down previous photo: %w", err)
		}

		err = q.QueryRow(ctx, `
			INSERT INTO developer_photos
			  (user_id, original_key, original_bytes, original_mime,
			   original_width, original_height,
			   crop_x, crop_y, crop_w, crop_h, rotation, crop_shape,
			   derivatives, placeholder, is_current)
			VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,true)
			RETURNING id`,
			in.UserID, in.OriginalKey, in.Bytes, in.MIME, in.Width, in.Height,
			in.Crop.X, in.Crop.Y, in.Crop.W, in.Crop.H, in.Crop.Rotation,
			string(in.Crop.Shape), in.Derivatives, nullIfBlank(in.Placeholder)).
			Scan(&newID)
		if err != nil {
			return fmt.Errorf("insert photo: %w", err)
		}
		return nil
	})
	return newID, stale, err
}

// ── The photo pipeline ──────────────────────────────────────────────────────

// PhotoService turns an upload into the derivatives the product serves.
type PhotoService struct {
	store    *Store
	storage  storage.Store
	maxBytes int64
}

func NewPhotoService(store *Store, blobs storage.Store, maxBytes int64) *PhotoService {
	if maxBytes <= 0 {
		maxBytes = 10 << 20
	}
	return &PhotoService{store: store, storage: blobs, maxBytes: maxBytes}
}

var (
	ErrPhotoTooLarge   = errors.New("image is larger than the limit")
	ErrPhotoUnreadable = errors.New("image could not be read")
	ErrNoPhoto         = errors.New("no photo has been uploaded")
)

// UploadResult is what the client needs to open the crop editor.
type UploadResult struct {
	PhotoID uuid.UUID `json:"photo_id"`
	Width   int       `json:"width"`
	Height  int       `json:"height"`
	// A signed URL to the private original, so the editor can show the full
	// image while it is being cropped. It expires in minutes.
	EditURL string `json:"edit_url,omitempty"`
	// The crop the server applied by default, centred and square.
	Crop  CropView  `json:"crop"`
	Photo *PhotoSet `json:"photo"`
}

// CropView is the crop geometry in the shape the browser editor consumes.
// imaging.Crop is the internal representation and is not serialised directly,
// so the API's field names do not track an internal refactor.
type CropView struct {
	X        int    `json:"x"`
	Y        int    `json:"y"`
	Width    int    `json:"width"`
	Height   int    `json:"height"`
	Rotation int    `json:"rotation"`
	Shape    string `json:"shape"`
}

func cropView(c imaging.Crop) CropView {
	return CropView{
		X: c.X, Y: c.Y, Width: c.W, Height: c.H,
		Rotation: c.Rotation, Shape: string(c.Shape),
	}
}

// Upload stores the original privately and renders a default centred crop.
//
// The original is kept private and never served publicly: it may show more
// than the developer intended to publish, and keeping it is what allows a
// re-crop later without another upload.
func (p *PhotoService) Upload(ctx context.Context, userID uuid.UUID, r io.Reader, declaredMIME string) (*UploadResult, error) {
	// Read once into memory: the file is capped at 10 MiB, the format has to be
	// identified before decoding, and the bytes are needed twice (stored as the
	// original, and decoded for the derivatives).
	raw, err := io.ReadAll(io.LimitReader(r, p.maxBytes+1))
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrPhotoUnreadable, err)
	}
	if int64(len(raw)) > p.maxBytes {
		return nil, ErrPhotoTooLarge
	}

	img, det, err := imaging.Decode(bytes.NewReader(raw), p.maxBytes)
	if err != nil {
		return nil, err
	}

	// A square centred on the image is what the editor opens on, and what a
	// user who never touches the controls ends up with.
	side := min(det.Width, det.Height)
	crop := imaging.Crop{
		X:     (det.Width - side) / 2,
		Y:     (det.Height - side) / 2,
		W:     side,
		H:     side,
		Shape: imaging.Circle,
	}

	originalKey, err := storage.NewKey("avatar-original", userID.String(), det.Kind.Extension())
	if err != nil {
		return nil, fmt.Errorf("build storage key: %w", err)
	}
	if _, err := p.storage.Put(ctx, originalKey, bytes.NewReader(raw), int64(len(raw)),
		storage.PutOptions{
			ContentType: string(det.Kind),
			Visibility:  storage.Private,
			Metadata:    map[string]string{"averix-user": userID.String()},
		}); err != nil {
		return nil, fmt.Errorf("store original: %w", err)
	}

	set, photoID, err := p.render(ctx, userID, img, det, crop, originalKey, int64(len(raw)))
	if err != nil {
		// The original is orphaned rather than left dangling in the database.
		_ = p.storage.Delete(context.WithoutCancel(ctx), originalKey, storage.Private)
		return nil, err
	}

	editURL, err := p.storage.SignedURL(ctx, originalKey, 15*time.Minute, "")
	if err != nil {
		// Not fatal: the editor can fall back to the largest derivative.
		editURL = ""
	}

	return &UploadResult{
		PhotoID: photoID,
		Width:   det.Width,
		Height:  det.Height,
		EditURL: editURL,
		Crop:    cropView(crop),
		Photo:   set,
	}, nil
}

// Recrop re-renders the derivatives from the stored original.
//
// This is why the original is retained: adjusting a crop costs no upload and no
// quality, because it is always applied to the source rather than to a
// previously compressed derivative.
func (p *PhotoService) Recrop(ctx context.Context, userID uuid.UUID, crop imaging.Crop) (*PhotoSet, error) {
	record, err := p.store.CurrentPhotoRecord(ctx, userID)
	if errors.Is(err, ErrNotFound) {
		return nil, ErrNoPhoto
	}
	if err != nil {
		return nil, err
	}

	reader, obj, err := p.storage.Get(ctx, record.OriginalKey, storage.Private)
	if err != nil {
		return nil, fmt.Errorf("read stored original: %w", err)
	}
	defer reader.Close()

	img, det, err := imaging.Decode(reader, p.maxBytes)
	if err != nil {
		return nil, err
	}
	if err := crop.Validate(det.Width, det.Height); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrInvalidCrop, err)
	}

	set, _, err := p.render(ctx, userID, img, det, crop, record.OriginalKey, obj.Size)
	if err != nil {
		return nil, err
	}
	return set, nil
}

var ErrInvalidCrop = errors.New("crop is not valid for this image")

// render applies the crop, writes every derivative and records the result.
func (p *PhotoService) render(ctx context.Context, userID uuid.UUID, img image.Image,
	det imaging.Detected, crop imaging.Crop, originalKey string, originalBytes int64) (*PhotoSet, uuid.UUID, error) {

	cropped, err := imaging.Transform(img, crop)
	if err != nil {
		return nil, uuid.Nil, fmt.Errorf("%w: %v", ErrInvalidCrop, err)
	}

	derivatives, err := imaging.BuildAvatarSet(cropped, imaging.DefaultEncodeOptions())
	if err != nil {
		return nil, uuid.Nil, fmt.Errorf("render derivatives: %w", err)
	}

	// Derivatives are public: they are what appears on a profile, in search
	// results and on project cards, and making each one a signed request would
	// make a list of twenty developers twenty signature computations.
	sources := map[string]map[string]string{}
	written := make([]string, 0, len(derivatives))
	for _, d := range derivatives {
		format := "jpeg"
		if d.Format == imaging.WebP {
			format = "webp"
		}
		key, err := storage.NewKey("avatar", userID.String(), d.Format.Extension())
		if err != nil {
			p.cleanup(ctx, written)
			return nil, uuid.Nil, fmt.Errorf("build derivative key: %w", err)
		}
		if _, err := p.storage.Put(ctx, key, bytes.NewReader(d.Bytes), int64(len(d.Bytes)),
			storage.PutOptions{
				ContentType: string(d.Format),
				Visibility:  storage.Public,
			}); err != nil {
			p.cleanup(ctx, written)
			return nil, uuid.Nil, fmt.Errorf("store derivative: %w", err)
		}
		written = append(written, key)
		if sources[format] == nil {
			sources[format] = map[string]string{}
		}
		sources[format][strconv.Itoa(d.Width)] = key
	}

	photoID, stale, err := p.store.savePhoto(ctx, savePhotoInput{
		UserID:      userID,
		OriginalKey: originalKey,
		Bytes:       originalBytes,
		MIME:        string(det.Kind),
		Width:       det.Width,
		Height:      det.Height,
		Crop:        crop,
		Derivatives: sources,
		Placeholder: imaging.AverageColour(cropped),
	})
	if err != nil {
		p.cleanup(ctx, written)
		return nil, uuid.Nil, err
	}

	// Superseded derivatives are removed after the transaction commits, so a
	// failed write never deletes the photo that is still being served.
	p.cleanup(context.WithoutCancel(ctx), stale)

	widest := 0
	for _, d := range derivatives {
		if d.Width > widest {
			widest = d.Width
		}
	}
	urls := make(map[string]map[string]string, len(sources))
	for format, sizes := range sources {
		urls[format] = make(map[string]string, len(sizes))
		for size, key := range sizes {
			urls[format][size] = p.storage.PublicURL(key)
		}
	}
	return &PhotoSet{
		Placeholder: imaging.AverageColour(cropped),
		CropShape:   string(crop.Shape),
		Sources:     urls,
		Width:       widest,
	}, photoID, nil
}

func (p *PhotoService) cleanup(ctx context.Context, keys []string) {
	for _, key := range keys {
		_ = p.storage.Delete(ctx, key, storage.Public)
	}
}

// Remove deletes the avatar and its derivatives.
func (p *PhotoService) Remove(ctx context.Context, userID uuid.UUID) error {
	record, err := p.store.CurrentPhotoRecord(ctx, userID)
	if errors.Is(err, ErrNotFound) {
		return nil
	}
	if err != nil {
		return err
	}

	if _, err := p.store.db.Exec(ctx,
		`DELETE FROM developer_photos WHERE id = $1 AND user_id = $2`,
		record.ID, userID); err != nil {
		return fmt.Errorf("delete photo record: %w", err)
	}

	// The objects are removed on a detached context: the database row is
	// already gone, so a slow delete must not fail the request.
	bg := context.WithoutCancel(ctx)
	for _, sizes := range record.Derivatives {
		for _, key := range sizes {
			_ = p.storage.Delete(bg, key, storage.Public)
		}
	}
	_ = p.storage.Delete(bg, record.OriginalKey, storage.Private)
	return nil
}
